# 0309 – Lead motions: one slider per machine function, in a drop-down on the top bar, live and in the animation

**Who:** worker · **Status:** done (0.2.236) · **Branch:** `claude/cad-render-animation-0309-i8zuvl`
**Started by:** lead, 23 Nov 2026 (owner 21:14: "a machine has 5 motions, but each motion needs 5 joints. Then you can
set lead motions, that come to a separate menu … a menu on the top bar that when clicked drops down with sliders to show
off the lead movements … when animating these lead motions are easy to access and for live viewing. The other
animations are still needed … Make it easy to show off each function, and makes animation easy. Select from a short
list when animating or showing off the project.") · **Model:** Opus · effort High
**Area:** new **Lead motions lane** – new files `core/lead_motions.py` (no Blender: the value of each joint at a slider
position, timing windows, easing), `blender/lead_motions.py`, `blender/ops_lead_motions.py`,
`blender/ui_lead_motions.py`; additive: `props.py` (a `FRLeadMotion` group beside `FRPose`), `ui_topbar.py` (one
button), `animation.py` + the step list (one step kind, as 0299 adds its Weather & time step), the step's settings where
6 Animation draws a step (`ui_motion.py`, after 0290), `lock.py` (the Client view lets the sliders move the joints, then
puts nothing back), `reimport.py` (a model update keeps the lead motions), `core/functions.py`, tour, PC check, guide.
**Not:** joints, cylinders, linkages themselves (lead motions only set joint values; whatever follows a joint today
follows it here too); the Web 3D page (that is **0310**); the 0305 build tasks (they come after this one in the
Motion lane's files).

## Goal

The person who sets up a machine (an engineer) groups its joints into a few **lead motions** – "Boom up", "Slew",
"Telescope out", "Outriggers", "Gripper close" – each one slider. Anyone else (a sales person, a client in the Client
view) opens one **drop-down on the top bar**, sees only that short list and drags a slider: the whole function moves,
live, in the right order. The same short list is what you pick from when you animate: "Lead motion: Boom up, 0 → 100 %
in 6 s". The ordinary joint and pose steps stay as they are for detailed animation work.

## Background

- Today a function of a machine is several joints moved one by one (4 Motion's joint box), or a **pose** (`FRPose` in
  `props.py`, `FRESING_PT_poses`: Save / Apply / Update / Reset) which jumps, or a joint that **follows** another at a
  ratio (`follows`, `couple_ratio`) – linear and always together. None of them gives "one slider that moves five
  joints, some after others, from here to there", and none sits where a non-technical user finds it.
- The owner's users (CLAUDE.md / the progress note, positioning 21 Nov): engineers from CAD, new to rendering; sales
  people who are not technical and need a few quick renders and movements for a client; skilled animators. Lead motions
  serve the first two directly and save the third set-up time.
- The web page plays glTF clips (`fr_page.js`, `AnimationMixer`): 0310 exports each lead motion as its own clip so the
  page gets the same sliders. Keep the data simple enough for that: per lead motion, per joint, a value at each slider
  position, nothing that needs Blender to work out.

## What to do

1. **What a lead motion is.** A name, an optional short description (tooltip and caption), its own seconds for a
   play-through (default 4 s), and rows: **joint · value at 0 % · value at 100 % · starts at % · ends at % · easing**.
   The timing window lets one slider do things in order (outriggers out over 0–40 %, then the boom up over 30–100 %).
   Joints that follow a joint (ratio, table, cylinders, linkages) move with it and are not listed. Units as the joint
   box shows them (mm, °). A joint may sit in several lead motions; say in the report what happens when two lead
   motions set the same joint (proposal: the last one moved wins, the menu shows the other slider as "moved by …").
2. **Making one – three ways, all in one function window** (0282's helper, "Lead motions…"):
   - **From two poses**: pick a start pose and an end pose → every joint that differs becomes a row (the quickest way
     for someone who already saved poses);
   - **Record**: put the machine where it starts → *Set start*; move the joints (joint box, G/R on joint parts) →
     *Set end* → the rows are the joints that moved;
   - **Pick joints** from the joint list and type the values.
   Then: reorder the lead motions (the order of the menu), rename, delete, *Test* (plays 0 → 100 → 0). An **"Order the
   joints"** helper: rows can be dragged into stages (stage 1, 2, 3 …) that set the windows for you.
3. **The menu.** A button **"Lead motions ▾"** on the top bar (next to the Fresing menu; 0279's Fr mark stays left).
   Click → a drop-down with one row per lead motion: name, slider (0–100 %, ends labelled with the joint's own values
   if one joint, else 0 % / 100 %), ▶ (plays 0 → 100 % over its seconds, again plays back), and at the bottom:
   *Back to start* (all to 0 %), *Keep open* (the same rows in a small function window that stays open and can sit on
   a second screen), *Edit lead motions…*. Dragging a slider moves the model **live**, one undo step per drag. Before
   building the button, compare 2–3 places in mock-up screenshots (top bar; the 3D view header; a small overlay in a
   corner of the 3D view) and take the one with the fewest clicks that is always visible – it must be **one click away
   in every workspace and in the Client view**. If you pick another place than the top bar, say why in the report
   with the pictures; do not stop to ask. With no lead motions yet the button opens a one-line hint + *Make one…*.
4. **Live speed.** Moving a slider on a big model must feel smooth: measure ms per slider change on the test crane, the
   test mill and the PC-check Heavy model (web machine), with Live preview off and on; target ≤ ~50 ms on the web
   machine for the crane. Only the joints in that lead motion are touched.
5. **Animating.** A step kind **"Lead motion"** in 6 Animation: pick from the short list, **From % → To %**, seconds,
   easing (the step's start as every step has it). In the drop-down each row gets **"+ Add to animation"** (a step
   0 → 100 % over its seconds at the end), and the menu a button **"Show every function"** (adds one step per lead
   motion, out and back, one after another, each with its name as a caption if captions are on – the sales person's
   one-click film of all functions). Build bakes these steps to the same joint keys a Move joint step makes (scripts-off
   safe, render queue, saved projects). Joint steps and lead-motion steps on the same joint at the same time: pick a
   rule (proposal: the later-starting step wins from its start), show a plain warning on the step, document it.
6. **Client view and workspaces.** The sliders work in the Client view (sales, clients) and need no unlocking; *Edit
   lead motions…* is not there. The button shows in every workspace (0294's workspaces when merged: Sales and Quick
   render must have it).
7. **Kept.** Saved with the project; a model update keeps them (a renamed joint follows by its id, a removed joint
   marks its row "missing" in red, nothing else lost); Save as / backups carry them.
8. **The demo / tour.** Give the test crane three lead motions (Boom up, Slew, Telescope out – timing windows on at
   least one) and the test mill two (Table X/Y travel, Door open if it has one); a tour stop that shows the drop-down;
   a lesson step in the crane lesson if 0304 has not reworked it yet (else a note for 0304).
9. Tooltips on everything; guide section "Lead motions" with pictures (the drop-down, the editor, the step); function
   entries `motion.lead_motions` and `animation.lead_motion_step` (`since=`); a Full PC-check line `motion.lead_motion`
   (slider at 50 % gives the joints the values `core/lead_motions.py` says; Build of a lead-motion step gives the same
   values at its middle frame); `MIN_LINES_FULL`, `MIN_CHECKS`.

## Done when

- [x] Lead motions made in all three ways; timing windows and stages work (tests on `core/lead_motions.py`: values at
      0 / 25 / 50 / 100 %, windows, easing)
- [x] The drop-down: one click from every workspace and the Client view; sliders move the model live; ▶ plays; Keep
      open window; place chosen with mock-ups (screenshots in the report)
- [x] Measured ms per slider change on the three models (table in the report)
- [x] "Lead motion" step + "+ Add to animation" + "Show every function"; Build gives the same values as the slider
      (test); overlap rule documented and warned
- [x] Kept through save, model update (renamed / removed joint), backups (tests)
- [x] Tests added/updated; full suite passes
- [x] (UI) screenshots checked with tools/ui_screens.py
- [x] (tour or functions changed) version fields: `since=` on new entries / stops, `changed=` raised on a changed tour
      set (`python3 tools/tour_versions.py --record`; the precheck says what to write)
- [x] Owner's test steps (numbered, click by click) in the report; merged, version, release

## Not in this task

The 3D page's sliders (0310), joints / cylinders / linkages themselves, 0305's build tasks, workspaces themselves
(0294), function windows themselves (0282 – use its helper).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (Opus · High), 24 Nov 2026. Branch `claude/cad-render-animation-0309-i8zuvl`
(the session's branch name), released as **0.2.236**.

**What changed:**

- `core/lead_motions.py` (no Blender): a lead motion = rows *joint · value at 0 % / 100 % · window start–end % · easing ·
  stage*; the joint values at any slider position, stage windows (stage k of n gets (k−1)/n … k/n, ±overlap/2), rows from
  two states (poses, Record), "moved by", ▶ positions, the step's values, Show every function's plan, `samples` /
  `to_data` (plain numbers for 0310's glTF clips).
- `props.py`: `FRLeadRow`, `FRLeadMotion` (name, description, seconds, `position` = the slider, rows), the list on the
  scene, a step kind **LEAD** (`lead`, `lead_use_from`, `lead_from`, `lead_to`).
- `blender/lead_motions.py`: the slider sets only its rows' joints (`joints.set_value`; followers, cylinders, mechanisms,
  hoses, cables follow as they do for the joint box); "moved by …"; from two poses / Record / a picked joint; stages;
  rename follows (`joints.rename` hook, step names follow a renamed lead motion); `bake_step` (a key per frame, the
  slider's own numbers). `ops_lead_motions.py` (19 buttons), `ui_lead_motions.py` (the drop-down, the editor, the step).
- **The drop-down** is a popover on the top bar right of the Fresing menu (`ui_topbar.py`, one line). Editor and Keep
  open are 0282 function windows. Client view: ▶, Test, Back to start, Keep open allowed (`lock.ALLOWED`); sliders are
  plain settings and work; Edit / + / Show every function are refused like every edit.
- 6 Animation: step **Lead motion** (pick, From where it is / From, To, duration, easing); the box lists the joints and
  says in red when another step moves the same joints at the same time.
- Function list: `motion.lead_motions` (in every workspace: `_COMMON`, and the work workspaces; button = ▶, so it works in
  the Client view), `animation.lead_motion_step` (Sales, Animator, the work workspaces). Guide sections `lead-motions`,
  `lead-motion-step` with three pictures from the real app. Crane lesson step 12 (a lead motion in two stages, made with
  the editor's own buttons; Show me slides it once). Tour: stop `lead_motions` (crane set: three lead motions and an
  animation "Every function" made by Show every function; the mill set gets *Table X travel* and *Table Y travel* – the
  test mill has no door). PC check Full line `motion.lead_motion`. Real-app test `ui_test_lead_motions.py` (24 checks,
  group paths-heavy). `tools/measure_lead_motions.py` (the table below).

**Rules picked:**

- *Two lead motions on one joint:* the last one moved wins; the other row says "moved by <it>" ("moved by hand" after the
  joint box). Its slider stays where it was.
- *A lead step and another step on the same joint at the same time:* the later-starting step wins from its start – the
  rule every step already had (`_merge` drops the keys after a later key). Build warns "Two steps move … at the same
  time"; the step's box says it in red. A joint that is not where the lead motion has it at the step's From % jumps
  there (warned).
- *Removed joint:* its row stays, marked "missing" in red, left out of the slider and of Build (warned); a renamed joint
  is followed. A follower can never be a row ("follows …").

**Where the button sits (mock-ups, `tasks/img/`):** a) top bar `0309_place_a_topbar.png`, b) the 3D view's header
`0309_place_b_header.png`, c) a corner of the 3D view `0309_place_c_corner.png`. **Picked: a) the top bar.** It is
drawn in every workspace and the Client view (one global bar, measured by the real-app test in 7 workspaces), one click
opens it, it never covers the model. b) sits at the far right after Make, is crowded already and is redrawn per 3D view
(two views = two buttons) and changed by the quiet window outside Full access. c) needs no click but covers the model
(see the picture: it sits on the crane) and would need its own drawn sliders and hit-testing. Client view:
`0309_client_view.png`.

**Tested and measured:**

- Locally (web machine, 4 cores, Linux, no graphics card): `test_lead_motions_core.py` (17), `test_lead_motions.py` (17:
  slider = its joints only, windows, follower, from poses, Record, picked joints + stages, "moved by", ▶/Test/Back to
  start, Build = slider at every tested frame and at 50 % in the middle, From where it is, jump + overlap warnings, + and
  Show every function, rename + save/reopen + model update (crane_b), removed joint, backup, Client view, every
  workspace); `test_tour.py` (125), `test_tour_clash.py` crane + mill, `test_lessons*.py`, `test_functions.py`,
  `test_workspaces*.py`, `test_form_window.py`, `test_places.py`, `test_user_guide.py`; PC check line `motion.lead_motion`
  OK (slider 1.4 ms); real app `ui_test_lead_motions.py` 24/24 (button found on screen by pixel comparison in Essentials,
  Sales, Quick render, Animator, Reviewer, All functions, Client view; one click opens it; ▶ under way after 1.5 s of 3 s,
  ends at 100 %; Keep open and the editor open as windows).
- **ms per slider change** (joints set + the scene worked out again, `view_layer.update()`, no drawing; web machine,
  4 cores, Blender as a module, `tools/measure_lead_motions.py`):

  | Model | joints | median | slowest | the same joints set directly (median) |
  | --- | --- | --- | --- | --- |
  | test crane | 2 | 0.21 ms | 1.8 ms | 0.16 ms |
  | test mill | 2 | 0.22 ms | 1.8 ms | 0.18 ms |
  | PC check Heavy machine (3,000 placed parts) | 2 | 20.9 ms | 150 ms (first change) | 21.4 ms |

  Live preview off / on (real app on the web machine's software GL, test crane, a whole 1800 × 2600 window drawn once):
  drawing alone 198 ms, with a slider change 260 ms; Live preview (Cycles, processor) 253 / 237 ms. The drawing is this
  machine's software GL; on a PC with a graphics card it is a few ms – the owner's test below.
- **GitHub runs: 4 full runs of the branch.** Run 1 (45383479219): 3 jobs red – a test's and the PC check's recording
  layouts of the top bar had no `popover` (`app.fr_mark`, `test_fr_mark.py`), and the PC check's and the real-app lesson
  test's crane lesson still counted 11 steps; all fixed (`tools/ui_test_lesson.py` does step 12 with Do it for me).
  Run 2 (45387623053): green, but tasks 0291 and 0315 took 0.2.233 and 0.2.234 meanwhile; run 3 was overtaken by 0276
  (0.2.235). Run 4 (45396520189): after merging main, 0.2.236, green (the real-app test moved to the motion group;
  0276's took its place in paths-heavy). `main` fast-forwarded to it; the release run on `main` (45401141766, reuse)
  published v0.2.236, the old version updated itself from it on Windows, offered to the apps; its landing-page job
  failed at GitHub's Pages step ("No artifacts named github-pages … re-run later", as on 45384829716 before) and
  passed on one re-run of that job.

**Subagents:** none (one area, written and tested in the session; the independent-review rule is for Windows-only code
and format rules – this task has neither).

**Open points / follow-up tasks:**

- Stages are numbers per row with **Order by stages**, not drag-and-drop (Blender's lists have no dragging between
  groups). Rows can be moved up / down.
- The test crane has no slew or telescope joint: its three lead motions are *Boom up and out* (two stages), *Boom up*,
  *Trolley out*. The demo vessel's crane could get real ones (slew, luff, hoist) – a small follow-up if the owner wants it.
- Live preview on the owner's RTX 3090: to be felt in the owner's test (step 4 below).
- 0304 (Learning hub round 2) should keep crane step 12 or move it into its new chapters.
- 0310 can read `core.lead_motions.samples()` / `to_data()` for the page's clips.

**Owner's test steps (on your PC, after Update now):**

1. Help > Fresing Render test tour… > open the tour project, stop **Lead motions: a slider each**, **Go**. The crane plays
   every function out and back with its name at the bottom.
2. Click **Lead motions** on the top bar (right of **Fresing**). You see three rows: *Boom up and out*, *Boom up*,
   *Trolley out*, each with a slider, ▶ and +.
3. Drag *Boom up and out* slowly from 0 to 100 %: the boom goes up first, then the trolley runs out. The other two rows
   say "moved by Boom up and out".
4. Press **Live preview**, then drag the slider again: it should follow the mouse without stutter.
5. Press ▶ on *Trolley out*: it runs out in 3 s; ▶ again: back.
6. **Workspace > Client view**, open Lead motions again: the sliders and ▶ work, **Edit lead motions…** is grey.
   Back to **All functions**.
7. **Edit lead motions…** – a window opens. Click **+**, pick a joint under *Pick a joint*, **Add joint**, type a value
   at 100 %, close. The new slider is in the drop-down.
8. Press **+** next to *Boom up* in the drop-down, then **Build & play**: the boom goes up at the end of the animation.
