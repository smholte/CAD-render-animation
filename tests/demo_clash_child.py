"""Task 0108: one worker of the demo project's clash check (``tests/test_demo_clash.py``), run as its own process.

    python demo_clash_child.py <project.blend> <out.json> <claim folder> <first-last> [<first-last> ...]

Opens the saved demo project, builds its animation (as the test did before), and runs the app's clash check
(``blender/clash.py``) on each window of frames given, with the sea at rest. Each window is checked exactly as the
whole animation is, with one difference made on purpose so that it is **as strict as the whole check**: how deep two
parts may be in each other is measured at the *animation's* first frame, not at the window's (``GlobalStart``). Writes
per window: the moments it checked, its rows and its stats. Several of these processes get the same windows and take
them one at a time in order: a window is taken by making the file ``<claim folder>/<first-last>`` (only one process can
make it), so a process that had cheap windows takes the next one while another still works on a heavy one.

Why windows: the check works the moments out one after the other on one core (task 0108 measured 800 s on a 4-core
web machine, 95 % of it the pairs at each moment); four of these processes share the windows and take a quarter of it.
"""

from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def global_start(scene, names):
    """Every checked part's world matrix at the animation's first frame (stored by columns, as ``Check._read``)."""
    import numpy as np
    obs = scene.objects
    index = {ob.name: i for i, ob in enumerate(obs)}
    sel = np.array([index[n] for n in names])
    buf = np.empty(len(obs) * 16, dtype=np.float64)
    scene.frame_set(int(scene.frame_start))
    obs.foreach_get("matrix_world", buf)
    return buf.reshape(len(obs), 4, 4)[sel].transpose(0, 2, 1).copy(), float(scene.frame_start)


def make_class(clash):
    class GlobalStart(clash.Check):
        """The app's check with the start overlap of each pair read at the animation's first frame (``start``).

        ``Check._start`` measures a pair at ``self.mats[0]``, the window's first moment; here that moment is swapped
        for the animation's first frame while it measures (and only then: everything else uses the window's own)."""

        start = None                                   # (P, 4, 4), time

        def _start(self, p, q):
            if (p, q) in self.base:
                return self.base[(p, q)]
            m0, t0 = self.start
            keep_m, keep_t = self.mats[0].copy(), self.times[0]
            self.mats[0], self.times[0] = m0, t0
            try:
                return super()._start(p, q)
            finally:
                self.mats[0], self.times[0] = keep_m, keep_t
    return GlobalStart


def main(argv: list[str]) -> int:
    blend, out, claims = argv[0], argv[1], argv[2]
    windows = [tuple(int(x) for x in w.split("-")) for w in argv[3:]]
    import bpy  # noqa: I001 - bpy first: it makes addon_utils importable
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import animation, clash, demo, vessel_motion
    from fresing_render.core import clash as core
    bpy.ops.wm.open_mainfile(filepath=blend)
    sc = bpy.context.scene
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    whole = clash.sample_times(sc)
    GlobalStart = make_class(clash)
    result = {"whole": whole, "windows": []}
    real_times = clash.sample_times
    with vessel_motion.at_rest(sc):
        names = [ob.name for ob in clash.objects(sc)]
        GlobalStart.start = global_start(sc, names)
        for a, b in windows:
            try:
                os.close(os.open(os.path.join(claims, f"{a}-{b}"), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                continue                               # another process has it
            mine = [t for t in whole if a <= t <= b]
            clash.sample_times = lambda _scene, mine=mine: list(mine)
            try:
                t0 = time.perf_counter()
                run = GlobalStart(sc)
                for _p in run.steps():
                    pass
                assert run.names == names, "the parts checked differ from the window's first read"
                result["windows"].append({"window": [a, b], "times": list(run.times), "seconds": time.perf_counter() - t0,
                                          "rows": [core.row_text(r) for r in run.rows],
                                          "stats": {k: v for k, v in run.stats.items() if isinstance(v, (int, float))}})
            finally:
                clash.sample_times = real_times
            print(f"window {a}-{b}: {len(run.rows)} rows in {time.perf_counter() - t0:.0f} s", flush=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    fresing_render.unregister()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
