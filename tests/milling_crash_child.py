"""Child process of tests/test_idprops.py (task 0038): milling reads the bits' path again with another length.

Run with Blender as a Python module:
``python tests/milling_crash_child.py [--unsafe] [--rounds N] [--save FILE] [--open FILE]``.
Sets up the small test mill, reads the path, changes the animation length (so the sample count changes),
reads it again a few times, then cuts at many frames (Manifold booleans) and allocates a lot of memory.
Blender 5.2.3 used to die here ("free(): invalid size", segfault) when the arrays were assigned over the old
ones; ``--unsafe`` puts back that old way of storing, to show the crash. Prints "OK <samples>" at the end.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bpy  # noqa: E402
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, machining  # noqa: E402

MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001


def _unsafe_store(owner, key, values, dtype=np.float64):
    owner[key] = np.asarray(values, dtype=dtype).reshape(-1)          # how 0.2.32 and older stored it


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def anim(sc, length, name):
    """A slot whose moves last ``length`` seconds in all: another length gives another sample count."""
    s = sc.fresing
    a = s.animations.get(name) or s.animations.add()
    a.name, a.tail = name, 0.0
    a.blocks.clear()
    k = length / 3.5
    for j, start, dur, to in (("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start * k, dur * k, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    return animation.bake(sc, a)["frames"]


def set_up(sc):
    """Import the test mill, make its axes and an animation, pick the bit and the stock."""
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    anim(sc, 3.5, "Mill")
    click(ob(sc, "END MILL D10"))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, "STOCK 200x200x40"))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    unsafe = "--unsafe" in sys.argv
    rounds = int(_arg("--rounds", 6))
    if unsafe:
        machining.store_array = _unsafe_store
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    if _arg("--open"):                                    # a project saved before (maybe by an old version)
        bpy.ops.wm.open_mainfile(filepath=_arg("--open"))
        sc = bpy.context.scene
        counts = [len(machining.settings(sc).bits[0]["fr_t"])]
    else:
        sc = bpy.context.scene
        set_up(sc)
        counts = [machining.sample(sc)]
    rng = np.random.default_rng(38)
    for n in range(rounds):
        frames = anim(sc, float(rng.uniform(1.0, 8.0)), "Mill")      # other length -> other sample count
        counts.append(machining.sample(sc))
        for f in range(1, frames + 1, max(1, frames // 12)):          # cut: Manifold booleans, new meshes
            sc.frame_set(f)
        junk = [np.ones(int(rng.integers(1_000, 400_000))) for _ in range(40)]
        del junk
    m = machining.settings(sc)
    item = m.bits[0]
    t = np.array(item["fr_t"])
    assert len(t) * 3 == len(np.array(item["fr_o"])) == len(np.array(item["fr_d"])), "path arrays disagree"
    assert len(t) == counts[-1], (len(t), counts[-1])
    assert len(np.array(m["fr_wp_m"])) % 16 == 0
    if rounds:
        assert len(set(counts)) > 1, f"the sample count never changed: {counts}"
        sc.frame_set(frames)                                          # the end of the slot: the stock is cut
        assert len(machining.workpiece(sc).data.vertices) > 8, "the stock was not cut"
    if _arg("--save"):
        bpy.ops.wm.save_as_mainfile(filepath=_arg("--save"))
    print("OK", counts, flush=True)


if __name__ == "__main__":
    main()
