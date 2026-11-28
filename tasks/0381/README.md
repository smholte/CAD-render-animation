# Task 0381 – prototypes and numbers (throw-away, not app code)

Scripts that measured the study (4-core web machine, Intel Xeon 2.1 GHz, 16 GB, no graphics card, Blender 5.2.3):

| Script | What it does |
| --- | --- |
| `s1_import.py` | imports the stress model with the app (Draft / Normal), makes its 8 joints, saves `draft.blend` / `normal.blend` |
| `s1b_camera.py` | puts one fixed camera in the base project, so every variant renders the same view |
| `s2_scaling.py` | Blender alone: update cost per object count (500 … 23,000 objects), hidden in 3 ways |
| `s2b_profile.py` | the same update under `py-spy --native`: where Blender spends it (`results/profile_update.json`) |
| `s3_variants.py` | turns the imported model into a variant with fewer objects (see its docstring) |
| `s4_measure.py` | one project: open, drag step, lone empty, Build + playback, pick rays, Cycles 320 x 180, save, memory |
| `s5_draw.py`, `s7_draw_synth.py` | the 3D view's drawing under xvfb (software OpenGL): real model / 11,500 small boxes |
| `s6_features.py` | instances: pick → the right part, hide one part, a colour per part (Cycles + EEVEE) |
| `s8_threads.py` | real Blender `-t 1 / 2 / 4`: does the thread count change the update cost? |
| `run_all.sh`, `table.py` | make every variant of a base project, measure each twice, print the table |

`results/`: every measurement as JSON (`Dm1_*` = Draft run 1, `Nm2_*` = Normal run 2 …). The stress model itself is
made by `fresing_render/pccheck/stress_scene.py` (invented, public).
