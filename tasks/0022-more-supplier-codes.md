# 0022 – More parts sorted on import: supplier catalogue codes

**Who:** worker · **Status:** done (0.2.14) · **Branch:** `task/0022-more-supplier-codes`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Part library (only `core/part_types_data.py`,
`core/part_types.py`, `tests/test_part_types.py`; no UI, no `blender/`) – runs next to 0015.

## Goal

More parts get the right material on their own. On the EGR test model (GrabCAD) the library sorts 55 %
of the placed parts (1,540 of 2,789; task 0010's report); 1,247 stay Unsorted, many of them with
supplier catalogue numbers the library does not know yet (Misumi above all). Raise that number
without sorting things wrongly.

## Background

- Read the reports of 0008 (how the library matches: words, vendor-code patterns, parent
  assemblies, machine modules) and 0010 (the EGR measurement).
- The owner attaches the EGR STEP in this chat (ask him). It is a **public GrabCAD model** made
  by someone else (not the owner's or his clients'): do not commit the file or lists of its
  names; write generic patterns and invented example codes in the same format.
- Its unknown abbreviations are its maker's in-house words, not the owner's: do not tune the
  library to them. Tune only to public knowledge (supplier catalogues, common machine-building
  words in EN/NL/DE) – the EGR file is a measuring stick, not the target.
- Ask the owner whether he can also attach **one of his own models** (Inventor or Fusion, chat
  only, never committed) – a second measuring stick with his own naming. Unknown words in his
  own model: list them for him in the chat; his company words go into his own rule set (0015).

## What to build

1. From the EGR names, find the biggest groups of unknown codes (by prefix/format, with counts –
   kept in the chat). For each supplier family that is public catalogue knowledge (Misumi
   shafts, linear bushings, brackets, pins, spacers, hinges, handles, plungers, …; and other
   suppliers that show up), add code patterns to `core/part_types_data.py` with the right part
   type.
2. Tests with invented codes in the real formats (positive and negative: a code pattern must not
   take ordinary words or other suppliers' codes).
3. **Independent check** as in 0008: a helper that has not seen the changes writes 200 realistic
   names with supplier codes and the expected group; report before/after.
4. Measure again on the EGR file: placed parts and part names sorted, before → after; and how many
   went to a group that looks wrong (spot check of 50, numbers only).

## Done when

- [x] EGR coverage before/after in the report (numbers only); spot check of wrong groups
- [x] Independent check numbers in the report
- [x] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)
- [x] If the owner attached one of his own models: its coverage too, and its unknown words
      listed for him in the chat (not committed) – he has no model with his naming yet

## Not in this task

- Rule sets (0015, running in the Looks lane at the same time: do not touch `core/rules.py`,
  `blender/`, the UI).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4–5 Nov 2026. Released as 0.2.14.

**What changed:**

- **Supplier catalogue codes** (`core/part_types_data.py`), all from public catalogue pages
  (Misumi, SMC, Omron, THK, Sankyo, Oiles, NBK), with the part type each one is:
  - Misumi, about 60 families: linear shafts incl. economy `C-`/`C` prefix and configured codes,
    rotary shafts, set collars, posts, spacers and collars, dowel/locating/stop pins (any pin with a
    tip field `-P8.5`, also with the `G` prefix), plungers, stopper bolts, keys, device stands,
    shaft supports and holders, linear bushings and housings, miniature guides (also two series
    letters, `SEBNZ`), ball and lead screws, support units, cam followers, bearings with Misumi
    prefixes, bearing holders, oil-free / multi-layer / locating bushings, couplings with two
    bores, timing pulleys and idlers, belts, rollers, urethane bumpers and washers, shock absorbers,
    levelling mounts, casters, hinges, magnet catches, handles, knobs, indexing plungers, toggle
    clamps, floating joints, frame nuts and caps, acrylic plates, cable carriers, cables, stands.
  - SMC JCQ compact cylinders; a cylinder series followed only by a switch model
    (`JCDQ-M9B`, `CDQ2B-M9BW`) is the switch. THK blocks with seal letters and rails with length.
    Omron V680 RFID. Sankyo Oilless, Oiles, NBK couplings. Ganter star knobs (GN/DIN 6336); Ganter
    feet and hinges are no longer taken by the GN handle pattern. Festo `MS6-10` is no longer a
    service unit (`MS6-LFR…` still is): `MS6-10` is a Misumi dowel pin.
  - Words: `LIMIT SW`, `PROX SW`, `REED SW`, `PRESSURE SW`, `TOUCH PC`, `POST`, `PILLAR`.
- **Matching** (`core/part_types.py`, `_pick_best`): a vendor code now beats the words next to
  it ("LMUW20 BUSHING" is a linear bushing, "PSFJ16-400_SHAFT" a linear shaft, "HBLTD6 BRACKET" a
  profile bracket), as a product code already did. A BUSHING inside a linear-bushing assembly is
  part of it.
- **Fewer wrong groups** (all common words, not the model maker's): a bare `LINK` is a link bar
  (Plates, blocks & brackets), not a chain ("CHAIN LINK" still is); a bare `PALLET`/`PALETTE` is a
  workpiece pallet of a conveyor and gets no type ("WOODEN PALLET", "EURO PALLET", "EPAL",
  "HOLZPALETTE" are still wood); "SENSOR POST" is a post, not a sensor.
- **Tests** (`tests/test_part_types.py`): about 200 invented codes in the real formats (alone, with
  a word, file suffix, occurrence number or the supplier's name), 30 look-alikes that must keep
  their group (drawing numbers, steel sections, other suppliers' codes, "PALLET", "PLATE-A93"), a
  check that no supplier code is also taken by another group's pattern, and parts inside supplier
  assemblies (SMC cylinder with switch, Misumi guide, floating joint, bushing housing).
- User guide, chapter 3: supplier codes named.

**Tested and measured** (2-core Linux test machine):

- **EGR model** (GrabCAD, AP203, attached in the chat, not in the repository). This import counts
  2,745 placed parts and 579 part names (task 0010 counted 2,789 / 582 another way). Default rules
  (Standard rule set):

  | | placed parts sorted | part names sorted |
  | --- | --- | --- |
  | before (main 0.2.13) | 1,521 of 2,745 (55.4 %) | 338 of 579 (58.4 %) |
  | after (0.2.14) | 1,840 of 2,745 (67.0 %) | 378 of 579 (65.3 %) |

  477 placed parts changed group: 340 from Unsorted into a group; 116 from one group to another
  (63 pallet parts out of "Wood parts", 37 "link" parts out of "Chains", 20 sensor posts out of
  "Sensors & switches", 14 cylinder rods from "Shafts" to "Chrome rods", 3 THK blocks from
  "Plates" to "Linear guides"); 21 workpiece pallets from "Wood parts" back to Unsorted (no good
  group for them). All 477 changes were looked at: all look right.
- **Spot check** of 50 random sorted placed parts (after): 48 look right, 2 look wrong (an SMC
  switch named with underscores comes out as the cylinder; a conveyor rail as a linear guide) –
  both were the same before this task; 1 borderline (a cover inside a roller assembly is a
  conveyor roller). A first spot check on an in-between version found 3 wrong + 1 borderline and
  led to the switch, POST, LINK and PALLET changes above.
- **What stays Unsorted on EGR** (905 placed parts): 634 dotted abbreviations of the model's
  maker, 143 generic "PARTn", 100 codes of suppliers without a public catalogue the chat could
  find (mostly Korean), 12 fasteners in Misumi/Korean notation, 16 other words. Not tuned to them
  (the maker's in-house words, as the brief says).
- **Independent check:** a helper agent that had not seen the library wrote 230 names (200 with
  supplier codes, 106 of them Misumi; 30 that name no part). Before this task 79 of 200 (40 %)
  went to the expected group (10 to another group); with the first set of patterns, written
  before the helper's list was seen, 119 of 200 (60 %). After tuning on its misses 176 of 200
  (88 %, 5 to another group) – this last number is no longer independent. The 30 non-parts stay
  Unsorted every time. Left out on purpose: pure-number codes (norelem `03090-…`, Mädler, Tente)
  and Kipp `K0338.…` – they look like in-house drawing numbers.
- Speed: sorting the EGR model's 2,745 placed parts from scratch 0.31 s before, 0.29 s after.
- Full suite: see the merge commit (all pass); GitHub run of the branch and of `main` green.

**Open points / follow-up tasks:**

- **Fasteners in Misumi and Korean/Japanese notation** (`MSSF5-5` set screws, `WRENCHBOLT` =
  socket head cap screw, `BOLT5-20`): handled by `core/fasteners.py`, outside this lane. A small
  follow-up for the fastener rules.
- SMC switch parts named with underscores (`_MXQ_Z_A93`) and "CONV.RAIL" as a linear guide: left
  as they are (one model's naming); watch real projects.
- A workpiece pallet has no group of its own now (Unsorted); a "Pallets & carriers" group could be
  added if real projects show many.
- The owner has no model with his own naming yet: when he has one, measure it the same way and
  list its unknown words for his rule set.
