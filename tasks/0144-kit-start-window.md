# 0144 – Render kit: a Fresing start window – graphics-card load limit, models, resume, quiet overnight runs

**Who:** worker · **Status:** done · **Branch:** `task/0144-kit-start-window`
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

- [x] Window, resume, status, duty cycle + temperature guard; tests (pure Python for the timing, the choices file,
      the resume list; the window's script checked for parse errors on GitHub's Windows job if it is PowerShell).
- [x] Independent review of the Windows-only parts (report says by whom and what changed).
- [x] Kit re-packed on the draft release `site-kit` (site-kit run green); GitHub run green; merged (no app version
      needed if only the kit changed – say so); report with numbered steps for the owner's next overnight run.

## Not in this task

The renders themselves; the take-in session (tasks/0112's report); the app's own render queue.

## Design (worker, 15 Nov)

- **Window: PowerShell 5.1 WinForms** (`site/render_kit/kit_window.ps1`, started by the .bat with `powershell.exe -STA
  -ExecutionPolicy Bypass`; nothing to install, Windows 11 has it). Blender's own Python has no tkinter. Three modes:
  `-Mode start` (the start window), `-Mode status` (the small status window with Pause/Resume/Stop) and `-Mode end`
  (a 60-second countdown with Cancel before sleep / shut down). ASCII only in the file (5.1 reads it as ANSI), CRLF.
  Logo: `fresing_logo.png` (the reversed full logo turned into a PNG, WinForms cannot draw SVG).
- **Pure Python, no Blender: `site/render_kit/kit_run.py`** – the choices (`DEFAULT_STANDARD`, `standard_path()` =
  `%LOCALAPPDATA%\Fresing Render\site_kit.json`, outside the kit; `load_choices`), quiet hours (`limits_at`), the
  expected wall time (`wall_seconds`: GPU seconds stretch by 100/p in 5-minute steps, the quiet window counted; the
  window has the same loop in PowerShell, a pytest compares them where `pwsh` exists), the `Pacer` (duty cycle: after a
  frame of t s wait t·(100/p − 1); temperature guard: wait while ≥ max until max − 3 °C, `nvidia-smi` read at most every
  10 s; pause / stop from `output/control.txt`; `status.json` for the status window), the `RunState`
  (`output/run_state.json`: the run's models and choices, the finished pictures/clips per model; `resume_info`).
- **make_site_pictures.py**: `--estimate-json=<file>` (models with their GPU/CPU seconds, the standard, the run to
  continue) for the window; `--choices=<file>` (the window's answer) and `--resume`; the stills call the pacer around
  each still, the clips through the queue's `should_stop` (called before every frame: the pacer measures the frame
  that just ended); a resumed clip keeps its frames (the queue's own resume, same fingerprint). Stop keeps what is done:
  JSON, contact sheet and zip of the finished pictures, exit code 4.
- **.bat**: estimate → start window (cancel ends; a window that cannot start falls back to the old Enter/time prompt)
  → status window started next to the console → Blender → open the output → end mode (sleep / shut down unless
  stopped). Power limit (`nvidia-smi -pl`) left out: it needs admin rights.
- **Checks**: the window's parse on GitHub's Windows job (`tools/ci_windows_install.ps1`, PowerShell 5.1 parser) and
  in pytest with `pwsh` on Linux runners.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 15 Nov 2026 (branch `task/0144-kit-start-window`).

**What changed:**
- New `site/render_kit/kit_window.ps1` (Windows PowerShell 5.1 WinForms, nothing to install; Blender's Python has no
  tkinter): **start window** (Fresing logo `fresing_logo.png` made from `site/brand/fresing-logo_full_reversed.svg`,
  palette from `site/style.css`) – load slider 40–100 %, max temperature Off / 70–85 °C, quiet hours (from–to, own load
  and max temperature), models ticked with their time (a missing STEP file unticked), Start now / at, When done
  nothing / sleep / shut down, a live "Expected: about … – done at about …", Back to standard, Cancel, Start; **status
  window** (model n of m, step, progress bar, % done, load, °C, expected end; Pause/Resume, Stop with a question; asks
  to resume when closed while paused; notices when the run's black window was closed); **end countdown** (60 s, Cancel;
  only after a finished run, not after Stop or a crash; shutdown uses `/f` so an open Notepad cannot hold it up).
- New `site/render_kit/kit_run.py` (no Blender): choices + the standard in `%LOCALAPPDATA%\Fresing Render\site_kit.json`
  (outside the kit; Start saves load, temperature, quiet hours, when done; **Back to standard = the kit's own settings**:
  100 %, no limit, no quiet hours, nothing), quiet hours over midnight, `wall_seconds`, the `Pacer` (pause after a frame
  of t s: t·(100/p − 1); temperature guard via `nvidia-smi` every ≥ 10 s, waits until 3 °C under the max; Pause / Stop
  from `output/control.txt`; `output/status.json`), the `RunState` (`output/run_state.json`).
- `make_site_pictures.py`: `--estimate-json=`, `--choices=`, `--resume`; the pacer around every still and through the
  queue's `should_stop` before every clip frame (+ the last frame); every finished still/clip recorded at once; a
  continued run skips them and keeps the clip's frames (the skipped still's camera is still made – without it the
  queue's fingerprint changed and all frames were rendered again, found in the real run below); Stop = zip of what is
  done, code 4. The true exit code goes through `output/run_result.txt` (Blender turns any non-zero end into 3).
- `Make site pictures.bat`: estimate → start window → status window → run → end countdown; if the window cannot start
  (exit ≠ 0/10) the old console question comes, with the saved standard. README: 7 steps + "The start window".
- `tools/make_site_projects.py` packs the 3 new files; `tools/ci_windows_install.ps1` parses `kit_window.ps1` with
  Windows PowerShell 5.1 and runs its time loop (one probe, a second).
- **Power limit (`nvidia-smi -pl`) left out:** it needs admin rights; pauses + temperature guard need none.
- **No run list:** one output folder holds one run, so at most one run can be continued per kit folder (owner: only if
  needed). **No app version:** only the kit and CI tools changed, the app is unchanged (no release).

**Tested and measured:**
- `tests/test_kit_window.py` (11 tests): choices/standard, quiet hours, expected wall time, a fake renderer at 70 %
  (card busy 70.0 % of the wall time, wall = the expected time within 1 %), quiet hours switching mid-run, the
  temperature guard (fake readings 84→76 °C at max 80: waits 60 s), Pause/Resume/Stop, the run state, the estimate JSON,
  the whole run loop stopped after 2 pictures (code 4, zip) and continued (only the rest made, run finished), and the
  window's own time loop against Python's under `pwsh` (ran on GitHub's Linux runner).
- Real Blender (bpy, 4-core web machine, Thor small): run at 70 % stopped by `control.txt` during the clip → code 4,
  1 of 2 done; continued at 100 % → still skipped, clip went on from frame 5 (frames 1–4 kept), 2 of 2 done.
  `test_kit_end_to_end_small` passes (186 s here).
- GitHub run 43773631877 (branch) green, incl. Windows: PowerShell 5 parses the window and gives 5743 s / 21600 s as
  Python. Not tested anywhere: the windows themselves on a screen, nvidia-smi on a real card, sleep / shutdown – the
  owner's PC only.
- Runs: 2 (the branch, then the merge with main).

**Independent review:** a helper agent that did not write the code read the .ps1, .bat and `kit_run.py` (8 findings,
all fixed): exit code 4 could not reach the .bat (→ `run_result.txt`); a PowerShell that cannot run looked like
Cancel (Cancel = 10 now, set-up errors exit 2 → console); closing the status window while paused left the run paused
for good (asks now); the countdown ran after crashes too; the status window stopped looking for "ended" after a
crash; `os.replace` of status.json retried; `shutdown /f`; window brought to the front. Its re-check found one more
(the countdown's TopMost undone), fixed. No other subagents.

**Open points / follow-up tasks:**
- The owner's first run tells whether the expected time and the window's layout at his screen scale are right.
- The temperature guard counts no waiting in the expected time (it depends on the room).
- If the CAD models or models.ini change between a stop and Continue, the remaining models use the new settings;
  a changed clip renders all its frames again (the queue's fingerprint).

**Owner's next overnight run (numbered steps):**
1. Download the new `fresing_site_kit.zip` from the draft release "Site kit" and unzip it next to the old kits
   (right-click > Extract All... > Extract).
2. Close Fresing Render. Open the folder "Fresing site kit" and double-click "Make site pictures.bat".
3. The black window works out the time; then the Fresing start window opens.
4. Set **Graphics card load** (e.g. 70 %) and **Max. temperature** (e.g. 80 °C). Tick **Quiet hours from** 22:00 to
   07:00 with load 60 % and max 70 °C if you want it quieter at night.
5. Leave all models ticked; **Start: Now** (or At 23:00); **When done: Sleep** or **Shut down**.
6. Check the green line "Expected: about … – done at about …", then click **Start**. A small status window appears
   with the model, how far it is and the temperature; **Pause** and **Stop** are there. Keep the black window open.
7. If the run stops (PC restarted, Stop): double-click the .bat again – "Continue the run of … (n of m done)" is
   ticked – click Start.
8. In the morning: upload `output\site_pictures_<date>.zip` to the draft release (README step 7) and send the lead
   the last lines of `output\log.txt` (they say the pauses and the cooling waits).
