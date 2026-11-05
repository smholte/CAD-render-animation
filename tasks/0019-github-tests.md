# 0019 – Automatic tests on GitHub, including a Windows install

**Who:** worker · **Status:** done · **Branch:** `task/0019-github-tests`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Quality & delivery · **Area:** `.github/`,
`tools/` (test runners), `installer/` (only switches needed to run unattended), `README.md`,
`CLAUDE.md` sections 4–5 and 7. **No app code** (`fresing_render/`), so no clash with other lanes.

## Goal

Every push to GitHub runs the tests by itself – on Linux and on a real Windows machine – so a
mistake is caught before it reaches the owner, especially Windows-only ones (every installer
before 0.2.2 had a PowerShell error that no Linux test could see). Several chats now merge into
`main`; this protects it.

## Background

- The repository is public: GitHub's standard runners (Linux and Windows) are free for public
  repositories.
- Tests today: `CLAUDE.md` section 5 (pytest suite ~8 min on 2 cores, real-app tests under
  xvfb, packaged Linux self-test). Windows parts (`installer/*.ps1`, ctypes, subprocess flags,
  paths) have only been checked by review and by the owner's PC.
- `tools/build_release.py` builds the Windows zip on Linux (downloads Windows wheels).
- Unknown: whether the chats' git access may push files in `.github/workflows/` (GitHub asks for
  a special "workflow" permission). Try it first. If it is refused, do not look for a way
  around it: give the owner numbered click steps to add the file on github.com himself
  (Add file → Create new file, path, paste, Commit).
- Also unknown: whether the chats can read the run results (GitHub API through the proxy, or the
  public web pages). Find out and write the way that works into `CLAUDE.md`.

## What to build

1. **Linux job** on every push and pull request: install the pinned packages, run the full pytest
   suite, the real-app tests under xvfb (download the Blender 5.2.3 Linux build in the job; cache
   it), and the packaged Linux self-test. Upload logs and screenshots as run artifacts – generic
   test models only.
2. **Windows job:** build the Windows zip, run `Install.bat` unattended into a temporary folder
   (portable Blender download inside the job), start the self-test, and fail the job on any line
   that is not OK – except the graphics-card line (no GPU on GitHub's runners), which must say
   "skipped: no graphics card" rather than fail. Upload the self-test report.
3. Results visible: status badge in `README.md`; a failing run is easy to read (which test).
4. `CLAUDE.md`: workers check the GitHub run after their merge and fix a red run first; how to
   read the results from a chat.

## Done when

- [x] Both jobs run green on `main`; a deliberately broken test on a scratch branch turns the run
      red (then delete the branch – refused for chats, owner deletes it, see report)
- [x] Windows job: install + self-test pass; the report is attached to the run
- [x] Run time of each job in the report; `CLAUDE.md` updated
- [x] Report filled in; merged (no app release needed unless the installer changed)

## Not in this task

- Publishing releases and the update channel (0020, builds on this).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4 Nov 2026 (evening).

**What changed:**
- `.github/workflows/tests.yml`: four jobs at every push (any branch), pull request, or by hand
  (Actions → Tests → Run workflow). A newer push to a branch cancels its older run; `main` runs
  always finish. Pinned runners: `ubuntu-24.04`, `windows-2025`.
  1. *Linux - test suite + packaged self-test*: pytest with a JUnit file (verdict table + one error
     line per failing test), then `test_install_linux.py` and its report judged.
  2. *Linux - real app*: `tools/ci_real_app.py` installs the extension (Linux wheels) and the app
     template into a fresh settings folder of the real Blender 5.2.3 and runs `ui_test_app.py`,
     `ui_test_app2.py` (xvfb) and `paths_test_blender.py`; logs + screenshots of the test crane
     are uploaded.
  3. *Build the Windows installer zip* with `tools/build_release.py`, exactly as for a release.
  4. *Windows - install + self-test* (`tools/ci_windows_install.ps1`): unzips into
     `…\Mijn downloads é\`, sets `LOCALAPPDATA` to `…\Users\Sébastien Test\AppData\Local`, runs
     `Install.bat` with no keyboard (its pause gets an empty input) – once fresh, once as a repair
     – checks Blender, extension version, app template, preferences, both Start-menu shortcuts and
     the Desktop shortcut, starts the self-test from the **Start-menu shortcut's own target and
     arguments**, judges the report, then runs `Uninstall.bat` and checks that everything is gone.
  Blender (Linux tar / Windows zip) is downloaded once per version, checked against its SHA-256
  and cached; the version and checksum are read from `installer/Install-FresingRender.ps1`.
- Self-test (`fresing_render/selftest.py`, the only app file touched): with
  `FRESING_SELFTEST_NO_GPU=1` (set only by the workflow) the two graphics-card lines say
  `[SKIP] …: skipped: no graphics card`; RESULT reads "ALL OK (2 skipped)". Without the variable –
  the owner's PC – nothing changes: a missing graphics card is still a FAIL. No release needed:
  users never see the difference; the next release of any lane carries it.
- New tools: `ci_check_selftest.py` (every line must be OK, only graphics-card lines may be
  skipped, RESULT line required, at least 10 checks), `ci_pytest_summary.py`, `ci_real_app.py`,
  `ci_windows_install.ps1`, `ci_status.py` (read a run from a chat), `requirements-dev.txt`
  (pinned packages). `test_install_linux.py` takes a report path and can build with a real
  Blender; `paths_test_blender.py` takes its folder from `PATHS_TEST_DIR`.
- Two real-app test bugs found by the first runs (they only passed before because the chat
  machines had the test crane in the import cache): an Esc sent in the same step as the import
  cancelled the import (the test then waited 30 minutes); the click "in the middle of the side
  panel" landed on a drop-down after a fresh import, which ate the pin click. Fixed in the tests;
  the import wait now gives up after 5 minutes. Not app bugs.
- README: status badge, setup with `requirements-dev.txt`. CLAUDE.md: rule "check the run;
  a red `main` comes first", section 5 how to read runs from a chat, release steps 3 and 5,
  lessons.
- 13 new tests (`tests/test_ci_tools.py`): the report checker, the pytest summary, the skip switch.

**Tested and measured** (GitHub's free runners: 4 cores, no graphics card; test models only):
- Green run on the branch, 356f0e4 (run 41917737164): all four jobs passed.

  | Job | Time |
  | --- | --- |
  | Linux - test suite + packaged self-test | 8.3 min (pytest 1,265 passed in 5.5 min; the render-queue test alone 4.5 min) |
  | Linux - real app | 9.8 min incl. the first Blender download (ui1 22/22 in 6.1 min, ui2 29/29 in 0.7 min, paths 8/8 in 2.0 min) |
  | Build the Windows installer zip | 0.4 min |
  | Windows - install + self-test | 2.0 min with Blender cached (install 15 s, repair 3 s, self-test 79 s, uninstall 1 s); 3.1 min when Blender was downloaded |

  Whole run about 10 minutes. Windows self-test on the runner: all lines OK, graphics card and
  HD render "skipped: no graphics card"; "Fast import" ran on 3 helper cores; App start (the
  Desktop-shortcut check) ran for real; Time test 44 s per frame (CPU, draft).
- Red-run check: scratch branch `scratch/0019-red-check` (4679fa0, run 41926045287) with one
  failing pytest test and one self-test line made to fail: the suite job and the Windows job went
  red and named exactly `test_deliberately_broken_for_the_red_run_check` and
  "Video encoder (MP4): deliberately broken…" (annotations, job summary, `ci_status.py`).
- What the chats can do (found out): pushing `.github/workflows/` works; runs, jobs, logs and
  annotations can be read through `gh api`; **artifacts cannot be downloaded** (their storage
  host is blocked by the proxy); `actions/permissions` is blocked; **deleting a branch is
  refused (403)**.
- On the 2-core chat machine: full suite 1,252 passed before (5.5 min); packaged self-test
  ALL OK (2 skipped, 2.3 min); with a fresh settings folder ui1 failed 14/17 before the test
  fixes and passed 17/17 after (quick mode, no renders; the full 22/22 ran on GitHub), ui2 29/29,
  paths 8/8.
- Independent review (a helper that did not write the code) before the merge: 1 blocker, 4
  should-fix, 6 minor/no-problem. All fixed except where noted under open points:
  `ci_status.py` could show an older commit's green run right after a push (now only the exact
  commit); the side-panel click hit no part, so it tested nothing (the view is now moved so the
  boom lies behind the click, proved with a ray; removing the side-panel guard in the app turned
  the test red); skipped tests (bpy/OCP not loading) could look green (package check + at most 1
  skip); Python errors outside the test steps and checks that silently disappear now fail;
  shorter limits so a stuck test cannot use up the whole job; files uploaded also after a
  timeout; the self-test skip only for a plain "CPU" result; strict check on Windows (App start
  must really run).
- Merged the newest `main` (0.2.9, 0.2.10) into the branch; the runner now also runs
  `ui_test_faces.py`. Final branch run 9ce40a6 (run 41934041369), all green:

  | Job | Time |
  | --- | --- |
  | Linux - test suite + packaged self-test | 9.2 min (1,302 passed, 0 skipped, 6.3 min) |
  | Linux - real app | 12.2 min, Blender from the cache (ui1 23/23 in 7.9 min, ui2 39/39 in 0.8, faces 10/10 in 0.3, paths 8/8 in 2.6) |
  | Build the Windows installer zip | 0.4 min |
  | Windows - install + self-test | 3.1 min (install 20 s, repair 5 s, self-test 135 s, uninstall 2 s); RESULT "ALL OK (2 skipped because FRESING_SELFTEST_NO_GPU=1)" |

  Run times vary by ±30 % between runs on GitHub's shared machines.
- After the merge, first run on `main` (ef54d3a, run 41935861802): all four jobs green (suite
  5.0 min, real app 10.2 min, build 0.6 min, Windows 2.8 min). Blender is now cached for all
  branches.

**Open points / follow-up tasks:**
- The owner deletes the scratch branch `scratch/0019-red-check` on github.com (chats cannot).
- Not covered by the Windows job: the installer's own Blender **download** (BITS / web request) –
  the job puts the cached zip next to Install.bat, the same route as the manual "Plan B". Also no
  real GUI start of the Desktop shortcut (the self-test's "App start" check covers loading the
  app template in the background).
- The GitHub run page shows the self-test report, screenshots and logs as downloadable files
  (14 days); chats only see what the logs print.
- Branch caches: a new branch's first run downloads Blender again (~1 min) until `main` has a run.
- From the review, not done (small): pushes to a branch with an open pull request run twice;
  the Linux Blender checksum is read from blender.org instead of being pinned; actions are
  pinned by version tag, not by commit.
