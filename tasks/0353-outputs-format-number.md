# 0353 – Format number on outputs (3D page, House round-trip file) + House sample re-pin to v1.0.2

**Who:** worker · **Status:** open – can start · **Branch:** `task/0353-outputs-format-number`
**Started by:** lead, 28 Nov 2026 (owner 25 Nov 22:5x: before the baseline and before the Viewer; 0352 done) ·
**Model:** Sonnet · effort Medium
**Area:** Web 3D + House lanes – the format-number spots only: `blender/web3d*.py` / `core/web3d*.py` (where the page's
data is written), the page's own reader in `fresing_render/web/`, `core/house_scene.py`, `house_import.py`,
`house_bake.py`, `ops_house.py`, `toolbox_inbox.py`, the House sample in `tests/data/` / `fresing_render/data/`, their
tests, guide lines. **Not:** the page's light / colours (0382 later), `core/compat.py` beyond reading (0352's style).

## What to do

1. **3D page:** the exported page and its data file carry a format number; the page reads older numbers and, for a
   newer one, says plainly "made by a newer Fresing Render – update to open it fully" and shows what it can.
2. **House round trip:** the bake package we send back carries our format number; the House scene we read is checked
   against what we support, with the same plain message for a newer one (agree the field with the House format – read
   the pinned spec, don't change House Planner).
3. **ToolBox inbox:** reads the numbers and passes the plain message on.
4. **Re-pin the House sample** to House Planner's tag `v1.0.2` with `example-house.hpscene` (as 0130 did for v1.0.1).
5. Same style as 0352's `core/compat` (a number + a plain line); one test per output for "older", "same", "newer".
6. The Viewer reads these later (V1): write the numbers and rules in `docs/` where the Viewer task will find them.

## Done when

- [ ] Both outputs carry the number; readers handle older / newer with tests; the re-pin done
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

**Chat / date:** Claude Code on the web (Sonnet), 28 Nov 2026.

**What changed (0.2.275):**
- New `core/outputs.py` (0352's style: a number + a plain line): `number`, `judge` (older / same / newer / bad),
  `newer()` = "Made by a newer Fresing Render – update to open it fully.", `page_format`, `page_state`.
- **3D page:** the settings block's `"v"` (there since the first page) is now `PAGE_FORMAT` (1) by name; the model inside
  (the page's data file) carries `asset.extras.fresing_format` = 1. `fr_page.js` reads both (`READS`), takes the higher,
  keeps older / missing numbers as format 1, and for a newer one opens and says the plain line once (also in
  `data-fr-player`: `format`, `formatState`, `newer`). A page without any number (all earlier ones) is format 1.
- **House:** both packages already carry the House format's own `version` ("1.0", FORMAT section 2; the bake also
  names the app in `generator`) and `house_scene.check_version` already refused another major version and noted a
  newer minor – so no field was added (agreed with the pinned spec, nothing changed on the House side). Table test for
  older / same / newer on both packages.
- **Toolbox inbox:** passes that line on in the job's status; new real-app test (newer 2.0 / older 0.9 house).
- `docs/OUTPUT-FORMATS.md` = the numbers and rules for the Viewer (V1). No button, panel or tour change, so no guide,
  PC-check line, tour stop or function entry.

**Tested and measured** (4-core web machine, Linux, headless Chromium, bpy module): `tests/test_outputs_format.py`
(9 tests: rule, page and model in Python, the page's words, the page opened in the browser as same / no number / newer
by `v` / newer by model), `test_toolbox_blender.py` (+1), `test_web3d*.py`, `test_house_scene.py`,
`test_house_pinned.py` all green locally; GitHub run: see below.

**Open points / follow-up tasks:**
- **Item 4, the re-pin to `v1.0.2`, is NOT done:** the tag `v1.0.2` does not exist yet, and `example-house.hpscene` is
  only on the unmerged branch `claude/task-0044-house-planner-y0f1ld` of `smholte/house-scene-format` (4 commits, MIT
  `LICENSE`, 5.9 MB sample, format unchanged – "1.0"). Pins are tags (never an unreviewed branch), and tags are the
  owner's. Once the House lead's and our lead's OK is given and the owner has made the tag: a small task re-pins
  `tests/data/house/` + `fresing_render/data/` as 0130 did (the sample is 5.9 MB, so decide whether it ships in the extension).
- No sample page of a newer number exists (none is written yet); the tests make one by raising `"v"` by hand.

**Owner's check:** none.
