# 0278 – Live preview and Build & play only on the left panel; Favourites folds like the other sections and remembers it

**Who:** worker · **Status:** done (0.2.204) · **Branch:** `task/0278-left-panel-only`
**Started by:** lead, 21 Nov 2026 (owner 20:02, screenshot of 0.2.197 with the crane lesson done: "the live preview under
5 Scene and Render can be removed because it's now always available on the left menu. The same for Build and play.
Favourites section on the left should be possible to fold in like other functions; this one remembers its position
when opening and closing the app.") · **Model:** Opus · effort Medium
**Area:**
- `blender/ui.py` – panel 5 Scene & Render only: the "Live preview" row above **Render image** (`ui.py` ~line 1277);
- `blender/ui_motion.py` – the Animation section only: the **Build & play** button (~line 1122). The X beside it
  (`fresing.anim_clear`, stops / clears the built animation) and the "Built · Space plays it again" line stay;
- `blender/ui_usage.py` – `FRESING_PT_favourites` (today `HIDE_HEADER`, so it cannot fold);
- `blender/prefs.py` – one new per-user setting for the fold (additive, next to `left_folded`);
- texts that say "Build & play **above**" (`ui_fade.py`, `ui_clash.py` – text only), the lessons' button pointers
  (`blender/lessons/crane.py` step `animation.build`, `lessons/mill.py` – whatever points the highlight at the removed
  button), `core/functions.py` entries of the two buttons (`changed=`), the guide, tests, CHANGELOG.
`blender/ui_left.py` (0260's left panel) is read, not changed, unless the fold needs a helper there.

## Goal

Each of the two always-there buttons exists once – on the left panel (also in its folded strip) – and the right panel
gets shorter. Favourites folds with the same arrow as Learning hub, Lesson and What's next, and stays folded or open
after the app is closed and opened again.

## What to do

1. **Live preview:** remove the row from panel 5. Render image stays the section's blue button.
2. **Build & play:** remove it from the Animation section. Keep the X (give it a tooltip that says what it does now
   that it stands alone, or a short label if alone it is unclear – your call, show both in the report) and the "Built"
   line.
3. **Every pointer to the removed buttons** goes to the left panel's buttons: texts ("Press Build & play above" →
   "Press Build & play (top left)"), lesson steps and their highlight (the crane and mill lessons' `animation.build`
   step must light up the left panel's button, also when the left panel is folded to its strip – then the strip's
   icon), the guide (text + pictures of panel 5 and Animation), the function list's guide anchors. Search the whole
   repository for `anim_build`, `fresing.preview`, "Build & play", "Live preview" and list in the report what you
   changed and what you left (helper buttons that only appear when something is missing – e.g. Clash's "No built
   animation to check yet" – **stay**: they are a hint, not a duplicate; list them for the owner).
4. **Favourites folds:** a header with the fold arrow like the other left sections (star icon, the gear button on the
   right of the header as today). Folded = only the header. The open / folded choice is kept **per user in the
   preferences**, like the left panel's own fold (`left_folded`), so it survives closing the app, opening another
   project and an update. The "You haven't used … recently" question keeps showing when it is due (folded: a small
   dot or "1 question" on the header – pick one, say which).
5. **Check the other left sections too** (All functions / workspace, Learning hub, Lesson, What's next): do they keep
   their fold after a restart? If not, give them the same per-user setting – the owner expects all of them to behave
   the same. Report which needed it.
6. Real-app test on the web machine: fold Favourites, quit, start again → still folded; the crane lesson's Build step
   highlights the left button (open and folded strip).
7. **"1–7" becomes "1–8" everywhere** (owner 21 Nov 21:42, screenshot of the Fresing menu's **User guide** tooltip:
   "what each section 1–7 is for" – since 0201 there are eight sections, 8 Lifting plan). Texts users see: the User
   guide tooltip (`app_template/fresing_render/__init__.py` ~line 145), the "sections 1 to 7 start folded" setting
   (`prefs.py` ~line 41), the tour text (`tour.py` ~line 5109 – one sentence, text only), the guide
   (`docs/USER-GUIDE.md`: "sections 1 to 7", "seven sections", the picture alt texts) and the guide pictures
   `docs/img/sidebar_sections.png` / `panel_top_tabs.png` (they show seven – 0201's open point). Also the docstrings and
   check names that say 1–7 (`panels.py`, `ui_header.py`, `tools/ui_test_layout.py`, `tools/update_test_blender.py`).
   Search the whole repository once more (`git grep -n -E "1[–-]7|1 to 7|seven sections"`) and fix any other user-facing
   one; better still, write the number from `places.SECTIONS` where a text is made in code, so a ninth section
   needs no hunt.
8. **Short tooltips on the section tabs All · 1 … 8** (owner 21 Nov 22:45, screenshot of tab 3's tooltip "Shows only 3
   Looks, opened: the other sections are out of the way until you click All again": "only short 'Looks' or so, this
   goes for sections 1–8"). Tab 1–8: just the section's name ("Import", "Structure", "Looks", … "Lifting plan");
   **All**: "All sections". Both places in `panels.py` (`FRESING_OT_panel_tab.description` ~line 463 and `_tab_items`
   ~line 491). The longer explanation (Ctrl+click, out of the way until All) stays in the guide only.

## Done when

- [ ] Panel 5 has no Live preview row; the Animation section has no Build & play button; both still work from the
      left panel and its strip
- [ ] Lessons, texts, guide and function list point to the left panel's buttons; the crane and mill lessons pass
- [ ] Favourites folds; its fold (and every other left section's) survives a restart – real-app test
- [ ] `changed=` on the touched functions and tour stops (`python3 tools/tour_versions.py --record`)
- [ ] Section tabs' tooltips are the section's name only; All = "All sections" (step 8)
- [ ] No user-facing "1–7" / "seven sections" left (step 7)
- [ ] Guide pictures redone (`tools/ui_screens.py`); full suite + GitHub run green
- [ ] Report below filled in; merged, version, release (CLAUDE.md section 7)

## Not in this task

What Live preview or Build & play do; the left panel's layout and its fold (0260); the Settings window and My usage
(0271); the rest of panel 5 and the Animation section; the side-panel look (0244's choices).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 21 Nov 2026 · 0.2.204

**What changed:**
- **Live preview** row gone from 5 Scene & Render > Image size & render (Render image stays its blue button);
  **Build & play** gone from 6 Animation. Both stay on the left panel (open + strip). `ui._viewport_rendered` (only
  used by that row) removed.
- **The X** (`fresing.anim_clear`): my call – an icon-only X beside the line "Built · Space plays it again", shown
  only while the animation is built; new tooltip: "Stops the built animation and clears it: the model goes back as it
  was before Build & play, and the joints can be moved by hand again. Build & play (top left) builds it again". Not
  built: a grey hint "Not built yet: Build & play is at the top left." (A label "Clear" beside a hint was tried
  first: the hint was cut off at the default width, so it went.)
- **Pointers moved to the left:** function `animation.build` now names `FRESING_PT_left_quick` (`changed=0.2.204`),
  so the crane (step 9) and mill lessons' Build step light up the left button – and the strip's icon when folded
  (real-app test). Texts: `ui_clash` how-to, `ui_fade` (2), `ui_people`, `ui_machining`, `toolpath.py` message,
  `clash.py` error, the two lesson texts, `prefs.live_preview`'s description, `ui.primary` docstring → "(top left)".
  **Left as they are** (hints, not duplicates, or no place named): Clash's "No built animation to check yet" with
  its Build & play button; texts "… press Build & play" that name no place (ops_paths, ops_tracks, ops_people,
  ops_tc_person, ops_toolpath, ops_machining, ui_gcode, ui_coolant, ui_tracks, ui_paths, ui_spool, sequence,
  coolant, machining, props); code comments "the section's one blue button is Build & play" in ui_flex / ui_paths /
  ui_spool / ui_machining (internal only).
- **Favourites folds:** no longer `HIDE_HEADER` – the app's title row with the fold arrow, star icon, gear on the
  right; folded with a question waiting the header says **"1 question"** (chosen over a dot: readable).
- **Folds kept over a restart – a finding:** Blender 5.2.3 does **not** keep the extension's own preferences over a
  restart while the app template is on (measured: a value saved with Save Preferences reads back as its default with
  `--app-template fresing_render`, and as saved without the template). So 0260's `left_folded` / `next_folded` never
  survived a restart either, and neither does any other Fresing setting in the preferences (keep sections, lesson
  look, backups, Live preview's last choice …). For this task the left panel's folds now live in
  `<config>/fresing_left.json` (like `fresing_layout.json`): every left section's fold (only the user's own click is
  remembered; a lesson / test opening a panel is not), the left panel's fold to the strip + its width, and What's
  next. Read at the first look after the start and at every project load. **Step 5 result:** all of them needed it –
  Workspace, Learning hub, its stops, Lesson opened again at every start/load; What's next and the strip forgot after
  a restart. `prefs.py` got no new property (only the "1 to 8" description) – less for 0272 to merge.
- **1–7 → 1–8:** User guide tooltip (app template), `keep_sections` description and the tab's description (count from
  `places.SECTIONS`), tour text (from `places.SECTIONS`), guide (3 places + alt texts), docstrings in `panels.py`,
  `ui_header.py`, `places.py`, `core/usage.py`, check names in `ui_test_layout.py` / `update_test_blender.py`,
  CLAUDE.md. `sidebar_sections.png` now has 8 Lifting plan (`guide_screens.py` list); `panel_top_tabs.png` came out
  identical (it already showed 1…8).
- **Step 8 (owner 22:45): the section tabs' tooltips are short** – 1 … 8 only the section's name ("Import" …
  "Lifting plan"), All "All sections"; one helper `panels.tab_tip` used by both `FRESING_OT_panel_tab.description` and
  `_tab_items`; test `test_the_section_tabs_have_short_tooltips`. `tooltip_report.py` now lists these two as "weak"
  (too short / repeats the label) – wanted by the owner, not a fault (it is not `--strict`'s "missing").
- Guide: left panel section (no duplicates, the folds), Image size & render step 4, 6 Animation step 6, Favourites,
  the sections; pictures redone: panel_5_output, panel_6_animation / motor / fade / camera_ride / camera_path /
  sequence / product_video / back_to_cad, sidebar_sections, usage_bar. COMPANY-USE names the new file.
- PC-check line `panel.folds` (Full, MIN_LINES_FULL 119); function `panel.left` and `usage.favourites` `changed=`;
  crane tour set `changed=0.2.204` (lesson text) + `tour_versions.py --record`; CLAUDE.md section 8 entry.

**Tested and measured** (4-core web machine, test crane): `tests/test_left_folds.py` (new, 8) + functions, places,
panels, usage, settings, workspaces, lessons, guide, about, learning, phase2, tour: 380 passed. Real app
`ui_test_left.py` 42/42 (was 30): lesson Build step points at the left button, open and strip; Favourites / Learning
hub / Workspace / What's next fold, then **a second app is started in the same settings folder** and finds them as
left (6 s); `ui_test_layout.py` 69/69. PC check `panel.folds` + `panel.two` OK. GitHub: see below.

**Open points / follow-up tasks:**
- **All other Fresing preferences are lost at every restart in the app** (see above) – a lead decision: either ship a
  `userpref.blend` in the app template (Blender then keeps the template's preferences in its own file – changes where
  all preferences live) or keep the app's settings in a file of its own. 0272 (Locations, `prefs.py`) should know
  this before it starts.
- No subagents were used.
- **GitHub runs: 4 full runs + 1 re-run of one job.** Run 1 (0.2.202): the lesson real-app test clicked step 9 in
  the side panel (fixed: `ui_test_lesson.py` clicks in the region the highlight drew in) and the PC check ran out of
  its 15 min on a slow runner. Run 2: green, but 0253 had taken 0.2.202 meanwhile → merge, 0.2.203. Run 3: 0259 took
  0.2.203 → merge, 0.2.204; its PC check timed out again on a slow runner (every line slower, renders ~2x; reached
  line 107 of 111 at 12 min, the green run at 8 min) – the failed job was re-run once: 12.1 min, green. The PC
  check's group sits close to its 15-minute box on a slow runner: worth splitting further (lead).
- The panel_6_* guide pictures were made before 0259 put the crane at real size (their numbers are the old crane's).
