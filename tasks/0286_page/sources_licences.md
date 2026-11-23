# Asset libraries – licences and terms (study for Fresing Render, 23 Nov 2026)

**How this was read.** This session's network reaches only GitHub. blendkit.com / blenderkit.com, polyhaven.com,
ambientcg.com, sketchfab.com, fab.com, blender.org (docs, extensions, developer), textures.com and web.archive.org
were all refused by the proxy. So:
- **[read]** = I read the file myself (GitHub: Poly Haven's API terms and their git history, the Blendkit add-on and its
  plugins, Poly Haven's add-on, a GitHub mirror of the Blender manual dated Jul 2026).
- **[search]** = the quote comes from the search engine's excerpt of that page (WebSearch); I could not open the page.
  Treat these as strong hints, not as read text. Every [search] row should be checked in a browser before a decision.

**News found on the way (affects all layers):**
- **BlenderKit is now "Blendkit"** (domain blendkit.com), with plugins for Maya, Rhino 8 and Godot (Aug 2026).
- **Poly Haven's API became free for commercial use on 18 Jul 2026** (git commit 4a6ceb9 "The API is now freely
  available for any purpose, including commercial."). Before that, commercial use was "strictly prohibited" without a
  licence. polyhaven.com/our-api may still show the old text (search excerpt below) – the GitHub terms are newer.
- **Blender 5.2 LTS has remote asset libraries**: a library is blend-files + a JSON listing on any static web server,
  browsed in Blender's own Asset Browser; Blender's own "Online Essentials" is one. From Blender 5.3 the Extensions
  platform lists CC0 asset libraries. This is a ready-made way to host the "Fresing standard" library (layer 1).

---

## 1. Blendkit (formerly BlenderKit)

| Question | Answer | Quote | Link |
| --- | --- | --- | --- |
| a) Ship Royalty-Free (RF) assets in installer / Fresing library | **No** | "royalty free license doesn't allow to re-sell 3D models even if modified" [search]; licence is creator → user: "we are not a contracting party of the licence contract concluded between you and the user" [search] | https://www.blendkit.com/docs/licenses/ · https://www.blendkit.com/terms-and-conditions-for-creators-2026/ |
| a) Ship CC0 assets from Blendkit | Legally yes (CC0), but Blendkit asks not to | "the CC0 license technically allows you to do anything with the assets" [search]; 2022: "will introduce a new option to exclude them from redistribution" [search] | https://www.blendkit.com/docs/licenses/licensing-faq/ · https://www.blenderkit.com/articles/our-position-on-cc0-models/ |
| b) Call their server/API with own code | **Unclear – no public API terms found** | No developer/API terms page found by search. The add-on uses a per-user key: "Your unique API key authenticates downloads and requests inside the add-on … auto-filled at login" [read] | https://github.com/BlenderKit/Blendkit/blob/main/__init__.py (line ~2205) |
| b) Older rule on other products | Old (2018) terms forbade it; status today unknown | "strictly prohibited from using BlenderKit assets or user's assets in any other products or services or develop products and services that compete with Blender Kit s.r.o." [search, 2018 terms] | https://www.blendkit.com/terms-and-conditions-2018/ |
| c) Own add-on / account; login for free assets | Own add-on is the normal way; **no login** for free assets | "Browse and download a selection of assets for free without an account. A free account lets you bookmark and rate assets." [read] | https://github.com/BlenderKit/Blendkit/blob/main/README.md |
| c) May Fresing install their add-on ("Get Blendkit" button) | Code: **yes** (GPL); a button to their own download page is the safe form | Add-on licence "SPDX:GPL-2.0-or-later" [read]; official route: "Download the add-on from the Blendkit website" [read] | https://github.com/BlenderKit/Blendkit/blob/main/blender_manifest.toml · README |
| c) Plans and price | Free plan + Full $9.90/month/seat (≤5 employees, ≤$100k revenue), Business $29/month/seat | "Full at $9.90 per month … Business at $29/month … for companies with more than 5 employees or revenue above $100k" [search, pricing page] | https://www.blendkit.com/plans/pricing/ |
| d) Credit | **No** | RF "allows commercial use without mentioning the author" [search] | https://www.blendkit.com/docs/licenses/ |
| e) Packed into a .blend sent to a client | **Probably yes, as part of a project** – wording unclear | "you may redistribute the product as a part of the project, provided all conditions under the Terms are met" [search, users' terms valid from 12 Jun 2026]; Article 5 (scope) not seen | https://www.blendkit.com/terms-and-conditions-2026/ |
| e) In a Web 3D page / viewer file (glTF + textures, anyone can download) | **Unclear / risky** | Games allowed "if these can't be extracted by the users in an easy way" [search]; not "within an asset pack or marketplace game level" [search] | https://www.blendkit.com/docs/licenses/licensing-faq/ |
| f) Company / commercial use | **Yes**, plan by company size | "You can use everything for both commercial and non-commercial purposes. The only limitation with Royalty-free licenses is you can't sell the assets themselves." [search] | https://www.blendkit.com/docs/licenses/licensing-faq/ |
| g) Other software / platforms | Assets go to other software via Blendkit's own plugins | Database "meant for scene creation in Blender and other 3D content creation software" [search]; fair share: assets "might be offered through other software and platforms in the future, always under similar conditions" [search]; Maya/Rhino/Godot plugins GPL [read] | https://www.blendkit.com/terms-and-conditions-2026/ · https://www.blendkit.com/docs/fair-share-terms/ · https://github.com/BlenderKit/bk_godot · https://github.com/BlenderKit/blendkit-rhino |

Verdict: **layer 2 only, through their own add-on** (a "Get Blendkit" button that opens blendkit.com/get-blendkit or
installs the GPL add-on). Not in layer 1. Own API code: only with written permission. Web 3D / viewer export of RF
assets: ask first, warn the user meanwhile.

## 2. Poly Haven

| Question | Answer | Quote | Link |
| --- | --- | --- | --- |
| a) Ship in installer / Fresing library | **Yes** (CC0) | "the only thing you can't do is claim to be the original author or re-license them" [search, FAQ] | https://polyhaven.com/faq · https://polyhaven.com/license |
| b) Own API code | **Yes, commercial too** (since 18 Jul 2026) | "free to access and use by anyone - individuals, organizations, and companies alike - for any purpose, including commercial use, at no charge" [read, ToS 2.1] | https://github.com/Poly-Haven/Public-API/blob/master/ToS.md |
| b) User-Agent | **Required** | "all API calls must be made with a unique "Referer" header or user-agent that matches your software name" [read, ToS 2.4] | same |
| b) Credit in the app | **Required while using the live API** | "a label within your interface (a title, menu item, or button that names Poly Haven), or … a "Powered by Poly Haven" credit displayed near the content" [read, ToS 2.5] | same |
| b) Endorsement / load | No implied endorsement; no abuse; no SLA | "must not state or imply that your product is made by, owned by, or officially endorsed by Poly Haven" [read, 2.5]; "provided on an "as available" basis" [read, 4.2] | same |
| b) Conflicting page | /our-api may still show the old rule | "free for non-commercial projects and academic research … commercial use requires a custom license, and typically sponsorship" [search, probably stale] | https://polyhaven.com/our-api |
| c) Own add-on / login | No login, no key; their add-on is optional and paid | "Poly Haven will never require payment, a license, or a key" [read, 2.3]; add-on: "Superhive … ($69)" or "Patreon … ($5/m)", GPL-3.0 [read] | ToS · https://github.com/Poly-Haven/polyhavenassets |
| d) Credit for the assets | **No** | "CC0 assets carry no attribution requirement whatsoever, now or ever" [read, 2.5] | ToS |
| e) Packed .blend / Web 3D / viewer | **Yes** (CC0) | "it does not apply to the CC0 assets themselves once downloaded or self-hosted" [read, 2.5] | ToS |
| f) Company / commercial | **Yes** | "Using the API to generate revenue, directly or indirectly, is explicitly permitted" [read, 2.3] | ToS |
| g) Competing products / other software | **Yes** | "build on that data in their own software, websites, services, or products, including for commercial and for-profit purposes" [read, 2.2] | ToS |

Verdict: **fits all three layers.** Layer 1 may copy chosen assets (self-hosted CC0 needs no credit). Layer 2 may call
api.polyhaven.com with a User-Agent like `FresingRender/<version>` and a visible "Poly Haven" label. Optional funding:
ToS 2.7 (polyhaven.com/corporate).

## 3. ambientCG

| Question | Answer | Quote | Link |
| --- | --- | --- | --- |
| a) Ship | **Yes** (CC0) | "All ambientCG assets are provided under the Creative Commons CC0 1.0 Universal License. This applies to the downloadable asset files and the material preview renders" [search] | https://docs.ambientcg.com/license/ |
| b) Own API code | **Yes as far as found – no API terms found** | v3 is current: "it is recommended to switch to the new API, especially for new projects" [search]; no User-Agent / rate-limit rules found | https://docs.ambientcg.com/updates/ · https://docs.ambientcg.com/ |
| c) Own add-on / login | No login; no official add-on required | third-party add-ons exist, e.g. "ambientCG Material Importer" on extensions.blender.org [search]; "ambientCG Lite" listed as an asset library [search, title only] | https://extensions.blender.org/add-ons/ambientcg-material-importer · https://extensions.blender.org/asset-libraries/ambientcg/ |
| d) Credit | **Not required, appreciated** | suggested line "Created using <asset name> from ambientCG.com, licensed under the Creative Commons CC0 1.0 Universal License." [search] | https://docs.ambientcg.com/license/ |
| e) Packed / Web 3D / viewer | **Yes** (CC0) | "free to use without attribution - even in commercial circumstances" [search, home page FAQ] | https://ambientcg.com/ |
| f) Commercial | **Yes** | same | same |
| g) Other software | **Yes** (CC0) | – | – |

Verdict: **fits all three layers**; ask the owner of ambientCG about API etiquette before shipping download code.

## 4. Quick in / out

| Source | In / out | Reason + quote | Link |
| --- | --- | --- | --- |
| Blender Essentials (bundled) | **In** (already in Blender) | README: all assets "licensed under CC0 "No Rights Reserved"" [search] | https://projects.blender.org/blender/blender-assets |
| Blender 5.2 remote libraries / Online Essentials | **In – and the model for layer 1** | "register remotely hosted asset libraries, browse them from within Blender, and download assets as needed" [search]; "must be possible to host an asset library using a static web server" [search]; Online Essentials "a selection of CC-0 assets" [search] | https://developer.blender.org/docs/release_notes/5.2/assets/ · https://developer.blender.org/docs/features/asset_system/remote_asset_libraries/ |
| Sketchfab Download API | **Out for now** (login + per-model CC licences, CC-BY credit must follow every export) | "the end-user must be able to log in with their Sketchfab account inside your application" [search]; app "must clearly display the Creative Commons license" [search] | https://sketchfab.com/developers/terms · https://sketchfab.com/developers/download-api/guidelines |
| Fab / Quixel Megascans | **Out** (Epic account, no standalone redistribution, no API for third parties found) | "Standalone redistribution of the assets is prohibited" [search, news report of the Fab Standard License]; use outside Unreal allowed | https://www.fab.com/cla · https://digitalproduction.com/2026/11/13/quixel-megascans-free-again |
| Textures.com | **Out** (paid, no redistribution) | "No, redistribution of the materials is not allowed." [search] | https://www.textures.com/faq-license |

## 5. extensions.blender.org rule for assets in add-ons

| Rule | Quote | Link |
| --- | --- | --- |
| Assets bundled in an add-on must be CC0 | "For assets used in add-ons, the required license is `Public Domain (CC0)`." [read, manual source on a GitHub mirror, Jul 2026; same text in search excerpt of the 5.2 LTS manual] | https://docs.blender.org/manual/en/latest/advanced/extensions/licenses.html · mirror: https://github.com/hoangduytran/blender-manual/blob/main/manual/advanced/extensions/licenses.rst |
| Add-on code | "For add-ons, the required license is GNU General Public License v3.0 or later." [read] | same |
| Credit for bundled third-party material | "all copyright holders should be properly credited in blender_manifest (copyright section)" [search] | https://extensions.blender.org/terms-of-service/ |
| Asset libraries on the platform (5.3) | "Only Public Domain (CC0) assets will be accepted." [search]; "reserves the right to unlist any asset library at any given time" [search] | https://developer.blender.org/docs/release_notes/5.3/assets/ · https://devtalk.blender.org/t/asset-libraries-extensions-platform/45779 |

Note: Fresing Render ships through its own installer, not the Extensions platform, so this rule binds it only if it
ever lists there; keeping the Fresing standard library CC0 keeps that door open.

---

## Unclear points – questions the owner could send

**Blendkit (support / admin@blenderkit.com)**
1. May a free GPL Blender app (Fresing Render) show a "Get Blendkit" button that downloads your official add-on zip
   from GitHub releases and enables it, or must it link to blendkit.com/get-blendkit?
2. Do you allow a third-party app to call your API with its own code (search + download of free assets, user logs in
   with their own account)? Are there written API / partner terms?
3. Users' terms (12 Jun 2026): "you may redistribute the product as a part of the project" – does this cover a .blend
   sent to a client or colleague who has no Blendkit plan? What does Article 5 point 4 and "the licence … shall
   terminate" mean here?
4. May Royalty-Free assets appear in a public web 3D page (glTF with baked textures, one HTML file anyone can open and
   save)? In a viewer file sent to a client?
5. Is the 2018 clause on "products and services that compete with Blender Kit" still in force for an app that only
   links to you?
6. Did the "exclude CC0 from redistribution" option of 2022 ship – may CC0 assets downloaded from Blendkit be
   re-hosted?

**Poly Haven (polyhaven.com/about-contact)**
7. polyhaven.com/our-api still says commercial use needs a custom licence; GitHub ToS (18 Jul 2026) says free. Which
   is current? Please update the page.
8. Is a menu entry "Poly Haven" in an in-app library list enough as the credit of ToS 2.5?
9. May we copy a curated subset (e.g. 30 HDRIs, 50 materials) into our own hosted library and installer (we read
   "self-hosted" in 2.5 as yes)?

**ambientCG**
10. Are there API conditions (User-Agent, rate limits, caching, credit) for a free app downloading via API v3?
11. May we mirror a subset in our own Blender remote asset library?

**Blender (devtalk / extensions moderators)**
12. Can a non-CC0 library (e.g. CC-BY or a company's own) be used as a Blender 5.2 remote asset library outside the
    Extensions platform (yes by design, as far as read) – and is "auth = TOKEN" usable for a company's private library?
