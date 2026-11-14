# 0124 – One function list + an anchor on every guide section + guide links on the website

**Who:** worker · **Status:** running · **Branch:** `ccr-0aa92403-hdxoti` (the web session's branch)
**Started by:** lead chat, 14 Nov 2026 (task 1 of study 0123's proposed tasks) · **Lane:** Learning (+ Docs). Files:
new `fresing_render/core/functions.py`, new `tests/test_functions.py`; `docs/USER-GUIDE.md` (anchors only, no text
changes); `tools/build_guide.py` (contents list); additive: `tools/ci_precheck.py` (one check), `site/media/media.json`
(`functions` per item), `tools/build_site.py` (the links). **No UI change, no app behaviour change.**
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

One list of every function the owner can see, in one place, that the side-panel overhaul (0062), the lessons (later
Learning tasks), the user guide and the website all read. After this task, adding a new function means adding one
entry, and the precheck says so when something is not linked.

## Background – read first

- **Study 0123's report** (`tasks/0123-learning-modes-study.md`, answers 3, 6, 7, 8 and "Proposed tasks" row 1) has the
  format, who reads it and why. The prototype's `fresing_render/core/functions.py` on branch `task/0123-learning-study`
  (11 crane entries + `problems()`) is the starting point: take it over (`git checkout task/0123-learning-study --
  fresing_render/core/functions.py`), do not take `lesson.py`, `lesson_crane.py` or the other prototype files.
- Fields per entry: `id` (`area.name`, never changes), `title`, `family` (0062's sets: import, looks, motion, machines,
  cnc, milling, offshore, scene, animation, queue, web, house), `panel`, `fold`, `button` or `prop` + `text`, `guide`
  (anchor), `tour` (stop ids), `pccheck` (Full line ids), `lesson` (empty for now), `since`.
- About **120 entries**: every test-tour stop, every Full PC-check line and every guide section must be named by an
  entry (several may share one). Check `family`, `panel` and `fold` against the real panel code (`blender/ui*.py`) –
  0062 sorts the panels by them, so they must be right.
- The guide has 23 anchors for 76 sections. Add `<a id="…"></a>` above every `##` and `###` heading that lacks one
  (stable, short, lower-case ids; keep the existing 23 as they are, so old links keep working – except fix `find`, which
  sits on "X-ray look" and not on "Find & sort parts": give X-ray its own id and move `find`). `build_guide.py` lists
  the `###` sections in the contents too.

## Done when

- [ ] `core/functions.py` with every function; `problems()` returns sentences that say what to fix (entry without a
      guide anchor, anchor that does not exist, stop or Full line no entry names, unknown family/panel, duplicate id).
- [ ] The precheck runs `problems()` and fails with those sentences; `tests/test_functions.py` tests the check itself
      (a made-up broken entry is caught for each kind of problem) and that the real list has none.
- [ ] Every guide section has an anchor; the contents list shows the `###` sections; old anchors still work; guide
      tests green.
- [ ] `media.json` items carry `functions: [...]` (ids from the list) and the built site shows under each picture,
      video and 3D viewer a short "How it's done: <title> · <title>" line linking to `guide/…#<anchor>`; `build_site.py`
      refuses an unknown id; `tests/test_site.py` covers it. Nothing of the Fresing 400.
- [ ] CLAUDE.md section 6: a short rule "a new function adds its entry in `core/functions.py` and a guide anchor"
      (the full lesson rule of 0123 comes later with the lessons task) and a line in section 3.
- [ ] GitHub green; merged to `main`. A version + CHANGELOG line only if something the owner sees changed (the guide's
      contents and the site's links do: next free version, short line); report filled in; `TASKS.md` (0124 done).

## Not in this task

The lesson engine, the Lesson or Guide panel, any panel change (0062), the `fresing://` link, the test models (0122
may run at the same time: do not edit `tour.py` or the test models; only read the stop ids).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
