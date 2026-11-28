# 0380 – Bug and friction hunt round 9 (findings only): 0.2.247–0.2.270 used together

**Who:** worker · **Status:** running · **Branch:** `task/0380-bug-hunt-9` (task file + report only,
`[skip ci]`) · **Started by:** lead, 28 Nov 2026 · **Model:** Opus · effort High
**Area:** none – findings only, no code. Work on the **tag `v0.2.270`**, not on `main` (other tasks merge meanwhile).

## Goal

Twenty-four releases since 0328's hunt (25 Nov) – find what broke or got awkward when they are used together, as
0328 did: as a **sales person** (not technical), a **CAD engineer new to rendering** and a **skilled animator**.

## Scope

- Everything merged since 0328: 0330–0339, 0295 Keys tab, 0331 first start, 0332 quiet window + Client lock, 0333
  workspaces, 0325 long cables, 0326 joint drag, 0327 clash memory, 0346 coolant liquid, 0348 lift path, 0352
  compatibility kit (format number, newer-project message), 0354 assets registry (app without a pack), 0366 faster model
  build, 0367 shorter menus + hidden Blender tabs (**can every user still reach what he needs?**), 0368 welds at import,
  0369 welds + colours on the 3D page.
- Re-check 0328's 36 rows (fixed / still there).
- Big model: the stress model – import, update, drag, clash, save, web export.
- Old projects: only "opens without a crash or says re-import" (CLAUDE.md section 6 – the baseline rule).

## Report

A table like 0328's: row, persona, steps to repeat, what happens, expected, severity (crash / lost work / wrong /
friction), lane, file if known. Then proposed **fix tasks grouped by lane** (F1, F2 …) so two never share a file,
model · effort each. No fixes.

## Done when

- [ ] The table, 0328's rows re-checked, fix tasks grouped by lane
- [ ] Report filled in, pushed to the branch with `[skip ci]`; TASKS.md row "done – findings"


---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
