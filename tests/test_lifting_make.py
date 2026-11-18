"""Task 0204 (Lifting L4c): "Make a crane…" without Blender – the numbers with their limits and rules
(``lifting_model/params.py``), the maker run on a crane's numbers (``make.make_crane``), the background job
(``lifting_model/job.py``: progress, Cancel, into the library through L2) and the picture.

- every class's own numbers through ``params`` give the very dataclass, the same equipment file (joints, poses, hook,
  masses, charts) and – made with OpenCascade – the same parts in the same places as the shipped STEP;
- one test per rule: a broken number is refused with that rule named, in plain words;
- random valid sets per kind are made by the OpenCascade makers without a failure;
- Cancel leaves nothing behind; a name already in the library is refused unless Replace;
- the made item is SAMPLE (``derived_from`` its own chart hash) until a real chart is entered.
"""

from __future__ import annotations

import json
import os
import random
import time

import numpy as np
import pytest

from fresing_render.core import lifting_library as LL
from fresing_render.lifting_model import classes as C
from fresing_render.lifting_model import equipment as E
from fresing_render.lifting_model import params as P

BUILTIN = LL.BUILTIN_DIR


def shipped(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_class_numbers_give_the_class(name):
    c = C.CLASSES[name]
    v = P.of_class(name)
    assert P.validate(c.kind, v) == []
    assert P.to_class(c.kind, v, name) == c
    d = shipped(name)
    fresh = E.data(P.to_class(c.kind, v, name), d["cog"])
    assert fresh == d                                    # joints, poses, hook, masses, charts, limits, footprint


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_dialog_numbers_round_trip_in_float32(name):
    """The dialog keeps numbers as 32-bit floats in m / t / degrees: read back they give the class exactly."""
    c = C.CLASSES[name]
    v = P.of_class(name)
    back = {}
    for f in P.FIELDS[c.kind]:
        ui = f.to_ui(v[f.key])
        back[f.key] = f.from_ui(ui if f.is_list or f.integer else np.float32(ui))
    assert back == v


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_class_masses_from_their_own_rule(name):
    c = C.CLASSES[name]
    v = P.of_class(name)
    got = P.suggest_masses(c.kind, v, name)
    for k, x in got.items():
        assert x == pytest.approx(v[k], abs=1e-3), k


def test_fields_have_labels_units_limits_and_folds():
    for kind, fields in P.FIELDS.items():
        keys = [f.key for f in fields]
        assert len(keys) == len(set(keys))
        for f in fields:
            assert f.label and f.fold in P.FOLDS[kind] and f.lo < f.hi
        for k in P.MASS_KEYS[kind]:
            assert k in keys


# ---------------------------------------------------------------------------------------------------------------------
# one test per rule

def _with(name, **change):
    v = P.of_class(name)
    v.update(change)
    return C.CLASSES[name].kind, v


RULES = {
    # rule: (class, changes)
    "range:L0": ("AT-100", {"L0": 1000.0}),
    "range:sections": ("AT-100", {"sections": 2.5}),
    "range:boom_lengths": ("CC-100", {"boom_lengths": (2.0, 36.0)}),
    "missing:wall": ("AT-100", {"wall": None}),
    "boom_lengths": ("AT-500", {"Lmax": 15000.0}),
    "sections_nest": ("AT-40", {"sections": 9, "wall": 40.0, "gap": 80.0}),
    "boom_fits": ("AT-40", {"boom_w": 2400.0}),
    "spreads": ("AT-100", {"spread_middle": 7700.0}),
    "spreads_out": ("AT-40", {"spread_narrow": 2450.0}),
    "counterweights": ("AT-100", {"cw_2": 30.0}),
    "falls": ("AT-100", {"hook_falls": 7}),
    "sections_overlap": ("AT-40", {"Lmax": 60000.0}),
    "axles_fit": ("AT-40", {"axles": 9}),
    "winch_fit": ("AT-100", {"cw_x": 2500.0}),
    "stable": ("AT-40", {"cw_1": 250.0, "cw_2": 280.0, "cw_3": 300.0, "cw_x": 9000.0, "mass_carrier": 5.0,
                         "mass_upper": 1.0}),      # tips backwards unloaded in every configuration
    "boom_list": ("CC-100", {"boom_lengths": (24.0, 18.0, 36.0)}),
    "model_boom": ("CC-100", {"boom_cad": 40000.0}),
    "luff_order": ("CC-100", {"luff_min": 65.0}),
    "jib": ("CC-750", {"jib_lengths": (30.0, 54.0)}),
    "teeth": ("CC-100", {"teeth": 13}),
    "tracks_tail": ("CC-100", {"run_links": 20}),
    "gauge": ("CC-100", {"gauge": 2000.0, "shoe_w": 1200.0}),
    "main_order": ("KB-50", {"main_min": 25.0}),
    "knuckle_order": ("KB-50", {"knuckle_cad": -10.0, "knuckle_max": -15.0}),
    "ext_stroke": ("KB-50", {"ext_stroke": 3000.0}),
    "ext_nest": ("KB-20", {"extensions": 9}),
    "tip_sheave": ("KB-100", {"boom_h": 400.0}),
    "max_cap": ("KB-50", {"max_cap": 30.0}),
    "cylinder_fit": ("KB-20", {"main_min": -30.0, "main_max": 85.0}),
}


@pytest.mark.parametrize("rule", list(RULES))
def test_each_rule_refuses_with_its_name(rule):
    name, change = RULES[rule]
    kind, v = _with(name, **change)
    probs = P.validate(kind, v)
    assert probs, rule
    assert rule in [p.rule for p in probs], [(p.rule, p.text) for p in probs]
    text = next(p.text for p in probs if p.rule == rule)
    assert text.endswith((".", ")")) and "Traceback" not in text and len(text) > 15
    assert P.fits_text(probs) != "Fits."


def test_every_rule_of_params_has_a_test():
    """Every rule name ``params`` can give has a broken case above (ranges / missing by one example each)."""
    import re
    src = open(P.__file__, encoding="utf-8").read()
    named = set(re.findall(r'Problem\("([a-z_]+)"', src)) | {r for _k, r, _t in P._GEOMETRY}
    named -= {"kind", "error", "charts", "geometry", "carrier_length"}     # safety nets: never reached by valid ranges
    assert named <= set(RULES), sorted(named - set(RULES))


def test_jib_rules():
    kind, v = _with("CC-750", jib_cad=40000.0)
    assert "jib" in [p.rule for p in P.validate(kind, v)]                  # not one of the chart lengths
    kind, v = _with("CC-750", mass_jib=0.0)
    assert "jib" in [p.rule for p in P.validate(kind, v)]
    kind, v = _with("CC-100", jib_cad=0.0, jib_lengths=(12.0,))              # no jib: its lengths are not used
    assert P.validate(kind, v) == []


def test_list_typed_as_text():
    assert P.parse_list("18, 24, 30") == (18.0, 24.0, 30.0)
    assert P.parse_list("18 24  30") == (18.0, 24.0, 30.0)
    assert P.parse_list("18,5; 24") == (18.5, 24.0)
    with pytest.raises(ValueError, match="'x'"):
        P.parse_list("18, x")
    kind, v = _with("CC-100", boom_lengths="18, 24, 30, 36")
    assert P.validate(kind, v) == []
    kind, v = _with("CC-100", boom_lengths="18, abc")
    assert [p.rule for p in P.validate(kind, v)] == ["range:boom_lengths"]


@pytest.mark.parametrize("kind", P.KINDS)
def test_random_sets_are_valid_and_differ(kind):
    rng = random.Random(4)
    sets = [P.random_values(kind, rng) for _ in range(20)]
    assert all(P.validate(kind, v) == [] for v in sets)
    assert len({json.dumps(v, sort_keys=True, default=list) for v in sets}) == 20


def test_class_word_and_nearest():
    v = P.of_class("AT-250")
    v["rated"] = 220.0
    assert P.class_word("AT", v) == "AT-220" and P.nearest_class("AT", v) == "AT-250"
    assert P.class_word("KB", P.of_class("KB-50")) == "KB-50"


# ---------------------------------------------------------------------------------------------------------------------
# the maker (OpenCascade)

def _ocp():
    pytest.importorskip("OCP")
    from fresing_render.lifting_model import make as M
    return M


def _step_parts(path):
    """(name, rounded position) of every placed part of a STEP, read with the app's reader's tools: counts and places,
    as CLAUDE.md says (the writer is not byte-stable)."""
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_DocumentTool
    from OCP.TopLoc import TopLoc_Location
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    assert r.ReadFile(path) == IFSelect_RetDone
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    out = []

    def name(lab):
        n = TDataStd_Name()
        return n.Get().ToExtString() if lab.FindAttribute(TDataStd_Name.GetID_s(), n) else ""

    def walk(lab, loc):
        if st.IsAssembly_s(lab):
            kids = TDF_LabelSequence()
            st.GetComponents_s(lab, kids, False)
            for i in range(1, kids.Length() + 1):
                comp = kids.Value(i)
                ref = st.GetShape_s(comp).Location()
                from OCP.TDF import TDF_Label
                tgt = TDF_Label()
                st.GetReferredShape_s(comp, tgt)
                walk(tgt, loc.Multiplied(ref))
        else:
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib
            b = Bnd_Box()
            BRepBndLib.Add_s(st.GetShape_s(lab).Moved(loc), b)
            lo, hi = b.CornerMin(), b.CornerMax()
            out.append((name(lab),) + tuple(round(v) for v in (lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z())))
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location())
    return sorted(out)


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_made_from_class_numbers_matches_the_shipped_class(name, tmp_path):
    M = _ocp()
    kind = C.CLASSES[name].kind
    spec = {"kind": kind, "name": name, "start": name, "values": P.of_class(name)}
    M.make_crane(spec, str(tmp_path), picture=False)
    made = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    d = shipped(name)
    for key in ("mass", "rig", "charts", "hook_blocks", "limits", "units", "kind", "class", "name"):
        assert made[key] == d[key], key
    for g, xyz in d["cog"].items():
        assert made["cog"][g] == pytest.approx(xyz, abs=0.002), g
    assert made["sample"] is True and made["derived_from"] == LL.chart_hash(made)
    assert made["made_from"]["class"] == name
    assert _step_parts(str(tmp_path / f"{name}.step")) == _step_parts(os.path.join(BUILTIN, name, f"{name}.step"))


@pytest.mark.parametrize("kind", P.KINDS)
def test_random_sets_are_made(kind, tmp_path):
    """The OpenCascade makers on random valid numbers: every set made, one solid per part, a readable item."""
    M = _ocp()
    rng = random.Random({"AT": 21, "CC": 22, "KB": 23}[kind])
    for i in range(8):
        v = P.random_values(kind, rng)
        out = tmp_path / f"r{i}"
        info = M.make_crane({"kind": kind, "name": f"Random {i}", "start": P.nearest_class(kind, v), "values": v},
                            str(out), picture=(i == 0))
        it = LL.read_item(str(out))
        assert it.ok, it.problems
        assert it.sample and it.model and info["parts"] > 40
        assert LL.charts_of(it)


def test_refused_numbers_write_nothing(tmp_path):
    M = _ocp()
    kind, v = _with("AT-100", hook_falls=7)
    with pytest.raises(ValueError, match="even"):
        M.make_crane({"kind": kind, "name": "Odd", "start": "AT-100", "values": v}, str(tmp_path / "x"))
    assert not (tmp_path / "x").exists()


def test_picture_is_a_png(tmp_path):
    M = _ocp()
    from fresing_render.lifting_model import picture as PI
    root, _L = M.model("KB-20")
    t0 = time.time()
    p = PI.picture(root, str(tmp_path / "kb.png"))
    took = time.time() - t0
    raw = open(p, "rb").read()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n" and b"IHDR" in raw[:20] and b"gAMA" not in raw and b"sRGB" not in raw
    assert took < 10.0
    rgb = PI.render(*PI.triangles(root))
    bg = (np.array(PI.BACKGROUND) * 255 + 0.5).astype(np.uint8)
    drawn = np.any(rgb != bg, axis=2).mean()
    assert 0.05 < drawn < 0.8                                    # the crane fills a fair share of the picture


# ---------------------------------------------------------------------------------------------------------------------
# the job

def _job(tmp_path, name="My crane", cls="KB-20", replace=False):
    _ocp()
    from fresing_render.lifting_model import job as J
    lib = tmp_path / "lib"
    lib.mkdir(exist_ok=True)
    spec = {"kind": C.CLASSES[cls].kind, "name": name, "start": cls, "values": P.of_class(cls)}
    return J, J.MakeJob(spec, str(lib), replace=replace), lib


def test_job_makes_into_the_library(tmp_path):
    J, job, lib = _job(tmp_path)
    job.start()
    seen = set()
    t0 = time.time()
    while not job.poll():
        seen.add(job.stage)
        assert time.time() - t0 < 120
        time.sleep(0.05)
    assert job.error == "", job.error
    assert os.listdir(lib) == ["My crane"]
    files = sorted(os.listdir(lib / "My crane"))
    assert files == ["My crane.json", "My crane.png", "My crane.step"]
    it = LL.read_item(str(lib / "My crane"))
    assert it.ok and it.sample and not it.builtin and it.picture and it.model
    assert it.data["class"] == "KB-20" and it.data["made_from"]["class"] == "KB-20"
    assert not os.path.exists(job.tmp)
    # the same name again: refused unless Replace
    J2, again, _ = _job(tmp_path)
    with pytest.raises(J.MakeError, match="already in your library"):
        again.start()
    _J3, rep, _ = _job(tmp_path, replace=True)
    rep.start()
    rep.wait()
    assert rep.error == "" and sorted(os.listdir(lib / "My crane")) == files


def test_cancel_leaves_nothing(tmp_path):
    J, job, lib = _job(tmp_path, cls="CC-1600")
    job.start()
    time.sleep(0.3)
    tmp = job.tmp
    job.cancel()
    assert job.done and job.error == "cancelled"
    assert not os.path.exists(tmp)
    assert os.listdir(lib) == []
    assert job.proc.poll() is not None


def test_job_refuses_bad_numbers_and_names(tmp_path):
    J, job, lib = _job(tmp_path, name="")
    with pytest.raises(J.MakeError, match="name"):
        job.start()
    J, job, lib = _job(tmp_path, name="Bad")
    job.spec["values"]["hook_mass"] = -1.0
    with pytest.raises(J.MakeError, match="Hook block mass"):
        job.start()
    assert os.listdir(lib) == []


def test_sample_mark_comes_off_only_with_a_real_chart(tmp_path):
    J, job, lib = _job(tmp_path)
    job.start()
    job.wait()
    it = LL.read_item(str(lib / "My crane"))
    data = dict(it.data)
    data["sample"] = False
    with pytest.raises(LL.LibraryError):                         # the sample's charts with the mark taken off
        LL.write_item(data, str(lib))
    csv = tmp_path / "chart.csv"
    csv.write_text("boom 10.5 m\nradius,capacity\n3,7.5\n5,4.2\n8,2.3\n", encoding="utf-8")
    entry = LL.read_chart_csv(str(csv), "t", "m")
    assert entry.ok, entry.errors
    data = LL.set_charts(dict(it.data), entry)
    LL.clear_sample(data)
    LL.write_item(data, str(lib))
    back = LL.read_item(str(lib / "My crane"))
    assert back.ok and not back.sample
