# 0257 – Coolant at the spinning tool: wraps round it, is flung off at the tool's speed, deflected at high rpm

**Who:** worker · **Status:** open – waits for 0249 (it owns the `coolant` tour set and the test mills) · **Branch:** `task/0257-coolant-at-the-tool`
**Started by:** lead, 21 Nov 2026 (owner 14:01: "the fluid should interact with the milling bit, so when the mill is
spinning fast the coolant should also turn around the mill and get splashed away – look up what it looks like")
· **Model:** Opus · effort Medium
**Area:** Machining lane – `fresing_render/core/coolant.py` (jets, splash, mist; no Blender) and
`fresing_render/blender/coolant.py` (what it reads per frame: the spindle speed, the tool's radius and flute length);
the tour set `coolant` and its stop(s) (`changed=`), the PC-check line `milling.coolant`, the guide's Coolant section
(+ picture), tests (`tests/test_coolant*.py`), CHANGELOG.

**Not:** the liquid on the machine (0255 = its core, B = on the machine – B comes after this task and uses these jets
as its pour), chips, the air blast, the test mills themselves (0249).

## Goal

The flood coolant at the tool looks like it does on a real machine and changes with the spindle speed and the tool's
size: a slow tool wears the liquid as a film that turns with it and sheds in streams; a fast tool throws it off as a
fine, fast, flat spray in the turning direction and partly blows the jet away before it reaches the tool.

## Background

- **Today (0042, `core/coolant.py` `splash`):** drops leave the tool at 0.25–1.15 m/s whatever the spindle speed (only
  the direction, `spin` ±1, follows M3 / M4); 75 % tangential, 55 % outward, up to 60 % up; nothing lies on the tool;
  the jet reaches the tool the same at any speed.
- **What it looks like on a real machine** (lead's search, 21 Nov):
  - A fast-turning tool makes its own small vortex: an **air layer turning with it** that coolant aimed at the tip
    runs into and is **atomised** – much less reaches the cutting edge (Cutting Tool Engineering). Patents describe the
    same: the air layer round an end mill turning fast **deflects a large part of the jetted coolant**; on grinding
    wheels the effect is strongest and coolant only gets through when the jet is as fast as the wheel's rim.
  - Shops speak of a "tornado-like air pocket" round the tool at 10,000 rpm and more; above some surface speed flood
    coolant is often switched off for mist.
  - Physics for the look: liquid that touches the tool leaves it tangentially at about the tool's surface speed
    v = ω·r (D10 at 10,000 rpm ≈ 5.2 m/s; D50 at 3,000 rpm ≈ 7.9 m/s; D10 at 1,000 rpm ≈ 0.5 m/s), in a thin flat sheet
    / ring that breaks into drops – finer drops the faster it turns.
- The worker looks at real slow-motion footage itself (Claude Code on the web has web search) and says in the report
  what it compared with (links only – never copies of others' videos or pictures in the repository).

## What to build

1. **Spindle speed and tool size drive the splash:** the drops leave at ≈ ω·r (with a spread, capped where the
   picture stops reading – say the cap), tangential first with an outward share, in a **flat band at the height where
   the jets meet the tool** (not a cloud up the whole tool); drop size falls with speed (big drops / streams below
   ~1–2 m/s, a fine spray above ~5 m/s, mist-like above ~15 m/s – tune by eye and say the numbers). How far they fly
   follows from their speed (gravity and a little air drag).
2. **Slow tool – the film:** below about 1 m/s rim speed the liquid **wraps round the tool** as a thin film that turns
   with it (a few rings of drops / a ribbon going round, running down the flutes to the tip) and sheds in a few streams
   from the flute edges.
3. **Fast tool – the air layer:** above about 5 m/s rim speed part of each jet is **deflected and atomised** a few mm
   before the tool (the jet's end bends with the turn and breaks into fine drops); the share grows with speed and falls
   with the jet's own speed (flow). Say the rule.
4. Same frame = same picture (as 0042: from the frame number alone); the cost per frame stays about as today (say
   the ms before and after on the test mill); Draft draws as today's draft.
5. Pictures: a page in `tasks/0257_page/` with short clips of the test mill's tool at three speeds (e.g. 1,000 /
   6,000 / 15,000 rpm) before and after, for the owner to judge (the lead publishes it).

## Done when

- [ ] Splash speed follows ω·r and the tool's radius; flat band; drop size by speed; film below ~1 m/s; deflection and
      atomising above ~5 m/s; M3 / M4 directions (tests with numbers for each)
- [ ] Same frame = same drops (test); ms per frame before / after in the report
- [ ] Tour stop(s) in the `coolant` set `changed=` (`tour_versions.py --record`), PC-check `milling.coolant` checks the
      speed rule, guide text + picture, function entry `changed=`, CHANGELOG
- [ ] The page with the clips; full suite + GitHub green; report (with the footage compared, as links)

## Not in this task

Liquid pools turning round the tool in a pocket (that is 0255's spinning-tool input + B), through-spindle coolant,
chips in the liquid, the air blast.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
