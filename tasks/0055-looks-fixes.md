# 0055 – Looks fixes: group renames, safer project loading, old caches, chrome rods and shafts

**Who:** worker · **Status:** done (0.2.40) · **Branch:** `task/0055-looks-fixes`
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 5, 19a, 19e, 19f; 0046 open point "part library")
**Lane:** Looks (+ Part library) – `blender/props.py` (`_group_renamed`, group name check), `blender/handlers.py`
(`_on_load`), import cache clean-up (importer cache code), `core/part_types_data.py` (two lines); tests; guide chapter 3
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0051 (Machining), 0052 (Motion) and 0053 (Quality & delivery). Do not touch
`materials_lib.py` (0051 adds materials there), `decals.py`, `reimport.py`, joints, machining, chips, G-code,
`updates.py`, `update_helper.py`, `project_lock.py`, `queue.py`.

## Goal

Renaming a group keeps its paint schemes and saved scenes' looks, two groups can't end up with the same name, one
failing upgrade step on load no longer silently skips the rest, old import caches don't fill the disk, and chrome
rods and shafts get the new 0046 looks.

## Background (proof and suggested fixes: `tasks/0045-bug-hunt.md`)

- **Row 5 – paint schemes and saved scenes' own looks don't follow a group rename.** In `_group_renamed` also rename
  `look.group` in `s.schemes[*].looks` and in every `shot.own_scheme.looks`. Test: the row's proof.
- **Row 19a – renaming a group to an existing name** gives two rows with that name. Refuse with a short message
  (or merge – say which and why).
- **Row 19e – `handlers._on_load`** runs every upgrade step for every scene in one `try … except: pass`. One try per
  scene and step, with a printed reason; the app still opens.
- **Row 19f – old import caches** of an older `CACHE_VERSION` are never deleted. Prune them (at import start, or at
  app start in the background); never delete the cache of the current version.
- **0046 open point:** part types "Chrome rods & linear shafts" → *Hydraulic chrome rod*, "Shafts" and
  "Linear guides" → *Steel, ground* in `core/part_types_data.py`. Only new imports and new rule sets; old projects
  keep their looks (check that the rule-set upgrade does not change them).

## Done when

- [ ] Rows 5, 19a, 19e, 19f fixed with a test each.
- [ ] The two part-type looks changed; part-type tests updated; old projects unchanged (test).
- [ ] Tooltips if anything visible changed; guide chapter 3 if group renames are described there.
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0055 done, 0056 "open – can start".

## Not in this task

Two copies of the same STEP sharing part IDs (row 11 → 0056, Opus High). New materials (0051).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 9 Nov 2026

**What changed:** `props._group_renamed` renames looks in schemes and scenes' own schemes and refuses duplicate names
(reverts, message in `last_message`); `handlers._on_load` runs one try per scene and step (`_upgrade_steps`);
`runner.prune_old_caches` called at import start; chrome rod / shaft / linear guide looks in `part_types_data.py`.
Tooltips and guide unchanged (nothing new visible besides the message).

**Tested and measured** (name the machine and the model): new `tests/test_looks_fixes.py` (6 tests) plus part-type tests pass locally (4-core web machine, test_materials.step). Real-app tests left to GitHub. Helper review skipped (no Windows code).

**Open points / follow-up tasks:**
