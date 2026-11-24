"""The render kit's start window and run control (task 0144): the choices and the standard kept outside the kit, quiet
hours, the expected wall time, the pauses between frames and the temperature guard (a fake renderer and a fake clock),
Pause / Stop, the run's state and continuing a stopped run, the start window's script (parsed with pwsh where it is
installed, as on GitHub's Linux runners; the Windows job parses it with Windows PowerShell 5.1)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(KIT, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def kr():
    return _load("kit_run_0144", "kit_run.py")


@pytest.fixture
def kit():
    return _load("kit_0144", "make_site_pictures.py")


def _at(h, m=0, day=15):
    return time.mktime((2026, 11, day, h, m, 0, 0, 0, -1))


class FakeTime:
    """A clock that only moves when something sleeps or renders."""

    def __init__(self, t0):
        self.t = t0
        self.slept = 0.0

    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s
        self.slept += s

    def render(self, s):
        self.t += s


# ---------------------------------------------------------------------------
# choices
# ---------------------------------------------------------------------------

def test_choices_cleaned_and_standard_outside_the_kit(kr, tmp_path, monkeypatch):
    monkeypatch.delenv("FRESING_KIT_STANDARD", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert kr.standard_path() == str(tmp_path / "Local" / "Fresing Render" / "site_kit.json")
    assert not kr.standard_path().startswith(KIT)
    assert kr.load_standard() == kr.DEFAULT_STANDARD               # nothing saved yet
    c = kr.clean({"load": 20, "max_temp": 90, "quiet_on": "false", "quiet_start": "25:00", "quiet_end": "7:5",
                  "quiet_load": "70", "when_done": "Shut down", "models": ["thor"]})
    assert c["load"] == 40 and c["max_temp"] == 85 and c["quiet_on"] is False
    assert c["quiet_start"] == "22:00" and c["quiet_end"] == "07:05" and c["quiet_load"] == 70
    assert c["when_done"] == "shutdown" and c["models"] == ["thor"]
    assert kr.clean({"max_temp": 0})["max_temp"] == 0 and kr.clean({"when_done": "dance"})["when_done"] == "nothing"
    path = kr.save_standard({"load": 70, "quiet_on": True, "when_done": "sleep", "models": ["x"]})
    saved = json.loads(open(path, encoding="utf-8").read())
    assert saved["load"] == 70 and saved["quiet_on"] is True and "models" not in saved
    assert kr.load_standard()["when_done"] == "sleep"
    # PowerShell writes UTF-8 with a BOM when told to: still read
    with open(path, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + json.dumps({"load": 55}).encode())
    assert kr.load_standard()["load"] == 55
    assert kr.load_choices("")["load"] == 55                      # the console fallback uses the standard
    assert kr.load_choices(str(tmp_path / "missing.json"))["load"] == 55


def test_quiet_hours_over_midnight(kr):
    c = kr.clean({"load": 100, "max_temp": 0, "quiet_on": True, "quiet_start": "22:00", "quiet_end": "07:00",
                  "quiet_load": 60, "quiet_max_temp": 70})
    assert kr.limits_at(c, _at(21, 59)) == (100, 0)
    assert kr.limits_at(c, _at(22, 0)) == (60, 70)
    assert kr.limits_at(c, _at(3)) == (60, 70)
    assert kr.limits_at(c, _at(7, 0)) == (100, 0)
    day = kr.clean(dict(c, quiet_start="12:00", quiet_end="13:30"))
    assert kr.limits_at(day, _at(12, 45)) == (60, 70) and kr.limits_at(day, _at(23)) == (100, 0)
    assert kr.limits_at(kr.clean(dict(c, quiet_on=False)), _at(3)) == (100, 0)


def test_expected_wall_time(kr):
    full = kr.clean({})
    assert kr.wall_seconds(3600, 600, _at(12), full) == pytest.approx(4200)
    at70 = kr.clean({"load": 70})
    assert kr.wall_seconds(3600, 600, _at(12), at70) == pytest.approx(3600 * 100 / 70 + 600, rel=1e-3)
    # 4 h of graphics-card work from 20:00, quiet 22:00–07:00 at 50 %: 2 h at full load, then 2 h of work at half speed
    quiet = kr.clean({"quiet_on": True, "quiet_load": 50})
    assert kr.wall_seconds(4 * 3600, 0, _at(20), quiet) == pytest.approx(6 * 3600, abs=1)
    # started in the quiet hours, it gets faster at 07:00
    assert kr.wall_seconds(4 * 3600, 0, _at(5), quiet) == pytest.approx(5 * 3600, abs=1)
    assert kr.wall_seconds(0, 0, _at(5), quiet) == 0


def test_pauses_follow_the_load_with_a_fake_renderer(kr):
    """Frames of a fake renderer: at 70 % the card renders 70 % of the wall time; the wall time is what the expected
    time said; the pauses switch to the quiet hours' load when the clock passes 22:00."""
    ft = FakeTime(_at(12))
    p = kr.Pacer({"load": 70}, clock=ft.clock, sleep=ft.sleep, gpu=lambda: None)
    frames = [12.0, 30.0, 7.5, 20.0] * 25                          # 1,737.5 s of rendering
    p.start_clip()
    for t in frames:                                              # the queue: should_stop before every frame
        assert p.frame_hook() is False
        ft.render(t)
    p.end_clip()
    busy = sum(frames)
    assert p.frames == len(frames)
    assert p.waited == pytest.approx(busy * (100 / 70 - 1), rel=1e-6)
    wall = ft.t - _at(12)
    assert busy / wall == pytest.approx(0.70, abs=1e-6)
    assert wall == pytest.approx(kr.wall_seconds(busy, 0, _at(12), p.c), rel=0.01)
    # stills: the same rule
    p2 = kr.Pacer({"load": 50}, clock=ft.clock, sleep=ft.sleep, gpu=lambda: None)
    p2.before_still()
    ft.render(40.0)
    assert p2.after_still() == pytest.approx(40.0)
    # quiet hours: before 22:00 full speed, after it 50 %
    ft = FakeTime(_at(21, 50))
    p3 = kr.Pacer({"quiet_on": True, "quiet_load": 50}, clock=ft.clock, sleep=ft.sleep, gpu=lambda: None)
    waits = []
    for _ in range(40):
        p3.before_still()
        ft.render(30.0)
        waits.append(p3.after_still())
    assert waits[0] == 0 and waits[-1] == pytest.approx(30.0)
    assert full_load_frames(waits) == 19          # 10 min / 30 s; the 20th frame ends at 22:00: its pause is quiet
    assert kr.Pacer({}, gpu=lambda: None).after_frame(10.0) == 0  # 100 %: no pause


def full_load_frames(waits):
    return sum(1 for w in waits if w == 0)


def test_temperature_guard(kr):
    """Above the max the next frame waits until the card is 3 °C below it; the reads come from nvidia-smi (faked)."""
    ft = FakeTime(_at(12))
    temps = iter([84, 84, 83, 82, 81, 79, 76])
    reads = []

    def gpu():
        t = next(temps, 70)
        reads.append(t)
        return {"temp": float(t), "util": 99.0, "power": 330.0}

    said = []
    p = kr.Pacer({"max_temp": 80}, clock=ft.clock, sleep=ft.sleep, gpu=gpu, log=said.append)
    p.guard()
    assert reads == [84, 84, 83, 82, 81, 79, 76]                   # stops at ≤ 77
    assert p.cooled == pytest.approx(60.0) and ft.slept == pytest.approx(60.0)
    assert any("84 °C" in s for s in said)
    ft2 = FakeTime(_at(12))
    p2 = kr.Pacer({"max_temp": 80}, clock=ft2.clock, sleep=ft2.sleep, gpu=lambda: {"temp": 75.0, "util": 1, "power": 1})
    p2.guard()
    assert ft2.slept == 0
    said = []
    p3 = kr.Pacer({"max_temp": 80}, gpu=lambda: None, log=said.append)
    p3.guard()
    p3.guard()
    assert sum("cannot be read" in s for s in said) == 1
    assert kr.parse_gpu("67, 98, 312.45\n") == {"temp": 67.0, "util": 98.0, "power": 312.45}
    assert kr.parse_gpu("67, 98, [N/A]") == {"temp": 67.0, "util": 98.0, "power": None}
    assert kr.parse_gpu("No devices were found") is None


def test_pause_resume_stop_through_the_control_file(kr, tmp_path):
    ft = FakeTime(_at(12))
    out = str(tmp_path)
    p = kr.Pacer({}, out, clock=ft.clock, sleep=None, gpu=lambda: None, log=lambda s: None)
    assert open(os.path.join(out, kr.CONTROL)).read().strip() == "run"
    n = [0]

    def sleep(s):                       # the owner presses Resume after 30 s of pause
        ft.sleep(s)
        n[0] += 1
        if n[0] == 30:
            with open(os.path.join(out, kr.CONTROL), "w") as fh:
                fh.write("run")
    p.sleep = sleep
    with open(os.path.join(out, kr.CONTROL), "w") as fh:
        fh.write("pause")
    p.checkpoint()
    assert p.paused_s == pytest.approx(30.0)
    with open(os.path.join(out, kr.CONTROL), "w") as fh:
        fh.write("stop\r\n")
    with pytest.raises(kr.Stopped):
        p.frame_hook()
    p.c["load"] = 50
    with pytest.raises(kr.Stopped):                                # also inside a long pause between frames
        p.after_frame(100.0)
    p.show(state="running", model="Thor", step="Picture 1 of 2")
    st = json.load(open(os.path.join(out, kr.STATUS)))
    assert st["model"] == "Thor" and st["load"] == 50 and st["state"] == "running"


def test_run_state_and_resume(kr, tmp_path):
    out = str(tmp_path / "output")
    models = [{"id": "a", "views": ["LOW", "HIGH"], "video": "turntable"}, {"id": "b", "views": ["ISO"], "video": "none"}]
    assert kr.resume_info(out) is None
    st = kr.RunState.new(out, models, {"load": 70}, when=_at(23, 10))
    assert kr.resume_info(out) == {"started": "2026-11-15 23:10", "done": 0, "total": 4, "models": ["a", "b"]}
    st.record("a", "still:low", {"file": "a_low.jpg", "model": "a", "kind": "picture"})
    st.record("a", "still:high", {"file": "a_high.jpg", "model": "a", "kind": "picture"})
    again = kr.RunState.load(out)
    assert again.is_done("a", "still:low") and not again.is_done("a", "video")
    info = kr.resume_info(out)
    assert (info["done"], info["total"]) == (2, 4)
    assert kr.resume_text(info) == "Continue the run of 2026-11-15 23:10 (2 of 4 done)"
    again.record("a", "video", {"file": "a_turntable.mp4", "model": "a", "kind": "video"})
    again.complete("a")
    assert [i["file"] for i in again.all_items()] == ["a_low.jpg", "a_high.jpg", "a_turntable.mp4"]
    again.finish()
    assert kr.resume_info(out) is None                             # a finished run is not offered
    with open(os.path.join(out, kr.STATE), "w") as fh:
        fh.write("{broken")
    assert kr.resume_info(out) is None


def test_estimate_json_for_the_window(kit, kr, tmp_path, monkeypatch):
    monkeypatch.setenv("FRESING_KIT_STANDARD", str(tmp_path / "std" / "site_kit.json"))
    kr_kit = kit.kit_run
    kr_kit.save_standard({"load": 70, "quiet_on": True})
    models_dir = tmp_path / "kit" / "models"          # its own kit folder: no other test's "models" beside it
    models_dir.mkdir(parents=True)
    (models_dir / "a.step").write_bytes(b"x" * 1_000_000)
    ini = tmp_path / "m.ini"
    ini.write_text("[a]\nfile = a.step\ntitle = Model A\ncredit = c\nviews = LOW, HIGH\nvideo = turntable\n"
                   "[b]\nfile = b.step\ncredit = c\nviews = LOW\n", encoding="utf-8")
    out = tmp_path / "output"
    general, models = kit.read_settings(str(ini))
    st = kr_kit.RunState.new(str(out), models, {"load": 70})
    st.record("a", "still:low", {"file": "a_low.jpg"})
    js = tmp_path / "est.json"
    assert kit.main(["x", str(models_dir), str(out), str(ini), f"--estimate-json={js}"]) == 0
    raw = js.read_bytes()
    assert raw.isascii()
    info = json.loads(raw)
    a, b = info["models"]
    assert a["id"] == "a" and a["title"] == "Model A" and a["found"] and not b["found"]
    parts = kit.estimate_parts(models[0], general, str(models_dir))
    assert a["gpu"] == pytest.approx(parts["gpu"], abs=0.1) and a["cpu"] == pytest.approx(parts["cpu"], abs=0.1)
    assert info["standard"]["load"] == 70 and info["standard"]["quiet_on"] is True
    assert info["factory"] == kr.DEFAULT_STANDARD and info["step"] == kr.STEP
    r = info["resume"]
    assert r["done"] == 1 and r["total"] == 4 and r["text"].startswith("Continue the run of")
    b_parts = kit.estimate_parts(models[1], general, str(tmp_path / "models"))
    assert r["gpu"] == pytest.approx(parts["gpu"] - parts["still"] + b_parts["gpu"], abs=0.2)


def test_window_and_bat_are_wired(kit):
    """The .bat shows the start window, falls back to the console prompt, starts the status window and the end
    countdown; the window script is plain ASCII with CRLF (Windows PowerShell 5.1 reads files without a BOM as ANSI);
    the kit packs the new files."""
    bat = open(os.path.join(KIT, "Make site pictures.bat"), "rb").read().decode("utf-8")
    for want in ("kit_window.ps1", "-Mode start", "-Mode status", "-Mode end", "--estimate-json=", "--choices=",
                 "set /p", "-ExecutionPolicy Bypass", "-STA",
                 'set /p CODE=<"%OUT%\\run_result.txt"', 'if "%WIN%"=="10"'):
        assert want in bat, want
    ps = open(os.path.join(KIT, "kit_window.ps1"), "rb").read()
    assert ps.isascii(), [i for i, b in enumerate(ps) if b > 127][:5]
    assert b"\n" not in ps.replace(b"\r\n", b"")                       # CRLF everywhere (.gitattributes)
    text = ps.decode("ascii")
    for want in ("Get-WallSeconds", "Back to standard", "Graphics card", "Quiet hours", "When done",
                 "SetSuspendState", "shutdown.exe", "control.txt", "status.json", "site_kit.json", "fresing_logo.png"):
        assert want in text, want
    assert os.path.isfile(os.path.join(KIT, "fresing_logo.png"))
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_site_projects as msp
    for f in ("kit_window.ps1", "kit_run.py", "fresing_logo.png"):
        assert f in msp.KIT_FILES


# Windows PowerShell 5.1's built-in aliases: an alias wins over a function of the same name ("Sc" was Set-Content and
# the window never opened, task 0177)
PS51_ALIASES = set("""
% ? ac asnp cat cd cfs chdir clc clear clhy cli clp cls clv cnsn compare copy cp cpi cpp curl cvpa dbp del diff dir
dnsn ebp echo epal epcsv epsn erase etsn exsn fc fhx fl foreach ft fw gal gbp gc gcb gci gcm gcs gdr ghy gi gin gjb gl
gm gmo gp gps gpv group gsn gsnp gsv gtz gu gv gwmi h history icm iex ihy ii ipal ipcsv ipmo ipsn irm ise iwmi iwr kill
lp ls man md measure mi mount move mp mv nal ndr ni nmo npssc nsn nv ogv oh popd ps pushd pwd r rbp rcjb rcsn rd rdr
ren ri rjb rm rmdir rmo rni rnp rp rsn rsnp rujb rv rvpa rwmi sajb sal saps sasv sbp sc scb select set shcm si sl
sleep sls sort sp spjb spps spsv start stz sujb sv swmi tee trcm type wget where wjb write
""".split())


def _ps(name):
    return open(os.path.join(ROOT, name), "rb").read()


def test_window_layout_from_the_dpi():
    """Task 0177: no control is placed at fixed 96-DPI pixels (every number in a SetBounds / client size goes through
    Px), no function is shadowed by a 5.1 alias, the files are ASCII + CRLF, and the Windows job runs the layout check at
    100-200 % and on a 1366 x 768 screen at 150 %."""
    import re
    for name in ("site/render_kit/kit_window.ps1", "tools/ci_kit_window_layout.ps1"):
        raw = _ps(name)
        assert raw.isascii(), name
        assert b"\n" not in raw.replace(b"\r\n", b""), name
        text = raw.decode("ascii")
        funcs = re.findall(r"(?im)^\s*function\s+([\w-]+)", text)
        assert funcs and not [f for f in funcs if f.lower() in PS51_ALIASES], name
    kw = _ps("site/render_kit/kit_window.ps1").decode("ascii")
    assert "AutoScaleMode]::None" in kw and "SetProcessDPIAware" in kw and "DpiX / 96.0" in kw
    for call in re.findall(r"SetBounds\(([^\n]*)\)", kw):
        bare = re.sub(r"\(?Px \d+(\.\d+)?\)?|/ 2\b|\b2 \* (?=\$)", "", call)   # halves, both margins
        assert not re.search(r"(?<![\w.$])[1-9]\d*(?![\w.])", bare), call
    for size in re.findall(r"Drawing\.Size\(([^\n]*)\)", kw):
        if "$MaxW" in size:                                        # the box a text is measured in, not a control
            continue
        assert not re.search(r"(?<![\w.$])[1-9]\d*(?![\w.])", re.sub(r"\(?Px \d+\)?|100000", "", size)), size
    assert "ListView" in kw and "Time at full load" in kw          # the time per model in a column of its own
    assert "AutoScroll = $true" in kw                              # a small screen: the middle scrolls
    assert "$TestOnShown" in kw                                    # the check clicks through the start window
    ci = _ps("tools/ci_windows_install.ps1").decode("utf-8")
    assert "ci_kit_window_layout.ps1" in ci
    runs = re.search(r"\$KitLayoutRuns = @\(([^)]*)\)", ci).group(1)
    for want in ("1.0 ", "1.25 ", "1.5 1366x768", "1.75 ", "2.0 "):
        assert want in runs, want
    check = _ps("tools/ci_kit_window_layout.ps1").decode("ascii")
    for want in ("-Mode layout", "Measure-UiText", "IntersectsWith", "DrawToBitmap", "LAYOUT PROBLEM", "ChangeDisplaySettings",
                 "the check itself"):
        assert want in check, want


PWSH = shutil.which("pwsh")


@pytest.mark.skipif(not PWSH, reason="pwsh is not installed here (GitHub's Linux runners have it)")
def test_window_script_parses_and_its_time_matches_python(kr, tmp_path):
    """The window's script and its layout check parse (PowerShell 7 parser; the Windows job parses it with 5.1), and its own expected-time
    loop gives Python's numbers for a few choices."""
    script = os.path.join(KIT, "kit_window.ps1")
    cases = [(3600, 600, _at(12), {}), (3600, 600, _at(12), {"load": 70}),
             (4 * 3600, 0, _at(20), {"quiet_on": True, "quiet_load": 50}),
             (9000, 1200, _at(5, 30), {"load": 85, "quiet_on": True, "quiet_load": 45, "quiet_start": "23:15",
                                       "quiet_end": "06:40"})]
    calls = []
    for gpu, cpu, start, c in cases:
        c = kr.clean(c)
        when = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start))
        calls.append(f"[math]::Round((Get-WallSeconds {gpu} {cpu} ([datetime]'{when}') {c['load']} "
                     f"${str(c['quiet_on']).lower()} '{c['quiet_start']}' '{c['quiet_end']}' {c['quiet_load']}), 1)")
    probe = tmp_path / "probe.ps1"
    layout = os.path.join(ROOT, "tools", "ci_kit_window_layout.ps1")
    probe.write_text(
        "$errs = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$errs)\n"
        "if ($errs.Count) { $errs | ForEach-Object { Write-Output (\"PARSE \" + $_.Message) }; exit 5 }\n"
        "$errs = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{layout}', [ref]$null, [ref]$errs)\n"
        "if ($errs.Count) { $errs | ForEach-Object { Write-Output (\"PARSE \" + $_.Message) }; exit 5 }\n"
        f". '{script}' -Mode lib\n" + "\n".join(calls) + "\n", encoding="utf-8")
    res = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(probe)], capture_output=True, text=True,
                         timeout=120)
    assert res.returncode == 0, res.stdout + res.stderr
    got = [float(x) for x in res.stdout.split()]
    want = [kr.wall_seconds(g, c_, s, kr.clean(c)) for g, c_, s, c in cases]
    assert got == pytest.approx(want, abs=1.0)


def test_run_stops_and_continues_with_a_fake_renderer(kit, tmp_path, monkeypatch):
    """The kit's run loop with a fake app and a fake do_model that renders through the pacer and records into the run
    state as the real one does: Stop after the second picture ends the run with code 4 and a zip of what is done; the
    next run with --resume makes only the rest and finishes the run (no further 'Continue')."""
    import sys
    import types
    monkeypatch.setenv("FRESING_KIT_STANDARD", str(tmp_path / "std.json"))
    pkg = types.ModuleType("fake_fr")
    pkg.__version__ = "0.0-test"
    blender = types.ModuleType("fake_fr.blender")
    render = types.ModuleType("fake_fr.blender.render")
    render.QUALITY = {"draft": (8, 1)}
    render.setup_gpu = lambda: "GPU (fake)"
    for m in (pkg, blender, render):
        monkeypatch.setitem(sys.modules, m.__name__, m)
    monkeypatch.setattr(kit, "load_app", lambda: pkg)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    ini = tmp_path / "m.ini"
    ini.write_text("[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\nvideo = turntable\n"
                   "[b]\nfile = b.step\ncredit = c\nviews = ISO\n", encoding="utf-8")
    out = tmp_path / "output"
    rendered = []

    def fake_do_model(pkg_, m, general, models_dir_, out_, small, log, cpu=False, clock=None, pacer=None, state=None,
                      resume=False):
        send = os.path.join(out_, "send")
        for v in m["views"]:
            unit = f"still:{v.lower()}"
            jpg = os.path.join(send, f"{m['id']}_{v.lower()}.jpg")
            if state.is_done(m["id"], unit) and os.path.isfile(jpg):
                continue
            pacer.before_still()
            rendered.append(f"{m['id']} {v}")
            open(jpg, "w").write("x")
            state.record(m["id"], unit, {"file": os.path.basename(jpg), "model": m["id"], "kind": "picture",
                                         "caption": v})
            pacer.after_still()
            if rendered == ["a LOW", "a HIGH"]:                   # the owner presses Stop in the status window
                open(os.path.join(out_, "control.txt"), "w").write("stop")
        if m["video"] != "none" and not state.is_done(m["id"], "video"):
            pacer.start_clip()
            for _ in range(3):
                pacer.frame_hook()
            pacer.end_clip()
            rendered.append(f"{m['id']} video")
            open(os.path.join(send, f"{m['id']}_turntable.mp4"), "w").write("x")
            state.record(m["id"], "video", {"file": f"{m['id']}_turntable.mp4", "model": m["id"], "kind": "video",
                                            "caption": "t"})
        return []

    monkeypatch.setattr(kit, "do_model", fake_do_model)
    choices = tmp_path / "choices.json"
    choices.write_text(json.dumps({"load": 100, "models": ["a", "b"], "start_at": "", "resume": False}))
    args = ["x", str(models_dir), str(out), str(ini), f"--choices={choices}"]
    assert kit.main(args) == 4
    assert rendered == ["a LOW", "a HIGH"]
    assert (out / "run_result.txt").read_text() == "4"           # the .bat reads it: Blender cannot pass 4 through
    log = (out / "log.txt").read_text(encoding="utf-8")
    assert "STOPPED" in log and "Continue the run" in log
    assert json.load(open(out / "status.json"))["state"] == "stopped"
    info = kit.kit_run.resume_info(str(out))
    assert (info["done"], info["total"]) == (2, 4)
    zips = [f for f in os.listdir(out) if f.startswith("site_pictures_")]
    assert len(zips) == 1                                          # what is done is kept and zipped
    # the next double-click: the start window offers to continue; the choices say resume
    choices.write_text(json.dumps({"load": 100, "models": [], "resume": True}))
    assert kit.main(args) == 0
    assert rendered == ["a LOW", "a HIGH", "a video", "b ISO"]
    assert kit.kit_run.resume_info(str(out)) is None
    assert (out / "run_result.txt").read_text() == "0"
    log = (out / "log.txt").read_text(encoding="utf-8")
    assert "STOPPED" in log and "Continuing the run of" in log and "(4 of 4 of the run)" in log
    sent = json.load(open(out / "send" / "site_pictures.json"))
    assert [i["file"] for i in sent["items"]] == ["a_low.jpg", "a_high.jpg", "a_turntable.mp4", "b_iso.jpg"]
    assert json.load(open(out / "status.json"))["state"] == "finished"
