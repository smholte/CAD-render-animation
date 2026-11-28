# 0379 – PC check: a Heavy line for weld speed, Stress memory with the import helpers, "Fresing Render" in Task Manager

**Who:** worker · **Status:** running · **Branch:** `task/0379-pc-check-lines`
**Started by:** lead, 28 Nov 2026 (open points of 0319 / 0368, 0315, 0178) · **Model:** Sonnet · effort High
**Area:** PC check lane – `fresing_render/pccheck/*` (you own the lines named here), `winexe.py` (row C), the
installer only if row C needs it, their tests, the guide's PC-check list. **Not:** the weld code (0372 changes
`weld_cad.py` this weekend – only call it), `installer/` beyond row C (0358 later).

## Rows

- **A (0319, 0368)** no Heavy line for weld speed: build an invented weld frame (~300 welds, like
  `tools/make_test_welds*`) at run time inside the PC check (`tools/` is not shipped) and time the weld finding at import
  and at a model update. One line, plain words, with the part and weld counts.
- **B (0315)** Stress's peak memory counts the app's own process only: add the import's helper processes (peak of the
  sum, sampled), and say which part is which in the line.
- **C (0178)** Task Manager still shows "Blender" for the app: give the Windows process the name / description
  "Fresing Render" (exe resources or the launcher) – Windows-only code, so an independent helper reviews it and the
  Windows CI job checks it.

## Done when

- [ ] Lines A and B in Heavy / Stress with numbers from the web machine in the report; C checked on Windows CI
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [ ] **Owner's check** line: which PC-check mode and which lines to send to the lead

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 28 Nov 2026. Released as 0.2.277.

**What changed:**
- **A – Heavy line `heavy.welds`** ("Welded frame: how fast the welds are found"). `pccheck/heavy_welds.py` (a program of
  its own, like `heavy_scene.py`; shape library `demo_model/geom.py`) writes task 0368's frame at run time: 100 cells =
  300 welds as beads in one "Welds" part, 301 parts (scaled down: 12 cells = 36 welds); revision B has every 10th cell's
  fin taller. The line imports revision A (reads `weld_cad.LAST`: finding, weld items, beads + heat zones, helper
  programs) and reads B in with Model update (clock round `weld_cad.carry_over`); it fails when a weld is lost.
  `MIN_LINES_HEAVY` 21 → 22.
- **B – Stress memory with the helper programs.** `MemoryWatch` (4 samples a second) now also adds up the processes below
  Blender (Linux: /proc; Windows: Toolhelp snapshot + working sets, a child older than its parent is a reused pid and left
  out with its whole tree) and keeps the peak of the SUM with its two parts and the most helpers at once. New metrics and a
  new table column **with helpers MB**; the old column **peak memory MB** is still the app's own, so the comparison with
  earlier Stress runs holds. A line with no helper programs reports only its own peak.
- **C – closed, nothing built (owner's decision in this chat, 28 Nov):** the PC check and the self-test are short
  diagnostic runs in a console window; "Blender" in Task Manager there is not worth +113 MB per install or a large
  Windows-only change (0178 left it so on purpose); with Smart App Control on only signing can change it (later). One
  sentence on both cases in the user guide (Install, step 3).
- Guide: Heavy step, Stress table columns; CHANGELOG 0.2.274; `tools/appicon_test.py` got a Windows check of the memory
  reading (a child program of Blender's Python holding 200 MB must be counted, and not any more once it ended).

**Tested and measured** (4-core web machine, Linux, Intel Xeon 2.3 GHz; invented frame):
- `heavy.welds` at full size: 300 welds in 301 parts; at the import welds found and made in **5.3 s** (finding 2.3, weld
  items 0.8, beads + heat zones 2.2; 3 helper programs; the whole import 8.6 s); model update (10 parts changed) welds
  carried over **8.1 s** (the whole update 24.6 s); all 300 kept; the line takes 36 s here (expected 90 s). Scaled down: 36
  welds, 1.1 s / 1.0 s, 8 s in all.
- Stress, scaled down, two lines run: `stress.import_draft` own peak 653 MB, app + helpers 1,713 MB (at that moment the app
  332 MB, helpers 1,380 MB, 4 helper programs at most). The two peaks do not fall at the same moment – that is why the sum
  is its own number.
- Tests: `tests/test_stress.py` +4 (the pids below a pid incl. cycles, a real 200 MB child counted and not counted once it
  ended, the table's new column, a line without helpers), `tests/test_pccheck.py` +1 (the weld frame's maker, both
  revisions, names and CAD material in the file); `test_pccheck`, `test_stress`, `test_user_guide`, `test_ci_tools`,
  `test_updates`, `test_functions` pass (194).
- **Windows-only code reviewed** by a helper that did not write it (read only): no wrong structure layout or handle
  truncation found; fixed after its review – a rejected (reused-pid) process's children were still counted; process
  rights now `QUERY_LIMITED_INFORMATION | VM_READ` (with the plain right as fallback); a process that ended but is still
  referenced is skipped (also zombies on Linux); the sampler thread survives an exception. Not fixed (nitpicks): the
  console host (`conhost.exe`) that a hidden console child gets probably counts as one more helper in "most at once";
  ctypes set-up is repeated at every sample (a few hundred µs).
- Windows CI checks the reading (`tools/appicon_test.py`, part A) and runs `heavy.welds` scaled down in the Heavy run
  (part B).

**GitHub runs:** see the line under Open points.

**Open points / follow-up tasks:**
- Not measured on the owner's PC (24 cores, up to 12 weld helpers): the lead gets the numbers from his Heavy run.
- Whether `GetProcessMemoryInfo` works on a handle with only the documented rights for every child, and whether
  `conhost.exe` is counted, only the Windows job / the owner's Stress run shows (the table's "with helpers" for the
  import lines should be well above the own column).
- Row C: needs signing (study 0207) – nothing to do before.
- **Owner's check:** run **PC check (heavy)** and send the lead the text block: look for the line "Welded frame: how fast
  the welds are found" (seconds at the import and at the update, helper programs). For Stress: send the table; the new
  column "with helpers MB" should be higher than "peak memory MB" on the import lines.
