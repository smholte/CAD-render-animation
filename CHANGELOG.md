# Changelog

What changed in each version, in plain words. Newest first. The app shows these texts under
"What's new" when it offers an update, and each GitHub release carries its section. From 0.2.14 on,
the release page (tag `v<version>`) shows the commit; before that, "Commit" is the Git commit the
installer of that version was built from.

## 0.2.14 – 5 Nov 2026 – updates inside the app (task 0020)

New versions with one click
- A few seconds after the app starts it looks on GitHub for a newer version. When there is one,
  **Update available** appears at the top of the Fresing tab, with **What's new**.
- **Update now** downloads the new version (and checks it), saves your project, closes the app,
  installs the update and opens the app again with the same project – about a minute. Then it says
  **Updated to …**. Projects, renders, templates and settings stay as they are.
- **Help > Check for Fresing Render updates** asks at any time. **Later** hides the notice until the
  next start. It can be switched off: Edit > Preferences > Add-ons > Fresing Render > **Check for
  updates at start-up**.
- An update also brings the app layout of the new version along (before, only Install.bat did).
- New line in the self-test: "Update check" (can this PC reach the updates on GitHub).
- Every new version is published on GitHub by itself, with the installer for new PCs:
  https://github.com/smholte/CAD-render-animation/releases

**Once more by hand:** this is the first version that can update itself. Run this installer once
over the old version on every PC; from then on updates come with **Update now**.

## 0.2.14 – 5 Nov 2026 – more parts sorted by supplier codes (task 0022)

Commit `2f7bf7a`.

3 Looks – sorting on import
- Many more supplier catalogue codes are recognised, Misumi above all (shafts, collars, pins,
  linear bushings, shaft supports, guides, cam followers, bushings, couplings, pulleys, urethane
  washers and bumpers, hinges, handles, toggle clamps, floating joints, frame nuts…), plus SMC
  JCQ cylinders, THK blocks, Omron RFID and more. Also when the code sits in a longer name
  ("PSFJ20-300_SHAFT", "_LMUW20_1").
- The switch of an SMC cylinder ("JCDQ-M9B") is a switch, not the cylinder body.
- Fewer wrong groups: a part called "PALLET" (a conveyor's workpiece pallet) is no longer made of
  wood (wooden and Euro pallets still are), "LINK" is a link bar instead of a chain, a "SENSOR
  POST" is a post.
- On the EGR test model (GrabCAD): 67 % of the placed parts sorted (was 55 %).

## 0.2.13 – 5 Nov 2026 – rule sets: one naming scheme per company (task 0015)

Commit `b5d716b`.

3 Looks
- **Rule set** at the top of 3 Looks: the sorting rules, the material of each group and the
  group names in one package – one for your company, one for each client with other part names.
  **Standard** is built in and read-only. **Manage rule sets** has **Copy…**, **New, empty…**,
  **Rename…**, **Delete…** and the rule set new projects start with.
- Rule sets are files in the shared library (folder `Rule sets`), so colleagues use the same
  ones; without a shared library they are kept in `Documents\Fresing Render\Rule sets`. Every
  project keeps its own copy, so it opens the same without the library.
- Switching a project to another rule set shows first what changes (parts that change group,
  new groups, groups that go away, unsorted now and after) and asks. Parts you put in a group by
  hand stay there; painted faces are sorted again too; Ctrl+Z goes back.
- Changes in a project (rules, group materials, **Make it a rule**) show as "Changed in this
  project: …" with **Save changes** and **Save as new…**. **Save changes** warns when a colleague
  saved a newer version meanwhile; "The library has a newer version" offers **Load it…**.
- Templates remember their rule set by name and keep a copy. Older templates and projects open
  unchanged: their rules become the rule set "From this project" (or Standard, when untouched).
- Preferences: **Default rule set** for new projects.
- Self-test: new line "Rule sets folder" (the folder can be written).
- User guide, chapter 3: new part "Rule sets", with a picture.

## 0.2.12 – 5 Nov 2026 – surroundings: sea, vessel deck, quay, factory halls

Commit `e658aab`.

5 Scene & Render – Background
- New built-in surroundings, made by the app itself (nothing to download): **Open sea**,
  **Vessel deck**, **Quayside**, **Clean factory hall**, **CNC machining hall**, **Assembly
  hall**, **Warehouse**. The machine stands on the floor (its lowest point, centred); the
  surroundings grow with the machine. **Simple** or **Detailed**.
- Sea: calm or rough, foam on the wave tops, waves that move in videos (or stand still).
  Open sea: the water level can be raised or lowered.
- Halls never hide the machine: walls are seen only from inside (a camera outside looks in),
  anything between the camera and the machine is left out of the picture, and the roof
  structure is left out when the camera is above it.
- **360° photo** now stands the machine on the photo's ground with its own shadow
  (**Stand on its ground**, **Photo taken at**). A link in the panel and the new guide
  `docs/SURROUNDINGS.md` list good free photos (Poly Haven) and how to add them to the library.
- **Props for scale** (new sub-panel): person 1.8 m, 20 ft container, euro pallet, safety
  barrier. One click puts one next to the machine; move it like any object; show/hide all in
  one click (also per saved scene).
- Saved scenes, templates and the render queue keep the surroundings.
- Every setting and button in 5 Scene & Render has a tooltip that says what it does.
- User guide, chapter 5: "Background & surroundings" and "Props for scale", with pictures.
- Render time on the processor (test machine): sea, deck, quay and photo about the same as the
  studio; halls about 1.4–2.8× (details in `docs/SURROUNDINGS.md`).

## 0.2.11 – 5 Nov 2026 – user guide (task 0021)

Commit `45af7cc`.

- A user guide: what each section 1–7 is for and how to work through it, step by step, with
  pictures of every panel; getting started (your first render in 10 minutes), export tips for
  Inventor and Fusion (AP214/AP242), and a troubleshooting page (self-test, where renders go,
  the queue). It covers everything up to this version, also painted faces and several joints on
  one subassembly. One page that works offline; it prints well (Print > Save as PDF).
- Open it from the app: **Help > Fresing Render user guide**. Also in the Start menu
  (Fresing Render > "Fresing Render - User guide") and as "User guide.html" next to Install.bat.
- The guide ships inside the extension, so an update always brings the guide of that version.
- For the other chats: a tooltip style guide, a tooltip check (`tools/tooltip_report.py`) and a
  list of the 93 tooltips still to write, with suggested texts (`docs/TOOLTIPS-TODO.md`).

## 0.2.10 – 5 Nov 2026 – Several joints on one subassembly (task 0011)

Commit `2d89872`.

4 Motion
- A subassembly can now have more than one joint, and the moves add up. Example: joint 1
  slides it 1000 mm in Y, joint 2 slides it 500 mm in X: it ends up at X +500 / Y +1000.
  Works for any mix of rotate and slide, and for three or more joints.
- How: click a subassembly that already moves with a joint and press Add rotate joint or
  Add slide joint as usual. Above the buttons it says "Adds a joint on top of '…': the moves
  add up". The new joint rides on the older one: its axis moves along with it (like a crane:
  slew, then luff).
- The joint list shows a joint that rides on another one indented right under it. The
  details of that joint show "Rides on '…'" and a "Swap order" button: the other joint then
  rides on this one. With two slides nothing changes; with a rotation it does (turn then
  slide, or slide then turn). Swap works when the lower joint moves only what the upper one
  moves (otherwise the button is grey and its tooltip says why).
- Removing a joint from a stack: what it moved goes back to the joint under it, and joints
  riding on it move down. Taking a part out of the top joint ("Remove" under Set-up) puts it
  back on the joint under it.
- Set-up of the lower joint: "Moves:" lists what it moves through the joints on it, and
  "Carries:" names those joints. "Select" selects all of it.
- Poses, "Everything back to CAD position", Explode, animation steps (one after the other
  or at the same time), Fit camera, limits, Flip, rotate/slide, undo and model updates all
  work with stacks. A joint list keeps its order after a model update.
- A selection where one part already moves with a joint and another does not (or with
  another joint) is refused with an explanation, before you click the pivot.
- Projects made with earlier versions open unchanged.

## 0.2.9 – 5 Nov 2026 – painted faces

Commit `2f35b33`.

3 Looks – paint single faces
- Faces painted in CAD come in painted. A face with its own colour (or its own Fusion/Inventor
  appearance) keeps it; the rest of the part keeps the part's material. A sorting rule on the
  colour can give such faces another material (for example "Colour is #C0C0C0 → anodised").
- New fold "Paint faces" in 3 Looks: pick a group, press "Paint faces…", click faces on the
  model. A click paints the whole CAD face; Shift+click gives it back the look of the part;
  Enter or right-click ends. Undo works.
- Every copy of a part gets the same painted faces; "Only this copy" paints one copy only.
  Each painted face set can get another group ("Other group…") or go back ("Whole part").
- A model update keeps painted faces of parts whose faces did not change; the report lists the
  parts that lost them.
- Wire mesh panels now have real holes (25 mm mesh), so you can see through them.
- "Aluminium, black anodised" (ready-made materials) uses the new black anodised material.
- Projects made before 0.2.8 that still had the old standard rules get the new rules (part types,
  CAD materials) when opened; projects with their own rules keep them.
- The part you clicked shows its CAD material name too; every button and setting in sections
  1–3 has a tooltip.


## 0.2.8 – 4 Nov 2026 – most parts get their material on import

Commit `4fd1d3b`.

3 Looks – sorting at import
- A library of 63 part types sorts most parts by their name: aluminium profiles (anodised),
  caps, connectors, plates and brackets, shafts and pins, chrome piston rods and guide shafts,
  covers, sheet metal, welded frames, pneumatic cylinders and grippers, valves, fittings,
  hoses, pipes, linear guides, ball screws, bearings and bearing units, bushings, couplings,
  gears, pulleys, chains, belts, springs, seals and O-rings, rubber buffers, cables, cable
  chains, cable glands, sensors, light curtains, motors and gearboxes, cabinets, electrical
  parts, push buttons, emergency stops, signal towers, robots, handles, levelling feet,
  casters, conveyor rollers, hinges, windows and plexiglass, wire mesh, gratings and stairs,
  labels, mannequins, tooling, shackles and wire ropes, winches and sheaves. Each gets its own
  group with a fitting material.
- It reads English, Dutch and German names, common typing errors, and order codes of many
  suppliers (SMC, Festo, igus, SKF, HIWIN, Sick, ifm, Rittal, Siemens, Ganter and more).
- Parts inside a bought assembly follow it: the "BODY" of an SMC cylinder is the cylinder
  (anodised), its "ROD" the chrome piston rod; a motor or sensor stays one colour. Machine
  stations ("… UNIT", "… SYSTEM", "… STATION") never pass their name on to their parts.
- A material in the name is used: "PLATE RVS" is stainless, "BLOK POM ZWART" black POM.
- Material and appearance names from the STEP file are used (Fusion 360 writes them, for
  example "Aluminum - Satin", "Rubber - Soft", "Paint - Enamel Glossy (Red)").
- The CAD colour only colours paints and plastics; metal, rubber and glass keep their look.
- New order of the sorting rules: fasteners → part type → CAD material → CAD colour →
  Unsorted. Projects made before keep their own rules; "Defaults" in the rules fold gives the
  new list.
- 8 new materials: nickel plated, black anodised aluminium, zinc die-cast, belt rubber, foam,
  felt, mannequin, wood.
- Self-test: new line "CAD material names and part types".

## 0.2.7 – 4 Nov 2026 – Structure and Looks: tree, find & sort

Commit `552a654`.

2 Structure
- The list is a tree like Windows Explorer: open and close each subassembly with its arrow
  (or all at once). "Levels shown" is gone.
- Click a row: that part or subassembly lights up in the view. The arrow at the end of a row
  adds it to the selection, so several rows can be selected.
- Click a part in the view: the tree opens down to it and marks its row.
- Identical parts next to each other are one row ("× 4"). Identical subassemblies get their
  number (":1", ":2", or the occurrence number from the CAD file), at the right end of the
  row so it stays visible when a long name is cut off. The full name is in the box under
  the list.
- Every part row shows its material colour.
- "Find in the tree" filters the tree and keeps the subassemblies above each match.
- Under the list: the selected row with "Zoom to it" and its lock.
- "Show only" hides everything else; a red box and "Show everything again" bring it back.
  Parts you hid yourself stay hidden.

3 Looks
- New fold "Find & sort parts": type a word (several words: all must fit; * = any text),
  tick the parts you want, put them in a new group (named after the search) or an existing
  one. "Make it a rule" puts the search on top of the rules, so the next revision is sorted
  the same way. "Only inside …" searches one subassembly.
- "Common words in unsorted parts": one click searches for the word.
- "Show only the unsorted parts", and "Show only these" per group.
- "Ready-made material…" per group: 28 machine materials (aluminium profile, anodised,
  stainless, chrome, galvanised, rubber, POM, polycarbonate, RAL paints, LED, …).
- "Rule: all of <subassembly> → this group" for the subassembly selected in 2 Structure.
- A part clicked in the view shows its group, with "Move selected to group…".

## 0.2.6 – 3 Nov 2026 – faster import, self-test checks the new features

Commit `b414a73`.

- The STEP reader takes each part's triangles from OpenCascade in one block instead of one
  point at a time. EGR line on the 2-core test machine: meshing 24.0 s → 17.7 s on one core,
  17.7 s → 14.8 s with 2 helpers; the result is identical to before, to the last bit.
- Self-test: new line "Animation time test (queue)" (the Time test button, run on your PC);
  the HD render line says whether noise removal ran on the graphics card.

## 0.2.5 – 3 Nov 2026 – side panel redesigned

Commit `e85321b`.

- Every section reads top to bottom: what you choose comes before its button.
- The main button of each section is big and blue: Import STEP, Render image,
  Render animation, Start queue.
- No cut-off labels at the normal side-panel width. Lists fit their items and show names;
  the details of the selected item are right under the list.
- Rarely used settings are folded away ("More", "Files & graphics card", joint "Set-up").
- Every panel header shows an icon and its state (model, parts, unsorted parts in red,
  joints, animation length, queue progress), also when the panel is closed.
- How-to steps where a section starts empty; "Selected: …" above Add joint.
- Renamed: "Open result" → "Open", "Back to CAD position" → "Everything back to CAD position",
  Clean-up "Remove for good" → "Remove selected".

## 0.2.4 – 3 Nov 2026 – faster animation renders

Commit `08a0f08`.

- Noise removal runs on the graphics card (Blender's default was the processor).
- Animation frames use lighter light-bounce settings: 44 % less render time per frame on
  the EGR line test, no visible difference.
- "Time test" renders two frames and shows how long the whole animation will take.
- "Show in folder" for queue results and for Render image.
- The queue log shows render and save time per frame.

## 0.2.3 – 3 Nov 2026 – import on all processor cores

Commit `72dce5e`.

- Big STEP files are meshed on all cores but one, at below-normal priority.
- A part that cannot be meshed is reported and skipped; the rest of the import goes on.
- Self-test line "Fast import (all cores)"; the import panel shows how many cores were used.

## 0.2.2 – 2 Nov 2026 – first working installer

Commit `0e21353`.

- Installer fixed: every earlier installer stopped with a PowerShell error before installing.
- Live preview and Render image no longer freeze the app.
- Big models: no false "moved" parts after an import, faster poses and animations.
- Queue keeps the PC awake; renders of unsaved projects go to Pictures\Fresing Render.

## 0.2.1 – 2 Nov 2026

- The Desktop shortcut opens the app with the Fresing panel (it was missing).
- Side panel opens on the Fresing tab; the view is framed on the model after import.

## 0.2.0 – 2 Nov 2026 – phase 2: motion

- Joints (rotate, slide, chains, limits; axis by clicking a hole or shaft), poses,
  exploded views, visibility sets, saved scenes.
- Animations from steps (joint moves, poses, camera moves, show/hide), Build & play.
- Render queue in a background Blender (images and MP4), keeps going when the app closes.
- Update to a new STEP revision keeps all work; "in use by" lock for shared projects.

## 0.1.0 – 2 Nov 2026 – phase 1: stills

- STEP import with assembly tree, names and CAD colours; fasteners recognised by name and
  sorted into material groups; RAL colours; paint schemes and templates.
- Backgrounds (colour, 360° photo, sky, transparent), studio light, floor, cameras, sizes
  from 16:9 to A3 at 300 dpi; GPU rendering; Windows installer; self-test.
