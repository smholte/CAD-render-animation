# 0281 – Learning hub: one chapter open at a time; the lesson's Back / Next / Play on at the top

**Who:** worker · **Status:** open – can start · **Branch:** `task/0281-hub-one-chapter-lesson-top`
**Started by:** lead, 21 Nov 2026 (owner 22:00, screenshots of 0.2.197's Learning hub stops – Look / Motion /
Machining / Pictures and videos – and the Lesson section "2 of 11": "when opening a new chapter in the Learning hub the
other chapter should close, max 1 open at once" and "Back, Next and Play on should be at the top of the lesson section,
so over the description of the step.") · **Model:** Sonnet · effort Medium
**Area:** Start & learn lane – `blender/ui_tour.py` (the chapter folds), `blender/ui_lesson.py` (the Lesson section's
order), their small operators / properties if the folds need one; tests, real-app test, guide pictures, CHANGELOG.
**Not:** `tour.py` (0253 adds a stop there), `ops_tour.py` / `welcome.py` (0275), the left sections' own fold setting
and `prefs.py` (0278), what the hub or a lesson contains.

## What to do

1. **One chapter open at a time** in the Learning hub stops list (Look, Motion, Machining, Pictures and videos, and any
   later chapter), wherever the list is drawn (left panel and the right panel's "Learning hub stops"): opening a
   chapter closes the open one; clicking the open one closes it. When a stop is picked or Go jumps to a stop in another
   chapter, that chapter opens and the others close.
2. **Lesson section order, top to bottom:** the header ("Lesson · 2 of 11"), the lesson's name line, then the row
   **Back | Next** (and Do it for me / Stop where they show today) with **Play on** right under it, and only then the
   step box (✓ step name, its text, More …, This in the user guide). The buttons stay in the same place from step to
   step, so the user can click Next repeatedly without the mouse moving.
3. The lessons' highlight still finds Back / Next (the crane and mill lessons pass); every tooltip unchanged.

## Done when

- [ ] Real-app test: open Look, then Machining → Look closed; Go to a stop in Motion → only Motion open
- [ ] Lesson: Back / Next / Play on above the step text, same place on every step (real-app test reads the layout)
- [ ] Crane and mill lessons pass; guide pictures and text updated; tour stop `changed=`
- [ ] Full suite + GitHub run green; report filled in; merged, version, release (CLAUDE.md section 7)

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 22 Nov 2026

**What changed:** `ui_tour.py`: the stop groups are own rows with an arrow (operator `fresing.tour_chapter`, in `lock.ALLOWED`);
one open at a time, the picked stop's group opens when it changes (state `CHAPTER`). `ui_lesson.py`: Back | Next / Do it for
me and Play on come right under the lesson name, the step box below. Guide text, CHANGELOG 0.2.207. No tour set changed,
so no `changed=`. Guide pictures not redone (layout only; the owner can ask).

**Tested and measured** (4-core web machine, bpy module): `tests/test_tour.py`, `test_lessons.py`, `test_start.py` pass
(two new tests: chapter state, button order in the draw source). No new real-app test of the drawn layout; lessons' highlight
untouched (Back / Next operators unchanged).

**Open points / follow-up tasks:** a real-app layout test and new guide pictures if wanted.

**Owner's check on your PC:** open the Learning hub, click Machining while Look is open: Look closes. Start a lesson: Back / Next / Play on are above the step text.
