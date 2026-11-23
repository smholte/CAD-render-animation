# 0306 – Study + design (findings only): a Vehicles workspace – suspension rigging, drawn and driven paths, terrain

**Who:** worker · **Status:** done 23 Nov (findings only, branch not merged) · **Branch:** `task/0306-study-vehicles` (branch only, never merged; every
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

- [x] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0306-study-vehicles` (every push `[skip ci]`; never
merged). Page: `tasks/0306_page/index.html` (pick ticks + Copy line `0306 pick: …`; recommended A B C D E H).

**What changed:** nothing in the app. On the branch only, in `tasks/0306_proto/`:
- `spec.py` – the invented **Test car** (SUV size; front double wishbone, steered; rear trailing arm) and **Test truck**
  (18 t, 2 axles, solid axles on leaf springs, twin rear tyres): sizes, masses, springs, dampers, hard points.
- `make_vehicles.py` – writes both as STEP with `demo_model/geom.py` (car 28 parts, truck 32; every part one solid;
  0 overlapping parts) + a points JSON. Written by a subagent (below); I moved the car's rear spring inboard.
- `ground.py` – height grid, speed bumps (long hump, short hump, raised crossing), off-road (waves, ruts, potholes), a
  rigid wheel on the ground (rolling envelope), all wheels / moments at once.
- `ride.py` – path (a **C2 spline**, plain NumPy), speed profile (bends, ramps, stop), Ackermann per wheel, each
  wheel's own rolled distance → spin, the ride: body heave / pitch / roll, independent wheels or solid axles (heave +
  roll), tyres that leave the ground, bump stops, anti-roll bar, braking and corners leaning the body (1 ms steps).
- `kin.py` – double wishbone, MacPherson, trailing arm on the app's own `core/linkages.py` (unchanged): table wheel
  travel → arm angle, camber and wheel move.
- `drive.py` – the live drive model (keys / stick), the recorder → pieces (forward / reverse) → few editable points +
  speed keys; `gamepad.py` – XInput + winmm joystick through ctypes (Windows; structure-checked only).
- `blender_bake.py` (bpy module: import with the app, ground mesh, ride, keys, measure, render),
  `drive_live_blender.py` (real Blender under xvfb, a modal drive with simulated keys), `try_*.py`, `make_page.py`.

**Tested and measured** (web machine, 4 cores, no graphics card; the invented test car / truck):
- Ride over a 75 mm × 3.7 m hump, then a rough track, 20 s drive (505 frames): ride solve 0.61 s (~1.2 ms a frame),
  mechanisms ~1 ms a frame, object keys for 28 parts ~4 ms a frame; pitch −3.2 … +3.2°, roll −3.9 … +1.9°, wheel
  travel −67 … +75 mm. Truck: 666 frames in 0.85 s. 20 m circle at the comfortable speed: car rolls 1.3° at 0.31 g
  (≈ 4°/g, normal), truck 4.5° at 0.18 g (too soft – needs anti-roll in its preset). Import of the car STEP 2.9 s.
- Suspension tables (37 rows): double wishbone 16 ms (camber +0.7 … −2.2°), MacPherson 332 ms, trailing arm 6 ms –
  `core/linkages.py` needed no change.
- Curves: the same 8 clicks as the camera path's Catmull–Rom vs a C2 spline: front wheels jump 12° within 10 cm
  (1,108°/s steering at 30 km/h) vs 0.3° (25°/s). **Vehicle paths must not use the camera path's curve.**
- Recorder (irregular ~60 Hz ticks with hitches): car keyboard 33 s → 3 pieces (142.6 m + reverse 11.9 m + 29.9 m),
  22 + 8 + 5 points, within 25 mm, fit 62 ms; car controller 330 m → 26 points, 35 mm, 68 ms; truck 11 + 6 + 2 points,
  65 mm, 20 ms. One stretch (car, full lock steered while creeping) fits up to 15 % tighter than full lock for a few dm:
  design keeps the drive as driven and clamps steering at Build.
- Real Blender 5.2.3 under xvfb: no game-controller event type exists (196 types checked); simulated keys arrive once per
  press / release; the timer ran 5.9–7.4 Hz because each redraw takes ~135 ms in software drawing whatever the scene
  (5k or 352k triangles) – says nothing about the owner's PC. The drive model sub-steps (20 ms), so a 6 Hz drive ended
  within 1.5 m of an ideal 60 Hz drive after 52 m (it lost a third of the way before that fix).
- Ground: `scene.ray_cast` 21 µs a ray vs 0.15 µs a grid point; a 100 m × 8 m strip at 5 cm by rays = 6.9 s (one core).
- Renders: Cycles CPU, 720 × 405, 24 samples, 3–5 s a frame (pictures on the page).

**Subagents:** one (Sonnet, worktree) wrote `make_vehicles.py` from `spec.py`; its overlap check found my rear spring
inside the tyre – spec fixed, a spring seat added on the arm, re-run: 0 overlaps. No independent tester (findings only).

**Open points / follow-up tasks** (the page's build tasks; a new **Vehicles lane**):
- A ★ vehicle rig + drawn path on flat ground (spline path tool, Ackermann table coupling, wheel spin, steering wheel)
  · B ★ ground height grid + ride + suspension kinds + speed-bump / off-road props · C ★ drive it yourself (shared
  core with 0312) · D ★ game controller (Windows-only: independent review + PC-check line) · E ★ presets, saved as my /
  department / company (0272) incl. the Lifting lane's mobile cranes · F springs that stretch (after 0300's picks) ·
  G trailers, all-wheel steer, tracked machines · H ★ wheels at speed (motion blur; 5-spoke car rim looks still at
  41 km/h at 25 fps, backwards from 20 km/h).
- **For 0312 (vessels):** section 6 of the page – one recorder with a motion model per kind; vessels also need heading
  keys apart from the path direction (crabbing on DP).
- **For 0311 (terrain):** the hand-over is only "a mesh under the path" – any mesh becomes the height grid at Build.
- How smooth a live drive is on the RTX 3090 and whether a pad / wheel is read are PC-check items for D / C.
- In the prototype the springs, dampers and tie rods ride rigidly on one link (a shortcut); the truck's leaf springs
  move with the axle.
