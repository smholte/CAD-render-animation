"""Baked light on the web page (task 0107), no Blender: the page's settings (``light``, ``plain``), the shader patch
in ``fr_page.js`` against three.js r180's own chunks (node) and what the page draws (headless browser, software GL).

The models are made by hand with ``core.web3d.Gltf``, laid out in three's own coordinates (y up), the way the export
writes a baked copy: its own mesh entry on the part's POSITION / NORMAL / indices accessors plus ``TEXCOORD_1``
(16-bit normalised, glTF's V running down the picture) and a material copy with ``occlusionTexture {texCoord: 1}``,
or the attribute ``_FR_LIGHT`` (VEC3, u8 normalised). Encoding: texel = (F / scale) ^ (1 / curve).

The camera looks straight down (``orbit=0,1,3``): screen right is +x, screen top is -z.
"""

import json
import os
import re
import shutil
import struct
import subprocess
import zlib

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_env as env

NODE = shutil.which("node")
BUNDLE = os.path.join(web3d.WEB_DIR, env.THREE_FILE)
SOFT = {"light": "SOFT", "scale": 1.0, "curve": 2.0}
ALL = {"light": "ALL", "scale": 1.0, "curve": 2.0}
SKY = {"kind": "SKY", "sun": env.sun_vector(50.0, 0.0)}
TOP = "auto=0&frames=4&t=0&orbit=0,1,3"


# ---------------------------------------------------------------------------
# small models
# ---------------------------------------------------------------------------

def png(rgb: np.ndarray) -> bytes:
    """An 8-bit RGB PNG of (h, w, 3) uint8, rows top-down (no Pillow needed)."""
    h, w = rgb.shape[:2]
    raw = b"".join(b"\x00" + rgb[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Model:
    """Up-facing quads (three's y = 0) side by side along x; each one unbaked, with a lightmap or with vertex light."""

    def __init__(self):
        self.g = web3d.Gltf()
        self.look = self.g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0],
                                                              "metallicFactor": 0.0, "roughnessFactor": 0.9}})
        pos = np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]], float)
        nrm = np.tile(np.array([[0, 127, 0]], np.int8), (4, 1))
        # one shared mesh, as a part's mesh in the export (the copies reuse its accessors)
        self.part = self.g.mesh("part", pos, nrm, None, [(self.look, np.array([[0, 2, 1], [0, 3, 2]]))],
                                quantize=False)
        self.x = []

    def _prim(self):
        return dict(self.g.doc["meshes"][self.part]["primitives"][0])

    def _place(self, mesh, x):
        self.g.node({"mesh": mesh, "translation": [float(x), 0.0, 0.0]})
        self.x.append(float(x))

    def plain(self, x):
        self._place(self.part, x)

    def mapped(self, x, picture: np.ndarray):
        """A copy with its own lightmap: u runs along +x, v (glTF, down the picture) along +z."""
        p = self._prim()
        uv1 = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
        p["attributes"] = dict(p["attributes"], TEXCOORD_1=self.g.accessor(
            np.round(uv1 * 65535).astype(np.uint16), "VEC2", web3d.USHORT, normalized=True,
            target=web3d.ARRAY_BUFFER))
        tex = self.g.texture(png(picture), wrap=web3d.CLAMP if hasattr(web3d, "CLAMP") else 33071)
        mat = json.loads(json.dumps(self.g.doc["materials"][self.look]))
        mat["occlusionTexture"] = {"index": tex, "texCoord": 1}
        p["material"] = self.g.material(mat)
        self.g.doc["meshes"].append({"name": "copy", "primitives": [p]})
        self.g.dequantize.append(None)
        self._place(len(self.g.doc["meshes"]) - 1, x)

    def vertex(self, x, light: np.ndarray):
        """A copy with per-vertex light (4 corners: -x-z, +x-z, +x+z, -x+z), u8 0 … 255."""
        p = self._prim()
        p["attributes"] = dict(p["attributes"], _FR_LIGHT=self.g.accessor(
            np.asarray(light, np.uint8), "VEC3", web3d.UBYTE, normalized=True, target=web3d.ARRAY_BUFFER))
        self.g.doc["meshes"].append({"name": "copy", "primitives": [p]})
        self.g.dequantize.append(None)
        self._place(len(self.g.doc["meshes"]) - 1, x)

    def page(self, path, light=None, plain=False, sky=SKY, shadows=False, sea=None):
        lo, hi = min(self.x) - 1, max(self.x) + 1
        ch = dict(env.default_choice(), shadows=shadows, auto=False, sea=sea is not None)
        st = env.settings(ch, [lo, -1.0, 0.0], [hi, 1.0, 0.01], sky=dict(sky), light=light, plain=plain, sea=sea)
        html = env.page_html("Baked light test", self.g.glb(), st)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        return str(path)


def halves(dark: int, bright: int, n: int = 8) -> np.ndarray:
    pic = np.full((n, n, 3), bright, np.uint8)
    pic[:, : n // 2] = dark
    return pic


def texel(f: float, scale: float = 1.0, curve: float = 2.0) -> int:
    return int(round(255 * (f / scale) ** (1.0 / curve)))


# ---------------------------------------------------------------------------
# the browser
# ---------------------------------------------------------------------------

def _read(path, query=TOP, probe=()):
    browser = env.find_browser()
    if not browser:
        pytest.skip("no headless browser on this machine")
    q = query + ("&probe=" + ";".join(f"{x},{y}" for x, y in probe) if probe else "")
    try:
        out = env.read_page(path, browser, q, seconds=120)
    except RuntimeError as exc:                     # GitHub's Linux runner: Chromium may crash at start (task 0106)
        pytest.skip(f"the browser did not run: {exc}")
    if out["state"] in ("no-webgl", "loading") or out["state"].startswith("error: no-webgl"):
        pytest.skip(f"no WebGL in this browser ({out['state']})")
    assert out["state"].startswith("ready"), out["state"]
    return out


def lum(px) -> float:
    return 0.2126 * px[0] + 0.7152 * px[1] + 0.0722 * px[2]


def screen_x(m: Model, x: float, dist: float = 3.0, aspect: float = 800 / 600) -> float:
    """Screen place (0 … 1) of model x for the straight-down camera of ``TOP`` (fov 30°, distance in model radii)."""
    lo, hi = min(m.x) - 1, max(m.x) + 1
    radius = 0.5 * float(np.linalg.norm([hi - lo, 0.01, 2.0]))
    half_w = dist * radius * np.tan(np.radians(15.0)) * aspect
    return 0.5 + (x - (lo + hi) / 2) / (2 * half_w)


# ---------------------------------------------------------------------------
# settings (no browser)
# ---------------------------------------------------------------------------

def test_settings_without_light_or_plain_are_unchanged():
    ch = dict(env.default_choice(), haze=True, rain=True)
    a = env.settings(ch, [0, 0, 0], [3, 2, 1])
    b = env.settings(ch, [0, 0, 0], [3, 2, 1], light=None, plain=False)
    c = env.settings(ch, [0, 0, 0], [3, 2, 1], light={"light": "LIVE"})
    assert "light" not in a and "plain" not in a
    assert json.dumps(a) == json.dumps(b) == json.dumps(c)
    assert env.page_html("M", b"glb", a) == env.page_html("M", b"glb", b)
    assert env.items_text(a) == "sky, haze, rain, sun shadows"


def test_settings_light_and_plain():
    st = env.settings(dict(env.default_choice(), haze=True, rain=True, clouds="OVERCAST"), [0, 0, 0], [3, 2, 1],
                      sea={"waves": [[0.1, 1, 0, 0.1, 0]], "near": 40}, light={"light": "ALL", "scale": 1.7},
                      plain=True)
    assert st["light"] == {"light": "ALL", "scale": 1.7, "curve": 2.0, "sun": 0.0}
    assert st["plain"] is True
    assert st["sea"] is None and st["vessel"] is None and st["haze"] is None and st["rain"] is None
    assert st["sky"]["clouds"] == "NONE"
    assert env.items_text(st) == "sky, sun shadows, baked light (everything)"
    soft = env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1], light=dict(SOFT, scale=2, curve=2))
    assert soft["light"] == {"light": "SOFT", "scale": 2.0, "curve": 2.0, "sun": 0.0} and "plain" not in soft
    assert env.items_text(soft).endswith("baked light (soft)")
    for bad in ({"light": "HALF"}, {"light": "SOFT", "scale": 0}, {"light": "ALL", "curve": float("nan")}):
        with pytest.raises(ValueError):
            env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1], light=bad)
    json.dumps(st, allow_nan=False)


# ---------------------------------------------------------------------------
# the shader patch against three.js r180 (node)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_three_chunks_still_have_what_the_patch_replaces():
    """fr_page.js replaces the environment's matte light line in lights_fragment_maps, adds global code after
    lights_physical_pars_fragment, drops aomap_fragment and wraps RE_Direct_Physical: all must exist in the bundle."""
    page = open(os.path.join(web3d.WEB_DIR, env.PAGE_FILE), encoding="utf-8").read()
    code = ("global.window = global; global.self = global;"
            f"eval(require('fs').readFileSync({json.dumps(BUNDLE)}, 'utf8') + ';global.FRTHREE = FRTHREE;');"
            "const C = FRTHREE.ShaderChunk, F = FRTHREE.ShaderLib.physical.fragmentShader;"
            "console.log(JSON.stringify({maps: C.lights_fragment_maps, pars: C.lights_physical_pars_fragment,"
            " begin: C.lights_fragment_begin, end: C.lights_fragment_end, frag: F,"
            " vert: FRTHREE.ShaderLib.physical.vertexShader}));")
    out = json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=60,
                                    check=True).stdout)
    assert "iblIrradiance += getIBLIrradiance( geometryNormal );" in out["maps"]
    assert "iblIrradiance += getIBLIrradiance( geometryNormal );" in page
    for inc in ("#include <lights_physical_pars_fragment>", "#include <lights_fragment_maps>",
                "#include <aomap_fragment>"):
        assert inc in out["frag"] and inc in page
    assert "#include <begin_vertex>" in out["vert"]
    assert ("void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, "
            "const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, "
            "const in PhysicalMaterial material, inout ReflectedLight reflectedLight )") in out["pars"]
    assert re.search(r"#define RE_Direct\s+RE_Direct_Physical\n", out["pars"])
    # the env's matte light reaches the surface only through iblIrradiance -> RE_IndirectSpecular
    assert "vec3 radiance = vec3( 0.0 );" in out["begin"] and "vec3 iblIrradiance = vec3( 0.0 );" in out["begin"]
    assert "RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance" in out["end"]
    # GLTFLoader: TEXCOORD_1 -> uv1, other attribute names lower case (_FR_LIGHT -> _fr_light), texCoord -> channel
    bundle = open(BUNDLE, encoding="utf-8").read()
    assert 'TEXCOORD_1:"uv1"' in bundle and ".channel=n.texCoord" in bundle


# ---------------------------------------------------------------------------
# what the page draws (headless browser)
# ---------------------------------------------------------------------------

def test_lightmap_darkens_its_dark_half(tmp_path):
    m = Model()
    m.mapped(0.0, halves(texel(0.15), texel(1.0)))
    out = _read(m.page(tmp_path / "map.html", light=ALL), probe=[(0.38, 0.5), (0.62, 0.5)])
    assert out["light"]["light"] == "ALL" and out["light"]["meshes"] == 1 and out["light"]["materials"] == 1
    dark, bright = (lum(p) for p in out["probe"])
    assert dark < bright - 25, out["probe"]


def test_vertex_light_works_the_same(tmp_path):
    m = Model()
    lo, hi = texel(0.1), texel(1.0)
    m.vertex(0.0, [[lo] * 3, [hi] * 3, [hi] * 3, [lo] * 3])          # -x corners dark, +x corners bright
    out = _read(m.page(tmp_path / "vtx.html", light=ALL), probe=[(0.3, 0.5), (0.7, 0.5)])
    assert out["light"]["meshes"] == 1
    dark, bright = (lum(p) for p in out["probe"])
    assert dark < bright - 20, out["probe"]


def _sun_scene(path, light):
    """Four up-facing quads in the sun: unbaked, baked F = 1 (map), baked F = 1 (vertex), baked F = 0.25 (map)."""
    m = Model()
    m.plain(-3.3)
    m.mapped(-1.1, np.full((4, 4, 3), texel(1.0), np.uint8))
    m.vertex(1.1, [[texel(1.0)] * 3] * 4)
    m.mapped(3.3, np.full((4, 4, 3), texel(0.25), np.uint8))
    probe = [(screen_x(m, x, dist=3.0), 0.5) for x in m.x]
    return _read(m.page(path, light=light), query="auto=0&frames=4&t=0&orbit=0,1,3", probe=probe)


def test_all_has_no_double_sun_and_soft_keeps_the_live_sun(tmp_path):
    soft = _sun_scene(tmp_path / "soft.html", SOFT)
    dark = _sun_scene(tmp_path / "all0.html", dict(ALL, sun=0.0))
    sunny = _sun_scene(tmp_path / "all3.html", dict(ALL, sun=3.0))
    assert soft["light"]["meshes"] == 3 and soft["light"]["materials"] == 3      # 2 maps + the vertex look copy
    s = [lum(p) for p in soft["probe"]]
    a0 = [lum(p) for p in dark["probe"]]
    a3 = [lum(p) for p in sunny["probe"]]
    # SOFT, F = 1 in the open: baked looks like unbaked (the live sun kept); measured 13 Nov 2026 (headless shell,
    # SwiftShader): equal to the last digit
    assert abs(s[1] - s[0]) <= 2 and abs(s[2] - s[0]) <= 2, s
    for a in (a0, a3):
        assert abs(a[0] - s[0]) <= 2                                             # unbaked: the same page light
        assert abs(a[1] - a[2]) <= 2, a                                          # map and vertex alike
    # ALL: the live sun gives no matte light on baked parts (no double sun): with Cycles' sun share 0 an F = 1 part
    # gets the sky alone; with a share of 3 it gets 4 x the sky, the render's balance
    assert a0[1] < s[1] - 15, (s, a0)
    assert a3[1] > a0[1] + 15, (a0, a3)
    # F = 0.25: SOFT keeps the full live sun on top, ALL dims sky and sun alike
    assert a0[3] < s[3] - 15 and a3[3] < a3[1] - 15, (s, a0, a3)
    assert s[3] < s[0] - 5, s


def test_unbaked_parts_look_the_same_with_and_without_baked_light(tmp_path):
    def scene(path, light):
        m = Model()
        m.plain(-1.1)
        m.mapped(1.1, halves(texel(0.2), texel(0.6)))
        return _read(m.page(path, light=light), query="auto=0&frames=4&t=0&orbit=0,1,2",
                     probe=[(screen_x(m, -1.1, dist=2), 0.5), (screen_x(m, -1.5, dist=2), 0.4)])
    off = scene(tmp_path / "off.html", None)
    on = scene(tmp_path / "on.html", SOFT)
    assert off["light"] is None and on["light"]["meshes"] == 1
    for p, q in zip(off["probe"], on["probe"]):
        assert max(abs(a - b) for a, b in zip(p, q)) <= 1, (off["probe"], on["probe"])


def test_plain_form_has_the_light_background_and_no_sky(tmp_path):
    m = Model()
    m.mapped(0.0, halves(texel(0.3), texel(1.0)))
    out = _read(m.page(tmp_path / "plain.html", light=SOFT, plain=True, shadows=True),
                probe=[(0.03, 0.97), (0.97, 0.03), (0.62, 0.5)])
    info = out["light"]
    assert info["plain"] is True and info["meshes"] == 1
    assert "radial-gradient" in info["background"] and "241, 243, 245" in info["background"]
    corner, other, model = out["probe"]
    assert corner[3] == 0 and other[3] == 0, out["probe"]       # see-through: the page's light ground shows
    assert model[3] == 255 and lum(model) > 20
    # the same page with surroundings draws its sky there
    sky = _read(m.page(tmp_path / "sky.html", light=SOFT), probe=[(0.03, 0.97)])
    assert sky["probe"][0][3] == 255 and sky["light"]["plain"] is False


def test_baked_page_has_no_errors_with_shadows_and_photo_light(tmp_path):
    """Shadows on (the sun's shadow map on baked materials) and a studio/photo light without pictures."""
    m = Model()
    m.plain(-1.1)
    m.mapped(1.1, halves(texel(0.3), texel(1.0)))
    for light in (SOFT, ALL):
        out = _read(m.page(tmp_path / f"shadow_{light['light']}.html", light=light, shadows=True))
        assert out["state"].startswith("ready"), out
    photo = {"kind": "PHOTO", "sun": env.sun_vector(40.0, 30.0), "sun_share": 2.0, "background": [0.4, 0.4, 0.4]}
    out = _read(m.page(tmp_path / "photo.html", light=SOFT, sky=photo))
    assert out["light"]["sunMatte"] is False         # a photo's key light: shine only on baked parts
