# 0261 – Real size, category A: the cylinder arm and the hose arm ×3, the mesh crane ×2.5

**Who:** worker · **Status:** open – waits for 0259 (its real pins / bolts / cylinder are the pattern) · **Branch:**
`task/0261-arms-mesh-crane-real-size`
**Started by:** lead, 21 Nov 2026 (owner 14:20: every model at a realistic scale – "study first, then one fix task per
type"; study **0258** category A) · **Model:** Opus · effort Medium
**Area:** Test models lane – `tools/make_test_cylinder.py`, `tools/make_test_flex.py` (the **hoses** model only),
`tools/make_test_mesh.py` (the mesh crane), their `tests/data/` files + `fresing_render/data/` copies, the maker tests;
every place that holds these models' numbers: `blender/tour.py` – the sets `cylinder`, `hoses`, `mesh` and the hose
part of `flex_drawn` (**numbers, cameras and framing only**, not the surroundings 0233 gave them), `pccheck/checks.py`
(their lines), the tests and tools that read them (`grep -rln "test_cylinder\|test_flex_hoses\|test_mesh_crane" tests
tools fresing_render`), `tools/ui_test_*.py` scripts that click on them, `tools/guide_screens.py` + the guide pictures
and texts that show them, `tools/tour_versions.py`'s record.
**Not:** app code (a fault found → report it), the drag chains and cable of `flex_drawn` (0262, 0263), the test crane
(0259), surroundings.

## Why

Study 0258 (`tasks/0258-study-real-sizes.md`, table + `tasks/img/0258/1_cranes_arms.jpg`): next to a 1.75 m person the
arms and the mesh crane are toys – the mesh crane's cab is smaller than a person.

## The sizes (0258's proposal – lead's decision, the owner can change it later)

- **`test_cylinder_a`** (+ `_b`): layout ×3 – arm ~4.8 m, arm pin ~1.9 m; cylinders a real bore / rod for the load
  (0258: bore 100–125, rod 56–70, ISO 6020/6022 series), stroke ×3.
- **`test_flex_hoses_a`** (+ `_b`): the same arm ×3; **hoses, fittings and the gland keep their real Ø** (Ø16–20,
  fittings 25–35 mm) and only get longer; the cable to the slide likewise.
- **`test_mesh_crane.glb`**: ×2.5 (boom ~7.5 m – the same class as 0259's crane; cab ≥ 1.5 m high).
- **The rule (0258):** scale the **layout** (places, lengths, travels), never the parts that have a real size – bolts,
  pins, hoses, fittings, sheet thickness. Real-size bolts and pins with names that follow the size, in the same
  supplier notation as 0259 (`ISO 4017 M… x … - 8.8 HDG`, `ISO 4762 M… x … - 12.9`).
- **Keep the structure:** same part and assembly names, tree, colours, joints, revisions (B keeps its differences);
  `--inventor-names` / `--plain` variants follow their `_a` model. Old saved-project fixtures stay as they are.

## Watch

- **Real-app scripts are the slow part** (0258: hoses 5, crane-like clicks): every hard-coded click, hover spot or size
  in `tools/ui_test_*.py` must still land on the same faces.
- **Numbers in tests:** most become "old × 3" (or × 2.5); every number that changed for another reason gets one line in
  the report. Hose lengths, MBR warnings and clip spacing are real-size rules – check they still hold.
- **Import weight:** measure triangles and import time at Draft / Normal before / after (0258 expects +1–6 %); the
  tests' total time within about +15 %.
- Every tour animation 0 clashes, every stop's check, cameras framed again on the new size; `changed=` on every touched
  set + `python3 tools/tour_versions.py --record` after merging `main` once.
- `flex_drawn` holds the hoses, chains and cable at once: this task changes only its hose part; 0262 and 0263 follow
  in the same lane.
- Search the repository afterwards for the old sizes in texts (guide, stop texts, tooltips).

## Done when

- [ ] The three makers make the new sizes (all variants); both copies of each file updated; maker tests green
- [ ] Every test, tour stop, real-app script and PC-check line green; changed numbers listed with the reason
- [ ] Sets `cylinder`, `hoses`, `mesh`, `flex_drawn` framed again, 0 clashes, `changed=` + the record
- [ ] Guide pictures of these models made again; texts with the new sizes
- [ ] Triangles / import times before–after in the report; tests' total time within about +15 %
- [ ] A line-up picture (new models beside a 1.75 m person and the IBC, test models only) in `tasks/img/0261/`
- [ ] Report filled in, merged, released

## Not in this task

Drag chains, cable, routers, way covers, winches, spools (0262, 0263); mechanisms (0264); the test crane (0259);
surroundings; app code. **Never the cable-lay vessel's equipment, never the Fresing 400.**

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
