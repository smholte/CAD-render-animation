# 0310 – 3D page: the lead motions as sliders

**Who:** worker · **Status:** running · **Branch:** `ccr-e50b9f63-gy57vr`
**Started by:** lead, 23 Nov 2026 (owner 21:14: "these sliders for movement could also come to web 3D viewer") ·
**Model:** Opus · effort Medium
**Area:** Web 3D lane – `core/web3d.py` / `blender/web3d.py` (export: one glTF clip per lead motion),
`web/fr_page.js` + the page's CSS (a "Motions" control), `ui_web3d.py` (one tick box), tests, guide, PC check.
**Not:** the lead motions themselves (0309), the Film (0252) apart from how the two share the clock.

## Goal

A client who opens an exported 3D page sees the same short list of machine functions as in the app's drop-down and
drags a slider or presses ▶ to see each one – no app, no Blender.

## Background

- The page plays glTF animation clips with three.js' `AnimationMixer` (`fr_page.js`, ~line 1458) and the Film's own
  camera track (0252). A lead motion (0309) is a set of joints with a value for each slider position, so it can be
  exported as **its own clip from 0 to 1 s** (keys at the positions where any row's window starts or ends, plus enough
  between them for the easing – check with the same tolerance idea as `core/web3d_film.encode`). The slider sets that
  clip's time; ▶ plays it over the lead motion's seconds.
- Moving cables, hoses and other baked looks (0142) follow the joints only where the Film already bakes them; say in
  the report what a lead-motion clip can and cannot carry (cables probably not – then they stay where the page starts).

## What to do

1. Export: a tick box **"Lead motions as sliders"** (on by default when the project has lead motions); one clip per
   lead motion, named after it, with its description and seconds in the page's settings block.
2. Page: a **Motions** control in the same style and place family as the saved-views control (0179; phone layout and
   safe areas): name, slider, ▶, *Back to start*. Using a slider pauses the Film; playing the Film puts the sliders
   back to start. Several sliders at once mix as in the app (0309's rule for two motions on one joint).
3. Measure the page size and load time with and without the clips on the test crane and the demo-size PC-check model.
4. Guide (3D page section), function entry `web3d.lead_motions` (`since=`), the Full PC-check line `web3d.lead_motions`
   (the crane page: slider at 50 % gives the joint values of `core/lead_motions.py`).

## Done when

- [ ] Clips exported per lead motion; the page's sliders and ▶ work on desktop and phone sizes (screenshots)
- [ ] Film and sliders share the clock as above (test); size cost measured
- [ ] Tests added/updated; full suite passes; owner's test steps in the report; merged, version, release

## Not in this task

The app-side lead motions (0309); Fresing Viewer (its V-tasks read the same clips later).

## Design (worker, 24 Nov 2026)

- **Export** (`blender/web3d_lead.py`, numbers in `core/web3d_lead.py`): **one glTF clip per joint** the lead motions use
  (not one per lead motion – see the report): the joint alone is stepped from the lowest to the highest value any lead
  motion gives it (101 values, through `joints.set_value`, followers and mechanisms along; hoses and cables held), every
  plain part's place is read, the parts it moves get a track thinned by `web3d_keys.node_track` (0.1 mm / 0.05°). Clip
  time 0 … 1 s = (value − lo) / (hi − lo); named "Joint 1 …" with Hide part names. Afterwards the joints go back and the
  frame shown is set again.
- **Several joints on one part** (the trolley on the boom): the page composes the joints' clips as moves of the world,
  `M = D_last · … · D_first · M0`, `D = M(v) · M0⁻¹` – exact for joints carried by joints. Which joint carries which is
  measured at export (both set at once in Blender, the order closer to Blender's place wins; `apply` per joint).
- **Page data** `ST.lead = {t, joints: [{clip, lo, hi, apply, kind, parts}], motions: [{name, about, seconds, rows: [{j,
  v0, v1, start, end, easing}], at, ends}]}` (also the file's `extras.fr_lead` for other viewers): the page works out the
  joint values with the app's own formulas (a JS port of `core/lead_motions.values`); a joint in two lead motions takes
  the one moved last (0309's rule). `at` = the slider position of the export's pose, `t` = the animation's moment of
  the frame shown (tubes stand there while the sliders rule).
- **fr_page.js:** the joint clips are kept out of the main mixer and the page's length; `page.motions`,
  `page.setMotion(k, %)`, `page.playMotion(k)`, `page.motionsBack()`, `page.leadState()`, URL `?lead=k:%,…`. A slider
  moved: the animation pauses, its parts stand as in the file, the sliders move them. Play / the time line / the Film:
  the sliders go back to where they started and the animation rules again.
- **fr_player.js:** a **Motions** button in the bottom stack (above the saved views) opens a panel – wide: above the
  stack beside the left tool column, the model stays free to turn; phone: a sheet from the bottom – one row per lead
  motion (name, description, end labels, slider, ▶, "moved by …") and *Back to start*; Esc / Back close it.
- **App:** `FRWeb3D.lead_sliders` ("Lead motions as sliders", default on; shown when the project has lead motions).
  Function `web.lead_motions` (the web entries are `web.*`), PC-check line `web3d.lead_motions`, the tour's web3d stop
  checks the sliders.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 (one session, no subagents).

**What changed:**
- Export: `blender/web3d_lead.py` + `core/web3d_lead.py` (above); `web3d.Job(lead_motions=True)`; the tick box **Lead
  motions as sliders** (5 Scene & Render > Web 3D model, lists the lead motions; also in "On the page").
- Page: `fr_page.js` (joint clips out of the mixer, the slider sum, ▶, Back to start, the hand-over with play / time
  line / Film, `?lead=`, `leadState` in `data-fr-player`); `fr_player.js` (Motions button + panel / sheet, help line,
  layout check, Esc / Back).
- Guide "Motions: the lead motions as sliders" (`#web3d-motions`, picture `docs/img/web3d_motions.png`), function
  `web.lead_motions`, PC-check line `web3d.lead_motions` (MIN_LINES_FULL 150), the tour's Web 3D model stop checks and
  describes the crane's three sliders (crane set `changed`).
- **One clip per joint instead of one per lead motion (deviation from the brief):** with per-lead-motion clips the
  crane's own case breaks – "Boom up and out" at 100 %, then "Boom up" to 50 %: the app keeps the trolley out, but the
  trolley's place in "Boom up"'s clip has the trolley in, and a part's place mixing two joints cannot be split back
  into its joints. Per joint the page gives exactly the app's state, a joint shared by several lead motions is in the
  file once, and the lead motions' rows are plain data in the page and in the file's `extras.fr_lead` (for Fresing
  Viewer). A generic glTF viewer shows the clips as "Joint 1", "Joint 2" (each over its range).
- **What a slider cannot carry:** hoses, cables, wire ropes, spool ropes and track links (drawn by modifiers, 0142) stay
  where the page starts – their shapes are only read along the animation. Mechanisms, followers, cylinders (constraint
  parts), decals do follow.

**Tested and measured** (web machine, 4 cores, headless Chromium with SwiftShader):
- `tests/test_web3d_lead.py` (maths: carrier order, the page sum exact for a trolley on a boom, the joint values = the
  app's, out-and-back rows); `tests/test_web3d_lead_blender.py` (the test crane with its Film animation, exported at
  frame 31: one clip per joint kept out of the animation; each slider alone at 0 / 20 / 45 / 50 / 77.7 / 100 % and four
  mixes give Blender's places within 0.5 mm / 2e-4; in the browser the page's places and joint values at the mixed case
  are Blender's / the app's, a slider pauses, play and the time line give the parts back, ▶ runs to 100 %);
  `tests/test_web_player.py` (Motions at 7 screen sizes animated and still: no overlaps, inside the safe areas, a sheet
  upright; slider, ▶, moved by, Back to start, Space, Esc, Back, help; no button without lead motions).
- PC check `web3d.lead_motions` here: OK, worst 0.08 mm, export 1.6 s, the page at 50 % agrees in chrome-headless-shell.
- Size and load (with / without sliders): test crane 3 lead motions, 2 joints – .glb 197 → 210 KB, page 1.438 → 1.446 MB
  (+7 KB), opens in 1.09 / 1.09 s; PC check's big invented machine (3,050 objects, 3 lead motions on 3 joints moving 816
  parts, 55,118 keys) – .glb 18.2 → 19.1 MB, page 13.58 → 13.91 MB (+2.4 %), export 13.9 → 25.9 s, opens in 17.3 /
  17.6 s (software drawing; the difference is noise).
- Screenshots: `tasks/img/0310_desktop.png` (1000 x 640), `tasks/img/0310_phone.png` (360 x 780).

**Owner's test steps (on your PC):**
1. Update (Update now), then **Help > Make test tour project**, open it, and in the **Test tour** panel pick the stop
   **Web 3D model** and press **Go**.
2. In 5 Scene & Render > Web 3D model you see "Lead motions as sliders" ticked and "Motions on the page (3 sliders):
   Boom up and out, Boom up, Trolley out". Press **Open page**.
3. In the browser: bottom left, above the camera button, **Motions 3**. Click it: a panel with three rows.
4. Drag **Boom up and out**: the boom goes up, then the trolley runs out. Then drag **Boom up** to the middle: the boom
   comes down to about half, the trolley stays out, and "Boom up and out" says "moved by Boom up" in orange.
5. Press **▶** on **Trolley out**: the trolley runs over 3 s. **Back to start**: everything to 0 %.
6. Press **Play** (Space) on the play bar: the animation plays again and the sliders let go.
7. On your phone (send yourself the page): Motions opens as a sheet from the bottom; the phone's Back closes it.

**Open points / follow-up tasks:**
- Hoses, cables and ropes do not follow a slider (above). Following them would need their shapes per joint value.
- The export reads 101 values per joint (big machine: +12 s for 3 joints); a slide joint without followers would need
  2 – a possible speed-up if big exports with many lead motions get slow.
- Fresing Viewer (V-tasks): read `extras.fr_lead` + the "Joint k" clips (not one clip per lead motion).

