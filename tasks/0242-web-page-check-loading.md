# 0242 – The Windows web-page PC-check lines stop failing at random ("loading"); licence notices text brought up to date

**Who:** worker · **Status:** done (0.2.183) · **Branch:** `claude/modest-einstein-fendd4` (the web session's own branch)
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

- [x] The cause named in the report with the stage marks that showed it
- [x] The two Windows web lines green in at least **10 runs in a row** on GitHub's Windows job (say how they were
      repeated and how long it took); none needed the second try, or the report says how many did and why
- [x] A page that never becomes ready (a test with a broken page) still fails the line
- [x] `THIRD-PARTY-NOTICES.md` and its copy agree and no longer say the licence texts are missing
- [x] Tests for `read_page`'s second try (a fake browser), precheck green
- [x] Report filled in (GitHub runs used and why), merged, released (the version follows the page change)

## Not in this task

What the web pages show or how they are made (`web3d.py`, export, the page's look); other PC-check lines; the owner's
open rows of the notices (licence of Fresing's pictures, brand-note wording, House format, FarmBot).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026; released as 0.2.183 (with the owner's extra job: the flaky app-icon step of 0229).

**What changed:**
- **Cause (stage marks):** a copy of the two check pages wrote `data-fr-stages` (time of each step) on `<html>`
  (`tools/tmp0242/stage.py`, branch history). On GitHub's Windows machines 0.5–3.7 s of the page's virtual clock passed
  before the hold started (Linux: 0.09 s) – the hold sat at the end of `fr_page.js` – and the hold stopped at "ready",
  before the first picture. The failures of `main`'s code in the A/B below were all **"ready PHONE frames 0"**: ready,
  but the clock jumped before a picture was drawn, so no places. The 2026-11-17 failures (0189) took the whole line
  5–6 s: a clock jump, not a slow PC.
- **Fix:** the hold is now the page's first script (`_HOLD` in `core/web3d_env.py`, first thing in `<head>`) and lasts
  until the first picture is drawn (self-test: both answers) or an error; `fr_page.js` no longer has its own. Each read
  still moves the clock a few ms, so a page that never gets ready runs out of clock and reads "loading" (cap 30,000
  reads as a last stop).
- `read_page`: a page still "loading" is opened once more with a 60 s clock (`tries`, `first`); the two lines refuse
  "still loading" in plain words and add "the page needed a second, longer opening" to their text when it happened.
- **App icon (0229's flake):** the copy had just been deleted while Windows still held it ("delete pending"): the
  rename onto its name was refused, the rename aside found no file (WinError 2). `winexe.swap_in` tries again for up to
  3 s; `take_out` waits up to 0.5 s for the name to go and says when the copy is still there. Independent review
  (a Sonnet helper that did not write it): cause plausible, no way to lose both copies, no endless loop; its point on
  the log text taken.
- Licence notices (step 4): already up to date on `main` (0206 / later edits had changed all five places) – nothing to
  do; root file and the copy in `fresing_render/licenses/` are byte for byte the same.
- CLAUDE.md section 8: the web3d lesson rewritten, a new one on delete-pending files.

**Tested and measured:**
- GitHub Windows (windows-2025, Edge), throw-away workflow `tmp-0242.yml` (removed before merging): run 44807123605 –
  6 machines × 60 openings of the staged pages, alone and 3 at once: 360 of 360 ready (the bare page does not show it).
  Run 44809615178 – 10 machines, the real PC-check lines (Blender 5.2.3 as a Python module + Edge), `main`'s code and
  this branch's taking turns, 3 times each per machine: **old `web3d.small` 3 of 30 failed** ("ready PHONE frames 0"),
  old `web3d.under` 30/30; **new 30/30 and 30/30, none needed the second opening.** ~6 min wall time.
- Web machine: a real page ready at the first opening (1 s); a page that waits for ever reads "loading" after two
  openings in 6 s (no time-out); fake-browser tests of the second try. 130 tests of the web / icon files pass.
  `test_web3d_env_blender.py::test_page_opens_in_a_browser` failed once here on unchanged code too (Auto quality did not
  lower under load) – not this task.
- GitHub runs: the two throw-away runs above; three Tests runs of in-between commits cancelled by hand; then 4 full
  runs: 0.2.181 taken by 0236 (precheck), 0.2.182 red only on this task's new real-browser test (Chromium aborts on
  GitHub's Linux machines: it now falls back like the other browser tests), green 44814560546, 0243 took 0.2.182 with
  code: merge + 0.2.183, green 44823644177 (Windows A and B green, PC check included); then this documents push.

**Open points / follow-up tasks:**
- A page waiting on a read that never ends (a stream) keeps the browser's clock stopped for good: a time-out ("not
  counted"), not "loading". Not seen on any check page.
- `test_page_opens_in_a_browser` (Auto lowers the quality) depends on load – flaky on a busy machine.
