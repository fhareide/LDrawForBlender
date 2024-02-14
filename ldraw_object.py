import bpy
from mathutils import Matrix

from .import_options import ImportOptions
from .ldraw_color import LDrawColor
from . import group
from . import strings
from . import ldraw_props
from . import ldraw_meta
from . import matrices



top_empty = None


def reset_caches():
    global top_empty

    top_empty = None


# TODO: to add rigid body - must apply scale and cannot be parented to empty
def create_object(mesh, geometry_data, color_code, matrix, collection):
    obj = bpy.data.objects.new(mesh.name, mesh)
    obj[strings.ldraw_filename_key] = geometry_data.file.name
    obj[strings.ldraw_color_code_key] = color_code

    color = LDrawColor.get_color(color_code)
    obj.color = color.linear_color_a

    ldraw_props.set_props(obj, geometry_data.file, color_code)
    __process_top_object_matrix(obj, matrix)
    __process_top_object_edges(obj)

    __link_obj_to_collection(obj, collection)

    return obj


def create_edge_obj(mesh, geometry_data, color_code, obj, collection):
    edge_obj = bpy.data.objects.new(mesh.name, mesh)
    edge_obj[strings.ldraw_filename_key] = f"{geometry_data.file.name}_edges"
    edge_obj[strings.ldraw_color_code_key] = color_code

    color = LDrawColor.get_color(color_code)
    edge_obj.color = color.linear_edge_color_d

    __link_obj_to_collection(edge_obj, collection)

    edge_obj.parent = obj
    edge_obj.matrix_world = obj.matrix_world

    return edge_obj

def apply_transform(ob, use_location=False, use_rotation=False, use_scale=False):
    mb = ob.matrix_basis
    I = Matrix()
    loc, rot, scale = mb.decompose()

    # rotation
    T = Matrix.Translation(loc)
    R = mb.to_3x3().normalized().to_4x4()
    S = Matrix.Diagonal(scale).to_4x4()

    transform = [I, I, I]
    basis = [T, R, S]

    def swap(i):
        transform[i], basis[i] = basis[i], transform[i]

    if use_location:
        swap(0)
    if use_rotation:
        swap(1)
    if use_scale:
        swap(2)

    M = transform[0] @ transform[1] @ transform[2]
    if hasattr(ob.data, "transform"):
        ob.data.transform(M)
    for c in ob.children:
        c.matrix_local = M @ c.matrix_local

    ob.matrix_basis = basis[0] @ basis[1] @ basis[2]

def __process_top_object_matrix(obj, obj_matrix):
    global top_empty

    import_scale_matrix = matrices.rotation_matrix @ matrices.import_scale_matrix

    matrix_world = import_scale_matrix @ obj_matrix
    obj.matrix_world = matrix_world
    apply_transform(obj, use_rotation=True, use_scale=True)


    if ImportOptions.scale_strategy_value() == "mesh":
        obj.matrix_world = matrix_world @ matrices.import_scale_matrix.inverted()




def __process_top_object_edges(obj):
    if ImportOptions.smooth_type_value() == "edge_split":
        edge_modifier = obj.modifiers.new("Edge Split", type='EDGE_SPLIT')
        edge_modifier.use_edge_sharp = True
        # need this or else items with right angles but aren't marked as sharp aren't shaded properly
        # see the back blue window stripes in 10252-1 - Volkswagen Beetle.mpd
        edge_modifier.use_edge_angle = True
        edge_modifier.split_angle = matrices.auto_smooth_angle


def __link_obj_to_collection(obj, _collection):
    group.link_obj(_collection, obj)

