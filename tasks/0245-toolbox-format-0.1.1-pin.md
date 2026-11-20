# 0245 – toolbox-format v0.1.1 pinned; Windows checks W2 (junction in an inbox) and W3 (status.json replaced while read)

**Who:** worker · **Status:** running ·
**Branch:** `task/0245-toolbox-format-0.1.1`
**Started by:** lead, 20 Nov 2026 (lead post: ToolBox's messages of 19 and 20 Nov – v0.1.1 tagged, W2 / W3 asked of us) ·
**Model:** Opus · effort Medium
**Area:** Toolbox lane – `fresing_render/core/tbf/` (the copied reference files), `tests/data/toolbox/tbf-v0.1*`,
`fresing_render/core/toolbox.py` (only where a 0.1.1 fix shows the same bug), the toolbox tests; additive: one Windows
CI step (Quality & delivery lane, after 0242), the toolbox line in `THIRD-PARTY-NOTICES.md` and its copy.

## Goal

Fresing Render follows `smholte/toolbox-format` **tag `v0.1.1`** (22 bug fixes from ToolBox's independent review, no
rule changed), and GitHub's Windows job proves the two checks the format's reviewer could not run: **W2** and **W3**.
The answer goes back to the ToolBox lead (the lead sends it; workers never touch the lead post).

## Background

- 0217 copied `names.py`, `detect.py` and `types.json` from tag `v0.1` into `fresing_render/core/tbf/` (byte for byte,
  one marked line in `detect.py`) and the whole tag into `tests/data/toolbox/tbf-v0.1/` (`PINNED.md` with SHA-256,
  checked by `tests/test_toolbox_pinned.py`). The inbox, status and clean-up code is **our own**,
  `core/toolbox.py`, written to `FORMAT.md` – it does not use the reference `folder.py`.
- v0.1.1 (commit `cc0356c…`, the tag's `CHANGELOG.md` section 0.1.1 lists every fix): crashes on hostile but valid input
  (a `scene.json` in a `.hpscene` nested 3000 deep, a number with thousands of digits – crashed every Python tool that
  detected the type; an unpaired `\ud800` escape in a title; two copies writing `alive.json` at once), 13 places where
  JavaScript and Python disagreed (a key written twice in `scene.json`, a BOM in a zip entry's name, a cut-short zip64
  field, a folder where a file should be, a `job.json` another program holds open → "try again", not `failed`), and one
  verdict changed: JSON with an unpaired surrogate escape is refused.
- What `core/toolbox.py` already does (read it, don't trust this line): `is_link()` treats a reparse point with the
  name-surrogate bit (junction, mount point, symlink) as a link that is never read, followed or deleted; `_write()` keeps
  a status write that Windows refused and writes it at the next look (`_flush()`), so a refused replace never stops a job.
- Format 0.2 (ToolBox task 0011) comes later through the lead post for review; not part of this task. Keep the
  "missing" test filter (ToolBox's answer of 20 Nov).

## What to do

1. **Pin v0.1.1.** New folder `tests/data/toolbox/tbf-v0.1.1/` from the tag (same set of files as `tbf-v0.1`, new
   `PINNED.md` with the full commit and SHA-256), point the four test files' `PIN` at it, delete `tbf-v0.1/`. Copy
   the tag's `names.py`, `detect.py`, `types.json` into `core/tbf/` (keep the one marked line), update the header of
   `core/tbf/__init__.py` and the toolbox line in `THIRD-PARTY-NOTICES.md` + `fresing_render/licenses/` copy.
2. **Same bugs in our own code?** Go through the changelog's 0.1.1 list and check each fix against `core/toolbox.py`
   (and `blender/toolbox_inbox.py`). Where our code has the same fault, fix it with a test; where it doesn't, one line
   in the report. A table in the report: fix → "copied" / "fixed here" / "not in our code".
3. **W2 on Windows:** a directory junction (`mklink /J`) inside our inbox (and one in place of a job folder's file):
   the inbox scan and the clean-up skip it and never delete through it; the junction's target stays untouched.
4. **W3 on Windows:** a writer replaces a job's `status.json` every second while a reader holds it open / reads it every
   second (a second process), for about 40 s like a bake: the job finishes, refused writes are kept and written at the
   next look, the last status on disk is the final one. Count how many writes Windows refused.
5. Run W2 and W3 **under Blender's own Python** in GitHub's Windows job (that is what the app runs on) – one short
   step, e.g. the installed Blender's `python.exe` on a plain test file; add it where it costs the least time (say
   where and how long it takes). If cheap, also under the runner's Python 3.11, since ToolBox's fix targets 3.11.
6. CLAUDE.md section 8: one line on what W2 / W3 showed.

## Done when

- [ ] `tbf-v0.1.1` pinned and checked by SHA-256; `core/tbf/` matches the tag (one marked line); `tbf-v0.1` gone
- [ ] The 0.1.1 table in the report; every "fixed here" has a test
- [ ] W2 and W3 green on GitHub's Windows job; the report gives **Windows version, Python version(s), refused writes
      in W3, and whether 5 × 50 ms (the reference code's retry) would have been too short** – the lead passes this on
- [ ] Precheck green, full run green, report filled in, merged, released

## Not in this task

Format 0.2; the `view-step` action; any change to what the app writes (no rule changed); House Planner's side.
