# 0120 – Bug-hunt fixes B: render queue, jobs during a bake, undo during long jobs, weather and redraw

**Who:** worker · **Status:** running (web session) · **Branch:** `task/0120-fixes-queue-render-undo` (or the web session's)
**Started by:** lead chat, 14 Nov 2026, from bug hunt 0118 (`tasks/0118-bug-hunt-3.md`)
**Area:** Scene & Render + queue: `blender/queue.py`, `ops_motion.py` (Add image), `states.py` (saved scene frame), `house_bake.py`, `ops_web3d.py`, `ops_house.py`, `ops_clash.py` (modal undo), `section.py` + `ui_section.py`, `ui_fade.py`, `ui_weather.py`, `weather.py` (`after_clear`), `animation.py` **additively** (a Build warning, `_channelbag`) – 0121 adds one call in `clear_keys`: merge carefully; their tests. **Do not edit:** `spool.py`, `paths_riders.py`, `tracks.py` (0119), `sequence.py`, `flex.py`, `vessel_motion.py`, `reimport.py` (0121), `importer/`, `build.py`, `faces.py` (0117).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Fix rows **1, 6, 11, 13, 15, 16, 18** of the bug hunt (every-paint-scheme animation jobs render one colour; queued stills at the wrong frame; Start later / Start queue / Ctrl+S during a House bake copies a half-baked project; Ctrl+Z during web 3D export, House bake, clash check; writes at render start off the main thread; Build switching the weather off silently; per-redraw walks, a dead function, the orphan scene action). Row 18 (d) needs only a comment.

## How

- The rows' text in `tasks/0118-bug-hunt-3.md` (Findings) gives where, what happens, the proof and a suggested fix.
  Read each row, repeat its proof first (it must fail), then fix. **Every fix gets a test that failed before**
  (CLAUDE.md section 6). The suggested fix is a suggestion: a better one is fine, say why in the report.
- A row that turns out not to be real (cannot be shown on today's `main`): say so in the report, no change.
- No new features, no UI redesign. A visible change (a new warning, a note) gets its tooltip/guide line; no new tour
  stop or PC-check line is needed for a fix unless the row asks for one.
- One version at the end (take the number last, CLAUDE.md section 2).

## Done when

- [ ] Each row: fixed with a test that failed before, or shown not real (with how)
- [ ] Full run green on GitHub; CHANGELOG in plain words (what the owner would have noticed); version taken last
- [ ] Report filled in; TASKS.md row → done

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 14 Nov 2026, branch `ccr-c5513248-6jgqki` · version 0.2.96

**What changed (per row):**
- **Row 1** (every-scheme animation in the start scene's colours): `queue._setup_animation` applies the job's scheme
  again right after `animation.bake` (Build's `apply_shot` had put the start scene's looks back). Time tests too.
- **Row 6** (queued still at the queue-start frame): "Add image" stores `fr_frame` (`queue.SHOT_FRAME`) on its hidden
  saved scene; `run_job` sets that frame after `apply_shot` (which clears the keys, so only frame-driven things –
  sea, vessel motion, rain, snow – follow it). Hidden scenes made before 0.2.96 have no frame: as before.
- **Row 11** (queue copies a half-baked project): `queue.busy_job` = House bake / Web 3D export / Clash check running
  (their runtime "running" flags). `start` refuses with the reason (so Start queue, Render animation, Time test,
  the turntable button), `_delay_tick` waits like for a running render, a new `save_pre` handler (`handlers.py`,
  additive) sets a warning – Blender cannot stop a save.
- **Row 13** (Ctrl+Z during long jobs): new `blender/longjob.py`; the three modals swallow Ctrl+Z / Ctrl+Shift+Z /
  Ctrl+Y and say "Undo is off while the … runs: press Cancel (or Esc) first". Edit > Undo from the menu is not a key
  event and is not caught (open point).
- **Row 15** (cut-away writes on the render thread): `section._on_render_init` syncs only on the main thread (the
  queue's background Blender, scripted renders); new `section.sync_for_render` is called by `render.prepare_still`
  (every app still render, in the window and the queue) and `queue._setup_animation`. Blender's own F12 in the
  window no longer syncs at render start – the cut is kept in step by its own edits anyway.
- **Row 16** (Build switches the weather off silently): `animation.bake` compares the weather before/after the start
  scene and warns when it switched the weather off ("The start scene 'X' has no weather, so Build switched the
  weather off …"). A first version also warned when a start scene brought other weather of its own: the test tour's
  "Weather changes in a video" stop (start scene "Clear day") showed that is the scene's point, so that warning was
  dropped (run 43585482413, 2 failures). Guide: Weather & time paragraph.
- **Row 18** (a) `fade.xray_count`, `ui_weather.light_count`, `section.cut_count`: counts kept between redraws
  (bumped by a generation number when the look/members change, objects come or go, at most 2 s for undo); the work
  lights' list is walked only when its fold is open. (b) `section._cut_objects` removed. (c) `weather.after_clear`
  removes the app's scene action (no "FR Scene" orphan) and `animation._channelbag` keeps a user's own action in an
  ID property (`fr_user_action` + slot) that `_drop_action` puts back at Clear keys – for scenes, objects and
  camera data alike. (d) comments at the drivers in `weather_sky.drive` and `paths_sea`; `spool.py` (spool end,
  carousel scale floor) is 0119's file – not touched, no fix needed there either.

**Tested:** `tests/test_fixes_0120.py` – 13 tests, 12 failed on the code before the fixes (the 13th tests the new
key helper only). Locally: queue (schemes, fixes, safety, delayed), fade, section, weather (+fx, sky, independent),
house_blender, web3d, idprops, updates – 254 passed. Precheck and tooltip report clean (736 ok). GitHub: see below.

**Open points:** Edit > Undo from the menu (and the undo history) during a long job still passes – only the keys
are caught. A save during a long job warns but cannot be stopped. Row 15: a user's own F12 in the window renders
the cut as it is (no sync at render start).
