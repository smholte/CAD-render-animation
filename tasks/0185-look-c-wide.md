# 0185 – Look C wide: the spotlight with the Lesson panel dark or bright, shown with more of the app

**Who:** worker · **Status:** open – can start · **Branch:** `task/0185-look-c-wide`, made from
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
