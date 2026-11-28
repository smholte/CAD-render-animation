# 0355 – Assets pack P2: bring, keep and update pack items in a project (invisible)

**Who:** worker · **Status:** done (28 Nov 2026, 0.2.271) · **Branch:** `task/0355-assets-bring-keep-update`
**Started by:** lead, 25 Nov 2026 23:3x (0344's P2; owner's picks 23:17) · **Model:** Opus · effort High · Claude Code
on the web, environment "CAD-render-animation" · **independent review** (a helper agent that did not write the code tries
to break it – section 2, "Subagents")
**Area:** Assets lane – new `fresing_render/blender/assets.py` (+ pure helpers in `core/` if useful); additive:
`blender/props.py` (the scene fields `assets_source`, `assets_version`), `blender/materials.py` **only new helper
functions for `fr_look_src`** (read / write / compare – nothing in `build_nodes` or `is_current` changes here; that is
0360); tests, CHANGELOG + version files.
**Not:** `build_nodes`' look block, the finishes' `BUILDERS`, `world.py` / `studio.py`, `surroundings.py`, `props_scale.py`,
`people.py`, the tour and lessons (the plug-in tasks 0360–0363 wire the kinds in); any UI – Settings > Assets (0357) and
"Use the new Fresing looks" (0359); `handlers.py` (no load-time upgrade – see rule 3); `installer/`, `.github/`.

## Goal

The engine every later assets task uses: bring a pack item into the open project as **its own copy with its pictures
packed inside** (owner's pick 1), keep exactly one copy per item and version, stamp where it came from, and update
copies to a newer pack version on request – so that a project made with the pack **opens complete on a PC without the
pack**: a client's PC, plain Blender, a backup, the render queue's copy. Still no visible change: nothing calls it from
the UI yet.

## Background (read first – only the parts named)

- `tasks/0344-study-assets-pack-plan.md`: **"Owner's picks"** (top), report **2.2** (how a system asks – the project's
  own copy first), **2.4** (append + pack the pictures – the proof, its table, `reuse_local_id`, one picture datablock
  per file, one material per id + version), **2.5** (what a project stores: `fr_asset`, `fr_look_src`, `assets_source`,
  `assets_version`), **4** (old projects: nothing changes until the user chooses), **5** (2k inside projects; bring
  time), the rows "Backups", "Render queue", "Model update", "Client view" of the table in **3**.
- 0354's report: the interfaces of `core/assets_pack.py`, `core/assets_registry.py` and the test-pack maker
  (`pccheck/assets_test_pack.py`, with its version `1.1.0`).
- The proof on branch `task/0344-study-assets-pack-plan`: `tools/assets_pack_proto/try_pack.py` – steps `bring`,
  `open`, `update`, `reuse` (and `_dedupe_materials`) – and `results_25nov.md`.
- How the app appends today: `blender/material_picker.py` (own Blender materials appended as "FRM <name>", never
  linked); backups `blender/backups.py:273` (`save_as_mainfile(copy=True, relative_remap=False)`); the queue's copy
  `blender/queue.py:378` (`relative_remap=True`).
- CLAUDE.md section 6: "Old projects – the baseline" (this task is groundwork **before** the baseline: no new upgrade
  code, an old project only has to open without a crash), "Keep saved data small", and the assets-pack rules.

## What to do

1. **Bring** (`blender/assets.py`): for an id the registry answers with a pack item – append its datablock(s) from the
   pack's `.blend` (never link), **pack every picture it uses into the project** at the project quality (2k; never the
   4k files – pick 2), stamp `fr_asset` = `{id, pack, version, contract, sha}` on every brought datablock, give them the
   app's names. **One per id + version:** a second bring reuses the copy; two items that share a picture file share one
   image datablock (map it at once – no packing work twice); an environment that brings its own copy of a material
   keeps the project's one. **All or nothing:** if a file is missing, unreadable or holds something it should not (a
   Text datablock, a script, a Python driver – check what came in), remove what was appended, use the code look, and
   give one note per session – never a half-built item. Bringing must work in a **background Blender** (queue, tour /
   demo builds, PC check), which finds the pack by 0354's lookup, not by settings.
2. **Ask in one place:** `assets.get(scene, id)` (name it as you like) answers in 2.2's order – the project's own copy
   (by its `fr_asset` id) → bring from the pack when the project's source is `pack` and the pack has the id with a
   fitting contract → `None` = the caller builds today's code look. Answers from memory; **`world.apply`, the colour /
   wear sliders and the picker's draw must never touch the disk** – show it with a count or a timing in the tests.
   A small way for the plug-in tasks to register a kind (what "bring" and "update" mean for that kind) without
   editing this file's core.
3. **The project's source** (2.5, picks 5 and 7): `assets_source` on the scene – `""` (made before the pack) counts as
   `code`; `pack`; `code` – plus `assets_version`. A project **made in this version** gets its source when it is made:
   `pack` when a pack is found and the switch is on (the switch itself comes with 0357 – read it through one function
   with default "on"), else `code`. A project **opened from a file without the field stays `code`** – installing,
   updating or removing the pack never changes it; only the user's "Use the new Fresing looks" (0359) does. No load
   handler, no `LOOK_VERSION` / `MAT_VERSION` / `fr_prop_ver` stamp is used for any of this (report 4).
   `fr_look_src` helpers (`code` | `pack:<version>`) for 0360's `is_current`.
4. **Update engine, no UI** (0359 puts the button on it): `changes(scene, pack)` lists what would change – copies with
   an older pack version, and, for a `code` project, the kinds that have a registered plug-in (none yet: the list is
   empty until 0360–0363); `apply(scene, pack)` makes the change as **one undo step**: re-brings newer versions and
   points every user at the new copy, keeps each group's own colour, wear, rust, Adjust and finish settings (the proof
   kept the group node's colour through 1.0 → 1.1), removes the old copies, sets `assets_source` / `assets_version`.
   It calls 0246's backup before changing anything (one function call – the dialog is 0359's).
5. **Tests – both ways** (with 0354's test pack, and without any pack – CI accepts no "no pack" skip):
   - every kind of the test pack brought, saved, and the file opened **alone in another folder with the pack hidden**
     (a "client"): nothing missing – no library links, every picture packed – and a small Cycles picture the same as
     with the pack (no pink, no black);
   - the same for a **backup** (opened from `Backups\`) and the **queue's copy**;
   - one per id + version; shared pictures once; the environment's material once;
   - update 1.0.0 → 1.1.0: the changed look changes, the group's own colour / wear stay, Ctrl+Z gives the old one back;
     the updated project on a "client" is still complete;
   - a broken pack file during bring → nothing half-built, the code look, one note;
   - a new project gets `pack` with a pack and the switch on, `code` without a pack; an **opened** project without the
     field stays `code` with a pack present (use `tests/data/old_project_0_2_195.blend` – it only has to open without a
     crash and stay unchanged; no upgrade code for it);
   - a background Blender finds the pack by `FRESING_ASSETS` and brings the same;
   - without any pack: every answer is "code", nothing is written to the project.
6. **Speed and size:** bring time per item and for a 40-group project with one world and one environment (0344
   estimated +0.5 s), open and save time, project size with packed 2k pictures – measured on the web machine, in the
   report. Saved data stays small: `fr_asset` is the only stamp per datablock.
7. **Independent review** before merging: a helper agent that did not write the code reads the brief and section 2.4 and
   tries to break it (client open, backup, queue copy, undo, a pack removed or updated mid-session, the Client view's
   lock, a model update of a pack project on a PC without the pack). Its findings go back to the author; the report
   says what it found.
8. CHANGELOG: one plain line (no visible change). No guide chapter yet.

## Done when

- [ ] Bring, keep, ask and update work as above; the app without a pack works exactly as before.
- [ ] The tests of step 5 pass locally and on GitHub (full run green); the independent review's findings are fixed or
      listed.
- [ ] Report: the interface 0357, 0359 and 0360–0363 call (functions, the kind registration, the notes), the measured
      times and sizes, what the review found.
- [ ] Report filled in, merged, released (section 7).

## Not in this task

Any UI; the looks' plug-in points (`build_nodes`, finishes, light, surroundings, props, people, tour, small looks –
0360–0363); the 3D page caps (0364); the installer and pack updates (0358); the pack checks (0356). Never the owner's
files; never his employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 28 Nov 2026 · 0.2.271

**What changed:** no visible change. New `blender/assets.py` (the engine) and `core/assets_keep.py` (its plain rules);
additive: `props.py` scene fields `assets_source` / `assets_version`, `materials.py` helpers `look_src_of`,
`set_look_src`, `look_src_matches` (`fr_look_src`; `build_nodes` / `is_current` untouched), one `register()` line in
`__init__.py`. Tests `tests/test_assets_bring.py` (22, Blender as a module) and `tests/test_assets_keep.py` (7).

**Interface (0357, 0359, 0360–0363 call these – `from fresing_render.blender import assets`)**
- **Ask:** `assets.get(scene, "<kind>:<id>", bring=True) -> Answer(source, id, datablock)` – `source` "project" (the
  project's own copy), "pack" (just brought) or "code" (build today's look for `answer.id` / `answer.code_id`; a
  pack-only id answers with its fallback's id, "" = nobody knows it). Never raises. `bring=False` in a draw. A copy
  has no users when brought: **use it at once** (Blender does not save a datablock nothing uses; the next ask brings
  it again). The copy is the item's own datablock: material / finish → the node group "FRP <id>", light / hdri → an
  image (named "FRP <kind> <id>" unless the kind names it), prop → the object, environment → the collection.
- **Source:** `assets.source(scene)` ("pack" / "code"), `assets.version(scene)`, `assets.new_source()`,
  `assets.is_new_project()`. New project: answers `new_source()` until its first save (`save_pre`) or first bring writes
  it; a scene made later takes the file's stored source; an opened file without the field stays "code".
- **Switch / company folder:** `assets.SWITCH["read"] = <function → bool>` (0357; default on, a failing reader = on),
  `assets.FOLDER["read"] = <function → folder>` (0358).
- **Registry:** `assets.registry()` (read once, warmed in a helper thread at `register`), `assets.forget()` (after a
  pack update is put in place – also clears the session's refused items), `assets.note()` (ONE line: this session's
  bring problem `NOTE_BRING`, else the registry's note).
- **Update:** `assets.changes(scene) -> [assets_keep.Change(id, kind, what "newer" | "code", old, new, text)]`;
  `assets.apply(scene, backup=True, undo="") -> Result(done, failed, backup, note)` – `compat.blocked` → nothing;
  backup first through `backups.make(force=True, note=False)` (no backup → nothing changes, `NOTE_BACKUP`); `undo=` the
  step's name when called outside an operator (0359's operator with `UNDO` passes ""). Items whose pack row says they
  did not change since the copy's version (`changed` / `since`, or the same sha256) are only re-stamped.
- **Kinds:** `assets.register_kind(kind, name=, after_bring=, swap=, code_changes=, code_apply=)`,
  `unregister_kind`. Default swap: `user_remap` (node groups: group materials keep their colour / wear / rust / Adjust
  / finish; `fr_look_src` follows); objects keep every placed copy and take the new mesh. **0362 should register its
  own swap for environments** (the default `user_remap` of a collection puts back the pack's module layout).
- **Stamps:** `assets.stamp_of(idb)`; `fr_asset` = {id, pack, version, contract, sha} + name, file, of, part, space
  (`core/assets_keep.py`). `materials.look_src_of / set_look_src / look_src_matches` for 0360's `is_current`.
- **Rule for the pack's makers (0356):** a datablock's name inside a pack file is shared with another item only if it is
  that item's own datablock (e.g. "FRP cast_iron" in an environment's file); other names are kept per file.

**Tested and measured** (4-core web machine, Linux, Blender 5.2.3 as a module, 0354's test pack):
- Every kind brought, used, saved, opened alone in another folder by a plain Blender with the pack hidden: no library,
  every picture packed (2k), same Cycles picture as with the pack (mean colour within 0.01, no pink, not black); the
  same for a backup from `Backups` and the queue's copy; update 1.0.0 → 1.1.0 (paint_satin 0.36 → 0.42, cast iron's new
  roughness picture, the colour picture not packed twice, the group's orange and wear kept), Ctrl+Z gives 1.0.0 back,
  the updated project complete on a client; a broken pack (missing picture, damaged .blend, a script node) → nothing
  left, the code look, one note; new / opened / old (0.2.195) projects' source; no pack → every code id answers code,
  nothing written; a background Blender finds the pack by `FRESING_ASSETS` and stamps the same; a pack project without
  the pack keeps its copies.
- **Times:** bring one item 0.7 ms (a light picture) – 5.6 ms (cast iron, two pictures), sha256 check included; a
  40-group project with a world and an environment (5 items brought): +37 ms over the same project without the pack;
  save 13 vs 8 ms, open 18 vs 13 ms; size 2.35 MB vs 0.14 MB (the test pack's 2k pictures and light EXR). A question
  answered from memory: 7 µs (looks); on 11,228 objects a prop question 0.4 ms (Blender's `len()` of the object list
  walks it), a bring 35–62 ms there (the before / after list of all datablocks). The reviewer measured `apply` of 2
  looks on 11,000 parts: 0.42 s without the backup.
- Hot path: 1,400 questions for existing copies opened no file, looked at no folder, appended nothing (test).
- Local: 29 new tests in 19 s; the neighbours (`test_assets_*`, `test_backups_blender`, `test_compat*`,
  `test_materials_look`) 215 passed. GitHub: see below.

**Independent review** (a helper agent that did not write the code, 28 Nov): 9 findings, 8 reproduced, all fixed with a
regression test each – parts of two pack files with the same name merged (now shared only within a file or as an
item's own datablock); a prop update put every placed copy on one spot (objects now keep their copies and take the new
mesh); a shared picture kept the first item's colour space (key now bytes + colour space + alpha); a refused item was
tried again at every ask (remembered per session); a scene made after the first save read "code"; two picture items
with the same bytes became one; a race between the start-up read and `forget()`; brought items have no users (the rule
is now in the interface); packed pictures in a pack file, a font file, a failed update's version and note, the user's
duplicate of a pack node group answering for the pack copy (Blender's weak reference to the pack file tells the
original). Held up: Python drivers, script nodes (also nested), pictures outside the pack, UDIM, linked libraries –
refused with nothing left behind; undo / redo of a bring and of `apply`; the index after opening files one after
another; Recover keeps a project "code". Not tried: the Client view's lock (needs the real app; the engine adds no
operator – 0357 / 0359 put their buttons on `lock.ALLOWED` or not).

**Open points / follow-up tasks:**
- 0362: register a `swap` for environments (keep the code layout's placing) and people.
- 0356: check the pack rule above (one name = one datablock across files only for an item's own datablock) and that no
  pack picture is packed inside a `.blend`.
- 0354's report said the test pack's other files are byte-equal between 1.0.0 and 1.1.0: true for pictures, not for the
  `.blend` files (Blender writes them differently each time) – the update therefore reads each row's `changed` /
  `since`.
- No PC-check line, tour stop or function entry (nothing visible yet) – 0357 adds `assets.pack`.
