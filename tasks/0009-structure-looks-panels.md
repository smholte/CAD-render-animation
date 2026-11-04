# 0009 – Structure and Looks panels: tree, highlight, search, grouping tools

**Who:** lead · **Status:** running · **Branch:** `task/0009-structure-looks`
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

- [ ] All points above, tested (panel tests, real-app click test, screenshots)
- [ ] Report filled in; merged into `main`; release

## Not in this task

- Point 4 (face painting): task 0010. Points 17–18 (part-type rules, CAD materials): task 0008.

---

## Report

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
