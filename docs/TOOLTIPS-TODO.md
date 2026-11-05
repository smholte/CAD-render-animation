# Tooltips still to do

Nothing left: every button and setting in the side panel has a tooltip (Looks lane: task 0023;
Motion lane – panels 4 Motion, 6 Animation, 7 Render queue and Saved scenes – task 0012; Scene &
Render lane before that). Check the live state with `~/venv/bin/python tools/tooltip_report.py`
(`--all` lists the good ones too).

A task that adds a button or setting writes its tooltip in the same change, by the style guide at
the top of `docs/USER-GUIDE.md`, and runs the check before merging. If the check finds something
it cannot fix in its own panels, it lists the row here, under its lane.
