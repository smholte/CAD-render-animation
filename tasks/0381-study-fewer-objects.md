# 0381 – Study (findings + measurements): big models with fewer Blender objects

**Who:** worker · **Status:** open – can start · **Branch:** `task/0381-study-fewer-objects` (branch only, `[skip ci]`)
**Started by:** lead, 28 Nov 2026 (0326's open point; the owner's machines are big) · **Model:** Opus · effort High
**Area:** none on `main` – findings, measurements and throw-away prototypes on the branch.

## Goal

Know what the app would gain – and what it would break – by giving Blender far fewer objects on big models.

## Background

- 0326: a joint drag on the stress model (11,228 parts) now costs ~16–21 ms per step; **~15 ms is Blender's own
  per-update cost on ~11,500 objects** (also playback's ~14 ms per frame).
- 0327: clash memory is mostly every part's matrix at every moment. 0366: model build stages. 0324 / 0345: model
  update reuses meshes / keeps objects.
- The app assumes one object per part in many places (picking, hover, looks per part, paint per face, welds, joints,
  clash, web export, place / copy, the tree).

## Options to measure (on the stress model, web machine; note the owner's 24-core PC where it matters)

1. **Instances for repeated parts** (bolts, nuts, washers – `core/fasteners.py` knows them): collection instances or
   geometry-node instances – objects saved, what still works (pick, look, hide, clash, web export).
2. **One object per rigid body** for parts that never move relative to each other (joined mesh + a face → part map
   for picking, looks and paint) – the biggest cut; what every system would need.
3. **Hidden / far parts** left out of the depsgraph while dragging or playing.
4. Blender's own settings that scale with object count (relations, drivers, handlers per object).

For each: per-update ms (drag, playback), import, model update, save size, open time, render, web export, clash
memory, and the list of systems that break or need work. Prototype in a script, not in the app.

## Report

A ranked table (gain vs. risk vs. size of work), the recommended path, and build tasks by lane with model · effort –
for the owner to decide. Must say how it fits the import popup's speed options (0341: one object per sub-assembly).

## Done when

- [ ] Measurements for at least options 1 and 2; the ranked table and the build tasks
- [ ] Report on the branch, `[skip ci]`; TASKS.md row "done – findings"


---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
