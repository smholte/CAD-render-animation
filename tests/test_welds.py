"""Task 0319: welds in Blender – picking faces like Inventor, the quick way, the bead objects, the looks, hiding,
save + reopen, model update, motion, slice, X-ray, clash, web 3D and the Client view.

The invented weldment of ``tools/make_test_weldment.py`` (mm; BASE PLATE 400 x 300 x 12 painted, FIN on it, GUSSET,
POST through a hole, BRANCH coped onto the MAIN TUBE, EXTENSION PLATE butt to the base)."""

import json
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
WELDMENT = os.path.join(HERE, "data", "test_weldment.step")
WELDMENT_B = os.path.join(HERE, "data", "test_weldment_b.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, ops_welds, weld_looks, welds  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=WELDMENT, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def part(sc, name):
    return next(o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name)


def face_at(ob, point_mm, normal):
    """The CAD face of ``ob`` through this world point (mm) facing this way."""
    p, t, f = welds.mesh_tables(ob.data)
    m = np.array([list(r) for r in ob.matrix_world])
    w = p @ m[:3, :3].T + m[:3, 3]
    v = w[t]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    q = np.asarray(point_mm, float) / 1000.0
    ok = (n @ np.asarray(normal, float) > 0.99) & (np.abs(((q - v[:, 0]) * n).sum(1)) < 1e-4)
    assert ok.any(), (ob.name, point_mm)
    return int(np.bincount(f[ok]).argmax())


def beads(item):
    return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.KIND]


def heat(item):
    return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.HEAT_KIND]


def pick_fin_one_side(sc):
    """Inventor's way: the base plate's top, Next, the fin's +y side face: one seam 200 mm."""
    pk = ops_welds.start(sc)
    base, fin = part(sc, "BASE PLATE"), part(sc, "FIN")
    assert pk.click(base, face_at(base, (100, 100, 12), (0, 0, 1))) == ""
    assert pk.next() == ""
    assert pk.click(base, 0) != ""                       # the first part again: refused, with a reason
    assert pk.click(fin, face_at(fin, (150, 155, 50), (0, 1, 0))) == ""
    return pk


# ---------------------------------------------------------------------------
# picking
# ---------------------------------------------------------------------------

def test_picker_two_face_sets_like_inventor(scene):
    pk = pick_fin_one_side(scene)
    assert [round(s.length * 1000) for s in pk.seams] == [200]
    assert len(welds.settings(scene).preview) == 1
    assert pk.next() == ""
    it = pk.item
    ops_welds.finish(scene)
    assert [round(s.length * 1000) for s in it.seams] == [200]
    assert not it.whole and json.loads(it.faces_a) and json.loads(it.faces_b)
    b, h = beads(it), heat(it)
    assert len(b) == 1 and len(h) == 1
    assert b[0].parent == part(scene, "BASE PLATE") and h[0].parent == b[0].parent
    assert b[0].data.uv_layers.get("fr_weld") is not None and h[0].data.uv_layers.get("fr_weld_end") is not None
    # the bead sits in the corner on the fin's +y side: y from 155 to ~155 + leg, z from 12 up
    co = np.array([b[0].matrix_world @ v.co for v in b[0].data.vertices]) * 1000
    assert co[:, 1].min() > 154.8 and co[:, 2].min() > 11.8 and 160 < co[:, 1].max() < 165
    assert welds.settings(scene).picking == ""


def test_picker_shift_click_adds_and_takes_away(scene):
    pk = ops_welds.start(scene)
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    top = face_at(base, (100, 100, 12), (0, 0, 1))
    pk.click(base, top)
    pk.next()
    s1 = face_at(fin, (150, 155, 50), (0, 1, 0))
    s2 = face_at(fin, (150, 145, 50), (0, -1, 0))
    pk.click(fin, s1)
    pk.click(fin, s2, add=True)
    assert len(pk.seams) == 2 and pk.faces_b == {s1, s2}
    pk.click(fin, s2, add=True)                         # Shift-click again: taken away
    assert len(pk.seams) == 1
    pk.click(fin, s2)                                    # a plain click: only this face
    assert pk.faces_b == {s2} and len(pk.seams) == 1
    ops_welds.finish(scene)


def test_unticked_preview_seams_are_left_out(scene):
    pk = ops_welds.start(scene)
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    pk.click(base, face_at(base, (100, 100, 12), (0, 0, 1)))
    pk.next()
    pk.click(fin, face_at(fin, (150, 155, 50), (0, 1, 0)))
    pk.click(fin, face_at(fin, (150, 145, 50), (0, -1, 0)), add=True)
    welds.settings(scene).preview[1].enabled = False
    assert pk.next() == ""
    it = pk.item
    ops_welds.finish(scene)
    assert [s.enabled for s in it.seams] == [True, False]
    assert len(it.seams) == 2


def test_faces_that_do_not_meet_say_so(scene):
    pk = ops_welds.start(scene)
    base, main = part(scene, "BASE PLATE"), part(scene, "MAIN TUBE")
    pk.click(base, face_at(base, (100, 100, 12), (0, 0, 1)))
    pk.next()
    pk.click(main, 0)
    assert pk.seams == [] and "do not meet" in pk.note
    assert "do not meet" in pk.next()
    ops_welds.finish(scene)


# ---------------------------------------------------------------------------
# the quick way: two parts
# ---------------------------------------------------------------------------

EXPECT = {("BASE PLATE", "FIN"): [10, 10, 200, 200], ("BASE PLATE", "POST"): [189, 189],
          ("BASE PLATE", "BRANCH"): [126, 152], ("BRANCH", "MAIN TUBE"): [128, 155],
          ("BASE PLATE", "EXTENSION PLATE"): [12, 12, 300, 300]}


@pytest.mark.parametrize("pair", sorted(EXPECT))
def test_two_parts_every_seam(scene, pair):
    it = welds.make(scene, part(scene, pair[0]), [], part(scene, pair[1]), [], whole=True)
    assert sorted(round(s.length * 1000) for s in it.seams) == EXPECT[pair]
    if pair[1] in ("POST", "BRANCH", "MAIN TUBE"):
        assert all(s.closed for s in it.seams)            # all round
    if pair[1] == "EXTENSION PLATE":
        assert {s.kind for s in it.seams} == {"BUTT"}


def test_weld_two_parts_button_needs_two_selected(scene):
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    for o in scene.objects:
        o.select_set(False)
    base.select_set(True)
    assert bpy.ops.fresing.weld_parts() == {"CANCELLED"}
    fin.select_set(True)
    bpy.context.view_layer.objects.active = fin
    assert bpy.ops.fresing.weld_parts() == {"FINISHED"}
    it = welds.active(scene)
    assert it.part_a == fin and it.part_b == base and it.whole      # the active part carries the bead


def test_defaults_from_the_parts(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    assert it.size == pytest.approx(0.005)                # half the 10 mm fin
    assert it.finish == "PAINTED"                         # the base plate is painted
    tube = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "POST"), [], whole=True)
    assert tube.size == pytest.approx(0.0025)             # the post's 5 mm wall


# ---------------------------------------------------------------------------
# shape and look
# ---------------------------------------------------------------------------

def test_ticks_and_sizes_rebuild_the_bead(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    l0 = it["fr_length"]
    it.seams[0].enabled = False
    assert it["fr_length"] == pytest.approx(l0 - 0.2, abs=1e-4)
    def top():
        b = beads(it)[0]
        return max((b.matrix_world @ v.co).z for v in b.data.vertices)
    z0 = top()
    it.size = 0.008
    assert top() > z0 + 0.003
    it.intermittent, it.length, it.pitch = True, 0.04, 0.08
    assert it.get("fr_length") < 0.25
    for s in it.seams:
        s.enabled = False
    assert beads(it) == [] and heat(it) == []
    s = welds.stats(scene)
    assert s["seams"] == 0 and s["welds"] == 1


@pytest.mark.parametrize("metal, process, finish", [
    ("STEEL", "MAG", "AS_WELDED"), ("STEEL", "STICK", "AS_WELDED"), ("STAINLESS", "TIG", "AS_WELDED"),
    ("ALUMINIUM", "MIG", "AS_WELDED"), ("ALUMINIUM", "TIG", "AS_WELDED"), ("STEEL", "MAG", "GROUND"),
    ("STEEL", "MAG", "PAINTED")])
def test_looks_build(scene, metal, process, finish):
    it = welds.make(scene, part(scene, "FIN"), [], part(scene, "GUSSET"), [], whole=True)
    it.metal, it.process, it.finish = metal, process, finish
    it.rust, it.spatter = 0.4, True
    b, h = beads(it)[0], heat(it)[0]
    bm, hm = b.data.materials[0], h.data.materials[0]
    assert bm.name.startswith(weld_looks.PREFIX) and hm.name.startswith(weld_looks.PREFIX)
    uvs = {n.uv_map for m in (bm, hm) for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeUVMap"}
    assert "fr_weld" in uvs and "fr_weld_end" in uvs
    if finish == "PAINTED":
        assert bm.get(weld_looks.SRC)                     # a copy of the part's paint
        bsdf = weld_looks._principled_of(bm.node_tree)
        assert bsdf.inputs["Normal"].is_linked           # the ripples through the paint


def test_same_look_shares_one_material(scene):
    a = welds.make(scene, part(scene, "FIN"), [], part(scene, "GUSSET"), [], whole=True)
    b = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "GUSSET"), [], whole=True)
    for it in (a, b):
        it.finish, it.metal, it.process = "AS_WELDED", "STEEL", "MAG"
    assert beads(a)[0].data.materials[0] == beads(b)[0].data.materials[0]


def test_painted_bead_follows_the_paint(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    assert it.finish == "PAINTED"
    src = welds.part_material(part(scene, "BASE PLATE"))
    first = beads(it)[0].data.materials[0]
    from fresing_render.blender import materials
    materials.build_nodes(src, src["fr_material"], "RAL 2004", 0.3)     # the group's colour and wear change
    assert welds.sync_paint(scene) == 1
    now = beads(it)[0].data.materials[0]
    assert now.get(weld_looks.SRC) == weld_looks.source_signature(src)
    assert welds.sync_paint(scene) == 0                    # nothing more to do
    del first


def test_two_metals_warn_calmly(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    assert welds.warning(it) == ""
    from fresing_render.blender import materials
    mat = materials.ensure_material("weld test alu", "aluminium_machined")
    materials.assign(part(scene, "FIN"), mat)
    assert "aluminium" in welds.warning(it)


# ---------------------------------------------------------------------------
# kept through everything
# ---------------------------------------------------------------------------

def test_hidden_with_either_part(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    b = beads(it)[0]
    from fresing_render.blender import logic
    dg = bpy.context.evaluated_depsgraph_get()
    assert not b.evaluated_get(dg).hide_render
    logic.set_hidden(part(scene, "FIN"), True)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    assert b.evaluated_get(dg).hide_render
    logic.set_hidden(part(scene, "FIN"), False)
    it.hidden = True
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    assert b.evaluated_get(dg).hide_render


def test_save_and_reopen(scene, tmp_path):
    pk = pick_fin_one_side(scene)
    pk.next()
    ops_welds.finish(scene)
    welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "POST"), [], whole=True)
    path = str(tmp_path / "welds ä.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    its = list(welds.items(sc))
    assert len(its) == 2 and all(len(beads(it)) == 1 for it in its)
    its[0].size = 0.007                                   # found again after the load (nothing kept in memory)
    assert len(beads(its[0])) == 1 and not its[0].lost


def test_model_update_finds_faces_again_or_says_lost(scene):
    pk = pick_fin_one_side(scene)                          # picked faces on the fin: its side gets taller in B
    pk.next()
    fin_side = pk.item
    ops_welds.finish(scene)
    pk = ops_welds.start(scene)                           # picked faces on the post: unchanged in B
    base, post = part(scene, "BASE PLATE"), part(scene, "POST")
    pk.click(base, face_at(base, (100, 100, 12), (0, 0, 1)))
    pk.next()
    p, t, f = welds.mesh_tables(post.data)
    outer = int(np.bincount(f[np.linalg.norm(p[t].mean(1)[:, :2] - [0.3, 0.2], axis=1) > 0.029]).argmax())
    pk.click(post, outer)
    pk.next()
    post_weld = pk.item
    ops_welds.finish(scene)
    whole = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "GUSSET"), [], whole=True)
    branch = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "BRANCH"), [], whole=True)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=WELDMENT_B, quality="draft", update_root=root.name) == {"FINISHED"}
    sc = bpy.context.scene
    by = {it.key: it for it in welds.items(sc)}
    assert by[post_weld.key].lost is False and len(beads(by[post_weld.key])) == 1
    assert by[post_weld.key].part_a == part(sc, "BASE PLATE")
    assert by[whole.key].lost is False and len(beads(by[whole.key])) == 1
    assert by[fin_side.key].lost and "pick again" in by[fin_side.key].note
    assert by[branch.key].lost and "not in the new model" in by[branch.key].note
    assert beads(by[fin_side.key]) == [] and beads(by[branch.key]) == []
    notes = [n.text for n in sc.fresing.report_notes]
    assert sum("Weld '" in n for n in notes) == 2
    # every bead rides on a part of the new model
    for ob in bpy.data.objects:
        if welds.is_weld(ob):
            assert ob.parent is not None and ob.parent.name in sc.objects


def test_lost_weld_is_picked_again(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    welds._set_lost(it, "Weld lost its faces – pick again")
    pk = ops_welds.start(scene, it.key)
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    pk.click(base, face_at(base, (100, 100, 12), (0, 0, 1)))
    pk.next()
    pk.click(fin, face_at(fin, (150, 155, 50), (0, 1, 0)))
    assert pk.next() == ""
    ops_welds.finish(scene)
    assert len(welds.items(scene)) == 1 and not it.lost and len(beads(it)) == 1
    assert [round(s.length * 1000) for s in it.seams] == [200]


def test_motion_welded_parts_that_move_apart(scene):
    from fresing_render.blender import joints
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    assert not welds.moves_apart(it)
    fin = part(scene, "FIN")
    joints.create(scene, "ROTATE", [fin], (0.05, 0.15, 0.012), (1, 0, 0), name="Fin hinge")
    assert welds.moves_apart(it)
    assert "left joint" in welds.move_as_one(scene, it)
    assert not welds.moves_apart(it)


def test_slice_and_xray_take_the_weld_along(scene):
    from fresing_render.blender import fade, section
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    base = part(scene, "BASE PLATE")
    cut = section.add(scene, [("PART", base, "")])
    section.sync(scene)
    for ob in welds.objects_of(it):
        assert ob.get(section.ATTR + cut.key) and ob.get(section.NOCAP)
        assert all(section.is_wrapped(m) for m in ob.data.materials)
    fade.apply_look(scene, [base])
    for ob in welds.objects_of(it):
        assert ob.get(fade.LOOK)


def test_clash_and_structure_leave_welds_out(scene):
    from fresing_render.blender import clash, logic
    welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    objs = clash.objects(scene)
    assert objs and not any(welds.is_weld(o) for o in objs)
    tree = logic.Tree(scene)
    assert not any(welds.is_weld(o) for o in tree.descendants(build.model_roots(scene)[0]))


def test_web3d_takes_the_beads_not_the_heat_zones(scene):
    from fresing_render.blender import web3d
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    parts, _marks = web3d.objects(scene)
    assert beads(it)[0] in parts and heat(it)[0] not in parts


def test_removing_a_part_marks_its_weld_lost(scene):
    from fresing_render.blender import remove
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    fin = part(scene, "FIN")
    bpy.data.objects.remove(fin)
    assert welds.lost_parts(scene) == 1
    assert it.lost and welds.objects_of(it) == []
    del remove


def test_client_view_shows_welds_but_does_not_edit():
    from fresing_render.blender import lock
    for op in ("fresing.weld_add", "fresing.weld_parts", "fresing.weld_remove", "fresing.weld_ticks",
               "fresing.ctx_weld", "fresing.weld_move_as_one"):
        assert not lock.allowed(op)
    from fresing_render.blender import context_menu
    assert "Weld to another part…" in context_menu.ON_PART and "Weld to another part…" in context_menu.CLIENT_DROPS


def test_remove_weld(scene):
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    key = it.key
    assert bpy.ops.fresing.weld_remove(key=key) == {"FINISHED"}
    assert len(welds.items(scene)) == 0
    assert not [o for o in bpy.data.objects if welds.is_weld(o)]


def test_the_bead_moves_with_its_first_part(scene):
    """Exploded views, animations and Place move the part: its bead (a child) goes along."""
    from mathutils import Matrix
    it = welds.make(scene, part(scene, "BASE PLATE"), [], part(scene, "FIN"), [], whole=True)
    b = beads(it)[0]
    bpy.context.view_layer.update()
    before = b.matrix_world.copy()
    base = part(scene, "BASE PLATE")
    base.matrix_basis = Matrix.Translation((0.0, 0.0, 0.3)) @ base.matrix_basis
    bpy.context.view_layer.update()
    assert (b.matrix_world.translation - before.translation).z == pytest.approx(0.3, abs=1e-6)
