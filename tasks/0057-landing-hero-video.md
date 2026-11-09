# 0057 – New video at the top of the landing page

**Who:** worker · **Status:** open – can start · **Branch:** none needed (site-only change, straight to `main` after the
docs run is green)
**Started by:** lead chat, 9 Nov 2026 (owner's wish: replace the video at the top of
https://smholte.github.io/CAD-render-animation/)
**Lane:** Quality & delivery (landing page) – `site/media/` (video, poster, `media.json`), `site/CREDITS.md` if the
credits list the video; no app code, no `tools/build_site.py` changes unless a bug is found
**Model:** Sonnet · effort Low · **Place:** **a new chat in the claude.ai project "STEP rendering App" (Cowork)**, not
Claude Code on the web – the owner's raw video is too big to send there (CLAUDE.md section 2, the exception for the
owner's own files). The owner attaches the video to the first message.

## Goal

The owner's new render is the looping video at the top of the landing page, small enough for the web (≤ 8 MB, H.264,
no sound, ≤ 1080 p high), with a poster picture and a caption, and the page is live with it.

## How it works now (task 0047)

- `site/media/media.json` → `"hero"`: now `fresing_mill_air_blast.mp4` + `_poster.jpg`, caption "Milling on a Fresing
  mill: … (rendered with Fresing Render)", `"model": "fresing_mill"`, `"keep": true` (keeps it at the top when
  `--take` brings in new pictures).
- `tools/build_site.py --hero-video <file> --start <s> --length <s> --model <id> --caption "<text>"` cuts
  and compresses with ffmpeg (`web_mp4`: ≤ 1080 p, ≤ 8 MB, no sound), makes the poster
  (`poster_of`, first frame) and writes `media.json`. `tools/build_site.py` then builds `dist/site/` and checks it
  (too-big files are reported).
- A push to `main` that only changes `site/` runs the docs-mode tests (~2 min) and republishes GitHub Pages
  (`.github/workflows/pages.yml`).

## Steps

1. **Ask the owner first (one message, short):** which part of the video (start and length – the top video loops;
   10–20 s works well), the caption (keep "(rendered with Fresing Render)" at the end), and whether the old milling
   video should stay further down the page in the gallery or go. Also: does the video show anything that must not be
   public (customer names, part names)? The repository and page are public; the owner's landing-page renders and
   videos are an agreed exception (CLAUDE.md section 6).
2. Set-up by hand (CLAUDE.md section 4): clone the repository, install ffmpeg and ImageMagick if missing (no Blender
   needed). Connect GitHub for the push.
3. Run `--hero-video` with the owner's answers. If the result is over 8 MB, `web_mp4` lowers the quality by itself;
   if it still does not fit, shorten the cut and say so. Check the poster frame is a good picture (not black, not a
   title card); if not, take a frame from a better moment (`ffmpeg -ss`) and name it in the report.
4. If the old video goes: remove its `.mp4` and poster from `site/media/` and from `media.json`; if it stays, add it
   as a gallery item (as `--take` does for videos: `<video … preload="none">` + caption).
5. Build and check: `tools/build_site.py` (and `pytest tests/test_site.py`). Look at `dist/site/index.html` in a
   browser (Playwright screenshot, desktop and phone width): video plays, poster shows, caption fits. **Send the
   owner the screenshot and the cut video (attachment) and wait for his OK before pushing.**
6. Push to `main` (only `site/` and this task file + `TASKS.md`), wait for the docs run (green) and the Pages
   republish, then open https://smholte.github.io/CAD-render-animation/ and check the new video is there (browsers
   cache: add `?v=2` to the address when checking).

**Plan B if the owner's file is too big even for the chat:** he exports a shorter or lighter version from his video
editor (e.g. 1080 p, 20 s), or uploads the raw file as an asset of a **draft** release on github.com (repository →
Releases → Draft a new release → attach the file → Save draft; up to 2 GB) and the chat downloads it with `gh release
download`. The draft release can be deleted afterwards (as `landing-video-raw` from 0047).

## Done when

- [ ] The owner's answers (cut, caption, old video) in the report.
- [ ] New hero video ≤ 8 MB, ≤ 1080 p, no sound, with poster; `media.json` updated, `"keep": true`.
- [ ] Old video removed or moved to the gallery, as the owner chose.
- [ ] Owner's OK on the screenshot before the push.
- [ ] Docs run green; page live with the new video (checked on the live address).
- [ ] Report filled in; `TASKS.md`: 0057 done.

## Not in this task

New pictures for the gallery (`--take`, the owner's render kit – the Thor and OpenArm re-renders from 0047 are still
open; if the owner attaches those too, they may be taken in the same push). Page layout or text changes.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Owner's answers:**

**What changed:**

**Checked** (sizes, screenshot, live page):

**Open points / follow-up tasks:**
