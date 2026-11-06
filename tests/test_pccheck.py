"""PC check (task 0032): lines, history, speed and picture flags, the text block, the report, the runner.

The real lines run on GitHub in the real Blender (tools/ci_real_app.py "pccheck" and the Windows job);
here the runner is tested with small made-up lines, so a failing line, a skipped one and a black picture
are known in advance.
"""

import os
import shutil

import numpy as np
import pytest

from fresing_render.pccheck import core
from fresing_render.pccheck.core import FAILED, OK, SKIPPED, Result, Run

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(results, mode="full", app="0.2.21", own=False, tag=""):
    r = Run(app, mode, "2026-11-05 10:00", blender="5.2.3", pc={"cpu": "Test CPU", "cores": 4, "ram_gb": 16,
                                                                "gpu": "GPU (OPTIX): Test", "driver": "1.0", "os": "Test"},
            own_model=own, model_tag=tag)
    r.results = results
    r.finished = True
    return r


def _res(id, status=OK, seconds=1.0, since="0.1.0", **kw):
    return Result(id, id.replace(".", " "), since, status=status, seconds=seconds, **kw)


def _history(*runs):
    h = {"format": 1, "runs": []}
    for r in runs:
        h = core.add_to_history(h, core.run_record(r))
    return h


# ---------------------------------------------------------------------------
# speed against the last runs
# ---------------------------------------------------------------------------

def test_slower_needs_25_percent_and_a_second():
    assert core.is_slower(13.0, 10.0)                  # +30 %, 3 s
    assert not core.is_slower(12.0, 10.0)              # +20 %
    assert not core.is_slower(1.4, 1.0)                # +40 % but only 0.4 s: jitter
    assert core.is_slower(0.5, 0.3, min_s=0.2)         # metrics in seconds use a smaller minimum
    assert not core.is_slower(5.0, None)               # nothing to compare with
    assert core.is_faster(5.0, 10.0) and not core.is_faster(9.0, 10.0)


def test_reference_is_the_median_of_the_last_runs_of_the_same_kind():
    h = _history(_run([_res("a", seconds=10)]), _run([_res("a", seconds=100)]), _run([_res("a", seconds=11)]),
                 _run([_res("a", seconds=12)]), _run([_res("a", seconds=1)], mode="quick"),
                 _run([_res("a", status=FAILED, seconds=0.1)]))
    # the failed run does not count; the quick run is another kind
    assert core.reference_time(h, "full", "a") == 12.0          # median of 12, 11, 100
    assert core.reference_time(h, "quick", "a") == 1.0
    assert core.reference_time(h, "full", "b") is None


def test_compare_flags_a_slower_line_and_a_slower_metric():
    old = _run([_res("import", seconds=10), _res("render", seconds=5, metrics={"per frame": (2.0, "s/frame")})])
    h = _history(old)
    new = _run([_res("import", seconds=14), _res("render", seconds=5, metrics={"per frame": (3.0, "s/frame")}),
                _res("broken", status=FAILED)])
    core.compare(new, h)
    by = {r.id: r for r in new.results}
    assert "slower" in by["import"].flags and by["import"].reference == 10
    assert "slower" in by["render"].flags and by["render"].metric_refs["per frame"] == 2.0
    assert by["broken"].flags == ["failed"]
    assert new.compared_with == "the run of 2026-11-05 10:00 (0.2.21)"
    assert core.change_text(14, 10) == "+40 %"


def test_own_model_runs_compare_only_with_the_same_file():
    a = _run([_res("own.import", seconds=10)], own=True, tag="aaa")
    h = _history(a)
    b = _run([_res("own.import", seconds=30)], own=True, tag="bbb")
    core.compare(b, h)
    assert b.results[0].reference is None and not b.results[0].flags
    c = _run([_res("own.import", seconds=30)], own=True, tag="aaa")
    core.compare(c, h)
    assert "slower" in c.results[0].flags


def test_history_keeps_the_last_runs_of_each_kind():
    h = {"runs": []}
    for i in range(8):
        h = core.add_to_history(h, core.run_record(_run([_res("a", seconds=i)])))
    h = core.add_to_history(h, core.run_record(_run([_res("a")], mode="quick")))
    keys = [r["key"] for r in h["runs"]]
    assert keys.count("full") == core.KEEP_RUNS_PER_KEY and keys.count("quick") == 1
    assert h["runs"][-2]["lines"]["a"]["seconds"] == 7        # the newest are kept, in order


def test_history_file_roundtrip_and_damaged_file(tmp_path):
    path = str(tmp_path / "sub" / "history.json")
    assert core.load_history(path)["runs"] == []
    h = _history(_run([_res("a")]))
    core.save_history(path, h)
    assert core.load_history(path) == h
    with open(path, "w") as fh:
        fh.write("{damaged")
    assert core.load_history(path)["runs"] == []


# ---------------------------------------------------------------------------
# new in this version
# ---------------------------------------------------------------------------

def test_new_lines_since_the_last_run_on_this_pc():
    last = _run([_res("old", since="0.2.10")], app="0.2.20")
    h = _history(last)
    now = _run([_res("old", since="0.2.10"), _res("added", since="0.2.15"), _res("fresh", since="0.2.21")])
    # "added" was in no earlier run (its line is new to the check); "fresh" came with a newer version
    assert core.new_line_ids(now, h) == {"added", "fresh"}


def test_first_run_shows_the_lines_of_this_version_as_new():
    now = _run([_res("old", since="0.2.10"), _res("fresh", since="0.2.21")], app="0.2.21")
    assert core.new_line_ids(now, {"runs": []}) == {"fresh"}


def test_versions_compare_as_numbers():
    assert core.version_tuple("0.2.10") > core.version_tuple("0.2.9")
    assert core.version_tuple("1.0") == (1, 0, 0)


# ---------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------

def _picture(model=True, bg=0.8):
    px = np.full((90, 160, 3), bg, np.float32)
    if model:
        px[30:60, 50:110] = (0.9, 0.6, 0.1)
    return px


def test_picture_problems():
    assert core.picture_problems(_picture()) == []
    assert core.picture_problems(np.zeros((90, 160, 3))) == ["the picture is black"]
    assert core.picture_problems(_picture(model=False)) == ["the picture is one flat colour (empty)"]
    speck = _picture(model=False)
    speck[0:3, 0:3] = 0.0                                   # only a few pixels differ
    speck[45, 80] = 0.0
    assert "the model is not in the picture" in core.picture_problems(speck)[0]
    # surroundings fill the picture: no model check there
    noisy = np.random.default_rng(1).random((90, 160, 3)).astype(np.float32)
    assert core.picture_problems(noisy, model_check=False) == []


def test_picture_difference_and_thumbnail():
    a = core.thumbnail(_picture())
    assert a.shape == (90, 160, 3)                          # never bigger than the picture
    assert core.thumbnail(np.zeros((540, 960, 3))).shape == (135, 240, 3)
    assert core.picture_difference(a, a) == 0.0
    b = core.thumbnail(_picture(bg=0.2))
    assert core.picture_difference(a, b) > core.PICTURE_DIFF
    assert core.picture_difference(a, core.thumbnail(_picture(), width=100)) is None     # other size
    assert core.picture_difference(a, None) is None
    # box average: a 2 x 2 checkerboard of 0 and 1 becomes 0.5
    cb = np.indices((4, 4)).sum(axis=0) % 2
    assert np.allclose(core.thumbnail(cb[..., None].repeat(3, -1).astype(float), width=2), 0.5)


# ---------------------------------------------------------------------------
# the text block: numbers only
# ---------------------------------------------------------------------------

SECRET_FILE = r"C:\Users\Sebastian\Klanten\Geheim BV\SKID-4711 rev C.step"
SECRET_PARTS = ["SKID-4711.ASM", "Hoofdframe klant X", "PUMP_GEHEIM_22"]


def test_text_block_holds_no_file_or_part_names():
    own = _res("own.import", status=OK, seconds=40, own=True,
               metrics={"import": (38.0, "s"), "parts": (2789, ""), "sorted": (67.0, "%")},
               note="SKID-4711.ASM imported from " + SECRET_FILE)
    own_fail = _res("own.gpu", status=FAILED, own=True, error_type="RuntimeError",
                    reason=f"Part 'PUMP_GEHEIM_22' of {SECRET_FILE} has no faces")
    test_fail = _res("render.gpu", status=FAILED, reason=f"could not write {SECRET_FILE} for Hoofdframe klant X")
    run = _run([_res("import.crane", seconds=2.5, metrics={"import": (2.4, "s")}), own, own_fail, test_fail],
               own=True, tag="abc")
    secrets = SECRET_PARTS + [os.path.basename(SECRET_FILE), "SKID-4711 rev C", "Sebastian", "DESKTOP-FRESING"]
    block = core.text_block(run, secrets)
    for word in SECRET_PARTS + ["SKID-4711", "Geheim", "Klanten", "Sebastian", ".step", "C:\\"]:
        assert word.lower() not in block.lower(), word
    assert "own.import 40.0 s" in block and "parts 2789" in block and "sorted 67.0 %" in block
    assert "[FAIL] own.gpu" in block and "RuntimeError" in block
    assert "[FAIL] render.gpu" in block and "<path>" in block
    assert "Test CPU, 4 cores, 16 GB" in block and "GPU (OPTIX): Test; driver 1.0" in block


def test_scrub_removes_paths_and_names():
    assert core.scrub("open /home/user/x y.step failed", ()) == "open <path> failed"
    assert core.scrub(r"see \\SERVER\share\file now", ()) == "see <path> now"
    assert core.scrub(r"C:\Users\x\Klant BV\SKID 4711 rev C.step has no faces", ()) == "<path> has no faces"
    assert core.scrub("a/b and 50/50 stay", ()) == "a/b and 50/50 stay"
    assert core.scrub("Part FRAME-77 broke", ["frame-77"]) == "Part <name> broke"
    assert len(core.scrub("x" * 500, ())) == 160


def test_new_lines_come_first_in_the_text_block():
    run = _run([_res("old"), _res("fresh", since="0.2.21")])
    run.new_ids = {"fresh"}
    rows = core.text_block(run).splitlines()[3:]
    assert rows[0].startswith("NEW [ OK ] fresh") and rows[1].startswith("[ OK ] old")


# ---------------------------------------------------------------------------
# the HTML report
# ---------------------------------------------------------------------------

def test_html_report_has_new_lines_on_top_pictures_and_copy_button():
    from fresing_render.pccheck.core import Picture
    pic = Picture("p", "Crane <HD>", thumb_png=b"\x89PNG fake", difference=0.2, flagged=True)
    run = _run([_res("old", status=FAILED, reason="it <broke>"), _res("fresh", since="0.2.21", pictures=[pic])])
    run.new_ids = {"fresh"}
    page = core.html_report(run, core.text_block(run))
    assert page.index("New in this version") < page.index("Look at these") < page.index("Every function")
    assert "it &lt;broke&gt;" in page and "<broke>" not in page
    assert "data:image/png;base64," in page and "differs from last time" in page
    assert "copyBlock()" in page and "<textarea id='block' readonly>" in page
    assert "1 of 2 functions FAILED" in page
    running = _run([_res("a")])
    running.finished = False
    assert "Still running" in core.html_report(running, "")


def test_arguments_from_the_shortcut(tmp_path):
    model = tmp_path / "my model.STEP"
    model.write_text("x")
    a = core.parse_args([str(tmp_path), "full", str(model)])
    assert a == {"desktop": str(tmp_path), "mode": "full", "model": str(model)}
    # a file dropped on the shortcut comes last; the order does not matter
    assert core.parse_args([str(model), "QUICK", str(tmp_path)])["model"] == str(model)
    assert core.parse_args([])["mode"] == "quick"
    assert core.parse_args([str(tmp_path / "missing.step")])["model"] == ""


# ---------------------------------------------------------------------------
# the lines themselves
# ---------------------------------------------------------------------------

def test_every_line_is_complete():
    from fresing_render import __version__
    from fresing_render.pccheck import checks
    ids = [ln.id for ln in checks.LINES]
    assert len(ids) == len(set(ids)), "line ids must be unique"
    for ln in checks.LINES:
        assert ln.title and ln.what, ln.id
        assert set(ln.modes) <= {"quick", "full", "own"} and ln.modes, ln.id
        assert core.version_tuple(ln.since) <= core.version_tuple(__version__), (ln.id, "since a later version")
        for r in ln.requires:
            assert r in ids and ids.index(r) < ids.index(ln.id), (ln.id, r)
    quick = {ln.id for ln in core.lines_for(checks.LINES, "quick", False)}
    assert {"import.crane", "joints.rotate", "render.gpu", "queue.eevee"} <= quick
    full = {ln.id for ln in core.lines_for(checks.LINES, "full", False)}
    assert len(full) >= 25 and quick <= full
    own = {ln.id for ln in core.lines_for(checks.LINES, "quick", True)} - quick
    assert own == {"own.import", "own.gpu", "own.time_preview", "own.time_eevee"}


def test_test_models_in_the_extension_are_the_test_data():
    for name in ("test_machine.step", "test_materials.step", "test_crane_a.step", "test_crane_b.step",
                 "test_faces_a.step", "test_mill.step", "test_decals_a.step"):
        a = os.path.join(ROOT, "fresing_render", "data", name)
        b = os.path.join(ROOT, "tests", "data", name)
        with open(a, "rb") as fa, open(b, "rb") as fb:
            assert fa.read() == fb.read(), f"{name}: copy tests/data/{name} to fresing_render/data/"


# ---------------------------------------------------------------------------
# in Blender: the runner with made-up lines, the Help entry
# ---------------------------------------------------------------------------

@pytest.fixture()
def blender(tmp_path, monkeypatch):
    bpy = pytest.importorskip("bpy")
    import addon_utils
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    monkeypatch.setenv("FRESING_PCCHECK_DIR", str(tmp_path / "hist"))
    monkeypatch.setenv("FRESING_SELFTEST_NO_GPU", "1")
    yield bpy
    fresing_render.unregister()


def _png(bpy, path, px):
    from fresing_render.pccheck import runner
    runner.write_png(str(path), np.asarray(px, np.float32))
    return str(path)


def test_runner_reports_failures_skips_and_pictures(blender, tmp_path):
    from fresing_render.pccheck import runner
    from fresing_render.pccheck.core import Line
    seen = []

    def good(ctx):
        ctx.metric("thing", 1.5, "s")
        ctx.picture(_png(blender, tmp_path / "good.png", _picture()), "good", "A good picture")
        seen.append("good")
        return "fine"

    def broken(ctx):
        raise ValueError("it broke")

    def needs(ctx):
        seen.append("needs")              # never runs: the line it needs failed

    def black(ctx):
        ctx.picture(_png(blender, tmp_path / "black.png", np.zeros((90, 160, 3))), "black", "Black")

    def gpu(ctx):
        ctx.need_gpu()

    lines = [Line("t.good", "Good", "0.1.0", ("quick",), good, what="x"),
             Line("t.broken", "Broken", "0.1.0", ("quick",), broken, what="x"),
             Line("t.needs", "Needs", "0.1.0", ("quick",), needs, ("t.broken",), what="x"),
             Line("t.black", "Black", "0.1.0", ("quick",), black, what="x"),
             Line("t.gpu", "GPU", "0.1.0", ("quick",), gpu, what="x"),
             Line("t.full", "Only full", "0.1.0", ("full",), needs, what="x")]
    desk = tmp_path / "Desktop é"
    desk.mkdir()
    run = runner.run("quick", str(desk), open_report=False, lines=lines)
    by = {r.id: r for r in run.results}
    assert [r.id for r in run.results] == ["t.good", "t.broken", "t.needs", "t.black", "t.gpu"]
    assert by["t.good"].status == OK and by["t.good"].note == "fine" and by["t.good"].metrics["thing"] == (1.5, "s")
    assert by["t.broken"].status == FAILED and by["t.broken"].reason == "it broke" and "ValueError" in by["t.broken"].trace
    assert by["t.needs"].status == SKIPPED and "needs Broken" in by["t.needs"].reason
    assert by["t.black"].status == FAILED and "black" in by["t.black"].reason
    assert by["t.gpu"].status == SKIPPED and by["t.gpu"].reason == "no graphics card"
    assert seen == ["good"]
    page = (desk / runner.REPORT_NAME).read_text(encoding="utf-8")
    assert "2 of 5 functions FAILED" in page and "data:image/png;base64," in page
    hist = tmp_path / "hist"
    assert (hist / "history.json").is_file() and (hist / "pictures" / "quick" / "good.png").is_file()
    assert not (hist / "running.json").exists()
    # second run: the good picture is compared with the first one, the times too
    run2 = runner.run("quick", str(desk), open_report=False, lines=lines)
    good2 = run2.results[0]
    assert good2.pictures[0].difference == pytest.approx(0.0, abs=0.01) and not good2.pictures[0].flagged
    assert good2.reference is not None and run2.compared_with


def test_help_menu_entry_and_command_line(blender):
    from fresing_render.pccheck import ops
    funcs = blender.types.TOPBAR_MT_help._dyn_ui_initialize()
    from fresing_render.blender import updates
    assert funcs.index(updates._draw_help) + 1 == funcs.index(ops._draw_pc_check_help), "right under the update check"
    assert blender.ops.fresing.pc_check.get_rna_type().description.startswith("Test every main function")
    cmd = ops.launch_command("C:/B/blender.exe", "D:/Desk top", "full", "E:/m.step")
    assert cmd == ["C:/B/blender.exe", "--background", "--python", ops.LAUNCHER, "--", "D:/Desk top", "full", "E:/m.step"]
    assert ops.shortcut_arguments(r"C:\Users\O'Brien\Desktop", "quick") == \
        f'--background --python "{ops.LAUNCHER}" -- "C:\\Users\\O\'Brien\\Desktop" quick'


def test_shortcut_script_quotes_apostrophes():
    pytest.importorskip("bpy")
    from fresing_render.pccheck import ops
    script = ops.shortcut_script(r"C:\Start\Fresing Render", r"C:\Users\O'Brien\blender.exe",
                                 r"C:\Users\O'Brien\Desktop", ["quick", "full"])
    assert "O''Brien" in script and "O'Brien" not in script.replace("O''Brien", "")
    assert script.count("$l.Save()") == 2 and "PC check (full).lnk" in script
    # PowerShell ends a quoted string at typographic quotes too (a user name like O’Brien)
    assert ops._ps_quote("C:\\Users\\O\u2019Brien") == "'C:\\Users\\O\u2019\u2019Brien'"
    desk = ops.shortcut_script("S", "b.exe", r"C:\D", ["desktop"])
    assert ops.DESKTOP_SHORTCUT in desk and '" quick' in desk


def test_shortcuts_only_where_missing(tmp_path):
    pytest.importorskip("bpy")
    from fresing_render.pccheck import ops
    assert ops.missing_shortcuts(str(tmp_path)) == ["quick", "full"]
    (tmp_path / ops.SHORTCUTS["quick"]).write_text("x")
    assert ops.missing_shortcuts(str(tmp_path)) == ["full"]
    desk = tmp_path / "desk"
    desk.mkdir()
    assert ops.missing_shortcuts(str(tmp_path), str(desk)) == ["full"]       # no app shortcut there: leave it
    (desk / "Fresing Render.lnk").write_text("x")
    assert ops.missing_shortcuts(str(tmp_path), str(desk)) == ["full", "desktop"]


def test_running_check_is_detected(tmp_path):
    pytest.importorskip("bpy")
    import json
    import subprocess
    import sys
    from fresing_render.pccheck import ops
    assert ops.running_pid(str(tmp_path)) == 0
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        (tmp_path / ops.RUNNING_FILE).write_text(json.dumps({"pid": p.pid}))
        assert ops.running_pid(str(tmp_path)) == p.pid
    finally:
        p.kill()
        p.wait()
    assert ops.running_pid(str(tmp_path)) == 0
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_github_verdict_reads_the_text_block():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ci_check_pccheck as chk
    good = _run([_res("a"), _res("render.gpu", status=SKIPPED, reason="no graphics card")])
    rows, problems = chk.judge(core.text_block(good), min_lines=2)
    assert [r[0] for r in rows] == ["OK", "skipped"] and problems == []
    bad = _run([_res("a", status=FAILED, reason="it broke"), _res("b", status=SKIPPED, reason="needs a to work first"),
                _res("render.gpu", status=SKIPPED, reason="no graphics card")])
    bad.finished = False
    rows, problems = chk.judge(core.text_block(bad), min_lines=5)
    assert any("did not finish" in p for p in problems) and any(p.startswith("a: it broke") for p in problems)
    assert any("b skipped" in p for p in problems) and any("at least 5" in p for p in problems)
    assert chk.judge("")[1] and chk.MIN_LINES_FULL <= len(core.lines_for(__import__(
        "fresing_render.pccheck.checks", fromlist=["LINES"]).LINES, "full", False))
