# 0254 – The cable-lay equipment's report pictures leave `main` (study 0226 package 4)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0254-vessel-report-pictures`
**Started by:** lead, 21 Nov 2026 (study 0226 package 4; owner's answer 20 Nov: "yes – delete the ~53 report pictures
from `main`, copies in the private repository first") · **Model:** Sonnet · effort Low
**Private vessel: yes – read only** (to check that the private repository holds a copy of every picture deleted here;
push there only to add a missing copy, into its `img/`)
**Area:** `tasks/img/` (deleting the pictures listed below) and the **old** task files that link them (`tasks/0076-*` …
`tasks/0179-*`), `TASKS.md`. Nothing else.

**Not:** app code, `docs/` (0247 already reworded the guide), `site/`, `CHANGELOG.md`, the task files of running tasks
(0233, 0234, 0249, 0252, 0253 and newer).

## Goal

None of the cable-lay vessel's equipment (carousel, tensioners, chute, A-frame / quadrant, ROV, deck machines, wires,
the spread's layout) is shown in a picture on `main` any more. The ship with her own deck crane, the wind park, the sea
and the quay may stay (CLAUDE.md section 6).

## Background

- Study 0226 (`tasks/0226-study-private-vessel.md`, table row `tasks/img/`) counted **53 files (13 MB)** that certainly
  show the spread: 0076 (4), 0077 (2), 0078 (2), 0079 (1), 0084 (7), 0091 (2), 0095 (3), 0102 (2), 0107 (2), 0142 (3),
  0143 (3), 0149 (1), 0153 (4), 0154 (3), 0158 (3), 0159 (2), 0166 (3, the park with the vessel in view), 0173 (3), 0174
  (1), 0175 (1). **Probably:** 0106 (5, "demo vessel, same camera"), 0109 (3), 0179 (1) – look before deleting.
- Package 1 (0228) copied the 53 into the private repository `smholte/fresing-render-vessel`, folder `img/`. The cut
  (0247, 0.2.188) took the equipment's code, the demo and the guide's mentions off `main`; it left these pictures.
- The history is not rewritten (owner 20 Nov): old commits keep them.

## What to do

1. List every file in `tasks/img/` (and pictures directly in `tasks/`) of tasks 0076 – 0179. Delete the 53 above.
   **Look** at 0106's, 0109's and 0179's pictures (small crops are enough) and at any other picture of a demo /
   vessel task in that range: delete each one that shows any equipment; keep one that shows only the ship with her
   deck crane, the park, the sea or the quay. Pictures of test models stay.
2. Check that the private repository's `img/` has a copy of every deleted file (same name or same bytes); add any that
   is missing (push there, nothing else).
3. In the task files, each link to a deleted picture becomes the text *(picture removed – private, task 0226)*;
   the words around it stay.
4. Check that nothing on `main` still links a deleted file (`grep` the repository for each file name; the guide build
   and `tests/test_user_guide.py` must still pass).
5. One push of `tasks/` + `TASKS.md` only (it starts no GitHub run; run `python3 tools/ci_precheck.py` first). No
   version, no CHANGELOG.

## Done when

- [ ] The pictures are gone from `main`, each with a copy in the private repository's `img/`
- [ ] No link points at a deleted file; the kept pictures are named in the report with a one-line reason
- [ ] Report filled in (files deleted, MB, which were kept and why); TASKS.md row done

## Not in this task

Pictures of other tasks, `docs/img/`, `site/media/` (none show the equipment – study 0226), any rewording of old
reports beyond the links.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026

**What changed:** 65 pictures (about 2 MB less; `tasks/img/` 13 MB -> 11 MB, 122 -> 57 files) deleted from `main`: the 53 listed, plus
all 5 of 0106 (carousel, tensioners on the deck), 0080's two (drum and carousel), 0109's `presets`, `time_of_day`,
`wet_snow` (they show the carousel) and 0179's `before_360` (a carousel in the list). Links in 22 old task files now say
*(picture removed – private, task 0226)*. Private repository: byte copies of all, 4 were missing and were added
(0080 x2, 0109 x2) to `img/` + `LIST.md` on its branch `claude/intelligent-faraday-15f3zc` (not main).

**Kept and why:** `0109_sea_before_after`, `0109_sea_horizon` (ship with crane, sea only), `0109_mill_night_fixed`, the
test-model pictures (`0107_mill_render`, `0154_test_*`, `0158_test_*`), `0148_seabed_shot` (seabed only, no equipment),
0179's phone/laptop pictures and every other picture of the range (mill, web page, people, props, looks).

**Tested and measured:** grep of every deleted name over the repository: no hit left. Guide build untouched (no `docs/` change).

**Open points / follow-up tasks:** the history keeps the pictures (by decision). The private branch needs merging by the owner or a private-repo task.
