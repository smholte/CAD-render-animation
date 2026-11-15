# Scratch scripts of study 0141 (never merged)

Why the demo's Build depends on the frame shown (bug hunt 0131 row 6). The findings and the fix plan are in
`tasks/0141-demo-build-frame-study.md` on `main`. Everything here runs with Blender as a Python module
(`~/venv/bin/python <script>`), on a web session's machine.

| Script | What it does | Time (4 cores) |
| --- | --- | --- |
| `repeat.py` | **The smallest repeat case** (for 0138's failing test): `test_moving.step` + `paths.set_up_moving_model` + a start scene; Build with frame 1 shown, then with the last frame shown. Cases A–F. | 25 s |
| `caseg.py` | The same function reached another way: the same layback / water level set again at a late frame, built and not built. | 20 s |
| `make_demo.py small\|full <folder>` | Makes the demo project (as `tests/test_demo_project.py` does). | 230 s / 261 s |
| `row6.py <demo .blend> 1 1803 -1` | Row 6 itself: Build with these frames shown, compared with what Make demo saved; logs every new touch-down and who asked for it. `FRAME1=1`: the fix plan's step 1 tried. `NOANCHOR=1`: no new touch-down during a Build. | ~70 s per frame |
| `why.py <demo .blend> 1803 -1` | What in the pose shown moves the touch-down: as it is / vessel at rest / let go ignored / both. | 50 s |
| `third.py <demo .blend> 1803 "Second end"` | The one frame left with the touch-down kept: the places read and the sea solver's numbers frame by frame. `ROUND_SCALE=1`: nothing left. | 2.5 min |
| `tourset.py <folder> [--patch log\|frame1\|noanchor] <set ids>` | A tour set built, then Build again with frame 1, 80 % and the last frame shown; compared. | seconds per set |
| `snap.py` | What is compared: app-made meshes, cable settings, joint values, every key on joints, parts and cameras. | |
