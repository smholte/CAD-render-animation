# 0275 – "Making the Learning hub…" says so clearly: a progress window after Take the test tour; Next goes to the next stop at once

**Who:** worker · **Status:** done (0.2.212) · **Branch:** `task/0275-hub-progress`
**Started by:** lead, 21 Nov 2026 (owner 17:45 + 17:53 – Next in the tour, screenshot of the welcome window: "When I press Take the test tour it
should tell you clearly that it is making the test tour and to wait for it. Now it is a bit unclear for a new user,
with only a little status in the bottom left.") · **Model:** Sonnet · effort Medium
**Area:** Start & learn lane – `blender/welcome.py`, `blender/ops_tour.py` (the make / progress part only:
`building`, `progress_text`, `FRESING_OT_tour_make`'s modal), 0260's left panel (one progress line, additive), their
tests, a real-app test, guide picture, CHANGELOG. 0253 is in the same lane: one after the other, either order.
**Not:** what the tour / Learning hub contains; the first-start set-up (0276, own brief).

## Goal

A new user who presses **Take the test tour** (after 0260: the Learning hub) sees at once, in the middle of the
screen, that the app is **making the Learning hub**, how far it is and roughly how long it still takes, that they may
keep working meanwhile, and where the progress stays visible when they hide the window (bottom left). When it is
ready, they are told and can open it with one click.

## What to do

1. **Progress window** right after the click (the welcome window closes): title "Making the Learning hub", one line
   what happens ("Fresing Render is building small sample projects with every function set up – about N minutes on a
   PC like yours"), a **progress bar** with "project 4 of 23 – <set name>" (from `tour.read_progress`), **time left**
   (from the measured time per project so far; "about 2 min left", never jumping up and down by more than a step),
   and one line: **"You can keep working. The progress also shows in the bottom-left corner."** Buttons: **Hide**
   (keeps building), **Stop making it** (asks once; the projects made so far are kept or removed – say which).
   Built like the other app windows of 0260 (stays open, can be moved) or as a modal popup that refreshes – pick the
   one that does not freeze Blender and say why.
2. **Bottom-left status** stays as it is (it already says "Making the test tour: project N of M"), with the new name;
   while it runs, 0260's left panel shows the same line with a small bar and **Show progress** (opens the window again).
3. **Done:** the window (or, when hidden, a notice that pops up once – not only a status line) says **"The Learning
   hub is ready"** with **Open it now** / **Later** (later: Fresing menu > Learning hub). A failure says what failed in
   plain words, where the log is, and offers **Try again**.
4. **Same window** for every other way the hub is made (Fresing menu, What's new's "make the new models", the left
   panel's button): one code path.
5. The welcome text: keep the "about N minutes" line and add "(you can keep working while it is made)".
6. **Next goes there at once** (owner 17:53, screenshot of "→ Next: 2. Painted faces"): today **Next** only picks the
   next stop (`fresing.tour_pick`) and the user must press **Go** as well. Next = pick + Go in one click (also when the
   next stop lives in another set's project: it opens it, as Go does; with unsaved changes, Go's own question). The
   same for a **Back / previous** button if the panel has one. A click on a stop in the list keeps today's behaviour
   (pick, read, then Go) – say in the report if you think it should go at once too. Tooltip, guide and the tour's
   real-app test (`ui_test_tour.py`: one click on Next → the next stop is set up, its check passes).

## Done when

- [ ] Real-app test: Take the test tour → the window is there within 1 s, the bar moves, Hide → the left panel line +
      bottom-left status, Show progress brings it back, done → "ready" notice → Open it now opens the hub
- [ ] Stop making it and a forced failure tested
- [ ] Next sets up the next stop in one click (also across sets); real-app test
- [ ] Guide picture of the window; function list (`changed=`), PC-check line if the tour check reads the texts;
      CHANGELOG; report with the owner's check steps; merged, released

## Not in this task

Making the hub faster; the first-start set-up (0276).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker (Claude Code on the web), 23 Nov 2026

**What changed:**
- A **card in the middle of the main 3D view** while the hub is made (`blender/hub_progress.py`, words and numbers in
  `core/hub_progress.py`): title, one line what happens ("about N minutes"), bar with "project 4 of 23 – <set>", time
  left (steps of 30 s, falls freely, rises one step at a time), "You can keep working. The progress also shows in the
  bottom-left corner.", **Hide** / **Stop making it** (asks once; projects made so far are kept). Done: it comes up
  again, also when hidden: **The Learning hub is ready – Open it now / Later**; a failure: what failed, the log's
  place, **Try again**. One code path: `FRESING_OT_tour_make`'s modal runs the card for every way the hub is made.
- **Why a drawn card, not a window or popup:** a popup blocks Blender and cannot refresh; an app window (0260's
  `open_window`) needs a split + settle timer, so nothing shows for a moment. A draw handler shows at the first
  redraw and refreshes on the build's own timer; the build's modal hit-tests its buttons and passes every other event on.
- Left panel (Learning hub panel): while it runs, the same line + a small bar + **Show progress** (`fresing.hub_show`,
  in `lock.ALLOWED`). Bottom-left status unchanged. Welcome text: "(you can keep working while it is made)".
- **Next = Go on the next stop** (also across projects). Back button: the panel has none. A click on a stop in the list
  still only picks (my view: keep it, so a stop can be read before it is set up). Go has no "unsaved changes" question
  today (it never had); not added.
- Function list `help.tour` `changed=0.2.211`; guide chapter + 2 pictures; CHANGELOG 0.2.211.

**Tested and measured** (Linux web machine, 4 cores, no graphics card):
- `tests/test_hub_progress.py` (4). Real app `ui_test_tour.py` (tourui, 15 → 31 checks): Next in one click across
  projects; card there in 0.00 s after the call; Hide; Show progress; Stop asks once, Keep making it, Yes stop (build
  killed, card gone); a forced failure (build killed from outside) → failed card + log, Try again; done → ready card →
  Open it now opens the hub. Pictures looked at (progress, ready).
- Not tested: the left panel line is drawn only while a build runs (not in a screenshot). Opening another file while
  building drops the card (the build goes on; the modal ends as before).

**Runs:** 4 GitHub runs: the allow-list count (+ hub_show), a version clash (0261 took 0.2.211 → 0.2.212), the forced-failure test step racing the build (now kills it at once), then green; main = reuse run + release 0.2.212 published.

**Open points / follow-up tasks:**
- `ui_test_tour.py`'s "OK / Problem / Note are saved" + "Copy results" failed in 2 of 5 local runs, before any of my
  steps (a race after Go into another project; not caused by this task, shown in the check's detail now). Worth a look.
- Owner's check: Fresing menu > Open the Learning hub (when not yet made) → the card appears at once; Hide, then
  Show progress on the left panel; when ready press Open it now; in the hub press Next under a stop.
