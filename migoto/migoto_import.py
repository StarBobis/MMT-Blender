from .migoto_format import *
from array import array
from glob import glob

import os.path
import itertools
import bpy

from bpy_extras.io_utils import unpack_list, ImportHelper, axis_conversion
from bpy.props import BoolProperty, StringProperty, CollectionProperty
from bpy_extras.io_utils import orientation_helper


def load_3dmigoto_mesh_bin(operator, vb_paths, ib_paths):
    if len(vb_paths) != 1 or len(ib_paths) > 1:
        raise Fatal('Cannot merge meshes loaded from binary files')

    # Loading from binary files, but still need to use the .txt files as a
    # reference for the format:
    vb_bin_path, vb_txt_path = vb_paths[0]
    ib_bin_path, ib_txt_path = ib_paths[0]

    vb = VertexBuffer(open(vb_txt_path, 'r'), load_vertices=False)
    vb.parse_vb_bin(open(vb_bin_path, 'rb'))

    ib = None
    if ib_paths:
        ib = IndexBuffer(open(ib_txt_path, 'r'), load_indices=False)
        ib.parse_ib_bin(open(ib_bin_path, 'rb'))

    return vb, ib, os.path.basename(vb_bin_path)


def load_3dmigoto_mesh(operator, paths):
    vb_paths, ib_paths, use_bin = zip(*paths)

    if use_bin[0]:
        return load_3dmigoto_mesh_bin(operator, vb_paths, ib_paths)

    vb = VertexBuffer(open(vb_paths[0], 'r'))
    # Merge additional vertex buffers for meshes split over multiple draw calls:
    for vb_path in vb_paths[1:]:
        tmp = VertexBuffer(open(vb_path, 'r'))
        vb.merge(tmp)

    # For quickly testing how importent any unsupported semantics may be:
    # vb.wipe_semantic_for_testing('POSITION.w', 1.0)
    # vb.wipe_semantic_for_testing('TEXCOORD.w', 0.0)
    # vb.wipe_semantic_for_testing('TEXCOORD5', 0)
    # vb.wipe_semantic_for_testing('BINORMAL')
    # vb.wipe_semantic_for_testing('TANGENT')
    # vb.write(open(os.path.join(os.path.dirname(vb_paths[0]), 'TEST.vb'), 'wb'), operator=operator)

    ib = None
    if ib_paths:
        ib = IndexBuffer(open(ib_paths[0], 'r'))
        # Merge additional vertex buffers for meshes split over multiple draw calls:
        for ib_path in ib_paths[1:]:
            tmp = IndexBuffer(open(ib_path, 'r'))
            ib.merge(tmp)

    return vb, ib, os.path.basename(vb_paths[0])


def import_normals_step1(mesh, data):
    # Nico:
    # Blender不支持4D normal，而UE4 Normal的的第四个分量一般情况下是1，可以忽略后导入
    # 而BINORMAL第四个分量不是1就是-1，这时第四个分量代表手性信息，需要根据是否为-1进行向量翻转。
    # 不过暂时没有发现BINORMAL，现代引擎一般都用不上BINORMAL了，所以我们这里不再考虑兼容
    # 这里直接忽略第四个值，无需多余判断，如果真有游戏是4D的Position那到时候再研究
    # if len(data[0]) == 4:
        # if [x[3] for x in data] != [0.0] * len(data):
        #     raise Fatal('Normals are 4D')
    normals = [(x[0], x[1], x[2]) for x in data]

    # To make sure the normals don't get lost by Blender's edit mode,
    # or mesh.update() we need to set custom normals in the loops, not
    # vertices.
    #
    # For testing, to make sure our normals are preserved let's use
    # garbage ones:
    # import random
    # normals = [(random.random() * 2 - 1,random.random() * 2 - 1,random.random() * 2 - 1) for x in normals]
    #
    # Comment from other import scripts:
    # Note: we store 'temp' normals in loops, since validate() may alter final mesh,
    #       we can only set custom lnors *after* calling it.

    # TODO This can't use in BlenderV4.1  see:
    # https://developer.blender.org/docs/release_notes/4.1/python_api/#mesh
    mesh.create_normals_split()
    for l in mesh.loops:
        # TODO mesh loop.normal is read only in 4.1!
        l.normal[:] = normals[l.vertex_index]


def import_normals_step2(mesh):
    # Taken from import_obj/import_fbx
    clnors = array('f', [0.0] * (len(mesh.loops) * 3))
    mesh.loops.foreach_get("normal", clnors)
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.normals_split_custom_set(tuple(zip(*(iter(clnors),) * 3)))


def import_vertex_groups(mesh, obj, blend_indices, blend_weights):
    assert (len(blend_indices) == len(blend_weights))
    if blend_indices:
        # We will need to make sure we re-export the same blend indices later -
        # that they haven't been renumbered. Not positive whether it is better
        # to use the vertex group index, vertex group name or attach some extra
        # data. Make sure the indices and names match:
        num_vertex_groups = max(itertools.chain(*itertools.chain(*blend_indices.values()))) + 1
        for i in range(num_vertex_groups):
            obj.vertex_groups.new(name=str(i))
        for vertex in mesh.vertices:
            for semantic_index in sorted(blend_indices.keys()):
                for i, w in zip(blend_indices[semantic_index][vertex.index],
                                blend_weights[semantic_index][vertex.index]):
                    if w == 0.0:
                        continue
                    obj.vertex_groups[i].add((vertex.index,), w, 'REPLACE')


def import_uv_layers(mesh, obj, texcoords, flip_texcoord_v):
    for (texcoord, data) in sorted(texcoords.items()):
        # TEXCOORDS can have up to four components, but UVs can only have two
        # dimensions. Not positive of the best way to handle this in general,
        # but for now I'm thinking that splitting the TEXCOORD into two sets of
        # UV coordinates might work:
        dim = len(data[0])
        if dim == 4:
            components_list = ('xy', 'zw')
        elif dim == 2:
            components_list = ('xy',)
        else:
            raise Fatal('Unhandled TEXCOORD dimension: %i' % dim)
        cmap = {'x': 0, 'y': 1, 'z': 2, 'w': 3}

        for components in components_list:
            uv_name = 'TEXCOORD%s.%s' % (texcoord and texcoord or '', components)
            if hasattr(mesh, 'uv_textures'):  # 2.79
                mesh.uv_textures.new(uv_name)
            else:  # 2.80
                mesh.uv_layers.new(name=uv_name)
            blender_uvs = mesh.uv_layers[uv_name]

            # This will assign a texture to the UV layer, which works fine but
            # working out which texture maps to which UV layer is guesswork
            # before the import and the artist may as well just assign it
            # themselves in the UV editor pane when they can see the unwrapped
            # mesh to compare it with the dumped textures:
            #
            # path = textures.get(uv_layer, None)
            # if path is not None:
            #    image = load_image(path)
            #    for i in range(len(mesh.polygons)):
            #        mesh.uv_textures[uv_layer].data[i].image = image

            # Can't find an easy way to flip the display of V in Blender, so
            # add an option to flip it on import & export:
            if flip_texcoord_v:
                flip_uv = lambda uv: (uv[0], 1.0 - uv[1])
                # Record that V was flipped, so we know to undo it when exporting:
                obj['3DMigoto:' + uv_name] = {'flip_v': True}
            else:
                flip_uv = lambda uv: uv

            # TODO WTF? why merge them in one line, too hard to understand.
            uvs = [[d[cmap[c]] for c in components] for d in data]

            for l in mesh.loops:
                blender_uvs.data[l.index].uv = flip_uv(uvs[l.vertex_index])


# VertexLayer的设计应该被去除
# Nico:
# 在游戏Mod制作中，所有提取的属性和生成的属性都是应该提前规划好的，
# 而不是在这里做额外的无用步骤来传递一些垃圾属性。
# This loads unknown data from the vertex buffers as vertex layers
# def import_vertex_layers(mesh, obj, vertex_layers):
#     for (element_name, data) in sorted(vertex_layers.items()):
#         dim = len(data[0])
#         cmap = {0: 'x', 1: 'y', 2: 'z', 3: 'w'}
#         for component in range(dim):

#             if dim != 1 or element_name.find('.') == -1:
#                 layer_name = '%s.%s' % (element_name, cmap[component])
#             else:
#                 layer_name = element_name

#             if type(data[0][0]) == int:
#                 layer = mesh.vertex_layers.new(name=layer_name, type='INT')

#                 for v in mesh.vertices:
#                     val = data[v.index][component]
#                     # Blender integer layers are 32bit signed and will throw an
#                     # exception if we are assigning an unsigned value that
#                     # can't fit in that range. Reinterpret as signed if necessary:
#                     if val < 0x80000000:
#                         layer.data[v.index].value = val
#                     else:
#                         layer.data[v.index].value = struct.unpack('i', struct.pack('I', val))[0]
#             elif type(data[0][0]) == float:
#                 layer = mesh.vertex_layers.new(name=layer_name, type='FLOAT')
#                 for v in mesh.vertices:
#                     layer.data[v.index].value = data[v.index][component]
#             else:
#                 raise Fatal('BUG: Bad layer type %s' % type(data[0][0]))


def import_faces_from_ib(mesh, ib):
    mesh.loops.add(len(ib.faces) * 3)
    mesh.polygons.add(len(ib.faces))
    mesh.loops.foreach_set('vertex_index', unpack_list(ib.faces))
    mesh.polygons.foreach_set('loop_start', [x * 3 for x in range(len(ib.faces))])
    mesh.polygons.foreach_set('loop_total', [3] * len(ib.faces))


# Nico: 这玩意基本上用不到吧，没有IB的情况下要怎么做到自动生成顶点索引呢？这样生成出来真的和游戏里替换所需要的格式一样吗？
def import_faces_from_vb(mesh, vb):
    # Only lightly tested
    num_faces = len(vb.vertices) // 3
    mesh.loops.add(num_faces * 3)
    mesh.polygons.add(num_faces)
    mesh.loops.foreach_set('vertex_index', [x for x in range(num_faces * 3)])
    mesh.polygons.foreach_set('loop_start', [x * 3 for x in range(num_faces)])
    mesh.polygons.foreach_set('loop_total', [3] * num_faces)


def import_vertices(mesh, vb):
    mesh.vertices.add(len(vb.vertices))

    seen_offsets = set()
    blend_indices = {}
    blend_weights = {}
    texcoords = {}
    vertex_layers = {}
    use_normals = False

    for elem in vb.layout:
        if elem.InputSlotClass != 'per-vertex':
            continue

        # Discard elements that reuse offsets in the vertex buffer, e.g. COLOR
        # and some TEXCOORDs may be aliases of POSITION:
        if (elem.InputSlot, elem.AlignedByteOffset) in seen_offsets:
            assert (elem.name != 'POSITION')
            continue
        seen_offsets.add((elem.InputSlot, elem.AlignedByteOffset))

        data = tuple(x[elem.name] for x in vb.vertices)
        if elem.name == 'POSITION':
            # Ensure positions are 3-dimensional:
            if len(data[0]) == 4:
                if ([x[3] for x in data] != [1.0] * len(data)):
                    # XXX: Leaving this fatal error in for now, as the meshes
                    # it triggers on in DOA6 (skirts) lie about almost every
                    # semantic and we cannot import them with this version of
                    # the script regardless. Comment it out if you want to try
                    # importing anyway and preserving the W coordinate in a
                    # vertex group. It might also be possible to project this
                    # back into 3D if we assume the coordinates are homogeneous
                    # (i.e. divide XYZ by W), but that might be assuming too
                    # much for a generic script.
                    raise Fatal('Positions are 4D')

                    # Nico: Blender暂时不支持4D索引，加了也没用，直接不行就报错，转人工处理。
                    # Occurs in some meshes in DOA6, such as skirts.
                    # W coordinate must be preserved in these cases.
                    # print('Positions are 4D, storing W coordinate in POSITION.w vertex layer')
                    # vertex_layers['POSITION.w'] = [[x[3]] for x in data]
            positions = [(x[0], x[1], x[2]) for x in data]
            mesh.vertices.foreach_set('co', unpack_list(positions))
        elif elem.name.startswith('COLOR'):
            if len(data[0]) <= 3 or vertex_color_layer_channels == 4:
                # Either a monochrome/RGB layer, or Blender 2.80 which uses 4
                # channel layers
                mesh.vertex_colors.new(name=elem.name)
                color_layer = mesh.vertex_colors[elem.name].data
                c = vertex_color_layer_channels
                for l in mesh.loops:
                    color_layer[l.index].color = list(data[l.vertex_index]) + [0] * (c - len(data[l.vertex_index]))
            else:
                mesh.vertex_colors.new(name=elem.name + '.RGB')
                mesh.vertex_colors.new(name=elem.name + '.A')
                color_layer = mesh.vertex_colors[elem.name + '.RGB'].data
                alpha_layer = mesh.vertex_colors[elem.name + '.A'].data
                for l in mesh.loops:
                    color_layer[l.index].color = data[l.vertex_index][:3]
                    alpha_layer[l.index].color = [data[l.vertex_index][3], 0, 0]
        elif elem.name == 'NORMAL':
            use_normals = True
            import_normals_step1(mesh, data)
        elif elem.name in ('TANGENT', 'BINORMAL'):
            #    # XXX: loops.tangent is read only. Not positive how to handle
            #    # this, or if we should just calculate it when re-exporting.
            #    for l in mesh.loops:
            #        assert(data[l.vertex_index][3] in (1.0, -1.0))
            #        l.tangent[:] = data[l.vertex_index][0:3]
            print('NOTICE: Skipping import of %s in favour of recalculating on export' % elem.name)
        elif elem.name.startswith('BLENDINDICES'):
            blend_indices[elem.SemanticIndex] = data
        elif elem.name.startswith('BLENDWEIGHT'):
            blend_weights[elem.SemanticIndex] = data
        elif elem.name.startswith('TEXCOORD') and elem.is_float():
            texcoords[elem.SemanticIndex] = data
        else:
            print('NOTICE: Storing unhandled semantic %s %s as vertex layer' % (elem.name, elem.Format))
            vertex_layers[elem.name] = data

    return (blend_indices, blend_weights, texcoords, vertex_layers, use_normals)


def import_3dmigoto(operator, context, paths, **kwargs):
    obj = []
    for p in paths:
        try:
            obj.append(import_3dmigoto_vb_ib(operator, context, [p], **kwargs))
        except Fatal as e:
            operator.report({'ERROR'}, str(e) + ': ' + str(p[:2]))
    # FIXME: Group objects together  (Nico:这里他的意思应该是导入后自动放入一个集合里，我们也需要这个功能)
    return obj


def create_material_with_texture(obj, mesh_name, directory):
    # Изменим имя текстуры, чтобы оно точно совпадало с шаблоном (Change the texture name to match the template exactly)
    material_name = f"{mesh_name}_Material"
    # texture_name = f"{mesh_name}-DiffuseMap.jpg"

    mesh_name_split = str(mesh_name).split(".")[0].split("-")
    texture_prefix = mesh_name_split[0] # IB Hash
    if len(mesh_name_split) > 1:
        texture_suffix = f"{mesh_name_split[1]}-DiffuseMap.tga" # Part Name
    else:
        texture_suffix = "-DiffuseMap.tga"

    # 查找是否存在满足条件的转换好的tga贴图文件
    texture_path = find_texture(texture_prefix, texture_suffix, directory)

    # 如果不存在，试试查找jpg文件
    if texture_path is None:
        if len(mesh_name_split) > 1:
            texture_suffix = f"{mesh_name_split[1]}-DiffuseMap.jpg"  # Part Name
        else:
            texture_suffix = "-DiffuseMap.jpg"

        # 查找jpg文件，如果这里没找到的话后面也是正常的，但是这里如果找到了就能起到兼容旧版本jpg文件的作用
        texture_path = find_texture(texture_prefix, texture_suffix, directory)

    # Nico: 这里如果没有检测到对应贴图则不创建材质，也不新建BSDF
    # 否则会造成合并模型后，UV编辑界面选择不同材质的UV会跳到不同UV贴图界面导致无法正常编辑的问题
    if texture_path is None:
        pass
    else:
        # Создание нового материала (Create new materials)
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True

        # Nico: Currently only support EN and ZH-CN
        bsdf = material.node_tree.nodes.get("原理化BSDF")
        if not bsdf:
            bsdf = material.node_tree.nodes.get("Principled BSDF")

        if bsdf:
            # Поиск текстуры (Search for textures)

            if texture_path:
                tex_image = material.node_tree.nodes.new('ShaderNodeTexImage')
                tex_image.image = bpy.data.images.load(texture_path)

                # 因为tga格式贴图有alpha通道，所以必须用CHANNEL_PACKED才能显示正常颜色
                tex_image.image.alpha_mode = "CHANNEL_PACKED"

                material.node_tree.links.new(bsdf.inputs['Base Color'], tex_image.outputs['Color'])

            # Применение материала к мешу (Materials applied to bags)
            if obj.data.materials:
                obj.data.materials[0] = material
            else:
                obj.data.materials.append(material)


def find_texture(texture_prefix, texture_suffix, directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(texture_suffix) and file.startswith(texture_prefix):
                texture_path = os.path.join(root, file)
                return texture_path
    return None


def import_3dmigoto_vb_ib(operator, context, paths, flip_texcoord_v=True, axis_forward='-Z', axis_up='Y'):
    vb, ib, name = load_3dmigoto_mesh(operator, paths)

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(mesh.name, mesh)

    global_matrix = axis_conversion(from_forward=axis_forward, from_up=axis_up).to_4x4()
    obj.matrix_world = global_matrix

    # Attach the vertex buffer layout to the object for later exporting. Can't
    # seem to retrieve this if attached to the mesh - to_mesh() doesn't copy it:
    obj['3DMigoto:VBLayout'] = vb.layout.serialise()
    obj['3DMigoto:VBStride'] = vb.layout.stride
    obj['3DMigoto:FirstVertex'] = vb.first

    # 这里我们不像GIMI一样在导入的时候就把Format变成R32_UINT，我们只在导出的时候改变格式
    if ib is not None:
        import_faces_from_ib(mesh, ib)
        # Attach the index buffer layout to the object for later exporting.
        obj['3DMigoto:IBFormat'] = ib.format
        obj['3DMigoto:FirstIndex'] = ib.first
    else:
        import_faces_from_vb(mesh, vb)

    (blend_indices, blend_weights, texcoords, vertex_layers, use_normals) = import_vertices(mesh, vb)

    import_uv_layers(mesh, obj, texcoords, flip_texcoord_v)

    import_vertex_groups(mesh, obj, blend_indices, blend_weights)

    # Validate closes the loops so they don't disappear after edit mode and probably other important things:
    mesh.validate(verbose=False, clean_customdata=False)  # *Very* important to not remove lnors here!
    # 这里的lnors可能指的是mesh.loop里的normal？
    # Not actually sure update is necessary. It seems to update the vertex normals, not sure what else:
    mesh.update()

    # Must be done after validate step:
    if use_normals:
        import_normals_step2(mesh)
    else:
        mesh.calc_normals()

    link_object_to_scene(context, obj)
    obj.select_set(True)
    set_active_object(context, obj)

    operator.report({'INFO'}, "Import Into 3Dmigoto")

    import bmesh
    # 创建 BMesh 副本
    bm = bmesh.new()
    bm.from_mesh(mesh)
    

    # 删除松散点 delete loose before get this
    # bm.verts.ensure_lookup_table()
    # for v in bm.verts:
    #     if not v.link_faces:
    #         bm.verts.remove(v)

    # 将 BMesh 更新回原始网格
    bm.to_mesh(mesh)
    bm.free()

    # 设置导入时的顶点数和索引数，用于插件右键对比是否和原本顶点数量一致
    obj['3DMigoto:OriginalVertexNumber'] = len(mesh.vertices)
    obj['3DMigoto:OriginalIndicesNumber'] = len(mesh.loops)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Nico: 下面是由rayvy提议的添加贴图自动导入支持，需要大量测试如何以优雅的方式和MMT结合在一起
    mesh_prefix: str = str(mesh.name).split(".")[0]
    # operator.report({'INFO'}, mesh_prefix)
    create_material_with_texture(obj, mesh_prefix, os.path.dirname(paths[0][0][0]))
    return obj


@orientation_helper(axis_forward='-Z', axis_up='Y')
class Import3DMigotoFrameAnalysis(bpy.types.Operator, ImportHelper, IOOBJOrientationHelper):
    """Import a mesh dumped with 3DMigoto's frame analysis"""
    bl_idname = "import_mesh.migoto_frame_analysis_mmt"
    bl_label = "Import 3DMigoto Frame Analysis Dump  (MMT)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = '.txt'

    directory: StringProperty(
        name="Directory",
        subtype='DIR_PATH',
        default= "",
    ) # type: ignore

    filter_glob: StringProperty(
        default='*.txt',
        options={'HIDDEN'},
    ) # type: ignore

    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    ) # type: ignore

    flip_texcoord_v: BoolProperty(
        name="Flip TEXCOORD V",
        description="Flip TEXCOORD V asix during importing",
        default=True,
    ) # type: ignore

    load_related: BoolProperty(
        name="Auto-load related meshes",
        description="Automatically load related meshes found in the frame analysis dump",
        default=True,
    ) # type: ignore

    def get_vb_ib_paths(self):
        buffer_pattern = re.compile(r'''-(?:ib|vb[0-9]+)(?P<hash>=[0-9a-f]+)?(?=[^0-9a-f=])''')

        dirname = os.path.dirname(self.filepath)
        ret = set()

        files = []
        if self.load_related:
            for filename in self.files:
                match = buffer_pattern.search(filename.name)
                if match is None or not match.group('hash'):
                    continue
                paths = glob(os.path.join(dirname, '*%s*.txt' % filename.name[match.start():match.end()]))
                files.extend([os.path.basename(x) for x in paths])
        if not files:
            files = [x.name for x in self.files]

        for filename in files:
            match = buffer_pattern.search(filename)
            if match is None:
                raise Fatal(
                    'Unable to find corresponding buffers from filename - ensure you are loading a dump from a timestamped Frame Analysis directory (not a deduped directory)')

            use_bin = False
            if not match.group('hash') and not use_bin:
                self.report({'INFO'},
                            'Filename did not contain hash - if Frame Analysis dumped a custom resource the .txt file may be incomplete, Using .buf files instead')
                use_bin = True  # FIXME: Ask

            ib_pattern = filename[:match.start()] + '-ib*' + filename[match.end():]
            vb_pattern = filename[:match.start()] + '-vb*' + filename[match.end():]
            ib_paths = glob(os.path.join(dirname, ib_pattern))
            vb_paths = glob(os.path.join(dirname, vb_pattern))

            if vb_paths and use_bin:
                vb_bin_paths = [os.path.splitext(x)[0] + '.buf' for x in vb_paths]
                ib_bin_paths = [os.path.splitext(x)[0] + '.buf' for x in ib_paths]
                if all([os.path.exists(x) for x in itertools.chain(vb_bin_paths, ib_bin_paths)]):
                    # When loading the binary files, we still need to process
                    # the .txt files as well, as they indicate the format:
                    ib_paths = list(zip(ib_bin_paths, ib_paths))
                    vb_paths = list(zip(vb_bin_paths, vb_paths))
                else:
                    self.report({'WARNING'}, 'Corresponding .buf files not found - using .txt files')
                    use_bin = False

            # if self.pose_cb:
            #     pose_pattern = filename[:match.start()] + '*-' + self.pose_cb + '=*.txt'
            #     try:
            #         pose_path = glob(os.path.join(dirname, pose_pattern))[0]
            #     except IndexError:
            #         pass

            if len(ib_paths) != 1 or len(vb_paths) != 1:
                raise Fatal(
                    'Only draw calls using a single vertex buffer and a single index buffer are supported for now')

            ret.add((vb_paths[0], ib_paths[0], use_bin))
        return ret

    def execute(self, context):
        # if self.load_buf:
        #     # Is there a way to have the mutual exclusivity reflected in
        #     # the UI? Grey out options or use radio buttons or whatever?
        #     if self.merge_meshes or self.load_related:
        #         self.report({'INFO'}, 'Loading .buf files selected: Disabled incompatible options')
        #     self.merge_meshes = False
        #     self.load_related = False

        try:
            keywords = self.as_keywords(
                ignore=('filepath', 'files', 'filter_glob', 'load_related', 'load_buf', 'pose_cb','directory'))
            paths = self.get_vb_ib_paths()
            self.report({'INFO'}, "test：" + str(paths))
            import_3dmigoto(self, context, paths, **keywords)
        except Fatal as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


def import_3dmigoto_raw_buffers(operator, context, vb_fmt_path, ib_fmt_path, vb_path=None, ib_path=None, **kwargs):
    paths = (((vb_path, vb_fmt_path), (ib_path, ib_fmt_path), True),)
    return import_3dmigoto(operator, context, paths, **kwargs)


@orientation_helper(axis_forward='-Z', axis_up='Y')
class Import3DMigotoRaw(bpy.types.Operator, ImportHelper, IOOBJOrientationHelper):
    """Import raw 3DMigoto vertex and index buffers"""
    bl_idname = "import_mesh.migoto_raw_buffers_mmt"
    bl_label = "Import 3DMigoto Raw Buffers (MMT)"
    # bl_options = {'PRESET', 'UNDO'}
    bl_options = {'UNDO'}

    filename_ext = '.vb;.ib'
    filter_glob: StringProperty(
        default='*.vb;*.ib',
        options={'HIDDEN'},
    ) # type: ignore

    files: CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    ) # type: ignore

    flip_texcoord_v: BoolProperty(
        name="Flip TEXCOORD V",
        description="Flip TEXCOORD V asix during importing",
        default=True,
    ) # type: ignore

    def get_vb_ib_paths(self, filename):
        vb_bin_path = os.path.splitext(filename)[0] + '.vb'
        ib_bin_path = os.path.splitext(filename)[0] + '.ib'
        fmt_path = os.path.splitext(filename)[0] + '.fmt'
        if not os.path.exists(vb_bin_path):
            raise Fatal('Unable to find matching .vb file for %s' % filename)
        if not os.path.exists(ib_bin_path):
            raise Fatal('Unable to find matching .ib file for %s' % filename)
        if not os.path.exists(fmt_path):
            fmt_path = None
        return (vb_bin_path, ib_bin_path, fmt_path)

    def execute(self, context):
        # I'm not sure how to find the Import3DMigotoReferenceInputFormat
        # instance that Blender instantiated to pass the values from one
        # import dialog to another, but since everything is modal we can
        # just use globals:
        global migoto_raw_import_options
        migoto_raw_import_options = self.as_keywords(ignore=('filepath', 'files', 'filter_glob'))

        # 我们需要添加到一个新建的集合里，方便后续操作
        # 这里集合的名称需要为当前文件夹的名称
        collection_name = os.path.basename(os.path.dirname(self.filepath))
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

        done = set()
        dirname = os.path.dirname(self.filepath)
        for filename in self.files:
            try:
                (vb_path, ib_path, fmt_path) = self.get_vb_ib_paths(os.path.join(dirname, filename.name))
                if os.path.normcase(vb_path) in done:
                    continue
                done.add(os.path.normcase(vb_path))

                if fmt_path is not None:
                    obj_results = import_3dmigoto_raw_buffers(self, context, fmt_path, fmt_path, vb_path=vb_path, ib_path=ib_path, **migoto_raw_import_options)
                    # 虽然复制之后名字会多个001 002这种，但是不影响正常使用，只要能达到效果就行了
                    for obj in obj_results:
                        new_object = obj.copy()
                        new_object.data = obj.data.copy()

                        collection.objects.link(new_object)
                        bpy.data.objects.remove(obj)
                else:
                    migoto_raw_import_options['vb_path'] = vb_path
                    migoto_raw_import_options['ib_path'] = ib_path
                    bpy.ops.import_mesh.migoto_input_format('INVOKE_DEFAULT')
            except Fatal as e:
                self.report({'ERROR'}, str(e))


        return {'FINISHED'}


# used to import .fmt file.
class Import3DMigotoReferenceInputFormat(bpy.types.Operator, ImportHelper):
    bl_idname = "import_mesh.migoto_input_format"
    bl_label = "Select a .txt file with matching format"
    bl_options = {'UNDO', 'INTERNAL'}

    filename_ext = '.txt;.fmt'
    filter_glob: StringProperty(
        default='*.txt;*.fmt',
        options={'HIDDEN'},
    ) # type: ignore

    def get_vb_ib_paths(self):
        if os.path.splitext(self.filepath)[1].lower() == '.fmt':
            return (self.filepath, self.filepath)

        buffer_pattern = re.compile(r'''-(?:ib|vb[0-9]+)(?P<hash>=[0-9a-f]+)?(?=[^0-9a-f=])''')

        dirname = os.path.dirname(self.filepath)
        filename = os.path.basename(self.filepath)

        match = buffer_pattern.search(filename)
        if match is None:
            raise Fatal('Reference .txt filename does not look like a 3DMigoto timestamped Frame Analysis Dump')
        ib_pattern = filename[:match.start()] + '-ib*' + filename[match.end():]
        vb_pattern = filename[:match.start()] + '-vb*' + filename[match.end():]
        ib_paths = glob(os.path.join(dirname, ib_pattern))
        vb_paths = glob(os.path.join(dirname, vb_pattern))
        if len(ib_paths) < 1 or len(vb_paths) < 1:
            raise Fatal('Unable to locate reference files for both vertex buffer and index buffer format descriptions')
        return (vb_paths[0], ib_paths[0])

    def execute(self, context):
        global migoto_raw_import_options

        try:
            vb_fmt_path, ib_fmt_path = self.get_vb_ib_paths()
            import_3dmigoto_raw_buffers(self, context, vb_fmt_path, ib_fmt_path, **migoto_raw_import_options)
        except Fatal as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}