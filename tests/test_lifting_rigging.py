"""Task 0232: 8 Lifting plan > Rigging and the reeved hoist rope in the app – the study's C2 / C3 hand cases on a real
hang, the load following the hook, Set down, Build, save and open, a model update, the Client view, the AT-100's 8
falls and the time of a hook move. Blender as a Python module."""

from __future__ import annotations

import math
import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.core import lifting as core  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "fresing_render", "data")
LOADS = os.path.join(DATA, "test_loads.step")
OUT = "/tmp/fr_lifting_rig_test"


@pytest.fixture(scope="module", autouse=True)
def registered():
    os.environ["FRESING_LIFTING_UNDERSTOOD"] = "1"
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def _mods():
    from fresing_render.blender import lifting as BL, lifting_rig as RG, lifting_rope as RP
    return BL, RG, RP


def _new(step=LOADS):
    BL, _RG, _RP = _mods()
    bpy.ops.wm.read_homefile(use_empty=True)
    from fresing_render.blender import workspaces
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    sc.fresing.out_folder = OUT
    if step:
        assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    BL.forget()
    return sc


def _update():
    bpy.context.view_layer.update()


def _crane(sc, name="AT-40", at=(1.0, 7.6, 0.0)):
    BL, _RG, _RP = _mods()
    c = BL.place(bpy.context, os.path.join(DATA, "lifting", name), at, math.pi)
    BL.apply_pose(sc, c, "Set up")
    return c


def _box_load(sc, mass_t, size, cog_x=None):
    """A box load whose CoG (moved by hand) lies ``cog_x`` m from its -x end on its middle line, 0.5 m under the top."""
    BL, _RG, _RP = _mods()
    ld = BL.new_box(sc, size, mass_t, location=(6.0, 0.0, 0.0), name="Beam")
    _update()
    mk = BL.ensure_marker(sc, ld)
    if cog_x is not None:
        mk.location = Vector((-size[0] / 2 + cog_x, 0.0, size[2] - 0.5))
    _update()
    return ld


def _skid(sc):
    BL, RG, _RP = _mods()
    from fresing_render.blender import build, logic
    part = next(o for o in logic.descendants(build.model_roots(sc)[0]) if o.get(build.PROP_NAME) == "PUMP SKID.ASM")
    ld = BL.new_load(sc, [part], "Pump skid")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", 6.0, "ESTIMATE"
    assert RG.find_named(sc, ld) == 4
    ld.leg_length = 4.0
    return ld


def _above(sc, c, ld, up=4.0):
    BL, _RG, _RP = _mods()
    p = BL.above_load(sc, ld)
    p[2] += up
    a = BL.hook_to(sc, c, p, ld)
    assert a.ok, a.reason
    return a


def test_c2_hand_case_on_a_real_hang():
    """Study 0180 C2: 10 t, A and B 4.0 m apart, CoG 1.5 m from A, legs 3.3541 / 3.9051 m (hook 3 m above): the beam
    hangs level, T_A 6.988 t, T_B 4.881 t (within 0.5 %); the C2 row against an 8 t leg is 87.3 %."""
    BL, RG, _RP = _mods()
    sc = _new()
    c = _crane(sc)
    ld = _box_load(sc, 10.0, (4.0, 0.6, 1.0), cog_x=1.5)
    box = ld.box
    RG.add_point(sc, ld, box, np.array(box.matrix_world @ Vector((-2.0, 0.0, 1.0))))
    RG.add_point(sc, ld, box, np.array(box.matrix_world @ Vector((2.0, 0.0, 1.0))))
    ld.points[0].length, ld.points[1].length = math.hypot(1.5, 3.0), math.hypot(2.5, 3.0)
    ld.sling = "builtin:CH8-2L-16"                          # 8 t per leg
    _above(sc, c, ld)
    h = RG.hang(sc, c, ld)
    assert h.ok and h.tilts[0] < 0.05
    r = RG.result(ld)
    legs = {lg["name"]: lg for lg in r["legs"]}
    assert core.tonnes(legs["A"]["force"] / core.G) == pytest.approx(6.988, rel=5e-3)
    assert core.tonnes(legs["B"]["force"] / core.G) == pytest.approx(4.881, rel=5e-3)
    assert legs["A"]["angle"] == pytest.approx(26.57, abs=0.1)
    c2 = r["checks"][0]
    assert c2["check"] == "C2" and c2["parts"][0]["use"] == pytest.approx(0.873, abs=5e-3)
    assert RG.check_hang(sc)


def test_c3_hand_case_on_a_real_hang():
    """Study 0180 C3: 20 t on a 4.0 x 3.0 m rectangle, legs 4.3012 m (35.54°): two legs carry 12.289 t each (rigid),
    98.3 % of a 12.5 t leg, the assembly 76.2 % of 2.1 x 12.5 t."""
    BL, RG, _RP = _mods()
    sc = _new()
    c = _crane(sc, "AT-100", (1.0, 12.0, 0.0))
    ld = _box_load(sc, 20.0, (4.0, 3.0, 1.0), cog_x=2.0)
    for x, y in ((2, 1.5), (-2, 1.5), (-2, -1.5), (2, -1.5)):
        RG.add_point(sc, ld, ld.box, np.array(ld.box.matrix_world @ Vector((x, y, 1.0))))
    ld.leg_length = 4.3012
    ld.sling = "builtin:CH8-4L-20"                          # 12.5 t per leg
    _above(sc, c, ld)
    RG.hang(sc, c, ld)
    r = RG.result(ld)
    for lg in r["legs"]:
        assert core.tonnes(lg["planned"] / core.G) == pytest.approx(12.289, rel=5e-3)
        assert lg["angle"] == pytest.approx(35.54, abs=0.1)
    c3 = r["checks"][0]
    assert c3["check"] == "C3"
    assert c3["parts"][0]["use"] == pytest.approx(0.983, abs=5e-3)
    assert c3["parts"][1]["use"] == pytest.approx(0.762, abs=5e-3)
    assert RG.check_hang(sc)


def test_the_skid_hangs_follows_the_hook_sets_down_and_survives_build_and_reopen():
    BL, RG, _RP = _mods()
    from fresing_render.blender import animation
    sc = _new()
    c = _crane(sc)
    ld = _skid(sc)
    _above(sc, c, ld)
    RG.hang(sc, c, ld)
    assert ld.sling and ld.shackle                         # picked when none was
    assert RG.check_hang(sc).startswith("Pump skid on AT-40")
    r = RG.result(ld)
    assert r["tilt"] > 1.0 and not RG.stale(sc, ld)
    # the rigging's mass is in the gross load
    ro = BL.readout(sc, c, ld)
    assert ro.rigging == pytest.approx(RG.rigging_mass(ld)) and ro.rigging > 0
    # Hook to here: the load comes along, rigid
    cog0, hook0 = BL.cog_world(ld), BL._hook_block_world(sc, c)
    p = BL.above_load(sc, ld) + np.array([1.0, -1.0, 0.0])
    assert BL.hook_to(sc, c, p, ld).ok
    _update()
    d = BL._hook_block_world(sc, c) - hook0
    assert np.allclose(BL.cog_world(ld) - cog0, d, atol=2e-3)
    # Build keeps it on the hook
    from fresing_render.blender import build, logic
    ibc = next(o for o in logic.descendants(build.model_roots(sc)[0]) if o.get(build.PROP_NAME) == "IBC ON PALLET.ASM")
    a = sc.fresing.animations.add()
    a.name = "Hide the IBC"
    b = a.blocks.add()
    b.kind = "HIDE"
    b.target_uid = ibc.get(build.PROP_UID)
    b.start, b.duration = 0.0, 0.5
    animation.bake(sc, a)
    sc.frame_set(1)
    _update()
    assert np.linalg.norm((BL.cog_world(ld) - BL._hook_block_world(sc, c))[:2]) < 0.005
    animation.clear_keys(sc)
    # a change after hanging: out of date
    ld.leg_length = 4.5
    assert RG.stale(sc, ld)
    ld.leg_length = 4.0
    # Set down: stays where it is; the slings are hidden, the shackles stay
    here = BL.cog_world(ld)
    RG.set_down(sc, ld)
    assert np.allclose(BL.cog_world(ld), here, atol=1e-6)
    assert BL.hook_to(sc, c, BL.above_load(sc, ld) + np.array([0, 0, 3.0]), ld).ok
    _update()
    assert np.allclose(BL.cog_world(ld), here, atol=1e-6)
    hidden = [rr.obj.hide_render for rr in ld.rig_objects if rr.obj.name.startswith(RG.SLING)]
    assert hidden and all(hidden)
    # save and open: the plan, the hang and the rope are kept
    path = os.path.join(OUT, "rig.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    ld = sc.fresing.lifting.loads[0]
    c = sc.fresing.lifting.cranes[0]
    assert ld.rig_state == "DOWN" and len(ld.points) == 4 and np.allclose(BL.cog_world(ld), here, atol=1e-5)
    _RP_ = _mods()[2]
    assert _RP_.is_reeved(c)
    # Remove: back where it stood
    RG.remove(sc, ld)
    assert BL.cog_world(ld)[2] < here[2] - 0.1


def test_a_model_update_keeps_the_lift_points_and_the_hang():
    BL, RG, _RP = _mods()
    from fresing_render.blender import build
    sc = _new()
    c = _crane(sc)
    ld = _skid(sc)
    _above(sc, c, ld)
    RG.hang(sc, c, ld)
    cog = BL.cog_world(ld)
    root = next(r for r in build.model_roots(sc) if BL.crane_of_root(sc, r) is None)
    assert bpy.ops.fresing.import_step(filepath=LOADS, quality="draft", update_root=root.name) == {"FINISHED"}
    _update()
    ld = sc.fresing.lifting.loads[0]
    assert len(ld.points) == 4 and all(p.obj is not None and p.obj.name in sc.objects for p in ld.points)
    assert ld.rig_state == "HUNG"
    assert np.allclose(BL.cog_world(ld), cog, atol=2e-3)
    assert all(o.constraints.get(RG.CON) is not None for o in RG.top_objects(ld))


def test_client_view_cannot_edit_the_rigging():
    BL, RG, _RP = _mods()
    from fresing_render.blender import workspaces
    sc = _new()
    c = _crane(sc)
    ld = _skid(sc)
    _above(sc, c, ld)
    assert bpy.ops.fresing.lifting_hang.poll()
    workspaces.switch(sc, "Client view")
    try:
        for op in (bpy.ops.fresing.lifting_hang, bpy.ops.fresing.lifting_points_find, bpy.ops.fresing.lifting_reeve,
                   bpy.ops.fresing.lifting_point_add):
            assert not op.poll(), op
    finally:
        workspaces.switch(sc, "All functions")


@pytest.mark.parametrize("name,falls,head,block", [("AT-100", 8, 4, 4), ("CC-1600", 28, 14, 14)])
def test_the_rope_runs_in_its_falls_and_a_hook_move_is_quick(name, falls, head, block):
    """AT-100: 8 falls over 4 + 4 sheaves; hook 1 m up = 8 m of rope (the drawn rope and the drum's turn). The time of
    one hook move (set the hoist, update the scene) is printed for the report."""
    BL, _RG, RP = _mods()
    sc = _new(None)
    c = BL.place(bpy.context, os.path.join(DATA, "lifting", name), (0.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Working")
    assert c.reeved and c.falls == falls
    assert RP.falls_drawn(sc, c) == falls and RP.sheaves_drawn(c) == (head, block)
    msg = RP.check(sc, c, 1.0)
    assert f"{falls} falls" in msg
    hoist = BL.rig_of(c).role["hoist"]
    v = BL.values(sc, c)[hoist]
    t0 = time.perf_counter()
    for k in range(20):
        BL.set_values(sc, c, {hoist: v + 100.0 * (k + 1)})
    t_move = (time.perf_counter() - t0) / 20
    RP.unreeve(sc, c, keep_cad=True)
    _update()
    t0 = time.perf_counter()
    for k in range(20):
        BL.set_values(sc, c, {hoist: v + 100.0 * (k + 1)})
    t_plain = (time.perf_counter() - t0) / 20
    print(f"\n{name}: hook move {t_move * 1000:.2f} ms reeved, {t_plain * 1000:.2f} ms without the rope")
    assert t_move < 0.2
    # reeved again by the button
    assert bpy.ops.fresing.lifting_reeve() == {"FINISHED"} and RP.falls_drawn(sc, c) == falls
    # Remove takes all of it
    n = len(bpy.data.objects)
    BL.remove(sc, c)
    assert not [o for o in bpy.data.objects if o.get(RP.TAG)]
    assert len(bpy.data.objects) < n
