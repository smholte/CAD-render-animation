# 0284 – Review (findings only): toolbox-format 0.2 against how Fresing Render uses it

**Who:** worker · **Status:** open – can start (not a code task) · **Branch:** `task/0284-tbf-0.2-review`
**Started by:** lead, 23 Nov 2026 (ToolBox lead's request through the lead post, 21 Nov: format 0.2 ready for review;
round 3 – an empty `job.json` counts as "not there yet" – follows) · **Model:** Opus · effort Medium
**Area:** read only – `smholte/toolbox-format` branch `task/0011-format-0.2` (from commit `8cd350b`, and round 3 when
it is on the branch), its `CHANGELOG.md` section 0.2 "What changed for tool authors" (points 1–11); Fresing Render's
`core/toolbox.py`, `core/tbf/`, `blender/toolbox_inbox.py`, `ops_toolbox.py`, the installer / uninstaller. Writes only
this task file. No code change (the move to 0.2 is a later task after the tag).

## What to answer (in the report, each with the point / section it concerns)

1. **OK for 0.2, or findings** – what Fresing Render would have to change to move from v0.1.1, and anything in 0.2 that
   does not fit how it works.
2. **Point 10:** a native tool that may run as several copies does not delete `alive.json` when it closes (6.4), and a
   finished job's files may be removed at once without the checker complaining (P30). Can Fresing Render run as
   several copies (two windows of the app)? Who writes / deletes its `alive.json` today? How does it clean up a
   finished job? Does 0.2's rule fit, or what would break?
3. **Point 11 / `write_status()`:** where Fresing Render treats `false` as "the job has ended" today (from 0.2 it means
   "not written now").
4. **Round 3** (if pushed by the time you finish): an empty `job.json` from Chrome – does Fresing Render's receiver read
   it as "not there yet"? Anything else in round 3 that touches it.
5. The **Fresing Viewer**'s types for the next format version (from study 0269): which it needs built in (e.g. IGES,
   3MF, the baked 3D page) – one list.

The lead turns the report into the answer to the ToolBox lead. Keep it to what the ToolBox lead needs: one page.
