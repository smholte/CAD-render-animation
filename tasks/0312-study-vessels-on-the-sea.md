# 0312 – Study + prototype (findings only): vessels on the sea – presets, driving and paths, anything floats and can be hit, waves that break on a beach, the camera under water

**Who:** worker · **Status:** open – can start · **Branch:** `task/0312-study-vessels-on-the-sea` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner 21:14: "the same for the boats / ships as we told earlier for cars, driving
simulation but with ocean waves, and the path creation … this also adds water vessel interaction physics; waves that
break at the beach; the camera looks good under water (adjustable clarity as well); anything can float, and get hit;
different presets for different types of boats and ships, applied and adjusted by a user; a new preset can be saved by
user and organisation." Example he found: https://superhivemarket.com/products/ocean-physics-pro – "don't just copy it,
take inspiration, make it better and easier to use") · **Model:** Opus · effort High
**Area:** findings + design only; prototype in **new files** on the branch (e.g. `tools/vessels_proto/`). Reads the Sea
lane: `core/sea.py` (the spectrum sea, sum of travelling sines, deep water), `core/vessel_motion.py` /
`blender/vessel_motion.py` (0085), `core/vessel_work.py` / `blender/vessel_work.py` (0154: wake, bow wave, thruster
jets, ahead then DP), `blender/sea_view_cut.py` + 0081 / 0143 (seabed, clarity, cut-away, the 3D page under water),
`core/surroundings.py` (SEA, DECK, QUAY), `core/paths.py` / `camera_path.py` (curves), `people.py` (0157 walk paths).
Study **0306** (Vehicles) designs the drive / path recorder for cars – see point C. The page in `tasks/0312_page/`.
Not a code slot.

## The example (lead's notes from its page, 23 Nov – look yourself too; if the site is refused from the web machine, use these)

Ocean Physics Pro (Blender Procedural, GPL, Blender 5.2–5.3, ~$15): you **drive** boats and ships **with the keyboard**
on a real-time ocean; the hull cuts through the waves and leaves a **wake, foam and spray**; **nine ready-made vessels**
or your own model; **record the drive, bake it**, render in EEVEE or Cycles; "shore waves" and "under water" are listed
without details; built with Geometry Nodes. Its FAQ / documentation pages were not read. **Ideas only – no outside code**
(CLAUDE.md: the owner accepts no outside code).

## What to find out

A. **Where we stand**: what today's sea, vessel motion and water effects already do and what they cannot (shallow
   water, a shore, things floating that are not "the vessel", collisions, driving, more than one vessel).
B. **Vessel presets**: kinds a user of this app needs first (RIB, crew transfer vessel, tug, multicat / workboat, PSV,
   cable-lay vessel, a barge under tow, jack-up in transit, a yacht for scale …) – per kind: length, beam, draught,
   displacement, speed range, turning, how it pitches and rolls (0085's response), thrusters / DP, its wake class.
   Applying one to **the user's own model** (pick the hull; waterline from the model), adjusting it, **saving it as my /
   department / company preset** (0272's locations, `.frsetup`). Invented generic test vessels at real size for the
   prototype (the demo vessel's equipment stays private – CLAUDE.md section 6; the bare ship may be used).
C. **Driving and paths**: drive a vessel yourself on the live sea (keyboard; a game controller – 0306 checks whether
   Blender can read one), recorded → smoothed → an **editable path** like a drawn one; a path drawn on the water;
   speed along the path; manoeuvres (turn on the spot with thrusters, approach a monopile or quay and hold on DP).
   **The drive / path recorder is shared with 0306's cars**: if 0306 is done, build on its design; if not, write a
   section "What the shared drive / path tool must do for vessels" so the lead can merge the two designs.
D. **Water**: waves that feel the depth (shoaling, refraction round a shore), **waves that break on a beach** with
   foam (a hand-over with 0311's beach / terrain), spray where the hull slams, the vessel's own waves rocking other
   floating things; cost per frame; what stays exact with `core/sea.py`'s "one place" rule.
E. **Anything floats and can be hit**: buoyancy for any object (container, buoy, debris, a dropped part, a person in
   a life jacket?) from its size and how full / heavy it is, drift with wind and current; collisions – a vessel hits a
   floating object, an object hits a hull, two vessels touch; solved at Build (scripts-off safe, like the cables) or
   Blender's rigid bodies – which, and the cost.
F. **The camera under water**: crossing the surface (the water line across the picture), under-water colour and
   **adjustable clarity** (today's `sea_clarity`), light shafts, bubbles / particles; the same on the 3D page later.
G. **Users**: a sales person picks "Tug" + "Drive" or a ready path; an engineer sets the vessel up; an animator edits
   keys. Phases and build tasks with lanes (the Sea lane owns these files), models / efforts.
H. **Prototype** on the branch: a crew transfer vessel and a tug on a moderate sea – one driven, one on a drawn path –
   a container floating and hit, waves breaking on a beach, the camera dipping under; pictures + short clips; the page
   with pick ticks and a Copy line (`0312 pick: …`).

## Done when

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
