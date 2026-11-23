# 0303 – Study + look sheet (findings only): people in two more looks – low poly and realistic – on the same rig

**Who:** worker · **Status:** running 23 Nov · **Branch:** `task/0303-study-people-looks` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Better humans (visual) option for low poly, and
realistic.") · **Model:** Opus · effort High
**Area:** findings only; prototype in new files on the branch; reads `core/props_detail.py`, `blender/props_scale.py`,
`core/person_rig.py`, `blender/person_rig.py`, `blender/people.py`, `core/tc_person.py`. Pictures, clips and the page in
`tasks/0303_page/`. Not a code slot.

## Background

0155: a posable person (6 poses, 3 heights, 3 outfits, light versions by camera distance, a face without a likeness);
0157: its rig – walk paths with 5 gaits, 12 actions, carried items; 0156: a person changing a tool.

## What to find out

A. **Low poly:** a clean, stylised mannequin – very light, for big scenes and the web 3D page – on the same rig.
B. **Realistic:** the sources and their licences **checked at the source** (Blender Studio's human base meshes,
   MakeHuman / MPFB assets and add-on, others; which may ship in a GPL app and a public repository, which may not), or
   an own upgrade of 0155 (skin, cloth, hair, a face without a likeness); work clothes and PPE (hard hat, hi-vis vest,
   coverall, safety boots, offshore suit); body and skin variety; size per person (MB) and render cost; how it fits
   0157's rig (walk paths, actions, hands for the tool change) – same skeleton or a retarget.
C. **Look sheet:** today's person, low poly and realistic side by side at three camera distances, and a short walk clip
   of each; the page with pick ticks + a Copy line; ranked build tasks with sizes.

## Done when

- [ ] Report + page on the branch; licences listed with their source pages → the lead publishes the page for the
      owner's picks → build task

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
