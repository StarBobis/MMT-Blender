# This mesh_operator.py is only used in right click options.
import math

from ..migoto.migoto_format import *
from ..migoto.migoto_import import *
from ..migoto.migoto_export import *


def remove_unused_vertex_group(self, context):
    # Copy from https://blenderartists.org/t/batch-delete-vertex-groups-script/449881/23
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            # obj = bpy.context.active_object
            obj.update_from_editmode()
            vgroup_used = {i: False for i, k in enumerate(obj.vertex_groups)}

            for v in obj.data.vertices:
                for g in v.groups:
                    if g.weight > 0.0:
                        vgroup_used[g.group] = True

            for i, used in sorted(vgroup_used.items(), reverse=True):
                if not used:
                    obj.vertex_groups.remove(obj.vertex_groups[i])

    return {'FINISHED'}


class RemoveUnusedVertexGroupOperator(bpy.types.Operator):
    bl_idname = "object.remove_unused_vertex_group"
    bl_label = "移除未使用的空顶点组"

    def execute(self, context):
        return remove_unused_vertex_group(self, context)


def merge_vertex_group_with_same_number(self, context):
    # Author: SilentNightSound#7430
    # Combines vertex groups with the same prefix into one, a fast alternative to the Vertex Weight Mix that works for multiple groups
    # You will likely want to use blender_fill_vg_gaps.txt after this to fill in any gaps caused by merging groups together
    # Nico: we only need mode 3 here.

    import bpy
    import itertools
    class Fatal(Exception):
        pass

    selected_obj = [obj for obj in bpy.context.selected_objects]
    vgroup_names = []

    ##### USAGE INSTRUCTIONS
    # MODE 1: Runs the merge on a specific list of vertex groups in the selected object(s). Can add more names or fewer to the list - change the names to what you need
    # MODE 2: Runs the merge on a range of vertex groups in the selected object(s). Replace smallest_group_number with the lower bound, and largest_group_number with the upper bound
    # MODE 3 (DEFAULT): Runs the merge on ALL vertex groups in the selected object(s)

    # Select the mode you want to run:
    mode = 3

    # Required data for MODE 1:
    vertex_groups = ["replace_with_first_vertex_group_name", "second_vertex_group_name", "third_name_etc"]

    # Required data for MODE 2:
    smallest_group_number = 000
    largest_group_number = 999

    ######

    if mode == 1:
        vgroup_names = [vertex_groups]
    elif mode == 2:
        vgroup_names = [[f"{i}" for i in range(smallest_group_number, largest_group_number + 1)]]
    elif mode == 3:
        vgroup_names = [[x.name.split(".")[0] for x in y.vertex_groups] for y in selected_obj]
    else:
        raise Fatal("Mode not recognized, exiting")

    if not vgroup_names:
        raise Fatal(
            "No vertex groups found, please double check an object is selected and required data has been entered")

    for cur_obj, cur_vgroup in zip(selected_obj, itertools.cycle(vgroup_names)):
        for vname in cur_vgroup:
            relevant = [x.name for x in cur_obj.vertex_groups if x.name.split(".")[0] == f"{vname}"]

            if relevant:

                vgroup = cur_obj.vertex_groups.new(name=f"x{vname}")

                for vert_id, vert in enumerate(cur_obj.data.vertices):
                    available_groups = [v_group_elem.group for v_group_elem in vert.groups]

                    combined = 0
                    for v in relevant:
                        if cur_obj.vertex_groups[v].index in available_groups:
                            combined += cur_obj.vertex_groups[v].weight(vert_id)

                    if combined > 0:
                        vgroup.add([vert_id], combined, 'ADD')

                for vg in [x for x in cur_obj.vertex_groups if x.name.split(".")[0] == f"{vname}"]:
                    cur_obj.vertex_groups.remove(vg)

                for vg in cur_obj.vertex_groups:
                    if vg.name[0].lower() == "x":
                        vg.name = vg.name[1:]

        bpy.context.view_layer.objects.active = cur_obj
        bpy.ops.object.vertex_group_sort()
    return {'FINISHED'}


class MergeVertexGroupsWithSameNumber(bpy.types.Operator):
    bl_idname = "object.merge_vertex_group_with_same_number"
    bl_label = "合并具有相同数字前缀名称的顶点组"

    def execute(self, context):
        return merge_vertex_group_with_same_number(self, context)


def fill_vertex_group_gaps(self, context):
    # Author: SilentNightSound#7430
    # Fills in missing vertex groups for a model so there are no gaps, and sorts to make sure everything is in order
    # Works on the currently selected object
    # e.g. if the selected model has groups 0 1 4 5 7 2 it adds an empty group for 3 and 6 and sorts to make it 0 1 2 3 4 5 6 7
    # Very useful to make sure there are no gaps or out-of-order vertex groups

    # Can change this to another number in order to generate missing groups up to that number
    # e.g. setting this to 130 will create 0,1,2...130 even if the active selected object only has 90
    # Otherwise, it will use the largest found group number and generate everything up to that number
    largest = 0

    ob = bpy.context.active_object
    ob.update_from_editmode()

    for vg in ob.vertex_groups:
        try:
            if int(vg.name.split(".")[0]) > largest:
                largest = int(vg.name.split(".")[0])
        except ValueError:
            print("Vertex group not named as integer, skipping")

    missing = set([f"{i}" for i in range(largest + 1)]) - set([x.name.split(".")[0] for x in ob.vertex_groups])
    for number in missing:
        ob.vertex_groups.new(name=f"{number}")

    bpy.ops.object.vertex_group_sort()
    return {'FINISHED'}


class FillVertexGroupGaps(bpy.types.Operator):
    bl_idname = "object.fill_vertex_group_gaps"
    bl_label = "填充数字顶点组的间隙"

    def execute(self, context):
        return fill_vertex_group_gaps(self, context)


def add_bone_from_vertex_group(self, context):
    # 这玩意实际上没啥用，但是好像又有点用，反正鸡肋，加上吧。
    # 获取当前选中的物体
    selected_object = bpy.context.object

    # 创建骨骼
    bpy.ops.object.armature_add()
    armature_object = bpy.context.object
    armature = armature_object.data

    # 切换到编辑模式
    bpy.ops.object.mode_set(mode='EDIT')

    # 遍历所有的顶点组
    for vertex_group in selected_object.vertex_groups:
        # 获取顶点组的名称
        vertex_group_name = vertex_group.name

        # 创建骨骼
        bone = armature.edit_bones.new(vertex_group_name)

        # 根据顶点组位置生成骨骼
        for vertex in selected_object.data.vertices:
            for group_element in vertex.groups:
                if group_element.group == vertex_group.index:
                    # 获取顶点位置
                    vertex_position = selected_object.matrix_world @ vertex.co

                    # 设置骨骼位置
                    bone.head = vertex_position
                    bone.tail = Vector(vertex_position) + Vector((0, 0, 0.1))  # 设置骨骼长度

                    # 分配顶点到骨骼
                    bone_vertex_group = selected_object.vertex_groups[vertex_group_name]
                    bone_vertex_group.add([vertex.index], 0, 'ADD')

    # 刷新场景
    bpy.context.view_layer.update()

    # 切换回对象模式
    bpy.ops.object.mode_set(mode='OBJECT')
    return {'FINISHED'}


class AddBoneFromVertexGroup(bpy.types.Operator):
    bl_idname = "object.add_bone_from_vertex_group"
    bl_label = "根据顶点组自动生成骨骼"

    def execute(self, context):
        return add_bone_from_vertex_group(self, context)


def remove_not_number_vertex_group(self, context):
    for obj in bpy.context.selected_objects:
        for vg in reversed(obj.vertex_groups):
            if vg.name.isdecimal():
                continue
            # print('Removing vertex group', vg.name)
            obj.vertex_groups.remove(vg)
    return {'FINISHED'}


class RemoveNotNumberVertexGroup(bpy.types.Operator):
    bl_idname = "object.remove_not_number_vertex_group"
    bl_label = "移除非数字名称的顶点组"

    def execute(self, context):
        return remove_not_number_vertex_group(self, context)


def convert_to_fragment(self, context):
    # 获取当前选中的对象
    selected_objects = bpy.context.selected_objects

    # 检查是否选中了一个Mesh对象
    if len(selected_objects) != 1 or selected_objects[0].type != 'MESH':
        raise ValueError("请选中一个Mesh对象")

    # 获取选中的网格对象
    mesh_obj = selected_objects[0]
    mesh = mesh_obj.data

    # 遍历所有面
    selected_face_index = -1
    for i, face in enumerate(mesh.polygons):
        # 检查当前面是否已经是一个三角形
        if len(face.vertices) == 3:
            selected_face_index = i
            break

    if selected_face_index == -1:
        raise ValueError("没有选中的三角形面")

    # 选择指定索引的面
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')

    # 选择指定面的所有顶点
    bpy.context.tool_settings.mesh_select_mode[0] = True
    bpy.context.tool_settings.mesh_select_mode[1] = False
    bpy.context.tool_settings.mesh_select_mode[2] = False

    bpy.ops.object.mode_set(mode='OBJECT')

    # 获取选中面的所有顶点索引
    selected_face = mesh.polygons[selected_face_index]
    selected_vertices = [v for v in selected_face.vertices]

    # 删除非选定面的顶点
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')

    bpy.context.tool_settings.mesh_select_mode[0] = True
    bpy.context.tool_settings.mesh_select_mode[1] = False
    bpy.context.tool_settings.mesh_select_mode[2] = False

    bpy.ops.object.mode_set(mode='OBJECT')

    for vertex in mesh.vertices:
        if vertex.index not in selected_vertices:
            vertex.select = True

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.delete(type='VERT')

    # 切换回对象模式
    bpy.ops.object.mode_set(mode='OBJECT')

    return {'FINISHED'}


class ConvertToFragmentOperator(bpy.types.Operator):
    bl_idname = "object.convert_to_fragment"
    bl_label = "转换为一个3Dmigoto碎片用于合并"

    def execute(self, context):
        return convert_to_fragment(self, context)


def delete_loose(self, context):
    # 获取当前选中的对象
    selected_objects = bpy.context.selected_objects
    # 检查是否选中了一个Mesh对象
    for obj in selected_objects:
        if obj.type == 'MESH':
            # 获取选中的网格对象
            bpy.ops.object.mode_set(mode='EDIT')
            # 选择所有的顶点
            bpy.ops.mesh.select_all(action='SELECT')
            # 执行删除孤立顶点操作
            bpy.ops.mesh.delete_loose()
            # 切换回对象模式
            bpy.ops.object.mode_set(mode='OBJECT')
    return {'FINISHED'}


class MMTDeleteLoose(bpy.types.Operator):
    bl_idname = "object.mmt_delete_loose"
    bl_label = "删除物体的松散点"

    def execute(self, context):
        return delete_loose(self, context)


def mmt_reset_rotation(self, context):
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            # 将旋转角度归零
            obj.rotation_euler[0] = 0.0  # X轴
            obj.rotation_euler[1] = 0.0  # Y轴
            obj.rotation_euler[2] = 0.0  # Z轴

            # 应用旋转变换
            # bpy.context.view_layer.objects.active = obj
            # bpy.ops.object.transform_apply(rotation=True)
    return {'FINISHED'}


class MMTResetRotation(bpy.types.Operator):
    bl_idname = "object.mmt_reset_rotation"
    bl_label = "重置x,y,z的旋转角度为0 (UE Model)"

    def execute(self, context):
        return mmt_reset_rotation(self, context)


def mmt_cancel_auto_smooth(self, context):
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            # 取消勾选"Auto Smooth"
            # TODO 4.1中移除了use_auto_smooth
            obj.data.use_auto_smooth = False
    return {'FINISHED'}


class MMTCancelAutoSmooth(bpy.types.Operator):
    bl_idname = "object.mmt_cancel_auto_smooth"
    bl_label = "取消自动平滑 (UE Model)"

    def execute(self, context):
        return mmt_cancel_auto_smooth(self, context)


def mmt_set_auto_smooth_89(self, context):
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            # 取消勾选"Auto Smooth"
            # TODO 4.1中移除了use_auto_smooth
            obj.data.use_auto_smooth = True
            # TODO 4.1中移除了auto_smooth_angle
            obj.data.auto_smooth_angle = math.radians(89)
    return {'FINISHED'}


class MMTSetAutoSmooth89(bpy.types.Operator):
    bl_idname = "object.mmt_set_auto_smooth_89"
    bl_label = "设置Normal的自动平滑为89° (Unity)"

    def execute(self, context):
        return mmt_set_auto_smooth_89(self, context)


def show_indexed_vertices(self, context):
    for obj in bpy.context.selected_objects:
        stride = obj['3DMigoto:VBStride']
        layout = InputLayout(obj['3DMigoto:VBLayout'], stride=stride)
        # 获取Mesh
        if hasattr(context, "evaluated_depsgraph_get"):  # 2.80
            mesh = obj.evaluated_get(context.evaluated_depsgraph_get()).to_mesh()
        else:  # 2.79
            mesh = obj.to_mesh(context.scene, True, 'PREVIEW', calc_tessface=False)

        mesh_triangulate(mesh)
        mesh.calc_tangents()

        texcoord_layers = {}
        for uv_layer in mesh.uv_layers:
            texcoords = {}
            try:
                flip_texcoord_v = obj['3DMigoto:' + uv_layer.name]['flip_v']
                if flip_texcoord_v:
                    flip_uv = lambda uv: (uv[0], 1.0 - uv[1])
                else:
                    flip_uv = lambda uv: uv
            except KeyError:
                flip_uv = lambda uv: uv

            for l in mesh.loops:
                uv = flip_uv(uv_layer.data[l.index].uv)
                texcoords[l.index] = uv
            texcoord_layers[uv_layer.name] = texcoords

        indexed_vertices = collections.OrderedDict()
        unique_position_vertices = {}

        index_number = 0
        for poly in mesh.polygons:
            face = []
            for blender_lvertex in mesh.loops[poly.loop_start:poly.loop_start + poly.loop_total]:
                #
                vertex = blender_vertex_to_3dmigoto_vertex(mesh, obj, blender_lvertex, layout, texcoord_layers)
                if "POSITION" in vertex and "NORMAL" in vertex and "TANGENT" in vertex:
                    if tuple(vertex["POSITION"] + vertex["NORMAL"]) in unique_position_vertices:
                        tangent_var = unique_position_vertices[tuple(vertex["POSITION"] + vertex["NORMAL"])]
                        vertex["TANGENT"] = tangent_var
                    else:
                        tangent_var = vertex["TANGENT"]
                        unique_position_vertices[tuple(vertex["POSITION"] + vertex["NORMAL"])] = tangent_var
                        vertex["TANGENT"] = tangent_var
                index_number = index_number + 1
                indexed_vertex = indexed_vertices.setdefault(HashableVertex(vertex), len(indexed_vertices))
                face.append(indexed_vertex)
        self.report({'INFO'}, "Original Indices:" + str(obj['3DMigoto:OriginalIndicesNumber']) + " Current Indices: " + str(index_number) + " Original Vertices:" + str(obj['3DMigoto:OriginalVertexNumber']) + "  Current Vertices: "+str(len(indexed_vertices)))

    return {'FINISHED'}


class MMTShowIndexedVertices(bpy.types.Operator):
    bl_idname = "object.mmt_show_indexed_vertices"
    bl_label = "展示Indexed Vertices和Indexes Number"

    def execute(self, context):
        return show_indexed_vertices(self, context)


def split_mesh_by_common_vertex_group(self, context):
    # Code copied and modified from @Kail_Nethunter, very useful in some special meets.
    # https://blenderartists.org/t/split-a-mesh-by-vertex-groups/438990/11

    for obj in bpy.context.selected_objects:
        origin_name = obj.name
        keys = obj.vertex_groups.keys()
        real_keys = []
        for gr in keys:
            bpy.ops.object.mode_set(mode="EDIT")
            # Set the vertex group as active
            bpy.ops.object.vertex_group_set_active(group=gr)

            # Deselect all verts and select only current VG
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.vertex_group_select()
            # bpy.ops.mesh.select_all(action='INVERT')
            try:
                bpy.ops.mesh.separate(type="SELECTED")
                real_keys.append(gr)
            except:
                pass
        for i in range(1, len(real_keys) + 1):
            bpy.data.objects['{}.{:03d}'.format(origin_name, i)].name = '{}.{}'.format(
                origin_name, real_keys[i - 1])

    return {'FINISHED'}


class SplitMeshByCommonVertexGroup(bpy.types.Operator):
    bl_idname = "object.split_mesh_by_common_vertex_group"
    bl_label = "根据相同的顶点组分割物体"

    def execute(self, context):
        return split_mesh_by_common_vertex_group(self, context)



# -----------------------------------这个属于右键菜单注册，单独的函数要往上面放---------------------------------------
class MigotoRightClickMenu(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_object_3Dmigoto"
    bl_label = "3Dmigoto"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.remove_unused_vertex_group")
        layout.operator("object.merge_vertex_group_with_same_number")
        layout.operator("object.fill_vertex_group_gaps")
        layout.operator("object.add_bone_from_vertex_group")
        layout.operator("object.remove_not_number_vertex_group")
        layout.operator("object.convert_to_fragment")
        layout.operator("object.mmt_delete_loose")
        layout.operator("object.mmt_reset_rotation")
        layout.operator("object.mmt_cancel_auto_smooth")
        layout.operator("object.mmt_set_auto_smooth_89")
        layout.operator("object.mmt_show_indexed_vertices")
        layout.operator("object.split_mesh_by_common_vertex_group")


# 定义菜单项的注册函数
def menu_func_migoto_right_click(self, context):
    self.layout.menu(MigotoRightClickMenu.bl_idname)


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

