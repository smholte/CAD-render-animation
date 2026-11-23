# 0288 – Study (findings only): learning from users to improve the app – "Send a report" now, opt-in anonymous statistics later

**Who:** worker · **Status:** done – findings on the branch, for the lead · **Branch:** `task/0288-study-feedback-data` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 18:43 (owner 18:18: "Should we collect data on how to improve the app from users (no
data for selling), only for improving the app performance." – owner 18:43: "yes, I agree" to the lead's plan below)
· **Model:** Opus · effort High
**Area:** findings only. Prototype code in **new files only** on the branch (e.g. `core/report_proto.py`,
`tools/report_proto/`); reads `core/usage.py`, `blender/usage.py`, `blender/ops_usage.py`, `pccheck/core.py`,
`selftest.py`, `core/locations.py` (0272's `.frsetup`), `blender/welcome.py` + `tasks/0276-first-start-setup.md`,
`docs/COMPANY-USE.md`, `SECURITY.md` – changes none of them. Pictures and the page in `tasks/0288_page/`. Not a code
slot.

## Goal

The owner gets a clear, privacy-first plan – with the exact texts – for learning from real users how the app is used
and how fast it runs, **never for selling data**, in two steps:

1. **"Send a report" (now):** a button that shows the user, in plain words, a summary the app already has (version,
   PC, usage counts from *My usage*, speeds, the last crash / error) and lets him send it himself. Nothing leaves the
   PC without that click.
2. **Opt-in anonymous statistics (later, after the public launch):** **off by default**; if the user says yes (in the
   first-start set-up 0276 and in Settings), a small summary goes once a week to a Fresing server. A company can switch
   it off for everyone through its `.frsetup` (0272).

The report says what exactly to collect and what never, the consent and privacy texts, the company switch, where the
data goes and what it costs, how a user sees and deletes his data, and which build tasks follow.

## Background

- Owner's rules (23 Nov): only to improve the app and its speed; no selling, no content. The app is GPL, public,
  donation-funded; Fresing is a Dutch company (EU, GDPR). Many users will be companies; their IT reads
  `docs/COMPANY-USE.md` first ("what reaches the network – and only this").
- What exists: the **usage tracker** (0181: `<config>/fresing_usage.json`, clicks per function, active time per stage,
  "no network import – tested"), **My usage** + profile export (0181), the **PC check** text block and HTML report
  (0032), the **self-test** report, the learning list (0208), the welcome / What's new (0199), the coming **first-start
  set-up** (0276) and Settings window (0271 / 0272).
- An IP address or a stable machine id is personal data under the GDPR even without a name. The lead suggested
  consent (opt-in) as the basis, plain texts, data minimisation, and a check by the owner's accountant / a privacy
  advisor – **the study does not give legal advice**: it lists the questions and points to the official sources
  (EU / Dutch DPA "Autoriteit Persoonsgegevens"), checked at the source.
- Blender's own extensions and Fresing Render already reach the network only for named things (updates, Blender's
  extension repositories off by default – `ext_sync.py`): keep `bpy.app.online_access` as the first gate (CLAUDE.md
  section 8).

## What to find out

**A. What to collect – and what never.** A table: each item, why it helps (which decision it serves), how it is
reduced (buckets: "1,000–5,000 parts", not the count; GPU model family; seconds rounded), and whether it is in step 1,
step 2 or neither. **Never:** part / file / folder / project names, pictures, models, G-code, user or company names,
paths, exact timestamps of work, anything a client's design could be read from. Crash reports: the Python trace with
paths stripped – show a before/after on a made-up trace.

**B. Step 1 – "Send a report".** Where the button lives (Help menu, Fresing menu, after a crash, the PC check's
report), what the window shows (the exact text the user reads, a "Copy" and a "Save as file" choice), how it is sent
with no server of ours: e-mail with the text filled in, a GitHub issue form (the repository's `ISSUE_TEMPLATE`, 0205) –
also for users without a GitHub account –, or a plain file the user attaches. Compare them; pick one. A mock-up picture
of the window on the page.

**C. Step 2 – opt-in statistics.** The consent question (exact words, in the first-start set-up and in Settings), what
is sent and how often, a random id that the user can reset, **"Show what was sent"** and **"Delete my data"**; the
company switch in `.frsetup` (on / off / user decides) and how it shows; how it behaves offline, behind a proxy, with
`online_access` off; no retries that slow the app.

**D. Where the data goes and what it costs.** Two or three hosting options for a small EU-hosted endpoint (e.g. a
Supabase project in an EU region, a small EU VPS, a privacy-first analytics service), each with: price at 100 / 1,000 /
10,000 users, where it runs, how data is kept and deleted (keep raw data at most N days, keep only totals), who can see
it, and the work to keep it running. Facts checked at the source with links and the date read; no account sign-ups,
no payments.

**E. Privacy texts.** A draft privacy page for the site (plain words: what, why, how long, who sees it, how to say no,
how to delete, contact) and the lines for `docs/COMPANY-USE.md`'s network table – both in the report only, not
changed. The list of questions for the owner's privacy advisor / accountant.

**F. Build tasks.** Step 1 and step 2 as separate tasks in order, each with model · effort, files, lane and what it
waits for (step 1 beside or after 0276; step 2 after the public launch – owner decides), plus a PC-check line and a
test that proves nothing is sent without consent (the network blocked in the test; `usage.py`'s "no network import"
test kept for the counting itself).

## Done when

- [~] Report with sections A–F; every legal / pricing fact with its link and the date read (short quotes) – *done, but
      only Supabase's facts were read at the source; the others come from web-search summaries (this session's network
      blocks the pages) and are marked "search": open point 1*
- [x] Page `tasks/0288_page/index.html`: the report window mock-up, the consent question as it would look in the
      first-start set-up and in Settings, a table "what we collect / what we never collect", and the owner's choices
      as tick boxes with a Copy line (send route for step 1; hosting for step 2; keep-time; company default)
- [x] Prototype on the branch: the report text built from a made-up usage file + PC-check block, with paths and names
      stripped – shown on the page
- [x] Branch pushed with `[skip ci]`; report below filled in

## Not in this task

- No change to any existing file outside `tasks/0288*`; no merge, no release, no network code in the app.
- No server, account, domain or payment set up; no e-mails sent.
- Not the first-start set-up itself (0276) – only the question's words and place.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0288-study-feedback-data`; never merged, every
push `[skip ci]`.

**What changed:** only new files on the branch:
- `tasks/0288_page/index.html`, the page. It is made by `tools/report_proto/make_page.py` from
  `page_template.html` and has the report window mock-up, the consent question in the set-up and in Settings
  (normal and company-locked), the table of what is and is not collected, the trace before/after, the weekly
  summary, the hosting comparison, and the owner's choices with a Copy line.
- `tools/report_proto/` holds the prototype. `report_proto.py` builds the report text and the weekly summary from
  a made-up usage file, a PC-check block and a trace, with paths and names taken out. `test_report_proto.py` has
  50 tests. The `sample_*` files are made up.

No existing file was changed. TASKS.md is left to the lead.

**This is not legal advice.** Section E lists the questions for a privacy advisor or the owner's accountant.

### What "source" means below

This session's network allows only a few hosts. eur-lex, curia, edpb, autoriteitpersoonsgegevens.nl, supabase.com,
hetzner.com, aptabase.com, plausible.io, docs.github.com and docs.blender.org were all refused (DNS refused by the
proxy; three fetch helpers tried and got nothing). So:
- **read in the docs**: Supabase's own documentation, read through Supabase's documentation connector on 23 Nov
  2026. This is the source itself.
- **search**: what a web search on 23 Nov 2026 showed of the official page. It is a short summary or snippet, not the
  page as read. These facts are likely right, but must be checked on the page before anything is ordered or
  published (open point 1).

### A. What to collect – and what never

| Item | Decision it serves | Reduced to | Step 1 report | Step 2 weekly |
| --- | --- | --- | --- | --- |
| App + Blender version | which versions are in use; when to drop old ones | as is | yes | yes |
| Windows | which Windows to test | release name ("Windows 11 24H2") from the build number | yes | yes |
| Processor | which PCs are slow | family ("AMD Ryzen 9"), cores in steps (1–4 … 33–64) | yes | yes |
| Memory | can users hold big models | the usual size ("64 GB") | yes | yes |
| Graphics card | GPU vs CPU render, drivers to test | family ("NVIDIA RTX 40-series"); video memory in steps; the driver's main number (report only) | yes | family |
| Function counts (`fresing_usage.json`) | what matters, what to simplify, teach or drop | the app's function ids; step 2 = this week's difference | yes | yes |
| Active time per stage | where time goes (Import → Render) | 5 min (report) / 15 min (summary) | yes | yes |
| Hidden panels, pinned favourites | clutter and favourites | app ids | yes | no |
| Speeds: import, Build, render | speed work per PC kind and model size | parts in steps (under 100 … over 100,000), seconds to 2 digits | yes | yes |
| PC check | faults per PC, slower after an update | its text block, scrubbed again (step 1); counts + ids of slower lines (step 2) | yes | counts |
| Last error / crash | the faults users hit | trace with paths and names out (step 1); kind + place in the app's code (step 2) | yes | kind + place |
| A company set-up in use | how many users are in companies | yes / no – never its id, name, label or folders | no | yes/no |
| Workspace | kinds of work | built-in name or "own" | no | yes |
| Random id | count users, delete one user's rows | 128-bit random, made at the yes, reset by the user | no | yes |

**Never, in any step:** part, file, folder, project, workspace, set-up and company names; paths; pictures; models;
G-code; label and caption texts; user, computer and domain names; e-mail addresses; serial numbers, MAC address,
Windows' machine id; times of day (step 2 sends an ISO week); anything the user typed. The IP address is not stored
(section D: how).

**Speeds are new counters.** The usage file of 0181 has no part counts or durations. Build task A adds three timers
(import with its part count, Build animation, render per frame with its size and samples) to the usage file. Each
holds a few rounded values, kept as the last 10.

**Crash reports, before and after (prototype, made-up trace):**

```
before:  File "C:\Users\jdevries\AppData\Local\FresingRender\…\fresing_render\blender\joints.py", line 233, in create
         File "\\FILESRV01\eng\Klant Acme\scripts\my_helper.py", line 7, in fix
             print("Pump skid rev4 by jdevries@acme-offshore.com")
         KeyError: 'IMPELLER HOUSING 250-3 has no fr_rest_basis' while reading 'fr_rest_basis' of "Pump skid rev4"
after:   File "fresing_render/blender/joints.py", line 233, in create
         File "<other file>", line 7, in fix
         KeyError: '<text>' while reading 'fr_rest_basis' of "<name>"
```

The rules:
- A frame in the app's own code keeps its path from `fresing_render/` on and its source line; the code is public.
- A frame in Blender's own code becomes `blender:/modules/…`.
- Any other file becomes `<other file>` and loses its source line.
- Paths become `<path>`; this uses the PC check's own pattern, `pccheck.core._PATH`.
- Names the app knows on the PC become `<name>`: the user, the computer, the open project and its parts.
- Quoted text that is not one of the app's own words (`fr_*`, `FR …`, `fresing.*`, snake_case keys) becomes
  `'<text>'`.

A leak check looks for drive, UNC and home paths, e-mail addresses and the known names. 20 random traces in the
tests leave nothing.

### B. Step 1 – "Send a report"

**Where:**
- Help menu and Fresing menu: "Send a report…".
- After an error of a Fresing button: one status-bar line, "Something went wrong – Send a report…". The trace is
  caught where every `fresing.*` operator is already wrapped (`usage.wrap`, task 0181) and kept as the last 5
  in `<config>/fresing_errors.json`, scrubbed when written.
- After a crash: at the next start, once, "Fresing Render closed unexpectedly last time. Send a report…?" with the
  buttons [Send a report…] [Not now]. A crash is found from Blender's crash file. Blender writes a file named after
  the open `.blend` (`<name>.crash.txt`), or `blender.crash.txt`, in its temporary directory (search:
  [Blender manual, crash](https://docs.blender.org/manual/en/5.2/troubleshooting/crash.html): "Usually, this file is
  written in the Temporary Directory directory"). The app reads such a file only when it is newer than the last clean
  start; the build task checks the exact Windows place.
- The end of a PC check: "Send this result to Fresing…".
- Fresing > Settings… > My usage.

**The window, word for word:**

> **Fresing Render – Send a report**
> This report helps Fresing find faults and make the app faster. **You see everything it holds.** Nothing has been
> sent: you choose below what to do with it.
> [x] The app and the PC (version, kind of processor and graphics card) · [x] How you use the app (the counts from My
> usage) · [x] Speeds measured while you worked · [x] The last PC check (date) · [x] The last error (date)
> What you want to tell us (optional – do not write confidential names): [ text box ]
> [ the whole report as plain text – it changes with the ticks ]
> **[E-mail it…]** [Copy] [Save as file…] [Close]
> E-mail it… opens your own mail program with the report to report@<Fresing domain>. Check it, then press Send there.
> A problem anyone may read and answer: Report a bug in public on GitHub… (needs a GitHub account; version and Windows
> are filled in). What Fresing does with a report

The report text itself, made by the prototype, is on the page in section 1. It is 2,528 characters for the sample.
The user's own words are scrubbed against the known names too, and the window says "do not write confidential names".

**Routes compared** (page section 1):

| Route | Private | Account | Our server | Verdict |
| --- | --- | --- | --- | --- |
| E-mail with the user's own mail program (`mailto:`) | yes | no | none | **pick** |
| GitHub issue form (`bug_report.yml`) | **public** | GitHub | none | public bugs only; never the whole report |
| GitHub private report | yes | GitHub | none | security only (SECURITY.md) |
| A file the user attaches anywhere | the user decides | no | none | always there (Save as file…) |
| Upload to a Fresing server | yes | no | **yes** | that is step 2's question |

**Pick: e-mail.**
- It is private: a GitHub issue is public, and usage counts plus a PC description should not be.
- It needs no account and goes through the company's own mail, so firewalls are no problem.
- No server of ours runs.

**How "E-mail it…" works.** The report is 2,528 characters, or 3,774 when encoded in a link. A `mailto:` link that
long is not reliable in every mail program (not measured; the build task measures Outlook classic, new Outlook and
the Windows Mail app on the owner's PC). So the button does three things:
1. It copies the report to the clipboard.
2. It saves it as `Fresing-report-<date>.txt` and shows that file in Explorer.
3. It opens the mail program with only a short body: To, the subject "Fresing Render <version> report", and "The
   report is on your clipboard – paste it here (Ctrl+V), or attach the file Fresing-report-<date>.txt that Explorer
   shows."

On Windows the link opens with `os.startfile`, as the app already opens files and folders (`blender/files.py`).

**GitHub stays for public bugs.** The link fills in the form's fields by their `id`. Search
([form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema)):
"If provided, the `id` is the canonical identifier for the field in URL query parameter prefills". So the link is
`…/issues/new?template=bug_report.yml&version=0.2.203&windows=Windows+11+24H2&gpu=NVIDIA+RTX+40-series`. Only those
three fields; the user pastes what else he wants.

Fresing needs **one receiving address** (owner's choice).

### C. Step 2 – opt-in statistics

**The question in the first-start set-up (0276), at the end of step 3 "Your PC"**, word for word:

> **Help make Fresing Render faster?**
> If you say yes, the app sends a small summary to Fresing **once a week**: the app's version, the kind of PC (for
> example "NVIDIA RTX 40-series, 64 GB"), how often you used each function, how long imports and renders took, and
> where the app ran into an error. **Never** your models, pictures, file or part names, your name or your company's
> name. It is stored in the EU, only Fresing can see it, and it is never sold.
> It stays off unless you say yes. You can see every summary, stop at any time and delete what was sent: Fresing >
> Settings… > My usage.
> [Yes, share the weekly summary] [No, thanks] · Show an example summary · Privacy page

- The two buttons look the same and nothing is chosen in advance.
- Next stays grey until the user answers; "Skip set-up" counts as no.
- Users of an older version who never saw the set-up get the same box once, in What's new of the version that
  brings step 2.
- Never with `FRESING_NO_WELCOME`, in background runs, the queue, the PC check, a kit or the Client view.

**In Settings > My usage**, a block "Share anonymous statistics with Fresing" (page section 4):
- Off / On, with the date of the yes.
- "Last sent: week 47, 944 bytes · next: week 48 · stored in the EU (Frankfurt), kept 90 days, then only totals
  without your id".
- [Show what was sent…]: the last 8 summaries, kept on the PC.
- [Show what would be sent now…].
- [New random id]: the old id's rows are deleted first.
- [Delete my data at Fresing…]: deletes everything for this id, then switches off and throws the id away. Offline it
  waits and says "Delete waiting – it is sent when the PC is online".
- "Your random id: 7f3c…57d4 – made when you said yes; it is not linked to your name or your PC" and a Privacy page
  link.

**What is sent and how often.** The summary is on the page; 944 bytes for the sample (section A's items).
- The function counts are the difference from the totals last sent successfully. A week that could not be sent is
  counted in the next one, so nothing is lost or counted twice (`week_counts`, tested with a reset in My usage).
- Each summary carries `asked: "<version of the question's words>"`, so Fresing can show which text was agreed to
  (GDPR Art. 7(1): the controller must be able to show consent).

**The company switch** goes in `setup.json`'s `settings` (0272):
- `"share_statistics": "off"` or `"user"`. `"user"` is the default: each user decides.
- **"on for everyone" is not offered** until the advisor says a company may agree for its staff (question 4).
- "off" hides the question in the set-up. Settings shows "🔒 Switched off by the set-up "<label> v<n>" (Company).
  Ask your IT to change it." Show what was sent and Delete still work.
- `COMPANY-USE.md` names the setting.
- The `first_start` part of a set-up (0276) may also skip the question.

**How it behaves on the network:**
- **Gate 1:** the user's yes and no company "off".
- **Gate 2:** `bpy.app.online_access` (CLAUDE.md section 8). When it is off, nothing is sent and Settings says so.
- **When:** at most once per 7 days, 2 minutes after the start, in a helper thread, one try a day, a 5-second
  timeout, no retry loop. Nothing waits for it.
- **Proxy:** the same opener as the update check, so Windows' proxy setting applies (COMPANY-USE "Proxies"). A
  proxy that refuses means "not sent", and the next day it tries once.
- **Endpoint:** `https://stats.<Fresing domain>/v1/week` (POST, JSON, at most 8 KB) and `/v1/delete` (POST `{id}`).
  The address is our own name, so the host can change without an app update.
- **Never** a read endpoint: the app shows what was sent from its own copy.

**The server keeps the IP out.**
- The function reads only the JSON body.
- It checks the layout against the schema (unknown keys are refused).
- It stores `(id, week, received date, body)`. Sending the same week again replaces the row.
- At most one row per id per day.
- The host's own request logs still see the IP for their log time: Supabase Free 1 day (search, Supabase pricing
  page: "Log retention (API & Database) | 1 day"); Pro to be checked.

**Keeping:** a nightly job (Supabase `pg_cron`, or `cron` on Hetzner) adds rows older than the keep-time (owner's
choice, suggested 90 days) into weekly totals without an id, then deletes the rows. Delete-my-data removes all rows
of that id at once. The totals hold no id, so they cannot be traced back.

### D. Where the data goes and what it costs

Load: one send per user per week is about 43,500 sends a month at 10,000 users. A row is about 2 KB with indexes
(an estimate, not measured), so 90 days ≈ 3 MB / 26 MB / 260 MB for 100 / 1,000 / 10,000 users.

| | Supabase, Frankfurt (suggested) | Hetzner Cloud, Germany | Aptabase (not chosen) |
| --- | --- | --- | --- |
| 100 users | Free $0 | CX23 ≈ €5.49 + IPv4 ≈ €5.99 | Free |
| 1,000 users | Free $0, or Pro $25 | same | Free |
| 10,000 users | Pro $25 | same | $10 |
| where | eu-central-1 Frankfurt; contract with Supabase Pte. (Singapore), EU standard clauses; sub-processors in US / Singapore | Hetzner Online GmbH, Germany / Finland | EU region, Germany |
| keeping / deleting | our tables, our job; delete by id | our disk, our job | **up to 5 years, no deletion on request** → fails "Delete my data" |
| upkeep | almost none | updates, HTTPS, backups, watching: ~1–2 h a month (estimate) | none |

Facts and their sources:
- **Supabase Free pauses a project** (read in the docs,
  [project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)): "Supabase pauses Free Plan
  projects that show low activity over a 7-day period" and "Paid projects cannot be paused". 100 users sending
  weekly may not count as enough activity, so Free suits a pilot, not the live service.
- **Function calls** (read in the docs,
  [invocations](https://supabase.com/docs/guides/platform/manage-your-usage/edge-function-invocations)): quota Free
  "500,000", Pro "2 million", over-use "$2 per 1 million". The billing example there: "Pro Plan | 1 | $25 …
  Compute Credits | -$10".
- **Database size** (read in the docs, [database size](https://supabase.com/docs/guides/platform/database-size)):
  "Free Plan projects enter read-only mode when your database size exceeds 500 MB".
- **Backups** (read in the docs, [backups](https://supabase.com/docs/guides/platform/backups)): "Pro Plan projects
  can access the last 7 days of daily backups"; "Database backups are not available for download for Free Plan
  projects".
- **Supabase regions** (search, [regions](https://supabase.com/docs/guides/platform/regions)): "Central EU
  (Frankfurt) eu-central-1", also Paris, Zurich and Stockholm. Supabase's GDPR page advises picking a specific EU
  region.
- **Supabase DPA** (search, [DPA](https://supabase.com/legal/dpa)): it "supplements … the Supabase Terms of Service
  … between the Customer and Supabase Pte." and uses the SCCs of "Commission Implementing Decision (EU) 2021/914".
  The search found no Data Privacy Framework entry. The transfer assessment lists the US and Singapore. Advisor
  question 6.
- **Hetzner** (search, [price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/),
  third-party reviews): prices rose on 15 June 2026. CX23 (2 vCPU, 4 GB, 40 GB) costs "€5.49/month in the EU", or
  "€5.99/month … including IPv4, excluding VAT". It could not always be ordered in September–October 2026, and the
  next type up was CPX22 at about €19.99. **Check before ordering.**
- **Aptabase** (search, [pricing](https://aptabase.com/pricing), [privacy](https://aptabase.com/legal/privacy)):
  free up to 20,000 events a month, 200,000 for $10. "EU (Germany)". IP and user agent are "processed only in memory
  and never stored". Data is "kept for up to 5 years and users can't request deletion".
- **Plausible** (search, [plans](https://plausible.io/docs/subscription-plans)): from about $9 a month. It counts
  page views on websites, so it is not a fit.

**Suggestion: Supabase in Frankfurt.**
- Start Free for a pilot on Fresing's own PCs, then go Pro ($25 a month) when it goes live.
- It sits behind our own domain, so moving to Hetzner later is an export plus a DNS change.
- The lead and workers can set it up and look at it with the Supabase connector, and nothing needs patching.
- **If the advisor finds the Singapore / US contract a problem, take Hetzner** (EU company, no transfer) and
  accept the upkeep.

No account was made, nothing was ordered.

### E. Privacy texts

**Draft privacy page for the site** (`site/privacy/index.html`; plain words; to check with the advisor):

> **Fresing Render and your data**
> *Who:* Fresing (the company behind Fresing Render), [address, KvK number], [contact address].
> *Without your yes, nothing about you leaves your PC.* Fresing Render counts which functions you use, to show you "My
> usage". Those counts stay on your PC. The app contacts the internet only to check for updates (you can switch that
> off) and, if you say yes, for the weekly summary below.
> **1. Reports you send us yourself.** "Send a report" makes a text you can read in full. You send it with your own
> mail program. *What:* app version, kind of PC, counts of functions, speeds, the last PC check and error – with
> folder, file and part names taken out – plus whatever you write and your e-mail address (your mail program adds
> it). *Why:* to fix the fault you report and improve the app. *Basis:* you send it to us (consent, GDPR Art. 6(1)(a)).
> *Kept:* until the question is answered, at most 12 months, then deleted. *Who sees it:* Fresing only.
> **2. The weekly summary (only if you said yes).** *What:* the items listed in Settings > My usage > "Show what would
> be sent now", with a random id that is not linked to your name or PC. Never your models, pictures, names of files,
> parts, projects or people. *Why:* to see which functions are used, which PCs are slow and which errors happen, so
> we can make the app better and faster. **Never sold, never used for advertising, never combined with other data.**
> *Basis:* your consent (GDPR Art. 6(1)(a)); you can withdraw it at any time, as easily as you gave it (Art. 7(3)).
> *Where:* [Supabase, Frankfurt, Germany / Hetzner, Germany]. *Kept:* 90 days with the id; after that only totals
> without any id. *Your internet address:* our server sees it while it answers, like every website, but does not
> store it; [the host keeps its request logs for N days].
> **Stop and delete.** Fresing Render > Settings… > My usage: switch it off; "Delete my data at Fresing" deletes
> everything sent with your id at once; "New random id" starts again with a new one. You can also write to us.
> **Your rights.** You may ask what we hold, have it corrected or deleted, and complain to the Autoriteit
> Persoonsgegevens (autoriteitpersoonsgegevens.nl). We cannot find data by your name, because we do not have it: give
> us the id shown in Settings.
> **Companies.** IT can switch the summary off for all its PCs (the set-up file, see "Using Fresing Render in a
> company").
> *Changes to this page are dated; a change in what is sent asks you again.*

**Rows for `docs/COMPANY-USE.md`'s network table** (not changed here):

| # | What | When | Where to | In the code |
| --- | --- | --- | --- | --- |
| 7 | **Report e-mail** – the app opens the user's own mail program with a short text; the report is on the clipboard or in a file next to it. The app sends nothing; the user presses Send. | only when the user clicks **E-mail it…** in Send a report | the user's own mail server, to Fresing's report address | (build task A) |
| 8 | **Weekly statistics** – one summary of ≤ 8 KB (shown in full in Settings), random id, no names or paths | **only after the user said yes**; at most once a week, 2 min after a start; never with Blender's online access off; **switch it off for every PC with `"share_statistics": "off"` in the set-up file** | `https://stats.<Fresing domain>/v1/week` (+ `/v1/delete` when the user deletes) | (build task B) |

Also a line under "What never reaches the network": "no telemetry" becomes "no telemetry without the user's yes
(row 8)".

**Questions for the privacy advisor / the owner's accountant:**
1. Is consent (Art. 6(1)(a)) the right basis for the weekly summary, or would legitimate interest (Art. 6(1)(f))
   also hold? The plan uses consent either way, and the summary stores a random id on the PC and sends it back:
   ePrivacy Art. 5(3) / Telecommunicatiewet art. 11.7a (search: EDPB
   [Guidelines 2/2023 v2](https://edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf),
   final 7 Oct 2024, names "information", "terminal equipment" and "gaining access" as the conditions).
2. Is the weekly summary with a random id personal data? Recital 30 names "online identifiers … such as internet
   protocol addresses, cookie identifiers" (search: [recital 30](https://gdpr-info.eu/recitals/no-30/)); the plan
   treats it as personal data.
3. Are the set-up texts above valid consent: informed, specific, an active choice, equal buttons? Search: CJEU
   Planet49 C-673/17 ([press release](https://curia.europa.eu/jcms/upload/docs/application/pdf/2019-10/cp190125en.pdf)),
   a pre-ticked box is not valid consent; recital 32: "Silence, pre-ticked boxes or inactivity should not … constitute
   consent".
4. May a **company** switch the summary **on** for its staff? (Employee consent is seldom free; the company would
   then be the controller and Fresing its processor, with a processing agreement.) Until then, only "off" / "user
   decides".
5. Does Fresing need a register of processing activities? Search (business.gov.nl,
   [processing register](https://business.gov.nl/regulation/when-do-you-need-processing-register); European
   Commission SME page): under 250 employees not always, "tenzij de verwerking een regelmatige activiteit is". A
   weekly summary is regular, so probably yes. A short one is no burden.
6. Supabase: the contract is with Supabase Pte. (Singapore) under the SCCs, with sub-processors in the US and
   Singapore, while the data sits in Frankfurt. Acceptable, or Hetzner?
7. Keep-times: 90 days with the id and totals for ever; 12 months for e-mailed reports. Fine?
8. Who supervises what in the Netherlands for this case (AP for the GDPR, ACM for art. 11.7a; search: a government
   answer on [the split](https://zoek.officielebekendmakingen.nl/ah-tk-20192020-958.pdf)), and does anything change
   for users outside the EU (UK, Norway, US)?
9. The privacy page's contact data: is a KvK number and a postal address needed on the page?
10. VAT and bookkeeping (accountant): a US/Singapore service billed in dollars ($25 a month): reverse charge? This
    is about the bookkeeping only.

### F. Build tasks (in order; the lead numbers them)

**Task A – "Send a report"** (Opus · Medium; Start & learn lane; after 0276, or beside it if 0276 does not touch the
Fresing menu in `ui_topbar.py`). New `core/report.py`, made from the prototype: buckets, `strip_trace`, `leaks`,
`report_text`; it imports no network library (AST test as in `tests/test_usage.py`).
- `core/usage.py` / `blender/usage.py`: the three speed timers, and the last 5 errors caught in `usage.wrap` into
  `fresing_errors.json`, scrubbed when written.
- New `blender/ops_report.py`: the window as an output window (0260/0271 pattern), Copy, Save as file…, E-mail it…
  (clipboard + file + `mailto:` via `os.startfile`), the GitHub link with field prefills.
- The places: Help and Fresing menus, the status-bar line after an error, the start after a crash (Blender's crash
  file newer than the last clean start), the end of the PC check, Settings > My usage.
- A function entry, a guide section, a tour stop, a PC-check line `report.text`. That line builds the report from
  the real usage file of that PC with the PC's user and computer names as secrets, and fails on any leak.
- `COMPANY-USE.md` row 7. CHANGELOG.
- **The test that nothing is sent**: every path of the window runs with `socket` blocked, and `os.startfile` /
  `webbrowser` are stubbed and only called on the click.
- Measure on the owner's PC: Outlook classic, new Outlook and Mail with the short `mailto:` text.
- Waits for: the owner's address for reports.

**Task B1 – the statistics server** (Sonnet · Medium; a new lane "Statistics"; after the owner's choices and the
advisor's answers).
- The owner makes the account (Supabase organisation or Hetzner) and the DNS name `stats.<domain>`.
- The worker writes the table, the Edge Function (schema check, 8 KB cap, one row per id per day, no IP stored),
  `/v1/delete`, and the nightly totals-and-delete job.
- Tests against a local Supabase (`supabase start`) or SQLite, and a page for the owner with the weekly totals
  (read-only).
- Waits for: the hosting choice and the advisor.

**Task B2 – opt-in statistics in the app** (Opus · High; Statistics lane; after B1, A and 0276; **after the public
launch – the owner decides when**).
- New `core/stats.py`: the state file `fresing_stats.json` (yes/no + date + question version, id, totals last sent,
  last 8 summaries, delete waiting), the summary (from the prototype's `weekly_summary`), the schedule rules.
- New `blender/stats.py`: the helper thread, `online_access` gate, 5 s timeout, one try a day, the update check's
  opener and proxy.
- The question's step in 0276's set-up window, and the What's new box for earlier users.
- The Settings block in the My usage tab of `ui_settings.py`.
- `share_statistics` in `core/locations.py`'s set-up settings, with its lock line.
- The site's privacy page, `COMPANY-USE.md` row 8, the guide, the function entry, a PC-check line `stats.consent`.
  That line proves no request with the answer "no" or with "off" from a set-up file, and with "yes" exactly the
  shown JSON to a local test server.
- A tour stop (the Settings block).
- **Tests**, with `socket` blocked:
  - without a yes nothing is sent; with a company "off" nothing is sent; with `online_access` off nothing is sent;
  - offline: one try, no loop, the app's start not slowed (timed);
  - the summary sent equals "Show what was sent";
  - delete works offline and later;
  - `usage.py`'s "no network import" test stays: the counting itself never gets network code – only
    `blender/stats.py` sends.
- **Windows review** by an independent agent (network and threads on Windows), as section 6 asks.

**Tested and measured** (4-core web machine, Linux, made-up samples):
- `~/venv/bin/python -m pytest -q tools/report_proto` – **50 passed** in 0.12 s. It covers: no network import; the
  report and the summary built with `socket` blocked (any connect or getaddrinfo fails the test); no known name,
  path or e-mail left in the report, the summary or the trace; the samples do hold those names before; 20 random
  traces; buckets; week counts after a reset; summary keys and size.
- Sizes: the report is 2,528 characters (3,774 encoded as a link); the weekly summary is **944 bytes**.
- The page was opened in Chromium at 1100 px and 390 px: no sideways scroll, and the Copy line works.
- Nothing was measured on the owner's PC; no mail program was tried.

**Subagents:** three fetch helpers were to read the legal, pricing and GitHub/Blender pages at the source. All three
got nothing: the hosts are refused by this session's network. They were replaced by web searches and Supabase's
documentation connector, as marked above. No other subagents; the code and the page were written by this session.
No independent review of the prototype (it is a study prototype; task A's real code should get one).

**Open points / follow-up tasks:**
1. **Facts marked "search" must be read on their pages** before step 2 is ordered or the privacy page goes up: the
   law (eur-lex, curia, edpb, AP), Hetzner, Aptabase, Plausible, GitHub, Blender. The lead can do it in a chat with
   web access, or the environment can allow those hosts. The Supabase facts were read at the source.
2. The owner's choices: the Copy line on the page (route, address, hosting, keep-time, company default, when,
   advisor).
3. The advisor's answers to section E's questions, before task B2. Task A may go ahead first: it sends nothing
   itself.
4. Panel class names (`FRESING_PT_lifting`) show raw in the prototype's report; task A shows their titles from
   `core/places.py`.
5. The `mailto:` limits and the Windows crash-file place are not measured – task A measures them.
