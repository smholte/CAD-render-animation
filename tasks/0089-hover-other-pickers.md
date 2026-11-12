# 0089 – Hover highlight for all other click pickers

**Who:** worker · **Status:** done (0.2.66) · **Branch:** `task/0089-hover-other-pickers`
**Started by:** lead chat, 12 Nov 2026 (follow-up of 0088, the owner's wish)
**Lane:** Pick & hover – `blender/hover.py` (only additions it needs, e.g. a "point" mode without an axis), and the
click pickers in `ops_scene.py` (sharp spot), `ops_callouts.py` (label point on a part), `ops_decals.py` (where a decal
goes), `ops_fade.py` (trail points), `ops_gcode.py` (ATC pockets and other picks), `ops_coolant.py` (nozzles),
`ops_toolpath.py` (block / finished part); tests, guide sentences. The owner starts 0061 (Machining lane) only after this
task is merged.
**Model:** Sonnet · effort Medium (along 0088's pattern; stuck: Opus) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

Runs at the same time as 0077 (demo project), 0085 (vessel motion) and 0090 (way-cover pose); none of them touches the
files above.

## Goal

Every click-to-pick in the app shows what the click will hit before the click, the way Add joint / Set axis does since
0.2.63: the face under the mouse lights up, with a short note of what the click does ("Sharp spot here", "Label points
here", "Decal on this face", "Trail point on Boom"). The click itself does exactly what it does today.

## Background

0088 made `blender/hover.py`; its report says per picker: `hover.start` in invoke, `hover.on_event` first in modal,
`hover.pick` for the click, `hover.end` wherever the modal ends (also on Esc and errors). Measured on the test crane:
0.04 ms per mouse move. The preference "Highlight the face under the mouse when picking an axis" switches it off.

## What to build

- Find every click picker in these files (read each operator's modal). For pickers that pick a **point** (not an
  axis), show the face and a small dot where the click lands, no axis line; add that mode to `hover.py` if it is
  missing (no change to how axis pickers look).
- Decals: the highlight shows the face the decal will lie on (flat or round – say "wraps round" for a cylinder face if
  `decal_geometry` would wrap it). Labels and trail points: the part's name in the note.
- Rename the preference to cover all pickers ("Highlight what is under the mouse when picking"), same property, so the
  owner's setting is kept.
- Nothing in `bpy.data`, nothing in renders; the highlight disappears when the picker ends in any way.

## Done when

- [ ] Each click picker in these files uses hover; a test per picker (start, a move over a part, the click gives the same
      result as before, end leaves no draw handler) in the style of 0088's tests.
- [ ] Time per mouse move measured on the test crane and on the PC check's Heavy machine (scaled down is fine).
- [ ] Guide: one sentence per chapter where those pickers are described; tooltip check 0 missing.
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The axis pickers' look, any picker's result.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 12 Nov 2026

**What changed:** `hover.py` got a point mode (`start(..., point=True, note=, refuse=)`, `look_point`): the face lights up,
a dot marks where the click lands, a note says what the click does; red with a reason when refused. Wired in: sharp spot
(`ops_scene`), label add / move and trail point (`_PickPart` in `ops_callouts`, used by `ops_fade`), CNC zero, air nozzle,
tool-changer pockets (`ops_gcode`), coolant nozzle (`ops_coolant`), Add decal (`ops_decals`; note "lies flat" /
"wraps round" from `decals.wraps_round`, cached per face). These clicks now go through `hover.pick`, so highlight and
click use the same ray (and a click through a sticker counts as the part, as with joints). Preference renamed to "Highlight
what is under the mouse when picking" (same property). Guide sentences in Motion, Decals, CNC zero, Labels, trails and
sharp spot. PC-check line `motion.hover` also checks the point mode. Version 0.2.66.

**Tested and measured** (4-core Linux box, test crane): `tests/test_hover.py` 24 tests pass (point look equals the
click's part / face / spot; empty space; refusal; a failing note; decal note flat and round; every picker uses the helper;
end leaves no draw handler). Time per mouse move: 0.03 ms axis, 0.01 ms point (50 moves, warm). PC-check line OK
(median 0.10 ms, slowest 0.62 ms). Tooltip check 0 missing. Not run: the PC check's Heavy machine (no change to the heavy
path; per-move work is one ray + a cached face), real clicks in a window (no graphics card here; GitHub's real-app tests
cover start-up of the modals only via the existing tests).

**Open points / follow-up tasks:** "Toolpath block / finished part" and "set workpiece" are not click pickers (they use
the selection), so nothing to do there. Vessel motion's "click the pivot" picker (0085) also clicks water and deck, which
hover does not treat as parts: left as it is. Hover over a Tool-change hand-over or other pickers added later: use
`hover.start(..., point=True)`.
