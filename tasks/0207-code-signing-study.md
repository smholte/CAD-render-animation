# 0207 – Study (findings only): signing Fresing Render on Windows – so company PCs and Smart App Control let it run

**Who:** worker · **Status:** done (findings only: no code, no test run, does not count against the four
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

**Chat / date:** Claude Code on the web, 18 Nov 2026. Findings only: no code, no test run, nothing bought.
Sources: web search on 18 Nov 2026. Fetching whole pages was blocked in this environment (the hosts are not on its
network list), so every price below comes from the search tool's quotes of the pages named. **Check prices on the
seller's own page before buying.**

**Findings:**

1. **Why Smart App Control (SAC) blocks `Fresing Render.exe`.** SAC first asks Microsoft's cloud service whether a file
   is known to be safe. If the cloud has no answer, SAC checks for a valid signature from a certificate authority that
   Windows trusts. If neither check passes, the file is blocked ([What is Smart App Control](https://support.microsoft.com/en-us/topic/what-is-smart-app-control-285ea03d-fa88-4d56-882e-6698afdb7003)).
   Our copy is new to the cloud (its hash exists only on our PCs) and it has no signature. 0178 removed Blender's
   signature on purpose, because any changed byte breaks it. A broken signature counts the same as none. So yes: changing
   the icon and resources is what takes away Blender's trust. **Our own valid signature would fix it.** SAC accepts
   any valid signature that chains to a trusted root; there is no list of "good" sellers. Microsoft's answer to
   developers is "sign your app with a valid certificate". Use an RSA key: reports from 2026 say SAC did not accept ECC
   signatures ([Authenticode in 2024](https://textslashplain.com/2024/05/22/authenticode-in-2024/), Microsoft Q&A
   threads). SAC also checks **DLLs** an app loads ("blocked part of this app",
   [support page](https://support.microsoft.com/en-us/topic/smart-app-control-has-blocked-part-of-this-app-0729fff1-48bf-4b25-aa97-632fe55ccca2)).
   The OCP / manifold `.pyd` files from the wheels are unsigned. On the owner's PC they evidently pass, probably on cloud
   reputation (they are popular PyPI files). A company's App Control (WDAC) would not let them through that way.
2. **What happens today with SAC on.** 0178's fallback works: no copy is made, and the shortcuts start Blender's own
   `blender-launcher.exe`, which is signed by Stichting Blender Foundation. The app runs, but Task Manager says "Blender".
   So for SAC, signing gains the name and icon, not "it runs at all".
3. **SmartScreen** looks only at files with a Mark of the Web (downloaded). Since 2024, EV certificates no longer skip
   the warning: reputation is built per file and per publisher, and a new file starts from nothing
   ([Microsoft: SmartScreen reputation](https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation),
   [code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options),
   [ToDesktop, EV no longer instant](https://www.todesktop.com/blog/posts/windows-apps-psa-ev-certs-do-not-grant-immediate-reputation-anymore)).
   The copy made on the PC has no Mark of the Web (0178 checked this). The **downloaded zip** does have one, and
   Windows passes it to the files unpacked from it. So `Install.bat` gets the SmartScreen / "Open File" warning.
   A `.bat` file cannot be signed (Authenticode covers exe/dll/msi/ps1, not batch files). Getting rid of that warning
   would take a signed installer `.exe` – a later step.
4. **PowerShell.** `Install.bat` starts the script with `-ExecutionPolicy Bypass`. That beats the user's own setting,
   but **not** an execution policy set by company Group Policy: MachinePolicy / UserPolicy rank above the
   `-ExecutionPolicy` switch ([about_Execution_Policies](https://learn.microsoft.com/powershell/module/microsoft.powershell.core/about/about_execution_policies)).
   A company with "AllSigned" by Group Policy, or AppLocker / WDAC script rules (which put unsigned scripts in
   Constrained Language mode), stops `Install-FresingRender.ps1` / `Uninstall-FresingRender.ps1`. Signing both
   `.ps1` files fixes that. `.py` files (update helper, queue runner, PC check) run inside Blender's Python, and
   AppLocker / WDAC do not look at them.
5. **Releases are many and automatic** (several a day, 0.2.158 today). Any way that needs a **manual approval per
   release** (SignPath Foundation) or a phone code per signing session (Certum SimplySign) does not fit unless the
   build signs only the files that changed. The files to sign change rarely: the exe (only with a new Blender or
   maker), the two `.ps1` files, the wheels' `.pyd` (only with new pinned wheels). **Sign once per content and reuse
   the signed file**, keyed by the unsigned file's SHA-256. Then even 20 signatures a month is plenty.

**Ways to sign** (prices from search quotes, 18 Nov 2026):

| Way | Price / year | Who may buy | Time to get | Signs from GitHub | Notes |
| --- | --- | --- | --- | --- | --- |
| **Microsoft Artifact Signing** (was Trusted Signing; GA, [Microsoft blog](https://techcommunity.microsoft.com/blog/microsoft-security-blog/-/4482789)) | Basic $9.99/month ≈ $120 (5,000 signatures/month, then $0.005) – [Azure pricing](https://azure.microsoft.com/en-us/pricing/details/artifact-signing/), [SKU doc](https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/artifact-signing/how-to-change-sku.md) | **Organisations** in the EU/UK with **≥ 3 years of verifiable history**; **individuals only USA/Canada** ([code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)). Needs a paid Azure subscription (no free/trial) | Validation "1–7 business days"; many 2026 Q&A threads of EU sole traders failing without a reason ([Polish sole proprietor](https://learn.microsoft.com/en-us/answers/questions/5781004/identity-validation-failed-for-polish-sole-proprie), [Irish sole trader](https://learn.microsoft.com/en-us/answers/questions/5915697/can-an-irish-sole-trader-(non-incorporated)-qualif)); 3 tries, then refused | Yes: Microsoft's GitHub action with a login without a stored secret (OIDC); key never leaves Microsoft | Certificates live 72 h, so **timestamping is required** ([cert management](https://learn.microsoft.com/en-us/azure/trusted-signing/concept-trusted-signing-cert-management)). Publisher shows as the organisation name ("Fresing"). Microsoft's own recommendation |
| **OV / IV certificate, SSL.com + eSigner cloud** | OV or IV $129/yr + eSigner from $20/month for 20 signings (≈ $180/yr paid yearly) ≈ **$310/yr** ([eSigner pricing](https://ssl.com/guide/esigner-pricing-for-code-signing/), [IV](https://ssl.com/products/software-integrity/code-signing/iv/)) | OV: a registered business (KvK extract); **IV: a private person** (passport) – both fine from NL | Days (document checks) | Yes: SSL.com's CodeSignTool / eSigner in the workflow (credentials as GitHub secrets) | Since June 2023 the key must be on a hardware token or in the CA's cloud ([SSL.com](https://www.ssl.com/guide/esigner-pricing-for-code-signing/)). Certificates now max ~460 days |
| **OV, Sectigo / DigiCert** | Sectigo ≈ $220/yr via resellers, DigiCert ≈ $440/yr; plus their cloud key service (KeyLocker etc.) for CI ([SSL Insights](https://sslinsights.com/digicert-vs-sectigo-code-signing/), [ssldragon](https://www.ssldragon.com/ssl-certificates/code-signing/)) | Business (OV) | Days | Only with the CA's cloud signing (extra cost) or a self-run HSM | No advantage over SSL.com for us |
| **EV certificate** | ≈ $290–620/yr | Business, stricter checks | 1–2 weeks | Cloud/HSM | **No longer skips SmartScreen** (finding 3): not worth the extra |
| **Certum Open Source (cloud, SimplySign)** | from **€49** gross ([Certum shop](https://shop.certum.eu/open-source-code-signing-on-simplysign.html), [my-ssl](https://my-ssl.com/learn/open-source-code-signing-certificate)) | A private person; the certificate reads "Open Source Developer, <owner's name>" (his name becomes public) | Days | Awkward: SimplySign wants a phone code per session; workarounds exist, none checked | Resellers describe it as for **non-commercial** open source; Certum's own terms not read. A company using the app commercially makes this doubtful |
| **SignPath Foundation** (free) | €0 | OSI licence (GPL-3.0 ok), public repo, free downloads, **no proprietary component**, all team members with MFA, a public code-signing policy page, **manual approval per release** ([conditions](https://signpath.org/terms.html)) | Application; approval at their discretion | Yes (SignPath's GitHub connector) | Publisher shows as **"SignPath Foundation"**, not Fresing. The manual approval per release does not fit our automatic releases |
| **Do nothing + company IT allows it** | €0 | – | – | – | Works on managed PCs: allow Blender by its publisher (Stichting Blender Foundation), and our files by path (the install folder) or by hash. SAC on a home PC: the app falls back to Blender's launcher (works, says "Blender") |

**What to sign, and launcher vs signed copy:**

- **(a) Signed copy:** make `Fresing Render.exe` in GitHub's Windows job instead of on the PC. The byte work is
  already in `winexe.py`, and the resource API exists on the runner. Sign it there and ship it.
  + Task Manager, the window and "Open with" say "Fresing Render" (0178's goal), also with SAC on.
  − 113 MB more per new Blender version. Fresing becomes the publisher of a modified Blender binary: GPL allows that;
  the source offer is Blender's own public source plus `winexe.py`.
  − The app can no longer make it itself: a missing or old copy must be downloaded (a release asset, checked by
  SHA-256 like the updates).
- **(b) Small signed launcher** "Fresing Render.exe" (~100 KB) that starts the untouched, Blender-signed `blender.exe`
  without a console. This is the same thing `blender-launcher.exe` does.
  + Tiny, changes almost never (one signature, reputation builds once).
  − Task Manager names a process by its own file's description, so the **main process still shows "Blender"**. That
  is the same as today's SAC fallback. Grouping under a parent launcher was not checked; only a try on Windows can
  tell.
- **Recommendation: (a)**, because only (a) reaches 0178's goal. Plus signing the two `.ps1` files and the wheels'
  `.pyd`/`.dll` (only when they change). The zips need no signature: the updater already checks size + SHA-256, and
  Windows does not check zip signatures.
- **Updates:** nothing is re-signed on the PC (no key there, ever). An update only downloads already-signed files.
  The app's own local copy-making stays as the fallback for an unsigned build (forks, rehearsals) – and with SAC on,
  as now, the fallback is Blender's launcher.

**Ranked proposals:**

1. **Artifact Signing as the organisation "Fresing"** – ≈ $120/yr, about 1–2 weeks if validation passes, cheapest,
   Microsoft's own, no secret key in GitHub. Owner: Azure account with a credit card, the validation (KvK extract,
   ID + face check, possibly more documents), **only if Fresing is ≥ 3 years in the KvK**. Risk: EU sole traders are
   often refused without a reason.
2. **SSL.com OV (company "Fresing") or IV (owner's name) + eSigner** – ≈ $310/yr, days. Owner: buy, pass the document
   check, put the eSigner credentials into the repository's GitHub secrets himself (a worker never sees them). The
   fallback if 1 is refused or Fresing is younger than 3 years.
3. **Do nothing now, help company IT** – €0, today. The text below for `docs/COMPANY-USE.md`. Enough for a company with
   a willing IT department; not for SAC's name/icon.
4. Certum Open Source (€49) – only if Certum confirms in writing that commercial use by a company is fine; awkward in CI.
5. SignPath Foundation (free) – not recommended: the publisher is not Fresing, and every release needs a manual approval.
6. EV – not recommended (no SmartScreen advantage any more).

**Owner decides:**

- Is Fresing registered at the KvK, and **since when** (≥ 3 years → try 1; otherwise 2)? Eenmanszaak or B.V.?
- Budget: ≈ $120 (1) or ≈ $310 (2) per year.
- Signed copy (a, name kept, +113 MB per Blender version) or launcher (b, small, Task Manager says "Blender")?
  Recommendation: (a).
- Meanwhile: put proposal 3's text into `docs/COMPANY-USE.md` (0205 owns that file; the lead passes it on).

**Text for `docs/COMPANY-USE.md` (0205) – "For your IT department":**

> Fresing Render is Blender 5.2.3 LTS (the Blender Foundation's own build, from download.blender.org, checked by
> SHA-256) plus a Blender extension, installed for one user without administrator rights.
> - **Install folder:** `%LOCALAPPDATA%\FresingRender` (or the folder given with `-InstallDir`). Everything the app runs
>   lives there.
> - **Programs:** `blender.exe`, `blender-launcher.exe` and Blender's DLLs – signed by *Stichting Blender Foundation*;
>   allow by publisher. `Fresing Render.exe` – a copy of `blender.exe` with the app's name and icon, made on the PC at
>   install; **not signed** today: allow by path, or let the app use Blender's launcher (it does so by itself when
>   Smart App Control is on or the copy is blocked).
> - **Scripts:** `Install.bat` / `Uninstall.bat` start `Install-FresingRender.ps1` / `Uninstall-FresingRender.ps1`
>   with `-ExecutionPolicy Bypass`. Under an "AllSigned" Group Policy or AppLocker script rules, allow these two files
>   by path or hash, or install with an administrator.
> - **Python add-ons:** the extension contains unsigned Python modules (OpenCascade `OCP`, `manifold3d`) loaded by
>   Blender: under App Control for Business (WDAC) allow the install folder.
> - **Network:** `download.blender.org` (install), `github.com` / `objects.githubusercontent.com` (update check and
>   download; can be turned off and pointed at a file share with `Install.bat -UpdateUrl`).
> - **Checking a download:** each release page lists the SHA-256 of its files; the app checks every update's size and
>   SHA-256 before installing it.
> - **Who:** Fresing (the Netherlands), source code public under GPL-3.0-or-later at
>   github.com/smholte/CAD-render-animation. Security reports: see `SECURITY.md`.

(Lead: check the update hosts and that the release page lists SHA-256 values; if not, the build task below adds a
`SHA256SUMS.txt` to each release.)

**Brief text for the build task:**

> **NNNN – Sign Fresing Render on Windows** · Opus · effort High · Claude Code on the web · lead review before merge
> (Windows-only code, a key in GitHub's secrets).
> Goal: Windows trusts what we ship, so Smart App Control and company App Control let the app run under its own
> name. Owner has <Artifact Signing account "Fresing" | SSL.com OV + eSigner>; the credentials are in the repository's
> GitHub secrets (he put them there; the worker never reads or prints them).
> 1. **Make the copy in CI:** the Windows job builds `Fresing Render.exe` from the pinned `blender.exe` with
>    `winexe.py` (same bytes as on a PC), signs it (RSA, SHA-256, **timestamped**), and checks `Get-AuthenticodeSignature`
>    = Valid.
> 2. **Sign what changed only:** `Install-FresingRender.ps1`, `Uninstall-FresingRender.ps1`, the wheels' `.pyd`/`.dll`
>    and the exe are signed only when their unsigned SHA-256 is new. Otherwise the signed file comes from the previous
>    release (a release asset `signed-files-<hash>.zip`, checked). Signing runs **only** in the release jobs on
>    `main` – never on branch pushes or forks (no secret there; those builds stay unsigned and use today's
>    on-PC copy).
> 3. **Ship it:** the installer zip holds the signed exe. The app downloads a new signed exe (release asset, size +
>    SHA-256 checked like updates) only when the Blender version or `winexe.MAKER` changes. The on-PC copy-making stays
>    as the fallback for unsigned builds. With a signed copy, Smart App Control no longer turns the copy off: the
>    check becomes "the copy's signature is Valid".
> 4. **Tests:** the Windows job – signature Valid on the exe and both `.ps1`; install with `AllSigned` set for the
>    machine, as far as a runner allows; SAC simulated on → the copy is used. The PC check gets a line "Signature:
>    Fresing Render.exe signed by <publisher>, valid". Release rehearsal before merging.
> 5. **Docs:** `docs/COMPANY-USE.md` (publisher name, "allow by publisher"), `docs/UPDATES.md` (where the signing
>    happens, how to renew), CHANGELOG. `SHA256SUMS.txt` on every release.
> Not in it: a signed installer `.exe` instead of `Install.bat` (SmartScreen on the downloaded `.bat`) – a later task
> if companies ask.
> Owner checks on his PC with SAC on: the app starts as "Fresing Render" in Task Manager; Properties > Digital
> Signatures shows the publisher.

**Left open / not proven:** prices and rules were read from search quotes, not the full pages (fetching was blocked);
whether Artifact Signing accepts a Dutch eenmanszaak; Certum's commercial-use terms; whether the Azure action signs
`.ps1` directly (otherwise `Set-AuthenticodeSignature` with the SSL.com certificate, or the Artifact Signing dlib with
`signtool` – to check in the build task); whether `winexe.py`'s copy is byte-identical between runs (needed only for
allow-by-hash).
