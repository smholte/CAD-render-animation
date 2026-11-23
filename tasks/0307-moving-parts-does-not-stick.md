# 0307 – Moving parts with G / R does not stick: find why, fix it, and a short guide for the owner

**Who:** worker · **Status:** open – can start · **Branch:** `task/0307-moving-does-not-stick`
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
