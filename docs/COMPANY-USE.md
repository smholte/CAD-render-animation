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
| the app's settings and small files | `…\portable\config\` – among them `fresing_update.json` (an update address, only if set), `fresing_usage.json` (counts, see below), `fresing_start.json` (what has been shown) |
| the in-app update's log | `…\portable\config\fresing_update\update.log` |
| shortcuts | Desktop (Fresing Render, PC check heavy), Start menu > Fresing Render (self test, PC checks, user guide, safe start) |
| `Fresing Render.exe` | next to `blender.exe`: Blender's own program under the app's name and icon (made by the app; not signed, see below) |

What it writes while it works: the user's **projects** (`.blend`) where the user saves them; **renders** in a "Renders"
folder next to the saved project (or `Pictures\Fresing Render`); a **cache** of read STEP files in the extension's user
folder (`…\cache\`, so the same file opens fast the next time); the **self-test and PC-check reports** on the Desktop;
the **logs** named above. `Uninstall.bat` removes the install folder; projects and renders are not touched. The installer writes no registry keys and
starts no service (searched in `Install-FresingRender.ps1`).

## Your files stay on your PC

**What reaches the network – and only this:**

| # | What | When | Where to | In the code |
| --- | --- | --- | --- | --- |
| 1 | **Update check**: reads one small file, `index.json` (the newest version's number, size and checksum), and `changelog.json` | a few seconds after the app starts, if **Edit > Preferences > Add-ons > Fresing Render > "Check for updates at start-up"** is on (it is by default) and Blender's online access is on; also when the user clicks **Check now** / Help > Check for Fresing Render updates | `https://github.com/smholte/CAD-render-animation/releases/latest/download/index.json` (GitHub redirects to its download servers), **or** the address in `fresing_update.json`, **or** a network folder (below) | `core/updates.py` lines 271–278 (`urlopen`), 281 (`fetch_json`), 349 (`check`), 389 (`index_url_from`); `blender/updates.py` 119 (`check_now`), 137 (`check_in_background`), 172 (`_startup_check`); `blender/prefs.py` 28 |
| 2 | **Update download**: the extension zip of the new version, checked against the size and SHA-256 in `index.json` | only when the user clicks **Update now** | the address in `index.json` (a GitHub release file) | `core/updates.py` 311 (`download`); `blender/updates.py` 311 (`start_download`) |
| 3 | **The same check, once**, inside the self-test and the PC-check line "Update check" | when the user runs them | as 1 | `selftest.py` 238–258; `pccheck/checks.py` 4261 |
| 4 | **Links that open the web browser** | only when the user clicks one: "What's new" release page, "How to get free 360° photos" | `github.com/smholte/CAD-render-animation` pages | `blender/updates.py` 652; `blender/welcome.py` 501; `blender/ui.py` 38 and 990 |
| 5 | **The installer downloads Blender** | at install time, unless `blender-5.2.3-windows-x64.zip` is put next to `Install.bat` | `https://download.blender.org/release/Blender5.2/` (an old PowerShell may use BITS) | `installer/Install-FresingRender.ps1` 52 (address), 121 and 126 (transfer) |

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
- no crash reports, no telemetry, no licence server, no account.

**Blender itself.** The installer switches Blender's **online access on** (`Install-FresingRender.ps1` line 258), because
the update check needs it. With it on, Blender's own extension manager may contact `extensions.blender.org` at start-up:
in Blender 5.2.3 that repository is set to "sync on start-up" by default (checked in Blender 5.2.3 on Linux with
`use_sync_on_startup`). This is Blender's behaviour, not Fresing Render's, and **it has not been measured on Windows**; a
company that wants no such traffic can set Edit > Preferences > Get Extensions > the repository's "Check for Updates on
Startup" off, or block `extensions.blender.org` – the app does not need it. (Whether the installer should switch it off
is an open decision of the owner.)

**Switching the update check off:** untick **Check for updates at start-up** (Edit > Preferences > Add-ons > Fresing
Render), or switch Blender's online access off (Edit > Preferences > System > Network): then the app contacts no
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
