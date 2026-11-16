"""The demo project's clash check (task 0077/0097), moved here from ``test_demo_project.py`` by task 0108.

The check of the whole demo animation (1,853 frames, 1,226 parts) took 13 minutes on one core, the longest test of the
run. It now runs as windows of frames in four processes at once (``tests/demo_clash_child.py``), each a quarter of it.
**It is as strict as before:**

- every frame and every step between two frames is checked: the windows overlap by one frame, and the test proves that
  together they hold every moment of the whole check (``test_no_clash_in_the_animation``; since task 0145 the windows
  are shared by this file and ``test_demo_clash_b.py``, two GitHub jobs: each proves that each of its windows held
  every moment from its first frame to its last, this one that the windows follow on each other from the first frame
  to the last; both use the demo made once, ``tests/demo_made.py``);
- how deep two parts may be in each other is measured at the animation's first frame, as in the whole check, not at a
  window's first frame (``GlobalStart`` in the child); ``test_windows_find_what_the_whole_check_finds`` shows on the
  clash test model that the windows find exactly the whole check's rows, and that a window measured from its own first
  frame would miss one;
- which parts turn in place (held still) and which pairs with a turning part are checked once per stretch of its turn
  (task 0092) is decided once over the whole animation, as the whole check decides it, and each window gets its slice;
- parts that do not move against each other within a window are one body there and not compared: their depth is the
  same all through the window, and its first frame was the last frame of the window before (checked there).

Measured on a 4-core web machine (task 0108): the whole check 800 s on one core; the windows 689 s of work in all, with
exactly the whole check's 38,835 moments between frames, 172 s per worker.
"""

import json
import math
import os
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
import demo_made  # noqa: E402  (the made demo project, shared: tests/demo_made.py)
from fresing_render.blender import demo  # noqa: E402

VERSION = demo_made.VERSION
WORKERS = 4                       # processes at once (GitHub's runners and the web machines have 4 cores)
WINDOWS = 36                      # windows of frames, taken one at a time by whichever worker is free (task 0108: the
                                  # cost per frame differs 100-fold along the animation: 6 s to 820 s per 155 frames)


def windows(f0: int, f1: int, n: int) -> list:
    """n windows of frames f0 … f1 that overlap by one frame: every step k → k+1 lies inside one of them."""
    cuts = sorted({f0, f1} | {f0 + round((f1 - f0) * i / n) for i in range(1, n)})
    return [(a, b) for a, b in zip(cuts, cuts[1:])]


def test_windows_cover_every_step():
    w = windows(1, 1853, 12)
    assert w[0][0] == 1 and w[-1][1] == 1853 and len(w) == 12 and len(windows(1, 1853, 36)) == 36
    assert all(a[1] == b[0] for a, b in zip(w, w[1:]))
    assert windows(1, 3, 12) == [(1, 2), (2, 3)]


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    """The demo project made once for every demo test file (``tests/demo_made.py``, task 0145), opened here."""
    info = demo_made.read(demo_made.ensure(str(tmp_path_factory.getbasetemp())))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    bpy.ops.wm.open_mainfile(filepath=info["out"]["path"])
    return info


HALVES = 2                        # task 0145: the windows are shared by two test files (two GitHub jobs at once): the
                                  # even ones here, the odd ones in test_demo_clash_b.py


def check_part(made, tmp_path, part: int) -> None:
    """The clash check over the whole animation, windows ``part``, ``part + HALVES`` …: 0 rows (a clash is a fault in
    the model or the set-up). The rollers, wheels and drums are checked too since task 0097: they turn about their own
    axis, so the clash check holds them still on their carrier (task 0092). That they really turn about their own axis
    is checked here too (part 0).

    Task 0145: as strict as the whole check in one file. Each part proves that each of its windows held every moment of
    the whole check from its first frame to its last (so every step between two moments inside it); part 0 proves that
    the windows of all parts follow on each other from the animation's first frame to its last. The workers start on
    the saved, built project; this process reads the whole animation for them first (``hold_whole``) and builds it again
    while they work: the keys must give the saved project's fingerprint (the workers' too)."""
    from mathutils import Vector

    from fresing_render.blender import animation, build, clash, joints
    sc = bpy.context.scene
    # the workers first (each opens the saved, built project and waits for the reading below), then the build here
    f0, f1 = int(sc.frame_start), int(sc.frame_end)
    win = windows(f0, f1, WINDOWS)
    mine = win[part::HALVES]
    procs = []
    claims = tmp_path / "claims"
    claims.mkdir()
    whole_file = tmp_path / "whole.pickle"
    for w in range(WORKERS):
        out = str(tmp_path / f"worker{w}.json")
        cmd = [sys.executable, os.path.join(HERE, "demo_clash_child.py"), made["out"]["path"], out, str(claims),
               str(whole_file), *[f"{a}-{b}" for a, b in mine]]
        log = open(tmp_path / f"worker{w}.log", "w", encoding="utf-8")
        procs.append((subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT), out, log, w))
    try:
        # the whole animation read once (the saved build), and which parts turn in place decided as the whole check
        # does: for the workers (task 0145: before this process builds it again, so they need not wait for that)
        import pickle

        import demo_clash_child as child
        from fresing_render.blender import vessel_motion
        saved = clash.build_signature(sc)
        whole = clash.sample_times(sc)
        with vessel_motion.at_rest(sc):
            w_all = child.hold_whole(clash, child.make_class(clash), sc)
        with open(str(whole_file) + ".part", "wb") as fh:
            pickle.dump(w_all, fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(str(whole_file) + ".part", whole_file)
        del w_all
        animation.bake(sc, sc.fresing.animations[demo.ANIM])         # built again: the saved project's keys
        assert (int(sc.frame_start), int(sc.frame_end)) == (f0, f1)
        assert clash.build_signature(sc) == saved, "built again, the keys differ from the saved project's"
        assert clash.sample_times(sc) == whole
        if part == 0:
            leave = demo.turning_in_place(sc)
            assert 250 < len(leave) < 600
            for j in sc.fresing.joints:                                    # round about their own axis
                top = joints.driver_of(sc, j)
                if j.kind != "ROTATE" or top is None or top.name not in (demo.CABLE, demo.TRAVEL):
                    continue
                o, dvec = joints.axis_world(j)
                for m in joints.members(j):
                    if m.get(build.PROP_KIND) != "part":
                        continue
                    c = sum((m.matrix_world @ Vector(v) for v in m.bound_box), Vector()) / 8.0
                    off = c - o
                    off -= dvec * off.dot(dvec)
                    assert off.length < 0.01, (j.name, off.length)
            # the windows of all parts follow on each other from the first frame to the last
            assert sorted(w for k in range(HALVES) for w in win[k::HALVES]) == win
            assert win[0][0] == f0 and win[-1][1] == f1 and all(a[1] == b[0] for a, b in zip(win, win[1:]))
        # (the cable is on its path since task 0078: the clash check leaves a drawn cable out by itself, as it does hoses)
        # the sea at rest (task 0091, in the child): the vessel's sway moves the whole model as one, so it changes nothing
        # between two parts; but where the sway turns very slowly while a part slides (a lift, the cylinder rods) the
        # check's step between two frames came out up to centimetres off (screw_between reads a tiny turn from float32
        # matrices), and the rows it gave (1.2 mm, 0.8 mm) moved with the sea's phase. Open point for the clash lane (0092).
        results = []
        for p, out, log, w in procs:
            code = p.wait(timeout=3600)
            log.flush()
            text = (tmp_path / f"worker{w}.log").read_text(encoding="utf-8", errors="replace")
            assert code == 0, f"worker {w} stopped ({code}):\n{text[-4000:]}"
            with open(out, encoding="utf-8") as fh:
                results.append(json.load(fh))
        done = [x for r in results for x in r["windows"]]
        assert all(r["whole"] == whole for r in results)          # each worker checks the animation built here
        assert all(r["signature"] == saved for r in results)
        assert sorted(tuple(x["window"]) for x in done) == mine
        # every moment of the whole check inside a window, from its first frame to its last, is checked in it – and so
        # every step between two of them (with part 0's proof above: every moment and step of the whole animation)
        for x in done:
            a, b = x["window"]
            assert x["times"] == [t for t in whole if a <= t <= b], x["window"]
        secs = [x["seconds"] for x in done]
        print(f"\ndemo clash check, part {part + 1} of {HALVES}: {len(done)} windows, "
              f"{len({t for x in done for t in x['times']})} of {len(whole)} moments, {sum(secs):.0f} s of work, "
              f"longest window {max(secs):.0f} s, {sum(x['stats']['between'] for x in done)} moments between frames; "
              f"workers waited {max(r.get('wait_s', 0.0) for r in results):.0f} s; "
              f"per worker {[round(sum(x['seconds'] for x in r['windows'])) for r in results]} s")
        assert min(x["stats"]["parts"] for x in done) > 700
        rows = [r for x in done for r in x["rows"]]
        assert not rows, rows[:5]

    finally:
        for p, _out, log, _w in procs:              # a failed check here: no worker left running
            if p.poll() is None:
                p.kill()
            log.close()


def test_no_clash_in_the_animation(made, tmp_path):
    """The clash check over the whole animation: 0 rows – its first part here, the second in test_demo_clash_b.py."""
    check_part(made, tmp_path, 0)


def test_windows_find_what_the_whole_check_finds(tmp_path):
    """The proof on a small model (the clash test model, as ``tests/test_clash.py`` sets it up): the arms come down
    onto each other (6.0 mm deep from frame 49 to 51), and an arm swung through a post within one frame (found only
    between two frames). Checked in windows as the demo is, the rows are the whole check's (pairs, frames, depth). A
    window measured from its own first frame would miss the arms (already 6 mm in each other there): the child
    measures from the animation's first frame."""
    import demo_clash_child as child

    from fresing_render.blender import animation, build, clash, joints, tour
    from fresing_render.core import clash as core
    from mathutils import Vector

    def load():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        addon_utils.enable("cycles", default_set=True)
        sc = bpy.context.scene
        sc.fresing.out_folder = str(tmp_path)
        assert bpy.ops.fresing.import_step(filepath=os.path.join(HERE, "data", "test_clash.step"),
                                           quality="draft") == {"FINISHED"}
        return sc

    def key(rows):
        return sorted((frozenset((r.a, r.b)), r.frame_from, r.frame_to, round(r.depth * 1000, 1))
                      for r in rows if r.kind == "CLASH")

    def windowed(sc, cls, lo, hi):
        times = clash.sample_times(sc)
        real = clash.sample_times
        clash.sample_times = lambda _s: [t for t in times if lo <= t <= hi]
        try:
            return _run(cls(sc))
        finally:
            clash.sample_times = real

    def base(run):
        return {(run.names[p], run.names[q]): v for (p, q), v in run.base.items()}

    def compare(sc, expect, ns):
        full = clash.check(sc, store=False)
        whole = key(full.rows)
        assert expect <= {k[0] for k in whole}, whole
        cls = child.make_class(clash)
        cls.whole = child.hold_whole(clash, cls, sc)
        cls.start = (cls.whole["mats"][0].copy(), cls.whole["times"][0])
        assert np.allclose(cls.start[0], child.global_start(sc, cls.whole["names"])[0], atol=1e-9)
        f0, f1 = int(sc.frame_start), int(sc.frame_end)
        for n in ns:
            runs = [windowed(sc, cls, lo, hi) for lo, hi in windows(f0, f1, n)]
            for run in runs:                                    # the start overlaps are the whole check's
                for pair, v in base(run).items():
                    assert v == base(full).get(pair, v), (n, pair, v, base(full).get(pair))
            got = key([r for run in runs for r in run.rows])
            assert {k[0] for k in got} == {k[0] for k in whole}, (n, got, whole)
            for k in whole:                                     # each row of the whole check: same depth, its frames
                mine = [g for g in got if g[0] == k[0]]
                assert max(g[3] for g in mine) == pytest.approx(k[3], abs=0.15), (n, k, mine)
                assert min(g[1] for g in mine) == k[1] and max(g[2] for g in mine) == k[2], (n, k, mine)
        return cls

    arms_ = frozenset(("ARM.A", "ARM.B"))
    sc = load()
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Arms meet", 0.0, "25"
    tour.clash_arms(sc, a)
    animation.bake(sc, a)
    cls = compare(sc, {arms_}, (3, 7))
    # measured from a window's own first frame (the plain check), the arms would be allowed 2.9 mm more: the child
    # measures them from the animation's first frame, where they are apart
    plain, strict = base(windowed(sc, clash.Check, 50, 51)), base(windowed(sc, cls, 50, 51))
    assert plain[("ARM.A", "ARM.B")][0] > 0.002 and strict[("ARM.A", "ARM.B")][0] == 0.0, (plain, strict)

    sc = load()
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Fast swing", 0.2, "25"
    post = next(o for o in sc.objects if o.get(build.PROP_NAME) == "ARM.A.ASM")
    joints.create(sc, "ROTATE", [post], Vector((0.0, 0.044, 0.0)), Vector((0, 0, 1)), name="Arm A")
    tour._joint_step(a, "Arm A", 0.0, 0.04, math.radians(90))      # 90° within one frame
    animation.bake(sc, a)
    compare(sc, {frozenset(("ARM.A", "POST"))}, (2, 3))
    assert core.DEPTH > 0


def _run(run):
    for _p in run.steps():
        pass
    return run
