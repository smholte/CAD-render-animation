# 0341 – Import speed options: one object per sub-assembly, leave out parts hidden inside

**Who:** worker · **Status:** open · **Branch:** `task/0341-import-speed-options`
**Started by:** lead, 25 Nov 2026. The owner picked the lead's "speed options" for the import popup on 25 Nov 12:4x.
· **Model:** Opus · effort High
**Area:** Import lane. These are the same files as 0340 / 0342: `blender/import_settings.py`, `core/import_options.py`,
`importer/runner.py`, `blender/build.py`, `blender/reimport.py` (additive), their tests, guide, PC-check line and
CHANGELOG.
**Starts after:** 0342 is merged (same popup files; 0340 → 0342 → 0341).

## Goal

Two switches in the import popup's **More options**, both **off** by default, make very large models faster to work
with. Each shows a short hint about what you give up.

## What to do

1. **One object per sub-assembly (faster, parts can't move).**
   - Ticked: each sub-assembly at the level the user picks (say how the level is chosen; default the top level under
     the model) becomes one object.
   - Looks stay per part, as material slots, so groups and 3 Looks still work.
   - The tooltip says that joints, poses, Take apart and moving single parts don't work inside such an object.
   - A model update matches it as one part.
   - Measure the stress model: object count, viewport fps, model update time, file size.
2. **Leave out parts hidden inside others.**
   - Ticked: parts that cannot be seen from outside the model are not imported. Examples: parts inside a closed
     housing, and bearing rollers inside a bearing.
   - Be conservative: a part is hidden only if no view from many directions outside the model reaches any of its
     faces. Use a coarse test, e.g. rays against the Draft meshes.
   - The parts are listed in the import report as "hidden inside" and come back with a model update with the switch
     off.
   - Time the test itself on the stress model. It must save more than it costs, or say so honestly.
3. Both switches are stored per model and with "Use these next time without asking" (0342).

## Done when

- [ ] Both switches in More options with tooltips, off by default; stress-model numbers before / after in the report
- [ ] Hidden-inside test never removes a visible part on the demo, stress and test-tour models (pictures before / after)
- [ ] Tests added/updated; full suite passes; GitHub run green; real-app check
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
