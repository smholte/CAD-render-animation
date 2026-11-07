# 0037 – The owner's old CNC mill: workpiece, end mill, G-code program and milling, set up in his project

**Who:** worker · **Model:** Opus · effort Medium · **Place:** a new chat in the claude.ai project "STEP rendering App"
(preferred, because the owner attaches his project file and gets the finished one back as a file; Claude Code on the web
is fine too if both work there – if the file cannot come in or go back, say so at once and the owner moves to a chat) · **Status:** done (7 Nov 2026) · **Branch:** none (no code change)
**Started by:** lead chat, 6 Nov 2026 · **Lane:** none – touches no app code. Only this task file and `TASKS.md` are
pushed at the end.

## Goal

The owner's own project of an older CNC mill of his (X, Y, Z, spindle, way covers and other joints already set up in
the app; no tool changer, no workpiece) comes back ready to render: a raw block on the table, an end mill in the spindle,
4 Motion > CNC machine and Milling set up with chips, a G-code program, and a "Run G-code program" step. He builds and
renders the video on his PC (RTX 3090). It is also the first test of tasks 0026 (G-code), 0027 (milling), 0028 (chips)
and 0034 (way covers) on a real machine of his.

## Confidential – read first

- The repository is **public**. The owner's project file, his model, part names, the G-code program made for his machine
  (it holds his machine's sizes), renders and screenshots **never** go into the repository, a commit message, the report
  or `TASKS.md`. Keep them in a folder **outside** the clone (e.g. `~/owner/`). Run `git status` before the one push at
  the end: only `tasks/0037-…md` and `TASKS.md` may be changed.
- The report gives numbers only (parts count, travel, times, check results) – no names from his model.

## At the start – ask the owner (one message, four questions)

1. **Block:** material (aluminium / steel / brass / plastic) and rough size in mm – or "you pick" (then: aluminium, sized
   to the table and the axes' travel with room to spare).
2. **Bit:** diameter and type – or "you pick" (then: one flat end mill, Ø6 or what suits the block). No tool changer: one
   tool, unless he wants a manual tool change (M6 with a pause, the tool in the spindle swapped).
3. **What to mill:** the default demo – face the top, a rectangular pocket with round corners, a round pocket with a
   helical entry, a few holes made by helical interpolation, a contour round the outside; "FRESING" engraved only if it
   is feasible with the chosen tool – or his own idea.
4. **His project file** attached: before attaching, update the app to 0.2.31 (Update now), open the project, File > Save,
   close the app; if the file is over about 30 MB, right-click it > Send to > Compressed (zipped) folder and attach the zip.
   Ask the file size if it does not attach.

If he is not there to answer, take the "you pick" answers and say so at the top of your reply.

## What to do

1. **Set up** as CLAUDE.md section 4 (venv with bpy 5.2.3 from `tools/requirements-dev.txt`, the extension from the
   clone, as `tests/` load it). The real Blender program is not needed. Open his file with the bpy module.
2. **Look at the machine:** which joints are X, Y, Z (4 Motion > CNC machine > Find the axes), the spindle, their limits
   (the travel), which joint moves the table, the way covers. If anything is unclear or looks wrong (an axis reversed,
   limits missing), ask him rather than guess; a problem in the app itself goes into the report (see 7).
3. **Add the block and the end mill as parts of the project.** Make them as a small STEP (OpenCascade, as the
   `tools/make_test_*.py` generators do) and bring them in with the app's own import into the existing project (a second
   model in one project is supported), so they are real model parts that Milling and the CNC panel accept. Put the block
   on the table (on a simple vise or clamps if it looks better), inside the travel, and make it move with whatever joint
   moves the table; put the end mill in the spindle nose with a sensible stick-out, moving with Z and turning with the
   spindle. Use the app's own functions (joints, members) – no hand-made Blender parenting the app does not know.
4. **CNC machine panel:** axes, spindle, tool, workpiece, work zero (top corner or top centre of the block), rapid speeds
   that suit an older mill (ask if unsure). **Milling:** workpiece + bit (the app recognises the bit type), **Chips**
   Realistic for the block's material.
5. **The G-code program** (LinuxCNC `.ngc`, the dialect the app reads; see 0026's report for what is supported): feeds
   and speeds that are right for the material and bit, depth per pass a real machinist would accept, safe heights,
   M3/M5, no move outside the axes' limits. About 1–3 minutes of machining; the step set to **Fit into** 30–60 s
   (owner can change it). Add the **Run G-code program** step in 6 Animation, Build.
6. **Check before giving it back:**
   - the step's warnings: no soft-limit or unsupported-code warnings;
   - the tool tip follows the program (as 0026's tests check it) on a few frames;
   - the block is cut where the program cuts (milling's result at the last frame), chips appear;
   - way covers move with their axis through the program;
   - save, reopen, still all there; the program copy is in the project;
   - three or four small CPU check pictures (e.g. 480 × 270, Draft) at the start, middle and end – look at them; send
     them to the owner with the result, do not commit them.
7. **Give back** in the chat: the project file (zipped if big) and the `.ngc`, plus numbered click steps for his PC:
   open the project, 6 Animation > Build & play, Time test, Render animation; what he should see; where the render goes.
   App problems found on the way (something that did not work on his machine, a missing button, a confusing message)
   go into the report as a list for the lead – **do not fix app code in this task**.
8. **Report** below (numbers only, no names), task to Done in `TASKS.md`, one push of those two files.

## Done when

- [ ] Owner has the project back with block, end mill, CNC machine, milling + chips, program and step; checks in 6 passed
- [ ] Click steps for his PC given; problems in the app listed for the lead
- [ ] Nothing of his in the repository (`git status` checked before the push); report filled in

## Not in this task

App code changes (lanes 0031/0035 wait; app problems found here become follow-up tasks); tool changers (his mill has none);
the app making toolpaths by itself (task 0029).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (Opus), 6–7 Nov 2026. App 0.2.31, bpy 5.2.3 as a module, 2-core cloud
machine. The owner's file came in and went back through the chat (attachment, 150 MB; zipping gains nothing, the
file is already compressed). No app code changed.

**What was done** (numbers only):
- Owner's answers: aluminium block, one Ø10 flat end mill (his choice), default demo; no engraving (Ø10 too big).
- Model: 697 objects, 21 joints; X, Y (table, moves the workpiece), Z and spindle were already picked in the CNC
  panel; travel ±205 / ±200 / ±100 mm; 7 way-cover sections follow the table axis. Work-zero shift left at
  (150, −80, 90) mm from earlier tries: reset to 0.
- Block 100 × 152.3 × 50 mm (fills the vise's open jaws, 18 mm above them) and a Ø10 × 72 mm 3-flute end mill
  (35° helix, 42 mm stick-out) made as one STEP with OpenCascade (outside the repository), brought in with Import
  STEP as a second model. Block added to the table joint, end mill to the spindle joint (so it moves with X and Z and
  turns); the model's own end mill (Ø12) hidden. Bit read as "Flat end mill Ø10.0 mm, 72 mm long".
- CNC machine: work zero top centre, rapids 4000 / 4000 / 2500 mm/min; spindle joint set to Motor (the step asked
  for it). Milling: block + bit, Chips Realistic, material read as aluminium from the name.
- Program (LinuxCNC, 187 lines, 3.4 min on the machine): face 0.5 mm, pocket 50 × 30 R6 × 6 deep (3 levels, helical
  entry), round pocket Ø30 × 6 (helical entry, 2 levels), 4 holes Ø14 × 8 by helical interpolation, outside contour
  1 mm per side × 8 deep, R10 corners; S18000, F700–2500. Step Run G-code program: Fit into 45 s, rapids ×3 →
  1,151 frames at 25 fps. Start pose: Z up 90 mm. New camera + saved scene "Milling close-up" as the start scene.

**Checked:**
- Step: no soft-limit or unknown-code warnings; only two way-cover warnings from the owner's own set-up (below).
- Tool tip against the program on every 7th frame: worst 0.038 mm (on a Ø20 circle).
- Cut depths read from the milled mesh: face −0.5, pocket −6.5, round pocket −6.5, holes −8.5, contour −8.5 mm, at
  the right frames (250 / 500 / 750 / 1000 / 1151). 13,657 chips. Way covers move with the table (86.5 mm at the
  end: 86.5 / 64.9 / 43.2 / 21.6 mm per side).
- Saved, opened again in a new session with the .ngc gone: set-up, step, start scene, motor, chips all there;
  program taken from the copy in the project.
- 4 CPU check pictures (480 × 270, 24 samples, 20–27 s each): start, pocket, round pocket, end – looked at,
  sent to the owner, not committed. Build: 5.4 s; reading the bit's path: 8 s; showing a milled frame: 1–7.5 s.

**Problems in the app found on the way (for the lead):**
1. **Crash (high priority): milling corrupts memory when it reads the bit path again.** Blender 5.2.3 corrupts its
   memory when an array ID property is given a NumPy array of a *different length* than it had
   (`scene["x"] = np.random.rand(250)` then `= np.random.rand(2000)` → "free(): invalid size" / "corrupted size vs.
   prev_size" a little later; same length, a list (`.tolist()`) or `del` first are fine). `machining.sample()` does
   exactly this (`item["fr_t"]`, `["fr_o"]`, `["fr_d"]`, `s["fr_wp_m"]`), and every new Build gives a slightly
   different sample count (1,928 ↔ 1,930 here), so on a real machine the first cut after a re-read crashed Blender
   4 times out of 4 (segfault or abort in the Manifold boolean, where the damage shows). Fix: `del` the keys before
   assigning (or `.tolist()`); test: sample twice with different lengths, then allocate. Work-around in the
   delivered file: no stored path (the first read on his PC creates the properties fresh, which is safe); a second
   Build that changes the count is still at risk until the fix is released.
2. Bit detection read the model's own fluted end mill (measured Ø12.06) as a flat Ø10.4; a cut with it would be too
   narrow. The plain helical Ø10 made here was read right.
3. Way covers: his machine has a cover on each side of the table on one axis; the panel holds one cover, and the
   section limits it wrote (7 sections, housing counts: 0, 33 … 200 mm) do not match the ratios he set by hand
   (1, 0.75, 0.5, 0.25 per side), so every Build warns "Way cover Section 1/2 … goes beyond its own limits". The
   motion itself is right. Suggest: several covers per axis (lane of 0035).
4. Picking the spindle in 4 Motion > CNC machine could tick Motor itself; now Build warns afterwards.
5. Import STEP of a second model re-laid the surroundings (hall moved ~0.3 m in X and Y, its high part ~0.36 m up).
6. Program path: `gcode_file` refuses the "//" relative prefix with a warning when set from Python (works anyway);
   a program picked in the file browser is stored absolute, so on another PC the copy in the project is used.
7. Scripts: in a background session nothing reads the milling path after Build (`mark_stale` only schedules in the
   UI) – call `machining.sample()`. Worth one line in CLAUDE.md section 8.

**Open points:**
- The owner builds and renders on his PC (RTX 3090); render times there not known yet.
- Until problem 1 is fixed: change the step's settings (Fit into, rapids) as little as possible; if Blender
  crashes after a change, open the file again – the path is then read fresh.

**Addendum 7 Nov 2026 (owner's PC):** the program ran without problems in the app. A queued 4K video (501 frames,
GPU OptiX, 16.3 s per frame, 2 h 16 min) rendered every frame, then Blender crashed while making the MP4 (at frame
77 of the video, "Microsoft C++ Exception"). The queue's runner reads the milling path again at its start ("Milling:
reading the motion of the bits"), with another sample count than the project had stored – problem 1 above.
Reproduced here: the project file + a new Build + `machining.sample()` without deleting first, then the queue's
`encode_mp4` of 120 4K frames → segfault 2 of 2; the same encode without the re-read worked. The frames on his PC are
fine: the owner got a stand-alone "Make video.bat" + `make_video.py` (Blender in the background, no project loaded,
same H.264 settings) to make the MP4 from them; tested on Linux with 120 frames at 4K, the .bat not tested on Windows.
Retrying the failed job with Start queue would reuse the frames but read the path again (same crash risk).
Also seen: the sequencer keeps every 4K frame in its cache while encoding (+33 MB per frame up to the 4 GB cache
limit, measured here), inside the runner that still holds the whole project – fine on 47 GB, worth a look for 4K on
smaller PCs.

