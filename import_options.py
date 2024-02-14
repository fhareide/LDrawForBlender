# TODO: remove class
class ImportOptions:
    defaults = {}

    defaults["remove_doubles"] = True
    remove_doubles = defaults["remove_doubles"]

    defaults["merge_distance"] = 0.05
    merge_distance = defaults["merge_distance"]

    defaults["meta_bfc"] = True
    meta_bfc = defaults["meta_bfc"]

    defaults["meta_print_write"] = False
    meta_print_write = defaults["meta_print_write"]

    defaults["meta_texmap"] = False
    meta_texmap = defaults["meta_texmap"]

    defaults["display_logo"] = False
    display_logo = defaults["display_logo"]

    # cast items as list or "EnumProperty(..., default='logo3'): not found in enum members" and a messed up menu
    chosen_logo_choices = list(((logo, logo, logo) for logo in ["logo", "logo2", "logo3", "logo4", "logo5", "high-contrast"]))

    defaults["chosen_logo"] = 2
    chosen_logo = defaults["chosen_logo"]

    @staticmethod
    def chosen_logo_value():
        return ImportOptions.chosen_logo_choices[ImportOptions.chosen_logo][0]

    defaults["shade_smooth"] = True
    shade_smooth = defaults["shade_smooth"]

    smooth_type_choices = (
        ("edge_split", "Edge split", "Use an edge split modifier"),
        ("auto_smooth", "Auto smooth", "Use auto smooth"),
        ("bmesh_split", "bmesh smooth", "Split while processing bmesh"),
    )

    defaults["smooth_type"] = 1
    smooth_type = defaults["smooth_type"]

    @staticmethod
    def smooth_type_value():
        return ImportOptions.smooth_type_choices[ImportOptions.smooth_type][0]

    defaults["import_edges"] = False
    import_edges = defaults["import_edges"]

    defaults["use_freestyle_edges"] = False
    use_freestyle_edges = defaults["use_freestyle_edges"]

    defaults["import_scale"] = 1.0
    import_scale = defaults["import_scale"]

    defaults["parent_to_empty"] = False  # True False
    parent_to_empty = defaults["parent_to_empty"]

    defaults["treat_shortcut_as_model"] = False  # TODO: if true parent to empty at median of group
    treat_shortcut_as_model = defaults["treat_shortcut_as_model"]

    defaults['preserve_hierarchy'] = False
    preserve_hierarchy = defaults['preserve_hierarchy']

    scale_strategy_choices = (
        ("mesh", "Scale mesh", "Apply import scaling to mesh. Recommended for rendering"),
        ("object", "Scale object", "Apply import scaling to object. Recommended for part editing"),
    )

    defaults["scale_strategy"] = 0
    scale_strategy = defaults["scale_strategy"]

    @staticmethod
    def scale_strategy_value():
        return ImportOptions.scale_strategy_choices[ImportOptions.scale_strategy][0]
