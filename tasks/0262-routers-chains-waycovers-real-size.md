# 0262 – Real size, category B: the gantry routers ×2.5 on a stand, the drag-chain router ×2.5, the way covers ×2

**Who:** worker · **Status:** open – waits for 0261 (same lane; `flex_drawn` is shared) · **Branch:**
`task/0262-routers-chains-waycovers-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale, one fix task per type; study **0258**
category B) · **Model:** Opus · effort Medium
**Area:** Test models lane – `tools/make_test_gantry.py`, `tools/make_test_flex.py` (the **drag-chain** model only),
`tools/make_test_waycover.py` (`_b`, `_c`, `_d`; **not** `_a`, the owner's real sub-assembly), their `tests/data/` files +
`fresing_render/data/` copies, maker tests; every place that holds their numbers: `blender/tour.py` – the sets `gantry`,
`atc` (if it uses the gantry), `chains`, the chain part of `flex_drawn`, `waycover`, `waycover2` (**numbers, G-code
programs, work zero, cameras and framing only**, not surroundings), `pccheck/checks.py` (their lines), the tests and
tools that read them (`grep -rln "test_gantry\|test_flex_chains\|test_waycover_[bcd]" tests tools fresing_render`), the
real-app scripts (0258: gantry 7 scripts), `tools/guide_screens.py` + guide pictures and texts, the site's web model if
it is one of these, `tools/tour_versions.py`'s record.
**Not:** app code (a fault → report it), hoses (0261) and the cable (0263) of `flex_drawn`, the mills (0249 / 0250).

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, `tasks/img/0258/5_routers_covers.jpg`): the routers are desk / hobby
size on the floor (bed 0.8 × 0.6), the way covers 1.1 m long – beside 0249's VMC (X travel 1000) they read as toys.

## The sizes (0258's proposal – lead's decision)

- **`test_gantry`**: layout ×2.5 (bed ~2.0 × 1.5, a sheet-size router class) **on a stand** so the table top is at
  ~0.9 m (0.85–0.95 working height). Tools keep their real Ø (4–10 mm, only the holders as real); the tool carousel
  becomes a real router changer size (Ø0.4–0.6, keep its 3 tools unless more is cheap – say which).
- **`test_flex_chains_a`**: the same router ×2.5 on the stand; **drag-chain links keep their size** (pitch 40, bend R80,
  links 20 × 32) – the chains just get longer (~47 → ~110 links; measure the cost).
- **`test_waycover_b`, `_c`, `_d`**: ×2 (~2.2 × 0.6 extended), **matched to 0249's VMC X travel** (read it from
  `make_test_mill.py` after 0249); sheet 1.5–3 mm real.
- **The rule (0258):** scale the layout, never the parts with a real size (bolts, rails, guide blocks, motors, chain
  links, tools, sheet). Same part names, tree, colours, joints, revisions; variants follow their `_a` / `_b`.
- **G-code:** programs, work zero and the toolpath of these sets scaled with the bed – feeds and spindle speeds stay
  real (a bigger router does not cut faster). Program times in tests change: list them.
- **Never the Fresing 400's size class** (small mill, BT30, double-arm changer) – a sheet-size router is far from it.

## Watch

- Real-app scripts that click on the gantry (7) are the slow part: every click / hover must still land.
- Import triangles and times before / after (0258: +1 %; the longer chains add parts – measure); tests' total time
  within about +15 %.
- Every tour animation 0 clashes (the stand and the gantry beam's travel), every stop's check, framing again,
  `changed=` + `python3 tools/tour_versions.py --record` after merging `main` once.
- Search afterwards for the old sizes in guide, stop texts and tooltips.

## Done when

- [ ] The makers make the new sizes (all variants, both copies); maker tests green
- [ ] Every test, tour stop, real-app script and PC-check line green; changed numbers listed with the reason
- [ ] Sets framed again, 0 clashes, `changed=` + the record; guide pictures and texts updated
- [ ] Triangles / import times before–after; tests' total time within about +15 %
- [ ] A line-up picture (person 1.75 m + euro pallet, test models only) in `tasks/img/0262/`
- [ ] Report filled in, merged, released

## Not in this task

Hoses / arms (0261), winches / spools / the cable (0263), mechanisms (0264), the mills (0249 / 0250), surroundings, app
code. **Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
