# 0019 – Automatic tests on GitHub, including a Windows install

**Who:** worker · **Status:** running · **Branch:** `task/0019-github-tests`
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

- [ ] Both jobs run green on `main`; a deliberately broken test on a scratch branch turns the run
      red (then delete the branch)
- [ ] Windows job: install + self-test pass; the report is attached to the run
- [ ] Run time of each job in the report; `CLAUDE.md` updated
- [ ] Report filled in; merged (no app release needed unless the installer changed)

## Not in this task

- Publishing releases and the update channel (0020, builds on this).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
