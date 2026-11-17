# 0168 – Highlight looks round 2: more looks, each in several colours, one page with the animations

**Who:** worker · **Status:** open – can start · **Branch:** `task/0168-highlight-looks-2` (made from
`task/0133-highlight-looks`, **never merged**; a session branch `claude/…` is fine – say which in the report)
**Started by:** lead chat, 16 Nov 2026 (owner after looking at 0133's comparison page) · **Model:** Sonnet · effort
Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Learning lane, prototype branch only):** `fresing_render/blender/lesson.py`, `tools/lesson_looks_app.py`,
`tools/lesson_looks_sheets.py` and a new page folder `tasks/0168_page/` – **all on the branch only**. On `main` only
this file (report) and at most three small stills `tasks/img/0168_*.jpg`.
**Do not edit on `main`:** any app code, tests, `TASKS.md` rows of other tasks. Code tasks are running: this study
starts **no test run** (see "How to push").

## Goal

The owner picks the lesson highlight looks from one web page: many more looks than 0133 in all three groups (button,
closed section, part), each one moving as in the app, and each one in several colours chosen with a colour picker that
stays in the top corner while he scrolls. He is about 80 % sure he keeps Fresing Green; the page must let him check
that against the other colours.

## Background

- 0133 (report in `tasks/0133-highlight-looks.md`, code on branch `task/0133-highlight-looks`, commit 401905a) made
  button looks A–F, section markers 1–3 and part looks 1–3 behind `lesson.set_look(kind, key)`, in the Fresing palette
  from `site/style.css`; stills `tasks/img/0133_buttons.jpg`, `_sections.jpg`, `_parts.jpg` and GIFs of A–F.
- **Owner, 16 Nov:** wants **more options in all 3 groups**, **every look in a couple of colours**, a **colour picker in
  the top corner that follows the page when scrolling**, and **the animations in the new page** (0133's page showed
  stills; its GIFs were grabbed at ~6.5 pictures/s and look choppy). He likes the green of 0133 = **Fresing Green
  `#479B29`**.
- Rules kept from 0133: calm pulse (nothing faster than about 1 per second), test crane only (`test_crane_a.step`), no
  owner models (CLAUDE.md section 6), the look sits on **one** button of a joined pair.

## What to make

1. **Colour as a setting.** Every look takes its colour from one setting (`lesson.set_colour(hex)` or an argument of
   `set_look`), not baked into the look. Colours on the page, in this order:
   **Fresing Green `#479B29`** (default) · Green Bright `#5CBF37` · Amber `#F5B700` · Hi-vis orange `#FF6A13` ·
   Cyan `#1FB5D6` · White `#F2F2F2`. (No magenta – the owner turned it down.) Look F (Blender's blue) stays blue: show
   it once, not per colour. The text card's accent follows the colour.
2. **More looks – keep all of 0133's, add at least these** (rename or replace an idea if it does not work out, and say
   why; add your own where you see a good one):
   - **Buttons (new G–N):** G an underline that fills left → right once, then stays · H a soft light sweep across the
     button every 3 s · I a ring that ripples outward from the button every 2 s (calm, fades) · J a small pointing hand
     at the button's side that taps it slowly · K outline + soft outer glow (B's clarity with A's softness, no arrow) ·
     L a slow "marching" dashed outline · M a softer spotlight: rest of the side panel dimmed ~30 %, the Lesson panel
     **not** dimmed · N a tag outside the panel edge ("▶ here" / the step number) joined to the button by a short line.
   - **Closed sections (new 4–7):** 4 a bar on the header's left edge · 5 the header label in the colour with a slowly
     nodding fold arrow · 6 the header outlined with A's breathing glow · 7 a small arrow at the panel's edge pointing
     at the header, the step number in it.
   - **Parts (new 4–8):** 4 the part filled in the colour, half see-through, edges in the colour · 5 glow that breathes
     (1 with a slow pulse) · 6 X-ray: the rest as faint ghosts / thin lines, the part solid in its own colour with an
     outline · 7 the part outlined + a leader line from the text card to the part · 8 outline (2) + the rest faded (3)
     together.
3. **Clips that move smoothly.** Do not grab in real time: drive the looks' clock from the script (a time override in
   `lesson.py`), set it per frame and grab – **25 pictures per second, 3 s loops that join seamlessly** (a breath or a
   ripple ends where it starts). Grab with Blender's Resolution Scale **2.0** (sharp on the owner's screen; the page
   shows them at half size). Crop to what matters: the side panel round the target for buttons and sections, the 3D
   view round the crane plus the text card for parts. Same crane step for every look of a group (0133's steps 2, 3, 7).
   Encode **H.264 MP4** (`ffmpeg` is at `/usr/local/bin/ffmpeg`; `-preset veryfast`, small CRF, no sound,
   `yuv420p`, `+faststart`) – one file per look × colour, e.g. `clips/button_G_479B29.mp4`.
4. **The page** `tasks/0168_page/index.html` + `clips/` (+ a poster still per clip), one self-made page, no outside
   links or fonts beyond what is in the folder (it is published as a private claude.ai artifact by the lead):
   - **Colour picker fixed in the top-right corner** (stays when scrolling): six swatches with their name and hex, the
     chosen one marked; changing it swaps every clip on the page to that colour (same play position if easy). Keys
     1–6 also switch.
   - Three sections with a jump bar at the top: **Buttons**, **Closed sections**, **Parts**. Each look a card: letter or
     number, a one-line description, its looping clip (`autoplay muted loop playsinline`, load lazily – only clips near
     the screen play), its cost per redraw from your measurements, and a "new" tag for round-2 looks.
   - A **"pick" tick** per card (one per group, or two to compare) and a box at the bottom that writes the owner's
     answer as one line to copy: `0168 pick: button K, section 6, part 8, colour Fresing Green` (a Copy button).
     Remember the ticks in `localStorage` inside try/catch (it may be unavailable); the page must work without it.
   - A **"side by side" toggle** that shows the chosen colour's clip of a look next to Fresing Green's.
   - Styled in the Fresing palette (`site/style.css`: Deep Charcoal background, IBM Plex Sans from `site/fonts/` if it
     fits the size budget), readable on a laptop and a phone.
   - **Size:** whole folder ≤ ~25 MB (aim lower; report the size). If the clips do not fit, lower the CRF or crop
     tighter before dropping colours.
5. **Costs** per new look per redraw as in 0133 (software GL on the web machine, Python side), and for the part looks
   per 3D-view redraw. The colour must not change the cost (check one look in two colours).

## How to push (no test run)

- Code, tools **and the page folder** on the branch, pushed **once at the end** with **`[skip ci]`** in the commit
  message (never merged; the clips stay off `main`).
- This task file's report (+ at most three small stills `tasks/img/0168_*.jpg`, together < 1 MB) in a separate push
  to `main` touching only `tasks/` (starts no run), then check that `main` really contains your commit.

## Done when

- [ ] Colour is a setting; every look of 0133 plus at least 8 new button looks, 4 new section markers and 5 new part
      looks behind `set_look`; one button of a joined pair.
- [ ] One smooth 3 s seamless MP4 per look × colour (F once, in blue), 25 pictures/s, Resolution Scale 2.0.
- [ ] `tasks/0168_page/` on the branch: fixed colour picker top right, three sections, lazy clips, pick ticks + Copy
      line, side-by-side toggle, ≤ ~25 MB; opened and checked in a browser on the web machine (headless Chromium or
      similar: a scrolled screenshot showing the picker still in the corner).
- [ ] `tools/lesson_proto_app.py` and `tools/lesson_looks_app.py` still pass on the branch (run locally).
- [ ] Report: "In short (for the owner)" with one line per new look, the page's path on the branch, its size, costs,
      how the lead publishes it (below); branch pushed with `[skip ci]`; report on `main`.

## For the lead after this task

Publish `tasks/0168_page/` from the branch as a private claude.ai artifact (multi-file publish) and give the owner the
link; update the progress note. The owner answers with the Copy line ("0168 pick: …"); the pick goes into the 0062
brief (the highlight hook) and the lesson build tasks.

## Not in this task

Choosing (owner); Show me / Play on, Build it yourself, lessons, in-app guide, `fresing://` (after 0062); any change
on `main`'s app code; the side-panel overhaul (0062).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker, Sonnet), 16 Nov 2026. Everything, this report included, is on branch
**`claude/practical-heisenberg-jm99vr`** (made from `task/0133-highlight-looks`, pushed with `[skip ci]`, never merged).
Nothing was pushed to `main` (the session was told "branch only"): the lead copies this file and the three stills
(`tasks/img/0168_*.jpg`, 97 KB) to `main` if wanted.

### In short (for the owner)

One page, **`tasks/0168_page/index.html`** on the branch (the lead publishes it): 29 looks, each a 3 s loop in all six
colours (Fresing Green, Green Bright, Amber, Hi-vis orange, Cyan, White; F once, in Blender blue). Colour picker fixed top
right, keys 1-6 too, "Side by side" shows your colour next to Fresing Green, pick ticks per group (two allowed), a **Copy**
line at the bottom: `0168 pick: button K, section 6, part 8, colour Fresing Green`.
New looks (round 1's A-F, 1-3 stay):
- **Buttons:** G underline fills once - H light sweep every 3 s - I ring ripples out every 1.5 s - J pointing hand taps -
  K outline + soft glow - L marching dashes - M softer spotlight (rest dimmed 30 %, Lesson panel kept clear) - N tag with the
  step number, joined by a short line.
- **Closed sections:** 4 bar on the left edge - 5 header tinted, fold arrow nods - 6 outline + breathing glow - 7 arrow at the
  panel's edge with the step number.
- **Parts:** 4 half see-through fill + edges - 5 breathing halo - 6 X-ray (rest as ghost lines, part solid + outline) -
  7 outline + bold leader line with a moving dot - 8 outline + rest faded.
Honest notes: M's dimming is subtle on this dark panel; N's tag sits **inside** the panel (the side panel cannot draw outside
itself) and is small; J's hand covers part of the label. Breaths are now 1.5 s (so loops join at 3 s): a little quicker than
0133's 2 s, still under 1 per second.

### What changed (on the branch only)

| File | What |
| --- | --- |
| `fresing_render/blender/lesson.py` | colour is one setting (`set_colour`, `COLOURS`; "done" stays green); a clock the clip maker sets per picture (`begin_clip`, `set_clock`, `end_clip`; `_now()` everywhere, `_out()` fades once-only looks at the end so loops join); looks G-N, 4-7, 4-8; markers on the Lesson panel (header + last button, painted over) for look M; look 7's leader in the card |
| `tools/lesson_clips_app.py` | new: real app, UI scale 2.0, 75 pictures per clip (25/s), H.264 (veryfast, CRF 27, yuv420p, faststart) + poster per clip, costs |
| `tools/lesson_looks_page.py` | new: builds `tasks/0168_page/` (index.html, clips/, fonts/) |
| `tasks/0168_page/` | the page + 169 clips + posters |

### Tested and measured

Machine: web session, 4 cores, no graphics card, Blender 5.2.3 under xvfb (software GL), window 2000 x 1500 at UI scale 2.0
(1600 x 1000 was too small: the target never came into view), test crane. Four Blender runs at once, ~45 min,
**169 clips, 0 failed checks**; one grab took 0.3 s alone, 0.7 s with four running.
- **Page folder 7.5 MB.** Opened in headless Chromium: no script errors, picker still in the top right corner after scrolling
  (`0168_page.jpg`), a colour key swaps the clips, a pick shows in the Copy line. A phone-width screenshot was taken but not looked at.
- **Cost per side-panel redraw** (drawing only, Python side, Fresing Green): G 0.05 - H 0.39 - I 0.08 - J 0.33 - K 0.21 -
  L 1.25 - M 0.26 - N 0.83 ms; sections 4 0.06 - 5 0.14 - 6 0.22 - 7 0.92; parts (per 3D-view redraw) 4 0.42 - 5 0.75 -
  6 **2.1** - 7 0.70 - 8 0.89 ms. Round 1: A 0.21, B 0.93, C 0.14, D 0.05, E 0.17, F 0.43; sections 0.16/0.13/0.99; parts
  0.33/0.43/1.25. Colour does not change the cost (K in six colours 0.20-0.41 with four runs sharing the cores; part 6 1.96-2.26).
  Finding the button now also looks for the Lesson panel's two markers (two more pixel searches per redraw, not timed separately).
- `tools/lesson_proto_app.py`: 0 failed checks; `tools/lesson_looks_app.py`: 12 of 12 OK (both on this branch, scale 1.0).
- Not tried on the owner's PC (graphics card, Windows scaling). No subagents, no GitHub run (all `[skip ci]`).

### Open points / follow-up tasks

- Lead: publish `tasks/0168_page/` from the branch as a private artifact (multi-file publish); the pick goes into the 0062 brief.
- Look 6 (X-ray) draws every other part's edges, the most expensive: fine on the crane, to check on a big model once chosen.
- White and Amber with J's white hand / N's white text: readable here, recheck if chosen.
- The branch carries `lesson.py` changes on top of 0133's; the build task keeps only the chosen looks.

### Owner's pick (17 Nov 2026)

`0168 pick: button C + D, section 5 + 4, part 3 + 1, colour Fresing Green` – two finalists per group (the page's
"+" = two ticks to compare), first named = his first choice. Colour **Fresing Green `#479B29`**. Lead: both of each
pair go into the 0062 highlight hook behind one setting, first named as default; the owner settles each pair on his
RTX 3090 and the lesson build tasks drop the other. Details in the 0062 brief (lead note 17 Nov – highlight looks).
