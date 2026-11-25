# 0320 – Welds round 2: a copy takes its welds along; weld symbols (ISO 2553) with one switch, and a weld list

**Who:** worker · **Status:** done · **Branch:** `task/0320-welds-copy-and-symbols`
**Started by:** lead, 24 Nov 2026 (owner 11:44: "when making a copy of an assembly I want welds to also come with";
"the weld symbols can come in. A simple toggle to activate these and deactivate (standard it's deactivated)") ·
**Model:** Opus · effort Medium
**Area:** Welds lane – `core/welds.py`, `blender/welds.py`, `ops_welds.py`, `ui_welds.py`, a new
`blender/weld_symbols.py` (+ `core/weld_symbols.py`, no Blender: the ISO 2553 text and the list); additive: 0293's copy
code (`blender/copy.py` / `ops_copy.py` – one hook that copies welds), the app's labels code (read, or one additive
draw hook), `props.py`, `core/functions.py`; tests, guide, tour, PC check, CHANGELOG.
**Not:** the weld looks (done in 0319), the Rust slider (0318), the Welding workspace (0321 – but add your functions to
it, see 3), 2D drawings (later).

## Goal

Copying a welded subassembly or model gives a copy with the same welds; and anyone who needs it can switch weld symbols
on (off by default) and get a weld list.

## Background

- 0319 (0.2.231) report, Open points: a copied subassembly should copy each weld whose two parts are inside it – a new
  `FRWeld` with the copies as `part_a` / `part_b`, the same faces, `seam_data`, `rel` and settings, then
  `welds.rebuild`. 0293 (0.2.227) copies model objects only, so welds stay with the original today. The weld data has
  everything a symbol needs: kind, throat a, length, all round, intermittent piece / pitch.
- 0293's open point: cables, drums and tracks are not copied either – not this task.

## What to do

1. **Copy carries welds**: every weld whose two parts are both in the copy comes along (Ctrl+C / Ctrl+V, Paste here,
   right-click Copy). A weld with only one part inside: left out, and the copy window's "what was left out" line says
   so. Undo removes the copied welds too. Model update of a copy: as 0293's rule, welds follow.
2. **Weld symbols**: a switch **Weld symbols** in 3 Looks > Welds (and in the Welding workspace), **off by default**,
   saved per project. On: an ISO 2553 label beside each seam (arrow line to the seam, reference line, the symbol for
   fillet / butt, "a5", length or "n × l (e)" for intermittent, the all-round circle, both-sides symbol), readable at any
   zoom, drawn with the app's label style; hidden in renders unless *Show in renders* is ticked (off by default).
   Optional ISO 2553 system A only – say if B is needed.
3. **Weld list**: a window with one row per weld (number, parts, type, size, length, process, finish) – the number
   also on the symbol; *Export CSV*. Add `looks.weld_symbols` and the list to the **Welding workspace** if 0321 is
   merged; if not, 0321 adds them (say in the report).
4. Guide (Welds: Copies, Symbols, List), function entries (`since=`), the tour stop of 0319 extended, a Full PC-check
   line (a copied weldment has the same number of welds; the symbol text of a known weld is right).

## Done when

- [ ] Copy / paste of a welded subassembly and of a whole model gives the welds (tests, incl. undo and one-part welds)
- [ ] Symbols switch, off by default; correct ISO 2553 text for fillet, butt, all-round, intermittent, both sides (tests)
- [ ] Weld list + CSV
- [ ] Tests added/updated; full suite passes; screenshots checked; version fields; owner's test steps; merged, release

## Not in this task

Weld looks, Rust, the Welding workspace itself, 2D drawings, copying cables / drums / tracks.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 24 Nov 2026. Branch `task/0320-welds-copy-and-symbols`. Released as
0.2.240.

**What changed:**
- **Copies take their welds** (`blender/welds.py` `for_copy` / `copy_to`, one hook each in `copy.py` `_select`,
  `_paste`, `_snapshot` / `_roll_back`, `summary`): every weld whose two parts are both in the copy is copied raw onto
  the copied parts (shared meshes, so faces, `seam_data`, `rel`, ticks and settings stay true), named "… (2)", and
  rebuilt; a weld with one part outside goes into the paste's "left out" line; a failed paste removes them again.
  Undo: the welds are scene data, Ctrl+Z takes them with the copy (real-app test).
- **Fault of 0319 fixed** (found by this task's model-update test): `welds.carry_over` marked *every* weld not on the
  updated model as lost – a second model's, a frozen parts copy's, and a whole-model copy's (its group update runs per
  model). Now only welds of the models being updated are touched.
- **Weld symbols**: `core/weld_symbols.py` (no Blender: ISO 2553 system A text – fillet ◸/◺ with a-size, square butt ‖
  up to 4 mm / single-V, double-V both sides, intermittent "n × l (e)" with e = the gap and n as the bead lays it,
  "1 × l" for one piece, all round ○, ground flush ‾, tail with the ISO 4063 process number; the list rows and CSV with
  a BOM and formula-safe cells). `blender/weld_symbols.py`: the switch `scene.fresing_welds.symbols` (off by default,
  saved) and `symbols_render` (off), a POST_PIXEL draw handler (fixed screen size, the brand kit's box colour, white
  lines/text, arrow + head, reference line, dashed line on one-sided welds, circle, tail, number), `label_todo` for
  renders (added in `callouts.draws_at`; `callouts.any_labels` now gates stills, videos and the queue).
  The symbol describes a weld's longest ticked seam; "both sides" = a second ticked seam of the same kind within 10 %.
- **Weld list** (`fresing.weld_list`, a function window – in `form_window.WINDOWS`) and **Export CSV…**
  (`fresing.weld_list_csv`), both allowed in the Client view (`lock.ALLOWED`: reading changes nothing).
- Panel 3 Looks > Welds: a row Weld symbols | Show in renders and **Weld list…** above the list (always drawn once a
  weld exists). Function entries `looks.weld_copy`, `looks.weld_symbols`, `looks.weld_list` (since 0.2.240); guide
  sections Copies / Weld symbols / Weld list, copy-paste section names welds, `panel_3_welds.png` new; tour set +
  stop "welds" (symbols on, checks the texts; changed 0.2.240); PC check Full line `looks.weld_symbols`
  (MIN_LINES_FULL 150); real-app test `ui_test_welds.py` +4 checks (20).
- **Welding workspace (0321)**: 0321 runs beside this task and was not merged – **0321 adds `looks.weld_symbols` and
  `looks.weld_list`** to it.

**Tested and measured** (4-core web machine, test weldment):
- `test_weld_copy.py` (10), `test_weld_symbols_core.py` (10), `test_weld_symbols_independent.py` (83, written by an
  independent subagent that did not write the code: it found 2 minor faults – a NaN length crashed the text, a part
  name like `=HYPERLINK(…)` went into the CSV as a formula – and suggested one decimal below 20 mm and no gap for a
  single piece; all four done), plus `test_welds*.py`, `test_copy*.py`, `test_form_window.py`: 249 passed;
  functions / places / guide 41 passed; tour stop welds (Go + check) passed; PC check line OK (4.8 s; copy of the
  7-weld weldment 463 ms); real-app welds 20/20 (symbols drawn, Paste + Ctrl+Z).
- GitHub: see below.

**Owner's test steps** (after Update now to 0.2.240):
1. Help > Make test tour project, open it, stop **Welds**, **Go**: beside each of the seven welds a dark label with
   its symbol and number 1–7 – "a5" with a triangle above and below the line for the fin, a circle at the bend of the
   three round welds, "135 / 141 / 131" in the tail. Zoom in and out: the symbols keep their size.
2. 3 Looks > Welds: untick **Weld symbols** – they go; tick it again. Render image: no symbols. Tick **Show in
   renders** and render again: each symbol is a label pointing at its seam.
3. **Weld list…**: seven rows; **Export CSV…**, save, open the file in Excel.
4. Right-click the model's top row in 2 Structure (or click the model and press Ctrl+C), then Ctrl+V: the copy stands
   beside it with all seven beads; the Welds list now has 14 welds ("… (2)"). Ctrl+Z: the copy and its welds go.
5. Copy only the base plate and the fin: the copy has one weld; the line after the paste names the welds left out.

**Open points / follow-up tasks:**
- Symbols are not moved apart when two lie on each other on screen (in renders the label placer does it).
- Butt weld size (s) is not written; a butt is ‖ or V by the thinner plate. ISO 2553 system B is not offered (say if
  needed).
- Welding workspace entries: 0321.
