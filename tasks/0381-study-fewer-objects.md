# 0381 – Study (findings + measurements): big models with fewer Blender objects

**Who:** worker · **Status:** done – findings · **Branch:** `claude/cad-render-animation-0381-7028s9` (branch only, `[skip ci]`)
**Started by:** lead, 28 Nov 2026 (0326's open point; the owner's machines are big) · **Model:** Opus · effort High
**Area:** none on `main` – findings, measurements and throw-away prototypes on the branch.

## Goal

Know what the app would gain – and what it would break – by giving Blender far fewer objects on big models.

## Background

- 0326: a joint drag on the stress model (11,228 parts) now costs ~16–21 ms per step; **~15 ms is Blender's own
  per-update cost on ~11,500 objects** (also playback's ~14 ms per frame).
- 0327: clash memory is mostly every part's matrix at every moment. 0366: model build stages. 0324 / 0345: model
  update reuses meshes / keeps objects.
- The app assumes one object per part in many places (picking, hover, looks per part, paint per face, welds, joints,
  clash, web export, place / copy, the tree).

## Options to measure (on the stress model, web machine; note the owner's 24-core PC where it matters)

1. **Instances for repeated parts** (bolts, nuts, washers – `core/fasteners.py` knows them): collection instances or
   geometry-node instances – objects saved, what still works (pick, look, hide, clash, web export).
2. **One object per rigid body** for parts that never move relative to each other (joined mesh + a face → part map
   for picking, looks and paint) – the biggest cut; what every system would need.
3. **Hidden / far parts** left out of the depsgraph while dragging or playing.
4. Blender's own settings that scale with object count (relations, drivers, handlers per object).

For each: per-update ms (drag, playback), import, model update, save size, open time, render, web export, clash
memory, and the list of systems that break or need work. Prototype in a script, not in the app.

## Report

A ranked table (gain vs. risk vs. size of work), the recommended path, and build tasks by lane with model · effort –
for the owner to decide. Must say how it fits the import popup's speed options (0341: one object per sub-assembly).

## Done when

- [x] Measurements for at least options 1 and 2; the ranked table and the build tasks
- [x] Report on the branch, `[skip ci]`; TASKS.md row "done – findings"


---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 28 Nov 2026. Findings only: no app code, no test run.
Branch `claude/cad-render-animation-0381-7028s9` (the session's branch name; the brief said `task/0381-…`).

### In short (for the owner)

1. **The time goes to the number of objects, not to triangles or to what moves.** Every scene update, Blender walks
   *all* the work items of *all* objects (~1.5–2 µs per object here): moving one lone empty costs the same as slewing
   the crane. 11,500 objects ≈ 17–25 ms per update on the test machine; **23,000 objects ≈ 70 ms** (it grows faster
   than the count). More threads do not help; hiding with the eye does not help; only "Disable in viewports" or fewer
   objects do.
2. **Fewer objects works, and the gain is large** (stress model, a drag step of the crane):
   **25 ms → 13 ms** with the bolts / nuts / washers as instances, **→ 5 ms** with every repeated part as instances,
   **→ 0.5–0.8 ms** with one object per rigid body. Playback the same; opening, saving and rendering get faster too.
3. **The price is the app's work, not Blender's:** about 90 of the app's files assume "one part = one object" (picking,
   looks, paint, hide, joints, welds, clash, web export, Place / Copy, the tree, model update …). Each step below says
   what it costs.
4. **Recommended path:** (a) a small, safe win now – hidden and left-out parts "disabled in viewports" instead of hidden
   with the eye; (b) **0341** builds "one object per sub-assembly" as planned (measured here: 0.6 ms), with the numbers
   below; (c) a fourth choice for bolts in **0342**: "Bolts as one set (faster)" – instances; (d) the full "part handles"
   redesign (one object per rigid body, every function working) only after (b) and (c) have been used on real models –
   a study of its own first. Your PC will be faster than these numbers (expectation: about 1.5 x, as 0326 measured);
   the PC check's Stress line "dragging a joint" will tell after each build task.

### Where Blender's ~15–25 ms goes (option 4: Blender's own settings)

- **Profile** of an update with 11,500 mesh objects (`py-spy --native`, Blender as a module, nothing of the app):
  96 % in `scene_graph_update_tagged`; of that **77 % `deg_evaluate_on_refresh`** – mostly `schedule_node`, a walk
  over every operation node of the depsgraph at every update – and **18 % `deg_graph_flush_updates`** (every ID).
  So the cost is "number of depsgraph nodes", i.e. objects; it does not depend on triangles or on how much moved.
- **Scaling** (Blender alone, one box moved per step, mean of 50 steps): 500 objects 0.7 ms · 2,000: 3.0 · 5,000: 7.8 ·
  **11,500: 17.4** · **23,000: 70.2 ms**. Empties cost about the same as meshes (13.9 ms at 11,500); a flat scene
  without the assembly tree 16.5 ms.
- **Half of 11,500 hidden:** with the eye (`hide_set`, what the app's Hide and "left out" use today) **19.4 ms – no
  gain**; "Disable in viewports" (`hide_viewport`) **8.4 ms**; collection excluded 9.3 ms.
- **Threads** (real Blender, `-t 1 / 2 / 4`, 2 runs each): 19.6–24.8 / 18.2–19.6 / 22.7–29.6 ms – no setting helps.
- The app's 14 scene-update handlers: no measurable share (all removed: the same time) – 0326 already fixed that.
- **No Blender setting** changes this; only fewer objects, or objects "disabled in viewports", do.

### Measured: the stress model in 7 forms

Stress model (11,228 placed / 1,995 unique parts, 4,876 in "Fasteners" groups, 9,304 parts whose shape is used ≥ 4
times), imported with the app (`main` at 0.2.273), its 8 joints made, then turned into each form by `s3_variants.py`.
**4-core web machine (Intel Xeon 2.1 GHz), Blender 5.2.3 as a Python module with the app registered**, each form
measured twice in a fresh process (mean; the drag on the unchanged model varied 21.7–29.5 ms between runs, playback
25–45 ms: the machine is noisy, the order of the forms never changed).
Normal = 4.14 M triangles placed / 1.15 M unique (the model is lighter than in 0315 since 0325's cable change).

| Form (Normal) | Objects | Drag step ms | Playback ms / frame | Open s | Save MB | RAM after open MB | Cycles 320 x 180 s | Render RAM + MB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **today** – one object per part | 11,559 | **25.2** | 25–45 | 1.9 | 16.9 | 556 | 4.7 | 534 |
| fasteners **disabled in viewports** (option 3) | 11,559 | 13.6 | 16.5 | 1.6 | 16.9 | 437 | 4.1 | 550 |
| **fasteners as instances** (one GN object per sub-assembly, 34 shapes) | 6,978 | **12.8** | 14.9 | 1.3 | 16.1 | 428 | 3.6 | 385 |
| **every repeated part as instances** (≥ 4 copies, 105 shapes) | 2,643 | **5.4** | 6.2 | 0.7 | 15.0 | 270 | 2.0 | 208 |
| one object per rigid body, GN instances (1,996 prototype objects kept) | 2,336 | 4.6 | 4.7 | 0.6 | 14.5 | 239 | 1.9 | 185 |
| **one object per rigid body, shapes in one library object** (GN *Split to Instances*) | 341 | **0.5** | 0.5 | 4.1 | 27.6 | 605–732 | 5.1 | 96–176 |
| **one object per rigid body, joined mesh** (0341's form) | 340 | **0.6** | 0.6 | 0.6 | **92.8** | 340 | 1.9 | 47 |

Draft (2.12 M / 0.56 M triangles): the same picture – today 25.7 ms, fasteners 15.3, repeated 5.2, rigid GN 4.8, library
0.8, joined 0.7 ms; save 7.9 / 6.8 / 5.8 / 5.3 / 13.6 / **48.2 MB**; open 1.9 / 1.3 / 0.6 / 0.5 / 2.2 / 0.4 s.
"Build" of the 10 s animation: 1.6 s today, 0.06–1.1 s in the other forms. All forms render the same picture (Cycles,
fixed camera; RMSE 0.9–1.3 % = 1-sample noise). Objects that remain in every form: 328 sub-assembly empties, joint
empties, the camera – about 0.5 ms of the 0.5–0.8 ms.

**What the numbers say**
- The drag step follows the object count almost exactly (≈ 2 µs per object, the same as Blender alone).
- **Instances keep the file and the memory small** (shapes shared); **a joined mesh makes the file 5.5 x bigger**
  (every bolt stored as its own triangles: 4.14 M placed vs 1.15 M unique) but rendering needs the least memory.
- **The library form** is the fastest per update and shares the shapes, but splits the library at every open (+2 s,
  more memory while open): good for moving, worse for opening.
- **Prototype objects count too:** with one GN object per rigid body but 1,996 prototype objects (even in no scene)
  the update stays at 4.6 ms – they are still depsgraph objects. Only one library object brings it to 0.5 ms.

**The 3D view's drawing** (real Blender under xvfb, *software* OpenGL – a direction only, your graphics card decides):
the real model drew in 190–220 ms per picture in every form (llvmpipe's triangle work hides everything else). With
11,500 small boxes (few triangles): 11,500 objects **47 ms** per still picture / **146 ms** per move + draw; the same
boxes as instances on one object 37–40 / 95–101 ms; one joined mesh 33–34 / 88–94 ms. So drawing also pays per object;
on a graphics card that draws the triangles fast this share will be larger (expectation, not measured).

### What still works with instances (s6_features.py, Blender 5.2.3)

- **Picking:** `scene.ray_cast` returns the prototype object (or the carrier, in the library form) **plus the
  instance's matrix**; matching that matrix against the carrier's list gives the part: **50 of 50 right, 0.14 ms each**.
  The joined form gives the face → its `fr_part` face attribute → the part.
- **Hide one part:** a boolean point attribute as *Instance on Points*' Selection: 200 → 199 instances.
- **A colour per part:** a point attribute read in the material by an Attribute node of type *Instancer*: every
  instance its own colour in **Cycles and EEVEE** (451 / 410 colours in a 160 x 120 picture). So looks, Fade and the
  clash's red can be per part without an object per part.
- Moving a part *inside* an instance object means re-running its node tree (all its instances): fine for a rigid body,
  wrong for anything a joint moves – such parts keep their own object or carrier.

### What breaks or needs work (one object per part is assumed in ~90 files)

`iter_parts` / "kind = part" appears in 92 files. Grouped:

| System | Fasteners / repeated as instances | One object per rigid body |
| --- | --- | --- |
| Picking, hover, right-click menu, Finder, measure | matrix → part lookup (shown to work) | face → `fr_part` or matrix lookup |
| Structure tree, lists, select, Show only / Hide | a part = (carrier, index); hide by attribute | the same, for every part |
| Looks per part, groups, Fade, section, clash red | prototype per (shape, look) or an instance colour attribute | material slot per part (joined) / attribute |
| Paint per face, finishes, decals, logos | instances share faces: one paint per (shape, look) | joined: per face works; decals need a parent |
| Joints, poses, Take apart, sequence, Place / Copy | parts a joint moves must leave the set (one carrier per mover) | nothing can move inside; a new joint splits the body |
| Welds (finder, beads) | fasteners: none (left out today) | finder reads part meshes: needs the per-part pieces |
| Clash check | already rigid bodies inside (`rigid_groups_of`); rows need part names | fits well: 11,228 matrices per moment → ~10 (memory) |
| Web 3D export, Film | expand instances to glTF nodes (meshes already shared) | split per part or export bodies |
| Model update (0324 / 0345), identity, welds, cables | match parts inside a carrier | match parts inside a body |
| Import (build) | fewer objects to make (−2,500 … −11,000) | fewer objects; a joined mesh costs memory |
| Callouts, cameras aimed at parts, cables / hoses ends | point on (carrier, index) | point on (body, part) |
| PC check, test tour, lessons | new lines for the option | new lines |

Already known object-count costs elsewhere (0366): `bpy.data.batch_remove` of 11,500 old objects 50 s in a model
update, the weld check's `ob.children` per part (n²) – both shrink with fewer objects, and both have their own fixes.

### Ranked (gain vs risk vs work)

| # | Step | Gain (stress, drag step) | Risk | Work | Fits |
| --- | --- | --- | --- | --- | --- |
| 1 | **Hidden and left-out parts "disabled in viewports"** instead of the eye (keep the eye only where the user hid one by hand in Blender) | 25 → 13.6 ms when 43 % are hidden; in proportion to what is hidden | low – code that reads a hidden part's `matrix_world` gets a stale one (CLAUDE.md 0064 note) | small | Motion / Looks: `logic.set_visible_flags`, `exclude` |
| 2 | **0341 "one object per sub-assembly"** as a joined mesh + `fr_part` + material slots (as briefed) | 25 → 0.6 ms at rigid-body level; at the top sub-assembly level about the same | medium – opt-in, the parts inside can't move (said in the popup) | large (already planned) | Import lane 0341 |
| 3 | **"Bolts as one set (faster)"** – a 4th choice next to Include / Simple / Leave out in 0342: fasteners as instances, one GN object per sub-assembly | 25 → 12.8 ms (≈ 2 x), file −5 %, RAM −25 % | medium – pick, hide, looks, web export, model update for those parts | medium–large | Import lane, after 0342 / with 0341 |
| 4 | **Every repeated part as instances** (≥ 4 copies) | 25 → 5.4 ms (≈ 5 x) | high – clips, glands, cabinets, gratings are parts users click, colour and move | large | after #3 has worked on real models |
| 5 | **"Part handles": one object per rigid body, every function working** (library or prototype form) | 25 → 0.5 ms (≈ 40 x) | very high – ~90 files | very large (a lane of its own, months) | study first, owner decides |
| – | Far / off-screen parts left out while dragging | in proportion, like #1 | high – parts vanish; places read stale | medium | not recommended |
| – | Blender settings (threads, handlers) | none measured | – | – | – |

### How it fits the import popup (0341 / 0342)

- 0341's "one object per sub-assembly" **is** option 2 at a level the user picks: this study measured its form (joined
  mesh, `fr_part` per face, looks as material slots): **0.6 ms** per update, open 0.4–0.6 s, but the **file grows with
  the placed triangles** (Normal 16.9 → 92.8 MB, Draft 7.9 → 48.2 MB here: bolts repeated in every body). Suggest to
  0341: inside a merged sub-assembly keep the **repeated parts (bolts) as instances** on the same object (a GN modifier
  adds them to the joined mesh) – then the file stays near today's size and the update stays near 0.6 ms (not measured
  as a combination; the two parts were).
- 0342's bolts choice gets a 4th value "As one set (faster)" (#3), or 0341 takes it as one more switch.
- The level: at import there are no joints yet, so "rigid body" is not known; the top sub-assemblies under the model are
  a good default (the stress model: 9 rigid bodies, most of the parts in one).

**What changed:** nothing in the app. Prototypes and numbers in `tasks/0381/` (README, 9 scripts, `results/` JSON).

**Tested and measured** (name the machine and the model): 4-core web machine, Intel Xeon 2.1 GHz, 16 GB, no graphics
card; Blender 5.2.3 as a Python module (app registered) and real Blender 5.2.3 (background and under xvfb); the stress
model of 0315 (`pccheck/stress_scene.py`, revision A, 206 MB STEP), imported at Draft (72.5 s) and Normal (78.7 s);
synthetic box scenes. Not measured: the owner's PC, a graphics card, a model update or web export of the new forms
(the app's own code does not handle them yet), the clash check's memory in the new forms (expectation from 0327: the
motion matrices drop from 11,228 to ~10 per moment).

**Open points / follow-up tasks** (for the owner to decide; model · effort):
- **0381a** (Motion lane, small): hidden / left-out / excluded parts "disabled in viewports" (`hide_viewport`) with the
  eye kept in step; find the code that reads hidden parts' places; a PC-check Stress line "drag with half hidden".
  **Opus · Medium.**
- **0341** (Import lane, as planned): take these numbers and the suggestion above (repeated parts as instances inside
  a merged sub-assembly) into its brief. **Opus · High** (unchanged).
- **0381b** (Import lane, after 0342): bolts "As one set (faster)" – fasteners as GN instances per sub-assembly, part
  identity per instance (pick by matrix, hide / colour by attributes), web export expands them, model update matches
  them. **Opus · High.**
- **Study "part handles"** (later, only if #2 and #3 are not enough on the owner's real models): one object per rigid
  body with every function working; an inventory of the ~90 files and an order of work. **Opus · High.**
- Owner: after any of these, run PC check > Stress and send the line "Stress model: dragging a joint" (today on the web
  machine 22–29 ms per step; on the owner's PC expected ~15 ms).
