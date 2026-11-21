# 0269 – Study (findings + design only): Fresing Viewer – a stand-alone viewer for STEP (and more) that works and looks like Fresing Render's exported 3D page, with a round trip to Fresing Render through ToolBox

**Who:** worker · **Status:** open · **Branch:** `task/0269-fresing-viewer-study` (findings only, `[skip ci]`)
**Started by:** lead, 21 Nov 2026 (owner 16:59–17:09: "a viewer that opens a STEP file directly – yes, but the exported
3D web viewer from Fresing Render stays its own offline file with all functions included"; "a ToolBox tool, with its own
licence"; "I want to keep the same working and looks as the exported 3D viewer"; round trip: pictures, videos and a
baked 3D page all come back; this lead builds it, with ToolBox integration like Fresing Render's; its own page with a
direct button to Fresing Render and back, other tools in a fold-down; formats: STEP and Fresing Render's own 3D page
first, then IGES, STL / 3MF / OBJ, glTF / GLB – "try to keep measuring and other functions for the other formats")
· **Model:** Opus · effort High
**Area:** only `tasks/0269-fresing-viewer-study.md` (this report) and `tasks/img/0269_*` (small pictures); a throw-away
prototype on the branch is allowed (never merged). No app code, no `site/`.

## Goal

The owner and the lead get a clear plan for **Fresing Viewer** before anything is built: what it is, how it opens each
format, how it stays the same as the exported 3D page, how it talks to Fresing Render through ToolBox, where it lives,
its licence, and 3–6 build tasks in order with sizes.

## Background

- **The exported 3D page** (Web 3D lane, `fresing_render/web/fr_page.js`, `fr_player.js`, `core/web3d.py`): one
  offline HTML file per model with baked light, motion, settings menu, part tools (click a part, measure points /
  planes / Ø / centre to centre), slice by face or X / Y / Z (0218), measuring labels + edges (0219), Film (0252), phone
  layout (0179). It stays as it is: the Viewer is a separate tool.
- **ToolBox** (`smholte/ToolBox`, `smholte/toolbox-format`, MIT): tools on one PC hand files to each other through a
  `Toolbox` folder (manifests, inboxes, jobs). Fresing Render already has its inbox (`core/toolbox.py`,
  `blender/toolbox_inbox.py`) and the House Planner round trip (0114, 0217) – the model for this round trip. The
  ToolBox lead planned a `view-step` step after its router: this Viewer replaces / fills that – read their task list.
- **House Planner** (https://smholte.github.io/house-planner/) is a browser app that already writes to and reads from
  the Toolbox folder (PC Chrome / Edge) – the closest example of a web tool in ToolBox.
- **Licence:** the Viewer has its own licence (owner). The exported page's player code is the owner's own (no outside
  code was ever accepted), so it may be reused under the Viewer's licence – say how to share it without two copies
  drifting apart (a small shared package, or the Viewer as the source the app copies, or …).
- **Never** the Fresing 400 or anything of the owner's employer as a sample.

## Questions to answer

1. **Formats, in the owner's order:** STEP (AP203 / 214 / 242: assembly tree, names, colours) and **Fresing Render's
   own 3D page** (open its model in the Viewer with its looks and motion) first; then IGES; STL / 3MF / OBJ; glTF / GLB.
   For each: reader (e.g. OpenCascade compiled to WebAssembly – occt-import-js, opencascade.js – its licence, size,
   load time; three.js loaders for meshes), what is lost (exact faces, units, assembly, colours).
2. **Measuring and the other tools on every format:** on exact CAD (STEP / IGES) – true faces, planes, cylinders; on
   meshes – fitted planes / cylinders, edges from angles; what works, what is approximate, how the page says so.
3. **Same working and look as the exported page:** which parts of `fr_page.js` / `fr_player.js` carry over, what is
   new (file open, assembly tree, big-file progress), and how both stay in step.
4. **Speed and size:** a 2,000-part STEP of ~80 MB (use an openly licensed one, e.g. the Thor STEP built by
   `tools/a4_to_step.py`, or the EGR-like public GrabCAD class of model) – time to first picture and memory on the web
   machine; the Viewer page's own size.
5. **Round trip through ToolBox:** "Send to Fresing Render" → which job (model + settings: a still, a turntable, a
   video, a baked 3D page) → Fresing Render does it → **pictures, videos and the baked 3D page** come back and show in
   the Viewer. Which toolbox-format messages are new (a format change goes to the ToolBox lead through the lead post –
   list it, do not send it); what the Viewer needs from Fresing Render's inbox.
6. **Where it lives and runs:** its own public repository (name proposal), a page on GitHub Pages now
   (later perhaps viewer.fresing.nl), works offline after the first visit (installable page?), Chrome / Edge / Firefox
   / Safari and phone – what works where (the Toolbox folder needs the File System Access API: which browsers).
7. **Its page and links:** a landing page like Fresing Render's (0267 style: light, mono labels, numbered cards),
   direct buttons Fresing Render ↔ Fresing Viewer, "More tools" fold-down (House Planner); the app mark (brand rule:
   F + lowercase initial – "Fv"? check the Brand Specification's rule and say it needs the owner's and the Fresing
   lead's OK).
8. **Task split:** 3–6 build tasks in order, each with model · effort, what it delivers, what it waits for.

## Done when

- [ ] Report with answers 1–8, a table of formats × functions (works / approximate / not), measured numbers, sizes
- [ ] Proposals that need the owner marked **Owner decides** (repository name, licence, app mark, browsers)
- [ ] Nothing merged to `main` except this file and its pictures (lead merges the report or the worker pushes it with
      `[skip ci]`)

## Not in this task

Building the Viewer; changing toolbox-format (only a list); the landing page (0267); the exported 3D page.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
