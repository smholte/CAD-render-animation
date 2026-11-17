# 0177 – Render kit windows: text cut off at Windows display scaling

**Who:** worker · **Status:** open · **Branch:** `task/0177-kit-window-layout` (a web session may name its own)
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

- [ ] Both windows: every text, field and button fully visible, nothing overlapping, at 100–200 % (step 5's check green
      on the Windows job) and on a 1366 × 768 screen at 150 %
- [ ] Models' times readable
- [ ] Choices, standard file, resume, Pause / Stop, countdown unchanged in behaviour (0144's tests still green)
- [ ] Windows-only code reviewed by a helper that did not write it (CLAUDE.md section 2)
- [ ] The kit on draft release `site-kit` re-packed by the site-kit workflow after the merge (check the asset's date)
- [ ] Report below filled in; merged to `main`; owner's check as numbered steps (download the kit again, double-click,
      look at both windows) – no app version needed (kit only), unless the release procedure says otherwise

## Not in this task

- No change to what the kit renders, its models, timings or `make_site_pictures.py` beyond step 6.
- "FarmBot Genesis (file not found: skipped)" is expected: the owner puts `farmbot.step` into the kit's `models` folder
  himself (README line 17) – not a bug.
- The app itself (`fresing_render/`), other lanes' files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
