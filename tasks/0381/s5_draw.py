"""0381: the 3D view's drawing (real Blender under xvfb, software OpenGL, NO app) – what an object costs to draw.
xvfb-run -a -s "-screen 0 1280x720x24" blender -p 0 0 1280 720 --factory-startup <file.blend> --python s5_draw.py -- out.json
Solid view of the whole model; (a) the view redrawn 10 x, nothing changed; (b) 20 drag steps: the crane's slew value
changed (as joints.set_value writes it) + the view redrawn. Numbers are CPU + llvmpipe: compare variants, not PCs."""
import bpy, json, math, sys, time
out = sys.argv[sys.argv.index("--") + 1]

def area3d():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == "VIEW_3D":
                return w, a, [r for r in a.regions if r.type == "WINDOW"][0]

def run():
    w, a, r = area3d()
    sp = a.spaces.active
    sp.shading.type = "SOLID"
    sp.overlay.show_overlays = False
    with bpy.context.temp_override(window=w, area=a, region=r):
        bpy.ops.view3d.view_all()
    res = {"objects": len(bpy.data.objects)}
    with bpy.context.temp_override(window=w, area=a, region=r):
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=3)       # warm up: batches made
        t0 = time.perf_counter(); bpy.ops.wm.redraw_timer(type="DRAW", iterations=10)
        res["redraw_ms"] = round((time.perf_counter() - t0) * 100, 1)
    mo = next((o for o in bpy.data.objects if ": Slew" in o.name and "fr_value" in o.keys()), None)
    res["mover"] = mo.name if mo else None
    if mo:
        t = []
        for k in range(20):
            t0 = time.perf_counter()
            mo["fr_value"] = math.radians(3 * (k + 1)); mo.update_tag(refresh={"OBJECT", "DATA"})
            with bpy.context.temp_override(window=w, area=a, region=r):
                bpy.ops.wm.redraw_timer(type="DRAW", iterations=1)
            t.append((time.perf_counter() - t0) * 1000)
        t.sort(); res["drag_and_draw_ms"] = round(sum(t[2:-2]) / 16, 1)
    json.dump(res, open(out, "w"))
    print("0381", res, flush=True)
    bpy.ops.wm.quit_blender()

bpy.app.timers.register(run, first_interval=3.0)
