# 0009 – Structure and Looks panels: tree, highlight, search, grouping tools

**Who:** lead · **Status:** done · **Branch:** `task/0009-structure-looks`
**Started by:** lead chat, 4 Nov 2026 · **Area:** `blender/ui*.py`, `blender/ops_*.py`,
`blender/props.py`, `blender/logic.py` (new functions only; `facts_for_object` belongs to task 0008),
`tests/`.

## Goal

Owner's points 1–3 and 5–16 (4 Nov 2026):

Structure: (1) clicking a row highlights it in the view, zoom-to per row; (2) explorer-style tree
with open/close arrows per assembly instead of "Levels shown", opens to what is clicked in the view;
(5) copies told apart by occurrence name; (6) isolate; (7) search in the tree; (8) several rows at
once; (9) colour dot per part row.
Looks: (3) search by name with ticks, select all, put in group; (10) save a search as a rule;
(11) group a whole subassembly; (12) suggestions for unsorted parts (common words with counts);
(13) show only unsorted; (14) ready-made machine materials; (15) group of a part clicked in the
view with "move to group"; (16) groups made from a search are named after it.

## Done when

- [x] All points above, tested (panel tests, real-app click test, screenshots)
- [x] Report filled in; merged into `main`; release 0.2.7

## Not in this task

- Point 4 (face painting): task 0010. Points 17–18 (part-type rules, CAD materials): task 0008.

---

## Report

**Chat / date:** lead chat, 4 Nov 2026

**What changed:**
- `blender/tree.py` (new): the tree list. Rows for subassemblies *and* parts; identical part
  names under one parent are one row with `same = N`; identical subassembly names get the CAD
  occurrence name (`NAME:2`) or ` :k`. Open state per assembly object (`fr_tree_open`, carried
  over by a model update). `visible_rows` (open branches, or search matches with their
  parents), `row_of` (object -> row, cached), `row_objects`, `follow_view` (click in the view
  opens the tree to it, index set without re-selecting), `show_only` / `end_show_only`
  (`fr_iso_hidden`; parts the user hid stay hidden; `show_all` also clears it).
- `blender/finder.py` (new): search (all words, `*` wildcard), results per part name,
  put in group (hand assignment `fr_group_manual`), search -> rule (one word: `contains`,
  else a look-ahead regex; tested to match exactly the same names), rule on top, subassembly
  -> rule (`path contains`), suggestions (words of unsorted part names, cached), 28 presets.
- `blender/ops_panels.py` (new): operators for all of the above.
- `props.py`: tree item fields (`parent_index`, `is_part`, `same`, `has_kids`, `expanded`,
  `label`), `tree_search`, `isolated`, `find_*`, `found`. `tree_depth` stays (old projects).
- `ui.py`: Structure panel (tree, search row, selected-row box with Zoom / lock, Show only box),
  Looks panel (show-only unsorted, preset menu, show only a group, subassembly rule, clicked
  part box) and the new sub-panel "Find & sort parts".
- `logic.rebuild_tree` -> `tree.rebuild`; `handlers` calls `follow_view`; `reimport` keeps
  open rows.

**Tested and measured:**
- `tests/test_panels.py` (22 tests): tree rows, merged parts, labels, open/close, search,
  row click selection, view click opens the tree, show only and back, find/group/rule,
  search-vs-rule equivalence, only-inside, subassembly rule, suggestions, presets, move to
  group, every row button, tree after a model update, scene walks per rebuild.
  `test_blender.py` draws every panel and list (also with a search, "show only" and a
  subassembly row). Full suite: all pass.
- Real app (Linux, xvfb): `ui_test_app2.py` new steps – row click highlights, Zoom to it moves
  the view, Show only / Show all, find → new group → rule. Screenshots looked at (crane model);
  names no longer cut off except very long part names.
- EGR model (2,280 rows, 447 subassemblies), 2-core test machine: tree rebuild 4.6 s → 0.07 s
  (a slowdown of this branch, never released: one scene walk per "× N" row; fixed and tested;
  import from cache 10.0 s → 4.7 s with the fix);
  visible rows with everything open 44 ms → 0.5 ms per redraw; row click 25–31 ms; search
  5 ms; suggestions 11 ms (then cached); show only + back 26 ms; sort 32 ms.

**Open points / follow-up tasks:**
- Shift/Ctrl on a list row itself cannot be read by an add-on; adding to the selection is the
  arrow at the end of each row.
- Point 4 (face painting) is task 0010; points 17–18 are task 0008 (worker).
