# 0330 – Animation keeps the user's keys (0328 F1)

**Who:** worker · **Status:** done (0.2.247) · **Branch:** `task/0330-animation-keeps-user-keys`
**Started by:** lead, 25 Nov 2026 (from 0328's report, owner's focus: user friendliness) · **Model:** Opus · effort Medium
**Area:** Motion lane – `blender/animation.py`, `blender/queue.py` (the warning before a queued Build), `blender/turntable.py`, `blender/lead_motions.py` (logic only, not its panel), their tests, guide, CHANGELOG.
**Not:** `ui_lead_motions.py` (0333), `ui_motion.py` (0333), the Keys / top bar (0295).

## Goal

An animator never loses a key or a step without being asked: a Graph-Editor edit survives the next Build (or the app asks Keep / Replace), a faded part keeps its own hand keys, a second Turntable click replaces only its own orbit step, a lead slider on a built animation says so or takes the Build off, and the timeline fits a new Build.

## What to do

Fix 0328's rows **2, 3, 4, 8, 35** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows"; grouping "Grouping into fix tasks"). Rows 3 and 2 first (lost work), then 4, 8, 35.

## Watch

- Each row's **repeat case** and **proposed fix** are in `tasks/0328-bug-and-friction-hunt-8.md` ("Rows" table) – read those rows first, repeat the
  case, then fix. The proposed fix is a proposal: a better one is fine, say why in the report.
- Row 32's words: change only the words that are in **your** files (the row lists them by place).
- Every visible change: tooltip, user guide, PC-check line, tour stop / function-list entry with `since=` / `changed=`
  (CLAUDE.md section 2). Real-app check (`tools/ci_real_app.py`) for every row that was seen in the real app.
- Two tasks never share a file: stay inside **Area**; a needed change elsewhere → open point in the report.

## Done when

- [x] Each row's repeat case now gives "what should happen" (a test per row; real-app check where it was seen there)
- [x] Tests added/updated; full suite passes; GitHub run green
- [x] (UI) screenshots checked with tools/ui_screens.py
- [x] Guide, PC-check line, tour / function-list version fields as CLAUDE.md section 2 asks
- [x] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · Medium), 25 Nov 2026

**What changed:**
- **Row 2** (`animation.py`): at the end of every Build a fingerprint of the keys it wrote (per object / camera of its
  own action, per curve: keys, handles, interpolation, easing) goes on the scene (`fr_anim_print`). The next Build
  (also the queue's background copy, which reads it from the saved file, and F12) first collects the curves that differ
  from it; after building, a curve whose new keys equal the old fingerprint gets the user's keys back ("Kept your own
  change to the keys of joint 'Boom' …"), else it stays new and the warning says the steps changed. Stop
  (`clear_keys`) drops the fingerprint, so Stop + Build goes back to the steps' keys. Better than the proposed Keep /
  Replace question: no dialog in the queue or F12, and nothing is lost while the steps stay the same.
  `edited_text()` gives the one line for a later "before the queue" note (not used yet: the queue's Build already
  reports the bake's warnings). A hand key on a channel Build also keys is now named in the warnings (no longer silent).
- **Row 3**: a faded / shown part with an action of its own goes through `_channelbag` (own action set aside, put back
  at Stop) instead of the shared visibility action. New: the user's own curves on channels Build does not key are
  copied into the built action (`_aside_curves`), so the hand motion plays while built (objects, cameras, the scene).
- **Row 4** (`turntable.py`): the orbit step is tagged (`orbit_block`; older projects: found by its name) and only it is
  made again; `animations_index` is left where it was (set only when out of range).
- **Row 8** (`lead_motions.py`): `apply` (slider, ▶, Back to start, row edits) takes the Build off first when it moves
  a joint of a built animation to another value (`took_off`; a row added or edited that leaves the joints where they
  are keeps the Build – the crane lesson builds, then makes its lead motion) and writes `BUILT_OFF` into the scene's last message. The popover's own line
  is 0333's (ui_lead_motions.py).
- **Row 35**: `animation.fit_timeline` after every Build in the app (a timer, `action.view_all` in each timeline).
- Row 32: none of its words are in this task's files.
- Guide (Build & play "Your own keys", Turntable, Lead motions), CHANGELOG 0.2.247, function list `changed=` for Build &
  play, Turntable and Lead motions, PC-check line `animation.user_keys` (Full; `MIN_LINES_FULL` 156). No tour stop: no
  new function, the stops show the same.

**Tested and measured** (4-core web machine, test crane):
- `tests/test_user_keys.py` (11 tests, one or more per row: repeat case → what should happen; a save + reopen for row 3
  and for the queue's case of row 2); the turntable, fade, lead-motion, studio-camera, 0120-fix, build-any-frame and
  camera-rebake tests (166 passed).
- No false "kept" warnings: every animation of every test-tour set (50) built twice – no warning about own keys.
- Real app (`ci_real_app.py --only leadmotions`, 3 new checks): Build & play of a 12 s animation → the timeline went
  from 0–260 to 0–308; a lead slider on it took the Build off with the message and the boom stayed at the next frame.
  On the first local run the timeline check failed once (the timer had not run yet when the check looked, after an
  unrelated check in the same run had failed); the check now waits 2 s.
- PC-check line `animation.user_keys` (bpy module): OK, 1 s.
- GitHub runs: 1st red – the crane lesson (and the PC check's app.lessons, Linux and Windows) lost its Build when its
  lead motion's rows were added; fixed as above. 2nd: precheck – 0.2.246 taken by 0329, renumbered to 0.2.247. 3rd: green (run 45598850149, 33 min).

**Open points / follow-up tasks:**
- Other code that takes a Build off (a joint's own slider, `joints.set_table`, turntable, a lead slider) still drops
  hand-changed keys with the Build (as Stop does); only Build → Build keeps them.
- 0333 (`ui_lead_motions.py`): the popover could show "Built" next to the sliders; the message is in `last_message`.
