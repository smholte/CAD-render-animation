# 0083 – Reference study: how a cable-lay spread really looks and moves

**Who:** worker · **Status:** open – can start (Wed 11 Nov evening), next to 0076 · **Branch:**
`task/0083-cable-lay-reference`
**Started by:** lead chat, 11 Nov 2026
**Area:** findings only – this task file and, at most, small notes in `tasks/0076-demo-cable-lay-model.md` (a "Notes
from 0083" section). No code, no version, no release (a `tasks/`-only push starts no test run).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation" (web search and
web pages through the session's own search/fetch tools; the shell cannot reach most websites)

## Goal

The demo model (0076), the demo project (0077) and the motion-paths tasks (0078–0082) must look and move like the real
thing to an engineer who designs these machines (the owner). This study collects, from public sources, **what the
equipment looks like, its typical sizes, and how and how fast each part moves**, so the briefs and the reviews have
facts instead of guesses. It also proposes a **shot list** for the demo video.

## Background

Owner's answers (end of `tasks/0075-motion-paths-design.md`): carousel usually (also standalone storage carousels),
chute or quadrant at the stern, cable Ø 50–500 mm, lay speed ~10 m/min, two track tensioners with pad chains that
squeeze, quadrant + quadrant handling winch + tipping winches, handling winches helping the tensioners, spiral-groove and
Lebus drums, CPS, power cable black with yellow angled stripes, steel wire rope on winches. Read 0076's brief: it is
being built at the same time from general knowledge.

The owner may paste **screenshots** of reference videos (his own collection) into the session: use them as private
reference only – **never commit them or describe a client's design in the public repository**; write generic findings.

## Questions to answer (numbers with a source; say plainly what is an estimate)

1. **Track tensioners:** 2-track vs 4-track; track length, pad size and shape (V or flat, rubber), chain pitch, pads per
   track; how the top track squeezes (cylinders, stroke, opening for Ø range); line pull and speed ranges; what visibly
   moves (tracks, sprockets, cylinders) and in which direction; how two tensioners in a row share the load.
2. **Carousels:** outer/inner diameters and rim heights for 1,000–10,000 t; turning speed at 10 m/min lay speed
   (rpm vs coil radius); how the cable lies in the carousel (flat spiral layers, from outside in or inside out, the
   crossover to the next layer); the **loading arm / radius controller** (how it follows the layer, its motion range).
   Standalone storage carousels on a quay or barge: what differs.
3. **Cable route on deck:** roller conveyors, cable gutters, guide wheels / radius controllers at bends, straighteners,
   cable engines; typical spacing of rollers; heights above deck.
4. **Stern:** overboarding chute (radius, rollers, width) vs overboarding sheave; the **quadrant** – shape, radius,
   how the cable end is fixed (hang-off, pulling head), the **first-end and second-end** procedures step by step, what the
   quadrant handling winch and the **tipping winches** do and in which order, typical durations.
5. **Handling winches helping the tensioners:** how a winch wire is joined to the cable (pulling grip, stopper,
   Chinese finger) and when; A&R winch.
6. **Winch drums:** spiral groove vs **Lebus** grooving (parallel sections + crossover zones per turn, risers/fillers at
   the flanges, layer change); what to show in close-ups; fleet angle limits.
7. **Cable into the sea:** lay catenary, touch-down point distance for typical depths, tension; lay speed in practice;
   what an underwater shot usually shows; **CPS** types (bend restrictor, polymer sleeves, centraliser, latch for
   monopile/J-tube) and how they look on the cable.
8. **Looks:** export / inter-array power cables (outer serving, colour, **yellow stripe** pitch and angle, length marks),
   steel wire rope (strands, lay, compacted vs regular, sheen), typical deck/machine paint (RAL), wear, wet decks.
9. **Vessel motion** that looks right in a video (roll/pitch amplitudes and periods in a calm working sea state).
10. **Shot list:** 8–12 camera shots for a 1–2 minute demo video of the spread (like a manufacturer's promo): what each
    shows, camera place and move, duration, which app feature it needs (existing or task 0077–0082).

## Done when

- [ ] Each question answered briefly with numbers and **source links** (manufacturer pages, papers, class/industry
      guidance); estimates marked as such; no long quotes, no pictures from the web committed.
- [ ] A short list **"check against 0076"**: where 0076's brief assumes something different (sizes, shapes, missing
      parts), each with the suggested change – the lead decides.
- [ ] Per motion-paths task 0077–0082: the facts its brief needs (one short block each).
- [ ] The shot list.
- [ ] Report pushed to `main` (tasks/ only, no test run); `TASKS.md`: 0083 done.

## Not in this task

Code, models, pictures from the web, anything of the owner's employer or its clients.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Check against 0076:**

**Facts per task 0077–0082:**

**Shot list:**

**Open points:**
