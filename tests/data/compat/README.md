# Compatibility test projects (task 0352)

One folder per **project format number** (`fresing_render/core/compat.py` `FORMAT`), never one per release:
`format_<n>/` holds the small invented projects `tools/make_compat_project.py` makes (`<set>.blend`, one per test-tour
set in `COMPAT_SETS`), their `summary.json` (the stored choices) and a tiny reference picture per project
(`<set>.png`). `tests/test_compat_projects.py` opens every folder here in the running version, runs the upgrade
chain, and compares the choices (exactly, or as a chain step says it changes them) and the picture (within
`PICTURE_TOLERANCE`).

**Before the baseline this folder is empty** (CLAUDE.md section 6): the tests make the project in the current
version and open it again instead.

**From the baseline on**, a release that raises `FORMAT`:

1. adds its step to `STEPS` in `fresing_render/core/compat.py` (from the old number to the new one);
2. runs `~/venv/bin/python tools/make_compat_project.py tests/data/compat` – it writes `format_<FORMAT>/`;
3. commits that folder (each project under ~1 MB, no packed pictures, no bakes).

The lead also commits `format_<BASELINE_FORMAT>/` the day the baseline is set. The precheck
(`tools/ci_precheck.py`) fails a push whose `FORMAT` has no folder here or no chain step.
