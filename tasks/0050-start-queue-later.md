# 0050 – Start queue in …: the render queue starts by itself later

**Who:** worker · **Status:** open – can start (start now, 10 Nov, with 0060; before 0058 on Thursday) · **Branch:** `task/0050-start-queue-later`
**Started by:** owner's wish 9 Nov 2026, briefed by the lead 9 Nov
**Lane:** Motion (panel 7 Render queue) – `blender/queue.py`, `ui_motion.py` (queue panel only), `blender/ops_motion.py`
(queue operators only); tests; guide "7 Render queue"
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

Do not touch `animation.py`, `handlers.py` beyond a one-line timer registration, machining/coolant, tour files.

## Goal

Next to **Start queue** the owner can choose **Start in …** (hours and minutes, 0–12 h) or **Start at …** (a clock
time, today or tomorrow), so a long queue starts by itself, e.g. after work or at night. The panel shows the countdown
("Starts in 2 h 14 min – at 18:30"); **Cancel** stops it; **Start now** starts at once. The app must stay open (say so
in the tooltip and the guide); a delayed start is not kept when the project is closed or the app restarts – a note
says so if that happens.

## Details

- A Blender timer (no busy loop); the countdown text refreshes about once a minute.
- At the start time it does exactly what Start queue does (same checks; if the queue is already running or empty, a
  note instead).
- Works with the project saved; if the project has unsaved changes at the start time, the queue starts as Start queue
  would (check what it does now and keep that).
- Test with a short delay (seconds, a test-only setting) that the queue starts, Cancel stops it, closing the project
  clears it (0054 keeps runtimes per project – follow that).

## Done when

- [ ] Start in … / Start at … / Cancel / Start now with tooltips; countdown in the panel.
- [ ] Tests as above; guide "7 Render queue" + picture; PC-check line if it fits (`queue.delayed`).
- [ ] If the test tour (0059) is merged: its stop for this.
- [ ] GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0050 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 10 Nov 2026

**What changed:** 7 Render queue got **Start later**: choose In … (0–12 h + minutes) or At … (clock time, today or
tomorrow), click Start later; the panel shows "Starts in 2 h 14 min - at 18:30" with Start now and Cancel. A Blender
timer (looks every 30 s, panel refreshes then) calls the same `queue.start` as Start queue; "already running / empty"
gives a note instead. Closing or switching the project clears it (load_pre handler) and a note says so; not kept in
the file. Operators `fresing.queue_start_later` (hidden test-only `seconds`), `queue_start_cancel`, `queue_start_now`.
Test tour stop 29 "Render queue: start later" (`MIN_LINES_TOUR` 30). Guide chapter 7 + new panel picture. Version 0.2.49.

**Tested and measured** (2-core-class web machine, test crane): `tests/test_queue_delayed.py` 8 tests (clock maths,
schedule/describe, Cancel, timer start, Start now, already running, project closed, other project) – pass;
`test_tour.py` 39 pass; tooltip report strict 0 missing; precheck ok. GitHub run: see below.

**Open points / follow-up tasks:** No PC-check line (a delayed start needs minutes of waiting; the tour stop covers the
button path). Windows behaviour is the same code path as Start queue. Clock time follows the PC's local time zone.
