"""The PC check "Stress" on a Linux machine without a graphics card (task 0315): the manual GitHub workflow stress.yml
and a web session run it the same way.

    ~/venv/bin/python tools/ci_stress.py --blender <blender> --wheels <linux wheels dir> --out <dir> [--small]

Installs the extension and the app template into a fresh settings folder (as ``ci_real_app.py``), starts the PC
check's launcher in mode Stress under a virtual screen (as the Tools-folder shortcut "PC check (stress)" does), then
judges its text block: every line OK, or skipped only for "no graphics card". The report, the stress table and the
console log stay in <dir>; the table goes to the run's summary on GitHub. Never part of the push run.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ci_check_pccheck  # noqa: E402
import ci_real_app  # noqa: E402


def stress_line_count() -> int:
    """How many lines the Stress mode has (read from the source: no Blender needed)."""
    path = os.path.join(ci_real_app.ROOT, "fresing_render", "pccheck", "stress.py")
    with open(path, encoding="utf-8") as fh:
        return sum(1 for ln in fh if ln.startswith('@stress_line("'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--blender", required=True)
    ap.add_argument("--wheels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--small", action="store_true", help="the small model (a few hundred parts): minutes")
    ap.add_argument("--timeout-min", type=float, default=150.0)
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fr_stress_")
    user_res = os.path.join(work, "user é")
    ci_real_app.install(a.blender, os.path.abspath(a.wheels), user_res, work)
    launcher = os.path.join(user_res, "extensions", "user_default", "fresing_render", "pccheck", "launcher.py")
    env = dict(os.environ, BLENDER_USER_RESOURCES=user_res, PYTHONUNBUFFERED="1", FRESING_SELFTEST_NO_GPU="1",
               FRESING_PCCHECK_DIR=os.path.join(out, "history"), FRESING_PCCHECK_NO_OPEN="1",
               TOOLBOX_HOME=os.path.join(work, "Toolbox é"))
    if a.small:
        env["FRESING_PCCHECK_STRESS_SMALL"] = "1"
    cmd = ["xvfb-run", "-a", "-s", ci_real_app.SCREEN, a.blender, "--background", "--online-mode",
           "--python-exit-code", "1", "--python", launcher, "--", out, "stress"]
    code, secs, _text = ci_real_app.run(cmd, env, os.path.join(out, "blender_output.log"), a.timeout_min * 60)
    block_path = os.path.join(out, "history", "last_run.txt")
    block = open(block_path, encoding="utf-8").read() if os.path.isfile(block_path) else ""
    rows, problems = ci_check_pccheck.judge(block, stress_line_count())
    if code not in (0, 1):
        problems.append(f"Blender stopped with exit code {code}")
    summary = ["### PC check Stress (Linux, no graphics card" + (", small model" if a.small else "") + ")", "",
               f"{len(rows)} lines in {secs / 60:.1f} min: " + ("all fine" if not problems else "PROBLEMS"), "",
               "```", block.strip(), "```"]
    if problems:
        summary += ["", "Problems:"] + [f"- {p}" for p in problems]
    text = "\n".join(summary) + "\n"
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    shutil.rmtree(work, ignore_errors=True)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
