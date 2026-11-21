# 0256 – Web 3D page: a quick flick sets the model spinning

**Who:** worker · **Status:** open – waits for 0252 (same files: `fr_page.js`, `fr_player.js`) · **Branch:** `task/0256-web-flick-spin`
**Started by:** lead, 21 Nov 2026 (owner 13:59: "in the 3D web viewer it auto-rotates after a while; additionally I
want, when I rotate fast for a short time and let go, that it starts auto-rotating") · **Model:** Sonnet · effort Medium
**Area:** Web 3D lane – `fresing_render/web/fr_page.js` (the auto-turn block: `stopTurn`, `armTurn`, `input`, the
OrbitControls set-up), `fr_player.js` only for the Auto-turn setting's tooltip / label; the page tests
(`tests/test_web3d*.py` that open a page with `core/web3d_env.read_page`), the PC-check line that checks the page, the
guide's "Web 3D model" section, tour stop `web3d` (`changed=`), `core/functions.py` (`changed=` on the web page's
entry), CHANGELOG.

**Not:** the model-viewer page (Surroundings None – it has no auto-turn today; say in the report whether it should
get both), Film (0252), the export, `site/` (the landing page's models get it when the site is rebuilt).

## Goal

On the web 3D page a short, fast turn with the mouse or one finger, let go while still moving, sets the model spinning
in that direction – like giving a turntable a push. A slow drag still stops where it is let go, as today.

## Background

- Today (`fr_page.js`, "auto-turn"): OrbitControls with damping (`dampingFactor` 0.08); after ~8 s without input the
  page starts turning (`controls.autoRotate`, `autoRotateSpeed` 1.0 = one turn a minute) when the Auto-turn setting is
  on (`page.turn`, address `turn=`, the player's settings: "Auto-turn (after 8 s without a touch)"); any pointer-down or
  wheel stops it (`input()`).
- The owner's aim: as simple as possible – no new button.

## What to build (lead's decisions – small follow-ups if the owner disagrees)

1. **The flick:** a turn-drag (left mouse / one finger – never pan, zoom, a pinch, a part tool's handle or a measuring
   drag) whose turn speed about the vertical over its last ~0.1 s is above a threshold (start around 90° a second;
   tune it so a normal drag never triggers it, and name it in one constant) when it is let go.
2. **The spin:** about the vertical only, in the flick's direction (left or right), starting at the flick's speed
   (capped at about half a turn a second), the tilt kept where it was let go. It eases over ~2 s down to the auto-turn
   speed (one turn a minute) **and keeps turning** like auto-turn, also in the flick's direction – when Auto-turn is
   on. With Auto-turn **off** it eases down and stops (a coasting turntable).
3. Any pointer-down, wheel, key, saved view, Film or part tool stops it, exactly as auto-turn is stopped today; the
   8 s auto-turn after that works as before (it may keep the last flick's direction – say which you chose).
4. Phone: the same with one finger (0179's layout unchanged). Draws only while it turns (the page sleeps again after).
5. The Auto-turn setting's tooltip / label says it in a few words ("… or flick the model to set it turning").

## Done when

- [ ] Page test with synthetic pointer events: a fast short drag → spinning in its direction, easing to one turn a
      minute (Auto-turn on) or to a stop (off); a slow drag → no spin; a pointer-down stops it; a pinch / pan / tool
      handle never starts it
- [ ] PC-check line for the page checks the flick (or a new line `web3d.flick` if that fits better), guide sentence,
      tour stop `web3d` `changed=` (`tour_versions.py --record`), function entry `changed=`, CHANGELOG
- [ ] Full suite + GitHub green; report filled in (the threshold and why)

## Not in this task

Spin about other axes, inertia for pan or zoom, the model-viewer page, Film.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
