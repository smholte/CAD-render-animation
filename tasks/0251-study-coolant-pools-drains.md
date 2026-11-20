# 0251 – Study + prototype (findings only): coolant that pools in the cuts, moves with the machine and runs to the drain

**Who:** worker · **Status:** open – can start (findings only: a prototype on its own branch, `[skip ci]`, only the
`tasks/` files go to `main`) · **Branch:** `task/0251-study-coolant-pools`
**Started by:** lead, 20 Nov 2026 (owner 23:45: "I also want coolant fluid to simulate on the machine. So when milling
collecting in the cut slots, moving around with the motions and going down in the drain." His picks 23:50 in the
answer box below.) · **Model:** Opus · effort High
**Area:** Machining lane – read `core/coolant.py`, `blender/coolant.py` (0042: jets, drops, splash, wet sheen, every
frame from the frame number), `blender/machining.py` / `core/machining*` (the cut mesh and its pockets / slots),
`core/chips.py` (how chips land and pile – the nearest thing to what is wanted), `blender/animation.py` (the joints'
motion per frame). Prototype code only on the branch; nothing merged to the app.

## Owner's picks (20 Nov 23:50)

- **Study + prototype first**, a page with pictures / short videos so he can pick.
- **Path of the liquid:** fills the cut pockets and slots → spills over onto the table → runs along the T-slots and off
  the table's ends → **chip tray / way-cover troughs → down a drain hole**.
- **Shown in:** Cycles and EEVEE renders **and** the 3D view while playing (the web 3D page later).
- **Machine:** the new larger VMC (0249, which gets a chip tray and a drain). The study can use today's test mill and
  a plain stand-in tray; the build task comes after 0249.

- **Tested on 3, 4 and 5 axis + stand-alone fluid tests** (owner 23:48): every method is tried on (1) the 3-axis
  test mill (pockets and slots filling, the table moving in X / Y), (2) the 4th-axis mill (liquid on the turning bar
  and the rotary table – it runs off as the bar turns), (3) the 5-axis trunnion (the cradle tilts: pools spill and
  run to the low side), and (4) **stand-alone fluid tests without a machine** – small invented test models of their
  own, each proving one thing with a number: a closed pocket fills to a known volume and holds it; an open slot drains
  out at its end; a plate tilted 0 → 30° spills at the right angle; a tray with a slope empties down its drain in a
  measured time; a box moved and stopped hard sloshes and settles; nothing leaks through a wall. Propose these as tour
  stops and automatic tests for the build task (a new learning / test set "Coolant liquid").

## Questions to answer

1. **Method.** Compare at least:
   a. a **shallow-liquid height field** on the wet surfaces (part, table, tray): a grid baked at Build (water depth +
      flow per cell, gravity + the table's acceleration from the joints' motion, fill from the jets' flow rate, run-off
      at edges / into T-slots / to the drain), drawn as a thin mesh with a liquid material;
   b. **particles baked at Build** (SPH / position-based: a few thousand drops that pool), drawn as a meshed surface or
      metaballs;
   c. **Blender's own liquid simulation** (Mantaflow FLIP) on a small domain round the table;
   d. anything better found (web search works: real-time fluid in games, machining-sim products – public sources, no
      maker's code).
   For each: how it looks (pictures + a 5–10 s video of a pocket filling, the table moving in X and the liquid
   sloshing, run-off to the drain), Build time, per-frame cost in the 3D view, render cost (Cycles / EEVEE), memory /
   cache size on disk, whether it gives the same picture for the same frame whatever was shown before (0042's rule),
   and how it behaves on the demo-sized projects.
2. **Pockets and slots.** How the liquid finds the cut's low spots: from the cut mesh (`machining`) or a height map of
   the workpiece's top; open slots that run out at the part's edge drain, closed pockets hold.
3. **Moving with the machine.** The table / part move (X / Y joints, 4th / 5th axis tilt): the liquid follows the part,
   lags with acceleration (sloshes), spills when tilted. What the head's motion does (nothing, except the jets).
4. **Amount.** Flow rate from today's coolant settings (flood / mist / off, `gcode_coolant` spans), chips in the
   liquid (do they float / settle?), M9 → the pools drain slowly, the film dries (0042's wet sheen).
5. **The drain.** What 0249's VMC needs: tray shape, slope, trough along the way covers, the drain hole's place and
   size – written as a short list **for 0249's maker** (the lead adds it to 0249 / 0250).
6. **Settings the user sees.** As few as possible (owner's aim: simple): probably one "Liquid on the machine" tick box
   in 4 Motion > CNC machine > Coolant, a Detail choice tied to Draft / Normal / Final.

## Page and report

`tasks/0251_page/index.html` (published by the lead): the methods side by side with pictures and the short videos
(test models only – never the Fresing 400 or the demo's equipment), one row per test (3 / 4 / 5 axis, each stand-alone test), the numbers table, the lead-recommended method
first. The report: the recommendation, the build task(s) split by lane with sizes, what 0249 needs for the drain, open
points, the branch (kept for the build task's prototype code or deleted).
