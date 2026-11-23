# 0303 – Study + look sheet (findings only): people in two more looks – low poly and realistic – on the same rig

**Who:** worker · **Status:** done 23 Nov – findings only, page waits for the owner's picks · **Branch:** `task/0303-study-people-looks` (branch only, never merged;
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

- [x] Report + page on the branch; licences listed with their source pages → the lead publishes the page for the
      owner's picks → build task

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0303-study-people-looks` (never merged; every push `[skip ci]`).

**What changed:** nothing in the app. On the branch: `tasks/0303_page/` (pick page `index.html`, pictures + walk clip in `img/`,
`numbers.json`) and `tasks/0303_proto/` – `lowpoly.py` (the mannequin, NumPy only), `realistic.py` (fit, rest pose, dressing, hard hat),
`weights_bpy.py` (Blender's automatic weights on the fitted 17 bones), `export_hbm.py` (the bundle's bodies to .npz), `render_sheet.py`
(look sheet, walk clip, variety row, crowd test). The Human Base Meshes bundle is not committed.

**Findings:**
- **Both looks run on the rig of 0157 unchanged** (same 17 bones, `core/person_rig.Figure`, `core/people.plan`): the walk clip drives today's,
  the low-poly and the realistic person from one plan.
- **Low poly:** 1,016 triangles (today 6,780 / light 2,248), saved 0.09 MB, rigid per bone (ball joints), mitten hands, outfit colours,
  plain-mannequin option. 40 people: +1.7 s, +16 MB over an empty scene.
- **Realistic:** Blender Studio's Human Base Meshes v1.4.1 from download.blender.org – **CC0 in every asset's licence field in the file**
  (scan-based male / female bodies, 10,582 points, multires, UVs, no rig). Fitted once (17 landmark points per body picked from plots),
  Blender's bone-heat weights (1.2 s per body with Blender's start, 0 points without weight), turned into the rig's rest pose by per-bone
  turn + stretch. Clothes = the body pushed out 9–14 mm and smoothed, regions coloured (suit, bands, boots, vest), a hard hat made in code,
  the scan's face smoothed. 24,856 triangles (99,688 with Subdivision 1 at render), saved 0.64 MB.
- **Cost of many people** (40, 960 × 540, 64 samples, web machine): empty 10.5 s / 816 MB; low poly 12.2 s / 832 MB; today light 14.2 s /
  870 MB; today 14.2 s / 914 MB; realistic without smoothing 15.0 s / 1,078 MB; realistic with smoothing 20.3 s / **3,752 MB (~73 MB a
  person)**. One person close up: 11–15 s for every look (the pixels decide).
- **Licences** (page section 4): ship = Human Base Meshes, MPFB system assets, Mesh2Motion, Kenney (CC0), Rigify metarig (GPL-2+); no =
  Mixamo, MetaHuman, Reallusion, Human Generator, SMPL, Bandai Namco (NC); unclear = Quaternius. No CC0 hard hat or hi-vis vest found
  (Sketchfab ones are CC-BY): PPE made in code. Only download.blender.org and GitHub could be read from here; the other source pages were
  read through a search tool (marked on the page) – a build task checks them again.
- **Open for the realistic route:** the scan's hands stay open (no finger keys → task C), the coverall reads as a tight suit close up
  (task F), the face is still a real face after smoothing – a likeness question against the 0155 rule (task B makes it generic).

**Tested and measured:** web machine (4 cores, no graphics card), Blender 5.2.3 as a Python module and the real Blender for the bundle
(scripts off); Cycles CPU. Numbers in `tasks/0303_page/numbers.json`. No graphics-card measurement (the 3090 estimate on the page is
worked out, not measured). No app tests run (no app code changed). One subagent checked the licences (web search + GitHub); its unreadable
sources are flagged on the page.

**Open points / follow-up tasks:** the lead publishes `tasks/0303_page/index.html` for the owner's picks; build tasks A–H on the page
(★ A low-poly look + Look choice, ★ B realistic from Human Base Meshes, ★ C hands that grip, ★ D PPE set, ★ G light body for clash /
preview; E body variety, F cloth folds, H bring your own MPFB figure). The walk clip was rendered before the realistic chest bands were
moved off the chest's curve (they are ragged in the clip, straight in the stills).
