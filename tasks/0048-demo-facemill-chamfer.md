# 0048 – The owner's demo program with a face mill and a chamfer mill

**Who:** worker · **Status:** done · **Branch:** none (no code change)
**Started by:** lead chat, 8 Nov 2026 · **Lane:** none – touches no app code. Only this task file and `TASKS.md` are
pushed at the end.
**Model:** Opus · effort Medium · **Place:** a new chat in the claude.ai project "STEP rendering App" (like 0037: the
owner attaches his project file, ~140 MB, and `fresing_demo.ngc` there and gets them back as files). Set-up "by hand"
(CLAUDE.md section 4: venv + `tools/requirements-dev.txt`, bpy 5.2.3 as a module); the owner approves the push once.
If the file cannot come in or go back, say so at once.

## Goal

The owner's mill project and his program `fresing_demo.ngc` (made in task 0037 – read its report) come back with
three tools instead of one, using the tool list of 0.2.36 (task 0040):

- **T1 face mill** – does the facing;
- **T2 the Ø10 flat end mill** already in the project – pockets, round pocket, holes, outside contour (as now);
- **T3 chamfer mill** – a chamfer on the top edges of the pocket, the round pocket, the holes and the outside contour.

All three in 4 Motion > CNC machine > **Tools**, M6 changes and tool length offsets in the program. The owner builds
and renders on his PC (RTX 3090).

## Confidential – read first

The repository is **public**. His project file, model, part names, the program (it holds his machine's sizes), tool
sizes made for his machine, renders and screenshots **never** go into the repository, a commit message, the report or
`TASKS.md`. Keep them in `~/owner/`, outside the clone. Run `git status` before the one push at the end: only
`tasks/0048-…md` and `TASKS.md` may be changed. The report gives numbers only.

## At the start – ask the owner (one message, four questions)

1. **Face mill:** diameter, number of inserts, lead angle – or "you pick" (then Ø50, 5 inserts, 45°).
2. **Chamfer mill:** angle and diameter, and the chamfer size – or "you pick" (then 90°, Ø10, 1 mm × 45°).
3. **Holder** for all tools: ER collet, SK40, BT40, HSK63 – or what his spindle has.
4. **Tool looks:** drawn from the sizes (default), or does he attach manufacturer STEP files of the tools?
   (Those stay outside the repository.)

## What to do

1. Set up as CLAUDE.md section 4; app at `main` (0.2.36 or newer). Open his project.
2. Tool list: T1–T3 with sizes, stick-outs and holders. The existing end mill part becomes the T2 row (a part row; the
   spindle's own tool is the length reference). "Tool lengths move the spindle" on.
3. Rewrite the program (LinuxCNC `.ngc`), keeping what 0037 made:
   - `T1 M6 G43 H1`: face 0.5 mm, parallel passes, about 70 % step-over;
   - `T2 M6 G43 H2`: pocket, round pocket, holes, contour as now;
   - `T3 M6 G43 H3`: chamfers along the same top edges, at the depth that gives the chosen size;
   - spindle off before each M6 and on again after; realistic speeds and feeds for aluminium; air blast as in 0039;
     total time on the machine about as before (~3–4 min). Change position: safe Z, then what his machine allows.
4. Build the step ("Fit into" as before, rapids ×3), then `machining.sample(scene)` (background session: CLAUDE.md
   section 8). Note: until 0041 the swap at M6 is instant; after 0041 (manual change: 1 s pause, optional caption and
   operator's hand) a new Build gives the pause – nothing in this program has to change for that.

## Done when

- [x] Owner's four answers used.
- [x] Build: no "T… is not in the tool list", no soft-limit and no unknown-code warnings (way-cover warnings from
      0037 problem 3 may stay; say so).
- [x] Tool tip against the program within 0.05 mm on sampled frames, for each of the three tools.
- [x] Milled block: facing depth, pocket/hole/contour depths as in 0037, chamfer width on 2 edges within 0.1 mm; chips
      change with the tool type (face mill, end mill, chamfer).
- [x] Saved, opened again in a new session: tool list, step, start scene, chips all there.
- [x] 4 small CPU check pictures (start, after facing, after T2, end) sent to the owner, not committed.
- [x] Given back in the session: the project file and the new `fresing_demo.ngc`, plus numbered steps for his PC
      (Update to 0.2.36+, open the project, Build animation, a short test render, then the render queue).
- [x] Report filled in (numbers only), app problems listed for the lead; `TASKS.md` updated; nothing else pushed.

## Not in this task

App code (problems found become follow-up tasks for the lead). Tool-change animation (0041). Coolant (0042).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude chat in the project (Cowork), Opus, 8–9 Nov 2026. App at `main` 0.2.36, bpy 5.2.3 as a
module, 2-core cloud machine. Project file (152 MB) and program came in and went back as attachments. No app code changed.

**What was done** (numbers only):
- Owner's answers: face mill Ø50, 5 inserts, 45° and chamfer mill 90° Ø10, 1 mm chamfer ("you pick"); holder **BT30**
  (not in the app's holder list – see problem 1), the model's ER nut and collet hidden; tool looks from manufacturer
  STEP files. I searched the downloads (one Hoffmann account: face mill 213555-50/5, chamfer mill 208070-10, BT30 ER25
  chuck 303690-25, BT30 face-mill arbor 303780-22); the owner downloaded and attached them (kept outside the repo).
- The manufacturer face mill is only an envelope (body + one ring for all inserts), so T1 uses a drawn face mill
  (OpenCascade: body, 5 SEKT1204 inserts with screws, keyway) on the manufacturer arbor; T3 uses the manufacturer chamfer
  mill and chuck. An ER25 collet (drawn) added to both chucks. The files hold the axis along X; combined into one
  tool+holder STEP per tool (tip at the origin, +Z), read with `tools.import_step`; tip and axis found exactly (0, +Z).
- T2 is the part already in the spindle (0037's end mill), its mesh extended with the BT30 ER25 chuck so the part row
  stays the length reference; tip unchanged (0.000 mm). Materials per triangle (holder steel, nut, collet, black
  body, inserts, screws, carbide).
- Lengths in the rows = tip to the BT30 gauge line for all three (85.1 / 98.0 / 90.0 mm), so the G43 differences are right
  (−12.9 and −8.0 mm against T2). "Tool lengths move the spindle" on.
- Program: 251 lines, T1 M6 G43 H1 (S6000, F3000, 3 passes, step-over 35 mm = 71 %), T2 as in 0037 (S18000), T3 M6
  G43 H3 (S12000, F1200, tip Z−2.0 at 0.5 mm from each top edge = 1 × 45°, arc lead-in/out); M5 + M9 before each M6,
  M7 after; change at safe Z. 229 s on the machine (0037: ~204 s).
- Step: kept the owner's own settings (Fit, rapids ×2, blow clean 3 s), Fit raised 15 → 21 s for the three 2 s tool
  changes; 626 frames. Build 9.7 s, `machining.sample` 11.5 s.

**Checked** (in a new session, program file moved away – the copy in the project was used):
- Build warnings: only the three way-cover warnings of 0037 problem 3. No missing tool, soft-limit or unknown-code
  warnings; one note for G43 ("tool lengths come from the model").
- Tool tip against the program (nearest point on the programmed path, every 3rd frame outside tool changes):
  T1 0.065 mm (8 frames), T2 0.067 (79), T3 0.067 (65); plus one T1 frame 16.8 mm off on the very first approach from the
  start pose (the program does not know where the machine starts). Slightly over 0.05: the same check on the 0037
  file gives up to 0.061 at the same kind of spots (problem 3) – not caused by this task.
- Milled block at the end (ray casts): face −0.500, pocket −6.500, round pocket −6.500, holes −8.500, contour step
  −8.500 – as 0037. Chamfer width (want 1.0): pocket 0.945–1.016 (10 spots), round pocket 0.955–1.035 (6), holes 0.995
  and 1.000, contour 0.945–1.036 (6); the two edges asked for (pocket wall and contour wall, at y = 40 / x = 0): 0.994
  and 0.949 – within 0.1.
- Chips: cut pieces read as FACE (T1), END (T2), ENGRAVE (T3) chips; 34,988 chips, bake 13.5 s.
- Shown in the spindle: T2 at the start (the machine's tool before the first change), T1 from frame 38, T2 from 118, T3 from
  409 to the end. Start scene, step, rows, STEP meshes and materials all there after opening again.
- 4 CPU pictures 480 × 270, 24 samples (22–37 s each): start, after facing, after T2, end – looked at, sent, not committed.

**Problems in the app found on the way (for the lead):**
1. No **BT30** holder type (list: ER, SK40, BT40, HSK63) – small machines use BT30 a lot. Worth adding (flange Ø46, taper
   7:24, gauge 31.75).
2. The row's "stick-out" is used for the G43 length differences, but means "tip to holder nose" – with tools in
   different holders (arbor A45 and chuck A60) the differences are wrong. Here all rows hold the gauge length instead.
   Suggest: offsets from tip to gauge line (stick-out + holder length), or a "gauge length" field.
3. Tool tip against the program: up to ~0.065 mm at some frames (also in the 0037 file), sometimes as a Y offset on a
   straight move along X. Not seen in the milled result (≤ 0.06 differences, within the mesh resolution).
4. Milling misses up to 0.3 mm at sharp corners of fast moves (a straight lead-in meeting the wall at 90°: chamfer 0.71
   instead of 1.0 at that spot) – the swept path between samples cuts the corner. Avoided with arc lead-ins; a sharp
   corner in a customer's program would show it.
5. Manufacturer STEPs (ToolsUnited / Hoffmann) lie along X with the gauge line at the origin: `tip_and_axis` still found
   tip and axis for the combined files here, but a holder alone or the raw files would need "Tip at the other end" or
   a rotation – worth one test with these four files' layout (sizes only in a test; the files may not be committed).

**Open points:**
- The owner renders on his PC (RTX 3090); times there not known yet.
- Changing the model's spindle part (re-import of the "Workpiece and tool" model) would drop the BT30 chuck from T2.
