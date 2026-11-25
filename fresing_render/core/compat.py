"""Compatibility kit (task 0352): the project format number, the one chain of upgrade steps, the saved-data list and
the comparisons the test projects use. No Blender here (``blender/compat.py`` is the Blender side).

* **The format number.** ``FORMAT`` is stamped on every local scene at every save (also an automatic backup and the
  render queue's copy) as two plain custom properties – ``fr_format`` (int) and ``fr_saved_by`` (the app version) –
  never as fields of the app's property groups, so ANY version of the app can read them, whatever its settings look
  like. A project without the stamp was saved before the kit (0.2.261). A file's format = the highest stamp of its
  local scenes (a scene linked from a library is not this file's).
* **What raises it.** A change in what a project stores (a new, renamed or re-meant choice) raises ``FORMAT`` by one
  and adds ONE step to ``STEPS`` (from the old number to the new one) plus the test project of the new number
  (``tools/make_compat_project.py``). Derived data – bakes, caches, meshes the app makes, cable shapes, liquid, baked
  light, the keys of a built animation – is rebuilt from the choices and never gets a step (CLAUDE.md section 6).
* **The baseline.** ``BASELINE_FORMAT`` is None until the lead releases the baseline (CLAUDE.md section 6). Below the
  baseline, or without a stamp, the chain does nothing: today's per-lane load code still runs until the cleanups 0350
  remove it. From the baseline on every kept project is at least at the baseline's number, and the chain carries it to
  ``FORMAT`` before any other Fresing load handler runs.
* **A project from a newer app** (its format above ``FORMAT``) opens to look at only: saving it over itself is refused
  (and Blender's own save keeps the newer file aside first), no backup, no render queue, no model update.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

FORMAT = 1                     # the project format this app writes; raise by one per change of what a project stores
BASELINE_FORMAT = None         # the baseline's format number, set by the lead when the baseline is released

STAMP = "fr_format"            # scene custom property: the format the project was saved in (int)
STAMP_APP = "fr_saved_by"      # scene custom property: the app version that saved it ("0.2.261")


# ---------------------------------------------------------------------------
# the chain of upgrade steps
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Step:
    """One upgrade step: a project at ``from_format`` comes out at ``to_format`` (= from_format + 1).

    ``function`` = "module:function" inside ``fresing_render.blender`` (resolved only when it runs, so this list is
    plain data the precheck can read). It runs ONCE per file and gets the list of local scenes that are below
    ``to_format`` (objects, meshes, materials two scenes share are one datablock: change each once). It must be safe
    to run again on its own output (a later step failing makes the next open run the chain from the last format
    reached). ``changes`` = the summary paths the step changes on purpose ("scenes.Scene.settings.fresing.x") – the
    test projects' comparison allows exactly those."""

    from_format: int
    to_format: int
    name: str
    function: str
    changes: tuple = ()


STEPS: tuple = ()               # empty until the first change after the baseline (every kept project is at it then)


def chain_problems(steps=None, fmt: int | None = None, baseline=None, *, check_baseline: bool = True) -> list[str]:
    """What is wrong with a chain (the precheck and the tests): steps out of order, a step that does not go up by
    exactly one, two steps from one number, a gap between the baseline and ``fmt``, a step above ``fmt``."""
    steps = STEPS if steps is None else tuple(steps)
    fmt = FORMAT if fmt is None else fmt
    baseline = BASELINE_FORMAT if (baseline is None and check_baseline) else baseline
    out = []
    if not isinstance(fmt, int) or fmt < 1:
        out.append(f"FORMAT must be a whole number of 1 or more, not {fmt!r}")
        return out
    if baseline is not None and (not isinstance(baseline, int) or not 1 <= baseline <= fmt):
        out.append(f"BASELINE_FORMAT {baseline!r} must be a whole number between 1 and FORMAT ({fmt})")
        return out
    seen = set()
    last = None
    for s in steps:
        if not isinstance(s, Step):
            out.append(f"{s!r} is not a Step")
            continue
        if s.to_format != s.from_format + 1:
            out.append(f"step '{s.name}' goes from {s.from_format} to {s.to_format}: one step raises the format by one")
        if s.from_format in seen:
            out.append(f"two steps start at format {s.from_format} ('{s.name}' is the second)")
        seen.add(s.from_format)
        if last is not None and s.from_format < last:
            out.append(f"step '{s.name}' is out of order: the steps go from the lowest format up")
        last = s.from_format
        if s.to_format > fmt:
            out.append(f"step '{s.name}' goes to format {s.to_format}, above FORMAT ({fmt})")
        if ":" not in s.function:
            out.append(f"step '{s.name}': function must be 'module:function' inside fresing_render.blender")
    if baseline is not None:
        for n in range(baseline, fmt):
            if n not in seen:
                out.append(f"no upgrade step from format {n} to {n + 1}: FORMAT was raised without its step in "
                           "core/compat.py STEPS")
    return out


def plan(found, steps=None, fmt: int | None = None, baseline=None, *, use_baseline: bool = True) -> list:
    """The steps a project stamped ``found`` needs, in order: none without a stamp, below the baseline (or no
    baseline yet), at or above ``fmt``."""
    steps = STEPS if steps is None else tuple(steps)
    fmt = FORMAT if fmt is None else fmt
    baseline = BASELINE_FORMAT if (baseline is None and use_baseline) else baseline
    if not isinstance(found, int) or isinstance(found, bool) or baseline is None or found < baseline or found >= fmt:
        return []
    return sorted((s for s in steps if s.from_format >= found and s.to_format <= fmt), key=lambda s: s.from_format)


def run(steps, call, say=print) -> tuple[list, list]:
    """Run ``steps`` in order with ``call(step)``, each in its own try / except: a failing step gives one plain line
    and never stops the project from opening (as handlers._on_load since 0055). Unlike _on_load's independent
    per-lane upgrades, the chain's steps build on each other – step n+1 expects data at format n+1 –, so the chain
    stops at a failing step and the project stays at the format it reached (a fixed version tries again).
    Returns (names done, names failed)."""
    done, failed = [], []
    steps = list(steps)
    for i, s in enumerate(steps):
        try:
            call(s)
            done.append(s.name)
        except Exception as exc:  # noqa: BLE001 - the project opens whatever a step does
            failed.append(s.name)
            rest = len(steps) - i - 1
            say(f"Fresing Render: upgrade step '{s.name}' ({s.from_format} → {s.to_format}) failed: {exc}"
                + (f" – the {rest} step(s) after it wait for a fixed version" if rest else ""))
            break
    return done, failed


def as_format(value) -> int | None:
    """A stamp's value as a format number (None: no stamp or not a number – an unreadable stamp counts as none)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, float) and value.is_integer() and value >= 1:
        return int(value)
    if isinstance(value, str) and value.strip().isdigit() and int(value) >= 1:
        return int(value)
    return None


def file_format(stamps) -> int | None:
    """The file's format from its local scenes' stamps: the highest readable one (None: no scene has one)."""
    nums = [n for n in (as_format(v) for v in stamps) if n is not None]
    return max(nums) if nums else None


def is_newer(found, fmt: int | None = None) -> bool:
    fmt = FORMAT if fmt is None else fmt
    n = as_format(found)
    return n is not None and n > fmt


def newer_note(saved_by: str, this_version: str) -> str:
    """The plain message for a project from a newer app (task 0352 step 4)."""
    by = (saved_by or "").strip() or "a newer version"
    head = f"Saved by Fresing Render {by}" if by[0].isdigit() else f"Saved by {by} of Fresing Render"
    return (f"{head}, newer than this one ({this_version}). Update the app to work on it – Fresing > Check for "
            "updates. Saving is off so nothing in it is lost.")


def aside_name(path: str, saved_by: str, exists=os.path.exists) -> str:
    """Where Blender's own save keeps the newer file before it writes over it: "<name> (Fresing Render 0.2.X).blend"
    next to it, " (2)", " (3)" … when that is taken."""
    folder, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    tag = f"Fresing Render {saved_by}" if saved_by else "newer Fresing Render"
    tag = "".join(c for c in tag if c not in '<>:"/\\|?*')
    cand = os.path.join(folder, f"{stem} ({tag}){ext or '.blend'}")
    n = 2
    while exists(cand):
        cand = os.path.join(folder, f"{stem} ({tag}) ({n}){ext or '.blend'}")
        n += 1
    return cand


def same_path(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return os.path.normcase(os.path.realpath(os.path.abspath(a))) == os.path.normcase(os.path.realpath(os.path.abspath(b)))


# ---------------------------------------------------------------------------
# which function families store data (the test project must cover each)
# ---------------------------------------------------------------------------

FAMILY_DATA = {             # family (core/functions.FAMILIES) -> does a project store choices of it?
    "import": True,         # models, groups, structure, rules, excluded parts
    "looks": True,          # materials, colours, painted faces, decals, welds, finishes
    "motion": True,         # joints, couplings, poses, saved scenes, lead motions
    "machines": True,       # cylinders, mechanisms, way covers, hoses, tracks
    "cnc": True,            # the CNC machine, tools, rotary axes, tool changes
    "milling": True,        # the milling set-up, toolpath settings, chips
    "offshore": True,       # cables, drums, sea, vessel motion
    "scene": True,          # surroundings, light looks, cameras, picture settings
    "animation": True,      # animations and their steps
    "video": True,          # brand kit, labels, picture cards, music
    "queue": True,          # render-queue jobs
    "web": True,            # the web 3D model's settings
    "house": True,          # a house scene's import and bake settings
    "lifting": True,        # the lifting plan: cranes, loads, rigging
    "help": False,          # self-test, PC check, updates, guide: nothing in the project
    "panel": True,          # the project's workspace and its ticks
}


def family_problems(families: dict, covered) -> list[str]:
    """Every family of ``core/functions.FAMILIES`` is sorted into FAMILY_DATA, and every family that stores data is
    ``covered`` by the test project's maker."""
    out = []
    for fam in families:
        if fam not in FAMILY_DATA:
            out.append(f"family '{fam}' is not in core/compat.py FAMILY_DATA: say whether a project stores its choices")
    for fam in FAMILY_DATA:
        if fam not in families:
            out.append(f"FAMILY_DATA names '{fam}', which is not a family of core/functions.py")
    covered = set(covered)
    for fam, stores in FAMILY_DATA.items():
        if stores and fam in families and fam not in covered:
            out.append(f"the test project (tools/make_compat_project.py) has nothing of the family '{fam}', which "
                       "stores data: add a test-tour set that shows one of its functions to COMPAT_SETS")
    return out


# ---------------------------------------------------------------------------
# the summary of a project's stored choices, and comparing two of them
# ---------------------------------------------------------------------------

# Settings that are not choices: messages, progress, UI state, measured or worked-out values. The summary leaves them
# out. "<PropertyGroup class>.<property>" (exact: a name means one setting of one group); a bare name only for the
# few that are never a choice in any group (a test checks no bare name hides a collection of choices).
NOT_CHOICES = frozenset({
    "last_message", "progress", "progress_text", "busy", "running", "error",
    # the scene's own group: UI state and what an import / Build / the queue worked out
    *(f"FRSceneSettings.{p}" for p in (
        "panels_open", "saved_by", "rendered_once", "next_hidden", "last_render", "tree", "found", "unmatched",
        "model_count", "bounds_valid", "bounds_min", "bounds_max", "anim_baked", "queue_dir", "queue_pid",
        "report_new", "report_missing", "report_notes", "report_title")),
    "FRQueueJob.status", "FRQueueJob.message", "FRMechanism.status", "FRLifting.message", "FRCraneSetup.message",
    "FRClash.rows", "FRClash.signature", "FRToolpath.result", "FRToolpath.program_sig",
    "FRMilling.stock_mesh", "FRMilling.cut_mesh", "FRMilling.path_sig", "FRWeld.cad_mesh",
    "FRLiftLoad.rig_result", "FRLiftLoad.volume_mass", "FRCraneGroup.volume_mass",
    "FRWeb3D.last_path", "FRWeb3D.last_html", "FRWeb3D.last_text", "FRWeb3D.last_size",
    "FRHouse.last_bake", "FRHouse.last_seconds", "FRHouse.last_problems", "FRHouse.last_text",
})


def not_a_choice(group_class: str, prop: str) -> bool:
    return prop in NOT_CHOICES or f"{group_class}.{prop}" in NOT_CHOICES


def round_value(v):
    """Numbers as they compare between two reads: floats to 6 significant digits (float32 settings)."""
    if isinstance(v, bool) or v is None or isinstance(v, (int, str)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return str(v)
        return float(f"{v:.6g}")
    if isinstance(v, dict):
        return {str(k): round_value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [round_value(x) for x in v]
    return str(v)


def compare(old, new, allowed=(), path: str = "") -> list[str]:
    """Differences that matter between a stored summary ``old`` and one read later ``new``: everything ``old`` has must
    be in ``new`` with the same value (a newer version may ADD settings). ``allowed``: path prefixes a chain step
    changes on purpose (``Step.changes``). Returns plain lines, [] = the same."""
    out: list[str] = []
    if any(path == a or path.startswith(a + ".") or path.startswith(a + "[") for a in allowed if a):
        return out
    if isinstance(old, dict):
        if not isinstance(new, dict):
            return [f"{path or '(top)'}: was a group, now {type(new).__name__}"]
        for k, v in old.items():
            p = f"{path}.{k}" if path else str(k)
            if k not in new:
                if not any(p == a or p.startswith(a + ".") for a in allowed if a):
                    out.append(f"{p}: gone")
                continue
            out += compare(v, new[k], allowed, p)
        return out
    if isinstance(old, list):
        if not isinstance(new, list):
            return [f"{path}: was a list, now {type(new).__name__}"]
        if len(old) != len(new):
            out.append(f"{path}: {len(old)} items, now {len(new)}")
        for i, (a, b) in enumerate(zip(old, new)):
            out += compare(a, b, allowed, f"{path}[{i}]")
        return out
    if isinstance(old, float) and isinstance(new, (int, float)) and not isinstance(new, bool):
        if not math.isclose(old, float(new), rel_tol=2e-6, abs_tol=1e-9):
            out.append(f"{path}: {old!r} -> {new!r}")
        return out
    if old != new:
        out.append(f"{path}: {old!r} -> {new!r}")
    return out


def picture_difference(a, b) -> float:
    """Mean absolute difference of two pictures (numbers 0 … 1, same shape); 1.0 when the shapes differ."""
    import numpy as np
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.shape != b.shape:
        return 1.0
    return float(np.abs(a - b).mean()) if a.size else 0.0


PICTURE_TOLERANCE = 0.02       # mean difference per channel (0 … 1) a later version may show: noise, not a new look

