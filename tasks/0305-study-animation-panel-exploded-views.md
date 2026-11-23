# 0305 – Study + mock-ups (findings only): the animation panel and exploded views – what to make easier and better

**Who:** worker · **Status:** running · **Branch:** `task/0305-study-animation-exploded` (branch only, never
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
E. **Realistic exploded views – parts leave the way they really come out** (owner 23 Nov 20:41, added while 0305
   ran): "recognize how the parts sit in each other and in each subassembly … a bearing sits in a housing, the app
   recognizes that the bearing … can only exit through one opening, the same for bolts, they exit out of the hole
   with their head not going in the part (bolts and nuts also unscrew) (also have different types of exploded
   views)". Today Take apart (`sequence.py`) moves every part of a step in **one** direction and only warns when a
   part hits another on its way. Find out: (1) the **free directions per part** from the geometry – which way a
   part can leave its neighbours (a bearing out of its bore only through the open side, a pin along its hole, a
   shaft out of the side without a shoulder); methods (rays / swept boxes as today, contact faces and their
   normals, round faces = an axis), what works on 2,000+ parts and how fast; (2) **bolts, screws and nuts** along
   their own axis, head side out, **turning while they unscrew** (pitch from the fastener notation, 0030; a few
   turns shown, then the straight move), nuts off the thread first, washers after; (3) the **order** from what
   blocks what (fasteners first, then the parts they held, inner parts out through the opening that is free),
   per subassembly and between subassemblies; (4) **kinds of exploded view** to offer – e.g. realistic
   take-apart (the order and ways above), straight along one axis (today), radial / spread for a picture, by
   assembly level, a service view (only the parts of one job come out) – one line each on what it is for; (5)
   where the user corrects the app (a part's way, a part kept in place) with the fewest clicks. Rank these as
   build tasks like the rest (gain, work, lanes – they touch `sequence.py` and the Motion lane).
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
