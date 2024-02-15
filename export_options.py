class ExportOptions:
    defaults = {}

    defaults["remove_doubles"] = False
    remove_doubles = defaults["remove_doubles"]

    defaults["merge_distance"] = 0.05
    merge_distance = defaults["merge_distance"]

    defaults["triangulate"] = True
    triangulate = defaults["triangulate"]

    defaults["ngon_handling"] = "triangulate"
    ngon_handling = defaults["ngon_handling"]

    defaults["selection_only"] = True
    selection_only = defaults["selection_only"]

    defaults["export_precision"] = 3
    export_precision = defaults["export_precision"]
