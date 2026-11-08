FRESING SITE PICTURES - pictures and a video for the web page
=============================================================

Makes the pictures and the short video for https://smholte.github.io/CAD-render-animation/
with the Fresing Render installed on this PC (on the graphics card, Final quality).

What you need
-------------
- Fresing Render installed (Install.bat). Nothing else.
- The STEP files of the models listed in models.ini (download links in the chat / in models.ini).

Steps
-----
1. Unzip "Fresing site pictures kit.zip" anywhere, e.g. in Downloads.
   You get a folder with "Make site pictures.bat", models.ini and this file.
2. Make a folder "models" in it (or double-click "Make site pictures.bat" once: it makes the
   folder and opens it).
3. Put the STEP files in "models" and give them the names from models.ini
   (when renaming, type only the first part, e.g. evo - Windows keeps the .step):
   evo.step, openarm.step, farmbot.step (thor.step and ceb_press.step come with this kit)
   (right-click the file > Rename). A model you do not have is skipped with a note.
4. Close Fresing Render if it is open: the pictures then get all of the graphics card's memory.
5. Double-click "Make site pictures.bat". A black window shows each step.
   It takes about 5 to 15 minutes per model, the video about 15 minutes more.
6. When it is done, the "output" folder opens and the contact sheet opens in your browser:
   all pictures on one page. Look at them.
7. Send "Fresing site pictures.zip" (in the output folder) in the chat. If it is over 30 MB,
   send the files in output\send in two messages instead.

Changing a picture
------------------
Open models.ini in Notepad: each model has a few lines (light look, surroundings, camera
views, captions). Change one, save, double-click the .bat again. The meaning of every line
is at the top of models.ini.
The project of each model is saved in output\full\<model>.blend: open it in Fresing Render
(File > Open) to change things by hand and render from the app instead.

If something goes wrong
-----------------------
- "Fresing Render is not installed on this PC": run Install.bat first.
- "file not found": the name in "models" differs from models.ini (file = ...).
- "no graphics card found": the window says so at the start; it still works, but very slowly.
- Otherwise: send output\log.txt in the chat.
