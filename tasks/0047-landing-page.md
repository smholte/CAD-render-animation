# 0047 – Landing page on GitHub Pages: pictures, download button, user guide

**Who:** worker · **Status:** open – can start · **Branch:** `task/0047-landing-page`
**Started by:** lead chat, 8 Nov 2026 · **Lane:** Quality & delivery – new folder `site/`, a new tool
`tools/build_site.py`, a new Pages job in `.github/workflows/tests.yml` (and `tools/ci_precheck.py` only if the
mode rules need `site/`), tests for the tool; no app code
**Model:** Sonnet · effort Medium · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

Runs next to 0040, 0043, 0044, 0045, 0046. Do **not** change `docs/` (0044 is adding pictures there) – read the guide
and its pictures from `docs/` as they are on `main` when the page is built.

## Goal

A small public page at **https://smholte.github.io/CAD-render-animation/** with a few pictures of what the app
makes, a big **Download for Windows** button for the newest release, and the user guide readable in the browser.
The page updates itself at every release; nobody has to touch it.

## Background

- The repository is public; GitHub Pages is free for it. Releases are published by the `release` / `release-check` /
  `release-latest` jobs (CLAUDE.md section 5); the installer is `FresingRender-<version>-windows.zip` on the release.
- The user guide is `docs/USER-GUIDE.md` + `docs/img/`; `tools/build_guide.py` already makes one HTML file with the
  pictures embedded (`dist/guide/user_guide.html`). All guide pictures show generic test models only.
- Install steps for a new PC: `docs/README-install.txt` and the release text in `tools/release_tools.py`.
- Licence in the manifest: GPL-3.0-or-later. Made by Fresing (the owner's company).
- **Privacy:** the page is public. Pictures only of the generic test models in `tests/data/` (mill, crane,
  machine, way cover, decals …) and the guide's own screenshots – never the owner's machines or the EGR model.
  The owner may later send his own renders for the page; those go in only with his explicit OK in that session.

## What to build

1. **`site/`**: one static page (`index.html` + one CSS file; no frameworks, no external fonts, scripts or
   trackers, no cookies). English, plain words, works on a phone. Content top to bottom:
   - Name **Fresing Render**, one line on what it is (photo-real renders and animations of large STEP assemblies –
     machines, CNC mills, offshore equipment), the big **Download for Windows** button with version and date
     under it, and one short line: Windows 10/11, NVIDIA graphics card recommended, no admin rights needed.
   - 4–6 pictures with a one-line caption each (see 3), shown as a simple grid; click opens it full size.
   - What it does: 6–8 short points (drop in a STEP file; parts sorted and given materials; motion – joints,
     cylinders, mechanisms; G-code milling with chips; surroundings – hall, sea, deck; stills, turntables and
     finished videos with titles and captions; render queue; updates itself).
   - Install in 3 steps; **User guide** button (→ `guide/`); **What's new** (the newest CHANGELOG section);
     link to all releases.
   - Footer: source on GitHub, licence GPL-3.0-or-later, made by Fresing.
2. **`tools/build_site.py`**: writes the finished page into `dist/site/`: fills in version, date, download
   address (the exact release asset) and What's new from the files of that commit; copies the pictures; builds the
   guide with `build_guide.py` into `dist/site/guide/index.html`. Tests: the page has the right version and a
   download address of the right form, every picture exists, the guide is there, and every link stays on GitHub
   (no outside addresses).
3. **Pictures** in `site/img/`: render 4–5 stills of the generic test models with the real Blender on the web machine
   (Cycles CPU, ~1600 px wide, good light look and surroundings – e.g. the test mill in the CNC hall, the crane on
   the quay, a milled block with chips, a decal close-up) plus one app screenshot from `docs/img/`. Compress them
   (JPG, each under ~400 KB). A short looping video is welcome if it stays under ~5 MB.
4. **Pages job** in `.github/workflows/tests.yml`: after `release-latest` (only when a release was offered;
   `!cancelled() && needs.release-latest.result == 'success'`, CLAUDE.md section 8) build the site and deploy it
   (`actions/upload-pages-artifact` + `actions/deploy-pages`, job-level `permissions: pages: write, id-token:
   write`). Also deploy on a push to `main` that changes only `site/` or `tools/build_site.py` (built from the newest
   release's version, cheap – no full test run), and on `workflow_dispatch`.
5. **Turning Pages on** needs one repository setting (Settings → Pages → Source: **GitHub Actions**). Try it through
   the GitHub API first; if that is refused, give the owner the click-by-click steps and wait for his "done".

## Done when

- [ ] The page is live at https://smholte.github.io/CAD-render-animation/; the button downloads the zip of the
      newest release; the guide opens at `…/guide/`; pictures load; page checked at desktop and phone width
      (Playwright screenshots, looked at, small).
- [ ] The next release updates the page by itself (proved with a `workflow_dispatch` run now; the report says which
      run). No change to the app, its version or the update listing.
- [ ] Tests for `build_site.py`; precheck still passes; GitHub green; `TASKS.md` updated; report filled in with the
      address, the run and the size of the page.

## Not in this task

A custom domain (e.g. a fresing.nl address – owner decides later, then a CNAME). The owner's own renders. Any
change to the guide text, the installer or the release assets.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
