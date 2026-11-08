# 0031 – Claude Code on the web: a stored set-up for every worker session

**Who:** worker (two rounds; the owner changes one setting in between) · **Model:** Sonnet · effort Medium ·
**Place:** Claude Code on the web · **Status:** open – can start · **Branch:** `task/0031-web-setup`
**Started by:** lead chat, 6 Nov 2026 · **Lane:** Quality & delivery · **Area:** a new set-up script in `tools/`,
`.claude/` (if a session hook is used), CLAUDE.md sections 4 and 5, `tests/test_ci_tools.py` (or a new small test
file). No app code.

## Goal

Every worker session starts with everything it needs already there – the Python venv with the pinned packages,
the real Blender 5.2.3 (Linux), `xvfb-run` and ImageMagick – without spending its first minutes (and the owner's
usage) on installing. Workers can then run real-app tests and make user-guide pictures locally again instead of
only on GitHub.

## Background

- Since 5 Nov workers run in Claude Code on the web (CLAUDE.md section 2). Today each session sets itself up by
  hand (section 4) and **download.blender.org is blocked**, so workers cannot run the real app or
  `tools/guide_screens.py`: 0026 had to make its guide pictures in a GitHub job and read them back from the log as
  base64; 0025 and 0034 left their guide pictures undone for that reason.
- What section 4 says now (check it against Anthropic's current documentation at docs.claude.com before relying
  on it – it may have changed): a cloud environment can have a **set-up script** that runs once and whose result is
  stored for later sessions (about 7 days), but only when it finishes within about 5 minutes; the environment has
  its own list of **allowed websites**, and the default list covers PyPI and GitHub, not download.blender.org.
  Another route is a **session-start hook** in the repository's `.claude/settings.json` (runs every session, so it
  must be quick when things are already there). Pick what the documentation supports; a combination is fine.
- GitHub's workflow already downloads Blender with a checksum check (`.github/workflows/tests.yml`, around line
  207): reuse that logic (same file name, same sha256 check).
- If the owner cannot or would rather not allow download.blender.org: Blender is GPL, so a copy of the Linux
  tarball as an asset of a GitHub release of this repository (e.g. a release `blender-5.2.3-linux`) is allowed –
  check first whether a session can download GitHub release assets with the default network list. Say in the
  report which route was used and why.
- The owner is not a programmer: anything he must set in claude.ai/code goes to him as numbered click-by-click
  steps with the exact names of the screens and fields, and what he should see when it worked.

## What to build

**Round 1 (this session):**
1. `tools/web_setup.sh` (name free): idempotent – skips what is there already. Python venv at `~/venv` from
   `tools/requirements-dev.txt`; Blender 5.2.3 Linux into a fixed place (e.g. `~/blender-5.2.3`) with its sha256
   checked; `xvfb` and ImageMagick (apt) if missing; the Linux wheels dir for the packaged test (section 5 command)
   into a fixed place. Prints one line per part with its time, and a last line "ready in N s".
2. Run it in this session as far as the network allows; time each part. If the Blender download is blocked here,
   test that part against the GitHub-release route or say so.
3. Steps for the owner (in the report **and** in your last message): how to put the script and the allowed website
   into the environment of `smholte/CAD-render-animation` in claude.ai/code.
4. Push the branch (code + CLAUDE.md section 4 draft), write round 1 in the report, set the task to
   "waiting – owner sets the environment" in `TASKS.md`, and tell the owner the sentence for round 2:
   "Read CLAUDE.md and TASKS.md in github.com/smholte/CAD-render-animation and continue task 0031 from its branch."

**Round 2 (a new session, after the owner's change):**
5. Check the stored set-up arrived: Blender, venv, xvfb, ImageMagick are there at the start. Measure: time from
   session start to "ready" (first session after the change and a later one), and run one real-app test
   (`python3 tools/ci_real_app.py --only waycover …`) and one `tools/guide_screens.py` picture to prove they work.
6. CLAUDE.md section 4 rewritten for the new way (what is there at start, where, what to do when the stored set-up
   expired); section 5's real-app and guide-picture rows say they run locally. A small test checks the script's
   paths and versions match `tools/requirements-dev.txt` and the workflow's Blender version, so they cannot drift.
7. Merge as CLAUDE.md sections 2 and 7 say (this task touches no app code: no version number, no release, unless the
   precheck asks for one).

## Done when

- [ ] A fresh worker session has venv, Blender 5.2.3, xvfb and ImageMagick at start; times measured (round 2)
- [ ] One real-app test and one guide picture made locally in such a session
- [ ] Owner's click steps written and used once
- [ ] CLAUDE.md section 4 and 5 current; drift test added; GitHub run green
- [ ] Report filled in: route chosen, times before/after, runs needed

## Not in this task

App code, the workflow's test jobs (task 0036 just reorganised them – read, do not change), the user guide.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 7 Nov 2026. Both rounds in one session: the session could create
and switch to the new environment itself (owner approved the card), so no second session was needed.

**What changed:** `tools/web_setup.sh` (idempotent: apt packages, `~/venv`, Blender 5.2.3 with sha256 check into
`~/blender-5.2.3`, Linux wheels into `~/linux-wheels`; one line per part + "ready in N s"), `tools/web_install_app.py`
(settings folder `~/fr_user` for guide pictures), `tests/test_web_setup.py` (drift test: Blender version vs installer,
OCP/manifold versions vs workflow and requirements), CLAUDE.md sections 4 and 5 rewritten. Route: **download.blender.org
allowed in the environment** (a GitHub-release copy was not needed). Environment "CAD-render-animation" (personal,
Limited network + `download.blender.org`, setup script `for d in */tools/web_setup.sh; do [ -f "$d" ] && bash "$d"; done`).

**Tested and measured** (this session, 4 cores): from nothing: apt 6 s, venv 76 s, wheels 16 s, Blender download+unpack
37 s = about 2.3 min (under the 5-minute limit); a second run 0 s per part. Real-app `--only waycover`: 14/14 passed, 27 s.
Guide picture (`GUIDE_SHOTS=decals`) made in ~1 min. Drift test passes. The download was refused (403) before the
environment was changed. **Not yet measured:** a fresh session starting on the new environment (the script is only
read from the repository once it is on `main`).

**Runs:** 2 full runs, both green first time (12.7 and 13.4 min): the code push, then the merge of `main` (0.2.34). Merged to `main` by fast-forward at 725b05d (no version change, no release).

**Open points:** (1) ~~merge to `main`~~ done; (2) owner: start a new session with
environment CAD-render-animation and check `ls ~/blender-5.2.3` - then the start-time measurement; (3) the local
`ci_precheck.py` complains about the version only because this branch equals `main`; no version change here.
