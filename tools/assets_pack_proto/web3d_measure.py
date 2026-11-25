"""Task 0344 proof (study files only): what a Web 3D page carries of a pack's 360° photo and pictures, and what a
smaller copy costs in file size and in look. Owner 25 Nov 21:41: the export never carries the pack's full-size HDRIs or
360° photos – a reduced background, and textures baked at the page's size – with the size and look cost measured.

Not part of the app. Runs with Blender as a Python module and the app from this checkout (as the tests do):

    ~/venv/bin/python tools/assets_pack_proto/web3d_measure.py <work folder> <pack root of make_test_pack.py>

1. Background: the test crane with a made-up photo-like 360° picture (4096 x 2048 EXR, drawn here) as its background
   and light, exported with the page's background size of each level (Phone 1024, Balanced 2048, Best 4096 px wide –
   ``core/web3d_env.QUALITY``). Every page is shot in headless Chromium at the SAME page level (Best, auto off), so
   only the background picture differs; the Best export shot twice gives the noise floor.
2. Pictures: one group of the crane gets a pictured look (the test pack's concrete: colour, roughness and relief at
   2k, one picture per 0.2 m – the pack contract), exported at the app's texture sizes 512 / 1024 / 2048 px per
   0.2 m tile and shot from a close camera. The page never holds the original pictures: checked in the .glb.

Look cost = mean absolute difference per pixel (0–255) against the largest size, over the whole picture and over a
crop; plus PSNR. Writes ``<work>/web3d_measure.json`` + ``.md`` and side-by-side crops.
"""

from __future__ import annotations

import json
import math
import os
import re
import struct
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import web3d, web3d_env, world  # noqa: E402
from fresing_render.core import web3d_env as env  # noqa: E402

CRANE = os.path.join(ROOT, "tests", "data", "test_crane_a.step")
SHOT = os.path.join(ROOT, "tools", "web3d_env_shot.js")
W, H = 960, 540


# ---- a made-up photo-like 360° picture --------------------------------------------------------------------------

def make_photo(path: str, width: int = 4096) -> None:
    """Sky with clouds, a row of buildings with windows on the horizon, a ground with grain, a sun – detail like a
    photograph (a smooth made-up sky would make every size look the same). Linear, rows bottom-up."""
    h = width // 2
    rng = np.random.default_rng(3)
    y = (np.arange(h, dtype=np.float32) + 0.5) / h          # 0 = straight down, 1 = straight up
    x = (np.arange(width, dtype=np.float32) + 0.5) / width
    X, Y = np.meshgrid(x, y)
    img = np.zeros((h, width, 3), np.float32)
    up = np.clip((Y - 0.5) * 2, 0, 1)
    sky = np.stack([0.35 + 0.25 * up, 0.5 + 0.25 * up, 0.85 + 0.1 * up], -1) * (0.6 + 0.4 * up[..., None])
    cloud = np.zeros_like(X)
    for k in range(7):
        f = 2 ** (k + 2)
        ph = rng.uniform(0, 6.3, 2)
        cloud += np.sin(f * 6.283 * X + ph[0] + 3 * np.sin(2 * 6.283 * Y)) * np.sin(f * 3.1 * Y + ph[1]) / (k + 1.5)
    cloud = np.clip((cloud - 0.2) * 1.5, 0, 1)[..., None] * (Y > 0.5)[..., None]
    img[:] = sky * (1 - 0.7 * cloud) + 0.9 * cloud
    ground = Y < 0.5
    grain = rng.random((h, width), dtype=np.float32)
    g = (0.18 + 0.08 * np.sin(X * 6.283 * 180) * np.sin(Y * 3.14 * 90) + 0.06 * grain)[..., None]
    img[ground] = (g * np.array([0.9, 0.85, 0.75], np.float32))[ground]
    # buildings: blocks along the horizon with a grid of windows
    x0 = 0
    while x0 < width:
        bw = int(rng.integers(width // 90, width // 25))
        bh = rng.uniform(0.02, 0.09)
        top = 0.5 + bh
        cols = slice(x0, min(width, x0 + bw))
        rows = (Y[:, 0] >= 0.5) & (Y[:, 0] < top)
        tone = rng.uniform(0.15, 0.45)
        block = np.full((rows.sum(), cols.stop - cols.start, 3), tone, np.float32) * np.array([1.0, 0.97, 0.92])
        wy = (np.arange(block.shape[0]) // max(2, h // 400)) % 3 == 1
        wx = (np.arange(block.shape[1]) // max(2, width // 1200)) % 4 == 1
        lit = rng.random((block.shape[0], block.shape[1])) > 0.4
        block[np.outer(wy, wx) & lit] = (0.95, 0.85, 0.55)
        img[rows, cols] = block
        x0 += bw + int(rng.integers(0, width // 200 + 1))
    # the sun
    d2 = (X - 0.3) ** 2 * 4 + (Y - 0.78) ** 2
    img += (np.exp(-d2 / 2e-5) * 400.0)[..., None]
    rgba = np.concatenate([img, np.ones((h, width, 1), np.float32)], -1)
    im = bpy.data.images.new("fr0344 photo", width, h, alpha=True, float_buffer=True)
    im.pixels.foreach_set(rgba.ravel())
    sc = bpy.context.scene
    st = sc.render.image_settings
    st.file_format, st.color_depth, st.exr_codec = "OPEN_EXR", "16", "ZIP"
    im.save_render(path, scene=sc)
    bpy.data.images.remove(im)


# ---- the scene ----------------------------------------------------------------------------------------------------

def crane(background: str, photo: str = ""):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    s.background = background
    if photo:
        s.hdri_path = photo
    world.apply(sc, s)
    sc.frame_set(1)
    w = s.web3d
    w.env_mode = "PROJECT"
    w.env_sky, w.env_sky_source = True, "PROJECT"
    return sc


def pictured_group(sc, pack_root: str):
    """The group with the biggest part gets the pack's concrete (2k pictures, one per 0.2 m, object space – the
    contract's "seamless at 0.2 m"); a camera 0.6 m in front of that part's largest face becomes the scene camera."""
    from mathutils import Vector
    parts = [o for o in sc.objects if o.type == "MESH" and o.get("fr_group")]
    big = max(parts, key=lambda o: o.dimensions.x * o.dimensions.y * o.dimensions.z)
    group = big["fr_group"]
    mat = bpy.data.materials.new("FRP test concrete")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 5.0, 5.0)           # one picture per 0.2 m
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    for key, cs in (("color", "sRGB"), ("rough", "Non-Color"), ("normal", "Non-Color")):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(pack_root, "textures", "2k",
                                                       f"concrete_{key}." + ("jpg" if key == "color" else "png")))
        node.image.colorspace_settings.name = cs
        node.projection = "BOX"
        node.projection_blend = 0.2
        nt.links.new(mp.outputs["Vector"], node.inputs["Vector"])
        if key == "color":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        elif key == "rough":
            nt.links.new(node.outputs["Color"], bsdf.inputs["Roughness"])
        else:
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nt.links.new(node.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    n = 0
    for o in parts:
        if o.get("fr_group") == group:
            if not o.material_slots:
                o.data.materials.append(None)
            o.material_slots[0].link = "OBJECT"
            o.material_slots[0].material = mat
            n += 1
    corners = [big.matrix_world @ Vector(c) for c in big.bound_box]
    lo = Vector([min(c[i] for c in corners) for i in range(3)])
    hi = Vector([max(c[i] for c in corners) for i in range(3)])
    centre = (lo + hi) / 2
    size = hi - lo
    axis = min(range(3), key=lambda i: size[i])              # look at the largest face: along its thinnest side
    eye = centre.copy()
    eye[axis] = lo[axis] - 0.6
    if axis == 2:
        eye[2] = hi[2] + 0.6
    cam = bpy.data.objects.new("Close", bpy.data.cameras.new("Close"))
    cam.data.lens = 35
    cam.location = eye + Vector((0.05, 0.05, 0.05))
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam
    return group, n, big.name


# ---- reading what a page holds ---------------------------------------------------------------------------------

def _dims(raw: bytes) -> tuple:
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", raw[16:24])
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        kind = raw[12:16]
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", raw[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            b = int.from_bytes(raw[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(raw[24:27], "little") + 1, int.from_bytes(raw[27:30], "little") + 1
    if raw[:2] == b"\xff\xd8":
        i = 2
        while i < len(raw) - 9:
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            ln = int.from_bytes(raw[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                return w, h
            i += 2 + ln
    if raw[:2] == b"#?":
        m = re.search(rb"-Y (\d+) \+X (\d+)", raw[:400])
        if m:
            return int(m.group(2)), int(m.group(1))
    return (0, 0)


def page_parts(html_path: str) -> dict:
    page = open(html_path, encoding="utf-8").read()
    pics = {}
    for m in re.finditer(r'id="fr-pic-([^"]+)" data-type="([^"]+)" data-bytes="(\d+)">([^<]*)</script>', page):
        import base64
        raw = base64.b64decode(m.group(4))
        pics[m.group(1)] = {"type": m.group(2), "bytes": int(m.group(3)), "size": list(_dims(raw))}
    glb = env.page_glb(page)
    jlen = struct.unpack("<I", glb[12:16])[0]
    gj = json.loads(glb[20:20 + jlen])
    binc = glb[20 + jlen + 8:]
    images = []
    for im in gj.get("images", []):
        bv = gj["bufferViews"][im["bufferView"]]
        raw = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        images.append({"type": im.get("mimeType"), "bytes": bv["byteLength"], "size": list(_dims(raw))})
    return {"html_bytes": os.path.getsize(html_path), "glb_bytes": len(glb), "pictures": pics, "glb_images": images,
            "_glb": glb}


def shoot(html_path: str, png: str) -> dict:
    r = subprocess.run(["node", SHOT, html_path, png, str(W), str(H), "--query=quality=BEST&auto=0&t=1&soft=0",
                        "--hide-ui", "--wait=2500"], capture_output=True, text=True, timeout=600)
    line = (r.stdout.strip().splitlines() or ["{}"])[-1]
    try:
        return json.loads(line)
    except ValueError:
        return {"ok": False, "raw": r.stdout[-400:] + r.stderr[-400:]}


def _load(png: str) -> np.ndarray:
    im = bpy.data.images.load(png)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, :3] * 255.0
    bpy.data.images.remove(im)
    return a


def look_cost(a_png: str, b_png: str, box=None) -> dict:
    a, b = _load(a_png), _load(b_png)
    if box:
        x0, y0, x1, y1 = box
        a, b = a[y0:y1, x0:x1], b[y0:y1, x0:x1]
    d = np.abs(a - b)
    mse = float((d ** 2).mean())
    return {"mean_abs": round(float(d.mean()), 2), "p99_abs": round(float(np.percentile(d, 99)), 1),
            "psnr_db": round(10 * math.log10(255 ** 2 / mse), 1) if mse > 0 else None}


def crops(pngs: list, labels: list, box, out_jpg: str, scale: int = 2) -> None:
    x0, y0, x1, y1 = box
    tiles = []
    for p, lab in zip(pngs, labels):
        t = p + ".crop.png"
        subprocess.run(["convert", p, "-crop", f"{x1 - x0}x{y1 - y0}+{x0}+{y0}", "+repage", "-filter", "point",
                        "-resize", f"{scale * 100}%", "-gravity", "south", "-background", "#222428", "-fill", "white",
                        "-font", "DejaVu-Sans", "-pointsize", "14", "-splice", "0x24", "-annotate", "+0+4", lab, t],
                       check=True)
        tiles.append(t)
    subprocess.run(["montage", *tiles, "-tile", f"{len(tiles)}x1", "-geometry", "+3+3", "-background", "#222428",
                    "-quality", "86", out_jpg], check=True)


def main():
    work, pack_root = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(work, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    res = {"machine": "4-core web machine, Blender 5.2.3 as a Python module, headless Chromium (software GL)"}

    photo = os.path.join(work, "made_up_photo_4k.exr")
    if not os.path.exists(photo):
        make_photo(photo, 4096)
    res["photo_exr_bytes"] = os.path.getsize(photo)

    # 1 · the background
    bg = {}
    for q in ("BEST", "BALANCED", "PHONE"):
        sc = crane("HDRI", photo)
        sc.fresing.web3d.env_quality = q
        t0 = time.perf_counter()
        out = web3d.export(sc, os.path.join(work, f"bg_{q}.glb"), size=512, surroundings=web3d_env.choice(sc))
        parts = page_parts(out["html"])
        parts.pop("_glb")
        bg[q] = {**parts, "export_s": round(time.perf_counter() - t0, 1), "html": out["html"]}
        bg[q]["shot"] = shoot(out["html"], os.path.join(work, f"bg_{q}.png"))
    bg["BEST"]["shot_again"] = shoot(bg["BEST"]["html"], os.path.join(work, "bg_BEST_again.png"))
    top = (0, 0, W, H // 3)                                     # the sky and the horizon's buildings
    ref = os.path.join(work, "bg_BEST.png")
    res["background"] = bg
    res["background_cost"] = {
        "noise_floor": {"all": look_cost(ref, os.path.join(work, "bg_BEST_again.png")),
                        "top": look_cost(ref, os.path.join(work, "bg_BEST_again.png"), top)},
        **{q: {"all": look_cost(ref, os.path.join(work, f"bg_{q}.png")),
               "top": look_cost(ref, os.path.join(work, f"bg_{q}.png"), top)} for q in ("BALANCED", "PHONE")}}

    # 2 · pictures baked at the page's size
    tex = {}
    for size in (2048, 1024, 512):
        sc = crane("COLOR")
        group, n, big = pictured_group(sc, pack_root)
        t0 = time.perf_counter()
        out = web3d.export(sc, os.path.join(work, f"tex_{size}.glb"), size=size, surroundings=web3d_env.choice(sc))
        parts = page_parts(out["html"])
        glb = parts.pop("_glb")
        originals = {}
        for f in ("concrete_color.jpg", "concrete_rough.png", "concrete_normal.png"):
            head = open(os.path.join(pack_root, "textures", "2k", f), "rb").read()[64:4160]
            originals[f] = head in glb
        tex[size] = {**parts, "group": group, "parts": n, "export_s": round(time.perf_counter() - t0, 1),
                     "original_pictures_inside": originals, "html": out["html"]}
        tex[size]["shot"] = shoot(out["html"], os.path.join(work, f"tex_{size}.png"))
    centre = (W // 2 - 160, H // 2 - 90, W // 2 + 160, H // 2 + 90)
    tref = os.path.join(work, "tex_2048.png")
    res["pictures"] = {str(k): v for k, v in tex.items()}
    res["pictures_cost"] = {str(s): {"all": look_cost(tref, os.path.join(work, f"tex_{s}.png")),
                                     "centre": look_cost(tref, os.path.join(work, f"tex_{s}.png"), centre)}
                            for s in (1024, 512)}

    crops([os.path.join(work, f"bg_{q}.png") for q in ("BEST", "BALANCED", "PHONE")],
          ["Background 4096 px (Best)", "2048 px (Balanced)", "1024 px (Phone)"],
          (W // 2 - 150, 20, W // 2 + 150, 170), os.path.join(work, "web3d_background.jpg"))
    crops([os.path.join(work, f"tex_{s}.png") for s in (2048, 1024, 512)],
          ["Pictures 2048 px / 0.2 m", "1024 px (default)", "512 px"],
          centre, os.path.join(work, "web3d_pictures.jpg"), scale=1)
    with open(os.path.join(work, "web3d_measure.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("FR0344 WEB3D", json.dumps({k: v for k, v in res.items() if k.endswith("cost")}))


main()
