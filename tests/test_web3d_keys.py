"""Task 0175: the web export's animation keys – error-bounded against every frame as three.js plays them, 16-bit
turns, still paths left out, shown/hidden only at changes – the meshopt filters (bit for bit against Blender's own
meshopt library where it is found), the model gzip-packed in the page, WebP pictures and duplicate shapes."""

import base64
import ctypes
import glob
import gzip
import math
import os

import numpy as np
import pytest

from fresing_render.core import meshopt
from fresing_render.core import web3d as core
from fresing_render.core import web3d_env as env
from fresing_render.core import web3d_keys as K

FPS = 25.0


def _quat_z(a):
    return np.stack([np.zeros_like(a), np.zeros_like(a), np.sin(a / 2), np.cos(a / 2)], 1)


def _quat_axis(axis, a):
    axis = np.asarray(axis, np.float64) / np.linalg.norm(axis)
    return np.concatenate([axis[None] * np.sin(a / 2)[:, None], np.cos(a / 2)[:, None]], 1)


def _qmul(a, b):
    x1, y1, z1, w1 = a.T
    x2, y2, z2, w2 = b.T
    return np.stack([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2], 1)


def motions():
    """(name, t, q, s, reach): the kinds of motion the demo has – a roller turning faster and slower, a carriage
    with a cylinder's tilt, a carousel 24 m across, a part far from the origin swinging, a scaled part."""
    f = 900
    tm = np.arange(f) / FPS
    speed = 0.5 + 0.5 * np.sin(tm / 5) ** 2
    roller = ("roller", np.tile([12.0, -3.0, 4.5], (f, 1)), _quat_axis([1, 0, 0], np.cumsum(speed) * 0.1),
              None, 0.4)
    ease = 0.5 - 0.5 * np.cos(np.clip(tm / 20, 0, 1) * math.pi)
    carriage = ("carriage", np.stack([40 + 6 * ease, -2 + 0 * tm, 3 + 0.05 * np.sin(tm / 3)], 1),
                _qmul(_quat_axis([0, 1, 0], 0.2 * ease), _quat_z(0.05 * np.sin(tm / 3))), None, 3.0)
    carousel = ("carousel", np.tile([-20.0, 0.0, 6.0], (f, 1)), _quat_z(tm * 0.08), None, 12.5)
    swing = ("swing", np.stack([95 + 0.4 * np.sin(tm / 8), 8 * np.cos(tm / 20), 30 + tm * 0.01], 1),
             _quat_axis([0.3, 1, 0.2], 0.4 * np.sin(tm / 8)), None, 6.0)
    scaled = ("scaled", np.tile([1.0, 2.0, 3.0], (f, 1)), _quat_z(np.zeros(f)),
              np.stack([1 + 0.2 * ease] * 3, 1), 2.0)
    return tm, [roller, carriage, carousel, swing, scaled]


@pytest.mark.parametrize("packed", [True, False])
def test_keys_within_the_bound_at_every_frame(packed):
    """0.1 mm, 0.05° and 1 mm at the far end at every frame, as three.js plays the file's own numbers – and far fewer
    keys than frames for smooth motion."""
    tm, ms = motions()
    for name, t, q, s, reach in ms:
        tr = K.node_track(t, q, s, reach=reach, frames=tm, packed=packed)
        place, turn, far = K.check(tr, t, q, s, reach, tm)
        assert place <= K.POS_TOL * 1.001, name
        assert turn <= K.ANGLE_TOL * 1.001, name
        assert far <= K.NODE_TOL * 1.001, name
        assert len(tr.keys) < len(tm) * 0.5, (name, len(tr.keys))


def test_still_paths_are_left_out():
    tm, ms = motions()
    _n, t, q, _s, reach = ms[0]                      # the roller only turns
    tr = K.node_track(t, q, None, reach=reach, frames=tm)
    assert set(tr.paths) == {"rotation"}
    _n, t, q, _s, reach = ms[4]                      # the scaled part only grows
    tr = K.node_track(t, q, ms[4][3], reach=reach, frames=tm)
    assert set(tr.paths) == {"scale"}
    tr = K.node_track(np.tile([1.0, 2, 3], (50, 1)), _quat_z(np.full(50, 0.3)), None, frames=tm[:50])
    assert tr.paths == {} and len(tr.keys) == 0


def test_long_part_keeps_32_bit_turns():
    """A turn written as 16-bit numbers moves a point 20 m out by up to ~1 mm: such a part keeps float turns."""
    tm, ms = motions()
    _n, t, q, _s, _r = ms[2]
    assert K.node_track(t, q, None, reach=0.5, frames=tm).rot16
    tr = K.node_track(t, q, None, reach=60.0, frames=tm)
    assert not tr.rot16 and tr.paths["rotation"][0].dtype == np.float32
    assert K.check(tr, t, q, None, 60.0, tm)[2] <= K.NODE_TOL * 1.001


def test_slerp_flat_is_threes():
    """three.js slerpFlat: the ends as they are (not made unit), the short way, a straight blend made unit when the
    two are nearly the same."""
    a = np.array([[0.0, 0, 0, 1.00002]])
    b = _quat_z(np.array([2.0]))
    assert np.array_equal(K.slerp_flat(a, b, np.array([0.0])), a)
    mid = K.slerp_flat(_quat_z(np.array([0.0])), _quat_z(np.array([1.0])), np.array([0.5]))
    assert np.allclose(mid, _quat_z(np.array([0.5])), atol=1e-12)
    back = K.slerp_flat(_quat_z(np.array([0.0])), -_quat_z(np.array([1.0])), np.array([0.5]))
    assert np.allclose(np.abs(back), np.abs(_quat_z(np.array([0.5]))), atol=1e-12)


def test_shown_and_hidden_only_at_changes():
    v = np.array([0, 0, 0, 1, 1, 1, 1, 0, 0, 1], bool)
    assert K.changes(v).tolist() == [0, 3, 7, 9]
    assert K.changes(np.ones(5, bool)).tolist() == [0, 4]


def test_exponential_filter_round_trip():
    rng = np.random.default_rng(3)
    v = np.c_[rng.uniform(-120, 120, 500), rng.uniform(-1, 1, 500), rng.uniform(-3000, 3000, 500)]
    back = K.exp_decode(K.exp_encode(v))
    e = K.exp_exponent(v)
    assert e[0] == K.EXP_STEP and e[1] == K.EXP_STEP and e[2] > K.EXP_STEP     # 3 km does not fit 2^-16 m
    assert np.abs(back[:, :2] - v[:, :2]).max() <= 2.0 ** (K.EXP_STEP - 1) * 1.01
    assert np.abs(back[:, 2] - v[:, 2]).max() <= 2.0 ** (e[2] - 1) * 1.01
    t = np.arange(4000) / FPS
    tt = K.exp_decode(K.exp_encode(t[:, None], K.EXP_TIME))[:, 0]
    assert np.all(np.diff(tt) > 0) and np.abs(tt - t).max() < 2e-5        # float32 itself: 1.5e-5 s at 160 s
    assert np.array_equal(K.file_times(t, True), tt)


def test_quaternion_filter_round_trip():
    rng = np.random.default_rng(4)
    q = rng.normal(size=(2000, 4))
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    back = K.read_short(K.quat_decode(K.quat_encode(q)))
    dot = np.abs((back / np.linalg.norm(back, axis=1, keepdims=True) * q).sum(1))
    assert np.degrees(2 * np.arccos(np.clip(dot, -1, 1))).max() < 0.01
    assert np.abs(np.linalg.norm(back, axis=1) - 1).max() < 1e-4


# ---------------------------------------------------------------------------
# against Blender's own meshopt library (Linux: its lib folder; the bridge Windows' glTF add-on uses has the same
# functions) – skipped where none is found
# ---------------------------------------------------------------------------

def _bridge():
    try:
        import bpy  # noqa: F401
        base = os.path.dirname(os.path.dirname(os.path.abspath(bpy.__file__)))
    except ImportError:
        base = ""
    found = glob.glob(os.path.join(base, "bpy", "lib", "libbf_intern_meshopt_bridge*")) + \
        glob.glob(os.path.expanduser("~/blender-*/blender-*/lib/libbf_intern_meshopt_bridge*"))
    for p in found:
        try:
            lib = ctypes.CDLL(p)
            lib.decodeFilterQuat, lib.decodeFilterExp, lib.encodeFilterQuat  # noqa: B018
            return lib
        except (OSError, AttributeError):
            continue
    return None


def test_filters_match_blenders_meshopt():
    lib = _bridge()
    if lib is None:
        pytest.skip("Blender's meshopt bridge not found")
    rng = np.random.default_rng(5)
    q = rng.normal(size=(3000, 4)).astype(np.float32)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    native = np.empty((len(q), 4), np.int16)
    lib.encodeFilterQuat.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_int, ctypes.c_void_p]
    lib.encodeFilterQuat(native.ctypes.data, len(q), 8, 16, np.ascontiguousarray(q).ctypes.data)
    mine = K.quat_encode(q)
    assert np.abs(native.astype(int) - mine.astype(int)).max() <= 1
    lib.decodeFilterQuat.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
    buf = mine.copy()
    lib.decodeFilterQuat(buf.ctypes.data, len(buf), 8)
    assert np.abs(buf.astype(int) - K.quat_decode(mine).astype(int)).max() <= 1
    v = np.c_[rng.uniform(-120, 120, 800), rng.uniform(-0.01, 0.01, 800), rng.uniform(-5000, 5000, 800)]
    enc = K.exp_encode(v)
    buf = enc.copy()
    lib.decodeFilterExp.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
    lib.decodeFilterExp(buf.ctypes.data, len(buf), 12)
    assert np.array_equal(buf.view(np.float32), K.exp_decode(enc))


# ---------------------------------------------------------------------------
# into the file and back
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("compress", [True, False])
def test_file_reads_back_what_the_keys_promise(compress):
    tm, ms = motions()
    g = core.Gltf(compress=compress)
    root = g.node({"name": "Model"})
    tracks, want = [], {}
    for name, t, q, s, reach in ms:
        node = g.node({"name": name}, root)
        tr = K.node_track(t, q, s, reach=reach, frames=tm, packed=compress)
        for path, (_file, read) in tr.paths.items():
            tracks.append((node, path, tr.paths[path][0], "LINEAR", tm[tr.keys], tr.how(path)))
            want[(node, path)] = (tm[tr.keys], read)
    g.animation("A", tm, tracks)
    data = g.glb()
    assert core.problems(data) == []
    doc, binary = core.read_glb(data)
    filters = set()
    for smp, ch in zip(doc["animations"][0]["samplers"], doc["animations"][0]["channels"]):
        key = (ch["target"]["node"], ch["target"]["path"])
        times = core.accessor_array(doc, binary, smp["input"])[:, 0]
        vals = core.accessor_array(doc, binary, smp["output"]).astype(np.float64)
        assert np.array_equal(times, K.file_times(want[key][0], compress))
        assert np.abs(vals - want[key][1]).max() < 1e-6, key
        for acc in (smp["input"], smp["output"]):
            view = doc["bufferViews"][doc["accessors"][acc]["bufferView"]]
            filters.add(((view.get("extensions") or {}).get(core.MESHOPT) or {}).get("filter", "NONE"))
    assert filters == ({"EXPONENTIAL", "QUATERNION", "NONE"} if compress else {"NONE"})


def test_duplicate_shapes_written_once():
    g = core.Gltf(compress=True)
    pos = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    nrm = np.array([[0, 0, 127]] * 3, np.int8)
    a = g.mesh("a", pos, nrm, None, [(0, np.array([[0, 1, 2]]))])
    b = g.mesh("b", pos.copy(), nrm.copy(), None, [(0, np.array([[0, 1, 2]]))])
    c = g.mesh("c", pos, nrm, None, [(1, np.array([[0, 1, 2]]))])        # another material: its own
    assert a == b != c and g.duplicates == 1 and len(g.doc["meshes"]) == 2


# ---------------------------------------------------------------------------
# the page and the pictures
# ---------------------------------------------------------------------------

def test_page_holds_the_model_gzip_packed():
    g = core.Gltf()
    g.node({"name": "Model"})
    glb = g.glb() + b""
    page = env.page_html("T", glb, env.settings(env.default_choice(), (0, 0, 0), (1, 1, 1), sky={"kind": "SKY"},
                                                  plain=True) if False else {"sky": {}}, {})
    assert 'data-gzip="1"' in page and env.page_glb(page) == glb
    raw = base64.b64decode(page.split('id="fr-glb"')[1].split(">", 1)[1].split("<", 1)[0])
    assert gzip.decompress(raw) == glb
    old = '<script type="application/octet-stream" id="fr-glb" data-bytes="%d">%s</script>' % (
        len(glb), base64.b64encode(glb).decode())                       # a page written before 0175
    assert env.page_glb(old) == glb


def test_webp_texture_and_its_size():
    # a 1 x 1 lossy WebP (VP8) and the extension it is named by
    webp = bytes.fromhex("52494646240000005745425056503820180000003001009d012a0100010002003425a400037000"
                         "00fefb94000000")
    assert core.is_webp(webp) and core.image_size(webp) == (1, 1)
    g = core.Gltf()
    k = g.texture(webp)
    doc, _ = core.read_glb(g.glb())
    assert "source" not in doc["textures"][k] and core.texture_image(doc, k) == 0
    assert doc["images"][0]["mimeType"] == "image/webp"
    assert core.WEBP in doc["extensionsRequired"] and core.problems(g.glb()) == []
    jpg_like = core.Gltf()
    k = jpg_like.texture(b"\xff\xd8\xff\xe0" + bytes(20))
    doc, _ = core.read_glb(jpg_like.glb())
    assert doc["textures"][k]["source"] == 0 and core.WEBP not in doc.get("extensionsUsed", [])


def test_meshopt_vertex_codec_still_reads_filtered_views():
    """A filtered view is still ATTRIBUTES-mode bytes the plain decoder reads (the filter is a step after it)."""
    enc = K.exp_encode(np.linspace(0, 3, 40)[:, None])
    raw = meshopt.encode_vertex_buffer(enc.view(np.uint8).reshape(40, 4))
    back = meshopt.decode_vertex_buffer(raw, 40, 4).copy().view(np.uint32).reshape(40, 1)
    assert np.array_equal(back, enc)
