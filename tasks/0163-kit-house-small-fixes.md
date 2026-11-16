# 0163 – Fix: render kit continues a crashed run from the console, Pause stays paused; House zip names checked raw; worn blade edge on the right side

**Who:** worker · **Status:** waiting – starts **after 0148 is merged** (0148 edits `tools/site_projects/iea15*.py`) ·
**Branch:** `task/0163-kit-house-fixes`
**Started by:** lead chat, 16 Nov 2026 (rows of bug hunt 0147, report in `tasks/0147-bug-hunt-5.md`) ·
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation".
**Area (Site kit lane + House lane):** `site/render_kit/` (`Make site pictures.bat`, `kit_window.ps1`, `kit_run.py`,
`make_site_pictures.py`), `core/house_scene.py` (`read_zip`), `tools/site_projects/iea15.py` (one check), their tests
(`tests/test_kit_window.py` and the House / IEA tests).
**Do not edit:** the pinned copy of the format checker (`tests/data/house/hsf-v1.0.1/hsf/`) – it is a copy of `smholte/house-scene-format`;
`marine_looks.py` (0153); the Web 3D lane; `paths*` (0159, 0160). **Never attach `smholte/house-planner-dev`**
(CLAUDE.md section 6).

## Goal

A night's render with the kit is never redone or left hanging, House packages are checked the same on Windows as on
Linux, and the turbine's worn edge cannot land on the wrong side of a blade.

## Background

Read rows 4, 17, 18 and 21g and the open question "Worn blade edge and the real blades" of
`tasks/0147-bug-hunt-5.md` first. Repeat each one before fixing it. Windows parts cannot run here: test them the way
`tests/test_kit_window.py` does, and have a helper that did not write the change review the PowerShell / .bat lines
(CLAUDE.md: Windows-only code is reviewed independently).

- **Row 4:** when the start window cannot open, the console route asks "Continue the run of … (Y/n)" when
  `resume_info` finds one and passes `--resume`; the message after a crash says what the next double-click will do.
  Test: crash after 2 of 3 stills, console route again → only the 3rd is rendered.
- **Row 17:** after Pause the status window keeps "Resume" while `control.txt` says pause (or the run writes
  `state: "pausing"` when it sees the click), and closing the status window while paused or pausing asks first.
- **Row 21g:** "done at about" in invariant culture (English day names), as the rest of the window.
- **Row 18:** `read_zip` checks the raw names (`info.orig_filename` / the central directory) for `\` and NUL before
  anything else, refuses them as FORMAT says, and gives a clear message for a name that is not UTF-8. The format's own
  checker has the same gap: do not change that copy; write it in the report so the owner can pass it to the House Planner
  lead.
- **Blade edge:** `tools/site_projects/iea15.py` already works out `leading_edge_side(mirrored)`; the converter refuses
  (with a clear message) when it disagrees with the worn-edge look's `edge_dir` for a blade. Test on the stand-in, both
  mirror settings.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix; the Windows lines reviewed by a helper.
- [ ] The kit on the draft release `site-kit` rebuilt (its workflow green) – the owner downloads the fixed kit for his
      next run.
- [ ] GitHub run green; merged; version only if app code changed (CLAUDE.md section 7); report with a short list for
      the owner and the format-checker note for the House Planner lead.

## Not in this task

The other rows of 0147 (0160, 0161, 0162); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026.

**What changed:** Kit console route asks "Continue the run of … (Y/n)" (`--ask-resume`, `make_site_pictures.ask_resume`) and
the messages say so (row 4). Status window keeps "Resume" while `control.txt` says pause, shows "Pausing – after the
picture being made", and closing asks first (row 17). "Done at about" in invariant culture (21g). `house_scene.read_zip`
checks the raw names (`orig_filename`): backslash and NUL refused, a non-UTF-8 name gets its own message (row 18).
`iea15.check_worn_edge` refuses a blade whose leading edge is not within ~45° of EROSION's `edge_dir`. Version 0.2.122.
Tests: `tests/test_task0163_fixes.py` (7; all failed before the fix).

**Tested and measured:** On the 4-core web machine: new tests, `test_kit_window`, `test_house_scene`, `test_site_turbine_standin`
(31 passed, 236 s). GitHub run 43881074669 on the branch: green, 1 run needed, full mode, 18.8 min. A helper that did not
write the Windows lines reviewed the .ps1/.bat/Python changes: no faults (cosmetic: the Resume text stays on a finished run
while the button is disabled). PowerShell itself not run here.

**Open points / follow-up tasks:** For the House Planner lead: the pinned format checker (`smholte/house-scene-format`,
`hsf/package.py`) has the same gap – on Windows `light\a.png` becomes `light/a.png` and is accepted, and a NUL cuts a name short;
it should check the raw names. Not changed here. The site-kit workflow rebuilds the kit on the draft release after this push to
main (check it is green before the owner downloads the kit). Blade check "both mirror settings" is covered by the check function
(mirrored side passes, unmirrored side refuses), not by a mirror switch – the converter has none.
