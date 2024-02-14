import bpy
import mathutils

from .import_options import ImportOptions
from .pe_texmap import PETexInfo, PETexmap
from .texmap import TexMap
from .geometry_data import FaceData
from . import helpers
from . import ldraw_camera


current_frame = 0
current_step = 0
cameras = []
camera = None


def reset_caches():
    global current_frame
    global current_step
    global cameras
    global camera

    current_frame = 0
    current_step = 0
    cameras.clear()
    camera = None


def meta_bfc(ldraw_node, child_node, matrix, local_cull, winding, invert_next, accum_invert):
    clean_line = child_node.line
    _params = clean_line.split()[2:]

    # https://www.ldraw.org/article/415.html#processing
    if ldraw_node.bfc_certified is not False:
        if ldraw_node.bfc_certified is None and "NOCERTIFY" not in _params:
            ldraw_node.bfc_certified = True

        if "CERTIFY" in _params:
            ldraw_node.bfc_certified = True

        if "NOCERTIFY" in _params:
            ldraw_node.bfc_certified = False

        """
        https://www.ldraw.org/article/415.html#rendering
        Degenerate Matrices. Some orientation matrices do not allow calculation of a determinate.
        This calculation is central to BFC processing. If an orientation matrix for a subfile is
        degenerate, then culling will not be possible for that subfile.

        https://math.stackexchange.com/a/792591
        A singular matrix, also known as a degenerate matrix, is a square matrix whose determinate is zero.
        https://www.algebrapracticeproblems.com/singular-degenerate-matrix/
        A singular (or degenerate) matrix is a square matrix whose inverse matrix cannot be calculated.
        Therefore, the determinant of a singular matrix is equal to 0.
        """
        if matrix.determinant() == 0:
            ldraw_node.bfc_certified = False

    if "CLIP" in _params:
        local_cull = True

    if "NOCLIP" in _params:
        local_cull = False

    if "CCW" in _params:
        if accum_invert:
            winding = "CW"
        else:
            winding = "CCW"

    if "CW" in _params:
        if accum_invert:
            winding = "CCW"
        else:
            winding = "CW"

    if "INVERTNEXT" in _params:
        invert_next = True

    """
    https://www.ldraw.org/article/415.html#rendering
    If the rendering engine does not detect and adjust for reversed matrices, the winding of all polygons in
    the subfile will be switched, causing the subfile to be rendered incorrectly.

    The typical method of determining that an orientation matrix is reversed is to calculate the determinant of
    the matrix. If the determinant is negative, then the matrix has been reversed.

    The typical way to adjust for matrix reversals is to switch the expected winding of the polygon vertices.
    That is, if the file specifies the winding as CW and the orientation matrix is reversed, the rendering
    program would proceed as if the winding is CCW.

    The INVERTNEXT option also reverses the winding of the polygons within the subpart or primitive.
    If the matrix applied to the subpart or primitive has itself been reversed the INVERTNEXT processing
    is done IN ADDITION TO the automatic inversion - the two effectively cancelling each other out.
    """
    if matrix.determinant() < 0:
        if not invert_next:
            if winding == "CW":
                winding = "CCW"
            else:
                winding = "CW"

    return local_cull, winding, invert_next


def meta_print(child_node):
    if ImportOptions.meta_print_write:
        print(child_node.meta_args["message"])

# https://www.ldraw.org/documentation/ldraw-org-file-format-standards/language-extension-for-texture-mapping.html

def meta_texmap(ldraw_node, child_node, matrix):
    if not ImportOptions.meta_texmap:
        return

    clean_line = child_node.line

    if ldraw_node.texmap_start:
        if clean_line == "0 !TEXMAP FALLBACK":
            ldraw_node.texmap_fallback = True
        elif clean_line == "0 !TEXMAP END":
            set_texmap_end(ldraw_node)
    elif clean_line.startswith("0 !TEXMAP START ") or clean_line.startswith("0 !TEXMAP NEXT "):
        if clean_line.startswith("0 !TEXMAP START "):
            ldraw_node.texmap_start = True
        elif clean_line.startswith("0 !TEXMAP NEXT "):
            ldraw_node.texmap_next = True
        ldraw_node.texmap_fallback = False

        method = clean_line.split()[3]

        new_texmap = TexMap(method=method)
        if new_texmap.is_planar():
            _params = clean_line.split(maxsplit=13)  # planar

            (x1, y1, z1, x2, y2, z2, x3, y3, z3) = map(float, _params[4:13])

            texture_params = helpers.parse_csv_line(_params[13], 2)
            texture = texture_params[0]
            glossmap = texture_params[1]
            if glossmap == "":
                glossmap = None

            new_texmap.parameters = [
                matrix @ mathutils.Vector((x1, y1, z1)),
                matrix @ mathutils.Vector((x2, y2, z2)),
                matrix @ mathutils.Vector((x3, y3, z3)),
            ]
            new_texmap.texture = texture
            new_texmap.glossmap = glossmap
        elif new_texmap.is_cylindrical():
            _params = clean_line.split(maxsplit=14)  # cylindrical

            (x1, y1, z1, x2, y2, z2, x3, y3, z3, a) = map(float, _params[4:14])

            texture_params = helpers.parse_csv_line(_params[14], 2)
            texture = texture_params[0]
            glossmap = texture_params[1]
            if glossmap == "":
                glossmap = None

            new_texmap.parameters = [
                matrix @ mathutils.Vector((x1, y1, z1)),
                matrix @ mathutils.Vector((x2, y2, z2)),
                matrix @ mathutils.Vector((x3, y3, z3)),
                a,
            ]
            new_texmap.texture = texture
            new_texmap.glossmap = glossmap
        elif new_texmap.is_spherical():
            _params = clean_line.split(maxsplit=15)  # spherical

            (x1, y1, z1, x2, y2, z2, x3, y3, z3, a, b) = map(float, _params[4:15])

            texture_params = helpers.parse_csv_line(_params[15], 2)
            texture = texture_params[0]
            glossmap = texture_params[1]
            if glossmap == "":
                glossmap = None

            new_texmap.parameters = [
                matrix @ mathutils.Vector((x1, y1, z1)),
                matrix @ mathutils.Vector((x2, y2, z2)),
                matrix @ mathutils.Vector((x3, y3, z3)),
                a,
                b,
            ]
            new_texmap.texture = texture
            new_texmap.glossmap = glossmap

        if ldraw_node.texmap is not None:
            ldraw_node.texmaps.append(ldraw_node.texmap)
        ldraw_node.texmap = new_texmap


def set_texmap_end(ldraw_node):
    try:
        ldraw_node.texmap = ldraw_node.texmaps.pop()
    except IndexError as e:
        print(e)
        import traceback
        print(traceback.format_exc())
        ldraw_node.texmap = None

    ldraw_node.texmap_start = False
    ldraw_node.texmap_next = False
    ldraw_node.texmap_fallback = False


def meta_pe_tex(ldraw_node, child_node, matrix):
    if child_node.meta_command == "pe_tex_info":
        meta_pe_tex_info(ldraw_node, child_node, matrix)
    elif child_node.meta_command == "pe_tex_next_shear":
        """no idea"""
    else:
        ldraw_node.current_pe_tex_path = None
        if child_node.meta_command == "pe_tex_path":
            meta_pe_tex_path(ldraw_node, child_node)


# 0 PE_TEX_PATH 5 0
# 0 PE_TEX_INFO -0.5346 -0.1464 2.2554 3.1670 0.8638 -1.5619 2.4660 -0.0307 -2.4765 12.9236 -0.0535 13.1611 -4.1933 16.2951 8.3761 3.6621 PNGBASE64==
# 0 PE_TEX_PATH 5 2
# 0 PE_TEX_INFO 0.3341 0.3594 6.3035 -1.9794 -0.5399 0.9762 3.5733 -0.0208 2.1631 -5.7369 0.0881 9.8519 7.3309 23.9951 19.4351 14.5649 PNGBASE64==
# 0 PE_TEX_PATH 5 4
# 0 PE_TEX_NEXT_SHEAR
# 0 PE_TEX_INFO 0.6682 7.2554 13.4921 -3.9588 -1.0797 1.9523 -40.5715 0.2365 -24.6051 -16.5249 0.2054 16.5954 15.5934 18.4983 19.7776 12.8449 PNGBASE64==
# -1 is this file
# >= 0 is the file at the nth subfile_line_index
# second arg is the nth subfile_line_index of line of file at that line
# PE_TEX_PATH 5 4 is self.line_type_1_list[5].line_type_1_list[4]
def meta_pe_tex_path(ldraw_node, child_node):
    clean_line = child_node.line
    _params = clean_line.split()[2:]

    ldraw_node.current_pe_tex_path = int(_params[0])
    if len(_params) == 4:
        ldraw_node.current_subfile_pe_tex_path = int(_params[1])


# PE_TEX_INFO bse64_str uses the file's uvs
# PE_TEX_INFO x,y,z,a,b,c,d,e,f,g,h,i,bl/tl,tr/br is matrix and plane coordinates for uv calculations
# multiple PE_TEX_INFO have to be flattened into one
# if no matrix, identity @ rotation?
def meta_pe_tex_info(ldraw_node, child_node, matrix):
    if ldraw_node.current_pe_tex_path is None:
        return

    clean_line = child_node.line
    _params = clean_line.split()[2:]

    pe_tex_info = PETexInfo()
    base64_str = None
    if len(_params) == 1:
        # current_pe_tex_path should be -1
        # meaning this pe_tex_info applies to this file
        base64_str = _params[0]
    elif len(_params) == 17:
        # defines a bounding box and its transformation
        # rotated 90 deg on x, similar to the original part export matrix
        # aa = __reverse_rotation @ obj.matrix_world
        params = _params

        # m03 = float(params[0])
        # m13 = float(params[1])
        # m23 = -float(params[2])
        #
        # m00 = float(params[3])
        # m01 = float(params[4])
        # m02 = -float(params[5])
        #
        # m10 = float(params[6])
        # m11 = float(params[7])
        # m12 = -float(params[8])
        #
        # m20 = -float(params[9])
        # m21 = -float(params[10])
        # m22 = float(params[11])
        #
        # m30 = 0.0
        # m31 = 0.0
        # m32 = 0.0
        # m33 = 1
        #
        # _matrix = mathutils.Matrix((
        #     (m00, m01, m02, m03),
        #     (m10, m11, m12, m13),
        #     (m20, m21, m22, m23),
        #     (m30, m31, m32, m33)
        # ))

        x = float(params[0])
        y = float(params[1])
        z = -float(params[2])

        a = float(params[3])
        b = float(params[4])
        c = -float(params[5])

        d = float(params[6])
        e = float(params[7])
        f = -float(params[8])

        g = -float(params[9])
        h = -float(params[10])
        i = float(params[11])

        _matrix = mathutils.Matrix((
            (a, b, c, x),
            (d, e, f, y),
            (g, h, i, z),
            (0, 0, 0, 1)
        ))

        # this is the original transformation of the bounding box
        _inverse_matrix = _matrix.inverted()

        point_min = mathutils.Vector((0, 0))
        point_max = mathutils.Vector((0, 0))
        point_min.x = float(params[12])
        point_min.y = float(params[13])
        point_max.x = float(params[14])
        point_max.y = float(params[15])
        point_diff = point_max - point_min
        box_extents = 0.5 * mathutils.Vector((1, 1))

        pe_tex_info.point_min = point_min.freeze()
        pe_tex_info.point_max = point_max.freeze()
        pe_tex_info.point_diff = point_diff.freeze()
        pe_tex_info.box_extents = box_extents.freeze()
        pe_tex_info.matrix = (matrix @ _matrix).freeze()
        pe_tex_info.matrix_inverse = _inverse_matrix.freeze()

        # this pe_tex_info applies to the subfile at current_pe_tex_path or
        # the subfile's subfile at subfile_pe_tex_infos[current_pe_tex_path][current_subfile_pe_tex_path]
        base64_str = _params[16]

        # (x, y, z, a, b, c, d, e, f, g, h, i, bl_x, bl_y, tr_x, tr_y) = map(float, _params[0:16])
        # _matrix = mathutils.Matrix((
        #     (a, b, c, x),
        #     (d, e, f, y),
        #     (g, h, i, z),
        #     (0, 0, 0, 1)
        # ))
        # bl = mathutils.Vector((bl_x, bl_y))
        # tr = mathutils.Vector((tr_x, tr_y))
        # diff = tr - bl
        # extents = 0.5 * mathutils.Vector((1, 1))

        # pe_tex_info.min_point = bl.freeze()
        # pe_tex_info.tr = tr.freeze()
        # pe_tex_info.diff = diff
        # pe_tex_info.extents = extents
        # pe_tex_info.matrix = (matrix @ _matrix).freeze()
        # pe_tex_info.matrix_inverse = pe_tex_info.matrix.inverted()

    if base64_str is None:
        return

    from . import base64_handler
    image = base64_handler.named_png_from_base64_str(f"{ldraw_node.file.name}_{ldraw_node.current_pe_tex_path}.png", base64_str)

    pe_tex_info.image = image.name

    if ldraw_node.current_subfile_pe_tex_path is not None:
        ldraw_node.subfile_pe_tex_infos.setdefault(ldraw_node.current_pe_tex_path, {})
        ldraw_node.subfile_pe_tex_infos[ldraw_node.current_pe_tex_path].setdefault(ldraw_node.current_subfile_pe_tex_path, [])
        ldraw_node.subfile_pe_tex_infos[ldraw_node.current_pe_tex_path][ldraw_node.current_subfile_pe_tex_path].append(pe_tex_info)
    else:
        ldraw_node.pe_tex_infos.setdefault(ldraw_node.current_pe_tex_path, [])
        ldraw_node.pe_tex_infos[ldraw_node.current_pe_tex_path].append(pe_tex_info)

    if ldraw_node.current_pe_tex_path == -1:
        ldraw_node.pe_tex_info = ldraw_node.pe_tex_infos[ldraw_node.current_pe_tex_path]


def meta_edge(child_node, color_code, matrix, geometry_data):
    vertices = [matrix @ v for v in child_node.vertices]

    geometry_data.add_edge_data(
        vertices=vertices,
        color_code=color_code,
    )


def meta_face(ldraw_node, child_node, color_code, matrix, geometry_data, winding):
    vertices = FaceData.handle_vertex_winding(child_node, matrix, winding)
    pe_texmap = PETexmap.build_pe_texmap(ldraw_node, child_node)

    geometry_data.add_face_data(
        vertices=vertices,
        color_code=color_code,
        texmap=ldraw_node.texmap,
        pe_texmap=pe_texmap,
    )


def meta_line(child_node, color_code, matrix, geometry_data):
    vertices = [matrix @ v for v in child_node.vertices]

    geometry_data.add_line_data(
        vertices=vertices,
        color_code=color_code,
    )
