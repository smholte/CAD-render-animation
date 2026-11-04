# CLAUDE.md – how the AI works on Fresing Render

Read this first in every chat that works on this repository. Then read `TASKS.md`.
Keep this file current: when a rule or a way of working changes, change it here in the
same commit.

## 1. The project and the owner

**Fresing Render** is an in-house app for photo-realistic renders and animations of large
STEP assemblies (offshore wind / cable-laying machines, CNC mills; up to thousands of parts).
It is a Blender 5.2.3 LTS extension plus an app template ("Fresing Render" on the Desktop),
rendered with Cycles. Windows only for users; development and tests run on Linux.

**Owner: Sebastian (Fresing).** Designs machines in Autodesk Inventor Professional 2027 and
Fusion. Not a programmer. He tests on his own PC: Windows 11, AMD 24 cores,
NVIDIA RTX 3090. No chat can use a graphics card or Windows; he is the only tester for both.

How to work with him:
- Plain language, short. Results first, no account of the effort. No code unless he asks.
- Anything he has to do on his PC: numbered steps, click by click, with the exact names of
  buttons and menus. Say what he should see when it worked.
- Say plainly what was measured where ("on the 2-core test machine", "on your PC") and what
  is an expectation. Never present a guess as a measurement.
- He decides priorities, tests on his PC and approves releases.

## 2. How the work is organised

**One lead chat** (the chat in the claude.ai project "STEP rendering App" that the owner
works with) plans, writes task briefs, answers the owner's questions, keeps `TASKS.md` and the
progress note current, and reads the reports and changes of finished tasks.
**The lead does not build or test** (owner's rule, 4 Nov 2026): anything expected to take more
than about 5 minutes of work goes to a worker chat – features, fixes, tests, measurements,
releases. Planning and writing briefs stay with the lead, also when they take longer. Small
edits to `CLAUDE.md`, `TASKS.md` and task files are fine for the lead.

**Worker chats** take one task each (a feature, a fix, benchmarks, an independent review). The
owner starts them by hand. **The lead tells the owner when a task should go to another chat
and gives the exact sentence to paste**, for example:

> Read CLAUDE.md and TASKS.md in github.com/smholte/CAD-render-animation and do task 0007.

**Chats share nothing but GitHub.** No shared files, no reliable messages between chats.
Everything another chat needs must be in the repository: this file, `TASKS.md`, the task
file, the code.

Rules:
- `main` is always the tested, working version. Installers are built only from `main`.
- Every task gets its own branch `task/NNNN-short-name`. **The worker finishes the task
  completely:** all tests pass, report filled in, then it updates its branch to the newest
  `main` (tests again if `main` moved), merges into `main`, pushes, and does the release steps
  (section 7) so the owner gets the installer in that chat. Exception: a task file that says
  "lead review before merge" – then the worker stops at a pushed branch and the lead decides.
- The lead reads each finished task's report and changes afterwards and writes a follow-up
  task if something is off. Lead edits to documents may go to `main` directly.
- Two chats never work on the same area at the same time (for example two chats both in
  `blender/ui*.py`). `TASKS.md` groups the tasks in **lanes**: one running task per lane.
- A worker that starts a task sets it to "running" in `TASKS.md` and pushes that change to
  `main` right away. When it finishes, it moves the task to "Done" and sets the next task in
  its lane to "open – can start", so the owner can start the next chat.
- A task is done when its "Done when" list is met, the tests pass and the **Report** in its
  task file is filled in (what changed, what was tested and measured, what is left open).
- Each new chat needs push access to the repository; the owner approves that once per chat.
- The lead keeps the progress note in the claude.ai project
  (`claude/render-app-progress.md`) up to date for the owner.

Task files: `tasks/NNNN-short-name.md`, made from `tasks/TEMPLATE.md`. `TASKS.md` is the
overview (number, title, status, who, branch).

## 3. Repository layout

```
fresing_render/            the Blender extension (Python package)
  core/                    no Blender: fasteners (DIN/ISO names), rules, RAL table, materials, size presets, templates
  importer/                STEP reader (OpenCascade via OCP) and the runner that starts it as a subprocess
    step_reader.py         reads STEP -> tree.json + meshes.npz cache; meshes on all cores with helper processes
    runner.py              ImportJob: starts the reader with Blender's own Python, follows its progress
  blender/                 bpy code
    build.py               builds objects from the cache (one mesh per unique part)
    logic.py               sorting rules, groups, structure, exclusion
    joints.py states.py    joints (drivers), poses, visibility sets, saved scenes
    animation.py           animation steps baked to keyframes
    reimport.py            model update to a new STEP revision, keeping all work
    render.py world.py cameras.py materials.py
    queue.py               render queue: background Blender runs queue_runner.py
    project_lock.py        "in use by" lock for shared projects
    ops_*.py               operators;  ui.py ui_motion.py  side panel (sections 1-7)
    files.py               open a file / show it in Explorer
  queue_runner.py          runs queued renders inside a background Blender
  selftest.py              installation self-test (report on the Desktop)
  blender_manifest.toml    extension manifest (version, bundled wheels)
app_template/fresing_render/   app template: layout, units, switches the extension on
installer/                 Install.bat / Install-FresingRender.ps1 (Windows, no admin rights, portable Blender)
tools/                     build_release.py, test-model makers, real-app tests, screenshot tool
tests/                     pytest suite (pure Python + Blender as a Python module)
docs/                      README-install.txt (shipped to the owner), DEVELOPMENT.md, UPDATES.md
```

`docs/DEVELOPMENT.md` explains how an import works and has measured timings.

## 4. Setting up a fresh chat machine (Linux)

The chat machine is empty at the start. Python 3.13 is there; pip works; most other websites
are blocked.

```bash
git clone https://github.com/smholte/CAD-render-animation fresing-render
python3.13 -m venv ~/venv
~/venv/bin/pip install bpy==5.2.3 cadquery-ocp==8.0.1.1.0 numpy pillow pytest
cd fresing-render && ~/venv/bin/python -m pytest tests/ -q          # about 5 minutes, all must pass
```

Real-app tests also need the real Blender program (Linux build of 5.2.3,
`blender-5.2.3-linux-x64.tar.xz` from download.blender.org; if the download is blocked,
say so and run the pytest suite only) and `xvfb-run` + ImageMagick (`import`, `convert`).

## 5. Tests – what to run when

| What | Command | When |
| --- | --- | --- |
| Full suite (108+ tests) | `~/venv/bin/python -m pytest tests/ -q` | every change |
| Packaged install + self-test (Linux build of the zip) | `BLENDER_USER_RESOURCES=/tmp/fr_user python tools/test_install_linux.py <linux wheels dir>` | packaging, importer, self-test changes |
| Real app, simulated clicks (install the extension and app template first, see the script's docstring) | `xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate --python tools/ui_test_app.py` (and `ui_test_app2.py`, `paths_test_blender.py`) | UI, operators, before a release |
| Side-panel screenshots | `tools/ui_screens.py` (see its docstring) | every UI change: look at the result |

Linux wheels for the packaged test: `pip download cadquery-ocp-novtk==8.0.1.1.0
cadquery-ocp-proxy==8.0.1.1.0 --no-deps --only-binary=:all: --platform manylinux_2_28_x86_64
--python-version 3.13 -d <dir>`.

Big test model: the owner's "EGR.Cooler.Insp.Line-872" STEP (78 MB, 2,789 placed / 584 unique
parts, 4.2 M triangles) is **not** in the repository. Ask the owner to attach it when a task
needs it. Small test models are in `tests/data/` (made by `tools/make_test_step.py` and
`tools/make_test_crane.py`).

## 6. Rules for changes

- **The repository is public.** Never commit the owner's STEP files, part-name lists, renders
  or screenshots of his (or his clients') machines. Generic examples only; numbers in reports.
- New behaviour gets a test. A bug fix gets a test that failed before.
- Speed claims are measured, with the model and machine named. Before/after numbers in the
  task report.
- **Windows-only code** (ctypes calls, subprocess flags, PowerShell installer, paths) cannot
  run here. Have it reviewed independently (a helper agent or review chat that did not write
  it) before a release, and add a self-test line when the owner's PC can confirm it.
- Do not change the cache format or saved-project data silently: bump `CACHE_VERSION` in
  `importer/step_reader.py` when the cache changes; old projects must keep opening.
- UI follows the layout rules at the top of `blender/ui.py`: steps top to bottom, choices
  above their button, the main button big and blue (`primary()`), details of the selected
  list item under the list, no cut-off labels at the default side-panel width, rarely used
  settings in folds, a state in every panel header. Check with `tools/ui_screens.py`.
- Commit messages say what changed and why, in plain words, and end with the attribution
  lines the chat's instructions give.

## 7. Release procedure (the worker chat that finishes a task)

0. `git pull` first: another chat may have released in the meantime; take the next free
   version number.
1. Raise the version in `fresing_render/__init__.py` **and** `fresing_render/blender_manifest.toml`.
2. Add the version to `CHANGELOG.md` (plain words, for the owner).
3. Full test suite; real-app tests for UI changes; packaged self-test for importer/packaging changes.
4. `~/venv/bin/python tools/build_release.py` (downloads the Windows wheels into `wheels/` the
   first time) -> `dist/FresingRender-<version>-windows.zip`.
5. Commit, push `main`, and write the commit hash under the version in `CHANGELOG.md`.
   (Tag pushes are refused by the chats' git policy; the owner can add tags or GitHub
   Releases on github.com if he wants them.)
6. Send the owner the installer zip with short install/test steps (numbered, click by click);
   add a short entry to the project progress note `claude/render-app-progress.md` (if the chat
   cannot reach it, say so: the lead will add it).

## 8. Things learned the hard way

- PowerShell: `$Name:` inside a double-quoted here-string is a scope-qualified variable and a
  parse error -> write `${Name}`. Every installer before 0.2.2 failed on this.
- `.bat` / `.ps1` need CRLF line endings (`.gitattributes`).
- Child processes on Windows: `CREATE_NO_WINDOW`, or every one pops up a console window.
  Python's multiprocessing cannot pass that flag, so the STEP reader starts its own helpers.
- Blender keeps a separate add-on list per app template: the template switches the extension
  on in a `load_post` handler.
- Assigning a render setting to the value it already has stops a running viewport preview:
  set only on change (`render._set`).
- `layout.panel()` folds need the full panel width (not inside a box).
- Cycles denoises on the processor by default (`denoising_use_gpu` is False): set it.
- Joint values: always through `joints.set_value` (drivers need the update tag).
- float32 rounding made ~2,000 parts look "moved" after an import: compare with `MOVE_EPS`.
- `logic.Tree(scene)` walks the whole scene: make it once per operation, never inside a loop
  (one per tree row cost 4.6 s on the EGR model). In `UIList.filter_items` and other code that
  runs at every redraw, read collection columns with `foreach_get`, not row by row.
- OpenCascade orders some internal maps by memory address: meshing a binary copy of a part
  can give another triangle order (same triangles). Compare meshes by counts and positions,
  not byte for byte.
