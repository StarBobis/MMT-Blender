# This mesh_operator.py is only used in right click options.
from .mesh_functions import *


class RemoveUnusedVertexGroupOperator(bpy.types.Operator):
    bl_idname = "object.remove_unused_vertex_group"
    bl_label = "移除未使用的空顶点组"

    def execute(self, context):
        return remove_unused_vertex_group(self, context)


class MergeVertexGroupsWithSameNumber(bpy.types.Operator):
    bl_idname = "object.merge_vertex_group_with_same_number"
    bl_label = "合并具有相同数字前缀名称的顶点组"

    def execute(self, context):
        return merge_vertex_group_with_same_number(self, context)


class FillVertexGroupGaps(bpy.types.Operator):
    bl_idname = "object.fill_vertex_group_gaps"
    bl_label = "填充数字顶点组的间隙"

    def execute(self, context):
        return fill_vertex_group_gaps(self, context)


class AddBoneFromVertexGroup(bpy.types.Operator):
    bl_idname = "object.add_bone_from_vertex_group"
    bl_label = "根据顶点组自动生成骨骼"

    def execute(self, context):
        return add_bone_from_vertex_group(self, context)


class RemoveNotNumberVertexGroup(bpy.types.Operator):
    bl_idname = "object.remove_not_number_vertex_group"
    bl_label = "移除非数字名称的顶点组"

    def execute(self, context):
        return remove_not_number_vertex_group(self, context)


class ConvertToFragmentOperator(bpy.types.Operator):
    bl_idname = "object.convert_to_fragment"
    bl_label = "转换为一个3Dmigoto碎片用于合并"

    def execute(self, context):
        return convert_to_fragment(self, context)


class MMTDeleteLoose(bpy.types.Operator):
    bl_idname = "object.mmt_delete_loose"
    bl_label = "删除物体的松散点"

    def execute(self, context):
        return delete_loose(self, context)


class MMTResetRotation(bpy.types.Operator):
    bl_idname = "object.mmt_reset_rotation"
    bl_label = "重置x,y,z的旋转角度为0 (UE Model)"

    def execute(self, context):
        return mmt_reset_rotation(self, context)


class MMTCancelAutoSmooth(bpy.types.Operator):
    bl_idname = "object.mmt_cancel_auto_smooth"
    bl_label = "取消自动平滑 (UE Model)"

    def execute(self, context):
        return mmt_cancel_auto_smooth(self, context)


class MMTSetAutoSmooth89(bpy.types.Operator):
    bl_idname = "object.mmt_set_auto_smooth_89"
    bl_label = "设置Normal的自动平滑为89° (Unity)"

    def execute(self, context):
        return mmt_set_auto_smooth_89(self, context)


class MMTShowIndexedVertices(bpy.types.Operator):
    bl_idname = "object.mmt_show_indexed_vertices"
    bl_label = "展示Indexed Vertices和Indexes Number"

    def execute(self, context):
        return show_indexed_vertices(self, context)


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
