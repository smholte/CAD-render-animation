"""Windows checks W2 and W3 of the toolbox format's review (task 0245), on plain Python – no Blender module needed:

    <python.exe> tools/ci_toolbox_w2w3.py <work folder> [--seconds 40] [--label "Blender's Python"]

``tools/ci_windows_install.ps1`` (part A) runs it with the installed Blender's own ``python.exe`` (what the app runs
on) and, at the same time, with the runner's Python 3.11 when the runner has one. ``tests/test_toolbox.py`` runs
it for a few seconds on Linux (symbolic links in place of junctions; Linux never refuses a replace).

W2 – junctions: a directory junction (``mklink /J``) in the inbox whose name is a job id and whose target holds a whole
job, and a junction in place of a job's file. The inbox scan never takes the first, refuses the job of the second
(bad-job), and neither the files of the finished job nor the clean-up 40 days later delete anything through them;
both targets stay byte for byte as they were.

W3 – status.json replaced while read: Fresing Render's inbox works on a job for ``--seconds`` like a bake (a
``working`` status every second, a look every 25 ms) while a second process reads status.json every second – the
first half open, read, close; the second half it holds the file open 0.5 s each time, like a slow reader. Windows
refuses a replace while a handle is open: the refused writes are counted, each is kept and written at a later look,
and how long each stayed refused is measured (to answer whether the reference code's 5 x 50 ms would have been
enough). The job then finishes while the reader still reads: the last status on disk must be ``done``.

Prints one line per check and a last line ``W2W3 {json}`` with the numbers; exits 1 when a check fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent / "fresing_render"
sys.path.insert(0, str(APP))
from core import toolbox as tb  # noqa: E402  (the app's own code, imported without Blender)

HOUSE = APP / "data" / "sample-house.hpscene"
WIN = os.name == "nt"
FAILED: list[str] = []

READER = r"""
import json, sys, time
path, seconds, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
t0 = time.perf_counter()
n = {"reads": 0, "held": 0, "refused": 0, "missing": 0, "not_whole": 0}
open(out + ".started", "w").close()
while time.perf_counter() - t0 < seconds:
    late = time.perf_counter() - t0 > seconds / 2
    try:
        with open(path, "rb") as fh:
            data = fh.read()
            if late:
                n["held"] += 1
                time.sleep(0.5)
        n["reads"] += 1
        try:
            json.loads(data.decode("utf-8"))
        except ValueError:
            n["not_whole"] += 1
    except FileNotFoundError:
        n["missing"] += 1
    except PermissionError:
        n["refused"] += 1
    time.sleep(0.5 if late else 1.0)
open(out, "w").write(json.dumps(n))
"""


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'OK  ' if ok else 'FAIL'} {name}" + (f" ({detail})" if detail else ""), flush=True)
    if not ok:
        FAILED.append(name)
    return ok


def link_dir(link: Path, target: Path) -> None:
    """A directory junction on Windows (``mklink /J``), a symbolic link elsewhere."""
    if WIN:
        r = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if r.returncode:
            raise OSError(f"mklink /J failed: {r.stdout.strip()} {r.stderr.strip()}")
    else:
        os.symlink(target, link, target_is_directory=True)


def unlink_dir(link: Path) -> None:
    """Remove the junction / link itself, never what it points at."""
    if os.path.lexists(link):
        if WIN:
            os.rmdir(link)
        else:
            os.unlink(link)


def tree(d: Path) -> dict:
    """every file under ``d`` with its SHA-256 (what must stay untouched)"""
    out = {}
    for base, _dirs, files in os.walk(d):
        for f in files:
            p = Path(base, f)
            out[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def job_doc(jid: str, name: str, size: int) -> dict:
    return {"format": "toolbox-job", "version": tb.VERSION, "job": jid, "created": tb.now(),
            "from": tb.HOUSE_PLANNER, "to": tb.ME, "action": "bake-house",
            "files": [{"name": name, "type": "hpscene", "size": size}], "return": "import-bake", "title": "W2"}


def w2(work: Path) -> dict:
    root = work / "Toolbox"
    ib = tb.Inbox(root, "0", keep_dir=work / "kept")
    check("W2 the inbox starts", ib.start(), ib.problem)
    size = HOUSE.stat().st_size
    # target 1: a whole, valid job of its own (as if the junction were a job folder)
    j1 = "20261120-000000-aaaaaa"
    t1 = work / "outside 1 é"
    t1.mkdir()
    shutil.copyfile(HOUSE, t1 / HOUSE.name)
    tb.write_json(t1 / "job.json", job_doc(j1, HOUSE.name, size))
    # target 2: a folder that stands where a job's file should be
    t2 = work / "outside 2 é"
    t2.mkdir()
    (t2 / "keep.txt").write_text("keep", "utf-8")
    shutil.copyfile(HOUSE, t2 / HOUSE.name)
    before1, before2 = tree(t1), tree(t2)

    tb.play_house_planner(root, HOUSE, "W2 setup")                 # House Planner's stand-in manifest
    for d in ib._job_folders():
        shutil.rmtree(d)
    junction = ib.inbox / j1
    link_dir(junction, t1)
    j2 = "20261120-000001-bbbbbb"
    d2 = ib.inbox / j2
    d2.mkdir()
    link_dir(d2 / HOUSE.name, t2)
    tb.write_json(d2 / "job.json", job_doc(j2, HOUSE.name, size))
    inner = d2 / "inner"
    link_dir(inner, t2)
    tags = {}
    for p in (junction, d2 / HOUSE.name):
        st = os.lstat(p)
        tags[p.name] = hex(getattr(st, "st_reparse_tag", 0))
    check("W2 both are seen as links", tb.is_link(junction) and tb.is_link(d2 / HOUSE.name) and tb.is_link(inner),
          f"reparse tags {tags}, os.path.isjunction: {hasattr(os.path, 'isjunction')}")

    for _ in range(3):
        ib.look()
    check("W2 a junction named like a job is never taken", j1 not in ib.jobs and not (t1 / "status.json").exists())
    st = json.loads((d2 / "status.json").read_text("utf-8")) if (d2 / "status.json").exists() else {}
    check("W2 a junction in place of a job's file: bad-job", st.get("state") == "failed" and st.get("code") == "bad-job",
          st.get("text", "no status"))
    ib.clean(at=time.time() + 40 * tb.DAY)
    ib.look()
    check("W2 clean-up and the finished job's files: nothing deleted through a junction",
          tree(t1) == before1 and tree(t2) == before2)
    check("W2 the junctions themselves are left", os.path.lexists(junction) and os.path.lexists(d2 / HOUSE.name))
    for p in (junction, d2 / HOUSE.name, inner):
        unlink_dir(p)
    check("W2 targets untouched after removing the junctions", tree(t1) == before1 and tree(t2) == before2)
    return {"reparse_tags": tags}


def w3(work: Path, seconds: float) -> dict:
    root = work / "Toolbox"
    ib = tb.Inbox(root, "0", keep_dir=work / "kept")
    ib.start()
    jid = tb.play_house_planner(root, HOUSE, "W3 – a bake of a while")
    ib.look()
    check("W3 the job waits", jid in ib.jobs)
    check("W3 the job starts", ib.begin(jid, "Baking") == "")
    path = ib.folder(jid) / "status.json"

    refused: list[float] = []          # when each refused write happened
    blocked: list[float] = []          # how long a refused status stayed refused (until a write of it worked)
    first_refused: dict[Path, float] = {}
    real_write = tb.write_json

    def counted(p: Path, doc: dict) -> None:
        try:
            real_write(p, doc)
        except OSError:
            if p == path:
                t = time.perf_counter()
                refused.append(t)
                first_refused.setdefault(p, t)
            raise
        if p in first_refused:
            blocked.append(time.perf_counter() - first_refused.pop(p))

    tb.write_json = counted
    out = work / "reader.json"
    reader = subprocess.Popen([sys.executable, "-c", READER, str(path), str(seconds + 3), str(out)])
    try:
        t_wait = time.perf_counter()
        while not Path(str(out) + ".started").exists() and time.perf_counter() - t_wait < 30:
            time.sleep(0.05)
        t0 = time.perf_counter()
        half = None
        while time.perf_counter() - t0 < seconds:
            frac = (time.perf_counter() - t0) / seconds
            if half is None and frac >= 0.5:
                half = len(refused)
            ib.progress(jid, frac, f"Baking {round(frac * 100)} %")
            ib.look()
            time.sleep(0.025)
        rid, text = ib.reply(jid, [HOUSE], "Baked")            # final status while the reader still reads
        t_end = time.perf_counter()
        while ib._later and time.perf_counter() - t_end < 10:
            ib.look()
            time.sleep(0.025)
        check("W3 refused writes are written at a later look", not ib._later, f"{len(ib._later)} still kept")
    finally:
        reader.wait(timeout=seconds + 30)
        tb.write_json = real_write
    st = json.loads(path.read_text("utf-8"))
    check("W3 the last status on disk is the final one", st["state"] == "done", st["state"])
    r = json.loads(out.read_text("utf-8"))
    check("W3 the reader always read a whole file", r["not_whole"] == 0 and r["reads"] > 0, json.dumps(r))
    half = half if half is not None else len(refused)
    longest = max(blocked) if blocked else 0.0
    nums = {"seconds": seconds, "refused_writes": len(refused), "refused_quick_reads": half,
            "refused_held_reads": len(refused) - half, "longest_refused_s": round(longest, 3),
            "refused_over_0_25_s": sum(b > 0.25 for b in blocked), "reader": r, "reply_job": bool(rid)}
    check("W3 the job finished", st["state"] == "done", text)
    if WIN:                             # the check proves something only if Windows did refuse while a reader held it
        check("W3 Windows refused writes while the reader held status.json", nums["refused_held_reads"] > 0,
              f"{nums['refused_held_reads']} refused")
    return nums


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--seconds", type=float, default=40.0)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):        # a piped console on Windows is not UTF-8: never crash on a name
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    work = Path(a.work)
    shutil.rmtree(work, ignore_errors=True)
    info = {"label": a.label, "python": platform.python_version(), "executable": sys.executable,
            "system": platform.platform(), "windows": " ".join(platform.win32_ver()) if WIN else ""}
    print(f"W2/W3 {a.label}: Python {info['python']} on {info['system']}", flush=True)
    try:
        info["w2"] = w2(work / "w2")
        info["w3"] = w3(work / "w3", a.seconds)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        FAILED.append("crashed")
    info["failed"] = FAILED
    print("W2W3 " + json.dumps(info), flush=True)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
