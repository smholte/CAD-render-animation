# 0133 – Highlight looks to compare (lesson study, owner's answer 1 to study 0123)

**Who:** worker · **Status:** done (study – the owner picks a look) · **Branch:** `task/0133-highlight-looks` (made from
`task/0123-learning-study`, **never merged**)
**Started by:** lead chat, 15 Nov 2026 (owner: "yes push") · **Model:** Sonnet · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Learning lane, prototype branch only):** `fresing_render/blender/lesson.py` and `tools/lesson_proto_app.py` on
the branch; on `main` only this file and `tasks/img/0133_*`.
**Do not edit on `main`:** any app code, tests, `TASKS.md` rows of other tasks. Four code tasks are running (0126,
0128, 0130, 0132): this study must start **no test run** (see "How to push").

## Goal

The owner sees several highlight looks side by side – moving, the way they will look in the app – and picks one (or a
mix). The lesson build task (step 3 of 0123's order) then builds only the chosen look.

## Background

- Study 0123 made a working prototype on branch `task/0123-learning-study`: the target button is marked through a
  stand-in layout, found again in the side panel's pixels (≈ 3.6 ms per redraw), and drawn as a **pulsing magenta
  frame**; a closed section gets a **dot** in its header; parts glow in the 3D view with a text card beside them.
  Pictures: `tasks/img/0123_show_me_pointing.jpg`, `0123_closed_section.jpg`. Costs and open points: tasks/0123
  report.
- **Owner, 15 Nov (answer 1):** not the magenta frame – make **several versions so he can compare** before one is
  chosen. (Answers 2–6 are for the build task, not here.)
- The prototype already knows the button's rectangle in pixels, so looks that draw *around* the rectangle (dim the
  rest, an arrow at its side) are as cheap as the frame. 0123 said greying out "needs more work per button" – that was
  for greying inside Blender's layout; an overlay over the region outside the rectangle does not.
- Colours: the Fresing palette in `site/style.css` (Fresing Green `#479B29`, Green Bright `#5CBF37`, Deep Charcoal
  `#1A2027`) and Blender's own theme (its selection blue). The owner's Blender uses the default dark theme.

## What to make

1. **Button looks, 5–6 versions** (one switch in the prototype, e.g. a `LOOK` setting in `lesson.py`), for example:
   A soft glow/halo in Fresing Green that breathes slowly · B thin steady outline + a small arrow or numbered badge
   at the panel's edge pointing at it · C spotlight: the rest of the side panel dimmed, the target clear · D a bar on
   the button's left edge + its label tinted · E corner brackets that close in once, then stay · F a version of your
   own choosing. Keep the pulse calm (no blinking faster than about 1 per second).
2. **Closed-section marker, 2–3 versions** to go with them (the dot today; e.g. the header tinted, an arrow at the
   fold triangle).
3. **Part highlight on the model, 3 versions** (today's glow; an outline only; the other parts faded/X-ray) – same
   text card.
4. Fix 0123's open point while at it: the look must sit on **one** button when two are aligned in a row (*Add rotate
   joint* / *Add slide joint*).

## What the owner gets

- One **comparison sheet** per group (button / section / part): the looks side by side on the same crane step, each
  labelled with its letter – `tasks/img/0133_buttons.jpg`, `0133_sections.jpg`, `0133_parts.jpg`.
- A **short clip per button look** (2–3 s loop, small GIF or MP4 under ~1 MB each) so the pulse can be judged:
  `tasks/img/0133_look_A.gif` …
- Per look in the report: cost per side-panel redraw (ms, measured on the web machine, software GL), and whether it
  stayed readable on the light and the dark part of the panel.
- Test crane only (`test_crane_a.step`); no owner models (CLAUDE.md section 6).

## How to push (no test run)

- The prototype code: commit on `task/0133-highlight-looks` and push **once at the end** with **`[skip ci]`** in the
  commit message (the branch is never merged; `main`'s tests do not apply to it).
- This task file's report and the pictures: a separate push to `main` touching only `tasks/` (starts no run), then
  check that `main` really contains your commit.

## Done when

- [x] 5–6 button looks, 2–3 section markers, 3 part looks behind one switch on the branch; the aligned-buttons case
      shows one button.
- [x] `tools/lesson_proto_app.py` still passes on the branch (16/16 or more), run locally.
- [x] Comparison sheets + one clip per button look in `tasks/img/`; cost per look in the report.
- [x] Report: a short "In short (for the owner)" with the sheets' file names and one line per look; branch pushed
      with `[skip ci]`; report pushed to `main`.

## Not in this task

Choosing the look (owner); Show me / Play on, Build it yourself, lessons, guide panel, `fresing://` (the build tasks
after 0062); any change on `main`'s app code; the side-panel overhaul (0062).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 15 Nov 2026. Code on branch **`task/0133-highlight-looks`** (commit
401905a, pushed with `[skip ci]`, never merged); on `main` only this file and `tasks/img/0133_*`.

### In short (for the owner)

Pick one letter for the button, one number for a closed section and one for the part (or a mix: "B, but in A's glow").
All looks are on the test crane, in the real app:

- **`tasks/img/0133_buttons.jpg`** – the six button looks, each on two buttons: *Product studio* (beside the blue,
  selected *White, endless*) and *Add rotate joint* (joined to *Add slide joint*). Clips, 3 s each:
  `tasks/img/0133_look_A.gif` … `0133_look_F.gif`.
  - **A** soft green glow round the button, breathes slowly (one breath in 2 s). The calmest; at the low point of the
    breath it is the faintest of the six.
  - **B** thin steady green outline, a small arrow at the panel's edge that moves 2–3 px, and the step's number in the
    button's icon place. The clearest to read; the number links the button to the card ("3 of 11").
  - **C** spotlight: the rest of the side panel dimmed, the button clear with a thin outline. The strongest; it also
    dims the Lesson panel (its *Do it for me* button stays usable, but grey).
  - **D** green bar on the button's left edge and the button tinted green, breathing. Quiet, but the white label on
    green is a little less sharp.
  - **E** four corner brackets that close in once (0.7 s), then stay. Calm after the first second; clear on both
    buttons.
  - **F** Blender's own blue outline with a light that runs round it once in 2 s. Looks "native", but beside the blue
    selected button (step 2) it reads like a second selected button – the least clear there.
- **`tasks/img/0133_sections.jpg`** – a closed section that holds the next button: **1** green dot with a ring that
  grows from it, **2** the whole header tinted green, **3** a ring round the fold triangle and a green "Open" at the
  header's end.
- **`tasks/img/0133_parts.jpg`** – the part on the model, same text card: **1** glow (see-through green), **2** outline
  (the part's edges in green, bold where seen, faint through other parts), **3** the rest faded (everything greyed, the
  part clear in its own colour).
- **Fixed:** with two buttons joined in a row, the look now sits on the one button only (*Add rotate joint*; 116 of 292
  px, checked).

### What changed (on the branch only)

| File | What |
| --- | --- |
| `fresing_render/blender/lesson.py` | `BUTTON_LOOKS` A–F, `SECTION_LOOKS` 1–3, `PART_LOOKS` 1–3 behind one switch `set_look(kind, key)` (or `FR_LESSON_LOOK` / `FR_LESSON_SECTION` / `FR_LESSON_PART`); Fresing palette from `site/style.css`, F in Blender's selection blue; the magenta marker icons painted over with the button's own colour (a small green ▶ in their place); `button_box` finds the button's own edges (the line between two joined buttons is 1 px wide – 0123's search needed 2 px); part outline edges (> 30° or open) and normals worked out once per mesh |
| `tools/lesson_looks_app.py` | new: the real-app run that shows every look on steps 2, 3 and 7, takes the pictures and clips and measures the costs (12 checks) |
| `tools/lesson_looks_sheets.py` | new: the comparison sheets and GIFs from those pictures (ImageMagick) |
| `tools/lesson_proto_app.py` | two more checks: one button of an aligned pair, no drawing error |

### Tested and measured

Machine: **Claude Code web session, 4 cores, no graphics card**; real Blender 5.2.3 under xvfb (software OpenGL),
window 1600 × 1000, side panel 292 × 824 px, 3D view 1311 × 878 px, UI scale 1.0; **test crane**
(`test_crane_a.step`, draft).

- `tools/lesson_proto_app.py`: **16 of 16 checks OK** (0123's script had 14 `check` calls – its report said 16 –, now
  16 with the two new ones). `tools/lesson_looks_app.py`: **12 of 12 OK**. `pytest tests/test_lesson_proto.py`: 4
  passed.
- **Cost per side-panel redraw**, Python side (the GPU work runs later in the driver, not in these numbers):

| Look | Drawing the look | Readable on the grey panel / grey button / beside the blue button |
| --- | --- | --- |
| A glow | 0.21 ms | yes / yes / yes – faintest at the low point of the breath |
| B outline + arrow + number | 0.52 ms (the number's text) | yes / yes / yes |
| C spotlight | 0.16 ms | yes / yes / yes – dims everything else, Lesson panel too |
| D bar + tint | 0.04 ms | yes / yes / yes – label a little softer on green |
| E brackets | 0.11 ms | yes / yes / yes |
| F blue + running light | 0.30 ms | yes / yes / **poor** – blue beside Blender's blue "selected" |
| Section 1 / 2 / 3 | 0.12 / 0.08 / 0.47 ms | all clear on the dark header |

  Finding the button (pixels read, markers, button edges): **3.4–3.5 ms** per redraw, as 0123 (3.3 ms); my first
  edge search converted the whole picture and cost 6.0 ms – now only the row and column it walks.
  (The panel has no white parts near these targets: "light" here = the lighter grey button and the blue one.)
- **Part looks**, drawing only: 1 glow 0.23 ms, 2 outline 0.36 ms, 3 rest faded 0.69 ms per 3D-view redraw; the whole
  3D view redraws in 63–71 ms in software OpenGL with or without them (66 ms without a lesson) – the looks add nothing
  measurable here. On the owner's RTX 3090: expected a few ms per view redraw, not measured.
- Clips: 20 screen grabs over 2.8–3.2 s each, at their real times (≈ 6.5 pictures/s here – the grab is slow, the
  app's own pulse runs smoother), 22–91 KB per GIF.
- GitHub runs: **none** (branch `[skip ci]`, this push touches only `tasks/`). No subagents; no independent review
  (study prototype, nothing on `main`'s app code).

### Open points / follow-up tasks

- **The owner picks** a button look, a section marker and a part look; the build task keeps only those (and drops
  `set_look`, the other looks and the sheet tools).
- "Done" is green (0.25, 0.85, 0.35) – close to Fresing Green Bright: with looks A–E "pointing" and "done" differ only a
  little in colour. The build task should show "done" by a tick or text too, not by colour alone.
- The header marker (0123's way to find a closed section) is an extra icon in the header: it pushes the header's text
  right – probably why, at the default width, "5 Scene & Render" runs into its own header text ("Solid colour"). The 0062 hook
  should mark headers without adding width.
- Part look 3 clears the 3D view's depth in its draw handler (so the part shows on top); fine in all pictures here,
  to be checked with gizmos on the owner's PC once chosen.
- C dims the Lesson panel too; if C is chosen, keep the Lesson panel clear (it is always at the top: one more marker).
- Not tried on the owner's PC (graphics card, Windows scaling) – the build task's PC-check line and tour stop will.
- `TASKS.md` row of 0133 not touched (the brief allows only this file and `tasks/img/0133_*` on `main`): the lead moves
  it to Done.
