# Using Fresing Render in a company

For an IT or legal reader. Plain words; this is a description of what the program does, **not legal advice**. Written
18 Nov 2026 for version 0.2.158. Every statement about the network comes from reading the program's code (file and
line numbers in the table below); what was **measured** and what is only **read from the code** is said each time.
A question this page does not answer: the contact in "Support" at the end.

## What it is

Fresing Render makes photo-realistic pictures and animations of large STEP assemblies (machines, plants, vessels). It is a
**Blender 5.2 LTS extension** with its own app layout, run by Blender's Cycles renderer. It runs on **Windows 11
(64 bit)**; a graphics card (NVIDIA recommended) makes rendering fast but is not needed to start.

It is free software under **GPL-3.0-or-later** (see "The licence in plain words").

## What the installer puts where

`Install.bat` (no administrator rights) does this, in the folder `%LOCALAPPDATA%\FresingRender` (another folder with
`-InstallDir`):

| What | Where |
| --- | --- |
| Blender 5.2.3 LTS, portable (downloaded from `download.blender.org`, SHA-256 checked) | `%LOCALAPPDATA%\FresingRender\blender-5.2.3-windows-x64\` |
| the Fresing Render extension and app layout | inside that Blender folder, `portable\` (settings, extension, app template) |
| the app's settings and small files | `…\portable\config\` – among them `fresing_update.json` (an update address, only if set), `fresing_usage.json` (counts, see below), `fresing_start.json` (what has been shown), `fresing_left.json` (how you left the left panel's folds), `fresing_settings.json` (every setting of Fresing > Settings…, see below) |
| the in-app update's log | `…\portable\config\fresing_update\update.log` |
| shortcuts | Desktop and Start menu: Fresing Render only; `%LOCALAPPDATA%\FresingRender\Tools` (self test, PC checks, safe start, user guide) |
| `Fresing Render.exe` | next to `blender.exe`: Blender's own program under the app's name and icon (made by the app; not signed, see below) |
| the **Toolbox folder** (task 0217) | `%USERPROFILE%\Toolbox\` (made when missing; `TOOLBOX_HOME` names another folder): `toolbox-folder.json` and the app's own `tools\nl.fresing.render\` – its description `toolbox.json`, `alive.json` while it runs, and `inbox\` where other tools on this PC (House Planner) leave files for it. `Uninstall.bat` removes only `tools\nl.fresing.render\` |

What it writes while it works: the user's **projects** (`.blend`) where the user saves them; **renders** in a "Renders"
folder next to the saved project (or `Pictures\Fresing Render`; or an export place of Fresing > Settings… > Exports); a **cache** of read STEP files in the extension's user
folder (`…\cache\`, so the same file opens fast the next time); the **self-test and PC-check reports** on the Desktop;
the **logs** named above. `Uninstall.bat` (or Uninstall in Installed apps) removes the install folder; projects and renders are not touched. The installer writes **one registry key, per user** (no admin
rights): `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\FresingRender`, so the app is listed in Settings > Apps > Installed apps with its version, size and an Uninstall button (task 0265; the app updates its version at **Update now** and checks it at start; the uninstaller removes the key last). It starts no service (searched in `Install-FresingRender.ps1`).

## The user's settings (one file)

Everything a user sets in **Fresing > Settings…** (default template, rule set and workspace, the
lesson look, backups, update checks …) is kept in **one file**, `…\portable\config\fresing_settings.json`
(task 0283; Blender itself forgets an add-on's preferences while the app's layout is on). It is plain JSON:
`{"format": "fresing-settings", "version": 1, "settings": {…}}`, holding only the settings that differ from the
app's defaults – an empty `settings` means "all defaults". The app reads it at start and writes it within a second
of a change (a temporary file, then a rename). An update – **Update now** or the installer over an older install –
leaves it as it is; `Uninstall.bat` removes it with the install folder, like the other files in `config\`.

**To give every PC the same settings:** set them once on one PC, then copy that file into `…\portable\config\` of
the others (with the app closed). Paths in it (the default template) must exist on each PC – a
network share works. A file that cannot be read is not used: the app starts with the defaults, keeps the file as
`fresing_settings.broken-<date>-<time>.json` and shows one line in Settings > General. A file from a newer version
of the app is read for what this version knows; the rest is kept. For folders, export places and settings for a
whole company or department there is the **set-up file** (below).

## Set up locations for everyone (one set-up file)

The app reads models, logos, stickers, materials, 360° photos, templates, rule sets, workspaces, brand kits and lifting
equipment from **folders per kind**, each marked **Company**, **Department** or **Mine** (Fresing > Settings… >
Locations). A company or department hands out its folders, export places and settings as **one file**,
`<name>.frsetup` – a zip with a `setup.json` and, if wanted, the content itself in folders named `STEP models`,
`Materials`, `Logos`, `Stickers`, `HDRI`, `Templates`, `Rule sets`, `Workspaces`, `Brand kits`, `Lifting equipment`
(so a firm without a network share can hand out everything in one file). Example `setup.json`:

```json
{"format": "fresing-setup", "format_version": 1, "id": "acme-standard", "name": "Acme standard",
 "level": "company", "label": "Acme", "version": 4, "date": "2026-11-23", "made_by": "IT",
 "settings": {"default_rule_set": "Acme", "default_workspace": "CNC milling"},
 "locations": {"logos": ["\\\\server\\share\\Fresing\\Logos"], "rule_sets": ["Rule sets"],
               "step": ["S:\\Engineering\\STEP"]},
 "exports": [{"name": "Marketing share", "path": "\\\\server\\marketing\\Renders", "project_sub": true}]}
```

- **Paths** may be UNC (`\\server\share\…`), a mapped drive, a local path, or **relative to the set-up file** (as
  `Rule sets` above): a set-up kept in a folder synced by OneDrive / SharePoint works wherever that folder lands.
- **The `id` makes it the same set-up**, whatever the file is called: a file with the same id and a higher `version`
  is offered as an update with the list of what changes. **Fresing > Settings… > Locations > Save as a set-up file…**
  writes one from a PC that is set up (and raises the version when saving over the old one); **Edit this set-up
  file…** writes back a set-up in use.
- **Bring it to every PC:** put it in the folder of the approved version (the folder `Install.bat -UpdateUrl` points
  at, [below](#holding-one-approved-version)) – every PC picks it up by itself at its next start, linked: when you
  replace it there with a newer version, every PC updates at its next start. Or each user adds it with **Add a set-up
  file…** (copy or link) or drops it on the app window. A PC whose first start of this version finds such a set-up
  makes the user's own folders but switches them off, with one note.
- **Who may change it:** Windows' file rights on the set-up file and its folders are the only guard; make them
  read-only for users. Folders users cannot write to are never offered for saving.
- **The app keeps** a copy of each set-up and its unpacked content in `…\portable\config\fresing_setups\`, and the
  user's folders, set-ups and export places in `…\portable\config\fresing_locations.json`. A folder that cannot be
  reached (network down, VPN off) is looked at in the background and left out until it answers – the app never waits
  for it.
- **Refused** with a plain message: a file that is not a Fresing set-up or is damaged, content of an unknown kind, a
  path that would write outside its folder, a single file over 200 MB or more than 1 GB in all. A set-up from a newer
  app is read for what this version knows; what is left out is named.
- **Export places** in a set-up show next to **Next to the project (Renders)** – the standard – and
  **Pictures\Fresing Render\<project>**; "project_sub" puts each project's outputs in a folder of its own.

## Your files stay on your PC

**What reaches the network – and only this:**

| # | What | When | Where to | In the code |
| --- | --- | --- | --- | --- |
| 1 | **Update check**: reads one small file, `index.json` (the newest version's number, size and checksum), and `changelog.json` | a few seconds after the app starts, if **Fresing > Settings… > Updates > "Check for updates at start-up"** is on (it is by default) and Blender's online access is on; also when the user clicks **Check now** / Help > Check for Fresing Render updates | `https://github.com/smholte/CAD-render-animation/releases/latest/download/index.json` (GitHub redirects to its download servers), **or** the address in `fresing_update.json`, **or** a network folder (below) | `core/updates.py` lines 271–278 (`urlopen`), 281 (`fetch_json`), 349 (`check`), 389 (`index_url_from`); `blender/updates.py` 119 (`check_now`), 137 (`check_in_background`), 172 (`_startup_check`); `blender/prefs.py` 28 |
| 2 | **Update download**: the extension zip of the new version, checked against the size and SHA-256 in `index.json` | only when the user clicks **Update now** | the address in `index.json` (a GitHub release file) | `core/updates.py` 311 (`download`); `blender/updates.py` 311 (`start_download`) |
| 3 | **The same check, once**, inside the self-test and the PC-check line "Update check" | when the user runs them | as 1 | `selftest.py` 238–258; `pccheck/checks.py` 4261 |
| 4 | **Links that open the web browser** | only when the user clicks one: "What's new" release page, "How to get free 360° photos" | `github.com/smholte/CAD-render-animation` pages | `blender/updates.py` 652; `blender/welcome.py` 501; `blender/ui.py` 38 and 990 |
| 6 | **Folders on your own file shares** (task 0272): the folders of Locations, a linked set-up file, the set-up file in the approved version's folder – read like any file on the share, never the internet | at the start and in the background while the app runs (each folder at most every 30 s), when a list is shown, when the user clicks Look again | the paths in the set-up files and the user's own folders | `core/locations.py` 638 (`Reach._look`), 168 (`read_setup`), 304 (`unpack`); `blender/locations.py` 174 (`install`), 239 (`refresh`), 274 (`approved_folder`), 296 (`pick_up`), 445 (`items`) |
| 5 | **The installer downloads Blender** | at install time, unless `blender-5.2.3-windows-x64.zip` is put next to `Install.bat` | `https://download.blender.org/release/Blender5.2/` (an old PowerShell may use BITS) | `installer/Install-FresingRender.ps1` 52 (address), 128 and 133 (transfer) |

The request carries only `FresingRender/<version> (update check)` as its `User-Agent` (`core/updates.py`, `user_agent`) –
**no model, file name, user name, project or machine name**. As with any web request, the server sees the PC's
(or the company's) internet address.

**What never reaches the network** (checked by searching the code for `urllib`, `http`, `socket`, `webbrowser`,
`subprocess` and `fetch`; **read from the code, not measured with a network monitor**):
- the STEP files, projects, renders, part names, pictures – the STEP reader is a program on the same PC
  (`importer/step_reader.py`), the render queue is a second Blender on the same PC
- the **usage counts**: the app counts which functions are used (for "My usage", the favourites bar and "time saved"). They
  stay in `fresing_usage.json` on the PC; the module imports no network library and a test checks that
  (`core/usage.py` line 5, `tests/test_usage.py`). The user can export a profile to a file and hand it on by hand.
- the **Web 3D model** pages the app writes: one file, with the viewer inside; it loads nothing from the internet
  (`fresing_render/web/README.txt`; the only `fetch` is of the page's own in-memory data, `web/fr_page.js` line 2192)
- the PC check and the self-test (apart from the one update check of row 3)
- the **Toolbox folder** (task 0217): tools on the same PC hand files to each other through a plain folder in the user's
  home folder – no server, no network port, nothing leaves the PC (`core/toolbox.py` imports no network library;
  `blender/toolbox_inbox.py` only looks at that folder every 2 seconds). The app reads only files of the two kinds it
  takes (a STEP file, a House Planner house), checks name, size and kind by content before it opens one, never follows
  a link, and imports or bakes only when the user presses **Import now** / **Bake now**. A house it bakes goes back as a
  file into House Planner's folder there. Like the user's Documents, anything that can write in that folder can offer
  the app a file.
- **demo kits** (task 0228): Help > Make demo project… > **Add a demo kit…** unpacks a zip the user picks into Blender's
  settings folder (`fresing_demo_kits`) and **Make** runs the Python code in it inside the app, like an add-on – it
  can do anything the app can. **A demo kit is Python code that runs in the app: add only kits you made yourself.**
  The app checks the zip's layout and the versions it was made for, not what the code does (`core/demo_kits.py`,
  `blender/demo.py` `_kit_build`). The app itself downloads no kit and reaches no network for one.
- no crash reports, no telemetry, no licence server, no account.

**Blender itself.** The installer switches Blender's **online access on** (`Install-FresingRender.ps1`, the `set_prefs.py`
block), because the update check needs it. In Blender 5.2.3 its own extension repository (`extensions.blender.org`) is set
to "sync on start-up" by default (`use_sync_on_startup`), which would let Blender itself contact that address at every
start. **Since 0.2.162 the installer switches that sync off on every remote repository, and an install made before it
does the same once, at the first start after the update** (`blender/ext_sync.py`; it is remembered in
`fresing_ext_sync.json` next to the other settings, so a user who turns the sync back on keeps it on). So at start the app
contacts nothing except its own update check. The Windows test of every release checks that no remote repository syncs at
start after an install. A company that wants no Blender extension traffic at all can also block `extensions.blender.org`
– the app does not need it.

**Switching the update check off:** untick **Check for updates at start-up** (Fresing > Settings… > Updates; the same setting as before in Edit >
Preferences > Add-ons > Fresing Render), or switch Blender's online access off (Edit > Preferences > System > Network): then the app contacts no
server at all. New versions then come by running the new installer.

## Holding one approved version

IT can keep all PCs on one tested version and update them by its own schedule:

1. Download the three release files of the approved version from the GitHub release page
   (`https://github.com/smholte/CAD-render-animation/releases`): `index.json`, `changelog.json` and
   `fresing_render-<version>.zip`. Put them in one folder, for example `\\SERVER\share\fresing\`.
2. On each PC, once: `Install.bat -UpdateUrl "\\SERVER\share\fresing\index.json"` (keep the quotes). The app then looks
   in that folder, never on GitHub; a file address `file://SERVER/share/…` works too.
3. For the next approved version, put its three files in the folder (replace the old ones). The PCs offer it at their
   next start.
4. To go back to GitHub: `Install.bat -UpdateUrl default`.

The installer itself (`FresingRender-<version>-windows.zip`) can come from the same place; a PC without internet access
puts `blender-5.2.3-windows-x64.zip` next to `Install.bat`. Details: `docs/UPDATES.md`, "Other update addresses" and the
install instructions `docs/README-install.txt`.

## Proxies, SmartScreen and Smart App Control

- **Proxy:** the update check uses the Windows proxy setting (Internet Options). A proxy that needs a Windows login or is
  set by a script (PAC/WPAD) may block the check; the self-test line "Update check" says so. IT can allow
  `github.com` and the download servers it redirects to, or use the network folder above. The installer uses the
  Windows login for its proxy when it downloads Blender (`Install-FresingRender.ps1`).
- **SmartScreen:** the installer is not signed; Windows may say "Windows protected your PC": More info > Run anyway.
- **`Fresing Render.exe` is not signed.** It is a copy of Blender's `blender.exe` with Blender's signature taken off and
  the name and icon changed (`fresing_render/winexe.py`), so Task Manager shows "Fresing Render". With **Windows 11
  Smart App Control** on (or evaluating), Windows blocks unsigned programs; the app then does not make or use that
  copy and starts with Blender's own signed program (shortcut **Fresing Render - safe start**; Task Manager says
  "Blender"). Signing Fresing Render's own program is being looked at; **no date is promised**. IT can also allow the
  install folder in its application-control policy.
- Virus scanners sometimes lock freshly unpacked files; the installer retries for some seconds.

## The licence in plain words

*Not legal advice.* Fresing Render is under the **GNU General Public License, version 3 or later** (`LICENSE`). In
short:

- **You may use it inside the company, for any work, also commercial.** Renders and videos made with it are yours; the
  licence puts no claim on them.
- **Changes kept inside the company need not be published.** The GPL's duties start when you **give the program
  (changed or not) to others outside the company** – customers, partners, another company: then they get the source
  code, under the same licence, and the licence text. Giving it to your own employees or contractors working for you
  on your behalf is the company's own use.
- Using the Fresing **name and logo** for a changed version is not covered: a changed copy given to others has its own
  name (see `THIRD-PARTY-NOTICES.md`, brand note).
- **No warranty** (GPL sections 15 and 16): the program is given as it is, without a promise that it fits a purpose.
- The libraries in it (Blender, OpenCascade, Manifold, three.js …) have their own licences, all of which allow this use:
  `THIRD-PARTY-NOTICES.md`.
- The GPL's own questions and answers: https://www.gnu.org/licenses/gpl-faq.html

## Lifting plans

The section **8 Lifting plan** is a **planning aid**. It checks a plan only against the data entered in it – not against the
real equipment, ground or load. **The competent person's checks and the maker's real load charts decide**, and the plan
must be approved by the competent person (appointed person, lift director) before any lift. The cranes that come with
the app are **invented classes with SAMPLE charts** ("SAMPLE – not for real lifts"); a real lift needs the real crane's
own chart entered. The app never calls a lift "safe". See the user guide, chapter 8.

## Reporting problems without leaking models

The repository is public. Bug reports and ideas: issues on GitHub, **without** confidential models, part names or
screenshots (`CONTRIBUTING.md`; the form has a tick for it). A security problem, or a problem that only shows with a
confidential model: GitHub's private report form (`SECURITY.md`), never a public issue.

## Support, training and custom work

Through **Fresing** (https://fresing.nl). Support, training for your team and work made to your needs are not part of the
free software; ask Fresing.
