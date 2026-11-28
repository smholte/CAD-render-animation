"""0381: measure one project (Blender as a Python module, the app registered, a fresh process per project).
python s4_measure.py <in.blend> <out.json> [--render] [--playback]"""
import json, math, os, sys, time, resource
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
import bpy, addon_utils  # noqa
import fresing_render
from mathutils import Vector
src, dst = sys.argv[1:3]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import build, joints, animation
from fresing_render.pccheck import stress

def rss_mb():
    with open("/proc/self/status") as fh:
        for ln in fh:
            if ln.startswith("VmRSS"):
                return int(ln.split()[1]) / 1024
r = {"file": os.path.basename(src), "file_mb": round(os.path.getsize(src) / 1e6, 2)}
m0 = rss_mb()
t0 = time.perf_counter()
bpy.ops.wm.open_mainfile(filepath=src)
vl = bpy.context.view_layer
vl.update()
r["open_s"] = round(time.perf_counter() - t0, 2)
scene = bpy.context.scene
r["objects"] = len(bpy.data.objects)
dg = bpy.context.evaluated_depsgraph_get()
r["drawn_instances"] = sum(1 for _ in dg.object_instances)
r["ids_in_depsgraph"] = len(dg.ids)
r["rss_after_open_mb"] = round(rss_mb() - m0)

def step_ms(fn, n=40):
    t = []
    for k in range(n):
        t0 = time.perf_counter(); fn(k); vl.update(); t.append((time.perf_counter() - t0) * 1000)
    t.sort()
    return round(sum(t[3:-3]) / (len(t) - 6), 2)

j = stress._joint(scene, ": Slew")
r["drag_ms"] = step_ms(lambda k: joints.set_value(j, math.radians(3 * (k + 1))))
joints.set_value(j, 0.0); vl.update()
lone = bpy.data.objects.new("lone", None); scene.collection.objects.link(lone); vl.update()
def mv(k):
    lone.location.z = 0.01 * k
    lone.update_tag(refresh={"OBJECT"})
r["lone_empty_ms"] = step_ms(mv)
bpy.data.objects.remove(lone); vl.update()

# pick: a ray from above down onto the middle of the deck, and from the side
RAYS = os.path.join(os.path.dirname(os.path.abspath(src)), "rays.json")   # the same rays for every variant
if os.path.isfile(RAYS):
    c = Vector(json.load(open(RAYS)))
else:
    c = Vector((0, 0, 0)); n = 0
    for o in build.iter_parts(scene):
        c += o.matrix_world.translation; n += 1
    c /= max(n, 1)
    json.dump(list(c), open(RAYS, "w"))
picks = []
for org, d in ((c + Vector((0.3, 0.2, 40)), Vector((0, 0, -1))), (c + Vector((60, 0.4, 2)), Vector((-1, 0, 0)))):
    hit, loc, nrm, idx, ob, M = scene.ray_cast(dg, org, d)
    picks.append({"hit": hit, "object": ob.name if ob else None, "face": idx,
                  "same_as_instance_matrix": bool(ob is not None and (ob.matrix_world - M).to_scale().length < 1e-6
                                                  and (ob.matrix_world.translation - M.translation).length < 1e-6)})
r["picks"] = picks

if "--playback" in sys.argv:
    try:
        a = stress._animation(scene, 10.0)
        t0 = time.perf_counter(); frames = animation.bake(scene, a)["frames"]; r["build_s"] = round(time.perf_counter() - t0, 2)
        t0 = time.perf_counter()
        for f in range(1, 101):
            scene.frame_set(f)
        r["playback_ms_frame"] = round((time.perf_counter() - t0) * 10, 2)
        animation.clear_keys(scene); scene.frame_set(1)
    except Exception as e:  # noqa
        r["playback_error"] = repr(e)[:200]

if "--render" in sys.argv:
    cam = bpy.data.objects.get("FR0381 cam") or stress._camera(scene)   # made in the base project, kept
    scene.camera = cam
    scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 320, 180, 100
    scene.render.filepath = os.path.abspath(os.path.splitext(dst)[0] + ".png")
    m1 = rss_mb()
    t0 = time.perf_counter(); bpy.ops.render.render(write_still=True); r["render_s"] = round(time.perf_counter() - t0, 2)
    r["render_rss_gain_mb"] = round(rss_mb() - m1)

tmp = os.path.splitext(dst)[0] + ".resaved.blend"
t0 = time.perf_counter(); bpy.ops.wm.save_as_mainfile(filepath=tmp, copy=True); r["save_s"] = round(time.perf_counter() - t0, 2)
r["save_mb"] = round(os.path.getsize(tmp) / 1e6, 2); os.remove(tmp)
r["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
json.dump(r, open(dst, "w"), indent=1)
print(json.dumps(r))
