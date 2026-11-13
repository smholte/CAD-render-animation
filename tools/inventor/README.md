# Motion from Inventor and Fusion (draft, task 0104)

**What this is:** two small export scripts that write the motion you set up in Inventor or Fusion (constraints, joints,
their limits) to a file next to the STEP file: `<assembly name>.fresing.json`. A later version of Fresing Render reads
that file at import and makes the joints for you. **The app does not read it yet** – these drafts are here so you can
try the Inventor side on your PC first (task 0104 report, "Proposed tasks").

Not part of the app, not run by any automatic test. Nothing in your assembly is changed: the scripts only read.

| File | For |
| --- | --- |
| `FresingMotionExport.iLogicVb` | Inventor (an iLogic rule) |
| `fusion/FresingMotionExport/` | Fusion (a script: the folder with the `.py` and `.manifest`) |
| `prototype/` | how the app would use the file (tested here with Blender, no Inventor): `make_example.py` writes an invented test assembly + its file, `motion_plan.py` works out the joints, `try_in_blender.py` makes them in the app and checks they move right; `example.fresing.json` is what the file looks like |

Only try it on an assembly **you made yourself for this** (a hinge, a slide, a cylinder) – never a client's or your
employer's model, and never the Fresing 400.

## Inventor 2027: run the rule

1. On github.com/smholte/CAD-render-animation open `tools/inventor/FresingMotionExport.iLogicVb`, click **Download
   raw file** (the arrow at the top right of the file) and save it in a folder of your own, for example
   `Documents\Fresing\iLogic`.
2. In Inventor open your test assembly (`.iam`). Save it once if it is new.
3. **Manage** tab → **iLogic** panel → **iLogic Browser**. The iLogic Browser opens at the side.
4. In the iLogic Browser click the tab **External Rules**. Right-click in it → **Add External Rule** → pick
   `FresingMotionExport.iLogicVb`.
   *If Inventor says the folder is not trusted or not an external rule folder:* **Tools** → **iLogic Configuration** →
   add the folder under **External Rule Directories**, OK, and try again.
5. Right-click **FresingMotionExport** in the list → **Run Rule**.
6. It asks **"Also save the STEP file now?"** → **Yes** (the STEP and the motion file then always match).
7. **What you should see:** a message "Written: …\\<assembly>.fresing.json – N parts and subassemblies, N constraints,
   N joints", and next to the `.iam` two new files: `<assembly>.stp` and `<assembly>.fresing.json`.
   If it lists "things that could not be read", that is fine for a draft: send the list.
8. Send back the `.fresing.json` (it holds only names, positions and directions of your test parts) and, if it failed,
   a screenshot of the message.

A red error window instead of the message means the draft has a mistake: send a screenshot of the whole window.

## Fusion: run the script

1. Download the folder `tools/inventor/fusion/FresingMotionExport` (both files) into a folder of your own, keeping
   the folder name `FresingMotionExport`.
2. In Fusion open the design. **Utilities** tab → **Add-Ins** → **Scripts and Add-Ins** (or Shift+S).
3. Click the green **+** next to **My Scripts** → pick the `FresingMotionExport` folder.
4. Select **FresingMotionExport** → **Run**. Pick a folder for the file, then **Yes** for the STEP file too.
5. **What you should see:** "Written: …\\<design>.fresing.json – N occurrences, N joints."

## A test assembly to build in Inventor (10–20 minutes)

Generic parts, any sizes. Each line is one thing the app should turn into a joint (the invented one in
`prototype/make_example.py` has the same pieces):

1. **Frame** – a plate, grounded.
2. **Door on a hinge** – Mate the door's hole axis to the frame's hole axis, Mate the door's bottom face on the
   frame's lug; an **Angle** between a frame face and the door face with **Use limits** 0° … 100°.
3. **Hinge pin** – Insert into the door's eye (it only spins: the app lets it ride with the door).
4. **Carriage on a rail** – Mate bottom on rail top, Flush one side; Mate its end face to a stop with an offset and
   **Use limits** (for example 0 … 340 mm).
5. **Lid on the carriage** – an assembly **Joint**, Rotational, with limits.
6. **Arm** as a subassembly (rigid) on a post: Mate axis-axis + Mate face; Angle with limits. Inside the arm
   subassembly a part that slides along it (with limits).
7. **Hydraulic cylinder** – a subassembly (set it **Flexible**) of barrel + rod, Mate axis-axis inside; Insert the
   barrel's eye on a frame lug and the rod's eye on the arm.
8. **Two gears** – each Inserted on a shaft, plus a **Motion** constraint (Rotation) between them with a ratio.
9. **Two bolts** – Inserted in holes of the plate.

Then: set the door's angle to 30° (edit Angle:1), run the rule again, send the file too – it shows whether the app
reads Inventor's angle the same way round.
