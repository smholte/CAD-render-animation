"""The built-in cranes of the Lifting lane (task 0191) without Blender: the 12 classes' files, their invented SAMPLE
charts (``core/lifting.py`` rules + the shape rules of study 0180), the crane-use check on each class, the maker's own
kinematics against hand formulas, and that no maker's name is anywhere in them.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from fresing_render.core import lifting  # noqa: E402
from fresing_render.lifting_model import charts as K  # noqa: E402
from fresing_render.lifting_model import classes as C  # noqa: E402
from fresing_render.lifting_model import equipment as E  # noqa: E402

DATA = os.path.join(ROOT, "fresing_render", "data", "lifting")
NAMES = list(C.CLASSES)
# makers of cranes, loader cranes and their charts / software: none of these words may appear
MAKERS = ("liebherr", "tadano", "grove", "manitowoc", "terex", "demag", "sany", "xcmg", "zoomlion", "kobelco",
          "palfinger", "hiab", "fassi", "effer", "link-belt", "linkbelt", "sennebogen", "kato", "faun", "hitachi",
          "sumitomo", "mammoet", "sarens", "potain", "pm group", "copma", "cormach", "atlas", "huisman", "konecranes",
          "manitex", "broderson", "maeda", "unic", "jekko", "spierings", "ormig", "kranlyft")


def load(name):
    with open(os.path.join(DATA, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_twelve_classes_in_three_kinds():
    assert len(NAMES) == 12
    for kind, names in (("AT", ["AT-40", "AT-100", "AT-250", "AT-500"]), ("CC", ["CC-100", "CC-300", "CC-750",
                        "CC-1600"]), ("KB", ["KB-20", "KB-50", "KB-100", "KB-200"])):
        assert C.names(kind) == names


@pytest.mark.parametrize("name", NAMES)
def test_built_in_folder(name):
    """Each class: <class>.json (equal to a fresh make), <class>.step (one model per class), <class>.png."""
    folder = os.path.join(DATA, name)
    for ext in ("json", "step", "png"):
        assert os.path.isfile(os.path.join(folder, f"{name}.{ext}")), ext
    with open(os.path.join(folder, f"{name}.png"), "rb") as fh:
        assert fh.read(8) == b"\x89PNG\r\n\x1a\n"
    with open(os.path.join(folder, f"{name}.step"), encoding="utf-8", errors="replace") as fh:
        head = fh.read(4000)
    assert "ISO-10303-21" in head and f"PRODUCT('{name}','{name}'" in head


def test_files_are_up_to_date_and_small():
    import make_lifting_cranes as tool
    assert tool.check() == []
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _d, fs in os.walk(DATA) for f in fs)
    assert total < 11.5e6, f"{total / 1e6:.1f} MB: make the classes on first use instead (task 0191 brief)"


@pytest.mark.parametrize("name", NAMES)
def test_equipment_file(name):
    d = load(name)
    assert d["format"] == "fresing-lifting-equipment" and d["format_version"] == "1.0"
    assert d["class"] == name and d["name"] == name and d["kind"] == C.KINDS[C.CLASSES[name].kind]
    assert d["sample"] is True and d["source"] == "invented sample – Fresing Render"
    assert d["units"] == {"mass": "t", "length": "m"}
    assert set(d["mass"]) == set(d["cog"]) == set(d["rig"]["groups"])
    assert all(v > 0 for v in d["mass"].values())
    assert set(d) <= set(("format", "format_version", "kind", "class", "name", "units", "mass", "cog", "rig",
                          "charts", "hook_blocks", "outriggers", "tracks", "axles", "wll", "limits", "sample",
                          "derived_from", "source", "reeving")), "only the fields of the format (study 0180 section 4)"
    rig = d["rig"]
    names = {j["name"] for j in rig["joints"]}
    for j in rig["joints"]:
        for dep in ("rides_on", "follows"):
            assert j.get(dep) in (None, *names), (j["name"], dep)
    for p in rig["poses"]:
        assert set(p["values"]) <= names, p["name"]
    assert rig["start_pose"] in {p["name"] for p in rig["poses"]}
    assert rig["hook"]["joint"] == "Hoist" and rig["cables"][0]["part"] == "HOIST ROPE"
    assert ("tracks" in d) == (C.CLASSES[name].kind == "CC") == ("tracks" in rig)
    assert ("outriggers" in d) == (C.CLASSES[name].kind != "CC")
    # the centre of gravity of the whole crane lies inside its footprint (CAD pose)
    m = sum(d["mass"].values())
    x = sum(d["mass"][g] * d["cog"][g][0] for g in d["mass"]) / m
    y = sum(d["mass"][g] * d["cog"][g][1] for g in d["mass"]) / m
    if "outriggers" in d:
        o = d["outriggers"]
        assert abs(x - o["centre"][0]) < o["a"] and abs(y) < o["spreads"]["full"]
    else:
        t = d["tracks"]
        assert abs(x) < t["length"] / 2 and abs(y) < t["gauge"] / 2


@pytest.mark.parametrize("name", NAMES)
def test_charts_validate_and_are_samples(name):
    d = load(name)
    charts = [lifting.chart_from_dict(c, "t", "m") for c in d["charts"]]
    errors, warnings = lifting.validate_charts(charts)
    assert errors == [] and warnings == []
    assert len(charts) >= 8
    for c in d["charts"]:
        assert c["sample"] is True and c["includes_hook_block"] is False and c["interpolate"] is False
        assert c["wind_max"] > 0 and c["name"].startswith("SAMPLE – 360°")
        assert set(c["config"]) <= {"boom", "jib", "counterweight", "outriggers"}
        assert all(v > 0 for v in c["capacity"]) and len(c["radius"]) >= 2


def _table(c):
    return dict(zip(c["radius"], c["capacity"]))


@pytest.mark.parametrize("name", NAMES)
def test_chart_shapes(name):
    """The class number at the shortest radius; a tip-load end; more counterweight / a wider spread never holds less;
    a jib never more than the boom it sits on; a knuckle boom's capacity x outreach never above its class moment."""
    cl = C.CLASSES[name]
    charts = load(name)["charts"]
    top = max(max(c["capacity"]) for c in charts)
    if cl.kind == "KB":
        assert top == pytest.approx(cl.max_cap)
        for c in charts:
            assert max(r * x for r, x in zip(c["radius"], c["capacity"])) <= cl.moment + 1e-6
        assert max(r * x for c in charts for r, x in zip(c["radius"], c["capacity"])) >= 0.95 * cl.moment
    else:
        assert top == pytest.approx(cl.rated)
    for c in charts:
        assert c["capacity"][-1] < c["capacity"][0]
        assert c["radius"][-1] <= (c["config"]["boom"] + c["config"].get("jib", 0.0)) + 1e-6
    # better settings never hold less (same everything else)
    for key in ("counterweight", "outriggers"):
        for a in charts:
            for b in charts:
                if key not in a["config"] or a["config"][key] >= b["config"][key]:
                    continue
                if {k: v for k, v in a["config"].items() if k != key} != \
                        {k: v for k, v in b["config"].items() if k != key}:
                    continue
                ta, tb = _table(a), _table(b)
                for r, x in ta.items():
                    assert r not in tb or tb[r] >= x, (name, key, a["name"], r)
    for j in (c for c in charts if "jib" in c["config"]):
        main = next(c for c in charts if "jib" not in c["config"] and c["config"]["boom"] == j["config"]["boom"]
                    and c["config"]["counterweight"] == j["config"]["counterweight"])
        tm = _table(main)
        for r, x in _table(j).items():
            nxt = [v for rr, v in tm.items() if rr >= r]
            if nxt and r >= main["radius"][0]:
                assert x <= nxt[0], (j["name"], r)


@pytest.mark.parametrize("name", NAMES)
def test_charts_have_backward_stability(name):
    """No charted configuration lets the unloaded crane, boom steep, lean back past its reserve (review of task
    0191: the 165 t counterweight on the narrowest spread of AT-500 did). Task 0349: a mobile crane over its real
    outrigger base, with the file's centres of gravity, at every slew angle."""
    cl = C.CLASSES[name]
    if cl.kind == "KB":
        return
    d = load(name)
    for c in d["charts"]:
        cw = c["config"]["counterweight"]
        if cl.kind == "AT":
            fixed, turn0, out_x = K.mobile_masses(cl, d["cog"])
            turning = [(cw if m is None else m, u, v) for m, u, v in turn0]
            steep = (cl.mass_boom, C.layout(cl).pts["xp"] / 1000.0
                     + 0.42 * c["config"]["boom"] * math.cos(math.radians(cl.luff_max)), 0.0)
            base = ((out_x[0] + out_x[1]) / 2, abs(out_x[0] - out_x[1]) / 2, c["config"]["outriggers"] / 2)
            assert min(K.base_margins(fixed, turning + [steep], base)) >= K.BACK_RESERVE - 1e-9, c["name"]
            continue
        tr = C.crawler_track(cl)
        e = min(cl.gauge / 2000.0, tr["contact"] / 2000.0)
        base = cl.mass_lower + cl.mass_upper
        boom = cl.mass_boom * c["config"]["boom"] / (cl.boom_cad / 1000.0)
        boom_x = C.layout(cl).pts["xp"] / 1000.0 + 0.5 * c["config"]["boom"] * math.cos(math.radians(cl.luff_max))
        x = (cw * -cl.cw_x / 1000.0 + boom * boom_x) / (base + cw + boom)      # carrier / upper on the slew axis
        assert x + e >= 0.15 * e - 1e-9, (c["name"], x, e)


@pytest.mark.parametrize("name", NAMES)
def test_crane_use_on_each_class(name):
    """C1 on each class at three radii of its strongest chart: the next longer row, the use under 100 %; past the
    chart: red, outside the chart."""
    charts = [lifting.chart_from_dict(c, "t", "m") for c in load(name)["charts"]]
    cfg = max(charts, key=lambda c: (c.config.get("counterweight", 0), c.config.get("outriggers", 0),
                                     -c.config.get("boom", 0), -c.config.get("jib", 0)))
    if "jib" in cfg.config:
        cfg = max((c for c in charts if "jib" not in c.config), key=lambda c: (c.config["counterweight"],
                                                                                -c.config["boom"]))
    block = load(name)["hook_blocks"][0]["mass"]
    rs = cfg.radius
    for r in (rs[0] + 0.3, rs[len(rs) // 2] - 0.4, rs[-1] - 0.2):
        lk = lifting.lookup(cfg, r)
        load_kg = 0.5 * lk.capacity
        res = lifting.crane_use(load_kg, r, cfg, rigging=lifting.kg(0.1), hook_block=lifting.kg(block))
        assert res.details["row_radius"] >= r and res.details["capacity"] == lk.capacity
        assert 0.5 < res.use < 1.0 and res.status in (lifting.OK, lifting.AMBER)
    out = lifting.crane_use(lifting.kg(0.1), rs[-1] + 1.0, cfg)
    assert out.status == lifting.RED and "outside the chart" in out.message
    picked, why = lifting.pick_chart(charts, boom=cfg.config["boom"] - 0.5,
                                     **{k: v for k, v in cfg.config.items() if k != "boom"})
    assert picked is not None and picked.config["boom"] <= cfg.config["boom"] + 1e-9, why


def _hand_hook(name, v):
    """The hook's (radius, height) in m from the class's numbers, worked out by hand (not with ``classes.motions``)."""
    cl = C.CLASSES[name]
    L = C.layout(cl)
    p = L.pts
    if cl.kind == "AT":
        Lb = cl.L0 + (cl.sections - 1) * v.get("Telescope", 0.0)
        th = math.radians(v.get("Luff", 0.0))
        r = p["xp"] + Lb * math.cos(th)
        z = p["zp"] + Lb * math.sin(th) - p["d0"] - v.get("Hoist", 0.0)
    elif cl.kind == "CC":
        th = math.radians(cl.luff_cad + v.get("Luff", 0.0))
        r = p["xp"] + cl.boom_cad * math.cos(th)
        z = p["zp"] + cl.boom_cad * math.sin(th)
        if cl.jib_cad:
            hb = (r, z)
            jp = (hb[0] + 0.42 * cl.boom_w * math.sin(th), hb[1] - 0.42 * cl.boom_w * math.cos(th))
            tj = th + math.radians(cl.jib_angle + v.get("Jib", 0.0))
            r, z = jp[0] + cl.jib_cad * math.cos(tj), jp[1] + cl.jib_cad * math.sin(tj)
        z -= p["d0"] + v.get("Hoist", 0.0)
    else:
        a = math.radians(cl.main_cad + v.get("Main boom", 0.0))
        k = a + math.radians(cl.knuckle_cad + v.get("Knuckle", 0.0))
        lo = cl.outer_len + cl.extensions * v.get("Extension", 0.0)
        r = cl.main_len * math.cos(a) + lo * math.cos(k)
        z = p["col_top"] + cl.main_len * math.sin(a) + lo * math.sin(k) - p["d0"] - v.get("Hoist", 0.0)
    return abs(r) / 1000.0, z / 1000.0


@pytest.mark.parametrize("name", NAMES)
def test_hook_kinematics_against_hand_formulas(name):
    """The maker's kinematics (``classes.hook_radius_height``, the one the app is tested against) agree with the
    booms' trigonometry at every named pose and at a few more, within 1 mm; slew does not change radius or height."""
    L = C.layout(name)
    poses = [p["values"] for p in L.poses] + [
        {"Luff": 70.0, "Telescope": 1000.0, "Hoist": 5000.0}, {"Luff": -20.0, "Jib": -30.0, "Hoist": 1000.0},
        {"Main boom": 40.0, "Knuckle": -30.0, "Extension": 500.0, "Hoist": 800.0}]
    for v in poses:
        v = {k: x for k, x in v.items() if any(j["name"] == k for j in L.joints)}
        r, z = C.hook_radius_height(L, {**v, "Slew": 0.0})
        hr, hz = _hand_hook(name, v)
        assert r == pytest.approx(hr, abs=1e-3) and z == pytest.approx(hz, abs=1e-3), v
        r2, z2 = C.hook_radius_height(L, {**v, "Slew": 77.0})
        assert r2 == pytest.approx(r, abs=1e-6) and z2 == pytest.approx(z, abs=1e-6)


@pytest.mark.parametrize("name", NAMES)
def test_cylinders_and_sections_fit_over_their_range(name):
    L = C.layout(name)
    for cy in L.cylinders:
        f = cy["fit"]
        assert f["dmin"] - f["rod_len"] >= 1.5 * f["barrel_r"] - 1e-6        # rod clear of the barrel's end, closed
        assert f["barrel_len"] - (f["dmax"] - f["rod_len"]) >= 2.0 * f["barrel_r"] - 1e-6   # overlap at full stroke
        assert f["dmin"] - 1e-6 <= f["cad"] <= f["dmax"] + 1e-6
    if C.CLASSES[name].kind == "AT":
        s = L.pts["stroke"]
        for sec in L.pts["sections"][1:]:
            assert sec["a1"] - sec["a0"] - s >= 0.15 * (sec["a1"] - sec["a0"])


def test_no_maker_names_anywhere():
    """No crane maker's name in the built-ins, their STEP product names or the makers' code (public repository)."""
    pat = re.compile(r"\b(" + "|".join(re.escape(m) for m in MAKERS) + r")\b", re.I)
    texts = []
    for dp, _d, fs in os.walk(DATA):
        for f in fs:
            if f.endswith((".json", ".step")):
                with open(os.path.join(dp, f), encoding="utf-8", errors="replace") as fh:
                    texts.append((f, fh.read()))
    src = os.path.join(ROOT, "fresing_render", "lifting_model")
    for f in os.listdir(src):
        if f.endswith(".py"):
            with open(os.path.join(src, f), encoding="utf-8") as fh:
                texts.append((f, fh.read()))
    for f, t in texts:
        hit = pat.search(t)
        assert hit is None, f"{f}: '{hit.group(0)}'"


def test_charts_module_matches_files():
    for name in NAMES:
        assert K.charts_of(name, load(name)["cog"]) == load(name)["charts"]       # task 0349: the file's CoGs
        assert E.masses(name) == load(name)["mass"]


def test_every_built_in_reads_with_the_library():
    """Task 0190's reader: the 12 built-ins with no problem, warning or note, as SAMPLE built-ins with model and
    picture."""
    from fresing_render.core import lifting_library as LL
    items = LL.list_items(None)
    assert sorted(it.cls for it in items) == sorted(NAMES)
    for it in items:
        assert it.builtin and it.sample and it.ok, (it.cls, it.problems)
        assert it.warnings == [] and it.notes == [], (it.cls, it.warnings, it.notes)
        assert it.model.endswith(f"{it.cls}.step") and it.picture.endswith(f"{it.cls}.png")
        assert it.kind in LL.KINDS
