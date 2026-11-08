# 0047 – Landing page on GitHub Pages: Fresing look, pictures, download button, user guide

**Who:** worker · **Status:** running – Claude Code on the web, 8 Nov · **Branch:** `task/0047-landing-page`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
