# 0340 – Painted, bare and partly painted parts come in right + the import settings popup (Finish)

**Who:** worker · **Status:** open (high priority – done well, not fast) · **Branch:** `task/0340-import-settings-popup`
**Started by:** lead, 25 Nov 2026.
- Owner, 23 Nov 17:07: every steel part of a work model came out bare steel although it is painted in Inventor.
- Owner, 25 Nov 12:38: wants a popup with import settings, where you choose and then press Continue. Default: keep the
  painted surface.
- Owner, 12:52 / 12:56: "the paint and bare material and partly painted are very important to the app" – **high
  priority means done well: don't go too fast.**
- Split on 12:5x: the other popup options are in **0342**. This task also takes the paint part of 0287; 0287 keeps rows
  18, 20 and 19 of 0328 and runs after this one.

· **Model:** Opus · effort **Max**

**Area:** Import / Looks:
- `core/part_types.py`, `core/cad_materials.py`: the paint rule.
- New `core/import_options.py`: pure logic – colour rows and their defaults, stored settings.
- New `blender/import_settings.py`: the popup.
- `blender/ops_import.py`: the popup after the file is picked or dropped, Import again, model update.
- `importer/step_meta.py`, additive: a quick pre-scan for colours with part counts, appearance and material names, and
  weld bodies present.
- `blender/build.py`: the finish per colour, painted faces.
- `blender/props.py`, `blender/reimport.py`, additive: the settings are stored per model, and a model update keeps them.
- `core/functions.py`, additive.
- Its tests, guide, PC-check line, tour stop and CHANGELOG.

**Not:**
- `core/rules.py` group naming and the part-type keywords (0287).
- `ui_material_picker.py` (0287 row 19); reuse its list of looks, don't change it.
- Settings files.
- Part size, fasteners, sub-assemblies, floor, "use these next time" (**0342**).
- The weld files of 0323: only call their "find welds" step, or skip it.

**Starts after:** **0323** (welds from CAD; it changes `ops_import.py` and `reimport.py`) is merged to `main`. The lead
gives the start prompt then.

## Goal

1. A part that is painted in the CAD file comes in painted in its colour, a bare part comes in as its material, and a
   part with some faces painted comes in with exactly those faces painted and the rest bare.
2. Whatever its CAD material is, it comes in the way it looks in Inventor (and Fusion), with no set-up.
3. A small popup after choosing the file shows this as a list of the file's colours, each **Paint** or **Material**,
   which the user can change before pressing **Continue**.

## Background

- **The bug:** only paints, powder coat and plastics take the CAD colour (`cad_materials.COLOURED`,
  `takes_cad_colour`; used in `part_types.cad_group` and `cad_look_for_group`). A part whose material is steel or cast
  iron becomes bare steel, even when Inventor shows it painted yellow.
- **The owner's test files:** the owner attaches three small STEP files made in Inventor (material steel):
  1. bare material
  2. painted
  3. some faces painted, the rest bare material

  They are **attach-only: never commit them** (public repository). For the repository tests, write invented files that
  copy what Inventor writes, with a new `tools/make_test_painted.py` (OCC, as `tools/make_test_weldment.py` does).
- Existing pieces:
  - Material and appearance names from the file text: `importer/step_meta.py`, which also gives names of single faces
    by colour.
  - Face colours: `importer/step_reader.py` `_face_colors`.
  - Paint on single faces: 0235.
  - Looks list: `materials_lib` and the 0273 picker's library, own materials included.
  - Adjust a look: 0314.
  - Model update keeps the work: 0052, 0324.
  - Drop = button: 0289.
  - Options today: Detail and Up axis in the file browser's side panel (`FRESING_OT_import_step.draw`).

## Step 1 – findings first, then the owner's OK (no building before it)

1. Read the three files and write down in the report, per file, exactly what Inventor wrote:
   - the colour entities (part, body, face), with their RGB values;
   - the `STYLED_ITEM` / `FILL_AREA_STYLE` names;
   - the material names (`PROPERTY_DEFINITION` / `MATERIAL_DESIGNATION`);
   - how the painted faces of file 3 differ from the rest.

   Say what today's import does with each file (render one picture of each).
2. Propose **the rule**. Cover each case:
   - colour only;
   - paint appearance name;
   - a material appearance with a colour override;
   - face colours;
   - a colour equal to the material's own default.

   Include a table of Inventor's and Fusion's default appearance colours for steel / stainless / aluminium / cast iron /
   brass / copper / plastics, with a tolerance, and where each value comes from. Also cover:
   - parts with no material name;
   - AP203 files with colours only;
   - Fusion files, using the existing Fusion test files in `tests/data`.
3. **Stop and ask the owner in this session** with a click box. Show the findings and the rule in short words, plus
   pictures of what each of his files will look like. Build after his OK, and follow any change he asks for.

## Step 2 – build

1. **The paint rule** in `core/` (pure, fully tested): every part and every face gets **Paint (in its CAD colour)** or
   **Material** by the agreed rule.
   - Painted faces keep their own paint; the rest of the part follows the part's own row.
   - A painted part sits in a group per paint colour. In 3 Looks that group can still be switched to its material with
     the picker as usual.
2. **The popup** opens after a STEP file is picked or dropped, and replaces the file browser's side-panel options. The
   side panel then says "Settings come after you pick the file".
   - Small and centred, with the file name and part count at the top, then **Cancel** and **Continue** (Enter / Esc).
   - Every control gets a tooltip.
   - It is a proper dialog that doesn't close when the mouse leaves.
   - **Finish:** **Keep CAD paint** (default) / **CAD material only** (today's way: every row Material).
   - **Colours in this file:** one row per CAD colour (body and face colours), sorted by part count. Each row shows a
     swatch, the colour in words (hex in the tooltip) and the part / face count.
     - Each row has a choice of **Paint** or **Material** (owner: "Material", not "Bare metal" – not all materials are
       metals), with the default from the rule.
     - Each row also has a **fold-out** to pick a specific look: the paints (gloss, satin, matte, powder coat, painted
       cast iron …), which keep the CAD colour, and all materials of the library, own materials included, which are
       used for every part with this colour.
     - More than about 8 colours: the list scrolls, or shows the first 8 and "Show all".
   - **Welds:** a switch, on by default ("Weld beads found in the file: N"). Off: 0323's weld bodies are left out, as
     welds and as parts. Greyed with "No weld beads in this file" when none are found.
   - **Detail** (Draft / Normal / Fine) and **Up axis** (Z / Y) move here, with their stored defaults.
   - Leave room in the layout for 0342's rows (part size, fasteners, More options, "Use these next time"), so 0342 only
     adds rows.
3. **Pre-scan speed:** time the text pre-scan on the EGR cooler line (78 MB) and the stress model.
   - If it takes more than about 0.5 s, the popup opens at once with "Reading the file…" and fills the rows when ready.
   - Continue works before the scan is done; the defaults are then applied during the import.
4. **Stored per model:** each model keeps its choices per colour. Then:
   - **Model update** and **Import again** open the popup filled with them.
   - New colours in a revision get the defaults and are named in the update report.
   - **Old projects** have no stored settings: today's result is kept unless the user changes it. Say clearly in the
     guide / message how to get the new paint on an old model: Model update, then Keep CAD paint.
5. **No popup for scripted imports:** the demo kits, the Learning hub / tour, the PC check, tests and the queue use the
   arguments (defaults). Client view: the popup appears (Import is allowed there, 0062).
6. **Check the demo and test-tour models:**
   - With Keep CAD paint, re-import the demo kits and test-tour models and compare pictures before / after.
   - Any model whose look changes for the worse (e.g. a part meant as bare that now becomes paint) is a rule problem:
     fix the rule, not the model.
   - Steel weldments: a weldment whose parts all carry the same CAD colour gets one look. This is part of 0328 row 20;
     say what remains for 0287.

## Step 3 – review and the owner's OK before merging

1. **Independent review:** a helper that did not write the code reads the rule, its tests and the popup code against
   this brief (CLAUDE.md "Subagents in a worker session"). Fix what it finds and list it in the report.
2. **Pictures for the owner:** Cycles renders (same camera and light) of:
   - his three files and the invented test files, today vs new;
   - a demo kit and the stress model, before / after;
   - the popup (`tools/ui_screens.py`, also at 2560 px).

   Show them in this session and **merge only after his OK**.
3. Real app (`tools/ci_real_app.py`): pick, drop, Import again, model update, Esc / Enter, the fold-out.
4. Speed: an import with defaults must not get more than ~2 % slower (stress model).
5. Every visible change gets:
   - a tooltip
   - a guide entry (1 Import, plus a new "Import settings" part)
   - a PC-check line
   - a tour-stop / function-list entry with `since=` / `changed=`

## Done when

- [ ] Findings + rule in the report, OK'd by the owner before building
- [ ] With defaults: the owner's file 2 comes in painted in its colour, file 1 as bare steel, and file 3 with exactly
      the painted faces painted and the rest bare; Fusion and AP203 test files as agreed
- [ ] Popup: Finish, colour list (Paint / Material + fold-out with paints and all materials), Welds, Detail, Up axis;
      Model update / Import again reopen it with the model's own choices; old projects unchanged until changed; scripted
      imports show no popup
- [ ] Demo kits / test tour checked before / after; nothing got worse
- [ ] Independent review done; pictures OK'd by the owner
- [ ] Tests added/updated; full suite passes; GitHub run green; real-app check
- [ ] Report below filled in, merged, released

## Not in this task

- **0342:** part size, bolts / nuts / washers, sub-assemblies, floor + centred, "Use these next time without asking" +
  the Settings switch.
- **0341:** speed options (one object per sub-assembly, parts hidden inside).
- **0287:** group names in words, one look per weldment's groups, picker names.
- The mesh import (glTF, OBJ, FBX) keeps its own options.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings (step 1):**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
