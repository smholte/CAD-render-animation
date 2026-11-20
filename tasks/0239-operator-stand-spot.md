# 0239 – Fix from bug hunt 0209, group I: the tool-change person's stand spot when the machine is moved

**Who:** worker · **Status:** open · **Branch:** `task/0239-operator-stand-spot`
**Started by:** lead, 20 Nov 2026 (bug hunt 0209 row 18) · **Model:** Sonnet · effort Medium
**Area:** People – `core/tc_person.py` (the floor grid and `stand_spot`), its tests (`tests/test_tc_person*`); the
`operator` tour set only if its check needs a number (then `changed=` + re-record).

## Goal

The person who changes the tool stands at the same spot relative to the machine wherever the machine stands, and their
hands never go into the cabinet.

## Background

Bug hunt 0209 row 18 (`tasks/0209-bug-hunt-7.md`): `core/tc_person.py` ~129 fixes the floor grid to world cell lines
(0194), so where the cabinet edge falls depends on the model's world place; `stand_spot` (~410) has no margin for the
arms. Tour set "operator" with the model moved 1 cm … 25 cm: the person stands at −0.56 instead of −0.60 and the hands go
into "CABINET STAND" at frames 172, 460, 463 – 6 of 6 moved placements. 0183 row 16's own case (0194) holds. Suggested:
grid relative to the machine plus a one-cell margin (or check the arms' reach).

## What to do

1. A test that fails today: the operator set's machine moved by fractions of a cell (1, 7, 13, 25 cm, and turned 90°) →
   the same spot relative to the machine, no hand in the cabinet (the clash check on the person's hands, 0 rows).
2. Grid relative to the machine + a one-cell margin; or the arms' reach checked – whichever keeps 0194's case.
3. The `operator` set's stop and `tests/test_tour_clash.py` still at 0 clashes.

## Done when

- [ ] Moved / turned placements give the same relative spot and no hand clash; 0194's and 0183 row 16's cases green
- [ ] Full suite green; report filled in, merged, released

## Not in this task

Walk paths and other people (0157), other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
