# 0037 – The owner's old CNC mill: workpiece, end mill, G-code program and milling, set up in his project

**Who:** worker · **Model:** Opus · effort Medium · **Place:** a new chat in the claude.ai project "STEP rendering App"
(not Claude Code on the web: the owner attaches his project file and gets the finished one back as a file in the chat;
both need the chat's file upload and file sending) · **Status:** open – can start · **Branch:** none (no code change)
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

**Chat / date:**

**What was done** (numbers only):

**Checked:**

**Problems in the app found on the way (for the lead):**

**Open points:**
