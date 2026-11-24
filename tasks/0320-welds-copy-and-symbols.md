# 0320 – Welds round 2: a copy takes its welds along; weld symbols (ISO 2553) with one switch, and a weld list

**Who:** worker · **Status:** running · **Branch:** `task/0320-welds-copy-and-symbols`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
