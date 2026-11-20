# 0242 – The Windows web-page PC-check lines stop failing at random ("loading"); licence notices text brought up to date

**Who:** worker · **Status:** open – can start · **Branch:** `task/0242-web-page-check-loading`
**Started by:** lead, 20 Nov 2026 (lead review of the reports 0187, 0189, 0193, 0195, 0227; 0206's open point 1) ·
**Model:** Opus · effort Medium
**Area:** Quality & delivery lane, plus the page's test clock – `fresing_render/web/fr_page.js` (**only** `holdTestClock`
and where it starts), `fresing_render/core/web3d_env.py` (`read_page` only), the `web3d.*` lines in
`fresing_render/pccheck/checks.py` (only how they call `read_page` and judge "loading"), their tests;
`THIRD-PARTY-NOTICES.md` and its copy in `fresing_render/licenses/` (text only).

## Goal

GitHub's Windows job no longer goes red at random on the web-page PC-check lines (`web3d.small` "the page gave no places
of its parts (loading)", `web3d.under` "the page does not show the seabed …: {}"). Every task stops paying an extra
~20-minute run for it. A page that really does not load still fails.

## Background

- Seen in five reports: 0187 (failed twice, passed on the 3rd try), 0189 (twice), 0193 (twice, once in a re-run),
  0195 (`web3d.under` then `web3d.small`, 3rd try green), 0227 (`web3d.small`, 20 Nov). Every time the job passed on a
  re-run with no code change.
- CLAUDE.md section 8 has the mechanism: a browser without a window under `--virtual-time-budget`
  (`core/web3d_env.read_page`, budget 20,000) jumps its clock ahead whenever the page waits for work off the main
  thread (`createImageBitmap`, a Blob read) and dumps the page as "loading". 0062 added `holdTestClock` in
  `web/fr_page.js` (a test page fetches a 1-byte blob of its own until it is ready) – it fixed the web machine
  (5 of 6 → 0) but the Windows job still fails now and then. Suspects to check first: whether the hold starts before
  the packed model's unpacking (`data-gzip="1"`, a `DecompressionStream` / Blob read) and the WebP pictures, whether
  `?places=1` and the plain `?frames=` query of `web3d.under` both start it, and Edge's own behaviour on Windows.
- `read_page` today: one try, no retry; `state` = "loading" when the page never wrote `data-fr-state`.

## What to do

1. Find why the Windows job still sees "loading": add stage marks in a copy of the page (`data-…` on `<html>`, as
   section 8 says) and run the two lines on GitHub's Windows job enough times to see it (a throw-away branch with
   `[full run]` or a workflow input that repeats only the Windows web lines – your choice, say which in the report).
2. Fix the cause in the page's test clock if it is there (the hold covers every off-thread wait of a test page, from
   the first byte to "ready").
3. Belt and braces in `read_page`: when the dump says "loading", open the page once more with a longer budget
   (e.g. 60,000) before giving up. Still "loading" after that = the line fails as today (never "not counted").
   Log in the line's text when a second try was needed, so a slow PC is visible.
4. **Licence notices (0206 open point 1):** `THIRD-PARTY-NOTICES.md` still says the licence texts are missing (the header
   "Two things reach a PC without a licence text", the "Task 0206 to do" line in 2.1, the meshoptimizer row, section
   1's "not yet looked at on Windows", owner row 5). Since 0206 the texts are in both release zips and every install:
   bring those places up to date, root file and the copy in `fresing_render/licenses/` the same. Only what 0206
   changed – the owner's open rows stay.
5. CLAUDE.md section 8: replace the "web3d.small" lesson's last part with what was found and fixed.

## Done when

- [ ] The cause named in the report with the stage marks that showed it
- [ ] The two Windows web lines green in at least **10 runs in a row** on GitHub's Windows job (say how they were
      repeated and how long it took); none needed the second try, or the report says how many did and why
- [ ] A page that never becomes ready (a test with a broken page) still fails the line
- [ ] `THIRD-PARTY-NOTICES.md` and its copy agree and no longer say the licence texts are missing
- [ ] Tests for `read_page`'s second try (a fake browser), precheck green
- [ ] Report filled in (GitHub runs used and why), merged, released (the version follows the page change)

## Not in this task

What the web pages show or how they are made (`web3d.py`, export, the page's look); other PC-check lines; the owner's
open rows of the notices (licence of Fresing's pictures, brand-note wording, House format, FarmBot).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
