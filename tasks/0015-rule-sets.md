# 0015 – Rule sets: one naming scheme per company, chosen per project

**Who:** worker · **Status:** running (worker chat, 4 Nov 2026) · **Branch:** `task/0015-rule-sets`
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

- [ ] Tests: copy Standard, edit, save, load in a new project; New empty; switch with hand
      assignments kept; preview counts correct; library missing → project copy used; old project
      and old template open unchanged
- [ ] Real-app click test step (pick, switch, save) and screenshots of 3 Looks checked
- [ ] Full suite passes; report filled in; merged and released (CLAUDE.md sections 2 and 7)

## Not in this task

- A different rule set per model in one project (several machines in one scene, task 0006):
  note in the report how it would fit.
- Choosing the rule set automatically from the file name: possible follow-up, not asked for.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
