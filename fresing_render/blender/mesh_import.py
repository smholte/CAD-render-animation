"""Mesh models in the app (task 0117): the file's own materials, the look "From file", the credit line.

A mesh model (glTF, OBJ, FBX) comes in through the same cache as a STEP model (``importer/mesh_reader.py``), so
``build.build`` makes its objects. What a STEP model does not have is kept here:

* **The file's materials** (``info["materials"]`` of the cache): one Blender material "FR file <name>" each – the
  Principled BSDF with the file's colour, metallic, roughness, alpha and its textures (base colour, normal map,
  metallic/roughness), the images **packed** into the project so it stays one file. A part's mesh names its
  material in ``fr_file_material``.
* **The look "From file"** (``core/materials_lib`` id ``from_file``): a group with this look shows every part in
  its own file material (``materials.assign`` swaps it in); a part without one shows the group's colour. After a
  mesh import every new group whose parts all have a file material starts with it, so the model looks as its
  maker drew it; picking another look for a group replaces it as usual.
* **The credit**: the root keeps the file's credit line (``fr_credit``) and full licence text (``fr_credit_text``),
  the Import panel shows the line, and the text block "Model credits" in the project lists every mesh model's
  credit (it is saved with the project).
"""

from __future__ import annotations

import json
import os

import bpy

from ..core import ral

FROM_FILE = "from_file"
PROP_FILE_MATERIAL = "fr_file_material"     # on a part's mesh: the name of its file material
PROP_KIND = "fr_source_kind"                # on a model root: "mesh" for a mesh model
PROP_CREDIT = "fr_credit"
PROP_CREDIT_TEXT = "fr_credit_text"
PROP_OPTIONS = "fr_mesh_options"            # JSON: units, up, split as read
PROP_NOTES = "fr_import_notes"              # JSON list: what the reader guessed or left out
CREDITS_TEXT = "Model credits"
MAT_PREFIX = "FR file "


def is_mesh_model(root) -> bool:
    return root is not None and root.get(PROP_KIND) == "mesh"


def file_material(ob):
    """The file material of a part (``None`` when its mesh has none or it was deleted)."""
    me = ob.data if ob is not None and ob.type == "MESH" else None
    name = me.get(PROP_FILE_MATERIAL) if me is not None else None
    return bpy.data.materials.get(name) if name else None


# ---------------------------------------------------------------------------
# the file's materials
# ---------------------------------------------------------------------------

def _image(cache_dir: str, rel: str, colour: bool):
    """Load a texture of the cache and pack it into the project."""
    path = os.path.join(cache_dir, rel)
    if not os.path.isfile(path):
        return None
    try:
        img = bpy.data.images.load(path, check_existing=False)
    except RuntimeError:
        return None
    img.name = "FR file " + os.path.splitext(os.path.basename(rel))[0][4:]
    try:
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    except TypeError:
        pass
    try:
        img.pack()
    except RuntimeError:
        pass
    return img


def make_materials(info: dict, cache_dir: str) -> list:
    """One Blender material per material of the cache (``None`` where it could not be made)."""
    out = []
    for k, spec in enumerate(info.get("materials") or []):
        try:
            out.append(_make_material(spec, cache_dir))
        except Exception as exc:                 # a broken texture must not stop the import
            print(f"Fresing Render: file material {k} not made: {exc}")
            out.append(None)
    return out


def _make_material(spec: dict, cache_dir: str):
    name = MAT_PREFIX + str(spec.get("name") or "material")
    mat = bpy.data.materials.new(name)
    mat["fr_file_material"] = True
    mat["fr_material"] = "file"
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    rgb = [ral.srgb_to_linear(float(c)) for c in (spec.get("color") or (0.8, 0.8, 0.8))[:3]]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Metallic"].default_value = float(spec.get("metallic", 0.0))
    bsdf.inputs["Roughness"].default_value = float(spec.get("roughness", 0.5))
    alpha = float(spec.get("alpha", 1.0))
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    mat.diffuse_color = (*rgb, alpha)
    mat.use_backface_culling = False
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.location = (-700, 0)
    uv.uv_map = "UVMap"
    base = spec.get("base_texture")
    img = _image(cache_dir, base, True) if base else None
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-450, 200)
        tex.image = img
        tex.label = "Base colour (file)"
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        if any(abs(c - 1.0) > 1e-4 for c in rgb):
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.location = (-150, 200)
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(tex.outputs["Color"], mix.inputs[6])
            mix.inputs[7].default_value = (*rgb, 1.0)
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
        else:
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        mat["fr_has_texture"] = True
    mr = spec.get("mr_texture")
    img = _image(cache_dir, mr, False) if mr else None
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-450, -100)
        tex.image = img
        tex.label = "Metallic / roughness (file)"
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-200, -100)
        nt.links.new(tex.outputs["Color"], sep.inputs["Color"])
        for channel, socket, factor in (("Green", "Roughness", spec.get("roughness", 1.0)),
                                        ("Blue", "Metallic", spec.get("metallic", 1.0))):
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.inputs[1].default_value = float(factor)
            nt.links.new(sep.outputs[channel], mul.inputs[0])
            nt.links.new(mul.outputs[0], bsdf.inputs[socket])
    nrm = spec.get("normal_texture")
    img = _image(cache_dir, nrm, False) if nrm else None
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-450, -400)
        tex.image = img
        tex.label = "Normal map (file)"
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        if spec.get("normal_is_bump"):
            bump = nt.nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = 0.3
            nt.links.new(tex.outputs["Color"], bump.inputs["Height"])
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        else:
            nmap = nt.nodes.new("ShaderNodeNormalMap")
            nmap.location = (-150, -400)
            nmap.uv_map = "UVMap"
            nt.links.new(tex.outputs["Color"], nmap.inputs["Color"])
            nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ---------------------------------------------------------------------------
# after an import
# ---------------------------------------------------------------------------

def take_root_info(root, info: dict) -> None:
    """Keep what a mesh model's cache says about its file on the model root."""
    root[PROP_KIND] = "mesh"
    root[PROP_CREDIT] = str(info.get("credit") or "")
    root[PROP_CREDIT_TEXT] = str(info.get("credit_text") or "")
    root[PROP_OPTIONS] = json.dumps(info.get("options") or {})
    root[PROP_NOTES] = json.dumps(info.get("notes") or [])


def options(root) -> dict:
    try:
        return json.loads(root.get(PROP_OPTIONS, "") or "{}")
    except (TypeError, ValueError):
        return {}


def notes(root) -> list:
    try:
        return list(json.loads(root.get(PROP_NOTES, "") or "[]"))
    except (TypeError, ValueError):
        return []


def write_credits(scene) -> str:
    """The text block "Model credits": every mesh model's credit, saved with the project. Returns its text."""
    from . import build
    lines = []
    for root in build.model_roots(scene):
        if not is_mesh_model(root):
            continue
        src = os.path.basename(root.get(build.PROP_SOURCE, "") or root.name)
        lines.append(f"{root.name} ({src})")
        full = str(root.get(PROP_CREDIT_TEXT, "") or root.get(PROP_CREDIT, "") or "").strip()
        lines.append(full if full else "No credit or licence text in the file: check where it came from.")
        lines.append("")
    text = "\n".join(lines).strip()
    tb = bpy.data.texts.get(CREDITS_TEXT)
    if not text:
        if tb is not None:
            bpy.data.texts.remove(tb)
        return ""
    if tb is None:
        tb = bpy.data.texts.new(CREDITS_TEXT)
    tb.clear()
    tb.write(text + "\n")
    return text


def start_from_file(scene, groups_before: set) -> list[str]:
    """New groups whose parts all have a file material start with the look "From file". Returns their names."""
    from . import build, logic
    s = scene.fresing
    parts: dict[str, list] = {}
    for ob in build.iter_parts(scene):
        parts.setdefault(ob.get(build.PROP_GROUP, ""), []).append(ob)
    changed = []
    for g in s.groups:
        obs = parts.get(g.name, [])
        if g.name in groups_before or not obs or g.material == FROM_FILE:
            continue
        if all(file_material(ob) is not None for ob in obs):
            g.material = FROM_FILE
            changed.append(g.name)
    if changed:
        logic.refresh_group_materials(scene)
    return changed
