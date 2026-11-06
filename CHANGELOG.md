# Changelog

What changed in each version, in plain words. Newest first. The app shows these texts under
"What's new" when it offers an update, and each GitHub release carries its section. From 0.2.16 on,
the release page (tag `v<version>`) shows the commit; before that, "Commit" is the Git commit the
installer of that version was built from.

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
