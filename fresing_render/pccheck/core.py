"""PC check without Blender: lines and results, the history on this PC, speed and picture comparison,
the text block for the lead chat and the HTML report.

Everything here is plain Python + numpy so ``tests/test_pccheck.py`` can test it without Blender.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import statistics
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

OK, FAILED, SKIPPED, RUNNING = "OK", "FAILED", "skipped", "running"
MODES = ("quick", "full", "heavy")
MODE_TITLES = {"quick": "Quick", "full": "Full", "heavy": "Heavy"}

SLOWER = 1.25            # a step more than 25 % slower than before is flagged
MIN_SLOWER_S = 1.0       # ...and at least this many seconds slower (short steps jitter)
MIN_SLOWER_METRIC_S = 0.2
FASTER = 0.75            # shown as "faster" below this share of the earlier time
REFERENCE_RUNS = 3       # the reference is the median of this many earlier runs
KEEP_RUNS_PER_KEY = 5
KEEP_RUNS = 40
PICTURE_DIFF = 0.06      # mean difference (0..1) above which a picture is flagged "look at this"
THUMB_WIDTH = 240
HISTORY_FORMAT = 1


class Skipped(Exception):
    """A line that does not apply here (no graphics card, no own model): reported as skipped."""


class Cancelled(Exception):
    """The owner stopped the check (Help > Cancel PC check, or Ctrl+C in its window): the lines done so
    far stay in the report."""


# ---------------------------------------------------------------------------
# lines and results
# ---------------------------------------------------------------------------

@dataclass
class Line:
    """One function of the app the check tests. ``since``: the version that brought it (for "new in
    this version"); ``modes``: "quick", "full" and/or "own" (with the owner's own model)."""
    id: str
    title: str
    since: str
    modes: tuple
    fn: Callable
    requires: tuple = ()
    what: str = ""          # one sentence: what the line does, shown in the report
    expected: int = 0       # seconds the line is expected to take on the owner's PC (Heavy: shown while it runs)
    shows: str = ""         # Heavy: one sentence "what this shows"
    not_shown: str = ""     # Heavy: one sentence "what this does not show"


@dataclass
class Picture:
    key: str
    title: str
    thumb_png: bytes = b""
    problems: list = field(default_factory=list)     # "black", "model not in the picture", ...
    width: int = 0                                   # thumbnail width (0 = the usual small one); Heavy: larger
    settings: str = ""                               # shown under the picture: size, quality, device
    difference: float | None = None                  # mean difference from the last run's picture
    flagged: bool = False                            # differs a lot: "look at this"


@dataclass
class Result:
    id: str
    title: str
    since: str
    status: str = RUNNING
    seconds: float = 0.0
    note: str = ""                                   # shown in the report (this PC only)
    reason: str = ""                                 # why it failed or was skipped
    trace: str = ""
    metrics: dict = field(default_factory=dict)      # name -> (value, unit)
    pictures: list = field(default_factory=list)
    own: bool = False                                # a line on the owner's own model: numbers only
    what: str = ""
    error_type: str = ""
    reference: float | None = None                   # median time of the earlier runs
    flags: list = field(default_factory=list)        # "slower", "picture", "failed"
    metric_refs: dict = field(default_factory=dict)  # name -> earlier median
    expected: int = 0
    started: float = 0.0                             # time.time() when the line began (progress line)
    shows: str = ""
    not_shown: str = ""


@dataclass
class Run:
    app_version: str
    mode: str
    date: str
    blender: str = ""
    pc: dict = field(default_factory=dict)           # cpu, cores, ram_gb, gpu, driver, os
    results: list = field(default_factory=list)
    new_ids: set = field(default_factory=set)
    own_model: bool = False
    finished: bool = False
    seconds: float = 0.0
    compared_with: str = ""                          # "the run of 4 Nov 2026 (0.2.20)" or ""
    planned: list = field(default_factory=list)      # titles of the lines still to run
    model_tag: str = ""                              # a short code of the own model's file (never its name)
    cancelled: bool = False                          # the owner stopped the check
    scaled: bool = False                             # Heavy in its scaled-down form (GitHub, small machines)

    @property
    def key(self) -> str:
        """Runs of the same key are compared: same mode, and with an own model the same file."""
        return self.mode + (f"+own-{self.model_tag}" if self.own_model else "")

    def counts(self) -> dict:
        c = {OK: 0, FAILED: 0, SKIPPED: 0}
        for r in self.results:
            if r.status in c:
                c[r.status] += 1
        return c

    def all_ok(self) -> bool:
        return self.finished and not any(r.status == FAILED for r in self.results)


def lines_for(lines: list, mode: str, own_model: bool) -> list:
    """The lines a run does: the mode's lines, plus the own-model lines when a model was given."""
    out = [ln for ln in lines if mode in ln.modes]
    if own_model:
        out += [ln for ln in lines if "own" in ln.modes and ln not in out]
        if mode == "heavy":                      # Heavy with an own model: the own-model Heavy lines too
            out += [ln for ln in lines if "ownheavy" in ln.modes and ln not in out]
    return out


def version_tuple(text: str) -> tuple:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


# ---------------------------------------------------------------------------
# history on this PC
# ---------------------------------------------------------------------------

def load_history(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("runs"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"format": HISTORY_FORMAT, "runs": []}


def run_record(run: Run) -> dict:
    """What the history keeps of a run: numbers and states only."""
    lines = {}
    for r in run.results:
        if r.status == RUNNING:
            continue
        lines[r.id] = {"status": r.status, "seconds": round(r.seconds, 2),
                       "metrics": {k: round(float(v[0]), 4) for k, v in r.metrics.items()
                                   if isinstance(v[0], (int, float))}}
    return {"app": run.app_version, "mode": run.mode, "key": run.key, "date": run.date,
            "finished": run.finished, "lines": lines}


def add_to_history(history: dict, record: dict) -> dict:
    runs = list(history.get("runs", [])) + [record]
    keep, per_key = [], {}
    for rec in reversed(runs):                      # newest first: keep the last few of each kind
        k = rec.get("key", "")
        per_key[k] = per_key.get(k, 0) + 1
        if per_key[k] <= KEEP_RUNS_PER_KEY and len(keep) < KEEP_RUNS:
            keep.append(rec)
    return {"format": HISTORY_FORMAT, "runs": list(reversed(keep))}


def save_history(path: str, history: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=1)
    os.replace(tmp, path)


def earlier_runs(history: dict, key: str) -> list:
    """Earlier runs of the same kind (Quick, Full, with own model), newest first."""
    return [r for r in reversed(history.get("runs", [])) if r.get("key") == key]


def reference_time(history: dict, key: str, line_id: str) -> float | None:
    vals = [r["lines"][line_id]["seconds"] for r in earlier_runs(history, key)
            if r.get("lines", {}).get(line_id, {}).get("status") == OK][:REFERENCE_RUNS]
    return statistics.median(vals) if vals else None


def reference_metric(history: dict, key: str, line_id: str, name: str) -> float | None:
    vals = []
    for r in earlier_runs(history, key):
        ln = r.get("lines", {}).get(line_id, {})
        if ln.get("status") == OK and name in ln.get("metrics", {}):
            vals.append(ln["metrics"][name])
    vals = vals[:REFERENCE_RUNS]
    return statistics.median(vals) if vals else None


def is_slower(seconds: float, reference: float | None, min_s: float = MIN_SLOWER_S) -> bool:
    return reference is not None and seconds > reference * SLOWER and seconds - reference >= min_s


def is_faster(seconds: float, reference: float | None, min_s: float = MIN_SLOWER_S) -> bool:
    return reference is not None and seconds < reference * FASTER and reference - seconds >= min_s


def change_text(seconds: float, reference: float | None) -> str:
    if reference is None or reference <= 0:
        return ""
    pct = (seconds / reference - 1.0) * 100.0
    return f"{pct:+.0f} %"


def compare(run: Run, history: dict) -> None:
    """Fill in references, speed flags and "new in this version" from the earlier runs on this PC."""
    for r in run.results:
        r.flags = [f for f in r.flags if f not in ("slower", "failed")]
        if r.status == FAILED:
            r.flags.append("failed")
        if r.status != OK:
            continue
        r.reference = reference_time(history, run.key, r.id)
        slow = is_slower(r.seconds, r.reference)
        for name, (value, unit) in r.metrics.items():
            if not isinstance(value, (int, float)) or not str(unit).startswith("s"):
                continue
            ref = reference_metric(history, run.key, r.id, name)
            r.metric_refs[name] = ref
            slow = slow or is_slower(float(value), ref, MIN_SLOWER_METRIC_S)
        for name, (value, unit) in r.metrics.items():          # milliseconds per frame (playback): 2 ms is a jump
            if isinstance(value, (int, float)) and str(unit).startswith("ms"):
                ref = reference_metric(history, run.key, r.id, name)
                r.metric_refs[name] = ref
                if is_slower(float(value), ref, 2.0):
                    slow = True
        if slow:
            r.flags.append("slower")
    run.new_ids = new_line_ids(run, history)
    prev = earlier_runs(history, run.key)
    if prev:
        run.compared_with = f"the run of {prev[0].get('date', '?')} ({prev[0].get('app', '?')})"


def new_line_ids(run: Run, history: dict) -> set:
    """Lines new since the last run of this kind on this PC; with no earlier run, the lines that came
    with this version."""
    prev = earlier_runs(history, run.key)
    if not prev:
        return {r.id for r in run.results if version_tuple(r.since) == version_tuple(run.app_version)}
    last = prev[0]
    seen = set(last.get("lines", {}))
    last_app = version_tuple(last.get("app", "0"))
    return {r.id for r in run.results if r.id not in seen or version_tuple(r.since) > last_app}


# ---------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------

def thumbnail(px: np.ndarray, width: int = THUMB_WIDTH) -> np.ndarray:
    """Box-averaged smaller copy of an RGB(A) picture (rows top to bottom), ``width`` pixels wide."""
    px = np.asarray(px, dtype=np.float64)
    h, w = px.shape[:2]
    width = max(1, min(width, w))
    height = max(1, round(h * width / w))
    ii = np.zeros((h + 1, w + 1) + px.shape[2:])
    ii[1:, 1:] = px.cumsum(0).cumsum(1)
    ys = np.linspace(0, h, height + 1).round().astype(int)
    xs = np.linspace(0, w, width + 1).round().astype(int)
    y0, y1 = ys[:-1, None], np.maximum(ys[1:], ys[:-1] + 1)[:, None]
    x0, x1 = xs[None, :-1], np.maximum(xs[1:], xs[:-1] + 1)[None, :]
    y1, x1 = np.minimum(y1, h), np.minimum(x1, w)
    total = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
    area = ((y1 - y0) * (x1 - x0)).astype(float)
    if px.ndim == 3:
        area = area[..., None]
    return (total / area).astype(np.float32)


def picture_problems(px: np.ndarray, model_check: bool = True) -> list[str]:
    """What is wrong with a rendered picture (screen values 0..1): black, one flat colour, or (with
    ``model_check``, for pictures on a plain background) no model in it."""
    rgb = np.asarray(px, dtype=np.float32)[..., :3]
    problems = []
    if float(rgb.mean()) < 0.02:
        return ["the picture is black"]
    if float(rgb.std()) < 0.01:
        return ["the picture is one flat colour (empty)"]
    if model_check:
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
        bg = np.median(border, axis=0)
        differs = np.abs(rgb - bg).max(axis=-1) > 0.08
        share = float(differs.mean())
        if share < 0.01:
            problems.append("the model is not in the picture (only background)")
        elif share > 0.995:
            problems.append("the picture has no background left (the camera is inside the model?)")
    return problems


def contact_sheet(frames: list, cols: int = 4, width: int = 240, gap: int = 4) -> np.ndarray:
    """Several pictures side by side in a grid (rows top to bottom), each scaled to ``width`` pixels, with a
    thin grey gap: the Heavy report shows a video as a few frames across its length."""
    if not frames:
        raise ValueError("no pictures for the contact sheet")
    thumbs = [thumbnail(f[..., :3], width) for f in frames]
    h = max(t.shape[0] for t in thumbs)
    cols = max(1, min(cols, len(thumbs)))
    rows = -(-len(thumbs) // cols)
    sheet = np.full((rows * h + (rows + 1) * gap, cols * width + (cols + 1) * gap, 3), 0.5)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        y, x = gap + r * (h + gap), gap + c * (width + gap)
        sheet[y:y + t.shape[0], x:x + t.shape[1]] = t
    return sheet


def picture_difference(a: np.ndarray | None, b: np.ndarray | None) -> float | None:
    """Mean difference (0..1) of two thumbnails of the same size; None when they cannot be compared."""
    if a is None or b is None:
        return None
    a, b = np.asarray(a, np.float32)[..., :3], np.asarray(b, np.float32)[..., :3]
    if a.shape != b.shape:
        return None
    return float(np.abs(a - b).mean())


# ---------------------------------------------------------------------------
# the text block for the lead chat: numbers only
# ---------------------------------------------------------------------------

# a path: from its start (drive, \\server, ~/ or /) to its last separator, then the file name (with spaces
# up to its extension) or one word; generous on purpose: more text removed is fine, a name left in is not
_PATH = re.compile(r"""(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|(?<![\w.])/(?=[\w.~-]))
                       [^'"<>|\r\n]*[\\/]
                       (?:[^\\/'"<>|\r\n]{0,80}?\.[A-Za-z0-9]{1,5}\b|[^\s\\/'"<>|,;()]*)""", re.X)


def scrub(text: str, secrets=(), limit: int = 160) -> str:
    """``text`` without file paths and without any of ``secrets`` (file, part, user and computer names)."""
    text = _PATH.sub("<path>", " ".join(str(text or "").split()))
    for s in sorted({str(x) for x in secrets if x and len(str(x)) >= 3}, key=len, reverse=True):
        text = re.sub(re.escape(s), "<name>", text, flags=re.I)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _fmt_value(value, unit: str) -> str:
    if isinstance(value, float):
        txt = f"{value:.2f}" if abs(value) < 10 else f"{value:.1f}" if abs(value) < 100 else f"{value:.0f}"
    else:
        txt = str(int(value))
    return f"{txt} {unit}".strip()


def metric_text(metrics: dict) -> str:
    return ", ".join(f"{k} {_fmt_value(v, u)}" for k, (v, u) in metrics.items() if isinstance(v, (int, float)))


def text_block(run: Run, secrets=()) -> str:
    """The plain text the owner copies into the lead chat: version, PC, every line with its state and
    time, the flags. Lines on his own model carry numbers only: no reason text, no names."""
    pc = run.pc
    c = run.counts()
    out = [f"Fresing Render PC check {run.app_version} - {MODE_TITLES.get(run.mode, run.mode)}"
           f"{' + own model' if run.own_model else ''} - {run.date}"
           f"{'' if run.finished else ' - DID NOT FINISH'}{' - CANCELLED' if run.cancelled else ''}"
           f"{' - SCALED DOWN' if run.scaled else ''}",
           f"PC: {pc.get('cpu', '?')}, {pc.get('cores', '?')} cores, {pc.get('ram_gb', '?')} GB; "
           f"{pc.get('gpu', '?')}; driver {pc.get('driver', '?')}; {pc.get('os', '?')}; Blender {run.blender}",
           f"Result: {c[OK]} OK, {c[FAILED]} FAILED, {c[SKIPPED]} skipped in {run.seconds:.0f} s; "
           + (f"compared with {run.compared_with}" if run.compared_with else "first run of this kind on this PC")]
    order = sorted(run.results, key=lambda r: (r.id not in run.new_ids,))
    for r in order:
        tag = {OK: "[ OK ]", FAILED: "[FAIL]", SKIPPED: "[SKIP]"}.get(r.status, "[....]")
        new = "NEW " if r.id in run.new_ids else ""
        ref = f" (before {r.reference:.1f} s, {change_text(r.seconds, r.reference)})" if r.reference else ""
        row = f"{new}{tag} {r.id} {r.seconds:.1f} s{ref}"
        if r.metrics:
            row += " | " + metric_text(r.metrics)
        if r.status in (FAILED, SKIPPED):
            if r.own:
                row += f" | {r.error_type or 'error'}" if r.status == FAILED else " | skipped"
            else:
                row += " | " + scrub(r.reason, secrets)
        flags = [f for f in r.flags if f != "failed"]
        for p in r.pictures:
            if p.problems:
                flags.append("picture: " + "; ".join(p.problems))
        if flags:
            row += " | FLAG: " + ", ".join(sorted(set(flags)))
        out.append(row)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# the HTML report (stays on this PC)
# ---------------------------------------------------------------------------

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d232b;--muted:#5d6672;--line:#dfe3e8;--ok:#1e7d3a;--bad:#c0262d;
--skip:#7a6400;--new:#1f5fbf;--flag:#b35c00}
@media (prefers-color-scheme:dark){:root{--bg:#15181c;--card:#1f2329;--ink:#e6e9ed;--muted:#9aa3ad;
--line:#353b44;--ok:#5cc47a;--bad:#ff6b6b;--skip:#d9c25a;--new:#7fb0ff;--flag:#ffa94d}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
.sub{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.big{font-size:20px;font-weight:600}.ok{color:var(--ok)}.bad{color:var(--bad)}.skip{color:var(--skip)}
.flag{color:var(--flag);font-weight:600}.new{color:var(--new);font-weight:600}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:13px;color:var(--muted);font-weight:600}td.num{white-space:nowrap;text-align:right}
.what{color:var(--muted);font-size:13px}
.pics{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
.pics figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}
.pics figure.big{grid-column:1/-1;max-width:760px}
.pics img{width:100%;height:auto;display:block;border-radius:4px}.pics figcaption{font-size:13px;margin-top:4px}
textarea{width:100%;box-sizing:border-box;min-height:220px;font:12px/1.4 Consolas,monospace;
background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px}
button{font:inherit;padding:8px 18px;border-radius:6px;border:0;background:#2563c9;color:#fff;cursor:pointer}
details pre{white-space:pre-wrap;font-size:12px;color:var(--muted)}
.wrap{overflow-x:auto}
"""

_SCRIPT = """
function copyBlock(){var t=document.getElementById('block');t.select();var done=function(){
document.getElementById('copied').textContent='Copied - paste it into the lead chat.'};
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t.value).then(done,
function(){document.execCommand('copy');done()})}else{document.execCommand('copy');done()}}
"""


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _minutes(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds} s" if seconds < 90 else f"{seconds / 60:.0f} min"


def _status_html(r: Result) -> str:
    cls = {OK: "ok", FAILED: "bad", SKIPPED: "skip"}.get(r.status, "sub")
    label = {OK: "OK", FAILED: "FAILED", SKIPPED: "skipped", RUNNING: "running…"}.get(r.status, r.status)
    return f'<span class="{cls}">{label}</span>'


def _row(r: Result, new: bool) -> str:
    detail = []
    if r.note:
        detail.append(_e(r.note))
    if r.reason:
        detail.append(f'<span class="{"bad" if r.status == FAILED else "skip"}">{_e(r.reason)}</span>')
    if r.metrics:
        parts = []
        for k, (v, u) in r.metrics.items():
            ref = r.metric_refs.get(k)
            txt = f"{_e(k)}: {_e(_fmt_value(v, u) if isinstance(v, (int, float)) else v)}"
            if ref is not None and isinstance(v, (int, float)):
                txt += f" <span class='sub'>(before {_e(_fmt_value(ref, u))}, {change_text(float(v), ref)})</span>"
            parts.append(txt)
        detail.append("<br>".join(parts))
    for p in r.pictures:
        if p.problems:
            detail.append(f'<span class="flag">Picture "{_e(p.title)}": {_e("; ".join(p.problems))}</span>')
        if p.flagged:
            detail.append(f'<span class="flag">Picture "{_e(p.title)}" looks different from last time: '
                          f'look at it below</span>')
    if "slower" in r.flags:
        detail.append('<span class="flag">Slower than before</span>')
    if r.trace:
        detail.append(f"<details><summary>Details for the developer</summary><pre>{_e(r.trace)}</pre></details>")
    before = f"{r.reference:.1f} s" if r.reference is not None else ""
    change = change_text(r.seconds, r.reference)
    if r.reference is not None and is_faster(r.seconds, r.reference):
        change += " faster"
    tag = '<span class="new">NEW</span> ' if new else ""
    what = f"{_e(r.what)} · " if r.what else ""
    sn = ""
    if r.shows:
        sn += f"<div class='what'><b>Shows:</b> {_e(r.shows)}</div>"
    if r.not_shown:
        sn += f"<div class='what'><b>Does not show:</b> {_e(r.not_shown)}</div>"
    if r.status == RUNNING and r.started:
        el = max(0, time.time() - r.started)
        exp = f", expected about {_minutes(r.expected)}" if r.expected else ""
        sn += f"<div class='flag'>Running for {_minutes(el)}{exp}</div>"
    return (f"<tr><td>{tag}{_e(r.title)}<div class='what'>{what}since {_e(r.since)}</div>{sn}</td><td>{_status_html(r)}</td>"
            f"<td class='num'>{r.seconds:.1f} s</td><td class='num'>{_e(before)}</td>"
            f"<td class='num'>{_e(change)}</td><td>{'<br>'.join(detail)}</td></tr>")


def _table(results: list, new_ids: set) -> str:
    rows = "".join(_row(r, r.id in new_ids) for r in results)
    return ("<div class='wrap'><table><tr><th>Function</th><th>Result</th><th>Time</th><th>Before</th>"
            f"<th>Change</th><th>Details</th></tr>{rows}</table></div>")


def html_report(run: Run, block: str) -> str:
    c = run.counts()
    if not run.finished:
        head = '<span class="sub">Still running… this page updates itself every few seconds.</span>'
    elif run.cancelled:
        head = f'<span class="skip">Cancelled: the {len(run.results)} lines done so far are below</span>'
    elif c[FAILED]:
        head = f'<span class="bad">{c[FAILED]} of {len(run.results)} functions FAILED</span>'
    else:
        head = (f'<span class="ok">No problems: {c[OK]} functions work</span>'
                + (f' <span class="skip">({c[SKIPPED]} skipped)</span>' if c[SKIPPED] else ""))
    flags = sum(1 for r in run.results if [f for f in r.flags if f != "failed"]
                or any(p.flagged or p.problems for p in r.pictures))
    pc = run.pc
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        + ("" if run.finished else "<meta http-equiv='refresh' content='10'>"),
        f"<title>Fresing Render PC check</title><style>{_CSS}</style><script>{_SCRIPT}</script></head><body><main>",
        f"<h1>Fresing Render PC check {_e(run.app_version)}</h1>",
        f"<div class='sub'>{_e(MODE_TITLES.get(run.mode, run.mode))}{' + your own model' if run.own_model else ''}"
        f" · {_e(run.date)} · {run.seconds:.0f} s · {_e(pc.get('cpu', '?'))}, {_e(pc.get('cores', '?'))} cores · "
        f"{_e(pc.get('gpu', '?'))}, driver {_e(pc.get('driver', '?'))} · Blender {_e(run.blender)}</div>",
        f"<div class='card' style='margin-top:14px'><div class='big'>{head}</div>",
        f"<div>{c[OK]} OK · {c[FAILED]} failed · {c[SKIPPED]} skipped"
        + (f" · <span class='flag'>{flags} to look at</span>" if flags else "")
        + (f" · times compared with {_e(run.compared_with)}" if run.compared_with else
           " · first run of this kind on this PC: the next run compares its times with this one") + "</div></div>",
    ]
    if not run.finished:
        todo = f"Still to do: {_e(', '.join(run.planned))}. " if run.planned else ""
        parts.append(f"<p class='sub'>{todo}To stop the check: in Blender Help &gt; Cancel Fresing Render PC "
                     "check (or press Ctrl+C in its window); the lines done so far stay in this report.</p>")
    new = [r for r in run.results if r.id in run.new_ids]
    if new:
        parts += ["<h2>New in this version</h2>", _table(new, run.new_ids)]
    look = [r for r in run.results if r.id not in run.new_ids and (r.status == FAILED or r.flags
            or any(p.flagged or p.problems for p in r.pictures))]
    if look:
        parts += ["<h2>Look at these</h2>", _table(look, run.new_ids)]
    parts += ["<h2>Every function</h2>", _table(run.results, run.new_ids)]
    pics = [(r, p) for r in run.results for p in r.pictures if p.thumb_png]
    if pics:
        parts.append("<h2>Pictures</h2><div class='pics'>")
        for r, p in pics:
            src = "data:image/png;base64," + base64.b64encode(p.thumb_png).decode("ascii")
            note = ""
            if p.problems:
                note = f" <span class='flag'>{_e('; '.join(p.problems))}</span>"
            elif p.flagged:
                note = f" <span class='flag'>differs from last time ({p.difference:.2f})</span>"
            elif p.difference is not None:
                note = f" <span class='sub'>same as last time ({p.difference:.3f})</span>"
            big = " class='big'" if p.width > THUMB_WIDTH else ""
            sets = f"<br><span class='sub'>{_e(p.settings)}</span>" if p.settings else ""
            parts.append(f"<figure{big}><img src='{src}' alt='{_e(p.title)}'><figcaption>{_e(p.title)}{note}"
                         f"{sets}</figcaption></figure>")
        parts.append("</div>")
    parts += ["<h2>For the lead chat</h2>",
              "<p>Copy this block and paste it into the lead chat. It holds numbers only: no file names, "
              "part names or pictures.</p>",
              f"<textarea id='block' readonly>{_e(block)}</textarea>",
              "<p><button onclick='copyBlock()'>Copy</button> <span id='copied' class='ok'></span></p>",
              "</main></body></html>"]
    return "\n".join(parts)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def parse_args(argv: list) -> dict:
    """Arguments after Blender's "--": the Desktop folder, "quick" / "full", a STEP file (dropped on the
    shortcut or picked in the app). Any order; unknown words are ignored."""
    out = {"desktop": "", "mode": "quick", "model": ""}
    for a in argv:
        low = a.strip().lower()
        if low in MODES:
            out["mode"] = low
        elif low.endswith((".step", ".stp")) and os.path.isfile(a):
            out["model"] = a
        elif os.path.isdir(a) and not out["desktop"]:
            out["desktop"] = a
    return out
