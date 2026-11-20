# 0248 – A let-go sea cable lies straight: the cable already on the seabed stays put, only the freed stretch lies down

**Who:** worker · **Status:** open – can start · **Branch:** `task/0248-let-go-cable-lies-straight`
**Started by:** lead, 20 Nov 2026 (owner 23:30, with three screenshots of test-tour stop 38 "A cable on a moving part"
on 0.2.182: "after dropping a cable it gets wobbly (not realistic, it should stay straight) – probably not fully
straight at the end, but it wobbles through the entire cable. Also in the full cable laying demo.")
**Model:** Opus · effort High
**Area:** Flex parts lane – `core/catenary.py` (the PILED shape), `blender/paths.py` (`_apply_let_go`, `settle`,
`settle_share`), `blender/paths_sea.py` (point counts, the warning only if needed), their tests, the guide section
`#settle` in `docs/USER-GUIDE.md`, `CHANGELOG.md`. **Not** `blender/tour.py` (0230 and 0232 are in it), **not**
`blender/demo.py` / `demo_model/` (0247 "the cut" splits them), not `spool.py`, `paths_rollers.py`, `flex*.py`.

## Goal

When a sea cable's end (and its turn round a sheave or quadrant) is let go, **the cable that already lies on the
seabed does not move at all** – not during the settle, not after it. Only the stretch that was hanging in the water at
the let-go moment sinks and lies down, and it lies as a real cable would: in line with the lay, with at most **one
smooth, gentle curve** where it has more length than distance – no wave train, never along the whole cable.

## What the owner sees today (0.2.182)

- **Stop 38** (set `moving_cable`, `test_moving.step`): before the let-go the cable lies dead straight on the seabed
  and hangs from the block's sheave. As it settles (2 s) the **whole laid cable**, from its far end up to the touch-down,
  turns into a snake of short even waves, and stays so. The curl at the very end (the turn round the sheave left
  behind, "the loop lies flat") is meant and stays.
- **The full cable-lay demo** (second end let go at the D / quadrant, `demo.py` `LET_GO_AFTER`): the same – the whole
  laid cable snakes after the let-go.

## Cause (lead's reading of the code – check it)

- After the let-go the end sinks straight down (`settle`), so the length that hung in the water (≈ the depth and more)
  plus the turn are now **more cable than flat distance + depth**: `core/catenary.py` gives `kind = PILED`.
- PILED draws the laid part as a sine snake of wavelength `SNAKE` = 4 m spread **over the whole flat distance S → TDP**
  (`points`, the `pile` block; `_snake_amplitudes`) so the length stays L. With tens of metres of extra length over a
  long laid line that is the even wobble from end to end.
- The warning is quiet then (`laid_down` = calm in `paths_sea.py`), so nothing told anyone.
- The PILED snake was written for the **warned** case (paid out too much while laying); it is also unrealistic there
  (cable laid earlier does not start to snake because more is paid out now).

## What to build

**A. Let-go (required).**
1. The points of the cable that lay on the seabed at the let-go frame stay **exactly** where they were (the same as
   at the let-go frame, within 1 mm) at every later frame, in the seabed's coordinates (the seabed moves with the
   lay – keep 0081's holding frame).
2. The freed stretch – from the touch-down at the let-go frame to the end, including the turn let go with it – goes
   from its hanging shape to its lying shape over **Settles in**, smoothly (no jump at the first or last settle frame),
   and its length stays L (within 1 mm).
3. Lying shape: in line with the laid cable at the old touch-down (no kink: same direction there), then **one smooth
   curve to one side** carrying the extra length (a bight / soft S), ending at the end's settled place with the turn
   as today. Its tightest bend not under the cable's smallest bend radius (0243's Size gives it; Custom / none:
   10 × the cable's diameter). If the extra length cannot fit that way within the stretch, let the bight grow
   sideways – never push waves back onto the cable that already lay there. Pick the shape (a bight, a clothoid-like
   S, the end sliding forward along the lay line) by what looks most like a real lay-down; say which and why in the
   report.
4. No new warning for a let-go cable (lying there is what it should do – guide `#settle`).
5. Every way the frame is reached gives the same shape: playback, Build, a jump to any frame, undo, opening the
   project, a model update (0216's rules), the web 3D export of the scene, the render queue.

**B. The warned PILED case while laying (do it if it falls out of A cheaply; otherwise an open point).**
Extra cable piles **near the touch-down**, not over the whole laid line: the laid cable from S stays straight up to
where the extra begins. Keep the warning as it is.

## Checks

- New tests (pure Python where possible, in `tests/test_paths_settle.py` or a new `tests/test_paths_let_go_lay.py`):
  laid points unchanged after the let-go (≤ 1 mm, every frame of the settle and after); total length kept (≤ 1 mm);
  tightest bend ≥ the smallest bend radius on the freed stretch; no sideways offset beyond 1 mm on the old laid part;
  direction continuous at the old touch-down (≤ 1°); no jump between frames during the settle (largest point step per
  frame ≤ what the settle's speed allows); same shape through Build / frame jump / reopen.
- Stop 38 and the demo's let-go (shots 11–12) in pictures **on your machine only** (test models; the demo's pictures
  never in the repository – CLAUDE.md section 6). If stop 38's picture or record changes: merge `main` once after 0230
  and 0232 are merged and re-record `tour_versions` (shared record file); stop 38's text stays.
- Speed: the let-go must not add a visible wait (measure Build of stop 38 and the solve per frame before / after; 0192's
  sea cable solve is already ~7 s – do not make it worse).
- Guide `#settle`: one or two sentences that the cable already on the seabed stays put and the freed stretch lies down
  in one smooth curve; `changed=` on its function-list entry. PC-check line and tour stop: only if their check reads the
  shape (say so in the report).

## Report

What the cause really was, the shape chosen and why, the numbers of the checks (before / after), B done or an open
point, the branch to delete. Owner's PC steps: open the test tour, stop 38, Go, look at the cable after the let-go;
then the full demo's let-go (Help > Make demo project…).
