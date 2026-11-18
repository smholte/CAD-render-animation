# 0207 – Study (findings only): signing Fresing Render on Windows – so company PCs and Smart App Control let it run

**Who:** worker · **Status:** running (findings only: no code, no test run, does not count against the four
code tasks) · **Branch:** `task/0207-code-signing-study` (report only, `[docs]`)
**Started by:** lead chat, 18 Nov 2026 (owner: a company wants to use the app; its IT will meet the unsigned program)
· **Lane:** none (study)
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation" (web search
works there)

## Goal

The owner gets a short, ranked choice: how to make Windows (SmartScreen, Smart App Control, a company's AppLocker /
WDAC / antivirus) trust Fresing Render, what each way costs per year, who may buy it (a Dutch one-person company,
the owner as a private person), how long it takes to get, and what the build would change – so he can decide before
a company rolls the app out.

## Background

- 0178 made `Fresing Render.exe`: Blender's `blender.exe` under the app's name and icon, no console. Smart App Control
  turns it off on the owner's PC (`CLAUDE.md`, 0178's report; the PC check notes it). Find out **why**: does changing
  the icon / resources break the Blender Foundation's signature on the copy, and would a signature of our own fix it?
  Is a small signed launcher that starts the untouched, Blender-signed `blender.exe` a better way (keeps Task Manager's
  name? – 0178's goal)?
- What else runs: `Install.bat` → `Install-FresingRender.ps1` (PowerShell), `Uninstall*`, the update helper
  (`update_helper.py` with Blender's Python), the queue runner, the PC check. Which of these does a company's policy
  look at (PowerShell execution policy, signed scripts, Mark of the Web on the downloaded zip)?
- Releases are built and published by GitHub Actions (`.github/workflows/tests.yml`, `tools/build_release.py`,
  `docs/UPDATES.md`); a signature has to be made there, without the key ever in the public repository.
- Downloads are already checked by size + SHA-256 in the updater.

## What to find out

1. Why Smart App Control / SmartScreen block or warn today – from Microsoft's documentation, and from 0178's notes.
2. The ways to sign, each with: price per year, who may buy (organisation vs individual; the Netherlands; KvK
   registration needed?), identity checks and time to get, whether SmartScreen reputation starts at once or builds,
   whether Smart App Control accepts it, how it signs from GitHub Actions (cloud key, HSM, token), and limits. At least:
   Microsoft's cloud signing service (Azure Trusted Signing / Artifact Signing – check today's name, prices and who may
   use it), OV and EV certificates from the usual sellers, free options for open-source projects (e.g. SignPath
   Foundation – check its rules and whether a GPL app with a company behind it qualifies), and "do nothing + IT allows
   it by hash or path".
3. What we would sign (the exe or a launcher, the PowerShell scripts, the zips) and what changes in the build and the
   updater; whether an update must re-sign anything on the PC.
4. What a company's IT needs from us either way (hashes per release, a publisher name, a page for allow-listing) –
   a short list for `docs/COMPANY-USE.md` (0205 owns that file: give the text in the report, the lead passes it on).

## Report

Ranked proposals (cost, time, effort, what the owner must do himself – e.g. identity checks), with sources for every
price and rule (dates – prices change). A recommendation, and the task brief text for the build task it leads to.
Push only the report (`[docs]`), merge to `main`.

## Not in this task

Buying anything, creating accounts, changing the build. The licence (0205, 0206).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Ranked proposals:**

**Owner decides:**

**Brief text for the build task:**
