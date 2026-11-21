"""Task 0135 in Blender: the web 3D export carries the face data for measuring (flat faces' planes, round faces'
axes with each face's own radius) and the part cards (label, name, or with Hide part names the material group) –
on the test crane, whose sizes are known (tools/make_test_crane.py)."""

import os

import numpy as np
import pytest

from fresing_render.core import web3d as core, web3d_faces as wf

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, callouts, web3d  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module")
def crane():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    yield bpy.context.scene
    fresing_render.unregister()


def export(scene, path, **kw):
    out = web3d.Job(scene, str(path), size=256, page=False, **kw).run()
    with open(out["path"], "rb") as fh:
        return out, fh.read()


def step_of(data):
    """{mesh number: its 16-bit step (the node's scale)}."""
    doc, _ = core.read_glb(data)
    return {n["mesh"]: n.get("scale", [1.0])[0] for n in doc["nodes"] if "mesh" in n}


def diameters(data):
    """{mesh number: sorted Ø of its round faces in mm} read back from the file."""
    doc, _ = core.read_glb(data)
    step = {}
    for n in doc["nodes"]:
        if "mesh" in n:
            step[n["mesh"]] = n.get("scale", [1.0])[0]
    out = {}
    for k, (_runs, rows) in wf.read(data).items():
        out[k] = sorted(round(float(r[7]) * step[k] * 2000, 2) for r in rows if int(r[0]) == wf.ROUND)
    return out


def test_face_data_and_cards_with_hidden_names(crane, tmp_path):
    out, data = export(crane, tmp_path / "crane.glb")
    assert core.problems(data) == []
    got = wf.read(data)
    assert len(got) >= 10 and out["face_bytes"] > 0
    rows = np.vstack([t for _r, t in got.values()])
    assert (rows[:, 0] == wf.FLAT).sum() > 200 and (rows[:, 0] == wf.ROUND).sum() > 30
    all_d = sorted({d for ds in diameters(data).values() for d in ds})
    # the crane's known sizes (task 0259): bolt holes Ø33, boom pin Ø100 in a Ø100.4 bore, luffing pins Ø70, piston
    # Ø198, rod Ø110
    for d in (33.0, 70.0, 110.0, 100.0, 100.4, 198.0):
        assert d in all_d, (d, all_d)
    # task 0219: the CAD edges – straight ones and round rims, among them the boom pin's Ø100 and the bolt holes' Ø33
    edges = wf.read_edges(data)
    assert len(edges) >= 10
    allE = np.vstack(list(edges.values()))
    assert (allE[:, 0] == wf.LINE).sum() > 200 and (allE[:, 0] == wf.CIRCLE).sum() > 30
    rims = set()
    for k, et in edges.items():
        for e in et[et[:, 0] == wf.CIRCLE]:
            rims.add(round(float(np.linalg.norm(e[6:9] - e[3:6])) * step_of(data)[k] * 2000, 1))
    for d in (33.0, 100.0):
        assert d in rims, (d, sorted(rims))
    # the boom pin's bore Ø100.4 and the boom's round end round it share one axis line (0122): each keeps its own radius
    assert any(100.4 in ds and 500.0 in ds for ds in diameters(data).values())
    doc, _ = core.read_glb(data)
    names = [build.PROP_NAME]
    cards = [n["extras"]["fr_card"] for n in doc["nodes"] if "fr_card" in n.get("extras", {})]
    groups = {p.get(build.PROP_GROUP, "") for p in build.iter_parts(crane)}
    part_names = {str(p.get(names[0]) or p.name) for p in build.iter_parts(crane)}
    assert cards and set(cards) <= groups, (set(cards) - groups)
    for n in part_names - groups:                          # never a part name in the file
        assert n.encode("utf-8") not in data, n


def test_cards_with_names_and_labels_and_no_face_data(crane, tmp_path):
    parts = [p for p in build.iter_parts(crane) if p.type == "MESH" and p.visible_get()]
    labelled = parts[0]
    c = callouts.add(crane, labelled, labelled.matrix_world.translation, text="Slew drive")
    try:
        _out, data = export(crane, tmp_path / "named.glb", hide_names=False)
        doc, _ = core.read_glb(data)
        cards = {n["name"]: n["extras"]["fr_card"] for n in doc["nodes"] if "fr_card" in n.get("extras", {})}
        assert "Slew drive" in cards.values()
        other = parts[1]
        name = str(other.get(build.PROP_NAME) or other.name)
        assert cards.get(name) == name
        # Hide part names: the label still shows (the owner's own words for showing)
        _out, hidden = export(crane, tmp_path / "hidden.glb")
        assert b"Slew drive" in hidden
    finally:
        crane.fresing.callouts.remove(len(crane.fresing.callouts) - 1)
    out_on, with_faces = export(crane, tmp_path / "on.glb")
    out_off, without = export(crane, tmp_path / "off.glb", faces=False)
    assert wf.read(without) == {} and out_off["face_bytes"] == 0
    # task 0219: with the edges about a third more on this draft with small pictures (the page: +11 %)
    assert 0 < len(with_faces) - len(without) < 0.4 * len(without)
    assert c is not None


def test_live_label_fields_are_left_out_of_an_animated_page(crane):
    """Task 0189 (0183 row 13): an animated page showed a label's live fields as at the exported frame ("Lay speed
    0.0 m/min" while the lay plays). On an animated page the lines with a field are left out; a label of fields only
    gives the part's name; a still page fills them in as before."""
    parts = [p for p in build.iter_parts(crane) if p.type == "MESH" and p.visible_get()]
    a = callouts.add(crane, parts[0], parts[0].matrix_world.translation, text="Main cable\nLay speed {speed} m/min")
    b = callouts.add(crane, parts[1], parts[1].matrix_world.translation, text="{top} kN")
    try:
        still = web3d.part_labels(crane)
        assert still[parts[0].name] == "Main cable\nLay speed – m/min" and still[parts[1].name] == "– kN"
        moving = web3d.part_labels(crane, animated=True)
        assert moving[parts[0].name] == "Main cable"
        assert parts[1].name not in moving                    # the card shows the part's name
    finally:
        crane.fresing.callouts.remove(len(crane.fresing.callouts) - 1)
        crane.fresing.callouts.remove(len(crane.fresing.callouts) - 1)
    assert a is not None and b is not None
