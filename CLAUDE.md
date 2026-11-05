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
- **GitHub tests every push by itself** (section 5). The worker checks the run of its branch
  before merging and the run on `main` after merging (`python3 tools/ci_status.py --wait`).
  **A red run on `main` comes first:** the chat that turned it red fixes it before anything
  else; a chat that finds `main` red at its start says so to the owner.
- A task is done when its "Done when" list is met, the tests pass (also on GitHub) and the
  **Report** in its task file is filled in (what changed, what was tested and measured, what
  is left open).
- Each new chat needs push access to the repository; the owner approves that once per chat.
- The lead keeps the progress note in the claude.ai project
  (`claude/render-app-progress.md`) up to date for the owner.

Task files: `tasks/NNNN-short-name.md`, made from `tasks/TEMPLATE.md`. `TASKS.md` is the
overview (number, title, status, who, branch).

## 3. Repository layout

```
fresing_render/            the Blender extension (Python package)
  core/                    no Blender: fasteners (DIN/ISO names), rules, RAL table, materials, size presets, templates,
                           surroundings.py (layouts of the sea, deck, quay, halls; props for scale)
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
    surroundings.py        surroundings and props: meshes, procedural materials (hall cut-away), sea waves, photo ground
    queue.py               render queue: background Blender runs queue_runner.py
    project_lock.py        "in use by" lock for shared projects
    ops_*.py               operators (ops_surroundings.py: props, put on floor);  ui.py ui_motion.py  side panel (1-7)
    files.py               open a file / show it in Explorer
    updates.py             in-app updates: start-up check, "Update available" panel, Update now, template refresh
  core/updates.py          versions, update listing (index.json), changelog.json, checked downloads (no Blender)
  update_helper.py         installs a downloaded update while Blender is closed, starts the app again
  queue_runner.py          runs queued renders inside a background Blender
  selftest.py              installation self-test (report on the Desktop)
  blender_manifest.toml    extension manifest (version, bundled wheels)
app_template/fresing_render/   app template: layout, units, switches the extension on
installer/                 Install.bat / Install-FresingRender.ps1 (Windows, no admin rights, portable Blender)
tools/                     build_release.py, release_tools.py (release job), test-model makers, real-app tests,
                           screenshot tool, ci_*.py / ci_windows_install.ps1 (automatic tests),
                           ci_update_test.py + update_test_blender.py (in-app update), requirements-dev.txt
tests/                     pytest suite (pure Python + Blender as a Python module)
.github/workflows/tests.yml  automatic tests on GitHub (section 5)
docs/                      README-install.txt (shipped to the owner), DEVELOPMENT.md, UPDATES.md (how updates work),
                           USER-GUIDE.md (+ img/: the user guide), TOOLTIPS-TODO.md (tooltips still to do),
                           SURROUNDINGS.md (surroundings, props, free 360° photos and how to add them)
```

`docs/DEVELOPMENT.md` explains how an import works and has measured timings.

## 4. Setting up a fresh chat machine (Linux)

The chat machine is empty at the start. Python 3.13 is there; pip works; most other websites
are blocked.

```bash
git clone https://github.com/smholte/CAD-render-animation fresing-render
python3.13 -m venv ~/venv
~/venv/bin/pip install -r fresing-render/tools/requirements-dev.txt     # pinned versions
cd fresing-render && ~/venv/bin/python -m pytest tests/ -q          # about 6 minutes, all must pass
```

Real-app tests also need the real Blender program (Linux build of 5.2.3,
`blender-5.2.3-linux-x64.tar.xz` from download.blender.org; if the download is blocked,
say so and run the pytest suite only) and `xvfb-run` + ImageMagick (`import`, `convert`).
GitHub runs all of them at every push anyway (section 5), so a chat that cannot run them
locally pushes its branch and reads the run.

## 5. Tests – what to run when

| What | Command | When |
| --- | --- | --- |
| Full suite (1,360+ tests) | `~/venv/bin/python -m pytest tests/ -q` | every change |
| Packaged install + self-test (Linux build of the zip) | `FRESING_SELFTEST_NO_GPU=1 BLENDER_USER_RESOURCES=/tmp/fr_user python tools/test_install_linux.py <linux wheels dir>` | packaging, importer, self-test changes |
| Real app, simulated clicks + accented paths + in-app update (installs the extension and app template into a fresh settings folder itself) | `python3 tools/ci_real_app.py --blender <blender> --wheels <linux wheels dir> --out <dir>` (some: `--only ui1,surroundings,update`; `UITEST_QUICK=1` skips ui1's renders) | UI, operators, before a release |
| In-app update against the real GitHub release (check + download) | `python3 tools/ci_update_test.py --github --expect <version> --blender <blender> --wheels <dir> --out <dir>` | after a release |
| Side-panel screenshots | `tools/ui_screens.py` (see its docstring) | every UI change: look at the result |
| **All of the above except the screenshots, plus a Windows install** | automatic on GitHub at every push | read the run: below |
| User guide pictures | `tools/guide_screens.py` (modes panels / window / render, see its docstring) | your panels changed: replace their pictures in `docs/img/` |
| User guide page | `~/venv/bin/python tools/build_guide.py`, open `dist/guide/user_guide.html` | guide or pictures changed |
| Tooltip check | `~/venv/bin/python tools/tooltip_report.py` (`--all`, `--markdown`) | buttons or settings added or changed |
| Help menu opens the guide (real app, guide inside the installed extension) | `xvfb-run -a -s "-screen 0 1920x1200x24" blender -p 0 0 1920 1200 --app-template fresing_render --enable-event-simulate --python tools/guide_test_app.py` | app template, packaging |

Linux wheels for the packaged test: `pip download cadquery-ocp-novtk==8.0.1.1.0
cadquery-ocp-proxy==8.0.1.1.0 --no-deps --only-binary=:all: --platform manylinux_2_28_x86_64
--python-version 3.13 -d <dir>`.

### Automatic tests on GitHub

`.github/workflows/tests.yml` runs at every push (any branch) and pull request – except a push that
changes only the task list (`TASKS.md`, `tasks/`): that starts no run, and `ci_status.py` says so –, on GitHub's
free runners (4 cores, no graphics card). A newer push to the same branch cancels the older
run; runs on `main` always finish. Four test jobs; the whole run takes about 12 minutes (measured 5 Nov
2026). On `main` with a new version, three release jobs follow (below):

| Job | What it does | Time |
| --- | --- | --- |
| Linux - test suite + packaged self-test | pytest (all tests), then `test_install_linux.py` | 9.2 min (pytest 6.3) |
| Linux - real app (simulated clicks) | `tools/ci_real_app.py`: `ui_test_app.py`, `ui_test_app2.py`, `ui_test_faces.py`, `ui_test_surroundings.py`, `ui_test_rule_sets.py`, `paths_test_blender.py`, `ci_update_test.py --gui` on Blender 5.2.3 under xvfb; each test must report at least its number of checks (`MIN_CHECKS`: raise it when you add checks) | 11.4 min (ui1 5.0, ui2 0.7, faces 0.2, surroundings 3.6, paths 1.4; 5 Nov 2026) + update 0.5 |
| Build the Windows installer zip | `tools/build_release.py`, as for a release, plus an "old" build (`--version-as 0.0.1 --template-from tests/data/old_app_template`); installer, old installer and the update listing go to the Windows job | 0.5 min |
| Windows - install + self-test | `tools/ci_windows_install.ps1`: the old build installed with `Install.bat -UpdateUrl` (local listing in a folder with a space and an accent) updates itself in the app (`update_test_blender.py`: check, Update now, helper, restart); then the current zip unzipped into a folder with a space and an accent, `LOCALAPPDATA` with a space and an accent, `Install.bat` unattended (install, then repair) over it, checks files and shortcuts, runs the self-test from its Start-menu shortcut, then `Uninstall.bat` | 3-4 min |
| Publish the release (only `main` with a new version, all tests green) | `tools/release_tools.py`: tag `v<version>`, installer, extension, `index.json` (full download addresses), `changelog.json`, CHANGELOG section as text | < 1 min |
| Windows - an installed old version updates itself from the release | the old build, update address GitHub (default), must find and install the new release | 2-3 min |
| Delete the rehearsal pre-release | only after a `[release rehearsal]` branch push (docs/UPDATES.md) | < 1 min |

Blender is downloaded once per version (checked against its SHA-256) and kept in GitHub's
cache; the version comes from `installer/Install-FresingRender.ps1`, so raising it there is
enough. On the runners `FRESING_SELFTEST_NO_GPU=1` turns the two graphics-card checks of the
self-test into "skipped: no graphics card"; every other self-test line must be OK
(`tools/ci_check_selftest.py`).

**Reading the results from a chat** (the `gh` command works through the chat's proxy):

```bash
python3 tools/ci_status.py --wait              # run of the current commit (HEAD); waits until it is done
python3 tools/ci_status.py --branch main --wait  # run of the newest commit on main
python3 tools/ci_status.py --run <id> --log "Windows"   # whole log of the jobs matching "Windows"
```

It only shows the run of exactly that commit (never an older one), lists every job with its
time and, for a failed job, the failing step, the error lines and the log up to the error. Each job also prints its verdict as a table (which test, which self-test line)
in the log and on the run page ("Summary"). The chats can read runs, jobs, logs and
annotations through the GitHub API, but **cannot download the run's files** (artifacts:
screenshots, self-test reports, logs) - their storage is blocked by the proxy; the owner can
download them on the run page. A chat may push files under `.github/workflows/`, but cannot
delete branches on GitHub (refused, like tag pushes): name leftover branches in the report so
the owner can delete them on github.com (Code → branches → bin icon).

Big test model: the "EGR line" STEP (78 MB, 2,789 placed / 584 unique parts, 4.2 M triangles)
is a public model from GrabCAD, **not** the owner's or his clients' design. It is not in the
repository (its maker's rights: do not redistribute it). Ask the owner to attach it when a task
needs it. Its part names follow its maker's conventions, not the owner's: for sorting coverage
on the owner's own naming, ask him for one of his own models (attached in the chat only). Small test models are in `tests/data/` (made by `tools/make_test_step.py` and
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
- **Tooltips:** every button and setting has one (operator docstring/`description`, property
  `description`): first what it does, then how to use it or what happens next, in plain words
  ("Puts the ticked parts in a new group named after your search. Then pick its material
  below."). Style guide: the comment at the top of `docs/USER-GUIDE.md`. Check with
  `tools/tooltip_report.py`; `docs/TOOLTIPS-TODO.md` lists what each lane still has to do, with
  suggested texts (delete your rows when done).
- **User guide:** a task that changes what the owner sees updates its chapter of
  `docs/USER-GUIDE.md` in the same commit, and replaces the pictures of its panels
  (`tools/guide_screens.py`, test crane only). The guide is built into the release by
  `tools/build_release.py` (needs `markdown`); it opens from Help > Fresing Render user guide.
- Commit messages say what changed and why, in plain words, and end with the attribution
  lines the chat's instructions give.

## 7. Release procedure (the worker chat that finishes a task)

GitHub publishes the release itself (task 0020, `docs/UPDATES.md`): the worker bumps the version and
merges; every installed app (0.2.15 and newer) then offers the update at its next start.

0. `git pull` first: another chat may have released in the meantime; take the next free
   version number.
1. Raise the version in `fresing_render/__init__.py` **and** `fresing_render/blender_manifest.toml`.
2. Add the version to `CHANGELOG.md` at the top (plain words, for the owner): the app shows this text
   under "What's new", the release page too. Heading: `## <version> – <date> – <short title>`. No
   "Commit" line needed any more (the release page shows the commit).
3. Full test suite; real-app tests for UI changes; packaged self-test for importer/packaging
   changes. The GitHub run of the branch must be green (section 5).
4. Merge into `main` and push. GitHub tests `main` once more, then publishes the release and checks on
   Windows that an installed old version updates itself to it. Wait for it:
   `python3 tools/ci_status.py --branch main --wait` – every job green, including "Publish the
   release" and "Windows - an installed old version updates itself from the release". When the release
   job did not run (it only runs with all tests green), fix `main` first.
5. Give the owner the release link (`https://github.com/smholte/CAD-render-animation/releases/tag/v<version>`)
   and, as before, the installer zip in the chat: build it locally with
   `~/venv/bin/python tools/build_release.py` (same files as the release; or download it from the
   release page) and send `dist/FresingRender-<version>-windows.zip` with short steps: for installed
   PCs "start the app, click **Update now**", for new PCs "unzip, Install.bat".
6. Add a short entry to the project progress note `claude/render-app-progress.md` (if the chat cannot
   reach it, say so: the lead will add it).

To try the release path before merging (only when the release machinery itself changed): push the
branch with `[release rehearsal]` in the newest commit message; GitHub makes a pre-release, checks it
and deletes it again. A release that went wrong: the owner can delete it on github.com (Releases →
the release → Delete); the next run on `main` publishes it again.

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
- Part-library keywords are whole words in English, Dutch and German at once: "LINKS" is "left"
  in German and Dutch ("Abdeckung links"), "PALLET" in an automation line is a workpiece carrier,
  not wood. Check a new keyword against all three languages and the example lists in
  `tests/test_part_types.py`; measure on the EGR model which parts change group.
- OpenCascade orders some internal maps by memory address: meshing a binary copy of a part
  can give another triangle order (same triangles). Compare meshes by counts and positions,
  not byte for byte.
- Operator tooltips: `bpy.types.X_OT_y.bl_rna.description` is empty; ask
  `bpy.ops.x.y.get_rna_type().description`. A property group that defines its own `name` has two
  `name` properties in `bl_rna.properties`; the UI uses its own (the last one).
- Real-app screenshots: switch `preferences.system.use_region_overlap` off, or the side panel is
  see-through. A panel's open/closed state is kept per panel name once drawn; to picture it in
  another state, register a copy under a new name (`tools/guide_screens.py` does this).
- Blender's own Python has numpy but no Pillow: real-app tools crop and save pictures with numpy
  and ImageMagick.
- Real-app tests: `event_simulate` only queues events. An Esc sent in the same step as a modal
  operator reaches that operator (it cancelled the import); give it a step of its own. A click
  "somewhere in the side panel" lands on whatever button the layout puts there (an open
  drop-down then eats the next click): click a fixed spot such as a section's title row.
  These only showed up on GitHub because its runners start with an empty import cache.
- Windows PowerShell 5.1 started from PowerShell 7 inherits PowerShell 7's `PSModulePath` and can
  load the wrong modules: clear it for the child (`tools/ci_windows_install.ps1` does).
- GitHub caches made on a branch are only seen by that branch; caches made on `main` are seen
  by all branches. The first run of a new branch may download Blender again (about 1 minute).
- Python references to items of a collection property (`scene.fresing.joints[i]`) become
  invalid when that collection grows or shrinks: keep names (or the joint's Objects) and look
  the item up again; compare items with `==` or by name, never with `is`.
- A joint axis made from a point + direction leaves the arrow's turn about its own axis open
  (and unstable for a vertical axis). Joints riding on it (stacks, task 0011) depend on that
  turn: when rebuilding, pass the whole frame matrix (`joints.create(frame_world=...)`).
- A flat panel's visible side follows the right-hand rule of its corners: hall walls were drawn
  facing out, so a hall looked solid grey from outside and see-through from inside. Test the
  normals (`tests/test_surroundings.py`), and always look at renders from several camera spots.
- Cycles stops a ray after 8 transparent steps by default and shows black: see-through walls
  and cut-away beams need more (`scene.cycles.transparent_max_bounces`).
- 16-bit PNGs load as linear values in Blender, 8-bit PNGs as screen values: compare pictures
  of the same bit depth in tests.
- An animation without steps lasts 1 s (26 frames): a test video needs one short step.
- In-app updates: a panel's place in the side panel follows `bl_order` and, for equal numbers, the order
  of registration; a negative `bl_order` does not put it on top (the update notice is registered first).
- `wm.quit_blender` in a background Blender only closes it when the running script ends.
- An extension that reaches the network declares `network` under `[permissions]` in its manifest and
  checks `bpy.app.online_access` first.
- Blender resolves a relative `archive_url` in index.json against the address it asked (not the one
  GitHub redirected to); the release job writes full addresses so the listing stays right.
