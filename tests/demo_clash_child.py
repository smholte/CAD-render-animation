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

import numpy as np

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
        """The app's check on a window of moments, made to judge each moment as the check of the whole animation does.

        ``start``: the start overlap of each pair is read at the animation's first frame. ``Check._start`` measures a
        pair at ``self.mats[0]``, the window's first moment; here that moment is swapped for the animation's first
        frame while it measures (and only then).

        ``whole`` (optional, ``hold_whole``): which parts turn in place and are held still, and which pairs with a
        turning part that is not round are checked once per stretch of its turn (``Check._hold_still``,
        ``Check._still_pairs``, task 0092), decided once over the whole animation as the whole check does, and given
        to each window as its slice. A window alone sees only part of a turn and finds fewer such pairs: still right
        (they are checked at every moment, a stricter test), but three times slower (task 0108: a spoked sheave
        against the rope in its groove, the carousel's rim fence against the deck)."""

        start = None                                   # (P, 4, 4), time
        whole = None                                   # dict from hold_whole()

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

        def _hold_still(self, groups):
            w = self.whole
            if w is None:
                return super()._hold_still(groups)
            index = {t: k for k, t in enumerate(w["times"])}
            idx = [index[t] for t in self.times]
            assert idx == list(range(idx[0], idx[0] + len(idx))), "a window is a run of the whole check's moments"
            ws, n = idx[0], len(idx)
            self._ws = ws
            H = w["mats"]
            self.mats[:] = H[ws:ws + n]
            self.round_memo, self.band_memo = dict(w["round_memo"]), dict(w["band_memo"])
            self.unround = []
            for p, a, b, rep, x, c, u in w["unround"]:
                a2, b2 = max(a, ws) - ws, min(b, ws + n) - ws
                if b2 <= a2:
                    continue
                # x, c, u are given in the carrier's place at the whole animation's start; here at the window's
                m = np.eye(4) if rep is None else H[ws, rep] @ np.linalg.inv(H[0, rep])
                self.unround.append((p, a2, b2, rep, m @ x, m[:3, :3] @ c + m[:3, 3], m[:3, :3] @ u))
            return w["held"]

        def _still_pairs(self):
            """The whole check's pairs that are checked once per stretch of a turn (``Check._still_pairs``), its moment
            numbers moved to this window's (a stretch that began before the window: not at the window's first moment
            either, as in the whole check)."""
            w = self.whole
            if w is None:
                return super()._still_pairs()
            ws = self._ws
            self.windows = {k: [(a - ws, b - ws) for a, b in v] for k, v in w["windows"].items()}
            return sum(len(v) for v in self.windows.values())
    return GlobalStart


def hold_whole(clash, cls, scene) -> dict:
    """Read the whole animation and decide, as the whole check does, which parts are held still (their matrices)."""
    from fresing_render.core import clash as core
    full = clash.Check.__new__(cls)
    clash.Check.__init__(full, scene)
    full._setup()
    for _p in full._read():
        pass
    groups = core.rigid_groups(core.deltas(full.mats))
    full.orig = groups
    held = clash.Check._hold_still(full, groups)
    clash.Check._still_pairs(full)
    return {"times": list(full.times), "mats": full.mats, "held": held, "unround": list(full.unround),
            "windows": dict(full.windows),
            "round_memo": full.round_memo, "band_memo": full.band_memo, "names": list(full.names)}


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
        t0 = time.perf_counter()
        GlobalStart.whole = hold_whole(clash, GlobalStart, sc)
        names = GlobalStart.whole["names"]
        GlobalStart.start = (GlobalStart.whole["mats"][0].copy(), GlobalStart.whole["times"][0])
        result["hold_s"] = time.perf_counter() - t0
        print(f"whole animation read, {GlobalStart.whole['held']} parts held still, in {result['hold_s']:.0f} s",
              flush=True)
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
