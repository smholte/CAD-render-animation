# 0297 – Study + prototype (findings only): a Blender / Fresing Render switch button at the top right, with slide options and their lag

**Who:** worker · **Status:** open – can start · **Branch:** `task/0297-study-switch-button` (branch only, never merged;
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

- [ ] Page + clips on the branch; report with the numbers and a recommended option; the lead publishes the page for the
      owner's pick → the build task

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
