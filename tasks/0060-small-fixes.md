# 0060 – Small fixes: floor in queued stills vs videos, test-run waiting, Blender folder spellings

**Who:** worker · **Status:** open – after 0059 (same Quality & delivery files) · **Branch:** `task/0060-small-fixes`
**Started by:** lead chat, 9 Nov 2026 (open points of 0053 and 0054)
**Lane:** Quality & delivery (`tools/ci_status.py`, `update_helper.py`) + Scene & Render (floor placement, the
surroundings code that places the floor; no `animation.py` changes unless the floor of a video is set there – then
only that); tests
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Fixes

1. **Floor (0054 open point):** a still re-places the floor under the model's lowest point, an animation keeps the
   floor of frame 1; a part that swings below the floor during a video is cut by the floor in the video but not in a
   queued still of that frame. Make a queued still of an animation frame use the animation's floor (the frame shown
   = the video's frame), and say in the guide what the floor does. Test with the crane swinging a part below frame 1's
   lowest point.
2. **`tools/ci_status.py --wait` (0053 open point):** on a merge commit whose first parent differs only in the task list
   it says "no test run" although GitHub ran one. Judge by the commit's own run (or both parents). Test with a recorded
   API answer.
3. **Blender folder spellings (0053 open point):** matching other Blenders by path misses 8.3 short names and `subst`
   drives. Compare normalised long paths (`GetLongPathNameW`, case-insensitive) and the file's identity (volume serial
   + file index) where possible. Test with mocks on Linux; the Windows CI job runs the PC check line `updates.safe`.

## Done when

- [ ] Three fixes with tests; GitHub green incl. Windows.
- [ ] Guide note on the floor; if the test tour (0059) is merged: nothing to add (no new visible function).
- [ ] Merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0060 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
