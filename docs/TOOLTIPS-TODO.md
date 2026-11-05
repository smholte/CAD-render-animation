# Tooltips still to do

Snapshot of `tools/tooltip_report.py` on `main` at `ef54d3a` (after 0.2.10, task 0011; 5 Nov 2026): 210 buttons and settings in the side panel, **65 without a tooltip**, **28 weak**, 117 fine.

Each lane does its own panels (TASKS.md) and writes the tooltips by the style guide at the top of
`docs/USER-GUIDE.md`. The suggestions below follow it and were checked against the code; use them,
or better ones. Where the same operator sits on several buttons, give it a
`description(cls, context, properties)` classmethod with one text per button.

See the live state (also after your changes) with
`~/venv/bin/python tools/tooltip_report.py` (`--all` lists the good ones too). Tick off a row by
deleting it when your change is merged; the file goes when it is empty.

Not in the list: the choices inside drop-down lists (each item's own description) – most already
have one; check yours when you touch a setting.

## Looks lane (14)

### 1 Import

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon X | Close the model update report | icon-only button: the tooltip is all there is | Closes this update report. The model does not change | `fresing.report_clear` ui.py:185 |

### 2 Structure

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon DISCLOSURE_TRI_DOWN | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_RIGHT] | Opens every subassembly in the tree | `fresing.tree_open_all (open=True)` ui.py:292 |
| icon DISCLOSURE_TRI_RIGHT | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_DOWN] | Closes every subassembly in the tree; only the top level stays | `fresing.tree_open_all (open=False)` ui.py:293 |

### Visibility sets

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the visibility set. Double-click to rename | `FRVisSet.name` ui.py:349 |

### 3 Looks

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Show only the unsorted parts | Show only these parts (Show all brings everything back) | same text as Show only these | Shows only the parts no rule could sort (Unsorted), so you see what still needs a group. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=)` ui.py:440 |
| Show only these | Show only these parts (Show all brings everything back) | same text as Show only the unsorted parts | Shows only the parts of this group and hides the rest. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=…)` ui.py:465 |

### Sorting rules

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon ADD | Add a sorting rule (checked from top to bottom; the first match wins) | same text as From active part | Adds a rule at the top of the list (so it wins), for the selected group. Set what it looks for below, then Sort parts into groups | `fresing.rule_add` ui.py:639 |
| icon TRIA_UP | Move the selected rule up or down. Rules are checked from the top: the first rule that fits a part decides its group | same text as [icon TRIA_DOWN] | Moves the selected rule up: rules higher in the list are checked first | `fresing.rule_move (direction=UP)` ui.py:642 |
| icon TRIA_DOWN | Move the selected rule up or down. Rules are checked from the top: the first rule that fits a part decides its group | same text as [icon TRIA_UP] | Moves the selected rule down: rules lower in the list are checked later | `fresing.rule_move (direction=DOWN)` ui.py:643 |
| From active part | Add a sorting rule (checked from top to bottom; the first match wins) | same text as [icon ADD] | Adds a rule 'Part name contains <the clicked part's name>' for the selected group, at the top of the list. Edit it below | `fresing.rule_add (from_selection=True)` ui.py:657 |

### Paint schemes & templates

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the paint scheme. Double-click to rename | `FRScheme.name` ui.py:410 |

### Find & sort parts

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon CHECKBOX_HLT | Tick or untick every part name found | same text as [icon CHECKBOX_DEHLT] | Ticks every part name found | `fresing.find_tick (tick=True)` ui.py:612 |
| icon CHECKBOX_DEHLT | Tick or untick every part name found | same text as [icon CHECKBOX_HLT] | Unticks every part name found | `fresing.find_tick (tick=False)` ui.py:613 |
| Select the ticked parts in the view | Select the ticked parts in the view | repeats the label | Selects the ticked parts in the view, so you can see where they are (or hide them in 2 Structure) | `fresing.find_select` ui.py:614 |
