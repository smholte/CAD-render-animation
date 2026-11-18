# 0205 – Repository basics: licence file, third-party notices, security policy, contributing, issue templates, "Using Fresing Render in a company"

**Who:** worker · **Status:** open – can start (0202 done, 0.2.157) · **Branch:** `task/0205-repository-basics`
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

**Chat / date:**

**What changed:**

**Tested and measured:**

**Needs the owner:**

**Open points / follow-up tasks:**
