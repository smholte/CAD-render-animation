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

**Chat / date:**

**What changed:**

**Tested:**

**Open points / follow-up tasks:**
