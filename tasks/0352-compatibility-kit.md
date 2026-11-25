# 0352 – Compatibility kit: a format number on every project, one upgrade chain, test projects that later versions must open

**Who:** worker · **Status:** open · **Branch:** `task/0352-compatibility-kit`
**Started by:** lead, 25 Nov 2026 23:5x (owner 25 Nov 22:4x–22:5x: strict backward compatibility from the baseline) ·
**Model:** Opus · effort High · Claude Code on the web, environment "CAD-render-animation" · **independent review** (a
helper agent that did not write the code tries to break it – section 2, "Subagents")
**Area:** new lane **Compatibility** – new `fresing_render/core/compat.py` (format number, the saved-data list, the
chain of steps – plain Python), new `fresing_render/blender/compat.py` (its own load / save handlers, the message), new
`tools/make_compat_project.py`, new `tests/test_compat*.py`, `tests/data/compat/` (README only for now – see step 5);
additive: `blender/props.py` (the stamp fields), `__init__.py` (register the module), CLAUDE.md sections 6 and 7 (the
rules and the release step), CHANGELOG + version files.
**Not:** `blender/handlers.py` (0326 is running there – register your own handlers in `blender/compat.py`, first in
Blender's lists, as `measure.py` and `welds.py` register their own); **the existing load-time upgrades in ~32 files stay
where they are** – you list them (step 1), you don't move or delete them (pre-baseline ones go with the per-lane cleanups
0350a, b …); 0353's outputs (3D page, House file, Viewer file); the Save / Save As code of 0291 except one call if step 4
needs it.

## Goal

From the **baseline** on (CLAUDE.md section 6), every project saved by Fresing Render keeps opening – with the same data
and the same look – in every later version. This task builds the kit that makes that checkable instead of hoped for: a
**format number** on every save, **one ordered chain** where every future change of saved data gets its upgrade step,
**test projects** that every later version must open, a **plain message** for a project from a newer app, and the
**list of what a project stores** (choices) against what is rebuilt (derived data).

## Background (read first – only the parts named)

- CLAUDE.md section 6: **"Old projects – the baseline"** (before the baseline an older project only has to open without
  a crash; no new upgrade code for pre-baseline projects) and **"Keep saved data small"** (choices are stored; bakes,
  caches, app-made meshes, liquid, cable shapes, baked light are rebuilt, never upgraded); the **assets-pack** rule
  (`fr_asset`, `assets_source` – 0355 adds them).
- TASKS.md rows 0350 (per-lane cleanups) and 0353 (outputs – not this task).
- Today's load-time code: `blender/handlers.py` `_on_load` and `_upgrade_steps` (≈ line 140–215 at 0.2.260) and the
  `load_post` handlers of about 32 files (`grep -rln load_post fresing_render`); `materials.LOOK_VERSION`, the
  surroundings' `MAT_VERSION`, `props_scale.upgrade`, `fr_prop_ver`, the tool-mark / weld version stamps (0344 report
  section 4 lists the look ones).
- The save handlers in `handlers.py` (`_before_save` / `_after_save`), backups (`blender/backups.py`), the queue's copy
  (`blender/queue.py`), project names / Save As (0291).
- `tests/data/old_project_0_2_195.blend` and the tests that open it (52 test files mention old projects – 0350's list).

## What to do

1. **Findings first (in the task file, then go on – no stop):** a table of every load-time action today, one row each:
   file / function, what it does, and its kind – **(a)** upgrades stored data (a choice), **(b)** rebuilds derived data
   (allowed, not versioned), **(c)** only for pre-baseline projects (0350 deletes it in its lane), **(d)** not an upgrade
   (subscriptions, caches, UI). And the **saved-data list**: every property group, custom property and datablock stamp a
   project stores today, marked *choice* or *derived*; derived data that is saved today (and so grows projects or needs
   upgrading) becomes a row for the matching 0350 cleanup. Keep both tables short and exact.
2. **The format number** (`core/compat.py`): `FORMAT` (an integer; start at 1) + the app version, stamped on the scene at
   **every save** (also backups and the queue's copy) by a `save_pre` handler in `blender/compat.py`. A project without
   the stamp = made before the kit. The baseline's format number is written into CLAUDE.md section 6 by the lead when the
   baseline is released; until then the constant `BASELINE_FORMAT` is `None`.
3. **One ordered chain** (`core/compat.py` + `blender/compat.py`): steps registered as `(from_format, to_format, name,
   function)`, run in order on load **before every other Fresing load handler** (insert first in `load_post`), each step
   in its own try / except with one plain line (as `_on_load` does since 0055), the project then stamped with the
   current format in memory. Starts **empty**: at the baseline every kept project is at the baseline format. Below the
   baseline (or no stamp) the chain does nothing – today's per-lane code still runs until 0350 removes it. A test proves
   the order, the one-failing-step rule and that a step runs once.
4. **A project from a newer app** (format above the app's): open it to look at, **never damage it** – a plain message in
   the app's own style ("Saved by Fresing Render 0.2.X, newer than this one (0.2.Y). Update the app to work on it –
   Fresing > Updates. Saving is off so nothing in it is lost.") and saving it refused or turned into a copy with a new
   name – find the safest way the app's save path allows (0291 owns Save / Save As; Blender cannot cancel a save from
   `save_pre`). Also the queue, backups and the model update must not write into it. Tests for each.
5. **Test projects** (`tools/make_compat_project.py`): makes a **small invented project in the running app version**
   that uses every function family that stores data (`core/functions.py` `FAMILIES` – a test fails when a family that
   stores data is missing from the maker), saves it with a JSON summary of its stored choices (the saved-data list of
   step 1) and a small reference picture (Cycles on the processor, tiny, a few samples – as other picture tests do).
   `tests/test_compat_projects.py` opens every project in `tests/data/compat/`, runs the chain, and compares the
   summary (exactly, or by the step's documented change) and the picture (with a tolerance). **One test project per
   format number, not per release** (a release that does not change the format saves the same structures; one per
   release would add tens of MB a month to the repository) – each under ~1 MB, no packed pictures, no bakes. Before the
   baseline nothing is kept: CI runs the maker in the current version and opens its result (save → open → same summary
   and picture), and `tests/data/compat/README.md` says how projects get there. **The release step** (CLAUDE.md section
   7): a release that raises `FORMAT` (from the baseline on) runs the maker and commits `format_<n>.blend` + its
   summary and picture; the precheck fails a raised `FORMAT` without them and without a chain step.
6. **Rules in CLAUDE.md** (section 6, short): a change in what a project stores = raise `FORMAT` + one chain step + the
   test project (from the baseline on); derived data never gets a step; never a new load-time upgrade outside the chain
   once the baseline is set. The lead reviews the wording.
7. **Independent review** before merging: an agent that did not write the code tries to break steps 2–5 (a crash in a
   step, a newer project through backup / queue / model update / Save As, a project without the stamp, two scenes, a
   library-linked scene). Findings back to the author; the report says what it found.
8. CHANGELOG in plain words (the user sees only step 4's message). No guide chapter beyond one short "Projects from a
   newer version" line in the user guide's FAQ / troubleshooting part, with its anchor.

**Running beside you:** 0355 (assets pack P2) adds `assets_source`, `assets_version` and `fr_asset` – whoever merges
second puts them in the saved-data list. 0326 owns `handlers.py`; 0346 / 0348 add load handlers of their own – your
handler must run before theirs.

## Done when

- [ ] Steps 1–6 on `main`; the format number is on every save; the chain runs first and is empty; a newer project is
      never damaged; the maker covers every data-storing family and its result opens the same in CI.
- [ ] The findings tables are in the report, with the (c) rows and the saved derived-data rows grouped by lane for
      0350a, b …
- [ ] The independent review's findings are fixed or listed; the full run on GitHub is green.
- [ ] Report filled in, merged, released (section 7).

## Not in this task

Moving or deleting today's upgrades (0350 per lane); outputs' format numbers (0353); the baseline itself (the lead sets
it when 0344's groundwork, the import lane, 0345 and the other "before the baseline" tasks are in); the assets pack
(0354–0365). Never the owner's files; never his employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
