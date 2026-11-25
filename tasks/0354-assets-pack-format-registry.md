# 0354 – Assets pack P1: pack format, registry and test pack (invisible)

**Who:** worker · **Status:** running · **Branch:** `task/0354-assets-pack-format-registry`
**Started by:** lead, 25 Nov 2026 23:3x (0344's P1; owner's picks 23:17) · **Model:** Opus · effort High · Claude Code
on the web, environment "CAD-render-animation"
**Area:** new **Assets** lane – new files only: `fresing_render/core/assets_pack.py`, `fresing_render/core/assets_registry.py`,
`fresing_render/pccheck/assets_test_pack.py` (the test-pack maker, shipped so the PC check can make it on a user's PC
later), `tools/make_test_assets_pack.py` (a thin command-line wrapper around it), their tests, CHANGELOG + version files.
**Not:** any existing app file – nothing calls the new modules yet (that is 0355); `pccheck/checks.py` (0346 adds lines
now; the PC-check line comes with 0357); `installer/`, `.github/` (0356, 0358); the looks themselves.

## Goal

The invisible base of the Fresing assets pack: the app can find and read a pack folder (`pack.json`), check it without
ever crashing, and answer "pack item or today's built-in look?" for any asset id – and one maker writes a small made-up
test pack at test time, so every later task can test with and without a pack. **Nothing changes for users.**

## Background (read first – only the parts named)

- `tasks/0344-study-assets-pack-plan.md`: **"Owner's picks"** (top – they win where the report differs), report **"In
  short"**, **1.1** (zip and folder layout, `pack.json` fields), **1.2** (where the app looks: `FRESING_ASSETS`, a
  company folder, the install folder; background Blenders), **1.5** (a broken or missing pack), **2.1** (ids =
  `<kind>:<today's code id>`, every pack id has a code twin), **2.2** (how a system asks, in which order; nothing in the
  hot paths touches the disk), **2.3** (the contract per kind), **2.5** (what a project stores – names only; storing is
  0355), **5** (qualities and budget).
- The proof on branch `task/0344-study-assets-pack-plan`, folder `tools/assets_pack_proto/` (`git fetch origin
  task/0344-study-assets-pack-plan`, then `git show origin/task/0344-study-assets-pack-plan:tools/assets_pack_proto/<file>`):
  `registry_proto.py` is the shape of the two core modules (19 self-checks), `make_test_pack.py` the shape of the maker,
  `README.md` how they ran. Study code – take what fits, don't copy blindly.
- Patterns to follow: the demo kits' outside folder found by an environment variable (`core/demo_kits.py`,
  `FRESING_DEMO_KITS`); the settings file's "ignore, one line, never a crash" rules (`core/settings_file.py`, 0283).
- CLAUDE.md section 6, "Old projects – the baseline" and the assets-pack rules: this task is part of the groundwork the
  baseline waits for.

## What to do

1. **`core/assets_pack.py`** (plain Python, no `bpy`): read and check `pack.json` as in 1.1 / 1.5 – format and format
   version, the app window `app_min`–`app_max`, one contract number per kind (`CONTRACTS`), ids (`<kind>:<id>`; a file
   path outside the pack folder is refused), `qualities` (draft 1k · normal 2k · final 4k – pick 2), per-set `budget_mb`
   and per-asset `cost` (render time against its code twin – pick 10: above 1.3 × only with an `approved_slower` mark
   from the owner's pick page), the pack's total size (pick 11: ~300 MB for 1.0 – a warning number, not a hard stop).
   **Never raises:** no `pack.json` → no pack, nothing said; damaged / not ours / newer format / app outside the window →
   no pack + **one** plain note (the technical reason to the console); a bad row or a newer contract → that id uses its
   code look, one note counts them. A `verify()` that checks every listed file's size and sha256 – only called after an
   install or a pack update (0356 / 0358 call it), never at every start. **Where to look** (1.2): `FRESING_ASSETS` → a
   folder the caller passes in (the company set-up's shared pack – its `.frsetup` part comes with 0358) →
   `<install folder>\Fresing Assets`. It must work in a background Blender too (queue, tour / demo builds, PC check),
   which never reads the settings file.
2. **`core/assets_registry.py`** (plain Python): the kinds and today's code ids per kind (2.1's table) – **read them from
   the code modules where they live** (`materials_lib.UIDS`, `finishes`, `studio`, `surroundings`, …) so a new code
   look is never missed; `weather` stays code. `resolve(...)` answers pack item or code in 2.2's order (the project's
   own copy first is the Blender side's job in 0355 – give it what it needs to ask); a pack-only id must name a code
   twin or a `fallback`, else it is refused with a note; `problems()` for Settings and the PC check later. Answers come
   from memory – the pack's index is read once.
3. **The test-pack maker** – one function in `pccheck/assets_test_pack.py`, called by `tools/make_test_assets_pack.py`
   and by the tests (no second copy): writes a small made-up CC0 pack into a given folder **at test time** –
   `pack.json`, a placeholder `LICENSE-ASSETS.txt` that says it is a test pack, one item per kind that has a contract
   (at least: a material node group "FRP <id>" on 2.3's material contract – inputs `Colour` + numbers, outputs
   `Colour` / `Metallic` / `Roughness` / `Normal`, no BSDF and no Output inside; a finish group; a light picture; a
   prop; an environment module with its own floor material), small pictures at 1k and 2k made by code, the 256 px
   picker pictures, and a **second version `1.1.0`** with one changed look and one changed picture (0355's update tests
   need it). **No binary in the repository.** Data only – no Text datablocks, no Python drivers, no scripts, no handlers
   (1.5). Quick: aim under 30 s; say the time and size in the report. It needs Blender to write the `.blend` files – run
   it the way the other makers do (background Blender or bpy as a module, CLAUDE.md section 4).
4. **Tests:** plain tests for every rule of 1.5 (missing, damaged, not ours, newer format, outside the window, a bad
   row, a path outside the pack, a newer contract per kind, a size / sha256 mismatch in `verify()`), the ids (every code
   id of every kind resolves; a pack-only id without a twin or fallback is refused), the resolve order, read-once (a
   second answer opens no file). One real-Blender test: the maker writes a pack, `assets_pack` reads it with no notes,
   every `.blend` opens and holds what `pack.json` lists and nothing that can run code.
5. CHANGELOG: one plain line ("groundwork for the Fresing assets pack – no visible change"). No guide chapter, function
   entry, PC-check line or tour stop – nothing is visible yet; if the precheck asks for one, say so in the report
   instead of adding UI.

## Done when

- [ ] The two core modules, the maker and their tests are on `main`; the app looks and works exactly as before (no
      existing app file changed).
- [ ] Every rule of 0344 report 1.5 has a test; the full run on GitHub is green.
- [ ] Report: the modules' interfaces written out (functions, arguments, what they return, the notes' texts) – **0355,
      0356 and 0358 build on them**; the maker's time and size; anything in 0344's plan that turned out different.
- [ ] Report filled in, merged, released (section 7).

## Not in this task

Bringing anything into a project (0355); Settings > Assets and the switch (0357); the installer, the pin and pack
updates (0358); the pack checks, CI jobs and releases (0356); real looks; licence texts. Never the owner's files; never
his employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
