# Changelog

What changed in each version, in plain words. Newest first. The app shows these texts under
"What's new" when it offers an update, and each GitHub release carries its section. From 0.2.16 on,
the release page (tag `v<version>`) shows the commit; before that, "Commit" is the Git commit the
installer of that version was built from.

## 0.2.225 – 24 Nov 2026 – The winch and spool test models at real size; the winch drum is full of wire (task 0263)

- **The cable test machine** (test tour "Cable over sheaves", the PC check, the user guide) is now real size: its
  A-frame stands about 5 m tall on an 8 m base. The winch drum, the sheaves, the V rollers, the chute and the 24 mm
  wire rope kept their real size – the rope's way is longer.
- **The winch drum is full of wire rope**, layer on layer, and works as a winch drum (4 Motion > Drums and carousels):
  when the rope runs, it winds off and on the drum wrap by wrap. A new picture in the user guide shows it close up.
- **The spooling test model's carousel** is twice as big: 4 m across with a 1.28 m core, so the 40 mm power cable
  bends round it as a real one would. It holds 665 m of cable now (was 166 m). The winch beside it is unchanged.
- **Web 3D model:** a cable coming off a drum or carousel could show one ring more at its end than the app; the page
  now ends it exactly where the app does.

## 0.2.224 – 24 Nov 2026 – Joints in a fold, several parts per cylinder item, a clicked joint shows what it moves (task 0290)

- **4 Motion > Joints** is now a fold of its own, like Cylinders and Mechanisms: Add rotate joint, Add slide joint,
  the joint list and the selected joint's settings sit in it. "Everything back to CAD position" stays at the top of
  4 Motion.
- **Cylinders take several parts or subassemblies per item.** Under Barrel and Rod, **Add selected** adds what is
  selected (Shift+click or Ctrl+click in the view or in 2 Structure selects several) – it no longer replaces what was
  picked. Each pick shows as a short row with **×** to drop it, **🗑** clears the item. A part is never in both: adding
  it to the rod takes it off the barrel. The same for a made cylinder (Set-up: parts and pins: barrel, rod and stages),
  and in the Set-up window's cylinder step of Set up a crane. The stroke is read again from all the parts.
- **The panel stays still:** a follower past its limits shows a short red "Beyond limits" on its Distance / Angle
  row (the longer text when you rest the mouse on it) instead of two new lines that pushed Limits and the fields
  under it down while you dragged. A cylinder past its stroke does the same on its Stroke row.
- **Clicking a joint in the list shows what it moves:** its arrow (also when "Show joint arrows" is off) and its parts
  tinted green in the view, joints riding on it in a lighter green. Nothing gets selected, hidden parts stay hidden
  (the box says how many). Clicking a mechanism shows its moving links. A click elsewhere ends it. The list rows have
  a real tooltip now.
## 0.2.223 – 24 Nov 2026 – Make: larger icons, switch outputs in their window, Render this view (task 0308)

- **Make's row is taller, with larger icons** – easier to hit; still one row at the top of the Fresing panel.
- **Every output window has a strip of all outputs on its left.** Picture, Product video, Turntable, 3D page, Animation
  and Queue, the one the window shows in blue: one click shows another output in the same window. Drag the strip wider
  and the names show beside the icons. Blender's own side-panel tabs (Tool, View, Animation) no longer show in these
  windows.
- **Render this view** (under the Make row, and in Make in the 3D view's header): renders exactly what the 3D view
  shows – its angle and zoom – at the Picture's size, quality and file type, without adding or picking a camera. The
  picture is fitted round the view, so nothing you see is cut off, and saved as *project*_View_*date*_*time*. The
  active camera and your saved cameras stay as they were. In camera view it renders that camera.

## 0.2.222 – 24 Nov 2026 – More part kinds; unnamed washers, nuts and O-rings found by their shape (task 0302)

- **About 230 more part names are recognised** when the parts are sorted into groups, in English, Dutch and German,
  from public catalogues: hose ends and tube fittings ("Schneidring", "SNIJRING", "HOSE TAIL", "Überwurfmutter"), test
  points, rotary unions, lubricators, compressors, heat exchangers, air receivers and tank accessories, pressure and
  temperature sensors, flow meters, linear scales, claw / bellows couplings and cardan shafts, crossed roller guides,
  wire rope ends and lifting points ("Kausche", "PERSHULS", "Lastöse", "KRAANHAAK"), rod seals and wipers, index
  plungers, swivel feet, magnet catches, thrust washers, slide blocks, brake resistors, blowers, control panels.
- **German and Dutch one-word fasteners** now count as fasteners too: "Federscheibe", "Zahnscheibe", "Passscheibe",
  "Nutmutter", "Einschlagmutter", "SLEUFMOER", "BLINDKLINKMOER", "Senkniet", "BORGRING" and more. Bonded and thrust
  washers are no longer taken for fasteners (they go to the seals and the plain bearings).
- **Parts whose name says nothing** ("Part123", "Onderdeel4", a drawing number) are looked at once more by their
  shape: a thin flat ring with a round hole goes to the fasteners as a washer, a hexagon with a bore about as high as a
  nut as a hex nut, a torus to "Seals & O-rings". Only these three, and only when the shape leaves no doubt; every
  other part keeps the group its CAD material or colour gives it.
- On the test models only one part changes group: the test mill's "CONTROL PANEL" (a box with a screen) is now an
  electrical part instead of a cover. New PC check line: **import.shapes**.

## 0.2.221 – 23 Nov 2026 – Always the graphics card (task 0296)

- **Renders use only the graphics card.** On a PC with an AMD processor and an AMD card, the processor's small built-in
  Radeon and the card were both used for renders, and the built-in one slowed the card down. Now only the card renders
  (NVIDIA, AMD Radeon RX / Pro, Intel Arc). A PC without a card keeps using what it has.
- **The window on the graphics card.** Windows picks which GPU draws each program; Blender only asks NVIDIA's driver
  for the card, not AMD's. The installer, Update now and the app's start now set Windows' graphics preference for
  Fresing Render to High performance (Settings > System > Display > Graphics) – only where you have not chosen
  yourself. It counts from the next start. The uninstaller removes it again.
- **A calm notice** when the window is still drawn by the built-in graphics although the PC has a card, or when the 3D
  view is clearly slow: **Use the graphics card**, **Show me how** (Windows' Graphics settings, NVIDIA Control Panel,
  the monitor cable in the card, not the motherboard), Cancel = not now, **Don't ask again**. At most once per start.
- **Fresing > Settings > General > Graphics:** which GPU draws the window, which renders, and **Render on** to pick
  the device (or the processor).
- Self-test line "Graphics card used", PC check line `pc.gpu`; the PC check's report names the GPU that draws and the
  one that renders. New guide section "Graphics card" (Troubleshooting).

## 0.2.220 – 23 Nov 2026 – Update now: save or not, also for a project that was never saved (task 0316)

- **Update now no longer refuses a project that was never saved.** With unsaved changes it asks first, in one small
  window: **Save and update** (as before) or **Update without saving**; for a project that was never saved the first
  button is **Save as… and update** – choose a name and a folder, and the update goes on by itself once it is saved
  (Cancel in Save As: nothing happens, Update now stays). **Cancel** closes the window.
- **Update without saving**: the app opens again with the project as you last saved it (or empty, for a project that
  was never saved) – the changes since then are left out. With automatic backups on, one backup copy of the work is
  kept first ("A backup copy is kept"); the next start does not ask to restore it, it is in Fresing > Restore a
  backup… if you need it. The app closes without Blender's "Save changes?" question; that question is back as usual
  afterwards.
## 0.2.219 – 23 Nov 2026 – Place: move and turn by numbers; Remove a model, subassembly or parts; a lock in every tree row (task 0292)

- **2 Structure > Place** (new): select a model, a subassembly or parts and type where it goes – X / Y / Z in mm and
  turns in degrees, measured in the **World** or along the **Model axes** (then 0 means "where the CAD file has it").
  **–** / **+** step it by 10 or 100 mm, 15 or 90°; **Snap** rounds to 1 / 10 / 100 mm or 5 / 15 / 45°. **Move with
  mouse** / **Turn with mouse** (X / Y / Z keeps to an axis, type a number, click to place), and **arrows and rings**
  on what is selected while Place is open. **Put on the floor** and **Back to the CAD place** (a model: **Back to where
  it was imported**). The right-click menu's **Move / turn…** opens the same in a window of its own.
- **A Place move stays**: Build & play, poses, Reset pose, saved scenes and a model update keep it. A whole model moves
  with its joints, cylinders, hoses, cables and labels. A subassembly a joint moves (the boom on its pin) takes the
  joint's axis along.
- **Remove…** (new) – in Place, in the selected row's box of 2 Structure, in the right-click menu, and the **Delete**
  and **X** keys outside Full access: a window lists what goes with it (parts, joints, cylinders, mechanisms, hoses,
  cables, labels, stickers, animation steps that only move it) and what only loses something; **Remove** takes it out
  in one step, **Ctrl+Z** brings it all back. The import stays (1 Import > Imported models), and a model update keeps
  removed parts out. **Clean-up** stays what it was: it only hides parts and Restore all brings them back.
- **A lock in every 2 Structure row**, next to the eye and the arrow: closed = locked in place, open = free to move;
  one click switches it (greyed when a subassembly above it is locked – it still moves with that one).
- The part count of a model's box now counts like 2 Structure's header (parts without a shape in the CAD file were
  counted in the box only: 564 vs 562).

## 0.2.218 – 23 Nov 2026 – Drop a file like Import STEP…, Imported models with Import again, Up axis after the import (task 0289)

- **A STEP or mesh file dropped on the view now comes in exactly like Import STEP…**: the side panel opens on
  1 Import (also when it was hidden or another section's tab was chosen), the Detail and Up axis you chose there are
  used, the progress bar with Esc to cancel shows, then the model's box and the same message. Several files dropped
  at once: the first one is imported and the panel says so.
- **1 Import > Imported models** (a fold; its title says how many are stored) lists every model in the import cache,
  newest first, with parts, detail, size and date. **Import again** adds it to this project – an unchanged file from
  the stored copy in seconds, a changed file read again (the message says so), a moved file from the stored copy.
  The folder button shows the file, the bin removes it from the cache (asks first). A search field from 11 models on.
- **Up axis after the import**: each model's box has **Z up / Y up**. It turns the whole model as the import would
  have; joints, cylinders, poses, saved scenes and labels keep working, a built animation is taken off (Build again
  gives the same motion, turned). One Ctrl+Z undoes it; a model update keeps the axis.
- New PC-check lines `import.drop`, `import.again`, `import.up_axis` and a test-tour stop "Import again and Up axis".
## 0.2.217 – 23 Nov 2026 – Make a crane and the other forms open in windows that stay open (task 0282)

- **Make a crane… opens in a window of its own** – and so do 22 more forms: Save as my own workspace, Save pose,
  Save scene, the rule-set Copy / New / Rename, Make demo project, the PC check's choices, Learn…, My learning list,
  Restore a backup, About and others (the user guide has the list). The window **stays open** while you click in the
  main window, can be **dragged onto another screen**, and opens again **as big as you left it** (on Windows also
  **where** you left it). Two different windows can be open at once; pressing the button again brings its window to
  the front with what you typed.
- Its button at the bottom (**Make**, **Save**, **Start** …) works with the project **as it is when you press it**;
  when it cannot (no name, no model, a job running), the window stays and says why in red. **Cancel**, the **X** or
  **Esc** over the window close it; **Return** there is its button. Undo works as before.
- Short yes / no questions ("Remove this?", "Switch rule set?") stay small popups. The Client view refuses the same
  functions as before. Window sizes and places are kept in the app's settings file.

## 0.2.216 – 23 Nov 2026 – Moving parts with G / R: it moves, or it says why not (task 0307)

- **Why G / R did nothing:** after an import every subassembly is *Locked in place*. G / R showed their numbers, and on
  Enter the part was back – without a word. Now G / R (and S) say at once in the status bar why something cannot move
  and what to do, and nothing starts.
- **Right-click a part > Unlock so it can move** unlocks its subassembly (the same as 2 Structure > Locked in place).
  Then **G X 500 Enter** moves it half a metre along X, **R Z 90 Enter** turns it a quarter turn, and it stays.
- **After Build & play** a move was undone at the next Build or Stop. G / R now say: stop the animation first
  (4 Motion > Stop it to move joints by hand), move it, build again – the new place is kept.
- New guide section "Moving and turning parts" (2 Structure), a PC-check line and a test with real key presses.

## 0.2.215 – 23 Nov 2026 – Test models at real size: the gantry routers and the way covers (task 0262)

- **The two gantry routers are 2.5 times bigger and stand on a stand.** The CNC gantry of the test tour, the PC check
  and the guide was a desk router on the floor: now its bed is 2.0 x 1.5 m (a sheet-size router) and its top is at a
  working height of 0.9 m. The tool carousel is Ø425 mm. The tools, the 300 x 200 x 30 block, its clamps and bolts and
  the T-slots keep their real size; the servo motors have real sizes.
- **The drag-chain router is the same machine:** its chain links keep their size (pitch 40 mm, bend radius 80 mm), the
  chains are just longer – 62 links instead of 47.
- **The way covers are twice as big:** an X axis of 1000 mm, like the test mill's, the sheet still 3 mm.
- Same part names, assemblies and colours as before (the routers get one more part, `MACHINE STAND`). The tour stops
  show the new sizes: the way cover's carriage now travels 1000 mm, and the drag chains' program moves further.


## 0.2.214 – 23 Nov 2026 – Fresing Render is in Windows' "Installed apps": uninstall it from Settings (task 0265)

- **Settings > Apps > Installed apps now lists Fresing Render**, with its version, "Fresing" as the publisher, its icon
  and its size. **⋯ > Uninstall** there removes the app like any other program: a window says what goes and that your
  projects, renders and backups stay, and closes on a key. It needs no administrator rights.
- **Update now keeps the entry right** (the new version and size), and an install made before this version gets the
  entry once at its next start – you do not have to install again.
- **Uninstall.bat** in the installer folder still works and does the same.
- New line in the self-test: "Windows: in Installed apps".

## 0.2.213 – 23 Nov 2026 – Test models at real size: the scissor lift table and the bearing unit (task 0264)

- **The scissor lift table is 0.80 m wide.** Two scissor pairs stand side by side, joined by cross tubes, with a wide
  roller and long pins across the width; platform and base are 1.30 × 0.80 m. Lift height, arm lengths and the
  mechanism's numbers are unchanged. It is in the Mechanisms test set.
- **The bearing unit's nut is a shaft lock nut** (KM 5, M25 × 1.5, Ø38, 7 high, four slots in the rim) instead of an
  M24 hex nut. It is in the Assembly sequence and Product video test sets.

## 0.2.212 – 23 Nov 2026 – "Making the Learning hub" says so clearly; Next goes to the next stop at once (task 0275)

- **A card in the middle of the screen while the Learning hub is made.** It says what is happening, shows a bar with
  "project 4 of 23", about how long it still takes, and that you can keep working. **Hide** keeps the bar in the
  bottom-left corner and on the left panel (**Show progress** brings the card back); **Stop making it** asks once and
  keeps the projects made so far.
- **When it is done** the card comes up (also when hidden): **The Learning hub is ready – Open it now / Later**. If
  something failed it says what, where the log is, and offers **Try again**. Every way of making the hub (Fresing
  menu, the welcome, What's new, the left panel) uses the same card.
- **Next in the Learning hub** now sets the next stop up in one click, also when it lives in another project. The
  welcome says you can keep working while the hub is made.

## 0.2.211 – 23 Nov 2026 – Test models at real size: the cylinder arm, the hose arm and the mesh crane (task 0261)

- **The two luffing arms are three times bigger.** The cylinder arm and the hose arm of the test tour, the PC check and
  the guide were desk-sized next to the life-size people and props: now the arm reaches 4.5 m from its pivot, which
  sits 1.8 m up. The parts that have a real size are drawn at it, not three times bigger: pins Ø60, cylinders with a
  Ø125 bore and a Ø70 rod (an ISO size), M24 anchor bolts (`ISO 4017 M24 x 120 - 8.8 HDG`). The hoses, fittings,
  glands and the cable keep their real thickness and only get longer (the arm's hose is now 3.0 m).
- **The mesh crane is 2.5 times bigger**: a 7.5 m boom and a cab 2 m high (it was lower than a person), with a real
  Ø100 boom pin.
- Same part names, assemblies and colours as before. The
  tour stops show the new sizes: the cylinder now strokes 450 mm, the hose arm's slide travels 360 mm out and 660 mm
  back.


## 0.2.210 – 23 Nov 2026 – Locations: company, department and your own folders; set-up files; export places (task 0272)

- **Several folders per kind, each with a badge.** STEP models, materials, logos, stickers, 360° photos, templates,
  rule sets, workspaces, brand kits and lifting equipment can each have several folders – **Company**, **Department**
  or **Mine**. Every list in the app (logos and stickers, rule sets, templates, 360° photos, brand kits, your
  workspaces, lifting equipment) shows what all of them hold, sorted by name, each with its badge
  ("Acme · Company"). The same name in two folders shows twice. A new tab **Fresing Settings > Locations** shows
  them, one fold per kind.
- **Your own folders are ready from the start.** No more "No library folder" message: the app makes
  `Documents\Fresing Render\Library` with a folder per kind at its first start, so Make a crane, a logo and a saved
  rule set work straight away. A **Shared library** folder you had set before is your own folder now, with its
  sub-folders as they were – nothing is moved.
- **One set-up file for a company or a department** (`.frsetup`): its folders, export places and settings in one file,
  optionally with the logos, rule sets … themselves packed inside. **Add a set-up file…** (or drop it on the window),
  linked where it lies or copied into the app. A newer file of the same set-up – whatever its name – shows what
  changes first (**Update** or keep the old one); a linked one that changed on the network updates itself at the next
  start. **Save as a set-up file…** makes one from your own settings; **Edit this set-up file…** writes one back.
  **Different from standard** lists what is not as the app comes, with where it comes from, and **Back to standard**
  for your own choices. A set-up put by IT next to the approved version is picked up by every PC by itself.
- **Saving asks where**: a new rule set or workspace goes into your own folder first; when you can write into more
  than one, the dialog has **Save in**.
- **A folder that cannot be reached** (network down, VPN off) is greyed with a line why and its items are left out
  until it is back. The app never waits for it: measured, the start's reading with a folder on a server that does
  not answer took 53 ms (test machine).
- **Export places** (new tab **Fresing Settings > Exports**): Next to the project (Renders) – still the standard –,
  Pictures\Fresing Render\<project>, places from a set-up and your own. Each project's outputs have **Save to**
  (Render image, the render queue, the web 3D model), and **Also save a copy to** saves a second copy of every
  picture, video and 3D page into another place, e.g. the company share.
- **Import STEP…** opens in your first STEP models folder and lists all of them on the left of the file browser.
- The PC check has the line "Locations", the test tour the stop "Locations and Exports"; the user guide has the new
  chapters Locations and Exports; "Using it in a company" has "Set up locations for everyone" with an example.

## 0.2.209 – 23 Nov 2026 – The Fr mark in the top bar (task 0279)

- **The Fr mark instead of Blender's logo.** At the far left of the top bar stands the green and white Fr mark, in
  every workspace. Click it: **About Fresing Render…**, **Fresing Settings…** and, under a line, **Blender** with
  Blender's own menu (Splash Screen, About Blender …). The Fresing menu after Help stays as it was. Switching the
  extension off gives Blender's logo back.
## 0.2.208 – 22 Nov 2026 – Learning hub: one group open at a time, lesson buttons on top (task 0281)

- **One group of stops at a time.** In the Learning hub's list of stops, opening a group (Look, Motion, Machining,
  Pictures and videos) closes the other one. Picking a stop in another group opens that group.
- **Lesson buttons at the top.** In the Lesson panel **Back**, **Next** (or **Do it for me**) and **Play on** now sit
  above the step's text, so they stay in the same place from step to step.

## 0.2.207 – 22 Nov 2026 – The double-arm, 4th- and 5th-axis test mills are the larger machine too (task 0250)

- **Double-arm tool changer (test tour stop "Double-arm tool change"):** the test mill with the arm is now the larger
  vertical machining centre of 0.2.195 (travel 1000 x 500 x 500 mm, BT40). Its tools sit in a **24-pot magazine
  beside the column**; the arm is longer (460 mm between its claws, 95 mm pull-out stroke for BT40) and a change takes
  about 1.9 s, as on such a machine. Three BT40 tools, random pots, every hand-over within 0.01 mm, as before.
- **4th axis:** a rotary table (faceplate Ø220) and a tailstock stand on the larger mill's table; the bar, the wrapped
  slot and the flats are as before. **5th axis:** a trunnion with a Ø250 rotary table on the same table; the tool still
  follows the part (TCP).
- The landing page's 3D model "Turn it yourself" shows the new mill with its side magazine (2.4 MB, loop 10.5 s).
- Fix: a project saved in the middle of a double-arm tool change and opened again worked out the CNC machine's work
  zero from where the hidden spindle tool had last been drawn – on the larger mill 480 mm off, so the program's timing
  and every change moved. The app now works out a hidden tool's place from the part it hangs on.
- The user guide's pictures of the arm and the rotary axes are made again; the test tour's three stops have new
  views.

## 0.2.206 – 22 Nov 2026 – Your settings are kept over a restart (task 0283)

- **Every setting in Fresing > Settings… now stays as you set it** – also after closing the app, after a restart of
  the PC and after an update. Until now Blender forgot them at every start while the app was open in its own layout,
  so the library folder, default template, lesson look, backups, update check and the rest went back to their
  defaults. Choices the app remembers by itself (Live preview on or off, the tab the Settings window opens on, Play
  on) are kept too.
- **Nothing to save:** a change is written within a second to the app's own settings file. Settings > General says
  so at its top.
- **A damaged settings file** (a PC that crashed while writing it) no longer matters: the app starts with the default
  settings, keeps a copy of the damaged file and says so in one red line on Settings > General.
- For IT: the file is `fresing_settings.json` in the app's settings folder; copy it to other PCs to give them the same
  settings ("Using it in a company" in Help > About).

## 0.2.205 – 21 Nov 2026 – Tool marks look good everywhere, without setting anything (task 0280)

- **Tool marks at any distance.** Real marks are often far finer than a pixel, so outside a close-up they used to
  turn into wandering stripes on walls (moiré), a sandy shimmer, or vanished from floors. Now the app never draws them
  closer together than a few pixels: further away it draws every second, fourth, eighth … mark and blends smoothly
  from one to the next while the camera moves. The arcs on floors and the lines on walls are readable in every shot
  of a part, in EEVEE and Cycles, in the view and in the final render; in a shot of the whole machine they fade into
  the sheen. **Mark size** still works on top, for bigger marks.
- **Bright satin walls.** Milled walls and floors are satin aluminium now: a wall no longer turns into a black
  mirror of the room (EEVEE showed pocket walls black, Cycles dark blue). The line where two depths meet is a clean
  line from any distance.
- **Coolant:** the wet sheen keeps cut metal bright – a clear, glossy film over it – instead of turning a wet pocket
  into a dark mirror with sparkles.
- Learning hub stop 60 (Tool marks) shows the cut again at its last frame (the camera rides on the table), and the
  Machining stops show the new look.

## 0.2.204 – 21 Nov 2026 – Live preview and Build & play once, top left; the left panel's folds are kept (task 0278)

- **Live preview** and **Build & play** are now only on the left panel (top left, also in its folded strip). They are
  gone from 5 Scene & Render and 6 Animation, so the right panel is shorter. 6 Animation still says **Built · Space
  plays it again**, with the **X** beside it that clears the built animation (its tooltip says so). Hints, the
  lessons and the user guide now say "Build & play (top left)"; the crane and milling lessons point at the button
  on the left – also at its icon when the left panel is folded to its strip.
- **Favourites folds** with the small arrow in its title row, like Learning hub, Lesson and What's next; the gear
  stays on the right. Folded, its title row says **1 question** when a question about an unused panel is waiting.
- **Every part of the left panel keeps its fold** – Workspace, Learning hub, its stops, Lesson, Favourites, What's
  next and the left panel's own fold to the strip: closed and opened again, in another project and after an update,
  they are as you left them. (Before, they opened again at every start.)
- Texts that said "sections 1–7" now say **1–8** (8 Lifting plan): the User guide's tooltip, the setting "Keep
  sections as I left them", the Learning hub and the guide; the guide's picture of the sections shows all eight.
- The section tabs **All · 1 … 8** have short tooltips: a number shows only its section's name ("Import", "Lifting
  plan"), All shows "All sections". How the tabs work is in the user guide.
## 0.2.203 – 21 Nov 2026 – The test crane at real size (task 0259)

- **The test crane is now a service crane at real size**, five times bigger than before: a base of 5 × 3 m, a boom of
  7.5 m on a pin 2.4 m up – a person walks under it – and real bolts (M30 anchor bolts, M24 screws), pins (Ø100 boom
  pin, Ø70 cylinder pins) and a luffing cylinder with a Ø200 bore. Next to the people, the IBC and the containers of
  the Learning hub it no longer looks like a toy. Same parts, names, colours and joints as before.
- The Learning hub, the crane lesson, the PC check and the user guide's pictures use the new crane. Projects you made
  with the old test crane open as before.
## 0.2.202 – 21 Nov 2026 – Blender's keys can no longer break the model; F12 renders; a short right-click menu (task 0253)

- **Blender keys that delete or change parts do nothing outside Full access.** Delete, X, Shift+D, Alt+D, Ctrl+J,
  Ctrl+P, Alt+P, Ctrl+A, M, Shift+M, Shift+A, Ctrl+H, Ctrl+0 … 5, Tab, Ctrl+Tab, Ctrl+Page Up / Down, I, Alt+I and K
  change nothing; the status bar says "That is a Blender key – Fresing > Show all of Blender gives you Blender's keys".
  H / Alt+H (hide / show), A, Home, the number pad, Z, Space, Ctrl+Z, F3, N, Ctrl+S and Ctrl+O work as before.
- **F12** renders a picture with the app (as the blue Render image button), **Ctrl+F12** renders the animation in the
  background (as Make's Render animation).
- **Right-click on a part** selects it and opens a short menu: Zoom to it, Show in 2 Structure, Hide, Show only this,
  Show all, Add a label here (pointing at the spot you clicked), Add joint here… On empty space: Zoom to all, Show all.
  In the Client view only the viewing entries, and Hide there hides in the view only.
- **Fresing > Show all of Blender** (Workspace > Full access) gives Blender's keys and its own right-click menu back at
  once. New test-tour stop "Keys and the right-click menu" in the crane set; PC-check line app.keys.

## 0.2.201 – 21 Nov 2026 – Fresing Settings: all settings in one window with tabs (task 0271)

- **Fresing > Settings…** opens one window with all of the app's own settings and a row of tabs along its top:
  **General** (library folder, default template and rule set, workspace for new projects, the highlight while
  picking), **Side panel** (sections, How it works, the favourites bar, the questions about unused panels),
  **Lessons**, **Backups**, **Updates**, **My usage** and **About**. Click a tab to change page; the window opens on
  the page you had last. Drag it anywhere – also onto a second screen; it stays open until you close it. Also from
  the gear at the top of the left panel.
- **My usage** is now a tab of this window: Fresing > My usage… and Help > My usage… open it there. Everything of the
  old My usage window is still there (the switches of the favourites bar and the questions moved to the tab Side
  panel).
- **My usage counts only the time you really use the app**: a mouse move, a click, the wheel or a button. When none
  of these comes for 2 minutes, that time is left out – also while the app plays an animation, renders, shows a Live
  preview or works through the queue by itself.
- Edit > Preferences > Add-ons > Fresing Render now only has a button **Open Fresing Settings**. Your settings from
  before stay as they were.

## 0.2.200 – 21 Nov 2026 – Coolant at the spinning tool: the splash follows the spindle speed (task 0257)

- **The splash now depends on how fast the tool turns and how big it is.** Coolant leaves the tool at about the speed
  of its rim (a Ø10 mm tool at 6,000 rpm: 3 m/s), in the turning direction (M3 / M4), in a flat band at the height where
  the jets hit the tool – no longer a cloud up the whole tool at the same speed for every tool.
- **Slow tool:** the coolant wears the tool as a film that turns with it and runs down to the tip, and drips off in a
  few streams of big drops.
- **Fast tool:** a fine, fast, flat spray; the faster, the finer. Above about 5 m/s at the rim the air turning with
  the tool bends the end of each jet and breaks part of it into a mist round the tool – less coolant reaches the tool
  (a Ø10 mm tool with full flow: about a quarter at 15,000 rpm). A stronger flow gets through better.
- The speed comes from the program's S words at **Build & play**; press it once in older projects. The test tour's
  Coolant stop now runs at 15,000 rpm. A frame still looks the same whatever frame was shown before; drawing it takes
  about 0.5 ms more.

## 0.2.199 – 21 Nov 2026 – Test tour: every set in its own surroundings (task 0233)

- **Test tour:** the machine sets stand in a hall that fits them (a factory or an assembly hall), the cable sets in a
  warehouse or factory, the looks and product-video sets in a clean light studio, and the people and props sets on a
  quay and in a warehouse round a real-size container, so you see the function in a place it belongs.
- **Cameras fixed:** Materials looks close at the worn base and trolley (Wear shows), the Mechanisms picture keeps the
  raised scissor platform in the frame, the night shift is brighter, and the weather video's stop now shows its middle
  (dusk coming, rain starting) instead of the dark end.
- **What's new / links:** the function list now links Couplings to the cable stop, Poses to the Model
  update stop, and Props: detail by distance to the props stop.

## 0.2.198 – 21 Nov 2026 – Web 3D page: flick the model and it keeps turning (task 0256)

- **Flick to spin.** On the web 3D page, drag the model quickly sideways and let go while it is still moving (mouse or
  one finger): it keeps turning that way, then slows down to the slow auto-turn (one turn a minute, still in your
  direction) – or to a stop when Auto-turn is off, like a turntable you gave a push. A slow drag still stops where you
  let go; a touch, a key, a saved view, the Film or a part tool stops the spin. The Auto-turn line in the settings
  says so.
## 0.2.197 – 21 Nov 2026 – Two panels: the steps on the right, everything else on the left; Make in its own windows; the Learning hub (task 0260)

- **The Fresing panel on the right shows only the work.** At its top: **Make**, the section tabs and (for a CNC mill or a
  mechanism) **Set-up window…** – then 1 Import to 8 Lifting plan. The first step is always at the top.
- **A new panel on the left of the 3D view** holds the rest: **Live preview** and **Build & play** (always there), the
  update notice, your **Workspace**, the **Learning hub**, **Favourites** and **What's next**. The small arrow at its top
  folds it to a narrow strip – Live preview and Build & play stay there as icons. The app keeps your choice. In Full
  access Blender's own tool buttons are at its top again.
- **Make is one row of six icons** (Picture, Product video, Turntable, 3D page, Animation, Queue); click **Make** for the
  list with names. **Each output opens a window of its own** with its settings and Make button: drag it anywhere, also
  onto a second screen – it stays open while you work elsewhere, until you close it. Pressing it again opens no second
  one (on Windows it comes to the front and opens where it was last time).
- **The test tour is now called the Learning hub.** On the left panel three buttons – **View · Show me · Build it
  yourself** – switch between the three ways to learn in one click; in your own project they open the Learn window.
  Your old test tour folder and results keep working.
- **What's next** can be folded with a small arrow; it stays folded until you open it again.

## 0.2.196 – 21 Nov 2026 – Test tour: the offshore sets in the open sea (task 0234)

- **Marine looks** in the test tour now show on a monopile standing in the open sea: its transition piece and platform
  above the water, and through a cut-away the pile right down to its toe 9 m in the seabed – growth below the sea's
  own waterline, the splash zone above it, run-down streaks, a concrete mattress on the seabed.
- **Vessel motion**: a person and an IBC tank stand on the deck beside the crane and roll with it.
- **Vessel at work, Cable into the sea, A cable on a moving part**: the test boats have real hull shapes – a flat
  bottom, round bilges, a fine bow under a raised forecastle and a deckhouse – and the workboat is seen from close by.
  The app now also reads their bow from the hull, so the wake and the bow wave sit at the right end.
- Nothing in the app itself changed; open the test tour (Help > Make test tour project) to see the new sets.
## 0.2.195 – 21 Nov 2026 – A larger test mill: a vertical machining centre (task 0249)

- **New test mill.** The small test mill is gone. In its place is an invented **vertical machining centre**: travels
  X 1000 × Y 500 × Z 500 mm, a 1200 × 500 table with three 18 mm T-slots, a BT40 spindle, a column with ribs,
  telescopic way covers that follow the saddle, a chip tray that falls to a coolant drain and tank (ready for coolant
  liquid later), about 2.4 m tall. The block, the tools, the programs and the work zero are where they were, so every
  cut looks the same – only now the table moves along X and Y and the head along Z, as on most VMCs.
- **A person changes the tool:** the machine now stands on the floor in its **own enclosure with two front sliding
  doors**, a control panel and a work light (no cabinet). The operator walks up, opens the doors, leans in, takes the
  BT40 tool out, lays it on the trolley, puts the next one in and closes the doors. People lean a little further now
  when they reach into a machine (up to 65° instead of 55°).
- **Test tour:** Milling a slot, Three tools and the hand, Tool marks, Air blast, Coolant, A person changes the tool
  and The app makes the toolpath run on the new machine; the tools are BT40. The PC check's milling lines too.
- **Fix – chips:** on a machine whose table rides on a saddle, chips that fell past the saddle sometimes fell
  through the fixed parts beside it and on for ever; they now land on those parts (or the floor).
- **Fix – long finishing programs:** whether a long program is worked out the fast way (as a height map) no longer
  depends on rounding noise of a few nanometres when its points lie on whole millimetres.

## 0.2.194 – 21 Nov 2026 – Web 3D page: Film – the motion through the video's camera (task 0252)

- **Film on the web page.** A web 3D model of a project whose animation has camera steps (Move to, Cut, Ride along,
  Fly a path, Keep a part in the middle), exported with **Include animation**, gets a **Film** button at the end of
  the page's play bar. Pressed, the page plays the motion **seen through the video's camera** – the same shots,
  camera moves, cuts and zoom as the rendered video – with the page's own light. The time line, Space, the arrow keys
  and the speed move it along. A drag or zoom leaves the Film while the motion plays on; the button then has an orange
  ring and one press glides back. A copied link opens the page in the Film. The page still opens in the free view.
- **Captions, labels, title and end card on the Film.** Three new tick boxes under Include animation (only when the
  project has a built Animation camera; all off by default): **Film: captions**, **Film: labels** (the part labels
  with their lines, riding on their parts) and **Film: title and end card**. They show only while the Film is on.
- The Film costs a few KB (the test crane: 4 KB) and the page draws as fast with it as without.

## 0.2.193 – 21 Nov 2026 – Toolbox: the newest format fixes (task 0245)

- **Houses from House Planner:** Fresing Render follows the Toolbox format's bug-fix version 0.1.1. A job whose file
  says a size no file can have, or names a file Windows cannot hold, is now refused at once with a clear reason
  instead of after a minute as "not complete". A job file with a field written twice is now read the way House
  Planner reads it (the last one counts) instead of being refused. Odd, hostile job files (deeply nested, huge
  numbers, broken text) can no longer upset the inbox.
- **Tested on Windows:** GitHub now checks that a folder link (junction) in the inbox is never followed or emptied,
  and that a job finishes right while another program keeps reading its status file.
## 0.2.192 – 21 Nov 2026 – Rigging and the hoist rope in its falls (task 0232)

- **Rig the load.** 8 Lifting plan has a new step, **Rigging**: **Find lift points** puts a lift point in every padeye,
  lifting lug or container corner casting of the load (by their names); **Add lift point** lets you click them (a click
  in a hole lands on the hole's axis). Pick a **sling set** (chain grade 8, wire rope or round slings; 1, 2 or 4 legs),
  the **shackles** and, if wanted, a **spreader beam** or the **lifting frame** LF-20 for a 20 ft container. All
  built-in gear is invented SAMPLE gear in usual size classes; your own slings, shackles and spreaders are files like
  your cranes.
- **Hang on the hook.** The load hangs under the crane's hook the way it really would: its centre of gravity straight
  under the hook, tilted when its CoG is off the middle. It then follows the hook – Hook to here, crane poses, joints,
  Build and the render queue. **Set down** leaves it where it is; **Remove** puts it back.
- **Each leg's angle and force**, and the checks C2 (two legs), C3 (three or four legs: "two legs carry", equal share
  or the offshore × 1.25), C4 (each shackle, the spreader, its legs) in green / amber / red. Plain words for odd cases:
  a slack leg, a leg too short, a load that would roll over (CoG above its lift points). The rigging's mass is added
  to the gross load.
- **The hoist rope runs in its falls.** A crane you place now has its rope reeved from the winch drum over the boom
  head's sheaves and down and up through the hook block's (the AT-100: 8 falls over 4 + 4 sheaves). Raising the hook
  1 m winds 8 m onto the drum, which turns layer by layer. Cranes placed before keep their one-piece rope until you
  press **Reeve the rope** (Equipment).
- **Line pull (C10)** in Hook & capacity: the pull in the hoist rope for the gross load on the crane's falls (reeving
  efficiency of API RP 9B), against the winch's maximum.
- Test tour: two new stops in the Lifting set – the pump skid on a 4-leg chain sling, the empty container on the
  lifting frame. PC check: two new lines (hang the skid; the AT-100's 8 falls).
## 0.2.191 – 21 Nov 2026 – No long freeze for a riding camera after a sea change (task 0238)

- **The window keeps moving while the camera is worked out again.** After a change of the sea (Calm → Rough, the water
  level) a camera step that rides on a part was worked out again in one go: on the full demo (4,481 frames) the window
  stood still for 10–11 s at the end of the progress bar. Now the camera's part is read in the same pass through the
  frames as the hoses and cables, a frame at a time, with the progress bar moving and Cancel working; its own last step
  takes about half a second. The whole re-bake on the demo is about 11 s shorter (103 → 91 s on the 4-core test machine).
  The camera's path is the same as before.


## 0.2.190 – 21 Nov 2026 – A let-go cable lies straight (task 0248)

- **The cable on the seabed stays where it lay.** When you let go a cable into the sea (**Let go here**), the cable
  that already lies on the seabed no longer turns into a snake of short waves from end to end: it does not move at
  all, during the settle or after it.
- **Only the stretch that hung in the water lies down** – in line with the cable before it. The let-go end goes down
  and forward along the lay line together, and what is left over lies in **one smooth bight** next to the end, never
  tighter than the cable's **Smallest bend** (none set: 10 x its diameter). Test tour stop "A cable on a moving part"
  shows it.
- A cable that piles up while laying (the warning "has … m more cable than the water is deep") now lies straight from
  its end and puts the extra cable in one bight next to the touch-down, instead of waves along the whole cable.
- Build after updating: a cable let go in an older version gets the new lying-down at its next **Build & play**.

## 0.2.189 – 21 Nov 2026 – Learn: Show me and Build it yourself on the sample projects (task 0230)

- **Fresing > Learn…** lists the sample projects (the test tour's). **View** opens the finished one in the test tour.
  **Crane** and **Milling a slot** now also have a lesson: **Show me** opens a new project with the plain model and the
  app does each step itself – the button to press stands out in the side panel, the part is shown in the 3D view, a
  card beside it says what happens – then waits for **Next** (or tick **Play on**). **Build it yourself** lets you do
  each step: the app points, and goes on by itself once the project shows the step done, however you did it.
  **Do it for me** does a step for you; **Back** (or Ctrl+Z) takes it back. The other samples get their lessons later.
- The crane lesson (11 steps): light look, a rotate joint, a joint on a joint, a camera, a saved scene, an animation
  with a step, Build & play, an exploded view, a picture in the render queue. The mill lesson (13 steps): three slide
  axes, the bit, the workpiece, raw steel, chips, a close-up, the cut, Build & play and a picture of the cut.
- A project saved half-way remembers its lesson: open it and the **Lesson** panel offers to go on where you stopped.
  Starting a lesson asks first when your open project has unsaved changes. In the Client view a lesson waits.
- **My learning list**: **Show me** and **Build** open the lesson of a function at its own step; the question about a
  panel you never use offers **Show me in a lesson**.
- The test tour: the crane and the mill are now made of their lessons' steps (View, Show me and Build it yourself give
  the same project). The crane's "open sea" stop is gone (the vessel and sea-cable stops show the sea); its finished
  video has a picture card and music; a new stop "Learn". New PC check line `app.lessons`; user guide chapter "Learn".


## 0.2.188 – 21 Nov 2026 – The demo is now "Vessel in a wind park" (task 0247)

- **A new demo project: "Vessel in a wind park".** Help > Make demo project… now makes an invented ship with her own
  deck crane in an offshore wind park of nine turbines and a substation, the park's power cable lying on the seabed
  right under her. Its video lasts about a minute: she sails in and holds her place on her thrusters, her crane slews
  outboard and lowers its hook (the wire comes off the drum layer by layer), along her hull and under water at her
  thrusters, at the seabed where the cable comes down turbine WTG 05, the park from above and at night. It is made in
  about a minute instead of six. The cable-lay equipment of the old demo is no longer part of the app.
- **New saved cameras** in the demo: **Deck crane** and **At the seabed** (through the cut-away behind the stern, along
  the cable to the turbine's foot).
- **The clash check can leave a whole model out, stored in the project.** The demo's wind park is left out this way
  (its nine turning rotors would make the check several times as long); the mark stays when you save, reopen or
  update the model. A demo kit uses it for its own scenery.


## 0.2.187 – 21 Nov 2026 – Automatic backups (task 0246)

- **Your work is saved every 5 minutes.** While you work, the app saves a backup copy of the open project in a folder
  **Backups** next to it – only when something changed. Your project itself stays as it is (its name, the "not saved"
  mark and Ctrl+Z). The Fresing tab says "Backup saved 14:35". A project you never saved gets its backups in
  Documents\Fresing Render\Backups\Unsaved projects.
- **The last 5 and one a day for 7 days** are kept; older backups are deleted (only files with the backup name pattern
  of that project – nothing else).
- **Fresing > Restore a backup…** lists them with time and size. **Restore** first keeps your work as it is now as a
  backup too, then opens the chosen one in the project's place.
- **A question when you open a project** whose backup is newer than the saved file (Blender or the PC stopped before
  you saved): Open the backup, or keep the saved project. At the start, unsaved work from the last 24 hours is offered
  the same way.
- No backups in the Client view, nor while a render, the render queue, a clash check, web 3D export, House bake, cable
  re-bake, import or the animation runs (tried again half a minute later). A colleague's backups of a shared project
  are never offered to you. Settings: Edit > Preferences > Add-ons > Fresing Render > **Automatic backups** (on/off,
  every 1–60 min, keep the last 1–50, one a day for 0–60 days).
- Measured on the 4-core test machine: one backup of the demo project (246 MB) takes 1.3 s; a small project 0.02 s.


## 0.2.186 – 21 Nov 2026 – A mesh model update keeps the work on a moved group whose part changed (task 0237)

- **Updating a glTF, OBJ or FBX model no longer loses work** when a group without a name in the file ("Node 4") was
  moved in the new revision **and** one of its parts changed (for example 20 mm wider). The Hide step, the eye in
  2 Structure and the joints on that group and its parts stay. Before, the update said "6 parts kept" but the Hide
  step and the eye were gone – or, when the parts had no names either, "4 kept, 2 new, 2 missing" and the joint was
  deleted.
- Parts without a name in a moved group are now found by their shape and the move they share (also when the whole
  group of 3,000 parts moved: before, all 3,000 came back as new). A part that changed shape keeps its work, and so
  does a part that only moved to another place inside the group.
- The update report says what happened: "Node 4 moved 100 mm; 1 part changed – its work is kept".

## 0.2.185 – 20 Nov 2026 – The tool-change person stands the same way wherever the machine is (task 0239)

The person who changes the tools now stands at the same spot in front of the machine wherever you place or turn the machine, with a little more room, so their hands no longer go into the cabinet.

## 0.2.184 – 20 Nov 2026 – A quiet window (task 0241)

- **Only what you need to look at your model.** The 3D view's header now has the **View** menu, the shading buttons
  (Solid, Material, Live preview), overlays, X-ray and **Make**. Blender's **Object Mode**, **Select**, **Add** and
  **Object** menus and its modelling settings are gone (465 px of the header freed), the tool row under the header is
  off, and the top bar no longer shows **Scene** and **View Layer**.
- **The start-up screen is the app's own:** New project, Open…, Recover Last Session, your recent projects, Take the
  test tour, Demo project, User guide – no Blender templates or web links.
- **File > New** (and **Ctrl+N**) gives only **New project**, which starts like the app does: millimetres, Cycles and
  the app's layout. (Blender's General template opened in metres with another render engine.)
- **Fresing > Show all of Blender** brings all of Blender's menus, tools and tabs back in one click (workspace **Full
  access**; nothing in the project changes). **Back to the Fresing window** hides them again and returns to the
  workspace you were in. Picking **Full access** in the Workspace list does the same. Greyed in the Client view.
- In Blender's Edit Mode (or another mode) the header stays Blender's own, so the way back to Object Mode is always
  there.

## 0.2.183 – 20 Nov 2026 – The web-page checks no longer fail at random (task 0242)

- **PC check, web 3D model lines:** "Web 3D model: smaller file" and "Web 3D model under the sea" no longer fail now
  and then with "the page gave no places of its parts" or "the page does not show the seabed". The browser without a
  window that the check uses ran ahead of the page; the page now keeps it waiting until its first picture is drawn.
  Should a page still not be ready, the check opens it once more with more time and says so in its line.
- **Windows:** making `Fresing Render.exe` again right after it was removed (for example when Smart App Control is
  switched off again) no longer fails when Windows still holds the old file for a moment – the app waits up to 3 s.
## 0.2.182 – 20 Nov 2026 – Hose, cable and drag chain kinds, colours and sizes (task 0243)

- **Pick a kind, a colour and a size.** Every hose, cable and drag chain – drawn or read from CAD – has **Kind**,
  **Colour** and **Size** under its list (4 Motion > Hoses and drag chains, and Cables and paths). Hoses: hydraulic,
  steel-braided, pneumatic tube, protective sleeve. Cables: machine cable, power cable, offshore power cable, wire rope.
- **Sizes set the numbers at once**: the diameter and the smallest bend (a chain: width, height, link length, bend
  radius). Hydraulic hoses follow EN 853 2SN (DN 6 … DN 51), wire ropes 6 … 64 mm with a sheave at least 20 × the rope.
  Type a number yourself and the size says **Custom**.
- **New looks**: black rubber with a printed line, a woven steel braid, matte PU tubes in seven colours (one see-through),
  a spiral sleeve with the hose showing in its gaps, galvanised wire rope. One look per kind and colour, shared.
- **Drag chain types**: open, closed (lids top and bottom), half-open, steel – for the chains the app draws.
- **Drawn ones start ready**: Draw hose gives a hydraulic hose, Draw cable a machine cable, Draw drag chain an open
  chain, Draw cable route a wire rope – each in the standard size nearest what you clicked.
- Your projects open as before: their hoses and cables keep their look ("As in the CAD file") and their numbers.

## 0.2.181 – 20 Nov 2026 – Usage and start fixes (task 0236)

- **No question about what is new to you.** After an update the app no longer asks "You haven't used Equipment
  recently. Hide it?" for a panel What's new has just listed; it waits 10 app starts.
- **What's new leads with what you see first** (workspaces, the Client view, folded sections, the Fresing menu), says "N
  new, M better" and has a second short list, **Better since …**, for functions that got visibly better.
- **A profile's hidden panels can be undone.** Export profile keeps your hides apart from the workspace; an imported
  profile's hides join yours, and **Back to the workspace as it came** shows them again.
- A panel you hid shows again when the project starts using it (after Build, undo or a model update), not only at the
  next start.
- A damaged start file (wrong numbers or versions) is repaired instead of stopping What's new and the welcome.
- The favourites bar shows whole labels at the normal side-panel width, and the question about an unused panel stands
  apart from the buttons above it.

## 0.2.180 – 20 Nov 2026 – Draw hoses, cables and drag chains by clicking (task 0240)

- **Draw hose / Draw cable** (4 Motion > Hoses and drag chains): for the hoses and cables your CAD model does not have.
  Click the fitting at end A, any clips the hose runs through, the fitting at end B, then press Enter. The face under
  the mouse lights up with the line the hose will take. The hose gets a sensible length – long enough for the travel of
  the joints that move its ends, when they have limits – and follows the motion like a hose read from CAD, also
  through its clips.
- **Draw drag chain**: click the bracket of the fixed end, then the bracket on the part that moves. The app draws a
  chain of links that rolls with the axis; its bend radius, links, width and height follow from the brackets and the
  travel and can be changed. **Flip bend** puts the bend on the other side.
- **Draw cable route** (4 Motion > Cables and paths): click where the cable starts (a drum, or a point on a part), each
  sheave, roller or chute in order (the same one again: the other side), then where it ends (or Enter for a free
  end). It becomes a normal cable: it runs, turns its sheaves, rollers and drum, and pays out like a cable read from
  CAD.
- **Replaces CAD part**: a drawn hose, chain or cable can replace a simplified CAD part – it is then hidden in the
  view, in renders, in the clash check and in the web 3D model, and shows again when you remove the drawn one. Click a
  part named like a hose or a chain and the panel offers to draw one in its place.
- While clicking: Backspace (or Ctrl+Z) takes the last click back, Esc stops. Drawn items stay through a model
  update, save and open, undo, Build and the render queue. New test tour stops (set "Hoses, a chain and a cable
  drawn by clicking") and a PC check line `motion.drawn`.

## 0.2.179 – 20 Nov 2026 – A bigger, calmer window: Blender's Outliner and Properties hidden, a solid side panel (task 0221)

- **The 3D view reaches the right edge of the window.** Blender's Outliner (its list of objects, top right) and its
  Properties editor (below it) are hidden in every project – a new one, the test tour, the demo and your own, also one
  saved with them. Fresing Render does not need them: the Fresing tab has the parts and every setting the app uses.
- **Fresing > Show Blender's editors** brings both back at the right of the 3D view, Outliner on top, at Blender's
  usual width; the same entry then says **Hide Blender's editors**. Your choice is kept for every project and after a
  restart.
- **Client view:** they are always hidden there and the entry is greyed; Full access brings back what you chose.
- **The side panel is solid**: the 3D view no longer shows through it, so its texts and boxes stay readable on a light
  background. (Blender's preference Region Overlap is switched off once; turn it on again in Edit > Preferences >
  Interface if you prefer it, the app keeps that.)
- PC check: a new line "Blender's Outliner and Properties hidden …".

## 0.2.178 – 20 Nov 2026 – Demo kits: a demo project from a zip (task 0228)

- **Help > Make demo project…** now shows a list: the app's own demo, then every **demo kit** you added. A demo kit
  is a demo project someone made for the app – its own model and animation – in one .zip file.
- **Add a demo kit…** under the list: pick the zip. The app checks it and keeps a copy; pick it in the list and
  **Make it** – it is made in the background like the app's own demo and goes next to it
  (Documents\Fresing Render\Demo\Kits). **Help > Open <kit name>** opens it. **Remove** takes a kit off the list
  (a demo already made from it stays).
- A kit says which app versions it was made for; after an update outside them the app tells you to download the kit's
  newer version.
- A demo kit is Python code that runs in the app: add only kits you made yourself. In the Client view Add and Remove
  are switched off.
- The PC check has a new line, "Demo kits", that adds a small made-up test kit, makes its demo and removes it again.
## 0.2.177 – 20 Nov 2026 – The tracks test model's tensioner tilts; checks on the public test models (task 0229)

- The tensioner test model (test tour "Tensioner tracks and a belt") now stands on a hinge: a cylinder under its deck
  tilts the whole tensioner 6° and back while the cable runs. The tracks, their pads and the cable go with it.
- Fixed in that tour stop: the top track jumped 150 mm down in one frame at 4 s instead of coming down slowly.
- New checks on the public test models for what only the cable-lay demo proved so far: a carousel's partly
  paid-out top layer, a Lebus drum's climbs, a load lowered past a part with the clash check, the 38 kg/m sea cable
  and its Lay data label, a wrap set by hand on a turning sheave through a model update, 400 joints at once, and the
  clash check with 200 turning rollers and big rotors. Nothing changes in the app for you apart from the tour stop.
## 0.2.176 – 20 Nov 2026 – Lifting test tour: a real yard, real-size loads, the load always in view (task 0231)
The three Lifting stops of the test tour now look like a real lift: a quayside yard with an IBC on its pallet, a 6 t
pump skid and a 20 ft container (invented, real sizes), and the AT-40 standing on four timber crane mats. The skid is
the load; its CoG sits off the middle because the pump and motor are on one side. Every stop now checks that the load's
CoG is in the picture and that nothing – not even the crane's own carrier – hides it from the camera. The "crane made
from numbers" stop shows that crane by itself with its boom out; "Set up a crane" stands on the same ground. New test
model: test_loads.

## 0.2.175 – 20 Nov 2026 – Web 3D page: measure to edges, numbers never on top of each other (task 0219)

- **Measure to an edge** on the web 3D page: move the pointer close to an edge of a part – it lights up as an orange
  line – and click it. A straight edge gives its length, a round edge (a hole's rim, where a rounding meets a flat
  face) its diameter. Two edges: the distance between them (or the shortest distance and the angle); an edge and a
  flat face: face to edge; a round edge measures from its centre – to another hole's centre (with the distance
  across and along the axes), to an axis, an edge or a face.
- **The numbers never cover each other**: when the distance and its X / Y / Z numbers would lie on top of each other,
  they move apart and a short line points to where each belongs.
- The edges come from the export's faces (no change to the import); a page gets about a tenth bigger (measured: the
  test crane's page +0.7 %, the demo vessel's +12 %). Export again to get edges on an older page.

## 0.2.174 – 20 Nov 2026 – The Client view keeps parts safe from X and Delete (task 0227)

- **Client view:** Ctrl+Z no longer takes the project out of the Client view. Before, Ctrl+Z right after picking the
  Client view undid the pick itself: the lock went off, the part you had selected before was selected again, and X /
  Delete deleted it. Undo of earlier work still happens; only the Workspace switcher leaves the Client view.
- In the Client view a part that somehow became clickable or selected is locked and deselected again at once.
- X and Delete are also blocked with Shift (Blender's "Delete globally"); Tab still does nothing. In Full access they
  work as before.

## 0.2.173 – 19 Nov 2026 – A house from House Planner by itself (task 0217)

- A house sent from House Planner now **arrives by itself**: no Save, no Import, no sending the bake back by hand. The
  two apps hand files to each other through a plain folder on your PC, `C:\Users\<you>\Toolbox` (made by the
  installer and at the app's start; nothing goes over the internet).
- When a house arrives, **5 Scene & Render > House from House Planner** (or the card at the top of the Fresing tab when
  no model is open) shows "From House Planner: <house>" with **Bake now** and **Not now**. Bake now puts the house in
  a scene of its own – your project does not change –, bakes it with its own settings (progress and Cancel in the
  panel), sends the bake back to House Planner and removes that scene again. The panel then says **Sent back to House
  Planner**.
- While the app is busy (another bake, a web export, a clash check, the render queue, an import) the house waits and
  House Planner is told so. Cancel in House Planner stops the bake. A file that is not what it says (wrong kind, wrong
  size, a strange name) is refused with a reason and never opened.
- Uninstall removes only the app's own part of the Toolbox folder.
- Test tour: new stop "A house arrives by itself"; PC check: new line "A house from House Planner by itself".

## 0.2.172 – 19 Nov 2026 – Test tour stop 22: the four-bar moves too (task 0225)

In the test tour, stop 22 "Mechanisms" now moves all three mechanisms of the test model: the scissor lift rises, the four-bar's crank turns and swings its rocker, and the slider-crank turns once. Before, the middle one (the four-bar) was never made and stood still.
## 0.2.171 – 19 Nov 2026 – Every cut looks cut, every cutting move cuts (task 0223)

- **A painted block now shows bare metal where it is cut.** Every imported part is painted until its group gets a
  material in 3 Looks, so most blocks cut to grey paint with faint marks: plain grey, soft-looking dents. Their cut
  faces are now *Aluminium, machined* – bright, with the tool marks and sharp edges. Give the block its own metal in
  3 Looks for steel, brass or plastic; glass, wood and rubber keep their look as before.
- **Use the CNC tool and workpiece** (4 Motion > Milling, and under the workpiece in 4 Motion > CNC machine): when the
  CNC machine has its tool and workpiece but Milling has neither, the program's path ran through a block that stayed
  whole. One click lets the program cut it – the other tools of the program cut while they are in the spindle.
- **Test tour:** the CNC gantry, the double-arm tool changer and the operator now cut their blocks (a slot with an arc
  and two holes; two strips and a plunge; two strips). Every machining stop now also checks the cut: tool marks on
  every cut face, every move through the block took material away, no program running through a block nothing
  cuts – the PC check's mode Tour fails on exactly what you saw.
- **PC check:** new line *Milling: the block shows what the program does*.

## 0.2.170 – 18 Nov 2026 – Cutaway is now called Slice (task 0220)

- **3 Looks > Slice.** The section view that opens up a machine (the red cut faces, hatch lines) has a new name, the
  same word the web 3D page uses: the panel, its buttons ("Add slice"), tips, the guide and the test tour say Slice.
  New slices are named "Slice 1", "Slice 2" …; slices in older projects keep their names and work as before.
  The sea's cut-away behind the stern and the hall's cut-away are other functions and keep their names.

## 0.2.169 – 18 Nov 2026 – Slice on the web 3D page (task 0218)

- The web 3D page's **Cutaway** is now **Slice** (key C, as before; S stays the screenshot). **Add slice**, then click a
  face: a flat face slices in its own plane, a round face (shaft, bore) through its axis, square to your view. Or
  choose X, Y or Z. The side away from you stays, so you look into the cut; **Flip** keeps the other side.
- **Several slices at once** (up to 8), numbered and listed with **Edit**, **Hide / Show** and **Delete**. The red cut
  faces stay right where two slices meet.
- **Edit** shows the slice as a plane with handles: drag the white arrow to move it, a yellow knob to turn it about one
  of two axes, or type mm and degrees.
- The slices stay on while you measure, use Part info or Fade the rest – those click through the slices onto what is
  kept, never onto a cut-away part.
- Pages exported earlier keep their Cutaway; export again to get Slice.

## 0.2.168 – 18 Nov 2026 – Cables and the sea after changes (task 0216)
- **Undo after a water change:** a cable into the sea is worked out again for the water it now has (after water level 2 → 3 m, re-bake, Undo it lay 1 m under the seabed). The water level, the water depth and a cable's own depth count, like the sea state and the speed already did. A project saved while that re-bake ran is worked out again when it opens.
- **Model update:** a cable whose own parts (the cable, its rollers and sheaves, its drum) come back unchanged keeps its route, wraps and drum, also when other parts of the model changed; only cables within about 1 m of a change are read again (before, any change read every cable again: the demo's power cable came out 7 cm shorter and a winch warned of a 38.7° fleet angle).
- **A crane of a lifting plan beside the hull** no longer moves the sea: Fit surroundings, a sea change or a model update measure the vessel without the placed cranes (the waterline came out 6.5 m lower with a hook lowered beside the hull).
- No tension shown for a cable bend resting on the seabed (labels jumped to 5–22 kN for a few frames).
- A save while the cables are worked out again keeps the frame you were at (it reopened at frame 1).
- A drum or carousel can no longer be renamed to an empty name (two of them shared their drawing).
- The 3D view of the demo can look closer again: its near clip comes from what is drawn (0.16 m), not from the cameras' reach (0.29 m).

## 0.2.167 – 18 Nov 2026 – One shortcut only (task 0212)

- **Only "Fresing Render"** on the Desktop and in the Start menu (one entry, no folder). The self-test, the PC checks
  (quick, full, heavy), the safe start and the user guide moved into the app's **Tools** folder
  (`%LOCALAPPDATA%\FresingRender\Tools`), all with the Fresing **Fr** icon. A STEP file dropped on a PC check shortcut
  there is still tested.
- **Fresing > Tools and checks** in the app: **Run the self-test** (its report lands on the Desktop), **PC check…** and
  **Open the app folder** (opens the Tools folder).
- **Nothing to reinstall:** at the first start after **Update now** the app removes the old extra shortcuts from the
  Desktop and the Start menu and makes them in the Tools folder. Only shortcuts that start this install are touched; a
  shortcut of your own stays. Install.bat does the same, and Uninstall removes the old and the new ones.
- The PC check has a new line, "One shortcut only".
## 0.2.166 – 18 Nov 2026 – Lifting plans work with the rest of the app (task 0214)
- **A model update keeps the lifting load:** its parts, mass and centre of gravity stay (a CoG you set by hand stays where you put it). Parts that are gone in the new revision are named in the update's report. Before, the load lost every part.
- **Build animation keeps the crane where the plan put it** (Hook to here, a Pose button, Above the load) – before, a second Build put the crane back.
- A placed crane's model is not offered for **Update to new revision** any more (Remove it and place it again). A crane whose model you deleted shows "its model is gone" and **Remove** takes its joints, poses and cables out too.
- **On a moving deck** (vessel motion on): Place and Move put the crane where you click (it sat 0.34 m in the deck), and a **Box** load rides with the deck.
- A crane's pose used from 4 Motion > Poses or in a Go to pose step no longer moves hand-moved sub-assemblies of other models back.
- A renamed crane joint, or a crane made again with another hook block, is named: Hook to here stops and says what to do instead of putting the hook metres off.
- Hook to here past the chart's longest radius warns "no crane use"; the hook height is said from the crane's base.
- The CoG symbol shows only where the Lifting plan shows (not in the Client view or a camera's view).
- **The built-in cranes** (SAMPLE) made again: outrigger and stabiliser beams no longer run through the chassis or a tyre, a knuckle crane's first extension and main cylinder and a crawler's jib foot no longer run into other parts – a crane's own pose animation has no clash rows.

## 0.2.165 – 18 Nov 2026 – Make > 3D page has its Export button again (task 0215)
- **Make > 3D page** shows all its settings (Surroundings, Light, On the page) and the **Export…** button again; since 0.2.152 it stopped after "Include animation".
- The Web 3D panel answers a click, a selection or a frame change faster (the marine-looks estimate no longer reads every part again).
- A sea cable with its own depth, on a page without vessel motion, now lies on its own bottom as in the app (it was up to 0.65 m off).
## 0.2.164 – 18 Nov 2026 – The Client view stays locked (task 0213)
- **Client view:** Blender's list of objects (the Outliner) can no longer be brought back while the project is locked – not from an area's editor menu, Shift+F9, a new window, another Blender workspace or Ctrl+Space. Before, the whole model could be selected and deleted there.
- Ctrl+Z right after an import no longer frees the camera and the floor in the Client view.
- **New camera view**, **Save scene** and **Every paint scheme** now work in the Client view (they were shown greyed out).
- Ctrl+Z of something else no longer throws the Set-up window back to another step.
- A test-tour or demo project made by an older version opens with every function and unlocked, also when your default workspace is the Client view.
## 0.2.163 – 18 Nov 2026 – Faster click and first hover on big models (task 0210)
- Clicking a part in "Subassembly" pick mode no longer rebuilds the part tree each time, and the first mouse move in an axis picker (Add joint, Set axis, cylinders) is as quick as the later ones. Nothing looks different.
## 0.2.162 – 18 Nov 2026 – About Fresing Render and the licence files (task 0206)

- **Fresing > About Fresing Render…** (also in the **Help** menu): the version, the Blender it runs on, © 2026 Fresing and
  the licence in one plain line (free software, GPL-3.0-or-later, no warranty). Buttons: **Licence**, **Third-party
  licences**, **Using it in a company** and **Licence texts folder**. It works offline: every file is inside your install.
- **The licence files are in every install**, also after an update: Fresing Render's own licence (GPL), the third-party
  notices, the page for a company's IT or legal reader, and the licence texts of the libraries inside the app
  (OpenCascade, FreeImage, LibRaw, OpenEXR, FreeType, libpng and more – 25 texts, each with where it comes from). The
  installer zip carries them at its top, the installer copies them next to the app and prints one line about the licence
  (no "I agree": the GPL asks for none). Blender's own licence folder stays as it came; the installer checks it is there.
- **Blender's own extension repository no longer syncs at start.** The installer sets it off, and an older install does the
  same once at its first start after this update, so at start the app contacts nothing except its own update check. If
  you want Blender's sync, turn it on again in Blender's Preferences: the app does not switch it off a second time.
- The PC check has a new line, "Licence files in this install, About Fresing Render, Blender's extension sync off".


## 0.2.161 – 18 Nov 2026 – Lifting plan: set up your own crane (task 0203)

- **Set up your own crane.** 8 Lifting plan > Equipment > **Set up a crane…** opens the Set-up window on your kind
  of crane – **mobile telescopic**, **crawler**, **knuckle-boom** or **other** – and takes you through its steps:
  slew, luff (with its cylinder), telescope sections or extensions, fly / luffing jib, hoist and hook block (the hook
  hangs plumb), outriggers or stabilisers corner by corner, counterweight, tracks, masses & CoG, the load chart,
  poses, Check, Save. Parts are typed by name or clicked; each joint's axis comes from a list of the parts' round
  faces (or a click on the model, as in 4 Motion). Everything is made with the app's own joints, cylinders, tracks and
  poses, so it shows in 4 Motion too.
- **Roles:** every crane joint now carries its role (Slew, Luff, Telescope, Jib, Knuckle, Extension, Hoist, Hook swing,
  Outrigger, Jack, Track, Travel) and knows its way round (+ raises the boom, slides out, lets the hook down).
- **Masses & CoG** per group (entered or volume x density, CoG worked out or typed, with markers); the **load chart**
  typed, pasted as CSV or read from a CSV file, refused rows named; **Check** runs every joint through its range and
  every pose (hook plumb, followers within their limits, the clash check on the crane's own motion, masses, CoG over
  the footprint, the chart) and leads to the step of each problem; **Save** writes the crane with a copy of its STEP
  into your library "Lifting equipment" – never into the built-ins – and it places in any project like a built-in.
- **Hook to here works on any crane** now: it finds the joints by their roles and solves in 3-D, not by names.
- Test tour: a new set "Set up a crane" (KB-20 rigged from its bare STEP). PC check: a new line `lifting.setup`.

## 0.2.160 – 18 Nov 2026 – Learn as you go (task 0208)

- **A panel you never use is offered for learning as well as for hiding.** The quiet question now says what the
  function does and has **Show me in the guide**, **Show me in the test tour** (it sets up the tour's stop and points at
  the button), **Add to my learning list**, **Hide it**, Not now and Don't ask again.
- **My learning list** (Fresing menu): each function with Guide, Tour and Done. It is ticked by itself when you used the
  function on 3 different days (a setting). Add to it with the question, with a right-click on any button
  (**Add to my learning list**), or with **Add the new functions to my learning list** in What's new.
- **Next to learn:** at most one quiet line per start on the What's next card – a function in the kind of work you
  do that you have not tried yet – with Learn and Not interested. All of it can be switched off in My usage, stays on your
  PC, and Clear my usage data asks whether to clear the list too.
## 0.2.159 – 18 Nov 2026 – Make a crane from numbers (task 0204)

- **Make a crane…** in 8 Lifting plan > Equipment: pick the type (mobile telescopic, crawler, knuckle-boom), start
  from the nearest built-in class and change only the numbers you care about – boom sections and lengths, outrigger
  spreads, counterweight steps, axles, track gauge and links, hoist and hook, masses. The dialog says **Fits** or, in
  red, the rule your numbers break, in plain words. **Make** draws the crane in the background (2–3 s; you keep
  working, **Cancel** writes nothing) and puts it into your library folder "Lifting equipment": fully rigged, with a
  picture and a **SAMPLE** chart worked out from your numbers. Then **Place now…**.
- **Enter your chart…** reads the chart of your real crane from a CSV table into a crane of your own library; the
  SAMPLE mark comes off once the charts are your own.
- The built-in cranes are a little better: the knuckle-boom cranes' control stand no longer swings into the truck cab,
  the crawler cranes' boom foot, gantry and jib strut no longer run into the pendant bars or the upper frame while the
  boom and jib move (found by checking the cranes' own motion for clashes).

## 0.2.158 – 18 Nov 2026 – Favourites bar, My usage, hide what you never use (task 0181)

- **The app learns what you use – on your PC only, nothing is ever sent.** One small file in your settings folder
  counts how often you use each function and open each panel. **Fresing > My usage…** (also at the end of the Help
  menu) shows it: your most used functions, **where your time goes** as bars per stage (Import & structure, Looks,
  Motion & rigging, Scene & surroundings, Animation, Render & export; idle time over 2 minutes is left out) and the
  **time saved – an estimate** with how it is worked out ("about 5 s per part by hand: pick the part and give it its
  material"). **Track my usage** switches it off, **Clear my usage data** deletes it, **Show the file** shows it.
- **Favourites bar** under the Workspace row: your most used buttons (6; 5–8 in My usage). It is sorted when the app
  starts, never while you work. A click opens the function's section and points at its button. Pin a function in My
  usage so it always stays; switch the bar off there too.
- **Hide what you never use:** after 10 starts without using a panel, one quiet question at the top of the Fresing
  tab – Hide / Not now / Don't ask again. At most one per start, never about something the open project uses.
  Hiding is your own layer on top of the workspace; **Back to the workspace as it came** (in My usage, and in the
  Workspace panel when you hid something) undoes it.
- **Profiles:** **Export profile…** saves your workspace with the favourites bar and the hidden panels as one file in
  the library folder Workspaces (your counts only when you tick it); **Import profile…** uses one from a colleague.
- New test-tour stop "Favourites bar and My usage" and PC-check line `app.usage` (what a counted click costs).

## 0.2.157 – 18 Nov 2026 – A new sea state in about 2 seconds; the sea cut-away in the 3D view costs nothing (task 0202)

- **Changing the sea state, the wind or the water clarity is quicker.** The sea's water look and its waves keep what
  they are made of and only take the new numbers: on the demo vessel a new sea state is ready in 2–2.5 s instead of
  about 7 s (the hoses and cables are worked out again afterwards, as before). Pictures are exactly as before. In a
  project from an earlier version the first change still takes the old time once.
- **The open box behind the stern in the 3D view no longer slows playing.** 0.2.153 cost about 6 ms a frame on a
  Detailed sea; now it costs nothing measurable. Its edge is a straight wall along the box (no jagged spikes), and the
  hull foam and, with the ground, the seabed and its stones are open there too. Renders are made exactly as before.
## 0.2.156 – 18 Nov 2026 – Lifting plan: place a crane, the load and its CoG, Hook to here (task 0201)

- **New section 8 Lifting plan** and a new workspace **Lifting plans** (lifting plan, import, structure, looks, scene,
  animation, render queue – no CNC, milling, cables or sea). The first time you open it, one dialog shows the
  planning-aid line; click **I understand** (asked once per user).
- **Equipment – place a crane.** Pick one of the twelve built-in sample cranes (mobile AT-40 … AT-500, crawler
  CC-100 … CC-1600, knuckle-boom KB-20 … KB-200) or your own from the library folder "Lifting equipment", click
  **Place…**: the crane comes in rigged (joints, cylinders, poses, crawler tracks, the hoist rope on the hook block)
  and follows the mouse – the mouse wheel turns it, a click puts it down. Two cranes in one project keep their own
  names ("AT-40 · Slew", "AT-40 2 · Slew"). Poses move only that crane; **Move…** and **Remove**.
- **Set-up the chart is picked for:** counterweight and outrigger spread, only the values the crane's charts have; a
  value in between takes the next safer chart and says so.
- **Load:** the selected parts (or a box) with their mass – entered with its source, or volume x density as an
  estimate – and a contingency factor; the gross load is summed (rigging comes later). The **CoG marker** is worked
  out from the parts' volumes, drawn on top of everything, and can be moved by hand (then marked) or put back.
- **Hook to here:** click a point – the crane slews, luffs, telescopes (or luffs its jib, folds its knuckle) and pays
  out the hoist so the hook hangs plumb on it, with the lowest crane use. **Above the load** puts it over the CoG.
  Out of reach: it says by how much. **Hook & capacity** shows radius, hook height, boom, chart row, capacity, gross
  load and the **crane use %** in the plan's words (Within / Near / Over entered limits). Built-in cranes carry SAMPLE
  charts – marked everywhere.
- Test tour: a new set "Lifting plan" (3 stops). PC check: two new lines, `lifting.place` and `lifting.hook`.
- For the site kit: the sheet reader now lives in the app (`blender/sheet.py`); the render kit calls it.

## 0.2.155 – 18 Nov 2026 – Start here: a Fresing menu, a welcome, What's new after an update (task 0199)

- **A "Fresing" menu at the top of the window**, after Help: Take the test tour, What's new in this version, Show the
  Fresing panel, the demo project, the user guide, the PC check, Check for updates and the Welcome screen – in every
  workspace, also in the Client view. The Help menu keeps its lines.
- **A welcome for a new user:** the first starts show, at the top of the start-up screen, what the app is for and the
  test tour, with **Take the test tour**, **Later** (asks again at the next start, at most three starts) and **Don't
  show this again**.
- **What's new after an update:** the first start of a newer version shows the new and improved functions (each with
  **Show in guide**) and the new and changed test models, with a tour of **only the new and changed test models** –
  much quicker to make than the whole tour. **Cancel** keeps it in the Fresing menu until you open it. It never shows
  after going back to an older version or installing the same version again.
- **The test tour marks what is new:** after an update the Test tour panel says which test models are new or changed
  and marks new stops "– New" and changed ones "– Changed". A tour of only some models says so and offers **Make the
  whole tour**; making the tour can now be cancelled from the Fresing menu.
## 0.2.154 – 18 Nov 2026 – The tool-change operator keeps his place (task 0194)

- **The person who changes the tool always stands on the same spot.** After a model update with nothing changed he
  used to step 4 cm closer to the machine; the map of the floor he stands on now has fixed cell lines, so tiny
  rounding differences cannot move him.

## 0.2.153 – 18 Nov 2026 – The sea cut-away is open in the 3D view too (task 0196)

- **The box behind the stern is open while you work**, not only in a render. In Solid view and Material Preview the
  sea's surface no longer covers the cable, the seabed and the soil section inside the cut-away. Renders are made
  exactly as before. The open box follows its numbers when you change them.

## 0.2.152 – 18 Nov 2026 – A calm side panel: workspaces, folded sections, Make, the Set-up window (task 0062)

- **The side panel starts calm.** Every time the app starts or a project opens, sections 1 to 7 are folded; each
  title row – and now every sub-panel's – shows its state on the right ("9 groups", "2 cuts", "1920 × 1080"). Click a
  title to open it, **Ctrl+click** to keep only that one open, or use the new **tabs All · 1 … 7** to see one section
  at a time. Prefer it as you left it? Preferences > Fresing Render > **Keep sections as I left them**.
- **Workspaces: only the functions your work needs.** The new row at the top of the Fresing tab picks one: All
  functions, CNC & machining, Offshore & cable laying, Product design & R&D, Client view, Education & training, Full
  access. Open it (the small arrow) to tick single **families of functions** on or off for this project – CNC
  machine, Milling, Cables, drums & sea, Video finishing … Hiding never deletes or switches off anything; hiding a
  family the project uses asks first and names what is set up. A project from before opens with everything it uses.
- **Your own workspaces:** Save as my own… writes one file into the library folder "Workspaces"; a colleague gets it by
  copying that file. Use for new projects makes a workspace your start.
- **Client view locks the project:** editing buttons are greyed out, no part can be clicked, moved or deleted (also
  not with Blender's own keys), Blender's object list is replaced and Save As / Import / Export are off. Importing,
  surroundings, camera views, saved scenes, turntable, Render image and the queue still work. Full access undoes it.
- **Blender's own row of tabs** (Layout, Modeling, Sculpting …) is hidden, except in the workspace Full access.
- **Make: every output in one place.** Above 1 Import, and under **Make** in the header of the 3D view: Picture,
  Product video, Turntable, 3D page, Animation and Queue. Each opens that output's own settings with its Make button;
  nothing was moved or renumbered.
- **The Set-up window.** Set-up window… (in Make, in 4 Motion > CNC machine and in 4 Motion > Mechanisms) opens a small
  window you can drag anywhere, also onto a second screen: a CNC mill or a mechanism one step at a time, with Back and
  Next, while you click parts in the main window. The step is saved with the project.
- **Clearer panels.** Steps stand apart; hints are grey and only problems are red; each section has **one blue
  button** (Import STEP…, Sort parts into groups, Render image, Build & play, Start queue); the numbered how-to boxes
  are folds **How it works** that close by themselves once the project has the thing (Preferences: Keep How it works
  open); texts that were cut off with "…" fit; a sub-panel whose thing is missing (no sea, no cable) shows one line.
- **One word per action:** Remove (out of the project), Clear (a list or a result), Delete (a file in the library),
  Show in folder, Add / Use as, Back to …, Find, and **Build & play** everywhere.
- **5 Scene & Render is in the order you work:** surroundings (Weather & time, Vessel motion, Vessel at work, Props) →
  Camera → Saved scenes → Image size & render → Turntable video → Web 3D model. **Brand kit & logo, Labels and
  Watermark moved to 6 Animation**, next to Finishing, Pictures and Music.
- A **What's next** card in a new project says the next step and opens its section (× hides it; gone after the
  first render). The **test tour's Go** now opens the stop's own panel. "7 subassemblys" is "7 subassemblies".
- For the lessons that come later: what a lesson points with (a button, a folded section, a part) is built in;
  Preferences > Lesson highlight picks between two looks of each.
- **PC check:** the line "Web 3D model: smaller file" failed now and then with "the page gave no places of its
  parts (loading)" – the browser without a window was read before the page had unpacked its model. The page now
  holds the browser until it is ready; the 3D pages you open yourself are unchanged.

## 0.2.151 – 18 Nov 2026 – Lifting plans: twelve ready-rigged sample cranes (task 0191)

Nothing new to click yet: the Lifting panels come in a later update. What comes in this update are the cranes they
will use, inside the app:

- **Twelve invented cranes in size classes**, each a 3D model with its joints already made:
  - mobile telescopic cranes (all-terrain) **AT-40, AT-100, AT-250, AT-500**: slew, luff with its cylinder, a telescopic
    boom whose sections run out together, four two-stage outriggers with jacks, the hook block on the hoist rope;
  - crawler cranes with a lattice boom **CC-100, CC-300, CC-750, CC-1600** (the two big ones with a luffing jib): travel
    with tracks that really run (the shoes on the ground stand still while the crane drives), slew, luff;
  - knuckle-boom cranes on a truck **KB-20, KB-50, KB-100, KB-200**: column, main boom and knuckle with their cylinders,
    extensions, four stabilisers, a small winch.
  The hook block always hangs straight down, whatever the boom does.
- **Each crane has its masses, centres of gravity and sample load charts** (per boom length, counterweight and
  outrigger spread; crawlers also per jib; knuckle booms per outreach). Every chart is marked "SAMPLE – not for real
  lifts": the numbers are invented with a plausible shape and belong to no real crane. A chart where the empty crane
  would lean back too far (heaviest counterweight on the narrowest spread) is left out, as on real charts.
- The user guide names them under **Own lifting equipment**.

## 0.2.150 – 17 Nov 2026 – The app's window stays yours, the Fresing panel always comes back (task 0198)

- **Every project opens in the app's layout.** Your own project, the test tour, the demo and an older
  version's project all show the side panel on the Fresing tab with Blender's toolbar folded. Your own view
  of the model (camera, shading, sizes) stays as you saved it.
- **Live preview keeps your last choice** while you go through the test tour and the demo: on stays on, off
  stays off, also after a restart. A project of your own opens as you saved it.
- **A "Fresing" button at the right end of the 3D view's header** brings the side panel back when it is
  hidden or another tab is open. It shows only then. New test tour stop "Fresing panel always back".

## 0.2.149 – 17 Nov 2026 – Cables: model update keeps routes, re-bake also redoes riding cameras, seabed follows Vessel at work

- **Model update with the same file changes nothing in the cables.** A contact you took off a cable's list stays off
  (also after an update to a changed file); "From CAD cable again" still brings it back. On the demo, an update of the
  vessel with its own file followed by Build now gives exactly the saved animation – before, the A&R wire came out
  74.9 m long instead of 2.8 m ("cannot go round HANDLER TOP PULLEY"), the tipping wires got back a bend the demo had
  taken off and the lay data label showed 32.3 instead of 32.0 m.
- **The re-bake after a sea change no longer fails with "StructRNA of type Object has been removed"** (seen on the
  demo in 0.2.146). It happened when the sea, the weather or the vessel was changed again while the cables were still
  being worked out again. Now the job finishes and then runs once more for the newest setting.
- **A camera that rides on a part, flies a path or keeps a part in the middle** is worked out again with the cables
  after a change of the sea or the vessel motion (before: it kept the old sea's heave, up to 1.5 m off on the demo).
- **The seabed under a cable into the sea sails at the vessel's own speed:** 5 Scene & Render > Vessel at work
  (Ahead at the vessel speed; 0 when the vessel lies still) and its steps in a video – with Weather & time on or off.
  Before, it sailed at the Weather & time speed even when the vessel lay still, and not at all with Weather & time off.
  A new speed after a Build with such steps takes the built animation off (press Build again).
- In scripts and the render queue a sea change works the cables out in one pass (before: two or three); the window's
  job redraws between the cables.

## 0.2.148 – 17 Nov 2026 – The 3D view sees the whole scene (task 0193)

- **No more grey cut-off in the 3D view.** In the normal 3D view the far turbines, the substation and the
  sea's far waves were cut away; only camera views saw them. Now the 3D view sees as far as the scene reaches,
  also in projects made before (it is set when the project opens). A larger value you set yourself is kept.

## 0.2.147 – 17 Nov 2026 – Web 3D export of the demo 8x faster, and small page fixes (task 0189)

- **Web 3D model with marine looks is much faster.** The small demo project took 29 minutes to export, now 3.5 minutes
  (measured on the 4-core test machine: 1,754 s → 214 s), and its file went from 16 to 11 MB:
  - copies of a part with a marine look that stand at the same height and tilt (the clamps, J-tubes and boat landings
    of every turbine in the wind park) are baked once and share the pictures: 69 bakes instead of 264, the same look;
  - every bake – also the tiles and the baked light – no longer drags the whole project along (a bake of a small part
    took 2.4 s on the demo, now 0.25 s).
- **The panel's estimate is honest:** it says how many parts are baked ("69 parts baked (copies share one)") and about
  how long it takes – it counts the time per bake, not only the pixels (it said "about 34 s" for half an hour).
- **The Web 3D panel draws at once** again on big projects: its estimates are kept until something changes (it took
  30–45 ms at every redraw on the demo, now under 1 ms).
- **Cable into the sea on a page without vessel motion:** the laid cable lies on the seabed again (it dipped up to
  0.8 m into it or floated above it). With vessel motion on the page, the visitor can no longer switch the motion off
  when a cable hangs from the vessel into the sea (the cable would leave the seabed).
- **Phone held sideways:** the Measure and Cutaway panel no longer covers the saved views and the time line.
- **A page with the animation:** a part's card leaves out a label's live numbers ("Lay speed 0.0 m/min" while the cable
  was paid out); a still page shows them as before.
- Landing page: adding a 3D model no longer removes the credits of models whose pictures come later.

## 0.2.146 – 17 Nov 2026 – Cables: saving and undo around "Working the cables out again" (task 0187)

- **Saving while the cables are worked out again no longer saves a half-hidden project.** Ctrl+S or autosave during
  the job used to write the file with most parts hidden and at another frame. Now the save gets the project as it
  was before the job, Save warns that the job is running, and the render queue waits for it.
- **Undo after the cables were worked out again** no longer shows the new water level (sea state, vessel speed) with
  the cable for the old one: the app works the cables out again for what the scene has after the undo.
- **Cable tension after "let go":** once the cable lies on the seabed the panel and the labels show "–" instead of
  an enormous tension (16,802 kN).
- **Two drums can no longer share a name:** renaming a drum or carousel to a name that is taken gives it a free one
  ("Drum 2"), as cables do.
- **A web 3D export run from a script** (PC check, site pictures) no longer saves the hidden drum solids into the project.
## 0.2.145 – 17 Nov 2026 – Fast 3-axis no longer leaves a hole through the block (task 0186)

- **Milling with Fast 3-axis: no more square hole straight through the workpiece.** On some programs one small square
  of the block (about 6 × 6 mm) vanished for a few frames, all the way through, although the program never cut there.
  Where a wall met the edge of one of the fast method's squares, its two corner points were joined in the wrong order;
  that square is now built the right way.
- Should a square ever still come out broken, the app now draws it the simpler way, or as uncut block – never as a hole.

## 0.2.144 – 17 Nov 2026 – Model update keeps the work on a moved group without a name (task 0188)

- **Mesh model update (glTF, OBJ, FBX): a group without a name in the file keeps its work when it moves.** Before,
  when the new revision moved such a group ("Node 4"), its parts came in as new, its Hide step lost its target, its
  eye in 2 Structure was lost and a joint on one of its parts was deleted. Now its parts with names of their own are
  found by name wherever they went, and the group follows them: all parts kept, the steps, the eye and the joint stay.
- **The same when only that group is left in the file.** The app then makes that group the model itself; the work on
  the old group now goes to it instead of being lost.
- STEP model updates are unchanged.

## 0.2.143 – 17 Nov 2026 – Smaller web 3D files (task 0175)

- **Web 3D model: the page is less than half as big.** The demo's page went from 98 MB to 42 MB, its `.glb` from 73 to
  50 MB, with the same picture and motion:
  - the model is packed inside the page (the browser unpacks it as it opens – about half a second on the demo);
  - moving parts keep only the moments a straight blend cannot give, checked at every frame (within 0.1 mm and
    0.05°); turns are stored as 16-bit numbers, a part that never moves or never turns gets no keys for it, and a
    part that is shown and hidden only where that changes;
  - moving cables store how much they moved from one moment to the next (the cable into the sea: 17 MB → 7 MB);
  - pictures are WebP where that is smaller and as faithful as JPG; the baked light's map positions are stored
    coarser (a quarter of a light pixel at most); a shape that is in the project twice is stored once.
- Pages exported before stay as they were: export again to get the smaller page.
## 0.2.142 – 17 Nov 2026 – A carousel is read the same on every computer (task 0184)

- **Drums and carousels:** when a guide sheave touches the coil (no free cable between them), the way the cable is
  wound was read from a piece of cable with no length. On some processors that came out the wrong way round: the
  carousel then turned the other way, its arm swung to the other side, and the cable "no longer touched" the guide.
  The winding is now read from the cable's arc on the coil itself, so every PC sets the same model up the same way.
  (It made the test tour's spool stop fail now and then on GitHub's test machines.)

## 0.2.141 – 17 Nov 2026 – The demo reads like a real lay: lay data, an ROV, a lighter cable, every winch spooled (task 0173)

- **Labels with live numbers and several lines** (5 Scene & Render > Labels): type **\n** in a label's words for a new
  line. A label on a cable that hangs into the sea can show its numbers, worked out again in every frame of a video:
  {top} and {bottom} (tension in kN), {layback}, {angle}, {depth}, {speed} (m/min), {laid}, {hanging}. Example:
  "Top tension {top} kN" shows "Top tension 19.4 kN".
- **The demo project** (make it again to see it):
  - Shot 8 has a **Lay data** box on the cable – top and bottom tension, layback, departure angle, lay speed and water
    depth, as a lay supervisor watches them; the caption says "surface lay".
  - An invented **work-class ROV** hovers beside the touch-down and watches it, its lights on, its propellers turning,
    its tether to the stern following the vessel's motion. It is there while the cable is laid (shots 1–8b).
  - The two **tipping winches** at the stern now hold their wire in layers on narrow drums (fleet angle 1.7°, was
    6.5°): the drum pays out what the tipping wire takes as the D-quadrant is lowered and tipped. Every winch of the
    demo is spooled now.
  - Captions: the handler's tilt in shots 9 and 12 says "x 30" like the other time-lapses; shot 5 names the
    tensioner (15–20 t class) and the cable (Ø 200 mm, MBR 3.5 m).
- **A power cable weighs 38 kg/m in water at Ø 200 mm** when you leave the weight at 0 (was 51; real cables of that size
  weigh 22–39). With the layback typed (the usual way) the cable hangs exactly as before; only the tensions shown are
  lower (the demo: 7.3 kN at the seabed, 19.4 kN at the top, was 9.8 and 26.1).
- **Build animation:** a cable whose speed follows a winch that keeps its wire tight – or that lies on a part such a
  winch moves – now moves at the first Build (before, only after a second one), without a second pass through the
  frames.
## 0.2.140 – 17 Nov 2026 – The web 3D page on a phone (task 0179)

- **Saved views as one control.** On a phone held upright the page's saved views are one control above the play bar:
  **‹ name ›** – the arrows step to the previous or next view, a tap on the name opens a list of all views from the
  bottom (closes on a pick, a tap outside or the phone's Back). On a PC, a tablet and a phone held sideways they are
  one row that never wraps: it scrolls sideways, and **All views** opens the same list. No more wall of buttons over
  the model.
- **Views by their camera's name.** New setting **View names** in 5 Scene & Render > Web 3D model: **Camera names**
  (the default – "Shot 3: carousel and arch") or **Numbered** (View 1, View 2 … when the names should stay private).
  Hide part names no longer turns the views into numbers. The panel shows the names the page will get. Export again
  to give an older page the names.
- **Nothing on top of anything.** One stack at the bottom (views, play bar, "Made with"), the button columns under the
  title, all clear of a notch and the Android gesture bar or iPhone home bar. The note "Quality Phone: lowered to keep
  it smooth" is a short message for a few seconds (the level stays in the settings).
- **The model where you can see it.** The page frames the machine in the space the controls leave free, also after
  turning the phone, and each saved view in the middle of that space.
- **Easier on a phone:** the title on one line (the whole title in the help); "Drag to turn …" only on the first visit;
  a long press on a button shows its name; the help lists every button with its icon; the rarer buttons (Screenshot,
  Copy link, Clean look) under **More tools** (⋯); Back closes an open menu instead of leaving the page; the settings
  have a close button.
- The landing page's two 3D models were made again with the new page.

## 0.2.139 – 17 Nov 2026 – Drums and carousels full of real cable (task 0174)

- **Every layer is cable now.** A drum or carousel (4 Motion > Drums and carousels) no longer shows a grey sleeve or
  ring under its top layer: the whole coil is one cable, from where it is fixed at the core or the flange, layer on
  layer up to where it leaves – on a drum with its climbs at the flanges and the Lebus crossovers on every layer. Its
  look (wire rope, power cable, served cable) runs on from layer to layer.
- **Wind it fully out and fully in.** Pay the cable all out and the layers come off one by one down to the bare drum
  or core; haul it all in and they go on again until the drum or carousel is full – live and in a built animation.
  It costs little: only the layer being paid out is worked out again at each frame.
- **More winches of the demo have their wire on the drum:** handling winch 2 (as winch 1), and the deck crane got a
  hoist drum at its boom's foot with its wire over a sheave at the boom head down to the hook block. Make the demo
  project again to see them. (The two tipping winches at the stern follow in a later version.)
- Projects made with an older version show the full layers as cable when opened.
- The web 3D model keeps showing the full layers of a coil as one solid under the moving top layer (the whole coil as
  cable would make the page far too big).

## 0.2.138 – 17 Nov 2026 – The demo's quadrant on the seabed, sheaves that stand still, a swivel to try (task 0172)

- **Shot 11 of the demo:** as the D-quadrant tips flat and is set down on the seabed, the cable stays in its gutter to
  the far end – the end that points the way the cable lies – and bends down from there onto the seabed. Before, it
  slid round to the middle of the gutter and back, kinked by up to 60° and jumped metres between two frames.
- **A chute or quadrant lying flat** (any project): the cable leaves it at the end that points the way it lies on the
  seabed; lowered close to the seabed, the bend after it turns only as far as fits and the cable lies on the seabed
  from there – no kink at the gutter, never into the seabed.
- **Sheaves the cable has left stand still**, as rollers already did: a sheave that turns with the cable's speed
  turns only while the drawn cable touches it (lifted off, run past or out of reach: it stands still for those frames).
- **Make demo project is about a minute faster:** the depth the D is set down to is right with one Build (it read the
  vessel's heave at the wrong frame rate and needed a second Build to correct it).
- **New in the test tour and the PC check: "Sheave turns to follow its wire"** – a deck davit slews while its wire runs
  from a fairlead on the deck over a sheave on a swivel head; the head turns so the wire always runs straight into the
  groove.

## 0.2.137 – 17 Nov 2026 – Task Manager says "Fresing Render" (task 0178)

- **Task Manager now shows the app as "Fresing Render"**, with its Fr icon, not as "Blender" – also for renders the
  render queue runs in the background. The app's shortcuts start **Fresing Render.exe**: Blender's own program under
  the app's name and icon, made next to it by the installer (or by the app at its first start after **Update now**)
  and checked once before it is used. No black console window opens with it.
- **New in the Start menu: Fresing Render - safe start.** It starts the app with Blender's own program. Use it only if
  Fresing Render does not start from its usual shortcut (for example when a virus scanner removed the copy).
- While Windows 11's *Smart App Control* is on, the app keeps using Blender's own program (that setting blocks
  programs without a signature), and Task Manager still says "Blender".


## 0.2.136 – 17 Nov 2026 – The app icon says "Fr" (task 0169)

- **The app icon is now "Fr" for Fresing Render:** the white F with its green swoosh and an r beside it, taken from
  the Fresing word mark, on the same dark rounded square. It shows on the Desktop, in the Start menu, on the window
  and in the taskbar, and stays sharp at the smallest sizes.
- Nothing to do after **Update now**: the app swaps the icon file at its first start and tells Windows to redraw the
  shortcuts. If a shortcut or a pinned taskbar icon still shows the plain F, press F5 on the Desktop, or unpin and pin
  the taskbar icon again.

## 0.2.135 – 17 Nov 2026 – The Fresing logo as a watermark (task 0176)

- **The Fresing logo as a watermark:** in 5 Scene & Render > Watermark you can now pick **Fresing logo** (or **Brand kit
  logo**, the logo of your own kit) instead of words. **Place** it in the **Centre**, **Tiled** across the whole picture
  (turned like the words) or small in a **corner**, and choose its colour: **Colour**, **White** (for dark pictures) or
  **Dark** (for light pictures). Size and See-through work as before. It goes on stills, videos, the render queue and the
  product video, the same as the words. Old projects keep their DRAFT or CONFIDENTIAL words.
- **A ready-made "Fresing" brand kit** comes with the app: Fresing's logo (sharp in 4K) and colours. It is always in the
  list of kits, cannot be changed or deleted, and you can load it, give it another name and save a copy of your own.

## 0.2.134 – 16 Nov 2026 – Fast 3-axis: fewer faces, truer flanks (task 0167)

- **Long milling programs (Fast 3-axis) give lighter, cleaner surfaces.** Faces along the passes, walls and steps are
  now long strips instead of many small triangles: the test finishing program (40,000 points) has 24,700 faces
  instead of 29,500, the app's own toolpath test model 117,000 instead of 182,000 (the exact cut: 96,000).
- **Closer to the exact cut where it was furthest off:** the rounded strip at the start of a flat bit's ramp 0.055 mm
  (was 0.14), the fillet of a corner-radius mill 0.075 mm (was 0.11), and a thin rib left between two cuts is kept
  (was up to 0.29 mm off). A wall that stands exactly on the map's grid is no longer off.
- **Finish at the CAD part:** where a finishing pass ran right on the finished part the surface now lies a hair
  (0.0125 mm) over it instead of mixing with it into thousands of slivers.
- What you might notice: scrubbing through such a program is a little slower per frame (about 5–10 ms on the test
  machine).

## 0.2.133 – 16 Nov 2026 – The Fresing icon and start-up screen (task 0169)

- **Fresing Render now looks like Fresing everywhere in Windows:** the Desktop shortcut, the Start menu, the window and
  the taskbar while the app runs show the green and white Fresing **F** instead of Blender's logo. The taskbar groups
  the app under it, and **Pin to taskbar** keeps Fresing Render with its own icon.
- **Already installed?** Nothing to do: at the first start after **Update now** the app puts the new icon on its
  shortcuts (Desktop, Start menu and a pinned taskbar icon). If a pinned icon still shows Blender's logo, unpin it and
  pin it again (Windows keeps its old picture for a while).
- **New start-up screen** with the Fresing logo; its accent line is now Fresing Green instead of amber.
## 0.2.132 – 16 Nov 2026 – A person changes the tool (task 0156)

- **A whole person can do a manual tool change.** In the program step (6 Animation > Run G-code program > Lines, tool
  changes …) **Changed by** is now Nobody, Hand or **Person**. With Person the operator walks up to the machine before
  the first change (round everything that stands in the way – never through the machine or a table), opens the
  door by its handle, presses the drawbar's release button with the left hand, takes the old tool out of the spindle
  by its holder, lays it on small cradles on a tool trolley beside it, takes the new tool, pushes it in, closes the
  door, and walks away after the last change. Feet planted, no sliding (the walking of task 0157).
- The pause at M6 grows to what the person needs (about 6 s, plus the door); the step's Details say how long each
  change takes.
- Settings in 4 Motion > CNC machine > Tool changes > **Person at the machine**: height, clothes, helmet, the
  **door's joint** and how far it opens, the release button, **Show the spots** (move where the operator stands and
  where it comes from), **Show the operator** (saved with a scene: hide it for one shot). The trolley stands on the
  operator's right (the hand that carries the tools).
- The clash check knows the operator (its body along its way); the arms reach into the machine only through the
  door's opening.
- **The gloved hand looks real now:** fingers with joints and knuckles, a thumb, a gauntlet cuff, a nitrile coating;
  the fingers are open as it reaches in and close round the holder.
- New test model: the test mill on a cabinet with an enclosure, a sliding door and a release button (test tour stop
  "A person changes the tool", PC check line "A person changes the tool").

## 0.2.131 – 16 Nov 2026 – Web 3D page: part info, measure, cutaway, fade the rest (task 0135)

- **Four part tools on the left of the web page** (on PC and phone):
  - **Part info** (I): click a part – a card says what it is: its label's text, else its name. With **Hide part
    names** the card shows the part's material group, never a part name. Below it: Flat face or Round face Ø … mm.
  - **Measure** (D): click two faces. Two flat faces – the **distance between the planes** (parallel within 1°) or
    the **angle** between them; one round face (hole, shaft, bore) – its **diameter**; two round faces – **centre to
    centre**; a flat and a round face – **face to centre**. **Points** measures straight between two clicked points.
    **X / Y / Z parts** (X) shows the measurement's three parts as red, green and blue arrows, each with its number.
  - **Cutaway** (C): a plane across X, Y or Z moved by a slider, **Flip** for the other side, the cut faces in the
    app's red cap colour. Only the machine is cut, not the sea; the cut moves with the vessel.
  - **Fade the rest** (T): click a part – it stays solid, the rest goes see-through; empty space or Esc brings it back.
  Phone: tap = click, a long press shows a part's card. With the mouse the part (or face) under the pointer lights up.
- The page measures on the **exact CAD faces**: the export now puts each part's flat and round faces into the file
  (new tick **Faces for measuring**, on by default; about a tenth more file – test crane +17 KB, demo vessel +356 KB
  on 4.4 MB). A hole on the same axis as a bigger round face keeps its own diameter.
- Page fixes (bug hunt 0147): a damaged remembered setting no longer stops the page; a browser drawing without the
  graphics card no longer writes "off=shadows" into a copied link; on a phone the keys help is a sheet from the
  bottom (it covered the buttons), the buttons fit one column when the phone is held sideways, the hint speaks of
  fingers, not keys; the help says "1" with one saved view; a screenshot of a page whose title has letters like "å"
  or "–" now saves as a .png.

## 0.2.130 – 16 Nov 2026 – Demo: a wind park round the cable-lay vessel (task 0166)

- **The demo project now works inside an offshore wind park:** nine turbines on monopiles in three rows (1.2 km apart
  along a row, 1.5 km between the rows) and an offshore substation between the rows. The turbines are invented, sized
  from the IEA 15 MW reference turbine's public numbers (240 m rotor, 150 m hub height), with their platforms, boat
  landings, J-tubes and scour rock; the substation has a jacket, three decks, a helideck, a crane and J-tubes.
- **The park stands on the seabed:** it moves aft with the seabed as the cable is laid and never heaves or rolls with
  the vessel. The cable's first end comes up the J-tube of turbine WTG 05 and runs over its scour rock down to the
  seabed; shots 9–12 lay the second end down beside turbine WTG 06.
- **The rotors turn** (clockwise seen from the front, all facing one wind, each at its own phase).
- **Three new shots:** beside turbine WTG 05 (its boat landing and J-tube, the vessel laying away from it), the park
  from above (the vessel laying on through the rows), and the park at night: red aviation lights on the nacelles and
  yellow marine lights on the platforms flash together, the substation's floodlights burn.
- Making the demo takes about two minutes longer; the animation is about 26 s longer.

## 0.2.129 – 16 Nov 2026 – Web 3D page: under the sea (task 0143)

- **The web page shows what lies under the water**, as the app does, when the project is on the **Open sea** and
  Surroundings on the page is **As in the project**: the seabed with its sand and ripples, the **cut-away behind the
  stern** (the same box, placed by the cable or by your numbers, with its bright top line and walls darkening with
  depth), the cable hanging down to its touch-down, and the **ground in the cut-away** (soil layers, a pile down to its
  toe). What lies behind the box's walls fades into the water's colour by the project's **Water clarity** – the app's
  own formula. With a cable into the sea the seabed drifts aft while the cable pays out.
- **The camera can go under the water** on the page: the water takes its colour and fades everything by the clarity,
  the surface shows from below, the seabed is the floor. No flicker when it crosses the surface.
- Two switches in the page's settings: **Under the sea** and **Camera under water**. Without a graphics card Auto
  quality switches Under the sea off at Phone when the page cannot keep up (a note says so).
- A **saved camera below the water or the floor** (an "At the seabed" view) now shows where you saved it; before, the
  page pushed it up to the surface.
- The Vessel deck and the Quayside have no seabed, as in the app; a page without the open sea is unchanged.

## 0.2.128 – 16 Nov 2026 – People walk, carry and meet (task 0157)

- **People who move:** new panel 6 Animation > **People**. **Add person** and click on the floor (or the deck), **Draw
  path** by clicking the points it walks through (numbered in the view; drag, add or delete them afterwards with
  **Edit points**), then list its **steps**: walk (stroll, walk, brisk, carry-walk or run), stop, turn to face, pick
  up, put down, wave, greet (a handshake), talk, point at, look at, idle, operate a panel. **Build & play** makes the
  animation; the **Preview** slider shows any moment without building.
- **Real steps:** the feet are put down on the floor and roll from heel to toe; the step length goes with the speed,
  so nothing slides. The person follows the floor's height and is warned about where a path runs into the machine.
- **Meetings line up:** a greeting or a talk starts when both people are there – whoever is first waits and looks at
  the other. Any step can wait for another person's step.
- **Items:** a toolbox, clipboard, tablet, hard hat, cable drum, crate, spanner or hose, carried in the right hand(s)
  and put down on whatever is in front – the floor, a table, a part's top.
- **Example: two people meet** sets up Anna walking in with a toolbox, putting it down by Ben, a handshake and a talk.
- People with steps are checked by the Clash check like parts. People keep the light version far from the camera.
## 0.2.127 – 16 Nov 2026 – Vessel at work: wake, ship waves, bow wave and thruster jets (task 0154)

- **What the vessel does shows in the water.** New panel 5 Scene & Render > **Vessel at work**: **Still**, **Ahead**
  (at the vessel speed), **Sideways** (DP: the thrusters push it to port or starboard) or **Turning** on the spot.
  - **Ahead:** a white wake behind the stern that fades and breaks up further back, the ship's waves fanning out
    behind the bow in a wedge of 19.5° each side (their spacing follows the speed), white water rolling off the bow and
    along the sides.
  - **Sideways / Turning:** white, boiling jets stream out beside the hull where each thruster pushes its water, as
    long and as white as the thrust makes them.
  - Works in Cycles and EEVEE, with Auto Run Python Scripts off and in the render queue; needs Foam ticked.
- **Thrusters:** **Find thrusters** reads the propellers from your joints (names with propeller, screw, schroef,
  Schraube) and tells azimuths (with their steer joint), tunnel thrusters and shaft propellers apart. The azimuths
  steer round at once; in a video every propeller turns as hard as it works.
- **In a video:** a new step **Vessel at work** in 6 Animation changes what the vessel does over its time – it slows,
  the wake fades, the azimuths swing round, the jets grow. Saved scenes keep the setting; Build tells you when the
  start scene would put back another one (Save into start scene).
- The vessel speed (Weather & time) now also works with Weather & time off.
- **Demo project:** the vessel sails in at 6 knots in the first two shots, then holds its place on DP.
- Test tour: new stop "Vessel at work: wake and jets"; PC check: new line "Vessel at work".

## 0.2.126 – 16 Nov 2026 – Web 3D: Marine detail Normal or Fine (task 0165)

- New choice **Marine detail** in 5 Scene & Render > Web 3D model (shown when a marine look is in use). **Normal** is
  the small page as before (the same file). **Fine** gives the marine looks four times the pixels, so the run-down
  streaks and barnacles show on a part as big as a turbine tower: on a 90 m tower 11.6 mm per pixel instead of 52 mm.
- The panel says before you export how fine it gets and what Fine costs (file size, bake time); the line under the
  button suggests Fine when a part is coarser than 10 mm per pixel. Fine is heavier on phones and bakes slower.

## 0.2.125 – 16 Nov 2026 – Cables and the sea after Build (task 0160)

- **Renaming no longer loses a drum, carousel or track.** A renamed drum or carousel joint, layer follower (level
  wind, arm), track speed joint or wheel joint, or a renamed cable, is kept everywhere it is used: after a model
  update the drum, the level wind and the pulleys turn exactly as before (they used to stand still, and a track got a
  new speed joint at 0).
- **Changing the sea after Build gives what Build gives, at any frame shown.** The cables are worked out again from
  the animation's first frame; with a late frame shown the demo's second end was up to 8 m off. The sea itself is made
  again at the first frame too (it came 0.24 m lower at the demo's last frame).
- **A changed water level after Build** works the cables out again on the new seabed (they lay 1 m under it).
- **That work is a job with progress and Cancel** (4 Motion > Cables and paths and the status bar) instead of a
  minute-long freeze. Cancel (or Esc) takes the built animation off: press Build again.
- **Build never puts the start scene's sea or weather back silently.** Its warnings name what it changed ("Vessel
  speed 6 kn → 3 kn"), and the Sea, Vessel motion and Weather & time panels show **Save into start scene** when the
  value you set differs from the start scene's.
- **Older projects:** one saved built after a Build at a late frame with 0.2.104 – 0.2.112 gets its touch-down set
  again at the first frame when it opens (Build once more); a scene appended from an older file is brought up to date
  at Build. Foam and moving waves are named too when Build puts them back.
- **No more one-frame twitch** of a let-go cable settling onto the seabed (0.8 m and back), and two Builds give the
  same shape.
## 0.2.124 – 16 Nov 2026 – Props for scale and people in detail (task 0155)

- **People:** the grey mannequin is now a person in work clothes with a face (nobody's likeness), hands with fingers,
  safety shoes and a helmet. Click a person in the view and choose under 5 Scene & Render > Props for scale:
  **Pose** (standing, walking, pointing, hands on a panel, kneeling, operator at a machine), **Height** (1.65 /
  1.75 / 1.85 m), **Clothes** (workshop overalls, orange offshore coverall with reflective bands, office clothes with a
  yellow vest), **Helmet**, **Gloves** and **Look** (another skin tone and hair). The feet stay on the floor.
- **Props in detail:** the container has ribbed walls, corner castings and door bars; the pallet carries taped boxes;
  the barrier has a bent frame and feet. Three new props: **IBC tank**, **Gas bottle rack** and **Tool trolley**. No
  brand names or logos.
- **Quick with many props:** each prop has a light version for far away. Props further than 30 m from the camera use
  it by themselves (5 Scene & Render > Props for scale > Detail, where you can also choose always detailed or always
  light).
- Projects made with an older version get the new props when you open them: same names, same places.

## 0.2.123 – 16 Nov 2026 – Served cable: the yellow lines run as a spiral (task 0164)

- **Served cable (yarn):** the two yellow marker lines now wind round the whole cable as one continuous spiral, once
  round per metre, right-hand like a normal screw thread – as on a real export cable (before: separate rings). New
  settings **Marker lines** (Spiral or Rings), **Pitch (one turn)** and **Hand** (Right or Left). Same in the
  renders, the live view, the coil on a drum or carousel and the web 3D model.
- Projects saved with 0.2.116 to 0.2.122 keep their rings; new served cables and the demo get the spiral.

## 0.2.122 – 16 Nov 2026 – House packages checked the same on Windows, site kit fixes (task 0163)

- **House packages:** a file name with a backslash or a hidden NUL character inside a House package is now refused on
  Windows too (before, Windows quietly turned `light\a.png` into `light/a.png` and accepted it). A name that is not
  UTF-8 text gets its own clear message.
- **Site render kit** (the zip on the site-kit release; not in the app): when the start window cannot open and the
  questions come in the black window, it now asks "Continue the run of … (Y/n)" – before, the next start deleted the
  finished pictures of a night's run. After you click Pause the status window keeps "Resume" (the run pauses when the
  picture being made is done), and closing it asks first. "Done at about" shows English day names.

## 0.2.121 – 16 Nov 2026 – Web 3D model: marine looks on the page, safer light bake (task 0161)

- **Marine looks on the web page.** Marine growth, run-down streaks and the worn blade edge now show on the page as
  in the app: each part with one of them is baked on its own, where it stands (before, the page showed plain paint).
  The line under Export says on how many parts and how fine ("… mm per pixel"), and when a very big part (a tower)
  is too big for the finest streaks and barnacles. These parts make the export slower and the file bigger (the test
  crane: 0.2 → 0.8 MB, 2.5 → 25 s).
- **No crash in the light bake.** An export with Soft light or Everything baked (and the House bake) keeps the
  app's live functions (cables, hoses, vessel motion …) away from its working copy, as the looks bake already did.
- **Isometric views at the right size.** A saved Isometric camera shows the same frame on the page as in the app
  (it was almost twice as wide).
- **Any camera name works.** A camera name with `<!--` or `<script` in it no longer stops the page at "Loading".

## 0.2.120 – 16 Nov 2026 – The demo vessel in detail (task 0153)

- **The demo's vessel looks like a real offshore vessel close up.** A shaped hull: a raked bow with flare and a bulbous
  bow, the deck rising towards the bow, a flat transom with a skeg, bilge keels, a rubbing strake along each side.
  A proper superstructure: three tiers with rows of windows, a bridge with wings, two funnels, a mast with two radars,
  antennas and lights, lifeboats in davits, railings. On deck: a crane parked with its boom up, bollards, fairleads,
  hatches, windlasses with their anchors in the hawse pipes. Still invented: no real vessel's design or name.
- **Propulsion you can see turning:** two azimuth thrusters at the stern (a propeller in a nozzle, each turns about
  its upright axis) and two bow tunnel thrusters. Each propeller, each thruster's steering, the radars and the crane
  (slew, luff) have their own joint in 4 Motion; in "What it can do today" the propellers and radars keep turning.
- **Paint and wear:** dark blue hull with light run-down streaks, a black boot-top band round the waterline, red
  antifouling with marine growth below the waterline, the name "DEMO LAYER" on both bows and draft marks fore and aft
  (decals), a non-slip deck, white superstructure with tinted glass, galvanised railings, orange lifeboats, bronze
  propellers; the rubbing strake and the deck fittings worn to bare steel at their edges.
- **Two new saved cameras:** "Stern thrusters" (under water) and "Hull side" (along the starboard side from ahead of
  the bow). Making the demo takes about 12 % longer.
- **Test tour:** the demo stop's check now expects the animation's real length (about 2 ½ minutes).
## 0.2.119 – 16 Nov 2026 – Assembly sequence in any order; mesh model updates keep unnamed groups (task 0162)

- **Assembly sequence steps in any order.** Take apart a small subassembly, then the whole machine, then Put together
  the small one first: it now comes home (before, it stayed apart), and the whole machine's Put together leaves it
  there. Three levels deep and interleaved orders work too; a Back to CAD step of one subassembly no longer makes a
  later Put together throw its parts out again.
- **Put together shows its parts again.** After a Take apart with At the end **Hide** or **Fade**, a Put together with
  **Stay** used to play invisible; now every part appears (or fades in) as it comes in.
- **No jump for a part that rides on another** (a gripper on a carriage) when the Put together has other settings than
  its Take apart: it starts where it waits and glides onto its way in.
- **Hiding or showing parts after Build** (the eye in 2 Structure, Hide, Show only, Show all, Show everything again,
  a visibility set, Show only these in 3 Looks) takes the built animation off: build it again, so the video shows the
  parts as you left them. Before, the built keys still showed a part you had hidden.
- **Mesh model updates:** work on a group without a name in the file ("Node 5") – a Hide or Show step, the eye, a
  sequence step, a joint on one of its parts – stays on the same parts when another group is added or removed.
- **OBJ / MTL names with å, ö, é** stay right when another line of the file is in Windows' own code page (before,
  "Plåt" became "PlÃ¥t" and the update called it renamed).

## 0.2.118 – 16 Nov 2026 – Full carousel, faster cables (task 0159)

- **The demo's carousel is full.** The coil now fills the carousel up to its rim: 23 full layers and the top layer,
  partly paid out as before – 43.5 km of cable instead of 28.8 km. The loading arch stands 1.2 m higher (room for its
  guide rollers above the fuller coil) and the carousel shot's camera looks a little higher; the other shots are as
  before. Make the demo project again (Help > Make demo project) to see it.
- **Build is faster.** Build's pass through the frames for hoses and cables now lets Blender work out only the parts
  it reads and what they hang on, not the whole model at every frame: on the demo the Build takes 48–50 s instead of
  68–72 s on the 4-core test machine (making the demo 250 → 210 s), with exactly the same shapes and keys as before.
- **Moving a cable that hangs into the sea by hand is faster:** one step of "Cable travel" on the demo 133–153 →
  87–106 ms on the test machine.
- **A drum's or carousel's rope is set up faster:** the full carousel's whole wound path 3.0 → 1.1 s.
- Playback, renders and memory cost the same with the full carousel as with the part-filled one: the full layers are
  one light solid, only the top layer is drawn as rope.

## 0.2.117 – 16 Nov 2026 – Long milling programs are worked out in seconds (task 0146)

- **Fast 3-axis** (4 Motion > Milling, under Detail; on by itself, also in older projects). A long program that
  cuts straight from above – a finishing program from CAM, or the app's own **Make a toolpath** – is now worked out
  as a height map (the lowest point the tool reached above every spot of the block) instead of one exact cut per
  move. Measured on the 4-core test machine, Detail Normal:
  - a finishing program of 40,000 points (ball Ø6, 100 × 60 mm, passes 0.3 mm apart): the whole cut in **3.5 s
    instead of 2.4 minutes**, 30,000 faces instead of 256,000; one frame further while playing 38 ms instead of
    53 ms, one frame back 72 ms instead of 235 ms;
  - a dome (3,750 moves, passes 0.5 mm apart): 1.6 s instead of 32 s, 21,000 faces instead of 62,000;
  - the toolpath test model (7,243 moves, roughing and finishing): 8 s instead of about 2 minutes – but 146,000
    faces instead of 97,000: on walls and steps the map needs more faces than the exact cut.
- **What goes into it:** programs of 3,000 moves or more, and shorter ones (from 300 moves) whose passes lie close
  together (a short, thinly spread program is quicker and lighter cut exactly); of those the moves where the tool
  points straight at the block along one of its own axes, with a flat, ball or corner-radius mill that reaches above
  the block's top.
- **What is cut exactly as before:** short programs; V-bits, chamfer mills and drills; side cuts with a T-slot cutter
  (any bit that undercuts); tilted and rotary moves (4th and 5th axis); a tool so short that it tunnels. One program
  can have both kinds: they are joined in the block. The clash check, the chips, the cut faces' look, the tool marks
  and "Finish at the CAD part" work as before.
- **Same look, not the same to the hundredth.** Walls stand upright with their outline where the tool went, rims
  are sharp, cut faces know the move that made them (tool marks). At Detail Normal (a 0.2 mm grid) surfaces and
  walls are within 0.03 mm of the exact cut. What differs: the fine ridges between two finishing passes are left
  out when lower than 0.012 mm (the face is smooth there and shows the tool marks); the steep rounded strip under
  a rim or at the foot of a wall (a ball cutting deeper than two thirds of its radius, a corner radius' fillet) can
  be 0.2 mm off and look a little streaky in a close-up; a sharp outside corner of a wall, or a rib or slot
  thinner than 0.4 mm, can be up to 0.3 mm off. All of it halves at Detail Fine. Untick **Fast 3-axis** to cut
  every move exactly.
- The line under the Milling settings says how many moves went into the height map and how fine its grid is.
- **PC check:** the new Full line "Milling: a long finishing program as a height map" cuts one program both ways
  and compares them; the new Heavy line "Milling: a long finishing program (height map)" times 40,000 points.
## 0.2.116 – 16 Nov 2026 – Served cable look: black yarn with yellow marker bands (task 0158)

- **New cable look "Served cable (yarn)"** in 4 Motion > Cables and paths > Look, next to Power cable and Steel wire
  rope: the outer layer of a large export or array cable – black yarn served almost straight round the cable (fine
  grooves 2.5 mm apart, darker and lighter strands, a slight sheen, some dust) with pairs of yellow painted marker
  bands every 1.25 m (ragged edges, paint thinner in the grooves, smudged with wear). Settings: band distance, pairs
  or single, band width and gap, band colour, paint wear; in the fold **Yarn**: yarn pitch, lay angle, yarn colour,
  wear. The bands and the yarn run along with the cable, also on its drum or carousel, in Cycles and EEVEE, and on the
  web 3D model's page.
- **The demo project's power cable now has this look** (the lay cable and the second end); Power cable is still a
  choice.
- **Fixed:** when a cable's look was changed, the coil on its drum or carousel kept the old look until it was built
  again. It now changes at once.
## 0.2.115 – 16 Nov 2026 – The sea cut-away also cuts the ground (task 0148)

- **The cut goes on into the ground.** With the cut-away on, the seabed opens inside the box and shows a soil section:
  layers from sand to clay down to 5 m under the lowest part of the machine. A pile below the seabed is seen down to
  its toe; outside the box the seabed still hides it. New setting **Show the ground in the cut-away** (5 Scene &
  Render > Surroundings): it goes on by itself when a part reaches below the seabed, and stays off in older projects.
  The panel now also has **Water depth**, **Water clarity** and **Cut-away behind the stern**.
- **Wind turbine for the site:** the 45 m of monopile in the ground is no longer hidden; the "Seabed" shot looks at it
  from inside the ground.

## 0.2.114 – 16 Nov 2026 – Cables, ropes, coils and tracks move on the web page (task 0142)

- **Web 3D model with Include animation: what the app draws moves on the page too.** The power cable, wire ropes
  (A&R, tipping, winches), the rope on drums and the coil on a carousel, hoses, track links and pads, drag-chain
  links and a CPS set riding on a cable used to stand still in their CAD shape. Now the page shows them as the app
  draws them and moves them with the animation: the coil winds down layer by layer, the cable follows the quadrant,
  the links run round their wheels (within 1–2 mm of the app on the test models).
- **The cable looks are on the page:** the power cable's yellow stripes and the steel wire rope's strands, wires and
  grease, running along the cable as it is paid out (standing still on a drum or carousel, as in the app). Also
  without Include animation, at the frame shown.
- **A CAD coil that a drum or carousel hides is left out** of the web model, as in the app.
- **Much smaller files with motion:** each moving part and cable keeps only the moments the page cannot blend in
  between (at most 1 mm off), and the motion is packed like the shapes. The demo with its animation (Texture size
  512, no baked light): 155 MB before, 46 MB now. The export takes longer on it (3.0 → 4.9 min on the 4-core test
  machine): it reads every cable and link at every frame.

## 0.2.113 – 16 Nov 2026 – Build gives the same animation at any frame (task 0138)

- **Build no longer depends on the frame shown.** Pressing Build at a late frame of the demo put the second end and
  its CPS up to 114 m off in shots 9–12 and warned "98 m more cable than the water is deep". The start scene set the
  water level again, and every cable into the sea set its touch-down again in the pose of the frame shown (where
  let go and the sailing seabed had already moved things). Now Build always starts from frame 1, the same water set
  again changes nothing, and the touch-down is always worked out at the animation's first frame. The render queue
  benefits too: a project saved at a late frame gives the right video.
- **Set the touch-down here** works at the animation's first frame (the pose shown when nothing is built).

## 0.2.112 – 16 Nov 2026 – Web 3D page becomes a player (task 0134)

- **Settings on the page** (the gear, or M): switch the sea, vessel motion, sky, haze, rain and sun shadows on and
  off; Quality Auto, Phone, Balanced or Best; how many pictures a second it draws; the graphics card's name;
  Auto-turn (starts after 8 s without a touch); a Sun / time-of-day slider (live light only). The page remembers the
  choices for the next visit; Reset forgets them.
- **Playback:** Space plays and pauses, a time line to drag to any moment (also on a phone), speed ½× 1× 2×.
- **Saved views:** one button per camera of the project; the view flies there (View 1, 2 … with part names hidden).
- **Fullscreen** (F), **Reset view** (R), **Screenshot** (S), **Copy link to this view** (L), keys help (?), and a
  **clean look** (H) that hides every control. A loading bar shows the MB.
- **Says when the browser draws without the graphics card** (a red bar with the fix: `chrome://restart`) and then
  uses its lightest settings.
- **Lighter on the PC:** a picture only when something changes, at most 60 a second, nothing in a hidden tab; a still
  machine costs the graphics card nothing. Auto quality no longer drops to Phone after you leave the page and come
  back (the hidden time counted as one slow picture), and it steps up again when there is room.
- Every exported page is now this player (Surroundings None in its light plain form); the panel's fold "On the page"
  lists what it offers.

## 0.2.111 – 16 Nov 2026 – mesh model updates keep work on the right piece (task 0139)

- **Fixed (lost work):** updating a glTF/OBJ/FBX model moved joints, looks and stickers onto the wrong piece when a
  split mesh gained or lost a piece (the piece numbers "WELDMENT 3", "Node 7" shift). Names the app made itself are
  now matched by shape and place.
- **Fixed (lost work):** a mesh model's own looks were lost at save when no part showed them (a group set to another
  look); **From file** now always brings them back. An update lets the old revision's looks go.
- **Fixed:** a change to an OBJ's material file (.mtl), a texture picture or a glTF's .bin file now arrives at the next
  import or **Update to new revision** (before, the old copy was used).
- **Faster:** updating a big mesh model (3,000 parts: 37 s → 24 s on the 4-core test machine).
- **Fixed:** a round face on a part stretched along its axis showed 3 x its diameter; the hover could draw an old
  part's outline after two updates; OBJ/MTL files from older Windows programs (å, ö, ø) keep their names and find
  their pictures; a glTF with several scenes and no default reads the first one with something in it.
## 0.2.110 – 15 Nov 2026 – cable fixes: settings kept, sea cables follow a vessel change (task 0137)

- **Swivel and Let go kept:** a sheave's **Swivel** and **Let go** frame no longer vanish after a model update, **From
  CAD cable** again, **Add contact** or a change the app had to refuse.
- **Renamed joints:** renaming a joint is carried into the cables – their speed joint, a contact's turn and swivel
  joint, and a coupling put aside at Build – so a swivel head keeps following its wire.
- **Sea cables follow a vessel change after Build:** changing the vessel motion, sea state, bow or the vessel speed
  (Weather & time) after **Build animation** works the cables into the sea out again for the new motion by themselves,
  as the hoses already did (also for the sea state, bow and preset routes, which the hoses missed before).
- **Older projects:** a let-go cable into the sea in a project saved with 0.2.109 or older, whose **Settles in** was
  never set, opens with Settles in 0 – it stays where it was let go, as it did when the project was made. Set it again
  to let it sink.
- **Smoother payout when the hang-off changes twice in quick succession** (1–2 frames apart): no overshoot.

## 0.2.109 – 15 Nov 2026 – house format 1.0.1 (task 0130)

- **House round trip follows format 1.0.1:** the app now checks its House packages against the final tag `v1.0.1`
  (a package name made of plain letters is accepted with or without the zip's UTF-8 mark; a name with accents or other
  special characters without it is refused).
- **The sun's strength in a baked house is cleaner at a low sun:** it is now measured on a surface turned straight at the
  sun instead of being worked out from an upward-facing one (which multiplied the noise at a low evening sun). The
  numbers agree with the old way within 1 % at 35°, 12° and 4.8°; by day under a full overcast the sun is written as
  zero, and "none" only where there is no separate sun (night, a 360° photo, a studio).
## 0.2.108 – 15 Nov 2026 – the demo: a CPS set from the rack onto the cable end (task 0126)

- **Demo, new shot 8b:** after the cable has gone into the sea, a **CPS set** (cable protection) slides from the rack's
  top shelf, tail first, down the orange ramp and the curved slide onto side B's roller highway, runs round the
  D-quadrant and down side A, stops before tensioner 2 and runs back until its pull head is at the D's bar end – its
  place in front of the cable end. Shot 9 then shows the cable end connected to it (time-lapse × 15; about 24 s).
- **Its pieces follow the bends:** the CPS sets of the demo are now made of pieces of at most 0.5 m (the grey tube and
  sleeve in pieces), so they lie on their way round the D and the slide within 16 mm; they rest on the roller cradles
  (higher in the V than the cable, on the rollers' raised ends), on the D's floor against its guide rollers, and run
  into nothing on the way (checked at every frame).
- **The demo vessel for it:** the slide comes onto side B at the CPS's height, the cradle under the slide's last bend is
  gone (307 joints instead of 310), the D-quadrant's gutter is 123 mm wider and its top plate 58 mm higher, the tipping
  eyes' lugs sit over the CPS's way, the rack's side guides are lower.
- **The second end no longer piles up while the D carries it aft (shot 9):** it is hauled in by the D's travel (36 m
  piled up on the seabed by the end of the travel before). While the D is lowered to the seabed (shots 10–11) the
  cable still lays down in a loop under it – the warning says so.
## 0.2.107 – 15 Nov 2026 – Assembly sequence fixes (task 0140)

- **Steps inside steps:** take a subassembly apart, then the whole machine, and put them together in the reverse order:
  no part jumps any more. Each Put together brings the parts back to where the matching Take apart found them.
- **Same order every time:** two parts that sit flush no longer swap places between Builds, the render queue and the
  product video.
- **Preview not stored:** Save pose, Save scene and Make product video while the sequence Preview is above 0 % put
  the parts back first.
- **Hidden parts stay out:** a part hidden with the eye in 2 Structure takes no part in the sequence and stays hidden
  (the step's box counts it).
- A sequence's trail line of a part a model update removed is dropped without a warning; the Preview works the plan
  out again when a part round the subassembly is hidden, shown or moved.
## 0.2.106 – 15 Nov 2026 – Export web 3D model no longer crashes; marine growth follows the sea (task 0136)

- **Fixed a crash:** *Export web 3D model* closed Blender (and lost unsaved work) when the project had a moving cable
  and the animation was not built (after Clear keys, after a product video, before the first Build). The export now
  pauses the app's live updates while it bakes the looks.
- **Fixed:** the marine growth band stays at the sea's waterline when you change the water level or switch the Vessel
  deck on.

## 0.2.105 – 15 Nov 2026 – turbine extras: rock round the pile, worn blade edges, the new test mill (task 0128)

- **New look:** *Marine paint, worn leading edge (blades)* (3 Looks, Paint): along a wind turbine blade's front edge,
  from about 60 % of its length to the tip, the paint is worn away in patches – dull grey laminate with small chips.
- **Site model (render kit):** the offshore turbine has rock scour protection round the monopile's foot, a new
  "Seabed" view under the water (seabed and cut-away of the sea), and worn blade edges on both turbines.
- **Site page:** the "Turn it yourself" test mill is the new, more detailed machine of 0.2.101.

## 0.2.104 – 15 Nov 2026 – a follower's true value, Back to CAD after a Take apart, no false clash rows (task 0132)

- **A joint that follows another shows its true value:** in 4 Motion the joint list and the joint's box show a
  follower's angle or distance worked out from the joint it follows. Right after a change it could show the value of
  one step before.
- **Back to CAD right after a Take apart plays it backwards:** the same paths, the last part out comes in first, so no
  bolt flies through a cover any more. Joints that also have to go home move after that. In every other case Back to
  CAD is as before. The step's box says when it plays a Take apart backwards.
- **No false clash rows from a Put together:** a Put together with nothing taken apart before it puts its parts out at
  once at its first frame. The clash check no longer reads that jump as a move through the other parts; real clashes
  are still found.

## 0.2.103 – 15 Nov 2026 – the quadrant at the seabed, a cable that settles, one bow (task 0125)

- **A let-go cable settles onto the seabed:** a cable into the sea that is let go above the seabed – its end, and the
  turn round a quadrant or sheave let go with it – now sinks onto the seabed and lies there (a turn round a quadrant
  lies down flat; a CPS set on the end rests on the seabed, not in it). **4 Motion > Cables and paths > Into the sea >
  Settles in** sets how long it takes (4 s; 0 = it stays where it was let go, as before).
- **A sheave on a swivel turns to its wire:** pick the swivel's rotate joint as the head sheave's **Swivel**: the head
  turns so the wire leaves the sheave in its own plane, live and at Build animation. The demo's tipping wires use it.
- **Rollers the cable has left stand still:** rollers on the end of a horn that the cable no longer reaches (it leaves
  the horn earlier into the sea) no longer turn with the cable.
- **No kink where the cable leaves a quadrant or horn into the sea:** it goes on in a smooth bend of the gutter's radius
  to the hanging part (it used to flip between two answers and kink by up to 69° while the D tilted).
- **No lost path** when the D-quadrant comes down over horn A (frames 1924–1927 of the demo): the cable hangs from the
  quadrant.
- **Fewer wrong warnings:** no "piles up 0.00 m", nothing about a wire that only comes onto its pulley later, nothing for
  frames where the cable is hidden, nothing about a cable that lies on the seabed after it was let go.
- **Winch keeps it tight:** a cable into the sea no longer jumps its payout when it leaves a horn for a quadrant (the winch
  takes the difference up over 1 s).
- **One bow:** Weather & time > Bow is now the one direction the wake, the bow spray, wind "From the bow" and the swell of
  vessel motion all use. From the hull reads it from the waterline: the demo's wind from the bow now blows from +x (its
  bow). The Vessel deck and older projects keep their look.
- **Demo:** in shot 11 the D is set down on the seabed (its lowest point 16 mm over it at the deepest heave, never in it);
  the second end is let go as the D lifts off and settles onto the seabed with its CPS; the tipping-wire heads turn to
  their wires.

## 0.2.102 – 15 Nov 2026 – the assembly sequence watches the whole model, Back to CAD (task 0129)

- **Assembly sequence – the rest of the model counts:** a part whose way out would run through a frame, a beam or a
  wall that is not in the subassembly now goes another way – along another axis of the subassembly, sideways before
  backwards – that is clear of it and of the parts still in place. Only when no way is clear does Build name the part
  and what it runs into.
- **Assembly sequence – parts that ride on another part** (a gripper block on a carriage, a block in a robot's
  gripper) now fly on their own: first, from where the joint has put them, and they stay where they flew while the
  part they rode on leaves under them.
- **Assembly sequence – Away from the centre** now stacks parts that go nearly the same way, so parts nested in each
  other no longer end up inside each other.
- **New step "Back to CAD"** (6 Animation, Add step): every joint – of the whole model or of one subassembly – goes
  back to where the CAD file has it, and moved parts back to their places, smoothly over the step. A motor goes to its
  nearest whole turn.
- **Product video:** after the saved poses a Back to CAD step brings the machine home before the take-apart. The
  close-ups use your saved cameras that show part of the machine close; without them the app picks the spots itself –
  a type plate or logo first, then the moving parts round each joint (a boom at its hinge), seen from the side that
  shows most of it. (The import's whole-machine view no longer counts as a close-up.)
- The Assembly sequence preview no longer works its plan out twice when you start dragging.

## 0.2.101 – 14 Nov 2026 – the test models look like real machines (task 0122)

- **Test models:** the small models of the test tour, the PC check and the guide pictures now look like real machines:
  chamfered frames with ribs and gussets, rails and guide blocks, motors, real hex bolts and socket screws, clamps on
  the milling tables, deck plating, bollards and handrails on the offshore models, folded sheet-metal way covers, a
  V-belt pulley with its key on the spindle unit.
- **Test crane:** a luffing hydraulic cylinder under the boom. In the test tour and the PC check it follows the boom –
  its rod slides out and its eye stays on its pin – and the boom stops where the cylinder does (about −1.5° … 37.6°).
- The guide's pictures of these models are new. Nothing in the app's functions changed.

## 0.2.100 – 14 Nov 2026 – the guide's contents list every section (task 0124)

- **User guide:** the contents on the left now list every section under its chapter (Cylinders, Light look, Make a
  product video …), so you can jump straight to the one you need. Every section has its own link now.
- **Website:** under each picture, video and 3D model a short line **How it's done:** links to the guide sections of
  the functions it shows.
- Behind the scenes: one list of every function of the app, which the automatic tests keep in step with the guide,
  the test tour and the PC check; the coming side-panel overhaul and the lessons read it. Nothing in the app itself
  changed.

## 0.2.99 – 14 Nov 2026 – mesh models: glTF, OBJ and FBX (task 0117)

- **File > Import > Mesh model (glTF, OBJ, FBX)…** (also **Import mesh model…** in 1 Import, or drag the file onto
  the view): a model you did not draw – a vessel or a truck from Sketchfab, a client's glTF – comes in like a STEP
  model, with its tree, names and colours; a part used several times (four wheels) is stored once. It is read in the
  background with the same progress bar and Esc. FBX is read by Blender's own FBX importer first (a few seconds more).
- **Units and up axis:** glTF is metres and FBX says its own; for OBJ pick the units (Auto guesses mm or m from the
  size and says what it guessed) and the up axis (Y up by default).
- **Split by loose parts:** a model that comes as one big mesh gets every separate piece as a part you can move and
  give a look (Auto: when the file has fewer than 5 meshes).
- **The look "From file":** every part shows the colour, shine and pictures its file gave it; the pictures are packed
  into the project. Pick another material for a group and it replaces the file's look as usual.
- **Round faces on a mesh:** the app finds flat and round faces on a facetted mesh, so clicking a facetted shaft,
  hole or slewing ring for a joint gives its axis through the centre, as on a STEP part (tested: within 0.5° and
  0.5 % of the radius). Hover, painted faces and stickers work the same.
- **Credit line:** the file's credit (or Sketchfab's license.txt next to it) is shown under the model's name, and the
  text block "Model credits" in the project keeps the full text.
- **Model update** of a mesh model keeps your work; a part renamed in the new file is found by its shape and place
  and named in the report.
- **Web 3D model:** a part with a picture from its file exports that picture as it is, on its own UVs.
- **Fixed:** two imports of the same new file started within a second could share one half-written folder
  (bug hunt 0118 row 14); each import now writes its own.
- **Test tour and PC check:** a stop and a line "Mesh model: joint on a ring", a line for an FBX file, and
  a Heavy line with a mesh of 1 million triangles.

**Test this (on your PC):** File > Import > Mesh model…, pick a .glb (for example one downloaded from Sketchfab, or
the test crane: Help > Make test tour project, then the tour's "Mesh model" stop). Check the parts look like in the
file, the credit line under the model's name, and that 4 Motion > Add rotate joint on a round part gives the right
axis.

## 0.2.98 – 14 Nov 2026 – render queue, long jobs and redraw fixes (task 0120)

- **Every paint scheme** for an animation now really renders each video in its own colours. When the animation
  started from a saved scene (always so for a Product video), every video came out in that scene's colours.
- A picture added with **Current view** is rendered at the frame you were on when you added it: the sea, vessel
  motion, rain and snow of that moment. Before, it showed the frame the queue happened to start at.
- While a **House bake**, a **Web 3D model** export or a **Clash check** runs (they change the project for a while),
  **Start later** waits for it and **Start queue** / **Render animation** say to start when it is done; before, the
  queue could copy and render that half-done state. Saving during one of them now warns that the file holds its temporary state.
- **Ctrl+Z** during a House bake, Web 3D export or Clash check does nothing and says "press Cancel first". Before,
  the export stopped without a word, and a House bake mixed two states of the project.
- **Build animation** says so when its start scene switches the weather off (the scene was saved before the weather
  was set): set the weather and save that scene again to keep it.
- A cut-away no longer changes the project from the render's own thread when a render starts (a kind of thing that
  crashed Blender before); the app's render buttons and the queue bring it up to date just before.
- The side panel walks the whole model less often while an animation plays (X-ray, work lights and cut-away counts
  are kept between redraws). A key of your own on the scene is kept through Build and Clear keys, and Clear keys no
  longer leaves an unused "FR Scene" action behind.

## 0.2.97 – 14 Nov 2026 – hoses with vessel motion, the Assembly sequence preview (task 0121)

- **Hoses follow a vessel-motion change after Build.** Changing the strength, sea state, heading or a still/level part
  after building left the hoses where the old motion had put them: the fittings moved, the tube ends did not. They are
  worked out again for the new motion now (in the window once the slider rests).
- **Vessel motion without Build is lighter:** a hose whose two ends move together as one body is moved along instead of
  being worked out again at every frame (test model, 4 hoses, 60 frames: 4 solves instead of 240).
- **Assembly sequence Preview is quick:** dragging the slider no longer plans the whole step at every move – on the
  demo's tensioner (260 parts) 85–90 ms per step instead of about 4 s. The box now says that moving it takes a built
  animation off.
- **A preview left on no longer becomes permanent.** A model update (or Clear keys) with the Preview above 0 % kept the
  parts half-way out for good; the preview now ends first.
- **Assembly sequence with vessel motion:** the step's keys no longer depend on the frame you press Build at (they were
  measured on the tilted vessel; up to 4 mm apart on the test model).
- **Projects with vessel motion from 0.2.65–0.2.87** get the vessel's motion worked out again once when opened, so it
  matches today's sea.

## 0.2.96 – 14 Nov 2026 – a model update keeps drums, carousels, riders and tracks (task 0119)

- **Updating one model no longer undoes the drums and carousels of the others.** Before, updating (for example) the quay
  model stopped every drum and carousel in the project: the cable went back to a plain CAD cable and the drawn rope was
  deleted, without a note.
- **A drum whose part ID changed in an update keeps working** at the next update (it was lost then: "its part is gone").
- **Things riding on a cable:** a part that is gone in the new revision is dropped and the report says so (before, the
  rider kept empty entries and the report said nothing).
- **Tracks:** pads or plates that are gone are named in the report; a wheel whose part ID changed keeps its "coupled" tick.

## 0.2.95 – 14 Nov 2026 – a cable on a moving part; the quadrant operation in the demo (task 0082)

- **Winch keeps it tight** (4 Motion > Cables and paths, a cable's details): the winch pays out exactly what the
  cable's path needs when the parts it runs over move – a wire over a pulley on a tilting frame, a block that is
  lowered. Its drum, sheaves and stripes turn with it. Build writes the payout for every frame; while you pose, it
  follows at once. The line says how much the winch pays out now, or why it cannot (a step already moves it).
- **A cable into the sea hangs from what it still goes round:** when the part it hangs from moves past the horn or
  chute (a quadrant going over the stern), the cable leaves the horn and hangs from the moving part; when it comes
  back, the horn catches the cable again. Into the sea says which part it hangs from.
- **Let go here** on a cable's start, end or contact: from that frame on it stays where it was – on the seabed for
  a cable into the sea – while the part that carried it moves away (an ROV releases the cable from the quadrant).
- **Weather & time > Bow** (From the hull / +x / -x): the wake trails behind the real stern and the bow throws up
  the spray. From the hull reads the waterline; older projects keep their look.
- **Demo project:** the A&R wire and the tipping wires are now real cables of the app (kept tight by their
  winches). After the sea shot comes the **quadrant operation at the second end**: shot 9 – the D carries the cable
  end and its CPS aft and the handler tilts over the stern (was shot 7); 10 – the D hangs plumb from the A&R wire and
  is lowered through the cut-away; 11 – it tips flat near the seabed, the cable and its CPS are let go and lie on the
  seabed; 12 – it comes back up and travels back to its place. 0 clashes. The animation is about 2 ¼ minutes now.
- **Test tour and PC check:** a new stop and line "A cable on a moving part" (a small model: a cable over a sheave
  on a carriage that travels, tilts and lowers, into the sea, with a let-go).

**Test this (on your PC):** Help > Make demo project (about 1 minute longer than before), open it, 6 Animation >
What it can do today > Build & play from shot 9 on: the D goes over the stern with the cable end, down to the
seabed, tips, leaves the cable on the seabed and comes back. Render shots 10 and 11 on the RTX 3090 and look at the
D under water. Help > Make test tour project, stop "A cable on a moving part": Go, then OK or Problem.

## 0.2.94 – 14 Nov 2026 – marine looks: growth at the waterline, weathering streaks, concrete (task 0116)

- **3 Looks > Ready-made material… has three new looks**: **Marine paint, growth below the waterline** (your paint
  colour, dark green-brown sea growth below the water with a ragged top edge, and about 2.5 m of splash zone with a
  greenish tint and thin rust streaks above it – the waterline follows the sea of 5 Scene & Render > Surroundings),
  **Marine paint, run-down streaks** (light dirt and rust streaks running down towers and walls, never on decks) and
  **Concrete** (foundations, pedestals). They are drawn by the material itself: no pictures to add, Cycles and Fast
  preview.
- **Clash check, tall machines**: two parts of one moving body far above the ground (a wind turbine's rotor 136 m up)
  were sometimes checked against each other because of rounding, and gave clashes of a millimetre or two that are not
  there. Fixed.
- **For the web page**: the render kit gets the IEA 15 MW reference wind turbine (IEA Wind TCP Task 37, Apache-2.0) at
  sea on its monopile and on land, with what Fresing added: nacelle cover, tower door, transition piece, platform,
  davit, boat landing, ladder, J-tubes, foundation, signs and the motion (rotor at its rated 7.56 rpm, yaw, blade
  pitch, door, davit). The kit makes it from your STEP; nothing changes in the app for this.
- PC check: a new line "Marine looks". Test tour: a new stop "Marine growth, streaks, concrete".
## 0.2.93 – 14 Nov 2026 – web 3D models keep their tool changes; two moving models on the website (task 0111)

- **5 Scene & Render > Web 3D model** with Include animation: tools a tool change carries (spindle, changer arm,
  pots) and parts a Show/Hide step brings in or takes out now come and go in the file as in the animation. Before, the
  changer's arm turned with empty hands.
- The website's **Turn it yourself** now offers a choice of 3D models, each on its own page that plays by itself in a
  loop, with a Pause button: the test mill changing tools (2.2 MB) and the Thor robot arm at work (7.5 MB), both with
  soft baked light and a live sun shadow.

## 0.2.92 – 13 Nov 2026 – houses from House Planner: bake the light, send it back (task 0114)

- **File > Import > House Planner scene (.hpscene)**: brings in a house exported from House Planner – its rooms,
  furniture, lamps and plot, and the list of moments to bake (morning, evening, winter night …) with the photos it
  wants. Importing again replaces the house.
- New panel **5 Scene & Render > House from House Planner**: the house, the light and quality House Planner asked
  for, every season and moment. The eye button shows a moment in the view: the sun exactly where House Planner put
  it, the clouds, the season's wet or snowy look, the lamps that are on.
- **Bake and export…** bakes the light of every moment with Cycles (sun, sky, lamps; the storeys House Planner shows
  from above; a snow layer on the roof and the plot in a snowy season), renders the photos and turntable videos, and
  saves one bake package (.hpbake) next to the project for House Planner. Progress and Cancel; the project does not
  change.
- The made-up sample house comes with the app (`sample-house.hpscene` in its data folder); a real bake of it is in
  the repository for House Planner's tests.
- New line in the PC check (house.bake) and a new stop in the test tour (House from House Planner).

## 0.2.91 – 13 Nov 2026 – cable into the sea, seabed and cut-away (task 0081)

- **Into the sea** (4 Motion > Cables and paths, a new fold): a cable hangs from its last contact – a horn, a chute
  or an overboarding sheave – in a curve down to the seabed and lies on the seabed behind it. Set the touch-down by
  its **layback** (how far behind the horn) or by the **bottom tension** and the cable's weight in water; the panel
  shows the angle it leaves the horn at and the tensions at the seabed and at the top. The cable keeps its exact
  length while it pays out, leaves the horn without a kink, and its stripes run down the curve but stand still where
  it lies on the seabed. Warnings when it bends over the end of the horn, lifts its end off the seabed or would pile
  up.
- **The seabed moves aft** under the vessel: with the lay (the touch-down stays behind the vessel) or at the vessel
  speed of Weather & time. With vessel motion on, the horn rides the vessel and the curve follows it.
- **Things on the cable**: select a CPS set, a bend restrictor or a pull head and press **Put selected on the
  cable**: it rides along with the cable over the rollers, over the horn and down into the sea, each segment a stiff
  piece on the cable. Kept through a model update.
- **Sea: water depth, seabed, cut-away and water clarity** (5 Scene & Render > Surroundings, Open sea): a sandy
  seabed at the water depth; **Cut-away behind the stern** takes a box of water away so you see the cable hang down
  to the seabed; **Water clarity** (2 to 40 m) sets how far you see into the water past its walls. Without the
  cut-away the sea looks exactly as before.
- **Demo project**: shot 8 "Into the sea" – the power cable from horn A down to the seabed 30 m below, seen through
  the cut-away, paying out at 10 m/min. Handling winch 1's fleet angle and the D-quadrant's guide rollers for thin
  cables are fixed.
- Test tour stop "Cable into the sea", PC check line `motion.sea_cable`, user guide section "Into the sea".

## 0.2.90 – 13 Nov 2026 – the clash check takes a quarter of the time on big moving machines (task 0110)

- **6 Animation > Clash check is about 4 × faster on the demo vessel**: 3.4 minutes instead of 14 on the cloud test
  machine, with exactly the same result (no clashes). It finds the same clashes as before everywhere: every test, every
  test-tour animation and the PC check's big made-up machine (1,667 clashes) give the same rows.
- How: two parts far apart are proven apart once and then left alone until they have moved that far against each
  other – also small parts now (a sprocket spinning a metre from a big frame was tested 48 times between every two
  frames). A sheave turning on its pin is checked once per turn even while the head carrying both tips over. And a
  part that is not round but repeats – a carousel's rim fence of posts turning past its drive gearboxes – is checked
  over one post step and then left alone, as long as nothing touched in that step.

## 0.2.89 – 13 Nov 2026 – web 3D model with baked light (task 0107)

New in 5 Scene & Render > Web 3D model: the fold **Light**, a choice per export
- **Live only** (as before): the page lights the parts itself – smallest file, fastest export.
- **Soft light baked, sun live**: Cycles bakes the light from the sky, the soft shadows under and between parts,
  darker inside corners and the light bounced off other parts (the sun's bounce too) into the file; the sun's sharp
  shadows stay live and move with the parts, the vessel and the sea. The choice for animations.
- **Everything baked**: the sun's shadows are baked too – closest to the render, for a machine that stands still.
  With an animation or vessel motion in the export, Export asks once (baked shadows do not move).
- **Bake quality** Draft / Normal / Fine and **Points per metre** (0 = Auto), with an estimate of the bake time and
  the extra file size before you export. The bake uses the project's light (or the sky picked for the page), runs on
  your graphics card when the app renders with one, and never changes the project. Cancel stops it.
- Each part gets its own light (also copies of one part); small parts with many copies carry it per corner point.
  Other 3D programs see the soft light as shadowing in corners (on the larger parts).
- With Surroundings None and a baked choice the page is the newer page in a plain form (the light background as
  before). Fixed on that page: with Live sun shadows off, the sun now shines from its real direction (it shone
  straight down).
- Measured on a 4-core PC without a graphics card (processor): the invented 124 m cable-lay vessel bakes in 43 s
  at Draft (+2.7 MB) and about 6 min at Normal (+4.3 MB); the test mill in 7–18 s.
- For other parts of the app (the house round trip): the bake can be called with a list of objects, a light choice
  and a time of day, and returns the light per object id; it uses an object's own second UV set as it is.

## 0.2.88 – 13 Nov 2026 – weather and time of day, and a new sea (task 0109)

New: 5 Scene & Render > **Weather & time**
- **One place for the weather.** Presets **Clear day**, **Grey North Sea**, **Storm**, **Snow at the quay** and
  **Night shift**, or set it yourself. Off: everything looks exactly as before (except the sea, below).
- **Time of day.** A clock from sunrise to night sets the sun's height, its direction and the sky's colour (sunrise,
  day, golden hour, dusk). Optional: a date and a latitude for the real sun path of that day. At night: a dark sky
  with stars and the moon, **floodlights** on masts round the deck or the quay (set up for you, Auto from dusk), and
  the picture opens up as a camera does. **Work lights**: click a lamp part, press Spot or Flood – it shines, moves
  with the part and stays through a model update (also with Weather & time off).
- **Clouds, haze and fog.** Cloud cover from clear to overcast, a low cloud deck, and a visibility in metres: haze
  towards the horizon, fog that hides the far sea and the quay. The fog costs no render time you can measure.
- **Rain.** Falling rain (amount, drop size) slanting with the wind, splashes on the deck, the quay and the sea, and a
  **Wet** look on the machine and the ground: darker, glossier, run-off streaks on slopes, puddles on flat parts –
  also after the rain, without rain falling.
- **Snow.** Falling flakes drifting with the wind, and a **snow layer** on everything that faces up under the open
  sky; parts under a roof or a cover stay clear. It also works on any imported mesh (a function other parts of the
  app can call).
- **Wind.** Beaufort strength and direction (compass, or from the vessel's bow): rain, snow, spray and an optional
  **flag** follow it; the sea can follow it too.
- **In a video:** a new step **Weather & time** in 6 Animation fades from the weather before it to a new one – day to
  dusk, the rain starting, the fog lifting. Works with scripts off, in the render queue and for every paint scheme;
  saved scenes keep their weather.

New sea (Open sea, Vessel deck, Quayside) – **old projects open with it**:
- The broad white stripes are gone. The sea is now many waves of different lengths and directions from a measured
  wave spectrum (JONSWAP / Pierson–Moskowitz), so it never repeats, also seen from high above or towards the horizon.
- White caps only where waves are steep, in patches that come and go and drift; as many as measured at sea (Monahan
  & O'Muircheartaigh 1980: hardly any at Beaufort 3, about 2 % at 6, about 16 % at 9), foam streaks from Beaufort 7.
- Foam round the hull at the waterline that rides with the vessel, a wake when a vessel speed is set, spray at the bow
  and off the wave tops in strong wind, a deeper water colour with the sky reflected.
- Sea: **Calm** (Beaufort 3), **Rough** (Beaufort 6) or new **From the wind**. Vessel motion keeps its numbers.

Test tour stops "Weather: grey North Sea", "Weather changes in a video", "Night shift"; PC-check lines `weather.time`,
`weather.rain`, `weather.snow`, `weather.fog`, `weather.sea`, `weather.step`, Heavy `heavy.weather`; guide chapter
"Weather & time".

## 0.2.87 – 13 Nov 2026 – tensioner tracks and belts run with the cable (task 0079)

New: 4 Motion > **Tracks and belts**
- **The pads of a tensioner run with the cable.** Press **Add track**, click the track's wheels round the loop
  (sprockets, idlers, support rollers) and press Enter, click one link of the chain, then a pad or back plate if the
  links carry them, and press Enter. The app finds all the links, pads and plates, lays the chain round the wheels
  and runs it: the pads that hold the cable move exactly as fast as the cable, and the sprockets turn one tooth per
  link. Your own parts move – their colours, paint schemes, fades and hiding keep working.
- **Its speed** is the cable that runs through it (4 Motion > Cables and paths), found by itself. Pick another
  joint under **Speed** (any slide joint, or the joint of one of its own wheels); **Runs the other way** turns it
  round. Without a cable the track gets a joint of its own: give it a **Run motor** step in 6 Animation.
- A track on a lift or tilt (a tensioner's top track) lifts and tilts as one; its pads keep running.
- The same works for **belts and chains of separate links** round wheels of any size, and crawler tracks.
- It costs no time in Python while playing or rendering, works in the render queue and with scripts switched off,
  survives a model update and is left out of the clash check.

Also
- **Cables and paths: Speed from.** Pick an existing slide joint above Add cable and the new cable runs on it (for
  example a joint that already turns rollers). Empty: the app makes a joint as before.
- **Demo project:** the four tracks of the two tensioners run on the cable; in shot 5 the cable runs again while the
  top track squeezes it, and the pads run with it. The demo's sprocket joints turn one tooth per link of chain.
## 0.2.86 – 13 Nov 2026 – web 3D model with its surroundings: sea, sky, weather and a live sun (task 0106)

New in 5 Scene & Render > Web 3D model: the fold **Surroundings on the page**
- **None** keeps the page as before. **As in the project** puts the machine's surroundings on the page, picked
  per export (the project itself does not change): an endless **moving sea** with the app's own waves (white caps
  when Rough), **vessel motion** – the machine and the deck heave, pitch and roll in step with the waves, Still and
  Level parts as in the app, together with an exported animation –, the **sky** (the project's sky and sun, or a
  sky at a time of day with clouds; a 360° photo or a studio look becomes the page's light, so shiny metal mirrors
  what the app shows), **haze**, **rain** with a wet look and spray at the bow on a rough sea, and **live sun
  shadows** that move with the parts.
- **Page quality** Phone / Balanced / Best, and **Auto quality**: the page lowers its quality by itself on a slow
  phone or laptop and says so in its corner.
- Still one file that opens without internet. The line under Export says what the surroundings add to the file.
- Test tour stop "Web 3D model with surroundings", PC-check line `web3d.surroundings`, guide section
  "Surroundings on the page".

## 0.2.85 – 13 Nov 2026 – drums and carousels: the cable comes off layer by layer (task 0080)

New: 4 Motion > **Drums and carousels**
- **A cable that comes off its drum or carousel.** Choose the cable in Cables and paths, press **Add drum** or **Add
  carousel** and click the drum's barrel or the carousel's turntable. The app reads the drum (first layer, the width
  between the flanges) or the coil (inner and outer radius) and how much cable is on it from where the CAD cable
  leaves it. The CAD coil or wire on the drum is hidden; the app draws the cable on it, in the cable's own look.
- **Layer by layer.** On a drum the wraps lie side by side in the spiral groove, each layer back the other way and a
  layer higher; with **Lebus** grooves the wraps run parallel and step half a groove at two crossovers per turn. On a
  carousel the top layer gets smaller turn by turn; the full layers under it show as one solid that gets lower layer
  by layer. The free cable always starts exactly where it leaves the drum or coil.
- **It turns at the right speed.** The drum or carousel follows the cable speed **by table**: faster as the layers
  get smaller (within 0.01° of the exact wraps over 100 m). This is a new kind of coupling between joints: it works
  with scripts off, in the render queue and at any frame rate; the joint's details say "Follows … by a table".
- **This joint follows the layer:** a level wind goes along the drum with the wrap being paid out, a loading arm or
  arch swings so its guide stays over the turn being paid out, a guide's swivel turns along it.
- **Warnings in plain words:** a fleet angle above 1.5° to the first sheave (naming the flange; the limit can be
  changed), a drum or carousel that runs empty or overfills – in the panel and when you build an animation.
- **Demo project:** the carousel spools the power cable – in shot 3 the top layer pays out (time-lapse x 90) while the
  arch slews and the guide's cage swivels with it; handling winch 1 (shot 6) pays out its wire from its Lebus drum.
- Test tour stop "Drum and carousel spooling", PC-check line `motion.spool`, guide section "Drums and carousels".

## 0.2.84 – 13 Nov 2026 – demo: the D-quadrant as wide as the cable's path, tensioners open sideways (task 0102)

Changed in the demo project (Help > Make demo project), as you work on deck:
- **No S-bends any more.** The side lanes lie exactly on the D-quadrant's curve: the cable runs straight from the
  two tensioners round the D's gutter, one smooth U. The deck behind it moved up a few metres (the oval is 170 m,
  was 188 m).
- **The D travels aft between the tensioners**, its sides – gutter and cable – through their lines. Its frame below
  the cable's height stays inside the tensioners' bottom tracks; towards its ends the gutter is a channel over the
  cable (guide rollers hanging from a top plate), so it passes over the bottom tracks, the horns and the cradles.
- **The tensioner is remade:** the top track first **lifts** (two lift cylinders), then **tilts 70° out to its own
  side** about a hinge along the cable on its outboard side – tensioner 1 to port, tensioner 2 to starboard – with
  two tilt cylinders that follow (4 Motion > Cylinders). Open, nothing of it stands between the two cable lines.
- **Every roller cradle in the D's way drops** out of it: one "Cradle … drop" joint per lane, the others follow.
- **Shot 5** shows the new opening (lift, tilt out, back, squeeze); **shot 7** opens both tensioners and drops the
  cradles before the D travels aft between them. The clash check over the whole animation: 0.
## 0.2.83 – 13 Nov 2026 – G-code timed with acceleration: short moves take as long as on the machine (task 0103)

New in 4 Motion > CNC machine > **Machine: speeds, zero, shift**
- **Speed up and slow down (acceleration)**: every move of a G-code program now speeds up and slows down with each
  axis' maximum acceleration, as on the machine. Programs with many short moves no longer play too fast: the step's
  time matches what the machine does. On for new machines; projects made before keep their timing until you tick it.
- **X / Y / Z accel.** (mm/s²), and for rotary axes **A / B / C accel.** (°/s²) under Rotary axes.
- **Read from LinuxCNC INI…**: pick your machine's `.ini`; the rapid speed and acceleration of every axis are filled
  in (the file is only read, not kept).
- Corners as LinuxCNC takes them: **G61** stops at every corner, **G64** (the default) slows down only as much as the
  corner needs (a line cut into many short pieces runs straight through), **G64 P** slows more for its tolerance.
  Arcs run no faster than √(acceleration × radius). Close to LinuxCNC, not its exact planner.
- The tool visibly speeds up and slows down in the video; milling, chips, coolant and tool marks follow it.
- The step shows its time with and without acceleration ("1 min 12 s on the machine (58.0 s without acceleration)").
- Test tour stop "Acceleration: slow short moves", PC check line `gcode.acceleration`.

## 0.2.82 – 13 Nov 2026 – web 3D model: half the file for big machines, half the memory at 2048 (task 0105)

5 Scene & Render > **Web 3D model**
- **Smaller file** (compressed), on by default: a big model (200,000 triangles or more) is packed with meshopt –
  about **half the file** (the 3,000-part test machine 35 → 17 MB, the cable-lay demo vessel 25 → 12 MB). The page
  still opens offline from its one file, also on a phone: the viewer already carries the unpacker. Some older 3D
  programs cannot open a packed .glb on its own (Blender 5.2, Chrome, Edge, Firefox and Safari can); switch it off
  for a customer whose program refuses it. The line under Export says "compressed" when it was packed.
- **Texture size 2048 needs half the memory**: the looks are baked in smaller pieces (the demo vessel 5.2 → 2.5 GB,
  and a little faster: 58 → 46 s on the 4-core test machine).
## 0.2.81 – 13 Nov 2026 – one-click product video (task 0101)

New: 6 Animation > **Make a product video**
- One button builds a first complete film from what the project already has: a title card, one turn round the
  machine, the machine's own motions (each joint with a range goes to its far limit and back, with the camera watching
  the moving part), the saved poses, a subassembly taken apart and put together again, a close-up from two saved
  cameras and an end card. It is a new animation called "Product video" with ordinary steps you can change.
- Options (folded under the button): length (about 30, 60 or 90 s), which subassembly to take apart (the biggest, the
  selected one, or none), how many motions to show, title card, end card, title text and captions.
- A project without joints skips the motions, one without a big subassembly skips the take-apart; the line under the
  button says what was left out and why. Pressing it again makes the video anew and asks first if you changed its steps.
- New test tour stop "One-click product video", new PC-check line, and a guide section "Make a product video".

## 0.2.80 – 13 Nov 2026 – cables and paths: one cable speed moves the cable and turns every roller (task 0078)

New: 4 Motion > **Cables and paths**
- **A cable that runs.** Select the cable you drew in CAD (one solid along its route) and press **Add cable**. The
  app reads its middle line and diameter and finds what it touches: the sheaves it goes round, the rollers it rests on
  (also V-roller pairs and guide rollers), chutes it slides over and the bends it was drawn with. The stiff CAD part
  is replaced by a cable drawn by the app on exactly that path.
- **One cable speed, in m/min.** Every cable gets a joint "Cable <name>" whose value is the metres paid out. In
  6 Animation the step **Run motor** on that joint takes the speed as **Cable speed (m/min)** (laying a power cable:
  about 10 m/min; negative hauls back in). Every roller and sheave the cable touches turns at exactly the speed of
  the cable where it touches – rollers and sheaves that already had a joint keep it.
- **Two looks that move with the cable:** **Power cable** (black with yellow stripes at an angle; stripe distance,
  angle and width can be set) and **Steel wire rope** (twisted strands, lay length can be set). The pattern runs
  along with the paid-out length, so you see the cable move – in the view, in Cycles and EEVEE, in the render queue.
- **Sheaves that move.** When a sheave sits on something that moves (a luffing A-frame, a tilting arm) the cable
  follows: at once while you pose, and Build animation works out every frame's path once. A cable whose sheaves all
  stand still is drawn once and costs nothing per frame.
- **What it touches** lists every contact with its diameter, wrap angle and side. Flip the side, remove a contact,
  add one by clicking a part, switch **Turns with the cable** off for a fixed guide, put the start or end on a part
  or leave it as a free end.
- **Warnings in plain words:** a bend tighter than the cable's **Smallest bend (MBR)** names the sheave; a sheave
  the cable no longer touches, or goes round the wrong way, is named with the frame. A part that is not a cable, or
  a path that cannot be made, is refused with the reason – never a broken shape.
- **Demo project** (Help > Make demo project): the vessel's power cable now lies on its path over 218 rollers and
  its bends, with the yellow stripes; in the roller-highway shot it runs at 10 m/min and every roller turns with it.
  Make the demo again to get it.
- Test tour stop "Cable over sheaves and rollers", PC-check line "A cable runs over sheaves, rollers and a chute",
  guide chapter "Cables and paths".

Fixed
- A joint that moves nothing by itself (the demo's "Cable travel") was removed by a model update, together with
  every roller following it. It is kept now.

Not yet (later tasks): tensioner tracks gripping the cable, the coil on a carousel or drum, the cable into the sea.

For your PC: the cable in the real view (does it follow smoothly while you drag a joint?), a GPU render of the demo's
roller-highway shot, and one of your own CAD cables (does **Add cable** find its rollers and sheaves?).

## 0.2.79 – 13 Nov 2026 – take a subassembly apart part by part (task 0100)

New: 6 Animation > Add step > **Assembly sequence**
- **"How it is built" in one step.** Select a subassembly and add the step: its parts fly out one after another,
  each starting while the one before is still on its way, to an exploded place. **Put together** is the exact
  reverse and every part ends exactly where it belongs.
- **Order:** Outside in (bolts, nuts and washers first, then the parts nearest the outside; a part waits while
  another part is still in its way), Tree order or Reverse. **Direction:** along an axis of the subassembly (+X …
  -Z, it turns with the subassembly), up, or away from the centre. **Distance** by size or set. Along an axis the
  parts end in a neat column: the first one out goes furthest, so nothing flies through a part that is already out.
- **Per part** and **Overlap** set the pace; the step's length follows. **At the end:** stay, hide or fade.
  **Trail lines** draws each part's path. **Preview** shows the step in the view without building.
- Works after a joint has moved the subassembly, keeps every joint as it is, logos ride along, hoses follow; a part
  whose way is blocked is named at Build.
- Test tour: new stop "Assembly sequence"; PC check: new line `animation.sequence`; user guide: "Take a subassembly
  apart".

## 0.2.78 – 13 Nov 2026 – hoses, cables and drag chains follow the motion (task 0058)

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
## 0.2.77 – 12 Nov 2026 – web 3D model: turn the machine in a web browser (task 0099)

New: **5 Scene & Render > Web 3D model**
- **Export…** saves the machine as it is shown now as **one 3D file** (`.glb`) and **a page** (`.html`) that shows
  it in any web browser: drag to turn it, scroll or pinch to zoom. The page is one file: e-mail it to a customer or
  put it on your website; it also opens without internet, on a PC or a phone.
- The looks are **baked into small pictures** that repeat over the parts at the scale of your renders: colours,
  gloss, metal, cast and blasted surfaces, glass, lights, wire mesh with holes, and your logos and stickers. Looks
  that are one colour need no picture, so the file stays small. Not in the web model: edge wear, the stretched shine
  of brushed or turned metal, the very fine orange peel of paint, tool marks, the cutaway, the surroundings.
- **Texture size** 512 / 1024 / 2048 (sharper close up, bigger file), **Hide part names** (on: the file calls them
  Part 1, Part 2 …, so customers do not see your part numbers) and **Include animation** (after Build animation:
  the page plays it in a loop). Hidden parts stay out; the pose and paint scheme you see go in.
- The line under the button shows the size, triangles, pictures and time, with **Open page** and **Show in folder**.
  A big model shows how far it is; **Cancel** (or Esc) stops it and saves nothing.
- Measured on the 4-core test machine: the test mill in 2–3 s (0.3 MB); a 3,000-part machine in 4–10 s (35 MB).

Also: the landing page has a **Turn it yourself** section with a model to turn (an invented test mill with a tool
changer); the test tour has a stop "Web 3D model"; the PC check has the lines web3d.export and heavy.web3d.

## 0.2.76 – 12 Nov 2026 – milling fixes: no dive after a tool change, chips on a moving 4th-axis table (task 0096)

Tool changes (4 Motion > CNC machine)
- **No more holes where the program does not cut.** After a tool change the new tool, when it is longer, could
  dive into the part (in the test tour's "Three tools" the end mill went 17.7 mm into the block). Now the spindle
  rises before a longer tool goes in, and on the way back from the change position the head comes down onto the
  program's point with the new tool's length. Works for changes by hand, the carousel and the double arm.
- **An M6 without G43 for the new tool** is shown as on the machine: the old tool's length stays, so the new tool
  runs too deep (or too high). The Build says so with the number of mm and the line, and the clash check lists it.

Milling (4 Motion > Milling)
- **Chips on a table that carries the 4th axis**: when the rotary table sits on a table that moves, chips that fall
  past the chuck land on that table and move with it; chips past it land on the bed.
- **A floor stays flat up to a slope**: where a pocket floor meets a gentle slope a ball end mill finished, the floor
  no longer shows a shaded band along the edge (197 mm² of floor on the test model, now none).
- **Drill rings** on the drill point and a plunge's bottom are spaced by the feed per turn (F / S), like the rest.
- **F12 straight after scrubbing** now always renders the exact shading of the milled block ("Lock Interface" is
  kept on while milling).

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
