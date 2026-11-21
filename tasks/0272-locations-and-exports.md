# 0272 – Locations: several folders per kind (company, department, mine) + export places

**Who:** worker · **Status:** open – after 0278 (both change `prefs.py`; 0271 done) · **Branch:** `task/0272-locations`
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

- [ ] The `.frsetup` file: save, add (copy / link), update by id with the change list, Different from standard; tests
      incl. a renamed newer file, an older file, a damaged zip, a zip with a path outside its folder
- [ ] `core/locations.py` with tests (merge, same names, read-only, unreachable folder, relative paths, the set-up
      file's checks with plain-word errors)
- [ ] Update from the previous version: no folder set → ready-made folders made and on; a folder set → kept as Mine
- [ ] Update test: an older version's settings with no library folder → after the update the ready-made folder is
      there and on; with one set → that one is Mine
- [ ] With a set-up file installed first: Mine folders made but off, the note shown once, switch on per kind works
- [ ] A fresh user (no settings) makes a crane, adds a logo and saves a rule set without setting any folder; no
      "No library folder" message left (`git grep`)
- [ ] Every listed reader goes through it; a test proves no reader still builds its own library path
- [ ] Locations and Exports tabs; real-app test: two set-up files + a Mine folder, a decal and a rule set from each
      shown with badges; an unreachable folder does not slow the start (number in the report)
- [ ] Every output goes to the chosen place; "also a copy" works for a still, a video and the queue
- [ ] 0004 closed in TASKS.md with the owner's default; guide + COMPANY-USE; function list, PC-check line, CHANGELOG
- [ ] Independent review of the Windows parts; report with the owner's check steps; merged, released

## Not in this task

The material picker and own materials (0273); syncing or copying libraries between PCs; any server.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
