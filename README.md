# Fresing Render

[![Tests](https://github.com/smholte/CAD-render-animation/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/smholte/CAD-render-animation/actions/workflows/tests.yml)

Photo-realistic renders and animations of large STEP assemblies (hundreds to thousands of
parts), built on Blender 5.2 LTS and its Cycles renderer. Owned by Fresing.

- **CLAUDE.md** – how the AI works on this project (read first)
- **TASKS.md** – open and finished tasks; one file per larger task in `tasks/`
- **CHANGELOG.md** – what changed in each version
- **docs/README-install.txt** – install and use (shipped with the installer)

## What it does

Phase 1 (stills):

1. **Import** a STEP file (Inventor, Fusion, any CAD). OpenCascade reads it in a separate
   process; the assembly tree, part names and CAD colours are kept, repeated parts (bolts)
   are stored once, every part gets a stable ID. Unchanged files re-import instantly from a cache.
2. **Structure**: subassemblies with lock/unlock, show/hide, click-selects-subassembly
   (Inventor-like), clean-up of internal and tiny parts.
3. **Looks**: parts are sorted into material groups by rules. Standard parts are recognised
   by name (DIN/ISO/EN, size, property class, stainless grade, finish), so black socket
   screws and galvanized hex bolts get different materials. Material library with paints
   (full RAL Classic table), metals, fastener finishes, plastics, glass. Paint schemes and
   templates (JSON) for the next machine.
4. **Scene & Render**: solid colour (exact colour), 360° HDRI, sky or transparent
   background; built-in studio light; shadow-only or visible floor; cameras fitted to the
   model; formats by use (16:9, 21:9, square, 9:16, A4/A5/A3 at 150/300 dpi with bleed)
   x resolution (540p to 8K); GPU picked automatically (OptiX, CUDA, HIP...).

Phase 2 (motion): joints, poses, exploded views, visibility sets, saved scenes, animations
and a background render queue; model updates to a new STEP revision keep all work.
See CHANGELOG.md.

## Layout

```
fresing_render/          the Blender extension
  core/                  pure Python, no Blender: fasteners, rules, RAL, materials, presets, templates
  importer/              STEP reader (OpenCascade) + subprocess runner
  blender/               bpy code: build, materials, world, cameras, render, operators, UI
  data/test_machine.step small test model (used by the self-test)
  selftest.py            installation self-test (writes a report on the Desktop)
app_template/            "Fresing Render" app layout for Blender
installer/               Windows installer (PowerShell, no admin rights)
tools/                   build_release.py, test-model makers, real-app tests, ci_* helpers of the automatic tests
tests/                   pytest: core + full Blender pipeline
docs/                    install readme, update channel, development notes
```

## Develop

```
python -m venv venv
venv/bin/pip install -r tools/requirements-dev.txt
venv/bin/python -m pytest tests/          # 1,260+ tests, about 6 minutes on 2 cores
venv/bin/python tools/build_release.py    # dist/: extension zip, installer zip, update repo
```

Every push and pull request runs the tests on GitHub by itself (`.github/workflows/tests.yml`):
the test suite and the real app on Linux, and an unattended install + self-test on a real
Windows machine. The badge above shows the state of `main`; `python3 tools/ci_status.py`
shows a run from the command line. See CLAUDE.md section 5.

See docs/DEVELOPMENT.md and docs/UPDATES.md.
