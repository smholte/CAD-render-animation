# 0383 – CI: full run before the claim, a short catch-up run after it; fewer, balanced jobs

**Who:** worker · **Status:** running · **Branch:** `task/0383-ci-catch-up`
**Started by:** lead, 28 Nov 2026 (owner: "is it slower from fighting for GitHub compute?" – yes; 14 cancelled runs)
· **Model:** Opus · effort High
**Area:** Quality & delivery lane: `tools/ci_precheck.py`, `tools/ci_groups.py`, `tools/ci_status.py`,
`.github/workflows/tests.yml`, their tests, `tools/ci_times.json`, CLAUDE.md sections 2 + 5 (CI text only).
**Not:** app code. **Not** `tools/ci_real_app.py` / `tools/ci_check_pccheck.py` until **0371 and 0379 are merged** (both
change them); after that, only `GROUPS`.

## Why (28 Nov measurement, lead)

- A full run is ~32 jobs. The owner's account is on GitHub Pro: 40 jobs at a time for the account (not 20 – corrected 28 Nov 19:48). Full runs took 30–35 min in the morning (≤ 6
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
- **E – fewer, balanced jobs.** Count a full run's jobs. Aim for ≤ 20, so two full runs fit the 40-job limit at once: merge small
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

**Chat / date:** Claude Code on the web, 28 Nov 2026.

**What changed:**
- **A – `[full run]` before the claim.** Already worked: a `[full run]` with the version not raised is a full run, its
  verdict has no lane mark, so `run_is_proven` / `proven_state` take it as proven. Now tested.
- **B – mode `catchup`** (`ci_precheck.catchup_decision`, `ci_groups.catchup_plan`). For a branch push (not
  `[full run]`): the nearest branch commit G (not on main) whose tree, merged with main by `git merge-tree`, equals the
  pushed tree apart from documents, the version lines, **version stamps** set to the new version (a tour set's
  `changed=`, a function's / PC-check line's `since=` – every changed line must be the old line with some version
  numbers or an empty `since=/added=/changed=` turned into the new version; no line added) and
  `tests/data/tour_versions.json` (the precheck checks it itself), and whose run is proven. Conflicts only in documents
  are allowed (a real case: 0349's CHANGELOG). What it runs, and why:
  - the lane plan of the files **main brought** since `merge-base(G, main)` – less main's own version lines and stamps
    (every merge brings main's version raise; those are no code). Shared files: with the lane rule 18 of the last 20
    release increments on main brought one, so a catch-up would almost never happen. Most were the files every
    feature task appends to: the function list, `tour.py`, `pccheck/`, the CI counts. Brought by main, they already
    ran every test on main, so they get their own checks (`CATCHUP_REGISTRY`: test_functions; the tour tests + real-app
    tour / tour2; test_pccheck + real-app pccheck / pccheck2 (heavy: pccheckheavy); test_ci_tools). **Core** shared
    files (props, ui, reimport, animation, handlers, build, the package's `__init__` beyond its version – e.g. a new
    `register()` line –, importer/, installer/, packaging) → **full**. Replayed on the last 20 release increments:
    **10 catch-ups** (5–23 jobs, longest job 12–24 min), 10 full;
  - **every test file and real-app test the branch itself changed or added** (they ran green in G, but against the
    old main; they are the new tests most likely to meet main's change). Not the tests that merely name the branch's
    modules: on 0349 that pulled in 55–61 test files per module and made the catch-up nearly full;
  - **the build, always**, with the documentation checks (+ `test_tour_versions.py`): the release takes this run's
    installer (reuse), and the CHANGELOG / guide changed;
  - **Windows part A only when main brought Windows code** (lane rule). The branch's own Windows code ran on Windows
    in G; the published release is checked on Windows by the release job anyway;
  - no PC check, no test tour (as in lane runs; they ran in G and in main's own runs).
  - **Safety – what it can miss:** a test that reaches a module main changed only indirectly (it does not name it),
    and fails only with the branch's change too. Every test that reaches neither side's change behaves exactly as in
    G (same code); every test that names main's modules runs; both sides ran every test on their own (G full, main
    full / catch-up). The blind spot is the lane runs' blind spot, accepted there for building; here it is the last
    gate before a release, so the fallbacks are strict: shared files (props, ui, reimport, animation, handlers,
    build, tour, functions, pccheck/, importer/, installer/, packaging, tools/ci_*, .github/) → full; any code change
    after the merge → full; a conflict in code settled by hand → full; `[full run]` → full. Tests: catch-up yes, after
    a merge alone, with documents only from main; no catch-up for a G that is lane / red / cancelled / running / has
    no run, for code beyond the merge, for a code conflict, for `[full run]`; full for a shared file from main.
- **C – reuse after a catch-up: yes.** A green catch-up proves its tree (verdict "Tests - verdict (catch-up)", build
  green), so main's fast-forward is a reuse and a later catch-up / docs run may stand on it. The other choice – a full
  run on main per release, never cancelled – would cost ~26 jobs / ~350 job-minutes / 30–75 min per release (today's
  full runs), i.e. the whole gain of B, and would line releases up behind it again.
- **D – stale runs** (`stale_decision`, mode `stale`): a branch run whose branch on GitHub has moved on to a commit that
  changes more than the task list cancels its own run at the precheck (`actions: write` on the precheck job only;
  task-list-only pushes start no run, so they never make an older run stale). **Measured:** over the last 300 runs
  (24–28 Nov) no branch run went on once a newer run on its branch existed – `cancel-in-progress` covers docs, lane and
  full runs on branches; the guard only closes the first seconds after a push. Main: 3 overlaps in 300 runs, all by
  design (a main run publishes its version) – one of them a 76-min full run on main because task 0373 fast-forwarded
  a lane-run commit (no `[full run]`): the new order prevents that. Main runs are never stopped.
- **E – fewer, balanced jobs.** Before (run 46173220142): 32 jobs listed, 26 ran; at once: 9 pytest + make-demo +
  10 real-app + build = 21, later 2 Windows + demo. Now: 8 pytest groups, the demo made inside its own job (the make
  job is gone), every matrix slowest first (`slowest_first`, real-app by recorded job minutes), times recorded again
  from run 46173220142. A full run: 24 jobs, at most 20 test jobs at once (8 + 1 + 10 + build; then 2 Windows) – two
  full runs fit GitHub Pro's 40. `GROUPS` (10 real-app groups) untouched: 0371 / 0379 were not merged (open point).
- **F – claim helper:** `ci_status.py --claim [--no-version] [--trailer …]`, `--unclaim`, `--claimed`. Reads
  `tasks/MERGING.md` on GitHub's main, refuses while another task holds it (who, since when, when its branch last
  moved; flags > 90 min with no push), takes the next version after main and every release, writes only that file in
  a worktree of `origin/main` and pushes it; tested against a local bare repository. CLAUDE.md section 2: the new order
  (build → `[full run]` green → claim → merge main + version → catch-up green → fast-forward → unclaim → report).
- CLAUDE.md section 5: modes catchup and stale, job counts, the demo job, 8 groups, the verdict.

**Tested and measured** (runs, jobs, minutes):
- Locally: `tests/test_ci_tools.py` 87 passed (18 new: A, stamps, catch-up yes / 5 kinds of no / full on shared /
  documents only / chain, stale, claim text + claim against a local "GitHub", workflow wiring, slowest first + ≤ 20 at
  once); `ci_precheck.py` passes on the repository.
- Replayed on real history (real GitHub runs): task 0349's two "merge main" pushes after its green `[full run]`
  (87ade27, 05e617f) would have been catch-ups of **5 and 10 jobs** (~16 / ~61 job-minutes, longest job 8 / 14 min);
  they ran as full runs of 26 jobs each (347 / 358 job-minutes, 68 / 53 min, waits up to 45 min).
- RUNS_PLACEHOLDER

**Row G – numbers:**
- **Before (28 Nov, task 0349):** green `[full run]` 15:20 → released 17:31 (**2 h 11 min**), two more full runs only
  to catch up with main (and renumbers 0.2.272 → 274 → 275 earlier). The task's runs that day: 7 runs, 162 jobs,
  2,141 job-minutes; its jobs waited up to 45 min for a runner. Task 0347: 9 runs, 185 jobs, 1,393 job-minutes, 5 of
  them cancelled.
- **After:** per task one `[full run]` (~24 jobs) + one catch-up (5–10 jobs, ~15 min) + a reuse run on main (~3 jobs,
  ~5 min). AFTER_PLACEHOLDER

**Open points / follow-up tasks:**
- `tools/ci_real_app.py` `GROUPS`: 10 → 8 real-app groups once 0371 and 0379 are merged (tour 11.7 + paths-heavy 9.5,
  pccheck 10.8 + machines 9.8 by the 28 Nov times) – a full run would then start at most 18 test jobs at once. A small
  Quality-lane follow-up.
- The catch-up runs neither the PC check nor the test tour on the merged code; the owner's PC check after each
  update covers that. If a release ever breaks there, make the PC check's Linux halves part of every catch-up.
- `[release rehearsal]` on a catch-up: allowed (the build is what a release takes) – REHEARSAL_PLACEHOLDER
