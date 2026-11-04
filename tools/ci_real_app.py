"""Real-app tests in one go: for the automatic tests on GitHub, and usable on a chat machine.

Installs the extension (built with Linux wheels) and the app template into a real Blender with
its own, fresh settings folder (BLENDER_USER_RESOURCES), then runs:

    ui1    tools/ui_test_app.py   - the real app on a virtual screen, simulated clicks, screenshots
    ui2    tools/ui_test_app2.py  - the remaining buttons, undo/redo
    paths  tools/paths_test_blender.py - paths with spaces, accents, an apostrophe and an en dash

    python3 tools/ci_real_app.py --blender <blender program> --wheels <linux wheels dir> --out <dir>
                                 [--only ui1,paths] [--timeout-min 40]

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
MIN_CHECKS = {"ui1": 23, "ui2": 29, "paths": 8}
MIN_CHECKS_QUICK = {"ui1": 18}           # UITEST_QUICK=1 skips the renders of ui1


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
    ap.add_argument("--only", default="ui1,ui2,paths")
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
    tests = {
        "ui1": ("Real app: import, looks, joints, animation, queue (ui_test_app.py)", "ui_test_app.py", True),
        "ui2": ("Real app: remaining buttons, undo/redo (ui_test_app2.py)", "ui_test_app2.py", True),
        "paths": ("Paths with spaces, accents, ' and – (paths_test_blender.py)", "paths_test_blender.py", False),
    }
    rows = []
    for key in [k.strip() for k in args.only.split(",") if k.strip()]:
        title, script, gui = tests[key]
        folder = os.path.join(out, key)
        os.makedirs(folder, exist_ok=True)
        env = dict(base_env, UITEST_OUT=folder)
        script_path = os.path.join(ROOT, "tools", script)
        if gui:
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
        rows.append((title, verdict, detail, secs, fails))
        print(f"== {title}: {'PASS' if verdict else 'FAIL'} - {detail} ({secs:.0f} s)", flush=True)

    lines = ["### Real app (Linux, virtual screen)", "", "| Test | Result | Time |", "| --- | --- | --- |"]
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
