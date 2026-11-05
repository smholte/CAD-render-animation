FRESING RENDER - INSTALLATION
=============================

Install (once per PC, no admin rights needed)
---------------------------------------------
1. Unzip this folder anywhere (e.g. Downloads).
2. Double-click  Install.bat   (close Fresing Render first when upgrading)
   If Windows shows "Windows protected your PC": click "More info", then "Run anyway".
   Unpacking Blender takes a few minutes without a progress bar; let it finish.
   - downloads Blender 5.2.3 LTS (about 400 MB) and checks it
   - installs Fresing Render in  %LOCALAPPDATA%\FresingRender
     (separate from any other Blender on this PC)
   - creates a "Fresing Render" shortcut on the Desktop
3. Start "Fresing Render" from the Desktop.
4. Optional but recommended: Start menu > Fresing Render > "Fresing Render - Self test".
   It checks the graphics card, imports a small test model, renders it, and writes
   "Fresing Render self-test.txt" on the Desktop.

User guide: "User guide.html" in this folder (opens in your web browser, works offline).
After installing it is also in the app (Help > Fresing Render user guide) and in the
Start menu (Fresing Render > "Fresing Render - User guide").

Tip: if a PC has no internet access, put blender-5.2.3-windows-x64.zip
(from https://download.blender.org/release/Blender5.2/) next to Install.bat.

Updates
-------
- The app looks for a new version on GitHub a few seconds after it starts. When there is
  one, the Fresing tab shows "Update available" with what's new. Click "Update now": the
  app saves your project, closes, installs the update and opens again (about a minute).
  Help > "Check for Fresing Render updates" asks at any time.
- Versions before 0.2.16 cannot do this yet: run this installer once over the old one.
- The check needs internet access to github.com (and its download servers). It can be
  switched off: Edit > Preferences > Add-ons > Fresing Render > "Check for updates at
  start-up". Without internet: run the new installer over the old one.
- Another update address (for example a network folder with the files of a release):
      Install.bat -UpdateUrl "\\SERVER\share\fresing\index.json"
  (keep the quotes; -UpdateUrl default goes back to GitHub).
- Company proxy that asks for a login: the check may not get through (the self-test line
  "Update check" says so). Ask IT to allow github.com, or run new installers by hand.
- A version that needs a newer Blender comes with a new installer (the app says so). Update
  all PCs together: projects saved in a newer Blender may not open in an older one.

Remove
------
Double-click Uninstall.bat (close Fresing Render first).
Projects (.blend files) and renders are not touched.
If you installed into another folder with -InstallDir, give the same folder:
    Uninstall.bat -InstallDir "D:\Apps\FresingRender"

Company PCs
-----------
If Install.bat stops with a message about scripts being disabled or blocked, the PC's
IT policy blocks PowerShell scripts or programs in %LOCALAPPDATA%. Ask IT to allow
Install-FresingRender.ps1 once, or to install into an allowed folder:
    Install.bat -InstallDir "D:\Apps\FresingRender"

Using it (short) - the user guide explains every step with pictures
-------------------------------------------------------------------
Side panel on the right of the 3D view, tab "Fresing" (press N if it is hidden).
Work top to bottom: in every section what you choose comes first, the main button is the
big blue one, and the header of a closed section shows its state (parts, joints, queue...).
1 Import          Import STEP... or drag a .step file onto the view. Big files are meshed on
                  all processor cores at once (one is left free, so the PC stays usable).
                  A second import of an unchanged file comes from the stored copy.
                  "Update to new revision..." loads a newer STEP of the same machine and keeps
                  all work (colours, hidden parts, joints, poses, scenes); a report lists new
                  and missing parts.
2 Structure       Subassemblies: lock/unlock, show/hide, select. Clean-up removes
                  parts that never show. Visibility sets save which parts are hidden.
3 Looks           Parts are sorted into material groups automatically (fasteners by
                  type and finish, CAD colours). Pick a material and RAL colour per
                  group. Sorting rules and paint schemes are in the sub-panels.
4 Motion          Joints: click the subassembly that should move, press "Add rotate joint"
                  (or slide) and click its pivot hole or shaft on the model. Drag the slider.
                  "Sits on" (under Set-up) makes a joint ride on another subassembly.
                  A second joint on the same subassembly goes on top of the first: the
                  moves add up (Y 1000 mm, then X 500 mm = X 500 / Y 1000). The newer one
                  rides on the older one; "Swap order" turns that round.
                  "Follows a joint": one joint moves others at a ratio (gears, telescope
                  sections, gripper jaws, spindles, racks, rolling wheels).
                  "Motor" on a rotate joint: no limits, it turns without end.
                  Poses save all joint positions; Explode moves pieces apart.
5 Scene & Render  Background (colour, 360 photo, sky, transparent), floor, cameras,
                  image size (16:9 HD/4K, A4/A3 at 300 dpi...), Render image.
                  Saved scenes = colours + pose + visibility + camera + background in one click.
6 Animation       Steps on a timeline: move a joint, go to a pose, camera cut / move / orbit,
                  show or hide a subassembly, run a motor (12 rpm for 5 s = 1 turn).
                  "Build & play" plays it in the view (Space).
                  "Render animation" makes an MP4 (and the single frames) in the queue.
                  "Time test (2 frames)" renders two frames first and shows how long the whole
                  animation will take (and the test frame, to check the look).
                  Quality "Fast preview (EEVEE)" is minutes instead of hours, to check motion.
7 Render queue    Images and animations rendered by a second Blender in the background:
                  keep working, or close the app and let it run overnight.
                  Select a finished item: "Open" plays/opens it, "Show in folder"
                  opens File Explorer with the file selected.
Renders are saved in a "Renders" folder next to the saved project
(or Pictures\Fresing Render when the project is not saved yet).
After "Render image": "Open" and "Show in folder" appear under the button.

Projects on a shared folder: while you have a project open, others who open it see
"In use by <name> on <computer>" in panel 1.
