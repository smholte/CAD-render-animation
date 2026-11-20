# 0244 – Prototype (findings only): steps and their functions look different in the side panel

**Who:** worker · **Status:** open – can start (findings only: no merge of app code, does not count as a code task) ·
**Branch:** the session's own; prototype code pushed with `[skip ci]`, never merged; report + pictures to `main` as
`tasks/` files only
**Started by:** lead chat, 20 Nov 2026 21:55 (owner 21:02, with a screenshot: "need to easily see where a step ends and a
new one starts, now all functions look alike and the 1–8 tabs"; look picked by the owner 21:02–21:51 from six rounds of
mock-ups) · **Lane:** Start & learn (prototype; the full change is a later task) · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Show the owner, in the real app, his chosen side-panel look for **step 4 Motion and step 5 Scene & Render**: a step and
the functions inside it (Cylinders, Mechanisms … Tracks and belts; Sea, Hall …) must look different, and an **open**
function must stand apart from the step's own buttons. Find out what Blender allows, what it costs per redraw, and write
the plan for the full change of all steps.

## The look the owner chose (version "C2 + green arrows everywhere")

Today every function is a Blender sub-panel (`bl_parent_id = "FRESING_PT_motion"` etc.) and Blender draws it with almost
the same box as the step, so the side panel reads as one long list. The owner wants:

| Part | Look |
| --- | --- |
| **Step title row** (1–8) | grey bar, a little **lighter** than today's panel header; a **3 px Fresing Green edge on the left** (`#479B29`, `highlight.GREEN`); white text; its own icon as now; state on the right as now |
| **Closed function row** | **darker** than the step, **indented** (~10 px); a **green › fold arrow**; its normal icon in white; **white text**; state on the right in grey as now ("1 cylinder", "none") |
| **Open function** | its content in a **grey frame** (1 px, about `#555`) with a **3 px Fresing Green line on the left**; a **green ⌄ arrow**; title and icon **white**; body as dark as a closed row |
| **A fold inside a function** (e.g. Cylinders' *Set-up*) | green › / ⌄ arrow, **no frame**; its body indented with a thin dashed grey line on its left |
| Text | **white everywhere** – the owner tried green titles and turned them down |

The owner turned down: green titles, a green-tinted step bar ("a bit too much green"), lighter greys for the whole
window, number badges, a "More in step 4" divider line. Keep the dark greys. Mock-up colours used (a guide, not a
rule – match the real Blender theme): window `#1d1d1d`, step bar `#3d3d3d`, function row / open body `#262626`, frame
`#555`, buttons `#545454`, green arrows a lighter green (`#8cc46f`) for contrast on dark grey – try both that and `#479B29`.

## What to find out and build (on your branch only)

1. **Functions drawn inside the step.** Draw the functions of steps 4 and 5 as folds inside the step's own body
   instead of separate sub-panels – reuse each sub-panel's own `draw()` with the fold's body as its layout (a stand-in
   `self`, as `highlight.py`'s `_L` does), so no function's code is copied. Try both: (a) Blender's `layout.panel()`
   folds and (b) the app's own fold rows (a BoolProperty + an emboss-free toggle with a custom icon, like `ui.fold`).
   Report which can carry a **green arrow** (Blender draws its own arrow for `layout.panel()` – can it be hidden or
   replaced?), which keeps open / closed per project, and which allows **one function open at a time**.
2. **Greys from Blender's colour settings** – which theme fields (`panelcolors.header` / `back` / `sub_back`,
   `wcol_box`, …) give the lighter step bar and the darker function rows; set them only in the app's own Blender
   config. What else in the window changes with them (3D view header, menus, Blender's own panels in **Show all of
   Blender** / Full access)? A screenshot of each.
3. **Green arrows and icons** – custom icons (`bpy.utils.previews`), sharp at 100 % and 200 % UI scale.
4. **The frame and the green left line** – the frame with `layout.box()`; the green line and the step's green edge:
   Blender cannot colour a single row, so try (a) the lesson highlight's way (`highlight.py`: a marker icon of one
   exact colour, a draw handler of the side panel finds it in the region's pixels and paints over it) and (b) anything
   cheaper you find. **Measure** the side panel's redraw time with and without it: 0, 1 and 3 open functions, 1920 and
   2560 px, scrolling and while a joint is dragged. The highlight today runs only while a lesson points – this would run
   whenever a function is open, so the cost decides. Show the **fallback** without overlay too (box + green arrows only).
5. **One function open at a time** – both ways (on / off), as a prototype preference; which feels better with the
   long step 4 list.
6. **What the full change touches** – list every place that finds a function by its panel id or Blender's panel
   state, with a plan for each: `panels.py` (`open_to()`, `PARENT`), `highlight.py` / the lessons (0230), favourites,
   declutter and hides (`usage.py`, 0181 / 0208 / 0236), `core/functions.py` anchors, the section tabs and
   "Keep sections as I left them", the PC-check lines, the test-tour stops, real-app tests, the guide's pictures. And
   which tasks it must not run beside (all side-panel lanes), the order with 0241 → 0222 packages B and C and the
   "top of the side panel too full" study (TASKS.md "Problems found"), and its size (one task, or one per step).

## Deliver

- Pictures in `tasks/img/0244/` (to `main` as `tasks/` files): the **whole window** and a panel close-up at **1920 and
  2560 px** – today's look; the new look with step 4 open, Cylinders open with Set-up open, the rest closed, step 5
  closed and open; the fallback without the green line; Show all of Blender with the new greys. Use public test models
  only (the test crane of the tour) – never the demo vessel's equipment, never the Fresing 400.
- A short page `tasks/0244_page/index.html` (like 0200's) with the pictures side by side for the owner to pick; the lead
  publishes it.
- The report: the answers to 1–6, the timings, the owner's choices left (arrow green shade, one-open-at-a-time default,
  overlay or fallback), and the brief-ready plan for the full task.

## Done when

- [ ] Prototype code on the branch, pushed with `[skip ci]` on every push, **never merged**; no version change
- [ ] Pictures + page + report on `main` as `tasks/` files only (a `tasks/`-only push starts no run)
- [ ] Timings measured on the 4-core web machine with the real Blender (name it), at both widths
- [ ] Report filled in below

## Not in this task

Merging app code; changing any step other than 4 and 5; the top of the side panel (workspace row, favourites,
coaching) – that is the later study; Blender's side-panel tabs (0222 package C).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
