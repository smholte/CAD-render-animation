# 0305 – Study + mock-ups (findings only): the animation panel and exploded views – what to make easier and better

**Who:** worker · **Status:** done 23 Nov (findings; waits for the owner's picks) · **Branch:** `task/0305-study-animation-exploded` (branch only, never
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

- [x] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 23 Nov 2026. Branch `task/0305-study-animation-exploded`
(`[skip ci]`, never merged). Point E (added by the lead while the task ran) is included.

**What changed:** no app code. On the branch: the page `tasks/0305_page/` (`index.html`, 15 pictures in `img/`, the
action ledgers `ledger_crane/mill/product.json`, `freeways.json`; 0.7 MB, no external links) – **the lead publishes it
for the owner's picks** (Copy line `0305 pick: …`, default `A B C D F H I J L`). Scripts in `tasks/0305_proto/`:
`walk.py` (the three walks in the real app, ledger + side-panel shots), `mock.py` (mock-up panels drawn with the app's
own `ui.py` helpers + gpu drawings over the real model: step bars on the time line, numbers + parts list, trail lines,
the ways out found), `freeways.py` (point E: free ways out and rounds, bpy module). Run lines in their docstrings.

**Tested and measured** (web machine, 4 cores, no graphics card; real Blender 5.2.3 + installed app 0.2.214, xvfb,
side panel 292 px, UI scale 1.0; test models `test_crane_a`, `test_gantry`, `test_sequence`):

| Walk (after the import) | Actions | Typed | Section changes | Render button |
|---|---|---|---|---|
| Crane lift, camera rides on the trolley (7.0 s) | 22 | 6 | 1 | ~1,250 px down |
| Mill program, camera keeps the tool in the middle (19.1 s) | 22 | 2 | 3 | ~1,540 px down (G-code step open) |
| Product: one-click product video | 3 | 0 | 1 | – (55 s; 20 s cannot be asked) |
| Product: Explode → pose → orbit / Go to pose / Back to CAD (21 s) | 25 | 7 | 2 | – |
| Product: orbit + Assembly sequence apart / together (21 s) | 18 | 5 | 0 | – |

Build & play 0.0–0.1 s on all three. 11 things the user must know that no panel says (page section 1): typed Starts so
steps play together; a length copied by hand (camera ↔ G-code); the hold invisible; a new Move joint step takes 4
Motion's selected joint; Explode is cumulative (a second Explode explodes the exploded state; Back is in another fold);
"Outwards" barely spreads a coaxial stack; three homes for an exploded view (pose / saved scene in the crane lesson /
Assembly sequence's own places); T1 is assigned in 4 Motion, not in the step; Render animation at the bottom; trail
lines only along an animation; product video ≥ 30 s.

Point E – free ways out (`freeways.py`: round axis first, then ±X/Y/Z; the Assembly sequence's `Rays`; box pre-filter;
rounds with fasteners first; the biggest part stays):

| Model | Parts | Time (1 core) | Rounds | Stuck | Head found / left head first |
|---|---|---|---|---|---|
| test_sequence | 13 | 0.02 s | 5 | 0 | 4 / 4 |
| test_sequence_frame | 9 | 0.02 s | 2 | 0 | 2 / 2 |
| test_crane_a | 20 | 0.04 s | 4 | 2 (cylinder rod in barrel) | 8 / 8 |
| test_atc | 100 | 0.16 s | 5 | 3 | 4 / 4 |
| test_mill_cabinet | 51 | 0.11 s | 8 | 25 (inside the closed enclosure) | 4 / – |
| PC check Heavy (invented, 3.8 M triangles) | 2,992 | 16.9 s | 4 | 100 (parts placed through each other) | plain cylinders |

Spindle unit: every part leaves through the housing's open end (+Z), bolts and locknut first. Without "the biggest
part stays" the housing slid off downwards and the bearings then left sideways. Heads: the end of the round axis whose
points lie furthest out (22 of 24 fasteners; the other 2 are a locknut and a split pin). Pitch: ISO coarse from the
size (M8 = 1.25 mm) or the fine pitch in the name – `core/fasteners.py` parses the size, not yet the pitch.

Comparison (KeyShot, Inventor Presentations, SolidWorks Composer / exploded views, Fusion, Onshape, Blender): a
subagent (Sonnet) read search results only – the help sites are not reachable from the web machine; the page marks it.

**Build tasks (ranked; page section 5):** A starts together / lasts whole + Render on top (S–M, Opus Medium, first) ·
B ready-made steps in the + (M, after A) · C exploded view round 2: live gap from CAD places, along the stack / a
part's axis / radial, save as pose, one exploded state shared with the sequence (M–L, Opus High) · D steps as bars on
the time line, drag to retime (L, Opus High, after A) · E scrub one step (M; may fold into D) · F numbered picture +
parts list, CSV (L, Opus High, Scene & Render lane – labels) · G trail lines on a still exploded view, exploded
turntable (M, after C) · H small fixes: 20 s product video, T1 in the G-code step, "Start scene", lesson vs hint (S,
Sonnet) · I realistic take-apart: own ways, part that stays, rounds, stuck parts leave together, helper processes (L,
Opus High, after C) · J screws and nuts unscrew (M, with/after I) · K kinds of exploded view in one place incl. service
view (M, after C and I) · L right-click: Its way out… / Keep in place / Leaves together with… (S–M, with I). All Motion
lane (`ui_motion.py`, `animation.py`, `states.py`, `sequence.py`) except F; one at a time in that lane (0290 is next).

**Open points / follow-up tasks:**
- Counts after the changes are expectations from the mock-ups, not measured; the walks count operator calls, not
  simulated mouse clicks (a menu = 2, a field = 1 typed).
- Point E not tested: parts that need two moves or a turn to come out (bayonet, lip, circlip), snap fits, a long part
  at an angle through a hole; interference fits drawn as overlap read as "stuck". The rays test straight moves only.
- The Heavy timing is one core; helper processes on a 24-core PC are an expectation.
- Subagents: one (Sonnet) for the program comparison (web search snippets only). No independent review (findings only).
- GitHub runs: none (`[skip ci]`).
