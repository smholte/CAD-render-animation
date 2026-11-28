# 0377 – Start and windows: the welcome box, a new main window tidied, keyboard work counts as presence

**Who:** worker · **Status:** open – can start · **Branch:** `task/0377-start-windows-fixes`
**Started by:** lead, 28 Nov 2026 (open points of 0241, 0221, 0271) · **Model:** Sonnet · effort Medium
**Area:** Start & learn + Usage lanes – `welcome.py`, `quiet.py`, `editors.py` (the tidy-up of a window),
`usage.py` (presence only), their tests, guide lines if wording changes. **Not:** `ops_demo.py` (0371), `lock.py`,
`workspaces.py` beyond reading, the menus 0367 changed (no menu edits).

## Rows

- **A (0241)** the welcome box of the first starts sits above the splash's Fresing picture: place it so both read well
  (check at 1920 and 2560 px wide – the owner's screen is 2560).
- **B (0221)** Window > New Main Window, or switching to another Blender workspace in Full access, is not tidied until
  the next load: tidy it at once.
- **C (0271)** keyboard-only work (typing shortcuts, no mouse move for over 2 min) is not seen as presence by My usage:
  count key events too (local only, nothing leaves the PC).

## Done when

- [ ] A, B, C fixed with tests; screenshots of A at both widths in the report
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 28 Nov 2026

**What changed:** (A) the splash's welcome / What's new / set-up box wraps its lines at 50 characters and the buttons
are "Open the Learning hub" (own row) + "Later" + "Don't show again": nothing is cut off with "…" any more. The box
already sat below the Fresing picture; the real problem was the cut-off text. (B) `editors._drawn` (the 3D view's draw
handler) notes the windows and the screen each shows; a change (new main window, another workspace) asks for the
tidy-up (`editors.request`, from a timer). (C) the presence keymap also takes ~80 keyboard keys (letters, digits, F-keys,
arrows, Enter, Tab, Space …): they only mark presence, always pass on to Blender, nothing is stored or sent.
Version 0.2.275.

**Tested and measured** (4-core web machine, Blender 5.2.3 under xvfb): splash pictures made before and after at
1920 x 1080 and 2560 x 1440 (after: all lines whole at both). Unit tests: `test_editors.py` (new window / workspace
asks for a tidy-up), `test_settings_blender.py` (key list, a key marks presence at the same mouse spot),
`test_start.py` (box width). `ui_test_start.py` run at both widths: 77 / 75 checks passed. Not tried: a real
Window > New Main Window and a real key press in a running app (no way to open a second window with simulated
events here) – the draw-handler logic is tested with a changed window list only.

**Open points / follow-up tasks:** none for the code. **Owner's check:** Fresing > Welcome (or a new settings folder),
look at the start picture: the box should read whole. Then Window > New Main Window: its right-hand Blender column
should disappear by itself.
