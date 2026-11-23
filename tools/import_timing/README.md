# Import timing (task 0301, study – not part of the app)

Scripts that time the STEP import stage by stage. Findings and the ranked proposals: `tasks/0301-study-faster-step-import.md`.
Raw numbers of the study's runs (4-core web machine, Intel Xeon 2.1 GHz): `results/` (`r_<model>_h<helpers>.json` reader,
`b_<model>.json` Blender side, `split_big_<n>.json` the split-transfer prototype).

```bash
P=~/venv/bin/python
$P tools/import_timing/make_models.py /tmp/it/models heavy big nurbs             # invented models (no real design)
$P tools/import_timing/time_reader.py /tmp/it/models/big.step /tmp/it/c_big --helpers 4 --json r.json
$P tools/import_timing/time_build.py /tmp/it/c_big --variants --json b.json      # bpy module, on that cache
$P tools/import_timing/split_transfer.py /tmp/it/models/big.step 4 --mesh        # each process: parse, its share
$P tools/import_timing/step_hash.py old.step new.step                            # unchanged parts between revisions
```

- `time_reader.py` runs the same steps as `importer/step_reader._read_step` with a clock round each one; its helpers
  (`time_worker.py`) are the app's helper loop with a clock per part. Checked: the app's reader took 11.6 s on Heavy
  with 3 helpers, this one 11.2 s; same parts and triangles.
- `time_build.py` runs `ops_import.finish_import`'s steps one by one; `--variants` times faster ways to make the meshes.
- `split_transfer.py` and `step_hash.py` are prototypes that only measure.
