"""Task 0242 (throw-away): run the PC-check lines web3d.small and web3d.under N times from the app code at ROOT
(Blender as a Python module), print each result."""
import os, sys, time
root, n = os.path.abspath(sys.argv[1]), int(sys.argv[2])
sys.path.insert(0, root)
os.environ["FRESING_SELFTEST_NO_GPU"] = "1"
os.environ["FRESING_PCCHECK_ONLY"] = "web3d.small,web3d.under"
import bpy
import fresing_render
bpy.ops.wm.read_factory_settings(use_empty=True)
fresing_render.register()
from fresing_render.pccheck import runner
out = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "pc_" + os.path.basename(root))
os.makedirs(out, exist_ok=True)
for k in range(n):
    r = runner.run("full", out, open_report=False)
    for x in r.results:
        print(f"RESULT {os.path.basename(root)} {k} {x.id} {x.status} {round(x.seconds, 1) if hasattr(x, 'seconds') else ''} | "
              f"{(x.reason or x.note or '')[-160:]}", flush=True)
