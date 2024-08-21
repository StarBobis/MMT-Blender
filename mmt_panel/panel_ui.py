import os
import bpy
import json

from .panel_functions import *

from ..migoto.migoto_export import *
from ..migoto.migoto_import import *

mmt_version = "V1.0.5.7"


# -----------------------------------下面这两个不属于右键菜单，属于MMT面板，所以放到最下面---------------------------------------
class MMTImportAllTextModel(bpy.types.Operator):
    bl_idname = "mmt.import_all"
    bl_label = "Import all .ib .vb model from current OutputFolder"

    def execute(self, context):
        # 首先根据MMT路径，获取
        mmt_path = bpy.context.scene.mmt_props.path
        current_game = ""
        main_setting_path = os.path.join(context.scene.mmt_props.path, "Configs\\Main.json")
        if os.path.exists(main_setting_path):
            main_setting_file = open(main_setting_path)
            main_setting_json = json.load(main_setting_file)
            main_setting_file.close()
            current_game = main_setting_json["GameName"]

        game_config_path = os.path.join(context.scene.mmt_props.path, "Games\\" + current_game + "\\Config.json")
        game_config_file = open(game_config_path)
        game_config_json = json.load(game_config_file)
        game_config_file.close()

        output_folder_path = mmt_path + "Games\\" + current_game + "\\3Dmigoto\\Mods\\output\\"

        # 这里是根据Config.json中的DrawIB来决定导入时导入具体哪个IB
        import_folder_path_list = []
        for ib_config in game_config_json:
            draw_ib = ib_config["DrawIB"]
            # print("DrawIB:", draw_ib)
            import_folder_path_list.append(os.path.join(output_folder_path, draw_ib))

        # self.report({'INFO'}, "读取到的drawIB文件夹总数量：" + str(len(import_folder_path_list)))

        for import_folder_path in import_folder_path_list:
            # TODO 在这里导入当前文件夹下所有的ib vb文件
            # 1.我们需要添加到一个新建的集合里，方便后续操作
            folder_draw_ib_name = os.path.basename(import_folder_path)
            collection = bpy.data.collections.new(folder_draw_ib_name)
            bpy.context.scene.collection.children.link(collection)

            # 每个import_folder_path都是一个drawIB
            # 这里我们需要获取到文件夹名称
            # 获取文件夹名称

            # 读取文件夹下面所有的vb和ib文件的prefix
            prefix_set = set()
            # (1) 获取所有ib文件前缀列表
            # self.report({'INFO'}, "Folder Name：" + import_folder_path)
            # 构造需要匹配的文件路径模式
            file_pattern = os.path.join(import_folder_path, "*.ib")
            # 使用 glob.glob 获取匹配的文件列表
            txt_file_list = glob(file_pattern)
            for txt_file_path in txt_file_list:
                # 如果文件名不包含-则属于我们自动导出的文件名，则不计入统计
                if os.path.basename(txt_file_path).find("-") == -1:
                    continue

                # self.report({'INFO'}, "txt file: " + txt_file_path)
                txt_file_splits = os.path.basename(txt_file_path).split("-")
                ib_file_name = txt_file_splits[0] + "-" + txt_file_splits[1]
                ib_file_name = ib_file_name[0:len(ib_file_name) - 3]
                prefix_set.add(ib_file_name)
            # 遍历并导入每一个ib vb文件
            for prefix in prefix_set:
                vb_bin_path = import_folder_path + "\\" + prefix + '.vb'
                ib_bin_path = import_folder_path + "\\" + prefix + '.ib'
                fmt_path = import_folder_path + "\\" + prefix + '.fmt'
                if not os.path.exists(vb_bin_path):
                    raise Fatal('Unable to find matching .vb file for %s' % import_folder_path + "\\" + prefix)
                if not os.path.exists(ib_bin_path):
                    raise Fatal('Unable to find matching .ib file for %s' % import_folder_path + "\\" + prefix)
                if not os.path.exists(fmt_path):
                    fmt_path = None

                # 一些需要传递过去的参数，反正这里传空的是可以用的
                migoto_raw_import_options = {}

                # 这里使用一个done的set来记录已经处理过的文件路径，如果处理过就会在里面触发continue
                done = set()
                try:
                    if os.path.normcase(vb_bin_path) in done:
                        continue
                    done.add(os.path.normcase(vb_bin_path))
                    if fmt_path is not None:
                        obj_results = import_3dmigoto_raw_buffers(self, context, fmt_path, fmt_path, vb_path=vb_bin_path,
                                                                  ib_path=ib_bin_path, **migoto_raw_import_options)
                        # 虽然复制之后名字会多个001 002这种，但是不影响正常使用，只要能达到效果就行了
                        for obj in obj_results:
                            new_object = obj.copy()
                            new_object.data = obj.data.copy()

                            collection.objects.link(new_object)
                            bpy.data.objects.remove(obj)
                    else:
                        self.report({'ERROR'}, "Can't find .fmt file!")
                except Fatal as e:
                    self.report({'ERROR'}, str(e))

        return {'FINISHED'}


class MMTExportAllIBVBModel(bpy.types.Operator):
    bl_idname = "mmt.export_all"
    bl_label = "Export all .ib and .vb model to current OutputFolder"

    def execute(self, context):
        # 首先根据MMT路径，获取
        mmt_path = bpy.context.scene.mmt_props.path
        current_game = ""
        main_setting_path = os.path.join(context.scene.mmt_props.path, "Configs\\Main.json")
        if os.path.exists(main_setting_path):
            main_setting_file = open(main_setting_path)
            main_setting_json = json.load(main_setting_file)
            main_setting_file.close()
            current_game = main_setting_json["GameName"]

        output_folder_path = mmt_path + "Games\\" + current_game + "\\3Dmigoto\\Mods\\output\\"
        # 创建 Export3DMigoto 类的实例对象


        # 遍历当前选中列表的所有mesh，根据名称导出到对应的文件夹中
        # 获取当前选中的对象列表
        selected_collection = bpy.context.collection

        # 遍历选中的对象
        export_time = 0
        for obj in selected_collection.objects:
            # 判断对象是否为网格对象
            if obj.type == 'MESH':
                export_time = export_time + 1
                bpy.context.view_layer.objects.active = obj
                mesh = obj.data  # 获取网格数据

                self.report({'INFO'}, "export name: " + mesh.name)

                # 处理当前网格对象
                # 例如，打印网格名称

                name_splits = str(mesh.name).split("-")
                draw_ib = name_splits[0]
                draw_index = name_splits[1]
                draw_index = draw_index[0:len(draw_index) - 3]
                if draw_index.endswith(".vb."):
                    draw_index = draw_index[0:len(draw_index) - 4]

                # 设置类属性的值
                vb_path = output_folder_path + draw_ib + "\\" + draw_index + ".vb"
                self.report({'INFO'}, "export path: " + vb_path)

                ib_path = os.path.splitext(vb_path)[0] + '.ib'
                fmt_path = os.path.splitext(vb_path)[0] + '.fmt'

                # FIXME: ExportHelper will check for overwriting vb_path, but not ib_path

                export_3dmigoto(self, context, vb_path, ib_path, fmt_path)
        if export_time == 0:
            self.report({'ERROR'}, "导出失败！请选择一个集合后再点一键导出！")
        else:
            self.report({'INFO'}, "一键导出成功！成功导出的部位数量：" + str(export_time))
        return {'FINISHED'}


class MMTPathProperties(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty(
        name="主路径",
        description="Select a folder path of MMT",
        default=load_path(),
        subtype='DIR_PATH'
    ) # type: ignore

    export_same_number: bpy.props.BoolProperty(
        name="My Checkbox",
        description="This is a checkbox in the sidebar",
        default=False
    ) # type: ignore

    def __init__(self) -> None:
        super().__init__()
        self.subtype = 'DIR_PATH'
        self.path = load_path()


class MMTPathOperator(bpy.types.Operator):
    bl_idname = "mmt.select_folder"
    bl_label = "Select Folder"

    def execute(self, context):
        # 在这里处理文件夹选择逻辑
        bpy.ops.ui.directory_dialog('INVOKE_DEFAULT', directory=context.scene.mmt_props.path)
        return {'FINISHED'}


# MMT的侧边栏
class MMTPanel(bpy.types.Panel):
    bl_label = "MMT插件 " + mmt_version
    bl_idname = "VIEW3D_PT_MMT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MMT'
    # bl_region_width = 600 # TODO 记得点开之后就设置宽度啊

    def draw(self, context):

        layout = self.layout

        row = layout.row()
        # 在这里添加你的侧边栏内容
        # row.label(text="版本：" + mmt_version)

        # row.operator("wm.url_open", text="检查更新", icon='URL').url = "https://github.com/StarBobis/MMT-Blender-Plugin"
        props = context.scene.mmt_props
        layout.prop(props, "path")

        # 获取MMT.exe的路径
        mmt_path = os.path.join(context.scene.mmt_props.path, "MMT-GUI.exe")
        mmt_location = os.path.dirname(mmt_path)
        if os.path.exists(mmt_path):
            pass
            # layout.label(text="MMT主程序: " + mmt_path)
        else:
            layout.label(text="错误:请选择MMT主路径 ", icon='ERROR')

        # 读取MainSetting.json中当前游戏名称
        current_game = ""
        main_setting_path = os.path.join(context.scene.mmt_props.path, "Configs\\Main.json")
        if os.path.exists(main_setting_path):
            main_setting_file = open(main_setting_path)
            main_setting_json = json.load(main_setting_file)
            main_setting_file.close()
            current_game = main_setting_json["GameName"]
            layout.label(text="当前游戏: " + current_game)
        else:
            layout.label(text="错误:请选择MMT主路径 ", icon='ERROR')

        # 根据当前游戏名称，读取GameSetting中的OutputFolder路径并设置
        output_folder_path = mmt_location + "\\Games\\" + current_game + "\\3Dmigoto\\Mods\\output\\"

        # 绘制一个CheckBox用来存储是否导出相同顶点数
        layout.separator()
        layout.prop(context.scene.mmt_props, "export_same_number", text="导出不改变顶点数")

        layout.separator()
        layout.label(text="在OutputFolder中导入或导出")

        # 快速导入，点这个之后默认路径为OutputFolder，这样直接就能去导入不用翻很久文件夹找路径了
        operator_import_txt = self.layout.operator("import_mesh.migoto_frame_analysis_mmt", text="导入 .txt 模型文件")
        operator_import_txt.directory = output_folder_path

        # 新增快速导入buf文件
        operator_import_ib_vb = self.layout.operator("import_mesh.migoto_raw_buffers_mmt", text="导入 .ib & .vb 模型文件")
        operator_import_ib_vb.filepath = output_folder_path

        # 快速导出同理，点这个之后默认路径为OutputFolder，这样直接就能去导出不用翻很久文件夹找路径了
        operator_export_ibvb = self.layout.operator("export_mesh.migoto_mmt", text="导出 .ib & .vb 模型文件")
        operator_export_ibvb.filepath = output_folder_path + "1.vb"

        # 添加分隔符
        layout.separator()

        # 一键快速导入所有位于OutputFolder下的.txt模型
        layout.label(text="在OutputFolder中一键导入导出")
        operator_fast_import = self.layout.operator("mmt.import_all", text="一键导入所有.ib & .vb模型文件")

        # 一键快速导出当前选中Collection中的所有model到对应的hash值文件夹中，并直接调用MMT.exe的Mod生成方法，做到导出完即可游戏里F10刷新看效果。
        operator_export_ibvb = self.layout.operator("mmt.export_all", text="一键导出选中的MMT集合")

        # 添加分隔符
        layout.separator()

        # 导出MMD的Bone Matrix，连续骨骼变换矩阵，并生成ini文件
        layout.label(text="骨骼蒙皮动画Mod")
        layout.prop(context.scene, "mmt_mmd_animation_mod_start_frame")
        layout.prop(context.scene, "mmt_mmd_animation_mod_end_frame")
        layout.prop(context.scene, "mmt_mmd_animation_mod_play_speed")
        operator_export_mmd_bone_matrix = layout.operator("mmt.export_mmd_animation_mod", text="Export Animation Mod")
        operator_export_mmd_bone_matrix.output_folder = output_folder_path

        # # 添加分隔符
        # layout.separator()
        #
        # # 将当前动画的每一帧都转换为一个Position.buf然后导出，并生成逐帧ini文件
        # row = layout.row()
        # row.label(text="FrameBased Animation Mod")
        # operator_export_mmd_bone_matrix = row.operator("export_mesh.migoto", text="Export Position Files")
        # row = layout.row()
        # row.prop(context.scene, "mmt_mmd_animation_mod_start_frame")
        # row.prop(context.scene, "mmt_mmd_animation_mod_end_frame")
        # row.prop(context.scene, "mmt_mmd_animation_mod_play_speed")
        # # 添加分隔符
        # layout.separator()
        #
        # # 一键快速导入所有位于OutputFolder下的.txt模型
        # layout.label(text="ShapeKey Mod")