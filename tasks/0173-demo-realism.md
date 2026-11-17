# 0173 – Demo realism from study 0152: lay data, lighter cable, an ROV at the touch-down, the tipping winches spooled

**Who:** worker (web session) · **Status:** running · **Branch:** `ccr-1db7fd83-auleup`
**Started by:** lead, 17 Nov 2026 · **Area:** Demo models lane (`fresing_render/demo_model/`, `blender/demo.py` stages and
captions, `tools/make_demo_*.py`, `tests/test_demo_*.py`) + Flex lane for two small points (`core/catenary.py`'s
`WET_200`; the order in `paths._bake` for a cable that follows a kept-tight wire). **Model · effort:** Opus · High.
Claude Code on the web, environment "CAD-render-animation".

## Goal

The cable-lay demo looks and reads like a real, controlled lay to an offshore engineer: the lay numbers on screen in
the into-the-sea shot, a cable weight that matches real cables, an ROV watching the touch-down, consistent time-lapse
captions – and the last two demo winches (the tipping winches) spool their wire like the others.

## Background

- Study **0152** (`tasks/0152-*.md`, report on `main`) compared the demo with public references: almost everything is
  plausible. Its proposals 1, 2, 3, 4 and 6 are this task (proposal 5 – a fuller carousel – was done in 0159;
  7 and 8 – the pull-in variants – are later, owner decides).
- **0174** (0.2.139) drew every spool layer as cable and gave every demo winch its wire rope, except the two
  **tipping winches**: a Build baked their drum wire standing still, because `paths._bake` reads the places of a cable
  whose speed follows a kept-tight wire *before* that wire's payouts are written. The code that spools them is in
  0174's branch history (commit "every demo winch spooled": a lead cable + `set_follows` ratio ±1) – see 0174's
  report and its winch table. They also have a 6.5° fleet angle (no level wind, 2.6 m lead).
- **0172** (0.2.138) changed the D's gutter / set-down; its tests hold the demo's current numbers.

## What to build

1. **"Lay data" box in shot 8** (0152 #1): top tension, bottom tension, layback, departure angle, lay speed, water
   depth – from `paths_sea.numbers` (the sea stage writes them to the notes today) – shown as a label / card in the
   shot (the app's label system, 0027/0091 style), values changing with the frame where they change. Speed caption
   says **"surface lay"**. Readable in the shot's 4K and HD frames; also in the web page if labels go there (if not:
   say so in the report, no web work here).
2. **Wet weight 51 → ~38 kg/m at Ø 200** (0152 #2; `core/catenary.WET_200`, scaled with Ø² as now). **Lead's choice:
   keep the layback at 32 m** – the catenary's shape stays the same, only the tensions change (bottom ≈ 7.7 kN, top
   ≈ 18.9 kN, 66°), so the cut-away and the touch-down do not move. Update the expected numbers in the catenary / sea
   tests and the demo's notes; check other models that use `WET_200` (test models, the tour) and say which changed.
3. **An invented work-class ROV in shot 8** (0152 #3): box frame with buoyancy block, thrusters, two lights and a
   camera, a tether to the vessel's stern (an app hose/cable if it stays cheap at Build; otherwise a slack tether that
   rides with the ROV – say which and why). One joint (or a rider) keeps it beside and a little above the touch-down
   as the vessel lays; it looks at the touch-down. Lights on in the night shot (0166's shot 13) if the ROV is there.
   Left out of the clash check (as the park, 0166) with its clearance to the cable and seabed tested instead.
   Triangle budget: say what it costs; ≤ ~40,000 triangles.
4. **Handler tilt in shots 9 and 12** (0152 #4): the caption gets its "× N" like the other time-lapse captions (or the
   move is slowed to ~8–10 s – pick one, say which).
5. **Captions in shot 5** (0152 #6): name the tensioner class ("15–20 t tensioner") and the cable ("Ø 200 mm, MBR 3.5 m")
   once.
6. **The tipping winches spooled** (0174's open point): fix the order in `paths._bake` (a cable whose speed follows a
   kept-tight wire reads that wire's payouts after they are written), then spool both tipping winches' drums with
   their wire (0174's code from its branch history). Add a fairlead / short level wind so the fleet angle is ≤ ~2°, or
   say why not. Test: the drum wire's length on the drum changes with the tipping, matching the wire's payout within
   a few cm, and the Build is the same at any frame shown (0138's rule).
7. Every visible change: guide (the demo section), the demo's notes, test-tour/PC-check lines only where a function
   changed (point 6 may need none – say so).

## Design (worker, 17 Nov 2026)

Split (one owner per file):
- **Subagent "rov maker"** (worktree): new `fresing_render/demo_model/rov.py` – `build(p: Params) -> (Asm, info)`, an
  invented work-class ROV in its own coordinates (mm): origin at the middle of the skids' underside, +x forward (where
  camera and lights look), +y port, z up; about 3.0 x 1.8 x 1.9 m. Parts (each ONE solid with a colour, `geom.Part`):
  `ROV FRAME` (box frame of beams, grey), `ROV BUOYANCY` (yellow foam block on top), `ROV SKID` (runners),
  `ROV THRUSTER DUCT` x 7 (4 horizontal vectored at the corners, 3 vertical) each with a `ROV PROPELLER` in a turning
  sub-assembly, `ROV LIGHT` x 2 + `ROV LIGHT LENS` x 2 (front, either side), `ROV CAMERA` + `ROV CAMERA LENS` (front,
  middle), `ROV MANIPULATOR` x 2 (simple folded arms), `ROV TETHER TERMINATION` (top, aft). Joints: one rotate
  joint per propeller "ROV: Thruster k turn" (drive by "operator"). `info`: `tether` (point + direction, mm),
  `camera` (point + view direction), `lights` (points), `box` (min, max), `triangles_hint`. In `layout.py`:
  `FILES["rov"] = "demo_rov.step"`, `"rov"` in `MACHINE_FILES`, built with the park (`with_park`), its info in the
  route sheet as `"rov"`. Test `tests/test_demo_rov_model.py` (no Blender). Budget ≤ 40,000 triangles.
- **Worker:** everything else. `core/catenary.WET_200` 51 → 38; `paths._bake` (kept-tight cables first, then the
  cables whose speed follows a kept-tight joint get their places read again after the payouts are written);
  `core/callouts.py` + `blender/callouts.py`: a label on a cable into the sea may hold live fields (`{top}`,
  `{bottom}`, `{layback}`, `{angle}`, `{depth}`, `{speed}`, `{laid}`, `{hanging}`), several lines; `demo.py`: the lay
  data label and captions, the ROV stage (import, Still, place beside the touch-down looking at it, lights, tether,
  clash hook), the tipping winches spooled (0174's code) with a fairlead.

## Done when

- [ ] Points 1–7; Make demo project runs; its clash check stays at 0 rows (ROV left out, its clearances tested)
- [ ] Expected numbers in the demo / catenary / sea tests updated with a one-line reason each; nothing loosened
- [ ] Stills of shot 8 (lay data box + ROV, day and night if shot 13 shows it), shot 5's caption and a tipping-winch
      close-up, as `tasks/img/0173_*` (the demo is invented – fine to commit), named in the report
- [ ] Make demo time and the project size before/after in the report
- [ ] An independent tester (a subagent that did not write the code) checks points 2 and 6 by reading and running
- [ ] Tests added/updated; full suite passes on GitHub; report filled in; merged; release as usual (section 7)
- [ ] Report ends with the owner's steps (which shots to look at on the RTX 3090)

## Not in this task

- Pull-in variants (0152 #7, #8) – owner decides later.
- Drum layers riding up over crossings (0174's first open point), the full coil on the web page (0174 / Web 3D lane),
  0172's open points 1–4 (Flex lane, later).
- The web player (0179 is running in the Web 3D lane: `fresing_render/web/`, `blender/web3d.py`, `core/web3d*.py`).
- The vessel's freeboard, sea state, lay speed (0152 found them plausible).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
