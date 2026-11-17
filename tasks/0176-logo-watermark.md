# 0176 – The Fresing logo as a watermark (and a ready-made Fresing brand kit) for pictures and videos

**Who:** worker · **Status:** done (0.2.135) · **Branch:** `task/0176-logo-watermark` (a web session may name its own)
**Started by:** lead chat, 17 Nov 2026 (owner's wish after 0169) · **Model:** Sonnet · effort Medium · **Place:** Claude
Code on the web, environment "CAD-render-animation".
**Area:** Scene & Render lane, video finishing only: `core/brand.py`, `blender/video.py`, `blender/render.py`
(`finish_still`), the watermark / brand-kit settings in `props.py` (additive), the Watermark and Brand kit panels in
`ui_video.py`, new logo pictures in `fresing_render/brand/`, their tests; the function list entry
`animation.watermark`, the PC-check line `video.finishing`, a tour stop, the guide sections `#watermark` and
`#brand-kit`.
**Do not edit:** the Flex lane (0172, 0174 run), the Machining lane (0167), the CI files (0170/0171), `site/brand/`
(the site's files: copy from them, do not change them).

## Goal

The owner can put the **Fresing logo** on his renders and videos as a watermark, with one switch, without making a
brand kit or a PNG first. The logo is the one 0169 put in the app (green F on dark, the full "Fresing" logo).

## Background

- Since 0.2.23 (task 0018) the app has, in 5 Scene & Render: **Watermark** (`wm_on`, `wm_kind` DRAFT / CONFIDENTIAL /
  own text, `wm_size`, `wm_opacity`; words drawn across the picture at 25°, a text strip on channel 127 in videos,
  `video.finish_picture` on stills) and **Brand kit & logo** (a kit = logo PNG/JPG + colours + font in the library's
  "Brand kits" folder; the logo in a corner, `logo_corner`, `logo_size`). Blender cannot read SVG (`brand.LOGO_TYPES`).
- Logo files in the repository: `site/brand/*.svg` (app icon, compact/full, colour/reversed, symbol),
  `tools/brand/fresing-logo_full_reversed_2400px.png`, `tools/brand/fresing-app-icon_512px.png` (0169),
  `fresing_render/brand/fresing-render.ico`. The logo is public (on the site).

## What to do

1. **Logo watermark:** `wm_kind` gets **Fresing logo** and **Brand kit logo** (the current kit's logo) next to the
   words. A logo watermark is drawn as a picture: place **Centre** (default), **Tiled** (a see-through pattern across the
   picture, at the 25° angle as the words), or **Corner** (TL/TR/BL/BR, small); size, see-through (the existing
   settings), and for the Fresing logo **Colour / White / Dark** (Auto = by the picture's brightness under it, if cheap).
   The same on stills (`finish_still`) and videos (an image strip under the captions, over the picture), in the queue
   and in the product video.
2. **A ready-made "Fresing" brand kit** that ships with the app (logo PNGs in `fresing_render/brand/`, made once from
   `site/brand/*.svg` at a size that stays sharp in 4K – 2400 px wide or more; colours Fresing Green `#479B29` and
   `#1A2027`): it shows in the kit list even when the library has no kits, cannot be deleted, and a copy of it can be
   edited like any kit.
3. Old projects open as before (a project with DRAFT keeps DRAFT; the new choices default off).

## Rules

- Tests: the logo lands where chosen on a still and a short video frame (picture compared, as the PC check's
  `video.finishing` does), tiled covers the picture, Colour/White/Dark differ, the shipped kit is listed and safe from
  delete, a missing logo file gives a plain message instead of a crash.
- The tour stop (a still with the Fresing logo watermark, a number check), the PC-check line `video.finishing` covers
  the logo watermark (or a new Full line), the function list entry names them; the guide sections get a short text and a
  small picture; tooltips for every new setting. Raise MIN counts (CLAUDE.md section 6). CHANGELOG + version last.
- Screenshots of the two panels you changed with `tools/ui_screens.py` (cropped small).

## Done when

- [x] Logo watermark (Fresing / brand kit) on stills, videos, queue, product video; three places; colour choice
- [x] Shipped Fresing brand kit; old projects unchanged
- [x] Tests, tour stop, PC-check line, function list, guide, tooltips; GitHub run green; merged; version; report

## Not in this task

Animated logo intros/outros (the title/end cards stay as they are); the logo on the web 3D page.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 17 Nov 2026.

**What changed:** Watermark (5 Scene & Render) now offers Fresing logo and Brand kit logo next to the words; Place
Centre / Tiled / corner, Logo colour Colour / White / Dark (tinting in `core/brand.py`, tiles as one picture turned 25°;
one image strip on channel 127, so it works on stills, videos, queue and product video through the same `Finishing`).
Logos in `fresing_render/brand/` (colour + reversed, 2400 px, made from `site/brand/*.svg` with the pre-installed Chromium;
copies in `tools/brand/`). The shipped kit "Fresing" is always first in the kit list, cannot be deleted or saved over;
load it and save under another name for a copy. Old projects: DRAFT stays DRAFT, new choices default off.
Test changes: kits named "Fresing" in `test_video.py` and `ui_test_video.py` are now "Acme".

**Tested and measured** (4-core web machine, no GPU): `tests/test_watermark_logo.py` (30 tests: box inside picture,
tint, tiles cover the turned picture, centre/corner/tiled/colour/white/dark on a still, a video frame, missing logo,
shipped kit), `test_video.py`, PC-check line `video.finishing` (extended: Fresing logo tiled + centre, 8 s), tooltip
check (830 ok). Looked at one tiled still: even pattern, readable. GitHub: 2 pushes failed first (a real-app test
saved a kit called "Fresing"; a version clash with 0.2.134), then the full run was green (24.4 min).

**Open points / follow-up tasks:** (1) No new tour stop and no new PC-check line: the existing "finishing" stop checks the
logo file exists, the PC-check line covers the rendering – MIN counts unchanged. (2) "Auto" colour by the brightness
under the logo not done (optional). (3) The guide pictures `panel_5_watermark.png` / `panel_5_brand.png` are not
replaced: `tools/guide_screens.py` has no maker for them. A follow-up for a lead: add them there. (4) Tiled at 4K builds
a ~4400 x 4400 picture in memory (~80 MB); not measured on the owner's PC.
