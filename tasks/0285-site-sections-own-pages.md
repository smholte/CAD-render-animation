# 0285 – Landing page: the section buttons open pages of their own (not one long scroll)

**Who:** worker · **Status:** open – can start (site only, not a code task) · **Branch:** `task/0285-site-pages`
**Started by:** lead, 23 Nov 2026 (owner's wish, passed on by the House Planner lead 21 Nov: "a little rework" of the
Fresing Render page, **kept simple like now and with the colours as now**; the top bar stays as it is – logo, Fresing
Render, More tools ▾, the section buttons; **Who it is for, What it does** and the other section buttons open **a page
of their own**, "not just a long scroll") · **Model:** Sonnet · effort Medium
**Area:** `site/` (index, How it works page from 0267, new pages), `tools/build_site.py`, `tests/test_site.py`. Not
the app, not the render kit.

## What to do

1. Each section button in the top bar goes to its own page (Who it is for, What it does, How it works, Download, …);
   the start page keeps a short intro, the picture / video / 3D rows and links to the pages. Same top bar, colours,
   fonts and footer (with 0277's licence line) on every page; the open page's button highlighted.
2. Works offline as today's site build does; on a phone (390 px) and at 2560 px; no broken links (test).
3. **Keep the top bar's look** – House Planner copies it (task 0049 there). More tools keeps
   https://smholte.github.io/house-planner/ as House Planner's link. If the bar's look changes after all, say so in the
   report: the lead tells the House Planner lead.
4. Pictures of every page at 2560 and 390 px in the report.

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 22 Nov 2026

**What changed:** Every top-bar button is now a page of its own: `who/`, `what/` (with "Built on Blender"), `model/` (Turn it
yourself, as before), `how-it-works/`, `install/` (download, 3 steps, What's new), `guide/`. The start page keeps the hero,
the short facts, the picture / video / 3D rows, four "Find out more" cards linking to the pages, Made by Fresing and the
credits. The new pages share `site/layout.html` (same bar, tool switcher, fonts, colours, footer with the GPL line; the open
page's button is highlighted); their text is in `site/pages/*.html`. **The top bar's look is unchanged** (only its links went
from `#section` to pages) – the House Planner lead needs to hear nothing new; More tools still links to House Planner.
Files: `site/`, `tools/build_site.py`, `tests/test_site.py`. No app code, no version bump.

**Tested:** `pytest tests/test_site.py` 33 passed (new: every menu button is its own page with the same bar and footer;
a broken link on a new page is found); `build_site.py` check 0 problems (no broken links, no script on new pages). Pictures
of all five pages at 2560 and 390 px in `tasks/img/0285/` (no sideways scroll at either width, measured in Chromium).

**Open points / follow-up tasks:** none. The footer of the new pages links to the credits on the start page instead of
repeating the list.
