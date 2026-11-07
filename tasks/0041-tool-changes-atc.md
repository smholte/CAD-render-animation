# 0041 – Tool changes: manual change and ATC, animated from the program

**Who:** worker · **Status:** open – after 0040 · **Branch:** `task/0041-tool-changes-atc`
**Started by:** lead chat, 7 Nov 2026 (owner accepted: 2B-ii – the operator's hand as an optional choice in the
animation set-up; 2C-ii split – this is part 2 after 0040; pause at a manual change short by default and adjustable)
**Area:** Machining lane + G-code – `core/gcode.py` / `blender/gcode.py` (M6 handling, timing), `animation.py`
(step length), `ui_gcode.py` (changer set-up), `core/tools.py` / `blender/tools.py` from 0040 (pockets); tests; guide
**Model:** Opus · effort High

## Goal

Every M6 in the program is animated by itself. On a machine without a changer: the head goes to the change
position, a short pause, the tool is swapped (optionally by an operator's hand). On a machine with an ATC: all tools
sit visibly in their pockets from the first frame, and at each M6 the machine moves to the changer, the changer
moves, the old tool goes back into its pocket and the new one comes out.

## Background

- 0026 already plays a saved motion sequence for the changer at each M6 and hides the carousel part of the loaded
  tool (`tasks/0026-gcode-motion.md`). 0040 adds the tool list with a place per tool (spindle / pocket / bench) and
  makes every tool cut.
- The owner's new Fresing machine has an ATC; the older, smaller one has none – both must work.

## What to build

1. **Machine type** in 4 Motion > CNC machine: "Manual tool change" or "Automatic tool changer (ATC)".
2. **Manual change at M6:**
   - Head moves to a change position (set in the set-up: machine coordinates, or "stay where it is" / "Z up only").
   - **Pause, short by default: 1 s; slider 0–5 s** in the G-code step ("Tool change pause"). The owner finds a
     long pause boring in a video.
   - Old tool disappears, new one appears (quick fade or a cut), optional caption "Tool change: T3 Ø50 face mill"
     (tick box, uses the existing caption look from 0018).
   - **Optional operator's hand** (tick box "Show hand" in the G-code step, off by default): a simple app-made
     gloved hand (own design, no downloaded model) reaches in, takes the old tool out of the spindle, puts the new
     one in, leaves. Its timing fits inside the pause; if the pause is too short for it, the pause grows to the
     hand's minimum and the step's Details say so.
3. **ATC set-up:**
   - Pockets: pick the carousel/rack parts or click positions; number them; the tool list's place field (0040)
     links tools to pockets. Pockets follow the carousel when it turns.
   - The changer's motion: the existing saved motion sequence (0026), plus for a carousel "turn to pocket N" made
     by the app (the carousel's rotate joint turns the shortest way to the needed pocket).
   - Tool change position (machine coordinates).
4. **ATC at M6:** move to the change position → carousel turns to the old tool's pocket → old tool into its pocket →
   carousel turns to the new tool's pocket → new tool into the spindle → back to the program. Tools needed by the
   program are visible in their pockets from frame 1; an empty pocket stays empty; the tool in the spindle is not
   also shown in its pocket. Time per change: from the motion's own speeds, with a slider "Changer speed"
   (slower / real / faster) for the video.
5. **Timing:** the step's length includes all changes; "Fit into" (0026) still hits its length (changes shortened
   proportionally, with a minimum). Cutting stays exactly on the program between changes.
6. Tooltips on every control; user guide chapter "Tool changes" with pictures (manual, ATC); PC-check line.

## Done when

- [ ] Manual change: pause default 1 s, slider 0–5 s works; caption optional; tool swapped at the right frame.
- [ ] Hand: optional, off by default, looks clean in a still; fits in the pause or lengthens it with a note.
- [ ] ATC on a test changer (carousel with 8 pockets, 4 tools): every tool visible in its pocket from frame 1, the
      right pocket comes round each time, old tool back in its own pocket, new tool in the spindle; checked frame by
      frame at each change in a test.
- [ ] "Fit into" still exact with changes; tool tip on the program path between changes within 0.01 mm.
- [ ] Old projects (0026 changer sequence, no pockets) open and play as before.
- [ ] Tooltips, guide, pictures, PC-check line; tests; GitHub green; merged and released.
- [ ] Report filled in; `TASKS.md` updated.

## Not in this task

- Tool list, shapes and cutting (0040). Air (0039), coolant (0042).
- Tool length measuring (probe) animation; pallet changers – possible later ideas, not now.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
