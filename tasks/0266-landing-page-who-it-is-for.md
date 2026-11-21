# 0266 – Landing page and README: who Fresing Render is for (engineers, sales, animators) – "it speeds animators up, it does not replace them"

**Who:** worker · **Status:** open – can start (not a code task: site + docs only) · **Branch:**
`task/0266-landing-page-who-it-is-for`
**Started by:** lead, 21 Nov 2026 (owner 15:54: marketing that also gives animators hope – many fear losing their jobs;
Fresing Render makes animation easier for animators, lets engineers make renders and animations of their machines and
lets sales teams show clients previews; it speeds up the start and set-up with the same results, skilled animators take
it further with all of Blender; "easy to use by engineers, fast, skilled animators can take it further with the entire
Blender library, it just speeds them up". Owner 15:59: this lead handles the Fresing Render side; the Fresing company
website gets a short description later) · **Model:** Sonnet · effort Medium
**Area:** Web 3D lane, the website part only – `site/index.html`, `site/style.css` (only if a new section needs a style),
`tests/test_site.py` (its text checks), `README.md` (the opening lines), a new `docs/DESCRIPTION.md`. **Not:** the 3D
web page (`fresing_render/web/` – 0256 may run beside this task, no shared file), the app, the user guide, the Fresing
company website (another project – later).

## Goal

A visitor of https://smholte.github.io/CAD-render-animation/ sees within a screen **who the app is for** and the
message to animators: it does the slow set-up, the craft stays theirs. Same message, shorter, at the top of `README.md`.
Ready-made short descriptions in `docs/DESCRIPTION.md` for the Fresing website and other places later.

## The wording (lead's text, agreed in the owner's words – use it, trim to fit; keep the meaning)

**One line (hero, under the title – may replace or follow today's lead line):**
Fresing Render turns your CAD model into renders and animations – fast enough for engineers to make them themselves,
and a ready-made start for animators.

**Taglines (pick one for the hero or a section title):** "From CAD to animation, fast. Take it as far as you like." ·
"The set-up is done. The craft is yours." · "Built to speed animators up – not to replace them."

**Four points:**
- **Easy for engineers.** Step by step, in plain words – no Blender knowledge needed.
- **Fast.** Import, sorting, materials and motion in a few clicks instead of hours of set-up.
- **No limits for animators.** It stays a normal Blender scene: light, camera, effects and fine motion are all yours to
  push further.
- **Your real machine.** Every frame comes from your own CAD – true shape, true sizes, true motion. Nothing is guessed.

**For animators:** Many animators worry about what AI means for their work. Fresing Render is built on the opposite
idea: speed the animator up, not replace them. It takes over the repetitive set-up, so you start from a working scene
and spend your time where an animation is won – light, camera, timing, story. You deliver faster and stay competitive,
and the result still carries your skill.

**For sales teams:** Show a client how the machine looks and moves – early, convincingly, straight from the
engineering model.

**For engineers:** Renders and animations of your own machine without waiting for anyone – free and open source.

## What to do

1. `site/index.html`: the one line in the hero; a section **"Who it is for"** near the top (after the hero or after
   "Made with Fresing Render") with three short blocks – Engineers · Sales teams · Animators – and the four points;
   the animators' paragraph in it or as its own short block. Keep the page's style (Fresing palette A, IBM Plex Sans,
   existing classes); readable on a phone (check a narrow window). "Built on Blender" may link to the animators' part.
2. `README.md`: replace the first paragraph with the one line + the four points (short); keep the rest.
3. `docs/DESCRIPTION.md` (new): ready texts for others to copy – **25 words**, **60 words**, **one paragraph (~120
   words)**, each standing alone, plus the four points; a line on top: "For the Fresing website, stores, posts – keep
   the meaning: it speeds animators up, it does not replace them."
4. `tests/test_site.py`: the new section is there and the build keeps it (as for the other sections).
5. Look at the built page (`tools/build_site.py`, a 1280 px and a 400 px screenshot – small, cropped) before pushing.

## Rules

- **True claims only:** no speed numbers, no "same quality as …", no customer names, no competitor or AI product named.
  "Free and open source" (GPL) and "built on Blender" are true; "no Blender knowledge needed" is the app's aim (owner
  19 Nov) – write it as "step by step, in plain words".
- Warm about animators, never against AI as such: the case is that Fresing Render shows the **real** design.
- Never the Fresing 400, never the cable-lay vessel's equipment, nothing of the owner's employer (CLAUDE.md section 6).
- Plain English, short sentences, as the rest of the page.

## Done when

- [ ] Hero line + "Who it is for" on the page, phone-readable; README opening; `docs/DESCRIPTION.md`
- [ ] `tests/test_site.py` green; the docs run on GitHub green; the page published (Pages workflow after the push to
      `main`) and checked at the live address
- [ ] Two small screenshots (desktop, phone) in `tasks/img/0266/`
- [ ] Report filled in, merged (no version raise needed – site and docs only)

## Not in this task

The Fresing company website (later, its own project – it will use `docs/DESCRIPTION.md`); the user guide; the app's
welcome texts; the 3D web page.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
