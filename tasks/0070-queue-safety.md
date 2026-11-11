# 0070 – Render queue and update safety (bug hunt 0068 rows 1–5, 19e–h)

**Who:** worker · **Status:** done – 0.2.56 (Wed 11 Nov) · **Branch:** own
**Started by:** lead chat, 11 Nov 2026 (from bug hunt 0068)
**Lane:** Motion (queue) + Quality & delivery – `blender/queue.py`, `queue_runner.py`, `ops_queue.py`/the queue panel,
`blender/updates.py` (preflight), `project_lock.py`; a `save_post` handler (in `handlers.py` – a few lines; 0058 starts
there Thursday, so merge first); tests, guide "Render queue" where behaviour changes
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0071** (Machining lane: tool copies, double arm, coolant, rotary, milling per-frame cost).
Do not touch those files. Two releasing tasks at once: take the version number last; whoever finishes second merges
`main` once and renumbers. **If it cannot be green and merged by Wednesday 22:00:** push the branch, report, stop.

## Goal

The owner leaves long renders overnight with Start later (0050) and keeps projects in a shared folder. The bug hunt
found ways in which an overnight render silently never starts, starts at the wrong moment, or two runners fight over
the same frames. Each one is confirmed with a script in `tasks/0068-bug-hunt-2.md` – read its rows first.

## What to fix (rows of 0068)

1. **Row 1** – Start later is cancelled by the first Save / Save As of a project: follow the project's new path (a
   `save_post` handler), so the delayed start survives a save.
2. **Row 2** – Starting a queue tidies away another queue that is still live (just started, or running on a colleague's
   PC from the same `_queue` folder): tidy only folders whose status says not running, or older than a day; give each
   queue folder a unique name (pid/uuid) and refuse an existing one.
3. **Row 3** – Update now drops a pending Start later: `preflight` refuses with a clear line ("A delayed queue start is
   set for 22:00: cancel it or wait").
4. **Row 4** – The session remembers only one running queue: keep the runtime per project (queue folder), so reopening
   project A shows its jobs running, Stop now in B stops only B, and a second runner for the same jobs is refused (with
   a warning before a second runner while another of this session is alive – one graphics card).
5. **Row 5** – Start queue / Render animation / Time test also starts the jobs waiting for Start later: when a delay is
   set, these start only the new job (or cancel the delay and say so – pick one, say why; a quick Time test must never
   start the overnight renders).
6. **Row 19 e–h** – Windows sleep while Start later waits (`SetThreadExecutionState` from `schedule()` until the start;
   check the owner's case in the guide: "the PC must stay on"); `project_lock.write` via temp file + `os.replace`; own
   pid never counts as a live runner; `queue_runner.write`'s last write retried longer, and `sync` trusts per-job DONE.

## Done when

- [x] A test per row that fails on 0.2.55 and passes now (the 0068 scripts are the starting point); the queue and
      update tests green; real-app queue run (`tests/real_app`) green.
- [x] Guide "Render queue > Start later" updated where the behaviour changed; tooltips for any new text.
- [x] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [x] Report filled in; `TASKS.md`: 0070 done; 0068 rows 1–5, 19e–h marked fixed there.

## Not in this task

Machining rows (0071), clash and decal rows (0072). New queue features (variants in the queue – study 0069 #12).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · Medium), Wed 11 Nov 2026. Branch `claude/busy-goodall-etow8a`
(the session's own branch name, not `task/0070-…`).

**What changed:**
- Row 1: `handlers._after_save` (save_post) → `queue.project_saved()`: the delay (and the run the scene names) follows
  the new file name. Save As *copy* (the queue's own snapshot) leaves it alone.
- Row 2: queue folders `YYYY-MM-DD_HHMMSS_<6 hex>`, `os.makedirs` without `exist_ok` (`new_queue_dir`).
  `_tidy_old_queues` only tidies a folder when `_finished`: status `running: False`, or a runner on this PC that is
  gone, or nothing written for 24 h. No status yet, another PC's runner, or an old status without host: kept. The runner
  now writes `host` (and queue.json `host`, `started`).
- Row 3: `updates.preflight` refuses: "A delayed queue start is set for HH:MM (panel 7): cancel it (Cancel), or update
  when that queue has finished"; also refuses when any run of this session (other project) is alive.
- Row 4: `_RUNTIME` → `_RUNS[queue folder]` = {pid, dir, killed, project, label}. `_run_of(scene)`: the folder the
  scene names, else the newest run of this file. `kill` marks only that run. `start` refuses jobs already being rendered:
  `live_queue_for` scans `_queue` for a queue.json of *this project path* sharing a job ID whose runner is alive (this
  PC) or wrote in the last 15 min (another PC); a live one on this PC is adopted (`_adopt`). `_on_load` calls
  `find_live`, so A shows its jobs running also after an app restart. Start queue / Start now / Render animation
  (buttons) ask first (`invoke_confirm`, "Start anyway") when another project's queue of this session renders.
- Row 5 (choice: start only the new job – the overnight renders stay set, which is what the owner set them up for;
  cancelling them would be easy to miss): `queue_add(start=True)` and the turntable button with a pending delay call
  `start(only={new job})` and say "Queue started with this job only … The other jobs still start at 22:00". The delay
  tick waits while a render of this project runs, then starts (panel: "Due at 22:00: starts when this render ends").
  Start queue with a delay pending = Start now (cancels the wait, says so); the panel hides Start queue then.
- Row 19e: `queue.keep_awake` (SetThreadExecutionState ES_CONTINUOUS|ES_SYSTEM_REQUIRED on the main thread) from
  `schedule()`, cleared in `cancel_delay` (also on start). 19f: `project_lock._write_whole` (temp + `os.replace`,
  5 retries). 19g: `_pid_alive_os(os.getpid())` is False (so `kill` never targets the app). 19h: runner's last status
  write tries 60 s; `done_<job>.json` per finished job, which `sync` trusts over a stale RUNNING.
- Guide 7 Render queue (Start later, queue per project); panel text "Keep the app open and the PC on until then".

**Tested and measured:**
- `tests/test_queue_safety.py` (new, 13 tests, one or more per row; they use new functions, so they cannot pass on
  0.2.55; rows 1/2/4/5 repeat 0068's scripts with a fake runner process that writes a running status). Row 4's test:
  A started, B opened and started, A reopened shows RUNNING and refuses a 2nd runner, Stop now in B leaves A's
  process running; app restart (runtime cleared) finds A's live queue again.
- `test_queue_delayed.py` (one test changed: a due delay now waits for a running render instead of giving up),
  `test_queue_fixes.py` (row-9 test moved to `_RUNS` with a real live child process), `test_updates*.py`,
  `test_phase2.py`: all green locally. Tooltip check 549/549.
- Windows-only lines (keep_awake, lock replace, runner writes) reviewed by an independent helper agent: no defects
  (note: a lock `.tmp` can remain only after a crash between write and replace).
- GitHub: 2 runs on the branch commit 58ce51f: the first failed only in PC-check line `milling.rotary` (cut 32.4 s,
  bar not cut – a slow runner; the same line passes locally on this code in 2.3 s, and on main before); the failed jobs
  were re-run, green. Then `main` fast-forwarded to that commit (mode reuse).

**Open points / follow-up tasks:**
- `milling.rotary` PC-check line is timing-sensitive on a loaded runner (cut 32 s vs 2–3 s normally): Machining lane
  (0071 per-frame cost) may want to look.
- Not shown on Windows: the sleep block (owner can check with `powercfg /requests` while Start later waits: it lists
  blender.exe under SYSTEM). Confirm the owner's sleep setting.
- Matching a colleague's live queue uses the project path in queue.json: two PCs that map the share differently
  (Z:\ vs \\server\) are not matched (the folder is still never tidied while live).
- Leftover branch for the owner to delete: `claude/busy-goodall-etow8a`.
