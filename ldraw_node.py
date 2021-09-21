import math
import os
import uuid
import re

import bmesh
import bpy
import mathutils

from . import blender_materials
from . import import_options
from . import matrices
from . import special_bricks
from . import strings
from .geometry_data import GeometryData
from . import texmap

part_count = 0
current_step = 0
current_frame = 0
geometry_data_cache = dict()
top_collection = None
top_empty = None
gap_scale_empty = None
collection_id_map = dict()
next_collection = None
end_next_collection = False
key_map = dict()


def reset_caches():
    global part_count
    global current_step
    global current_frame
    global geometry_data_cache
    global top_collection
    global top_empty
    global gap_scale_empty
    global collection_id_map
    global next_collection
    global end_next_collection

    part_count = 0
    current_step = 0
    current_frame = 0
    geometry_data_cache = dict()
    top_collection = None
    top_empty = None
    gap_scale_empty = None
    collection_id_map = dict()
    next_collection = None
    end_next_collection = False
    key_map = dict()

    if import_options.meta_step:
        set_step()


def set_step():
    global current_step
    global current_frame

    first_frame = (import_options.starting_step_frame + import_options.frames_per_step)
    current_step_frame = (import_options.frames_per_step * current_step)
    current_frame = first_frame + current_step_frame
    current_step += 1
    if import_options.set_timelime_markers:
        bpy.context.scene.timeline_markers.new("STEP", frame=current_frame)


def create_meta_group(collection_name, parent_collection):
    if collection_name not in bpy.data.collections:
        bpy.data.collections.new(collection_name)
    collection = bpy.data.collections[collection_name]
    if parent_collection is None:
        parent_collection = bpy.context.scene.collection
    if collection.name not in parent_collection.children:
        parent_collection.children.link(collection)
    return collection


# obj.show_name = True
def do_create_object(mesh):
    if import_options.instancing:
        if mesh.name not in bpy.data.objects:
            bpy.data.objects.new(mesh.name, mesh)
        instanced_obj = bpy.data.objects[mesh.name]

        collection_name = 'Parts'
        if collection_name not in bpy.data.collections:
            parts_collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(parts_collection)
            parts_collection.hide_viewport = True
            parts_collection.hide_render = True
        parts_collection = bpy.data.collections[collection_name]

        collection_name = mesh.name
        if collection_name not in bpy.data.collections:
            part_collection = bpy.data.collections.new(collection_name)
            parts_collection.children.link(part_collection)
        part_collection = bpy.data.collections[collection_name]

        if instanced_obj.name not in part_collection.objects:
            part_collection.objects.link(instanced_obj)

        obj = bpy.data.objects.new(mesh.name, None)
        obj.instance_type = 'COLLECTION'
        obj.instance_collection = part_collection
    else:
        obj = bpy.data.objects.new(mesh.name, mesh)
    return obj


# https://docs.blender.org/api/current/bpy.types.bpy_struct.html#bpy.types.bpy_struct.keyframe_insert
# https://docs.blender.org/api/current/bpy.types.Scene.html?highlight=frame_set#bpy.types.Scene.frame_set
# https://docs.blender.org/api/current/bpy.types.Object.html?highlight=rotation_quaternion#bpy.types.Object.rotation_quaternion
def handle_meta_step(obj):
    bpy.context.scene.frame_set(import_options.starting_step_frame)
    obj.hide_viewport = True
    obj.hide_render = True
    obj.keyframe_insert(data_path="hide_render")
    obj.keyframe_insert(data_path="hide_viewport")
    bpy.context.scene.frame_set(current_frame)
    obj.hide_viewport = False
    obj.hide_render = False
    obj.keyframe_insert(data_path="hide_render")
    obj.keyframe_insert(data_path="hide_viewport")


def set_parented_object_matrix(obj, matrix):
    matrix_world = matrices.identity @ matrices.rotation @ matrices.scaled_matrix(import_options.import_scale)
    top_empty.matrix_world = matrix_world
    obj.matrix_world = matrix

    if import_options.make_gaps and import_options.gap_target == "object":
        if import_options.gap_scale_strategy == "object":
            matrix_world = obj.matrix_world @ matrices.scaled_matrix(import_options.gap_scale)
            obj.matrix_world = matrix_world
        elif import_options.gap_scale_strategy == "constraint":
            global gap_scale_empty
            if gap_scale_empty is None and top_collection is not None:
                gap_scale_empty = bpy.data.objects.new("gap_scale", None)
                matrix_world = gap_scale_empty.matrix_world @ matrices.scaled_matrix(import_options.gap_scale)
                gap_scale_empty.matrix_world = matrix_world
                top_collection.objects.link(gap_scale_empty)
            copy_scale_constraint = obj.constraints.new("COPY_SCALE")
            copy_scale_constraint.target = gap_scale_empty
            copy_scale_constraint.target.parent = top_empty

    obj.parent = top_empty  # must be after matrix_world set or else transform is incorrect


def set_object_matrix(obj, matrix):
    matrix_world = matrices.identity @ matrices.rotation @ matrices.scaled_matrix(import_options.import_scale)
    matrix_world = matrix_world @ matrix

    if import_options.make_gaps and import_options.gap_target == "object":
        matrix_world = matrix_world @ matrices.scaled_matrix(import_options.gap_scale)

    obj.matrix_world = matrix_world


def process_face(file, bm, mesh, face, color_code, texmap):
    face.smooth = import_options.shade_smooth
    part_slopes = special_bricks.get_part_slopes(file.name)

    material = blender_materials.get_material(color_code, part_slopes=part_slopes, texmap=texmap)
    # https://blender.stackexchange.com/questions/23905/select-faces-depending-on-material
    if material.name not in mesh.materials:
        mesh.materials.append(material)
    face.material_index = mesh.materials.find(material.name)

    if texmap is not None:
        texmap.uv_unwrap_face(bm, face)


class LDrawNode:
    """
    All of the data that makes up a part.
    """

    def __init__(self):
        self.file = None
        self.color_code = "16"
        self.matrix = matrices.identity
        self.meta_command = None
        self.meta_args = dict()
        self.bfc_winding = "CCW"

    def load(self, parent_matrix=matrices.identity, color_code="16", geometry_data=None, parent_collection=None, is_edge_logo=False):
        global part_count
        global top_collection
        global top_empty
        global next_collection
        global end_next_collection

        # these meta commands affect the scene
        if self.file is None:
            if self.meta_command == "step":
                if import_options.meta_step:
                    set_step()
            elif self.meta_command == "save":
                if import_options.meta_save:
                    if import_options.set_timelime_markers:
                        bpy.context.scene.timeline_markers.new("SAVE", frame=current_frame)
            elif self.meta_command == "clear":
                if import_options.meta_clear:
                    if import_options.set_timelime_markers:
                        bpy.context.scene.timeline_markers.new("CLEAR", frame=current_frame)
                    if top_collection is not None:
                        for ob in top_collection.all_objects:
                            bpy.context.scene.frame_set(current_frame)
                            ob.hide_viewport = True
                            ob.hide_render = True
                            ob.keyframe_insert(data_path="hide_render")
                            ob.keyframe_insert(data_path="hide_viewport")
            elif self.meta_command == "print":
                if import_options.meta_print_write:
                    print(self.meta_args)
            elif self.meta_command == "group_begin":
                create_meta_group(self.meta_args["name"], parent_collection)
                end_next_collection = False
                if self.meta_args["name"] in bpy.data.collections:
                    next_collection = bpy.data.collections[self.meta_args["name"]]
            elif self.meta_command == "group_end":
                end_next_collection = True
            elif self.meta_command == "group_def":
                if self.meta_args["id"] not in collection_id_map:
                    collection_id_map[self.meta_args["id"]] = self.meta_args["name"]
                create_meta_group(self.meta_args["name"], parent_collection)
            elif self.meta_command == "group_nxt":
                if self.meta_args["id"] in collection_id_map:
                    key = collection_id_map[self.meta_args["id"]]
                    if key in bpy.data.collections:
                        next_collection = bpy.data.collections[key]
                end_next_collection = True
            return

        # set the working color code to this file's
        # color code if it isn't color code 16
        if self.color_code != "16":
            color_code = self.color_code

        if self.file.is_edge_logo():
            is_edge_logo = True

        top = False
        matrix = parent_matrix @ self.matrix
        collection = parent_collection

        if geometry_data is None:
            if self.file.is_like_model():
                collection_name = os.path.basename(self.file.name)
                collection = bpy.data.collections.new(collection_name)
                if parent_collection is not None:
                    parent_collection.children.link(collection)

                if top_collection is None:
                    top_collection = collection
                    if import_options.parent_to_empty and top_empty is None:
                        top_empty = bpy.data.objects.new(top_collection.name, None)
                        if top_collection is not None:
                            top_collection.objects.link(top_empty)
            else:  # top-level part
                geometry_data = GeometryData()
                matrix = matrices.identity
                top = True
                part_count += 1

        if import_options.meta_group and next_collection is not None:
            collection = next_collection
            if end_next_collection:
                next_collection = None

        # key = str(hash((self.file.name, color_code, matrix.freeze())))
        _key = []
        _key.append(self.file.name)
        _key.append(color_code)
        _key.append(hash(matrix.freeze()))
        _key = "_".join([str(k).lower() for k in _key])
        # _key = re.sub(r"[^a-z0-9._]", "-", _key)

        if _key not in key_map:
            key_map[_key] = str(uuid.uuid4())
        key = key_map[_key]
        # key = _key

        # TODO: reuse primitive ldraw_nodes
        # if is_primitive then build primitive geometry_data
        # if geometry already in the geometry_cache, reuse it
        # only works with top level data
        # if top and key in serialized_meshes and key not in bpy.data.meshes:
        #     path = os.path.join(this_dir, f"{name}.pickle")
        #     with open(path, 'wb') as file:
        #         file.write(p)
        #
        #     pl = None
        #     with open(path, 'rb') as file:
        #         rp = file.read()
        #         pl = pickle.loads(rp)
        #     print(pl)
        #
        #     e_verts = pl['vertices']
        #     e_edges = []
        #     e_faces = pl['faces']
        #
        #     edge_mesh = bpy.data.meshes.new(key)
        #     edge_mesh.from_pydata(e_verts, e_edges, e_faces)
        #     edge_mesh.update()
        #     edge_mesh.validate()
        # elif key in geometry_data_cache:

        if key in geometry_data_cache:
            geometry_data = geometry_data_cache[key]
        else:
            if geometry_data is not None:
                if (not is_edge_logo) or (is_edge_logo and import_options.display_logo):
                    geometry_data.add_edge_data(matrix, color_code, self.file.geometry)
                geometry_data.add_face_data(matrix, color_code, self.file.geometry)

            for child_node in self.file.child_nodes:
                child_node.load(
                    geometry_data=geometry_data,
                    parent_matrix=matrix,
                    color_code=color_code,
                    parent_collection=collection,
                    is_edge_logo=is_edge_logo,
                )

            # without "if top:"
            # 10030-1 - Imperial Star Destroyer - UCS.mpd top back of the bridge - 3794a.dat renders incorrectly
            if top:
                geometry_data_cache[key] = geometry_data

        if top:
            matrix = parent_matrix @ self.matrix
            e_key = f"e_{key}"

            if key not in bpy.data.meshes:
                bm = bmesh.new()

                mesh = bpy.data.meshes.new(key)
                mesh.name = key
                mesh[strings.ldraw_filename_key] = self.file.name

                # FIXME: 31313 - Mindstorms EV3 - Spike3r.mpd - "31313 - 13710ac01.dat"
                # FIXME: if not treat_shortcut_as_model, texmap uvs may be incorrect, caused by unexpected part transform?
                # FIXME: move uv unwrap to after obj[strings.ldraw_filename_key] = self.file.name
                for fd in geometry_data.face_data:
                    for fi in fd.face_infos:
                        verts = []
                        for vertex in fi.vertices:
                            vert = fd.matrix @ vertex
                            bm_vert = bm.verts.new(vert)
                            verts.append(bm_vert)
                        face = bm.faces.new(verts)

                        color_code = fd.color_code
                        if fi.color_code != "16":
                            color_code = fi.color_code

                        process_face(self.file, bm, mesh, face, color_code, fi.texmap)

                bm.faces.ensure_lookup_table()
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()

                if import_options.remove_doubles:
                    # TODO: if vertices in sharp edge collection, do not add to merge collection
                    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=import_options.merge_distance)

                if import_options.recalculate_normals:
                    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

                # bpy.context.object.data.edges[6].use_edge_sharp = True
                # Create kd tree for fast "find nearest points" calculation
                # https://docs.blender.org/api/blender_python_api_current/mathutils.kdtree.html
                vertices = bm.verts
                kd = mathutils.kdtree.KDTree(len(vertices))
                for i, v in enumerate(vertices):
                    kd.insert(v.co, i)
                kd.balance()

                # increase the distance to look for edges to merge
                # merge line type 2 edges at a greater distance than mesh edges
                distance = import_options.merge_distance
                distance = import_options.merge_distance * 2

                edge_mesh = bpy.data.meshes.new(e_key)
                edge_mesh.name = e_key
                edge_mesh[strings.ldraw_filename_key] = self.file.name

                e_verts = []
                e_edges = []
                e_faces = []
                i = 0
                # Create edge_indices dictionary, which is the list of edges as pairs of indices into our verts array
                edge_indices = set()
                for ed in geometry_data.edge_data:
                    for fi in ed.face_infos:
                        edge_verts = []
                        face_indices = []
                        for vertex in fi.vertices:
                            vert = ed.matrix @ vertex
                            e_verts.append(vert)
                            edge_verts.append(vert)
                            face_indices.append(i)
                            i += 1
                        e_faces.append(face_indices)

                        edges0 = [index for (co, index, dist) in kd.find_range(edge_verts[0], distance)]
                        edges1 = [index for (co, index, dist) in kd.find_range(edge_verts[1], distance)]
                        for e0 in edges0:
                            for e1 in edges1:
                                edge_indices.add((e0, e1))
                                edge_indices.add((e1, e0))

                edge_mesh.from_pydata(e_verts, e_edges, e_faces)
                edge_mesh.update()
                edge_mesh.validate()

                # Find the appropriate mesh edges and make them sharp (i.e. not smooth)
                merge = set()
                for edge in bm.edges:
                    v0 = edge.verts[0].index
                    v1 = edge.verts[1].index
                    if (v0, v1) in edge_indices:
                        merge.add(edge.verts[0])
                        merge.add(edge.verts[1])

                        # Make edge sharp
                        edge.smooth = False

                if import_options.remove_doubles:
                    # if it was detected as a edge, then merge those vertices
                    bmesh.ops.remove_doubles(bm, verts=list(merge), dist=distance)

                bm.to_mesh(mesh)
                bm.clear()
                bm.free()

                mesh.update()
                mesh.validate()

                for edge in mesh.edges:
                    v0 = edge.vertices[0]
                    v1 = edge.vertices[1]
                    if (v0, v1) in edge_indices:
                        edge.use_edge_sharp = True
                        edge.use_freestyle_mark = True

                if import_options.smooth_type == "auto_smooth":
                    mesh.use_auto_smooth = import_options.shade_smooth
                    auto_smooth_angle = 31
                    auto_smooth_angle = 44.97
                    auto_smooth_angle = 51.1
                    auto_smooth_angle = 89.9  # 1.56905 - 89.9 so 90 degrees and up are affected
                    mesh.auto_smooth_angle = math.radians(auto_smooth_angle)

                if import_options.make_gaps and import_options.gap_target == "mesh":
                    mesh.transform(matrices.scaled_matrix(import_options.gap_scale))
                    edge_mesh.transform(matrices.scaled_matrix(import_options.gap_scale))
            mesh = bpy.data.meshes[key]
            obj = do_create_object(mesh)
            obj[strings.ldraw_filename_key] = self.file.name

            if top_empty is None:
                set_object_matrix(obj, matrix)
            else:
                set_parented_object_matrix(obj, matrix)

            if import_options.meta_step:
                handle_meta_step(obj)

            if import_options.smooth_type == "edge_split":
                edge_modifier = obj.modifiers.new("Edge Split", type='EDGE_SPLIT')
                edge_modifier.use_edge_angle = True
                edge_modifier.split_angle = math.radians(89.9)
                edge_modifier.use_edge_sharp = True

            # https://b3d.interplanety.org/en/how-to-get-global-vertex-coordinates/
            if collection is not None:
                collection.objects.link(obj)
            else:
                bpy.context.scene.collection.objects.link(obj)

            if import_options.import_edges:
                edge_mesh = bpy.data.meshes[e_key]
                edge_obj = do_create_object(edge_mesh)
                edge_obj[strings.ldraw_filename_key] = f"{self.file.name}_edges"

                edge_obj.parent = obj
                edge_obj.matrix_world = obj.matrix_world

                if import_options.meta_step:
                    handle_meta_step(obj)

                if collection is not None:
                    collection.objects.link(edge_obj)
                else:
                    bpy.context.scene.collection.objects.link(edge_obj)

        texmap.reset_caches()  # or else the previous part's texmap is applied to this part
        return self
