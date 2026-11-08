# 0048 – The owner's demo program with a face mill and a chamfer mill

**Who:** worker · **Status:** open – can start · **Branch:** none (no code change)
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

- [ ] Owner's four answers used.
- [ ] Build: no "T… is not in the tool list", no soft-limit and no unknown-code warnings (way-cover warnings from
      0037 problem 3 may stay; say so).
- [ ] Tool tip against the program within 0.05 mm on sampled frames, for each of the three tools.
- [ ] Milled block: facing depth, pocket/hole/contour depths as in 0037, chamfer width on 2 edges within 0.1 mm; chips
      change with the tool type (face mill, end mill, chamfer).
- [ ] Saved, opened again in a new session: tool list, step, start scene, chips all there.
- [ ] 4 small CPU check pictures (start, after facing, after T2, end) sent to the owner, not committed.
- [ ] Given back in the session: the project file and the new `fresing_demo.ngc`, plus numbered steps for his PC
      (Update to 0.2.36+, open the project, Build animation, a short test render, then the render queue).
- [ ] Report filled in (numbers only), app problems listed for the lead; `TASKS.md` updated; nothing else pushed.

## Not in this task

App code (problems found become follow-up tasks for the lead). Tool-change animation (0041). Coolant (0042).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What was done:**

**Checked:**

**Problems in the app found on the way (for the lead):**

**Open points:**
