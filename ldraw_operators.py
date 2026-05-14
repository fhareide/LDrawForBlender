import bpy
import os
import re

from .definitions import APP_ROOT
from .import_options import ImportOptions
from .export_options import ExportOptions
from .ldraw_color import LDrawColor
from . import matrices
from . import blender_import
from . import ldraw_export

def ensure_directory_exists(file_path):
    # Split the file path into directory and file components
    directory, filename = os.path.split(file_path)

    # Create all the directories in the path
    os.makedirs(directory, exist_ok=True)

def clean_name_with_backslash(name):
    # Replace invalid characters with underscores
    cleaned_name = re.sub(r'[<>:"/|?*]', '_', name)

    return cleaned_name

class VertPrecisionOperator(bpy.types.Operator):
    """Round vertex positions to Vertex precision places"""
    bl_idname = "export_ldraw.set_vert_precision"
    bl_label = "Set vertex positions"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        self.main(context)
        return {'FINISHED'}

    # bpy.context.object.active_material = bpy.data.materials[0]
    def main(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            mesh = obj.data
            precision = obj.ldraw_props.export_precision

            for vertex in mesh.vertices:
                vertex.co[0] = round(vertex.co[0], precision)
                vertex.co[1] = round(vertex.co[1], precision)
                vertex.co[2] = round(vertex.co[2], precision)


class ResetGridOperator(bpy.types.Operator):
    """Set scene grid to 1"""
    bl_idname = "export_ldraw.reset_grid"
    bl_label = "Reset grid"
    bl_options = {'UNDO'}

    def execute(self, context):
        import_scale = 1
        ldu = 1
        context.space_data.overlay.grid_scale = ldu * import_scale
        return {'FINISHED'}


class SnapToBrickOperator(bpy.types.Operator):
    """Set scene grid to 20 LDU"""
    bl_idname = "export_ldraw.snap_to_brick"
    bl_label = "Set grid to brick"
    bl_options = {'UNDO'}

    def execute(self, context):
        ldu = 20
        import_scale = ImportOptions.import_scale
        context.space_data.overlay.grid_scale = ldu * import_scale
        return {'FINISHED'}


class SnapToPlateOperator(bpy.types.Operator):
    """Set scene grid to 8 LDU"""
    bl_idname = "export_ldraw.snap_to_plate"
    bl_label = "Set grid to plate"
    bl_options = {'UNDO'}

    def execute(self, context):
        ldu = 8
        import_scale = ImportOptions.import_scale
        context.space_data.overlay.grid_scale = ldu * import_scale
        return {'FINISHED'}


class ReimportOperator(bpy.types.Operator):
    """Reimport selected parts"""
    bl_idname = "export_ldraw.reimport_part"
    bl_label = "Reimport"
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            mesh = blender_import.do_import(obj.ldraw_props.filename, color_code=obj.ldraw_props.color_code, return_mesh=True)
            obj.data = mesh

        return {'FINISHED'}

class BatchExportOperator(bpy.types.Operator):
    """Batch export selected parts"""
    bl_idname = "export_ldraw.batch_export"
    bl_label = "Export selected parts"
    bl_description = "Export all selected parts to LDraw files"

    def execute(self, context):
        scene = bpy.context.scene
        # export to blend file location
        basedir = os.path.dirname(bpy.data.filepath)
        if not basedir:
          self.report({'WARNING'},"Please save this .blend file before export.")
          return {'FINISHED'}
        
        if scene.ldraw_props.export_file_path:
          basedir = scene.ldraw_props.export_file_path
        
        view_layer = bpy.context.view_layer

        obj_active = view_layer.objects.active
        selection = bpy.context.selected_objects

        bpy.ops.object.select_all(action='DESELECT')

        LDrawColor.use_alt_colors = scene.ldraw_props.use_alt_colors

        ExportOptions.remove_doubles = scene.ldraw_props.remove_doubles
        ExportOptions.merge_distance = scene.ldraw_props.merge_distance
        ExportOptions.triangulate = scene.ldraw_props.triangulate
        ExportOptions.ngon_handling = scene.ldraw_props.ngon_handling

        for obj in selection:
          obj.select_set(True)

          # some exporters only use the active object
          view_layer.objects.active = obj

          name = obj.ldraw_props.name or clean_name_with_backslash(obj.name)

          # Check if the name doesn't end with ".dat" and add it if missing
          if not name.endswith(".dat"):
              name += ".dat"

          fn = os.path.join(basedir, name)
          abs_path = bpy.path.abspath(fn)


          print("exporting:", abs_path)

          # Ensure that the directory exists before exporting
          ensure_directory_exists(abs_path)

          ldraw_export.do_export(obj, abs_path)

          # Can be used for multiple formats
          # bpy.ops.export_scene.x3d(filepath=fn + ".x3d", use_selection=True)

          obj.select_set(False)

          print("written:", abs_path)            

        return {'FINISHED'}

class RemoveBevelOperator(bpy.types.Operator):
    """Remove bevel modifier from selected objects"""
    bl_idname = "export_ldraw.remove_bevel"
    bl_label = "Remove bevel"
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            for mod in obj.modifiers:
                if mod.type == 'BEVEL':
                    obj.modifiers.remove(mod)

        return {'FINISHED'}


class AddBevelOperator(bpy.types.Operator):
    """Remove existing and add bevel modifier to selected objects"""
    bl_idname = "export_ldraw.add_bevel"
    bl_label = "Add bevel"
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            pos = 0
            for mod in obj.modifiers:
                if mod.type == 'BEVEL':
                    obj.modifiers.remove(mod)

            modifier = obj.modifiers.new("Bevel", type='BEVEL')
            modifier.limit_method = 'ANGLE'
            modifier.width = ImportOptions.bevel_width * ImportOptions.import_scale
            modifier.segments = ImportOptions.bevel_segments

            keys = obj.modifiers.keys()
            i = keys.index(modifier.name)
            obj.modifiers.move(i, pos)

        return {'FINISHED'}


class AddEdgeSplitOperator(bpy.types.Operator):
    """Remove existing and add edge split modifier to selected objects"""
    bl_idname = "export_ldraw.add_edge_split"
    bl_label = "Add edge split"
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            pos = 0
            ii = 0
            for mod in obj.modifiers:
                if mod.type == 'BEVEL':
                    pos = ii
                elif mod.type == 'EDGE_SPLIT':
                    obj.modifiers.remove(mod)
                ii += 1

            modifier = obj.modifiers.new("Edge Split", type='EDGE_SPLIT')
            modifier.use_edge_sharp = True
            modifier.use_edge_angle = True
            modifier.split_angle = matrices.auto_smooth_angle

            keys = obj.modifiers.keys()
            i = keys.index(modifier.name)
            obj.modifiers.move(i, pos)

        return {'FINISHED'}


def parent(arm, obj, bone_name):
    obj.select_set(True)

    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    arm.data.bones.active = arm.data.bones[bone_name]

    bpy.ops.object.parent_set(type='BONE', keep_transform=True)
    bpy.ops.object.select_all(action='DESELECT')


def _get_catalog_id(ldraw_path):
    """Read the first catalog UUID from blender_assets.cats.txt, creating the file if missing."""
    import uuid

    cats_path = os.path.join(ldraw_path, "blender_assets.cats.txt")

    if os.path.isfile(cats_path):
        with open(cats_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.upper().startswith('VERSION'):
                    continue
                parts = line.split(':', 2)
                if len(parts) >= 2:
                    return parts[0]

    # No catalog file yet — create one
    new_uuid = str(uuid.uuid4())
    catalog_lines = (
        "# This is an Asset Catalog Definition file for Blender.\n"
        "#\n"
        "# Empty lines and lines starting with `#` will be ignored.\n"
        '# The first non-ignored line should be the version indicator.\n'
        '# Other lines are of the format "UUID:catalog/path/for/assets:simple catalog name"\n'
        "\n"
        "VERSION 1\n"
        "\n"
        f"{new_uuid}:LdrawColors:LdrawColors\n"
    )
    with open(cats_path, 'w', encoding='utf-8') as f:
        f.write(catalog_lines)

    return new_uuid


def _open_asset_browser(context, library_name=None):
    """Split the 3D viewport horizontally and open an Asset Browser in the new lower 20% area.
    If library_name is given, switch the browser to show that registered library.
    Reuses an existing asset browser panel if one is already open."""
    asset_space = None

    # Reuse an existing asset browser if already visible
    for area in context.screen.areas:
        if area.type == 'FILE_BROWSER':
            space = area.spaces.active
            if space and space.type == 'FILE_BROWSER' and space.browse_mode == 'ASSETS':
                asset_space = space
                break

    if asset_space is None:
        # Prefer context.area (where the button lives) if it is a VIEW_3D,
        # otherwise search for any VIEW_3D on the screen.
        target_area = context.area if (context.area and context.area.type == 'VIEW_3D') else None
        if target_area is None:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    target_area = area
                    break

        if target_area is None:
            return

        # area_split in Blender 4.x requires the WINDOW region to be in the override
        window_region = next((r for r in target_area.regions if r.type == 'WINDOW'), None)
        if window_region is None:
            return

        # With HORIZONTAL split Blender always creates the NEW area at the TOP and
        # keeps the ORIGINAL area at the BOTTOM (resized).
        # factor=0.2 → original (bottom) keeps 20%, new (top) gets 80% as VIEW_3D.
        # We then convert the original bottom area to the Asset Browser.
        try:
            with context.temp_override(area=target_area, region=window_region):
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.2)
        except Exception:
            return

        # target_area is now the bottom 20% — convert it to the Asset Browser
        target_area.type = 'FILE_BROWSER'
        asset_space = target_area.spaces.active
        if asset_space and asset_space.type == 'FILE_BROWSER':
            asset_space.browse_mode = 'ASSETS'

    # Switch to the registered library so catalog names resolve correctly
    if asset_space and library_name:
        try:
            asset_space.params.asset_library_reference = library_name
        except Exception:
            pass


def _generate_materials():
    """Set up paths, read LDConfig.ldr, create node groups, and return (materials, count, ldraw_dir).
    ldraw_dir is the directory of the config file that was actually found.
    Returns (None, 0, None) on failure."""
    from .filesystem import FileSystem
    from .ldraw_file import LDrawFile
    from .ldraw_color import LDrawColor
    from .blender_materials import BlenderMaterials
    from .addon_preferences import apply_preferences

    BlenderMaterials.reset_caches()
    FileSystem.reset_caches()
    LDrawColor.reset_caches()
    LDrawFile.reset_caches()

    apply_preferences()
    FileSystem.build_search_paths()
    ldraw_file = LDrawFile.read_color_table()

    if ldraw_file is None:
        return None, 0, None

    # Find the best writable LDraw directory.
    # Check candidates in priority order: user LDraw path first, then Studio, then the
    # directory of the located config file — taking the first one that is writable.
    ldraw_dir = None
    candidates = []
    if FileSystem.ldraw_path:
        candidates.append(FileSystem.ldraw_path)
    if FileSystem.studio_ldraw_path:
        candidates.append(FileSystem.studio_ldraw_path)
    config_path = FileSystem.locate("LDCfgalt.ldr") or FileSystem.locate("LDConfig.ldr")
    if config_path:
        candidates.append(os.path.dirname(config_path))

    for candidate in candidates:
        if os.path.isdir(candidate) and os.access(candidate, os.W_OK):
            ldraw_dir = candidate
            break

    BlenderMaterials.create_blender_node_groups()

    materials = []
    for color_code in LDrawColor.get_all_color_codes():
        mat = BlenderMaterials.get_material(color_code, easy_key=True, mark_as_asset=True)
        materials.append(mat)

    return materials, len(materials), ldraw_dir


def _save_and_register(materials, ldraw_dir):
    """Save materials to ldrawcolors.blend, update blender_assets.cats.txt, and register
    the LDraw folder as an asset library. Returns the registered library name, or None."""
    if not ldraw_dir or not os.path.isdir(ldraw_dir):
        return None

    catalog_id = _get_catalog_id(ldraw_dir)
    for mat in materials:
        if mat and mat.asset_data is not None:
            mat.asset_data.catalog_id = catalog_id

    datablocks = {m for m in materials if m is not None}
    for ng in bpy.data.node_groups:
        if ng.name.startswith("_") or ng.name.startswith("LEGO"):
            datablocks.add(ng)

    blend_path = os.path.join(ldraw_dir, "ldrawcolors.blend")
    bpy.data.libraries.write(blend_path, datablocks, fake_user=True, compress=True)

    return _register_library(ldraw_dir)


def _register_library(ldraw_dir):
    """Register ldraw_dir as a Blender asset library and save preferences.
    Returns the library name."""
    library_name = "LDraw Colors"
    prefs = bpy.context.preferences
    asset_libs = prefs.filepaths.asset_libraries
    norm_path = os.path.normpath(ldraw_dir)

    for lib in asset_libs:
        if os.path.normpath(lib.path) == norm_path:
            return lib.name  # Already registered — return its current name

    bpy.ops.preferences.asset_library_add(directory=ldraw_dir)
    if asset_libs:
        asset_libs[-1].name = library_name

    bpy.ops.wm.save_userpref()
    return library_name


class GenerateAllMaterialsOperator(bpy.types.Operator):
    """Generate all LDraw materials from LDConfig.ldr, save to ldrawcolors.blend, and open Asset Browser"""
    bl_idname = "ldraw.generate_all_materials"
    bl_label = "Generate LDraw Materials"
    bl_description = (
        "Generates all LDraw materials from LDConfig.ldr, saves them to ldrawcolors.blend "
        "in the LDraw folder, and opens them in the Asset Browser under LdrawColors"
    )
    bl_options = {'UNDO'}

    def execute(self, context):
        materials, count, ldraw_dir = _generate_materials()

        if materials is None:
            self.report({'ERROR'}, "Could not find LDConfig.ldr. Check your LDraw path in addon preferences.")
            return {'CANCELLED'}

        library_name = _save_and_register(materials, ldraw_dir)
        _open_asset_browser(context, library_name=library_name)
        self.report({'INFO'}, f"Generated {count} LDraw materials — saved to {ldraw_dir}.")
        return {'FINISHED'}


class SaveLDrawMaterialLibraryOperator(bpy.types.Operator):
    """Generate all LDraw materials, save them to ldrawcolors.blend, and register as an Asset Library"""
    bl_idname = "ldraw.save_material_library"
    bl_label = "Save LDraw Material Library..."
    bl_description = (
        "Generates all LDraw materials, saves them to ldrawcolors.blend in the LDraw folder, "
        "and registers the folder as a persistent Blender Asset Library"
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        from .filesystem import FileSystem
        layout = self.layout
        col = layout.column(align=True)

        # Find the writable LDraw directory (same logic as _generate_materials)
        candidates = []
        if FileSystem.ldraw_path:
            candidates.append(FileSystem.ldraw_path)
        if FileSystem.studio_ldraw_path:
            candidates.append(FileSystem.studio_ldraw_path)
        config_path = FileSystem.locate("LDCfgalt.ldr") or FileSystem.locate("LDConfig.ldr")
        if config_path:
            candidates.append(os.path.dirname(config_path))
        ldraw_path = next((c for c in candidates if os.path.isdir(c) and os.access(c, os.W_OK)), None)
        ldraw_path = ldraw_path or FileSystem.ldraw_path or "(LDraw path not found)"
        blend_path = os.path.join(ldraw_path, "ldrawcolors.blend")

        col.label(text="The following actions will be performed:", icon='INFO')
        col.separator(factor=0.5)
        col.label(text="  1.  Generate all LDraw materials from LDConfig.ldr")
        col.label(text=f"  2.  Save materials to:")
        col.label(text=f"       {blend_path}")
        col.label(text=f"  3.  Register as Blender Asset Library:")
        col.label(text=f"       {ldraw_path}")
        col.label(text="  4.  Save Blender preferences")
        col.separator(factor=0.5)
        col.label(text="Any existing ldrawcolors.blend will be overwritten.", icon='ERROR')

    def execute(self, context):
        materials, count, ldraw_dir = _generate_materials()

        if materials is None:
            self.report({'ERROR'}, "Could not find LDConfig.ldr. Check your LDraw path.")
            return {'CANCELLED'}

        if not ldraw_dir or not os.path.isdir(ldraw_dir):
            self.report({'ERROR'}, "Could not determine a writable LDraw folder.")
            return {'CANCELLED'}

        library_name = _save_and_register(materials, ldraw_dir)
        blend_path = os.path.join(ldraw_dir, "ldrawcolors.blend")
        _open_asset_browser(context, library_name=library_name)
        self.report({'INFO'}, f"Saved {count} materials to {blend_path} and registered as Asset Library.")
        return {'FINISHED'}


classesToRegister = [
    VertPrecisionOperator,
    ResetGridOperator,
    SnapToBrickOperator,
    SnapToPlateOperator,
    ReimportOperator,
    BatchExportOperator,
    RemoveBevelOperator,
    AddBevelOperator,
    AddEdgeSplitOperator,
    GenerateAllMaterialsOperator,
    SaveLDrawMaterialLibraryOperator,
]

# https://wiki.blender.org/wiki/Reference/Release_Notes/2.80/Python_API/Addons
registerClasses, unregisterClasses = bpy.utils.register_classes_factory(classesToRegister)


def register():
    """Register addon classes"""

    registerClasses()


def unregister():
    """Unregister addon classes"""

    unregisterClasses()


if __name__ == "__main__":
    register()
