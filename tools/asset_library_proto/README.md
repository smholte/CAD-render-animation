# Task 0286 proof – a tiny "Fresing standard" library as a Blender 5.2.3 remote asset library

Not part of the app. Study files only (branch `task/0286-study-asset-libraries`, never merged).

| File | What |
| --- | --- |
| `make_assets.py` | Makes 4 test assets, all drawn by the script (CC0 by their maker): a 360° sky (World, packed 1k EXR), a worn paint material (packed 256 px picture), a euro pallet at real size (Object, 1.2 × 0.8 × 0.144 m, packed wood picture) and a small workshop corner (Collection, 10 × 10 × 4 m). One self-contained `.blend` each, with a Cycles picture as preview, author, licence `CC0-1.0`, tags, a catalog and Fresing's own custom properties `fr_source`, `fr_kind`, `fr_size_m`, `fr_licence_url`, `fr_pass_on` (Blender's listing carries them along). |
| `try_in_blender.py` | Runs inside the real Fresing app (app template) under xvfb: adds the library as a **remote** library, opens Blender's Asset Browser on it, downloads all assets, places them, renders, saves a project with the assets packed, saves the preferences. Step `check` = a second start (offline) in the same settings folder. |

Steps (4-core web machine, Linux, Blender 5.2.3):

```bash
B=~/blender-5.2.3/blender-5.2.3-linux-x64/blender
$B -b --factory-startup --python tools/asset_library_proto/make_assets.py -- /tmp/lib        # ~5 s
#   edit /tmp/lib/_asset-library-meta.json once (name, contact) – the generator keeps it
$B -c asset_listing generate /tmp/lib                                                       # 0.09–0.12 s
(cd /tmp/lib && python3 -m http.server 8286 --bind 127.0.0.1 &)
~/venv/bin/python tools/web_install_app.py --user /tmp/fr_user                              # the app, 13 s
$B -b --factory-startup --python-expr "import bpy;bpy.ops.wm.save_as_mainfile(filepath='/tmp/start.blend')"
BLENDER_USER_RESOURCES=/tmp/fr_user XDG_CACHE_HOME=/tmp/xdg FRESING_NO_WELCOME=1 FR0286_OUT=/tmp/out FR0286_STEP=add \
  xvfb-run -a -s "-screen 0 1600x1000x24" $B -p 0 0 1600 1000 --app-template fresing_render --online-mode /tmp/start.blend \
  --python tools/asset_library_proto/try_in_blender.py
# then FR0286_STEP=check with --offline-mode
```

Results and snags: the report in `tasks/0286-study-online-asset-libraries.md`.
