# 0022 – More parts sorted on import: supplier catalogue codes

**Who:** worker · **Status:** running · **Branch:** `task/0022-more-supplier-codes`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Part library (only `core/part_types_data.py`,
`core/part_types.py`, `tests/test_part_types.py`; no UI, no `blender/`) – runs next to 0015.

## Goal

More parts get the right material on their own. On the owner's EGR model the library sorts 55 %
of the placed parts (1,540 of 2,789; task 0010's report); 1,247 stay Unsorted, many of them with
supplier catalogue numbers the library does not know yet (Misumi above all). Raise that number
without sorting things wrongly.

## Background

- Read the reports of 0008 (how the library matches: words, vendor-code patterns, parent
  assemblies, machine modules) and 0010 (the EGR measurement).
- The owner attaches the EGR STEP in this chat (ask him). **Its names never go into the
  repository** (public): not in tests, data, comments or commit messages. Write generic patterns
  and invented example codes in the same format instead.
- In-house abbreviations of the owner's company (or his clients) do not belong in the built-in
  library: they go into his own rule set once task 0015 is done. List them for him in the chat
  (top unknown words with counts – in the chat only), so he can say what they mean.

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

- [ ] EGR coverage before/after in the report (numbers only); spot check of wrong groups
- [ ] Independent check numbers in the report
- [ ] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)
- [ ] List of the owner's unknown in-house words given to him in the chat (not committed)

## Not in this task

- Rule sets (0015, running in the Looks lane at the same time: do not touch `core/rules.py`,
  `blender/`, the UI).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
