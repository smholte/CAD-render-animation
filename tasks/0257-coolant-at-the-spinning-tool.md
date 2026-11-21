# 0257 – Coolant at the spinning tool: wraps round it, is flung off at the tool's speed, deflected at high rpm

**Who:** worker · **Status:** done (0.2.200) · **Branch:** `task/0257-coolant-at-the-tool`
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

- [x] Splash speed follows ω·r and the tool's radius; flat band; drop size by speed; film below ~1 m/s; deflection and
      atomising above ~5 m/s; M3 / M4 directions (tests with numbers for each)
- [x] Same frame = same drops (test); ms per frame before / after in the report
- [x] Tour stop(s) in the `coolant` set `changed=` (`tour_versions.py --record`), PC-check `milling.coolant` checks the
      speed rule, guide text + picture, function entry `changed=`, CHANGELOG
- [x] The page with the clips; full suite + GitHub green; report (with the footage compared, as links)

## Not in this task

Liquid pools turning round the tool in a pocket (that is 0255's spinning-tool input + B), through-spindle coolant,
chips in the liquid, the air blast.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 21 Nov 2026 · version 0.2.200

**What changed:**
- `core/coolant.py`: the splash follows the tool. `rim_speed` (|rpm|·2π/60·r), `regime` (film < 1 m/s, streams < 2,
  spray < 15, mist above), `drop_diameter` (spinning-disc rule d = 3.8·√(σr/ρ)/v, σ = 0.04 N/m, between 0.08 and
  2.4 mm: a D10 gives 2.4 mm at 1,000 rpm, 0.54 mm at 6,000, 0.22 mm at 15,000), `drag_time` (Stokes ×
  Schiller-Naumann at the start speed; drops fly in closed form `_fly`), `film_share` (1 below 0.5 m/s, ½ at 1 m/s,
  0 above 1.5 m/s), `deflect_share` = (v − 5) / (v − 5 + 2·jet speed), at most 85 % (D10, full flow: 0 at 9,000 rpm,
  26 % at 15,000, 67 % at 40,000; less flow = more deflected).
  `splash` (new `rpm`, `band`, `deflect`): drops leave at 0.85–1.15 × the rim speed, **cap 25 m/s** (a D50 at
  10,000 rpm is 26 m/s; faster leaves the picture within a frame), tangential + 15–35 % outward, ±6 % up/down, in a band
  of the jets' width at the jets' height; fewer reach the tool by the deflected share. Slow tool: `_film` = beads on
  the tool turning with it and running down the 30° flutes to the tip; shed drops leave from 3 flute points that turn
  with the tool (streams). Fast tool: `jet(deflect=…)` bends the jet's last 3–9 mm in the turning direction (up to
  share × (2 mm + 0.6 r)) and thins it; `_atomised` = mist drops swirling round the tool at half the rim speed.
  Tuned by eye: a drop's life is divided by (1 + v/2) so as many show near the tool at any speed, and no drop is drawn
  smaller than 0.09 mm radius (finer ones vanished below a pixel in a close-up). Projects built before 0.2.200 have
  no stored speed: they look as at 3 m/s until Build & play.
- `blender/coolant.py`: the build stores the spindle's keys (`fr_rpm`: frame, signed rpm; 0 after the step);
  `rpm_at` reads them per frame and `refresh` passes them on.
- Tour set `coolant` (`changed=0.2.200`): the program runs at S15000; the stop's check reads 15,000 rpm and a deflected
  share > 10 %. PC check `milling.coolant`: reads 9,000 rpm (4.7 m/s for the D10), a film at 1,000 rpm, finer drops at
  15,000, jets turned away at 15,000 and not at 9,000. Function entry `cnc.coolant` `changed=0.2.200`. Guide: a
  paragraph on speed and the three looks, the picture made again (`tools/guide_mill_pictures.py`, the tour stop at
  15,000 rpm).
- Page `tasks/0257_page/index.html` (for the lead to publish): before / after clips at 1,000 / 6,000 / 15,000 rpm, 36
  frames each at half speed, Cycles 24 samples on the processor, a side cut along the block so the spray flies towards
  the camera; `numbers.json`.

**Tested and measured** (4-core web machine, no graphics card; test mill, D10, flood 0.7 from two automatic hoses):
- New tests: 10 in `tests/test_coolant_core.py` (rim speed, drop size by speed, drag, splash speed 0.8–1.2 × ω·r for
  D10 at 6,000 / 15,000 and D50 at 3,000, the 25 m/s cap, the flat band, M3 / M4 direction ≥ 90 % of the drops, film +
  streams, the deflection share and the bent jet, less splash when deflected, same frame = same drops at any speed,
  draft), 1 in `tests/test_coolant.py` (the build stores the speed; 1,000 rpm: a film on the tool; 15,000 rpm M3 / M4:
  the jets bend the other way). All coolant tests, the tour's coolant stop and the PC-check line pass locally.
- **ms per frame** (`coolant.refresh`, 60 frames of the flood): before 3.02 / 2.77 / 2.88 ms at 1,000 / 6,000 / 15,000
  rpm; after 3.38 / 3.20 / 3.60 ms (+0.4–0.7 ms; at 15,000 rpm 917 drops instead of 419 – the mist round the tool).
  PC check line: 2 ms per frame with coolant.
- Draft draws the jets only, as before (test).
- GitHub: 1 full run on the branch, green (run 44941674481, 19 min); no clash, no red run. Then a docs run for this
  report and the fast-forward of `main`.

**Footage compared** (links only; no copies in the repository): Blaser Swisslube's macro high-speed recordings of a
carbide milling tool cutting with metalworking fluid –
https://www.americanmachinist.com/cutting-tools/media-gallery/21252254/researchers-examine-the-details-of-every-chip-blaser-swisslube
and https://mmsonline.com/news/high-speed-videos-analyze-machining-processes-in-fine-detail ; the CFD study of coolant
coverage in end milling (Politecnico di Torino thesis) – https://webthesis.biblio.polito.it/37066/1/tesi.pdf . A search
found no openly published slow-motion footage of flood coolant thrown off an end mill at several speeds; the numbers
come from the physics (rim speed, spinning-disc drop size, drag) and the brief's sources on the air layer.

**Open points / follow-up tasks:**
- The splash uses the speed at the frame shown for every drop in the air (they live < 0.3 s), so a speed change shows
  at once.
- Drops pass through the block's walls (no collision; only the floor height and a 0.35 m reach end them) – inside a
  pocket much of a fast spray is hidden by the walls, as before. Liquid on the part is task B (`blender/liquid.py`).
- The owner judges the look on the page; the thresholds (film 1 m/s, air 5 m/s, cap 25 m/s, smallest drawn drop
  0.09 mm) are constants at the top of `core/coolant.py`.
