# 0343 – Study (findings only): companies pay, private use stays free – a Fresing assets licence, prices and how to sell

**Who:** worker · **Status:** open – can start · **Branch:** `task/0343-study-paid-company-use` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 25 Nov 2026 13:5x (owner 13:4x: "could we make some changes to the additions made by Fresing to
make it paid for companies? (still way cheaper than other options). Companies could copy the app yes, but would need
to remove the Fresing assets, and such that we don't allow them to use." – then: "paid by all companies, like the other
suggestion (professionals)") · **Model:** Opus · effort High
**Area:** findings only. Reads the whole repository, the landing page and the briefs of 0205, 0206, 0269, 0286; changes
none of them. Report in this file on the branch, pick page in `tasks/0343_page/`. **No change** to `LICENSE`,
`README.md`, `THIRD-PARTY-NOTICES.md`, `docs/COMPANY-USE.md`, the site or app code. Not a code slot.

## Goal

The owner gets a checked plan, in plain words, for this model:

- **The software stays GPL-3.0-or-later** (it is a Blender extension – that cannot change).
- **Fresing's own non-code things** ("Fresing assets": looks / finishes, environments, HDRIs and 360° photos, sample and
  learning projects, presets, logos …) get **their own licence**: **free for private use, students and schools, and
  non-profits** (owner 25 Nov 13:5x), **paid for every company / professional use** (freelancers included – a cheaper
  freelancer price may be proposed), priced **far below** other render tools.
- A company may copy the GPL code, but then without the Fresing assets and without the Fresing name.

The report says what can carry such a licence today, what must change first, what the app is without them, what to
charge, how to sell it, and which build tasks follow – with choices on a pick page.

## Background

- **Owner's decisions so far (19–21 Nov):** GPL-3.0-or-later, stays a Blender extension, open source,
  donation-funded ("Support Fresing" / "Support Fresing Render"), Fresing-led then a foundation if it grows; no outside
  code (a CLA if ever); "Fresing" umbrella name, control through the trademark. **25 Nov he changes the money part:
  companies (professionals) pay, private use is free.** 0286's "Fresing standard – free for everyone" is therefore open
  again. Perpetual or yearly, and how many years of updates: **not decided** – the study proposes. A price idea from
  another chat (€299 one-time per user, one year of updates) is only an example.
- **What the GPL allows** (lead read 25 Nov – check each at its source): Blender's FAQ says Python scripts that use
  Blender's API must be GPL; Superhive (formerly Blender Market) "Understanding the GNU GPL" – a sale of GPL code covers
  only the download / service, the buyer gets the GPL freedoms; Superhive "Using mixed licenses" – add-on GPL, assets
  under another licence in their own folder with their own LICENSE; the Blender add-on guidelines (jlampel) – non-code
  assets need not be open source if the add-on runs without error without them. So: **no extra conditions on the code,
  no licence-key lock on the code** – the paid part can only be the assets (and services).
- **What the app ships today (lead, 25 Nov, `main`):** `fresing_render/` holds 405 `.py` files; `data/` (51 MB) is
  mostly test STEPs, `material_pictures/` (jpg), lifting data, a sample house; `brand/` the logos. **Most looks and
  finishes are made by Python code** (e.g. `cad_materials.py`, `materials.py`) – code is GPL, so those are not
  "assets" yet. Find out what would have to move from code into data (e.g. a `.blend` asset library of finishes and
  environments, the owner's own HDRIs / Insta360 photos) and what that costs.
- **Already published stays published:** whatever the public repository and the released versions carry under the GPL
  stays GPL for those versions. Check which Fresing-made pictures / files were published under which terms (the brand
  note in `THIRD-PARTY-NOTICES.md` says "all rights reserved" for the name and logos; its row 2 leaves `site/media/`
  open).
- **Third-party assets** (CC0 and others in `THIRD-PARTY-NOTICES.md`) can never be made paid – list them apart.
- **Name:** the README and the brand note keep the Fresing name and logos out of the GPL. The trademark is not
  registered (waits for the 2027 SME Fund round). Check what an **unregistered** name protects in the Benelux / EU and
  whether the paid plan makes registering more urgent.
- Related: `docs/COMPANY-USE.md` (one approved version, `.frsetup` set-up file), the About window's "Using it in a
  company" button (0206), 0286's asset-library study (layer "Fresing standard"), Fresing Viewer is MIT (0269). The app
  works **fully offline** – any licence check must work without internet (or there is none: invoice + licence file).
- Blender: the owner wants part of the income to support Blender later (Development Fund: individual from €5 / month;
  corporate Bronze €6,000, Silver €12,000, Gold €30,000 a year – check at fund.blender.org).
- The owner has **no lawyer, no accountant and no budget for them**; he builds the app outside work hours, so support
  promises must stay small. **Never name his employer** anywhere (repository, page, report) – "a company".

## Done when

- [ ] **Inventory:** every Fresing-made non-code thing in the app, installer, site and repository (finish / material
      pictures and textures, HDRIs and 360° photos, environments and surroundings, demo, test-tour and learning
      projects, lifting models, vessels, people, sounds, logos, splash, guide pictures and videos): code or data, where,
      size, who made it, published under which terms since which version. Third-party assets in a separate list.
- [ ] **What can become "Fresing assets"**, per item: ready as data / must move from code to data / must stay GPL; the
      work to move it (size, lanes it touches, risk), and **what the app looks like without them** – it must still run
      (GPL condition); propose a plain fallback look. Pictures of "with" and "without" for 2–3 models.
- [ ] **Licence for the assets**, plain words + a draft text marked "a lawyer may word it": who is free (private /
      hobby, students and schools, non-profits – owner's choice; define each so it is clear), who pays (every company,
      freelancers included), renders made with them (always
      the user's), passing assets on, a company copy without them. How others word it, checked at the source (e.g.
      Superhive mixed licences, BlenderKit, KitBash3D, Fab / Quixel, Twinmotion / Unreal EULA; Poly Haven CC0 for
      contrast). What is enforceable and what the GPL forbids.
- [ ] **How it ships:** assets in their own folder with their own LICENSE; in the installer or a separate download (GPL
      "aggregate"); whether paid assets stay in the public repository; how a company shows it has paid (invoice +
      licence file, no online check). A **list** of what the About window, `COMPANY-USE.md`, README and landing page
      would need to say (no edits).
- [ ] **Prices:** table checked at the source (with the date) – Twinmotion, KeyShot, Enscape or D5 Render, Rhino, and
      2–3 Blender add-ons for product / CAD visualisation on Superhive: per seat or per company, one-time or yearly,
      update terms. Propose 2–3 models (e.g. one-time per user with all updates of a major version; yearly per company;
      both) with example prices "far below the others", and say plainly these are proposals, not measurements.
- [ ] **Selling:** 2–4 web shops that act as **seller of record** (they handle VAT per country) suited to a small Dutch
      company: fees, payouts, B2B invoices with VAT numbers, checked at the source; the questions for an accountant
      (VAT, income, the donations kept apart). A **support plan** outline with small promises.
- [ ] **Name:** what an unregistered "Fresing" name protects (Benelux / EU) and the advice on timing.
- [ ] **Build tasks** that would follow (order, size, lanes), nothing started.
- [ ] Report below filled in; pick page `tasks/0343_page/index.html` (plain words, one question per block, recommended
      option first) pushed on the branch; the lead publishes it for the owner.

## Not in this task

Building anything; changing any licence file, the README, the site or `COMPANY-USE.md`; the asset-library build tasks
(0286); code signing (LATER); setting up donations or a shop account. Never the owner's STEP files or his employer.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
