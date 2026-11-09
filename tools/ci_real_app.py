"""Real-app tests in one go: for the automatic tests on GitHub, and usable on a chat machine.

Installs the extension (built with Linux wheels) and the app template into a real Blender with
its own, fresh settings folder (BLENDER_USER_RESOURCES), then runs:

    ui1    tools/ui_test_app.py   - the real app on a virtual screen, simulated clicks, screenshots
    ui2    tools/ui_test_app2.py  - the remaining buttons, undo/redo
    faces  tools/ui_test_faces.py - painted faces: from CAD, 'Paint faces' with clicks in the view
    decals tools/ui_test_decals.py - logos & stickers: 'Add decal…' with a click, move with the mouse, one copy
    surroundings  tools/ui_test_surroundings.py - sea, deck, halls, props, queue (Cycles + EEVEE)
    studio  tools/ui_test_studio.py - light looks, camera views, blur + sharp spot, turntable in the queue
    callouts  tools/ui_test_callouts.py - labels on parts, picture card and music in a queued MP4, a still with a label
    video  tools/ui_test_video.py - brand kit in the library, logo, title/end card, captions, watermark in a queued MP4 and stills
    rulesets  tools/ui_test_rule_sets.py - rule sets: copy, change, save, switch with preview, undo
    milling  tools/ui_test_milling.py - milling: pick bit and block in the view, the cut follows the timeline; chips
    cylinder tools/ui_test_cylinder.py - cylinders: barrel and rod, clicks on the two pins, follow / drive, undo
    linkage tools/ui_test_linkage.py - mechanisms: Base, Add mechanism (scissor, four-bar), height, undo, Lift height
           step, save and open again, Remove
    gcode  tools/ui_test_gcode.py - CNC machine: axes, tool, workpiece, clicked work zero; Run G-code program step,
           the tip follows the program, tool change, toolpath, save and open again
    waycover tools/ui_test_waycover.py - way covers: axis, Add section x5, Make it, the axis drives the covers, Flip,
           Remove section, save and open again, Remove way cover
    paths  tools/paths_test_blender.py - paths with spaces, accents, an apostrophe and an en dash
    pccheck  the PC check (Full), started like its Start-menu shortcut: the launcher inside the installed
           extension, in a background Blender; judged by tools/ci_check_pccheck.py (task 0032)
    update tools/ci_update_test.py --gui - in-app update: an old version with the 0.2.10 app template finds
           this version on a local GitHub-like server, Update now, closes, is updated and starts again

    python3 tools/ci_real_app.py --blender <blender program> --wheels <linux wheels dir> --out <dir>
                                 [--only ui1,paths | --group ui] [--timeout-min 40]

Needs xvfb-run and ImageMagick ("import") for ui1/ui2. Every test's log and screenshots land in
<out>/<test>/; the verdict per test is printed, written to <out>/summary.md and to the GitHub job
summary. Exit code 1 when any test failed, did not finish, or reported no RESULT line.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import test_install_linux  # noqa: E402

SCREEN = "-screen 0 1800x2600x24"
RESULT_RE = re.compile(r"RESULT (\d+)/(\d+)")
# Fewest checks each test must report: a check that silently disappears turns the run red.
# Raise these when a test gets new checks (never lower them without saying why in the commit).
MIN_CHECKS = {"ui1": 23, "ui2": 50, "faces": 10, "decals": 13, "surroundings": 23, "rulesets": 17, "studio": 21,
              "milling": 25, "video": 14, "callouts": 15, "cylinder": 22, "linkage": 25, "waycover": 12, "gcode": 29,
              "paths": 8, "pccheck": 31, "pccheckheavy": 10, "update": 29, "tour": 29, "tourui": 15}
MIN_CHECKS_QUICK = {"ui1": 18, "surroundings": 17, "studio": 20, "video": 9, "callouts": 8}   # UITEST_QUICK=1 skips renders and the queue

# The real-app tests run on GitHub as parallel jobs, one per group (task 0036). Balanced by measured minutes
# (runs 42261621440 / 42263700501, 6 Nov 2026, each group on its own runner): pccheck 11.7 / 8.9 |
# callouts 5.2 / 9.8 (its queued video varies most: alone) | paths 2.8 / 2.7 + pccheckheavy 3.8 (task 0033) |
# ui1 7.7 + ui2 1.2 + faces 0.3 | surroundings 6.7 + rulesets 0.6 + decals 0.3 | video 3.4 + studio 1.6 + update 0.5 +
# milling 0.5 + cylinder 0.4 + linkage 0.4 + waycover 0.3 + gcode 0.4 (task 0026). A new test goes into the group with the fewest minutes
# (add it to TESTS and MIN_CHECKS too); a test that is in no group, or in two, fails the precheck
# (tools/ci_precheck.py). The PC check alone sets the run's length: keep the other groups below it.
GROUPS = {
    "pccheck": ["pccheck"],
    "callouts": ["callouts"],
    "paths-heavy": ["paths", "pccheckheavy", "tour"],
    "ui": ["ui1", "ui2", "faces"],
    "scenes": ["surroundings", "rulesets", "decals"],
    "motion": ["video", "studio", "update", "milling", "cylinder", "linkage", "waycover", "gcode", "tourui"],
}

TESTS = {
    "ui1": ("Real app: import, looks, joints, animation, queue (ui_test_app.py)", "ui_test_app.py", True),
    "ui2": ("Real app: remaining buttons, undo/redo (ui_test_app2.py)", "ui_test_app2.py", True),
    "faces": ("Real app: painted faces (ui_test_faces.py)", "ui_test_faces.py", True),
    "decals": ("Real app: logos & stickers – add with a click, move with the mouse (ui_test_decals.py)",
               "ui_test_decals.py", True),
    "surroundings": ("Real app: surroundings, props, queue (ui_test_surroundings.py)",
                     "ui_test_surroundings.py", True),
    "rulesets": ("Real app: rule sets – copy, save, switch, undo (ui_test_rule_sets.py)",
                 "ui_test_rule_sets.py", True),
    "studio": ("Real app: light looks, views, blur, turntable (ui_test_studio.py)", "ui_test_studio.py", True),
    "video": ("Real app: brand kit, logo, cards, captions, watermark in a queued video (ui_test_video.py)",
              "ui_test_video.py", True),
    "callouts": ("Real app: labels, picture card, music in a queued video (ui_test_callouts.py)",
                 "ui_test_callouts.py", True),
    "milling": ("Real app: milling – pick bit and block, cut follows the timeline (ui_test_milling.py)",
                "ui_test_milling.py", True),
    "cylinder": ("Real app: cylinders – barrel, rod, clicks on the pins, follow / drive (ui_test_cylinder.py)",
                 "ui_test_cylinder.py", True),
    "linkage": ("Real app: mechanisms – scissor lift, four-bar, height, Lift height step (ui_test_linkage.py)",
                "ui_test_linkage.py", True),
    "waycover": ("Real app: way covers – axis, five sections, Make it, the axis drives them (ui_test_waycover.py)",
                 "ui_test_waycover.py", True),
    "gcode": ("Real app: CNC machine and Run G-code program – clicks, tip on the path, tool change "
              "(ui_test_gcode.py)", "ui_test_gcode.py", True),
    "paths": ("Paths with spaces, accents, ' and – (paths_test_blender.py)", "paths_test_blender.py", False),
    "pccheck": ("PC check, Full, from the installed launcher (pccheck/launcher.py)", "", "pccheck"),
    "pccheckheavy": ("PC check, Heavy (scaled down), from the installed launcher", "", "pccheck"),
    "tour": ("Test tour, the automatic run (PC check mode Tour) from the installed launcher: every stop", "",
             "pccheck"),
    "tourui": ("Real app: test tour – make, open, Go here and in another project, OK / Problem, Copy results "
               "(ui_test_tour.py)", "ui_test_tour.py", True),
    "update": ("In-app update: old version + 0.2.10 template -> Update now -> new version (ci_update_test.py)",
               "ci_update_test.py", None),
}


def run(cmd, env, log_path, timeout):
    """Run cmd, write all output to log_path (and echo it). Returns (exit code or None, seconds, text)."""
    t0 = time.time()
    out: list[str] = []
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", start_new_session=True)

        def pump():
            for line in proc.stdout:
                log.write(line)
                log.flush()
                out.append(line)
                sys.stdout.write(line)
                sys.stdout.flush()

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)    # Blender and xvfb (a render queue has its own session)
            except ProcessLookupError:
                pass
            proc.wait()
            code = None
        reader.join(timeout=30)
        if code is None:
            log.write(f"\n*** stopped after {timeout / 60:.0f} minutes ***\n")
    return code, time.time() - t0, "".join(out)


def install(blender: str, wheels: str, user_res: str, work: str) -> str:
    """Build the Linux zip, install + enable it in a fresh settings folder, copy the app template."""
    env = dict(os.environ, BLENDER_USER_RESOURCES=user_res)
    zip_path = test_install_linux.build_linux_zip(wheels, os.path.join(work, "build"), blender=blender)
    subprocess.check_call([blender, "--factory-startup", "--command", "extension", "install-file",
                           "-r", "user_default", "-e", zip_path], env=env, timeout=600)
    dst = os.path.join(user_res, "scripts", "startup", "bl_app_templates_user", "fresing_render")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "app_template", "fresing_render"), dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return zip_path


def judge(key: str, code, text: str, timeout_min: float, quick: bool = False):
    """Verdict of one test from its exit code (None = stopped at the timeout) and its output.

    Returns (passed, detail, failure lines)."""
    lines = text.splitlines()
    fails = [ln.strip() for ln in lines if re.match(r"^(\[UITEST\] )?FAIL ", ln.strip()) or "ERROR in" in ln]
    m = None
    for m in RESULT_RE.finditer(text):
        pass
    # Python errors outside the test steps (a panel that fails to draw, a handler, an operator)
    # do not show up as a failed check: count them separately.
    stray = [i for i, ln in enumerate(lines) if "Traceback (most recent call last)" in ln and "ERROR in" not in ln]
    minimum = (MIN_CHECKS_QUICK if quick else {}).get(key, MIN_CHECKS[key])
    if code is None:
        verdict, detail = False, f"did not finish within {timeout_min:.0f} minutes"
    elif m is None:
        verdict, detail = False, f"no RESULT line (Blender exit code {code}): it stopped half-way"
    else:
        passed, total = int(m.group(1)), int(m.group(2))
        verdict = passed == total and total >= minimum
        detail = f"{passed}/{total} passed"
        if total < minimum:
            detail += f", but at least {minimum} checks expected"
    if stray:
        verdict = False
        i = stray[0]
        err = next((ln.strip() for ln in lines[i + 1:i + 40] if re.match(r"^\w*(Error|Exception)\b", ln.strip())), "")
        detail += f"; {len(stray)} Python error(s) outside the test steps"
        fails.append(f"Python error: {err or lines[i].strip()} (see blender_output.log)")
    return verdict, detail, fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", required=True)
    ap.add_argument("--wheels", required=True, help="folder with the Linux OpenCascade wheels")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=",".join(TESTS), help="tests to run, comma-separated (default: all)")
    ap.add_argument("--group", help="run one group of GROUPS (a parallel job on GitHub) instead of --only")
    ap.add_argument("--timeout-min", type=float, default=15, help="per test (they take 1-7 minutes)")
    args = ap.parse_args(argv)

    blender = os.path.abspath(args.blender)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fr_ci_")
    user_res = os.path.join(work, "blender_user")
    print("== installing the extension and the app template into", user_res, flush=True)
    t0 = time.time()
    install(blender, os.path.abspath(args.wheels), user_res, work)
    print(f"== installed in {time.time() - t0:.0f} s", flush=True)

    base_env = dict(os.environ, BLENDER_USER_RESOURCES=user_res, PYTHONUNBUFFERED="1")
    timeout = args.timeout_min * 60
    rows = []
    keys = GROUPS[args.group] if args.group else [k.strip() for k in args.only.split(",") if k.strip()]
    for key in keys:
        title, script, gui = TESTS[key]
        folder = os.path.join(out, key)
        os.makedirs(folder, exist_ok=True)
        env = dict(base_env, UITEST_OUT=folder)
        if key == "rulesets":                        # its own rule-set library; folds open so it can click in them
            env.update(FRESING_RULE_SETS_DIR=os.path.join(folder, "library", "Rule sets"), FRESING_UI_OPEN_FOLDS="1")
        script_path = os.path.join(ROOT, "tools", script)
        if gui == "pccheck":                         # as the Start-menu shortcut starts it (screen: for EEVEE)
            launcher = os.path.join(user_res, "extensions", "user_default", "fresing_render", "pccheck", "launcher.py")
            env.update(FRESING_PCCHECK_DIR=os.path.join(folder, "history"), FRESING_PCCHECK_NO_OPEN="1")
            cmd = ["xvfb-run", "-a", "-s", SCREEN, blender, "--background", "--online-mode", "--python-exit-code", "1",
                   "--python", launcher, "--", folder, {"pccheckheavy": "heavy", "tour": "tour"}.get(key, "full")]
            if key == "pccheckheavy":
                env["FRESING_PCCHECK_HEAVY_SMALL"] = "1"
        elif gui is None:                            # a driver of its own (own settings folder and screen)
            cmd = [sys.executable, script_path, "--gui", "--blender", blender, "--wheels", os.path.abspath(args.wheels),
                   "--out", folder, "--timeout-min", str(args.timeout_min)]
        elif gui:
            # --python-exit-code: an error while loading the script closes Blender instead of
            # leaving it open with nothing to drive it until the timeout
            cmd = ["xvfb-run", "-a", "-s", SCREEN, blender, "--app-template", "fresing_render",
                   "--enable-event-simulate", "--python-exit-code", "1", "--python", script_path]
        else:
            pdir = os.path.join(work, "pad test", "Mijn Projecten é ü", "Klant O'Brien – 2026")
            os.makedirs(pdir, exist_ok=True)
            for src, name in (("test_crane_a.step", "Kraan ontwerp – rev A é.step"),
                              ("test_crane_b.step", "Kraan ontwerp – rev B é.step")):
                shutil.copy2(os.path.join(ROOT, "tests", "data", src), os.path.join(pdir, name))
            env["PATHS_TEST_DIR"] = pdir
            cmd = [blender, "--background", "--python-exit-code", "1", "--python", script_path]
        print(f"\n== {title}", flush=True)
        code, secs, text = run(cmd, env, os.path.join(folder, "blender_output.log"), timeout)
        verdict, detail, fails = judge(key, code, text, args.timeout_min, bool(os.environ.get("UITEST_QUICK")))
        if gui == "pccheck":                         # skips only for "no graphics card", every line there
            import ci_check_pccheck
            block = os.path.join(folder, "history", "last_run.txt")
            text_block = open(block, encoding="utf-8").read() if os.path.isfile(block) else ""
            _rows, problems = ci_check_pccheck.judge(
                text_block, {"pccheckheavy": ci_check_pccheck.MIN_LINES_HEAVY,
                             "tour": ci_check_pccheck.MIN_LINES_TOUR}.get(key, ci_check_pccheck.MIN_LINES_FULL))
            if problems:
                verdict = False
                detail += "; " + "; ".join(problems[:3])
                fails += problems
        rows.append((title, verdict, detail, secs, fails))
        print(f"== {title}: {'PASS' if verdict else 'FAIL'} - {detail} ({secs:.0f} s)", flush=True)

    lines = [f"### Real app (Linux, virtual screen){f' - group {args.group}' if args.group else ''}", "", "| Test | Result | Time |", "| --- | --- | --- |"]
    for title, ok, detail, secs, _ in rows:
        lines.append(f"| {title} | {'✅' if ok else '❌'} {detail} | {secs / 60:.1f} min |")
    for title, ok, detail, secs, fails in rows:
        if fails:
            lines += ["", f"**{title}** - failing checks:", ""] + [f"- `{f[:200]}`" for f in fails[:30]]
    summary = "\n".join(lines) + "\n"
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    print("\n" + summary)
    for title, ok, detail, _, fails in rows:
        if not ok:
            print(f"::error title={title}::{detail}" + (f" - first failure: {fails[0][:200]}" if fails else ""))
    shutil.rmtree(work, ignore_errors=True)
    return 0 if rows and all(r[1] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
