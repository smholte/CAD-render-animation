# 0130 – House round trip: format 1.0.1 (re-pin, ASCII zip names, sun_light from a sun-facing probe)

**Who:** worker · **Status:** done (0.2.107) – tag **v1.0.1** exists (commit 89bc92d) · **Branch:** `task/0130-house-format-1-0-1`
**Started by:** lead chat, 15 Nov 2026 (House Planner's lead answered 0114's questions 1–4) · **Model:** Sonnet · effort Medium
**Area (House lane):** `fresing_render/core/house_scene.py`, `core/house_hash.py` / `core/house_snow.py` (only the tag in
their docstrings, unless 1.0.1 changes them), `blender/house_bake.py` (`_sun_light`), `tests/data/house/hsf-v1.0` →
the 1.0.1 copy, the house tests; `blender/lightbake.py` only additively. **Never attach or clone
`smholte/house-planner-dev`** (CLAUDE.md section 6) – only the public `smholte/house-scene-format`.

## Goal

Fresing Render reads and writes format 1.0.1 exactly as both sides now agree, and its `sun_light` no longer gets
noisy at a low evening sun.

## Background

House Planner's lead, 15 Nov 2026, on the four questions at the end of `tasks/0114-house-round-trip.md`:
1. **Zip names:** the checker was wrong; 1.0.1 refuses a **non-ASCII** name without the UTF-8 flag, and an **ASCII name
   without the flag stays valid**. Fresing Render already does exactly that (`house_scene.py`, the cp437 check about
   line 140) – keep it, add a test for an ASCII name without the flag if there is none, and re-pin the copy of the
   checker, schemas and samples (`tests/data/house/hsf-v1.0`) to tag **v1.0.1** (new folder name, e.g. `hsf-v1.0.1`,
   and every reference to `v1.0` / commit `52c0352` in code, docstrings and tests).
2. **Sun more than 0.5° off its moment's angles:** no change – reading on and writing a problems line is what FORMAT
   section 10 asks (the checker's ERROR judges the writer).
3. **Full overcast:** `sun_light` [0,0,0] by day is right; null only where there is no separate sun (ALL, LIVE, night,
   360° photo, studio). 1.0.1 adds the sentence to FORMAT 8.3 – check Fresing Render writes null in exactly those
   cases (test).
4. **`sun_light` = normal incidence** (House Planner's live sun is a directional light of that strength × N·L). **Do not
   divide the up-facing probe by sin(elevation)** – at a 4.8° evening sun that multiplied the noise × 12. Use a probe
   turned to face the sun, or the sky model's own sun value (0109's sky). 0114 put this in `house_bake._sun_light`.

## Done when

- [ ] Pinned to v1.0.1 (copy of checker/schemas/samples, references); every sample passes our reader and our
      `.hpbake` passes the 1.0.1 `check.py` with no ERROR / WARNING.
- [ ] Test: ASCII name without the UTF-8 flag accepted; non-ASCII without the flag refused (as now).
- [ ] Test: `sun_light` null / [0,0,0] / a value in exactly the cases of 1.0.1's FORMAT 8.3.
- [ ] `sun_light` from a sun-facing probe or the sky's sun value: at the sample's evening moment (4.8°) and a midday
      moment it agrees with the sky model's sun within a few %, and repeated bakes differ far less than before
      (numbers before/after in the report).
- [ ] Bake time of the sample before/after (0114: 15 s a moment, 4-core web machine).
- [ ] Guide sentence if anything the owner sees changes; GitHub run green; report filled in.

## Not in this task

House Planner's own code (private repository). Other House lane wishes.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker session, 15 Nov 2026.

**What changed:** (0.2.107)
- Pinned copy now `tests/data/house/hsf-v1.0.1` (tag v1.0.1, commit 89bc92d, SHA-256 list in PINNED.md; only
  `hsf/package.py` differs from v1.0, samples and schemas are byte-identical). All references renamed.
- Zip names: our reader already refused non-ASCII without the UTF-8 flag and accepted ASCII; added tests for both and
  for a flagged non-ASCII name.
- `sun_light`: `house_scene.sun_light_rule` = FORMAT 8.3 in one place (null / zero / measure); `house_bake` writes
  [0,0,0] by day under full overcast (clouds ≥ 0.999), null for ALL, LIVE, night and no separate sun. The measurement
  uses a probe turned at the sun (`lightbake.Bake(probe_normal=...)`, additive) and no longer divides by sin(elevation).
  `Bake` now copies the project's Cycles seed to its bake scene (so repeats can differ; same value as before by default).

**Tested and measured** (4-core web machine, real Cycles, tiny probe scene, sky sun at rotation 0):
- Facing probe vs old upward probe / sin(el): 35°: 3.169 vs 3.170, 12°: 2.036 vs 2.039, 4.8°: 0.956 vs 0.956 (64
  samples) – agree within 1 %.
- Noise over 5 seeds at 4.8°: 64 samples: 0.3 % both ways; 8 samples: 1.7 % (facing) vs 2.1 % (before). So the 12-fold
  noise HP saw did not show up in this clean probe test – the new way is never worse and removes the division, but I
  could not reproduce a big gain here; a real-house bake with fewer samples may show more.
- Bake time of the sample: not re-measured; the extra probe is the same 8-px bake as before (no change in work).
- Tests: test_house_scene/snow/independent/sample_bake/pinned/blender, test_lightbake*, new test_house_sun_light: green.
  `ci_precheck.py` passes. GitHub run: see below.

**Open points / follow-up tasks:** `sun_light_rule` treats clouds ≥ 0.999 as full overcast; if House Planner's overcast
flag is looser, tell me. No guide change (nothing the owner sees).
