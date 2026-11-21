# 0245 – toolbox-format v0.1.1 pinned; Windows checks W2 (junction in an inbox) and W3 (status.json replaced while read)

**Who:** worker · **Status:** done (0.2.188) ·
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

- [x] `tbf-v0.1.1` pinned and checked by SHA-256; `core/tbf/` matches the tag (one marked line); `tbf-v0.1` gone
- [x] The 0.1.1 table in the report; every "fixed here" has a test
- [x] W2 and W3 green on GitHub's Windows job; the report gives **Windows version, Python version(s), refused writes
      in W3, and whether 5 × 50 ms (the reference code's retry) would have been too short** – the lead passes this on
- [x] Precheck green, full run green, report filled in, merged, released

## Not in this task

Format 0.2; the `view-step` action; any change to what the app writes (no rule changed); House Planner's side.

## Report

**Chat / date:** Claude Code on the web, 20–21 Nov 2026. No subagents (Medium task; the independent tests of 0217 judged
the inbox again against the new checker).

**What changed:**
- `tests/data/toolbox/tbf-v0.1.1/` from tag `v0.1.1` (commit `cc0356c39c1237c1c89d0c557e9cb83b39962e7b`), the same 37
  files as before + `PINNED.md` with SHA-256; `tbf-v0.1/` deleted; the four test files point at it. Of the tag, only
  `tbf/*.py` changed – `FORMAT.md`, schemas, samples, `types.json`, `LICENSE` byte for byte as in v0.1.
- `core/tbf/names.py`, `detect.py`, `types.json` copied again (one marked line in `detect.py`), header of
  `core/tbf/__init__.py`, the toolbox line of `THIRD-PARTY-NOTICES.md` and its copy in `licenses/`.
- `core/toolbox.py`: `read_doc` reads a key written twice as the last (reader mode of 0.1.1); `take` refuses a size
  above 2^53 − 1 and a file name this PC cannot hold (lstat: ENAMETOOLONG / EINVAL / EILSEQ / ValueError) at once as
  bad-job. Nothing the app writes changed.
- Tests: `test_toolbox.py` – "duplicate-key" is no longer refused (new test: the last counts), new refused cases
  "size-too-big", "name-too-long" (each failed before the fix); `test_toolbox_independent.py` – the checker's
  `_times` is gone in 0.1.1 (its `read_doc` checks times), and our `read_doc` is now compared with the checker in
  reader mode (`strict=False`); `test_w2_w3_pass_and_report_their_numbers` in `test_toolbox.py` runs the W2/W3 tool 3 s on Linux.
- `tools/ci_toolbox_w2w3.py` (plain Python, imports `core` without Blender) + a step in `tools/ci_windows_install.ps1`
  part A, right after `ci_toolbox_windows.py`: the installed Blender's `python.exe` in the foreground and the runner's
  Python 3.11 (`$env:RUNNER_TOOL_CACHE\Python\3.11.*`) at the same time; both results in the job's summary table.
  It adds **45 s** to Windows part A.
- CLAUDE.md section 8: one line on W2/W3.

**The 0.1.1 list against our code** (each tried with a hostile job on the old and new code, `core/toolbox.py` +
`blender/toolbox_inbox.py`):

| 0.1.1 fix | Here |
| --- | --- |
| JSON nested thousands deep (RecursionError) | copied (`names.load_json`; old: the job was refused "maximum recursion depth", the look logged an error) |
| number with > 4300 digits | copied (old: refused with Python's ValueError text) |
| count in a pattern Python cannot hold `a{4294967295}` | copied (`names.pattern_problem`, used by own types) |
| file name the system cannot hold (OSError) | **fixed here** – old: waited a minute, then "not complete"; test `name-too-long` |
| the same in a house scene's `scene.json` | copied (`detect.py`) |
| two copies writing `alive.json` at once | not in our code (`write_json` already uses a random temp name per write) |
| unpaired `\ud800` escape refused | copied (`load_json`; old: such a title was taken) |
| `[\s-z]` range in a pattern | copied |
| own types with keys in another order = same type | not in our code (`all_types` compares dicts, order does not count) |
| BOM in a zip entry's name; zip64 field cut short | copied (`detect.py`) |
| key written twice in a job / scene: the last counts when reading | **fixed here** for jobs, statuses, manifests (`read_doc`); scene.json copied; test `test_a_key_written_twice_the_last_counts` |
| a date that does not exist | not in our code (we used `names.time_problem` already; now the new one) |
| job field `constructor` / `toString` | not in our code (unknown fields are refused) |
| a folder in place of a job's file | not in our code (bad-job already) |
| a size no file can have | **fixed here** – old: waited a minute, then "not complete"; test `size-too-big` |
| `job.json` held open by another program → try again | not in our code (OSError → next look already) |
| `send()`: names differing only in capitals; title cut to 120 | not in our code (both already) |
| `clean()` deletes only job folders | not in our code (`_job_folders` takes job ids only) |
| junctions on Python 3.11 | not in our code (`is_link` reads the reparse tag); proved by W2 on 3.11 below |

**Tested and measured:**
- Here (4-core web machine): the toolbox tests (`test_toolbox*.py`, `test_about.py`) 146 passed.
- GitHub run 44831037647 (branch, 0.2.184 before the renumber): full, green (34.8 min, queued behind other runs).
- **W2 / W3 on GitHub's Windows runner** (Windows Server 2025, 10.0.26100; numbers for the ToolBox lead):

| | Blender's Python | runner's Python |
| --- | --- | --- |
| Python | 3.13.13 (Blender 5.2.3's own – not 3.11) | 3.11.9 |
| W2: junction reparse tag / `os.path.isjunction` | 0xA0000003 / yes | 0xA0000003 / no (tag read instead) |
| W2: junction named like a job taken? job with a junction as its file? | no / bad-job | no / bad-job |
| W2: anything deleted through a junction (clean-up at +40 days, finished job's files)? | no | no |
| W3: refused `status.json` writes in 40 s | 22 | 36 |
| … while the reader opened, read, closed (every 1 s, first 20 s) | 0 | 0 |
| … while the reader held it open 0.5 s (every 1 s, last 20 s) | 22 | 36 |
| longest a write stayed refused (looks every 25 ms) | 0.30 s | 0.50 s |
| refusals longer than 0.25 s | 1 | 1 |
| reader: reads / not whole / refused | 43 / 0 / 0 | 43 / 0 / 0 |
| last status on disk | done | done |

  **5 × 50 ms would have been too short** for a reader that holds the file (1 of 22 and 1 of 36 refusals lasted longer
  than 0.25 s; a hold of 0.5 s outlasts it by design); for a reader that opens, reads and closes no write was refused
  at all. Keeping the write for the next look (what our `Inbox._later` does) always got through.

**Runs:** 6 full – `main` brought 0241 (0.2.184), 0239 (0.2.185), 0237 (0.2.186) and 0246 (0.2.187) while they ran, so renumbered four times; this task is 0.2.188. The 4th run failed only on "2 tests skipped (1 allowed)" in one pytest group: the new file `tests/test_toolbox_w2w3.py` had shifted the groups so that two tests that are always skipped on GitHub's Linux met in one group; the test moved into `tests/test_toolbox.py` (groups the same as on `main`) and a 5th run.

**Open points:**
- Tell the ToolBox lead: Blender 5.2.3 runs Python **3.13**, not 3.11 (0.1.1's changelog says "Python 3.11 (Blender)");
  the 3.11 path works too (above).
- CI: the pytest groups allow 1 skipped test each, and a new test file can regroup two always-skipped tests into one
  group (here). Worth a look in the Quality lane (which two skip on GitHub's Linux could not be read from the log).
- Our readers now take a key written twice; the checker still refuses it in what we *write* (we never write one).
