import bpy
import os
import re
import time

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


def _set_asset_browser_library(space, library_name):
    """Switch a FILE_BROWSER space to a named asset library. Tries both known property names."""
    for attr in ('asset_library_ref', 'asset_library_reference'):
        try:
            setattr(space.params, attr, library_name)
            return
        except (AttributeError, TypeError):
            pass


def _open_asset_browser(context, library_name=None):
    """Split the 3D viewport horizontally (80/20) and open an Asset Browser in the new lower area.
    If library_name is given, switch the browser to that registered library."""
    asset_browser_space = None

    # Re-use an existing asset browser if one is already open
    for area in context.screen.areas:
        if area.type == 'FILE_BROWSER':
            space = area.spaces.active
            if space and space.type == 'FILE_BROWSER' and space.browse_mode == 'ASSETS':
                asset_browser_space = space
                break

    if asset_browser_space is None:
        # No existing browser — split the 3D viewport
        view3d_area = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                view3d_area = area
                break

        if view3d_area is None:
            return

        old_area_ids = {id(a) for a in context.screen.areas}

        try:
            with context.temp_override(area=view3d_area):
                bpy.ops.screen.area_split(direction='HORIZONTAL', factor=0.8)
        except AttributeError:
            # Blender < 3.2 fallback
            override = context.copy()
            override['area'] = view3d_area
            bpy.ops.screen.area_split(override, direction='HORIZONTAL', factor=0.8)

        for area in context.screen.areas:
            if id(area) not in old_area_ids:
                area.type = 'FILE_BROWSER'
                space = area.spaces.active
                if space and space.type == 'FILE_BROWSER':
                    space.browse_mode = 'ASSETS'
                    asset_browser_space = space
                break

    if library_name and asset_browser_space:
        _set_asset_browser_library(asset_browser_space, library_name)


def _writable_ldraw_dir():
    """Return the best writable LDraw directory based on the current FileSystem settings.

    Uses ldraw_path by default. studio_ldraw_path is only considered when prefer_studio
    is enabled — and even then only as a fallback if ldraw_path is not writable.
    Falls back to the directory of the located config file as a last resort.
    """
    from .filesystem import FileSystem

    if FileSystem.prefer_studio:
        primary = FileSystem.studio_ldraw_path
        secondary = FileSystem.ldraw_path
    else:
        primary = FileSystem.ldraw_path
        secondary = FileSystem.studio_ldraw_path

    candidates = []
    if primary:
        candidates.append(primary)
    if secondary:
        candidates.append(secondary)

    config_path = FileSystem.locate("LDCfgalt.ldr") or FileSystem.locate("LDConfig.ldr")
    if config_path:
        candidates.append(os.path.dirname(config_path))

    for candidate in candidates:
        if os.path.isdir(candidate) and os.access(candidate, os.W_OK):
            return candidate
    return None


def _generate_materials():
    """Set up paths, read LDConfig.ldr, create node groups, and return (materials, count, ldraw_dir).
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

    ldraw_dir = _writable_ldraw_dir()

    BlenderMaterials.create_blender_node_groups()

    materials = []
    for color_code in LDrawColor.get_all_color_codes():
        mat = BlenderMaterials.get_material(color_code, easy_key=True, mark_as_asset=True)
        materials.append(mat)

    return materials, len(materials), ldraw_dir


_PREVIEW_POLL_INTERVAL = 0.3   # seconds between each readiness check
_PREVIEW_TIMEOUT      = 180.0  # give up waiting after 3 minutes

# Shared state published by GenerateLDrawMaterialsOperator, consumed by SaveLDrawMaterialLibraryOperator
_ready_materials  = []
_ready_datablocks = set()
_ready_ldraw_dir  = ""


def _register_asset_library(ldraw_path):
    prefs = bpy.context.preferences
    asset_libs = prefs.filepaths.asset_libraries
    norm_path = os.path.normpath(ldraw_path)

    for lib in asset_libs:
        if os.path.normpath(lib.path) == norm_path:
            return  # Already registered

    bpy.ops.preferences.asset_library_add(directory=ldraw_path)
    if asset_libs:
        asset_libs[-1].name = "LDraw Colors"

    bpy.ops.wm.save_userpref()


class GenerateLDrawMaterialsOperator(bpy.types.Operator):
    """Generate all LDraw materials and wait for preview thumbnails to finish rendering"""
    bl_idname = "ldraw.generate_materials"
    bl_label = "Generate LDraw Materials"
    bl_description = (
        "Generates all LDraw materials from LDConfig.ldr and renders their preview "
        "thumbnails. When finished, click 'Save to Asset Library' to persist them."
    )

    def execute(self, context):
        global _ready_materials, _ready_datablocks, _ready_ldraw_dir

        # Clear any previously generated state so the save button grays out while regenerating
        _ready_materials  = []
        _ready_datablocks = set()
        _ready_ldraw_dir  = ""

        materials, count, ldraw_dir = _generate_materials()

        if materials is None:
            self.report({'ERROR'}, "Could not find LDConfig.ldr. Check your LDraw path.")
            return {'CANCELLED'}

        if not ldraw_dir or not os.path.isdir(ldraw_dir):
            self.report({'ERROR'}, "Could not determine a writable LDraw folder.")
            return {'CANCELLED'}

        catalog_id = _get_catalog_id(ldraw_dir)
        valid_mats = []
        for mat in materials:
            if mat and mat.asset_data is not None:
                mat.asset_data.catalog_id = catalog_id
                valid_mats.append(mat)

        datablocks = set(valid_mats)
        for ng in bpy.data.node_groups:
            if ng.name.startswith("_") or ng.name.startswith("LEGO"):
                datablocks.add(ng)

        self._materials  = valid_mats
        self._datablocks = datablocks
        self._ldraw_dir  = ldraw_dir
        self._total      = len(valid_mats)
        self._start_time = time.time()

        if self._total == 0:
            self.report({'WARNING'}, "No LDraw materials were generated.")
            return {'CANCELLED'}

        context.window_manager.progress_begin(0, self._total)
        context.window_manager.progress_update(0)

        self._timer = context.window_manager.event_timer_add(
            _PREVIEW_POLL_INTERVAL, window=context.window
        )
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        ready = sum(
            1 for m in self._materials
            if m.preview and m.preview.image_size[0] > 0
        )

        context.window_manager.progress_update(ready)

        elapsed = time.time() - self._start_time
        try:
            context.workspace.status_text_set(
                f"LDraw materials — generating previews: {ready}/{self._total}  ({elapsed:.0f}s)"
            )
        except Exception:
            pass

        timed_out = elapsed > _PREVIEW_TIMEOUT
        if ready < self._total and not timed_out:
            return {'RUNNING_MODAL'}

        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        context.window_manager.progress_end()
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass

        if timed_out and ready < self._total:
            self.report(
                {'WARNING'},
                f"Preview timeout — {ready}/{self._total} thumbnails were ready. "
                "You can still save to the library.",
            )

        # Publish state so the save operator can use it
        global _ready_materials, _ready_datablocks, _ready_ldraw_dir
        _ready_materials  = self._materials
        _ready_datablocks = self._datablocks
        _ready_ldraw_dir  = self._ldraw_dir

        self.report(
            {'INFO'},
            f"Generated {len(_ready_materials)} LDraw materials — "
            "click 'Save to Asset Library' to save them.",
        )
        return {'FINISHED'}


class SaveLDrawMaterialLibraryOperator(bpy.types.Operator):
    """Save generated LDraw materials to ldrawcolors.blend and register it as an Asset Library"""
    bl_idname = "ldraw.save_material_library"
    bl_label = "Save to Asset Library..."
    bl_description = (
        "Saves the generated LDraw materials to ldrawcolors.blend in the LDraw folder "
        "and registers it as a persistent Blender Asset Library"
    )

    @classmethod
    def poll(cls, context):
        return len(_ready_materials) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        from .filesystem import FileSystem
        from .addon_preferences import apply_preferences
        apply_preferences()
        layout = self.layout
        col = layout.column(align=True)

        ldraw_path = _ready_ldraw_dir or FileSystem.ldraw_path or "(LDraw path not configured)"
        blend_path = os.path.join(ldraw_path, "ldrawcolors.blend")

        col.label(text=f"{len(_ready_materials)} materials are ready to save.", icon='INFO')
        col.separator(factor=0.5)
        col.label(text="The following actions will be performed:")
        col.separator(factor=0.3)
        col.label(text="  1.  Replace ldrawcolors.blend at:")
        col.label(text=f"       {blend_path}")
        col.label(text="  2.  Register as Blender Asset Library:")
        col.label(text=f"       {ldraw_path}")
        col.label(text="  3.  Save Blender preferences")
        col.label(text="  4.  Remove generated materials from the current session")

    def execute(self, context):
        global _ready_materials, _ready_datablocks, _ready_ldraw_dir

        if not _ready_materials:
            self.report({'ERROR'}, "No materials ready. Run 'Generate LDraw Materials' first.")
            return {'CANCELLED'}

        ldraw_dir = _ready_ldraw_dir
        if not ldraw_dir or not os.path.isdir(ldraw_dir):
            self.report({'ERROR'}, "Could not determine a writable LDraw folder.")
            return {'CANCELLED'}

        blend_path = os.path.join(ldraw_dir, "ldrawcolors.blend")

        if os.path.isfile(blend_path):
            os.remove(blend_path)

        bpy.data.libraries.write(
            blend_path, _ready_datablocks, fake_user=True, compress=True
        )

        # Remove the LDraw materials we generated from the current session.
        # Only materials in _ready_materials are touched — built-in materials,
        # brushes, and anything else already in the file are left completely alone.
        # Skip any material that has users (assigned to a mesh object in the scene).
        for mat in _ready_materials:
            try:
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
                else:
                    # Material is in use; unmark as asset so it does not clutter
                    # the asset browser (it lives in ldrawcolors.blend now)
                    mat.asset_clear()
            except Exception:
                pass
        # Only remove LDraw-addon node-groups that are no longer referenced anywhere
        for ng in list(bpy.data.node_groups):
            if (ng.name.startswith("_") or ng.name.startswith("LEGO")) and ng.users == 0:
                try:
                    bpy.data.node_groups.remove(ng)
                except Exception:
                    pass

        count = len(_ready_materials)

        _ready_materials  = []
        _ready_datablocks = set()
        _ready_ldraw_dir  = ""

        _register_asset_library(ldraw_dir)

        try:
            bpy.ops.asset.library_refresh()
        except Exception:
            pass

        self.report({'INFO'}, f"Saved {count} LDraw materials to {blend_path}.")
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
    GenerateLDrawMaterialsOperator,
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
