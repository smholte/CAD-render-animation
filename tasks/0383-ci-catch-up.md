# 0383 – CI: full run before the claim, a short catch-up run after it; fewer, balanced jobs

**Who:** worker · **Status:** open · **Branch:** `task/0383-ci-catch-up`
**Started by:** lead, 28 Nov 2026 (owner: "is it slower from fighting for GitHub compute?" – yes; 14 cancelled runs)
· **Model:** Opus · effort High
**Area:** Quality & delivery lane: `tools/ci_precheck.py`, `tools/ci_groups.py`, `tools/ci_status.py`,
`.github/workflows/tests.yml`, their tests, `tools/ci_times.json`, CLAUDE.md sections 2 + 5 (CI text only).
**Not:** app code. **Not** `tools/ci_real_app.py` / `tools/ci_check_pccheck.py` until **0371 and 0379 are merged** (both
change them); after that, only `GROUPS`.

## Why (28 Nov measurement, lead)

- A full run is ~32 jobs. GitHub Free runs 20 at a time for the account. Full runs took 30–35 min in the morning (≤ 6
  tasks) and 55–75 min in the afternoon; 0377's jobs waited ~10 min on average (up to 24) for a runner.
- 31 green, 9 red, **14 cancelled** runs in one day. The real cost is the **version race**: each merge makes every other
  green branch merge `main` and renumber. The precheck sees main's code as "code changed" and starts a full run (a pure
  renumber already gets docs mode). At 18:5x, three branches were all on 0.2.276.
- From 28 Nov the **version claim** (`tasks/MERGING.md`, CLAUDE.md section 2) stops the race, but it lines the full runs
  up one by one behind the claim (30–75 min each). This task makes the step after the claim short.

## Rows

- **A – full run before the claim.** A finished branch runs full with its version **not** raised (`[full run]` in the
  commit message – this already exists). Check that such a green run can serve as the basis G for row B (today a lane
  run never is one; check `run_is_proven` / `proven_state` for a `[full run]` run).
- **B – catch-up mode (new precheck mode).** It applies to a branch push whose commits since its newest full-green
  commit G are only (a) a merge of `main` and (b) the version lines, the CHANGELOG heading and documents.
  - **What it runs:** the precheck's checks, then the `lane_plan` of the files main brought in since G (diff between
    `merge-base(G, main)` and the new main parent), plus whatever the release path needs (build? Windows part A?).
    Decide and explain each choice.
  - **When it falls back to full:** shared files → full, as in lane mode.
  - **Safety:** show by reasoning and test cases which interactions a catch-up could miss, and why that is acceptable.
    If it is not acceptable, say what must stay full.
- **C – `main` after a catch-up.** Decide whether a green catch-up on top of a green full G is a proven basis for
  **reuse** on `main`. If not, `main` runs full once per release (never cancelled): measure what that costs in jobs and
  minutes, then pick.
- **D – stale runs.** A run whose branch already has a newer commit stops at the precheck, for queued runs as well
  (`cancel-in-progress` only covers some cases – check docs, lane and full).
- **E – fewer, balanced jobs.** Count a full run's jobs. Aim for ≤ 20, so one run fits GitHub Free's limit: merge small
  matrix groups and start the slowest first (`tools/ci_times.json`). `ci_real_app.py` `GROUPS` only after 0371 / 0379
  are merged. Measure before and after (`ci_status.py --record`).
- **F – claim helper.** `tools/ci_status.py --claim` / `--unclaim`: writes or empties `tasks/MERGING.md`, pushes only
  that file, refuses when the claim is held, and shows the claim and its age. Workers then never hand-edit it. Then
  update CLAUDE.md section 2 to the new order: build (lane runs) → `[full run]` green → claim → merge `main` + version
  → catch-up green → fast-forward → unclaim.
- **G – numbers.** For one task: "finished" → "released" before and after; jobs per task; queue wait. All in the report.

## Done when

- [ ] Precheck tests for every new decision (catch-up yes / no / falls back to full; stale run; claim helper)
- [ ] A real catch-up run on GitHub, green, named in the report (a `[release rehearsal]` push if the release path changed)
- [ ] CLAUDE.md sections 2 + 5 match what the code does (modes list, timings, the claim order)
- [ ] Report below filled in, with the numbers of row G and **Open points**. This is a tools task with no app version:
      `[full run]` before merging (CLAUDE.md section 2). When it merges, it uses the claim rule on `main` at that moment.

**Running beside it (28 Nov evening):** 0347 Machining · 0353 Web 3D + House · 0371 Demo (changes `ci_real_app.py`,
`ci_check_pccheck.py`) · 0377 Start & windows · 0379 PC check (changes `ci_check_pccheck.py`). 0383 owns
`ci_precheck.py`, `ci_groups.py`, `ci_status.py` and `tests.yml`; hands off the two files above until those tasks have
merged.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (runs, jobs, minutes):

**Open points / follow-up tasks:**
