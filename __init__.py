import bpy.props

# Nico: The __init__.py only designed to register and unregister ,so as a simple control for the whole plugin,
# keep it clean and don't add too many code,code should be in other files and import it here.
# we use .utils instead of utils because blender can't locate where utils is
# Blender can only locate panel.py only when you add a . before it.

from .mmt_panel.panel import *
from .model_menu.mesh_operator import *
from .animation.animation_operator import *

'''
Nico: This is a special fork version of DarkStarSword's blender_3dmigoto.py, and code learned from a lot of similar projects.
We modified some code to better meet our needs, here is a list for all credits.

Fork From:
- @DarkStarSword        3D-fixs                 https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py

Reference Links:
- @leotorrez            LeoTools                https://github.com/leotorrez/LeoTools
- @leotorrez            XXMITools               https://github.com/leotorrez/XXMITools
- @SpectrumQT           WWMI-TOOLS              https://github.com/SpectrumQT/WWMI-TOOLS
- @falling-ts           free-model              https://github.com/falling-ts/free-model
- @SilentNightSound     GI-Model-Importer       https://github.com/SilentNightSound/GI-Model-Importer
- @SilentNightSound     GI-Model-Importer       https://github.com/SilentNightSound/SR-Model-Importer
- @eArmada8             vbuffer_merge_split     https://github.com/eArmada8/vbuffer_merge_split
- @eArmada8             gust_stuff              https://github.com/eArmada8/gust_stuff

All code in MMT-Blender-Plugin credit to original 3Dmigoto repository:
https://github.com/bo3b/3Dmigoto
'''

bl_info = {
    "name": "MMT",
    "description": "MMT-Community's Blender Plugin",
    "blender": (3, 6, 0),
    "version": (1, 0, 5, 7),
    "location": "View3D",
    "warning": "Only support Blender 3.6 LTS",
    "category": "Generic"
}


register_classes = (
    # migoto
    MMTPathProperties,
    MMTPathOperator,
    MMTPanel,

    Import3DMigotoFrameAnalysis,
    Import3DMigotoRaw,
    Import3DMigotoReferenceInputFormat,
    Export3DMigoto,

    # mesh_operator 右键菜单栏
    RemoveUnusedVertexGroupOperator,
    MergeVertexGroupsWithSameNumber,
    FillVertexGroupGaps,
    AddBoneFromVertexGroup,
    RemoveNotNumberVertexGroup,
    ConvertToFragmentOperator,
    MMTDeleteLoose,
    MMTResetRotation,
    MigotoRightClickMenu,
    MMTCancelAutoSmooth,
    MMTShowIndexedVertices,
    MMTSetAutoSmooth89,
    SplitMeshByCommonVertexGroup,

    # MMT的一键导入导出
    MMTImportAllTextModel,
    MMTExportAllIBVBModel,

    # MMD类型动画Mod支持
    MMDModIniGenerator
)


def register():
    for cls in register_classes:
        # make_annotations(cls)
        bpy.utils.register_class(cls)

    # 新建一个属性用来专门装MMT的路径
    bpy.types.Scene.mmt_props = bpy.props.PointerProperty(type=MMTPathProperties)
    # mesh_operator
    bpy.types.VIEW3D_MT_object_context_menu.append(menu_func_migoto_right_click)

    # 在Blender退出前保存选择的MMT的路径
    bpy.app.handlers.depsgraph_update_post.append(save_mmt_path)

    # MMT数值保存的变量
    bpy.types.Scene.mmt_mmd_animation_mod_start_frame = bpy.props.IntProperty(name="Start Frame")
    bpy.types.Scene.mmt_mmd_animation_mod_end_frame = bpy.props.IntProperty(name="End Frame")
    bpy.types.Scene.mmt_mmd_animation_mod_play_speed = bpy.props.FloatProperty(name="Play Speed")

    
def unregister():
    for cls in reversed(register_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.mmt_props

    # mesh_operator
    bpy.types.VIEW3D_MT_object_context_menu.remove(menu_func_migoto_right_click)

    # 退出注册时删除MMT的MMD变量
    del bpy.types.Scene.mmt_mmd_animation_mod_start_frame
    del bpy.types.Scene.mmt_mmd_animation_mod_end_frame
    del bpy.types.Scene.mmt_mmd_animation_mod_play_speed


