import os
import bpy
import math
import mathutils
import bmesh

from . import options
from . import matrices

from .ldraw_geometry import LDrawGeometry
from .face_info import FaceInfo
from .blender_materials import BlenderMaterials
from .special_bricks import SpecialBricks


class LDrawNode:
    part_count = 0
    current_step = 0
    last_frame = 0
    face_info_cache = {}
    geometry_cache = {}
    top_collection = None
    top_empty = None
    gap_scale_empty = None
    collection_cache = {}
    next_collection = None
    end_next_collection = False

    def __init__(self, file, color_code="16", matrix=matrices.identity):
        self.file = file
        self.color_code = color_code
        self.matrix = matrix
        self.top = False
        self.meta_command = None
        self.meta_args = {}

    @classmethod
    def reset(cls):
        cls.current_step = 0
        if options.meta_step:
            LDrawNode.set_step()
        cls.top_collection = None
        cls.top_empty = None
        cls.gap_scale_empty = None
        cls.part_count = 0
        cls.collection_cache = {}

    @classmethod
    def reset_caches(cls):
        cls.face_info_cache = {}
        cls.geometry_cache = {}

    @staticmethod
    def set_step():
        start_frame = options.starting_step_frame
        frame_length = options.frames_per_step
        LDrawNode.last_frame = (start_frame + frame_length) + (frame_length * LDrawNode.current_step)
        if options.set_timelime_markers:
            bpy.context.scene.timeline_markers.new('STEP', frame=LDrawNode.last_frame)

    def create_meta_group(self, key, parent_collection):
        if self.meta_args[key] not in LDrawNode.collection_cache:
            LDrawNode.collection_cache[self.meta_args[key]] = bpy.data.collections.new(self.meta_args[key])
        collection = LDrawNode.collection_cache[self.meta_args[key]]
        if parent_collection is None:
            parent_collection = bpy.context.scene.collection
        if collection.name not in parent_collection.children:
            parent_collection.children.link(collection)

    def load(self, parent_matrix=matrices.identity, parent_color_code="16", geometry=None, is_stud=False, is_edge_logo=False, parent_collection=None):
        if self.file is None:
            if self.meta_command == "step":
                LDrawNode.current_step += 1
                LDrawNode.set_step()
            elif self.meta_command == "group_begin":
                self.create_meta_group('name', parent_collection)
                LDrawNode.end_next_collection = False
                if self.meta_args['name'] in LDrawNode.collection_cache:
                    LDrawNode.next_collection = LDrawNode.collection_cache[self.meta_args['name']]
            elif self.meta_command == "group_end":
                LDrawNode.end_next_collection = True
            elif self.meta_command == "group_def":
                self.create_meta_group('id', parent_collection)
            elif self.meta_command == "group_nxt":
                if self.meta_args['id'] in LDrawNode.collection_cache:
                    LDrawNode.next_collection = LDrawNode.collection_cache[self.meta_args['id']]
                LDrawNode.end_next_collection = True
            elif self.meta_command == "save":
                if options.set_timelime_markers:
                    bpy.context.scene.timeline_markers.new('SAVE', frame=LDrawNode.last_frame)
            elif self.meta_command == "clear":
                if options.set_timelime_markers:
                    bpy.context.scene.timeline_markers.new('CLEAR', frame=LDrawNode.last_frame)
                if LDrawNode.top_collection is not None:
                    for ob in LDrawNode.top_collection.all_objects:
                        bpy.context.scene.frame_set(LDrawNode.last_frame)
                        ob.hide_viewport = True
                        ob.hide_render = True
                        ob.keyframe_insert(data_path="hide_render")
                        ob.keyframe_insert(data_path="hide_viewport")
            return

        if options.no_studs and self.file.name.startswith("stud"):
            return

        if self.color_code != "16":
            parent_color_code = self.color_code

        key = []
        key.append(options.resolution)
        key.append(parent_color_code)
        if options.display_logo:
            key.append(options.chosen_logo)
        if options.remove_doubles:
            key.append("rd")
        if options.smooth_type == "auto_smooth":
            key.append("as")
        if options.smooth_type == "edge_split":
            key.append("es")
        if options.use_alt_colors:
            key.append("alt")
        if options.curved_walls:
            key.append("c")
        if options.add_subsurface:
            key.append("ss")
        if parent_color_code == "24":
            key.append("edge")
        key.append(self.file.name)
        key = "_".join([k.lower() for k in key])

        model_types = ['model', 'unofficial_model', 'un-official model', 'submodel', None]
        is_model = self.file.part_type in model_types

        part_types = ['part', 'unofficial_part', 'un-official part']
        is_part = self.file.part_type in part_types

        shortcut_types = ['shortcut', 'unofficial_shortcut', 'un-official shortcut']
        is_shortcut = self.file.part_type in shortcut_types

        subpart_types = ['primitive', 'subpart', 'un-official primitive', 'un-official subpart']
        is_subpart = self.file.part_type in subpart_types

        matrix = parent_matrix @ self.matrix
        file_collection = parent_collection

        if is_model:
            file_collection = bpy.data.collections.new(os.path.basename(self.file.filepath))
            if parent_collection is not None:
                parent_collection.children.link(file_collection)

            if LDrawNode.top_collection is None:
                LDrawNode.top_collection = file_collection
                if options.debug_text:
                    print(LDrawNode.top_collection.name)

                if options.parent_to_empty and LDrawNode.top_empty is None:
                    LDrawNode.top_empty = bpy.data.objects.new(LDrawNode.top_collection.name, None)
                    LDrawNode.top_empty.matrix_world = LDrawNode.top_empty.matrix_world @ matrices.rotation @ matrices.scaled_matrix(options.scale)
                    if LDrawNode.top_collection is not None:
                        LDrawNode.top_collection.objects.link(LDrawNode.top_empty)
                    if options.debug_text:
                        print(LDrawNode.top_empty.name)
        elif geometry is None:
            geometry = LDrawGeometry()
            matrix = matrices.identity
            self.top = True
            LDrawNode.part_count += 1

        if options.meta_group and LDrawNode.next_collection is not None:
            file_collection = LDrawNode.next_collection
            if LDrawNode.end_next_collection:
                LDrawNode.next_collection = None

        if options.debug_text:
            print("===========")
            if is_model:
                print("is_model")
            if is_part:
                print("is_part")
            elif is_shortcut:
                print("is_shortcut")
            elif is_subpart:
                print("is_subpart")
            print(self.file.name)
            print("===========")

        # if it's a part and already in the cache, reuse it
        # meta commands are not in self.top files which is how they are counted
        if self.top and key in LDrawNode.geometry_cache:
            geometry = LDrawNode.geometry_cache[key]
        else:
            if geometry is not None:
                if self.file.name in ["stud.dat", "stud2.dat"]:
                    is_stud = True

                # ["logo.dat", "logo2.dat", "logo3.dat", "logo4.dat", "logo5.dat"]
                if self.file.name in ["logo.dat", "logo2.dat"]:
                    is_edge_logo = True

                vertices = [matrix @ v for v in self.file.geometry.vertices]
                geometry.vertices.extend(vertices)

                if (not is_edge_logo) or (is_edge_logo and options.display_logo):
                    vertices = [matrix @ v for v in self.file.geometry.edge_vertices]
                    geometry.edge_vertices.extend(vertices)

                geometry.edges.extend(self.file.geometry.edges)
                geometry.faces.extend(self.file.geometry.faces)

                if key not in LDrawNode.face_info_cache:
                    new_face_info = []
                    for face_info in self.file.geometry.face_info:
                        copy = FaceInfo(color_code=parent_color_code,
                                        grain_slope_allowed=not is_stud)
                        if parent_color_code == "24":
                            copy.use_edge_color = True
                        if face_info.color_code != "16":
                            copy.color_code = face_info.color_code
                        new_face_info.append(copy)
                    LDrawNode.face_info_cache[key] = new_face_info
                new_face_info = LDrawNode.face_info_cache[key]
                geometry.face_info.extend(new_face_info)

            for child in self.file.child_nodes:
                child.load(parent_matrix=matrix,
                           parent_color_code=parent_color_code,
                           geometry=geometry,
                           is_stud=is_stud,
                           is_edge_logo=is_edge_logo,
                           parent_collection=file_collection)

            if self.top:
                LDrawNode.geometry_cache[key] = geometry

        if self.top:
            if key not in bpy.data.meshes:
                mesh = self.create_mesh(key, geometry)
                self.apply_materials(mesh, geometry, self.file.name)  # combine with create_mesh
                self.bmesh_ops(mesh, geometry)
                if options.smooth_type == "auto_smooth":
                    mesh.use_auto_smooth = options.shade_smooth
                    mesh.auto_smooth_angle = math.radians(89.9)  # 1.56905 - 89.9 so 90 degrees and up are affected
                if options.make_gaps and options.gap_target == "mesh":
                    mesh.transform(matrices.scaled_matrix(options.gap_scale))
                mesh[options.ldraw_name_key] = self.file.name
            mesh = bpy.data.meshes[key]

            if options.import_edges:
                e_key = f"e_{key}"
                if e_key not in bpy.data.meshes:
                    edge_mesh = self.create_edge_mesh(e_key, geometry)
                    edge_mesh[options.ldraw_edge_key] = self.file.name
                    if options.make_gaps and options.gap_target == "mesh":
                        edge_mesh.transform(matrices.scaled_matrix(options.gap_scale))
                edge_mesh = bpy.data.meshes[e_key]

                if options.grease_pencil_edges:
                    gp_mesh = LDrawNode.create_gp_mesh(key, edge_mesh)
                    LDrawNode.apply_gp_materials(gp_mesh)
                    gp_object = bpy.data.objects.new(key, gp_mesh)
                    gp_object.active_material_index = len(gp_mesh.materials)

                    collection_name = "Grease Pencil Edges"
                    if collection_name not in bpy.context.scene.collection.children:
                        collection = bpy.data.collections.new(collection_name)
                        bpy.context.scene.collection.children.link(collection)
                    collection = bpy.context.scene.collection.children[collection_name]
                    collection.objects.link(gp_object)

            obj = LDrawNode.create_object(mesh, parent_matrix, self.matrix)
            obj[options.ldraw_name_key] = self.file.name

            if file_collection is not None:
                file_collection.objects.link(obj)
            else:
                bpy.context.scene.collection.objects.link(obj)

    @staticmethod
    def create_object(mesh, parent_matrix, matrix):
        obj = bpy.data.objects.new(mesh.name, mesh)

        if LDrawNode.top_empty is None:
            obj.matrix_world = matrices.scaled_matrix(options.scale) @ matrices.rotation @ parent_matrix @ matrix
            if options.make_gaps and options.gap_target == "object":
                obj.matrix_world = obj.matrix_world @ matrices.scaled_matrix(options.gap_scale)
        else:
            obj.matrix_world = parent_matrix @ matrix

            if options.make_gaps and options.gap_target == "object":
                if options.gap_scale_strategy == "object":
                    obj.matrix_world = obj.matrix_world @ matrices.scaled_matrix(options.gap_scale)
                elif options.gap_scale_strategy == "constraint":
                    if LDrawNode.gap_scale_empty is None and LDrawNode.top_collection is not None:
                        LDrawNode.gap_scale_empty = bpy.data.objects.new("gap_scale", None)
                        LDrawNode.gap_scale_empty.matrix_world = LDrawNode.gap_scale_empty.matrix_world @ matrices.scaled_matrix(options.gap_scale)
                        LDrawNode.top_collection.objects.link(LDrawNode.gap_scale_empty)
                        if options.debug_text:
                            print(LDrawNode.gap_scale_empty.name)
                    copy_constraint = obj.constraints.new("COPY_SCALE")
                    copy_constraint.target = LDrawNode.gap_scale_empty
                    copy_constraint.target.parent = LDrawNode.top_empty

            obj.parent = LDrawNode.top_empty  # must be after matrix_world set or else transform is incorrect

        # https://docs.blender.org/api/current/bpy.types.bpy_struct.html#bpy.types.bpy_struct.keyframe_insert
        # https://docs.blender.org/api/current/bpy.types.Scene.html?highlight=frame_set#bpy.types.Scene.frame_set
        # https://docs.blender.org/api/current/bpy.types.Object.html?highlight=rotation_quaternion#bpy.types.Object.rotation_quaternion
        if options.meta_step:
            if options.debug_text:
                print(LDrawNode.current_step)

            bpy.context.scene.frame_set(options.starting_step_frame)
            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert(data_path="hide_render")
            obj.keyframe_insert(data_path="hide_viewport")

            bpy.context.scene.frame_set(LDrawNode.last_frame)
            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert(data_path="hide_render")
            obj.keyframe_insert(data_path="hide_viewport")

            if options.debug_text:
                print(LDrawNode.last_frame)

        if options.smooth_type == "edge_split":
            edge_modifier = obj.modifiers.new("Edge Split", type='EDGE_SPLIT')
            edge_modifier.use_edge_angle = True
            edge_modifier.split_angle = math.radians(89.9)  # 1.56905 - 89.9 so 90 degrees and up are affected
            edge_modifier.use_edge_sharp = True

        if options.bevel_edges:
            bevel_modifier = obj.modifiers.new("Bevel", type='BEVEL')
            bevel_modifier.width = 0.10
            bevel_modifier.segments = 4
            bevel_modifier.profile = 0.5
            bevel_modifier.limit_method = 'WEIGHT'
            bevel_modifier.use_clamp_overlap = True

        return obj

    @staticmethod
    def get_top_collection():
        return LDrawNode.top_collection

    @staticmethod
    def get_top_empty():
        return LDrawNode.top_empty

    # https://devtalk.blender.org/t/bmesh-adding-new-verts/11108/2
    # f1 = Vector((rand(-5, 5),rand(-5, 5),rand(-5, 5)))
    # f2 = Vector((rand(-5, 5),rand(-5, 5),rand(-5, 5)))
    # f3 = Vector((rand(-5, 5),rand(-5, 5),rand(-5, 5)))
    # f = [f1, f2, f3]
    # for f in enumerate(faces):
    #     this_vert = bm.verts.new(f)
    @staticmethod
    def do_create_mesh(key, geometry_vertices, geometry_faces):
        vertices = [v.to_tuple() for v in geometry_vertices]
        faces = []
        face_index = 0

        # makes indexes sequential
        for f in geometry_faces:
            new_face = []
            for _ in range(f):
                new_face.append(face_index)
                face_index += 1
            faces.append(new_face)

        # add materials before doing from_pydata step
        mesh = bpy.data.meshes.new(key)
        mesh.from_pydata(vertices, [], faces)
        mesh.validate()
        mesh.update()

        return mesh

    @staticmethod
    def create_edge_mesh(key, geometry):
        return LDrawNode.do_create_mesh(key, geometry.edge_vertices, geometry.edges)

    @staticmethod
    def create_mesh(key, geometry):
        return LDrawNode.do_create_mesh(key, geometry.vertices, geometry.faces)

    # https://blender.stackexchange.com/a/91687
    # for f in bm.faces:
    #     f.smooth = True
    # mesh = context.object.data
    # for f in mesh.polygons:
    #     f.use_smooth = True
    # values = [True] * len(mesh.polygons)
    # mesh.polygons.foreach_set("use_smooth", values)
    # bpy.context.object.active_material.use_backface_culling = True
    # bpy.context.object.active_material.use_screen_refraction = True
    @staticmethod
    def apply_materials(mesh, geometry, filename):
        for i, f in enumerate(mesh.polygons):
            face_info = geometry.face_info[i]

            is_slope_material = False
            if face_info.grain_slope_allowed:
                is_slope_material = SpecialBricks.is_slope_face(filename, f)

            material = BlenderMaterials.get_material(face_info.color_code,
                                                     use_edge_color=face_info.use_edge_color,
                                                     is_slope_material=is_slope_material)
            if material.name not in mesh.materials:
                mesh.materials.append(material)
            f.material_index = mesh.materials.find(material.name)
            f.use_smooth = options.shade_smooth

    @staticmethod
    def bmesh_ops(mesh, geometry):
        if options.bevel_edges:
            mesh.use_customdata_edge_bevel = True

        bm = bmesh.new()
        bm.from_mesh(mesh)

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        if options.remove_doubles:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=options.merge_distance)

        # Find layer for bevel weights
        bevel_weight_layer = None
        if options.bevel_edges:
            if 'BevelWeight' in bm.edges.layers.bevel_weight:
                bevel_weight_layer = bm.edges.layers.bevel_weight['BevelWeight']

        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

        # Create kd tree for fast "find nearest points" calculation
        kd = mathutils.kdtree.KDTree(len(bm.verts))
        for i, v in enumerate(bm.verts):
            kd.insert(v.co, i)
        kd.balance()
        # Create edgeIndices dictionary, which is the list of edges as pairs of indicies into our bm.verts array
        edge_indices = {}
        for i in range(0, len(geometry.edge_vertices), 2):
            edges0 = [index for (co, index, dist) in kd.find_range(geometry.edge_vertices[i + 0], options.merge_distance)]
            edges1 = [index for (co, index, dist) in kd.find_range(geometry.edge_vertices[i + 1], options.merge_distance)]

            for e0 in edges0:
                for e1 in edges1:
                    edge_indices[(e0, e1)] = True
                    edge_indices[(e1, e0)] = True

        # Find the appropriate mesh edges and make them sharp (i.e. not smooth)
        for edge_vertex in bm.edges:
            v0 = edge_vertex.verts[0].index
            v1 = edge_vertex.verts[1].index
            if (v0, v1) in edge_indices:
                # Make edge sharp
                edge_vertex.smooth = False

                # Add bevel weight
                if bevel_weight_layer is not None:
                    bevel_wight = 1.0
                    edge_vertex[bevel_weight_layer] = bevel_wight

        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        bm.to_mesh(mesh)

        bm.clear()
        bm.free()

    @staticmethod
    def create_gp_mesh(key, mesh):
        gp_mesh = bpy.data.grease_pencils.new(key)

        gp_mesh.pixel_factor = 5.0
        gp_mesh.stroke_depth_order = '3D'

        gp_layer = gp_mesh.layers.new('gpl')
        gp_frame = gp_layer.frames.new(1)
        gp_layer.active_frame = gp_frame

        for e in mesh.edges:
            gp_stroke = gp_frame.strokes.new()
            gp_stroke.material_index = 0
            gp_stroke.line_width = 10.0
            for v in e.vertices:
                i = len(gp_stroke.points)
                gp_stroke.points.add(1)
                gp_point = gp_stroke.points[i]
                gp_point.co = mesh.vertices[v].co

        return gp_mesh

    @staticmethod
    def apply_gp_materials(gp_mesh):
        base_material = BlenderMaterials.get_material('0', use_edge_color=True)
        material_name = f"gp_{base_material.name}"
        if material_name not in bpy.data.materials:
            material = base_material.copy()
            material.name = material_name
            bpy.data.materials.create_gpencil_data(material)  # https://developer.blender.org/T67102
        material = bpy.data.materials[material_name]
        gp_mesh.materials.append(material)
