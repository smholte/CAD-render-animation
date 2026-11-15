# 0144 – Render kit: a Fresing start window – graphics-card load limit, models, resume, quiet overnight runs

**Who:** worker · **Status:** running · **Branch:** `task/0144-kit-start-window`
**Started by:** lead chat, 15 Nov 2026 (owner, before a ~4 h overnight kit run) · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Site kit lane):** `site/render_kit/` ("Make site pictures.bat", `make_site_pictures.py`, `models.ini`,
`projects.py`), `tools/make_site_projects.py --kit` (packing), their tests. **Windows-only code** (the window, the
graphics-card queries): independent review by a helper that did not write it (CLAUDE.md section 6).
**Do not edit:** the app's render code (`render.py`, `queue.py`), the Web 3D lane (0134, 0142).

## Goal

When the owner double-clicks the kit, a small Fresing-branded window comes first: he picks how hard the graphics card
may work (e.g. 70 %), which models, when to start, what happens at the end – and an overnight run stays quiet and can
be continued if it stops.

## Background

- The kit (task 0112) renders the site's models on the owner's RTX 3090 (Windows 11, driver 617.42, no admin rights
  needed by the kit); the newest kit says "Expected: about 4 hours". It already has "start later" and one result zip
  `site_pictures_<date>.zip`.
- A "% of the graphics card" is not a Cycles setting. Ways that need no admin rights: **pauses between frames** (duty
  cycle: after a frame that took t s, wait t·(100/p − 1) s – average load and heat follow p, so the fans stay low;
  the expected time grows by 100/p) and **a temperature guard** (`nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,power.draw`
  is read-only, no admin: wait while above a set °C). A real power limit (`nvidia-smi -pl`) needs admin – offer it
  only as an explained extra, off by default, or leave it out (say which in the report).

## What to build

1. **Start window** (Windows, no install: e.g. PowerShell WinForms from the .bat, or what Blender's Python can show
   – say what you chose), Fresing logo and palette (`site/brand/`, `site/style.css`):
   - **Graphics-card load** slider 40–100 % (default 100), with the expected time updating (e.g. "about 5 h 40 min at
     70 %"); optional **max temperature** (off / 70–85 °C).
   - **Models**: tick list from `models.ini` with each one's expected time; all ticked by default.
   - **Start**: now / at a time (the existing start later); **when done**: nothing / sleep / shut down.
   - **Quiet hours** (owner, 15 Nov 23:48): a time window (e.g. 22:00–07:00) with its own load % and max
     temperature (e.g. 60 %, 70 °C); outside it the normal load (e.g. 100 %). The expected time counts both.
   - **Saved as the standard** (owner): the choices (load, temperature, quiet hours, when done) are kept as the
     defaults for every next run – also after a new kit is downloaded: keep them outside the kit folder (e.g.
     `%LOCALAPPDATA%\Fresing Render\site_kit.json`, the folder the app already uses), with a "Back to standard"
     button.
2. **Resume:** a run that stopped (PC restarted, closed) shows "Continue the run of <date> (<n> of <m> done)" – it
   skips finished pictures/clips. A **run list** only if more than one unfinished run exists (owner: only if needed).
3. **While it runs:** a small status window or console line – model, frame, % done, load %, temperature, expected
   end time; Pause / Resume / Stop (Stop keeps what is done).
4. The duty cycle and temperature guard in the render loop of `make_site_pictures.py` (frames of stills, clips and
   turntables alike), measured: a test with a fake renderer proves the waits and the expected-time sum.
5. Kit README / the guide's kit section: the window, what each choice does, numbered steps.

## Done when

- [ ] Window, resume, status, duty cycle + temperature guard; tests (pure Python for the timing, the choices file,
      the resume list; the window's script checked for parse errors on GitHub's Windows job if it is PowerShell).
- [ ] Independent review of the Windows-only parts (report says by whom and what changed).
- [ ] Kit re-packed on the draft release `site-kit` (site-kit run green); GitHub run green; merged (no app version
      needed if only the kit changed – say so); report with numbered steps for the owner's next overnight run.

## Not in this task

The renders themselves; the take-in session (tasks/0112's report); the app's own render queue.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
