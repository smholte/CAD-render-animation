# Changelog

What changed in each version, in plain words. Newest first. The app shows these texts under
"What's new" when it offers an update, and each GitHub release carries its section. From 0.2.16 on,
the release page (tag `v<version>`) shows the commit; before that, "Commit" is the Git commit the
installer of that version was built from.

## 0.2.76 – 13 Nov 2026 – hoses, cables and drag chains follow the motion (task 0058)

New: 4 Motion > **Hoses and drag chains**
- **Hoses and cables bend along when the machine moves.** Click the hose in the 3D view and press **Add hose** (or
  **Add cable** for a soft one). The app reads its middle line, diameter and length from the CAD part and finds the
  part each end touches (its fitting). From then on both ends stay on their parts, the hose keeps its length, bends
  smoothly and hangs under its own weight. The stiff CAD part is replaced by a tube of the same diameter in the
  part's own material. Settings: **Stiffness** (soft cable … stiff hydraulic hose), **Sag**, **Smallest bend**,
  **Length**, **Diameter**.
- **Drag chains roll over their bend.** Click one link and press **Add drag chain**: the app takes the whole row of
  links, reads the link length and the bend radius from the CAD pose and works out which end is fixed. When the axis
  moves, the CAD links are laid along the chain again – two straight runs and the bend, which moves at half the
  speed of the moving end. A chain drawn as one solid gets links drawn by the app. **Upper run**: straight, or lying
  on the lower run (long chains). **Swap ends** if the wrong end is the fixed one.
- **Find hoses and chains** selects the parts that are a hose, cable or cable chain by their name; **Find and add
  all** adds them in one go. Names such as "HYDRAULIC HOSE ARM" and "ENERGY CHAIN LINK" now sort into Hoses & tubing
  and Cable chains (before: brackets, frames or plain chains).
- **It works wherever the motion shows:** while you pose, in Build animation, in the render queue, in stills of saved
  scenes, turntables, G-code programs and cylinders driven by their stroke. Build animation works out every frame's
  shape once and keeps it with the project, so the same frame always looks the same and playing or rendering costs
  no extra time worth naming.
- **A hose stays on the side CAD drew it on.** A slack hose can often lie in two ways; it keeps the one of your CAD
  model instead of flipping over. (A hose pushed together until it forms a loop, or a very soft cable, can still
  change over once.)
- **Warnings** in the panel and after Build: "Hose 'X' is too short at frame 120 (it needs 12 mm more)", a bend
  tighter than the smallest bend you set, a drag chain that cannot reach.
- **Fit to the CAD pose** puts back what the CAD file says (length, ends, link length, bend radius). An end on the
  wrong part: click the right part, then the pipette beside that end.
- **Model update** keeps hoses and chains with their settings. The **clash check** leaves them out (they bend with
  the parts they join). Projects without hoses or chains are untouched.
- Measured on the 4-core test machine (no graphics card), the PC check's big machine (3,000 parts) with 20 hoses and
  3 chains of 40 links: 6–7 ms more per frame; Build animation about 4 s longer for 250 frames. Expected on your PC:
  faster (not measured yet).
- Not in yet: hoses do not push against other parts or each other; cables over sheaves and winch drums come with the
  motion paths; hoses with three ends; cable bundles.
- Test tour: two new stops, "Hoses and a cable follow the arm" and "Drag chains roll with the axes". PC check: a
  new line "Hoses, a cable and drag chains follow the motion". User guide: section "Hoses and drag chains".

## 0.2.75 – 12 Nov 2026 – demo vessel: the cradle rollers turn the right way (task 0097)

In the demo cable-lay vessel the 66 side rollers of the 33 roller cradles turned about a wrong, nearly upright axis and
wobbled through the cable. Now every roller turns about its own axis. Projects made before need Help > Make demo
project again.

## 0.2.74 – 12 Nov 2026 – brushed, ground and turned parts shine the right way (task 0098)

The bright band on a brushed or ground plate now runs across the brush lines, and on a turned shaft along the shaft –
as on real parts. Before, it ran the wrong way round. Older projects get the corrected look when you open them. The
material sheet picture in the guide is new.

## 0.2.73 – 12 Nov 2026 – tool marks on cut faces (task 0061)

Milling (4 Motion > Milling)
- **Cut faces show the marks of the tool that made them**, in the direction it went: the arcs of a face mill on a
  faced top, the finer arcs of an end mill on a pocket floor, fine upright lines on walls, a level line where each
  depth of a wall starts, rings in a drilled hole, lines along a chamfer, fine lines across a ball-mill pass. The
  **sheen follows the marks**: on a faced top the bright band swirls with the arcs when the camera or the light
  moves. Where a later tool cuts a face again it shows the new tool's marks; the rest keeps the old ones.
- The distance between the marks is real: from the program's **feed (F) and spindle speed (S)** and the tool's
  number of teeth. Without a program the app takes a typical feed for what the block is made of. A line in the
  panel says which one is used.
- Three new settings under **Cut faces**: **Tool marks** (on by itself, also in older projects), **Mark size**
  (1 = real, often only 0.05 to 0.3 mm apart, so a picture of the whole machine shows the sheen; raise it up to 10
  for a close-up) and **Strength**. Crisp on aluminium, finer on steel, dull on cast iron, faint on plastic and
  on paint.
- **No more dark patches in reflections on cut faces** (and on the block's faces next to a cut): the app now works
  out the milled block's shading itself. Flat faces are flat, round walls smooth, sharp edges crisp.
- Scrubbing is as fast as before: while the frame changes the block is shaded the quick way, a moment after it
  stands still – and in every render – it gets the exact shading. Measured on the 4-core test machine: 29 ms a
  frame on a 28,000-triangle cut (34 ms before), 2.9 ms on a small one (2.7 before). A close-up render with marks
  took 31 s against 28 s without (Cycles on the processor, 640 x 384).
- Works with "Auto Run Python Scripts" off, in the render queue, after a save and reopen and after a model update.
- Test tour: new stop **Tool marks on cut faces** (a faced strip, a pocket in two depths, a drilled hole, seen
  close). PC check: new line **Milling: tool marks on the cut faces**. User guide: Milling > Tool marks.

## 0.2.72 – 12 Nov 2026 – clash check: fast with parts that turn in place (task 0092)

Clash check (6 Animation > Clash check)
- **Parts that turn in place** – rollers, sheaves, drums, a coil, a shaft or a pin in its bore – are now found by the
  check itself: a part that turns about an axis that stays put (against the world, or against the carriage or the
  vessel it rides on) and is round about that axis fills the same room at every angle, so it is held where it is and
  only moves with what carries it. You no longer need to leave such parts out.
- A part that turns but is **not round** – a flat or a key on it, a sprocket's teeth, a cam, a wheel turning off its
  round centre – is still checked at every moment. Only a part resting against it well away from what is not round
  (the rope in the groove of a sheave with spokes) is checked once per turn.
- **Big parts far apart** are passed over quickly (no point-by-point test until they have moved close), and a test
  where no faces cross is much shorter.
- On the demo vessel (1,378 parts, 1,824 moments) the whole animation **with** its 222 turning rollers, wheels, the
  coil and the carousel is checked in about 12 minutes on a 4-core test machine (0 clashes); before, it had not
  finished after 47 minutes. Expected on your PC: faster (not measured yet).
- Two wrong results fixed: a part that slid far while hardly turning was put centimetres to kilometres off its path
  between two frames (false clashes of 1–2 mm at sea); and a point next to a big part with tiny gaps between its
  faces could read as deep inside it (a false clash of 577 mm between the carousel's rim fence and its drive).

## 0.2.71 – 12 Nov 2026 – demo: quadrant wires as on your vessels, cable engine and handling winches moved (task 0095)

Demo project (Help > Make demo project; make it again for this version)
- The **A&R wire** is always on the D-quadrant's new eye at the top of its curve: straight along the deck from its
  winch while the D travels aft (the winch's drum turns as the wire pays out), over the handler's top pulley once the
  handler tilts. The sheave at the handler's hinge is gone; the top pulley sits beyond the handler's end, under the D
  as it rolls on.
- The two **tipping wires** come up their swivel posts, over the swivel sheaves and down to the D's bottom corners
  (the ends of its straight bar) once it is on the handler; the sheave heads turn with the tilt.
- The wires follow the joints by themselves, also in the render queue and at any frame rate.
- **Shot 7** ends with the handler at 100°: the D stands vertical, curve up, hanging from the A&R wire over the top
  pulley, both tipping wires on. It no longer tips on the handler (that comes with lowering it into the sea).
  "Quadrant tip" now turns the D about its A&R eye.
- The **cable engine** stands on the lower path, just forward of tensioner 2; rollers took its place on side B.
- The two **handling winches** stand forward, one each side of the A&R winch, each in line with a tensioner, their
  wire leading aft at the cable's height; 80 % of the old size, still with the Lebus drum (shot 6 shows it).

## 0.2.70 – 12 Nov 2026 – joints made fast in one go; a moved model keeps its place (task 0093)

Motion
- A model moved or turned by its top row (for example the second copy of the same STEP file, placed beside the
  first) now stays where you put it: through **Build animation**, poses, saved scenes, the start scene,
  **Everything back to CAD position** and model updates. Before, it jumped back at the next Build. A part moved by
  hand *inside* a model still goes back, as before.
- Many joints made at once (the demo project, model updates) take seconds instead of a minute: the demo's 415
  joints 67 s → 2 s on the 4-core test machine, the whole small demo 160 s → 90 s. A joint stacked on another one
  made in the same go now lands on its right axis.

## 0.2.69 – 12 Nov 2026 – demo: the quadrant system moves, Lebus drum close-up (task 0091)

Demo project (make it again: Help > Make demo project…)
- **The quadrant system moves all the way now**, and the animation shows it at the end: the roller cradles of the
  S-bends that stood in the D-quadrant's way **drop** out of it, the D travels aft on its rails onto the handler
  (× 60 time-lapse), the handler **tilts over the stern carrying it**, and the quadrant **tips**. The clash check
  finds nothing running into anything over this part.
- What was changed in the invented model for it: four cradles drop (one joint, the other three follow), the D's travel
  rides on the handler's tilt and its tip on the travel, the quadrant handling wire runs low under the D to a sheave on
  the handler's hinge and along the handler (that part tilts with it), the handler's top pulley sits lower (the D rolls
  over it), the handler's frame swings clear of its hinge brackets, the tilt cylinders sit nearer the hinge, the rail
  wheels' flanges run beside the rail head. 419 joints in all (311 on the vessel).
- The winch drum close-up shows a **Lebus drum** (35° crossovers, risers at the flanges) on the handling winches.
- The X-ray labels of the tensioner shot stay apart and inside the picture.
- The animation lasts about 78 s with title and end card.

## 0.2.68 – 12 Nov 2026 – demo project: an invented cable-lay vessel (task 0077)

Demo project
- **Help > Make demo project…** makes a ready project to show what the app can do on a big machine: an invented
  cable-lay vessel (about 120 m, 1,250 parts – not a real vessel or anyone's design: the app draws it itself). It is
  made in the background in a few minutes; the bottom line of the window shows how far, **Help > Cancel demo
  project** stops it and leaves nothing behind. Then **Help > Open demo project**. One per version, in
  Documents\Fresing Render\Demo.
- Set up the way you would, with the app's own buttons: paint (machinery blue, accents orange, structure yellow,
  rubber pads, a black cable), **415 joints** (every roller, sprocket and wheel the cable runs over follows one
  joint, **Cable travel**), the tensioners' top tracks lift and tilt, the quadrant handler's two cylinders, the open
  sea with **vessel motion**, saved cameras, a second scene **Loading at the quay** and a brand kit "Demo".
- The animation **What it can do today** (about 75 s with title and end card): a flight round the vessel riding the
  swell, the deck from above, the carousel and the arch (× 10), the rollers turning, a tensioner opening and
  squeezing, X-ray with labels, a winch drum close-up with a blurred background, the quadrant system. Later updates
  add the moving cable, the tracks, the spooling and the cable going into the sea to this same demo.
- New stop in the test tour and a new line in the PC check (Heavy): how long the demo takes to make on your PC, the
  time per frame of its animation and the memory it needs.

Clash check
- The clash check no longer runs out of memory on very big parts (a vessel's hull and deck): long thin faces are
  cut into a strip of short pieces instead of being halved again and again.

## 0.2.67 – 12 Nov 2026 – the face lights up for every click (task 0089)

Picking
- **Every click on the model now shows what it will hit before you click**, as the axis pickers already did: the
  face under the mouse turns magenta, a dot marks where the click lands and a short note says what it does. For the
  **sharp spot**, a **label's point** (add and move), a **trail point**, the **CNC work zero**, the **air** and
  **coolant nozzle**, **tool-changer pockets** and **Add decal** ("lies flat" or "wraps round"). A spot the click would
  refuse (the tool as a workpiece, the workpiece as a nozzle) turns red and says why. The clicks themselves do what
  they did. The preference is now called "Highlight what is under the mouse when picking" (your setting is kept).

## 0.2.66 – 12 Nov 2026 – way cover drawn at any axis position (task 0090)

Motion
- **Way covers: "Drawn at"** (4 Motion > Way covers > 3 Travel). A cover drawn in CAD with the machine at
  mid-travel now works: type the axis position it was drawn at, or press **Drawn at: read from the axis**. There every
  section stays on its CAD place and the sections share the movement from there. A line under it shows where the
  sections stand at 0 mm and warns when the value is outside the axis limits. Every cover has its own value; old
  projects keep 0 and move exactly as before.

## 0.2.65 – 12 Nov 2026 – vessel motion at sea (task 0085)

Scene & Render
- **Vessel motion** (new, 5 Scene & Render > Vessel motion, on the Open sea and the Vessel deck): tick **Move with
  the sea** and the machine, the deck and the props heave, pitch and roll gently with the waves, while the sea, the
  sky and the camera stay put. The vessel rises when a wave crest passes under it: it moves on the same waves the sea
  shows (with vessel motion on, the sea gets a long, low swell; off, the sea is exactly as before).
- **Calm** is a working day of a cable-lay vessel: roll about ±1–1.5° once in 10–12 s, pitch ±0.3–0.6° in 6–8 s,
  heave ±0.2–0.4 m in 7–9 s, mixed so it never repeats. **Rough** is about three times that.
- **Waves from**: head sea, bow quarter, beam sea (rolls the most), stern quarter, following sea. **Strength**
  0–200 %. The fold **Vessel**: length and beam (from the deck or the model, or typed in), roll period, the point it
  turns about (Auto or a clicked point).
- **Camera on board**: a **Ride along** camera step (6 Animation) on any part of the machine rolls with the vessel;
  with **Keep level** the horizon stays still.
- **Stays still**: pick a subassembly and it keeps its place in the world (**Still**: a motion-compensated gangway, a
  hook that holds its place) or stays level and only rises and falls (**Level**). Its joints still work.
- Joints, cylinders, mechanisms, labels, way covers, fades and trail lines keep working on the moving vessel. It
  plays with scripts off, in the render queue and at any frame rate, and stays through Save, a model update and saved
  scenes. It costs no render time; about 6 ms per frame of playback on a 3,000-part machine.

Test tour and PC check
- New tour stop **Vessel motion at sea** (the crane on the vessel deck in a calm beam sea), PC-check lines
  **Vessel motion at sea** (a picture and the measured roll, pitch and heave) and, in Heavy, **Big machine: vessel
  motion on the open sea** (time per frame with and without).

## 0.2.64 – 12 Nov 2026 – cutaway: see inside the machine (task 0086)

3 Looks
- **New: Cutaway.** Select a subassembly (or pick a group, or the whole model), choose **Plane** or **Box** and
  click **Add cut**: the side facing you is taken away and the cut faces show a strong red **cap colour** (your
  choice of colour, optional **hatch lines**). **Flip** takes away the other side; a box takes away a corner or a
  quarter. Move the cut's arrow in the view (**Select the arrow**, then G or R) or set its place by numbers.
  Several cuts per project, each on or off; parts that are not cut (gears inside a cut housing) stay whole.
- The parts themselves are not changed: switch a cut off and they are whole again. It shows in the rendered view,
  in pictures and videos (Cycles and EEVEE), in the render queue and with "Auto Run Python Scripts" off. Light falls
  in through the cut. A cut costs almost no render time (measured: 1.8 s a frame with and without on the test
  crane; 8.1–8.6 s vs 7.9–8.3 s on a 3,000-part test machine).
- **A cut that moves in a video:** each cut has a slide joint with its name (**Cut 1** …): a **Move joint** step in
  6 Animation slides it in – "the housing opens up". Poses and saved scenes keep it; a model update keeps the cuts.
- Adding the first cut sets 5 Scene & Render > **Floor gap** to 0.1 mm when it was 0 (else the floor would show
  through the cut face of a part standing on it).
- New stop in the test tour ("Cutaway: the pedestal opens up") and a new PC-check line (looks.cutaway).

## 0.2.63 – 11 Nov 2026 – the face lights up before you click an axis (task 0088)

- **Add joint, Set axis, a cylinder's pins, the double arm's hub and pot hinge:** while the app waits for your
  click, the face under the mouse lights up in magenta – the whole hole, shaft or flat face – with the axis it would
  give (a line through the centre of a hole or shaft, an arrow on a flat face) and a short text next to the mouse,
  e.g. "Hole Ø40.4 mm – axis through its centre". The floor and empty space say "Not a part"; a spot the click
  would refuse turns red with the reason. The click does exactly what it did before.
- Only drawn in the view: never in a render or the saved project; it goes with Esc, a right-click, the click, undo
  or opening another file. Quick on big models (about 2 ms per mouse move on the 3,000-part test machine).
- A click on a logo or sticker now counts as a click on the part under it (it said "missed" before).
- Switch: Edit > Preferences > Add-ons > Fresing Render > "Highlight the face under the mouse when picking an axis".
- PC check: new line "Hover highlight when picking an axis".
## 0.2.62 – 11 Nov 2026 – camera rides along, flies a path, watches a part (task 0087)

6 Animation
- **New camera steps** (Camera step, second row of buttons):
  - **Ride along:** the camera sits on a part and moves with it – on the carriage while it cuts, at the boom tip.
    **Keep level** keeps it upright when the part tilts. A saved camera as **Seat camera** sets where it sits.
  - **Fly a path:** a smooth flight through points at an even speed, with a gentle start and stop. **Make path from
    saved cameras** or **Add this view**; it looks ahead, at the model or at a part. The path shows as a thin line in
    the view, never in renders.
  - **Watch part:** the camera stays where it is and turns so a part stays in the middle of the picture (a hook, the
    tool). Ride along and Fly a path can watch a part too.
- **Blend in** glides the camera from where it was into the new step: no jump. With background blur on, the sharp
  spot follows the part the camera watches. Works in the render queue and with scripts off; camera steps of older
  projects give exactly the same video as before.
## 0.2.61 – 11 Nov 2026 – several way covers: one each side of the table, the carriage as last section (task 0035)

4 Motion > Way covers
- **Several covers per project:** a **Covers** list with **+** / **−**. A cover on each side of the table is two covers
  on the same axis (for example "X left" and "X right"); covers on other axes are more lines. Each has its own axis,
  sections and travel. Two covers on one axis no longer warn "goes beyond its own limits" at **Build**.
- **The plate bolted to the carriage** can be the last section: click its parts (they already move with the axis)
  and **Add section**. It counts as a section (five sections over 500 mm: the others slide 100, 200, 300, 400 mm) but
  gets no joint of its own; the list shows it with a pin and "carriage". It always stays the last section.
- Tested with 8 sections. **Remove this cover** (the **−** next to the Covers list) leaves the axis and the carriage
  alone.
- Projects saved with one way cover open with it as the first line of the list and move exactly as before.

## 0.2.60 – 11 Nov 2026 – smooth big round parts, light bolts; a video in every paint scheme (task 0074)

Import
- **Big round parts stay smooth:** carousels, drums and slewing rings get their facets in millimetres. The flat spots
  on a Ø10 m ring are now at most 0.5 mm deep at Normal (were 3.7 mm), 2 mm at Draft and 0.2 mm at Fine.
- **Bolts, nuts and washers are lighter:** standard parts the app recognises by name get about 20 segments round at
  Normal (were 42–47): you cannot see the difference in a render, but a model with many fasteners has far fewer
  triangles (an invented offshore test model: 536,000 → 241,000). Cutters, lamps and other small parts stay as
  detailed as before.
- A project imported earlier keeps its meshes. **Update to new revision…** brings the new facets; painted faces,
  joints and looks stay (a model update now recognises a part meshed with other settings as the same part).

Render queue
- **Every paint scheme** (7 Render queue): tick paint schemes, click **Animation** or **Current view**: one job per
  scheme, each file named after its scheme. The scheme is only set in the background render; your project keeps its
  colours. Works with **Start later** for an overnight run.

## 0.2.59 – 11 Nov 2026 – fade, X-ray and trail lines (task 0073)

6 Animation
- **New:** steps **Fade out** and **Fade in**: a subassembly (e.g. a housing) fades away over the step's duration
  and comes back later. **Stop at** keeps a faint ghost (e.g. 20 %); at 0 % the parts are hidden after the fade, so
  they cost no render time and cast no shadow. **Fade to X-ray** turns them see-through with glowing edges instead.
  Each part fades on its own (other parts with the same material stay), logos and stickers fade with their part.
  Works in Cycles and EEVEE, in the view (rendered), pictures, videos and the render queue.
- **New:** **Trail lines**: a line that draws the path of a point of a part – its origin, a clicked point or the
  tool tip – as the animation plays (or the whole path at once). Colour, thickness, in renders on/off; several
  per project. It is drawn again at every Build.

3 Looks
- **New:** **X-ray look**: give a subassembly, a part or a whole material group a see-through look with glowing
  edges (colour and strength to choose), for stills and videos.

Test tour and PC check
- A new tour stop "Fade, X-ray and trail" and a PC check line "Fade to X-ray and a trail line".

## 0.2.58 – 11 Nov 2026 – clash check and decal fixes (task 0072)

Clash check
- **Fixed:** building the animation again while the clash check runs no longer stores the old result as up to date:
  the result is dropped and the status bar says to check again.
- **Fixed:** scrubbing the time line while the clash check reads the animation: milling and coolant follow again.
- **Fixed:** a 45° face mill cutting the block no longer counts as a clash (it is wider at the top of its inserts
  than its diameter).
- **Faster** on milled programs: the app's own Normal toolpath on the test part (7,326 moves) is checked in about
  4 minutes instead of about 15.

Logos and stickers
- **Fixed:** the same STEP imported twice: a template's logo meant for the second machine lands on the second machine,
  and "every copy" logos on both machines reach both.

Test models
- The test crane's pedestal and the test luffer's post now hold their arm in a fork, and the luffer's brackets have a
  slot for each cylinder: no part starts inside another one.

## 0.2.57 – 11 Nov 2026 – machining fixes: two programs in one animation, coolant, rotary axes, smoother milling (task 0071)

CNC machine and tool changes
- **Fixed:** two "Run G-code program" steps in one animation: the tool left in the spindle by the first program no
  longer stays next to the second program's tool, no tool shows twice (spindle, pocket, magazine pot, double arm),
  and milling and chips cut with the tool that is really in the spindle. Each program starts with its start tool in
  the spindle and the others in their pockets, as the program expects.
- **Fixed:** the tool changer's own animation now plays in step with M6 when the program does not start where the
  animation starts (a joint step or another program before it); the step's length is worked out from there too.
- **Fixed:** automatic coolant hoses sat 80 mm too high after the first Build (the second Build and the queue's
  video were right); after a model update they hang on the new head and the wet sheen stays.
- **Fixed:** with the trunnion tipped 90° or more when you press Build, C turned the wrong way; rotary **Check** no
  longer leaves the machine in the pose of the frame shown, and its old result goes when you pick other axes or open
  another project.
- **Fixed:** a model update kept the double arm's joints but forgot they were the arm's; old projects with the same
  STEP twice keep the CNC machine on the copy it was set up on.
- **Fixed:** a wrong click on the pot's hinge no longer removes the magazine's pockets; the "Show air" cone sits on
  the tip of the tool in the spindle (also a longer one).

Speed
- Milling, chips and coolant play about twice as smoothly next to a big machine: measured on the web test machine
  (3,000-part machine + the 5-axis test model), 40 → about 20 ms a frame with milling, chips and coolant on (the
  cut is exactly the same).
- The drawn toolpath and the air cone glow without lighting the scene: renders with a long drawn toolpath are much
  quicker (study: 2.0–2.6 → 0.6 s a frame), and look the same.

## 0.2.56 – 11 Nov 2026 – render queue and update safety (task 0070)

7 Render queue – overnight renders you can trust
- **Start later survives saving:** saving the project (also the first Save, or Save As under a new name) no longer
  cancels a delayed start.
- **Render animation / Time test while a delayed start waits** render only that new job now; the waiting jobs still
  start at the set time. If a render is still going at that time, the delayed start begins as soon as it ends.
  **Start queue** while a delayed start waits starts everything now and says the wait is cancelled.
- **The PC does not go to sleep** while a delayed start waits (Windows), not only while the queue renders.
- **One queue per project:** start A's queue, open B and start B's, open A again: A shows its jobs running; Stop now in
  B stops only B. Starting a second queue while another still renders asks first (they share the graphics card). The
  same jobs are never rendered twice, also after the app was closed and started again.
- **Starting a queue no longer removes the project copy of another queue that is still running** (one that has just
  started, or one running on a colleague's PC from the same shared folder). Every queue gets its own folder.
- **Update now** refuses while a delayed start waits ("A delayed queue start is set for 22:00 …"), instead of dropping it.
- Small: the "in use by" lock file is written whole (a colleague never reads a half-written one); a finished job never
  shows "Failed" when the renderer's last status write was lost; the app's own process is never taken for a renderer.

## 0.2.55 – 11 Nov 2026 – the app makes the toolpath (task 0029)

4 Motion > Milling > Make a toolpath (new)
- **No CAM program needed:** pick the block (workpiece) and the CAD part it becomes (finished part), a roughing and a
  finishing tool from the tool list, press **Make toolpath**. The app writes a LinuxCNC program next to the project
  and adds it as a "Run G-code program" step (Fit into 30 s): Build animation and the block turns into the part –
  spindle, tool change, coolant, chips and the drawn toolpath as for any program.
- **Roughing** level by level (step-down, plus a level at every flat face of the part), zigzag lines, once round the
  walls, ramping into material (never straight down), lifting just over the material between areas; leaves the
  stock you set (0.3 mm). **Finishing** in lines across the part, set apart by the scallop height (0.01 mm) for a
  ball or bull-nose tool. Measured on the test model: at most 0.007 mm into the part (the limit is 0.01 mm).
- Flat, ball and bull-nose end mills and face mills (roughing). Speeds and feeds from the stock material (aluminium,
  steel, POM) and the tool, or typed in. Flood, mist or air. **Detail**: Draft, Normal, Fine.
- Holes through the part are left full; **undercuts** (faces looking down under an overhang) are left and reported.
- Making it again replaces its step's program, and asks first when you changed the file by hand.
- Test model (block with pocket, rounded boss, dome, overhanging cap, hole), PC check line, test tour stop, user
  guide section.

Milling and animations
- **Fixed:** a G-code program played fast (many moves within one hundredth of a frame) could lose a lift: the tool
  then cut straight across the part. Keys that close together are now all kept.
- Reading the milling path got much faster when the toolpath is drawn (a 7,000-move program: 67 s → 1.2 s).

## 0.2.54 – 11 Nov 2026 – clash check: only real clashes (task 0067)

6 Animation > Clash check
- **No false clashes beside sharp edges:** a part passing close beside a sharp outer edge (the cut end of a U-shaped
  gripper claw) could be listed as 15–60 mm inside it. Fixed: the double-arm tool changer's 27 rows were 18 of these.
- **Faster on a turning or milled workpiece:** the 4th-axis test program's check took 10 minutes, now about half a
  minute (measured on the 4-core test machine).

Test models and test tour
- Every animation of the test tour now gives **No clashes** (the clash model keeps its one 6.0 mm clash): the double
  arm's claws are real U claws clear of the spindle, its magazine disc clear of the tipping pots; the gantry's
  carriage is behind the spindle and its carousel clear of the gantry and the spindle; the slider-crank's bearing post
  stands behind the crank; the scissor lift's cylinder and the luffing arm's two other cylinders follow their arms;
  the test mill's finished-part shape and its second tool are hidden in the milling projects.
- An automatic test builds and checks every tour animation, so a new function's tour stop is checked too.

## 0.2.53 – 10 Nov 2026 – clash check (task 0065)

6 Animation > Clash check (new)
- **Check for clashes** after Build: a list of every two parts that run into each other in the animation – which
  two (their names as in the tree), from which frame to which, and how deep (deepest first). A marker on the time
  line shows where each clash starts. The panel's header says "3 clashes", "No clashes" or "Not checked since the
  last Build"; it shows how far the check is, and **Cancel** stops it.
- **Click a row:** the time line goes to the moment the two are deepest in each other, both are selected, drawn red
  in the view (their materials do not change, renders never show it) and the view zooms to them.
- **What counts:** an overlap deeper than the **Clash depth** (0.5 mm). Parts that move together are never compared;
  parts that already touch in the CAD model (a pin in its bore) only count when they go clearly deeper. The cutting
  part of a milling tool going through the workpiece is no clash; its holder and the spindle are. Hidden parts are
  left out while hidden. Fast moves (G-code rapids, a turning arm) are checked between frames too. **Warn about
  near misses** also lists parts that come closer than a distance you set.
- The result is kept with the project and cleared when the animation is built again with other steps. Adding an
  animation with clashes (or never checked) to the render queue gives a one-line note; it renders anyway.
- Measured on the 4-core test machine: the test crane 0.1–0.3 s, a scissor lift with a crank 15 s, a 2,983-frame
  G-code program with tool changes 7 s, the PC check's 3,000-part machine (10 s, its modules run through each other on
  purpose) 73 s.

Test tour and PC check
- New stop **Clash check: two arms meet** (a new generic test model: arm A comes down 6.0 mm into arm B), PC-check
  lines "Clash check" (Full) and "Big machine: clash check" (Heavy).
- The tour's **Boom up** now really turns the boom up (it went down through the base: the clash check found it).
## 0.2.52 – 10 Nov 2026 – 4th and 5th axis (task 0066)

CNC machine > Rotary axes (new)
- **A rotary table or a trunnion turns the part under the tool.** Pick a rotate joint for **A** (turns about X),
  **B** (about Y) and/or **C** (about Z); each with **Reverse**, **Wrapped** (0 … 360°, LinuxCNC `WRAPPED_ROTARY`)
  and its rapid speed in degrees per minute. **Machine zero** keeps A0 B0 C0 too.
- **Kinematics: Plain** (the default; your CAM post already worked out X, Y, Z for the turned part, LinuxCNC
  `trivkins`) or **Follows part (TCP)**: the program is for the part as it lies at A0 B0 C0, and X, Y and Z follow
  so the tool tip stays on its point while the table or trunnion turns (within 0.01 mm; measured 0.0013 mm on the
  test trunnion). TCP is for axes that turn the part; a turning head stays Plain.
- **Check** turns each axis through its range in the view and says which way it turns, where its centre is from the
  work zero (the number your post needs), and with TCP how far the tool tip strays: a wrong joint shows at once.

G-code
- A, B, C on G0, G1, G2, G3 (on an arc the axis turns evenly along it), G28 / G30, G53, G92, G10 L2 / L20; G93
  inverse-time feed and back with G94; LinuxCNC's feed rule (F along X/Y/Z when they move, degrees per minute for a
  line that only turns). U, V, W are still reported as not supported.

Milling, toolpath, chips
- The material comes off in the right places on the turning part (a slot wrapped round a bar, flats, pockets on a
  tilted face). While an axis turns the app reads the tool more often, so the cut stays smooth (the tip within the
  detail level's tolerance, at most 0.5° of turn per piece). Three-axis programs cut exactly as before.
- The toolpath is drawn on the part and turns with it. Chips that landed on the part turn with it; chips on the
  bed stay. Tool changes keep the rotary axes where they are.

Test models and checks
- Two generic test machines ship with the app: a 4th-axis table with tailstock holding a round bar, and an A/C
  trunnion holding a block. PC check line "4th and 5th axis: rotary table and trunnion", test tour stops 20 and 21
  (the stops after them move up by two).

## 0.2.51 – 10 Nov 2026 – double-arm tool changer (task 0064)

CNC machine > Tool changes
- **Double-arm tool changer.** A third kind next to Manual and **Carousel / umbrella** (the old "Tool changer
  (ATC)", unchanged). At the **Tn** before an M6 the magazine turns the next tool's pot to the arm and tips it down
  while the machine still cuts; at the M6 the head goes up, the spindle stops at its orient angle, the arm turns onto
  both tools, pulls them out, turns half round, pushes them in and turns back. About 1.6 s per change at ATC speed 1;
  "Fit into" and ATC speed work as before.
- **Random pockets:** the old tool goes into the pot the new one came from, as on the machine. Every tool is held
  by the spindle, the arm or a pot at every frame; at each hand-over they meet within 0.01 mm, so nothing jumps.
- **Set-up in a few clicks, no joints to make by hand:** click the arm's hub (the app makes its turn and stroke and
  reads the grip angle from the claws), click the hinge of the pot at the change station (the app finds every pot
  and makes their tip joints). **Check** plays one change in the view and says what does not fit.
- The kind of changer is now picked from a drop-down (the three names did not fit as buttons).
- A new generic test model with an arm and a 12-pot magazine, a PC check line and a test tour stop.

## 0.2.50 – 10 Nov 2026 – small fixes (task 0060)

Pictures
- **A still with a logo or watermark is no longer black** when the timeline stands anywhere but frame 1 (the test
  tour found it). The still logo is now switched on in the test tour's "Still picture" stop.
- **A queued picture of a frame of a built animation has the video's floor.** A part that swings below the floor
  was cut by it in the video but not in the picture; now they match. The guide says how the floor is placed.

Updates and tests
- **Another Blender is found under any spelling of its folder** (8.3 short names, a `subst` drive, a link), so the
  update waits for it too.
- **The automatic test run is faster again:** the test tour has its own group.
- `ci_status.py --wait` no longer says "no test run" for a merge commit.

## 0.2.49 – 10 Nov 2026 – render queue starts by itself later (task 0050)

Render queue
- **Start later.** In 7 Render queue, under the list: choose **In …** (0–12 hours and minutes) or **At …** (a clock
  time, today or tomorrow) and click **Start later**. The panel counts down ("Starts in 2 h 14 min – at 18:30") with
  **Start now** and **Cancel**. At the time the queue starts exactly as with Start queue. The app must stay open: a
  delayed start is not kept when you close the project or the app, and the panel says so.
- The test tour has a new stop for it.

## 0.2.48 – 9 Nov 2026 – coolant: flood and mist while milling (task 0042)

Milling
- **Coolant.** 4 Motion > CNC machine > **Coolant**: tick it, and a milling video looks like the real machine. When the
  program says **M8**, milky coolant squirts from the nozzles onto the tool, splashes where the tool cuts (more while
  it cuts than while it moves through the air), the block, the table and the vise get a wet sheen (darker, glossier,
  drops on the sides) and the chips come out wet – darker, shinier, and they stay closer to the cut. **M9** stops it
  and the parts dry in a few seconds (**Dries in**, 4 s). **M7** gives mist: a fine cone of tiny drops.
- **Nozzles:** **Automatic** adds 1 to 4 flexible hoses (the blue Loc-Line look) on a ring round the spindle, aimed at
  the tool; after a tool change they bend to the new tool's length. Or use your model's own nozzle parts (**Use
  clicked part** / **Click point**, **Aim at the tool**).
- **Liquid:** emulsion (milky) or clear cutting oil; **Flow** from a thin stream to full flood; **Draft** for a quick
  view without splash and drops.
- **Per G-code step** (6 Animation): coolant **From the program** (M8 / M7 / M9), **Flood** or **Mist while cutting**
  (programs without coolant codes), or **Off**. The step says what it found ("Coolant: flood 1 time, 4.7 s").
- **M7 and the air blast:** with coolant on, M7 switches on mist and the air (mist is air with drops) when the air
  code is M7 too; M9 stops both. Give the air another code, or set Mist code to 0, to keep them apart.
- Every frame of the coolant comes from the frame number alone: the render queue can render frames in any order.
- Old projects are unchanged: no coolant until you tick it.

Test tour
- New stop **Coolant (flood)** in the Machining group.

PC check
- New line **Milling: coolant floods the tool** (jets, splash, wet and drying, the same frame every time, the time per
  frame and a Cycles picture of the flood).

## 0.2.47 – 9 Nov 2026 – test tour (task 0059)

Test tour
- **Help > Make test tour project…** makes a set of small projects from the app's own test models (crane, mill,
  gantry, cylinder, scissor lift, way cover…) with every function already set up, in about 2 minutes in the
  background: Documents\Fresing Render\Test tour. Then **Help > Open test tour project**.
- **The Test tour panel** (on top of the Fresing tab, only in a tour project): 27 numbered stops in four groups –
  Look, Motion, Machining, Pictures and videos. Each stop says what you should see and where the function is. **Go**
  opens the right project, its saved scene and camera, builds and plays its animation and selects the part. Mark it
  **OK** or **Problem** and add a **Note…**; **Next** goes on.
- **Copy results** puts the version, your PC and every stop with OK / PROBLEM and your note on the clipboard (and in a
  text file next to the tour): paste it into the lead chat.
- **Let it run by itself:** **More > Run the whole tour by itself** (or Help > Fresing Render PC check… > **Test
  tour**) goes through every stop in the background, checks what can be checked with numbers and renders a small
  picture or three frames of each stop. "Fresing Render test tour.html" opens at the end with a card per stop. Your
  own OK / Problem marks are not touched.
- The PC check (Full) has a new line: the test tour is made and every stop's Go works.

## 0.2.46 – 9 Nov 2026 – render queue fixes (task 0054)

Render queue
- **Current view in a built animation queues the frame you see.** Stopped at a frame of a built animation, **Current
  view** used to queue the model as it was before the animation, from the start camera. Now it takes that frame: the
  pose, the parts hidden at that moment and the camera where the animation has it.
- **A video started again never mixes old frames in.** Stop a video, change the animation (or shorten it), start the
  queue again: the job used to keep frames from before, even past the new end. Now it keeps them only when nothing
  changed (it says so when it renders all frames again), and the video takes exactly its own frames.
- **The queue stays in its own project.** Opening another project while a queue renders used to show that queue's jobs
  in the other project and block its own Start queue. Each project now keeps its own list.
- **Small queue faults fixed:** a waiting job removed while the queue runs is left out (it used to render and come
  back); **All scenes** no longer adds the hidden scenes of earlier **Current view** clicks; renaming an animation keeps
  "Time test" and "(with watermark)" in the job's name; a picture whose saved scene was deleted fails with that
  reason instead of rendering something else; a renderer that could not start marks its jobs **Failed** instead of
  leaving them waiting.
- **Files typed as `//…`** (next to the project: 360° photo, logo, font, music, pictures) are found by the queue too.

Videos
- **The sharp spot stays sharp in videos.** When the sharp-spot part had moved (a joint, a pose, the start scene), the
  video was sharp where the part used to be. Now it is worked out again when the animation is built, and a moving
  camera keeps the spot sharp on every frame, also while its part moves.
- **Videos with labels are made faster:** working out where the labels go took about 75 ms per frame on a machine of
  3,000 parts, now about 9 ms (about 35 s less for a 500-frame video).

PC check
- New line **Queued picture of an animation frame = the view**.

## 0.2.45 – 9 Nov 2026 – tool changes: by hand and with a tool changer (task 0041)

CNC machine
- **Every tool change (M6) now plays by itself.** New panel 4 Motion > CNC machine > **Tool changes**: **Manual** or
  **Tool changer (ATC)**.
- **Manual**: the head goes to the change position (**Where it is**, **Z up only**, or a **Change position** in machine
  coordinates; **Use the axes now** takes where the axes are), pauses and goes back. **Pause at M6** in the program step:
  **1 second by default**, a slider from 0 to 5 s (it was 2 s).
- **Show hand** (in the program step, off by default): a gloved hand reaches in, takes the old tool out of the spindle,
  puts the new one in and leaves. It needs 2.8 s; a shorter pause grows to that and the step says so.
- **Caption** (in the program step): "Tool change: T3 Ø50 face mill" in videos at every change, in the brand kit's
  caption look.
- **Tool changer (ATC)**: click the pockets on the changer (a carousel: pocket 1, then **Fill the carousel** with the
  number of pockets). The tools stand in their pockets from the first frame; at each M6 the carousel turns the
  shortest way, the spindle leaves the old tool in its own pocket and takes the new one, then goes back to the program.
  Without a carousel joint the pockets are a rack and the head goes to each one. Which tool stands where: the tool's
  **Pocket** in Tools, else the pocket it stands in in your model, else the pocket with its T number.
- The changer's own animation (arm, cover) plays at every change, split at **Swap at**; **ATC speed** makes the changer
  faster or slower in the video. **Fit into** still gives exactly its seconds: changes take at most half of them.
- `T1 M6` while T1 is already in the spindle does nothing, as on the machine.
- **Projects from before**: a step with a tool-changer animation makes the machine an ATC when the project is opened, and
  it plays as before. Tip: **Tool lengths move the spindle** (Tools) is on since 0.2.36; untick it for the old look.

PC check
- New line "Tool changes: by hand, and a tool changer with 8 pockets" (with a picture of the hand).

## 0.2.44 – 9 Nov 2026 – the same STEP twice: two separate machines (task 0056)

Import
- **The same file imported twice** (two cranes on one quay) now gives two separate machines. Before, both copies
  shared their part IDs: hiding a part of the second crane in a visibility set, a pose or a Show/Hide step acted on the
  first crane, and updating one copy to a new revision could change what was saved for the other. Now each copy keeps
  to itself, also through model updates. Sorting rules and materials still treat both copies alike.
- Projects made before with a file imported twice are sorted out when they are opened: the first copy keeps
  everything that was saved for it (that is what those settings acted on so far). Projects with one copy of each
  model are not changed.
- Logos and stickers saved in a template for one copy of a part find that copy again in another project.

PC check
- New line **The same STEP twice: two separate cranes**.

## 0.2.43 – 9 Nov 2026 – milled faces look freshly cut; milling fixes (task 0051)

Milling
- **Cut faces get their own look**: the block keeps its raw look outside, and everything the bit cuts shows as fresh,
  bright metal or fresh plastic. New setting **Cut faces** in 4 Motion > Milling: **Automatic (fresh cut)** (the
  default; also for old projects), **Same as the block**, or **Pick a material…**. Automatic: any aluminium cuts to
  machined aluminium, raw/ground/plated steel to machined steel, stainless to machined stainless, cast iron to bare
  grey iron, brass/bronze/copper brighter, plastics a little more matte; paint stays as the block. The render queue,
  stills and videos show the same as the view.
- **New raw stock looks** (3 Looks): **Aluminium, sawn plate** (rolled plate, a little dull, faint rolling lines) and
  **POM, black**. Steel, raw / mill scale, Cast iron and POM / PE, white were already there.
- Faces of the block that the bit did not touch now always keep their own look (also faces painted in CAD).
- A **logo or text on the block** is no longer emptied when you change it while milling (or after Stop milling).
- **Chips** of the newer materials: ground and turned steel, chrome rod, painted cast iron, sawn aluminium, black POM.
- Faster with chips: a frame change no longer rebuilds the whole scene (test mill + 3,000 parts: 89 → 23 ms a frame);
  the milling frame code itself is about twice as quick.
- Rendering in the window (F12) while milling is on locks the window during the render, so the cut can safely follow
  the frame.

CNC machine (G-code)
- Picking the **spindle** joint ticks **Motor** on it by itself (no warning after Build any more).
- A program or tool table **next to the saved project** (or in a folder below it) is stored relative to the project,
  so the project and its files can move to another PC together; the render queue still finds them.
- The line under a Run G-code program step always shows its own program, also after removing or moving a step.

PC check: new line **Milling: cut faces look freshly cut**.

## 0.2.42 – 9 Nov 2026 – safe updates and the project lock (task 0053)

Updates
- **Update now never saves over a colleague's work**: when someone else has the project open ("In use by …"),
  Update now says so and does nothing. Save As (a new name) or open another project first. The update notice shows
  the same red line.
- **Update now waits for every Fresing Render**: a second window, a queued render or the PC check of the same
  installation must be closed first (the app says so). Before, the installer could swap files they still used.
- **A failed update never leaves plain Blender**: the old version is copied aside first and put back when Windows
  stopped the new one from being put in place. The app opens with the old version and says what happened.
- **An update that was cut off** (PC switched off, logged off) no longer blocks Update now: the next start sees the
  old "being installed" note is stale and offers Update now again.

Shared projects
- **The same project in two windows on your PC** now shows "In use by you, in another Fresing Render window on this
  PC" in the second window, as for a colleague. When the first window closes or crashed, the second takes over.

PC check
- New line **Safe updates (other windows, backup, old notes)**: tests on your PC that the app can see other Fresing
  Render windows, put an old version back and ignore a stale update note (nothing is installed).
- The PC-check shortcuts are made again after an update even when Windows answers with accented characters.
## 0.2.41 – 9 Nov 2026 – Model update keeps everything (task 0052)

- **Two models linked together** (a crane on a ship's deck, a lamp on a lift's platform): joints, cylinders,
  mechanisms and way covers that use parts of both models now stay when you update either of the two. Before, an
  update could delete the joint or put it back on the wrong part.
- **Labels and the camera's sharp spot** stay on their parts after a model update. If a label's part is no longer in
  the new model, the update report says so (pick its point again).
- **All or nothing**: if a model update cannot finish (a damaged file, the PC runs out of memory), the status line
  says "Model update failed" and why, and the project stays exactly as it was. Before, joints could be lost and the
  new model left half-built.
- Updating a big model with joints is a bit faster (about 12 % on a 3,000-part test machine).

## 0.2.40 – 9 Nov 2026 – Looks fixes (task 0055)

- **Renaming a group** now also renames it in your paint schemes and in the saved scenes' own looks, so applying a
  scheme no longer skips it.
- **Two groups can't have the same name any more**: renaming to a name that is taken is refused with a short message.
- **Opening a project**: if one upgrade step fails, the others still run (the reason is printed in the console).
- **Old stored imports** of an older app version are deleted when you import, so they no longer fill the disk.
- **Chrome rods** now get the *Hydraulic chrome rod* look and **shafts and linear guides** get *Steel, ground* in new
  imports and new rule sets. Existing projects keep their looks.

## 0.2.39 – 9 Nov 2026 – better materials: real metals, paint, wear (task 0046)

Looks
- **Real metals**: new **Steel, ground** (fine straight grinding lines along the part, for ways and shafts),
  **Steel, turned** (fine rings round the part's axis) and **Hydraulic chrome rod**. **Aluminium, machined** has faint
  face-milling arcs, **Stainless, brushed** now really looks brushed (along the part's longest side). The marks come
  from each part's own shape, so every copy looks the same; they are finer than a millimetre and only show close up.
- **Anodised aluminium** (natural, black, colour) has the soft satin sheen of real anodising.
- **Cast iron** looks cast (rough, slightly mottled); new **Cast iron, painted** (any RAL colour over the casting).
- **Paint**: gloss, satin and marine paint have a little orange peel, powder coat a finer structure.
- **Rubber** is no longer pure black (soft sheen, a little dust); matte plastic has a fine moulded grain; **glass and
  polycarbonate** now look like glass in Fast preview (EEVEE) too.
- **Wear** slider per material group (3 Looks, under the material; 0 = new, the default): sharp edges turn lighter or
  bare metal in places and corners get a little dirt. Edges in Cycles; Fast preview shows only the dirt.
- **CAD names**: "Steel - Polished", "Steel, ground", "turned", "Hard chrome", "Piston rod", "Gray Iron" and their
  Dutch and German words pick the new materials.
- **Old projects** get the new looks when you open them; every group keeps its material and colour.
- Renders are not noticeably slower without wear (test crane, Cycles HD: +0.6 %); wear costs extra render time.
- PC check: new line **Materials: the material sheet** – every material in one picture, to judge on your PC.

## 0.2.38 – 9 Nov 2026 – tool library fixes: BT30, tool lengths, tip and corners (task 0049)

- Tools: **BT30** is a holder choice (flange Ø46, 7:24 taper, pull stud).
- Tool lengths (G43) are now measured from the tip to the holder's gauge line: stick-out + holder length, or the
  new **Gauge length** you type in for a tool whose part or STEP model has its holder inside. Tools in different
  holders (a face-mill arbor and an end-mill chuck) now move the spindle by the right amount. Projects whose
  tools all sit in one kind of holder move as before.
- The tool tip stays on the program while the spindle turns: before, a tip read a few hundredths of a mm beside
  the spindle's axis went round with it (up to about 0.07 mm off, sometimes sideways on a straight move).
- Milling cuts sharp corners right into the corner, also at high feeds (before: up to 0.2–0.3 mm short).
- Manufacturer STEP files that lie along X with the gauge line at the origin (ToolsUnited, Hoffmann) are read the
  right way round: a tool alone and a holder alone.

## 0.2.37 – 8 Nov 2026 – user guide: new pictures (task 0044)

- User guide: pictures for Way covers, Air blast, Labels, Pictures and Music.

## 0.2.36 – 8 Nov 2026 – tool library: every tool cuts with its own shape (task 0040)

CNC machine and milling
- **One tool list per project** (4 Motion > CNC machine > **Tools**): T number, name, type and sizes, stick-out,
  holder, place. Add (pick the type), copy, remove, sort by T. Saved with the project.
- **Eight types**, each with sizes that work at once: flat end mill, ball end mill, bull-nose end mill, spot drill /
  chamfer mill, drill, face mill (inserts, lead angle), thread mill (pitch), slot / T-slot cutter (width, neck).
- **Every tool cuts with its own shape, also after a tool change (M6)**: while T3 is in the spindle the block is
  cut with T3's sizes. Before, only the tool in the spindle at the start cut. Chips follow each tool's type (a face
  mill throws flat commas, a drill makes spirals).
- **What a tool looks like**: drawn from its sizes (flutes along a helix, inserts on a face mill, teeth on a thread
  mill and a slot cutter) with an optional **ER collet, SK40, BT40 or HSK63 holder**; or a manufacturer's **STEP
  model** of the tool (or tool + holder) – its axis and tip are found from its shape and its sizes read into the
  row; or a part of the model, as before.
- **Read tool files**: a Fusion tool library (`.json`, `.tools`, vendor libraries too) or a LinuxCNC tool table
  (`tool.tbl`); Tools from the program reads Fusion's tool comments as before. Unknown types are read as the nearest
  type with a note.
- **Tool lengths move the spindle** (on by default, like G43): a longer tool lifts the spindle by the difference, so
  every tool's tip is where the program says.
- A T number the program uses but the list does not have: the step says "T7 (line 42) is not in the tool list",
  with **Add T7 as …**. Sizes that look wrong give a warning.
- **Fixed**: a fluted end mill read from its shape could come out too small (the owner's Ø12 read as Ø10.4); the
  outline is now read from the whole surface, so it gives the outer diameter over the flutes (test end mill:
  Ø11.4 before, Ø12.00 now).
- Measured (test gantry, 4 cores): a program with a face mill, an end mill, a drill and a chamfer mill cuts every
  depth and width within 0.05 mm. The PC check has a new line, "Milling: each tool of the tool list cuts with its own
  shape". Projects made before open and cut as before.
## 0.2.35 – 8 Nov 2026 – surroundings stay put on a second import, lighter 4K videos (task 0043)

- **A second import no longer moves the hall** (or deck, quay, sea …). Adding a vise, a tool or a workpiece
  leaves the surroundings exactly where they are. If the new model sticks out of the floor area, the
  Background panel shows a note and a button **Fit surroundings to the model** (the old "Put on the floor
  again", renamed). A model update (new revision) fits them as before.
- **Making a 4K MP4 needs far less memory**: the video encoder no longer keeps every 4K frame in memory
  (250 frames of 4K: peak 5.7 GB → 1.7 GB on the test machine, same speed, same file).

## 0.2.34 – 7 Nov 2026 – air blast blows the chips away (task 0039)

Milling with chips
- **Air blast**: air blows the chips off the part while the program has air on, so the finished part stays visible.
  Set it up in 4 Motion > CNC machine > **Air blast**: the codes that switch it (M7 and M9 by default, or your own
  M100–M199), or **always on while the spindle turns** for programs without a code.
- The air comes **through the spindle** (out of the tool's tip, moving with it) or from an **external nozzle**: click
  the nozzle part (its tip is read from its shape) or click the spot where the air comes out; it moves with the head
  or stands with the frame. **Strength**, **Cone angle**, **Reach**, and **Show air** (a faint cone while it blows).
- Chips in the air are pushed away, chips lying in the jet are picked up and land further away – on the table, the
  bed, in the corners. The same frame gives the same chips every time, also in the render queue.
- **Blow the part clean at the end** (in the Run G-code program step, with **Time at end**, 2 s by default): the
  step gets longer, the tool goes up, the air blows the chips off and the last frames show the clean part.
- The step says when air is on ("Air: on 1 time, 3.1 s in all"), Details too. A user code chosen for air is no
  longer listed as "not shown".
- On the test mill (pocket 60 × 40 mm, chips Realistic): 1,560 chips on the block at the end without air, 0 with
  air through the spindle and 0 after blowing the part clean. The PC check has a new line, "Milling: air blast
  blows the chips away". Projects made before have air off and stay as they were.

## 0.2.33 – 7 Nov 2026 – milling no longer crashes (task 0038)

- Fixed a crash with milling: after a new Build, after a change in the animation, and at the start of every queued
  render, the app reads the bits' path again. When that path had another length than before, Blender's memory was
  damaged and it crashed a little later – while cutting, or at the end of a long queued video while making the MP4.
  The path is now stored in a way that cannot do this. Projects saved with an older version open and work as before.

## 0.2.32 – 7 Nov 2026 – PC check Heavy, round 2 (task 0033)

PC check
- Heavy has three more steps: the big machine in the **CNC hall** and on the **open sea** (Detailed, HD, Cycles on
  the graphics card), a **long milling cut** (more than 100 frames, chips Realistic: time to work out, ms per
  frame with and without chips, faces left in the block), and **playback under load** (a 10 s animation of the
  3,000-part machine with joints and a coupling: ms per frame, flagged when it jumps).
- With your own STEP file Heavy also renders it at **4K** on the graphics card and as a **3 second EEVEE
  video** through the queue (numbers only in the text block).
- The video in Heavy now moves a lot more (a module turns 90°, another slides 4 m), so a still frame is easy
  to spot in the contact sheet.
- Your first Heavy run (RTX 3090, 24 cores): all 7 steps in 12 minutes (Cycles 4K Final 57 s, EEVEE 0.93 s per
  frame over 251 frames, import of 3,000 parts 9 s, peak memory 4 GB), so the sizes stay as they are.

## 0.2.31 – 6 Nov 2026 – faster automatic tests (task 0036)

Nothing changes in the app itself. Behind the scenes:
- GitHub's automatic tests now run side by side on about a dozen machines instead of one after the other: about 13
  minutes per run instead of 35 to 50. Every test that ran before still runs.
- A quick first check (about a minute) catches a clashing version number before the long tests start.
- When a finished task is put on `main` exactly as it was tested, GitHub no longer repeats the tests: it
  publishes the update within minutes. Changes to texts and the guide only take a few minutes too.

## 0.2.30 – 6 Nov 2026 – G-code: CNC programs drive the machine (task 0026)

4 Motion > CNC machine (new)
- Tell the app which joints are the machine's **X**, **Y** and **Z** (**Find the axes** picks them) and the
  **Spindle**, click the **Tool** in the spindle and the **Workpiece**, and pick the **Work zero** as in your CAM
  set-up: top centre, a top corner, bottom centre, or a clicked point (it snaps onto a corner). Arrows show the
  work zero on the block. A table that moves the workpiece is fine: the program's +X is always the tool's way
  relative to the workpiece; **Reverse** turns an axis round.
- Fold **Machine**: rapid speed per axis (mm/min), a shift of the work zero, and the machine zero (G53 / G28).
- Fold **Tools for tool changes**: **Tools from the program** reads Fusion's tool comments (or LinuxCNC's
  tool table); a tool can be a part of the model (for example in the carousel) or a simple shape from its sizes.

6 Animation: new step **Run G-code program**
- Pick the program your CAM writes for the machine (LinuxCNC, `.ngc`): the machine moves exactly as the program
  says – straight moves, arcs in all three planes (also helical), drilling cycles, work offsets, inch or mm,
  subroutines, loops and parameters. The step's length follows from the program: **Real time**, **Faster** or
  **Fit into** a number of seconds; **Rapids faster** for the moves through the air.
- The spindle turns with S / M3 / M4 / M5 (slowed down so it looks right in a video, or at real speed).
- Tool changes (M6): the new tool shows in the spindle and leaves the carousel; an animation of the tool changer
  can play at every tool change while the program waits.
- **Show toolpath**: the path on the block, orange to cut, green once cut, rapids dashed blue; also in renders
  if you like.
- **Details** lists everything in the program the app does not show, with line numbers (cutter compensation
  G41/G42, rotary axes, threading …). A copy of the program is kept in the project, so the render queue and
  other PCs have it.
- Measured: a 30-minute program (20,000 lines, 45,349 frames) builds in 2–3 s on the 4-core test machine.
- PC check: new line "G-code program drives X, Y, Z and the tool change".

Fixes
- A joint within 0.1 mm (or 0.006°) of its CAD position jumped to it: Blender drops very small driver results.
  Every joint now works around that (projects made before are updated when they open).
## 0.2.29 – 6 Nov 2026 – PC check: Heavy mode (task 0033, round 1)

PC check
- New **Fresing Render - PC check (heavy)** (Start menu and Desktop; in the app Help > Fresing Render PC
  check… > Heavy). It loads the PC like real work: an invented machine of about 3,000 parts is made, imported
  on all cores and worked with (structure list, search, Show only, explode, save and open), Cycles pictures
  at HD and 4K (Preview and Final), EEVEE per frame at HD and 4K, a real 10 second EEVEE animation (250
  frames, 1920 × 1080) and a 3 second Cycles clip through the render queue. Takes 10 to 20 minutes (the sizes
  are tuned after the first run on your PC).
- The report shows which step is running and for how long, big pictures with their settings, a contact sheet
  and the last frame of each video, the peak memory, and under every step what it shows and what it does not.
- **Cancel:** Help > Cancel Fresing Render PC check (or Ctrl+C in the black window) stops the check; the steps
  done so far stay in the report.
- GitHub runs Heavy in a scaled-down form (a few hundred parts, 5 frames) on Linux and Windows.

## 0.2.28 – 6 Nov 2026 – way covers follow the machine axis (task 0034)

4 Motion > Way covers (new)
- Telescopic way covers move with a machine axis, set up in one go. Pick the slide joint (or make one from
  the selection), click the parts of each cover section – a section may be made of several parts – and press
  **Add section**, from the fixed end to the moving end. **Make it** does the rest.
- The travel is shared out: the axis moving 500 mm with 5 sections moves them 100, 200, 300, 400 and 500 mm
  (3 sections: 167, 333, 500 mm). **Read from the axis** takes the total from its limits, **Flip direction**
  opens the covers the other way, and **Housing counts** is for covers drawn with the fixed housing as the
  first section (500 mm over 5 sections: 0, 125, 250, 375, 500 mm).
- Changing the number or order of sections, the travel or the direction re-shares at once. A part in two
  sections, or in a section that already moves by itself, is refused with the reason.
- Works in poses, Move joint and Run motor steps, built animations and the render queue, also with scripts
  off; kept through model updates and in saved projects. **Remove way cover** takes away only what it made.
- PC check line "Way covers follow a machine axis"; two new test models (a generic one and the owner's
  5-section way cover, 166.5 to 586.5 mm).

## 0.2.27 – 6 Nov 2026 – labels, picture cards and music in videos (task 0025)

5 Scene & Render > Labels (new)
- **Add a label**: click a spot on a part, type the words. The label gets a box beside the machine (never
  on top of another label, outside the machine where there is room) and a thin line to the spot, in the
  brand kit's colours and font. Stills and MP4 videos.
- The spot stays on its part: when the part moves in an animation the line follows it in every frame
  (checked to within 2 pixels). A label of a hidden part is hidden too.
- **Only during** a step: the label fades in and out with that animation step. **Text size** Small / Medium /
  Large; **Draw labels in renders** switches all off.

6 Animation > Pictures and Music (new)
- **Pictures**: a photo or diagram over the video for a few seconds, full screen or in a corner, with a
  fade and an optional caption.
- **Music**: your own music file under the whole MP4 video: starts at, volume, fade in, fade out, cut to
  the video's length. The MP4 gets a normal AAC sound track.
- PC check: new line "Labels with lines on a picture and an MP4 with music".

## 0.2.26 – 6 Nov 2026 – mechanisms: scissor lifts, four-bar arms, slider-cranks (task 0014)

4 Motion > Mechanisms (new)
- Pick the **Type** (Scissor lift, Four-bar or parallel arm, Slider-crank, Other linkage), pick the **Base**,
  select the moving links and press **Add mechanism**. The pins are found by themselves: where two links
  have a hole or shaft on the same line. A scissor's rollers run on the base and under the platform; a
  slider slides along its piston or guide.
- Drive one link and everything follows, exactly: **Height** of a scissor lift's platform (with Lowest / CAD
  / Highest), or the **Drive angle** – a normal joint in the joint list, so poses, saved scenes, Move joint,
  Run motor and couplings move the mechanism too. A cylinder pinned to the arms drives it with its stroke
  (Drives the arm).
- The links never flip over to the other way they could be put together (also a parallelogram arm passing
  through the line of its four pins). A position it cannot reach stops at the last one it can, with the
  reason in red. The drive joint's limits are set to how far it can go (a scissor stops before its arms
  lie flat).
- 6 Animation: new step **Lift height** (platform from → to). Built animations keep every link's place on
  every frame: videos, the render queue and PCs without scripts in project files need nothing else.
- Kept in saved projects and through a model update (the pins are found again on the new revision).
- PC check: new line "Mechanisms: scissor lift height, slider-crank".

Fixes
- A joint could be put on a subassembly that carries its own base, or on the whole model: the check for
  that was skipped since 0.2.25. It is back.

## 0.2.25 – 6 Nov 2026 – hydraulic and electric cylinders (task 0013)

4 Motion > Cylinders (new)
- Pick the cylinder's **Barrel** and **Rod** (select, press the button), press **Add cylinder** and click the
  barrel's pin, then the rod's pin. From then on the cylinder moves with the arm by itself: the barrel
  turns about its pin, the rod slides in or out, both eyes stay on their pins (checked to 0.01 mm at every
  arm angle). Two cylinders side by side on one arm, a whole machine that slews, stacked and coupled
  joints: all fine.
- **Drives the arm**: set the **Stroke** (how far the rod is out, 0 = fully in) and the arm's joint turns to
  match – worked out exactly from the triangle pivot, barrel pin, rod pin (law of cosines); a cylinder
  pushing a carriage on a slide works too. **Fully in / CAD / Fully out**. The arm's limits become the
  cylinder's.
- **Closed length** and **Full stroke** are read from the parts (how far the piston can go back to the end
  cap and out to the gland), or typed in from the data sheet.
- Telescopic cylinders: **Stages** – each section slides out the same share of the travel.
- 6 Animation: new step **Move cylinder** (stroke from → to); the rod moves at the step's own pace
  (Constant speed = an even rod speed, as a real cylinder), the arm follows.
- Works in the render queue and with scripts switched off (Blender's own constraints); kept in saved
  projects and through a model update.
- PC check: new line "Cylinder: follows the arm, the stroke drives it".

Fixes
- **Show joint arrows in the view** (4 Motion) no longer gives an error; it also shows/hides the cylinders'
  pin markers.
- Messages say "1 subassembly added" and "1 piece … moved apart" (not "1 subassemblies", "1 pieces").
## 0.2.24 – 6 Nov 2026 – PC check: one click tests every function on your PC (task 0032)

After an update, one click tests the new version on your own PC and shows the result in your web browser.
- Start menu > Fresing Render > **Fresing Render - PC check (quick)** (about 3 minutes) or **(full)** (about
  15 minutes: every function), **Fresing Render - PC check** on the Desktop, or **Help > Fresing Render PC check…** in the app. It runs in the background
  with small test models that come with the app; you can keep working.
- The report ("Fresing Render PC check.html", also on the Desktop) shows every function as OK, FAILED (with
  the reason) or skipped, how long it took and how long it took last time on your PC. Steps more than 25 %
  slower, and pictures that are black, empty or look different from last time, are listed under **Look at
  these**. Functions new since your last check are on top. Small pictures of the test renders show at a
  glance that they look right.
- Your own model, if you like: drop a STEP file on **Fresing Render - PC check** on the Desktop, or tick **Also test my own STEP
  file**. It measures import time, parts, the share sorted, a picture on the graphics card and the time per
  frame for Preview and EEVEE.
- At the bottom: **Copy** the text for the lead chat. It holds numbers only – no file names, part names or
  pictures; the report stays on your PC.
- The check also runs on GitHub at every change, so it keeps working (there without a graphics card).
## 0.2.23 – 6 Nov 2026 – video finishing: logo, title and end card, captions, watermark (task 0018)

Videos come out ready to post or send.
- **Brand kit** (5 Scene & Render > Brand kit & logo): one kit per company with logo (PNG or JPG), card colour,
  text colour, font and contact line. **Save kit** puts it in the shared library (folder "Brand kits", next to
  "Rule sets"); the arrow next to **Kit** loads a saved kit. Every project keeps its own copy of the settings.
- **Finishing** (end of 6 Animation): logo in a corner (any of the four, adjustable size), **Title card** (title,
  subtitle, seconds), **End card** (logo and contact line, seconds) and **Captions from the step labels**
  (each labelled step shows its label while it happens, with a short fade). The video is as long as title card
  + animation + end card; the last line shows it. It goes into MP4 videos (not into PNG frames).
- **Square and upright videos**: **Framing** says what happens to the picture for 1:1 and 9:16: **Extend**
  keeps the width of the 16:9 picture, **Crop** keeps its height. New animations start on Extend; a 9:16 video
  of an older project now shows the whole width of the 16:9 picture instead of a narrow strip in the middle.
- **Logo on still images** (corner and size in the brand kit fold).
- **Watermark** (5 Scene & Render > Watermark): DRAFT, CONFIDENTIAL or your own words across images and videos,
  size and see-through amount adjustable. A switch decides per render: each job in the queue remembers whether it was
  added with the watermark on ("with watermark" in its name), so a draft can go out and the final renders clean.
- Every new button and setting has a tooltip; user guide chapters 5 and 6 have the new parts with pictures.
- Small: "1 prop deleted" (not "1 props").
- Tests (2-core test machine): 33 new automated tests (pictures of the title card, captions at their step times, logo
  in the chosen corner and watermark checked pixel by pixel; a queued animation with every option makes a square MP4
  of title + animation + end card length); real app: 14 new checks.

## 0.2.22 – 6 Nov 2026 – chips fly while milling (task 0028)

4 Motion > Milling > Chips (new)
- While the bit cuts, chips fly off it in the spindle's turning direction and land on the block, the
  table and the machine bed, where they pile up. **Chips: None / Few / Realistic** – Few is about one
  chip in eight (at most 3,000 at a time), Realistic as many as the removed material makes (at most
  25,000 at a time; the oldest lying ones then shrink away). The deeper or longer the cut, the more chips.
- They look like the material and the bit: shiny aluminium curls, blue-brown steel commas (temper
  colours), golden stainless commas, brass and cast-iron crumbs, long plastic ribbons in the block's
  colour, wood shavings with dust; long spirals out of a drilled hole, fine dust from an engraving bit,
  flat commas thrown far by a face mill.
- **Material: From the workpiece** reads it from the block's name ("BLOCK AlMg3", "Plaat RVS 316", "POM
  blok", "MDF plaat" …) and then from its material in 3 Looks; or pick one. **More**: Spindle turns
  clockwise (M3) or counter-clockwise (M4); Coolant mist (a fine mist around the bit that fades).
- Chips lying on the block are gone when the bit cuts there later; chips on the table ride along with
  it; chips that fall off the table stay on the bed or the floor.
- Worked out once whenever the motion or a chip setting changes (under 1 s for a short cut, about 4 s for
  a 46-second pocket program on the 2-core test machine). The same set-up gives the same chips every time,
  on every PC, whatever frame is shown first. The render queue works them out by itself before it renders.
- **Clear chips** removes every chip from the project and sets Chips to None.
- Render time, measured on the 2-core test machine (processor, 640 × 360, Preview): 26.0 s per frame
  without chips, 26.5 s with Few, 28.8 s with Realistic for a small slot; a bigger cut with about 6,200
  aluminium curls 32.2 s instead of 24.4 s. On the graphics card: still to be measured on your PC.

## 0.2.21 – 6 Nov 2026 – logos, text, type plates and stickers on the machine (task 0024)

3 Looks > Logos & stickers (new)
- Put a **picture** (your logo: PNG, JPG…), **text** you type, or a ready-made **sticker** on a part:
  choose it, click **Add decal…** and click the spot on the model. It lies flat on that face, upright,
  like a real sticker. On a round face (a cylinder barrel, a drum, a tank) it wraps round.
- Ready-made stickers, drawn by the app: CE mark, type plate (company, type, serial number, year,
  weight, small CE mark), warning signs (general, hand crush, electricity, hot surface, hanging load),
  a straight and a turning arrow.
- **Move with the mouse** (also onto another face of the part; wheel turns, Ctrl+wheel sizes), or by
  numbers: width and height in mm, right/up, turn. **Fit to face**, **Upright**, **Mirror**,
  **See-through**, **Finish** (matt, satin, gloss, metal).
- Text and stickers: colour of the letters, background and border on/off with their own colours,
  any font (the fonts on your PC are listed).
- On **every copy** of a part (a type plate on a bought motor) or on **this copy only** (a serial
  number). The list shows the decals of the clicked part (rename, switch off, remove) and of the whole
  project.
- A decal moves, turns and hides with its part: joints, poses, exploded views, animations, the render
  queue. Pictures are kept inside the project.
- Library: put your logos as PNG files in the folder `Logos` (and stickers in `Stickers`) of the
  shared library; they show in a list next to Picture.
- A model update keeps decals whose spot is still on the part; one whose face moved is switched off
  and named in the update report. A template keeps decals and puts them on parts with the same name.
- A click on a sticker while painting faces paints the face under it.


## 0.2.20 – 5 Nov 2026 – fasteners in supplier notation (task 0030)

Screws, nuts and washers named the way supplier catalogues write them now land in the fastener groups:
set screws like "MSSF5-5" or "SSCP5-8" (size and length read from the name), "WRENCHBOLT M8x20" and
"WRENCHBOLT6-15" (socket head cap screw), "BOLT5-20", "SCREW4-10", "NUT5" and "WASHER6". Your normal metric
bolts (DIN/ISO, any length, HDG / tZn / gvz / zwart / A2 / A4 / RVS) were already right; they are now
covered by tests too, so they stay right. No name that matched before stopped matching.

## 0.2.19 – 5 Nov 2026 – milling: the bit takes material away from the workpiece (task 0027)

Commit: 5f8bd88 (merge into main).

4 Motion > Milling (new)
- Click the milling bit in the view and **Use as bit**, click the raw block and **Use as workpiece**:
  wherever a bit moves through the block in the animation, material disappears – in the view while
  you scrub back and forth or play, and in the render queue. No modelling, no booleans by hand.
- The bit's shape is read from the part: flat end mill, ball end mill, corner radius, V-bit and drill
  are recognised (any other shape is used as it is). Or pick the type and type in diameter, corner
  radius, tip angle and length. Several bits are allowed; **Tip at the other end** turns a bit round.
- The workpiece may move too (a table on a slide joint): the cut follows the block.
- **Finished part** (optional): the CAD model of the machined part. The bits never cut below it, so
  the end result is exactly the CAD part even if the motion goes a little too deep.
- **Detail** Fine / Normal / Fast, **Cut material** on/off, **Reset workpiece**, **Stop milling**
  (the block is whole again). A changed animation is read again by itself. Saved with the project;
  a model update keeps the set-up.
- Cut edges are sharp like the CAD part (mesh booleans with the Manifold library, the same one as
  Blender's "Manifold" boolean). Straight moves cost one boolean each, however many frames they last.
- Measured on the 2-core test machine, 200 × 200 × 40 mm block: zig-zag pocket with a flat Ø10 bit
  3.6 ms per frame (Normal), with a ball Ø10 11 ms; a round pocket made of short pieces (like arcs)
  11 ms per frame.

Self-test
- New line "Milling (Manifold library)": the bundled library loads and cuts a slot of the right size.

User guide
- New part "Milling" in chapter 4, with a picture of the panel.

## 0.2.18 – 5 Nov 2026 – couplings and motors: one joint moves a whole mechanism (task 0012)

4 Motion
- **Follows a joint**: a joint moves along with another one at a ratio – gear pairs (turns per
  turn; negative for meshing gears), telescope sections and gripper jaws (mm per mm; −1 for the
  second jaw), spindles, ball screws, racks and winch ropes (mm per turn), rolling wheels and
  pinions on a rack (° per mm). An **Offset** sets where it stands when the other joint is at 0.
  A line under the ratio says it in other words ("One turn every 157.1 mm: a wheel of Ø50.0 mm
  rolling along").
- Chains work (a motor drives a spindle, the nut carries a trolley, its wheels roll). Two joints
  that would follow each other are refused, with the reason in red. A following joint shows its
  value in purple and is not moved by hand, by poses or by animation steps; its limits only warn.
  **Moves by itself** ends it; the joint stays where it is. The leading joint shows "Drives '…'".
- **Motor (turns without end)** on a rotate joint: no limits, the angle also in turns.
- Couplings and motors stay through a model update and in saved projects, also on a PC where
  project files may not run scripts (and in the background render queue).
- Removing a joint that others followed: they stay where they are and move by themselves.

6 Animation
- New step **Run motor**: a motor turns at a speed (rpm; a slide joint in mm/s) for the step's
  duration, with ramps (**Smooth**, **Slow start**, **Slow stop** and **Ramp (s)**). 12 rpm for 5 s
  at constant speed is exactly 1 turn. Joints that follow it move along. The step shows how far
  it goes ("0.90 turns in this step").
- A step for a joint that follows another one is shown red, and says which joint to pick.

Also
- Every button and setting of 4 Motion, 6 Animation, 7 Render queue and Saved scenes has a
  tooltip that says what it does and how to use it.
- Joint names can no longer be empty or used twice (steps and couplings find joints by name).
- User guide, chapters 4 and 6: couplings, motors and Run motor, with two new pictures.
## 0.2.17 – 5 Nov 2026 – light looks, camera views, background blur, turntable video (task 0017)

Commit `82555db`.

5 Scene & Render
- **Light look** at the top: five buttons that set light, background and floor in one click –
  **Product studio** (soft main light front left, fill, two rim lights, light grey background),
  **White, endless** (pure-white background with a soft shadow, bright soft light), **Dark studio**
  (black background, rim lights), **Outdoor sun**, **Overcast**. On the sea, the deck or the quay
  only the weather changes. The button of the look you see stays pressed.
- **Light**: new choices Product studio, White studio, Dark studio; the old studio light is now
  called **Soft studio** (old projects keep it and look the same). **Weather**: Sun or Overcast,
  wherever the sky gives the light (also on the sea, deck and quay). A line under the light says
  it in words: "Main light from the front left, high · normal brightness". **Strength** is now
  called **Brightness**.
- **Camera** (now its own part of panel 5): one-click views **Isometric** (no perspective),
  **Front**, **Side**, **Top**, **3/4 hero, low**, **3/4 hero, high**, **Where I look now** and
  **More**. They frame the **Whole model** or the **Selection**, with **Space around** Tight,
  Normal or Roomy; the new camera becomes the active one and the view looks through it.
- **Background blur**: None, A little or Strong – the same look on a small part and a big crane,
  each camera its own; the f-stop is worked out for you. **Sharp at**: the middle of the machine,
  or click the eyedropper and then the spot that should be sharp; the spot moves with its part.
  Renders in the queue use it too.
- **Turntable video**: length, camera height and quality, then **Make turntable video**: the
  camera goes once round the machine, the whole machine stays in the picture, the video loops
  without a jump; it goes into 7 Render queue and the queue starts. It makes the camera
  "Turntable camera", the saved scene "Turntable" and the animation "Turntable" (change size,
  shape or frame rate in 6 Animation, then click the button again). In a hall it says halls
  render 1.4–2.8× slower and offers **Use Simple**.

Fixed
- An Isometric (or other orthographic) camera in an upright picture cut off the sides.
- A camera added while the sea was the background did not see to the horizon until the
  background was rebuilt.

User guide: chapter 5 – Light look (with a picture of the five looks), Light, Camera, Turntable
video; new pictures of panel 5.

## 0.2.16 – 5 Nov 2026 – updates inside the app (task 0020)

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

## 0.2.15 – 5 Nov 2026 – clean-up of sections 1–3: tooltips, "1 part" not "1 parts" (task 0023)

Commit `ea65ef1`.

1 Import, 2 Structure, 3 Looks
- Every button and setting in these sections explains itself when you rest the mouse on it.
  Buttons that shared one text now each say what they do: the two arrows next to **Find in the
  tree** (open all / close all), **Show only the unsorted parts** and **Show only these**, **+** and
  **From clicked part** in Sorting rules (the second one names the part you clicked), the up and
  down arrows, the two tick buttons in Find & sort parts. The × of the model update report and
  the names in the lists of visibility sets and paint schemes got a tooltip too.
- The choices of a sorting rule (Part name, CAD colour, Finish… / contains, is, matches
  pattern…) each explain what they mean in the drop-down list.
- **From active part** (Sorting rules) is now called **From clicked part**.
- Counts say "1 part", "1 face set", "1 group", "1 core" (the Paint faces header said
  "1 face sets"); also in the messages after a button, in the window that shows what a rule-set
  switch changes ("1 part changes group") and in the model update report.

All sections
- Tooltips no longer break in the middle of a sentence (23 of them did, for example those of
  **Render image**, **Add camera** and **Defaults**).

User guide
- Chapters 1–3 checked against the app: **Make it a rule** for a whole subassembly, the
  placeholders a group name can hold, where **+** puts a new rule and **Select the ticked parts in
  the view** were out of date or missing. New picture of Paint faces and Sorting rules.
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
