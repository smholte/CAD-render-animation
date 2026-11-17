# 0185 – Look C wide: the spotlight with the Lesson panel dark or bright, shown with more of the app

**Who:** worker · **Status:** done (17 Nov 2026) – lead publishes the page · **Branch:** `task/0185-look-c-wide`, made from
`claude/practical-heisenberg-jm99vr` (0168's branch, **never merged**; a session branch `claude/…` is fine – say which
in the report)
**Started by:** lead chat, 17 Nov 2026 (owner after his 0168 pick) · **Model:** Sonnet · effort Medium · **Place:**
Claude Code on the web, environment "CAD-render-animation"
**Area (Learning lane, prototype branch only):** `fresing_render/blender/lesson.py`, `tools/lesson_clips_app.py`,
`tools/lesson_looks_page.py` and a new page folder `tasks/0185_page/` – **all on the branch only**. On `main` only this
file (report) and at most two small stills `tasks/img/0185_*.jpg`.
**Do not edit on `main`:** any app code, tests, `TASKS.md` rows of other tasks. This task starts **no test run**.

## Goal

The owner picked button look **C** (spotlight: the rest of the side panel dimmed, the button clear with a thin outline)
in 0168. In 0168's clip C also dims the **Lesson panel** (the step's text and *Do it for me*), and the clips were cropped
tight round the button. He wants to compare **C with the Lesson panel dark** against **C with the Lesson panel bright**,
each showing **much more of the app** in one picture, so he can judge the whole screen as a user sees it.

## Background

- 0168 (report in `tasks/0168-highlight-looks-2.md`): looks behind `lesson.set_look(kind, key)`, colour from
  `lesson.set_colour`, clock per picture (`begin_clip`, `set_clock`, `end_clip`), clips by `tools/lesson_clips_app.py`
  (real app, UI scale 2.0, 25 pictures/s, 3 s loops, H.264), page by `tools/lesson_looks_page.py`. Look **M** already
  keeps the Lesson panel clear (two markers on the Lesson panel: header + last button) – reuse that for "bright".
- Owner's pick 17 Nov: `button C + D, section 5 + 4, part 3 + 1, colour Fresing Green` (0062 brief, lead note 17 Nov).
- Rules kept: test crane only (`test_crane_a.step`), no owner models (CLAUDE.md section 6), Fresing Green `#479B29`,
  calm pulse, the look on **one** button of a joined pair, 0168's crane steps.

## What to make

1. **C as two variants** behind `set_look`: `C` = as in 0168 (Lesson panel dimmed too) and `C_bright` (same dimming
   strength on the rest of the side panel, the Lesson panel left fully clear and *Do it for me* in its normal colour).
   Nothing else changes between them.
2. **Wide clips:** the **whole app window** (3D view with the crane, the whole side panel incl. the Lesson panel and the
   text card) – no tight crop. Same 25 pictures/s, 3 s seamless loops, UI scale 2.0 grab, H.264 (`-preset veryfast`,
   `yuv420p`, `+faststart`), scaled to about 1600 px wide for the page. Make them for **two steps**: 0168's button step
   (*Add rotate joint*, joined to *Add slide joint*) and one where the target button sits **near the Lesson panel**
   (so the difference is easy to see). Per step: `C`, `C_bright` and, for reference, **`D`** (the owner's second
   button pick) in the same wide frame. Fresing Green only. = 6 clips + a poster still each.
3. **Page** `tasks/0185_page/index.html` (+ `clips/`), self-made like 0168's (Fresing palette, no outside links):
   per step a row with **C dark | C bright** side by side, large, D below; a toggle "one at a time" that shows one clip
   at full width with buttons / keys ← → to flip between C dark, C bright and D (same play position). A pick box at the
   bottom with a Copy line: `0185 pick: C dark` / `C bright` (optional note field). Remember the choice in `localStorage`
   inside try/catch. Folder ≤ ~15 MB.
4. **Cost** of `C_bright` per side-panel redraw against `C` (software GL, as in 0168).

## How to push (no test run)

- Code, tools and the page folder on the branch, pushed **once at the end** with **`[skip ci]`** (never merged).
- This file's report (+ at most two small stills `tasks/img/0185_*.jpg`, < 600 KB together) in a separate push to `main`
  touching only `tasks/` (starts no run); check that `main` really contains the commit. If the session may only push
  its own branch, say so in one line "WAITING FOR YOU:" after pushing the branch.

## Done when

- [ ] `C` and `C_bright` behind `set_look`; nothing else of the 0168 looks changed.
- [ ] 6 wide clips (2 steps × C, C_bright, D), whole app window, 3 s seamless at 25/s, Fresing Green, + posters.
- [ ] `tasks/0185_page/` on the branch: side by side + one-at-a-time flip, Copy line; opened in headless Chromium,
      a screenshot looked at; size reported.
- [ ] `tools/lesson_proto_app.py` and `tools/lesson_looks_app.py` still pass on the branch (run locally).
- [ ] Report: "In short (for the owner)", the page's path on the branch, size, the cost, branch name; report on `main`.

## For the lead after this task

Publish `tasks/0185_page/` from the branch as a private claude.ai artifact (multi-file publish), give the owner the link;
his "0185 pick" line goes into the 0062 brief (lead note 17 Nov – highlight looks) and the progress note.

## Not in this task

Any other look, colour or group; the highlight hook itself (0062); app code on `main`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker, Sonnet), 17 Nov 2026. Branch **`task/0185-look-c-wide`** (made from
`claude/practical-heisenberg-jm99vr`, 0168's session branch; pushed with `[skip ci]`, never merged; commit `7e8dd05`).
Page: **`tasks/0185_page/index.html`** on that branch (+ `clips/`, `fonts/`).

### In short (for the owner)

One page, two steps (*Add rotate joint* and *Add slide joint*), each with **C dark** (Lesson panel dimmed, as in 0168) and
**C bright** (Lesson panel fully clear) side by side, D underneath. "One at a time" shows one clip big; keys 1/2/3 or
← → flip between C dark, C bright, D at the same play position. Pick box at the bottom, Copy line `0185 pick: C dark` /
`C bright` (+ optional note), remembered in the browser. Fresing Green only. Stills: `tasks/img/0185_step3_C_dark.jpg`,
`0185_step3_C_bright.jpg`.
Honest notes: (1) the picture shows the **whole window** at UI scale **0.7** on a 2000 x 1900 window (scaled to 1600 wide):
at scale 2.0 the Lesson panel and the Motion buttons are never on screen together – the Lesson panel sits ~900 px above them,
below the 1 Import panel and above 2 Structure / 3 Looks. So text is small; the Lesson panel is the one at the top of the side
panel. (2) The brief's "a step whose button is near the Lesson panel" does not exist in the crane lesson (steps 1-2 are done
by the time the lesson is shown); both clips are at the Motion section, at the same distance. Step 3 is 0168's step.
(3) The Lesson step's text card in the 3D view is not dimmed in either variant (it lives in the view, not the side panel).

### What changed (branch only)

| File | What |
| --- | --- |
| `fresing_render/blender/lesson.py` | `C_bright` in `BUTTON_LOOKS` / `_BUTTON_DRAW` (`_look_c_bright`): C's dimming (0.62, same fade) with holes for the button and the Lesson panel's band (the two markers 0168 added for look M). `C` unchanged, all other looks unchanged |
| `tools/lesson_clips_wide.py` | new: whole app window, any step (`LESSON_STEP`), looks (`LESSON_LOOKS`), scrolls the side panel until the Lesson markers and the button are both in view, 75 pictures at 25/s, H.264 veryfast CRF 27 yuv420p faststart, scaled to 1600 px wide, poster |
| `tools/lesson_wide_page.py` | new: builds `tasks/0185_page/` |
| `tasks/0185_page/` | 6 clips + 6 posters + page + fonts |

### Tested and measured

Web session, 4 cores, software GL, Blender 5.2.3 under xvfb, test crane; two Blender runs at once, ~2 min each, 0 failed
checks. Six clips are 3 s loops, 78 drawn redraws each.
- **Page folder 1.6 MB** (limit ~15). Headless Chromium: no script errors; side by side looked at (screenshot); the flip key
  switched to "Showing: C bright"; a pick plus note gave `0185 pick: C bright – ok`. Videos not played in headless Chromium
  (posters shown); the clips themselves are the usual H.264.
- **Cost per side-panel redraw** (drawing only, Python side, 4 cores shared): step 3 – C 0.172 ms, **C_bright 0.166 ms**, D 0.041;
  step 4 – C 0.126, C_bright 0.166, D 0.040. C_bright is the same as C within noise (one more rectangle pair, two more pixel
  searches that the read does anyway for look M).
- `tools/lesson_proto_app.py`: 0 failed checks; `tools/lesson_looks_app.py`: 12 of 12 OK (both on the branch, scale 1.0).
- No subagents, no GitHub run (`[skip ci]`). Runs: none.

### Open points

- Lead: publish `tasks/0185_page/` from the branch as a private artifact (multi-file publish); the owner's "0185 pick" goes into
  the 0062 brief and the progress note.
- If the owner wants bigger text: a taller step with the Lesson panel closer needs the side panel's sections 2/3 folded; not done.
