# 0272 – Locations: several folders per kind (company, department, mine) + export places

**Who:** worker · **Status:** open – waits for 0271 (same lane: adds its tabs) · **Branch:** `task/0272-locations`
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

- [ ] `core/locations.py` with tests (merge, same names, read-only, unreachable folder, relative paths, the set-up
      file's checks with plain-word errors)
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
