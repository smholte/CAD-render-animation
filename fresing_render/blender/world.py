"""Backgrounds, lighting and the floor.

What the camera sees (background) and what lights the model (lighting) are
set separately, so a solid colour or transparent background can still have
realistic studio or HDRI light and reflections.

Background: COLOR | HDRI | SKY | TRANSPARENT
Lighting:   STUDIO | HDRI | SKY
Floor:      NONE | SHADOW (shadow catcher) | VISIBLE
"""

from __future__ import annotations

import math
import os

import bpy
import numpy as np

from . import build

WORLD_NAME = "FR World"
GROUND_RADIANCE = 4.0   # ground brightness under the physical sky (before the 0.08 strength)
FLOOR_NAME = "FR Floor"
STUDIO_IMAGE = "FR Studio"
FLOOR_MATERIAL = "FR Floor"


# --------------------------------------------------------------------------
# Procedural studio environment (no download needed)
# --------------------------------------------------------------------------

def _studio_pixels(width: int = 2048, height: int = 1024) -> np.ndarray:
    """Equirectangular HDR studio: soft gradient dome + three softboxes + floor bounce."""
    v = (np.arange(height) + 0.5) / height            # 0 bottom .. 1 top (Blender image rows go bottom-up)
    u = (np.arange(width) + 0.5) / width
    lat = (v - 0.5) * math.pi                          # -pi/2 .. pi/2
    lon = (u - 0.5) * 2 * math.pi                      # -pi .. pi
    LON, LAT = np.meshgrid(lon, lat)

    sky = 0.18 + 0.55 * np.clip(np.sin(LAT), 0, 1) ** 0.6   # brighter towards the top
    ground = 0.05 + 0.04 * np.clip(-np.sin(LAT), 0, 1)
    base = np.where(LAT >= 0, sky, ground)
    img = np.repeat(base[:, :, None], 3, axis=2).astype(np.float32)

    def softbox(center_lon, center_lat, w, h, power, tint=(1.0, 1.0, 1.0)):
        dlon = np.angle(np.exp(1j * (LON - center_lon)))
        dlat = LAT - center_lat
        edge = 0.02
        fx = np.clip((w / 2 - np.abs(dlon)) / edge, 0, 1)
        fy = np.clip((h / 2 - np.abs(dlat)) / edge, 0, 1)
        mask = fx * fy
        for c in range(3):
            img[:, :, c] += mask * power * tint[c]

    # key (front-left, high), fill (front-right), rim (back), top strip
    softbox(math.radians(-50), math.radians(35), math.radians(38), math.radians(28), 9.0, (1.0, 0.98, 0.95))
    softbox(math.radians(60), math.radians(20), math.radians(45), math.radians(25), 3.5, (0.95, 0.97, 1.0))
    softbox(math.radians(170), math.radians(30), math.radians(30), math.radians(40), 6.0)
    softbox(0.0, math.radians(80), math.radians(120), math.radians(8), 4.0)
    alpha = np.ones((height, width, 1), dtype=np.float32)
    return np.concatenate([img, alpha], axis=2)


def studio_image() -> bpy.types.Image:
    img = bpy.data.images.get(STUDIO_IMAGE)
    if img is not None and img.size[0] > 0:
        return img
    w, h = 2048, 1024
    img = bpy.data.images.new(STUDIO_IMAGE, w, h, alpha=True, float_buffer=True)
    img.pixels.foreach_set(_studio_pixels(w, h).ravel())
    img.pack()
    return img


# --------------------------------------------------------------------------
# World node tree
# --------------------------------------------------------------------------

def _load_hdri(path: str):
    if not path:
        return None
    path = bpy.path.abspath(path)
    if not os.path.isfile(path):
        return None
    for img in bpy.data.images:
        if bpy.path.abspath(img.filepath) == path:
            return img
    return bpy.data.images.load(path, check_existing=True)


def _env_branch(nt, kind: str, hdri_path: str, rotation_deg: float, strength: float, sun_elev_deg: float, y: float):
    """Create a light source branch; returns its colour output socket."""
    if kind == "SKY":
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.location = (-400, y)
        for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
            try:
                sky.sky_type = t
                break
            except TypeError:
                continue
        if hasattr(sky, "sun_elevation"):
            sky.sun_elevation = math.radians(sun_elev_deg)
            sky.sun_rotation = math.radians(rotation_deg)
        # Below the horizon the physical sky is black; looking down at a machine that reads
        # as night. Show a neutral ground there instead. (The physical sky types ignore the
        # vector input, so the ground is a colour scaled to the sky's brightness.)
        coord = nt.nodes.new("ShaderNodeTexCoord")
        coord.location = (-1100, y)
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        sep.location = (-900, y)
        nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
        below = nt.nodes.new("ShaderNodeMath")
        below.operation = "LESS_THAN"
        below.inputs[1].default_value = 0.0
        below.location = (-700, y + 120)
        nt.links.new(sep.outputs["Z"], below.inputs[0])
        ground = nt.nodes.new("ShaderNodeMix")
        ground.data_type = "RGBA"
        ground.blend_type = "MIX"
        ground.location = (-250, y)
        g = GROUND_RADIANCE
        ground.inputs["B"].default_value = (g * 1.0, g * 0.97, g * 0.92, 1.0)
        nt.links.new(below.outputs["Value"], ground.inputs["Factor"])
        nt.links.new(sky.outputs["Color"], ground.inputs["A"])
        bg = nt.nodes.new("ShaderNodeBackground")
        bg.location = (-50, y)
        bg.inputs["Strength"].default_value = 0.08 * strength
        nt.links.new(ground.outputs["Result"], bg.inputs["Color"])
        return bg.outputs["Background"]

    img = _load_hdri(hdri_path) if kind == "HDRI" else None
    if img is None:
        img = studio_image()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-900, y)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-700, y)
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rotation_deg))
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.location = (-450, y)
    env.image = img
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.location = (-150, y)
    bg.inputs["Strength"].default_value = strength
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    return bg.outputs["Background"]


def apply(scene, settings) -> None:
    """Build world + floor from the scene's FR settings (see props.FRSceneSettings)."""
    s = settings
    world = bpy.data.worlds.get(WORLD_NAME) or bpy.data.worlds.new(WORLD_NAME)
    try:
        world.use_nodes = True
    except Exception:
        pass
    scene.world = world
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    out.location = (600, 0)

    bg_mode = s.background
    light_kind = s.lighting
    if bg_mode == "HDRI":
        light_kind = "HDRI"
    elif bg_mode == "SKY":
        light_kind = "SKY"
    light_path = s.hdri_path if bg_mode == "HDRI" else s.light_hdri_path
    light = _env_branch(nt, light_kind, light_path, s.light_rotation, s.light_strength, s.sun_elevation, 0)

    scene.render.film_transparent = bg_mode == "TRANSPARENT"

    if bg_mode in ("HDRI", "SKY", "TRANSPARENT"):
        nt.links.new(light, out.inputs["Surface"])
    else:  # solid colour seen by the camera, studio/HDRI light everywhere else
        cam_bg = nt.nodes.new("ShaderNodeBackground")
        cam_bg.location = (-150, 250)
        cam_bg.inputs["Color"].default_value = (*s.background_color[:3], 1.0)
        cam_bg.inputs["Strength"].default_value = 1.0
        lp = nt.nodes.new("ShaderNodeLightPath")
        lp.location = (-150, 500)
        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.location = (300, 0)
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
        nt.links.new(light, mix.inputs[1])
        nt.links.new(cam_bg.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

    scene.view_settings.exposure = s.exposure
    update_floor(scene, s)


# --------------------------------------------------------------------------
# Floor
# --------------------------------------------------------------------------

def _floor_material(color) -> bpy.types.Material:
    mat = bpy.data.materials.get(FLOOR_MATERIAL) or bpy.data.materials.new(FLOOR_MATERIAL)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (*color[:3], 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    mat.diffuse_color = (*color[:3], 1.0)
    return mat


def update_floor(scene, s) -> None:
    floor = bpy.data.objects.get(FLOOR_NAME)
    if s.floor == "NONE":
        if floor is not None:
            floor.hide_render = True
            floor.hide_viewport = True
        return
    parts = [ob for ob in build.iter_parts(scene) if ob.visible_get()] or list(build.iter_parts(scene))
    mn, mx = build.world_bounds(parts)
    size = float(np.max(mx - mn)) if parts else 2.0
    center = (mn + mx) / 2
    if floor is None:
        me = bpy.data.meshes.new(FLOOR_NAME)
        r = 1.0
        me.from_pydata([(-r, -r, 0), (r, -r, 0), (r, r, 0), (-r, r, 0)], [], [(0, 1, 2, 3)])
        floor = bpy.data.objects.new(FLOOR_NAME, me)
        scene.collection.objects.link(floor)
        floor["fr_helper"] = True
    elif floor.name not in scene.collection.objects and not any(floor.name in c.objects for c in scene.collection.children_recursive):
        scene.collection.objects.link(floor)
    floor.hide_render = False
    floor.hide_viewport = False
    floor.hide_select = True
    floor.location = (center[0], center[1], mn[2] - s.floor_offset)
    floor.scale = (size * 4, size * 4, 1)
    floor.is_shadow_catcher = s.floor == "SHADOW"
    color = s.floor_color if s.floor_use_own_color else s.background_color
    mat = _floor_material(color)
    if floor.data.materials:
        floor.data.materials[0] = mat
    else:
        floor.data.materials.append(mat)
    floor.display_type = "WIRE" if s.floor == "SHADOW" else "TEXTURED"
