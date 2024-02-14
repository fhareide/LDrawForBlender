import bpy
import bmesh

from .import_settings import ImportSettings
from .import_options import ImportOptions
from .blender_materials import BlenderMaterials
from .ldraw_file import LDrawFile
from .ldraw_node import LDrawNode
from .filesystem import FileSystem
from .ldraw_color import LDrawColor
from . import helpers
from . import strings
from . import group
from . import ldraw_meta
from . import ldraw_object
from . import matrices


def do_import(filepath, color_code="16", return_mesh=False):
    print(filepath)  # TODO: multiple filepaths?

    ImportSettings.save_settings()
    ImportSettings.apply_settings()

    FileSystem.build_search_paths(parent_filepath=filepath)
    LDrawFile.read_color_table()
    BlenderMaterials.create_blender_node_groups()

    ldraw_file = LDrawFile.get_file(filepath)
    if ldraw_file is None:
        return

    if ldraw_file.is_configuration():
        __load_materials(ldraw_file)
        return

    root_node = LDrawNode()
    root_node.is_root = True
    root_node.file = ldraw_file

    group.groups_setup(filepath)

    # return root_node.load()
    obj = root_node.load(color_code=color_code, return_mesh=return_mesh)

    # s = {str(k): v for k, v in sorted(LDrawNode.geometry_datas2.items(), key=lambda ele: ele[1], reverse=True)}
    # helpers.write_json("gs2.json", s, indent=4)

    BlenderMaterials.reset_caches()
    FileSystem.reset_caches()
    LDrawColor.reset_caches()
    LDrawFile.reset_caches()
    LDrawNode.reset_caches()
    group.reset_caches()
    ldraw_meta.reset_caches()
    ldraw_object.reset_caches()
    matrices.reset_caches()

    return obj

def __load_materials(file):
    ImportOptions.parent_to_empty = False

    # slope texture demonstration
    obj = do_import('3044.dat')
    if obj is not None:
        obj.location.x = 0.0
        obj.location.y = 5.0
        obj.location.z = 0.5

    # texmap demonstration
    obj = do_import('27062p01.dat')
    if obj is not None:
        obj.location.x = 3
        obj.location.y = 5

    # cloth demonstration
    obj = do_import('50231.dat')
    if obj is not None:
        obj.location.x = 6
        obj.location.y = 5

    colors = {}
    group_name = 'blank'
    for line in file.lines:
        clean_line = helpers.clean_line(line)
        strip_line = line.strip()

        if clean_line.startswith("0 // LDraw"):
            group_name = clean_line
            colors[group_name] = []
            continue

        if clean_line.startswith("0 !COLOUR "):
            colors[group_name].append(LDrawColor.parse_color(clean_line))
            continue

    j = 0
    for codes in colors.items():
        for i, color_code in enumerate(codes):
            bm = bmesh.new()

            monkey = True
            if monkey:
                prefix = 'monkey'
                bmesh.ops.create_monkey(bm)
            else:
                prefix = 'cube'
                bmesh.ops.create_cube(bm, size=1.0)

            helpers.ensure_bmesh(bm)

            for f in bm.faces:
                f.smooth = True

            mesh = bpy.data.meshes.new(f"{prefix}_{color_code}")
            mesh[strings.ldraw_color_code_key] = color_code

            material = BlenderMaterials.get_material(color_code, easy_key=True)

            # https://blender.stackexchange.com/questions/23905/select-faces-depending-on-material
            if material.name not in mesh.materials:
                mesh.materials.append(material)
            for face in bm.faces:
                face.material_index = mesh.materials.find(material.name)

            helpers.finish_bmesh(bm, mesh)
            helpers.finish_mesh(mesh)

            obj = bpy.data.objects.new(mesh.name, mesh)
            obj[strings.ldraw_filename_key] = file.name
            obj[strings.ldraw_color_code_key] = color_code

            obj.modifiers.new("Subdivision", type='SUBSURF')
            obj.location.x = i * 3
            obj.location.y = -j * 3

            color = LDrawColor.get_color(color_code)
            obj.color = color.linear_color_a

        j += 1
