# 0030 – Fasteners in supplier notation

**Who:** worker · **Status:** open – can start · **Branch:** `task/0030-fasteners-supplier-notation`
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

## Done when

- [ ] Tests for the new notations, positives and negatives; full suite and GitHub run green
- [ ] Report filled in; merged and released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
