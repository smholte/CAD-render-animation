# 0133 – Highlight looks to compare (lesson study, owner's answer 1 to study 0123)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0133-highlight-looks` (made from
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

- [ ] 5–6 button looks, 2–3 section markers, 3 part looks behind one switch on the branch; the aligned-buttons case
      shows one button.
- [ ] `tools/lesson_proto_app.py` still passes on the branch (16/16 or more), run locally.
- [ ] Comparison sheets + one clip per button look in `tasks/img/`; cost per look in the report.
- [ ] Report: a short "In short (for the owner)" with the sheets' file names and one line per look; branch pushed
      with `[skip ci]`; report pushed to `main`.

## Not in this task

Choosing the look (owner); Show me / Play on, Build it yourself, lessons, guide panel, `fresing://` (the build tasks
after 0062); any change on `main`'s app code; the side-panel overhaul (0062).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
