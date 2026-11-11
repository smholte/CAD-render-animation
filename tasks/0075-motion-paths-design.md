# 0075 – Motion paths the offshore way: design study (findings only, no code changes)

**Who:** worker · **Status:** open – can start now (Wed 11 Nov) · **Branch:** `task/0075-motion-paths-design` (the
report only – **do not push to `main`**; the lead brings it over)
**Started by:** lead chat, 11 Nov 2026 · **Lane:** none – reads code and searches the web; prototypes only in a
scratch folder outside the repository; runs next to every lane
**Model:** **Opus · effort High** · **Environment:** "CAD-render-animation"

## Goal

Motion paths are the owner's priority 4 and the last big feature: cable from a carousel over sheaves through a
tensioner and chute into the sea, a winch drum spooling wire, tensioner track pads running round. Study 0069 (#3)
found how others do it. This study turns that into a **design the lead can write a Fable-day brief from**, building
on 0058 (hoses, cables and drag chains – Thursday) so the two fit together.

## What to do

1. Read `tasks/0058-hoses-cables-drag-chains.md`, `tasks/0069-improvement-study.md` (#3, sources 30–38), CLAUDE.md,
   and the motion code (`joints.py`, `animation.py`, `mechanisms`, `linkages`) – how a speed or a joint drives parts now.
2. Design, with a small prototype for each in Blender (scratch folder; measured ms per frame and how it looks):
   - **Rope over sheaves:** tangent lines + arcs between picked sheaves/drums (radii read from CAD round faces), a mark
     or texture running along at the rope speed, sheaves turning to match.
   - **Tensioner tracks / chains of pads:** rigid pads spaced along a closed path round the track's wheels.
   - **Drum spooling:** layer by layer, opposite hand per layer, the fleet angle to the first sheave.
   - **Catenary into the sea:** keeps its length, touch-down point moves with the vessel.
   - **One cable speed drives it all** (an animation step "Cable speed" or a joint), and how it ties to 0058's curves.
3. For each: what the owner must click (as few as possible), what the app reads from the CAD, scripts-off behaviour,
   the per-frame cost on a 3,000-part model, risks, and what to leave out.
4. **Questions for the owner** (short, with a suggested default each) – which machines he wants first, what must look
   exact and what may be approximate.
5. Write it up in this file below: design per part, prototypes' numbers, a proposed split into tasks (lanes, model,
   order, which can run on a Fable day), the questions. Push to `task/0075-motion-paths-design`.

## Not in this task

Building it. Changing 0058's plan (note conflicts as questions for the lead instead).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Design:**

**Prototypes and numbers:**

**Proposed tasks:**

**Questions for the owner:**
