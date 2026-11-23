# 0306 – Study + design (findings only): a Vehicles workspace – suspension rigging, drawn and driven paths, terrain

**Who:** worker · **Status:** open – can start · **Branch:** `task/0306-study-vehicles` (branch only, never merged; every
push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39, in short: car suspension in a separate car-rigging
workspace, easy to rig different types; paths added from the user's view with a simple tool, or drive a fully rigged
car yourself and have the path traced – possibly with a game controller for smooth steering, or smoothed afterwards –
and the driven path editable afterwards like a drawn path; ground with height so the suspension works over a speed bump
or an off-road track. Owner's click box 23 Nov: study now, build later) · **Model:** Opus · effort High
**Area:** findings + design only; prototype in new files on the branch; reads `joints.py`, `linkages.py` (0014),
`camera_path.py` (0087), `people.py` (0157 walk paths), `surroundings.py`, the Lifting lane's mobile cranes, study 0300
(springs). The page in `tasks/0306_page/`. Not a code slot.

## What to find out

A. **Suspension kinds to support first** (double wishbone, MacPherson, multi-link, solid axle with leaf or coil springs,
   trailing arm; bogies / tracks for machines?) and how to rig each from a STEP in a few clicks: pick the wheels, the
   knuckles, the arms → joints + mechanisms + springs; steering with Ackermann; wheels turning with the distance driven.
B. **Following a path on uneven ground:** each wheel on the ground (a ray per wheel per frame), the body's pitch and roll
   from the suspension travel (a spring-damper per wheel solved at Build, scripts-off safe), a speed profile along the
   path; the cost per frame.
C. **Paths:** drawn from the view (click on the ground, a smooth editable curve); **driving it yourself** (keyboard; a
   game controller on Windows – can Blender read one, or a small helper through XInput? check), the drive recorded →
   smoothed → an editable path like a drawn one.
D. **Terrain:** ground with height (a height map or a mesh), a speed bump, an off-road track, an imported terrain.
E. **An invented generic test vehicle** at real size (car and a truck) for the prototype; phases and build tasks with
   lanes; the page with a design sketch and pick ticks + a Copy line.

## Done when

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
