# 0182 – Lifting plans L1: the checks and the load-chart format in plain Python

**Who:** worker · **Status:** open – can start · **Branch:** `task/0182-lifting-checks`
**Started by:** lead chat, 17 Nov 2026 (study 0180, task L1; owner's answers the same day) · **Lane:** Lifting (new files
only: `fresing_render/core/lifting.py`, `tests/test_lifting.py`, `tests/test_lifting_independent.py`; nothing in `blender/`)
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The core every later Lifting task uses: the nine checks C1–C9 of study 0180 (crane use %, sling legs, shackle / sling
WLL, outrigger + mat pressure, crawler tracks, forklift load centre, offshore DAF, upending), the load-chart format with
its lookup and validation, units and the status words – pure Python, no Blender, proven by the study's worked cases.

## Read first

`tasks/0180-lifting-plans-study.md`: section 3 (the checks, formulas, **the worked test cases – use exactly these**, the
checks the app must not do), section 4 (chart format, sample mark), section 8 (the words), section 9 row L1.

## The owner's answers (17 Nov 2026, section 10 of the study)

1. **Radius between two chart rows: the next longer radius** (never interpolate; a radius past the last row = no
   capacity, red). Keep the chart's data model open for interpolation later, but do not offer it.
2. **Amber limits: 75 % crane use, 90 % rigging and ground** – defaults the planner can change per plan. Green below,
   amber up to 100 %, red above.
3. **Lift categories: BS 7121 (basic / intermediate / complex) by default, ASME P30.1 (standard / critical) selectable**
   – the plan stores which system; L1 gives the names and the plain rules the study lists, nothing more.
4. **Offshore DAF: a preset from the public DNV-OS-H205 (2014) table, editable**, with the note "check against the
   current DNV-ST-N001". (Questions 4 and 6 – onshore first, PDF + web page – go with the study's recommendation.)

## Rules

- Every result carries its inputs, the formula's name and a status (`ok` / `amber` / `red` / `not_checked`), so the
  panel and the printed plan can show how it was worked out. Units SI inside (kg, m, N, Pa), conversions at the edges.
- The words of section 8: never "safe" or "approved"; "within the entered chart / limits"; the competent-person line is
  a constant the plan uses on every page.
- Built-in sample charts are not in this task (L2/L3); the tests use small invented charts.
- **An independent tester** (a subagent that did not write `lifting.py`) writes `tests/test_lifting_independent.py`
  from section 3 and this brief only; send its findings back to the author (CLAUDE.md section 2).
- No tour stop, PC-check line or guide section yet (nothing the owner can see; the first visible Lifting task, L4,
  adds them). Say so in the report.

## Done when

- [ ] C1–C9 + chart lookup / validation (rising radius, falling capacity, units) + status + limits in `core/lifting.py`.
- [ ] Every worked case of section 3 passes to the study's digits; the independent tests pass.
- [ ] Full GitHub run green (put `[full run]` in the last code commit – no version raise, nothing visible); merged to
      `main`; report filled in; `TASKS.md`.

## Not in this task

Blender code, panels, equipment files and makers (L2/L3), the hang solver (L5), the printed plan (L7).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
