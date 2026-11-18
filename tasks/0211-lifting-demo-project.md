# 0211 – Demo project "Lifting site": a full lift plan in depth

**Who:** worker · **Status:** waiting – starts when Lifting L7 (printed plan + 2D / DXF) is done; its offshore stage
after L9 · **Branch:** `task/0211-lifting-demo-project`
**Started by:** lead, 18 Nov 2026 (owner's wish) · **Model:** Opus · effort High (the lead checks the size when it
writes the full brief: it may become two tasks – site + crane build-up first, the lift + outputs second)
**Area:** Demo models lane – new files only: a maker in a new package `fresing_render/demo_lifting/` (the pattern of
`fresing_render/demo_model/`), `tools/make_demo_lifting.py`, `tests/test_demo_lifting*.py`; additive: a second choice
under Help > Make demo project… / Open demo project (`blender/demo.py`, `ops_demo.py`: the cable-lay demo stays as it
is), its own stages (`@stage`). Reads the Lifting lane's functions (place, Hook to here, rigging, path, checks, plan);
never changes them – a fault found there goes back to the Lifting lane as a follow-up.

**This file is a placeholder.** The lead writes the full brief when L7 is done (the functions it shows must exist
first). Until then: each Lifting task L5–L9 keeps adding its own tour stops as now (the small demos per function).

## Goal

The owner's wish (18 Nov 2026): when the Lifting plans are further, one **full-depth demo** that shows everything
the workspace can do on one realistic invented site – like the cable-lay vessel demo does for cables: a site with
buildings, cranes that are built up there, something heavy being lifted, and the plan that comes out of it.

## What it should hold (first list – the lead completes it in the brief)

1. **The site:** an invented port / industrial yard – a hall and an office building, fences, roads, light masts, an
   overhead power line or a building edge as the obstacle the lift must clear, the quay edge, parked trucks, stacked
   containers, people at work (0157) and the exclusion zone round the lift.
2. **Crane build-up on site** (owner: "crane buildings" – the lead reads this as both the buildings round the crane
   and the crane being built up; ask the owner at brief time): a mobile crane drives in, sets its outriggers on mats;
   a crawler crane is assembled by it – boom sections pinned, counterweight slabs lifted on, boom raised (assist
   lifts, each checked).
3. **The main lift:** a heavy invented load (for example a transition piece, a cable reel or a process module – never
   anything of the owner's employer, never the Fresing 400), slung with real rigging (L5: slings, shackles, spreader,
   wire rope with several falls), tag lines, lifted along a path over the obstacle (L6), live checks with the worst
   moment (crane use %, sling forces, ground pressure under the pads / tracks, clearances), the lift data box.
4. **Smaller lifts beside it:** a forklift and a telehandler moving parts (L8), a chain hoist in the hall.
5. **What comes out:** the printed plan (PDF) with the 2D drawings per step and the DXF export (L7), a video with
   captions ("What a lifting plan can do"), saved cameras, the web page (display meshes only), a still per step.
6. **Offshore stage (after L9):** the load put onto a vessel or jack-up at the quay, then an offshore lift with
   vessel motion, Hs chart and DAF – a foundation lift with its own lifting tool (0180's "foundation demo plan for
   the site").
7. **Later, not in this task:** tandem lifts (owner 18 Nov).

## Rules that already apply

- Invented, unbranded equipment only; built-in charts stay "SAMPLE – not for real lifts"; no maker's chart in the
  repository (CLAUDE.md section 6, Lifting lane in TASKS.md).
- Every tour animation 0 clashes; a demo check is its own `tests/test_demo_lifting_<topic>.py` (task 0145's pattern:
  made once per run, handed on to the jobs) – the GitHub run must not grow past ~35 min.
- Tour stop, PC-check Heavy line, function entries (`since=`), guide section, What's new.

## Done when

(written by the lead with the full brief)

## Not in this task

Changes to the Lifting lane's own code; the cable-lay demo; real crane makes.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
