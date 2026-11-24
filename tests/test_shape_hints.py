"""Task 0302: shape hints – an unnamed washer, hex nut or O-ring found by its mesh, and nothing else.

The shapes are made with OpenCascade and meshed by the importer's own mesher at all three qualities, turned and
moved, so the test sees the meshes the app sees. Look-alikes (bolts, screws, flanges, bearings, discs, spacers,
hex bar, square nuts, a thick ring) must give nothing; a ring of square section is a washer, not an O-ring.
"""

import json
import math
import os
import sys

import numpy as np
import pytest

pytest.importorskip("OCP")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import model_details as md  # noqa: E402

from fresing_render.core import fasteners, part_types  # noqa: E402
from fresing_render.core import rules as R  # noqa: E402
from fresing_render.core import shape_hints as H  # noqa: E402
from fresing_render.demo_model import geom as g  # noqa: E402
from fresing_render.importer import step_reader as SR  # noqa: E402

OCC = SR._occ()


def _mesh(shape, quality="normal", standard=False):
    lin, ang = SR.QUALITY[quality]
    pos, _nrm, tri, _c, _p = SR._mesh_shape(OCC, shape, lin, ang, facets=SR.FACETS[quality], standard=standard)
    return np.asarray(pos), np.asarray(tri)


def _torus(r_mid, r_sec):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    return BRepPrimAPI_MakeTorus(r_mid, r_sec).Shape()


def _turn():
    a, b = 0.7, 1.1
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    rz = np.array([[math.cos(b), -math.sin(b), 0], [math.sin(b), math.cos(b), 0], [0, 0, 1]])
    return rx @ rz


def _cases():
    out = []
    for d in (6, 8, 12, 20, 30):
        out += [(f"ISO 7089 washer M{d}", md.washer(d), "washer"), (f"ISO 4032 nut M{d}", md.nut(d), "hex_nut"),
                (f"hex bolt M{d}", md.hex_bolt(d, 30), ""), (f"socket screw M{d}", md.socket_screw(d, 30), "")]
    for r_mid, r_sec in ((10, 1.5), (25, 2.5), (60, 3.5)):
        out.append((f"O-ring {2 * r_mid}x{2 * r_sec}", _torus(r_mid, r_sec), "o_ring"))
    holes = [g.cyl(3, 10, (28 * math.cos(k), 28 * math.sin(k), -1)) for k in np.linspace(0, 2 * math.pi, 6,
                                                                                         endpoint=False)]
    out += [
        ("disc without a hole", g.cyl(20, 3), ""),
        ("long spacer", g.tube(10, 5, 20), ""),
        ("short spacer", g.tube(10, 5, 6), ""),
        ("ring 20x12x4: square section, a thick washer, no O-ring", g.tube(10, 6, 4), "washer"),
        ("ring 20x12x8", g.tube(10, 6, 8), ""),
        ("flange with bolt holes", g.cut(g.cyl(40, 6), g.cyl(15, 10, (0, 0, -1)), *holes), ""),
        ("stepped ring", g.cut(g.fuse(g.cyl(20, 2), g.cyl(14, 5)), g.cyl(8, 10, (0, 0, -1))), ""),
        ("ball bearing rings", g.fuse(g.tube(26, 22, 15), g.tube(17, 12.5, 15), g.tube(22.5, 16.5, 1, (0, 0, 7))), ""),
        ("hex bar with a bore", g.cut(md.hex_prism(13, 40), g.cyl(4, 50, (0, 0, -1))), ""),
        ("hex without a bore", md.hex_prism(13, 6.8), ""),
        ("square nut", g.cut(g.box(-6.5, -6.5, 0, 13, 13, 6), g.cyl(4, 10, (0, 0, -1))), ""),
        ("ring 300 mm", g.cut(g.cyl(150, 5), g.cyl(100, 10, (0, 0, -1))), ""),
        ("block", g.box(0, 0, 0, 40, 20, 10), ""),
    ]
    return out


CASES = _cases()


@pytest.mark.parametrize("quality", ["draft", "normal", "fine"])
def test_shapes_at_every_quality(quality):
    wrong = []
    for name, shape, want in CASES:
        for standard in (False, True):
            p, t = _mesh(shape, quality, standard)
            for pts in (p, p @ _turn().T + 0.3):
                got = H.hint(pts, t)
                if got != want:
                    wrong.append((name, standard, got))
    assert not wrong


def test_nothing_for_bad_input():
    assert H.hint(np.zeros((0, 3)), np.zeros((0, 3), dtype=int)) == ""
    p, t = _mesh(md.washer(8))
    assert H.hint(p, t[:5]) == ""                                    # too few triangles
    assert H.hint(p * 100.0, t) == ""                               # 1.6 m: no small standard part
    bad = p.copy()
    bad[0, 0] = np.nan
    assert H.hint(bad, t) == ""
    assert H.hint(p, t + len(p)) == ""                              # indices out of range


def test_the_shape_counts_only_when_the_name_says_nothing():
    rules = R.default_rules()

    def group(name, shape, **kw):
        return R.classify_one(R.facts_for(name, shape=shape, **kw), rules)[0]

    assert group("Part123", "washer") == "Fasteners default"
    assert group("Onderdeel4", "hex_nut") == "Fasteners default"
    assert group("Teil1", "o_ring") == "Seals & O-rings"
    assert R.facts_for("Part123", shape="washer").fastener.kind == "washer"
    assert R.facts_for("Part123", shape="hex_nut").fastener.matched_by == "shape"
    # a known CAD material does not stop a hint (the fastener rules come first) ...
    assert group("Part123", "washer", cad_material="Steel, Mild") == "Fasteners default"
    # ... but a name, a parent assembly, a material in the name or a fastener name does
    assert group("SPACER", "washer") == "Shafts, pins & spacers"
    assert group("Part1", "washer", path="SMC MGPM32-75Z#1/Part1#1") == part_types.classify(
        "Part1", "SMC MGPM32-75Z#1/Part1#1")
    assert group("Part123 RVS", "washer") == "Stainless steel parts"
    assert group("ISO 4032 M8 A2", "washer") == "Fasteners stainless"
    assert group("Part123", "") == "Unsorted"
    assert R.shape_wanted("Part123") and not R.shape_wanted("O-RING 20X2")


def test_an_imported_step_file(tmp_path):
    """The whole way: a STEP with unnamed parts, read by the importer, the hints read from its cache."""
    root = g.Asm("ASSEMBLY")
    for name, shape in (("Part1", md.washer(10)), ("Part2", md.nut(10)), ("Part3", _torus(20, 2)),
                        ("Part4", md.hex_bolt(10, 40)), ("Part5", g.box(0, 0, 0, 30, 20, 10))):
        root.add(g.Part(name, shape))
    step = str(tmp_path / "unnamed.step")
    g.write_step(root, step)
    SR.read_step(step, str(tmp_path / "cache"), "normal", workers=0)
    info = json.load(open(tmp_path / "cache" / "tree.json"))
    z = np.load(tmp_path / "cache" / "meshes.npz")
    got = {m["name"]: H.hint(z[f"p{i}"], z[f"t{i}"]) for i, m in enumerate(info["meshes"])}
    assert got == {"Part1": "washer", "Part2": "hex_nut", "Part3": "o_ring", "Part4": "", "Part5": ""}
    rules = R.default_rules()
    groups = {n: R.classify_one(R.facts_for(n, shape=k), rules)[0] for n, k in got.items()}
    assert groups["Part1"] == groups["Part2"] == "Fasteners default"
    assert groups["Part3"] == "Seals & O-rings"
    assert fasteners.from_shape(got["Part2"]).label == "Hex nut"


def test_speed():
    p, t = _mesh(md.nut(12), "fine")
    import time
    t0 = time.perf_counter()
    for _ in range(50):
        H.hint(p, t)
    assert (time.perf_counter() - t0) / 50 < 0.02


def test_blender_part_objects():
    """``logic.facts_for_object`` reads the hint from the part's mesh – once per mesh in a sorting pass."""
    bpy = pytest.importorskip("bpy")
    from fresing_render.blender import build, logic
    obs = []
    for name, shape in (("Part7", md.washer(12)), ("Part8", md.nut(12)), ("BRACKET", md.washer(12)),
                        ("Part9", md.socket_screw(8, 20))):
        p, t = _mesh(shape)
        me = build._new_mesh(name + " mesh", p.astype(np.float32), None, t.astype(np.int32))
        ob = bpy.data.objects.new(name, me)
        ob[build.PROP_NAME] = name
        obs.append(ob)
    try:
        shapes = {}
        facts = [logic.facts_for_object(ob, shapes) for ob in obs]
        assert facts[0].fastener.kind == "washer" and facts[1].fastener.kind == "hex_nut"
        assert facts[2].fastener is None and facts[2].part_type == "Plates, blocks & brackets"
        assert facts[3].fastener is None
        assert shapes == {"Part7 mesh": "washer", "Part8 mesh": "hex_nut", "Part9 mesh": ""}   # BRACKET: not read
        assert logic.shape_of_mesh(obs[0].data) == "washer"
    finally:
        for ob in obs:
            me = ob.data
            bpy.data.objects.remove(ob)
            bpy.data.meshes.remove(me)
