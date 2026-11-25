# 0338 – Quick unlock popup by the mouse, "Lock it again" popup after the move

**Who:** worker · **Status:** running · **Branch:** `task/0338-quick-unlock-popups`
**Started by:** lead, 25 Nov 2026 (owner 11:07: moving or turning a locked assembly means hunting for Unlock in
2 Structure – "a small popup with a button to unlock it", and after the move "a small popup in the top left corner of the
3D view to lock it again"; owner's answers 11:1x below; replaces 0328 row 29's "second G unlocks", taken out of 0335)
· **Model:** Opus · effort Medium
**Area:** Place lane – `blender/place.py` (the "locked in place" refusal of G / R / S, task 0307), `blender/ops_place.py`
(`fresing.move_key`, `set_lock`, the Move / turn window's refusal), `blender/ui_place.py`, a new `blender/place_popups.py`
(both popups), `core/functions.py` (additive entry), their tests, guide, PC-check line, tour stop, CHANGELOG.
**Not:** `lock.py` (the G / R / S key list stays as it is – `fresing.move_key` is already the key's operator; 0295 and
0332 change `lock.py`), `form_window.py` / `ops_setup.py` window placement (0331), `panels.py` (0335).

## Goal

Pressing G or R (or Move / turn) on a locked model or subassembly no longer sends the user to 2 Structure: a small popup
by the mouse unlocks it and the move goes on; after the move a small popup in the 3D view's top left offers to lock it
again.

## What to do

1. **Unlock popup** – opens when G / R / S (or Move / turn…) is refused because of "Locked in place":
   - **close to the mouse**, small: the model / subassembly name, an **Unlock** button (tooltip: "Unlock it so it can
     move. You can lock it again afterwards"), and an **×**.
   - **Unlock = unlock and keep moving** (owner): it unlocks what held the move (all locked owners of the selection, as
     `place._locked` finds them) and starts the same G / R / S the user pressed, as if the key had worked.
   - Closes on a click **outside** the popup, on the **×**, and on **Esc**. Nothing changes when it is closed that way.
   - Not in the Client view (it stays refused there, as now). A built animation's refusal keeps its own message.
2. **"Lock it again" popup** – after a move / turn **of something unlocked through the unlock popup** (owner: only
   those; things unlocked in 2 Structure or the right-click menu get no popup) is confirmed (not when it is cancelled):
   - in the **top left of the 3D view, not overlapping** the view's header, the "… Perspective" text, the Lead motions
     drop-down, Measure labels or anything else drawn there – below / beside them; same place every time.
   - The name, a **Lock it again** button (locks exactly what the unlock popup unlocked), an **×**, and a separate way to
     close it as the owner asked: it **stays at least 5 seconds**; after those 5 s **a click anywhere in the 3D view or in
     another menu closes it** (the click still does its own job). **Esc** closes it at any time (an Esc that cancels a
     running move only cancels the move).
   - A second move of the same thing before it closes keeps one popup (no stacking); unlocking something else replaces it.
3. Undo: Unlock + the move are one undo step or two clear ones (say which); Lock it again is its own undo step.
4. The old refusal text in the status line stays as the fallback (keyboard-only users, a popup that cannot open) and now
   says "… or click Unlock in the popup".

## Watch

- Blender's own popups close when the mouse leaves them – the owner wants **click outside / × / Esc** instead: say how
  you built it (a modal operator with a GPU-drawn panel, or a small region) and test it in the real app
  (`tools/ci_real_app.py`), incl. a 2560 px screen scale and a second window.
- The top-left popup must not take keys or clicks from the view while it is up (apart from its own buttons); drawing it
  must cost nothing measurable per frame during playback.
- Every visible change: tooltip, guide (2 Structure's "Locked in place" part and Place), PC-check line, tour stop /
  function-list entry with `since=` / `changed=`. Screenshots with `tools/ui_screens.py`.

## Done when

- [ ] G / R / S / Move / turn on a locked assembly → popup by the mouse; Unlock → moves at once; click outside / × / Esc
      close it with nothing changed
- [ ] After that move → "Lock it again" top left, not over anything, ≥ 5 s, then closed by a click anywhere; × and Esc work;
      Lock it again locks exactly what was unlocked
- [ ] Client view and built animations behave as before
- [ ] Tests added/updated; full suite passes; GitHub run green; real-app check
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
