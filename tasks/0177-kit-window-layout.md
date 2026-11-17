# 0177 – Render kit windows: text cut off at Windows display scaling

**Who:** worker (web session) · **Status:** done (17 Nov) · **Branch:** `task/0177-kit-window-layout` (a web session may name its own)
**Started by:** lead, 17 Nov 2026 · **Area:** Site kit lane: `site/render_kit/kit_window.ps1` (both windows), its tests
(`tests/test_kit_window.py`), `site/render_kit/README.txt` only if a text changes, the CI step that parses / checks the
script. **Model · effort:** Opus · Medium. Claude Code on the web, environment "CAD-render-animation".

## Goal

The kit's start window ("Fresing site pictures - start") and status window ("… - running") show every word, field and
time in full on the owner's PC and at any Windows display scale (100–200 %), so he can read and set everything.

## Background

Owner's screenshots, 17 Nov 01:50 (his Windows 11 PC, kit from `site-kit`; described in words, not committed):

**Start window**
- Headings cut in half at the top: "Graphics card", "Models", "Start", "When done" (only the lower or upper half of
  the letters shows).
- "Load" label cut; the load value "94 %" cut at the bottom.
- "Max. temperature" shows as "Max. temp" and its drop-down is missing – only an empty white strip where it should be;
  the hint after it shows only "…until the card i" at the right edge.
- The grey explanation ("Less than 100 % = a pause after every frame …") runs past the right edge and its second line
  is cut at the bottom.
- Quiet-hours row: "Quiet hou", times "22:0" and "07:0" (last digit cut), "to" → "t", "load" → "loa", "% max." → "m";
  the fields overlap each other.
- Models list: every line is cut at the right ("(about 1 h 21 mi", "(about 31 min at full lo"); no way to read the
  time per model.
- Start row: "Now" → "No", "At" → "A", "23:00" → "23:0".
- "When done" → "When don"; "after a 60-second countdown you can cancel" → "…you can".
- "Back to standard" → "Back to standa".
- Only the green "Expected: about 3 h 28 min - done at about Tue 05:13." and the Cancel / Start buttons look right.

**Status window**
- "Waiting to start", "Starts at 02:15" and "load 60 %" cut at the top or bottom; "Closing this window does …" cut at
  the right.

**Likely cause (lead's reading of the code – check it):** `kit_window.ps1` calls `SetProcessDPIAware()`, sets
`AutoScaleMode = Dpi` with `AutoScaleDimensions` 96, then places every control at fixed pixel bounds (`SetBounds`,
`Add-Label … W H`) for 96 DPI and sets `ClientSize` again at the end. The fonts are in points, so at 125–150 % they get
bigger in pixels while the boxes keep their 96-DPI size (no Suspend/ResumeLayout round the adds, `ClientSize` reset
after them) → every text is clipped. Fixed-height labels (20 px) clip vertically; fixed widths clip horizontally.

**Owner's display scale:** not known yet (he answers on 17 Nov after 17:00; the lead pastes it into the session).
Test at 100, 125, 150, 175 and 200 % regardless. The status window's "Starts at 02:15 · load 60 %" is right: the owner
had chosen "At 02:15" and quiet hours for that run (owner, 17 Nov 01:55) – no behaviour bug.

## Do

1. Make both windows lay out from the actual DPI / font size: either a scale factor applied to every position and size
   (`$s = DeviceDpi / 96`, all bounds through one helper) or auto-sizing layout (`TableLayoutPanel` / `FlowLayoutPanel`,
   `AutoSize` labels with a maximum width so long hints wrap) – the worker picks; one consistent way for both windows.
   Long texts wrap onto extra lines and the window grows to fit; nothing overlaps.
2. Models list: wide enough for the longest line at the window's width, or the time per model in its own column
   (e.g. a `ListView` with check boxes and two columns), or a horizontal scroll bar – the time must be readable.
3. Time pickers and number boxes wide enough for "23:00" / "100" with the spin buttons at every scale.
4. The window fits a 1366 × 768 screen at 150 % (≈ 911 × 512 logical): if it would be taller than the screen's working
   area, the middle (settings + models) scrolls and the buttons stay visible.
5. A check that runs on GitHub's Windows job (Windows PowerShell 5.1, which the kit uses): build both windows without
   showing them at several scales (e.g. a test switch that multiplies the font size by 1.0 / 1.25 / 1.5 / 1.75 / 2.0,
   or the real DPI path if it can be forced), then for every control compare `TextRenderer.MeasureText` (with wrapping
   where the control wraps) against its client size and check no two visible controls overlap and all lie inside the
   form. Fails with the control's name and text. Also save a `DrawToBitmap` PNG per scale as a CI artifact (not
   committed) so the lead and the owner can look.

## Done when

- [x] Both windows: every text, field and button fully visible, nothing overlapping, at 100–200 % (step 5's check green
      on the Windows job) and on a 1366 × 768 screen at 150 %
- [x] Models' times readable
- [x] Choices, standard file, resume, Pause / Stop, countdown unchanged in behaviour (0144's tests still green)
- [x] Windows-only code reviewed by a helper that did not write it (CLAUDE.md section 2)
- [ ] The kit on draft release `site-kit` re-packed by the site-kit workflow after the merge (check the asset's date)
- [x] Report below filled in; merged to `main`; owner's check as numbered steps (download the kit again, double-click,
      look at both windows) – no app version needed (kit only), unless the release procedure says otherwise

## Not in this task

- No change to what the kit renders, its models, timings or `make_site_pictures.py` beyond step 6.
- "FarmBot Genesis (file not found: skipped)" is expected: the owner puts `farmbot.step` into the kit's `models` folder
  himself (README line 17) – not a bug.
- The app itself (`fresing_render/`), other lanes' files.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 17 Nov 2026.

**What changed:**
- `site/render_kit/kit_window.ps1`: the three windows (start, status, end countdown) no longer place anything at fixed
  96-DPI pixels. Every distance goes through `Px` (= the screen's DPI / 96 after `SetProcessDPIAware`), `AutoScaleMode`
  None, every text is measured with its own font (`TextRenderer`, and labels now draw with it too), a row helper
  (`Set-Row`) puts controls side by side and starts a new line when they do not fit; long hints wrap and the window
  grows. The models list is a `ListView` with check boxes and its own column "Time at full load". When the start window
  is taller than the screen's working area its middle part scrolls; the expected time and Back / Cancel / Start stay
  visible. The status window lays out again on each new text, never shrinks (Pause / Stop do not jump) and is left
  alone while minimised. Over a scrolling start window the mouse wheel on the load slider / number box scrolls the
  window instead of changing the load. Behaviour otherwise as in 0144 (choices file, standard, resume, Pause / Stop,
  countdown, exit codes). Lesson: `Sc` (first name of the scale helper) is a Windows PowerShell 5.1 alias of
  Set-Content and wins over a function – a test now refuses function names that are 5.1 aliases.
- `tools/ci_kit_window_layout.ps1` (new): the layout check. Loads the window script with `-Mode layout -TestScale`
  (fonts and distances as at that display scale on a 96-DPI screen) and `-TestScreen` (switches the runner's screen to
  that size for its own process, `ChangeDisplaySettings` CDS_FULLSCREEN – the runner has 1024 x 768 and Windows cut
  bigger windows to it). Builds the start window (with / without "Continue the run", an extra 89-hour model with a long
  name), the status window with its five longest texts and the end countdown; checks every visible control:
  `TextRenderer` text size vs its client size (labels wrapped at their width; check boxes with the box; buttons with
  both captions; drop-downs every item + arrow; time and number boxes "23:59" / "100" + spin buttons; list columns and
  every row visible), no overlap between neighbours, everything inside its window / panel, the window not taller than the
  screen's working area. First it proves on a deliberately broken window that it finds a cut text, an overlap and a
  control outside. Then it clicks through the start window (Back to standard, untick a model, At 02:15, load 75, Sleep,
  Start) and checks the choices file and the standard. One PNG per window and scale (`DrawToBitmap`, plus the scrolled
  lower half) in the Windows job's artifact `windows-install`, folder `kit_window/`.
- `tools/ci_windows_install.ps1`: runs it in Windows PowerShell 5.1 at 1.0, 1.25, 1.5 (1366 x 768 and 1920 x 1080),
  1.75 and 2.0; a fault is a Problem of the Windows job with the control's name and text.
- `tests/test_kit_window.py`: `test_window_layout_from_the_dpi` (no bare pixel numbers in SetBounds / sizes, no function
  named like a 5.1 alias, ASCII + CRLF, the Windows job's scales); the pwsh parse test also parses the check.
- `site/render_kit/README.txt`: the time column, the window follows the display scale and scrolls on a small screen.

**Tested and measured** (name the machine and the model):
- GitHub's Windows runner (windows-2025, Windows PowerShell 5.1, screen switched to 1920 x 1080 / 1366 x 768): LAYOUT OK
  at all six runs; click-through OK at all six. Window sizes measured there: start 580 x 762 px at 100 % (with
  "Continue"), 870 x 638 at 150 % on 1366 x 768 (middle scrolls), 1160 x 906 at 200 % on 1920 x 1080 (scrolls); status
  460 x 235 at 100 %, 920 x 478 at 200 %. I looked at the pictures at 100 %, 150 % (1366 x 768, top and scrolled) and
  200 %: every word, field and time in full.
- Not testable here: the real DPI path (Windows at 150 % – the check emulates it with fonts × scale at 96 DPI, so the
  title bar, check-box glyph, list row height and slider are the 96-DPI ones). Measuring with the real fonts and system
  sizes makes it the same layout, but only the owner's PC proves it.
- Independent review (a helper that did not write the code) of `kit_window.ps1`, the check and the Windows-job step: no
  blocking defect; its four points were fixed (right-click / double-click on a model name flipped the tick through my
  own click handler – removed, the list ticks by its box as normal; a minimised status window was resized every 2 s;
  the status window could shrink and grow; the mouse wheel over the slider changed the load while scrolling).
- Local: `tests/test_kit_window.py`, `tests/test_render_kit.py`, `tests/test_site.py` pass.
- Full runs: 1 (run 43997041597, green, 25 min; the Windows job's layout check OK at all six scales).
- Runs: a temporary workflow ran only the check on Windows 5 times while the layout was worked on (first: the `Sc`
  alias; then green), deleted before the merge; full runs: see below.

**Open points / follow-up tasks:**
- The owner's check on his PC (below). His display scale was not known when the task was done.
- Owner's steps: 1. On the draft release `site-kit` (github.com/smholte/CAD-render-animation/releases) download the kit
  zip again (its date is today's) and unzip it over the old one (the `models` folder stays). 2. Double-click
  "Make site pictures.bat". 3. In the start window every heading, the load value, "Max. temperature" with its drop-down,
  the grey hints, the quiet-hours times "22:00" / "07:00", every model with its time in the right column, "Now", "At
  23:00", "When done" and "Back to standard" show in full. On a small screen the middle part has a scroll bar and Start
  stays at the bottom. 4. Click Cancel (or start a run) – the status window shows "Waiting to start" / the model and
  "Closing this window does not stop the run." in full.
