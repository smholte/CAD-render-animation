# 0184 – The test tour's `spool` stop fails at random on GitHub: find the cause and fix it

**Who:** worker · **Status:** done (0.2.142) · **Branch:** `task/0184-tour-spool-random`
**Started by:** lead chat, 17 Nov 2026 (open point of 0171, 0173 and 0179) · **Lane:** Flex (`core/paths.py`,
`blender/paths.py`, `blender/spool.py` and their tests; `tour.py` only for this stop's set-up)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

No more random red runs from the tour stop `spool` ("Cable 'Power cable' no longer touches 'GUIDE SHEAVE' at frame
233"). It failed in run 44045080244 (0179's branch, a test-suite-5 job that took 19.4 min instead of 7.8) and on
0173's branch; both passed when run again. Cause from 0173's report: the tight-string solver takes the other branch
round GUIDE SHEAVE at frame 233, where the full spool's leave point (0174) moves on.

## What to do

1. Repeat it: run the stop's Build many times (and under load: `stress` or several processes at once, as a busy runner)
   until it fails; record how often. Find what differs between runs (thread timing, a warm start, float32 rounding, a
   solve order) – never "it is timing" without the case that shows it.
2. Fix the cause in the solver or the spool's leave point so the same Build always gives the same path (the branch
   kept from frame to frame, as `core/flex.solve_motion` keeps one shape). A test that failed before: the repeat case
   in a loop, deterministic.
3. Do not loosen the stop's check or the tour's 0-clash rule.

## Done when

- [x] Cause named with its evidence; fix + test; the stop passes N times in a row under load (N in the report).
- [x] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 17 Nov 2026

**Cause (with evidence):** not timing, not a race – the **processor**. The four failures (0179 and 0173, two attempts
each) were all at frame 233. A temporary workflow ran the stop on 12 runners at once and printed `lscpu`: it failed
on the one **AMD EPYC 7763** and passed on every other CPU (EPYC 9V45 / 9V74, Xeon 6975P-C / 8573C / 8370C); a second
round failed on both 7763s again. The 7763 builds a mirror image: the carousel is read as wound the other way round
(`hand` +1 instead of −1), so it turns the other way, the arm swings to −y instead of +y, and at frame 233 the leave
point lies where the cable cannot reach GUIDE SHEAVE (0.92 → 0 rad wrap = "lifted").
Why: the test carousel's GUIDE SHEAVE touches the coil, so the CAD path's straight from the coil to the sheave is a
fraction of a mm long or nothing. `spool._leave_cad` took the leave direction from that straight (next point minus
the arc's last point): rounding noise. On the 7763 it came out (0.998, 0.0006, 0.06) – outwards – instead of along
the coil (0.004, −1.000, 0), and `hand` = sign(L × T) flipped.
Ruled out here first (all identical bit for bit): 60 Builds in one process under 6 CPU-burning processes; 500 passes
through the frames reading the places under load (no stale driver value); 40 hash seeds; NumPy without AVX-512 / AVX2;
five OpenBLAS core types; 6 rebuilds with an empty import cache; 4 rounds of the real `test_tour.py` sequence under
load (7–9 min each, all green). The solver itself was robust: 3 cm of noise on any input at frame 233 never lifted.

**What changed:** `blender/spool.py`: `leave_direction` – the leave direction is the end tangent of the spool's own
arc (second-order backward difference over its last three points; its last chord with two; the first piece with a
length when there is no arc). Where a free span exists this is the same direction as before (the path is tangent
there), so only the touching case changes. No change to the solver, the stop's check or the 0-clash rule.

**Tested and measured:**
- New tests: `tests/test_spool.py::test_leave_direction_is_the_arc_end_whatever_comes_after` (50 random hair-long
  straights: the direction stays the arc's tangent to 0.1°); `tests/test_spool_leave.py` (the set-up with the
  7763's noise – the straight 1 µm long, outwards and 0.01 to either side – then the stop's full-range Build): **failed
  before the fix** (`hand` 1 == −1, and the Build gave exactly "no longer touches 'GUIDE SHEAVE' at frame 233"),
  passes after.
- Locally (4-core web machine, under 6 busy processes): the spool tests, 135 passed.
- On GitHub with the fix (diagnostic rounds 3 + 4, 32 runners): `hand` −1 everywhere, including 5 EPYC 7763 runners;
  round 4 ran the stop twice per runner (alone, and after the cables stop as in `test_tour.py`): **32 of 32 passed**,
  16 runners in a row (one 7763 among them). Before the fix: 3 of 3 EPYC 7763 runners failed, 21 of 21 others passed.
- GitHub runs: 4 diagnostic runs (the test runs they started were cancelled), then 1 full run of the release commit: green the first time (21.7 min, Windows A + B included); then the merge of main (documents only) + this report.

**Open points / follow-up tasks:**
- Other places that take a direction from a straight between two touching circles would have the same weakness; I
  found only this one in the spool set-up. The test model keeps its touching guide (it is the case worth testing).
- Leftover branch for the owner to delete on github.com: `task/0184-tour-spool-random` (after merge).
