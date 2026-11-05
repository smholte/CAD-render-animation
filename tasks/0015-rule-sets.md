# 0015 – Rule sets: one naming scheme per company, chosen per project

**Who:** worker · **Status:** done (0.2.13, 5 Nov 2026) · **Branch:** `task/0015-rule-sets`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Looks · **Area:** `core/rules.py`,
`core/template.py`, new `core/rule_sets.py`, `blender/logic.py`, `blender/ops_main.py` (templates),
`blender/ops_panels.py` and the 3 Looks part of `blender/ui.py`, `blender/props.py` (additive),
`tests/`.

## Goal

The owner works for his own company and for others, and each has its own part-naming scheme and
standards. He keeps one **rule set** per scheme (the sorting rules plus the material groups with
their materials), picks the rule set for a project, and can switch to another one during the
project.

## Background

- Today one list of rules lives in each project (`scene.fresing.rules`, groups in
  `scene.fresing.groups`); `default_rules()` in `core/rules.py` is the built-in list; task 0008
  adds the large part-type library to it. Templates (`core/template.py`, shared library folder in
  the add-on preferences, `prefs.library_dir(...)`) already carry rules, groups, colour schemes,
  background and output settings.
- Hand assignments (`fr_group_manual`, from "Put selected in", Find & sort parts, "Move to
  group") must survive any switch.
- Read the reports of 0008 and 0010 first: both change the sorting and the materials (0010 also
  sorts single faces through the rules: a switch of rule set re-sorts face sets too).
- In-house abbreviations of the owner's company or his clients belong in his own rule sets, not
  in the built-in library (the EGR test model is a public GrabCAD model, not his naming) (task 0022 runs at the same time in `core/part_types_data.py` – do not
  touch that file).
- If the owner attaches a small Fusion 360 STEP with one face painted in another appearance,
  check that the face comes in painted (task 0010 wrote that STEP structure by hand) – numbers in
  the report, file not committed.

## What to build

1. **Rule set** = name + sorting rules + material groups (material, colour) + group renames.
   Stored as a file in the shared library folder ("Rule sets"), so colleagues and other projects
   use the same ones; the project keeps a copy, so it opens without the library.
2. **Built-in "Standard"** (fasteners + part-type library from 0008): read-only. **Copy** makes
   an editable one; **New, empty** starts from the bottom up (only "Unsorted"); **Rename**,
   **Delete** (not Standard).
3. **Pick per project** at the top of 3 Looks: "Rule set: [Fresing ▾]". Switching during a
   project shows first what will change ("312 parts change group, 4 groups new") and needs a
   confirm; parts put in a group by hand stay there; undo works.
4. Edits in the project (rules, group materials, Find & sort parts → "Make it a rule") change the
   project's copy; the panel shows "changed" and offers **Save to rule set** (library) or
   **Save as new rule set**.
5. Default rule set for new projects in the add-on preferences. Templates refer to a rule set by
   name and keep their own copy (old templates load as before). Old projects: their rules become a
   rule set "From this project" – they open unchanged.

## Done when

- [x] Tests: copy Standard, edit, save, load in a new project; New empty; switch with hand
      assignments kept; preview counts correct; library missing → project copy used; old project
      and old template open unchanged
- [x] Real-app click test step (pick, switch, save) and screenshots of 3 Looks checked
- [x] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- A different rule set per model in one project (several machines in one scene, task 0006):
  note in the report how it would fit.
- Choosing the rule set automatically from the file name: possible follow-up, not asked for.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4–5 Nov 2026. Released as **0.2.13** (main had released 0.2.11 user
guide and 0.2.12 surroundings meanwhile).

**What changed:**

- New `core/rule_sets.py` (file format, library folder: scan, save, rename, delete; "changed"
  comparison) and `blender/rule_sets.py` (the project side: its copy, preview, switch, save,
  adopting old projects), operators in new `blender/ops_rule_sets.py`.
- A rule set = name + rules + group looks + group renames. One JSON file per rule set in
  `<shared library>/Rule sets/`, else `Documents\Fresing Render\Rule sets` on the PC (Windows asked
  for the real Documents folder: OneDrive may have moved it). The project stores the name and its
  own copy (`scene.fresing.rule_set`, `rule_set_data`), so it opens without the library.
- 3 Looks, top: **Rule set** menu; "Changed in this project: …" with Save changes / Save as new…
  (Standard: Save as new rule set…; a project-only set: Save to library…); "The library has a newer
  version" with Load it…; fold **Manage rule sets**: Copy…, New, empty…, Rename…, Delete…, New
  projects (default), folder and Show the folder. Preferences: Default rule set.
- Switching: a dialog with the preview first (parts that change group, painted face sets that
  change, new groups, groups that go away, groups that get another look, hand-placed parts that
  stay, unsorted now/after), then the switch. Hand assignments (`fr_group_manual`) and groups that
  only hold hand-placed parts stay; groups left empty go; painted faces are re-sorted; one undo step.
  The preview and the switch use the same dry-run sort (`logic.sort_plan`, `faces.plan`), so the
  counts match.
- "Changed" compares the project with its copy; a group look only counts when it differs from the
  built-in look for that name and the rules fill the group (`group.by_rules`, new, default False).
- Templates: `rule_set` (the project's rule set as it is, unsaved changes included) and
  `rule_set_base` (the library version it is based on). Loading: the library version wins when it
  moved on since the template was saved, else the template's copy (its changes shown as changed).
  Templates without these fields load exactly as before.
- Old projects (before 0.2.13): on open their rules become the rule set "From this project", or
  "Standard" when they are the untouched defaults; nothing is re-sorted, no look changes.
- Self-test: line "Rule sets folder" (the folder can be written, with a hidden temp file).
- User guide: 3 Looks has a new part "Rule sets" with a picture; Sorting rules, Templates and the
  shared-library text mention rule sets; the 3 Looks pictures are redone. `tools/guide_screens.py`
  makes the new picture.
- `tools/ci_real_app.py` runs the rule-set click test too, so GitHub checks it at every push.

**Independent review** (helper agent that did not write the code, incl. the Windows-only
`documents_dir` ctypes call): no blockers; 6 "should fix" and 4 minor points, all fixed, each with
a test that failed before (9 tests):
damaged/hand-edited files broke 3 Looks → skipped (or read when they still make sense, BOM too);
two names with the same file name ('A/B', 'A_B') overwrote each other → 'Name (2).json'; an
Explorer copy took over saves → the original's file name wins; menus numbered by position could
make Delete act on another rule set when a colleague added one while the dialog was open → numbers
from the name; Save changes overwrote a colleague's newer version silently → warning in the dialog;
the shared folder was asked at every redraw (a dead server would freeze the panel) → at most every
15 s; Save/Rename/Delete check afresh; Documents was asked from Windows at every redraw (each call
kept a ctypes type, ~6 KB) → once per session; a rule without a group showed "changed" for ever →
kept; a name of only dots fell back to "Rule set.json" → refused. The reviewer checked the ctypes
call itself (argument types, HRESULT, GUID byte order, CoTaskMemFree, fallback) and found it right.

**Tested and measured** (2-core Linux test machine, no GPU):

- `tests/test_rule_sets.py`: 37 tests – core (Standard, file round trip, own looks, differences,
  names, library scan/save/rename/delete, damaged files, file-name collisions, Explorer copies) and in
  Blender: new project = Standard; copy Standard, edit, save, load in a new project; default rule set
  missing → Standard + message; New empty (+ hand picks kept); switch keeps hand assignments and the
  preview counts equal the switch; looks restored; renames; hand-only groups; library missing →
  project copy; unreachable shared library; old project opens unchanged; old template loads as before;
  template by name, with unsaved changes, library newer; rename/delete; Standard cannot be saved
  over; painted faces re-sorted; panels draw in every state (also with damaged files); menu numbers
  stable; save warning; folder check cached; tooltips; cost of the "changed" check.
- Full suite on the merged code: 1,423 passed (8 min, 2-core test machine).
- Real app (`tools/ci_real_app.py`, virtual screen, simulated clicks, UITEST_QUICK=1) on the merged
  code: ui1 18/18, ui2 39/39, faces 10/10, surroundings 17/17, **rule sets 17/17**, paths 8/8.
  The rule-set test clicks the menu, Copy… (dialog + Enter), changes a look, Save changes (confirm),
  switches with the preview dialog, Undo/Redo, New empty…, switches back, "library newer" and "only
  in this project"; its screenshots of 3 Looks and every dialog were looked at (no cut-off labels).
- Guide pictures made in the real app (`guide_screens.py panels`), only section 3 and the overview
  strip changed; looked at all of them.
- Packaged install + self-test (Linux build of the zip): all OK, "Rule sets folder" OK. On GitHub's
  Windows runner (install + self-test job): "Rule sets folder (0.0 s): this PC:
  `C:\Users\runneradmin\Documents\Fresing Render\Rule sets`" – the Windows code runs; a Documents
  folder moved to OneDrive can only be checked on the owner's PC.
- Synthetic 2,800-part scene (test model copied with generic names, 70 parts put in a group by
  hand): preview of a switch 0.02–0.03 s, switch 0.04–0.06 s, the "changed" check the panel makes at
  every redraw 0.12 ms.
- Not measured: the EGR model and a Fusion STEP with a painted face were not attached in this chat,
  so no sorting-coverage numbers and no Fusion check.

**Open points / follow-up tasks:**

- Owner on Windows: self-test line "Rule sets folder" (Documents may be on OneDrive); a shared library
  on the network (two PCs: save on one, "The library has a newer version" on the other).
- Rule set per model (several machines in one scene, task 0006): store `rule_set` and
  `rule_set_data` on each model's root instead of the scene, and run `sort_plan` per root with that
  model's rules. The group list is shared by all models, so two rule sets that use the same group name
  with different looks would need per-model groups (or group names with the model as prefix); the
  panel would show the rule set of the model the selected part belongs to.
- Choosing the rule set from the file name (not asked; possible later).
- `docs/TOOLTIPS-TODO.md` lists 14 older Looks-lane tooltips (1 Import, 2 Structure, 3 Looks) that
  this task did not touch: for the next Looks-lane task.
- `render.pictures_dir()` (Scene & Render lane) has the same ctypes pattern the review flagged here
  (a new structure type per call). It runs only when rendering an unsaved project, not while
  drawing, so it is minor; cache it like `rule_sets.documents_dir` when that lane next touches
  `render.py`.
