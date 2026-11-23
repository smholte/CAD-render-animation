# 0288 – Study (findings only): learning from users to improve the app – "Send a report" now, opt-in anonymous statistics later

**Who:** worker · **Status:** open – can start · **Branch:** `task/0288-study-feedback-data` (branch only, never
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

- [ ] Report with sections A–F; every legal / pricing fact with its link and the date read (short quotes)
- [ ] Page `tasks/0288_page/index.html`: the report window mock-up, the consent question as it would look in the
      first-start set-up and in Settings, a table "what we collect / what we never collect", and the owner's choices
      as tick boxes with a Copy line (send route for step 1; hosting for step 2; keep-time; company default)
- [ ] Prototype on the branch: the report text built from a made-up usage file + PC-check block, with paths and names
      stripped – shown on the page
- [ ] Branch pushed with `[skip ci]`; report below filled in

## Not in this task

- No change to any existing file outside `tasks/0288*`; no merge, no release, no network code in the app.
- No server, account, domain or payment set up; no e-mails sent.
- Not the first-start set-up itself (0276) – only the question's words and place.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
