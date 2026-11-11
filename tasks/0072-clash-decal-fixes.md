# 0072 – Clash check and decal fixes (0068 rows 12, 13, 19d; 0029 and 0067 follow-ups)

**Who:** worker · **Status:** done 11 Nov (0.2.58) – was: open – start **as soon as 0070 or 0071 is merged** (third releasing task: never three at
once), and **no later than Wed 11 Nov 18:00**; **merged before Thursday 12 Nov 08:00** · **Branch:** own
**Started by:** lead chat, 11 Nov 2026
**Lane:** Clash – `core/clash.py`, `blender/clash.py`, `ops_clash.py`, `ui_clash.py`; Looks – `blender/decals.py`
(row 13 only); test-model makers `make_test_crane.py`, `make_test_cylinder.py` (+ STEPs); guide pictures of the gantry
carousel and double arm (`tools/guide_screens`); tests
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as whichever of 0070 / 0071 is still running. Do not touch the queue, update, machining, tool
change, coolant or rotary files, nor `handlers.py`, `animation.py`, `reimport.py`. Take the version number last;
whoever finishes second merges `main` once and renumbers. **If it cannot be green and merged by Thursday 07:00:**
push the branch, report, stop (Thursday's two Fable tasks must not have a third releasing task beside them).

## What to fix

1. **0068 row 12** – a clash check running while the animation is built again stores the old result as up to date:
   take the build signature in `_setup()` and drop the result if it no longer matches at the end (and say so).
2. **0068 row 19d** – the clash check holds `_Guard` across `yield` while reading frames, so milling and coolant stop
   updating if the user scrubs then: release it between ticks.
3. **0029 follow-up** – a 45° face mill is wider at the top of its inserts than the "may cut" zone (`clash.Tool` uses
   the tool's radius): use the widest radius of `tool_profile` for the cutting part, so its own cut is never a clash.
4. **0029 follow-up** – the check costs ~0.12 s per program move on a milled block (a 7,000-move program ≈ 15 min):
   find where the time goes and make it faster (e.g. compare the workpiece only at moments the cut has changed and only
   near the tool; reuse the oriented mesh between moments). Measure the 0029 Normal program before/after; aim < 3 min.
5. **0068 row 13** – Same STEP twice: decal templates store the scoped part ID too and prefer an exact match; the
   "already there" test is per target part (a logo for copy 2 lands on copy 2; "every copy" reaches both).
6. **0067 follow-up** – the crane's boom turns 30 mm inside its pedestal, the luffing arm 50 mm inside its post, the
   test cylinders' rods 15–20 mm inside ARM.BRACKET: give them forks/bores like 0067 did (start overlap ≤ 0.2 mm), so
   the all-tour clash test does not sit on its threshold. Their own tests stay green.
7. Re-make the guide pictures that show the gantry carousel and the double arm (models changed in 0067).

## Done when

- [x] A test per fix (row 12: build during a check → result dropped/stale; row 13: two copies, template on copy 2;
      the 45° face mill cutting the block → 0 rows); clash, decal, crane, cylinder tests and the all-tour clash test green.
- [x] Clash time on the 0029 Normal program before/after in the report.
- [x] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [x] Report filled in; `TASKS.md`: 0072 done; 0068 rows marked fixed there.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, Wed 11 Nov 2026 (branch claude/eager-newton-7iq03o).

**What changed:**
- **Row 12:** `Check._setup` takes the build signature; `clash.save` returns False and stores nothing when it no
  longer matches (the operator says "built again while the clash check ran … check again"). `check()` sets
  `run.stored`.
- **Row 19d:** `_read` holds `_Guard` only while it reads a batch of 20 moments (`READ_BATCH`), puts the time back
  before each yield, and takes over a frame the user scrubbed to between ticks.
- **45° face mill:** `clash.Tool` uses `widest(tool)` (largest radius of `tool_profile`) for the cut and follow zones.
- **Speed (milled programs):** the cut workpiece is checked tile by tile (`_meshes_at`, `_narrow`): each tile's Mesh and
  trees are kept while the tile object lives, results per tile pair memoised; the workpiece is worked out once per
  moment for all pairs, and **only at whole frames** – program corners and the extra moments between frames use the
  frame before (more material, never less, so nothing is missed; only the flutes' zone may lie in the extra). Depths
  are the same as with the whole mesh (a point inside lies in one tile, whose surface is nearest).
- **Row 13:** templates store `uid` too; `from_template` prefers the exact part (a one-copy decal goes only there),
  "already there" is asked per part.
- **Test models:** crane PEDESTAL = block + fork (cheeks, bore Ø40.4, boom 20 mm above the block); luffer POST = block
  + fork (arm 30 mm above), BASE.BRACKET and ARM.BRACKET get a 110 mm slot per cylinder. STEPs re-made (tests/data
  crane a/b/inv_a/inv_c, cylinder a/b; copies in fresing_render/data).
- Guide: `view_toolchange_atc/hand/arm.png` re-made; two sentences in the Clash check chapter.

**Tested and measured** (4-core cloud machine):
- Clash time, 0029 test part, Normal toolpath (7,326 moves, 776 frames, 7,997 moments + 11,886 between): **before
  1,163 s** (main 0.2.57; part of it with a pytest run beside it, so a little high – 0029 estimated ~15 min),
  **after 244 s** (alone; 267 s under the profiler); 0 rows both. Aim < 3 min **not met**: what is left is the cutting
  itself (~40 %, the same booleans milling playback does, 75 s alone) and the narrow phase (~37 %).
- Start overlaps > 0.2 mm (tour sets): crane PEDESTAL×BOOM 30 mm → none; cylinder 14 pairs (POST×ARM/ARM.PIN 50 mm,
  brackets × rods/barrels/pistons 10–20 mm) → none.
- New tests (each failed before): build during a check → dropped; scrub during reading → guard 0 between ticks, the
  scrubbed frame kept, same result; 45° face mill in the block → 0 mm (old zone: > 1 mm); decals with the same STEP twice.
- Locally green: test_clash (incl. all-tour), test_tour, test_decals (78); test_cylinders(+core), test_importer,
  test_model_update, test_same_step_twice, test_stacked_joints, test_couplings, test_phase2 (165).
- GitHub: 1 full run on the branch, green incl. Windows (run 43029767974, 12.5 min); `main` fast-forwarded to it (mode reuse), 0.2.58 released and offered.

**Open points / follow-up tasks:**
- Clash speed: below 3 min would need the narrow phase to skip tool/workpiece pairs while the parts outside the
  flutes are far from the cut (a gap bound), or fewer extra moments for a tool inside its own cut.
- The crane's other guide pictures (window, render, looks, decals) still show the old block pedestal (small change);
  re-make when that lane next touches them.
- Branches left on GitHub: claude/eager-newton-7iq03o (can be deleted).
