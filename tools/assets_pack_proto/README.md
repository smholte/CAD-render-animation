# Task 0344 proof – the Fresing assets pack: append vs link in Blender 5.2.3, and the registry

Not part of the app. Study files only (branch `task/0344-study-assets-pack-plan`, never merged). Everything here is
made up by the scripts (CC0); nothing of anyone else's, nothing of the owner's.

| File | What |
| --- | --- |
| `make_test_pack.py` | Blender script: writes a made-up pack `fresing_assets/` – `pack.json`, `LICENSE-ASSETS.txt`, one `.blend` per asset (a procedural node group, a material with 3 pictures, a world with an HDRI, an environment collection, a prop at real size), pictures at 1k / 2k / 4k, HDRIs at 2k / 4k. Version `1.1.0` changes a look and a picture. Third argument `packed`: the pictures packed inside each `.blend` instead (0286's style). |
| `try_pack.py` | Blender script, one step per run: `bring` (append or link the 5 items into a project – the group material is the app's own with the pack's group as its look), `open` (what is missing, a small Cycles picture), `update` ("Use the new Fresing looks": 1.0.0 → 1.1.0), `memory` (Cycles memory of a close-up at 1k / 2k / 4k: picture files, with `.tx` files, packed), `reuse` (Blender's `reuse_local_id`). |
| `run_proof.py` | Plain Python: runs every step in its own Blender, hides the pack for the "client" steps, writes `results.json` and `results.md`. |
| `registry_proto.py` | Plain Python, no Blender: `pack.json` check (missing / damaged / newer / outside the app window / contract too new – never raises, one note) and the registry (pack or code under the same id; the project's own choice first). `--selftest`: 19 checks. |

Run (4-core web machine, Blender 5.2.3 Linux):

```bash
python3 tools/assets_pack_proto/run_proof.py ~/blender-5.2.3/blender-5.2.3-linux-x64/blender /tmp/fr0344          # ~6 min
python3 tools/assets_pack_proto/run_proof.py ~/blender-5.2.3/blender-5.2.3-linux-x64/blender /tmp/fr0344 --extras  # ~5 min
python3 tools/assets_pack_proto/registry_proto.py --selftest
```

Methods: `append_ext` (append; pictures stay files in the pack), `append_packed` (append, then pack every picture into
the project), `link`, `link_packed` (link + Blender 5's "pack linked data", `libraries.load(link=True, pack=True)`).
A "client" = the project file alone in another folder, the pack hidden. The magenta column of `results.md` counts
fully magenta pixels only; missing pictures show as a pink tint (mean colour) – look at the pictures.

Results and what they mean: the report in `tasks/0344-study-assets-pack-plan.md`, section 2.
