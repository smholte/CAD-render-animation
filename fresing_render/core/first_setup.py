"""The first-start set-up's rules (task 0276), no Blender: its steps, the languages it offers, the work ticks and the
workspace they give, the hub chapter they suggest, the PC lines read from the PC check's Quick lines, and what a
company's set-up file says about it.

Every choice the set-up makes is one that already exists (Fresing Settings, Locations, Blender's own preferences):
the set-up only asks them in order. The ticks of step 2 are kept in the start file (``core/start.py``) – nothing
leaves the PC.
"""

from __future__ import annotations

STEPS = (("welcome", "Welcome"), ("work", "Your work"), ("pc", "Your PC"), ("company", "Company"),
         ("hub", "Learning hub"), ("done", "Done"))          # (key, the step bar's title)
STEP_KEYS = tuple(k for k, _t in STEPS)
HEADINGS = {"company": "Your company and your folders"}      # a step's heading where it is longer than its title

# Fresing Render's own texts are English; another language changes only Blender's menus under them. These are the
# languages whose part names the app's sorting rules also read (English, Dutch, German: CLAUDE.md, part library).
LANGUAGES = (("en_US", "English", "Fresing Render and Blender in English (recommended)"),
             ("nl_NL", "Nederlands", "Blender's own menus in Dutch; Fresing Render's texts stay English"),
             ("de_DE", "Deutsch", "Blender's own menus in German; Fresing Render's texts stay English"))
LANGUAGE_KEYS = tuple(k for k, _t, _d in LANGUAGES)

# (key, title, workspace key of core/workspaces.BUILTIN, Learning-hub chapter of tour.GROUPS)
WORK = (("cnc", "CNC & machining", "cnc", "Machining"),
        ("offshore", "Offshore & cable laying", "offshore", "Motion"),
        ("product", "Product design & R&D", "product", "Look"),
        ("lifting", "Lifting plans", "lifting", "Motion"),
        ("education", "Education & training", "education", "Look"),
        ("sales", "Sales / presentations", "sales", "Output"),
        ("animator", "Animation", "animator", "Motion"),
        ("quick", "Just pictures of my models", "quick", "Output"),
        ("reviewer", "Looking at models others made", "reviewer", "Look"),
        # task 0321: the workspaces of round 3
        ("welding", "Welding and fabrication", "welding", "Look"),
        ("builder", "Making machines move", "builder", "Motion"),
        ("video", "Videos of machines", "video", "Output"),
        ("houses", "Houses from House Planner", "houses", "Output"))
WORK_KEYS = tuple(w[0] for w in WORK)
BY_WORK = {w[0]: w for w in WORK}

RULE = ("No tick: Essentials (the start – a first picture and a simple motion). One tick: its own workspace. Two or "
        "more: All functions. Change it any time at the top of the Fresing tab or in Fresing Settings > General.")

# the PC check's Quick lines the set-up runs (task 0276: the PC part of Quick – no video, a few seconds' work)
PROBE_LINES = ("app.start", "gpu.device", "pc.gpu", "import.crane", "render.gpu")
PROBE_ENV = "FRESING_SETUP_PROBE_LINES"          # tests: a shorter list ("app.start" alone)
SLOW_HD_S = 30.0                                 # an HD still on the graphics card slower than this: a slow card
FEW_CORES = 6
LITTLE_RAM = 16

SKIP_VALUE = "skip"                              # a set-up file's "first_setup": "skip" – managed PCs start straight in


def workspace_for(ticks) -> tuple[str, str]:
    """(workspace name for "Workspace for new projects", why) from the ticked work. '' = not chosen = Essentials."""
    from . import workspaces as W
    ticks = [t for t in ticks if t in BY_WORK]
    if not ticks:
        return "", "No tick: new projects start in Essentials"
    if len(ticks) == 1:
        name = W.NAMES[BY_WORK[ticks[0]][2]]
        return name, f"One tick: new projects start in {name}"
    return W.DEFAULT, f"{len(ticks)} ticks: new projects start in {W.DEFAULT}"


def ticks_for(workspace: str) -> list:
    """The ticks that give ``workspace`` (a set-up file that names a workspace pre-fills step 2)."""
    from . import workspaces as W
    key = W.key_of(workspace) if workspace else ""
    return [w[0] for w in WORK if w[2] == key]


def chapter_for(ticks) -> str:
    """The Learning hub's chapter to open first for this work ('' = the hub's own first)."""
    for t in ticks:
        if t in BY_WORK:
            return BY_WORK[t][3]
    return ""


def language_ok(code: str) -> bool:
    return code in LANGUAGE_KEYS


# ---------------------------------------------------------------------------
# step 3: the PC in plain words
# ---------------------------------------------------------------------------

def _row(probe: dict, line_id: str) -> dict:
    return next((r for r in probe.get("results", []) if r.get("id") == line_id), {})


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def pc_summary(probe: dict) -> dict:
    """What the set-up says about this PC from the probe's results (``first_setup_probe.py``'s file):
    {"lines": [(icon, text)], "gpu": bool, "live_preview": bool, "quality": str, "slow": str}."""
    pc = probe.get("pc") or {}
    dev, used, render = _row(probe, "gpu.device"), _row(probe, "pc.gpu"), _row(probe, "render.gpu")
    gpu = dev.get("status") == "OK"
    lines = []
    if gpu:
        lines.append(("CHECKMARK", f"Graphics card found: {dev.get('note') or 'yes'}"))
    elif dev:
        lines.append(("INFO", "No graphics card Cycles can render on: pictures are rendered on the processor"))
    if used.get("status") == "FAILED" and used.get("reason"):
        lines.append(("ERROR", used["reason"]))
    elif used.get("status") == "OK" and used.get("note"):
        lines.append(("CHECKMARK", used["note"]))
    lines.append(("RENDER_STILL", "Renders on: " + ("the graphics card" if gpu else "the processor")))
    hd = None
    if render.get("status") == "OK":
        hd = _num((render.get("metrics") or {}).get("render", [None])[0], None)
        if hd is not None:
            lines.append(("TIME", f"A picture of the test crane at HD took {hd:.0f} s"))
    cores, ram = int(_num(pc.get("cores"))), int(_num(pc.get("ram_gb")))
    if cores or ram:
        parts = []
        if pc.get("cpu"):
            parts.append(str(pc["cpu"]))
        if cores:
            parts.append(f"{cores} cores")
        if ram:
            parts.append(f"{ram} GB memory")
        lines.append(("DESKTOP", "Processor: " + ", ".join(parts)))
    slow = []
    if not gpu:
        slow.append("no graphics card for renders")
    elif hd is not None and hd > SLOW_HD_S:
        slow.append("the graphics card is slow")
    if cores and cores < FEW_CORES:
        slow.append(f"only {cores} processor cores")
    if ram and ram < LITTLE_RAM:
        slow.append(f"only {ram} GB memory")
    fast = gpu and not slow
    return {"lines": lines, "gpu": gpu, "live_preview": bool(fast),
            "quality": "Final" if gpu else "Preview while you work, Final for the last picture",
            "suggest": ("Live preview: on – it renders the view as you work. Render quality: Final."
                        if fast else
                        "Live preview: off – switch it on top left when you want to see the real look. Render "
                        "quality: Preview while you work, Final for the last picture."),
            "slow": ("Big models will be slow on this PC: " + ", ".join(slow) + ".") if slow else ""}


def probe_failed_text(probe: dict) -> str:
    """'' when the probe ran; else why not, in plain words."""
    if probe.get("error"):
        return f"The PC check did not run: {probe['error']}"
    if not probe.get("results"):
        return "The PC check gave no answer"
    bad = _row(probe, "app.start")
    if bad.get("status") == "FAILED":
        return f"The PC check found a problem: {bad.get('reason', '')}"
    return ""


# ---------------------------------------------------------------------------
# a company's set-up file
# ---------------------------------------------------------------------------

def from_setups(first_starts) -> dict:
    """What the set-up files in use say about the first start (``Setup.first_start`` of each, company first):
    {"skip": bool, "workspace": str, "work": [...], "language": str}."""
    out = {"skip": False, "workspace": "", "work": [], "language": ""}
    for fs in first_starts:
        if not isinstance(fs, dict):
            continue
        if str(fs.get("first_setup", "")).strip().lower() == SKIP_VALUE or fs.get("skip") is True:
            out["skip"] = True
        ws = fs.get("workspace")
        if isinstance(ws, str) and ws.strip() and not out["workspace"]:
            out["workspace"] = ws.strip()
        work = fs.get("work")
        if isinstance(work, list) and not out["work"]:
            out["work"] = [w for w in work if w in BY_WORK]
        lang = fs.get("language")
        if isinstance(lang, str) and language_ok(lang) and not out["language"]:
            out["language"] = lang
    return out
