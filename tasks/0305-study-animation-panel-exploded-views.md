# 0305 – Study + mock-ups (findings only): the animation panel and exploded views – what to make easier and better

**Who:** worker · **Status:** open – can start · **Branch:** `task/0305-study-animation-exploded` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Look into improvements to the animations UI." –
"Exploded views improvements.") · **Model:** Opus · effort High
**Area:** findings only; reads `ui_motion.py` (6 Animation, 7 Render queue), `animation.py`, `states.py` (poses),
`sequence.py` (Take apart / Put together), `fade.py` (trail lines), `product_video.py`, `camera_path.py`, the 0200 and
0244 studies. Mock-ups and the page in `tasks/0305_page/`. Not a code slot.

## What to find out

A. **Use it as a new user** on three test sets (no code changes): a 20 s product animation with an exploded view, a
   crane lift with a riding camera, a mill program video – count clicks, scrolls and dead ends; note every place where
   the user has to know something the panel does not say.
B. **Compare** with what users know: KeyShot's animation, Inventor Presentations (storyboard, tweaks, trails), SolidWorks
   Composer, Blender's own timeline – which ideas fit "as simple as possible" (a timeline of step blocks to drag and
   retime? a preview scrubber per step?).
C. **Exploded views:** auto-explode (by assembly level, along an axis, radial, one distance slider), trail lines from a
   part to its place, a saved exploded state as a pose, numbered balloons and a parts list on a picture, one-click
   "Exploded view" picture / turntable.
D. **Mock-ups** of the changed panels (pictures in the app's look) and **ranked build tasks** (gain, work, lanes); the
   page with pick ticks + a Copy line.

## Done when

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
