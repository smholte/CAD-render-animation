# 0174 – Spools full of real cable: every layer drawn as one continuous cable on carousels and drums, wound fully in and out; every winch of the demo with its steel wire rope

**Who:** worker (web session) · **Status:** done (0.2.139) · **Branch:** `task/0174-full-spools` (a web session may name its own)
**Started by:** lead chat, 17 Nov 2026 (owner's wish, 16 Nov 23:59, with a screenshot of the demo's carousel) ·
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation". Subagents
allowed (CLAUDE.md section 2).
**Area:** Flex lane, spool part only: `core/spool.py`, `blender/spool.py`, `ui_spool.py`, `ops_spool.py`, their tests,
`tools/make_test_spool.py` + its model copies; the demo's `spool` stage and the set-up of the winches' wires in
`blender/demo.py` (+ `demo_model/` where a winch has no rope in its CAD); the spool ropes on the web page
(`blender/web3d.py` / the page script: the spool part only); `tools/measure_cables.py`; the tour stop `spool`, the
PC-check line `motion.spool`, the guide section `#drums`.
**Do not edit (0172 runs beside this task in the Flex lane):** `core/paths.py`, `core/catenary.py`, `blender/paths*.py`,
`ui_paths.py`, the demo's sea / quadrant stages and `set_down_depth`. If this task needs a change there, write it in the
report as a follow-up instead. In `demo.py` change only the `spool` stage, the winch set-up and their expected numbers;
whoever of 0172 / 0174 merges second updates its branch to `main` and the demo tests' expected numbers (CLAUDE.md
section 2). Not the Machining lane (0167) or the CI files (0170/0171).

## Goal

The owner (screenshot of the demo's carousel, 0.2.118+): the carousel shows its top layer as cable and under it a black
cylinder. He wants **cable all the way**: every layer drawn as cable, **one continuous cable** from the core to the
end, which can be **wound fully out and fully in** – the layers come off and go on one by one until the core is empty
(or full). The same for **winch drums** (every layer, Lebus crossovers on every layer, the climbs at the flanges). And
**every winch of the demo** has its real steel wire rope on its drum.

## Background

- `blender/spool.py` (0080): `DRAWN = {"DRUM": 2, "CAROUSEL": 1}` layers are drawn as rope (object "FR spool <name>",
  its Geometry Nodes trim the wound path by driven lengths); the full layers below are **one solid** ("FR spool solid
  <name>", a sleeve on a drum, a ring on a carousel) scaled by a step table (*(picture removed – private, task 0226)*, `S.stack`,
  `S.stack_breaks`). That solid is the black cylinder the owner sees.
- 0159 filled the demo's carousel to the rim: 23 + 1 layers, 43.5 km of Ø 200 mm served cable; the top layer must be an
  even one (CLAUDE.md section 8, the carousel's alternating layers). 0158/0164: the served-cable look with spiral
  bands on spools too; a coil follows a look change at once.
- 0142: the web page draws spool ropes as the wound path + a cut in its shader (the full layers as the solid).
- Spooled on the demo today: the carousel, handling winch 1, the A&R winch. **Not spooled (wire only as CAD or as a
  cable without a rope on its drum):** at least handling winch 2, the two tipping winches (their wires are app cables
  kept tight since 0095/0125; the drum only follows the speed), the deck crane's hoist (0153). The worker lists every
  winch and drum of the demo vessel (and the park's cranes/davits, 0166) and says which got what.
- Size: 43.5 km of cable as a tube is far more geometry than anything else in the demo. Most of it is hidden under the
  layers above, but whatever is paid out shows the layer below, so all of it must be there when needed. How to draw it
  cheaply (one static wound mesh trimmed by the paid-out length, fewer sides on turns that are covered, instancing per
  turn, a top-layer window at full detail …) is the worker's design – write it under "Design" before building.

## What to do

1. **Every layer as cable** on carousels and drums, the solid gone: one continuous centre line from the anchor at the
   core (carousel) / flange (drum) through every layer, crossovers and climbs to the leave point, drawn as the cable's
   own look (served cable, wire rope, power cable) with its bands running on without a jump at layer changes.
   Neighbouring turns touch and do not overlap (each turn in the groove of the turns below, as 0080's maths places them).
2. **Wind fully in and out:** the cable joint's whole range – from all paid out (core / drum empty, the cable's anchor
   end visible) to full – gives the right picture at every value, live and after Build; the followers (loading arm,
   level wind, guide swivel) follow over the whole range. A test winds the test spool from empty to full and back.
3. **Every winch of the demo with its steel wire rope:** each winch drum on the demo vessel gets its wire as a spooled
   cable with the steel wire rope look (0078's "Wire ropes"), on its drum in layers, leading to its sheave / fairlead
   as the CAD shows; a winch with no rope in its CAD gets an invented one in `demo_model/` (each part one solid, CLAUDE.md
   section 8). Anchor chains (windlasses) are not wire: leave them, say so.
4. **Cost, measured before/after on the demo** (machine named; `tools/measure_cables.py`, Make demo): Build, playback
   per frame, live posing of the cable joint, memory, saved project size. Aims: playback no more than ~3 ms a frame
   above today, Make demo no more than ~15 % longer; if an aim cannot be met, measure the best design found and say
   what it costs. A Heavy PC-check line if the cost depends on the coil's size (CLAUDE.md section 6).
5. **Web page:** the full coil on the page if it adds no more than ~5 MB to the demo's page; else the page keeps today's
   top layer + solid, measured and stated in the report (Web 3D follow-up).

## Rules

- New behaviour gets a test (the continuity of the centre line through every layer change, no overlap between
  neighbouring turns, the full range in and out, a drum with Lebus crossovers on several layers, an even/odd layer count
  on a carousel). Nothing loosened; every tour set and the demo stay 0 clashes.
- An **independent tester** (a subagent that did not write it) tries to break it: a nearly empty and a full spool, a
  joint value past either end, a spool with one layer, a carousel whose axis points down (`FRSpool.zsign`), a model
  update, an old project (0.2.118-style, solid) opening and getting the new drawing.
- The tour stop `spool` and the PC-check line `motion.spool` check the new drawing (a full spool emptied and filled);
  the guide section `#drums` gets the new behaviour and a new picture of the test spool; tooltips if a setting changes.
  CHANGELOG + version last (section 7).
- The owner's check on his PC goes in the report as numbered steps (Help > Make demo project, the carousel camera,
  scrub the cable payout fully out and in; the winches' close-ups).

## Design (worker, 16 Nov 2026)

**Measured first (4-core web machine, `core/spool.py`):** the demo's full carousel (Ø 200 mm, 24 layers, 45.7 km of
wound path) is 33,120 pieces; drawn at today's tolerance (sag d/60) it is 132,000 points – as a tube of 8 sides 1.06 M
points / 2.1 M triangles. The A&R drum (Ø 56 mm, 6 Lebus layers, 710 m) is 8,000 points. One Geometry Nodes tube over
all of it, trimmed at every frame, would cost tens of ms a frame: too much.

**What a viewer can see.** Only the layer being paid out changes from frame to frame; every layer below it is full and
does not change until the payout reaches it. So the coil is drawn in two kinds of objects:

1. **The live rope** (as today, "FR spool <name>"): the current layer only (`DRAWN = 1` for drums and carousels),
   from where it begins to the leave point, trimmed every frame by its two driven lengths. Its Start is no longer a
   table of keys but a **simple expression** of the cable joint: `S0 + (L > F1) * (S1 - S0) + …` with
   `L = W0 - sign (k a + c)` (one term per layer; plain arithmetic, works with scripts off).
2. **One static object per full layer** ("FR spool layer <k> <name>", role `layer`, layers 0 … n - 2: the top layer
   is never covered): its own mesh is that layer's stretch of the wound path's polyline (points + edges, `fr_L`, from
   where the climb into it begins to where the climb out of it begins – exactly the points the live rope uses, so the
   seams meet point on point), and a Geometry Nodes modifier "FR spool layer" (new tree, no Object Info, no time, no
   driven input) sweeps it into the same tube with the same look attributes (`fr_cable` with s = L - W0: the served
   bands and the wire's lay run on across every seam). Nothing in it changes with the frame: Blender works it out
   once and keeps it. Its **visibility** is one simple-expression driver on `hide_viewport` / `hide_render`:
   `max(part hidden, spool off, L <= F(k+1))` – hidden while the payout has reached its layer, with the very same
   comparison as the live rope's Start, so the drawn stretches always meet (no gap, no double layer).

Per frame: n - 1 tiny drivers; the static tubes cost nothing until a layer change shows or hides one. The solid
(*(picture removed – private, task 0226)*, "FR spool solid") is gone. The web page draws the whole coil as one spool rope (the wound path from the
anchor to the window's end, cut from 0) when that adds < 5 MB, else as today.

**Wind fully in and out.** The tables already span the whole range (W0 - total … W0); the live window is rewritten
when posed outside it (`after_draw`) and at Build for the animation's range. Tests drive the cable joint from all paid
out (nothing on the spool, the free cable starts at the anchor) to full and back, live and after Build.

**Old projects** (0.2.118-style, with a solid): `load_post` finds a spool with a solid or without its layer objects
and draws it again (`spool.upgrade`).

**Core additions** (`core/spool.py`): `layer_spans(path)` (start, end of each layer's drawn stretch), `shown_layers`
and `drawn_from` (the two expressions in plain Python, for the tests), `turn_gaps` (the closest approach between the
rope's middle line and the turns beside and below it, for the "touch, no overlap" tests).

**Demo winches** (stage `winch_wires`, after `wires`, only the winch set-up): every winch drum of the vessel gets its
wire as a spooled cable with the steel wire rope look – handling winch 2 as handling winch 1; each tipping winch's
fixed wire (drum → foot sheave → post top) as a cable spooled on its drum whose speed joint follows the tipping wire's
speed one to one (so the drum pays out what the kept-tight wire takes; the drum's ratio coupling becomes the spool's
table); the deck crane gets an invented hoist drum + wire in `demo_model/vessel.py`. The park's cranes and davits:
listed in the report.

**Subagents:** an independent tester (did not write the code) tries to break it (the brief's list); the guide text and
picture at the end. No parallel writers: the change sits in one file (`blender/spool.py`).

## Done when

- [ ] 1–3 done on carousels and drums, the solid gone, one continuous cable, full range in and out
- [ ] Every demo winch listed with what it got; wire rope look on each
- [ ] Before/after table (Build, playback ms, posing, memory, project size, page size); small before/after picture of
      the carousel in `tasks/img/0174_*` (the demo's invented vessel only)
- [ ] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

The cable paths and the sea (0172 runs: `paths*.py`, catenary, shot 11); 0152's demo realism (0173, after 0172 and this
task – both edit `demo.py`); anchor chains; cables or hoses swaying in wind.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker session), 16–17 Nov 2026. Released as **0.2.139**.

**What changed:**
- **Every layer is cable** (`blender/spool.py`, `core/spool.py`): the solid under the top layer is gone. The layer
  being paid out is the moving rope as before (`DRAWN` is now 1 for drums too); each full layer below is a static
  object ("FR spool layer <k> <name>", role `layer`): its own mesh is its stretch of the same drawing polyline, the
  new tree "FR spool layer" sweeps it into the same tube once (no time, nothing driven), the look's s = L - W0 runs on
  across every seam. Its visibility is one simple-expression driver of the cable joint (`max(part hidden, off,
  W0 - p <= show point)`); `core/spool.layer_shows` puts the show point half way up the climb out of the layer, so the
  layer object appears a little *before* the moving rope gives the layer up – a moment where both draw it, never a
  gap (32-bit keys). Core: `layer_spans`, `layer_switches`, `layer_shows`, `shown_layers`, `drawn_from`, `turn_gaps`.
- **Full range in and out:** the tables already covered W0 - total … W0; tested live and after Build from all paid out
  to full and back (and past both ends).
- **Old projects** (a solid, no layer objects) are drawn again on load (`spool.upgrade`, load_post); a renamed drum or
  carousel takes its drawing and tables along (`spool.renamed`, `FRSpool.name` update + `name_was`, found by the
  independent tester); a cable's new diameter draws its spool again (`after_draw` compares a key, also the tester's).
- **Web page:** during an export `spool.web_begin` makes a temporary solid for the full layers under the moving top
  layer (as the page showed before), `web_end` hides it and removes it a moment later. The full coil on the page would
  be the demo carousel's 1 M rope points (≈ 2 M triangles, tens of MB as a mesh in the file): over the 5 MB aim.
- **Demo winches** (new stage `winch_wires` after `wires`; `demo_model/vessel.py` for the crane):

  | Winch / drum | What it got |
  | --- | --- |
  | Carousel (power cable) | spooled already (0080, 0159): now all 25 layers cable |
  | Handling winch 1 | spooled already (0080): every layer wire (Lebus, level wind follows) |
  | Handling winch 2 | **new:** its fairlead wire on its Lebus drum, level wind follows (as winch 1; speed joint "HANDLING WINCH 2: Wire travel", stands still in the animation) |
  | A&R winch | spooled already (0082): every layer wire; its old fleet warning 13.6° unchanged |
  | Tipping winch port / stb | **not changed** (still the CAD sleeve, the drum turning by ratio with the tipping wire). Tried: their CAD lead (drum → foot sheave → up the post) as a cable spooled on the drum, its speed following the kept-tight tipping wire 1:1. GitHub's re-bake test showed it baked as standing still: `paths._bake` reads every cable's places in one pass *before* it writes the kept-tight payouts, so a cable whose speed follows a kept-tight wire sees no payout at Build (a re-bake afterwards does). The fix is an ordering change in `paths._bake` (0172's file): follow-up. Also: their lead is 2.6 m, the fleet angle 6.5° |
  | Deck crane hoist | **new, invented** (`vessel.hoist`): a Ø 28 mm wire on a drum between the boom's chords at its foot, along under the boom to a head sheave hung under the boom head and down plumb to the hook block (moved to hang 1.2 m under the sheave); joints "Hoist drum turn", "Head sheave turn" ride on Luff |
  | Lifeboat davits (4), windlasses (2) | not changed: davits have no winch drum in the CAD; windlasses carry anchor chain, not wire |
  | Park: substation crane (pedestal only), turbine davits (DAVIT + HOOK BLOCK, no drum) | not changed: no winch in the CAD, seen from far; a follow-up if wanted |

  Every winch spool has the steel wire rope look ("Wire ropes").
- **Test model:** `tools/make_test_spool.py` – the rim fence is 250 mm high instead of 420 (the arm's guide sheave hit
  it when the carousel is emptied); nothing the spool reads changes (the core sets the coil's top).
- Tour stop `spool` and PC-check line `motion.spool`: the animation goes on 8 s (`spool.add_full_range_steps`): the drum
  wound fully in and paid out to its anchor, the carousel emptied and wound back; `tour._check_full_spools` checks the
  layers shown and one cable without a gap. New Heavy line `heavy.spool` (a carousel of 7 km in 38 layers, scaled down
  1.3 km): set-up, posing, Build, playback, triangles, memory. Guide `#drums`: text + new picture
  `view_spools_full.jpg`, `view_spools.jpg` made again. `tools/measure_cables.py` counts the layers and the project size.

**Tested and measured** (4-core web machine, the demo made with `tests/demo_made.py`, `tools/measure_cables.py`,
Blender as a module, no graphics card; before = main at 0.2.133):

| | before | after |
| --- | --- | --- |
| Make demo | 364.6 s | 381.0 s (+4.5 %; the new stage 10.5 s; measured while another test ran) |
| Build animation | 88.9 s | 96.7 s |
| Playback per frame, before Build | 31.4 ms | 33.6 ms |
| Playback per frame, after Build (best of 3 × 120 frames) | 35.5 ms | 38.6 ms (+3.1: the full layers' drivers 1.3 ms, four new winch wires ~3 ms – two of them, the tipping drums, were taken out again afterwards, so the shipped demo costs less) |
| Live posing of Cable travel, per step | 132.3 ms | 134.0 ms |
| Memory after opening / after Build | 1,197 / 1,604 MB | 1,319 / 1,748 MB |
| Saved project | 224.1 MB | 226.2 MB (layer meshes are points only) |
| Carousel drawn | rope 43 k triangles + solid | rope 43 k + 24 static layers 1.97 M triangles (worked out once) |
| Cycles frame of the carousel shot, 480 × 270, 16 samples | 9.9 s | 11.3 s |
| Web page | top layer + solid | the same (full coil ≈ 1 M points: over the 5 MB aim) |

Picture: *(picture removed – private, task 0226)* (the black ring gone). Turns: on a carousel neighbouring turns lie
one cable apart (0.9998 d, the spiral's lead), at least 0.89 d only up the climbs; on a drum the turns of a layer lie a
pitch apart, but the layer above lies d·cos 30° out at constant radius (0080's maths) and where its helix crosses a turn
below the two middles come 0.866 d close – pinned by a test (follow-up below).

Tests: `tests/test_spool_full.py` (27, new), `tests/test_spool_full_independent.py` (48, the independent tester's),
the spool, web, tour, demo-project and vessel tests updated (the solid's two tests now check the layers; sheet joint
and spool counts). Locally: the spool files, `test_web3d_moving*` -k spool, `test_tour.py` (spool stop),
`test_tour_clash.py` -k spool (0 clashes), `test_demo_vessel.py`, `test_demo_project.py` on the made demo, the PC-check
lines `motion.spool` and `heavy.spool` (scaled down: 2.4 ms a frame, 8 ms a posing step, 0.44 M triangles).

**Subagents:** one independent tester (general-purpose, did not write the code): 48 tests; it found two real faults
(a cable's diameter did not redraw the spool; a renamed spool left its old drawing standing, now visible as every layer
twice) – both fixed by the worker, its tests kept. No parallel writers.

**The owner's check on his PC:**
1. Help > Make demo project, wait until it is made, open it.
2. In 5 Scene & Render > Cameras, choose the saved camera "Carousel".
3. In 4 Motion > Joints, choose "Cable travel" and drag its value down to about −2,600 m (all wound in: the carousel
   full to the rim) and up to about 43,500 m (all paid out): the layers come off one by one, every layer cable, no
   black ring, down to the bare core. Set it back to 0.
4. Choose the camera "Handling winch": the Lebus drum, every layer wire. Look at the deck crane: its new hoist wire from
   the drum at the boom's foot, under the boom, over the head sheave down to the hook block.
5. Play the animation: shot 3 (carousel) and shot 6 (handling winch) look as before, with cable under the top layer.

**Open points / follow-up tasks:**
- Drum layers cross the turns below at 0.866 d (0080's maths: constant radius per layer). A follow-up could let a
  layer ride up over each crossing (and nest a Lebus layer half a pitch over the one below) – it changes 0080's tables.
- **The tipping winches' drums** (see the winch table): `paths._bake` should read the places of a cable whose speed
  follows a kept-tight wire after that wire's payouts are written; then the stage `winch_wires` can spool them
  (the code is in this branch's history, commit "every demo winch spooled": a lead cable + `set_follows` ratio ±1).
- Web 3D: the full coil on the page (≈ 1 M points for the demo carousel) needs a lighter form (fewer sides on covered
  layers, or only the outer turns) – today the page keeps the solid.
- While the payout is in the second half of a climb, a layer is drawn twice (same points, rings up to 0.11 mm apart):
  could flicker in a render for that moment (the tester's note).
- The demo's tipping winches have a 6.5° fleet angle (no level wind, 2.6 m lead): a demo-model change if wanted, before
  they are spooled.
- 0172 runs beside this task in the Flex lane: whoever merges second updates the demo tests' expected numbers.

**GitHub runs:** 7 full runs of the branch. Early pushes: one cancelled by a newer push; one red with three real
failures (the Heavy line's placeholder version, the vessel's WINCH DRUM count, and the tipping drum wire that a Build
baked as standing still – the tipping winches were then taken out, see above); one red on a line break in a test. Then
green four times, three of them only because `main` moved under the branch (0169, 0178, 0177 and 0172 took 0.2.136 –
0.2.138): merge, renumber, run again. Green run 44004866932 on cd1026e, `main` fast-forwarded to it.

**Branches to delete on GitHub:** `task/0174-full-spools` (merged).

