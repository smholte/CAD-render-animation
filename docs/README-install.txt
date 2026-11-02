FRESING RENDER - INSTALLATION
=============================

Install (once per PC, no admin rights needed)
---------------------------------------------
1. Unzip this folder anywhere (e.g. Downloads).
2. Double-click  Install.bat   (close Fresing Render first when upgrading)
   - downloads Blender 5.2.3 LTS (about 400 MB) and checks it
   - installs Fresing Render in  %LOCALAPPDATA%\FresingRender
     (separate from any other Blender on this PC)
   - creates a "Fresing Render" shortcut on the Desktop
3. Start "Fresing Render" from the Desktop.
4. Optional but recommended: Start menu > Fresing Render > "Fresing Render - Self test".
   It checks the graphics card, imports a small test model, renders it, and writes
   "Fresing Render self-test.txt" on the Desktop.

Tip: if a PC has no internet access, put blender-5.2.3-windows-x64.zip
(from https://download.blender.org/release/Blender5.2/) next to Install.bat.

Updates
-------
- With an update server: install once with
      Install.bat -UpdateUrl https://<server>/index.json [-AccessToken <token>]
  New versions then show up in Blender as "update available" (Edit > Preferences >
  Get Extensions). One click updates.
- Without an update server: run the new installer over the old one.
- A version that needs a newer Blender comes with a new installer. Update all PCs
  together: projects saved in a newer Blender may not open in an older one.

Remove
------
Double-click Uninstall.bat (close Fresing Render first).
Projects (.blend files) and renders are not touched.

Company PCs
-----------
If Install.bat stops with a message about scripts being disabled or blocked, the PC's
IT policy blocks PowerShell scripts or programs in %LOCALAPPDATA%. Ask IT to allow
Install-FresingRender.ps1 once, or to install into an allowed folder:
    Install.bat -InstallDir "D:\Apps\FresingRender"

Using it (short)
----------------
Side panel on the right of the 3D view, tab "Fresing" (press N if it is hidden):
1 Import          Import STEP... or drag a .step file onto the view.
2 Structure       Subassemblies: lock/unlock, show/hide, select. Clean-up removes
                  parts that never show (internal parts, tiny parts).
3 Looks           Parts are sorted into material groups automatically (fasteners by
                  type and finish, CAD colours). Pick a material and RAL colour per
                  group. Sorting rules and paint schemes are in the sub-panels.
4 Scene & Render  Background (colour, 360 photo, sky, transparent), floor, cameras,
                  image size (16:9 HD/4K, A4/A3 at 300 dpi...), Render image.
Renders are saved in a "Renders" folder next to the saved project
(or Pictures\Fresing Render when the project is not saved yet).
