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

**Chat / date:** Claude Code on the web, 25 Nov 2026. Branch `task/0343-study-paid-company-use` (pushes `[skip ci]`,
never merged). App on the machine: `main` at 0.2.248. Not legal or tax advice – the lawyer / accountant questions are
listed.

**What changed:** only this report and the pick page `tasks/0343_page/` (index.html + 3 pictures). No licence file,
README, site, `docs/COMPANY-USE.md` or app code touched.

### In short

1. **The plan is allowed** – GPL code, Fresing's own non-code files under their own licence, in their own folder, the
   app running without them (GPL §5 "aggregate"; Lampel's add-on guidelines; quotes in section C).
2. **The hard part: almost none of Fresing's "assets" are assets today.** The 87 library materials, 43 ready-made
   colours, 25 finishes, 5 light looks (their studio light pictures are drawn by code at every start), 11 weather
   presets, 11 surroundings, props, people, the demo, the test tour and the lessons are **Python code**, and the
   extension has said `SPDX:GPL-3.0-or-later` in its manifest since its first release (v0.2.16, 5 Nov; checked in the
   tags). **All 232 releases up to 0.2.248 carry them under the GPL for ever** – a company may keep 0.2.248 with every
   look, legally and free. The paid licence can therefore only cover **new things made as data from now on** (the
   owner's own HDRIs and 360° photos, hand-made finish / environment libraries, learning projects) – or looks taken out
   of a *future* version's code, which the old versions keep anyway.
3. **What companies pay for** is then: the Fresing assets pack (new value), the Fresing name (official builds only;
   trademark), the installer + updates, and a small support promise. Payment is by **invoice + licence file, no
   online check, no lock** (a fee for running GPL code is not allowed: GPL §10).
4. **Price proposal (not a measurement):** one-time **€129 per company user**, **€59 freelancer**, with all updates of
   the pack's 1.x (promise ≥ 2 years); seat packs 5 / 10 users. Compare (official pages, 25 Nov 2026): KeyShot Studio
   USD 1,299–1,599 / year, Enscape USD 460–585 / year, Rhino 9 USD 995 once; Blender add-ons on Superhive USD 15–89.
5. **Shop:** Paddle (merchant of record, 5 % + 50¢, B2B reverse charge, it sends *you* a "reverse invoice") first;
   Gumroad (MoR, licence keys with seats, 10 % + $0.50) as the fallback. Lemon Squeezy is closing (stops 31 Mar 2027).
6. **Name:** an unregistered name gives next to nothing outside your own region (BOIP: "You only actually own your name
   or logo if you have registered your trademark"). Selling under it makes registering **more urgent**: Benelux classes
   9 + 42 = **€271** for 10 years. The 2026 SME Fund vouchers closed on 19 Nov 2026.

### A · Inventory – what Fresing made, and how it is published

"Published" = in the public repository and/or in a release zip. The extension's manifest declares GPL-3.0-or-later since
2 Nov 2026 (first release v0.2.16, 5 Nov); `LICENSE` file since 18 Nov (task 0205, first in 0.2.158). Repository public
since 1 Nov 2026. Sizes from `du` on `main` 0.2.248.

| # | What | Code or data | Where | Size | Made by | Published as, since |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Library materials (87), ready-made colours (43), categories, tags | code (dicts) | `core/materials_lib.py`; nodes by `blender/materials.py` | 751 + 750 lines | AI for Fresing | GPL, 0.2.16 (grown since) |
| 2 | Finishes (25: knurl, spun, tread plate, fabric, hammertone …), adjust sliders, wear / rust | code | `core/finishes.py`, `blender/finishes.py`, `core/look_adjust.py` | ~1,600 lines | AI | GPL, 0.2.229 / 0.2.237 / 0.2.245 |
| 3 | Material pictures (103 jpg, one per built-in) | **data**, rendered by the app from #1–2 | `data/material_pictures/` | 0.9 MB | app (code) | GPL (in the extension), 0.2.241 |
| 4 | Tool marks, cable looks, marine growth, CAD colours, RAL table | code | `toolmarks.py`, `cable_looks.py`, `marine_looks.py`, `cad_materials.py`, `ral.py` | – | AI | GPL; RAL is RAL gGmbH's name – the table is approximations |
| 5 | Light looks (5) – their studio light pictures ("FR Light product studio" 2048 px …) | code, pictures **drawn at run time** | `core/studio.py`, `blender/world.py` | – | AI | GPL, 0.2.13 |
| 6 | Weather presets (11), sky, sea (wave spectrum), seabed, snow | code | `core/weather.py`, `core/sea.py`, `blender/world.py` | – | AI | GPL |
| 7 | Surroundings (11 kinds: sea, deck, quay, halls …), props (7 + detailed), people (rig, 6 poses, outfits, actions) | code (meshes made at run time) | `core/surroundings.py`, `props_detail.py`, `people.py`, `blender/surroundings.py` | ~6,500 lines | AI | GPL |
| 8 | **HDRIs / 360° photos** | – | **none ship** (the user's own; `docs/SURROUNDINGS.md` links free ones) | – | – | – |
| 9 | Sounds / music | – | **none ship** (the user's own) | – | – | – |
| 10 | Demo project "Vessel in a wind park" | code (built on the PC) | `demo_model/`, `blender/demo.py`, `demo_park.py` | 228 KB code | AI | GPL |
| 11 | Test tour (55 sets, 116 stops), lessons (crane 12, mill 13, weather 4 steps) | code + test models | `blender/tour.py`, `blender/lessons/` | – | AI | GPL |
| 12 | Test models (49 STEP, 1 glTF) | **data**, made by GPL makers in `tools/` | `data/*.step`, `tests/data/` | ~39 MB | makers (code) | GPL (extension); the glTF / OBJ say "CC BY 4.0" (`tools/make_test_mesh.py`) |
| 13 | Built-in crane classes (12: AT / CC / KB) – STEP, chart json, picture | **data**, made by `lifting_model/` | `data/lifting/` | 12 MB | makers (code) | GPL, 0.2.~170 (task 0191) |
| 14 | Decal art (CE mark, warning signs, arrows, type plate), brand-kit title / end cards | code | `core/decal_art.py`, `core/brand.py` | – | AI | GPL (the CE mark and ISO-style signs are not Fresing's designs) |
| 15 | Part-type words (63 types, 86 groups), rule sets, presets, chip presets | code (data in code) | `core/part_types_data.py`, `rule_sets.py`, `presets.py`, `chips.py` | – | AI | GPL |
| 16 | Sample house | data | `data/sample-house.hpscene` | small | `house-scene-format` makers | that repository has **no licence file** (0205 point 3) |
| 17 | Web viewer `fr_*.js` | code | `web/` | – | AI | GPL (0269: shared page files to be dual GPL / MIT) |
| 18 | **Logos, app icon, splash** | data | `brand/`, `site/brand/`, `app_template/…/splash.png` | 0.4 MB | Fresing | **"not licensed for other products"** (brand note, 18 Nov) – already outside the GPL |
| 19 | Landing-page media of Fresing's own (milling video, test-mill 3D page) | data | `site/media/` | part of 22 MB | Fresing | "all rights reserved unless the owner says otherwise" (brand note) |
| 20 | User guide pictures (178), task report pictures | data | `docs/img/` (6.9 MB, guide ships in the zip), `tasks/img/` (19 MB, repo only) | 26 MB | app + AI | guide: in the extension (GPL); "Fresing's own" in THIRD-PARTY-NOTICES – no explicit licence |

**Third-party, never paid** (from `THIRD-PARTY-NOTICES.md`): Blender (GPL), OpenCascade / OCP / manifold3d and their
bundled libraries (LGPL / Apache / BSD …), three.js, meshoptimizer (MIT), model-viewer (Apache-2.0), IBM Plex fonts
(OFL), Thor and CEB press pictures (CC BY-SA 4.0), IEA 15 MW (Apache-2.0), render-kit models (CERN-OHL-S, FarmBot "CC0"
unconfirmed), the Toolbox format files (MIT, Fresing's own). And everything 0286 plans from outside: Poly Haven and
ambientCG (CC0), Blendkit (their licence, their add-on). **No third-party picture, HDRI, sound or model ships in the app
today** – so nothing third-party has to be taken out.

### B · What can become "Fresing assets"

| Item | Verdict | Work to move it | What the app does without it |
| --- | --- | --- | --- |
| Owner's own HDRIs / 360° photos (new) | **ready as data** – the cleanest asset (his own photographs) | small: shoot, check, pack (0286 listed the first ones: studio, overcast, hall, harbour, yard) | Blender's sky / the code's studio looks (as today) |
| New hand-made finish / material library (`.blend` node groups + textures from own photos or scans) | **new data** | medium–large per set (Looks lane); 0273's picker already reads material folders | the GPL library (#1–2) |
| New environments (hall, quay, showroom as `.blend` asset libraries) and learning projects (realistic machines) | **new data** | medium (Surroundings / Start & learn lanes); demo kits (0228) already load a project pack | the code surroundings, crane / mill lessons |
| Today's finishes, wear / rust, light-look pictures (#2, #5) | **must move from code to data** – possible for future versions only | large, high risk: Looks lane, 0274 / 0318 / 0314 tests, tour stops, PC-check lines, material pictures; 0.2.248 keeps them GPL anyway | plain look (below) |
| Library materials #1, colours, RAL | **stay GPL** – the base every model needs; a list of roughness values is close to facts (weak protection) | – | – |
| Weather, sea, surroundings, props, people, decal art, part words, crane classes, test models, tour, lessons, demo | **stay GPL** – behaviour / test data, generated by GPL code, needed by the tests | – | – |
| Material pictures #3 | follow #1–2 (made from them) | – | – |
| Logos, icon, splash | **already outside the GPL** – brand, not an asset licence | – | a fork uses its own |
| Guide and site pictures | not part of the paid plan (they sell the app) | – | – |

**The app without the pack – a plain fallback look.** Measured on this machine (4-core web machine, Cycles on the
processor, preview quality, 640 × 400, ~20 s each): the same test model with the app's looks, and with a "plain" look =
every material replaced by Blender's own Principled BSDF with only its colour, metal and roughness numbers, Blender's
grey world and one sun (scratch script, no app code). Pictures on the page: test crane, test mill, finishes model. The
crane and the mill look nearly the same; the finishes model loses its tread plate, grilles, knurls and textures. So:
**the app runs and gives clean pictures without the pack; the pack adds the surface detail and the light** – that is
the "plain fallback" proposal (keep colour + shine, drop textures and finish node groups, Blender sky / one plain
studio). Note: today these looks are GPL code, so the "without" pictures show what a *future* version would look like if
they were moved into the pack.

**Risk for the lawyer (not checked at a source):** copyright needs a human's own creative choices; assets made mostly
by an AI tool or rendered automatically may be weakly protected in the EU. The owner's own photographs are clearly his.
Prefer assets where his own hand and eye are in it.

### C · Licence for the assets

**What the sources say** (read 25 Nov 2026 with curl; quotes short):
- GPL-3.0 §5 (gnu.org/licenses/gpl-3.0.html): separate works "which are not by their nature extensions of the covered
  work … is called an 'aggregate' … Inclusion of a covered work in an aggregate does not cause this License to apply to
  the other parts". §10: "you may not impose a license fee, royalty, or other charge for exercise of rights granted under
  this License".
- GNU FAQ (gnu.org/licenses/gpl-faq.html): #DoesTheGPLAllowMoney "The right to sell copies is part of the definition of
  free software"; #DoesTheGPLAllowRequireFee "You can't require people to pay you when they get a copy from someone
  else"; #GPLOutput "the copyright on the output belongs to her, not you"; #MereAggregation – aggregates with non-free
  parts are allowed; where one program ends "is a legal question".
- Lampel, Blender add-on guidelines (jlampel.github.io/blender_add-on_guidelines/09_licensing.html): "Assets made for or
  with Blender that are not code, however, do not necessarily need to be open source … icons, images, models, scenes, or
  node groups"; "the add-on must be able to run without error … with or without them"; "ok for the add-on to detect that
  an asset … is avaliable and change its behavior"; the licence "in a text document at the top level of the distributed
  folder and … communicated to users before they purchase or download".
- Blender manual, Extension licenses (docs.blender.org/manual/en/latest/advanced/extensions/licenses.html): add-ons
  GPL-3.0-or-later; "For assets used in add-ons, the required license is Public Domain (CC0)" → **the pack can never be
  listed on extensions.blender.org** (Fresing Render ships from GitHub – no change).
- Superhive (superhivemarket.com/page/gpl-license): "All code-based products on Superhive are licensed either under the
  GNU General Public License … or as MIT." Its "mixed licenses" support article could not be opened (old host gone).
- Fab EULA (fab.com/eula): Personal and Professional tiers "grant you the same scope of rights"; "no need for upgrading …
  if you cross the revenue threshold after the purchase"; you may "Commercially distribute your Projects with the Fab
  assets incorporated", not "Resell or redistribute the asset … on a standalone basis". **Closest model** to this plan.
- Poly Haven (polyhaven.com/license): CC0 – "in any way and for any purpose, including commercial purposes".
- Creative Commons FAQ: NC is "primarily intended for or directed toward commercial advantage"; "does not turn on the
  type of user" → **CC BY-NC does not fit** "free for non-profits, paid for every company": a licence of our own that
  defines *users* is needed. CC allows NC + commercial permission for payers.
- Not readable from here: blender.org licence FAQ (Cloudflare), Twinmotion / Unreal EULA (Cloudflare), Blendkit and
  KitBash3D (proxy). 0286's report has Blendkit's terms (Full plan for ≤ 5 employees / ≤ $100k revenue, Business above,
  [search]).

**Plain words.** Free: (1) **private / hobby** – a person for themselves, not for paid work; (2) **education** – pupils,
students, teachers and researchers of a school, university or training centre, for learning, teaching and research, not
paid client work; (3) **non-profits** – a registered charity, association or foundation for its own work that is not
sold. Paid: **everyone else** – any business, a one-person business / freelancer included, and any paid work for a
client. Renders, videos, pictures and web pages made with the assets are **always the user's**. A project file with the
assets inside may go to a client (they open and render that project). The assets may not be passed on on their own. A
copy of the GPL code is fine, without the assets folder and without the Fresing name / logos.

**Draft – a lawyer may word it ("Fresing Assets Licence 1.0"):**

> 1. **What it covers.** The files in the folder `fresing_assets` and any pack named "Fresing Assets": pictures,
>    HDRIs, 360° photos, materials, environments and projects, © Fresing. Not the Fresing Render software (GPL-3.0-or-later)
>    and not files of others (their own licences, listed in the pack).
> 2. **Free use** – no payment needed: (a) a person for private use, not for paid work and not for a business;
>    (b) pupils, students, teachers and researchers of a school, university or training centre, for learning, teaching
>    and research, not for paid work for a client; (c) a registered non-profit organisation, for its own activities
>    that it does not sell.
> 3. **Company use** – all other use, by or for a business (a one-person business or freelancer included) or for paid
>    work, needs a paid licence: one per user (a person who uses the assets), or the number of users on the invoice.
> 4. **You may** use the assets in your projects; everything you make with them (pictures, videos, web 3D pages,
>    prints) is yours, also to sell, without credit; send a project with the assets inside to a client or partner so
>    they can open and render that project.
> 5. **You may not** sell, give or publish the assets on their own or in another library, pack or product; remove this
>    licence or the file that names the licensee.
> 6. **Copies of the software.** The GPL lets anyone copy and change Fresing Render. This licence does not let a copy
>    given to others include the assets, or use the Fresing name and logos.
> 7. **Proof.** Your invoice and licence file (company, users, invoice number). There is no online check.
> 8. **No warranty**; Fresing's liability is limited to the price paid. Dutch law applies.
> 9. **Ending.** The licence ends if you break it and do not put it right within 30 days of being told.

**What is enforceable / what the GPL forbids.** Enforceable: copyright in the asset files (strongest for the owner's
own photographs), the licence as a contract with each buyer, the brand (only once registered, see G). In practice:
a friendly letter; no small company sues over €129 – the plan rests on companies paying a fair price when asked plainly.
**Forbidden by the GPL:** any condition or fee on running, copying or changing the code (§10), a licence key or lock in
the code, assets the code needs to run, assets put inside code files. **Allowed:** charging for the download / the
pack / support, a licence file the app only *shows* ("Licensed to …").

### D · How it ships

- **Own folder, own licence:** `fresing_assets/` with `LICENSE-ASSETS.txt` at its top, never inside `fresing_render/`'s
  code; the app checks for it and changes behaviour (Lampel's "detect … and change its behavior").
- **Recommended: a separate download**, like the demo kits (0228: Help > Add a demo kit…): free from the landing page
  for private / education / non-profit users (the licence in front of the button), and from the shop for companies.
  Alternative: in the installer for everyone, the licence decides (simpler for private users, but every company gets
  the files without a step that reminds it).
- **Not in the public repository:** a private repository (`fresing-assets`, like `fresing-render-vessel`) builds the
  pack zip; the public CI never needs its token. The public app knows only "an assets pack" (as it knows only "demo
  kits").
- **Proof of payment:** invoice from the shop + a licence file `fresing-licence.json` (company, users, invoice number,
  date) that About shows; **no online check** (the app stays fully offline, `COMPANY-USE.md` "no licence server" stays
  true).

**What the texts would need to say (no edits made):**
- **About window:** "Fresing Render: GPL-3.0-or-later. Fresing assets: Fresing Assets Licence – free for private use,
  education and non-profits; companies need a licence" + "Licensed to <company>, <n> users" when a file is there + a
  button "Assets licence".
- **`docs/COMPANY-USE.md`:** a section "Fresing assets – company licence" (what is paid, per user, how to buy, the
  licence file, where to put it for everyone – the `.frsetup` set-up file of 0272 could carry it); in "The licence in
  plain words": the GPL part unchanged, the assets apart; the network table unchanged (no check).
- **README:** licence section: code GPL, assets under their own licence (not in this repository), name / logos.
- **THIRD-PARTY-NOTICES.md:** brand note + "Fresing assets" line; decide row 2 (site media) and the guide pictures.
- **Landing page:** "Free for private use, students and non-profits – companies €… per user" with the download and
  the buy button; the licence in plain words; a line on Blender support (if chosen).
- **0286:** its "Fresing standard library (our own, CC0)" becomes the paid-for-companies pack.

### E · Prices

Checked at the official page on 25 Nov 2026 (curl; USD unless stated; VAT not stated):

| Product | Price | Per | Term / updates | Free for | Source |
| --- | --- | --- | --- | --- | --- |
| KeyShot Studio Professional / Business | $1,299 / $1,599 a year | user | subscription, updates in term; no perpetual | EDU $95 / year | keyshot.com/pricing |
| Enscape Solo / Premium / Impact | $459.84 / $536.64 / $584.64 a year (US store) | user | subscription | education tab (price not read) | chaos.com/enscape/pricing |
| Rhino 9 | $995 once; upgrade $595; education $195 | concurrent user | perpetual, all service releases of the version | – | rhino3d.com/buy (Rhino 8 no longer listed) |
| Twinmotion | *secondary:* free below USD 1 M yearly revenue (also students, hobby); $445 / year / seat above | user | yearly | yes | twinmotion.com blocked (Cloudflare) – search excerpts + 3rd-party blogs |
| D5 Render | *secondary:* Community free, non-commercial; Pro ≈ $360 / year | user | subscription | Community | d5render.com blocked – excerpts |
| Superhive: Extreme PBR Nexus | $29–89 (by texture size) | – | – | – | superhivemarket.com product page |
| Superhive: Pro-Lighting: Studio | $89, "Royalty Free", seats selector | seat | – | – | same |
| Superhive: STEP Importer 3.0 / StepIO / StepXpert | $20 / $35 / $14.90 per user; 5 users $90 / $100; 10 users $160 / $200 | user | support period, +12 months for 50 %; StepXpert all 1.x updates | – | same |
| Blender Development Fund (corporate) | Bronze €6,000 · Silver €12,000 · Gold €30,000 · Platinum €60,000 · Titanium €120,000 · Patron €240,000 a year | company | yearly | – | fund.blender.org/corporate-memberships (individual levels not shown on the pages read) |

**Proposals (not measurements):**
- **Model 1 – one-time per user (recommended):** company user **€129**, freelancer (one-person business) **€59**,
  5 users €499, 10 users €899 (excl. VAT); all updates of pack 1.x, promised for at least 2 years; the next major at
  half price. ~10 % of one KeyShot year, ~13 % of Rhino; simple for a small company's purchase.
- **Model 2 – yearly per company:** €190 / year up to 10 people, €490 / year unlimited users at one company; always
  the newest pack. Steadier income, more admin, harder to sell to people who dislike subscriptions.
- **Model 3 – both** (one-time per user, or a yearly company licence).
- Shop fees on €129: Paddle ≈ €7 (5 % + 50¢), Gumroad ≈ €13.4 (10 % + $0.50).
- Blender: a fixed share, e.g. **5 % of pack income**, as an individual Development Fund membership; Bronze (€6,000 /
  year) only once income is far larger.

### F · Selling and support

| Shop | Seller of record? | Fees | Payout | B2B VAT number | Licence keys / seats | Source |
| --- | --- | --- | --- | --- | --- | --- |
| **Paddle** | yes ("Paddle as your Merchant of Record") | 5 % + 50¢, no monthly fee; under $10 "contact us" | monthly, min €100 when in EUR; EUR possible; maybe $15 SWIFT fee | buyer's valid VAT ID → reverse charge; you do **not** invoice Paddle, it sends a "Reverse Invoice" | not found – licence file by e-mail | paddle.com/pricing, paddle.com/help (read) |
| **Gumroad** | yes, since 1 Jan 2025 ("handles ALL your tax obligations") | 10 % + $0.50 (card fee inside or extra: its two pages differ – ask) | weekly / monthly, min $100 [search] | VAT ID → **refund** of VAT, not a reverse-charge invoice | **yes**, keys + "Multi-seat license" | gumroad.com/pricing, help 10 / 66 / 76 (read) |
| Lemon Squeezy → Stripe Managed Payments | was yes; **no new stores, stops 31 Mar 2027**; Stripe MP 3.5 % + Stripe fees, **no keys or file hosting** | – | – | MoR | no | docs.lemonsqueezy.com/migration (read) |
| FastSpring | yes [search] | custom pricing [search] | – | – | – | site blocked (403) |
| Superhive | marketplace; VAT: an old help article says no VAT collection [search] | free plan: 70 % to you + 5.5 % + $0.49; Pro $49 / month 80 %; Ultimate $199 / month 90 % | monthly [search] | – | seat selector exists | superhivemarket.com/pricing (read) |

Recommended: **Paddle** for the company licence (proper B2B invoices, lowest fee, EUR payouts) – it needs an account
review; **Gumroad** if Paddle says no or for a quick start. Superhive later as a second shop window to Blender users
(but check who pays VAT there).

**Questions for an accountant** (Belastingdienst pages read where marked):
1. With a merchant of record (Paddle UK / US) I sell to Paddle: reverse charge on that sale – what goes on my VAT
   return for Paddle's reverse invoice, and in the EC sales list (ICP)? (EU business buyers directly: "btw verlegd" +
   ICP – belastingdienst.nl, read.)
2. Is a downloaded pack + licence an electronically supplied service (place of supply = customer)?
3. KOR (≤ €20,000 turnover, NL establishment – read) or EU-KOR (≤ €100,000 – read): does turnover via a MoR count,
   and is KOR wise when costs (shop fees) carry VAT?
4. Income tax: the owner works outside his job – below 1,225 hours (urencriterium – read) the profit is "resultaat uit
   overige werkzaamheden"? What can be deducted?
5. Donations ("Support Fresing") next to sales: income of the business or gifts? How to keep them apart (separate
   page, separate account, no reward)?
6. Invoice rules when the MoR is the seller (who invoices whom).

**Support plan (small promises):** e-mail only (one address); answer within **5 working days**, best effort; fixes
come in the normal releases (no fixed fix time); no phone, no on-site, no custom work in the licence (paid apart,
"ask Fresing" as `COMPANY-USE.md` says now); support only for the newest version and the newest pack; private users:
GitHub issues. The licence is for the assets – support is a courtesy, not a contract term.

### G · The name

- BOIP (boip.int, read): "You only actually own your name or logo if you have registered your trademark"; a used
  trade name protects "only in the region where your company is active"; well-known marks without registration are
  "extremely rare" (opposition notes). The Handelsnaamwet (art. 5: no confusing trade name where the businesses and
  places make confusion likely) could not be read at wetten.overheid.nl (paraphrase from search). A logo can have
  copyright if it is original (Auteurswet; not read).
- Fees: **Benelux (BOIP, read): 1 class €244, 2nd €27, 3rd+ €81 each, 10 years** (classes 9 + 42 = €271; + 41 =
  €352). EU mark (EUIPO, not reachable – search): €850 / €50 / €150.
- **SME Fund 2026** (boip.int/en/sme-voucher, read): 75 % of fees up to €700; **vouchers 1 and 2 closed on 19 Nov
  2026**. Nothing found on a 2027 round – check in January; a voucher normally has to be granted *before* filing (check
  the 2027 rules).
- **Advice:** selling a paid licence under "Fresing" makes registering more urgent – the name is then worth copying,
  and the first to file wins. Benelux, classes **9** (software, downloadable assets) and **42** (software services),
  **before the first sale**; if a 2027 voucher round opens first, use it (saves ≈ €200 on €271). EU mark when sales
  spread beyond the Benelux.

### H · Build tasks that would follow (nothing started)

| # | Task | Size | Lane | After |
| --- | --- | --- | --- | --- |
| P1 | Owner: picks on the page; Benelux trademark filing; shop account (Paddle / Gumroad) | owner | – | – |
| P2 | Licence texts: `LICENSE-ASSETS` (from the draft), README, THIRD-PARTY brand / assets lines, `COMPANY-USE.md` section, About window lines + "Licensed to …" | small (Sonnet · Medium) | Repository & company use | P1 |
| P3 | Assets pack mechanism: pack format (zip + `pack.json` + licence), Add / Remove pack (the demo-kit pattern), licence file read and shown (no lock), `.frsetup` can carry pack + licence; tests: the app runs fully without a pack | medium (Opus · Medium) | Start & learn / Settings | P2 |
| P4 | Plain fallback look + looks that prefer pack materials / HDRIs when present; tour and PC check both ways | medium (Opus · High) | Looks | P3 |
| P5 | Private repository `fresing-assets` + its own small CI that builds the pack zip (private minutes rules as the vessel kit) | small | – | P3 |
| P6 | First pack content: the owner's HDRIs / 360° photos (0286's list), a hand-made finishes set, one learning project | medium + owner's photos | Looks / Surroundings | P4 |
| P7 | Landing page: free / company prices, download page with the licence, buy button | small (Sonnet · Low) | Site | P2, shop |
| P8 | (optional, large, high risk) move today's finishes / light pictures from code into the pack | large (Opus · High) | Looks | P4 – only if the owner picks it |

**Tested and measured:** with / without renders of `test_crane_a`, `test_mill`, `test_finishes` (Cycles CPU, preview,
640 × 400, ~20–24 s each) on the 4-core web machine; inventory from `du`, the code and `git log` / the release tags on
GitHub. Facts gathered by three helper agents (Sonnet) with curl – WebFetch could not resolve hosts; two network
approvals added the source hosts to this environment. Pages blocked by Cloudflare or the proxy are marked secondary.

**Open points / follow-up tasks:** the owner's picks on `tasks/0343_page/`; then P2–P8. Read in a browser before
deciding: Twinmotion's and D5's price pages, Blendkit's plans, the Superhive "mixed licenses" article, Blender's licence
FAQ, the Handelsnaamwet text, EUIPO fees and any 2027 SME Fund round. 0286's "Fresing standard (CC0)" is replaced by
this plan's pack if the owner picks it. A lawyer (if ever) for the licence draft and the AI-copyright point.
