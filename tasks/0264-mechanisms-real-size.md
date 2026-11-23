# 0264 – Real size, category D: the scissor table 0.18 → 0.80 m wide, the bearing unit's shaft nut

**Who:** worker · **Status:** open – can start once a code slot is free (no shared model with 0259 / 0261–0263)
· **Branch:** `task/0264-mechanisms-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale, one fix task per type; study **0258**
category D) · **Model:** Sonnet · effort Medium
**Area:** `tools/make_test_linkage.py` (`test_linkage_a` + `_b`), `tools/make_test_sequence.py` (`test_sequence`), their
`tests/data/` files + `fresing_render/data/` copies, maker tests; `blender/tour.py` – the sets `linkage`, `sequence`,
`productvideo` (**numbers, cameras, framing only**), `pccheck/checks.py` lines that read them, the tests and tools that
read them (`grep -rln "test_linkage\|test_sequence\b" tests tools fresing_render`), guide pictures / texts that show
them, `tools/tour_versions.py`'s record.
**Not:** app code (`core/linkages.py`, `core/sequence.py` – a fault → report it), the four-bar and crank-slider (real
already), `test_sequence_frame` (real), surroundings.

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, `tasks/img/0258/2_mechanisms.jpg`): these models are small on purpose and
right – except the scissor lift table, the right length and height but 0.18 m wide (a real lift table is ~0.8 m,
EN 1570-1 sizes), and the bearing unit's ISO 4032 M24 nut on a Ø25 shaft (a real unit has a shaft lock nut).

## What to do

1. **Scissor table:** platform and scissor frame ~1.30 × **0.80** (two scissor pairs side by side, as real tables have);
   lift height, arm lengths and the mechanism's plane unchanged, so the linkage's numbers stay; pins / bolts real.
2. **Bearing unit:** the M24 nut → a shaft lock nut **M25 × 1.5** (KM5-style, with its tab washer if cheap) – named in the
   same supplier style the part library sorts (check `core/part_types_data.py` knows it; if not, say so – app data is
   not this task's).
3. Same part names where a test or stop reads them (a renamed nut: change the reader in the same commit, say why).
4. Sets framed again if the wider table needs it; every stop's check, 0 clashes, `changed=` + `python3
   tools/tour_versions.py --record` after merging `main` once.

## Done when

- [ ] Both makers updated (both copies, variants); maker tests green; every test, stop and PC-check line green
- [ ] Sets framed, 0 clashes, `changed=` + the record; guide pictures of these models made again if they changed
- [ ] Before / after 400 px pictures in `tasks/img/0264/`
- [ ] Report filled in, merged, released

## Not in this task

Other models (0259, 0261–0263, 0235), app code, surroundings. **Never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, Sonnet, 23 Nov 2026

**What changed:** (version 0.2.213)
- `make_test_linkage.py` (both variants A and B): platform and base 1.30 × 0.80 m (were 0.18 m wide). Each scissor arm is now
  two bars joined by a cross tube, one solid, the second pair being the first mirrored about y = 340 mm; pins run the whole
  width; one wide roller between the bars (bottom outer arm, and under the platform at the top inner arm, now with its own
  pin); second brackets `LIFT.BASE.BRACKET.2`, `LIFT.PLATFORM.BRACKET.2`. Arm lengths, heights, pin places and every
  existing part name are unchanged, so the linkage numbers, the tour stop and the PC-check line did not change. The lifting
  cylinder stays at the front side (y -100 … -60).
- `make_test_sequence.py`: the M24 hex nut became **"SKF KM 5 Locknut M25x1.5"** (KM5: Ø38, 7 high, four slots in the rim,
  bore Ø25, z 145 … 152). The part library reads it as a fastener ("Lock nut M25") in the bearings group; no app data
  change needed. Test readers of the old name (`tests/test_sequence.py`) changed in the same commit.
- Data copies (`tests/data` + `fresing_render/data`), the sets `linkage`, `sequence`, `productvideo` `changed=0.2.213` +
  `tour_versions.json` record, CHANGELOG.

**Tested and measured** (4-core web machine): `test_linkages`, `test_sequence`, `test_seq_mesh_0162_independent`,
`test_model_update`, `test_product_video` 134 passed; `test_tour.py` 109 passed; `test_tour_clash` for the three sets
(0 clashes); precheck full mode. GitHub run: see the merge. Pictures (viewer drawn from the STEP, not the app):
`tasks/img/0264/`.

**Open points / follow-up tasks:** The tour's Mechanisms view is the front view (mechanism plane), so the new width does
not show in it; an oblique view would. No tab washer on the nut (not cheap in one solid). Guide pictures were not remade
(the front view looks the same).
