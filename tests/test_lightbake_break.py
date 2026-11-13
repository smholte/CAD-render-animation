"""Baked light (task 0107), written by the independent tester (did not write the code): cases that try to break
``blender/lightbake.py`` and the lit web 3D export. A test marked ``xfail(strict=True)`` pins a fault that is still
there; when the fault is fixed the test passes, strict xfail turns that into a failure, and the marker goes.

Note for CI: pytest's JUnit file lists an xfail as *skipped*, and each pytest group allows one skipped test
(``ci_pytest_summary.py --max-skipped 1``): fix the faults (or move the markers) before this file runs on GitHub."""

import math
import os

import numpy as np
import pytest

from fresing_render.core import lightmap as lm
from fresing_render.core import web3d as core

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, lightbake, materials, web3d  # noqa: E402
from fresing_render.core import materials_lib  # noqa: E402
from fresing_render.core.web3d import Cancelled  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
FAST = {"samples": 4, "quality": "DRAFT", "denoise": False}


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sky_world(sc, elevation=35.0):
    w = bpy.data.worlds.new("Test sky")
    nt = w.node_tree
    nt.nodes.clear()
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sun_elevation = math.radians(elevation)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.08
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    sc.world = w
    return w


def block_scene():
    """A 6 m floor and two copies of one 1 m box mesh, lit by a sky with its sun at 35°."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    _sky_world(sc)
    bpy.ops.mesh.primitive_plane_add(size=6.0)
    floor = bpy.context.object
    floor.name = "Floor"
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.5, 0.0, 0.5))
    box = bpy.context.object
    box.name = "Box A"
    box2 = box.copy()
    box2.name = "Box B"
    box2.location = (1.5, 0.0, 0.5)
    sc.collection.objects.link(box2)
    bpy.context.view_layer.update()
    return sc, floor, box, box2


def counts():
    d = bpy.data
    return (len(d.scenes), len(d.objects), len(d.meshes), len(d.materials), len(d.images), len(d.worlds),
            len(d.node_groups), len(d.cameras), len(d.lights))


def floor_light(item, x, y, ob):
    """The baked light (MAP) at the world point (x, y) on a flat floor object."""
    from mathutils import Vector
    from mathutils.geometry import barycentric_transform
    me = ob.data
    p = ob.matrix_world.inverted() @ Vector((x, y, ob.matrix_world.translation.z))
    for k, t in enumerate(me.loop_triangles):
        a, b, c = (me.vertices[i].co for i in t.vertices)
        bc = barycentric_transform(p, a, b, c, (1, 0, 0), (0, 1, 0), (0, 0, 1))
        if min(bc) >= -1e-6 and abs(sum(bc) - 1.0) < 1e-4:
            uvs = item.uv[k * 3:k * 3 + 3]
            u = bc[0] * uvs[0] + bc[1] * uvs[1] + bc[2] * uvs[2]
            h, w = item.pixels.shape[:2]
            return item.pixels[int(u[1] * h), int(u[0] * w)]
    raise AssertionError("point not on the floor")


def per_triangle(item):
    """(loop triangles, 3) light of every triangle (its centre texel, or the mean of its corners)."""
    if item.kind == "VERTEX":
        return item.corners.reshape(-1, 3, 3).mean(1)
    h, w = item.pixels.shape[:2]
    c = item.uv.reshape(-1, 3, 2).mean(1)
    return item.pixels[np.clip((c[:, 1] * h).astype(int), 0, h - 1), np.clip((c[:, 0] * w).astype(int), 0, w - 1)]


def top_faces(ob):
    m3 = ob.matrix_world.to_3x3()
    return np.array([(m3 @ t.normal).normalized().z > 0.9 for t in ob.data.loop_triangles])


# ---------------------------------------------------------------------------
# faults still there (xfail strict)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="mirrored copy (negative scale) is joined in world coordinates with its "
                                       "triangles' winding flipped: Cycles bakes it black (AUTO and VERTEX)")
@pytest.mark.parametrize("uv", ["AUTO", "VERTEX"])
def test_a_mirrored_copy_gets_the_same_light_as_the_plain_one(uv):
    sc, floor, box, box2 = block_scene()
    box2.scale = (-1.0, 1.0, 1.0)                 # a mirrored copy, standing in the open like box A
    bpy.context.view_layer.update()
    res = lightbake.bake([box, box2], "ALL", uv=uv, texels_per_m=40, samples=16, quality="DRAFT", denoise=False)
    top = top_faces(box)
    a = per_triangle(res.items["Box A"])[top].mean(0)
    b = per_triangle(res.items["Box B"])[top].mean(0)
    assert a[1] > 0.5 * res.reference[1]
    assert b[1] > 0.8 * a[1], (a, b)


@pytest.mark.xfail(strict=True, reason="the UV layers of all joined objects (+ fr_light) go on one bake mesh: more "
                                       "than Blender's 8 UV layers -> uv_layers.new returns None -> AttributeError")
def test_many_differently_named_uv_layers_do_not_stop_the_bake():
    sc, floor, box, box2 = block_scene()
    obs = []
    for i in range(9):                            # e.g. imported objects whose UV maps are named differently
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(i * 0.3 - 1.2, 2.5, 0.05))
        o = bpy.context.object
        o.data.uv_layers[0].name = f"Imported UV {i}"
        obs.append(o)
    before = counts()
    res = lightbake.bake(obs, "ALL", uv="VERTEX", **FAST)
    assert len(res.items) == 9
    assert counts() == before


@pytest.mark.xfail(strict=True, reason="a mesh with Blender's maximum of 8 UV layers: the bake copy needs a 9th "
                                       "(fr_light) for uv='UV1' and app-made maps -> AttributeError")
def test_a_mesh_with_eight_uv_layers_bakes_with_its_own_uv1():
    sc, floor, box, box2 = block_scene()
    me = box.data
    while len(me.uv_layers) < 8:
        me.uv_layers.new(name=f"uv{len(me.uv_layers)}")
    res = lightbake.bake([box], "ALL", uv="UV1", **FAST)
    assert res.items["Box A"].kind == "MAP"


@pytest.mark.xfail(strict=True, reason="a part with tens of thousands of separate faces (a grating): its charts do "
                                       "not fit one atlas even at the smallest size; plan() then calls pack() which "
                                       "raises TooBig and the whole bake / export fails")
def test_a_grating_with_many_charts_does_not_stop_the_bake():
    sc, floor, box, box2 = block_scene()
    n = 10000                                      # 10,000 bars of 10 x 100 x 30 mm on a 4 x 4 m field
    i = np.arange(n)
    base = np.stack([(i % 100) * 0.04 - 2.0, (i // 100) * 0.04 - 2.0, np.full(n, 1.5)], 1)
    corner = np.array([[dx, dy, dz] for dx in (0, 0.01) for dy in (0, 0.1) for dz in (0, 0.03)])
    verts = (base[:, None, :] + corner[None]).reshape(-1, 3)
    quad = np.array([[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]])
    faces = (quad[None] + 8 * i[:, None, None]).reshape(-1, 4)
    me = bpy.data.meshes.new("Grating")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.update()
    gr = bpy.data.objects.new("Grating", me)
    sc.collection.objects.link(gr)
    bpy.context.view_layer.update()
    job = lightbake.Bake([floor, gr], "ALL", quality="NORMAL", samples=2)
    plan = job.plan()                              # TooBig today
    assert any(r["ob"] is gr for r in plan["maps"] + plan["verts"])


@pytest.mark.xfail(strict=True, reason="a see-through part becomes an occluder made from ob.data: its OBJECT-linked "
                                       "glass (how the app's CAD parts hold their material) is lost and it casts a "
                                       "full black shadow")
def test_object_linked_glass_lets_the_light_through():
    sc, floor, box, box2 = block_scene()
    bpy.ops.mesh.primitive_plane_add(size=2.5, location=(1.5, -1.5, 0.2))
    roof = bpy.context.object
    roof.name = "Glass roof"
    glass = bpy.data.materials.new("Glass")
    pr = next(n for n in glass.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    pr.inputs["Transmission Weight"].default_value = 1.0
    pr.inputs["Roughness"].default_value = 0.0
    materials.assign(roof, glass)                  # the app's way: slot linked to the object
    bpy.context.view_layer.update()
    assert lightbake.see_through(roof)
    res = lightbake.bake([floor, roof], "ALL", texels_per_m=24, samples=16, quality="DRAFT",
                         denoise=False)
    assert "Glass roof" not in res.items
    under = floor_light(res.items["Floor"], 1.5, -1.5, floor)
    open_ = floor_light(res.items["Floor"], -2.5, -2.5, floor)
    assert under[1] > 0.25 * open_[1], (under, open_)     # data-linked glass gives ~0.5; object-linked gives 0.02


@pytest.mark.xfail(strict=True, reason="two objects with the same id (ob['fr_id'] copied by a duplicate, or ids=) "
                                       "-> one result silently replaces the other, no problem is reported")
def test_ids_that_collide_are_not_lost_silently():
    sc, floor, box, box2 = block_scene()
    box["fr_id"] = "same"
    box2["fr_id"] = "same"
    res = lightbake.bake([floor, box, box2], "ALL", texels_per_m=8, **FAST)
    assert len(res.items) == 3 or any("same" in p for p in res.problems), (sorted(res.items), res.problems)


@pytest.mark.xfail(strict=True, reason="the reference probe sits 1 km beside the parts at the height of their "
                                       "lowest point: under a big ground occluder (a basement below ground level) it "
                                       "is in the dark and the reference is 0 – every light factor is then huge")
def test_reference_probe_is_not_under_a_big_ground():
    sc, floor, box, box2 = block_scene()
    bpy.ops.mesh.primitive_plane_add(size=4000.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    floor.location.z = -0.5                        # the house's basement floor below the ground
    bpy.context.view_layer.update()
    res = lightbake.bake([floor, box, box2], "ALL", occluders=[ground], texels_per_m=8, **FAST)
    assert res.reference[1] > 0.5, res.reference      # 2.2 without the ground


@pytest.mark.xfail(strict=True, reason="SOFT promises the sun's shadow only in ALL, but a Sun lamp is a lamp and is "
                                       "baked with its hard shadow in SOFT too (the page then adds its live sun: two "
                                       "suns); the problem text speaks of a 360° photo or studio light")
def test_soft_does_not_bake_a_sun_lamps_shadow():
    sc, floor, box, box2 = block_scene()
    sc.world = None
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("Sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(45), 0.0, 0.0)          # shadows fall towards +y
    bpy.context.view_layer.update()
    res = lightbake.bake([floor, box, box2], "SOFT", texels_per_m=24, samples=8, quality="DRAFT", denoise=False)
    shade = floor_light(res.items["Floor"], -1.5, 1.2, floor)
    open_ = floor_light(res.items["Floor"], -1.5, -2.5, floor)
    assert shade[1] > 0.5 * open_[1], (shade, open_)


@pytest.mark.xfail(strict=True, reason="glass faces of an object that is not all glass (a window: frame + pane) bake "
                                       "to exactly 0: the page's frOcc = min(1, F) then takes the pane's reflections "
                                       "away and vertex light next to the pane is pulled down")
def test_glass_faces_of_a_mixed_part_are_not_black():
    sc, floor, box, box2 = block_scene()
    verts = [(x, y, 0.0) for y in (0, 1, 2) for x in (0, 1, 2)]
    faces = [(0, 1, 4, 3), (1, 2, 5, 4), (3, 4, 7, 6), (4, 5, 8, 7)]
    me = bpy.data.meshes.new("Window")
    me.from_pydata(verts, [], faces)
    me.update()
    win = bpy.data.objects.new("Window", me)
    win.location = (-2.5, -2.5, 1.5)
    sc.collection.objects.link(win)
    paint = bpy.data.materials.new("Paint")
    glass = bpy.data.materials.new("Glass")
    pr = next(n for n in glass.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    pr.inputs["Transmission Weight"].default_value = 1.0
    me.materials.append(paint)
    me.materials.append(glass)
    for k, p in enumerate(me.polygons):
        p.material_index = 1 if k < 2 else 0
    bpy.context.view_layer.update()
    assert not lightbake.see_through(win)
    res = lightbake.bake([floor, win], "ALL", uv="VERTEX", **FAST)
    mi = np.array([t.material_index for t in me.loop_triangles])
    light = per_triangle(res.items["Window"])
    assert light[mi == 1].mean(0)[1] > 0.3 * light[mi == 0].mean(0)[1], (light[mi == 1].mean(0), res.reference)


@pytest.mark.xfail(strict=True, reason="the bake scene is a copy of the project's scene and keeps its bake settings: "
                                       "'Selected to Active' on in the project -> 'No valid selected objects'")
def test_the_projects_own_bake_settings_do_not_stop_the_light_bake():
    sc, floor, box, box2 = block_scene()
    sc.render.bake.use_selected_to_active = True
    res = lightbake.bake([floor, box, box2], "ALL", texels_per_m=8, **FAST)
    assert len(res.items) == 3


# ---------------------------------------------------------------------------
# what held up
# ---------------------------------------------------------------------------

def test_cancel_at_every_step_leaves_nothing_behind():
    sc, floor, box, box2 = block_scene()
    obs = [floor, box, box2]
    before = counts()
    k = 0
    while True:
        calls = [0]

        def stop(_f, _text, k=k):
            calls[0] += 1
            return calls[0] <= k

        try:
            lightbake.bake(obs, "SOFT", texels_per_m=8, progress=stop, samples=4, quality="DRAFT")
            break
        except Cancelled:
            assert counts() == before, f"cancel at call {k + 1}"
        k += 1
        assert k < 50
    assert counts() == before
    # a panel that stops asking half way (generator dropped)
    job = lightbake.Bake(obs, "ALL", texels_per_m=8, **FAST)
    it = job.steps()
    for _ in range(3):
        next(it)
    assert counts() != before
    del it
    import gc
    gc.collect()
    assert counts() == before


def test_an_eevee_scene_bakes_and_keeps_its_engine():
    sc, floor, box, box2 = block_scene()
    sc.render.engine = "BLENDER_EEVEE"
    before = counts()
    res = lightbake.bake([floor, box, box2], "ALL", texels_per_m=8, **FAST)
    assert sc.render.engine == "BLENDER_EEVEE" and counts() == before
    assert res.reference[1] > 0.5 and len(res.items) == 3


def test_odd_meshes_parents_and_scale():
    """An n-gon, a loose vertex, a zero-area triangle, empty material slots, a child of a non-uniformly scaled
    parent; an object with no faces gets no result."""
    sc, floor, box, box2 = block_scene()
    verts = [(math.cos(a) * 0.5, math.sin(a) * 0.5, 0.0) for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
    verts += [(2, 2, 2), (0.6, 0, 0), (0.7, 0, 0), (0.8, 0, 0)]
    me = bpy.data.meshes.new("odd")
    me.from_pydata(verts, [], [tuple(range(8)), (9, 10, 11)])
    me.update()
    odd = bpy.data.objects.new("Odd", me)
    odd.location = (-2.0, -2.0, 1.0)
    sc.collection.objects.link(odd)
    me.materials.append(None)
    me.materials.append(None)
    me.polygons[1].material_index = 1
    par = bpy.data.objects.new("Parent", None)
    sc.collection.objects.link(par)
    par.location = (0.0, -2.2, 0.0)
    par.scale = (3.0, 0.5, 1.0)
    bpy.ops.mesh.primitive_cube_add(size=0.4)
    child = bpy.context.object
    child.name = "Child"
    child.parent = par
    child.location = (0.0, 0.0, 2.0)
    child.rotation_euler = (0.0, 0.0, math.radians(30))
    pts = bpy.data.objects.new("Points only", bpy.data.meshes.new("pts"))
    pts.data.from_pydata([(0, 0, 0), (1, 0, 0)], [(0, 1)], [])
    sc.collection.objects.link(pts)
    bpy.context.view_layer.update()
    for uv in ("AUTO", "VERTEX"):
        res = lightbake.bake([floor, odd, child, pts], "ALL", uv=uv, texels_per_m=40, **FAST)
        assert set(res.items) == {"Floor", "Odd", "Child"}
        top = per_triangle(res.items["Child"])[top_faces(child)].mean(0)
        assert abs(top[1] / res.reference[1] - 1.0) < 0.2, (uv, top, res.reference)


def test_no_library_look_bakes_black():
    """Every look of the app's material library on a cube in the open: glass and clear plastics are left out (not
    baked), every other look gets light (metals too)."""
    sc, floor, box, box2 = block_scene()
    import bmesh
    cubes = []
    for i, mid in enumerate(materials_lib.MATERIALS):
        me = bpy.data.meshes.new(f"m{i}")
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=0.3)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(mid, me)
        o.location = ((i % 10) * 0.6 - 3.0, (i // 10) * 0.6 - 3.0, 0.15)
        sc.collection.objects.link(o)
        mat = bpy.data.materials.new(mid)
        materials.build_nodes(mat, mid, "RAL 5015")
        materials.assign(o, mat)
        cubes.append(o)
    bpy.context.view_layer.update()
    res = lightbake.bake(cubes, "ALL", uv="VERTEX", **FAST)
    for o in cubes:
        it = res.items.get(o.name)
        if it is None:
            assert lightbake.see_through(o), o.name
            continue
        assert float(it.values.max()) > 0.2 * res.reference[1], o.name


@pytest.fixture(scope="module")
def mill_compressed(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    bare = next(p for p in build.iter_parts(sc) if p.name.startswith("COLUMN"))
    for s in bare.material_slots:                  # one part without a material
        s.material = None
    out = tmp_path_factory.mktemp("lit") / "Mill packed.glb"
    job = web3d.Job(sc, str(out), size=256, light="SOFT", light_quality="DRAFT", light_samples=4, compress=True)
    res = job.run()
    return {"job": job, "res": res, "data": out.read_bytes(), "bare": bare}


def _mesh_of(doc, node_i):
    node = doc["nodes"][node_i]
    if "mesh" in node:
        return node["mesh"], np.zeros(3), 1.0
    ch = doc["nodes"][node["children"][0]]
    return ch["mesh"], np.array(ch["translation"], np.float64), float(ch["scale"][0])


def test_compressed_file_keeps_every_copys_light_uvs(mill_compressed):
    """meshopt reorders the points: each copy's TEXCOORD_1, read back from the file, is still the bake's UV at the
    same point of the part (within 16-bit steps)."""
    job, data = mill_compressed["job"], mill_compressed["data"]
    assert mill_compressed["res"]["compressed"] and core.problems(data) == []
    doc, binary = core.read_glb(data)
    by_name = {it.name: it for it in job._lit.items.values()}
    checked = 0
    for ob, node_i in job._nodes:
        it = by_name.get(ob.name)
        if it is None or it.kind != "MAP":
            continue
        mesh_i, t, s = _mesh_of(doc, node_i)
        me = ob.data
        cpos = np.array([v.co for v in me.vertices])[np.array([tr.vertices for tr in me.loop_triangles]).ravel()]
        for p in doc["meshes"][mesh_i]["primitives"]:
            pos = core.accessor_array(doc, binary, p["attributes"]["POSITION"]).astype(np.float64) * s + t
            idx = core.accessor_array(doc, binary, p["indices"]).ravel().astype(np.int64)
            uv1 = core.accessor_array(doc, binary, p["attributes"]["TEXCOORD_1"]).astype(np.float64)
            uv1[:, 1] = 1.0 - uv1[:, 1]
            for s0 in range(0, len(idx), 500):
                cc = idx[s0:s0 + 500]
                d2 = ((pos[cc][:, None, :] - cpos[None, :, :]) ** 2).sum(-1)
                du = np.abs(it.uv[None, :, :] - uv1[cc][:, None, :]).max(-1)
                du = np.where(d2 <= d2.min(1)[:, None] + 1e-9, du, np.inf)
                assert float(du.min(1).max()) < 2.0 / 65535, ob.name
                checked += len(cc)
    assert checked > 1000


@pytest.mark.xfail(strict=True, reason="a part without a material: mesh_variant swaps only primitives that have a "
                                       "material, so its copy carries TEXCOORD_1 but no light picture (bytes for "
                                       "nothing; the page keeps it live)")
def test_a_part_without_material_gets_its_light_picture(mill_compressed):
    job, data = mill_compressed["job"], mill_compressed["data"]
    doc, _binary = core.read_glb(data)
    bare = mill_compressed["bare"]
    node_i = next(n for ob, n in job._nodes if ob == bare)
    mesh_i, _t, _s = _mesh_of(doc, node_i)
    for p in doc["meshes"][mesh_i]["primitives"]:
        if "TEXCOORD_1" in p["attributes"]:
            assert p.get("material") is not None
            assert "occlusionTexture" in doc["materials"][p["material"]]


def test_lightmap_encode_round_trip_and_tiny_charts():
    """encode/decode and the smallest chart a copy can have (no Blender bake)."""
    f = np.array([0.0, 0.01, 0.5, 1.0, 3.0, np.nan, np.inf, -1.0])
    back = lm.decode(lm.encode(f, 2.0), 2.0)
    assert np.all(np.isfinite(back)) and back.min() >= 0.0 and back.max() <= 2.0 + 1e-6
    assert abs(back[3] - 1.0) < 0.02
    px = lm.chart_pixels(np.zeros((3, 2)), 1e-3, 2)
    assert (px == 5).all()
