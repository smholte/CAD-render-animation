"""Build Blender materials from the material library.

One Blender material per material group ("FR <group>"). Switching a paint
scheme or changing a group's look rebuilds that material's nodes, so every
part in the group updates at once.
"""

from __future__ import annotations

import bpy

from ..core import materials_lib, ral

PREFIX = "FR "


def material_name(group: str) -> str:
    return PREFIX + group


def color_to_linear(color_text: str, fallback=(0.8, 0.8, 0.8)):
    parsed = ral.parse_colour(color_text) if color_text else None
    srgb = parsed[1] if parsed else fallback
    return tuple(ral.srgb_to_linear(c) for c in srgb), srgb


def _set(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        try:
            sock.default_value = value
        except (TypeError, ValueError):
            pass


def build_nodes(mat: bpy.types.Material, material_id: str, color_text: str = "") -> None:
    spec = materials_lib.get(material_id)
    if spec.get("needs_color"):
        lin, srgb = color_to_linear(color_text or materials_lib.DEFAULT_COLOR)
    else:
        srgb = spec.get("base_color", (0.8, 0.8, 0.8))
        lin = tuple(ral.srgb_to_linear(c) for c in srgb)

    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (250, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    _set(bsdf, "Base Color", (*lin, 1.0))
    _set(bsdf, "Metallic", spec.get("metallic", 0.0))
    _set(bsdf, "Roughness", spec.get("roughness", 0.4))
    _set(bsdf, "Specular IOR Level", spec.get("specular", 0.5))
    if spec.get("coat"):
        _set(bsdf, "Coat Weight", spec["coat"])
        _set(bsdf, "Coat Roughness", spec.get("coat_roughness", 0.1))
    if spec.get("transmission"):
        _set(bsdf, "Transmission Weight", spec["transmission"])
        _set(bsdf, "IOR", spec.get("ior", 1.5))
    if spec.get("anisotropic"):
        _set(bsdf, "Anisotropic", spec["anisotropic"])
    if spec.get("emission"):
        _set(bsdf, "Emission Color", (*lin, 1.0))
        _set(bsdf, "Emission Strength", spec.get("emission_strength", 5.0))

    var = spec.get("variation")
    bump = spec.get("bump")
    if var or bump:
        coord = nt.nodes.new("ShaderNodeTexCoord")
        coord.location = (-700, 0)
    if var:
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.location = (-500, 150)
        _set(noise, "Scale", var.get("scale", 20.0))
        _set(noise, "Detail", 4.0)
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        rmap = nt.nodes.new("ShaderNodeMapRange")
        rmap.location = (-250, 0)
        _set(rmap, "To Min", var.get("roughness_min", 0.3))
        _set(rmap, "To Max", var.get("roughness_max", 0.5))
        nt.links.new(noise.outputs["Fac"], rmap.inputs["Value"])
        nt.links.new(rmap.outputs["Result"], bsdf.inputs["Roughness"])
        amount = var.get("color_amount", 0.0)
        if amount:
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.location = (-250, 250)
            fmap = nt.nodes.new("ShaderNodeMapRange")
            fmap.location = (-450, 350)
            _set(fmap, "To Min", 0.0)
            _set(fmap, "To Max", amount * 2)
            nt.links.new(noise.outputs["Fac"], fmap.inputs["Value"])
            nt.links.new(fmap.outputs["Result"], mix.inputs["Factor"])
            mix.inputs["A"].default_value = (*lin, 1.0)
            mix.inputs["B"].default_value = (0.55, 0.55, 0.55, 1.0)
            nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    if bump:
        bn = nt.nodes.new("ShaderNodeTexNoise")
        bn.location = (-500, -250)
        _set(bn, "Scale", bump.get("scale", 500.0))
        nt.links.new(coord.outputs["Object"], bn.inputs["Vector"])
        bnode = nt.nodes.new("ShaderNodeBump")
        bnode.location = (0, -250)
        _set(bnode, "Strength", bump.get("strength", 0.05))
        _set(bnode, "Distance", 0.0005)
        nt.links.new(bn.outputs["Fac"], bnode.inputs["Height"])
        nt.links.new(bnode.outputs["Normal"], bsdf.inputs["Normal"])

    # viewport (solid mode) look
    mat.diffuse_color = (*lin, 1.0)
    mat.metallic = float(spec.get("metallic", 0.0))
    mat.roughness = float(spec.get("roughness", 0.4))
    if spec.get("transmission"):
        mat.diffuse_color = (*lin, 0.35)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    mat["fr_material"] = material_id
    mat["fr_color"] = color_text


def ensure_material(group: str, material_id: str, color_text: str = "") -> bpy.types.Material:
    name = material_name(group)
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        try:
            mat.use_nodes = True
        except Exception:
            pass
    if mat.node_tree is None:
        mat.use_nodes = True
    if mat.get("fr_material") != material_id or mat.get("fr_color") != color_text or not mat.node_tree.nodes:
        build_nodes(mat, material_id, color_text)
    return mat


def assign(ob: bpy.types.Object, mat: bpy.types.Material) -> None:
    if ob.type != "MESH" or ob.data is None:
        return
    if not ob.material_slots:
        ob.data.materials.append(None)
    slot = ob.material_slots[0]
    if slot.link != "OBJECT":
        slot.link = "OBJECT"
    if slot.material is not mat:
        slot.material = mat


def preview_rgb(material_id: str, color_text: str = ""):
    """sRGB colour for UI swatches."""
    spec = materials_lib.get(material_id)
    if spec.get("needs_color"):
        return color_to_linear(color_text or materials_lib.DEFAULT_COLOR)[1]
    return spec.get("base_color", (0.8, 0.8, 0.8))
