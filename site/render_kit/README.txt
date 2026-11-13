FRESING SITE KIT - pictures and videos for the web page
=======================================================

Makes the pictures and the moving clips for https://smholte.github.io/CAD-render-animation/ with the
Fresing Render installed on this PC (on the graphics card). Thor and the brick press become projects
that move (joints, cylinders, an animation) and get Fresing Render's one-click product video.

What you need: Fresing Render installed (Install.bat). Nothing else.

Steps
-----
1. Download: on github.com (signed in), open the repository's Releases page, find the draft
   "Site kit - pictures and videos for the web page" and click fresing_site_kit.zip.
2. Unzip it into Downloads, next to the folder of your first kit (9 Nov): right-click the zip >
   Extract All... > Extract. The kit takes evo.step, openarm.step and farmbot.step from that first
   kit's "models" folder; thor.step and ceb_press.step come with this kit.
3. Close Fresing Render. Open the new folder "Fresing site kit" and double-click
   "Make site pictures.bat". A black window shows the expected time and asks when to start:
   press Enter to start now, or type a time like 23:30 and press Enter.
4. Wait. Expected: about 3 1/2 hours on the RTX 3090 (the window says it more exactly after the
   first picture). Keep the window open; the PC stays awake. One model that fails does not stop
   the others: the window and log.txt say why.
5. When it is done, the "output" folder opens with site_pictures_<date>.zip in it, and the contact
   sheet opens in your browser (all pictures and clips on one page: have a look).
6. Upload: on the same draft release page click Edit (the pencil), drag site_pictures_<date>.zip
   onto "Attach binaries by dropping them here", wait until it is uploaded, then click
   "Save draft" (not Publish). Tell the lead chat: "site pictures uploaded".

Changing a picture
------------------
Open models.ini in Notepad: each model has a few lines (light look, surroundings, weather, camera
views, captions, which video). Change one, save, double-click the .bat again. The meaning of every
line is at the top of models.ini. The project of each model is saved in output\full\<model>.blend:
open it in Fresing Render (File > Open) to look at the joints and the animation.

If something goes wrong
-----------------------
- "Fresing Render is not installed on this PC": run Install.bat first.
- "file not found": put the missing STEP file into the "models" folder (names as in models.ini).
- "no graphics card found": the window says so at the start; it still works, but very slowly.
- Otherwise: upload output\log.txt to the draft release instead (step 6).
