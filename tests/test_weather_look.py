"""Wet and snowy looks through the "FR weather" node group (task 0109)."""

import os
import subprocess
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import fade, materials, section, surroundings, weather_look, world  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _empty():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    return bpy.context.scene


def _mat(name="FR Test paint", mid="paint_gloss", colour="RAL 5010"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    materials.build_nodes(mat, mid, colour)
    return mat


def _snapshot(mat):
    nt = mat.node_tree
    nodes = sorted((n.name, n.bl_idname, tuple(round(c, 3) for c in n.location)) for n in nt.nodes)
    links = sorted((lk.from_node.name, lk.from_socket.identifier, lk.to_node.name, lk.to_socket.identifier)
                   for lk in nt.links)
    return nodes, links


def _chain(mat):
    """Node kinds from the output's Surface back to the first plain shader."""
    out = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    sock, kinds = out.inputs["Surface"], []
    while sock.is_linked:
        node = sock.links[0].from_node
        kinds.append(node.node_tree.name if node.bl_idname == "ShaderNodeGroup" else node.bl_idname)
        if node.bl_idname != "ShaderNodeGroup":
            break
        sock = node.inputs[0]
    return kinds


def test_wrap_is_innermost_with_fade_and_section_in_any_order():
    sc = _empty()
    sng = section.node_group(sc)
    a = _mat("FR A")
    weather_look.wrap(a)
    section.wrap(a, sng)
    fade.wrap(a)
    b = _mat("FR B")
    fade.wrap(b)
    section.wrap(b, sng)
    weather_look.wrap(b)
    want = [fade.GROUP, section.GROUP, weather_look.GROUP, "ShaderNodeBsdfPrincipled"]
    assert _chain(a) == want and _chain(b) == want
    assert not weather_look.wrap(b)                       # twice: nothing changes
    assert sum(1 for n in b.node_tree.nodes if n.bl_idname == "ShaderNodeGroup"
               and n.node_tree.name == weather_look.GROUP) == 1


def test_unwrap_restores_the_tree_exactly():
    _empty()
    for mid in ("paint_gloss", "glass_clear", "steel_machined"):
        mat = _mat("FR " + mid, mid)
        fade.wrap(mat)
        before = _snapshot(mat)
        assert weather_look.wrap(mat) and weather_look.is_wrapped(mat) and mat.get(weather_look.TAG)
        assert _snapshot(mat) != before
        assert weather_look.unwrap(mat)
        assert _snapshot(mat) == before and weather_look.TAG not in mat


def test_a_decals_clear_parts_get_no_film_or_snow():
    _empty()
    mat = bpy.data.materials.new("FR decal")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    alpha = nt.nodes.new("ShaderNodeValue")
    alpha.name = "Alpha"
    nt.links.new(alpha.outputs[0], bsdf.inputs["Alpha"])
    before = _snapshot(mat)
    weather_look.wrap(mat)
    node = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeGroup")
    assert node.inputs["Alpha"].links[0].from_node == alpha          # the decal's own alpha
    weather_look.unwrap(mat)
    assert _snapshot(mat) == before


def test_rebuilt_material_keeps_the_wrap_and_porous_follows_the_look():
    _empty()
    mat = _mat()
    fade.wrap(mat)
    weather_look.wrap(mat)
    materials.build_nodes(mat, "steel_machined")          # a paint scheme / look change rebuilds the nodes
    assert _chain(mat) == [fade.GROUP, weather_look.GROUP, "ShaderNodeBsdfPrincipled"]
    node = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeGroup"
                and n.node_tree.name == weather_look.GROUP)
    assert node.inputs["Porous"].default_value == pytest.approx(0.12)     # metal hardly darkens
    con = bpy.data.materials.new("FR_env concrete")
    con["fr_env"] = "concrete"
    assert weather_look.porous(con) == pytest.approx(0.55)


def test_apply_wraps_the_model_and_the_quay_but_not_the_water_and_takes_it_away():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.background = "QUAY"
    world.apply(sc, sc.fresing)
    before = {m.name: _snapshot(m) for m in bpy.data.materials if m.node_tree is not None}
    n = weather_look.apply(sc, True)
    assert n > 5
    wrapped = {m.name for m in bpy.data.materials if weather_look.is_wrapped(m)}
    parts = {s.material.name for o in sc.objects if o.get("fr_kind") == "part" for s in o.material_slots}
    assert parts <= wrapped
    env = {m.get("fr_env") for m in bpy.data.materials if m.name in wrapped and m.get("fr_env")}
    assert "concrete" in env and "water" not in env
    assert not any(weather_look.is_wrapped(m) for m in bpy.data.materials if m.get("fr_env") == "water")
    assert weather_look.apply(sc, True) == 0                 # cheap: nothing to do
    ng = bpy.data.node_groups[weather_look.GROUP]
    kinds = {n.bl_idname for n in ng.nodes}
    assert kinds == {"NodeGroupInput", "NodeGroupOutput"}   # no wet, no snow anywhere: passes straight through
    # a Weather & time step keys the snow layer: the snow part is built (and only that: no AO cost without snow)
    sc["fr_wx_cover"] = 0.0
    sc.keyframe_insert('["fr_wx_cover"]', frame=1)
    sc["fr_wx_cover"] = 0.6
    sc.keyframe_insert('["fr_wx_cover"]', frame=40)
    weather_look.apply(sc, True)
    kinds = {n.bl_idname for n in ng.nodes}
    assert "ShaderNodeAmbientOcclusion" in kinds and "ShaderNodeTexVoronoi" not in kinds
    sc["fr_wx_wet"] = 0.3
    weather_look.apply(sc, True)
    kinds = {n.bl_idname for n in ng.nodes}
    assert "ShaderNodeAmbientOcclusion" in kinds and "ShaderNodeTexVoronoi" in kinds
    assert all(weather_look.is_wrapped(m) for m in bpy.data.materials if m.name in wrapped)
    sc.animation_data_clear()
    for k in ("fr_wx_wet", "fr_wx_cover"):
        del sc[k]
    weather_look.apply(sc, False)
    assert not any(weather_look.is_wrapped(m) for m in bpy.data.materials)
    assert bpy.data.node_groups.get(weather_look.GROUP) is None
    assert {m.name: _snapshot(m) for m in bpy.data.materials if m.node_tree is not None} == before


# ---------------------------------------------------------------------------
# renders
# ---------------------------------------------------------------------------

def _plate(name, x, y, z, half, mat, flip=False):
    h = half
    vs = [(x - h, y - h, z), (x + h, y - h, z), (x + h, y + h, z), (x - h, y + h, z)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], [(3, 2, 1, 0) if flip else (0, 1, 2, 3)])
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _stage(engine="CYCLES"):
    """Two dark plates on the ground; a roof 1.2 m over the right one. A camera low at the side looks under it."""
    sc = _empty()
    w = bpy.data.worlds.new("W")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.85, 1.0, 1.0)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    sc.world = w
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (np.radians(30), np.radians(-20), 0.0)
    sc.collection.objects.link(sun)
    paint = _mat("FR plate", "paint_matte", "RAL 3000")
    grey = _mat("FR roof", "paint_gloss", "RAL 7035")
    _plate("open", -1.5, 0.0, 0.0, 1.0, paint)
    _plate("covered", 1.5, 0.0, 0.0, 1.0, paint)
    _plate("roof", 1.5, 0.0, 1.2, 1.8, grey, flip=True)
    _plate("roof top", 1.5, 0.0, 1.21, 1.8, grey)
    cam_data = bpy.data.cameras.new("C")
    cam = bpy.data.objects.new("C", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (0.0, -5.0, 2.5)
    cam.rotation_euler = (np.radians(62), 0.0, 0.0)
    cam_data.lens = 24
    sc.camera = cam
    r = sc.render
    r.engine = engine
    r.resolution_x, r.resolution_y, r.resolution_percentage = 96, 48, 100
    if engine == "CYCLES":
        sc.cycles.samples, sc.cycles.device, sc.cycles.use_denoising, sc.cycles.seed = 32, "CPU", False, 1
    else:
        sc.eevee.taa_render_samples = 8
    bpy.context.view_layer.update()
    return sc


def _render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return px


def _spot(sc, xyz, px):
    """Mean colour of a small window round where ``xyz`` shows in the picture."""
    c = world_to_camera_view(sc, sc.camera, Vector(xyz))
    h, w = px.shape[:2]
    i, j = int(c.x * w), int(c.y * h)
    return px[max(j - 2, 0):j + 3, max(i - 3, 0):i + 4].mean(axis=(0, 1))


def _set(sc, wet=0.0, cover=0.0):
    sc["fr_wx_wet"] = float(wet)
    sc["fr_wx_cover"] = float(cover)


def _looks(sc, out):
    """Renders: unwrapped, wrapped with nothing, wet, snow. Returns {name: (open plate, covered plate, picture)}."""
    res = {}
    plain = _render(sc, os.path.join(out, "plain.png"))
    weather_look.node_group(True, True)              # both parts built, both at 0: still exactly as before
    for m in bpy.data.materials:
        if m.name.startswith("FR "):
            weather_look.wrap(m)
    for name, wet, cover in (("zero", 0, 0), ("wet", 1, 0), ("snow", 0, 0.8)):
        _set(sc, wet, cover)
        res[name] = _render(sc, os.path.join(out, name + ".png"))
    res["plain"] = plain
    return {k: (_spot(sc, (-1.5, -0.3, 0.0), v), _spot(sc, (1.5, -0.3, 0.0), v), v) for k, v in res.items()}


def _check(res, exact: bool):
    plain, zero = res["plain"][2], res["zero"][2]
    if exact:
        assert np.abs(plain - zero).max() == 0.0             # wet = cover = 0: exactly as before
    else:
        assert np.abs(plain - zero).mean() < 0.01
    assert res["wet"][0].mean() < 0.95 * res["plain"][0].mean()            # wet: darker
    o_snow, c_snow = res["snow"][0].mean(), res["snow"][1].mean()
    o_dry, c_dry = res["plain"][0].mean(), res["plain"][1].mean()
    assert o_snow > o_dry + 0.25, (o_snow, o_dry)                         # in the open: white
    return o_snow - o_dry, c_snow - c_dry


def test_cycles_zero_is_unchanged_wet_is_darker_snow_only_under_the_open_sky(tmp_path):
    sc = _stage("CYCLES")
    res = _looks(sc, str(tmp_path))
    gain_open, gain_covered = _check(res, exact=True)
    assert gain_covered < 0.15 * gain_open, (gain_open, gain_covered)    # under the roof: (almost) clear


EEVEE_CHILD = """
import sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {tests!r})
import test_weather_look as T
import bpy, addon_utils, fresing_render
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
sc = T._stage("BLENDER_EEVEE")
res = T._looks(sc, {out!r})
print("GAINS", *T._check(res, exact=False))
"""


def test_eevee_zero_is_unchanged_wet_is_darker_snow_lies(tmp_path):
    """EEVEE needs a GL context (none on GitHub's runners: skipped there, the PC check renders EEVEE). EEVEE's AO
    only sees what is on the screen, so the roof is not asked to keep the covered plate clear here."""
    code = EEVEE_CHILD.format(root=os.path.dirname(HERE), tests=HERE, out=str(tmp_path))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    line = next((x for x in p.stdout.splitlines() if x.startswith("GAINS ")), None)
    if line is None and p.returncode < 0 or p.returncode in (134, -6):
        pytest.skip("EEVEE cannot start here (no GL context)")
    assert line is not None, (p.returncode, p.stdout[-2000:], p.stderr[-2000:])
