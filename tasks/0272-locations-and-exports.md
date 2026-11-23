# 0272 – Locations: several folders per kind (company, department, mine) + export places

**Who:** worker · **Status:** done (0.2.210) · **Branch:** `task/0272-locations`
**Started by:** lead, 21 Nov 2026 (owner 17:27: "for organisation and user set-ups you should be able to refer to
different file locations from one of the settings pages, such as decals location, render export. For places where you
take information from, such as STEP models, decals, materials, you should be able to select multiple file locations –
a company standard and user-specific or department-specific standards. Possibly also multiple export locations?") ·
**Model:** Opus · effort Medium
**Area:** Settings lane – a **new** `core/locations.py` (no Blender: kinds, levels, the set-up file format, merging,
checks) + `blender/locations.py` (reading prefs, the Locations and Exports tabs in 0271's window); the **readers**
switched to it, read side only: `blender/decals.py` (Logos / Stickers), `rule_sets.py`, `workspaces.py`,
`video.py` (Brand kits), `ops_main.py` (Templates, HDRI), `lifting.py` / `ops_lifting_make.py` (Lifting equipment),
`ops_import.py` (STEP start folder + bookmarks), `render.py` / `queue.py` / `ops_video.py` / `ops_web3d.py` /
`product_video.py` (where outputs are written – one function, see 4); `prefs.py` (new properties, the old
`library_path` kept and migrated); their tests, a real-app test, guide, `docs/COMPANY-USE.md`, CHANGELOG.
Additive changes in other lanes' files: one call each, nothing else in them.
**Not:** the material library itself (0273 reads the Materials kind this task defines); the demo kits folder (stays
in Blender's config folder); what is inside rule sets, templates, workspaces.

## Goal

Every place the app **reads from** (STEP models, logos and stickers, materials, backgrounds, templates, rule sets,
workspaces, brand kits, lifting equipment) can have **several folders**, each marked **Company**, **Department** or
**Mine**. A company sets its standard folders once for everyone; a department adds its own; each user adds personal
ones. Every list in the app shows the items of all folders together, each with a small badge of where it comes from.
And the outputs (pictures, videos, 3D pages, the queue) can go to **named export places** – this settles open
decision **0004** ("where do renders go").

## Design (lead's proposal – the owner can change it; check the answers in TASKS.md before starting)

1. **Kinds:** STEP models · Materials · Logos · Stickers · Backgrounds (HDRI) · Templates · Rule sets · Workspaces ·
   Brand kits · Lifting equipment. One list of folders per kind, in order (top = first choice).
2. **Levels and where they come from:**
   - **Company / Department = set-up files.** A small JSON file (`fresing-setup.json`) on a network folder **or on the
     PC itself** (owner 21 Nov 17:39: organisation / department files are sometimes stored locally – e.g. a folder
     synced by OneDrive / SharePoint, `C:\ProgramData\…`, or copied by IT), written by
     whoever looks after the app there. It names its level and label ("Company", "Offshore department"), and per kind a
     list of folders (UNC paths `\\server\share\…`, mapped drives, local paths, paths relative to the set-up file – so a
     set-up kept in a synced folder works on every PC wherever that folder lands). It may also hold
     **export places** (below) and defaults (default template, rule set, workspace). The user adds set-up files in the
     Locations tab (several: one company + any departments). A set-up file next to the approved-version folder of
     `docs/COMPANY-USE.md` ("Holding one approved version") is picked up by itself – IT sets everyone up by
     putting one file there. Its folders show as **read-only** in the app unless the user can write there.
     **Edit this set-up file** in the tab writes it back when the user has the rights (Windows file permissions are
     the only guard – say so in COMPANY-USE).
   - **Mine:** folders the user adds per kind, saved with the app's settings.
   - The old **Shared library** folder becomes, on first start, a "Mine" location for every kind with today's sub-folder
     layout (`HDRI`, `Templates`, `Rule sets`, `Logos`, `Stickers`, `Brand kits`, `Lifting equipment`) – nothing a user
     has today disappears.
   - **A ready-made "Mine" folder for every user, no set-up needed (owner 21 Nov 22:39,** screenshot of Make a crane
     ending in "No library folder: set the library folder in Preferences first"**):** when no Shared library folder
     was set, the app makes its own on first use – one folder per user, e.g. `Documents\Fresing Render\Library` with
     the sub-folders above (the worker picks the place, says it in the report; OneDrive-moved Documents handled like
     Pictures in `render.py`). Every kind works straight away; the user can change or add folders in Settings >
     Locations. **No "No library folder" message is left anywhere** – today in `ops_lifting_make.py` ~165,
     `lifting_rig_out.py` ~379, `core/lifting_library.py` ~576, `lifting_model/job.py` ~47 (read side + that message
     only); any message that still names "Preferences" for a Fresing setting names **Fresing Settings** instead.
     **When a set-up file was installed first** (an organisation's or the user's own `.frsetup`, e.g. by IT before the
     first start – owner 21 Nov 22:45): the ready-made Mine folders are still made, but **switched off**; the user
     gets one plain note ("Your organisation's set-up is in use. Your own folders are ready but switched off – turn
     them on in Fresing Settings > Locations") and can switch them on per kind there. Without a set-up file they are
     on.
     **Existing users after the update** (like the owner) get the same: no Shared library folder set → the ready-made
     folder is made and switched on at the first start of the new version; a Shared library folder already set → it
     becomes their Mine location as above (nothing new made, nothing moved).
     **Users who update count the same** (owner 21 Nov 22:48 – he has no library folder set today): after the update
     to this version, the first start (or first use) makes the ready-made folders for him, switched on; a Shared
     library folder he had set stays his Mine location instead. The update test (`tools/update_test_blender.py`)
     covers both: an old install with no folder and one with a folder.
   **One file (owner 21 Nov 17:53):** "the set-up should be only one file or one zip, so a user or organisation can
   easily copy and paste one file to and from the app; updating from set-up files should be easy, also when the old
   and new file have different names." So a set-up is **one file, `<name>.frsetup`** (a zip): `setup.json` (a fixed
   **id**, name, level, label, **version** + date, who made it, the settings it sets, locations, export places,
   defaults, first-start choices) and, optionally, the **content** itself in folders (Materials, Logos, Stickers,
   Templates, Rule sets, Workspaces, Brand kits, Lifting equipment, Backgrounds) – so a small company without a network
   share can hand out everything in one file. Folder paths inside it may be absolute (the company share) or point at
   its own content.
   - **Bring one in:** Settings > Locations > **Add a set-up file…**, dropping the file on the app window (a Blender
     file handler, if Blender allows it for this kind – say), or the first-start set-up (0276). The app **copies** it
     into its settings folder (content unpacked there, read-only) **or links** it where it lies (network / synced
     folder: changes there are picked up at the next start) – the user picks, link is the default for a network path.
   - **Update:** a file with the **same id** is the same set-up whatever its file name: newer version → "Update
     *Offshore department* from version 3 to 4?" with the list of what changes (settings, folders, content added /
     changed / removed) → Update / Keep the old one; older → says so, asks before going back; same version, other
     content → shows the difference. A linked file that changed on the share: one quiet notice "Company set-up
     updated (3 → 4)", Show changes.
   - **Make one:** **Save as a set-up file…** – the user's own settings / locations / export places, ticks for what goes
     in (and which content folders to pack), level and label, version raised by itself when saving over an older one
     with the same id. **Edit this set-up file** (for the one who looks after it) does the same on an existing file.
   - **What differs from standard:** the Locations tab (and 0276's first start) can show **"Different from standard"**
     – every setting and folder where the active set-ups or the user's own choices differ from the app's defaults,
     each with where it comes from (Company v4 / Offshore department v2 / Mine), and **Back to standard** per row for
     the user's own ones.
   - Checks with plain-word refusals: not a Fresing set-up, made by a newer app version (what is left out), content
     with an unknown kind, a zip that would write outside its folder (path check), files over a size limit (say which).
   **Owner's answers 21 Nov 17:39:** set-up files may be local or on the network; same names → both shown with
   badges (agreed); the default export place stays **Renders next to the project** (agreed – 0004).
3. **Merging:** lists show every item from every folder, sorted by name, each with its badge (Built-in · Company ·
   department label · Mine). **Same name in two places: both shown**, never one silently hiding the other. A folder that
   cannot be reached (network down, VPN off) shows greyed with one line why, and the app never waits for it on start
   (time-out, read in the background, cached list shown meanwhile – measure on a path that does not answer).
   **Saving** something new (an own rule set, workspace, lifting item, later an own material) asks where, offering only
   the writable folders of that kind, "Mine" first.
4. **Export places:** a named list: **Next to the project (Renders)** and **Pictures\\Fresing Render\\<project>**
   built in, plus places from set-up files (e.g. "Marketing share") and the user's own. One is the **default**. Every
   output window (0260's Make windows) and the queue show **Save to: [place ▾]** with the default chosen; the project
   name becomes a sub-folder in shared places. One tick **"Also save a copy to [place ▾]"** for a second place
   (e.g. the company share). One function decides the folder for every output – no output builds its own path.
5. **STEP models:** Import's file browser opens in the first STEP location and lists all of them (and the last
   used folders) on its left side, so the company's model folder is one click away.
6. **The tabs in 0271's window:** **Locations** – set-up files at the top (add / remove / reload / edit), then one fold
   per kind with its folders (badge, path, reachable or not, up / down, add / remove for Mine). **Exports** – the
   export places, default, the "also a copy" choice.

## Watch

- Windows paths: UNC, mapped drives, OneDrive-moved Pictures (`render.py` already asks Windows), spaces and accents.
  Have the Windows-path handling and the background reading reviewed by an agent that did not write it.
- A project saved on one PC and opened on another where a location does not exist: the project still opens; items it
  used keep working from the project (decals, materials are inside the file) or show what is missing.
- Old projects and old settings: the migration runs once and is tested with a settings file from 0.2.19x.
- `docs/COMPANY-USE.md`: a short "Set up locations for everyone" part with an example `fresing-setup.json`.

## Done when

- [x] The `.frsetup` file: save, add (copy / link), update by id with the change list, Different from standard; tests
      incl. a renamed newer file, an older file, a damaged zip, a zip with a path outside its folder
- [x] `core/locations.py` with tests (merge, same names, read-only, unreachable folder, relative paths, the set-up
      file's checks with plain-word errors)
- [x] Update from the previous version: no folder set → ready-made folders made and on; a folder set → kept as Mine
- [x] Update test: an older version's settings with no library folder → after the update the ready-made folder is
      there and on; with one set → that one is Mine
- [x] With a set-up file installed first: Mine folders made but off, the note shown once, switch on per kind works
- [x] A fresh user (no settings) makes a crane, adds a logo and saves a rule set without setting any folder; no
      "No library folder" message left (`git grep`)
- [x] Every listed reader goes through it; a test proves no reader still builds its own library path
- [x] Locations and Exports tabs; real-app test: two set-up files + a Mine folder, a decal and a rule set from each
      shown with badges; an unreachable folder does not slow the start (number in the report)
- [x] Every output goes to the chosen place; "also a copy" works for a still, a video and the queue
- [x] 0004 closed in TASKS.md with the owner's default; guide + COMPANY-USE; function list, PC-check line, CHANGELOG
- [x] Independent review of the Windows parts; report with the owner's check steps; merged, released

## Not in this task

The material picker and own materials (0273); syncing or copying libraries between PCs; any server.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 23 Nov 2026 · branch `task/0272-locations` · version 0.2.210

**What changed:**
- New `core/locations.py` (no Blender): 10 kinds, levels Company / Department / Mine, the `.frsetup` set-up file (zip:
  `setup.json` with a fixed id + version, settings, locations, export places, first-start choices, optional content per
  kind), plain-word refusals (not a zip / damaged, no setup.json, not Fresing, newer format – what is left out named,
  unknown kind, a path outside its folder, Windows names: `:`, CON/NUL/COM1, trailing dot/space, capitals-only
  duplicates, file > 200 MB / all > 1 GB), the change list (`changes`), merging with badges (same names kept,
  "name (badge)" keys), `Reach` (folders looked at in helper threads – the PC's own folders and `\\server` ones in
  separate pools –, never waited for), export places + `place_folder`, `copy_output`, the migration, "different from
  standard".
- New `blender/locations.py`: state in `<config>/fresing_locations.json`, set-ups kept as a copy + unpacked content in
  `<config>/fresing_setups/` (linked ones re-read when they change), IT's set-up in the approved version's folder picked
  up (address decided from its text, never `isdir` on the main thread), the readers' API, `output_dir` (THE folder of
  every output), `copy_also`. New `ops_locations.py` (24 classes: add/update/remove/save/edit set-ups, own folders on
  off up down add remove, export places, default, also a copy, Save to, Back to standard, a FileHandler for dropping a
  `.frsetup`, STEP folders panel in Import's file browser), `ui_locations.py` (the two tabs, the Save to row).
- **Where the ready-made folder is:** `Documents\Fresing Render\Library\<kind>` (Documents asked from Windows, so a
  OneDrive-moved Documents is followed, as `rule_sets.documents_dir`). Folders a user already had without a library
  (`Documents\Fresing Render\Rule sets`, `Workspaces`, `Logos`, `Stickers`, `Brand kits`) are added as Mine too when
  they hold files – nothing a user had disappears.
- Readers switched (read side only): rule sets, workspaces (save asks **Save in**), decals' logos/stickers, brand kits,
  lifting equipment (Make a crane, own cranes), templates, 360° photos, Import STEP's start folder. Outputs: render
  still, the queue (job carries `also_dir`, `queue_runner` copies), web 3D export, Open render folder – all through
  `render.default_output_dir(scene)`. Old `Own folder` (`out_folder`) still wins; new scene setting `out_place`.
- `prefs.library_path` hidden, read once by the migration; no "No library folder" message left; texts that sent the
  user to "Preferences" for a library now name Fresing Settings > Locations.
- Settings window: tabs Locations, Exports after General (`ui_settings.LATER` = materials only). Client view: the new
  buttons are NOT on its allow list (kept the list short; the window still opens and shows).
- PC check line `settings.locations` (MIN_LINES_FULL 123); tour stop `locations` in the crane set (MIN_LINES_TOUR 97);
  function entries `settings.locations`, `settings.exports`; guide chapters Locations + Exports (+ every old "shared
  library" mention), pictures settings_locations/exports (and the other Settings tabs made again); COMPANY-USE "Set up
  locations for everyone" with an example and network table row 6; CHANGELOG.

**Tested and measured** (4-core web machine, Linux):
- `tests/test_locations.py` 27, `tests/test_locations_blender.py` 14, `tests/test_locations_independent.py` 56 cases
  (independent tester), `test_rule_sets.py`, `test_workspaces_independent.py` (3 old tests rewritten for the new
  folders: an unreachable share = no folder to save into, nothing made on it), about, ci_tools, functions, updates,
  user guide, lifting library/make: all pass.
- Real app: new `ui_test_locations.py` 17/17 (two set-ups + Mine, badges, update by id, Save to + also a copy),
  `ui_test_settings.py` 52/52 (9 tabs clicked), `ui_test_panel.py` and `ui_test_lifting_make.py` (moved from
  `library_path` to `locations.set_mine_root`) pass. PC check line OK (0.1 s).
- **Unreachable folder:** the start's reading (load + logo list) with an own folder on a server whose look takes 20 s:
  **53 ms** (real app), 54 ms in the PC check line (5 s server).
- Update test: `update_test_blender.py` gains two checks (GUI phase): no library folder before → ready-made folders made
  and on; a library folder before → it is Mine for every kind (the second case by running the start's load again).
- GitHub: 3 runs of the branch. Run 1 (45161708629): 2 jobs could not reach github.com (checkout), and 3 real faults –
  the new functions' buttons were refused in the Client view, 0271's tab-order test, the left panel's order test saw
  the file browser's STEP panel; a lesson undo check failed on a slow runner (passes locally, 38/38). Run 2
  (45165592422): all green but two jobs hung in GitHub's apt install; re-run of those two: green. `main` fast-forwarded
  (reuse run): release 0.2.210 published, the old-version update check on Windows green, offered to the apps.

**Subagents:** one independent reviewer + tester (Opus, worktree): reviewed the Windows parts and wrote
`tests/test_locations_independent.py`; it found 15 faults (zip names with `:`/device names/trailing dots, capitals-only
duplicates, PowerShell backslash folder entries, unpack deleting the old content first, Thumbs.db packed, `X:Logos`,
reserved project names, `os.access` saying yes on Windows, state `.tmp` left behind, 4 dead folders blocking the local
ones, `isdir` on the update address on the main thread, set-ups read again every 10 s, copied set-ups resolving
relative folders against the copy, own `file:` parsing). All 15 fixed by the worker; their xfail marks removed.

**Open points / follow-up tasks:**
- Writable / listing calls (`os.access` probe, `os.listdir` of a list) still run on the main thread for folders the
  helper thread found reachable (cached 30 s); a share that dies inside that window can still stall one redraw.
- AUTO mode links only `\\server` paths; a mapped drive (`X:`) is copied (Windows' drive type not asked).
- Not tested on Windows by hand: dropping a `.frsetup` on the window (Blender's FileHandler), the STEP folders panel in
  the file browser, Explorer buttons. Owner's check steps below.
- The full cable-lay demo kit is not affected (no kit `uses` name changed).

**Owner's check (on your PC, after Update now):**
1. Fresing > Settings… → tab **Locations**: under Folders each kind shows "(1)"; open **Logos**: one folder
   `…\Documents\Fresing Render\Library\Logos`, badge Mine.
2. 8 Lifting plan > Equipment > **Make a crane…** → Make: no "No library folder" message; the crane is in your list.
3. Locations → **Save as a set-up file…** → name "Test", tick Logos under "Pack the content of" → Save on the Desktop.
4. Put a PNG in the Logos folder (Show in folder button) → 5 Scene & Render > Logos & stickers > Picture list: it shows
   with "· Mine".
5. Tab **Exports**: tick **Also save a copy to**, pick Pictures… → 5 Scene & Render > Render image: the picture is
   saved next to the project AND in Pictures\Fresing Render\<project>.

