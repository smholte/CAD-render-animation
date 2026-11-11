# 0070 – Render queue and update safety (bug hunt 0068 rows 1–5, 19e–h)

**Who:** worker · **Status:** open – start now (Wed 11 Nov); **merged before Thursday 12 Nov 08:00** · **Branch:** own
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

- [ ] A test per row that fails on 0.2.55 and passes now (the 0068 scripts are the starting point); the queue and
      update tests green; real-app queue run (`tests/real_app`) green.
- [ ] Guide "Render queue > Start later" updated where the behaviour changed; tooltips for any new text.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0070 done; 0068 rows 1–5, 19e–h marked fixed there.

## Not in this task

Machining rows (0071), clash and decal rows (0072). New queue features (variants in the queue – study 0069 #12).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
