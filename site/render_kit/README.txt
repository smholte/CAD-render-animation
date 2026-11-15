FRESING SITE KIT - pictures and videos for the web page
=======================================================

Makes the pictures and the moving clips for https://smholte.github.io/CAD-render-animation/ with the
Fresing Render installed on this PC (on the graphics card). Thor and the brick press become projects
that move (joints, cylinders, an animation) and get Fresing Render's one-click product video. The
IEA 15 MW wind turbine comes twice: at sea on its monopile (with a clip of the rotor turning) and
on land.

What you need: Fresing Render installed (Install.bat). Nothing else.

Steps
-----
1. Download: on github.com (signed in), open the repository's Releases page, find the draft
   "Site kit - pictures and videos for the web page" and click fresing_site_kit.zip.
2. Unzip it into Downloads, next to the folder of your first kit (9 Nov): right-click the zip >
   Extract All... > Extract. The kit takes evo.step, openarm.step and farmbot.step from that first
   kit's "models" folder; thor.step, ceb_press.step, iea15_offshore.step and iea15_onshore.step
   come with this kit.
3. Close Fresing Render. Open the new folder "Fresing site kit" and double-click
   "Make site pictures.bat". A black window works out the expected time (a few seconds), then
   the Fresing start window opens (see "The start window" below).
4. Choose and click Start. Expected: about 4 hours on the RTX 3090 at 100 % load (the start
   window shows the time for your choices). A small status window shows the model, how far it
   is, the load, the temperature and when it should be done; Pause and Stop are there.
   Keep the black window open; the PC stays awake. One model that fails does not stop the
   others: the black window and log.txt say why.
5. If the run stopped (PC restarted, window closed, Stop): double-click the .bat again. The start
   window says "Continue the run of <date> (<n> of <m> done)": leave it ticked and click Start -
   only the pictures and clips that are missing are made.
6. When it is done, the "output" folder opens with site_pictures_<date>.zip in it, and the contact
   sheet opens in your browser (all pictures and clips on one page: have a look).
7. Upload: on the same draft release page click Edit (the pencil), drag site_pictures_<date>.zip
   onto "Attach binaries by dropping them here", wait until it is uploaded, then click
   "Save draft" (not Publish). Tell the lead chat: "site pictures uploaded".

The start window
----------------
- Graphics card load (40-100 %): below 100 % the kit pauses after every frame, so the card works
  that share of the time (70 % = it rests 30 % of the time): cooler and quieter, the run takes
  longer (at 70 % about 1.4 x). The expected time changes as you move the slider.
- Max. temperature (Off, 70-85 C): read from the card (nvidia-smi, no admin rights). When the card
  is at or above it, the next frame waits until the card is 3 C cooler.
- Quiet hours: from - to (for example 22:00 to 07:00) with their own load and max. temperature
  (for example 60 % and 70 C); outside them the load above. The expected time counts both.
- Models: untick the ones you do not want this time. A model whose STEP file is missing is
  unticked and skipped.
- Start: Now, or At a time (the PC stays awake until then).
- When done: Nothing, Sleep or Shut down. A 60-second countdown with Cancel comes first.
  After Stop nothing happens.
- Load, temperature, quiet hours and When done are kept as your standard for the next run - also
  in a newly downloaded kit (they live in %LOCALAPPDATA%\Fresing Render\site_kit.json).
  "Back to standard" puts the kit's own settings back: 100 %, no temperature limit, no quiet
  hours, nothing when done.
- If the start window cannot open, the black window asks for the start time instead and uses
  your saved standard.

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
- "Stopped": double-click the .bat again and keep "Continue the run" ticked (step 5).
- Otherwise: upload output\log.txt to the draft release instead (step 7).
