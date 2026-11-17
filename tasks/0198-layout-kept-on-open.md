# 0198 – Opening a tour or demo project keeps the app's layout, Live preview keeps its last choice, the Fresing panel is always easy to find again

**Who:** worker · **Status:** open – **start when 0193 is merged** · **Branch:** `task/0198-layout-kept-on-open`
**Started by:** lead chat, 17 Nov 2026 22:30 (owner's wishes) · **Lane:** Start & learn (new)
**Area:** `app_template/fresing_render/__init__.py` (`_after_load`, `_tidy_screens`), `blender/ops_tour.py` and
`blender/ops_demo.py` (only where they open a file), `blender/ops_main.py` (`FRESING_OT_preview` only), a new
`blender/ui_header.py` (the header button); additive: the extension's preferences in `props.py`, `core/functions.py`
entries, guide, tour stop, PC-check line
**Model:** Sonnet · effort Medium (stuck: Opus · Medium) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The owner (17 Nov, his words): *"I want the UI not to go away when opening demo projects or the different projects
from the test tour. I want the live preview to stay on or stay off (option last selected) when switching between the
different test tour projects. If someone accidentally closes the Fresing menu it might be hard to find again."*

So: whatever project the app opens, the window looks like the app (Fresing tab open, Blender's toolbar folded);
Live preview is on or off as the user last chose it while he moves through the tour and the demo; and a hidden side
panel comes back with one obvious click.

## Background (lead, read in the code 17 Nov)

- `app_template/fresing_render/__init__.py`: `_after_load` shows the Fresing tab **only for a new project**
  (`not bpy.data.filepath`); `_tidy_screens` (side panel on, toolbar off, Fresing tab, shading, clip) runs at the
  factory start-up. A project opened with File > Open, by the tour (`ops_tour.py` lines ~191 and ~255:
  `bpy.ops.wm.open_mainfile(filepath=path)`, default *Load UI*) or by the demo (`ops_demo.py` ~245) brings **its own
  saved window layout** – and the tour sets and the demo are made in a background Blender, so they carry Blender's
  default screens (toolbar shown, side panel hidden or on another tab). That is what the owner sees.
- Live preview = `FRESING_OT_preview` in `ops_main.py`: it flips the first 3D view's shading between SOLID and
  RENDERED (+ draft quality, world, 64 preview samples). The shading lives in the screen, so a new file with its own UI
  is always SOLID; `_tidy_screens` also forces SOLID.
- Task 0193 (running now) sets the views' clip end/start from the scene's reach in `surroundings.py`, `handlers.py`,
  `demo.py`, `ops_import.py`. Start this task **after 0193 is merged**, and do not overwrite its clip values (the
  template's fixed `clip_end = 1000` must not undo 0193 on a load).
- 0062 point 3 (start-up layout for every kind of project) **moves into this task**; 0062 keeps "sections 1–7 start
  folded".

## What to build

1. **The app's layout on every load** in the app (not in background, not in the PC check / self-test / kit runs):
   side panel shown at the Fresing tab, Blender's toolbar folded – for a new project, File > Open (own project, older
   version's project), a tour set, the demo, Revert, after Update now, and the start-up file. Decide by test whether
   the tour and demo should open with *Load UI* off (the current window layout stays – the simplest way to keep both
   the layout and Live preview) or with their own UI tidied after loading; File > Open of the user's own project keeps
   his own view (camera, shading, sizes) – only the side panel, the Fresing tab and the toolbar are put right. Mind
   the timer `_show_fresing_tab` already uses (the region exists only after the first redraw).
2. **Live preview keeps its last choice** while moving through the test tour (Go to a stop in another set, Next,
   Open test tour project) and when opening / making the demo: the choice is stored in the extension's preferences
   (survives a restart) and applied after the file is open, with the same draft settings the button sets. A user's own
   project opens as it was saved. The button's label shows the state ("Live preview: on" as today).
3. **The Fresing panel can always be found again:**
   - a small **"Fresing"** button (Fresing icon if one exists, else a clear text button) at the right of the 3D view's
     header that shows the side panel and switches to the Fresing tab – visible only when the side panel is hidden or
     another tab is open, so it never clutters;
   - **View > Sidebar** and **N** keep working; check what else can make the tab disappear in Blender 5.2.3 (the side
     panel dragged to zero width, a tab hidden through the region's right-click menu, a different workspace tab at the
     top, a maximised area with Ctrl+Space) and cover each one the header button cannot reach – say in the report
     which cases exist and what brings the panel back;
   - 0199 adds a "Fresing" menu in the top bar with "Show the Fresing panel": make the operator here
     (`fresing.show_panel`, tooltip) so 0199 only adds the menu line.
4. **The usual parts of a visible change** (CLAUDE.md): tooltips; guide (the side panel chapter: "If the Fresing panel
   is gone" with the steps); function-list entries; a test-tour stop (hide the side panel, then click the header
   button); a PC-check line if something here can break on Windows (load + layout).

## Done when

- [ ] A real-app test (fresh settings folder, Blender 5.2.3 under xvfb): opening a tour set made in a background
      Blender, the demo project, an own project saved with the side panel hidden and the toolbar shown, and a project
      saved by 0.2.140 – each shows the Fresing tab with the toolbar folded; the user's own project keeps its camera
      view and shading.
- [ ] Live preview on → Go to a stop in another tour set → still on; off → stays off; the same after a restart of the
      app; an own project opens as saved (test).
- [ ] Side panel hidden (N) → the header button shows and brings the Fresing tab back; each other "gone" case found
      has its way back (test or written check).
- [ ] 0193's clip values survive a load (test with a project whose scene reach is > 1 km).
- [ ] Tooltips, guide section, function entries, tour stop, PC-check line (or why none); screenshots of the header
      and the panel looked at.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`
      (0199 set to "open – can start").

## Not in this task

The top-bar "Fresing" menu, the welcome and What's new (0199). Folded sections, workspaces, panel layout (0062). The
far clip (0193).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
