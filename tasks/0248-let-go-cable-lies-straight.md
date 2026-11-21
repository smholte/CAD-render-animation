# 0248 – A let-go sea cable lies straight: the cable already on the seabed stays put, only the freed stretch lies down

**Who:** worker · **Status:** done (0.2.189) · **Branch:** `task/0248-let-go-cable-lies-straight`
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

## Design (worker, 20 Nov 2026)

- `core/catenary.py`: the PILED snake (waves of 4 m over S → TDP) is replaced by `bight()`: straight from S along the
  lay line, the extra length in one bight next to the TDP – four arcs of one radius R (out θ, back 2θ, in θ), in line
  at both ends. R = 1.5 × the smallest bend (`r_min`; none: θ = 45°), θ ≤ 140° (an Ω; beyond that R grows). It never
  reaches into `keep` metres from S; a bight that lay there at the let-go (`frozen_span`, `frozen_extra`) stays where
  it lay and only extra length beyond its own goes into a new bight next to the TDP.
- `blender/paths.py`: `_lay_down` works out, once per let-go frame (at **Let go here** and at every Build, stored in
  `fr_let_go_lay`), how the cable lies down: `keep` (cable lying straight from S then), the bight then, and a
  **slide**: the let-go group goes down *and forward along the lay line* together over Settles in (`settle(slide=)`),
  by as much as the cable would pile up, less 4 % of the freed cable (one gentle bight); never so far that the cable
  would hang from a contact before it again (bisection). Two one-moment solves (share 0 and share 1, `_STATE["probe"]`).
- `blender/paths_sea.py`: passes `r_min` (`min_bend`: MBR, else 10 × Ø), `keep` and the frozen bight per moment
  (`paths.let_go_keep`) to the catenary; points on the seabed spread over the farthest bight of all moments + one at
  S (`bight_lam`), so they do not slide along the line as a bight grows.
- `core/web3d_tubes.as_packed` + `blender/web3d_drawn.py`: the web export keeps a cable's own lengths along it when
  the page's chords of the 16-bit points differ (found by `test_web3d_moving`: points that fall on one place round
  apart, 1.5 cm over a cable).

## Report

**Chat / date:** Claude Code on the web, 20–21 Nov 2026. No subagents (the work was one chain of maths and its
plumbing; the checks were written as tests against the brief).

**The cause** was as the lead read it, with one more part: the PILED snake spread the extra length as 4 m waves over
the whole flat distance S → TDP, so every metre of laid cable moved sideways whenever the excess changed. On stop 38
the let-go end sank 11.8 m straight down from a cable hanging nearly vertically (12.1 m hanging, 1.6 m layback): ~10 m
of extra cable, which the snake spread over 66 m (0.50 m sideways). In the demo the cable already piles up 25 m
**before** the let-go (from 3205 on, while the D is lowered – the warned case since 0126); the snake showed it as
0.55 m waves along 340 m.

**The shape chosen and why.** A 10 m extra length in a 1.6 m stretch cannot lie in any bight without crossing itself
or bending far below the smallest bend (geometry: the feet of a bight need ≥ 4 R of line). So the let-go end **lies
forward along the lay line as it sinks** (down and forward together over Settles in): the stretch that hung lies down
in line behind it, as if the hanging cable tipped over onto the seabed, and only 4 % of the freed cable is left for
**one gentle bight** next to the end ("probably not fully straight at the end"). Going down and forward together (not
first down) keeps the cable just slack all the way, so no laid cable is lifted (checked: the slack stays ≥ 0 along
the path). A cable that piles up while laying (B) or was piled already at the let-go lies in one bight next to the
touch-down – compact (an Ω) for a big extra length.

**Tested and measured** (4-core web machine; test model `test_moving.step` = stop 38, and the demo made by
`tests/demo_made.py`, small form):

| | before (0.2.184) | after |
| --- | --- | --- |
| stop 38: laid cable moved after the let-go (largest distance of a point laid at the let-go frame to the cable at any later frame) | 0.50 m | 0.00003 m |
| stop 38: length change over the settle (drawn polyline) | 99 mm (the snake's corners) | 0.3 mm |
| stop 38: tightest bend of the settled freed stretch | – (waves) | ≥ 1.2 m = 10 × Ø (test) |
| demo: laid cable moved after the let-go | 0.55 m | 0.97 mm |
| demo: slide forward / bight | – | 0.11 m (the D lies on the seabed already; the 25 m piled before stays as it lay) |
| stop 38 Build (3 runs) | 0.69–0.77 s | 0.60–0.69 s |
| stop 38 one live solve after the let-go | 37–45 ms | 33–43 ms |
| working out the lay-down (once per let-go and Build) | – | 0.10 s |
| demo Build (whole animation, `animation.bake`) | 87 s | 74–83 s (noise) |
| demo warnings | "piles up 0.01 m … at frame 3205" | the same |

New tests: `tests/test_catenary_bight.py` (9, pure: length, ends, on the seabed, straight from S, one side, no kink
≤ 1°, never tighter than the bend radius, nothing within `keep` bent, grows from nothing without a jump, many moments
= one); `tests/test_paths_settle.py` +4 (laid cable ≤ 1 mm at every frame from the let-go to the end, length ≤ 1 mm,
in line at the old touch-down, bight ≥ 10 × Ø and to one side, no jump between frames, the same shape played, jumped
to, Build's one-moment solve, posed live and after opening the saved project); `test_web3d_tubes_core` +1.
Changed tests: `test_cable_speed` (the snake's bisection test is gone), `test_web3d_moving` (the settled cable no
longer needs its own lengths in the file; the page's lengths still checked to 2 mm). Locally: the sea / cable / web 3D
files (`test_catenary*`, `test_paths_settle`, `test_sea_after_build`, `test_web3d_moving`, `test_paths_sea*`,
`test_paths_moving*`, `test_paths_kept`, `test_build_any_frame`, `test_moving_lowering`, `test_sea_change`, …): green.

**B (the warned PILED case while laying): done** – it falls out of the same bight: the cable from S stays straight up
to the bight next to the touch-down; the warning is as it was.

**Tour stop 38 / PC check:** their checks read the start's height, the lengths and the block, not the shape: no
change; stop 38's text stays. Its picture changes only where the cable lies on the seabed.

**GitHub runs:** 6 full runs (the last one the release check). 1 cancelled by the version push; 2 failed only `test_idprops`' source check
(`hr["r_min"] = np.…` looked like an ID property: now `hr.update(...)`); 3 green (62.7 min, queued behind other
tasks); 4, 5 and 6 after merging `main` again – 0.2.186 went to 0237, 0.2.187 to 0246, 0.2.188 to 0247 (renumbered to
0.2.189); 4 and 5 failed only "2 tests skipped (at most 1 allowed)" in pytest group 2: `test_web3d_keys` and
`test_lifting_reach_independent` each skip one test on GitHub by design, and the time-balanced split put both into
one group once new test files came in. Fixed in `tools/ci_groups.py` (`SKIPS_ON_GITHUB`: never two in one group) with a
test in `test_ci_tools.py`.

**Owner's PC steps** (after **Update now** to 0.2.189):
1. **Help > Make test tour project**, open it, go to stop **38 "A cable on a moving part"**, press **Go**.
2. Play to the end. When the cable is let go near the seabed you should see: the black cable that already lies on the
   seabed stays dead straight and does not move; the end and its loop round the sheave go down and forward along the
   cable's line together; at the end the cable lies straight with one small, soft bend (about 1 m to the side) just
   before the loop. No waves along the cable.
3. Your private cable-lay demo kit (**Help > Make demo project…**, shots 11–12): when the second end is let go,
   nothing on the seabed moves. Before the let-go you will see the 25 m of cable that piles up while the D is lowered
   (the red warning "piles up" as before) as one round bight beside the D instead of waves along the whole cable.

**Branch to delete:** `task/0248-let-go-cable-lies-straight`.

**Open points:**
- The full cable-lay demo (since 0247 the private demo kit; measured here on the demo as it was on `main` before the
  cut, numbers only) piles up 25 m of the second end while the D is lowered (shots 10–11, warned since 0126). It now
  lies as one Ω bight about 19 m long and 15 m to the side next to the D, instead of waves along 340 m. The
  choreography that piles it belongs to the kit – paying in while lowering would leave nothing to pile. No function
  the kit uses was renamed; its let-go looks different (as intended): the lead may ask the owner to run the private
  workflow once.
- The leave point on a sheave that lies flat swings round it at the end of the settle (0125/0172's flat-wheel rule):
  the extra length then wobbles by ~0.25 m for a few frames, so the small bight at the end breathes a little there
  (within the twitch test's 0.3 m). Older than 0248; the snake hid it.
- PILED moments still hang straight down beside T and reach T with a sideways hop of `eta` at the touch-down (as
  before 0248).
- A stored lay-down is worked out at **Let go here** and at Build; a project let go before 0.2.189 gets it at its next
  Build (until then: no slide, the bight in the freed stretch only).

