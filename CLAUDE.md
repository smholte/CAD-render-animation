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
NVIDIA RTX 3090. No chat and no GitHub test machine has a graphics card. GitHub tests the
Windows install, the self-test and the in-app update on a Windows machine at every push
(section 5); working in the app on Windows and everything on the graphics card (GPU renders,
render speed) only he can test, on his PC.

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

**Worker chats** take one task each (a feature, a fix, benchmarks, the user guide, an independent
review). The owner starts them by hand. **The lead tells the owner when a task should go to another
chat and gives the exact sentence to paste, with where, which model and which effort**, for example:

> **Claude Code on the web · Opus · effort High**
> Read CLAUDE.md and TASKS.md in github.com/smholte/CAD-render-animation and do task 0013.

**Where the chats run** (owner's decision, 5 Nov 2026):
- **Lead:** a chat in the claude.ai project "STEP rendering App" – it keeps the progress note there
  and talks with the owner.
- **Workers:** Claude Code on the web (claude.ai/code), one session per task, repository
  `smholte/CAD-render-animation`. Also for the user guide, tooltips and texts: they live in the
  repository, their pictures are made with the real Blender and tests check them. Why: the
  set-up can be stored once and reused by every session (section 4, task 0031), sessions have
  4 cores (the chats had 2), and GitHub is connected once instead of a push approval per chat.
  It is the same usage limit as the chats – the place saves nothing by itself.
  Tasks that already run in a chat finish there.
- **Exception – tasks where the owner attaches his own project file** (big `.blend`, ~150 MB; 0037, 0048): a new
  chat in the claude.ai project "STEP rendering App" (Cowork). The file comes in and goes back as an attachment
  there; set-up "by hand" (section 4, bpy as a module). The task file says so in its header.
- The owner sets model and effort before the first message (in Claude Code: send `/model opus`
  or `/model sonnet`, then `/effort high`, `/effort medium` or `/effort low`).

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
- Each worker needs push access: in Claude Code on the web through GitHub, connected once at
  claude.ai/code; in a chat the owner approves it once per chat.
- The lead keeps the progress note in the claude.ai project
  (`claude/render-app-progress.md`) up to date for the owner.

Task files: `tasks/NNNN-short-name.md`, made from `tasks/TEMPLATE.md`. `TASKS.md` is the
overview (number, title, status, who, branch).

### Subagents in a worker session (owner's request, 12 Nov 2026)

Big tasks (above all the Fable tasks) may split their work over **subagents** (Claude Code's Agent tool). The
worker session stays the one in charge: it reads the brief, designs, merges, tests, pushes and releases.
- **Interfaces first.** Before spawning writers, the worker fixes the split: which files each subagent owns, the
  functions and data between them (names, arguments, units). Write that plan in the task file under "Design" and
  commit it on the branch – it is the subagents' brief and the record if the session has to be continued.
- **One owner per file.** Two subagents never edit the same file. Parallel writers run with `isolation: "worktree"`;
  the worker merges their work. Shared files (`props.py`, `ui.py`, `reimport.py`, `animation.py`, `handlers.py`, the
  tour, the PC check, the guide, `TASKS.md`, version files, CHANGELOG) stay with the worker.
- **Good jobs for a subagent:** reading and mapping code (Explore, read-only); a self-contained module with its own
  tests (a pure-Python solver in `core/`); test-model makers; **independent tests written from the brief by an
  agent that did not write the code**; the independent review (section 6); guide pictures and texts at the end.
- **Subagents never push, merge, bump the version or touch `TASKS.md`**; only the worker runs the GitHub cycle.
- **At most 3 at a time** (the web machine has 4 cores; real-Blender tests and renders one at a time).
- **Model:** a subagent runs on the session's model unless told otherwise; routine pieces (tests from a clear spec,
  guide text, tooltips) may go to `sonnet` to save usage.
- **Never `git add -A` while worktree subagents exist** without `.claude/worktrees/` in `.git/info/exclude`: their
  folders are added as links (happened in task 0061).
- **A worktree subagent may start from an older commit** than the worker's branch (task 0078: all of them started
  at the session's first commit, without the design). The brief's first line: "`git merge <the worker's branch>` in
  your worktree first". Commit the brief (the Design) before spawning.
- **Give an agent that did not write the code the job of breaking it** (task 0078: the independent tester found that the
  task's own test rope could not be read, and ten more faults, while all 77 of the author's tests passed). Send its
  findings back to the author (`SendMessage` resumes an agent with its context) rather than fixing them yourself.
- **Say in the report** which subagents ran, what each did and which work was re-done after merging.

### Saving usage (owner's request, 5 Nov 2026)

The owner's AI usage is limited; every chat works economically:
- **Tests:** locally run only the tests of what you changed (`pytest tests/test_<area>.py`, the
  one real-app test of your panel). GitHub runs the full suite, all real-app tests and the
  Windows install at every push – read its result instead of repeating it locally.
- **Pictures cost a lot:** look only at the screenshots of the panel you changed, cropped small.
- **Helper agents** (independent reviews, independent test lists) only for Windows-only code and
  for risky changes; say in the report when one was skipped.
- **Update your branch to `main` once**, right before merging – not after every other release.

### Working efficiently with the automatic tests (owner's request, 6 Nov 2026)

GitHub's minutes are free (public repository); the owner's *waiting time* and AI usage are not. Since task 0036
a full run takes about 13 minutes (parallel jobs; a docs-only run about 2), but a task is often run several times. So:
- **Take the version number last.** Do not bump the version, write the CHANGELOG heading or touch
  `MIN_*` counts until the branch is finished. Then `git fetch`, merge `main` **once**, take the next free
  version after what is on `main`/released, and push. Other tasks finish in the same hours: a clash costs a
  whole extra run – the `precheck` job catches it in about a minute ("someone took your version number: merge
  main and renumber to 0.2.NN") before any test starts.
- **Push when the work is ready, not after every edit.** A newer push to the same branch cancels the running
  run. Run the tests of your area locally first; push once with code, tests and guide together. Reports,
  `TASKS.md` and `tasks/` files go in a **separate last push** that touches only those (no run starts).
- **Documentation-only pushes are cheap.** A push that changes only `docs/`, `CHANGELOG.md`, `CLAUDE.md`,
  `README.md`, `TASKS.md`, `tasks/` and at most the version line of the two version files, on top of a commit
  whose run is green, runs mode **docs**: build, tooltip check, guide and their tests, a few minutes.
- **Use the waiting time.** While the run goes: write the report, check the guide, prepare the next step. Do
  not poll in a loop; use `python3 tools/ci_status.py --wait` once and read the result.
- **Merge the way that lets GitHub reuse the run.** Merge `main` into your branch, wait for green on *that*
  commit, then fast-forward `main` to exactly that commit (`git push origin HEAD:main`) – no new merge commit,
  no changes after the green run. GitHub then sees that this git tree already ran green (mode **reuse**), runs
  no tests again, and publishes the release with that run's installer in a few minutes. If `main` moved
  meanwhile, the fast-forward is refused: merge once more and accept one more run.
- **Several tasks at the same time:** the one that finishes first merges first; the others take the next
  version and merge `main` then. A lead sentence for a new task never fixes a version number in advance.
- **A red run:** read the failing step with `ci_status.py` (do not re-run blindly), fix, push once. A run that
  fails in `precheck` is a version/changelog/list problem (its message says what to change): fix that and push.
- **A new test:** a new `tests/test_*.py` file joins a pytest group by itself; a new real-app test goes into
  `TESTS`, `MIN_CHECKS` **and** the lightest group in `GROUPS` (`tools/ci_real_app.py`) – the precheck fails
  otherwise. After a big change in test times: `python3 tools/ci_status.py --run <green run> --record` and
  commit `tools/ci_times.json` (it balances the pytest groups).
- **Say in the report** how many runs the task needed and why (version clash, real failure).

- **No installer per task:** bump the version, write the changelog, merge, check the GitHub run.
  Build and send the installer only when the owner asks for one (once task 0020 is done, GitHub
  publishes releases by itself).
- Read only the files and earlier reports your task needs; keep reports short (numbers, open points).
- Small follow-ups go into the next task of the same lane, not into a new chat.
- **Long chats cost the most** (every message carries the whole conversation). **The lead tells
  the owner when to start a new lead chat** (owner's request, 5 Nov 2026), unasked and every time:
  when its conversation has grown long – large documents or many files read, many tool results,
  or about 15–20 exchanges. First it brings `TASKS.md` and the progress note up to date, then it
  gives this sentence for the new chat in the project:
  > You are the lead chat for Fresing Render. Read CLAUDE.md and TASKS.md in
  > github.com/smholte/CAD-render-animation and the project note claude/render-app-progress.md.
  > You plan, write task briefs and review finished tasks; you don't build or test.

  A worker whose session grows very long before its task is done pushes its branch, writes the
  state in its task file's report and tells the owner to continue in a new session with
  "… and continue task NNNN from its branch".
- **The lead picks model, effort and place for every task** (owner's rules, 5 Nov 2026) and writes
  them in the task file's header (`**Model:** Opus · effort High`), in the Model column of
  `TASKS.md` and above the sentence it gives the owner. Place: workers in Claude Code on the web,
  the lead in the project chat (section 2).
  - **Model.** **Sonnet** (uses less of the owner's usage) for routine work: tooltips, texts and
    the user guide, data and word lists, small fixes, extra tests, one-panel UI changes along an
    existing pattern. **Opus** for hard work: new algorithms and geometry (joints, cylinders,
    linkages, G-code, milling, chips), several modules at once, Windows-only code, performance
    work, anything where a wrong design is expensive.
  - **Effort** (higher effort = more thorough, slower, more usage). **High:** new algorithms and
    geometry. **Medium:** features along an existing pattern, small fixes, extra tests, the lead's
    own work (High only when it writes the brief of a hard task). **Low:** texts, tooltips, the user
    guide, data and word lists. Extra high and Max are not used by default.
  - **Stuck** (the same tests failing again and again, going in circles): first one step more
    effort; still stuck: switch Sonnet to Opus. When unsure at the start: the lower choice.

## 3. Repository layout

```
fresing_render/            the Blender extension (Python package)
  core/                    no Blender: fasteners (DIN/ISO names), rules, RAL table, materials, size presets, templates,
                           surroundings.py (layouts of the sea, deck, quay, halls; props for scale),
                           studio.py (light looks, light in words, blur and turntable numbers),
                           machining.py (milling: bit shapes, straight segments, Manifold booleans, tiles),
                           decal_geometry.py (where a decal lies: flat or wrapped round a cylinder),
                           decal_art.py (text, CE mark, warning signs, arrows, type plate drawn as masks),
                           waycover.py (way-cover shares: moving sections k/N, or housing counted 0 … 1),
                           chips.py (chip presets per material x bit, chip shapes, height fields, chip flight),
                           air.py (air blast, task 0039: the jet and the wall jet where it meets a surface; the chips
                           in chips.py feel it, lying chips are picked up again as copies),
                           cylinders.py (cylinder geometry: stroke <-> arm angle, travel read from the parts),
                           callouts.py (labels with lines: where boxes go, fades, the line; picture cards; music plan),
                           brand.py (brand kits, title/end cards, captions, time line of a finished video),
                           linkages.py (planar mechanisms: pins, tracks, sliders; exact steps + Newton, the
                           assembly mode kept by walking; pins from shared round faces; scissor layout)
                           gcode.py (G-code reader, LinuxCNC/RS274NGC: moves in machine coordinates, arcs,
                           cycles, o-words, parameters, Fusion tool comments; rotary axes A/B/C in degrees with
                           G93 and LinuxCNC's mixed feed rule, task 0066; Schedule = program time -> video),
                           clash.py (clash check, task 0065: rigid bodies from the motion, boxes, screw motion between
                           frames, tool zones, rows and texts),
                           vessel_motion.py (task 0085: heave / pitch / roll from the sea's own waves + a long swell;
                           hull averaging, a damped roll at its natural period, scaled so each sea state has its table),
                           toolmarks.py (tool marks on cut faces, task 0061: the contract between the milled mesh and
                           the cut-face material – four per-face attributes ``fr_mk_o/d/a/p``, six kinds of marks – and
                           the formula in plain Python the tests compare a render with; strengths per material),
                           cut_normals.py (the milled mesh's corner normals in NumPy: flat faces flat, round walls smooth,
                           needle triangles take their neighbour's, a big flat face keeps its own next to small facets),
                           web3d.py (web 3D model, task 0099: the glTF 2.0 writer/reader + checks, box UVs in 0.2 m
                           tiles, welding, 16-bit points/UVs, seamless tiles, the one-file viewer page),
                           toolpath.py (the app makes the toolpath, task 0029: drop-cutter for flat/ball/bull in NumPy,
                           zigzag roughing by levels + a pass round the walls + ramps, raster finishing by scallop height,
                           greedy thinning measured square to the move, the LinuxCNC program text; mm, program coordinates)
                           flex.py (hoses and cables, task 0058: an inextensible elastic rod under its own weight, Newton
                           on the segment directions coarse to fine, exact ends / end directions / length; batched over
                           hoses and frames; ``solve_motion`` keeps one shape along an animation),
                           flex_chain.py (drag chains: pins exactly one link length apart on fixed run – bend circle – run
                           to the moving end, closed forms + a 1-D solve for the bend's place; ``fit_links`` reads pitch,
                           radius, plane and each link's place on its pins from the CAD links),
                           flex_fit.py (a tube mesh's centreline, radius, ends and end directions)
                           paths.py (cable paths, task 0078: a cable's middle line is straight runs and round arcs; the
                           tight-string solver over wheels – tangent points in closed form, alternated; `held` keeps each
                           arc in its wheel's plane; a wheel the cable leaves is `lifted` –, the same over all frames at
                           once (`solve_frames`, fixed point counts), reading a CAD cable (`centreline` for long tubes,
                           `read_cable`: arcs → WRAP on a round part / BEND, rollers it rests on → TOUCH), the seat of a
                           cable in a groove from the mesh, `is_round`, the ratio of a wheel turned by the cable)
  importer/                STEP reader (OpenCascade via OCP) and the runner that starts it as a subprocess
    step_reader.py         reads STEP -> tree.json + meshes.npz cache; meshes on all cores with helper processes;
                           facets by size (task 0074, `FACETS`): big parts capped in mm, small standard parts lighter
    runner.py              ImportJob: starts the reader with Blender's own Python, follows its progress
  blender/                 bpy code
    build.py               builds objects from the cache (one mesh per unique part)
    logic.py               sorting rules, groups, structure, exclusion
    joints.py states.py    joints (drivers), stacks, couplings and motors; poses, visibility sets, saved scenes
    cylinders.py           cylinders: barrel aims at the rod pin, rod eye on its pin (constraints), drive mode,
                           telescopic stages; ops_cylinders.py; panel 4 Motion > Cylinders in ui_motion.py
    linkages.py            mechanisms (task 0014): a frame on the base, one empty per link it moves (keys when
                           built, a depsgraph handler while posing), the input is a normal joint; ops_linkages.py;
                           panel 4 Motion > Mechanisms in ui_motion.py
    animation.py           animation steps baked to keyframes
    reimport.py            model update to a new STEP revision, keeping all work
    render.py world.py cameras.py materials.py   (cameras.py: views, blur, sharp spot, turntable camera)
    surroundings.py        surroundings and props: meshes, procedural materials (hall cut-away), sea waves, photo ground
    turntable.py           one-click turntable: camera, saved scene and animation "Turntable"
    queue.py               render queue: background Blender runs queue_runner.py; a job's paint scheme is set only in
                           the background copy (task 0074, ops_queue_schemes.py: 7 Render queue > Every paint scheme)
    project_lock.py        "in use by" lock for shared projects
    machining.py           milling: set-up, bits' path read per frame, frame handler (workpiece shows its cut)
                           Task 0061: every cutter solid has a Manifold id -> ``Timeline.moves`` (one row per straight
                           move: start, axis, feed per tooth / per turn, step-down) -> per cut triangle the move that made
                           it last -> the attributes of core/toolmarks.py written with the mesh; ``gcode.feeds`` (F and S
                           per frame, stored at Build); quick normals while the frame changes, exact ones when it stands
                           still and in renders (``refresh(quick=)``, ``make_fine``)
    toolmarks.py           the node group "FR tool marks" (shader nodes only: reads the attributes, draws the marks as a
                           lean of the normal + the anisotropic tangent; inputs Size, Strength, Pixel angle), wired into a
                           material by ``materials.build_nodes`` when its spec has ``toolmarks``
    idprops.py             store_array: arrays into ID properties safely (task 0038)
    waycover.py            way covers (task 0034): sections are slide joints that follow one axis joint with
                           k/N of its travel (coupling ratios + limits); several covers per project in
                           scene.fresing.waycovers (task 0035; the old single cover moves in at load), the last section
                           may be the carriage (no joint); ops_waycover.py, ui_waycover.py
                           (4 Motion > Way covers); core/waycover.py has the shares
    chips.py               chips: inputs from the milling set-up, catch areas (rays down), bake, two point
                           clouds + a Geometry Nodes instancer (4 Motion > Milling > Chips)
    air.py                 air blast (task 0039): the nozzle (through the spindle = the bit's path, or a part read
                           per frame by machining.sample), the air frames each G-code step writes at Build
                           (cnc["fr_air"]), "Show air" cone; settings in 4 Motion > CNC machine > Air blast
    ops_*.py               operators (ops_surroundings.py: props, put on floor; ops_scene.py: light looks, sharp
                           spot, turntable);  ui.py ui_motion.py  side panel (1-7)
                           ui_machining.py: 4 Motion > Milling (ops_machining.py)
    gcode.py               CNC machine (task 0026): X/Y/Z joints + spindle, tool, work zero (marker), bake of the
                           Run G-code program step (keys on move ends + along arcs), tool copies at M6, the
                           toolpath (Geometry Nodes tubes); ops_gcode.py; ui_gcode.py (4 Motion > CNC machine,
                           the step's settings in 6 Animation)
    rotary.py              rotary axes A/B/C (task 0066): which rotate joint is which axis, the turn back to A0 B0 C0
                           when the machine is worked out, Plain (angles only) or TCP (X/Y/Z follow the turning part:
                           centres K and directions u in machine mm), Check, the toolpath on the part; the two test
                           models' programs and set-up (test_4axis.step / test_5axis.step from tools/make_test_4axis.py,
                           make_test_5axis.py); panel 4 Motion > CNC machine > Rotary axes in ui_gcode.py
    toolchange.py          tool changes (task 0041): manual (change position, pause, the app-made gloved hand) or ATC
                           (pockets on parts, carousel joint turned the shortest way, stations worked out from the
                           pockets); pocket copies, the hand's keys, captions; core/toolchange.py plans each change
                           as timed phases (no Blender); panel 4 Motion > CNC machine > Tool changes
    doublearm.py           double-arm tool changer (task 0064): the arm's two joints and the pots' tip joints made by
                           the app (tagged ``fr_atc``, never an axis or the spindle), Check, the bake (a tool copy per
                           holder: spindle, arm, pot; hand-overs worked out from the joints' frames with
                           ``world_at``); random pockets and Tn pre-indexing are planned in core/toolchange.py +
                           core/gcode.py Schedule; ops_doublearm.py; the shared set-up of the test model
                           (``set_up_test_model``, test_atc.step from tools/make_test_atc.py)
    decals.py              logos, text and stickers on parts (task 0024): settings on the part's mesh (every copy)
                           or object (one copy), a decal object per copy (child of the part, hidden with it by
                           MAX drivers), packed pictures, model update + templates; ops_decals.py, ui_decals.py
    callouts.py            labels pointing at parts (task 0025): point on a part, projected per frame, boxes placed;
                           ops_callouts.py, ui_callouts.py (5 Scene & Render > Labels, 6 Animation > Pictures, Music);
                           the strips for labels, picture cards and music are made in video.py
    files.py               open a file / show it in Explorer
    updates.py             in-app updates: start-up check, "Update available" panel, Update now, template refresh
    clash.py               clash check (task 0065): reads every part's place per frame (and G-code corners), groups
                           rigid bodies, checks pairs that move against each other (boxes, then BVH: depth = deepest
                           surface point inside the other, long faces split), between frames where a pair moves fast;
                           rows + markers + fingerprint of the built keys in scene.fresing.clash; red overlay (gpu draw
                           handler); HOOKS for later tasks (hoses); ops_clash.py, ui_clash.py (6 Animation > Clash
                           check). Task 0092: parts that turn in place and are round (rollers, sheaves, drums, a coil)
                           are held still on their carrier (`_hold_still`); a turning part that is not round (a spoked
                           sheave) and a part resting on it outside the room its features sweep are checked once per
                           turn (`_still_pairs`); big parts first look for a gap (box trees, `separation`)
    toolpath.py            the app makes the toolpath (task 0029): inputs from the milling set-up (block, finished part)
                           and the CNC machine (work zero), the program next to the project, its "Run G-code program"
                           step (tagged ``fr_toolpath``, replaced when made again), the result line, the test model's
                           set-up (``set_up_test_model``, test_toolpath.step from tools/make_test_toolpath.py);
                           ops_toolpath.py (Make toolpath: progress + Cancel); panel 4 Motion > Milling > Make a toolpath
                           in ui_machining.py
    hover.py               hover highlight while picking an axis (task 0088): ``look`` = the work of one mouse move
                           (``scene.ray_cast`` + ``decals.through`` = ``cast``, the CAD face from ``fr_face_starts``,
                           ``joints.axis_from_hit``), ``start``/``on_event``/``prompt``/``pick``/``end`` for a click
                           picker's modal; two draw handlers (POST_VIEW face + axis, POST_PIXEL text), nothing in
                           bpy.data; used by ops_motion (Add joint / Set axis), ops_cylinders, ops_doublearm
    vessel_motion.py       vessel motion at sea (task 0085): a rig of empties ("FR Vessel", "FR Vessel pivot") whose
                           channels are a driver giving the time in seconds + built-in sine modifiers (no Python, any
                           fps); model roots, deck objects and props get a Child Of "FR vessel motion" (set_inverse_pending
                           off!); "Still"/"Level" parts a Child Of on the inverse rig; ``at_rest`` mutes it all while the
                           surroundings or a model update measure world places; ops_vessel_motion.py, ui_vessel_motion.py
                           (5 Scene & Render > Vessel motion); the swell goes into the sea only while it is on
    flex.py                hoses, cables and drag chains that follow the motion (task 0058): the hose part itself gets
                           a Geometry Nodes modifier "FR flex" that draws a tube in its place, each CAD chain link one
                           that moves its own geometry (so looks, visibility and selection stay the part's); all shapes
                           live in one hidden mesh "FR flex shapes" (frames x points, world coordinates; the modifiers
                           pick the frame's slice with Scene Time -> Sample Index). Live: a depsgraph handler solves when
                           an end moved (one frame); Build animation reads the ends at every frame and solves them all at
                           once (``bake``; nothing runs in Python while playing or rendering). Ends sit on the parts
                           they touch in the CAD pose; flex parts are left out of the clash check (clash.HOOKS);
                           ``set_up_test_hoses`` / ``set_up_test_chains`` (test_flex_*.step from tools/make_test_flex.py);
                           ops_flex.py, ui_flex.py (4 Motion > Hoses and drag chains)
    paths.py               cables and paths (task 0078): a cable item = its CAD part + a slide joint whose value is the
                           metres paid out ("Cable <name>", moves nothing) + the contacts in order (SHEAVE / ROLLER /
                           CHUTE / BEND, each with a carrier whose coordinates hold its axis). The cable part gets a
                           Geometry Nodes modifier "FR cable" that draws a tube through the points of its own hidden mesh
                           "FR cable shapes <name>" (in the cable part's coordinates; a still tree without Scene Time, a
                           moving one that picks the frame's slice); rollers and sheaves follow the cable joint (own
                           joints kept, app-made ones tagged ``fr_cable``); live handler, ``bake`` at Build after
                           ``flex.bake``; the look's group ("Power cables" / "Wire ropes"); ``set_up_test_model``
                           (test_paths_a.step from tools/make_test_paths.py); ops_paths.py, ui_paths.py
                           (4 Motion > Cables and paths)
    cable_looks.py         the two cable looks (materials ``cable_power``, ``wire_rope``; hook in
                           ``materials.build_nodes``): shader nodes that read the tube's point attribute ``fr_cable``
                           = (cos φ, sin φ, length along the cable) and the object's ``fr_cable_pay`` (metres paid out
                           + 2.0, a simple-expression driver on the cable joint) and ``fr_cable_look``; ``pattern`` =
                           the same formula in plain Python for the tests
    tour.py                test tour (task 0059): the stops (one `stop(...)` each) and the sets (one small project per
                           test model, `@tour_set`), the build, Go (`apply`), OK / Problem results (JSON next to the
                           tour); ops_tour.py (Help > Make / Open test tour project, Go, marks, Copy results);
                           ui_tour.py (the Test tour panel, only in a tour project, on top of the Fresing tab)
    web3d.py               web 3D model (task 0099): the visible parts -> one .glb; each Principled input that is fed
                           by nodes is baked once per node signature as a 0.2 m tile (one bake object, one atlas; a
                           48 px look first drops inputs that are one number), decals on their own UVs; the bake scene
                           is a COPY of a Cycles scene (switching an engine froze the real app); ops_web3d.py (Export…,
                           progress, Cancel), ui_web3d.py (5 Scene & Render > Web 3D model); viewer: fresing_render/web/
                           (model-viewer 4.4.0, Apache-2.0); site: "Turn it yourself" -> model/index.html
    demo.py                demo project "Cable-lay vessel" (task 0077): Help > Make demo project; a background Blender
                           runs the model maker, imports, makes 415 joints (a "Cable travel" slide joint the cable-turned
                           rollers follow), the handler cylinders, sea + quay scenes, cameras and the animation "What it
                           can do today" as a list of named **stages** (``@stage``; tasks 0078–0082 add or replace one);
                           ops_demo.py (Make, Cancel = kill the build's program tree + delete the folder, Open)
  demo_model/              the model maker of the demo (tasks 0076, 0084; moved here from tools/ in task 0077), no Blender:
                           params.py one parameter set, route.py the route maths + positions, geom.py shapes + scene tree +
                           STEP writer, machines.py, deck.py (the deck machines), layout.py (files, sheets: demo_cable_route.json,
                           demo_joints.json), make.py = the command line, run as its own program with Blender's Python
  core/updates.py          versions, update listing (index.json), changelog.json, checked downloads (no Blender)
  update_helper.py         installs a downloaded update while Blender is closed, starts the app again
  queue_runner.py          runs queued renders inside a background Blender
  selftest.py              installation self-test (report on the Desktop)
  pccheck/                 PC check (task 0032): every main function tested on the owner's PC after an update;
                           checks.py = the lines (one per function), core.py (no Blender: history, speed and
                           picture flags, text block, HTML report), runner.py, launcher.py (Start-menu shortcuts,
                           Help > Fresing Render PC check…, Cancel), ops.py (Heavy shortcuts, Cancel);
                           heavy.py (task 0033: the Heavy lines, sizes, peak memory) + heavy_scene.py (writes the big
                           invented machine at run time with OpenCascade; nothing of it is in the repository);
                           tour.py (task 0059: mode Tour = the automatic test tour, a picture per stop)
  data/                    test models that ship with the extension (copies of tests/data, checked by a test)
  blender_manifest.toml    extension manifest (version, bundled wheels)
app_template/fresing_render/   app template: layout, units, switches the extension on
site/                      the landing page https://smholte.github.io/CAD-render-animation/ (task 0047): index.html +
                           style.css (Fresing palette A, IBM Plex Sans in fonts/), brand/ (Fresing logos), media/ (pictures,
                           video, media.json: captions + credits), CREDITS.md; render_kit/ (the owner's Windows kit: "Make site
                           pictures.bat" + make_site_pictures.py + models.ini). tools/build_site.py builds it into dist/site;
                           .github/workflows/pages.yml publishes it (after each release, on site-only pushes to main, by hand)
installer/                 Install.bat / Install-FresingRender.ps1 (Windows, no admin rights, portable Blender)
tools/                     build_release.py, release_tools.py (release job), test-model makers, real-app tests,
                           screenshot tool, ci_*.py / ci_windows_install.ps1 (automatic tests; ci_precheck.py first
                           job, ci_groups.py + ci_times.json parallel groups),
                           ci_update_test.py + update_test_blender.py (in-app update), requirements-dev.txt;
                           make_demo_cable_lay.py (tasks 0076, 0084: the invented cable-lay vessel – a thin wrapper of
                           fresing_render/demo_model/make.py since task 0077; demo_cable_lay_pictures.py renders it)
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

**Claude Code on the web (task 0031).** The owner's environment **"CAD-render-animation"** (claude.ai/code, Network
access Limited with `download.blender.org` allowed) runs `tools/web_setup.sh` as its setup script; the result is
stored for later sessions (about 7 days, only if the script ends within 5 minutes – it takes about 2.5 minutes from
nothing, 0 s when everything is there). What is there at the start of a session:

| What | Where |
| --- | --- |
| Python venv with the pinned packages (`tools/requirements-dev.txt`, incl. `bpy`) | `~/venv` (`~/venv/bin/python`) |
| Real Blender 5.2.3, Linux, sha256 checked | `~/blender-5.2.3/blender-5.2.3-linux-x64/blender` |
| Linux OpenCascade + manifold wheels for the packaged test | `~/linux-wheels` |
| xvfb, ImageMagick (`import`, `convert`) and Blender's system libraries | system |

Check with `ls ~/venv ~/blender-5.2.3 ~/linux-wheels`; when something is missing (stored set-up expired, or a session in
another environment) run `bash tools/web_setup.sh` – it skips what is there and prints one line per part and
"ready in N s". It needs `download.blender.org`; if that is refused, the session is not in the environment above:
tell the owner. For guide pictures make the settings folder once: `~/venv/bin/python tools/web_install_app.py`
(creates `~/fr_user`; then use `BLENDER_USER_RESOURCES=~/fr_user`, see the docstring of `tools/guide_screens.py`).
The set-up script is read from the checked-out repository (default branch): a change to it only reaches the stored
set-up once it is on `main`. `tests/test_web_setup.py` checks its versions against the installer, the workflow
and `requirements-dev.txt`.

By hand (a chat, or no stored set-up): `python3.13 -m venv ~/venv && ~/venv/bin/pip install -r tools/requirements-dev.txt`,
then `~/venv/bin/python -m pytest tests/ -q` (about 6 minutes, all must pass).

## 5. Tests – what to run when

| What | Command | When |
| --- | --- | --- |
| Full suite (1,360+ tests) | `~/venv/bin/python -m pytest tests/ -q` | every change |
| Packaged install + self-test (Linux build of the zip) | `FRESING_SELFTEST_NO_GPU=1 BLENDER_USER_RESOURCES=/tmp/fr_user python tools/test_install_linux.py <linux wheels dir>` | packaging, importer, self-test changes |
| Real app, simulated clicks + accented paths + in-app update (installs the extension and app template into a fresh settings folder itself) | `~/venv/bin/python tools/ci_real_app.py --blender <blender> --wheels <linux wheels dir> --out <dir>` (some: `--only ui1,surroundings,update`; `UITEST_QUICK=1` skips ui1's renders) | UI, operators, before a release. **Runs locally in a web session** (`--blender ~/blender-5.2.3/blender-5.2.3-linux-x64/blender --wheels ~/linux-wheels`; waycover test 27 s on 4 cores) |
| In-app update against the real GitHub release (check + download) | `~/venv/bin/python tools/ci_update_test.py --github --expect <version> --blender <blender> --wheels <dir> --out <dir>` | after a release |
| Side-panel screenshots | `tools/ui_screens.py` (see its docstring) | every UI change: look at the result |
| **All of the above except the screenshots, plus a Windows install** | automatic on GitHub at every push | read the run: below |
| User guide pictures | `tools/guide_screens.py` (modes panels / window / render, see its docstring) | your panels changed: replace their pictures in `docs/img/`. **Runs locally in a web session** (settings folder first: `tools/web_install_app.py`; the decals picture took ~1 min) |
| User guide page | `~/venv/bin/python tools/build_guide.py`, open `dist/guide/user_guide.html` | guide or pictures changed |
| Tooltip check | `~/venv/bin/python tools/tooltip_report.py` (`--all`, `--markdown`) | buttons or settings added or changed |
| PC check Heavy, scaled down (`FRESING_PCCHECK_HEAVY_SMALL=1`: ~300 parts, 14 frames, 540 px; real Blender under xvfb) | `FRESING_PCCHECK_HEAVY_SMALL=1 ~/venv/bin/python tools/ci_real_app.py --only pccheckheavy …` | you changed `pccheck/heavy.py` |
| Test tour: build, Go + check of every stop, buttons, the automatic run for a few stops | `~/venv/bin/python -m pytest tests/test_tour.py -q` (about 2 min); the whole automatic run: `--only tour,tourui` of `ci_real_app.py` | you added or changed a tour stop or a function a stop shows |
| PC check, your lines (bpy module, no graphics card) | `FRESING_SELFTEST_NO_GPU=1 FRESING_PCCHECK_DIR=/tmp/pc FRESING_PCCHECK_ONLY=<line ids> ~/venv/bin/python -c "…runner.run('full', '/tmp/pc', open_report=False)"` (see `tests/test_pccheck.py` for the set-up) | you added or changed a PC-check line |
| Help menu opens the guide (real app, guide inside the installed extension) | `xvfb-run -a -s "-screen 0 1920x1200x24" blender -p 0 0 1920 1200 --app-template fresing_render --enable-event-simulate --python tools/guide_test_app.py` | app template, packaging |

Linux wheels for the packaged test: `pip download cadquery-ocp-novtk==8.0.1.1.0
cadquery-ocp-proxy==8.0.1.1.0 manifold3d==3.5.4 --no-deps --only-binary=:all: --platform manylinux_2_28_x86_64
--python-version 3.13 -d <dir>`.

### Automatic tests on GitHub

`.github/workflows/tests.yml` runs at every push (any branch) and pull request – except a push that
changes only the task list (`TASKS.md`, `tasks/`): that starts no run, and `ci_status.py` says so –, on GitHub's
free runners (4 cores, no graphics card). A newer push to the same branch cancels the older
run; runs on `main` always finish. Since task 0036 the tests run as parallel jobs: a full run takes about
9–12 minutes from push to verdict (task 0063, 10 Nov 2026: two full runs on the branch: 8.8 and 11.9 min; before 0063: 15.7–18; task 0036: median 12.8;
before that 24–50). The job that sets the length is the queued-render test of `tests/test_air.py` (~10 min on a runner)
in a pytest group of its own. The first job,
`precheck`, picks the **mode** of the run (`ci_status.py` prints it):

- **full** – every job below.
- **docs** – the push changes only `docs/`, `site/`, `tools/build_site.py`, `tests/test_site.py`, `CHANGELOG.md`,
  `CLAUDE.md`, `README.md`, `TASKS.md`, `tasks/` and at most the version line of the two version files, compared with
  a commit whose run is green: only precheck, build, tooltip check, guide build and their tests (`test_user_guide.py`,
  `test_updates.py`, `test_ci_tools.py`, `test_site.py`).
- **reuse** – a push to `main` whose git tree already has a green run (the fast-forward of section 2): no tests;
  the release jobs take that run's installer files after `release_tools.py verify-run` checked it again.

When the precheck fails, nothing else starts. On `main` with a new version, three release jobs follow (below):

| Job | What it does | Time (run 42261621440) |
| --- | --- | --- |
| Precheck | `tools/ci_precheck.py`: the two version files agree; a branch that raised the version is newer than `main` and every release and has its CHANGELOG heading (else "someone took your version number: merge main and renumber to …"); `MIN_CHECKS` names every real-app test, `MIN_LINES_FULL` ≥ the PC check's Full lines; every test in exactly one group; `TASKS.md` tables parse; picks the mode and the groups | 0.1 min |
| Linux - test suite 1 … 4 | pytest, the `tests/test_*.py` files split in 7 groups (`PYTEST_GROUPS`; `test_air.py` fills one alone) balanced by `tools/ci_times.json` – the slowest of each file's last 3 recorded runs (`tools/ci_groups.py`, a new file joins by itself); one group also runs the packaged self-test (`test_install_linux.py`). A venv cache (by the hash of `tools/requirements-dev.txt`) saves the package install | 4–8 min; the air group ~9–10 min (task 0063) |
| Linux - real app pccheck / callouts / paths-heavy / tour / ui / scenes / motion | `tools/ci_real_app.py --group <name>`, groups in `GROUPS` next to `MIN_CHECKS`: pccheck + pccheck-b = the PC check (Full, from the installed launcher, judged by `tools/ci_check_pccheck.py`) in two halves – `pccheck2` runs `video.labels` and `queue.time_test` (+ `import.crane` they need), `pccheck` all other Full lines (`tools/ci_pccheck_lines.py`; the precheck fails when they stop adding up to every Full line); machines = milling, cylinder, linkage, waycover, gcode, tourui, doublearm (`ui_test_doublearm.py`, task 0064); callouts = `ui_test_callouts.py` (its queued video takes 5–10 min, so alone); paths-heavy = `paths_test_blender.py` + the PC check Heavy (scaled down, task 0033); tour = the automatic test tour (mode Tour,
task 0059; its own group since task 0060); ui = `ui_test_app.py`, `ui_test_app2.py`, `ui_test_faces.py`; scenes = `ui_test_surroundings.py`, `ui_test_rule_sets.py`, `ui_test_decals.py`; motion = `ui_test_video.py`, `ui_test_studio.py`, `ci_update_test.py --gui`, `ui_test_milling.py`, `ui_test_cylinder.py`, `ui_test_linkage.py`, `ui_test_waycover.py`, `ui_test_gcode.py` (CNC machine, Run G-code program), `ui_test_tour.py` (test tour); Blender 5.2.3 under xvfb, each group installs the extension itself; each test must report at least its number of checks (`MIN_CHECKS`) | pccheck 11–12.4, callouts 5.7–13.8 (with paths), ui 6.5–9.7, scenes 8.2, motion 7.5–9.6 min |
| Build the Windows installer zip | `tools/build_release.py`, as for a release, plus an "old" build (`--version-as 0.0.1 --template-from tests/data/old_app_template`); installer, old installer and the update listing go to the Windows job; mode docs: also `tooltip_report.py --strict`, `build_guide.py` and the documentation tests | 0.6 min |
| Windows - install + self-test | `tools/ci_windows_install.ps1`: the old build installed with `Install.bat -UpdateUrl` (local listing in a folder with a space and an accent) updates itself in the app (`update_test_blender.py`: check, Update now, helper, restart); then the current zip unzipped into a folder with a space and an accent, `LOCALAPPDATA` with a space and an accent, `Install.bat` unattended (install, then repair) over it, checks files and shortcuts, runs the self-test and the PC check (the Windows lines of Full, then Heavy scaled down) from their Start-menu shortcuts, then `Uninstall.bat`. **Which PC-check lines run where (task 0063):** Linux runs all Full lines (the two halves above); Windows runs all Full lines except `video.labels`, `queue.time_test`, `queue.video`, `scene.turntable`, `tour.make`, `looks.materials`, `milling.coolant` (long renders of the app's own code, `WINDOWS_SKIPS` in `tools/ci_pccheck_lines.py`) – the Windows-specific parts (install, start, import, CPU render, the queue's background Blender, update check, the launch from the shortcut, the report) stay | 5.7–6.7 min (was 14.6); starts after the build |
| Tests - verdict | sums up: full = every job above green, docs = build green, reuse = precheck green; the release jobs need it | < 0.1 min |
| Publish the release (only `main` with a new version, all tests green) | `tools/release_tools.py`: tag `v<version>`, installer, extension, `index.json` (full download addresses), `changelog.json`, CHANGELOG section as text; not "latest" yet | < 1 min |
| Windows - an installed old version updates itself from the release | the old build, update address = the release's own `index.json`, must find and install it | 2-3 min |
| Offer the release to the apps | only after that check: marks it "latest", the address every installed app asks | < 1 min |
| Delete the rehearsal pre-release | only after a `[release rehearsal]` branch push (docs/UPDATES.md) | < 1 min |
| Landing page (GitHub Pages) | after "Offer the release": `.github/workflows/pages.yml` builds `site/` with `tools/build_site.py` (newest release, its What's new, the guide) and publishes it; the same workflow runs on a push to `main` that changes `site/` or `tools/build_site.py`, and by hand (Actions → Landing page → Run workflow) | ~1 min |

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
python3 tools/ci_status.py --run <id> --record   # a green run's times -> tools/ci_times.json (balances groups)
python3 tools/ci_precheck.py                   # the precheck's checks, on a chat machine (before pushing)
```

It only shows the run of exactly that commit (never an older one), prints its mode (full / docs / reuse),
lists every job with its time (flagged SLOW above 1.5 x its time in `tools/ci_times.json`), the total and, for a failed job, the failing step, the error lines and the log up to the error. Each job also prints its verdict as a table (which test, which self-test line)
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
  Exception: a file the owner has said is generic and may be committed as a test model (so far: the
  way-cover sub-assembly, task 0034, 6 Nov 2026) – only after checking it holds nothing of a client's.
  Also the owner's own renders and his milling video on the landing page (`site/media/`, task 0047, owner's
  choice 8 Nov 2026) – only what he sends for the page.
- **The Fresing 400 is not public yet** (owner, 12 Nov 2026): it is not ready to be shown in full. Its milling video
  on the landing page shows only a basic interior. Never put the Fresing 400 or any part of it on the site, in a web 3D
  model, a test model, a guide picture or a report, unless the owner releases it explicitly.
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
- **PC check line** (owner's rule, task 0032): a task that adds something the owner can see adds its line to
  `fresing_render/pccheck/checks.py` in the same task – `@line("area.name", "Title", since="<the version it
  comes in>", modes=(F,))`, testing the feature on a test model in `fresing_render/data/` the way a user would,
  raising with a plain reason when it does not work; a render adds `ctx.picture(...)`, a speed `ctx.metric(...)`.
  Raise `MIN_LINES_FULL` in `tools/ci_check_pccheck.py`. A feature whose speed depends on load (big models,
  long animations, 4K, memory) also gets a **Heavy** line in `pccheck/heavy.py` (`modes=(H,)`, with `expected`,
  `shows`, `not_shown`; sizes from `heavy.sizes()` so the scaled-down form works) and `MIN_LINES_HEAVY`
  is raised. The owner runs the check after each update and sends
  back its text block; GitHub runs it at every push.
- **Test tour stop** (owner's rule, task 0059): a task that adds a function the owner can see adds its stop to the
  test tour in the same task – one `stop(...)` entry in `fresing_render/blender/tour.py` (title, "what you should
  see", where in the side panel, the set it lives in, `shot` or `animation`, a number `check`), set up in that set's
  build function (another test model: a new `@tour_set`). Raise `MIN_LINES_TOUR` in `tools/ci_check_pccheck.py` and
  `MIN_CHECKS["tour"]` in `tools/ci_real_app.py` (the precheck says so); `tests/test_tour.py` runs its Go and check.
  **Every tour animation gives 0 clashes** (task 0067): `tests/test_clash.py::test_every_tour_animation_has_no_clash`
  builds and checks every animation of every set by itself (only the clash model keeps its 6.0 mm). A new set that
  fails it has a fault in its test model or its set-up (a part left standing that the motion runs through, a shape
  in the way): fix that, do not loosen the test.
- **Counts** in labels and messages: `core/words.plural(n, "part")` gives "1 part" / "3 parts"
  (`verb()` for the verb that goes with it): never "1 parts".
- **User guide:** a task that changes what the owner sees updates its chapter of
  `docs/USER-GUIDE.md` in the same commit, and replaces the pictures of its panels
  (`tools/guide_screens.py`, test crane only). The guide is built into the release by
  `tools/build_release.py` (needs `markdown`); it opens from Help > Fresing Render user guide.
- Commit messages say what changed and why, in plain words, and end with the attribution
  lines the chat's instructions give.

## 7. Release procedure (the worker chat that finishes a task)

GitHub publishes the release itself (task 0020, `docs/UPDATES.md`): the worker bumps the version and
merges; every installed app (0.2.16 and newer) then offers the update at its next start.

0. `git pull` first: another chat may have released in the meantime; take the next free
   version number.
1. Raise the version in `fresing_render/__init__.py` **and** `fresing_render/blender_manifest.toml`.
2. Add the version to `CHANGELOG.md` at the top (plain words, for the owner): the app shows this text
   under "What's new", the release page too. Heading: `## <version> – <date> – <short title>`. No
   "Commit" line needed any more (the release page shows the commit).
3. Locally the tests of what you changed ("Saving usage", section 2); the GitHub run of the branch
   must be green (section 5): it runs the full suite, the real app and the Windows install.
4. Merge into `main` and push. GitHub tests `main` once more, then publishes the release, checks on
   Windows that an installed old version updates itself to it, and offers it to the apps. Wait for
   it: `python3 tools/ci_status.py --branch main --wait` – every job green, including "Publish the
   release", "Windows - an installed old version updates itself from the release" and "Offer the
   release to the apps". When the release job did not run (it only runs with all tests green), fix
   `main` first.
5. Give the owner the release link (`https://github.com/smholte/CAD-render-animation/releases/tag/v<version>`):
   installed PCs (0.2.16 and newer) get it with **Update now**; new PCs use the installer zip on that
   page. (Only when the owner asks for an installer in the chat – see "Saving usage" in section 2 –
   build it with `~/venv/bin/python tools/build_release.py` and send
   `dist/FresingRender-<version>-windows.zip` with short numbered steps.)
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
- Blender clamps keyed and driven values of a custom property to the property's min/max
  (`id_properties_ui`): a motor needs a wide range, a follower too (its limits only warn).
- Files must work with "Auto Run Python Scripts" off: drivers are AVERAGE or *simple expressions*
  (`driver.is_simple_expression`, e.g. `a * 0.0008 + 0.1`). Blender as a Python module runs every
  Python driver anyway, and real Blender with `-Y` still runs "safe-looking" Python (`len()`,
  `max()`): to prove scripts were off, a control driver needs an attribute lookup
  (`bpy.app.version`) – see `tools/coupling_check_noscripts.py`.
- Blender runs drivers on several threads and does not always finish a *driven* value before
  another driver reads it (a follower one frame behind, 1–3 % of updates on 2 cores). A driver
  reads only plain or keyed values: each follower reads the top joint of its chain directly. The
  copy a driver writes into a custom property can be stale too: compute it (`joints.get_value`).
- Blender keeps the line breaks of an operator's docstring in its tooltip, so a docstring wrapped in
  the source showed a sentence broken in the middle. `register()` joins the lines (test:
  `test_tooltips_have_no_line_breaks`); a `description()` should return one line too.
- In-app updates: a panel's place in the side panel follows `bl_order` and, for equal numbers, the order
  of registration; a negative `bl_order` does not put it on top (the update notice is registered first).
- `wm.quit_blender` in a background Blender only closes it when the running script ends.
- An extension that reaches the network declares `network` under `[permissions]` in its manifest and
  checks `bpy.app.online_access` first.
- Blender resolves a relative `archive_url` in index.json against the address it asked (not the one
  GitHub redirected to); the release job writes full addresses so the listing stays right.
- manifold3d only accepts writable NumPy arrays: arrays read back from a Manifold (`to_mesh()`) are
  read-only, so copy them (`np.array(x)`) before building a new `Mesh`.
- Milling keeps everything it needs in the project, but writes the workpiece mesh on every frame
  change (frame handler): never hold a Python reference to that mesh across frames; look it up
  through `scene.fresing.milling` each time (undo replaces the datablocks).
- "Build animation" remembers how things looked when it was first built (visibility, camera) and the
  render queue builds again: hide parts and set the camera *before* building, or the queue shows them.
- A child object is not hidden with its parent. Decals (task 0024) hide through plain MAX drivers on
  their part's `hide_render` (work with scripts off, in animations and in the queue), and `logic.Tree`
  leaves them out, so hiding a subassembly never hides a decal on its own in the view.
- Writing a small mesh with `from_pydata` + `normals_split_custom_set_from_vertices` took ~0.15 s even
  for 1,600 triangles; `foreach_set` + a `custom_normal` point attribute (as `build._new_mesh`) is
  many times faster – it matters when a mesh is rebuilt while the mouse moves.
- Real-app tests: a mouse-wheel step is one PRESS event (no release); a modal operator should act on
  `event.value == "PRESS"` for the wheel, or a simulated PRESS+RELEASE counts twice.
- Property definitions (`update=`, `get=`, `set=`) in a file with `from __future__ import annotations`: Blender
  evaluates them while the file is read, so the function must be defined *above* the class. A lambda calling a
  function defined further down raised NameError ("Show joint arrows", 0.2.19; test
  `test_show_joint_arrows_toggle`).
- A new or newly parented object has no world matrix until the next update (`matrix_world` is still the
  identity): when building a chain of new empties, pass the parent's world matrix yourself
  (`cylinders._place(..., parent_world)`); the rod's empty first landed twice as far out.
- Undo/redo after "Build animation" called from a script (no undo step of its own) crashes Blender
  5.2.3 (also without milling, found 5 Nov 2026). Real-app tests call operators like a button
  (`"EXEC_DEFAULT", True`), which pushes the undo step.
- Building an animation again puts back the camera it remembered first: to give an already built
  animation another camera (a test), `animation.clear_keys(scene)` first, then set the camera, then build.
- Blender as a Python module draws no text strips after `read_factory_settings()` once it has drawn some (found
  in 0018, 0025): a pytest that draws text (sequencer text strips) runs in a process of its own
  (`fresh_process` in `tests/test_video_labels.py`). Animated sound volume (keyframes) IS honoured in an MP4's
  audio, animated strip opacity is not.
- A text strip draws its own box, so a label's box is as wide as its text: only the box's centre is certain, the
  line ends under the box. Blender has 128 sequencer channels (`video.CH_*`).
- Geometry Nodes "Collection Info" with Separate Children orders the children by name: chips pick their
  shape by instance index, so the shape objects are named "FR chip 000", "FR chip 001" … in that order.
- Transforms set in a `depsgraph_update_post` handler (mechanisms) are evaluated at the *next* update, and nothing
  asks for one: the view lagged a step behind until the mouse moved (found by `ui_test_linkage.py` on GitHub). The
  handler starts a one-shot timer that updates and redraws the 3D views. A script or test that reads `matrix_world`
  must update twice (`tests/test_linkages.py` `update()`), or call `linkages.refresh_all` first (poses do).
- Two-answer formulas (a circle meets a circle or a line) keep their branch by prediction from the last two
  steps: scale the prediction to the step size (a half step during a bisection otherwise jumped to the folded
  scissor), and with fewer than two steps of history keep the same side – near-flat scissor arms move further per
  step than the two answers lie apart.
- A line left after a `return` inside an `if` is never run: 0.2.25 lost two checks of `joints.check_members` that
  way (no test failed). New checks get their own test.
- Way covers (0034): a section's slide joint is created in a loop that grows `scene.fresing.joints`, which
  invalidates any `JointItem` held across it (`make` kept the axis item and lost its frame): keep the joint's
  name or the objects, look it up again. Ratio and limit comparisons use 1e-6: Blender stores them in float32,
  and a changed value calls `set_follows`, which takes a built animation off.
- Inventor adds a version to part names ("Section 1 v8"): match test-model parts by name or `name + " v"`.
- Blender 5.2.3 writes 0 instead of a driver's result when that result is a small positive number (below about
  1e-4: a slide joint 0.05 mm from its CAD position sat exactly at it; found by task 0026). Joint motion drivers
  never give a small number: they work out value + `joints.BIAS` and a generator modifier takes it off again
  (`joints._add_driver`, `_write_one`); `joints.upgrade_drivers` fixes older projects on load. Any new driver
  whose result can be near 0 needs the same.
- G-code keys sit at fractional frames (every move's start and end): a step's last key can land inside the frame
  after its rounded end; `animation.bake` stretches `frame_end` to it.
- Chips are worked out from the bits' paths, never by stepping through frames: the bake must not call
  `frame_set` (it also runs inside the frame handler). The workpiece's place at every frame is read
  along with the paths (`machining.sample` stores it as `fr_wp_m`).
- GitHub Actions skips a job when any job further up its `needs` chain was skipped, even if its own `needs` are
  green, unless its `if:` uses `!cancelled()` (or `always()`) and names the results it wants. The release check
  was skipped after a docs-mode run that way (task 0036). A job behind the verdict needs
  `!cancelled() && needs.<job>.result == 'success'`.
- Blender 5.2.3 corrupts its memory when an array ID property gets a NumPy array of **another length**
  (`ob["x"] = np.zeros(250)`, later `ob["x"] = np.zeros(2000)`): "free(): invalid size" or a segfault a little later,
  wherever the next big allocation happens (milling crashed this way, 0037/0038). Store arrays only with
  `blender/idprops.store_array` (deletes the key first); `tests/test_idprops.py` refuses `["…"] = np.` in `blender/`.
- In a background script nothing reads the milling path after Build (`machining.mark_stale` only schedules a
  re-read in the UI): call `machining.sample(scene)` yourself after building or changing the motion (0037).
- A tool's tip read from its mesh can lie a few hundredths of a mm beside the axis its spindle turns about (fluted
  points are not round; a joint is made on another face). Turning, it went round in a circle and left the program by
  up to twice that (0.065 mm in 0037/0048). `machining.on_turning_axis` puts the tip on the turning joint's axis
  (`gcode._rest_tip`, `detect`, `sample`); test with a spindle joint 0.06 mm off (task 0049).
- An object hidden in the viewport (``hide_viewport``, as tool copies are between their keys) is not evaluated:
  its ``matrix_world`` is stale. A test that compares a hidden copy with a visible one works its world matrix out
  from the parent's: ``parent.matrix_world @ matrix_parent_inverse @ matrix_basis`` (task 0064).
- `actions/download-artifact` with `run-id` + `github-token` (and `actions: read`) takes another run's files: a
  reuse release ships exactly the installer that was tested. Job-level `permissions` replace the workflow's.
- Blender's `BVHTree.find_nearest` / `find_nearest_range` are millimetres off on long thin triangles (draft meshes have
  faces 1 m long and 2.5 mm wide; a point lying on one was reported 0.7 mm away, and the range search skipped the face
  at 2 mm). Cut long faces into short ones before a nearest-point tree (`core/clash.split_long`), and build the tree
  round the mesh's own centre (32-bit numbers; parts drawn metres from their origin lost the micrometres a ray needs).
- The app-made tool copies (task 0040) are meshes of several pieces with faces turned both ways: an inside/outside
  test that trusts the face normals goes wrong on them (`clash.Mesh._orient` turns them right).
- "Build animation" first puts back the visibility (and pose) it saved at the *previous* Build: a part hidden after
  that Build shows again. Clear the keys, then hide, then build (found in the clash tests).
- A copy of a part (`ob.copy()`) keeps `fr_cad_basis`/`fr_rest_basis`: a pose or a start scene puts it back on the
  original's place. Give it its own basis when a test moves it.
- `FCurve.update()` merges keys less than 0.01 frame apart (the later value lands on the earlier time). A G-code
  program squeezed into a short video has moves that short: a lift, a move over and the way down became one straight
  cut through the part (found by task 0029). `animation._write` sorts and recalculates handles instead
  (`keyframe_points.sort()`, `.handles_recalc()`); test `test_keys_close_together_are_kept`.
- Geometry Nodes objects that are only drawn (the toolpath tubes, chips, coolant) are worked out again at every
  `frame_set`: reading the milling path of a 7,000-move program took 67 s, 1.2 s with them hidden while it reads
  (`machining.sample` does that).
- An inside test that trusts the nearest face's normal fails beside a sharp outer edge: the face whose edge is nearest
  can point away from the point (the cut end of a U-shaped claw), so a point 15 mm *outside* read 15–60 mm inside
  (task 0067: 18 of the double arm's 27 rows). `clash.Mesh._inside` decides by the normal only when the point lies
  straight below the face (`FACING` 0.999), else by rays (`tests/test_clash.py`, a knife-edge wedge).
- The clash check found that the test tour's "Boom up" turned the boom down through the base (the joint axis from
  `axis_from_hit` pointed along +Y): fixed in 0065. Run it on a new tour set's animations.
- A STEP part whose shape is several solids (a compound of boxes) comes back from the importer **without its colour**
  (OpenCascade's writer puts the colour on each solid, the reader on sub-shapes): its frames rendered in the group's
  default colour (task 0076). Test models make every part one solid (`fuse`, a pipe swept along a route);
  `fresing_render/demo_model/geom.write_step` refuses anything else.
- A Child Of constraint made with `constraints.new("CHILD_OF")` sets its inverse to the target's place at its first
  evaluation (`set_inverse_pending` is on): the model stayed where it was at that frame and moved only by the
  difference (task 0085). Switch `set_inverse_pending` off and keep `inverse_matrix` the identity.
- A ruled loft between hull stations meshes light (0.3 M triangles at Normal); a smooth loft of the same stations gave
  1.4 M, because Normal caps the facet gap at 0.5 mm on big parts (task 0074).
- `cameras.add_camera` sets the camera's rotation mode to quaternions: setting `rotation_euler` afterwards does nothing
  (the demo's saved cameras looked away from the vessel). Place a camera with `matrix_world` (task 0077).
- `clash.split_long` cut every face longer than 25 mm by halving it at its longest edge: a sliver 60 m long became
  3^10 pieces, a vessel's deck and hull billions, and the clash check ran out of memory. Since task 0077 a long thin
  face is cut into a strip (about 2 x length / 25 mm pieces), a wide face stays whole, and a mesh past
  `MESH_BUDGET` is cut coarser.
- `joints.create` and `joints.set_follows` each updated the whole scene once, even inside `joints._batch`: 0.1 s per
  call on the 1,250-part demo vessel, 67 s for its 415 joints. Since task 0093 a batch updates once on the way in
  and once on the way out (2 s); inside it, read places with `joints.world_of(scene, ob)`, never `matrix_world` of a
  joint empty made in the same batch (still the identity: a stacked joint landed metres off).
- A model's **root** is never a free move (task 0093): `joints.free_moves` / `apply_free_moves` skip it, so a model
  (or a second copy) moved or turned by its root keeps that place through Build, poses, saved scenes and updates.
- The clash check's step between two frames (`core/clash.screw_between`) reads the turn of a body from float32
  matrices with `acos`: when a body turns very slowly while it moves a lot (a slide on a vessel whose sway is at a
  turning point, a cylinder whose angle stands still) that turn is off by ~1e-4 rad and the in-between place by up to
  centimetres: false rows of 1–2 mm (task 0091). The demo's test checks with the sea at rest (`vessel_motion.at_rest`),
  and a cylinder's base pin nearer its hinge than its rod pin keeps its angle moving (clash lane open point).
- A part that rides on something travelling far (the D-quadrant onto its handler) must ride on the thing that will
  carry it later: the travel rides on the handler's tilt, so once on the handler it tilts with it (task 0091).
- With vessel motion on, everything moves: a roller turns in place against the *deck*, not the world. The clash check
  looks for a turning part's carrier among the biggest bodies its box meets too; sorted smallest first, the deck's
  body was cut off and no roller was held (task 0092).
- Geometry Nodes in Blender 5.2 (task 0058, first seen in the 0075 study): a modifier input is
  `mod.properties.inputs.<identifier>.value` (not `mod["Socket_1"]`), the identifier comes from
  `node_group.interface.new_socket(...).identifier`. Geometry *made* by nodes has no material slot: it renders white
  until an (empty) Set Material node gives it slot 0, which the object's own slot then fills. Object Info "Relative"
  copies and transforms the whole source mesh for every user (0.37 ms per hose on a 195,000-point shapes mesh): read it
  "Original" and bring only the sampled points into the object's space (Self Object → Object Info → Invert Matrix →
  Transform Point: 0.055 ms). An object hidden in the view that a modifier input points at *is* evaluated.
- A tube through a hose's solved points needs the end direction built in: a 33-point polyline swept as it is shows
  kinks of ~11° and ends tilted ~1°; `flex.py` adds a point on the first and last piece and sweeps a spline (35 drawn
  points, `flex.DRAWN`).
- A slack hose between fittings that are not in one plane often has two shapes (wound left or right). A solver that
  only sees one frame picks the lower energy and so jumps once along a motion; Build solves the whole animation at
  once and keeps one shape (`core/flex.solve_motion`). Live posing still shows the one-frame answer.
- A box tree built from a Z-order (Morton) sort has nodes that jump across the model (a block of the sorted list can
  straddle a big boundary: a node as long as the whole rope). Halving at the median of each node's longest side, all
  nodes of a level at once (one sort per block), gives compact nodes and is just as fast (task 0092).
- The Principled BSDF stretches the highlight **along** its Tangent (measured in 5.2.3: 16 px along, 6 px across at
  Anisotropic 0.8). A milled or brushed face stretches it *across* its grooves: feed the direction across them
  (task 0061; 0046's brushed and ground looks feed the brushing direction – the wrong way round, still open).
- Manifold gives a face that lies on two solids to either of them: a deeper pass along the same wall takes over the
  whole wall (no line where the depths meet – the marks draw it from ``Moves.step``), and a move straight back out
  shares its faces with the move before it (``Moves.owner``).
- Booleans leave needle triangles (three points on one line; 239 of 2,220 on the milled test block). Their own
  direction is rounding noise, and Blender's smooth-by-angle mixes it into the flat faces next to them: dark facets in
  reflections. The milled mesh gets its corner normals from ``core/cut_normals.py`` (a corner-domain ``custom_normal``
  attribute, written with ``foreach_set``).
- A per-face attribute (FACE domain, FLOAT_VECTOR) is read in a material with an Attribute node of type GEOMETRY, in
  Cycles and EEVEE: no image, no driver. ``Mesh.clear_geometry()`` takes the attributes with it.
- Setting a scene's render engine (``scene.render.engine = "CYCLES"``) while a material-preview render runs froze the
  real app: Blender waits for the preview's thread, which needs the Python lock the script holds (task 0099). A
  temporary scene for baking is a copy of a scene that already renders with Cycles (``web3d.Baker``).
- Cycles bakes one object at a time over the whole target image: 8 bake planes into one atlas took 18 s, the same
  quads as one object 3–5 s (task 0099).
- A driver on an **object's custom property** does not make Blender work out that object's Geometry Nodes again
  (measured: a 32,000-point tube, 0 ms per frame), and a material reads the property with an Attribute node of type
  OBJECT, in Cycles and EEVEE: a pattern that must move every frame (the cable's stripes, task 0078) moves by such a
  driver, never by changing the geometry. A node tree with a Scene Time node is worked out at every frame: a shape
  that stands still gets a tree without one.
- Geometry Nodes 5.2: the Capture Attribute node has a ``Selection`` socket at index 1 – address sockets by name
  (``cap.inputs["len"]``), or the value goes into the selection and every point reads 0 or 1 (task 0078).
- `flex_fit.tube_centreline` cuts a tube at most 1,024 times: on a 300 m cable its line was 0.46 m off. Long cables
  are read in overlapping pieces (`core/paths.centreline`); where two pieces meet, drop only the overlap – dropping
  every later point "behind" the seam lost the part of a rope that turns back over a sheave (found by the independent
  tester of task 0078, not by the author's tests).
- "Round all the way" judged from a mesh's corners fails on real parts: a plain cylinder has corners only at its ends,
  so a drum with one anchor hole had a slice with only that hole's rim and counted as "not round". Judge by the
  triangles' share of the turn (`core/paths.is_round`).
- A joint that moves nothing (`joints.create(..., allow_empty=True)`: a cable's speed, the demo's "Cable travel") was
  dropped at a model update ("its moving parts are no longer in the model") with every coupling to it:
  `joints.rebuild_from_specs` keeps a joint whose spec has no members and no riders (task 0078).
- GitHub's test machines cannot start EEVEE (no GL context): a test that renders with EEVEE checks something else
  there instead of being skipped – each pytest group allows one skipped test (`ci_pytest_summary.py --max-skipped 1`).
