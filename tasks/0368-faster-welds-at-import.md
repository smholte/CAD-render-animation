# 0368 – Faster welds at import and model update + the square groove with a root gap (0323's open points)

**Who:** worker · **Status:** done 26 Nov (0.2.268) · **Branch:** `task/0368-faster-welds-at-import`
**Started by:** lead, 25 Nov 2026 23:5x (owner allowed extra code tasks for the night; 0323's open points)
· **Model:** Opus · effort Medium
**Area:** Welds lane – `core/welds.py`, `core/weld_cad.py`, `blender/welds.py`, `blender/weld_cad.py`,
`tools/make_test_weldment.py` (+ the CAD-weld test makers), their tests, the welds tour set, CHANGELOG. Small extras,
own spots only:
- `tools/guide_screens.py`: the `welds_panel` / `weld_cad_panel` modes.
- `blender/tour.py`: the welds set's stop camera.

0348 also edits both of these files in other places – whoever merges second updates its branch.

**Not:**
- `blender/weld_looks.py`'s look: the bead's colour / ripples / heat tint stay as they look today.
- `blender/welds.py`'s `web_objects`: 0369 runs beside you and exports the welds to the 3D page.
- **Keep the weld objects, their material slots, the UV layer `fr_weld` and the heat-zone strips' material names as
  today** – 0369 reads them.
- `ops_import.py` / `reimport.py` beyond the existing weld calls (0340 starts there on Monday).
- `pccheck/checks.py` existing lines (0348) – a new line is fine as a function of your own.
- Painted welds on a part with painted faces (0319's point: they take the part's main paint) → after 0340, which changes
  how painted faces come in.
- AP242 weld PMI (owner decides later).

## Goal

A welded frame with hundreds of welds imports and updates without the long wait. A square butt groove with a root gap
in the CAD file is found as a butt weld.

## Background (0323's report, `tasks/0323-*.md` on `main`)

- **Import time, 300-weld frame** (`--heavy 100 --beads`, 301 parts, Normal, 4-core web machine): 1.0 s without the welds
  → 32 s with them. 30.3 s go to finding and making 300 welds (~0.1 s per weld), about half of it 0319's heat-zone
  strips (`core/welds.py` `_heat` / `_heat_rows`). Proposed: share the heat-zone work, or do the welds' pure-Python part
  (no Blender: `core/welds.py`, `core/weld_cad.py`) in helper processes, as the importer does.
- Not found: a square groove with a root gap. There is no common edge, so the finder sees no corner. When named it comes
  in as OTHER (own shape only), and it is not found by shape.
- The Welds panel's guide pictures are wrong since 0319: `tools/guide_screens.py welds_panel` grabs the 3D view's toolbar
  ("Active Tool") instead of the side panel (`docs/img/panel_3_welds.png`); the CAD section has no picture.
- The tour stop's camera frames both weldments (the close camera fits wider than asked).

## What to do

1. **Profile first** one import of the 300-weld frame and one model update of it (`find_again`, `carry_over`): finding,
   bead mesh, heat zone, Blender objects. Put the split in the report.
2. Make it faster: share the heat-zone work, reuse what repeats, and move the pure-Python work into helper processes if
   the profile says it pays off. A model update re-does only the welds whose parts changed (check what it does today).
3. The square groove with a root gap (a few mm, no common edge): found by its shape and from the CAD file as a butt weld
   (BUTT) with its gap. Add it to the test weldment / the CAD-weld test files.
4. The two guide pictures (panel 3 Looks > Welds, and the "From the CAD file" section) show the side panel. The tour
   stop's close camera frames the asked weldment only.

## Done when

- [x] 300-weld frame: the welds take **≤ about 10 s** at import on the web machine (was 30.3 s). Model update measured
      before / after. The profile split before / after is in the report.
- [x] The same welds as before: the existing weld tests and the 0323 CAD tests stay green. The 6-weld frame and the tour
      set give the same welds and looks (a picture before / after in the report).
- [x] A square groove with a root gap is found by shape and from the CAD file as BUTT – a new test each.
- [x] Guide pictures right; tour set `changed=` raised if the stop changed (`tools/tour_versions.py --record`).
- [x] Tests added / updated; full suite passes; GitHub run green; CHANGELOG.
- [x] Report filled in, merged, released.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25–26 Nov 2026 (one worker session; one independent reviewer subagent for
`core/weld_pool.py`).

**What changed:**
- **Nearest-point search** (`core/welds.py` `Side.nearest_local`, used by the finder, the heat zones and the contacts):
  every run's (point, triangle) pairs in one array instead of ~6,000 small NumPy calls, and pairs whose triangle's box
  or plane lies beyond a point's nearest corner left out (a lower bound, so the same answer). Bit for bit the same
  numbers and the same triangle on a tie (test against the old code on 120 random meshes).
- **Helper processes** (`core/weld_pool.py`, new): the finder's per-bead contacts, the per-pair measures and every
  weld's bead + heat zone (`core.welds.job_beads`) are shared out over helpers (all cores but one, at most 12; none
  below 24 jobs), the master works jobs too; a helper that fails, stops or hangs only hands its jobs back to the
  master. Started as the liquid's helpers (`liquid_pool`'s Windows parts: no console, job object, no crash dialog).
  `FRESING_WELD_HELPERS=<n>` sets the count (tests, measuring).
- `core/weld_cad.find(pool=)`; `blender/welds.rebuild` split into plan / bead jobs / write, `rebuild_many` for many
  welds; `blender/weld_cad.make_all` and `carry_over` (model update) make all items first, then their beads at once.
- Smaller wastes: the weld objects looked up in a table made once (`welds.indexed`; 300 welds on 2,000 objects cost
  2 s of scans, also in the paint check after an import), each CAD bead transforms only its own points (it moved the
  whole 300-bead body per weld), the sides of a weld prepared in the helper.
- **Square groove with a root gap** (`core/weld_cad._square_groove`): the bead's faces on A and on B opposite and
  parallel, 0.3–8 mm apart → BUTT, its seam on the plates' top in the middle of the gap, size = cap width, `Found.gap`.
  By shape only with a cap 0.2–6 mm over the plates and wider than the gap (a flush filler bar is no weld). New
  `FRWeld.cad_gap`; the weld's box says "square groove, gap 3 mm"; the symbol is the square butt ‖
  (`core/weld_symbols.Weld.square`). Straight grooves only (a ring between pipe ends is not read).
- Test models `tools/make_test_weldment.py --gap inventor|unnamed` (two plates 3 mm apart with the groove bead, two
  more with a flush filler bar), `tests/data/test_weldment_gap_*.step` (inventor copy in `fresing_render/data/`).
- Guide pictures: `tools/guide_screens.py` `welds_panel` / `weld_cad_panel` gave an empty side panel (the project's
  workspace hid the panel in the real app; the other per-panel modes such as `spools_panel` have the same fault –
  not changed here): they call `workspaces.use_all`. New `docs/img/panel_3_welds.png`, `panel_3_welds_cad.png` (in
  the guide's CAD section now), guide text on the square groove and the speed.
- Tour: the stop `welds_cad`'s camera is fitted to the CAD frame's own parts (`tour._points_of`), not a fixed box.
- PC check line **looks.weld_gap** (Full); `functions.py` `looks.weld_cad` names it.

**Tested and measured** (4-core web machine; the 300-weld frame = `make_test_weldment.py --heavy 100 --beads`,
301 parts, quality Normal, import from cache):

| Import, welds part | before (this machine, same day) | after, 3 helpers | after, master alone |
| --- | --- | --- | --- |
| finding (`find`) | 13.3 s | 3.0 s | 9.4 s |
| weld items (`_set_from_found`, CAD mesh) | (in "making") | 1.05 s | 1.05 s |
| beads + heat zones + objects | 12.5 s | 2.8 s | 6.7 s |
| **total welds** | **25.8 s** (0323 measured 30.3 s) | **6.9 s** | 17.2 s |

Profile before: 16.8 s of the 34 s (profiler on) in `nearest_local` (5,740 calls, 27,000 small `distance` calls), 9.7 s
heat zones, 8.9 s contacts, 1.8 s object scans. Model update of the same frame (file revised, all 300 welds kept):
welds 29.8 s → 9.9 s; the whole update 57 s → 26 s (the rest is the model build, 0366's lane). The update still re-finds
and re-makes every weld (the old bead objects sit on the old parts); with the speed-up that was not worth more code.

Same welds: the 300-weld frame and the 6-weld CAD frame give the same weld table and byte-identical meshes (bead, heat
zone and CAD bead: points, loops, UVs) before / after, with 0 and 3 helpers (hash compared; that is stricter than a
picture). The welds tour set builds, its stops' checks give the same numbers.

Tests: all weld tests (0319 / 0320 / 0323, 435 incl. functions, places, PC check) pass; new `tests/test_weld_pool.py`
(7: nearest search = old, helpers = master alone for find and beads, a failing / killed helper, few jobs start none),
`tests/test_weld_gap.py` (3), `test_weld_cad.py` +3 (groove import by name and by shape, App's bead on it, heavy(4)
with 0 and 2 helpers bit for bit). PC-check line looks.weld_gap run locally: OK.

**Independent review** (subagent, did not write the code) of `core/weld_pool.py`: 7 faults found, all reproduced on
Linux – a job bigger than the pipe sent to a busy / hung helper blocked the master (Windows pipes ~4 KB: also lost most
of the speed there), answers of a call that ended in an error were taken by the next call, the master's caches were
sent to helpers, an unpicklable job raised, start-up and answer timeouts added up per helper. Fixed (writer thread per
helper, one answer queue, jobs tagged with their call, deadlines from when a job was sent, the master's jobs read
their own dict) and 3 tests added from its cases. Not testable here: CREATE_NO_WINDOW / priority / job object on
Windows (the same code as the liquid's helpers), a `;` in a folder name on PYTHONPATH.

Measured again after the fixes: 300 welds 7.2 s, the same meshes.

**GitHub runs:** 5 full runs. 1st green; 2nd and 4th only renumbering (0346, 0352, 0366, 0354 took 0.2.263 – 0.2.267
meanwhile); 3rd and 4th red on "2 tests skipped" in pytest group 6 – the new test files moved
`test_web_tools.py` (no node on GitHub) and 0352's `test_compat_projects.py` (empty parameter set) beside 0298's
xfail: both put in `ci_groups.SKIPS_ON_GITHUB`. `main` fast-forwarded to the green commit 4a6e5d8.

**Open points / follow-up tasks:**
- No Heavy PC-check line for the speed (the 300-weld frame is made by a tool outside the app); the owner's PC (24
  cores, up to 12 helpers) should be faster than the web machine – not measured there.
- A square groove round a pipe (two pipe ends with a gap, a ring) is not read yet (comes as OTHER).
- `tools/guide_screens.py`: the other per-panel modes (`spools_panel` checked: empty) have the same empty-picture fault
  – they need `workspaces.use_all` too (guide lane).
