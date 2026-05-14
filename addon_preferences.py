import bpy

from .filesystem import FileSystem
from .ldraw_color import LDrawColor


def apply_preferences():
    """Copy addon preferences into FileSystem / LDrawColor class variables."""
    try:
        prefs = bpy.context.preferences.addons[__package__].preferences
    except (KeyError, AttributeError):
        return

    if prefs.ldraw_path:
        FileSystem.ldraw_path = prefs.ldraw_path
    if prefs.studio_ldraw_path:
        FileSystem.studio_ldraw_path = prefs.studio_ldraw_path
    FileSystem.prefer_studio = prefs.prefer_studio
    LDrawColor.use_alt_colors = prefs.use_alt_colors


class LDrawAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    ldraw_path: bpy.props.StringProperty(
        name="LDraw path",
        description="Full filepath to the LDraw Parts Library (https://www.ldraw.org)",
        default=FileSystem.defaults["ldraw_path"],
        subtype='DIR_PATH',
    )

    studio_ldraw_path: bpy.props.StringProperty(
        name="Stud.io LDraw path",
        description="Full filepath to the Stud.io LDraw Parts Library",
        default=FileSystem.defaults["studio_ldraw_path"],
        subtype='DIR_PATH',
    )

    prefer_studio: bpy.props.BoolProperty(
        name="Prefer Stud.io library",
        description="Search for parts in the Stud.io library first",
        default=FileSystem.defaults["prefer_studio"],
    )

    use_alt_colors: bpy.props.BoolProperty(
        name="Use alternate colors",
        description="Use LDCfgalt.ldr instead of LDConfig.ldr",
        default=LDrawColor.defaults["use_alt_colors"],
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "ldraw_path")
        col.prop(self, "studio_ldraw_path")
        col.separator()
        row = col.row()
        row.prop(self, "prefer_studio")
        row.prop(self, "use_alt_colors")


classesToRegister = [LDrawAddonPreferences]
registerClasses, unregisterClasses = bpy.utils.register_classes_factory(classesToRegister)


def register():
    registerClasses()


def unregister():
    unregisterClasses()
