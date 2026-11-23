# 0309 – Lead motions: one slider per machine function, in a drop-down on the top bar, live and in the animation

**Who:** worker · **Status:** open – waits for 0282, 0290 and 0307 · **Branch:** `task/0309-lead-motions`
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

- [ ] Lead motions made in all three ways; timing windows and stages work (tests on `core/lead_motions.py`: values at
      0 / 25 / 50 / 100 %, windows, easing)
- [ ] The drop-down: one click from every workspace and the Client view; sliders move the model live; ▶ plays; Keep
      open window; place chosen with mock-ups (screenshots in the report)
- [ ] Measured ms per slider change on the three models (table in the report)
- [ ] "Lead motion" step + "+ Add to animation" + "Show every function"; Build gives the same values as the slider
      (test); overlap rule documented and warned
- [ ] Kept through save, model update (renamed / removed joint), backups (tests)
- [ ] Tests added/updated; full suite passes
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] (tour or functions changed) version fields: `since=` on new entries / stops, `changed=` raised on a changed tour
      set (`python3 tools/tour_versions.py --record`; the precheck says what to write)
- [ ] Owner's test steps (numbered, click by click) in the report; merged, version, release

## Not in this task

The 3D page's sliders (0310), joints / cylinders / linkages themselves, 0305's build tasks, workspaces themselves
(0294), function windows themselves (0282 – use its helper).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
