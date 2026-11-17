"""Task 0192 (bug hunt 6 row 1): a model update of the made demo with its OWN file, then Build, gives exactly the
Build the project was saved with – every cable's length, contacts and ends, every shape, every key, every lay label.

Before (small demo, 0.2.141 … 0.2.146): the A&R wire 2.82 -> 74.92 m ("cannot go round HANDLER TOP PULLEY … 301°
round": its hand-set CAD-pose wrap was worked out again), the tipping wires' removed bend came back ("no longer touches
'Bend 1'") and their start left the winch lead (made a cable later, so left out of the touch search), the second end
up to 2.8 m off, the lay cable's bends hung on another carrier (the carousel's arm follower came after its spool was
set up: a reading put them on the arm), lay label 32.3 instead of 32.0 m, rollers keyed to stand still. Now an update
that brings back the same model keeps every cable and spool as it was (``paths.same_model``).

The saved project IS a Build (checked in task 0192: a fresh Build of it gives every key and shape bit for bit), so the
saved state is the reference: one update and one Build here. The demo project is made once per run and shared by the
demo files (``tests/demo_made.py``, task 0145).
"""

import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import _keys, _scene, made  # noqa: E402,F401
from fresing_render.blender import animation, build, callouts, demo, joints, paths, paths_sea  # noqa: E402
from fresing_render.demo_model import layout  # noqa: E402

MM = 0.001
DEG = np.radians(0.01)
SHAPE = 0.002            # m: the drawn points (11 M on the second end; task 0192 measured 1.015 mm at one of them – the
#                          sea cable's solve, not a route: lengths, keys and lay data hold to 1 mm / 0.01°)


def _ref(sc, name: str) -> str:
    ob = sc.objects.get(name)
    return (ob.get(build.PROP_UID) or name) if ob is not None else name


def _of(ob) -> str:
    return "" if ob is None else (ob.get(build.PROP_UID) or ob.name)


def _state(sc) -> dict:
    out = {"cables": {}, "shapes": {}, "keys": {}, "labels": {}, "numbers": {}}
    for it in sc.fresing.cables:
        out["cables"][it.name] = {
            "length": float(it.length),
            "contacts": [(c.name, c.kind, int(c.side), round(float(c.wrap_cad), 4), _of(c.part)) for c in it.contacts],
            "ends": [(getattr(it, k + "_kind"), _of(getattr(it, k + "_part")), bool(getattr(it, k + "_free_end")))
                     for k in ("a", "b")]}
        sh = paths._shapes(sc, it)
        if sh is not None:
            co = np.empty(len(sh.data.vertices) * 3, np.float32)
            sh.data.vertices.foreach_get("co", co)
            out["shapes"][it.name] = co.reshape(-1, 3)
    for (name, path, index), pts in _keys(sc).items():
        rot = "rotation" in path
        if path == '["fr_value"]':
            j = next((j for j in sc.fresing.joints if j.motion is not None and j.motion.name == name), None)
            rot = j is not None and j.kind == "ROTATE"
        out["keys"][(_ref(sc, name), path, index)] = (pts, rot)
    live = [c for c in sc.fresing.callouts if "{" in c.text]
    sea = [it.name for it in sc.fresing.cables if it.b_kind == "SEA" and it.enabled]
    for f in np.linspace(sc.frame_start, sc.frame_end, 12).round().astype(int):
        sc.frame_set(int(f))
        for c in live:
            out["labels"][(c.name, int(f))] = callouts.label_text(sc, c)
        for name in sea:
            n = paths_sea.numbers(sc, paths.find(sc, name))
            out["numbers"][(name, int(f))] = {k: float(v) for k, v in n.items() if isinstance(v, (int, float))}
    sc.frame_set(sc.frame_start)
    return out


def test_an_update_to_the_same_file_then_build_is_the_saved_build(made):
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    assert sc.fresing.anim_baked == a.name
    want = _state(sc)
    root = next(r for r in build.model_roots(sc)
                if os.path.basename(r.get(build.PROP_SOURCE, "")) == layout.FILES["assembly"])
    t0 = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=root.get(build.PROP_SOURCE), quality="draft",
                                       update_root=root.name) == {"FINISHED"}
    took_update = time.perf_counter() - t0
    sc = _scene()
    t0 = time.perf_counter()
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    took_build = time.perf_counter() - t0
    got = _state(sc)
    print(f"\nmodel update {took_update:.1f} s, Build {took_build:.1f} s")

    bad = []
    for name, w in want["cables"].items():
        g = got["cables"].get(name)
        if g is None:
            bad.append(f"{name}: gone")
            continue
        if abs(g["length"] - w["length"]) > MM:
            bad.append(f"{name}: length {w['length']:.3f} -> {g['length']:.3f} m")
        if [c[:4] for c in g["contacts"]] != [c[:4] for c in w["contacts"]]:
            bad.append(f"{name}: contacts {w['contacts']} -> {g['contacts']}")
        if [(e[0], e[2]) for e in g["ends"]] != [(e[0], e[2]) for e in w["ends"]]:
            bad.append(f"{name}: ends {w['ends']} -> {g['ends']}")
    for name, w in want["shapes"].items():
        g = got["shapes"].get(name)
        if g is None or g.shape != w.shape:
            bad.append(f"{name}: shape {w.shape} -> {None if g is None else g.shape}")
        elif np.abs(g - w).max() > SHAPE:
            d = np.linalg.norm(g - w, axis=1)
            bad.append(f"{name}: shape {d.max():.6f} m off at point {int(d.argmax())} of {len(d)}, "
                       f"{int((d > MM).sum())} points over 1 mm")
    assert set(got["keys"]) == set(want["keys"]), sorted(set(got["keys"]) ^ set(want["keys"]))[:10]
    for k, (w, rot) in want["keys"].items():
        g = got["keys"][k][0]
        if g.shape != w.shape:
            bad.append(f"keys {k}: {len(w)} -> {len(g)}")
        elif np.abs(g[:, 1] - w[:, 1]).max() > (DEG if rot else MM) or np.abs(g[:, 0] - w[:, 0]).max() > 1e-4:
            bad.append(f"keys {k}: {np.abs(g[:, 1] - w[:, 1]).max():.5f} off")
    for k, w in want["labels"].items():
        if got["labels"].get(k) != w:
            bad.append(f"label {k}: {w!r} -> {got['labels'].get(k)!r}")
    for k, w in want["numbers"].items():
        g = got["numbers"].get(k, {})
        for n, v in w.items():
            tol = DEG if n == "angle" else MM if n in ("layback", "depth", "length", "free", "hang") else 1e-3 * abs(v)
            if n not in g or abs(g[n] - v) > max(tol, 1e-9):
                bad.append(f"lay data {k} {n}: {v} -> {g.get(n)}")
    assert not bad, f"{len(bad)} differences:\n" + "\n".join(bad[:30])
    assert joints.find(sc, demo.CABLE) is not None
