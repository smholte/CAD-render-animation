# 0047 – Landing page on GitHub Pages: Fresing look, pictures, download button, user guide

**Who:** worker · **Status:** done 8 Nov (page live; the owner's renders follow) · **Branch:** `task/0047-landing-page`
**Started by:** lead chat, 8 Nov 2026 (changed after the owner's answers, 22:30) · **Lane:** Quality & delivery –
new folder `site/` (page, brand files, picture kit), a new tool `tools/build_site.py`, a new Pages job in
`.github/workflows/tests.yml` (and `tools/ci_precheck.py` only if the mode rules need `site/`), tests; no app code
**Model:** Opus · effort Medium (Windows render kit + workflow job) · **Environment:** "CAD-render-animation"
(real Blender at start, CLAUDE.md section 4)

Runs next to 0040, 0043, 0044, 0045, 0046. Do **not** change `docs/` (0044 is adding pictures there) – read the guide
and its pictures from `docs/` as they are on `main` when the page is built.

## Goal

A small public page at **https://smholte.github.io/CAD-render-animation/** in Fresing's own look, with real-looking
pictures and a short video of what the app makes, a big **Download for Windows** button for the newest release, the
user guide readable in the browser, and a short part about Fresing with a link to fresing.nl. The page updates
itself at every release.

## Background

- The repository is public; GitHub Pages is free for it. Releases are published by the `release` / `release-check` /
  `release-latest` jobs (CLAUDE.md section 5); the installer is `FresingRender-<version>-windows.zip` on the release.
- The user guide is `docs/USER-GUIDE.md` + `docs/img/`; `tools/build_guide.py` already makes one HTML file with the
  pictures embedded (`dist/guide/user_guide.html`).
- Install steps for a new PC: `docs/README-install.txt` and the release text in `tools/release_tools.py`.
- Licence in the manifest: GPL-3.0-or-later. Made by Fresing (the owner's company, https://fresing.nl).
- **Owner's answers (8 Nov):**
  - **Brand:** the owner gives you Fresing's brand identity, colour palette and logos at the start of the session.
    The page follows them (colours, logo, type). They are his own brand and are meant for this public page, so they
    may be committed to `site/brand/` – confirm once with him. If attaching files in the session does not work, ask
    him to upload them on github.com into `site/brand/` (repository → **Add file** → **Upload files**). A brand
    font: put the font file in `site/` if its licence allows, else the nearest system font – no outside font sites.
  - **Pictures:** not the owner's machines, not the EGR model. Use **free models found online whose licence allows
    showing them on a public page** (CC0, CC-BY, CC-BY-SA, public domain or a maker's explicit permission), rendered
    on the **owner's PC** (RTX 3090) with a ready-made kit you write – much better quality than the web machine.
  - **Fresing:** a short part on the page about Fresing, with a link back to fresing.nl. The owner's idea for the
    message: Fresing builds tools for the people who build machines. Draft 2–3 short versions; he picks or rewrites.

## What to build

1. **Find the models.** 3–5 STEP models (or formats the app can import) that look like what the app is for: a CNC
   mill or lathe, a crane / winch / deck machine, a gearbox or robot arm, an assembly with many parts. For each:
   link, maker, licence, the credit line it needs. **Not GrabCAD** unless the model page itself states such a
   licence (GrabCAD's own terms do not allow it). Show the owner the list with the reasons; he says which to use.
   The models themselves are **never committed** (only the pictures, with credits in `site/CREDITS.md` and on the
   page). If this machine cannot download them, the owner downloads them on his PC.
2. **Picture kit for the owner's PC** (`site/render_kit/`): a `Make site pictures.bat` + a Python script run by the
   installed Fresing Render's Blender (background). From a folder with the chosen models it: imports each with the
   app's own importer and sorting, picks looks, a light look and surroundings that fit (mill → CNC hall, crane →
   quay or deck), sets 1–2 camera views per model, renders the stills (Cycles on the graphics card, ~2400 px wide,
   Final quality) and one short video (turntable or a few seconds of motion, ≤ 15 s, 1080p MP4), and writes
   everything plus a contact sheet into one output folder. Settings per model in one small text file in the kit so a
   picture can be changed without code. The owner gets: numbered click-by-click steps (where to put the models,
   double-click, how long it takes, which folder to send back). This is Windows-only code: test what you can here
   (the same script on Linux with the test models, Cycles CPU, small size) and have it **reviewed by a helper agent**
   (CLAUDE.md section 6) before giving it to the owner. Send the kit as a zip in the session.
3. **Placeholder pictures first:** until the owner's pictures arrive, the page uses 3–4 renders of the generic test
   models made here (the same kit, small), so the page can go live. Then swap in his pictures after he has looked at
   them and said OK. Compress: JPG ≤ ~400 KB each, video ≤ ~8 MB.
4. **`site/`**: one static page (`index.html` + CSS; no frameworks, no outside fonts, scripts or trackers, no
   cookies). English, plain words, works on a phone, in Fresing's colours and logo. Top to bottom:
   - Logo, **Fresing Render**, one line on what it is (photo-real renders and animations of large STEP assemblies –
     machines, CNC mills, offshore equipment), the big **Download for Windows** button with version and date, and:
     Windows 10/11, NVIDIA graphics card recommended, no admin rights needed.
   - The video, then 4–6 pictures with one-line captions (click opens full size).
   - What it does: 6–8 short points (drop in a STEP file; parts sorted and given materials; motion – joints,
     cylinders, mechanisms; G-code milling with chips; surroundings – hall, sea, deck; stills, turntables and
     finished videos with titles and captions; render queue; updates itself).
   - Install in 3 steps; **User guide** button (→ `guide/`); **What's new** (newest CHANGELOG section); link to all
     releases.
   - **Made by Fresing:** the owner's chosen text, Fresing logo, link to https://fresing.nl.
   - Footer: source on GitHub, licence GPL-3.0-or-later, model credits.
5. **`tools/build_site.py`**: writes the finished page into `dist/site/`: version, date, exact download address of
   the release asset, What's new; copies pictures, video and brand files; builds the guide with `build_guide.py`
   into `dist/site/guide/index.html`. Tests: right version and download address, every picture and the video exist,
   guide present, every model credited, links only to GitHub and fresing.nl.
6. **Pages job** in `.github/workflows/tests.yml`: after `release-latest` (only when a release was offered;
   `!cancelled() && needs.release-latest.result == 'success'`, CLAUDE.md section 8) build and deploy the site
   (`actions/upload-pages-artifact` + `actions/deploy-pages`, job-level `permissions: pages: write, id-token:
   write`). Also deploy on a push to `main` that changes only `site/` or `tools/build_site.py` (built from the newest
   release, no full test run) and on `workflow_dispatch`.
7. **Turning Pages on** needs one repository setting (Settings → Pages → Source: **GitHub Actions**). Try it through
   the GitHub API first; if refused, give the owner the click-by-click steps and wait for his "done".

## Done when

- [ ] Page live at https://smholte.github.io/CAD-render-animation/ in Fresing's look; the button downloads the zip of
      the newest release; the guide opens at `…/guide/`; pictures and video load; checked at desktop and phone
      width (Playwright screenshots, looked at, small).
- [ ] Model list with licences approved by the owner; credits on the page and in `site/CREDITS.md`; no model file
      in the repository.
- [ ] Render kit reviewed by a helper agent, tested here on Linux, sent to the owner with steps. Placeholder
      pictures live; the owner's pictures swapped in once he sends them and says OK (if he has not sent them by the
      end of the session, say so in the report – a later session swaps them in with the same tool).
- [ ] The next release updates the page by itself (proved with a `workflow_dispatch` run; the report names it). No
      change to the app, its version or the update listing.
- [ ] Tests for `build_site.py`; precheck passes; GitHub green; `TASKS.md` updated; report filled in with the
      address, the run, the page size and the model list.

## Not in this task

A fresing.nl address for the page (later: a CNAME). The owner's own machines. Any change to the guide text, the
installer or the release assets.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 8 Nov 2026 (one session).

**What changed:**
- `site/`: the page (`index.html`, `style.css`) in Fresing palette A (Green #479B29, Charcoal #252E36, Deep Charcoal
  #1A2027), the refined logo set from the owner's brand files (`brand/`: full + compact, colour + reversed, symbol,
  app icon as favicon; owner: logo yes, palette page no), IBM Plex Sans as woff2 (OFL, `fonts/`). No scripts, no
  outside fonts/trackers/cookies. Top: owner's milling video (his own mill with air blast, 15 s of 20, 1080p,
  4.2 MB, owner's choice to put it on top); 4 placeholder renders of test models; What it does (8 points); Install
  in 3 steps; What's new; Made by Fresing ("Made by machine builders, for machine builders…", owner picked);
  credits.
- `tools/build_site.py`: builds `dist/site/` (version, date, download address, CHANGELOG section, guide in
  `guide/index.html`) and checks it; `--take` and `--hero-video` compress and swap pictures/video (ImageMagick,
  ffmpeg). `site/media/media.json` = captions + credits; `site/CREDITS.md` = the same + the planned models.
- `site/render_kit/`: `Make site pictures.bat` + `make_site_pictures.py` + `models.ini` (+ `placeholders.ini`
  for the web machine). Reviewed by a helper agent; its 7 findings fixed (old frames in a re-rendered video,
  up_axis ignored, PC sleep, errors not in log.txt, stale zip after a crash, hidden extensions, .bat run from
  inside the zip) plus models.ini in ANSI/UTF-16.
- `.github/workflows/pages.yml` (after each release via a `pages` job in tests.yml, on site-only pushes to main,
  by hand); precheck counts `site/`, `tools/build_site.py`, `tests/test_site.py` as docs (docs mode runs
  test_site.py). CLAUDE.md sections 3 and 5.

**Tested and measured** (web machine, 4 cores, no graphics card):
- `tests/test_site.py` 13 tests (incl. the kit rendering the test gantry end to end, bpy module), test_ci_tools.
- Kit on the test crane, `--small`: still + 48-frame turntable MP4 in 393 s (8.1 s/frame on the processor).
  Placeholders (`--cpu`, 1600 × 900 Preview): 4 stills in 470 s (86–177 s each).
- Page: 6.5 MB with the guide (page + media 4.7 MB); Playwright at 1366 px and iPhone 13 (390 px, no sideways
  scroll), looked at.

**Live:** https://smholte.github.io/CAD-render-animation/ – first published by the push of the merge to main (Pages
run 42530450651, 0.3 min, built from release 0.2.36, 6.5 MB, 0 problems); by hand: workflow_dispatch run 42530514897
(green). The after-release path (tests.yml job `pages` behind `release-latest`) runs for the first time at the next
release. Branch runs: 42527974143 failed at once (a YAML error in pages.yml stopped both workflows: fixed, test added),
42528079043 green, 42529313380 green after merging main (0.2.35/0.2.36 had come in). This machine cannot open
github.io (proxy), so the live page was checked through the Pages run; the built page was looked at with Playwright.

**Models (owner OK 8 Nov):** Mekanika EVO CNC (CERN-OHL-S-2.0), OpenArm (CERN-OHL-S-2.0), Thor arm (CC BY-SA 4.0),
FarmBot Genesis (CC0, to be confirmed on genesis.farm.bot when downloading) + on the owner's request for a cylinder:
the OSE CEB brick press (CC BY-SA 4.0), converted here from FreeCAD with the new `tools/fcstd_to_step.py` (246 parts)
and shipped inside the kit zip (not committed). No openly licensed crane with CAD was found.

**Later in the session:** the owner asked for colours and Thor as one STEP: `colours =` lines in models.ini (part
name pattern = material + RAL/hex colour, a group "Site: <pattern>" each); `tools/a4_to_step.py` builds the whole
Thor arm from its FreeCAD Assembly4 files (522 parts, 163 unique, 82 MB STEP); `fcstd_to_step.py` fixed (took
constraint names). The kit zip (20 MB) carries thor.step and ceb_press.step. Runs: 42532842036 and 42534114433
green (one docs-mode run failed: the kit's render test needs OCP, now skipped there). Main at 73cafe5. The owner
started the kit on his PC on 8 Nov.

**Open points / follow-up tasks:**
- The owner renders with the kit (sent in the session, 3.9 MB with the CEB press) and sends the zip; a session runs
  `tools/build_site.py --take <folder>` (his video stays at the top: `keep`), checks, pushes `site/` (docs mode +
  Pages republish).
- The owner can delete the draft release `landing-video-raw` (his raw video).
