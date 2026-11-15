"""0141: the one frame left (ROUND_SCALE=1: the cable part's scale rounded -> nothing left). Build with frame 1 shown and with frame f shown (touch-down kept), compare the sea
solver's own numbers and the places read, frame by frame."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, addon_utils, fresing_render
import numpy as np
path, f, name = sys.argv[1], int(sys.argv[2]), sys.argv[3]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import animation, paths, paths_sea, joints
_sc0 = paths._scale
if os.environ.get("ROUND_SCALE"):
    paths._scale = lambda m: float(round(_sc0(m), 5))
real_changed = paths_sea.water_changed
paths_sea.water_changed = lambda scene: paths_sea.sync_bed(scene)
got = {}
for shown in (1, f):
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = sc.fresing
    sc.frame_set(shown)
    animation.bake(sc, s.animations[s.anim_baked])
    it = paths.find(sc, name)
    sea = {k: np.array(v) for k, v in paths_sea._STATE["sea"][paths._k(sc, it)].items()}
    slots = paths._inputs_of(it)[1]
    rel, first = paths._stored_places(sc, it, slots)
    sh = paths._shapes(sc, it)
    frames, per, _ = paths._layout_of(sh)
    co = np.empty(len(sh.data.vertices) * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    got[shown] = (sea, rel, [sl.name for sl in slots], co.reshape(frames, per, 3).astype(float), first,
                  {j.name: float(joints.get_value(j)) for j in s.joints})
a, b = got[1], got[f]
first = a[4]
print("slots:", len(a[2]))
d = np.abs(a[1] - b[1]).max(axis=(2, 3))            # (F, K)
print("places read: max diff", d.max(), "at frame", first + int(d.max(axis=1).argmax()), "slot", a[2][int(d.max(axis=0).argmax())])
for k in np.argsort(-d.max(axis=0))[:6]:
    print(f"   slot {a[2][k]}: max {d[:, k].max():.3e} at frame {first + int(d[:, k].argmax())}, frames > 1e-7: {int((d[:, k] > 1e-7).sum())}")
for key in a[0]:
    x, y = a[0][key], b[0][key]
    if x.shape != y.shape:
        print("sea", key, "shape", x.shape, y.shape); continue
    dd = np.abs(x.astype(float) - y.astype(float))
    dd = dd.reshape(len(dd), -1).max(axis=1) if dd.ndim > 1 else dd
    bad = np.flatnonzero(dd > 1e-6)
    if len(bad):
        print(f"sea[{key}]: {len(bad)} frames differ > 1e-6, max {dd.max():.5f} at frame {first + int(dd.argmax())}, first at {first + int(bad[0])}, last {first + int(bad[-1])}")
k = 2552 - first
for key in ("hang", "kind", "psi", "pay", "suspended", "laid", "length", "a", "h", "excess"):
    if key in a[0]:
        print(f"   {key}: frames 2550..2554  shown 1: {np.round(a[0][key][k - 2:k + 3], 5).tolist()}  shown {f}: {np.round(b[0][key][k - 2:k + 3], 5).tolist()}")
dsh = np.abs(a[3] - b[3]).max(axis=(1, 2))
print("shapes: frames > 1 mm:", (first + np.flatnonzero(dsh > 1e-3)).tolist()[:20], " > 1e-5:", int((dsh > 1e-5).sum()), " max", dsh.max())
for n, v in a[5].items():
    if abs(v - b[5][n]) > 1e-9:
        print("JOINT at frame 1 after Build", n, v, b[5][n])
