# 0307 – Moving parts with G / R does not stick: find why, fix it, and a short guide for the owner

**Who:** worker · **Status:** running · **Branch:** `task/0307-moving-does-not-stick`
**Started by:** lead, 23 Nov 2026 (the lead told the owner that G / R, then X / Y / Z and a number, move a part outside
Full access – task 0253 kept those keys. Owner 20:12: "Moving parts / assemblies is not working for me. I see some
numbers appear in the UI and when I click or press Enter they just disappear. So maybe a study to check this out? And
if it works, make a little guide for me.") · **Model:** Opus · effort Medium
**Area:** Place lane, first task (0292 Place, turn and remove waits for this one). Findings first, then the fix where it
lives: probably one of `lock.py` (keys, the Client view's put-back), `handlers.py`, `joints.py` (joint parts, rest
places, `lock_location` on joint objects), `animation.py` (keys written by Build / Go to pose), `linkages.py`'s handler,
`quiet.py`; a test that fails before the fix; the user guide's section on moving parts; CHANGELOG.
**Not:** the Place window, fields, gizmo, Remove (0292 builds those); Blender's own G / R.

## What to do

1. **Reproduce** in the real Blender under xvfb with simulated keys (G, X, typed number, Enter; also a mouse move + left
   click; R the same) on the test crane: a model root, a subassembly, a single part; a fresh import; with a joint on the
   part; after **Build & play**; after **Go to pose**; with a mechanism; in All functions, Client view and Full access;
   a part picked in the view and one picked in 2 Structure. Write down in a table which cases move and stay, and which
   jump back (the owner's case: the numbers show in the header while moving, then the part is back on click / Enter).
2. **Find the cause** of each "jumps back": e.g. animation keys from Build / Go to pose that put the part back at the
   next update (Blender's auto keying off), a driver or constraint on the part (joint members, cylinders, Child Of from
   vessel motion), a handler that resets places, the Client view lock, or the selection picking an app object (a joint's
   empty) instead of the part. Say it plainly.
3. **Fix** what is wrong and safe to fix here (a test that failed before for each). Where moving cannot work by design
   (e.g. a part moved by the animation), the app **says so at once** in the status bar instead of silently putting it
   back: "This part is moved by the animation – take the Build off first (6 Animation > …)" – the exact wording in
   plain words, with the place from `places.where()`.
4. **A short guide for the owner** – in the report, numbered, click by click (select, G / R, X / Y / Z, a number, Enter,
   Esc; moving a whole model vs a part; what to do after a Build), and the same as a section "Moving and turning parts"
   in `docs/USER-GUIDE.md` (0292 extends it later).

## Done when

- [ ] The case table in the report; every cause named; fixes with tests that failed before; a real-app test of G + X +
      number + Enter that stays moved (and one after Build that shows the message)
- [ ] Guide section + the owner's numbered steps in the report; full suite + GitHub run green; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026 · version 0.2.216

**Case table** (real Blender 5.2.3 under xvfb, simulated keys, test crane `test_crane_a.step`, web machine 4 cores;
"before" = 0.2.215):

| Case | Before | Now |
| --- | --- | --- |
| Fresh import, boom clicked (BOOM.ASM selected), G X 100 Enter – All functions | numbers show, **nothing moves** | nothing starts; status bar: "'BOOM.ASM' is locked in place – right-click it > Unlock so it can move …" |
| same, G + mouse move + left click; R Z 30 Enter | nothing moves | same message |
| same in Full access | nothing moves | same message |
| a single part picked (2 Structure part row) | nothing moves | message names its subassembly |
| subassembly unlocked, G X 100 Enter / G + mouse + click / R Z 30 Enter | moves, stays | moves, stays (1 s later, after a frame change) |
| unlocked part with a joint (boom joint + luffing cylinder), G / R | moves, stays | moves, stays |
| joint part, G, then Build & play | move kept | move kept |
| after Build & play, G | moves, but **undone at the next Build or at Stop** | nothing starts; "The animation is built: … Stop it first (4 Motion > Stop it to move joints by hand)" |
| after Stop it to move joints by hand, G | moves | moves (and a later Build keeps it) |
| G, then Go to pose | put back where the pose had it (by design) | same – said in the guide |
| S on a part | nothing (scale always locked) | "Parts keep their size from the CAD model" |
| Client view | nothing selectable, G has nothing to move | unchanged (the Client view allows only viewing operators) |
| model root | locked like every subassembly | same message; top row of 2 Structure > Locked in place unlocks the whole model |
| mechanism parts, vessel motion | not run with keys: by reading the code the link empties / Child Of are moved, never the part's own place, so a move stays; after Build the "built" message applies | – |

**Causes:** (1) **every import locks all subassemblies and parts in place** (`logic.lock_all`: lock_location /
rotation / scale). Blender's G / R then run, show their numbers, move nothing and say nothing – the owner's case. The
only unlock was a button under the 2 Structure tree. (2) **A built animation** saves how things stood and puts it back
at the next Build and at Stop: a move made after Build vanished later. (3) **Go to pose** puts subassemblies where the
pose has them (by design). (4) Blender's click cycling: a second click on the same spot selects the object behind
(found by the test: the trolley) – said in the guide. No handler, driver or Client-view lock put places back.

**What changed:** new `blender/place.py` (the Place lane's file; 0292 builds on it): `fresing.move_key` on G / R / S in
Object Mode (`lock.APP_KEYS`) checks what Blender would move (`movers`, `why_not`) – locked / built / scale → the reason in the status bar at once and Blender's key is not started; otherwise `PASS_THROUGH`, Blender's own
G / R unchanged (some of a selection locked: the rest moves, with the message). Right-click menu: last entry **Unlock so
it can move** / **Lock in place** (`fresing.ctx_unlock`, not in the Client view). Tooltip of Locked in place names G / R.
Not in the Client view (nothing selectable there; its allow-list keeps viewing operators only). Locks stay the default (no change to imports or saved projects). Guide: section "Moving and turning parts" (anchor
`moving-parts`), the right-click list and "These stay" keys. Function `structure.move`; PC-check Full line
`structure.move` (MIN_LINES_FULL 124); real-app test `move` (14 checks, group pccheck-b).

**Tested and measured:** web machine (4 cores, no GPU): `tests/test_place.py` (7) – the locked message failed before
(no check existed: G stayed silent); with test_keys_right_click, test_functions, test_user_guide, test_usage,
test_places 94 passed; `tools/ui_test_move.py` 14/14 (G X 100 Enter stays, mouse + click stays, R Z 30 stays, locked
and after-Build messages, Stop then G moves); PC-check line `structure.move` OK in 2 s; tooltip report --strict clean.
GitHub runs: see below. Subagents: none (small change; no Windows-only code, so no independent review).

**Owner's steps on your PC** (after Update now to 0.2.216):
1. Open a project (or Import STEP… the test crane).
2. Click a part in the 3D view, press **G**: the status bar at the bottom says "'…' is locked in place – right-click it
   > Unlock so it can move …" and nothing moves.
3. **Right-click** the same part → click **Unlock so it can move** (the last entry).
4. Click the part once, move the mouse over the 3D view, press **G**, then **X**, type **500**, press **Enter**: the
   subassembly moves half a metre along X and stays there.
5. **R**, **Z**, **90**, **Enter**: it turns a quarter turn and stays. **Esc** (or a right-click) while moving puts it back.
6. The whole model: in 2 Structure click the top row of the tree → **Locked in place** (it changes to "Unlocked: can be
   moved") → G / R as above.
7. With an animation built (after Build & play): G says "The animation is built …". Click **Stop it to move joints by
   hand** at the top of 4 Motion, move it, then **Build & play** again – the new place is kept.
8. After a move, a saved pose still has the old place: save the pose again (4 Motion > Poses & exploded views).

**Open points / follow-up tasks:** no test-tour stop (the PC-check line and the real-app test cover it; the guide
picture `img/view_right_click.png` does not show the new last entry yet – next guide-picture pass or 0292). 0292: the
fields / gizmo can reuse `place.why_not` and `lock_owner`. Possible later choice for the owner: unlock model roots by
default so a whole model moves without the extra click.

**Owner's check on your PC:**
