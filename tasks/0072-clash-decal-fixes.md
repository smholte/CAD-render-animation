# 0072 – Clash check and decal fixes (0068 rows 12, 13, 19d; 0029 and 0067 follow-ups)

**Who:** worker · **Status:** open – start **as soon as 0070 or 0071 is merged** (third releasing task: never three at
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

- [ ] A test per fix (row 12: build during a check → result dropped/stale; row 13: two copies, template on copy 2;
      the 45° face mill cutting the block → 0 rows); clash, decal, crane, cylinder tests and the all-tour clash test green.
- [ ] Clash time on the 0029 Normal program before/after in the report.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0072 done; 0068 rows marked fixed there.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
