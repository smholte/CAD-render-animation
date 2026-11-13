# 0101 – One-click product video: a first complete machine video from what the project already has

**Who:** worker · **Status:** open · **Branch:** `task/0101-product-video`
**Started by:** lead chat, 13 Nov 2026 (study 0069 #18; owner's pick 12 Nov: "#18 one-click product video after 0100,
Motion lane, Sonnet · Medium")
**Lane:** Motion. New files `blender/product_video.py`, `blender/ops_product_video.py`; the button and its options in
6 Animation (`ui_motion.py` – this task is the only Motion-lane task running). Additive: `props.py`, the tour, the PC
check, the guide. Reads (does not change) `turntable.py`, `video.py` (title / end card, brand kit), `sequence.py`
(0100), `cameras.py`, `camera_path.py`, `joints.py`. Also one small Quality-lane chore at the end (below).
**Model:** **Sonnet · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

One button – 6 Animation > **Make a product video** – builds a new animation "Product video" that the owner can render
at once or adjust step by step: title card, a fly round the machine, the machine's own motions, a part taken apart and
put together again, a few close-ups, end card. A first complete video in minutes instead of an evening of steps.

## Background (read)

- Study **0069 #18** (row 18 of its table): "a template that builds title card, turntable / orbit, explode + assemble,
  the machine's motion steps, end card from what the project already has"; every piece exists.
- The pieces: `turntable.py` (0017: camera, saved scene and an Orbit step – the pattern for "make or update an
  animation tagged as ours, never overwrite the owner's"), `video.py` (0018: title card, end card, logo, captions from
  step labels – from the brand kit), the step kinds in `props.BLOCK_KINDS` (Move joint, Go to pose, Camera incl. Fly a
  path / Ride along / Watch part (0087), Fade out / in (0073), **Assembly sequence** (0100), Run motor), saved cameras
  and saved poses, "Camera views framing model or selection" (0017).
- The demo project's "What it can do today" (`blender/demo.py`, stages `shot_*`) is a hand-written example of such a
  film; this task makes a general one for any project.
- The owner's rule (CLAUDE.md section 6): never the Fresing 400 in full anywhere in the repository.

## Scope

1. **Options** next to the button (folded under it, each with a tooltip): length (about 30 / 60 / 90 s), picture
   format (as the animation's; 16:9 / 1:1 / 9:16 by 0018's crop), the subassembly to take apart (default: the largest
   one with ≥ 5 parts that is not the whole model; "none"), which motions to show (default: every joint with limits and
   every saved pose, the longest-travel first, at most a few), title text (default: the project's name) and the brand
   kit (as 0018).
2. **What it builds** (a new animation "Product video", tagged; pressing again updates it and asks before replacing
   steps the owner changed): title card → orbit / fly round the machine (0087's Fly a path from framed views) → the
   machine's motions (Move joint through each chosen joint's range and back, or Go to pose for saved poses), a camera
   that frames the moving part (Watch part) → Assembly sequence take apart, hold, put together (0100) on the chosen
   subassembly with its framed view → one or two close-ups from saved cameras if there are any → end card. Step labels
   become captions (0018) if captions are on. Timings scaled to the chosen length.
3. **Sensible for any project:** a model without joints skips the motions, one without a subassembly skips the
   sequence, a model with a G-code step / cable may reuse that step (optional); the status line says what was left out
   and why. No step is made that would fail at Build.
4. **Then:** the owner can render it with the render queue as any animation (Add to queue); a short note under the
   button says the expected length and that every step can be changed in the list.
5. Tour stop "Product video" (on one of the tour's test models with joints and a subassembly), PC-check line
   `animation.product_video` (build it, Build animation, 0 warnings, the steps in order), guide section "Make a product
   video" with a picture.
6. **Quality-lane chore (0078 follow-up):** the GitHub test times grew (full run 12 → 14–16 min): after this task's
   green run, record the times with `python3 tools/ci_status.py --run <green run> --record` and commit
   `tools/ci_times.json` (CLAUDE.md section 2, "A new test").

## Done when

- [ ] Scope 1–5 in the real app (panel screenshot checked), every button and option with a tooltip.
- [ ] Tests: the animation built on 2–3 test models (with and without joints / subassembly), Build twice = the same,
      the owner's own steps in another animation untouched; a short still sequence (contact sheet) checked by eye.
- [ ] Guide section, tour stop, PC-check line; `ci_times.json` recorded; GitHub green; report filled in; merge to main
      and release.

## Not in this task

Motion blur (#6), steady videos (#14), new step kinds, music choice beyond what 0025 has, anything in the Flex lane
(0079 / 0080 run at the same time), the demo project's own film.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
