# 0310 – 3D page: the lead motions as sliders

**Who:** worker · **Status:** open – waits for 0309 · **Branch:** `task/0310-web-lead-motion-sliders`
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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
