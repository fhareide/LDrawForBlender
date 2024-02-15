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


classesToRegister = [
    VertPrecisionOperator,
    ResetGridOperator,
    SnapToBrickOperator,
    SnapToPlateOperator,
    ReimportOperator,
    BatchExportOperator,
    RemoveBevelOperator,
    AddBevelOperator,
    AddEdgeSplitOperator
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
