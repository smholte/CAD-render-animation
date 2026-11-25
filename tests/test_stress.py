"""PC check "Stress" (task 0315): the made-up 10,000-part model's maker (small version: seconds), the comparison
with the previous Stress run, the table, the lines and where the mode can be started.

The whole Stress run (about an hour on a 4-core machine) never runs here: by hand on GitHub (.github/workflows/
stress.yml, tools/ci_stress.py) and on the owner's PC.
"""

import json
import os
import subprocess
import sys

import pytest

from fresing_render.pccheck import core
from fresing_render.pccheck.core import FAILED, OK, SKIPPED, Result, Run

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCENE = os.path.join(ROOT, "fresing_render", "pccheck", "stress_scene.py")
sys.path.insert(0, os.path.join(ROOT, "tools"))


def _run(results, mode="stress"):
    r = Run("0.2.300", mode, "2026-11-24 10:00", pc={"cpu": "Test", "cores": 4})
    r.results = results
    r.finished = True
    return r


def _res(id, status=OK, seconds=1.0, **kw):
    return Result(id, id.replace(".", " "), "0.2.233", status=status, seconds=seconds, **kw)


def _history(*runs):
    h = {"format": 1, "runs": []}
    for r in runs:
        h = core.add_to_history(h, core.run_record(r))
    return h


# ---------------------------------------------------------------------------
# the maker (small version)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def small_models(tmp_path_factory):
    pytest.importorskip("OCP")
    out = tmp_path_factory.mktemp("stress")
    infos = {}
    for rev in ("A", "B"):
        step = out / f"rev_{rev}.step"
        info = out / f"rev_{rev}.json"
        subprocess.run([sys.executable, SCENE, str(step), "--small", "--revision", rev, "--json", str(info)],
                       check=True, stdout=subprocess.DEVNULL, timeout=300)
        infos[rev] = (step, json.loads(info.read_text(encoding="utf-8")))
    return infos


def test_the_small_model_is_like_a_real_assembly(small_models):
    step, info = small_models["A"]
    assert step.stat().st_size > 1_000_000 and info["mb"] > 1
    assert 1000 <= info["placed"] <= 4000 and 150 <= info["unique"] <= 1000
    assert 0.3 <= info["fastener_share"] <= 0.6                       # about 40 % bolts, nuts and washers
    assert info["levels"] >= 5                                        # 5–7 subassembly levels
    assert info["bspline_faces"] > 50 and info["nurbs_converted"] > 5  # lofts, sweeps, converted castings
    assert info["nameless"] >= 1                                      # a few parts without a useful name
    text = step.read_bytes()
    assert b"ISO 4017 M" in text and b"ISO 4032 M" in text and b"ISO 7089" in text
    assert b"OSS-TOPSIDE-M01" in text and b"PEDESTAL CRANE PC-40:1" in text       # Inventor's occurrence names


def test_the_joint_sheet_names_the_crane_davit_and_doors(small_models):
    step, _info = small_models["A"]
    sheet = json.loads((step.parent / (step.stem + ".joints.json")).read_text(encoding="utf-8"))
    names = [j["name"] for j in sheet["joints"]]
    for end in (": Slew", ": Boom luff", ": Hoist", ": Davit slew", ": Swing"):
        assert any(n.endswith(end) for n in names), end
    by_name = {j["name"]: j for j in sheet["joints"]}
    for j in sheet["joints"]:
        assert j["parts"] and all(p.startswith("OSS-TOPSIDE-M01#1/") for p in j["parts"])
        if j.get("rides_on"):
            assert j["rides_on"] in by_name                           # the boom rides on the slew, the hook on the boom
    hoist = next(j for j in sheet["joints"] if j["name"].endswith(": Hoist"))
    assert hoist["type"] == "slide" and hoist["axis"]["direction"][2] < -0.99   # the hook goes straight down


def test_revision_b_changes_a_few_parts_and_keeps_the_names(small_models):
    _step, a = small_models["A"]
    _step, b = small_models["B"]
    assert a["placed"] == b["placed"] and a["unique"] == b["unique"]
    assert b["changed_placed"] > 0 and b["changed_placed"] < 0.05 * b["placed"]
    assert a["changed_placed"] == 0


def test_the_full_model_is_sized_for_about_ten_thousand_parts():
    """Counted without making a single shape (the full maker takes about a minute: by hand, see the report)."""
    sys.path.insert(0, os.path.dirname(SCENE))
    try:
        import stress_scene as S
    finally:
        sys.path.remove(os.path.dirname(SCENE))
    full, small = S.FULL, S.SMALL
    assert full["bays_x"] * full["bay_x"] == 36000 and full["decks"] == 3
    assert set(full) == set(small)


# ---------------------------------------------------------------------------
# compared with the previous Stress run, the table
# ---------------------------------------------------------------------------

def test_stress_compares_with_the_previous_run_and_flags_15_percent():
    h = _history(_run([_res("s.a", seconds=10)]), _run([_res("s.a", seconds=10)]), _run([_res("s.a", seconds=20)]),
                 _run([_res("s.a", seconds=10)], mode="heavy"), _run([_res("s.a", seconds=10)], mode="heavy"),
                 _run([_res("s.a", seconds=20)], mode="heavy"))
    assert core.reference_time(h, "stress", "s.a") == 20.0       # the previous Stress run only
    assert core.reference_time(h, "heavy", "s.a") == 10.0        # Heavy: the median of the last three
    run = _run([_res("s.a", seconds=23.5)])
    core.compare(run, h)
    assert "slower" in run.results[0].flags                      # +17.5 %: more than 15 %
    run = _run([_res("s.a", seconds=22.5)])
    core.compare(run, h)
    assert "slower" not in run.results[0].flags                  # +12.5 %
    run = _run([_res("s.a", seconds=23.5)], mode="heavy")
    core.compare(run, _history(_run([_res("s.a", seconds=20)], mode="heavy")))
    assert "slower" not in run.results[0].flags                  # Heavy keeps its 25 %


def test_a_line_over_its_limit_is_slow_and_the_table_says_so():
    h = _history(_run([_res("s.a", seconds=10), _res("s.b", seconds=5), _res("s.c", seconds=2)]))
    run = _run([_res("s.a", seconds=10.5, limit=60, metrics={"peak memory": (1500, "MB"), "import": (9.9, "s")}),
                _res("s.b", seconds=7.0, limit=6),
                _res("s.c", status=FAILED, seconds=1.0, limit=60, reason="it broke, badly"),
                _res("s.d", status=SKIPPED, reason="no graphics card")])
    core.compare(run, h)
    rows = {r["line"]: r for r in core.stress_rows(run)}
    assert rows["s.a"]["mark"] == "pass" and rows["s.a"]["peak memory MB"] == 1500
    assert rows["s.a"]["previous s"] == 10.0 and rows["s.a"]["change"] == "+5 %"
    assert rows["s.b"]["mark"] == "slow" and rows["s.b"]["slower than before"] == "yes"
    assert rows["s.c"]["mark"] == "failed" and rows["s.d"]["mark"] == "skipped"
    csv = core.stress_csv(run).splitlines()
    assert csv[0] == ",".join(core.TABLE_COLUMNS) and len(csv) == 5
    assert '"it broke, badly"' in csv[3]                         # a comma in a cell is quoted
    assert "s.b" in core.stress_text(run) and "slow" in core.stress_text(run)
    assert "over limit" in core.text_block(run)


# ---------------------------------------------------------------------------
# the lines and where Stress starts
# ---------------------------------------------------------------------------

def _checks():
    from fresing_render.pccheck import checks
    return checks


def test_the_stress_lines_are_registered_complete_and_only_in_stress():
    lines = [ln for ln in _checks().LINES if "stress" in ln.modes]
    ids = [ln.id for ln in lines]
    assert len(ids) >= 15 and ids[0] == "stress.model" and ids[-1] == "stress.update"    # the update changes the model
    for need in ("stress.import_draft", "stress.import_normal", "stress.lists", "stress.select", "stress.solid",
                 "stress.live", "stress.build", "stress.drag", "stress.clash", "stress.save", "stress.backup",
                 "stress.undo", "stress.render", "stress.web3d"):
        assert need in ids, need
    for ln in lines:
        assert ln.modes == ("stress",) and ln.limit > 0 and ln.expected > 0, ln.id
        assert ln.what and ln.shows and ln.not_shown, ln.id
    assert {ln.id for ln in core.lines_for(_checks().LINES, "stress", False)} == set(ids)
    for mode in ("quick", "full", "heavy", "tour"):
        assert not set(ids) & {ln.id for ln in core.lines_for(_checks().LINES, mode, False)}, mode
    from fresing_render.pccheck import stress
    assert 5 <= stress.minutes_expected() <= 30
    import ci_stress
    assert ci_stress.stress_line_count() == len(ids)


def test_stress_is_a_mode_with_a_shortcut_text():
    assert "stress" in core.MODES and core.MODE_TITLES["stress"] == "Stress"
    assert core.parse_args(["stress"])["mode"] == "stress"
    assert "10 to 20 minutes" in core.SHORTCUT_TEXT["stress"] and "Cancel" in core.SHORTCUT_TEXT["stress"]
    with open(os.path.join(ROOT, "installer", "Install-FresingRender.ps1"), encoding="ascii") as fh:
        ps = fh.read()
    assert '"PC check (stress).lnk"' in ps and core.SHORTCUT_TEXT["stress"] in ps
    with open(os.path.join(ROOT, ".github", "workflows", "stress.yml"), encoding="utf-8") as fh:
        wf = fh.read()
    assert "workflow_dispatch" in wf and "push" not in wf.split("jobs:")[0].replace("on a push", "")
    assert "tools/ci_stress.py" in wf


def test_the_memory_watch_sees_a_peak_in_between():
    from fresing_render.pccheck import stress
    if not stress.current_memory_mb():
        pytest.skip("no memory reading on this system")
    import mmap
    import time
    size = 200 * 2 ** 20
    with stress.MemoryWatch(every=0.02) as w:
        # 200 MB of fresh pages for a moment, every page touched (resident). Task 0322: not a Python bytes object – its
        # allocator may hand out memory this process already holds after earlier tests, so the peak never showed
        # (failed twice on GitHub once another test file moved the order of this job)
        blob = mmap.mmap(-1, size)
        for i in range(0, size, mmap.PAGESIZE):
            blob[i] = 1
        time.sleep(0.2)
        blob.close()
    assert w.peak >= stress.current_memory_mb() + 100
