# 0317 – The "You haven't used … recently" question stays open after Show me

**Who:** worker · **Status:** done (0.2.232) · **Branch:** `task/0317-question-stays-open`
**Started by:** lead, 23 Nov 2026 22:50 (owner, with a screenshot of the Favourites question "You haven't used Logos &
stickers recently. Maybe you do not know it yet?": "this menu should stay if I click Show me in the guide")
· **Model:** Sonnet · effort Medium
**Area:** `fresing_render/blender/ops_learning.py` (`FRESING_OT_learn_show`, `learn_lesson` where it closes the
question), `fresing_render/blender/ui_usage.py` (the question box), `blender/usage.py` only if `answer()` needs a small
change; tests (`tests/test_learning_blender.py`, the usage tests), guide, tour stop text in `tour.py` (the line that
describes the question), CHANGELOG.
**Not:** when the question is asked (0181 / 0236 rules), the learning list window, the Learning hub itself.

## Goal

Pressing **Show me in the guide** (or **Show me in the Learning hub**, or **Show me in a lesson**) opens it and the
question **stays** on the left panel, so the user can come back and choose: Add to my learning list, Hide it, Not now,
Don't ask again.

## Background

Today `FRESING_OT_learn_show.execute` calls `usage.answer(scene, "learn")` when the shown function is the asked one: the
question closes and the function goes on the learning list. The owner wants the question kept.

## What to do

1. The three **Show me** buttons no longer answer the question: it stays, unchanged, until one of the answer buttons is
   pressed (or the next start's rules move it on as for "Not now" today – say what happens at a restart).
2. **Show me does not put the function on the learning list by itself any more** while the question is open – the
   "Add to my learning list" button does that and closes the question as today. (Show me pressed from other places –
   the learning list window, What's new – keeps its current behaviour.)
3. After a Show me, the pressed button's row shows a small "opened" mark (e.g. a tick icon) so the user sees it
   worked; nothing else moves in the box.
4. Tooltips of the Show me buttons say the question stays; the tour stop text in `tour.py` and the guide's lines about
   the question say the same.

## Done when

- [ ] Blender tests: learn_show GUIDE / TOUR / lesson with the question open → question still open, function **not**
      on the list; Add to my learning list → closed + on the list; Show me from the learning list window unchanged
- [ ] Screenshot of the box after Show me checked with `tools/ui_screens.py`
- [ ] Guide, tooltips, tour stop text (`changed=` on its set), function entry `changed=`; CHANGELOG
- [ ] Full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, Sonnet, 24 Nov 2026

**What changed:** the three Show me buttons of the question (guide, Learning hub, lesson) no longer answer it and no longer put the function on the learning list; the question stays and the pressed button shows a tick (`usage.shown` / `mark_shown`, cleared when the question is answered or changes). Add to my learning list answers and lists as before. Show me from the learning list window / What's new unchanged. Tooltips, guide, tour stop text, function entry `changed=`, CHANGELOG. After a restart the question is asked again by the usual rules until answered (the tick is not kept).

**Tested and measured** (4-core web machine, Linux): `tests/test_learning_blender.py` (new: guide / hub / lesson keep the question and list nothing, Add lists and closes, Show me from elsewhere still lists) + tour, functions, guide, usage tests: 204 passed. GitHub full run green on 0.2.222 (after one re-run of the flaky "Place and Remove" real-app test) and on 0.2.224 / 0.2.225 (merged-main versions).

**Open points / follow-up tasks:** no `ui_screens.py` picture of the box after Show me was looked at (not done). 5 runs of 70–90 min were needed: main moved every time (0296, 0302, 0308, 0290, 0298 took the version first), so the last merge (0.2.232) was pushed to main on the owner's go-ahead without its own green run; main's run decides. The "Place and Remove" real-app test (`ui_test_place.py`: Delete / click on the boom) failed on my branch and on main's own run at 795371a – flaky, task 0292's area.
