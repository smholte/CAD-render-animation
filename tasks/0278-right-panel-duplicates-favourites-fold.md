# 0278 – Live preview and Build & play only on the left panel; Favourites folds like the other sections and remembers it

**Who:** worker · **Status:** open – can start (0271 merged as 0.2.201; before 0272 – both change `prefs.py`) · **Branch:** `task/0278-left-panel-only`
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

## Done when

- [ ] Panel 5 has no Live preview row; the Animation section has no Build & play button; both still work from the
      left panel and its strip
- [ ] Lessons, texts, guide and function list point to the left panel's buttons; the crane and mill lessons pass
- [ ] Favourites folds; its fold (and every other left section's) survives a restart – real-app test
- [ ] `changed=` on the touched functions and tour stops (`python3 tools/tour_versions.py --record`)
- [ ] No user-facing "1–7" / "seven sections" left (step 7)
- [ ] Guide pictures redone (`tools/ui_screens.py`); full suite + GitHub run green
- [ ] Report below filled in; merged, version, release (CLAUDE.md section 7)

## Not in this task

What Live preview or Build & play do; the left panel's layout and its fold (0260); the Settings window and My usage
(0271); the rest of panel 5 and the Animation section; the side-panel look (0244's choices).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
