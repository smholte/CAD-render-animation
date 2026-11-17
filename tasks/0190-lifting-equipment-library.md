# 0190 – Lifting L2: the equipment library (own equipment as files, chart entry, sample mark)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0190-lifting-library`
**Started by:** lead chat, 17 Nov 2026 (study 0180, task split L2) · **Model:** Opus · effort Medium · **Place:** Claude Code
on the web, environment "CAD-render-animation"
**Area:** Lifting lane – new `fresing_render/core/lifting_library.py`, `tests/test_lifting_library.py` (+ an independent
test file); reads `core/lifting.py` (0182), does not change its checks. Runs beside 0191 (L3 crane makers).

## Goal

A user's own lifting equipment (cranes, forklifts, hoists, rigging gear) lives as plain files in his library, one folder
per item, and can be shared by copying the folder. The app reads, checks, writes and upgrades them; the built-in
samples can never lose their "SAMPLE" mark. Plain Python, no Blender – L4 puts it on screen.

## Background

- Study 0180's report, **section 4 "The user's own equipment"** is the design: read it first, then sections 2 (the data
  per kind) and 3 (what the checks need from the file). Owner's answers to 0180's questions are in its report and in
  `claude/render-app-progress.md` ("Lifting plans (owner 17 Nov)"): next longer chart row (never interpolate unless the
  file says so), BS 7121 default + ASME P30.1, generic equipment first, real makes later.
- `core/lifting.py` (0182) already has the chart: `Chart`, `chart_from_dict` / `chart_to_dict` (units), `validate_chart`,
  `validate_charts`, `pick_chart`, `lookup`, `SAMPLE_MARK`, `SAMPLE_PAGE_MARK`. **Use them – do not write a second chart
  reader.** If one of them needs a change, make it additive and keep every 0182 test as it is.
- Library folders: `blender/prefs.py` `library_dir(sub)` ("Brand kits", "Templates" use it). The core module takes the
  folder as an argument; the Blender side (L4) passes `prefs.library_dir("Lifting equipment")`.
- 0191 (L3) writes the built-in crane files at the same time, in this format. Agree through the study's section 4 and
  this brief, not through each other.

## What to build

1. **Format** `"format": "fresing-lifting-equipment"`, `"format_version": "1.0"`, the fields of study section 4
   (`kind`, `class`, `name`, `units`, `mass` + `cog` per moving group, `rig`, `charts`, `hook_blocks`,
   `outriggers` / `tracks` / `axles`, `wll`, `limits`, `sample`, `derived_from`, `source`). A short schema description
   at the top of the module (and the field list in the user guide's Lifting chapter, a new short section; no
   screenshots yet).
2. **One item = one folder** `<name>/<name>.json` + model (`.step`, `.glb`, `.obj`, `.fbx`) + optional picture.
   `list_items(folders)` over the user's folder **and** the built-in folder (read-only, given as an argument –
   0191 puts the built-ins in `fresing_render/data/lifting/`), each with kind, class, name, sample flag, problems.
   A broken item is listed with its problem, never stops the list.
3. **Read / write / upgrade:** same major version → read, unknown fields kept on write and named in a note; higher major
   → "made with a newer Fresing Render – update the app", no checks; older → upgraded in memory, written new only on
   save. Writing is atomic (temp file + replace) and never into the built-in folder.
4. **Chart entry:** a table as rows (`config`, `radius`, `capacity`) and **CSV** paste / file (`radius;capacity`
   or `radius,capacity`, a header line with the configuration, decimal comma or point, units t/kg/lb, m/ft). Refusals
   and warnings exactly as study section 4 (radii not rising, capacity ≤ 0, rising with radius, a sea column above a
   calmer one → refused; capacity rising with boom length at one radius → warned); gaps stay gaps. Every message in
   plain words with the row number.
5. **Sample mark:** built-ins carry `sample: true`; a copy (`copy_item`) keeps `derived_from` = a hash of the sample's
   charts; `sample` can be cleared only when the charts no longer equal the sample's (hash differs). Helper
   `is_sample(item)` that L4/L7 use for "SAMPLE DATA – NOT FOR REAL LIFTS" and the boom decal.
6. **Item → checks:** `charts_of(item)` → `list[lifting.Chart]` in SI; `wll_of(item)`; enough that a test can run
   `lifting.crane_use` and `lifting.wll_use` straight from a file.

## Rules for this task

- Plain Python only (stdlib); runs in the fast "core" test group. No maker's real chart, name or model anywhere –
  invented test charts only (CLAUDE.md section 6; the repository is public).
- Every rule above gets a test; the refusal list as a table-driven test. An **independent tester subagent** (CLAUDE.md
  "Subagents in a worker session") writes its own test file from this brief and section 4 without reading your code
  first; settle each fault it finds.
- No UI, no tour stop, no PC-check line (nothing visible yet – L4 adds them); function-list entry not needed yet.
- Normal finish (CLAUDE.md sections 2 and 7). No version raise is needed if nothing in the app changes visibly – follow
  0182's way (report + Done row "no release"), unless the guide section makes a docs release.

## Done when

- [ ] `core/lifting_library.py` with format, folders, read / write / upgrade, CSV + table chart entry, sample mark,
      item → `lifting.Chart` / WLL; its tests + the independent tester's tests pass.
- [ ] A round trip: a made-up item written, read, copied, its chart changed → `sample` can be cleared; unchanged →
      refused with the words.
- [ ] If 0191 is already on `main`: every built-in in `fresing_render/data/lifting/` reads without problems (a test);
      if not, 0191 adds that test when it merges.
- [ ] Guide: a short "Own lifting equipment (file format)" section.
- [ ] Report below filled in; TASKS.md row moved to Done.

## Not in this task

The panel and the chart editor on screen (L4), the crane models (0191), rigging gear makers (L8), offshore Hs charts in
use (L9 – the format must already hold an `hs` configuration key, which `lifting.Chart` has).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
