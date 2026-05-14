import bpy

import os
import uuid

from .definitions import APP_ROOT
from .ldraw_color import LDrawColor
from .filesystem import FileSystem
from . import strings


class BlenderMaterials:
    __key_map = {}

    @classmethod
    def reset_caches(cls):
        cls.__key_map.clear()

    # https://github.com/bblanimation/abs-plastic-materials
    @classmethod
    def create_blender_node_groups(cls):
        path = os.path.join(APP_ROOT, 'inc', 'all_monkeys.blend')
        if bpy.app.version < (3, 4):
            path = os.path.join(APP_ROOT, 'inc', 'all_monkeys_33.blend')
        elif bpy.app.version < (4,):
            path = os.path.join(APP_ROOT, 'inc', 'all_monkeys_36.blend')

        with bpy.data.libraries.load(path) as (data_from, data_to):
            all_node_groups = False
            if all_node_groups:
                data_to.node_groups = data_from.node_groups
            else:
                do_delete = False
                if do_delete:  # deleting them will cause materials that use those nodes to render solid black
                    data_to.node_groups = []
                    for c in data_from.node_groups:
                        existing_node_group = bpy.data.node_groups.get(c)
                        if existing_node_group is not None:
                            bpy.data.node_groups.remove(existing_node_group)
                        if c.startswith("_") or c.startswith("LEGO"):
                            data_to.node_groups.append(c)
                else:  # don't import the node group again if there is already one that exists with that name
                    data_to.node_groups = [c for c in data_from.node_groups if bpy.data.node_groups.get(c) is None and (c.startswith("_") or c.startswith("LEGO"))]
        for node_group in data_to.node_groups:
            node_group.use_fake_user = True

    @classmethod
    def get_material(cls, color_code, bfc_certified=True, part_slopes=None, parts_cloth=False, texmap=None, pe_texmap=None, easy_key=True, mark_as_asset=False):
            
        color = LDrawColor.get_color(color_code)
        bfc_certified = bfc_certified is True

        if easy_key:
            key = color_code + "-" + color.name
        else:
            key = cls.__build_key(color, bfc_certified, part_slopes, parts_cloth, texmap, pe_texmap)

        # Reuse current material if it exists, otherwise create a new material
        material = bpy.data.materials.get(key)
        if material is not None:
            return material

        material = cls.__create_node_based_material(
            key,
            color,
            bfc_certified=bfc_certified,
            part_slopes=part_slopes,
            parts_cloth=parts_cloth,
            texmap=texmap,
            pe_texmap=pe_texmap,
            mark_as_asset=mark_as_asset
        )
        return material

    @classmethod
    def __build_key(cls, color, bfc_certified, part_slopes, parts_cloth, texmap, pe_texmap):
        _key = ()

        _key += (color.name, color.code,)

        _key += (bfc_certified,)

        _key += (LDrawColor.use_alt_colors,)

        if part_slopes is not None:
            _key += (part_slopes,)

        if parts_cloth:
            _key += ("cloth",)

        if texmap is not None:
            _key += (texmap.method, texmap.texture, texmap.glossmap,)

        if pe_texmap is not None:
            _key += (pe_texmap.texture,)

        str_key = str(_key)
        if len(str_key) < 60:
            return str(str_key)

        key = cls.__key_map.get(_key)
        if key is None:
            cls.__key_map[_key] = str(uuid.uuid4())
            key = cls.__key_map.get(_key)

        return key

    @classmethod
    def __create_node_based_material(cls, key, color, bfc_certified=True, part_slopes=None, parts_cloth=False, texmap=None, pe_texmap=None, mark_as_asset=False):
        material = bpy.data.materials.new(key)
        material.use_fake_user = True
        material.use_nodes = True
        material.use_backface_culling = bfc_certified
        if mark_as_asset:
          material.asset_mark()
          material.asset_data.tags.new("ldraw")
        
        #bpy.data.materials.get(key).asset_mark()

        nodes = material.node_tree.nodes
        links = material.node_tree.links

        nodes.clear()

        out = cls.__node_output_material(nodes, 200, 0)

        node, rgb_node, mix_rgb_node = cls.__node_group_color_code(color, nodes, links, 200, 0)
        diff_color = color.linear_color_a
        material.diffuse_color = diff_color
        material[strings.ldraw_color_code_key] = color.code
        material[strings.ldraw_color_name_key] = color.name

        shader_out = cls.__socket(node.outputs, "Shader", "BSDF")

        if shader_out is None:
            # The LEGO group nodes have no exposed sockets in this Blender version.
            # Fall back to a Principled BSDF built directly from the LDraw color.
            nodes.clear()
            out = cls.__node_output_material(nodes, 300, 0)
            cls.__build_principled_fallback(color, nodes, links, out)
        else:
            links.new(shader_out, out.inputs["Surface"])

            is_transparent = color.alpha < 1.0
            if is_transparent:
                material.refraction_depth = 0.5

            if part_slopes is not None and len(part_slopes) > 0:
                cls.__create_slope(nodes, links, node, -200, -220, part_slopes)

            if parts_cloth:
                cls.__create_cloth(nodes, links, node, -200, -100)

            if texmap is not None:
                color2_in = cls.__socket(mix_rgb_node.inputs, "B", "Color2")
                fac_in = cls.__socket(mix_rgb_node.inputs, "Factor", "Fac")
                spec_in = cls.__socket(node.inputs, "Specular IOR Level", "Specular")
                if color2_in is not None and fac_in is not None:
                    cls.__create_texmap(nodes, links, -500, -140, texmap, color2_in, fac_in, spec_in)

            if pe_texmap is not None:
                color2_in = cls.__socket(mix_rgb_node.inputs, "B", "Color2")
                fac_in = cls.__socket(mix_rgb_node.inputs, "Factor", "Fac")
                if color2_in is not None and fac_in is not None:
                    cls.__create_texture(nodes, links, -500, -140, pe_texmap, color2_in, fac_in)

        if mark_as_asset:
          material.asset_generate_preview()

        return material

    @classmethod
    def __build_principled_fallback(cls, color, nodes, links, out):
        """Principled BSDF fallback used when LEGO group nodes have no exposed sockets."""
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = 0, 0

        base = cls.__socket(bsdf.inputs, "Base Color", "Color")
        if base is not None:
            base.default_value = color.linear_color_a

        is_transparent = color.alpha < 1.0
        alpha_in = cls.__socket(bsdf.inputs, "Alpha")
        if alpha_in is not None:
            alpha_in.default_value = color.alpha

        if is_transparent:
            trans_in = cls.__socket(bsdf.inputs, "Transmission Weight", "Transmission")
            if trans_in is not None:
                trans_in.default_value = 1.0
            ior_in = cls.__socket(bsdf.inputs, "IOR")
            if ior_in is not None:
                ior_in.default_value = 1.46

        mat_name = color.material_name or ""
        rough_in = cls.__socket(bsdf.inputs, "Roughness")
        metal_in = cls.__socket(bsdf.inputs, "Metallic")

        if mat_name == "chrome":
            if rough_in: rough_in.default_value = 0.05
            if metal_in: metal_in.default_value = 1.0
        elif mat_name == "metal":
            if rough_in: rough_in.default_value = 0.3
            if metal_in: metal_in.default_value = 1.0
        elif mat_name == "pearlescent":
            if rough_in: rough_in.default_value = 0.3
        elif mat_name == "rubber":
            if rough_in: rough_in.default_value = 0.9
        elif color.luminance > 0:
            emit_in = cls.__socket(bsdf.inputs, "Emission Color", "Emission")
            emit_str = cls.__socket(bsdf.inputs, "Emission Strength")
            if emit_in is not None:
                emit_in.default_value = color.linear_color_a
            if emit_str is not None:
                emit_str.default_value = color.luminance / 100.0
        else:
            if rough_in: rough_in.default_value = 0.5

        bsdf_out = cls.__socket(bsdf.outputs, "BSDF")
        if bsdf_out is not None:
            links.new(bsdf_out, out.inputs["Surface"])

    @classmethod
    def __node_output_material(cls, nodes, x, y):
        node = nodes.new("ShaderNodeOutputMaterial")
        node.location = x, y
        return node

    @classmethod
    def __node_tree(cls, group_name, use_fake_user=True):
        node = bpy.data.node_groups.new(group_name, "ShaderNodeTree")
        node.use_fake_user = use_fake_user
        return node

    @classmethod
    def __node_group(cls, group_name, nodes, x, y):
        node = nodes.new("ShaderNodeGroup")
        node.node_tree = bpy.data.node_groups[group_name]
        node.name = node.node_tree.name
        node.location = x, y
        return node

    @classmethod
    def __node_group_input(cls, nodes, x, y):
        node = nodes.new("NodeGroupInput")
        node.location = x, y
        return node

    @classmethod
    def __node_group_output(cls, nodes, x, y):
        node = nodes.new("NodeGroupOutput")
        node.location = x, y
        return node

    @classmethod
    def __node_rgb(cls, nodes, x, y):
        node = nodes.new("ShaderNodeRGB")
        node.location = x, y
        return node

    @classmethod
    def __node_mix_rgb(cls, nodes, x, y):
        # ShaderNodeMixRGB was removed in Blender 4.3; use the generic ShaderNodeMix instead
        if bpy.app.version >= (4, 3):
            node = nodes.new("ShaderNodeMix")
            node.data_type = 'RGBA'
        else:
            node = nodes.new("ShaderNodeMixRGB")
        node.location = x, y
        return node

    @staticmethod
    def __socket(collection, *names):
        """Return the first socket whose name or identifier matches.
        Returns None if the collection is empty or no match is found."""
        for name in names:
            s = collection.get(name)
            if s is not None:
                return s
        # Blender 4.x may store sockets by identifier rather than display name — scan manually
        for name in names:
            for s in collection:
                if s.name == name:
                    return s
        # Last resort: first socket, or None if the collection is empty
        return collection[0] if len(collection) > 0 else None

    @classmethod
    def __node_vertex_color(cls, nodes, x, y):
        node = nodes.new("ShaderNodeVertexColor")
        node.location = x, y
        return node

    @classmethod
    def __node_group_color_code(cls, color, nodes, links, x, y):
        diff_color = color.linear_color_d
        rgb_node = cls.__node_rgb(nodes, x + -600, y + 60)
        rgb_node.outputs["Color"].default_value = diff_color

        mix_rgb_node = cls.__node_mix_rgb(nodes, x + -400, y + 0)
        fac_socket = cls.__socket(mix_rgb_node.inputs, "Factor", "Fac")
        if fac_socket is not None:
            fac_socket.default_value = 0

        node = cls.__node_color_code_material(nodes, color, x + -200, y + 0)

        color1_in = cls.__socket(mix_rgb_node.inputs, "A", "Color1")
        if color1_in is not None:
            links.new(rgb_node.outputs["Color"], color1_in)

        mix_out = cls.__socket(mix_rgb_node.outputs, "Result", "Color")
        color_in = cls.__socket(node.inputs, "Color")
        if mix_out is not None and color_in is not None:
            links.new(mix_out, color_in)

        return node, rgb_node, mix_rgb_node

    @classmethod
    def __node_color_code_material(cls, nodes, color, x, y):
        is_transparent = color.alpha < 1.0

        if color.name == "Milky_White":
            node = cls.__node_lego_milky_white(nodes, x, y)
        elif "Opal" in color.name:
            material_color = color.material_color + (1.0,)
            glitter_color = LDrawColor.lighten_rgba(material_color, 0.5)
            node = cls.__node_lego_opal(nodes, glitter_color, x, y)
        elif color.material_name == "glitter":
            material_color = color.material_color + (1.0,)
            glitter_color = LDrawColor.lighten_rgba(material_color, 0.5)
            node = cls.__node_lego_glitter(nodes, glitter_color, x, y)
        elif color.material_name == "speckle":
            material_color = color.material_color + (1.0,)
            speckle_color = LDrawColor.lighten_rgba(material_color, 0.5)
            node = cls.__node_lego_speckle(nodes, speckle_color, x, y)
        elif color.luminance > 0:
            luminance = color.luminance / 100.0
            node = cls.__node_lego_emission(nodes, luminance, x, y)
        elif color.material_name == "chrome":
            node = cls.__node_lego_chrome(nodes, x, y)
        elif color.material_name == "pearlescent":
            node = cls.__node_lego_pearlescent(nodes, x, y)
        elif color.material_name == "metal":
            node = cls.__node_lego_metal(nodes, x, y)
        elif color.material_name == "rubber":
            if is_transparent:
                node = cls.__node_lego_rubber_translucent(nodes, x, y)
            else:
                node = cls.__node_lego_rubber(nodes, x, y)
        elif is_transparent:
            node = cls.__node_lego_transparent(nodes, x, y)
        else:
            node = cls.__node_lego_standard(nodes, x, y)

        return node

    @classmethod
    # TODO: slight variation in strength for each material
    def __create_slope(cls, nodes, links, node, x, y, part_slopes=None):
        slope_texture = cls.__node_slope_texture_by_angle(nodes, x, y, part_slopes)
        links.new(slope_texture.outputs["Normal"], node.inputs["Normal"])

    @classmethod
    def __node_slope_texture_by_angle(cls, nodes, x, y, angles):
        group_name = "_Slope Texture By Angle"
        node = cls.__node_group(group_name, nodes, x, y)
        if len(angles) > 0:
            node.inputs["Angle 1"].default_value = angles[0]
        if len(angles) > 1:
            node.inputs["Angle 2"].default_value = angles[1]
        if len(angles) > 2:
            node.inputs["Angle 3"].default_value = angles[2]
        if len(angles) > 3:
            node.inputs["Angle 4"].default_value = angles[3]
        node.inputs["Strength"].default_value = 0.6
        return node

    @classmethod
    def __create_texture(cls, nodes, links, x, y, texmap, color_input, alpha_input):
        image_name = texmap.texture
        if image_name is not None:
            texmap_image = cls.__node_tex_image_closest_clip(nodes, x, y, image_name, "sRGB")
            links.new(texmap_image.outputs["Color"], color_input)
            links.new(texmap_image.outputs["Alpha"], alpha_input)

    @classmethod
    def __create_texmap(cls, nodes, links, x, y, texmap, color_input, alpha_input, specular_input):
        cls.__create_texture(nodes, links, x, y, texmap, color_input, alpha_input)

        image_name = texmap.glossmap
        if image_name is not None:
            glossmap_image = cls.__node_tex_image_closest_clip(nodes, x, y - 280, image_name, "Non-Color")
            links.new(glossmap_image.outputs["Color"], specular_input)

    @staticmethod
    def __node_tex_image_closest_clip(nodes, x, y, image_name, colorspace):
        node = nodes.new("ShaderNodeTexImage")
        node.location = x, y
        node.name = image_name
        node.interpolation = "Closest"
        node.extension = "CLIP"

        # TODO: requests retrieve image from ldraw.org
        # https://blender.stackexchange.com/questions/157531/blender-2-8-python-add-texture-image
        image = bpy.data.images.get(image_name)
        if image is None:
            image_path = FileSystem.locate(image_name)
            if image_path is not None:
                image = bpy.data.images.load(image_path)
                image.name = image_name
                image[strings.ldraw_filename_key] = image_name
                image.colorspace_settings.name = colorspace
                image.pack()

        image = bpy.data.images.get(image_name)
        if image_name is not None:
            node.image = image

        return node

    @classmethod
    def __create_cloth(cls, nodes, links, node, x, y):
        cloth = cls.__node_cloth(nodes, x, y)
        links.new(cloth.outputs["Normal"], node.inputs["Normal"])
        links.new(cloth.outputs["Specular"], node.inputs["Specular"])

    @classmethod
    def __node_cloth(cls, nodes, x, y):
        group_name = "_cloth"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_standard(cls, nodes, x, y):
        group_name = "LEGO Standard"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_transparent(cls, nodes, x, y):
        group_name = "LEGO Transparent"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_rubber(cls, nodes, x, y):
        group_name = "LEGO Rubber Solid"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_rubber_translucent(cls, nodes, x, y):
        group_name = "LEGO Rubber Translucent"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_emission(cls, nodes, luminance, x, y):
        group_name = "LEGO Emission"
        node = cls.__node_group(group_name, nodes, x, y)
        node.inputs["Luminance"].default_value = luminance
        return node

    @classmethod
    def __node_lego_chrome(cls, nodes, x, y):
        group_name = "LEGO Chrome"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_pearlescent(cls, nodes, x, y):
        group_name = "LEGO Pearlescent"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_metal(cls, nodes, x, y):
        group_name = "LEGO Metal"
        node = cls.__node_group(group_name, nodes, x, y)
        return node

    @classmethod
    def __node_lego_opal(cls, nodes, glitter_color, x, y):
        group_name = "LEGO Opal"
        node = cls.__node_group(group_name, nodes, x, y)
        node.inputs["Glitter Color"].default_value = glitter_color
        return node

    @classmethod
    def __node_lego_glitter(cls, nodes, glitter_color, x, y):
        group_name = "LEGO Glitter"
        node = cls.__node_group(group_name, nodes, x, y)
        node.inputs["Glitter Color"].default_value = glitter_color
        return node

    @classmethod
    def __node_lego_speckle(cls, nodes, speckle_color, x, y):
        group_name = "LEGO Speckle"
        node = cls.__node_group(group_name, nodes, x, y)
        node.inputs["Speckle Color"].default_value = speckle_color
        return node

    @classmethod
    def __node_lego_milky_white(cls, nodes, x, y):
        group_name = "LEGO Milky White"
        node = cls.__node_group(group_name, nodes, x, y)
        return node
