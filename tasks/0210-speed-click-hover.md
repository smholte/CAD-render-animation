# 0210 – Faster click and first hover on big models (study 0195's A6 + A7)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0210-speed-click-hover`
**Started by:** lead chat, 18 Nov 2026 (owner: "more tasks?"; study 0195's quick wins)
· **Lane:** Pick & hover (`blender/hover.py`) + the selection handler (`blender/handlers.py` `_on_select`-part only,
`blender/logic.py` / `blender/tree.py` read-only unless a cache needs a hook)
**Area:** `fresing_render/blender/hover.py`, the selection part of `fresing_render/blender/handlers.py`, a small cache
(new code may live in `logic.py`), their tests; `tools/measure_demo.py` only to add a step if needed
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Two measured delays on the cable-lay demo (study 0195, app 0.2.146, 4-core web machine) get smaller, nothing else
changes:
- **A6 – a click to select:** 150–180 ms per click, of which 13–19 ms is `logic.Tree(scene)` built again at every
  selection change (`handlers.py`, Subassembly pick mode) even when nothing in the model changed.
- **A7 – the first hover in a picker** (Add joint / Set axis, cylinders, double arm): 70–115 ms over a big part,
  because the face table of the part under the mouse is built at the first hover; ~4 ms once it exists.

## Background

Read 0195's report rows A6 and A7 and its measuring tool (`tools/measure_demo.py`). The rest of the click time is
Blender's own (0195: 1,156 empties) – not in this task. `logic.Tree` walks the whole scene (CLAUDE.md section 8: make
it once per operation, never inside a loop).

## What to build

1. **A6:** keep the last `logic.Tree` and reuse it while the model has not changed. Decide what "changed" means safely
   (objects added / removed / re-parented, a model update, undo / redo, a project opened, groups or structure edited):
   a cheap key (for example the scene's object count + a counter the app bumps on its own structure changes + undo /
   load handlers that drop the cache) – the worker proposes, the design goes in the task file. Wrong is worse than
   slow: when unsure, build it again. Never key on `as_pointer()` (CLAUDE.md section 8).
2. **A7:** build the face table of the visible model parts (or of the parts in view, if that is much cheaper) when a
   picker starts, in one go, so the first hover costs what the later ones do. If starting a picker on the demo then
   takes noticeably longer (> ~0.3 s), build it in small pieces on a timer instead and say so in the report.
3. Measure before / after on the made demo with `tools/measure_demo.py` (add a "first hover" and a "click to select"
   step if missing), same machine, same model; numbers in the report.

## Done when

- [ ] Tests: the cached tree is dropped after each change listed in 1 (one test per kind of change, failing before the
      drop was added); subassembly picking still selects the same parts as before on the test crane and the demo; the
      first hover returns the same face / axis as a later one.
- [ ] Before / after numbers (click, first hover, picker start) on the made demo, machine named.
- [ ] Nothing the owner sees changes → no guide, tour or PC-check line needed; say so in the report. Version raised,
      CHANGELOG ("faster click and first hover on big models"), full GitHub run green, merged, main contains the commit.

## Not in this task

Blender's own selection cost; A3 (side panel draw) – 0195 asks for a new measurement first; the other 0195 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**
