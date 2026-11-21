# 0275 – "Making the Learning hub…" says so clearly: a progress window after Take the test tour

**Who:** worker · **Status:** open – waits for 0260 (same lane; 0260 renames the test tour to Learning hub and touches
`welcome.py`) · **Branch:** `task/0275-hub-progress`
**Started by:** lead, 21 Nov 2026 (owner 17:45, screenshot of the welcome window: "When I press Take the test tour it
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

## Done when

- [ ] Real-app test: Take the test tour → the window is there within 1 s, the bar moves, Hide → the left panel line +
      bottom-left status, Show progress brings it back, done → "ready" notice → Open it now opens the hub
- [ ] Stop making it and a forced failure tested
- [ ] Guide picture of the window; function list (`changed=`), PC-check line if the tour check reads the texts;
      CHANGELOG; report with the owner's check steps; merged, released

## Not in this task

Making the hub faster; the first-start set-up (0276).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
