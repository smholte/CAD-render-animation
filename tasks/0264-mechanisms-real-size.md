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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
