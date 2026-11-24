# 0302 – More part kinds and better recognition: common machine parts from public catalogues, shape hints, "not recognised" made easy to teach

**Who:** worker · **Status:** running (24 Nov, web) · **Branch:** `task/0302-more-part-kinds`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "More parts, recognitions and materials.") · **Model:**
Opus · effort Medium
**Area:** Part library lane – `core/part_types_data.py`, `core/part_types.py`, `core/fasteners.py`, their tests; the
"not recognised" list only if the app lacks one (3 Looks, along the existing rule sets); guide, CHANGELOG.
**Not:** new looks / finishes (0270 → 0274 and the material picker 0273 do materials), painted steel from Inventor (0287).

## Background

Part names are matched as whole words in English, Dutch and German at once (CLAUDE.md 8: check every new keyword in all
three languages and against `tests/test_part_types.py`'s lists; "LINKS", "PALLET" went wrong before). The owner's own
part names are never committed – he may paste a few unrecognised names in this session to test with.

## What to do

1. **A list of common parts the library does not know yet**, from public sources (Inventor Content Center families,
   supplier catalogue names – hydraulics, linear motion, drives, pneumatics, lifting gear): hydraulic fittings and
   adapters, hose ends, valves and manifolds, pumps, motors and gearboxes, couplings, sensors and encoders, cable glands
   and connectors, linear guides, ball screws, belts and pulleys, sheaves, shackles and rope ends, gaskets and O-rings,
   grease nipples, handles and knobs, castors and levelling feet, aluminium profiles and their fittings, sheet-metal
   covers and brackets, springs, bushings, seals – each with its kind, group and an existing look. Say per entry where
   the name came from.
2. **Recognition beyond names:** for parts named "Part123", cheap and safe shape hints only (thin round with a hole =
   washer, hex prism with a bore = nut …); measure how many parts of the test models would change group.
3. **Teach it easily:** if the app has no such thing yet, a "Not recognised" list (parts left in Other) with **Make a
   rule** that opens the rule sets with the name filled in.

## Done when

- [ ] Every new keyword checked in EN / NL / DE with examples in `tests/test_part_types.py`; the test models' groups
      unchanged except where intended (listed in the report)
- [ ] Guide (part kinds) updated; full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
