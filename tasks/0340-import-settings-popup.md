# 0340 – Import settings popup: keep the CAD paint, welds, part size, fasteners, sub-assemblies

**Who:** worker · **Status:** open (high priority) · **Branch:** `task/0340-import-settings-popup`
**Started by:** lead, 25 Nov 2026. The owner reported on 23 Nov 17:07 that every steel part of a work model came out
bare steel although it is painted in Inventor. On 25 Nov 12:38 he asked for a popup with import settings, where you
choose and then press Continue. Its defaults: keep the painted surface, welds on, all part sizes. The lead's extra
ideas were picked on 25 Nov 12:4x. This task takes over the paint part of 0287; 0287 keeps rows 18, 20 and 19 of 0328
and runs after this one.
· **Model:** Opus · effort High
**Area:** Import lane:
- `blender/ops_import.py`: the popup after the file is picked or dropped, Import again, model update.
- New `blender/import_settings.py` (the popup and its sub-assembly list) and new `core/import_options.py` (pure logic:
  colour rows and their defaults, size / fastener / sub-assembly filters, stored settings).
- `importer/step_meta.py`, additive: a quick pre-scan for colours with part counts, the sub-assembly tree and whether
  weld bodies are present.
- `importer/runner.py` and `importer/step_reader.py`, additive: parts that are left out are dropped before meshing.
- `core/part_types.py` and `core/cad_materials.py`: the paint rule.
- `blender/build.py`: the finish per colour, and the floor.
- `blender/props.py` and `blender/reimport.py`, additive: the settings are stored per model, and a model update keeps them.
- Settings, additive in `settings_store.py` and `ui_settings.py`: the switch "Ask for import settings at each import".
- `core/functions.py`, additive.
- Their tests, guide, PC-check line, tour stop and CHANGELOG.

**Not:**
- `core/rules.py` group naming and the part-type keywords (0287).
- `ui_material_picker.py` (0287 row 19); reuse its list of looks, don't change it.
- `place.py`: call `place.put_on_floor`, don't edit it (Place lane).
- The weld files of 0323 (`core/weld_cad.py`, `blender/weld_cad.py`, `blender/welds.py`): only call their "find welds"
  step, or skip it.
- `lock.py`.

**High priority** (owner 25 Nov 12:52: paint, bare material and partly painted are very important to the app).
**Starts now** (owner 12:5x). Two running tasks share a file with this one, so keep this order:
1. First, everything that is not in `blender/ops_import.py` or Settings: the paint rule (`core/part_types.py`,
   `core/cad_materials.py`, `blender/build.py`, painted faces), `core/import_options.py`, the popup in the new
   `blender/import_settings.py`, the pre-scan in `importer/step_meta.py`, and the filters in the importer. Test them
   through the operator's arguments.
2. Last, wire the popup into `blender/ops_import.py` (and the additive part of `reimport.py`). Do this only once **0323**
   (welds from CAD, which changes `ops_import.py` and `reimport.py`) is on `main`. Check `git log origin/main --oneline |
   grep "0323"`, then merge `main` into your branch first.
3. Last, the Settings switch (`settings_store.py`, `ui_settings.py`). Do this only once **0295** (Keys tab, which changes
   those two files) is on `main`.

If 0323 or 0295 is still not merged when step 1 is done, tell the owner, push your branch and wait – do not edit those
files before.

## Goal

After choosing a STEP file (button, drop, Import again or model update), a small popup shows the import settings with
good defaults. Press **Continue** and the import runs. Painted parts come in painted, whatever their CAD material.

## Background

- **The bug** (owner, 23 Nov): only paints, powder coat and plastics take the CAD colour (`cad_materials.COLOURED`,
  `takes_cad_colour`; used in `part_types.cad_group` and `cad_look_for_group`). A part whose material is steel or cast
  iron comes in as bare steel, even when Inventor shows it painted yellow. Nothing since 0287 has changed this. Find out
  from the owner's files how Inventor writes a painted part: an appearance name, a colour only (a part override), or a
  face style.
- **The owner's test files:** at the start of the session the owner attaches three small STEP files made in Inventor
  (material steel):
  1. bare material
  2. painted
  3. some faces painted, the rest bare material

  Read their colours, appearance names and material names, and set the defaults from them. They are **attach-only:
  never commit them** (public repository). For the repository tests, write invented files that copy what Inventor
  writes, with a new `tools/make_test_painted.py` (OCC, as `tools/make_test_weldment.py` does).
- Existing pieces:
  - Import options in the file browser's side panel today: Detail and Up axis (`FRESING_OT_import_step.draw`, and
    `scene.fresing.import_quality` / `import_up_axis`).
  - Drop = button (0289).
  - Model update keeps the work (0052, 0324).
  - Fastener names: `core/fasteners.parse`.
  - Material and appearance names from the file text: `importer/step_meta.py`.
  - Looks list: `materials_lib` and the 0273 picker's library, own materials included.
  - Paint on single faces: 0235.
  - Floor: `place.put_on_floor`.

## What to do

1. **The popup** opens after a file is picked or dropped.
   - It replaces the file browser's side-panel options. The side panel then says "Settings come after you pick the file".
   - Small and centred, with the file name and part count at the top, then **Cancel** and **Continue** (Enter =
     Continue, Esc = Cancel).
   - The look follows the owner's sketch of 25 Nov: rows with short labels, a grey hint line under each, and segment
     buttons or switches.
   - Every control gets a tooltip.

   Sections, in this order:

   - **Finish:** **Keep CAD paint** (default) / **CAD material only** (today's way).
     - Under it is the list **Colours in this file**. It has one row per CAD colour (body colours and face colours),
       sorted by part count.
     - Each row shows a swatch, the colour in words ("Yellow", "Dark grey", with the hex in the tooltip) and the part
       count.
     - Each row has a choice of **Paint** or **Material** (owner: "Material", not "Bare metal" – not all materials are
       metals).
     - Each row also has a **fold-out** to pick a specific look:
       - the paints (gloss, satin, matte, powder coat, painted cast iron …) – a paint keeps the CAD colour;
       - all materials of the library, own materials included – a material is used for every part with this colour.
       - Default: the fold-out stays closed (Paint = the app's default paint for that CAD paint, Material = the look
         the CAD material gives today).
     - **Default per row:**
       - **Paint** for every colour, except a colour that is the CAD material's own default appearance colour. Build a
         small table of Inventor's and Fusion's default steel / stainless / aluminium / cast iron / brass / copper
         colours, with a tolerance, checked against the owner's file 1. Those rows default to **Material**.
       - A row also defaults to Material when the appearance name is a known material or finish that is not paint.
       - Plastics and paints already take their colour, as now.
     - **CAD material only** sets every row to Material.
     - Painted faces (file 3) follow their colour's row. The rest of the part follows the part's own colour row.
     - After import, a painted part sits in a group per paint colour. In 3 Looks that group can still be switched to its
       material with the picker as usual.
     - More than about 8 colours: the list scrolls, or shows the first 8 and "Show all".
   - **Welds:** switch, on by default ("Weld beads found in the file: N").
     - Off: the weld bodies that 0323 finds are left out entirely, as welds and as parts.
     - The row is greyed with "No weld beads in this file" when the pre-scan finds none.
   - **Part size:** **All parts** (default) / leave out parts smaller than **5 / 10 / 25 mm** / **a number the user
     types** (mm).
     - Size = the part's largest bounding-box side, in its real units.
     - Say "Leaves out about N parts" when it can be known quickly (e.g. the file is in the import cache). Otherwise
       say "Counted during the import".
   - **Bolts, nuts, washers** (found by their names): **Include** (default) / **Simple** / **Leave out**.
     - Simple = a light shape: a plain hex or socket head + shank from `fasteners.parse` size and length when known,
       else the part at Draft detail.
     - Say what you built and the triangles saved on the stress model.
   - **Detail** (Draft / Normal / Fine) and **Up axis** (Z / Y) move here from the side panel. They keep their stored
     defaults.
   - **More options** (folded):
     - **Sub-assemblies to include:** a **Choose…** button opens a tree of the file's sub-assemblies with tick boxes,
       all ticked by default. Unticked branches are not imported. The list counts the parts left out.
     - **Put the model on the floor, centred:** on for the first model in an empty project. **Off by default when the
       project already holds a model**, because separate files keep their CAD positions to each other. A model update
       never moves the model.
   - Bottom left: **Use these next time without asking** (tick box). Ticked means:
     - the choices are saved as the user's defaults (not the per-file colour list – only its rule);
     - the popup is skipped;
     - Settings gets the switch **Ask for import settings at each import** to bring it back;
     - the message line says "Imported with your saved import settings – change them in Settings".
2. **Left-out parts are not imported** (owner: fastest).
   - They are dropped before meshing and **listed in the import report** (count + names, grouped by reason: size,
     fasteners, sub-assembly, welds off).
   - A sub-assembly that loses all its parts is not made.
   - **Model update / Import again with other settings brings them in.** Their work matching follows 0324 / 0052:
     parts that were left out are "new" in the update report, not "missing".
3. **Stored per model:** each model keeps its import settings, including the colour choices per colour. Then:
   - **Model update** and **Import again** open the popup filled with that model's settings.
   - New colours in a revision get the defaults and are named in the update report.
   - An old project without stored settings gets today's behaviour as its "settings", so nothing changes on update
     unless the user changes it.
4. **Pre-scan speed:** the popup must not wait on a full read.
   - Time the text pre-scan (colours, tree, weld bodies) on the EGR cooler line (78 MB) and the stress model.
   - If it takes more than about 0.5 s, the popup opens at once with "Reading the file…" in the colour list and fills
     the rows when ready.
   - Continue works before the scan is done; the defaults are then applied during the import.
5. **No popup for scripted imports:** the demo kits, the Learning hub / tour, the PC check, tests and the queue use the
   operator's arguments (defaults) without the popup. Client view: the popup appears, since the Client view lets Import
   in (0062).
6. AP203 files have no material or appearance names: the colour list still works on colours alone, and the Material
   choice gives the look today's import gives.

## Watch

- Real app (`tools/ci_real_app.py`):
  - The popup is a proper dialog, not a hover popup that closes when the mouse leaves.
  - Check it at 2560 px screen scale.
  - Check the fold-out per colour row.
  - Check drop on the 3D view.
  - Check Esc / Enter.
- Speed on the stress model:
  - with defaults, the import time must not grow more than ~2 % (pre-scan included);
  - with "smaller than 10 mm" and fasteners Leave out, give the import time, part and triangle counts.
- Steel weldments: with Keep CAD paint, a weldment whose parts all carry the same CAD colour gets one look. If that
  colour is the material's own, the look is Material. This is part of 0328 row 20, so say in the report what remains
  for 0287.
- Every visible change gets:
  - a tooltip
  - a guide entry (1 Import, plus a new "Import settings" part)
  - a PC-check line
  - a tour-stop / function-list entry with `since=` / `changed=`
  - screenshots with `tools/ui_screens.py`

## Done when

- [ ] The owner's file 2 imports painted in its colour, file 1 as bare steel, and file 3 with painted faces + bare
      rest, all with defaults
- [ ] Each colour row: Paint / Material + a fold-out with paints and all materials; CAD material only = today's way
- [ ] Welds switch, Part size (presets + own number), fasteners Include / Simple / Leave out, sub-assembly tick tree,
      floor + centred, Detail / Up axis in the popup; left-out parts listed in the import report and brought back by a
      model update
- [ ] "Use these next time without asking" + the Settings switch; scripted imports show no popup
- [ ] Model update / Import again open the popup with the model's own settings; old projects update as before
- [ ] Pre-scan timed on EGR + stress model; default import time within ~2 %
- [ ] Tests added/updated; full suite passes; GitHub run green; real-app check
- [ ] Report below filled in, merged, released

## Not in this task

- "One object per sub-assembly" and "leave out parts hidden inside others" (speed options) → **0341**, after this one.
- Group names in words, one look per weldment's groups, picker names (0287).
- The mesh import (glTF, OBJ, FBX) keeps its own options.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
