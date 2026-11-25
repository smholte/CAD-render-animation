# 0342 – Import popup options: part size, bolts / nuts / washers, sub-assemblies, floor, remember

**Who:** worker · **Status:** open · **Branch:** `task/0342-import-popup-options`
**Started by:** lead, 25 Nov 2026. These are the owner's choices of 12:38–12:4x; they were split out of 0340 on 12:5x so
that 0340's paint part gets full attention.
· **Model:** Opus · effort High
**Area:** Import lane. These are 0340's files:
- `blender/import_settings.py`, `core/import_options.py` (rows added).
- `importer/runner.py` and `importer/step_reader.py`, additive: parts that are left out are dropped before meshing.
- `importer/step_meta.py`, additive: the sub-assembly tree.
- `blender/build.py`: the floor.
- `blender/props.py`, `blender/reimport.py`, additive.
- Settings, additive in `settings_store.py` and `ui_settings.py`: the switch "Ask for import settings at each import".
- `core/functions.py`, additive.
- Their tests, guide, PC-check line, tour stop and CHANGELOG.

**Not:** `place.py` (call `place.put_on_floor`, don't edit it), the paint rule (0340), `lock.py`.
**Starts after:** **0340** is merged (and 0295, for the Settings files).

## Goal

The import popup from 0340 gets the owner's other options, all with defaults that change nothing unless the user
changes them.

## What to do

1. **Part size:** **All parts** (default) / leave out parts smaller than **5 / 10 / 25 mm** / **a number the user
   types** (mm).
   - Size = the part's largest bounding-box side, in its real units.
   - Say "Leaves out about N parts" when it can be known quickly (e.g. the file is in the import cache). Otherwise say
     "Counted during the import".
2. **Bolts, nuts, washers** (found by their names, `core/fasteners.parse`): **Include** (default) / **Simple** /
   **Leave out**.
   - Simple = a light shape: a plain hex or socket head + shank from size and length when known, else the part at Draft
     detail.
   - Say what you built and the triangles saved on the stress model.
3. **More options** (folded):
   - **Sub-assemblies to include:** a **Choose…** button opens a tree with tick boxes, all ticked by default. Unticked
     branches are not imported, and the list counts the parts left out.
   - **Put the model on the floor, centred:** on for the first model in an empty project. **Off by default when the
     project already holds a model**, because separate files keep their CAD positions to each other. A model update
     never moves the model.
4. **Use these next time without asking** (tick box, bottom left). Ticked means:
   - the choices are saved as the user's defaults (not the per-file colour list – only 0340's rule);
   - the popup is skipped;
   - Settings gets the switch **Ask for import settings at each import** to bring it back;
   - the message line says "Imported with your saved import settings – change them in Settings".
5. **Left-out parts are not imported** (owner: fastest).
   - They are dropped before meshing and **listed in the import report** (count + names, grouped by reason: size,
     fasteners, sub-assembly, welds off).
   - A sub-assembly that loses all its parts is not made.
   - **Model update / Import again with other settings brings them in**, as "new" in the update report, not "missing".
6. All choices are stored per model (0340's storage) and reopen with Model update / Import again.

## Watch

- Real app at 2560 px; the tick tree with a large model (stress model: thousands of rows – it must stay quick).
- Speed on the stress model with "smaller than 10 mm" + fasteners Leave out: import time, part and triangle counts.
- Every visible change gets:
  - a tooltip
  - a guide entry
  - a PC-check line
  - a tour-stop / function-list entry with `since=` / `changed=`
  - screenshots with `tools/ui_screens.py`

## Done when

- [ ] Part size (presets + own number), fasteners Include / Simple / Leave out, sub-assembly tick tree, floor + centred,
      "Use these next time without asking" + the Settings switch
- [ ] Left-out parts listed in the import report and brought back by a model update
- [ ] Tests added/updated; full suite passes; GitHub run green; real-app check
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
