# Changelog

What changed in each version, in plain words. Newest first. The app shows these texts under
"What's new" when it offers an update, and each GitHub release carries its section. From 0.2.16 on,
the release page (tag `v<version>`) shows the commit; before that, "Commit" is the Git commit the
installer of that version was built from.

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
