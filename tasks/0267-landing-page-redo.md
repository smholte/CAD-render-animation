# 0267 – Landing page redo: picture and video rows, "Turn it yourself" row, "Who it is for" as a band + numbered cards, a lighter fresing.nl-style overhaul, a "How it works" page, a tool switcher

**Who:** worker · **Status:** running · **Branch:** `task/0267-landing-page-redo`
**Started by:** lead, 21 Nov 2026 (owner 16:41–17:09: "I want to redo the page"; picks from the lead's mock-ups: layout
H's dark band with D's numbered cards, full text kept; the rest of the page "a little overhaul, but I like the lighter
look for this website, so not as much dark as fresing.nl"; "How it works" as its own page now; the Fresing Viewer page
later) · **Model:** Opus · effort Medium
**Area:** Web 3D lane, the website part only – `site/index.html`, `site/style.css`, new `site/how-it-works/` page (or
`site/how.html`, your choice), `site/fonts/` (IBM Plex Mono if used, OFL – credit it), `site/media/media.json` and the
three deleted files, `tools/build_site.py`, `tests/test_site.py`, `tests/test_site_take.py` (only if the take-in's
media.json handling changes). **Not:** the 3D web page player (`fresing_render/web/` – task 0256 may run beside this
task), the render kit (`site/render_kit/`, `tools/site_projects/` – task 0268), the app, the user guide's content.

## Goal

https://smholte.github.io/CAD-render-animation/ looks finished and calm: pictures and videos in two rows you scroll
left and right, the 3D models the same way, a "Who it is for" block that reads well, the same light page with a few of
fresing.nl's touches, a "How it works" page, and links to the other Fresing tools. It is ready for the new renders and
web models that come once the test models are redone (0259–0264): adding one is a media.json line, no code change.

## 1. Delete now (owner: "they don't look that good")

From the page, from `site/media/media.json` and from `site/media/`:
- `iea15_offshore_seabed.jpg`
- `iea15_onshore_from_the_field.jpg`
- `iea15_onshore_at_the_door.jpg`

**Stay until their new versions arrive** (task 0268 re-renders them; a later take-in swaps them):
`iea15_offshore_whole_turbine.jpg`, `iea15_offshore_loop.mp4` (the 7.56 rpm video), `thor_side.jpg` (the picture in
"Built on Blender"). If a model has no picture left after the deletion, its credit stays as long as any file of it is
on the page (`build_site.py`'s credit check).

## 2. "Made with Fresing Render" – two rows

- **Pictures on top, videos in a second row under it.** Each row: a horizontal strip that scrolls with a swipe, a
  trackpad, Shift + mouse wheel, and the keyboard; **‹ › arrow buttons** at its ends move one item; CSS scroll-snap so an
  item never stops half-cut; the arrow at an end greys out. A small row title each ("Pictures", "Videos") with a count.
- Without script the rows still scroll (the arrows are an addition – the page has no script today; a short inline
  script for the arrows is allowed, nothing loaded from elsewhere).
- Click a picture → full size as today. Videos: poster first, `preload="none"`, play in the row, one at a time.
- The rows come from media.json: `.jpg` items → pictures, `.mp4` items → videos (keep the order in media.json). The hero
  video at the top stays where it is (`keep: true`).
- Phone: one item and a bit of the next visible, so it is clear the row scrolls.

## 3. "Turn it yourself" – the same row

The cards of media.json `web_models` in the same scrolling row with ‹ › arrows (today: the test ATC mill and Thor).
Each card still opens its own page `model/<id>/`. One shared row component for all three rows.

## 4. "Who it is for" – owner's pick: H's band + D's cards

Light page; this block only gets a dark band:

- **Band** (Deep Charcoal `#1A2027` with a faint square grid like fresing.nl's hero, full width or a wide rounded box):
  a monospace label `// WHO IT IS FOR`, the line **"Built to speed animators up – not to replace them."** and one short
  line under it, for example: "Import, sorting, materials and motion in a few clicks – the craft stays yours."
- **Under it, three numbered cards** on the light ground, equal height, a 3 px Fresing Green top edge, mono label +
  headline + two lines (the owner said H alone had too little text – keep this much):
  - `01 · ENGINEERS` **Render it yourself** – Your own machine, step by step, in plain words. No waiting for anyone.
  - `02 · SALES TEAMS` **Show it before it exists** – How the machine looks and moves, straight from the engineering
    model. Nothing is guessed.
  - `03 · ANIMATORS` **Start from a working scene** – The set-up is done for you. Light, camera and story stay yours –
    with all of Blender.
- The four points of 0266 (Easy / Fast / No limits / Your real machine) are now inside the band line and the cards; the
  long animator paragraph moves to the "How it works" page (section 6). `docs/DESCRIPTION.md` stays as it is.
- Phone: the cards stack.

## 5. The rest of the page – a light overhaul

The owner likes **the lighter look** of this page – no dark page. Take a few touches from fresing.nl (a React site, look at
it in a browser; it is not fully up to the Fresing brand yet, so take **layout ideas only**, colours and fonts from
today's `site/style.css`, which follow the Fresing Brand Specification):
- small monospace section labels (`// MADE WITH FRESING RENDER`, `// WHAT IT DOES`, …) above the section titles;
- "What it does": the eight points as numbered cards (01–08) in a grid, not a list;
- the Download button with one cut corner (fresing.nl's buttons), Fresing Green;
- a thin spec strip under the hero on the light ground, e.g. **STEP IN** · from Inventor, Fusion, any CAD ·
  **CYCLES** · real light · **WINDOWS 10 / 11** · no admin rights · **FREE** · open source (GPL);
- keep everything else the page says; keep the page light (no new picture weight; fonts subset like the Plex Sans
  files).

## 6. New page "How it works"

Its own page, linked from the top menu ("How it works") and from the "Who it is for" band. From the lead's mock-up G:
- a drawing (inline SVG, "FIG." caption in the mono style): **CAD** (your model – Inventor, Fusion, any STEP) →
  **Fresing Render** (minutes – parts sorted, materials, motion, scene) → **Blender** (no limits – light, camera, story);
  under it: engineers and sales teams stop after Fresing Render, the render or film is done; animators carry on, the
  set-up is done and the craft is theirs;
- the steps in order (import, sort and materials, motion, surroundings and camera, render / video / web 3D, open in
  Blender), each with one or two lines and a link to its user-guide chapter (`guide/#…`, the anchors exist);
- the long animator paragraph from 0266 (it is in `docs/DESCRIPTION.md` and today's `site/index.html`);
- existing pictures only (no new media); same header, footer and look as the main page; `build_site.py` builds it and
  the link check covers it.

## 7. Tool switcher in the header

The owner wants each Fresing tool page to link to the others: **direct buttons** for the two closest tools (Fresing
Render and the coming **Fresing Viewer**) and a **"More tools" fold-down** for the rest (today: House Planner,
https://smholte.github.io/house-planner/).
- Now: "Fresing Render" (current page, marked) + "More tools ▾" with House Planner. **No Viewer button yet** – its page
  does not exist (owner: the Viewer page comes with the Viewer). Keep the list in one small data file read by
  `build_site.py` (e.g. `site/tools.json`: name, url, `direct: true/false`) so the Viewer button is one line later.
- The fold-down works without script (`<details>`) and on a phone.

## Done when

- [ ] The three pictures are gone from the page, media.json and `site/media/`; the three "redo" files are still there
- [ ] Pictures row and videos row scroll left / right (swipe, trackpad, Shift + wheel, keys, ‹ › arrows), snap, work
      without script; the same row shows "Turn it yourself"
- [ ] "Who it is for" = dark band + three numbered cards as above; phone layout stacks
- [ ] The lighter overhaul (labels, numbered "What it does", cut-corner button, spec strip); the page stays light
- [ ] "How it works" page built, in the menu, its links checked
- [ ] Tool switcher with House Planner in "More tools"; the tool list in one data file
- [ ] `tests/test_site.py` updated (rows from media.json, deleted files not referenced, the new page built, the tool
      list); `python3 tools/build_site.py` builds; full suite passes
- [ ] Screenshots at 2560 px, 1440 px and a phone width of the page and the new page, checked by eye and by a second
      reviewer that did not write the page (fresh subagent) – rows, arrows at the ends, the band, the cards
- [ ] After the merge: the live page checked (GitHub Pages deploy), noted in the report
- [ ] Report below filled in

## Not in this task

The 3D web page player (`fresing_render/web/`, 0256); the render kit and new renders (0268); the Fresing Viewer and its
page (study 0269); the Fresing company website (fresing.nl – another project); custom domains (Fresing lead, later);
the app and the user guide's content.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 21 Nov 2026

**What changed:**
- `site/media/`: `iea15_offshore_seabed.jpg`, `iea15_onshore_from_the_field.jpg`, `iea15_onshore_at_the_door.jpg` deleted
  (files + media.json). The three "redo" files stay. The onshore turbine's credit leaves the page by itself (no file of
  it shown); its entry stays in media.json `models` for the coming renders.
- **Rows:** `tools/build_site.py` `split_media` (.jpg → Pictures, .mp4 → Videos, media.json order), `row_html` = one
  shared row (title + count, `<ul class="strip">` that scrolls and snaps, ‹ › buttons hidden until the script shows
  them); "Turn it yourself" uses it too. `ROW_SCRIPT` = one inline script (arrows move one item, an arrow at an end
  goes, a row that fits hides its arrows, one row video at a time). The page check now allows exactly that script and
  refuses any other or one loaded from a file.
- **Who it is for:** dark band (Deep Charcoal, faint 36 px grid, `// WHO IT IS FOR`, the line, the sub line, "How it
  works →") + three numbered cards (3 px green top, equal height; stack on a phone).
- **Overhaul:** mono section labels (IBM Plex Mono Medium, Latin-1 subset, 17.9 KB, OFL – credited in
  THIRD-PARTY-NOTICES both copies, site/CREDITS.md, footer), "What it does" as numbered cards 01–08 (4 / 2 / 1 columns),
  cut-corner green Download button, spec strip under the hero; "Built on Blender" moved to the light ground (so the
  page keeps the same amount of dark with the new band).
- **How it works** (`site/how-it-works/index.html`): inline SVG (a wide and a phone drawing, "Fig. 1"), six steps with
  guide links (import, looks, motion, surroundings, camera, first-render, animation, web3d, queue, quiet-window), the
  animator paragraph (moved from the main page), the first two pictures of the row (one per model, credited on the
  page), Download + guide. Built by `build_site.py`; `check()` checks both pages' links, files and guide anchors.
- **Tool switcher:** `site/tools.json` (name, url, direct, here, note) → "Fresing Render" (marked) + "More tools"
  `<details>` with House Planner. Adding the Viewer = one line with `"direct": true`. Its host is allowed by the link
  check.
- Phone header: logo + tools on top, the menu in a second line that scrolls sideways (fades at its right edge).
- Tests: `tests/test_site.py` – rows from media.json + deleted / kept files, Who band + cards, How page (links, pictures,
  credits, a broken anchor found), tool switcher + tools.json refusal, script rule. CLAUDE.md layout line for `site/`.

**Tested and measured** (4-core web machine, headless Chromium):
- `build_site.py`: 0 problems, site 28.8 MB (the main page's media 3 pictures lighter). `test_site.py` 31 passed.
- Screenshots 2560 / 1440 / iPhone 13 of both pages: no sideways page scroll; the › button reaches the row's end in
  4 clicks (1440, 2560) / 5 (phone), then › goes and ‹ is there; at the start ‹ is hidden.
- Independent reviewer (fresh subagent, did not write the page): no blocking faults; keys, Shift + wheel and › move one
  item (460 px), snap back from an odd spot, rows scroll without script, one video at a time, phone shows one item + a
  bit, dropdown inside the phone screen. Its points fixed: phone menu showed no sign it scrolls (fade added), the greyed
  arrow covered the first picture (now hidden at an end), the two drawings' labels. Left as is: a third picture half
  visible at the right edge on desktop (on purpose – shows the row goes on; snapping keeps the left edge whole) and the
  muted top video keeps playing when a row video starts.
- GitHub runs: see below.

**Open points / follow-up tasks:**
- The new renders of 0268 go in with the take-in (a media.json line each; no code change).
- The Fresing Viewer button: one line in `site/tools.json` once its page exists.
