# 0124 – One function list + an anchor on every guide section + guide links on the website

**Who:** worker · **Status:** done (0.2.100) · **Branch:** `ccr-0aa92403-hdxoti` (the web session's branch)
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

- [x] `core/functions.py` with every function; `problems()` returns sentences that say what to fix (entry without a
      guide anchor, anchor that does not exist, stop or Full line no entry names, unknown family/panel, duplicate id).
- [x] The precheck runs `problems()` and fails with those sentences; `tests/test_functions.py` tests the check itself
      (a made-up broken entry is caught for each kind of problem) and that the real list has none.
- [x] Every guide section has an anchor; the contents list shows the `###` sections; old anchors still work; guide
      tests green.
- [x] `media.json` items carry `functions: [...]` (ids from the list) and the built site shows under each picture,
      video and 3D viewer a short "How it's done: <title> · <title>" line linking to `guide/…#<anchor>`; `build_site.py`
      refuses an unknown id; `tests/test_site.py` covers it. Nothing of the Fresing 400.
- [x] CLAUDE.md section 6: a short rule "a new function adds its entry in `core/functions.py` and a guide anchor"
      (the full lesson rule of 0123 comes later with the lessons task) and a line in section 3.
- [x] GitHub green; merged to `main`. A version + CHANGELOG line only if something the owner sees changed (the guide's
      contents and the site's links do: next free version, short line); report filled in; `TASKS.md` (0124 done).

## Not in this task

The lesson engine, the Lesson or Guide panel, any panel change (0062), the `fresing://` link, the test models (0122
may run at the same time: do not edit `tour.py` or the test models; only read the stop ids).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 14 Nov 2026. Branch `ccr-0aa92403-hdxoti` (the session's own
branch, fast-forwarded to `main`). Version **0.2.100**.

**What changed:**
- `fresing_render/core/functions.py` (from 0123's prototype): **93 entries** in 13 families (0062's 12 + `help` for the
  Help-menu functions: updates, PC check, test tour, demo). Each has family, panel (a `FRESING_PT_…` class or a menu:
  `TOPBAR_MT_help`, `TOPBAR_MT_file_import`), fold, button (operator id) or setting (property name), button text where
  the operator is drawn more than once, guide anchor, tour stops, PC-check Full lines, since; `lesson` is empty
  (the 0123 prototype's crane step numbers were taken out: no lessons on `main` yet). The 0123 ids are kept
  (`looks.light_look` stays although its family is `scene`).
- `problems()` checks: id format, duplicate id, family, title, since, button-or-setting, panel / fold / button / setting
  exist (read from `blender/ui*.py` and every `bl_idname`), the button text is in the app's code, anchor exists, tour
  stop and Full line exist, lesson step exists (when lessons are given); and the other way round: every tour stop (61),
  every Full PC-check line (80) and every guide anchor (86, minus the 16 reading-only ones in `READING`: layout,
  first steps, tips, troubleshooting) is named by an entry, no anchor twice. `read_repo(root)` reads all of it with
  `ast`/regex, no Blender. `tools/ci_precheck.py` `check_functions()` adds the sentences ("function list: …").
- Guide: **64 new anchors** (every `##`, `###`, `####` heading, plus 9 bold sub-sections of 6 Animation and 1 Import:
  run-motor, run-gcode, camera-path, fade, sequence, trails, finishing, pictures-music, update-model); the 23 old ones
  unchanged except `find`, now on "Find & sort parts" (X-ray look got `xray`). No text changed; one line in the notes
  for the chats (the anchor rule). `build_guide.py`: the contents list shows the `###` sections (53) indented under
  their chapter.
- Site: every `media.json` item (hero, 6 gallery items, the feature picture, 2 web models) has `functions`; under each
  a line "How it's done: <title> · <title>" links to `guide/#<anchor>` (model pages: `../../guide/#…`, in the note
  line). `build_site.py` refuses an unknown id (build and `how_html`), `check()` lists unknown ids and links to guide
  sections that do not exist; `--take` and `--web-model` keep `functions` (from the kit's items / the replaced model).
  Nothing of the Fresing 400 added (the hero video's links point at G-code / Tools / Chips in the guide, which shows
  only test models).
- CLAUDE.md: rule in section 6, `functions.py` in section 3. CHANGELOG 0.2.100.

**Tested and measured** (Claude Code web session, 4 cores): `tests/test_functions.py` 24 passed (14 kinds of broken
entry each caught, a stop/line/section nobody names, duplicate id and anchor, the precheck's sentences, the real list
clean); `tests/test_user_guide.py` 11 passed (old anchors, `find`/`xray`, contents with sections);
`tests/test_site.py` 27 passed (new: How it's done links, unknown id refused by build, `how_html` and `check`);
`tests/test_ci_tools.py` passed; `tools/ci_precheck.py` passed; `tooltip_report.py` 738 ok. Looked at one gallery
card and one 3D-model card of the built site (Playwright, cropped): the line sits under the caption, links underlined.
GitHub: see below.

**Open points / follow-up tasks:**
- `family` / `panel` / `fold` were checked against the panel code (the button or setting is drawn in the file that
  defines the panel; folds by their file); 0062 should still read the list once while it moves panels and fix entries
  it finds wrong. Family calls that are judgement: labels, brand kit and watermark → `animation` (video finishing),
  hoses / drag chains / tracks → `machines`, vessel motion → `offshore`, the G-code step → `cnc`.
- The lessons task fills `lesson` and adds the lesson rule to CLAUDE.md (0123's text).
- 93 entries, not ~120: every stop, Full line and section is named; further entries (e.g. lock, clear cache, poses
  of visibility) can be added when a lesson needs to point at them.
