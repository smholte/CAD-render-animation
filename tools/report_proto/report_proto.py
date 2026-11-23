"""Prototype of task 0288 (study, never merged): the text of "Send a report" and the weekly summary of the opt-in
statistics, both built from what the app already keeps – the usage file of task 0181 (``fresing_usage.json``) and the
PC check's text block (task 0032) – plus the last Python error, with paths and names taken out.

No Blender, no network: this file imports no network library (``test_report_proto.py`` checks it, as
``tests/test_usage.py`` does for the tracker) and the tests build everything with the network blocked.

    ~/venv/bin/python tools/report_proto/report_proto.py            # print the report and the summary of the samples
    ~/venv/bin/python tools/report_proto/make_page.py               # put them on tasks/0288_page/index.html

Three rules, the same in step 1 and step 2:

1. **Only the app's own words leave the PC**: function ids of ``core/functions.py``, panel class names, operator ids,
   stage names, version numbers, the names of the app's own files in a trace. Anything the user typed or chose (file,
   part, folder, project, workspace, set-up, company and computer names) is never copied in – it is not even read.
2. **Numbers are rounded or put in buckets** (``bucket_*``): "1,000–5,000 parts", "17–32 cores", a GPU family, seconds
   to two digits, active time to 5 (report) or 15 (summary) minutes, dates to the month (report) or the ISO week
   (summary).
3. **Free text is scrubbed twice**: paths out (``pccheck.core.scrub``'s pattern), then every name the app knows on
   this PC (user, computer, the open project's file and part names – ``secrets``) out, then quoted text that is not
   one of the app's own identifiers out. ``leaks`` looks for what is left and the tests demand that it finds nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fresing_render.core import usage as U                      # noqa: E402  (read only: the tracker's own rules)
from fresing_render.pccheck.core import _PATH                    # noqa: E402  (the PC check's path pattern)

SCHEMA = 1                                  # version of the weekly summary's layout
REPORT_TITLE = "Fresing Render – report"


# ---------------------------------------------------------------------------------------------------------------------
# buckets: a number that helps a decision, never one that tells this PC or this project apart

PART_BUCKETS = [(100, "under 100"), (1000, "100–1,000"), (5000, "1,000–5,000"), (20000, "5,000–20,000"),
                (100000, "20,000–100,000")]
CORE_BUCKETS = [(4, "1–4"), (8, "5–8"), (16, "9–16"), (32, "17–32"), (64, "33–64")]
RAM_SIZES = [8, 16, 32, 64, 128, 256]
WINDOWS_BUILDS = {19045: "Windows 10 22H2", 22000: "Windows 11 21H2", 22621: "Windows 11 22H2",
                  22631: "Windows 11 23H2", 26100: "Windows 11 24H2", 26200: "Windows 11 25H2"}


def bucket(n, table, last: str) -> str:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "unknown"
    for top, name in table:
        if n <= top:
            return name
    return last


def bucket_parts(n) -> str:
    return bucket(n, PART_BUCKETS, "over 100,000")


def bucket_cores(n) -> str:
    return bucket(n, CORE_BUCKETS, "over 64")


def bucket_ram(gb) -> str:
    """The nearest usual memory size at or above what Windows reports (it reports a little less than is fitted)."""
    try:
        gb = float(gb)
    except (TypeError, ValueError):
        return "unknown"
    for size in RAM_SIZES:
        if gb <= size * 1.02:
            return f"{size} GB"
    return "over 256 GB"


def two_digits(seconds) -> float:
    """Seconds to two significant digits (83.4 -> 83, 1234 -> 1200, 0.437 -> 0.44): enough to see a speed change."""
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return 0.0
    if s <= 0:
        return 0.0
    return float(f"{s:.2g}")


def round_minutes(seconds, step: int) -> int:
    return int(round(float(seconds) / 60.0 / step)) * step


def gpu_family(name: str) -> str:
    """'NVIDIA GeForce RTX 4070 Ti SUPER' -> 'NVIDIA RTX 40-series'; the model number is left out."""
    n = " ".join(str(name or "").replace("(R)", "").replace("(TM)", "").split())
    low = n.lower()
    if not n or low in ("-", "none", "?") or "no gpu" in low or "cpu" == low:
        return "none"
    m = re.search(r"\b(RTX|GTX)\s*(\d{2})\d{2}", n, re.I)
    if "nvidia" in low or m:
        if m:
            return f"NVIDIA {m.group(1).upper()} {m.group(2)}-series"
        if re.search(r"\bRTX\s*A\d|quadro|\bA\d{3,4}\b", n, re.I):
            return "NVIDIA workstation"
        return "NVIDIA other"
    if "radeon" in low or "amd" in low:
        m = re.search(r"\bRX\s*(\d)\d{3}", n, re.I)
        return f"AMD RX {m.group(1)}000-series" if m else "AMD other"
    if "intel" in low:
        m = re.search(r"\bArc\s*([ABC])\d", n, re.I)
        return f"Intel Arc {m.group(1).upper()}-series" if m else "Intel built-in"
    if "apple" in low:
        return "Apple"
    return "other"


def cpu_family(name: str) -> str:
    """'AMD Ryzen 9 7950X 16-Core Processor' -> 'AMD Ryzen 9'; 'Intel(R) Core(TM) i7-12700K' -> 'Intel Core i7'."""
    n = " ".join(str(name or "").replace("(R)", "").replace("(TM)", "").split())
    for pat, out in ((r"Threadripper", "AMD Threadripper"), (r"EPYC", "AMD EPYC"), (r"Ryzen\s*(\d)", "AMD Ryzen {}"),
                     (r"Core\s*Ultra\s*(\d)", "Intel Core Ultra {}"), (r"Core\s*i(\d)|\bi(\d)-\d{4,5}", "Intel Core i{}"),
                     (r"Xeon", "Intel Xeon")):
        m = re.search(pat, n, re.I)
        if m:
            return out.format(next((g for g in m.groups() if g), ""))
    low = n.lower()
    return "AMD other" if "amd" in low else "Intel other" if "intel" in low else "other"


def windows_name(os_text: str) -> str:
    """'Windows 10 (10.0.26100)' -> 'Windows 11 24H2' (Windows 11 still says 10 in its version number)."""
    m = re.search(r"10\.0\.(\d{5})", str(os_text or ""))
    if not m:
        return "Windows (unknown build)" if "windows" in str(os_text).lower() else "other"
    build = int(m.group(1))
    known = [b for b in WINDOWS_BUILDS if b <= build]
    return WINDOWS_BUILDS[max(known)] if known else "Windows 10 (older)"


# ---------------------------------------------------------------------------------------------------------------------
# free text: paths and names out

# The app's own words that may stay inside quotes in an error message: a property or object name the app makes
# ('fr_value', 'FR flex shapes'), an operator id ('fresing.import_step'), a Python identifier of 3–40 letters with an
# underscore (a dict key in the code). Anything else in quotes – a part name, a file name – becomes '<text>'.
_OWN_WORD = re.compile(r"^(?:fr_[\w.]{1,40}|FR [\w ]{1,30}|fresing\.[a-z_]{2,40}|[a-z]+(?:_[a-z0-9]+){1,4})$")
_QUOTED = re.compile(r"(['\"])(.*?)\1")
_FRAME = re.compile(r'^(\s*)File "([^"]+)", line (\d+), in (\S+)\s*$')
_OWN_FILE = re.compile(r"[\\/](fresing_render[\\/].+)$")
_BLENDER_FILE = re.compile(r"[\\/]scripts[\\/](modules|startup|addons_core)[\\/](.+)$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_WINUSER = re.compile(r"(?i)\\Users\\[^\\\s]+")


def _scrub_free(text: str, secrets=()) -> str:
    """One line of free text: paths -> <path>, known names -> <name>, e-mail -> <e-mail>, quoted text that is not
    the app's own word -> '<text>'."""
    text = _EMAIL.sub("<e-mail>", str(text or ""))
    text = _PATH.sub("<path>", text)
    for s in sorted({str(x) for x in secrets if x and len(str(x)) >= 3}, key=len, reverse=True):
        text = re.sub(re.escape(s), "<name>", text, flags=re.I)

    def quoted(m):
        inner = m.group(2)
        if inner in ("<path>", "<name>", "<text>") or _OWN_WORD.match(inner):
            return m.group(0)
        return f"{m.group(1)}<text>{m.group(1)}"
    return _QUOTED.sub(quoted, text)


def strip_trace(trace: str, secrets=()) -> str:
    """A Python traceback with nothing of the user's left in it.

    * a frame in the app's own files keeps its place from ``fresing_render/`` on, its line number, the function name
      and the source line (the app's code is public);
    * a frame in Blender's own Python keeps ``blender:/modules/…`` and its source line (Blender's code is public too);
    * any other frame (a script of the user's, a kit) becomes ``<other file>`` and its source line is dropped;
    * the message lines are scrubbed (``_scrub_free``)."""
    out = []
    keep_next = skip_next = False
    for raw in str(trace or "").splitlines():
        m = _FRAME.match(raw)
        if m:
            indent, path, line, func = m.groups()
            own = _OWN_FILE.search(path)
            if own:
                out.append(f'{indent}File "{own.group(1).replace(chr(92), "/")}", line {line}, in {func}')
                keep_next = True
            else:
                bl = _BLENDER_FILE.search(path)
                where = f"blender:/{bl.group(1)}/{bl.group(2).replace(chr(92), '/')}" if bl else "<other file>"
                out.append(f'{indent}File "{where}", line {line}, in {func}')
                keep_next, skip_next = bool(bl), not bl
            continue
        if skip_next and raw.startswith("    "):
            skip_next = False                                              # a user's own script: its line is his
            continue
        skip_next = False
        if keep_next and raw.startswith("    ") and not raw.lstrip().startswith(("File ", "^", "~")):
            out.append("    " + _scrub_free(raw.strip(), secrets))       # the app's own source line
            keep_next = False
            continue
        keep_next = False
        if raw.strip() and set(raw.strip()) <= set("^~ "):
            continue                                                       # the ^^^^ markers under a line
        out.append(_scrub_free(raw, secrets) if raw.strip() else raw)
    return "\n".join(out)


def error_key(trace: str) -> dict:
    """Step 2 sends only where an error happened and its kind – never the message: {"where", "type"}."""
    frames = [ln for ln in strip_trace(trace).splitlines() if ln.strip().startswith("File ")]
    own = [f for f in frames if '"fresing_render/' in f]
    last = (own or frames or [""])[-1]
    m = re.search(r'File "([^"]+)", line (\d+), in (\S+)', last)
    where = f"{m.group(1)}:{m.group(2)} {m.group(3)}" if m else "unknown"
    lines = [ln for ln in str(trace).strip().splitlines() if ln.strip()]
    kind = re.match(r"^([A-Za-z_][\w.]*)(?::|$)", lines[-1].strip()) if lines else None
    return {"where": where, "type": kind.group(1) if kind else "unknown"}


def scrub_pccheck(block: str, secrets=()) -> str:
    """The PC check's text block (already free of the own model's names, task 0032) scrubbed once more – a reason text
    can quote a path – and its PC line left out: the report has its own, bucketed."""
    out = []
    for ln in str(block or "").splitlines():
        if ln.startswith("PC: "):
            continue
        out.append(_scrub_free(ln, secrets))
    return "\n".join(out)


def leaks(text: str, secrets=()) -> list:
    """What would identify the user, his PC or his work, still found in ``text`` (the tests want []): a known name,
    a path (drive, UNC, a home folder), an e-mail address, a Windows user folder."""
    found = []
    low = str(text).lower()
    for s in secrets:
        if s and len(str(s)) >= 3 and str(s).lower() in low:
            found.append(f"name: {s}")
    for pat, what in ((r"(?<![A-Za-z])[A-Za-z]:[\\/]", "drive path"), (r"\\\\[\w.-]+\\", "network path"),
                      (r"(?<![\w<])/(?:home|Users|mnt|tmp)/", "home path"), (_EMAIL.pattern, "e-mail"),
                      (_WINUSER.pattern, "user folder")):
        for m in re.finditer(pat, str(text)):
            found.append(f"{what}: {m.group(0)}")
    return found


# ---------------------------------------------------------------------------------------------------------------------
# step 1: the report the user reads, copies, saves or mails himself

def _top(d: dict, n: int) -> list:
    return sorted(((k, v) for k, v in d.items() if v), key=lambda kv: (-kv[1], kv[0]))[:n]


def pc_lines(pc: dict) -> list:
    return [f"PC: {windows_name(pc.get('os'))}; processor {cpu_family(pc.get('cpu'))}, "
            f"{bucket_cores(pc.get('cores'))} cores; memory {bucket_ram(pc.get('ram_gb'))}",
            f"Graphics: {gpu_family(pc.get('gpu'))}"
            + (f", video memory {bucket_ram(pc.get('vram_gb'))}" if pc.get("vram_gb") else "")
            + (f", driver {str(pc.get('driver')).split('.')[0]}" if pc.get("driver") not in (None, "", "-") else "")]


def report_text(state: dict, app: str, blender: str, pc: dict, pccheck: str = "", trace: str = "",
                trace_date: str = "", speeds=(), made: str = "", secrets=()) -> str:
    """The plain text of "Send a report" – exactly what the window shows and what Copy / Save / E-mail hand on."""
    st = U.clean(state)
    rows = [f"{REPORT_TITLE} – made {made}" if made else REPORT_TITLE,
            "This is everything this report holds. Nothing has been sent: you decide what to do with it.",
            "",
            "== The app and the PC",
            f"Fresing Render {app}, Blender {blender}"]
    rows += pc_lines(pc)
    first = st.get("first", "")[:7]
    rows += ["", "== How the app is used (from My usage; counting can be switched off there)",
             f"App starts counted: {st['sessions']}" + (f", counting since {first}" if first else "")]
    stages = [(U.STAGES.get(k, k), round_minutes(v, 5)) for k, v in st["stages"].items()]
    stages = [(k, m) for k, m in stages if m > 0]
    if stages:
        rows.append("Active time by stage (5-minute steps): "
                    + "; ".join(f"{k} {U.duration(m * 60)}" for k, m in sorted(stages, key=lambda x: -x[1])))
    funcs = {k: v[0] for k, v in st["functions"].items()}
    if funcs:
        rows.append("Most-used functions (clicks): "
                    + ", ".join(f"{k} {v}" for k, v in _top(funcs, 15)))
    if st.get("hidden"):
        rows.append("Panels you hid: " + ", ".join(sorted(st["hidden"])[:20]))
    pins = st.get("bar", {}).get("pins") or []
    if pins:
        rows.append("Pinned on the favourites bar: " + ", ".join(pins[:8]))
    if speeds:
        rows += ["", "== Speeds measured while you worked (sizes in steps, times to two digits)"]
        for s in speeds:
            rows.append(f"{s['what']}: {bucket_parts(s.get('parts'))} parts, {two_digits(s.get('seconds')):g} s")
    if pccheck:
        rows += ["", "== The last PC check (its own text block, names and paths taken out)",
                 scrub_pccheck(pccheck, secrets)]
    if trace:
        rows += ["", "== The last error" + (f" ({trace_date})" if trace_date else "")
                 + " – folders, file names and your own names taken out",
                 strip_trace(trace, secrets)]
    rows += ["", "== Never in this report",
             "Names of parts, files, folders or projects; pictures, models, G-code; your name, your company's name, "
             "your computer's name; set-up files and their folders; anything you typed."]
    return "\n".join(rows)


# ---------------------------------------------------------------------------------------------------------------------
# step 2: the weekly summary (only after the user said yes)

def week_counts(now: dict, then: dict | None) -> dict:
    """This week's clicks per function: the usage file holds totals, so the app keeps the totals it last sent
    (``then``) and sends the difference. A reset (smaller total) counts from 0."""
    now = U.clean(now)
    then = U.clean(then or {})
    out = {}
    for k, (n, _last) in now["functions"].items():
        before = then["functions"].get(k, [0, 0])[0]
        d = n - before if n >= before else n
        if d > 0:
            out[k] = d
    return dict(sorted(out.items()))


def weekly_summary(now: dict, then: dict | None, install_id: str, week: str, app: str, blender: str, pc: dict,
                   speeds=(), errors=(), pccheck=None, company_setup: bool = False, workspace: str = "",
                   asked: str = "q1") -> dict:
    """The one small JSON a PC sends a week when the user said yes. ``install_id`` is a random id made at the yes
    (``Reset`` makes a new one); ``week`` is the ISO week ('2026-W47'), never a time of day; ``asked`` is the version
    of the consent question's words the user said yes to (GDPR Art. 7(1): consent must be shown)."""
    now_c, then_c = U.clean(now), U.clean(then or {})
    act = {}
    for k, v in now_c["stages"].items():
        d = v - then_c["stages"].get(k, 0.0)
        m = round_minutes(d if d >= 0 else v, 15)
        if m > 0:
            act[k] = m
    errs = {}
    for t in errors:
        key = error_key(t)
        name = f"{key['type']} at {key['where']}"
        errs[name] = errs.get(name, 0) + 1
    built_in = {"All functions", "CNC milling", "Offshore", "Product design", "Lifting plans", "Client view",
                "Full access", "Machines", "Presentations"}
    return {
        "schema": SCHEMA, "asked": asked, "id": install_id, "week": week, "app": app, "blender": blender,
        "os": windows_name(pc.get("os")), "cpu": cpu_family(pc.get("cpu")), "cores": bucket_cores(pc.get("cores")),
        "ram": bucket_ram(pc.get("ram_gb")), "gpu": gpu_family(pc.get("gpu")),
        "sessions": max(0, now_c["sessions"] - then_c["sessions"]),
        "active_minutes": act,
        "functions": week_counts(now, then),
        "speeds": [{"what": s["what"], "parts": bucket_parts(s.get("parts")), "s": two_digits(s.get("seconds"))}
                   for s in speeds],
        "errors": [{"what": k, "n": n} for k, n in sorted(errs.items())],
        "pccheck": pccheck or {},
        "company_setup": bool(company_setup),
        "workspace": workspace if workspace in built_in else ("own" if workspace else ""),
    }


def summary_bytes(summary: dict) -> int:
    return len(json.dumps(summary, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


# ---------------------------------------------------------------------------------------------------------------------
# the made-up samples

def samples() -> dict:
    with open(os.path.join(HERE, "sample_usage.json"), encoding="utf-8") as fh:
        usage = json.load(fh)
    with open(os.path.join(HERE, "sample_usage_last_week.json"), encoding="utf-8") as fh:
        last_week = json.load(fh)
    with open(os.path.join(HERE, "sample_pccheck.txt"), encoding="utf-8") as fh:
        pccheck = fh.read()
    with open(os.path.join(HERE, "sample_trace.txt"), encoding="utf-8") as fh:
        trace = fh.read()
    pc = {"cpu": "AMD Ryzen 9 7950X 16-Core Processor", "cores": 32, "ram_gb": 63.7,
          "gpu": "GPU: NVIDIA GeForce RTX 4070 Ti SUPER", "vram_gb": 16, "driver": "566.36",
          "os": "Windows 10 (10.0.26100)"}
    # what the app knows on this PC and must never send: the Windows user, the computer, the open project, its parts
    secrets = ["jdevries", "WS-ENG-0412", "Pump skid rev4", "pump_skid_rev4", "IMPELLER HOUSING 250-3",
               "Acme Offshore", "Klant Acme"]
    speeds = [{"what": "Import STEP", "parts": 2310, "seconds": 83.4},
              {"what": "Build animation", "parts": 2310, "seconds": 12.7},
              {"what": "Render image (Cycles, GPU, 1920 x 1080, 128 samples)", "parts": 2310, "seconds": 41.2}]
    return {"usage": usage, "last_week": last_week, "pccheck": pccheck, "trace": trace, "pc": pc,
            "secrets": secrets, "speeds": speeds}


def build_samples() -> dict:
    s = samples()
    report = report_text(s["usage"], "0.2.203", "5.2.3", s["pc"], s["pccheck"], s["trace"], "22 Nov 2026",
                         s["speeds"], made="23 Nov 2026", secrets=s["secrets"])
    summary = weekly_summary(s["usage"], s["last_week"], "7f3c9a2e5b10d4e8a1c06f93be2257d4", "2026-W47", "0.2.203", "5.2.3",
                             s["pc"], speeds=s["speeds"], errors=[s["trace"]],
                             pccheck={"mode": "full", "ok": 61, "failed": 1, "skipped": 2, "slower": ["render.cycles"]},
                             company_setup=True, workspace="Acme drafting")
    return {"report": report, "summary": summary, "trace_before": s["trace"],
            "trace_after": strip_trace(s["trace"], s["secrets"]), "secrets": s["secrets"],
            "pccheck_before": s["pccheck"]}


if __name__ == "__main__":
    out = build_samples()
    print(out["report"])
    print("\n---- weekly summary", summary_bytes(out["summary"]), "bytes ----")
    print(json.dumps(out["summary"], indent=1, ensure_ascii=False))
    print("\nleaks in the report:", leaks(out["report"], out["secrets"]) or "none")
    print("leaks in the summary:", leaks(json.dumps(out["summary"]), out["secrets"]) or "none")
