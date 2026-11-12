# 0092 – Clash check: fast with parts that turn in place (rollers, drums, a coil)

**Who:** worker · **Status:** done (0.2.72) · **Branch:** `task/0092-clash-turning-parts`
**Started by:** lead chat, 12 Nov 2026 (0077's open point)
**Lane:** Clash – `core/clash.py`, `blender/clash.py`, `ops_clash.py`, `ui_clash.py`; tests
**Model:** Opus · effort High (algorithm + speed) · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner can run the clash check on the whole cable-lay demo (and his own offshore models) in minutes, not hours, while
rollers, sheaves, drums and the coil turn – without missing a real clash.

## Background

0077 measured on the full-size demo (4-core web machine): with the 300 turning rollers, the coil and the support
rollers in the check it was stopped after 47 min, not done; with them left out 12.5 min (1,839 moments + 32,870
between, 355,868 narrow tests). Why: a part turning about its own round axis keeps moving its box corners, so every
pair near it is tested again at every moment, plus many moments between frames. The static cable lying on the rollers
is another costly contact (touching all the time).

## What to build

- **Turns in place:** a rigid body whose motion over a stretch of frames is a turn about an axis that stays put relative
  to the other body, and whose shape is round about that axis (check it: the mesh's distance to the axis per ring of
  points, within a tolerance), gives the same overlap with that other body at every angle. Test such a pair once per
  stretch instead of per moment; no moments between frames for it. A part that turns about its axis **and** moves (a
  roller on a moving carriage) is treated as a body that moves with its carrier only.
- A part that turns about its axis but is not round (a cam, a sprocket with teeth, a drum with a groove shape) keeps the
  full check unless its shape's turn changes nothing measurable (say how you decide; teeth of a sprocket meshing with a
  chain must still be checked).
- **Resting contact:** a pair touching from the start (the cable on its rollers) keeps today's rule (only depth beyond the
  start overlap counts) and should cost little: say what you did.
- The result rows of every existing test model stay the same (tour animations 0 rows; the clash model 6.0 mm; the 0065 /
  0067 / 0072 tests unchanged).

## Done when

- [x] Tests: a round roller turning beside a fixed frame (0 rows, tested once per stretch), the same roller with a
      flat cut on it (still checked fully, a real clash found), a roller on a moving carriage, a sprocket with teeth.
- [x] Measured on the full-size demo (Help > Make demo project, or `blender/demo.py` from a script) **with** the turning
      parts: time, moments, narrow tests; before (0077's numbers) and after. Target: about the 12.5 min of 0077 or less.
- [x] The PC check Heavy line for clash (exists) still passes; its time before/after.
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The demo model itself (0091), joints (0093), hoses (0058, which may add its own bodies later through `HOOKS`).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 12 Nov 2026.

**What changed** (Clash lane: `core/clash.py`, `blender/clash.py`; tests; guide; one metric in `pccheck/heavy.py`):
- **Turning in place** (`Check._hold_still`): a body whose motion against a carrier – the world, the 4 biggest and the
  12 smallest moving bodies its box meets (with vessel motion everything moves: the deck is the carrier) – is a turn
  about an axis that stays put (`core.spin_stretches`: stretches of ≥ 3 moments, every corner of its box within
  0.05 mm of the pure turn, the axis taken from the best-conditioned turn). Of that body every part that is **round**
  about the axis (`core.round_about`: surface points – all corners + points on the faces – turned by 0.37 / 1.23 /
  2.71 / 4.05 rad must land on the surface within 0.05 mm + the facets' sag, read from the mesh's own rings of
  vertices, 75th-percentile gap so a flat cut through a ring does not widen it) is held at its place and rides with the
  carrier only → it joins the carrier's body. Parts of one body as read are never compared, held or not. Tools and
  workpieces always keep their real motion. A roller on a moving carriage rides with the carriage (tested).
- **How "not round" is decided:** any sampled surface point that lands off the surface by more than tol + sag when
  turned. Teeth (any count: the four turns are not multiples of a common tooth pitch), a flat, a key, a cam, a wheel
  2 mm off its round centre, a helical drum groove, spokes: all fail → checked at every moment as before.
- **Resting contact / not round:** for a turning part that is not round, `core.unround_band` marks the (along-axis,
  radius) cells its non-round features sweep; a part that keeps its place against the same carrier for the whole
  stretch and whose box tree stays clear of those cells (+1 mm, + the near-miss distance) meets it the same way at every
  angle → that pair is checked once per stretch (`_still_pairs`, "windows"): the ropes in the spoked fairlead, tipping
  and handler-top sheaves. Resting contact with a **round** part costs nothing (one body: the cable on its rollers).
- **Big parts** (> 20,000 faces together) first look for a gap (`separation`: a box tree over each mesh's faces cut
  into pieces, built vectorised by median splits; best-first search, both boxes' axes): apart → no point tested, and
  not again until they moved that far against each other; between frames, two parts further apart than both travel
  in the step (exact arc factor (θ/2)/sin(θ/2)) get no extra moments. `narrow` moves only the part of a big mesh near the
  other one, and when no faces cross it decides with one corner per connected piece of each surface.
- **Fixes found on the way:** (1) the step between two frames (`screw_between`) is now the screw's exponential; the
  old least-squares axis point put tiny turns read from float32 places centimetres to **kilometres** off (task 0091's
  open point: false 1–2 mm rows at sea; test with random screws, 0 … 1 rad, < 0.01 mm). (2) A point found deep (> 5 mm)
  inside a big mesh by the three rays is confirmed with 7 more (8 of 10): the 140,000-face rim fence has tiny gaps,
  and a drive gearbox's corner read 0.58 m inside it (false 577 mm rows). (3) `core.transform` uses a matrix product
  (einsum was the slowest step of the set-up).
- Tests: `tests/test_clash_turning.py` (new, 9: round roller beside a frame – held, 0 narrow tests, 0 rows, and the old
  way 20+ narrow / 50+ between; the same roller with a flat – not held, the clash found; roller on a moving carriage –
  held, one body with it, its clash with a beam found; 12-tooth sprocket under a chain link – not held, both teeth
  found; wheel 2 mm off centre – found; spoked sheave + rope – once per turn, the pin in the spokes found; far pairs –
  no extra moments; a part inside another is not "apart"; a gap in a big mesh); `tests/test_clash_core.py` +7 (turn
  stretches, roundness, box tree bound, line–box distance, pieces, the screw step). Guide: "Parts that turn in place"
  + timing; CHANGELOG 0.2.72; CLAUDE.md section 3 + two lessons. No new PC-check line or tour stop (no new function the
  owner sees; `heavy.clash` reports "parts held still").

**Tested and measured** (4-core web machine, Blender as a module; the full-size demo of 0.2.71 + this branch,
"Help > Make demo project" from a script, 98 s; 1,824 moments):
- **With the turning parts** (222 held: 103 cable rollers, 54 guide rollers, 33 support rollers, coil, turntable, wheels,
  drum flanges …; 82 pairs once per turn), static cable and the 66 wobbling cradle rollers (below) left out:
  **744.7 s = 12.4 min**, 1,824 moments + 40,993 between, 322,024 narrow tests, **0 rows** (two checks running side by
  side). Before (0077, the old demo): stopped after 47 min, not done.
- 0077's way (turning parts + cable left out) on the same demo: old code 402 s, new 319 s (both with 2 other checks
  running), new alone-ish 268 s; 0 rows each.
- Everything in except the 66 wobbling rollers (static cable in; before fixes (2) and the last speed tweak): 48 min, 52
  rows: 6 false rim-fence rows (fixed since) and 46 of the **static cable** (arch, guide cage, tensioner pads squeezing
  −20 mm, the D-quadrant's gutter and rollers travelling through it) – the cable does not move or bend yet (0078/0082).
- As is (the 66 wobbling rollers in): stopped at 57 % after 45 min; they grind through the cable (rows up to 94 mm).
- **PC check Heavy `heavy.clash`** (3,000 parts, full size): before **90.0 s**, after **74.8 s**, both 1,667 clashes, 251
  frames (between 2,064 → 2,016). Local tests: `test_clash.py` 20, `test_clash_core.py` 21, `test_clash_turning.py` 9,
  `test_demo_project.py -k clash`, guide/updates 49, tooltips 603/0 missing: all green.

**Open points / follow-up tasks:**
- **Demo models lane:** the 31 V-cradles' side rollers ("CRADLE n: Roller port/stb", 66 in 0.2.71) turn about an axis
  ~63° off their own (`demo_joints.json` gives them a near-vertical axis): they wobble through the cable (up to 94 mm)
  and cost most of the remaining time. With their axis along the roller they are held like the others.
  `tests/test_demo_project.py` can then drop `demo.turning_in_place` from its clash check and the sea `at_rest`
  (fixed here, see (1)); the static cable stays a source of rows until 0078/0082 move it.
- The carousel's rim fence (posts, not round) sweeping past its drive gearboxes and brackets is the biggest remaining
  cost (~4 min of the 12): genuinely close parts, checked in full.
- Helper-agent review skipped: no Windows-only code.

**GitHub runs:** 1 full run on the branch, green on the first try (run 43255929684, 14.1 min; test suites 2/4/7 and real
app pccheck flagged SLOW against the recorded times – the new test file and the heavier clash tests; recording times is
for a later tools push). `main` fast-forwarded to that commit: run 43258629239 (reuse, 2.1 min) published **v0.2.72**,
the Windows update-from-the-release check passed, offered to the apps. Leftover branch: `task/0092-clash-turning-parts`.
