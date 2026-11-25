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

**Chat / date:** Claude Code on the web, 25 Nov 2026 – 0.2.247

**What changed:**
- New `blender/place_popups.py`. **How it is built:** both popups are drawn by one POST_PIXEL draw handler in the 3D
  view's window region (added only while a popup is up, removed when it closes – nothing is drawn per frame otherwise;
  drawn only in the area it belongs to, so a second window or a second 3D view shows nothing) and their clicks are read
  by a modal operator in that window – not Blender's popups, which close when the mouse leaves them.
  - `fresing.unlock_popup`: opened by `fresing.move_key` (G / R) when everything selected is held by "Locked in place",
    and by right-click > **Move / turn…** (`fresing.place_window`) on a locked part. Name, **Unlock** (tooltip as asked),
    **×**. Unlock (or Return) unlocks every locked owner of the selection (`held_owners`, via `place.lock_owner`) and
    starts the same move at once: Blender's translate / rotate (`release_confirm=False`), or the Move / turn window.
    Click outside / × / Esc close it; the click outside does nothing else. While it is up it holds the keyboard; mouse
    moves, wheel and middle button pass (the view can be turned).
  - `fresing.lock_again`: after a **confirmed** move of what the popup unlocked (Blender's move: a timer watches
    `Window.modal_operators` and compares the world matrices; Place / the Move / turn window: `place.apply` calls
    `after_move`). Top left of the 3D view, right of an overlapping toolbar, below an overlapping header and below the
    view's own text (3 lines; 12 with statistics on) – same place every time. **Lock it again** locks exactly what was
    unlocked; × and Esc close at once; after `STAY` = 5 s any click in that window closes it and is passed on. It
    passes every other event on. A second move of the same thing keeps one popup; another Unlock replaces it.
  - **Undo:** Unlock = its own step ("Unlock '…'"), the move Blender's own step – two clear steps. Lock it again = one
    step.
- `place.py`: the status-bar text now says "click Unlock in the popup, or right-click it > Unlock so it can move …"
  (fallback kept); `popup()` = no popup for S (parts keep their size – unlocking does not change that), a built
  animation (its own message stays), the Client view, or a selection only partly locked (Blender moves the free part,
  as before).
- Guide (Moving and turning parts, 2 Structure's lock line, Place step 1), function entry `structure.move` changed
  0.2.247 + PC-check line `structure.unlock_popup` (Full; `MIN_LINES_FULL` 156), CHANGELOG.
- **No tour stop:** the popups are transient and modal (a tour stop's still would need the modal running at Go);
  `structure.move` had no stop either. The real-app test covers the clicks instead.

**Tested and measured** (4-core web machine, test crane):
- `tests/test_place_popups.py` 12 tests (who is unlocked, cancelled move = no popup, unlocked in 2 Structure = no popup,
  one popup for a second move, replace, Lock it again exact, 5 s, card places at scale 1 and 2, hit test, no popup for
  S / built animation / Client view); `test_place.py`, functions, usage, guide, keys, place/remove: 130 passed.
- Real app `tools/ui_test_move.py`: 27/27 (14 before) – G opens the popup by the mouse (no Blender move), typed keys
  held, Esc / a click outside / × close it with the boom still selected, locked and in place; Unlock → translate runs at
  once, X 100 Enter moves 100 mm; Lock it again shows top left below the view's text; a click after 0.6 s leaves it
  (and still deselects), after 5 s a click closes it; a second round's Lock it again locks only BOOM.ASM; at UI scale 2
  the popup is twice as big, inside the view, and its × works. Looked at both popups in a screenshot (not committed).
- PC check `structure.unlock_popup` + `structure.move`: 2 OK (bpy module).
- GitHub: see runs below.

**Open points / follow-up tasks:**
- Not checked in the real app: a second Blender window (the draw handler only draws in the popup's own area; the
  modal handler lives in the window G was pressed in – a unit-level reason, not a measurement).
- A move unlocked through the popup and then cancelled leaves the part unlocked without a popup (as the brief asks:
  no popup after a cancel).
- Place's own **Move with the mouse** button stays greyed on a locked part (its lock is beside it in the same panel).
- No independent reviewer (no Windows-only code; the real-app test drives every click path).
