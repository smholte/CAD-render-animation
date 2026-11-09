# 0059 – Test tour: one project the owner opens to see every function work, and an automatic run through it

**Who:** worker · **Status:** running · **Branch:** `task/0059-test-tour`
**Started by:** lead chat, 9 Nov 2026 (owner: "make it easier/faster for me to check the functions – a test Blender
file to open and see the functions work, and a test running through it")
**Lane:** Quality & delivery + PC check – new files `blender/tour.py`, `blender/ops_tour.py`, `ui_tour.py` (its own
panel or sub-panel), `pccheck/tour.py` (the automatic run); `pccheck/ops.py` / `checks.py` only to add the mode
"Tour" and reuse the report code; new generic test models in `tests/data/` if needed; guide chapter "Test tour";
CLAUDE.md (one rule, see 6)
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0042 coolant (Machining lane): do not change machining, chips, air, coolant, G-code or
toolchange code – only call them. If a function needs a fix to show properly, write it as an open point.

## Why

The owner tests on his own PC (Windows 11, RTX 3090) but has little time. His open list: cylinders, mechanisms,
decals, chips, video finishing, labels, way covers, G-code, air, tool library, the manual-change hand on a BT30
holder, the ATC carousel, cut faces and raw stock, the 0046 materials and Wear, two copies of one STEP, model update,
render queue. Today each needs his own model and set-up. The PC check Full tests functions but is made for numbers,
not for looking at a function and saying "yes, that's right".

## What to build

1. **"Make test tour project"** (button with tooltip, next to the PC check in the app): builds
   `Documents\Fresing Render\Test tour\Test tour <version>.blend` fresh from generic test models in the repository
   (the repository is public: only generic models – `tests/data/*.step` and the PC check's own scenes; new ones if
   needed, e.g. a small mill with a BT30 spindle and an 8-pocket carousel). Built for the installed version, so it is
   never out of date. Takes at most ~2 minutes; a progress line.
2. **Tour panel** in that project: numbered stops (about 20–30), each with
   - a title and one or two lines "what you should see" (plain words, no code terms);
   - **Go** – sets everything up: opens the saved scene, camera, frame range, plays or scrubs to the right frame,
     selects the part, opens the right panel;
   - **OK / Problem** and a short note field;
   - stops grouped: Look (materials, Wear, cut faces + raw stock, decals, painted faces, surroundings, light looks),
     Motion (joints, stacked joints, cylinders by stroke, mechanisms, way covers, two copies of one STEP, model update
     A → B), Machining (G-code run, three tools with M6 + G43, manual change with the hand on a **BT30 holder**, ATC
     carousel, chips, air blast), Output (stills, turntable, video finishing: title/end cards, captions, watermark,
     labels, render queue still + video, 1:1 / 9:16).
   - **Copy results**: one short text (version, PC, per stop OK/Problem + note) to the clipboard and a `.txt` next to
     the project, to paste into the lead chat.
3. **Automatic run ("Tour" mode of the PC check, also a button in the tour panel):** goes through every stop
   unattended, renders each one (Cycles GPU still and/or a short EEVEE clip, small sizes), checks what can be checked
   by numbers (the same kind of checks as the PC check: positions, frame counts, files made) and writes the PC check
   style HTML report with a picture or clip per stop, the "what you should see" text and OK/FAILED for the number
   checks. Time on the web machine in the report; target ≤ 15 min on the owner's PC. The owner can start it, walk
   away, and later look at the report and tick OK/Problem in the tour panel.
4. **Tests:** the tour project builds on the web machine; every stop's Go works (no errors, the expected scene/frame
   is set); the automatic run finishes with pictures for every stop (CPU, tiny sizes in CI); Copy results text.
5. **Guide chapter "Test tour"** with a picture of the tour panel; tooltips on every button.
6. **Keep it current:** add a rule to CLAUDE.md (definition of done): every new visible function adds its tour stop
   (one entry in `blender/tour.py`). Make adding a stop one small entry (title, text, set-up function, optional
   number check). Coolant (0042, running at the same time) and hoses/drag chains (0058) add theirs in their own tasks
   – leave a note in their task files' Done-when lists.

## Done when

- [ ] Make test tour project → a working tour project in ≤ ~2 min; all stops with Go, OK/Problem, note.
- [ ] Copy results; automatic run with the HTML report (picture or clip per stop).
- [ ] Tests as in 4; GitHub green.
- [ ] Guide chapter, tooltips, CLAUDE.md rule, notes in 0042 and 0058.
- [ ] Merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in, with the list of stops; `TASKS.md`: 0059 done.

## Not in this task

New app functions or fixes (write problems found as open points). Coolant's and hoses' own stops (their tasks).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
