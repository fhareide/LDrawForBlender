import bpy

from . import filesystem
from .ldraw_file import LDrawNode
from .ldraw_colors import LDrawColors
from .blender_materials import BlenderMaterials
from .special_bricks import SpecialBricks

reuse_mesh_data = True


def do_import(filepath, ldraw_path, resolution):
    bpy.context.scene.eevee.use_ssr = True
    bpy.context.scene.eevee.use_ssr_refraction = True
    bpy.context.scene.eevee.use_taa_reprojection = True

    filesystem.search_paths.clear()
    filesystem.append_search_paths(ldraw_path, resolution)

    LDrawColors.read_color_table(ldraw_path)

    LDrawNode.node_cache.clear()
    LDrawNode.face_info_cache.clear()
    LDrawNode.geometry_cache.clear()

    BlenderMaterials.material_list.clear()
    BlenderMaterials.create_blender_node_groups()

    SpecialBricks.slope_angles.clear()
    SpecialBricks.build_slope_angles()

    root_node = LDrawNode(filepath)
    root_node.load()

    name = 'Parts'
    if name in bpy.data.collections:
        collection = bpy.data.collections[name]
        bpy.context.scene.collection.children.link(collection)

    # write_tree = True
    # if write_tree:
    #     path = os.path.join(ldraw_path, 'trees')
    #     pathlib.Path(path).mkdir(parents=True, exist_ok=True)
    #     trees_path = os.path.join(path, f"{os.path.basename(filepath).split('.')[0]}.txt")
    #     with open(trees_path, 'w') as file:
    #         file.write("\n".join(arr))
