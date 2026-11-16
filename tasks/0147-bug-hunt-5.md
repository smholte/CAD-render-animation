# 0147 – Bug hunt round 5: everything merged 15–16 Nov (findings only)

**Who:** worker · **Status:** done (findings only: no app code, starts no test run) · **Branch:**
`task/0147-bug-hunt-5` (report only)
**Started by:** lead chat, 16 Nov 2026 – 11 releases in one night, most of them merged unattended · **Model:** Opus ·
effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** reading and running everything; **no edits** except this file (and `tasks/img/0147_*`).

## Goal

Find what broke or is still wrong in the work merged since 0.2.104, before the owner relies on it – as bug hunts 0045,
0068, 0118 and 0131 did (same report format: one row per finding with place, proof, effect for the owner, suggested
fix, size).

## Scope (the reports in `tasks/` say what each changed)

0.2.105 0128 turbine extras + ATC web model · 0.2.106 0136 export crash fix + waterline · 0.2.107/108 0126 CPS run from
the rack, 0140 sequence fixes · 0.2.109 0130 House format 1.0.1 · 0.2.110 0137 cable data kept, sea re-bake, old
projects · 0.2.111 0139 mesh import fixes · 0.2.112 0134 web player · 0.2.113 0138 Build at any frame · 0144 render
kit start window (kit only).

Look especially for: work lost on save / reopen / model update / undo; old projects (made with 0.2.95–0.2.104)
opening and building the same; the fixes of 0136–0140 really holding (repeat each 0131 row's proof); two tasks merged
the same night touching neighbouring code (0137 + 0138 in paths/paths_sea, 0126 + 0137 + 0138 in the demo, 0134 +
0136 in web3d); the web player on a phone-sized window and with a software renderer (headless Chrome); the kit
window's PowerShell/Windows parts read carefully (no Windows here: say what you could not run).

## Done when

- [ ] Report with rows sorted by harm (crash / lost work / wrong result / slow / cosmetic), each with a proof script
      or steps; a short "In short (for the owner)".
- [ ] Pushed to `main` touching only `tasks/` (no run); then check that main really contains your commit.

## Not in this task

Fixing (the lead turns rows into tasks); 0142 and 0145 (running).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 16 Nov 2026. Hunted on `main` = bda374f (0.2.113).
**No app code, test or tool changed**; scratch scripts were outside the repository (the proofs below name them).
Three helper agents hunted one area each (A cables / sea / demo, B web 3D / player / looks, C sequence / mesh import /
House format + old projects); the main session read the kit window (0144) and ran its own proofs. Rows marked **(re-run)** were
run again in the main session with the helpers' scripts; rows marked **(helper)** were run by the helper only and
checked by reading the code here.

### In short (for the owner)

- **Nothing crashes today**, but the light bake of "Export web 3D model" (Soft light / Everything baked) still runs
  with the app's live handlers on: one missing check away from 0131's crash (row 1).
- **Work can be lost** after renaming a drum's, carousel's or track's joint (or a drum's cable) and then updating the
  model: the drum and level wind stop without a word (row 2); and after a **mesh** model update, work on a group the
  file did not name ("Node 5") can land on another group (row 3).
- **Old projects:** a project built at a late frame in 0.2.104–0.2.112 keeps a sea cable's wrong touch-down for good –
  Build at frame 1 no longer repairs it (row 5).
- **After Build**, changing the sea state while a late shot is shown re-bakes the demo's second end up to 8 m off
  (row 6); changing the water level leaves the cable 1 m under the seabed (row 8); the next Build silently puts the
  start scene's sea and speed back (row 12).
- **Assembly sequence:** nested steps in a non-nested order leave a subassembly apart (new in 0.2.107, row 7);
  Take apart "Hide" then Put together "Stay" plays the whole Put together invisible (row 9).
- **Web page:** marine growth / worn blade edge show as plain paint (row 10); an isometric camera shows the model at
  half size (row 14).
- **Render kit window:** sound on reading, with two traps: when the window cannot open, a crashed run is not
  continued but made again from the start (row 4); Pause can look undone and let the run hang paused (row 17). Not run
  on Windows here.
- **All of 0131's rows that 0136–0140 fixed still hold** (list below), and the whole test tour made with 0.2.95 and
  0.2.104 opens and builds the same in 0.2.113.

### Findings (worst first)

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | **crash risk** | `blender/lightbake.py:819–829` `_bake_call` | 0136 put only the looks bake (`web3d.Baker._run`) inside `handlers.pause_live()`. The **light bake** (export with Soft light / Everything baked, and the House bake) runs `bpy.ops.object.bake` on the `fr_bake` copy with every live handler on: 8 handlers (paths, flex, vessel motion, linkages, section, clash, machining, handlers) received the bake copy 5–14 times per export. Only `paths._follow`'s `fr_bake` check stops the 0131 row 1 segfault; any other handler that touches the copy the same way crashes Blender with unsaved work. | **(re-run)** B/`run_cases.sh moving_soft_notag` (moving cable, not built, Soft light, the copy's tag taken off) → `Segmentation fault`, rc 139, "Object 'FR seabed motion' already in collection"; the same with the tag: rc 0. Spy run `SPY=1 python exp_case.py hoses_soft x` → `logspy_*.txt` lists the handler calls with the bake copy. | Wrap the bake call in `_bake_call` in `handlers.pause_live()`; test: moving cable not built, light SOFT, with a handler that would fail on the copy. | web 3D | Sonnet | Low |
| 2 | **lost work** | `joints.rename` (joints.py:1596–1620) calls only `waycover.joint_renamed` and `paths.joint_renamed`: `FRSpool.joint`, `FRSpoolFollower.joint`, `FRTrack.joint`, `FRTrackWheel.joint` are not renamed; `FRCable.name` (props.py:2344) has no update callback, so `FRSpool.cable` keeps the old name | 0131 row 5's kind, not fixed for **drums, carousels and tracks**. Rename a drum's joint → Build warns "Drum or carousel 'Drum' could not be checked ('NoneType' object has no attribute 'frame')", any drum setting says "its cable or its turning joint is gone"; after a model update (same file) the drum is switched off: drum and level wind stand still (couplings ''), the rope object is removed, no Build warning ("its turning joint is gone in the new revision" – misleading). A renamed follower joint ("Arm slew") is lost at the update too. Track: rename the belt's speed joint + model update → a **new** joint "Track Belt" at 0, the pulleys stop. Rename the drum's **cable** → the same. | **(re-run)** A/`e3_spool_rename.py`, `e3b_spool_rename_update.py` (without rename: drum 30.77 rad, level wind −0.104; renamed: 0.0 / 0.0, spool objects 6 → 3); `e3c_track_rename.py` (pulleys −8.37 / −12.63 / −20.58 → 0.0, extra joint "Track Belt"); `e11_cable_rename.py`, `e11b_cable_rename_update.py`. Read here: `joints.rename` has no spool / tracks call. | `joints.rename` also calls new `spool.joint_renamed` / `tracks.joint_renamed`; an update callback on `FRCable.name` renames `FRSpool.cable` (and the vessel-motion TAG / STILL lists that name cables). Tests: rename, model update, Build, the drum still turns. | flex parts | Sonnet | Medium |
| 3 | **lost work** | `blender/reimport.py:76` (`"pos"` = the object's origin) with `:152` (a made name needs only "the same place"); `_made_assemblies` (178) never runs for these | 0139's fix for reader-made names does not hold for **assemblies**: unnamed glTF groups become "Node k" and usually all have their origin at the model's origin, so rule 2 pairs "Node 5" with the new "Node 5" ("same place", 0 mm). When an earlier group is removed or added, the numbers shift and everything keyed on a group lands on another group: Hide / Show / sequence step targets, the Structure eye. | **(re-run)** C/`mesh_edges.py <repo> <scratch> made_asm`: groups A/B/C unnamed, Hide step + hidden in Structure on B, update with A removed → "Hide step target: Node 5 ['C1', 'C2']", hidden: group C. v0.2.110 the same (not new in 0139, but its fix misses it). | Pair made-name assemblies only through their matched parts (`_made_assemblies`), or compare the centre of their parts' boxes, not the origin. Test: three unnamed groups at the origin, remove the first. | import | Opus | Medium |
| 4 | **lost work** (rare) | `site/render_kit/Make site pictures.bat` console route (no `--resume`) + `make_site_pictures._run` (`send/` emptied for a new run) | When the start window cannot open (PowerShell blocked, exit 1/2) the .bat asks in the console – and **can never continue a run**. After a crash it says "Double-click this file again to continue the run", but the next double-click starts a new run: the finished pictures in `send/` are deleted and rendered again (a night's work). | **(main session)** me/`k13_console_route.py` (fake renderer, as `tests/test_kit_window.py`): crash after 2 of 3 stills → `resume_info` 2 of 3; the console call again → all 3 stills rendered again. | Console route: when `resume_info` finds a run, ask "Continue the run of … (Y/n)" and pass `--resume`; or change the message. | site kit | Sonnet | Low |
| 5 | **wrong result, old projects** | `paths_sea.water_changed` (paths_sea.py:828–833, the "same water" skip, 0138); no versioning step | A project **last built at a late frame in 0.2.104–0.2.112** keeps its wrong touch-down for good: before 0.2.113 each Build set it again, so a Build at frame 1 repaired it; now the same water skips the re-set, so neither Build at frame 1 nor Clear keys + Build repairs it (the queue's Build neither). On the demo such shots stay up to 73 m off; the CHANGELOG's "a project saved at a late frame gives the right video" is not true for these files. | **(re-run)** A/`e10_old_late_build.py` (REPO = old tag) makes `out/late_v0.2.95/104/109.blend` (moving sea-cable model, start scene, built at frame 289); `e10b_open_late.py v0.2.109 v0.2.104` (main) builds at frame 1: touch-down **21.04 m** off, mark 10.12 m off vs the same set-up made in main, warning "21.93 m more cable than the water is deep … at frame 1"; control `e10c_old_repairs.py` (REPO = v0.2.109): Build at frame 1 repairs it there. Retyping the layback repairs it. Read here: the skip at 832–833. | A `load_post` step for scenes not stamped by 0.2.113+: `anchor` every sea cable once at the first frame, then stamp. Test: the late-built 0.2.109 file = the main-made project. | cable paths | Sonnet | Medium |
| 6 | **wrong result** (0137 × 0138) | `paths._motion_bake` (paths.py:3397) / `_motion_timer` (3412); likely `flex._motion_bake` (flex.py:1739) too. 0138's "show frame 1 first" is only in `animation.bake` (612–613) | The **re-bake after a sea-state / vessel / vessel-speed change after Build depends on the frame shown.** Small demo, built, CALM → ROUGH: with frame 1 shown the re-bake equals a Build with ROUGH exactly; with the last frame shown "Second end" is up to **8.13 m** off on 3,243 of 3,806 frames (worst in shots 10–11), "Power cable" 1 mm. In the window this is the timer route – the owner changes the sea while looking at a late shot. | **(helper)** A/`e18b_demo_rebake_vs_build.py` (log `out/e18b.log`, shapes `out/e18b_{A,B,C2}.npz`, `e18c_where.py`); not the 6-digit `_scale` (`e18d_scale.py`: 1.0 at every frame). The small test model (`e1_rebake_frame.py`) shows nothing: it needs the second end. Read here: `_motion_bake` reads at the frame shown. | `frame_set(frame_start)` in `paths._motion_bake` and `flex._motion_bake` before reading, as `animation.bake`, then the shown frame back. Test: re-bake at the last frame = Build. | cable paths | Opus | Medium |
| 7 | **wrong result** (new in 0.2.107) | `blender/sequence.py:338`, `368`, `376` (`home_top` / `_home_pop` pop the top of a per-part stack, whoever pushed it) | Nested steps **not in strict reverse order**: Take apart CARRIAGE.UNIT, Take apart SLIDE.UNIT, Put together CARRIAGE.UNIT, Put together SLIDE.UNIT → the 3rd step pops the SLIDE layer: **"Put together CARRIAGE.UNIT" leaves the carriage apart** (80 mm up at its own take-apart place; 0.2.104: home, 0 mm); in the last step the rail block flies through the waiting parts. No Build warning. | **(re-run)** C/`seq_nonlifo.py <scratch>` (deep.step from `make_deep.py`): carriage z after each step 80 / 284 / **80** / 0 (v0.2.104: 80 / 284 / 0 / 0); `seq_nested.py <scratch> nonlifo` → clash rows RAIL BLOCK × CARRIAGE 19.99 mm, × GRIPPER BLOCK 19.98, × SPLIT PIN 18.89. | Push (subassembly, delta); a Put together pops the newest entry its own subassembly (or one inside it) pushed, else the top. Test with the order above. | assembly sequence | Opus | Medium |
| 8 | **wrong result** | `paths_sea.water_changed` (818) with a built animation: `_rebuild` draws from stored places that hold the old seabed; 0137's one route does not cover the waterline | **Water level changed after Build:** the built sea cable lies **1 m under the seabed at every frame**, the animation still counts as built, nothing says "Build again" (older than 0.2.110; 0.2.109 also jumps the touch-down 21 m). | **(re-run)** A/`e16_waterlevel_after_build.py`: test_moving + Sea, water 2.0 → 3.0 after Build, end minus seabed −14.976 → **−15.976** m at frames 1/150/289; a Build repairs it. The cable's own depth change after Build is right (`e8_depth_after_build.py`). | When built, `water_changed` re-bakes the sea cables (as `paths.motion_changed`) or takes the Build off with a note. | cable paths | Sonnet | Medium |
| 9 | **wrong result** (since 0100) | `blender/sequence.py:456` (`_visibility`: `if end == "STAY": return`) | Take apart with At the end **Hide** or **Fade**, then Put together with the default **Stay**: the whole Put together plays invisible and the unit stays hidden / faded at the end. No warning. | **(re-run)** C/`seq_hide_stay.py`: SPINDLE.UNIT, FADE → STAY and HIDE → STAY: **0 of 12** parts render at the last frame; HIDE → HIDE, FADE → FADE: 12 of 12. v0.2.104 the same. | A Put together makes its parts visible and unfaded from each part's come-in, whatever its own At the end says (or Build warns). | assembly sequence | Sonnet | Low |
| 10 | **wrong result** | `blender/web3d.py` `_bake_material` / `Baker.tiles` (looks baked on flat 0.2 m tiles at z = 0) | **Marine looks vanish on the web page:** growth band, mottling, streaks and the worn blade edge depend on world height, up direction, normal or the part's own z – a flat tile facing up cannot carry them. Crane with marine growth, waterline 0.3 m: the Cycles render shows the growth, the page plain yellow paint; the worn edge must come out unworn (tile normal · edge direction = 0). Matters for the turbine pages (0128). | **(helper)** B/`marine_web.py mw` → `shots/growth_render.png` vs `shots/growth_page.png` (`viewshot.js`); erosion and streaks by reading. Read here: the tile bake. | Bake these looks per object on the part's own UVs (as the light bake does); at least say in the panel / export line that marine looks show as plain paint. | web 3D | Opus (warning: Sonnet) | Medium (Low) |
| 11 | **wrong result** | `web/fr_page.js:1095–1099` (`lowest` clamp) | A saved view **below the water** (sea page) or below the floor (plain page) is pushed up: the page can never show 0128's "Seabed" camera or an underside view. Asked eye y −4 / target −3.5: sea page −1.60 / −3, plain page 0 / 0. | **(helper)** B/`under.js pages/p_sea_under.html pages/p_none_under.html`; `shots/p_sea_under.png`, `shots/p_none_under.png`. | No clamp while the camera is on a saved view (until the visitor drags), or leave such views out with a note. | web 3D | Sonnet | Medium |
| 12 | **wrong result** (design question) | `states` start scene (`WORLD_KEYS`: `sea_state`, `water_level`, `weather` incl. `vessel_speed`) with 0137's re-bake | After Build the owner changes sea state or vessel speed: 0137 re-bakes and the view shows the new sea – the **next Build, and the queue's Build, silently put the start scene's values back** (the demo's "Overview" says CALM). What he checked is not what renders. | **(helper)** A/`e19_start_scene_undoes.py`: 3 → 6 kn re-baked, Build → speed back to **3.0**, no warning; demo `e18_demo_rebake.py` (`out/e18.log`): "Build with ROUGH" ends CALM, up to 0.72 m from the re-bake on 1,725 object-frames. | Lead's call: say in the panel that the start scene sets sea and weather at Build, or offer to save the change into it; at least warn when Build overrides a newer value. | cable paths / scenes | Sonnet | Low |
| 13 | **wrong result** | `blender/sequence.py:446` (`_rider_keys`: a rider's first Put together key is the plan's out place) – 0140's open point, now measured | A **rider** (a part a joint carries) in a Put together whose settings differ from its Take apart **jumps at the step's first frame** (non-riders come in from where they are). The jump goes into `fr_jumps`, so the clash check leaves it out, but it shows. | **(re-run)** C/`seq_rider.py`: deep model, carriage + gripper on joints, Take apart Up 0.1, Put together Away from centre → CARRIAGE and GRIPPER BLOCK **137.9 mm in one frame** (frame 111); without riders ≤ 0.4 mm per frame. | Start the rider's keys at its real place and blend to the plan line, as non-riders do (`d_out = start`, line 362). | assembly sequence | Opus | Medium |
| 14 | **wrong result** | `blender/web3d.py:1260` `views()` | An **orthographic** camera (the Isometric view) becomes a perspective view from its lens: the page frame is 1.96× wider, the model at half size. Perspective cameras match (×1.00). | **(re-run)** B/`ortho.py`: "ISOMETRIC type=ORTHO … camera shows 1.77 m across, page shows 3.46 m across (x1.96)". | For ORTHO: fov = 2·atan(ortho_scale / 2 / distance to the target). | web 3D | Sonnet | Low |
| 15 | page broken (rare) | `core/web3d_env.py:395` / `page_html` (only `</script` escaped) | With Hide part names off, a **camera name** holding `<!--` and then `<script` leaves the settings block open: the page stays at "Loading the 3D model …" (`SyntaxError: Unexpected non-whitespace character after JSON`). | **(re-run)** B/`make_pages.py pages` → `pages/p_views12.html`; `node errs.js pages/p_views12.html "" 6000 err`. | Escape every `<` as `<` in the JSON. | web 3D | Sonnet | Low |
| 16 | page broken for that visitor | `web/fr_page.js:855` | A remembered `off` that is not a list (a corrupt write, another version under the same `fresing-player:<path>` key) stops the page for good ("offList.indexOf is not a function"); the Reset link is in the menu that never appears. | **(helper)** B/`junk.js pages/p_anim.html`. | Type-check every remembered field. | web 3D | Sonnet | Low |
| 17 | lost time (small) | `site/render_kit/kit_window.ps1` status window tick (`elseif ($state -ne "stopped") { $pause.Text = "Pause" }`), FormClosing (asks only while the text is "Resume"); `kit_run.Pacer.checkpoint` reads `control.txt` only between frames | After **Pause** the run goes on until the picture being rendered ends (a final still: tens of seconds to minutes), and status.json says "running" meanwhile – so within 2 s the button turns back to "Pause". Closing the status window then asks nothing, and the run pauses afterwards with no window to resume it: stuck all night until the black window is closed. | **(main session, reading + run side)** me/`k9_pause_window.py`: Pause clicked 5 s into a 180 s still → status "running" at every 2-s tick for the rest of the frame, button "Pause", "close asks: False". PowerShell not run (no Windows / pwsh here). | The window keeps "Resume" while `control.txt` says pause (read it in the tick), or the run writes `state: "pausing"` when it sees the click; FormClosing checks `control.txt`. | site kit | Sonnet | Low |
| 18 | small, Windows-only | `core/house_scene.py:111/140` `read_zip`, and the pinned checker `hsf/package.py` | Python's `zipfile` cleans names before the checks: **on Windows `light\a.png` becomes `light/a.png` and is accepted** (Linux refuses), a NUL cuts a name short (`bake.json\0evil` → `bake.json`, accepted everywhere); FORMAT forbids both and House Planner's JavaScript reader sees the raw names. A non-UTF-8 name with the UTF-8 flag gets "not a zip package (damaged)". | **(re-run)** C/`house_zip.py` (patches `zipfile.os.sep` as on Windows): "backslash FR: OK ['light/a.png']", "NUL in name FR: OK ['bake.json']", checker the same. Not run on Windows. | Check the raw names (`info.orig_filename` / the central directory) for `\` and NUL first; a clear message for bad UTF-8. **Tell the format repository** (`smholte/house-scene-format`): its checker has the same gap. | house | Sonnet | Low |
| 19 | slow | `paths._motion_bake` / `flex._motion_bake` from the timer | The re-bake after a sea change takes **63–90 s on the small demo**, blocking, no progress or Cancel: Blender freezes for over a minute `MOTION_WAIT` after the change (the full demo longer, not measured). | **(helper)** A/`out/e18.log`, `out/e18b.log` (90 / 63 / 74 / 75 s), `out/e7s.log` 73 s (background; the window's timer not run). | A long job with progress and Cancel (`longjob`), or above a size mark take the Build off ("Build again") instead. | cable paths | Opus | Medium |
| 20 | old project (small) | `paths.version_settle` only in `load_post` (paths.py:3698–3724) | A scene **appended** from a 0.2.95 file settles over 4 s in the session it was appended in, 0 s after save + reopen: the same project builds differently per session. | **(helper)** A/`e13_append_settle.py`: appended `sea_settle` 4.0, stamp None; after reopen 0.0, stamp 1; Build layout 596 → 451 points. | Also stamp unstamped scenes at Build. | cable paths | Sonnet | Low |
| 21 | small | several | (a) **Let-go settle twitch** (test_moving): point 47 slides 0.87 m in one frame and back (275→276, 278→280); two Builds twitch on different frames (A/`e5_settle_jerk.py`, `e5b_settle_shape.py`, `e4b_update_where.py`). (b) `mesh_reader._decode` (609): one cp1252 byte anywhere decodes the whole OBJ/MTL as cp1252 – UTF-8 "Plåt" becomes "PlÃ¥t", a model update reports it renamed (C/`mixed_obj.py`). (c) A part hidden in 2 Structure **after** Build still shows (its sequence keys win; 18 of 21 frames), the animation still counts as built (C/`seq_misc.py <scratch> hidden_after`). (d) Web page: a software-rendering browser always writes `off=shadows` into the link, so the receiver gets no shadows (B/`r_none0.json`). (e) Phone: portrait – help covers the tool column; landscape 844×390 – the menu covers the 2nd tool column and shows ~2 sections, help overlaps the title; help says "1 … 1" with one view; the touch hint says "right-drag … ? for keys" (B/`phone.js`, `phone_land.js`, `shots/land_anim_menu.png`). (f) Screenshot of a page with a non-ASCII title saves as "download" without `.png` in headless Chromium (every site page: "… – Fresing Render"; B/`dl2.js`; check in real Chrome). (g) Kit: "done at about" shows the day in Windows' language ("ma 23:30") among English text (`kit_window.ps1` `ToString("ddd …")`, reading). | (a) **(helper)**; (b), (c) **(helper)**; (d)–(f) **(helper)**; (g) reading | (a) warm-start the settle from the previous frame; (b) decode line by line; (c) hiding a keyed part takes the Build off or says "Build again"; (d) write only items the visitor switched; (e) a narrow-height media query, help as a bottom sheet, touch wording; (f) fold the name to ASCII; (g) invariant culture | cable paths / import / sequence / web 3D / site kit | Sonnet | Low |

**Open questions (reading, no row)**
- **Worn blade edge and the real blades:** `marine_looks.py:91` fixes `edge_dir = (0, −1, 0)` and the span along the
  part's own z; nothing ties it to `iea15.leading_edge_side(mirrored)` (`tools/site_projects/iea15.py:340`), which the
  converter already works out. Right on the stand-in; a blade with other axes gets the strip on the wrong edge, no
  setting for it (0128's own open point). Suggest: the converter refuses when the two disagree.
- **Growth band with vessel motion:** the band is in world z, so a heaving hull moves through it (by design per the
  docstring; matters only for a moving hull).
- **Kit window, Windows-only parts not run:** the forms on a screen (DPI scaling, cut-off labels such as "Max.
  temperature" at 110 px), `nvidia-smi`, sleep / shut down, a PowerShell in Constrained Language Mode (falls back to the
  console route → row 4). Read and found sound: exit codes 0 / 10 / 2 and `run_result.txt`; ASCII + CRLF; the start
  window's handlers registered after the items are filled; the countdown's TopMost kept; status / control files
  written ASCII / UTF-8 without BOM and read with `utf-8-sig`; a status.json replace refused while PowerShell reads it
  is skipped, not fatal; Stop while paused; the black window closed (pid check).

**Fixes of 0136–0140 checked again – all hold**
- 0131 row 1 (export crash): moving cable not built, Live and Soft (1.3 / 24.6 s), hoses after a joint move, chains,
  spool, tracks, crane on the Vessel deck with vessel motion; export twice; cancel half-way (looks and light bake): no
  bake scene / object / material / image left, handlers put back; built animation at frame 38: frame put back.
- Rows 2, 5, 7, 14, 16a (cables): let go and contact joints kept through updates to three changed STEP files (part
  moved + new part, SHEAVE renamed, HORN and CLAMP renamed); the cables' own speed joints renamed while built (Build,
  Clear keys, re-bake at 6 kn, save + reopen + Build identical); test_moving re-bake at frames 1/150/289 = a Build; the
  motion key survives save + reopen; a 0.2.95 file opens with Settles in 0 and stamped; ramp cases ≤ 0.17 mm.
- Row 6 (0138, small demo): Build at the last frame (3806), mid shot 8b (1876), Clear keys at the last frame then
  Build at 2600, Build + save + reopen + Build at 2000 – all identical to Build at frame 1 (every cable's shape,
  touch-down, mark and warnings; CABLE END / CPS / PULL HEAD / restrictors / QUADRANT / sleeves); Make demo vs one more
  Build: 0 visible objects moved; the CPS run (0126), `haul_in`, shot 8b the same in every case.
- Rows 8–11, 16f–g (0140): nested 3 deep in reverse order, outer first, twice, Back to CAD after nested steps, a Take
  apart deleted between Builds (0.0 mm: the home stack does not leak), save / reopen, a model update between nested
  steps, nested riders with the same settings – clean; preview plan stable at 0 / 5 / 50 / 200 m from the origin.
- Rows 3, 4, 13, 15, 16b–e (0139): a moved piece, removed + moved, swapped equal pieces, unnamed parts at one origin
  keep their work; a missing .bin refused clearly, the next update works; two copies of one file keep their own file
  materials through an update and save / reopen; 1,500-part update 5.5 s (import 4.0 s).
- Row 12 (waterline): follows Sea, water level, sea state, cut-away, Vessel deck, vessel motion, save + reopen.
- **Real app (xvfb):** mesh model update undo / redo / save + reopen (file materials back, "From file" works after
  undo); sequence Build undo / redo, preview 60 → 80, Save pose during the preview, three undos, Build again: no crash.
- **House 1.0.1:** the pinned copy matches its SHA-256 list; our sample and the format's sample pass its checker;
  `sun_light` [0,0,0] under full overcast, null at night; zip names as FORMAT says on Linux (row 18 for Windows).
- **Old projects:** the whole test tour made with **v0.2.104 (38 sets) and v0.2.95 (36 sets)**, each set opened and
  every animation built in the old code and in 0.2.113, every object's place, hiding and mesh compared at 4 frames:
  nothing missing, doubled or erroring, warnings identical; only the unused "Animation camera" of the crane's
  "Finished video" / "Queue video" differs (11–12 cm; that animation's own camera is identical). Old sea-cable files
  built at a late frame: row 5.
- **Web player** on a phone (390×844 at 3×, touch, SwiftShader): loads in 0.6–2.6 s; menu, quality levels (0.33 /
  0.74 / 1.32 M pixels), view buttons and keys 1–9, 12 views with quotes / HTML / accents shown safely, link opened in a
  new page (camera within 0.02 m, time, paused, quality, items), H, screenshot, Auto never lowered; still, animated and
  sea pages and the built site's test_atc and Thor pages; localStorage throwing or full; bad link values (NaN, huge,
  0, negative, unknown items) handled; desktop 1280×800 no overlaps.

**Not tried:** a real Windows PC (kit window, row 18), a graphics card / real Chrome / iPhone Safari, the full-size demo
(the small form answered row 6 and found row 6's new case), the window's timer route of the re-bake (background route
only), scripts off (`-Y`), a model update of the demo, undo after an export and after deleting a mesh model's root in
the real app, the owner's turbine STEP (blade edge, scour protection), a real queue render of the growth look, the
test tour's sea-cable sets made in 0.2.109.

**What changed:** only this report (and `TASKS.md`: the task moved to Done). No app code, test or tool; no version,
no test run.

**Tested and measured:** 4-core web machine, Blender 5.2.3 as a module and the real app under xvfb, headless Chromium
(SwiftShader); test models from `tests/data/` and made-up ones in the scratch folders; the small demo form
(`demo.build_project(small=True)`, 3,806 frames, made in 270 s, Builds 99–120 s). Subagents: three helpers (A, B, C
above, Opus), each read and ran its area; the main session re-ran rows 1, 2, 3, 5, 7, 8, 9, 13, 14, 15, 18 with their scripts
and read the code of the others; rows 4, 17 and the kit window are the main session's own. Scratch scripts:
`/tmp/claude-0/-home-user/77abd9cb-0c50-5e66-8b57-9dadc69d1096/scratchpad/{A,B,C,me}/` (gone with the session: the
rows give each proof's numbers).

**Open points / follow-up tasks:** the rows above. First row 1 (one `pause_live` around the light bake: a crash with
lost work one guard away), then rows 2–3 and 5 (the owner's work and old projects), row 6 (frame-dependent re-bake,
Opus), row 7 (new in 0.2.107). Row 18 also concerns `smholte/house-scene-format` (its checker). Leftover: no branches,
no worktrees.
