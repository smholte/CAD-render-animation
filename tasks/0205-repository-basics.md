# 0205 – Repository basics: licence file, third-party notices, security policy, contributing, issue templates, "Using Fresing Render in a company"

**Who:** worker · **Status:** done 18 Nov · **Branch:** `task/0205-repository-basics`
**Started by:** lead chat, 18 Nov 2026 (owner after GitHub's Community Standards page; a company wants to use the app)
· **Lane:** Repository & company use (new: root files `LICENSE`, `THIRD-PARTY-NOTICES.md`, `SECURITY.md`,
`CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/`, `docs/COMPANY-USE.md`; small: `README.md`, `tools/ci_precheck.py` doc
lists, a link in `docs/USER-GUIDE.md`)
**Model:** Sonnet · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The repository says plainly what the licence is, what comes from others under which licence, how to report a security
problem or a bug without making anything public by accident, and that outside code is not taken in yet. A company's IT
or legal person finds one page that answers their questions about using the app. **No app code changes** (the licence
inside the app and the installer is 0206).

## Background

- The owner chose **GPL-3.0-or-later** (Nov 2026). `fresing_render/blender_manifest.toml` already says
  `license = ["SPDX:GPL-3.0-or-later"]`, `copyright = ["2026 Fresing"]`, but there is **no `LICENSE` file**, the README
  names no licence, and GitHub's Community Standards list shows Licence, Security policy, Contributing and Issue
  templates as missing.
- Third-party parts known to the lead (the worker makes the full list from the repository and the release zips, not
  from this list): Blender 5.2 (installed by `installer/Install-FresingRender.ps1`), the wheels in
  `tools/build_release.py` (`cadquery-ocp-novtk`, `cadquery-ocp-proxy`, `manifold3d`), `fresing_render/web/`
  (three.js, model-viewer – their LICENSE files are there), fonts in `site/fonts/`, `site/CREDITS.md` (Thor's web model
  CC BY-SA 4.0, IEA 15 MW turbine Apache-2.0), HDRIs / pictures / sounds shipped with the app, music for videos, test
  models in `tests/data/` and `fresing_render/data/`.
- The Fresing name and logo (`fresing_render/brand/`, `site/brand/`) are the owner's brand, not software.
- Network use: as far as the lead knows, the app only reads the update listing and downloads releases
  (`fresing_render/core/updates.py`); the usage tracker (0181, running) keeps everything on the PC. The worker checks
  this in the code (every `urllib`, `http`, `socket`, `webbrowser`, `subprocess` call that could reach the network,
  also in `tools/` scripts the user runs and in the web pages' JavaScript) and writes what it finds.
- A company can already hold one approved version: `Install.bat -UpdateUrl "\\SERVER\share\fresing\index.json"` makes
  the apps update from a network folder with a release's files (`docs/UPDATES.md`, "Other update addresses").
  Company proxies: same file.
- The repository is **public**. Bug reports from company users must never carry their models, part names or
  screenshots.

## What to build

1. **`LICENSE`** at the root: the full, unchanged GNU GPL v3 text (from gnu.org or Blender's own copy; check it is the
   official text). **README:** a "Licence" section – GPL-3.0-or-later, © 2026 Fresing, no warranty (GPL sections
   15–16 in one plain sentence), the Fresing name and logo not covered (see 3), third-party → `THIRD-PARTY-NOTICES.md`.
2. **`THIRD-PARTY-NOTICES.md`**: every third-party part that is in the repository or in a release zip – name,
   version, where it is, licence (SPDX id), source link, required credit line. Check each licence at its source, not
   from memory. **Flag, do not delete:** anything whose licence does not allow it to be in a public repository or to be
   shipped (e.g. a model from a site whose terms forbid redistribution, a picture with no licence found) – a table
   "Needs the owner" at the top of the report, with what to do (remove, replace, ask). Also say whether the GPL text
   and Blender's own licence files reach the PC with today's installer (0206 adds what is missing).
3. **Brand note** (in README and `THIRD-PARTY-NOTICES.md`): the GPL covers the software; the Fresing name and logo
   files are not licensed for other products – a fork must use its own name. Short, plain; mark it in the report as
   "**owner to check** (a lawyer may word it)".
4. **`SECURITY.md`**: supported version = the newest release; report privately through GitHub's private
   vulnerability reporting ("Report a vulnerability" on the Security tab – the owner turns it on, see "Owner") or the
   contact address the owner gives in the start line; never in a public issue; what is in scope (installer, updater,
   file readers STEP/mesh/G-code/house packages, web pages the app writes); best-effort answer, no fixed time.
5. **`CONTRIBUTING.md`**: bug reports and ideas are welcome as issues; **code contributions and pull requests are not
   taken for now** (one sentence why: the owner keeps the copyright whole); before reporting: version
   (Help menu), the PC check result, steps; **never attach confidential models, names or screenshots – the repository
   is public**; company users and anything confidential: the private address.
6. **`.github/ISSUE_TEMPLATE/`**: `bug_report.yml` (form: version, Windows version, graphics card, PC check result
   Quick/Full, steps, what happened, what was expected; a **required** tick "This report contains no confidential
   models, part names or screenshots"), `feature_request.yml`, `config.yml` (blank issues off; contact links: "Private
   report – company models or security" → the security advisory page and the contact address).
7. **`docs/COMPANY-USE.md`** – "Using Fresing Render in a company", for an IT or legal reader, plain words, **no
   company named**:
   - What it is; Windows 11, the bundled Blender 5.2 LTS; where it installs and what it writes where (installer,
     config, projects, renders, caches, logs).
   - **Your files stay on your PC:** what reaches the network (the list from the code check, with addresses) and what
     never does; the usage counts stay local; how to switch the update check off (preference) or point it at a
     network folder.
   - **Holding one approved version:** the network-folder update address (`-UpdateUrl`), how IT puts a release's
     three files there, how a PC returns to GitHub.
   - Proxies (from `docs/UPDATES.md`); Smart App Control / SmartScreen: `Fresing Render.exe` is not signed yet (what
     users see, what IT can do; signing is being looked at – no promise of a date).
   - **The licence in plain words** (not legal advice): free to use inside the company, also for commercial work;
     changes kept inside the company need not be published; giving the app (changed or not) to others outside the
     company brings the GPL's duties (source, same licence); no warranty. Link the GPL's own FAQ for details.
   - Lifting plans (section 8): a planning aid; the competent person's checks and the maker's real charts decide;
     built-in charts are SAMPLE.
   - Support, training and custom work: through Fresing (the contact address).
   Link it from the README and from `docs/USER-GUIDE.md` (one line near the start; the guide's anchor rules hold).
8. **`tools/ci_precheck.py`:** `LICENSE`, `THIRD-PARTY-NOTICES.md`, `SECURITY.md`, `CONTRIBUTING.md` into
   `DOC_FILES` and `.github/ISSUE_TEMPLATE/` into `DOC_PREFIXES`, with a test in its test file, so later changes to
   these files run as docs runs. (This change itself makes this task's run a full one – that is fine.)

## Rules

- The repository is public: no company names, no owner's or employer's anything, no personal e-mail other than the
  contact address the owner gives in the start line. If the start line gives no address, write the security advisory
  page as the only private route and say so in the report – do not stop and wait.
- Nothing is deleted or moved because of a licence doubt – flag it for the owner.
- No app code, no installer change (0206), no change to `docs/UPDATES.md` beyond a link.

## Done when

- [ ] GitHub's Community Standards page (Insights › Community standards) shows Licence, Security policy, Contributing
      and Issue templates ticked (check after the merge; note which stay open and why: Code of conduct, PR template,
      Accessibility – left out on purpose for now, owner 18 Nov).
- [ ] GitHub shows "GPL-3.0 license" in the repository's About box.
- [ ] Both issue forms open and work on github.com (the required tick blocks a report without it).
- [ ] `THIRD-PARTY-NOTICES.md` complete for the repository and both release zips; the "Needs the owner" table in the
      report.
- [ ] Network check written in `docs/COMPANY-USE.md` with file:line references in the report.
- [ ] Precheck test added; full GitHub run green; merged; main contains the commit. No version raise (no app change)
      – unless the release rules require one for a precheck change (CLAUDE.md section 7 decides).
- [ ] Report filled in.

## Owner (not the worker)

- Turn on private vulnerability reporting: Settings › Code security › Private vulnerability reporting › Enable.
- Give the contact address in the start line (or leave it out: then only the advisory page).
- Leave Discussions, Code of conduct, PR template and Accessibility for the public launch.

## Not in this task

The licence shown in the app and the installer, licence files in the install (0206). Code signing (study 0207).
SPDX headers in source files (later; would touch every file). Discussions.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (branch `claude/clever-heisenberg-wj9cqy`), 18 Nov 2026. No contact
address was given in the start line: the security advisory page is the only private route (`SECURITY.md`,
`CONTRIBUTING.md`, issue chooser) – see "Needs the owner".

**What changed (no app code, no version raise):**
- `LICENSE`: the full GNU GPL v3 text (35,149 bytes, sha256 `3972dc97…6986` – the FSF's `gpl-3.0.txt`; taken from Debian's
  `/usr/share/common-licenses/GPL-3`, because gnu.org is blocked here. Blender's own copy
  (`license/spdx/GPL-3.0-or-later.txt`) differs only in `http:` against `https:` links). README: "Licence" section (GPL-3.0-or-later,
  © 2026 Fresing, no warranty, brand note, links).
- `THIRD-PARTY-NOTICES.md`: Blender (downloaded by the installer), the three wheels and the libraries the OpenCascade wheel
  carries, the web viewer (three.js r180, meshoptimizer, model-viewer 4.4.0 / lit), fonts, the credited third-party
  models on the landing page, the pinned house-format copy, dev tools; brand note; the "Needs the owner" table. Licences
  checked at their source (raw files of CadQuery/OCP, OCCT, manifold, three.js, meshoptimizer, model-viewer, IEA 15 MW,
  Thor, CEB press, EVO's `REUSE.toml`, OpenArm; package metadata of the wheels, read from the Windows and Linux wheels
  themselves; Blender's own `license/` folder).
- `SECURITY.md`, `CONTRIBUTING.md` (no outside code for now), `.github/ISSUE_TEMPLATE/` (`bug_report.yml` with the required
  "no confidential" tick, `feature_request.yml`, `config.yml`: blank issues off, private-report link).
- `docs/COMPANY-USE.md` (linked from README and the guide's start): network table with file:line, files and folders, one
  approved version via `-UpdateUrl`, proxy / SmartScreen / Smart App Control, the licence in plain words, Lifting plans.
- `tools/ci_precheck.py`: `LICENSE`, `THIRD-PARTY-NOTICES.md`, `SECURITY.md`, `CONTRIBUTING.md` in `DOC_FILES`,
  `.github/ISSUE_TEMPLATE/` in `DOC_PREFIXES`; test `test_repository_basics_are_documents` (the workflows stay full runs).
- `CLAUDE.md`: layout, docs-mode list, a rule "licence and third parties".

**Network check (what the code does, read, not measured with a network monitor):** only the update check (`core/updates.py:271-278`,
started by `blender/updates.py:172`, off with the preference `prefs.py:28`), the update download on **Update now**
(`core/updates.py:311`), the same check once in the self-test (`selftest.py:238-258`) and the PC check (`checks.py:4261`),
three browser links on click (`updates.py:652`, `welcome.py:501`, `ui.py:990`), and the installer's Blender download
(`Install-FresingRender.ps1:52`). Nothing else uses `urllib`, `socket`, `http` or `webbrowser` in the app (`mesh_reader.py` uses
`urllib.parse` for text only; the web pages' only `fetch` is of an in-memory blob). The usage tracker imports no network library.
The User-Agent is `FresingRender/<version> (update check)` only.

**Tested and measured:** `pytest tests/test_ci_tools.py tests/test_user_guide.py tests/test_site.py tests/test_functions.py` green
locally (74 + 52); `python3 tools/ci_precheck.py` ok; the YAML forms parsed and checked (ids, the required tick).
Not measured: the issue forms on github.com and Community standards (after the merge, below); Blender's extension sync on Windows.

**Needs the owner** (nothing deleted or moved; the same table is at the end of `THIRD-PARTY-NOTICES.md`):
1. **Turn on** private vulnerability reporting (Settings › Code security) – the issue chooser and `SECURITY.md` point to it.
   Give a contact address if you want one (none was given).
2. **Brand note** wording (README, notices) – a lawyer may word it.
3. Decide the licence of Fresing's **own pictures, videos and logos** (`site/media/`, `brand/`): the notice says "all rights reserved"
   for now.
4. `smholte/house-scene-format` has **no licence file**; a pinned copy of its checker is in `tests/data/house/`.
5. **FarmBot Genesis**'s CC0 is "to be confirmed" in `site/CREDITS.md` and could not be confirmed here (the site is blocked);
   nothing of it is in the repository.
6. **The installer switches Blender's online access on and Blender's own extension repository syncs at start** (checked in
   Blender 5.2.3 on Linux: `use_sync_on_startup = True`): Blender may contact `extensions.blender.org` at every start. Not
   measured on Windows. A company will ask; decide whether the installer should switch that sync off (a follow-up task).
7. **Licence texts missing on the PC:** Fresing Render's own GPL, the libraries inside the OpenCascade wheel (FreeImage,
   LibRaw, OpenEXR, FreeType … – the wheel carries none), meshoptimizer's MIT text → task 0206. Whether Blender's `license/`
   folder reaches the PC is expected from the Linux package layout, **not looked at on Windows** → 0206.

**Open points / follow-up tasks:** Community standards, the "GPL-3.0 license" in the About box and the two forms on
github.com can only be looked at after the merge (below). Code of conduct, PR template, Accessibility are left out on
purpose (owner, 18 Nov). 0206 (licence in the app and installer) can start after 0181; points 6 and 7 go into its brief.
