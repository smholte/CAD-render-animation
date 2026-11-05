# 0030 – Fasteners in supplier notation

**Who:** worker · **Model:** Sonnet · **Status:** done (0.2.20) · **Branch:** `task/0030-fasteners-supplier-notation`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Part library (`core/fasteners.py` and its tests
only) · Small task.

## Goal

Screws, bolts, nuts and washers named the way supplier catalogues do (Misumi, and Korean/Japanese
notation, e.g. set screws "MSSF5-5", "WRENCHBOLT" for a socket head cap screw, "BOLT5-20") are
recognised as fasteners and get the fastener groups (task 0022's report, open points).

## What to do

1. Extend `core/fasteners.py` (read it and `tests/test_fasteners.py` first): these notations,
   with thread size and length where the name gives them; invented example names in tests (never
   names from the EGR model, which is a GrabCAD model by someone else).
2. Measure on the EGR model if the owner attaches it again: fasteners found before/after (numbers only).
3. No word may stop matching that matched before (the existing example lists stay green).

4. **The owner's own bolts must stay right** (5 Nov 2026: his companies use normal metric
   bolts, DIN/ISO norms, many lengths, HDG and other coatings). Add these as test names, each to
   its fastener group with the right finish; the owner may add more in the chat:
   - `DIN 933 M16x50 8.8 HDG`, `ISO 4017 M12 x 40 - 8.8 HDG`, `DIN 931 M20x120 10.9 tZn`,
     `ISO 4014 M24x150 8.8 thermisch verzinkt`
   - `DIN 912 M10x30 12.9`, `ISO 4762 M8x25 - 12.9 zwart`, `ISO 4762 M6x20 A2-70`,
     `DIN 7991 M8x20 10.9 gvz`, `ISO 10642 M6x16 A4`, `ISO 7380 M6x12 RVS`
   - `DIN 934 M16 8 HDG`, `ISO 4032 M12 - 8 tZn`, `DIN 985 M10 A2`, `ISO 7040 M8 Zn`
   - `DIN 125 A17 HDG`, `ISO 7089 M12 - 200HV HDG`, `DIN 9021 M8 A4`, `DIN 127 B10 Zn`
   - `DIN 975 M12x1000 8.8 HDG`, `DIN 913 M6x10 45H`, `ISO 4026 M8x12 A2`
   - coatings: HDG / tZn / thermisch verzinkt (hot-dip galvanised), Zn / gvz / galvanisch
     verzinkt / elektrolytisch verzinkt (zinc plated), zinc flake (Geomet, Delta Tone),
     zwart / black / blank, A2 / A4 / RVS / stainless.

## Done when

- [x] Tests for the new notations, positives and negatives; full suite and GitHub run green
- [x] Report filled in; merged and released

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat (Sonnet), 5 Nov 2026

**What changed:** `core/fasteners.py`: new supplier-notation patterns (`_SUPPLIER`): set screws `MSSF5-5`,
`MSS4-6`, `SSS6-10`, `SSCP`/`SSCS`/`SSEB`/`SSEBS`/`SSFP`/`SSDP` variants (size and length from the name, black
oxide by default); `WRENCHBOLT` / `WRENCH BOLT` (socket cap screw, with or without `M8x20` or `6-15`); `BOLT5-20`,
`SCREW4-10`, `BOLT8`; `NUT5`; `WASHER6`. Only Misumi's own codes (`CB6-20`...) still default to black; the new generic
ones (`BOLT`, `NUT`, `WASHER`) get no default finish. Names that matched before are unchanged.
Version 0.2.20, CHANGELOG.

**Tested and measured** (2-core test machine, no EGR model attached): `tests/test_fasteners.py` 40 → 94 cases (15
supplier names, the owner's 21 bolt/nut/washer names incl. all coatings, 5 more coating words, 13 lookalike
negatives); every one of the owner's names already parsed correctly before the change (checked first), so no
behaviour change there. Fastener, part-type and core tests: 1,441 passed. EGR coverage before/after: not
measured (model not attached).

**Open points / follow-up tasks:** attach the EGR model (or the owner's own model) to measure how many more parts
the new notations catch; real supplier code lists beyond these notations (Misumi nuts and washers, Korean codes
with other prefixes) need real example names from the owner. "SSS" (set screw abbreviation, existing keyword) and
names with the size glued to an excluded word ("NUT HOUSING5") are unchanged.
