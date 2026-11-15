# 0137 – Cable fixes: swivel and let-go kept, renames carried, sea cable re-worked after a vessel change, old projects

**Who:** worker · **Status:** waiting – starts after 0126 is merged (same files) · **Branch:** `task/0137-cable-data-kept`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Flex parts lane – cable paths):** `blender/paths.py`, `paths_swivel.py`, `paths_rollers.py`, `paths_sea.py`, `joints.rename`, `vessel_motion.hoses_follow` / `flex.motion_changed`, a `load_post` versioning step, their tests.
**Do not edit:** the Web 3D lane (0134), the Import lane (0139), `sequence.py` (0140).

## Goal

The owner's cable set-up survives model updates, re-reads, added contacts and renames; a built sea cable follows a change of vessel motion; old projects behave as they did.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 2 (lost work):** Swivel and Let go frame dropped whenever the contact list is rewritten.
- **Row 5 (lost work):** joint renames not carried into `contact.swivel`, `contact.joint`, `item.joint` and the `…_was` JSONs.
- **Row 7:** a built sea cable is not worked out again when vessel motion / vessel speed / sea state / preset changes after Build – re-bake (as `flex.motion_changed`) or take the Build off with a note; one route for every vessel/sea change (hoses too).
- **Row 14 (old project):** let-go sea cables of 0.2.95–0.2.102 projects sink over 4 s now – versioning: `sea_settle = 0` for those.
- **Row 16a:** `paths.ramp_steps` slope over changes 1–2 frames apart.
- Plus the guard 0136 leaves for later: `paths._follow` skips scenes that are not a real project scene.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
