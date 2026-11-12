# 0091 – Demo: the quadrant system moves freely, quadrant shot, Lebus close-up

**Who:** worker · **Status:** running · **Branch:** `claude/inspiring-keller-9fp79j` (the web session's branch)
**Started by:** lead chat, 12 Nov 2026 (0077's open points)
**Lane:** Demo models – `fresing_render/demo_model/` (the maker), `blender/demo.py`, `blender/ops_demo.py`,
`tests/test_demo_*.py`, `tools/make_demo_cable_lay.py`; no other app code (anything wrong elsewhere: an open point)
**Model:** Opus · effort Medium (3D geometry of an invented model) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The demo's quadrant system can do its whole move without parts running through each other, and the demo video shows it:
the D-quadrant travels aft on its rails to the handler, the handler tilts over the stern and the quadrant tips. The
drum close-up shows a real Lebus drum, and the X-ray labels no longer overlap.

## Background – what 0077 found (clash check on the full-size demo, report of `tasks/0077-demo-project.md`)

- The D's travel aft runs into the S-bend's **roller cradles** at once (125 mm, frames 3–30 of the travel); its
  **gutter** 50 mm and a **pad eye** 30 mm too.
- The **handler frame cuts its hinge brackets** past about 30° of tilt (139 mm).
- The **parked handling wire** stays behind when the handler tilts (233 mm) and the D passes through it (125 mm).
- The handler cylinders' **rod leaves its barrel** near 70° (2 rows) – the stroke or the pin points are wrong.
- The **rail wheels** show short 2–50 mm rows while turning fast: check the wheel's joint axis against its round centre.
- The demo's stern turn stays where it is (owner, 12 Nov): the cable passes 10 cm under the rail girders.
- The quadrant's tip joint rides on its travel; on the handler it must also ride the handler's tilt (0084's note).

## What to build

- Fix the model, not the check: raise or split the cradles where the D passes (or move the S-bend's cradles to stands
  that leave the middle lane free), give the hinge brackets room for 0–100°, let the parked handling wire hang from the
  handler (a part that moves with it), make the cylinders' stroke and pins fit 0–100°, put each wheel's joint on its
  own round centre. Keep every route rule of 0084 (bends ≥ 1.15 × MBR, rollers ≤ 1.6 m apart).
- The quadrant's tip: a joint that rides on the handler's tilt once the D is on the handler (a second stacked joint is
  fine; say which way you chose).
- **Shot 7** of the demo: the D travels aft (time-lapse caption), the handler tilts over the stern, the quadrant tips –
  0 clash rows over the shot.
- **Lebus close-up (shot 6):** one deck winch gets the Lebus drum (35° crossovers + risers, 0084) so the close-up shows it.
- **X-ray labels (shot 5):** no two label boxes overlap and none touches the picture's edge (move the label points or
  the camera in `demo.py`).

## Done when

- [ ] Clash check on the full-size demo over the quadrant shot: 0 rows (with the spinning parts left out as in 0077);
      a test on the scaled form checks the quadrant's whole move.
- [ ] Shot 7 and the Lebus close-up in the animation; the animation still 60–80 s; `tests/test_demo_project.py` and
      `tests/test_demo_cable_lay.py` green; two new pictures `tasks/img/0091-*.png` (quadrant tipped, Lebus close-up).
- [ ] Make demo project time measured again (should stay about 148 s on the web machine).
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The clash check's speed with spinning parts (0092), joint-creation speed (0093), the moving cable (0078) and the quadrant
operations with wires and cable (0082).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
