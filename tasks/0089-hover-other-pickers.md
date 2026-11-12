# 0089 – Hover highlight for the other click pickers (sharp spot, labels, decals, trail points)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0089-hover-other-pickers`
**Started by:** lead chat, 12 Nov 2026 (follow-up of 0088, the owner's wish)
**Lane:** Pick & hover – `blender/hover.py` (only additions it needs, e.g. a "point" mode without an axis), and the
click pickers in `ops_scene.py` (sharp spot), `ops_callouts.py` (label point on a part), `ops_decals.py` (where a decal
goes), `ops_fade.py` (trail points); tests, guide sentences. **Not** the Machining-lane pickers (ATC pockets in
`ops_gcode.py`, coolant nozzles in `ops_coolant.py`, toolpath parts in `ops_toolpath.py`): they wait for 0061.
**Model:** Sonnet · effort Medium (along 0088's pattern; stuck: Opus) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

Runs at the same time as 0077 (demo project), 0085 (vessel motion), 0090 (way-cover pose) and the Fable tasks 0058 and
0061. None of them touches the files above.

## Goal

Every click-to-pick in the app shows what the click will hit before the click, the way Add joint / Set axis does since
0.2.63: the face under the mouse lights up, with a short note of what the click does ("Sharp spot here", "Label points
here", "Decal on this face", "Trail point on Boom"). The click itself does exactly what it does today.

## Background

0088 made `blender/hover.py`; its report says per picker: `hover.start` in invoke, `hover.on_event` first in modal,
`hover.pick` for the click, `hover.end` wherever the modal ends (also on Esc and errors). Measured on the test crane:
0.04 ms per mouse move. The preference "Highlight the face under the mouse when picking an axis" switches it off.

## What to build

- Find every click picker in the four files (read each operator's modal). For pickers that pick a **point** (not an
  axis), show the face and a small dot where the click lands, no axis line; add that mode to `hover.py` if it is
  missing (no change to how axis pickers look).
- Decals: the highlight shows the face the decal will lie on (flat or round – say "wraps round" for a cylinder face if
  `decal_geometry` would wrap it). Labels and trail points: the part's name in the note.
- Rename the preference to cover all pickers ("Highlight what is under the mouse when picking"), same property, so the
  owner's setting is kept.
- Nothing in `bpy.data`, nothing in renders; the highlight disappears when the picker ends in any way.

## Done when

- [ ] Each picker in the four files uses hover; a test per picker (start, a move over a part, the click gives the same
      result as before, end leaves no draw handler) in the style of 0088's tests.
- [ ] Time per mouse move measured on the test crane and on the PC check's Heavy machine (scaled down is fine).
- [ ] Guide: one sentence per chapter where those pickers are described; tooltip check 0 missing.
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The Machining-lane pickers (after 0061), the axis pickers' look, any picker's result.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
