# 0128 – Turbine extras (scour protection, the pile in the ground, worn leading edges) + the site's ATC model re-made

**Who:** worker · **Status:** running · **Branch:** `task/0128-turbine-extras`
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Sonnet · effort Medium (stuck: Opus)
**Area (Site kit lane + Web 3D lane's site files + Looks lane additively):** `tools/site_projects/iea15*.py`,
`tools/site_projects/turbine_parts.py`, `site/render_kit/models.ini` + `site/render_kit/projects/iea15_*.json`,
`tests/test_site_turbine*.py`; additively `fresing_render/core/materials_lib.py` / `blender/materials.py` /
`blender/marine_looks.py` if a look is missing; `site/media/` + `site/media/media.json` for the ATC web model
(`tools/make_site_web_models.py test_atc`). **Do not edit:** the sea, seabed and cut-away code (`core/sea.py`,
`blender/surroundings.py`'s sea, `paths*`, `catenary.py`, `section.py`) – task 0125 runs at the same time;
`demo*`; `sequence.py`.

## Goal

The offshore turbine on the site looks like a real one at sea: rock scour protection round the monopile on the seabed,
and a shot that shows the pile going ~45 m into the ground; the blades show a worn leading edge. The site's "Turn it
yourself" ATC machine is the new, more detailed one from 0122. **Owner runs the render kit on Sunday evening (15 Nov):
the sooner this is on `main`, the more of it is in his run** (the site-kit workflow repacks the kit on every push to
`main` that changes `tools/site_projects/` or `site/render_kit/`).

## Background

- 0116's report (`tasks/0116-wind-turbine-site-model.md`): monopile model, the turbine frame, invented parts in
  `turbine_parts.py`, 0 clash rows, the check animation's clash check 8–10 min (only `make_site_projects.py --project`).
  0081's seabed (water depth, clarity, cut-away) reached `main` after 0116 started, so the offshore turbine does not use
  it yet. The source STEP stays on the draft release `site-kit` (Apache-2.0, credit in `site/CREDITS.md`).
- **Scour protection:** a ring of rock armour round the pile on the seabed (typ. a filter layer + armour stones,
  radius a few pile diameters, ~1–2 m thick, sloped edge). Invented geometry in `turbine_parts.py` – mind the triangle
  count (instanced stones or a displaced ring with a rock look, not thousands of unique meshes).
- **Pile in the ground:** use the app's own seabed and the 0081 cut-away (or the section view of 0086) to show the
  pile below the seabed in one offshore shot; if the app cannot do that for a turbine without changing 0125's files,
  say so in the report and use the plain seabed (no app change in this task).
- **Worn leading edge:** leading-edge erosion – a strip along each blade's leading edge, strongest towards the tip
  (outer third), duller and rougher paint with small chips showing the grey laminate; the leading edge is known in
  `iea15.py` (0116 mirrored the blades by it).
- **ATC web model** (0122's open point): `site/media/test_atc.page.html` still shows the old ATC machine. Re-make with
  `tools/make_site_web_models.py test_atc`; download size before/after in the report (0111: 0.8 MB model, 2.2 MB
  download) – if it more than doubles, use the export's Phone quality or fewer keys.

## Done when

- [ ] Offshore turbine: scour protection on the seabed round the pile, the water depth and seabed from the app's sea;
      0 clash rows; triangle count before/after in the report.
- [ ] One offshore shot (camera in the sheet) shows the pile below the seabed – or the report says why not.
- [ ] Worn leading edges on all three blades (both turbines), visible in the kit's close-up camera; a look test as
      the other looks have (`marine_looks.growth`-style plain-Python check).
- [ ] If a new look was added to the app: it is in the look list, guide + anchor, function-list entry, tour stop,
      PC-check line (CLAUDE.md section 6), as 0116 did for marine growth.
- [ ] `site/media/test_atc.page.html` re-made from the 0122 model; page opens offline; size in the report.
- [ ] Kit still packs (`tools/make_site_projects.py --kit`), the shipped sheets match; tests; GitHub run green;
      merged before Sunday evening if at all possible; the site-kit workflow run on `main` green (kit on `site-kit`).
- [ ] Report with the owner's one-line note for his kit run (what is new in the turbine pictures).

## Not in this task

The cable-lay demo next to the monopile / a J-tube (later). The other site models. The page's weather (0115).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 15 Nov 2026. **State: pushed on branch `task/0128-turbine-extras` (0.2.102), NOT merged:** the run is red in one job that fails the same way on other branches (below).

**What changed:**
- Scour protection (offshore): part `SCOUR PROTECTION`, a rock bed of flat faces (72-sided, foot 34 m radius, 1.9 m thick at the pile) with 150 boulders, one solid, ~4.4 k triangles (a revolved version meshed 46 k, a lofted one 230 k). 0 new clash rows expected: it is in the fixed TOWER body (not run here: the full turbine needs the owner's STEP).
- "Seabed" camera + sheet `scene.sea_depth_m` / `scene.cutaway` (90 m box round the pile); `site/render_kit/projects.py` `apply_scene` sets the app's seabed depth and the cut-away box. The pile **below** the seabed stays hidden: the seabed is an opaque surface, so it cannot be shown without changing the sea code (task 0125's files). The note in the sheet says so.
- New look `paint_blade_eroded` ("Marine paint, worn leading edge (blades)"), kind EROSION in `marine_looks.py`: strip along the edge facing -y of the part, from 70 m to the tip, patches of grey laminate with chips. Guide text added. Both turbines use it for `blade`. **Open:** I checked the blade's own axes on the stand-in turbine only (span along z, leading edge -y after mirroring); the real blade is not here. If the first kit pictures show the wear on the back edge, flip `edge_dir` in `marine_looks.DEFAULTS["EROSION"]`. No new tour stop / PC-check line (the existing `looks.marine` ones cover the family); it has its own render test.
- ATC web model re-made (`test_atc.page.html`): page 2.15 MB -> 2.49 MB (+16 %), model 1.1 MB, 44,167 triangles, 10.1 s loop.
- The shipped `iea15_offshore.json` was edited by hand (parts 89 -> 90, new part, camera, scene, hide note), because the owner's STEP is not here; the test that compares it with a fresh conversion needs the STEP and was skipped. Please run it on the owner's machine/kit run.

**Tested and measured** (4-core web machine): new `tests/test_blade_erosion.py` (4), `test_site_turbine_parts.py` (21), `test_site_turbine*.py`, stand-in conversion tests, marine/materials/guide/function tests all pass locally. GitHub run 43670263324: every job green except `Linux - real app ui` (`ui_test_spool.py`: "level wind follows the layer", 35/43), also after a re-run. The spool test passes alone here (43/43, 48 s), and the same failure is in run 43621844399 on branch `ccr-bde4018f-wmqawe`, before my commits: not caused by this task (task 0127 is about tests that fail at random). I did not touch or loosen it.

**Open points / follow-up tasks:** merge this branch once the spool test is green on `main` (or 0127 fixes it): merge `main` into the branch, push, wait for green, `git push origin HEAD:main`. Runs used: 2 (one real failure that is not mine, one re-run). Owner's note for the kit run: "The offshore turbine now has rock round the pile and a Seabed picture under the water; the blades are worn along their front edge towards the tip (tell me if it is on the wrong edge)."
