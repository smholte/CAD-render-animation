# 0297 – Study + prototype (findings only): a Blender / Fresing Render switch button at the top right, with slide options and their lag

**Who:** worker · **Status:** done (findings, branch only) · **Branch:** `task/0297-study-switch-button` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39, with a screenshot of 0.2.212's top bar, an area marked at
its far right: "Add a separate Blender button to the top right corner of the menu. When in full Blender mode the button
changes into a Fresing Render button. (possibly have it change with a small sliding animation, try different options,
show them to me and the lag it adds)") · **Model:** Opus · effort Medium
**Area:** findings only. Prototype code in new files on the branch; reads `blender/ui_topbar.py`, `blender/quiet.py`
(the top bar's right part), `lock.blender_ui`, `fresing.blender_all`, 0279's Fr mark. Clips and the page in
`tasks/0297_page/`. Not a code slot.

## What to find out

1. **Place:** the top bar's right end, in every workspace and in full Blender (where Blender's own top bar is back);
   never covered at 1920 and 2560 px wide; next to what is already there.
2. **Looks (3–4):** A – a plain button whose text swaps at once ("Blender" ↔ "Fresing Render"); B – a two-part pill
   "Fresing Render | Blender" whose filled side slides (~150 ms); C – the label slides out and the new one in; D – a
   fade. Whether Blender's logo may be used on it (check the Blender Foundation's logo rules at the source) – else
   words and the Fr mark only.
3. **Lag:** Blender cannot animate its UI by itself – a timer redrawing the top bar for 150–250 ms. Measure in the real
   Blender under xvfb on the 4-core web machine: how long the switch takes today (`fresing.blender_all` and back), what
   each animation adds, and whether the redraw loop costs frames in a playing animation. Say which numbers the owner
   should check on his PC.
4. **Page** (as 0168 / 0244): a short clip of each option in the real top bar at 2560 px, the measured switch time and
   added lag, pick ticks + a Copy line for the owner's answer.

## Done when

- [x] Page + clips on the branch; report with the numbers and a recommended option; the lead publishes the page for the
      owner's pick → the build task

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 23 Nov 2026. Branch `task/0297-study-switch-button` (commits `[skip ci]`,
never merged, no version change). Page `tasks/0297_page/index.html` (clips `clips/`, pictures `img/`, numbers `data/`),
prototype `tasks/0297_page/proto/switch_proto.py` (modes measure / clips / bars) + `make_clips.sh`.

**What changed:** nothing in the app. The prototype appends a draw function to `TOPBAR_HT_upper_bar` (only in its
right region – the top bar is two regions and an appended draw runs in both; without the check the button showed twice,
once after the Fresing menu) and calls `fresing.blender_all`. Four looks: A plain button (names where it takes you),
B two-part pill "Fr Fresing Render | Blender" whose blue half (where you are) slides, C label slides, D greyed blink.
**Recommended: B, 150 ms.**

**Tested and measured** (4-core web machine, no graphics card, xvfb, UI scale 1.0; test crane unless said):
- Place: far right of the top bar; fits in every workspace and in full Blender at 1920 and 2560 px (1920 full Blender:
  ~100 px free between the tabs' + and Scene). Slot 12 UI units (240 px) so both halves hold "Fr Fresing Render".
- The switch (`fresing.blender_all`, both ways, 24 clicks at 2560 × 1440): 1.3–2.1 ms (two at 3.5 / 4.3 ms); the top
  bar's right region draws ~2 ms after the click. The button's Python draw: 0.5 ms median (max 0.9, 77 draws).
- **The top bar has no Python draw handler** (no `bpy.types.SpaceTopBar`): nothing can be drawn freely there (no gpu /
  blf, no real slide of text, no alpha). B, C and D are made of Blender's own buttons with `ui_units_x` widths and
  `active` / `depress`. A true fade is impossible (D = greyed steps); C can only drop letters and shrink the button.
- **Redraw:** `context.region.tag_redraw()` (or `context.area`) of the top bar, kept from its draw call, from a 1/60 s
  timer works: 3–4 top-bar frames in a 150 ms slide at 1280 × 720 empty scene. The whole-window trick of
  `lock._topbar_redraw` (`screen.show_statusbar = …`) gave **0** top-bar frames in 350 ms – and on its own does not
  repaint the top bar at all until the mouse moves over it (the first 1920 shot after a switch showed the old bar).
- Whole-window redraw at 2560 × 1440 with the crane: 202–220 ms (software GL) → only 2 frames per slide (start, and
  the end 280–350 ms after the click): the slide cannot be seen on this machine. Clips are therefore drawn by the real
  top bar at forced steps of the slide (10 steps) and timed in the GIF (real speed 20 ms a step, slow 140 ms).
- A playing animation (sync off, frames as fast as possible): 3.3–3.4 frames/s with and without the slide looping
  non-stop – no difference this machine can show (p95 frame 309–331 ms without, 318–378 ms with).
- Logo: www.blender.org is not reachable from the web machine – the Blender Foundation's logo rules were **not** read at
  the source. Prototype uses words + the Fr mark only.
- Runs: no GitHub run (`[skip ci]`); 6 real-app runs locally.

**Open points / follow-up tasks:**
- Lead: check blender.org/about/logo (and its trademark page) before offering the logo choice.
- Build task (after the owner's pick): the button in `ui_topbar.py` / `quiet.py` (right region only), always drawn
  (also in full Blender, where `quiet` gives Blender's own right part back), redraw by the top-bar region's own
  `tag_redraw` from a timer only while the slide runs; in the Client view `fresing.blender_all` is refused, so the
  button is hidden or greyed there; function entry, guide, tour stop, and a **PC-check
  line that measures on the owner's PC**: top-bar frames during the slide (expected ~9 at 60 Hz), click to rest
  (expected ≤ ~170 ms), and a playing animation's frames/s while the switch runs. These three are the numbers the owner
  should check; nothing here measured them with a graphics card.
- `lock._topbar_redraw` does not repaint the top bar on its own (see above) – worth a look in the 0222 C / quiet-window
  lane; the top bar's tabs after a switch may only update when the mouse moves.
