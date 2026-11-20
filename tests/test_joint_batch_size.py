"""Task 0229, stand-in for the demo vessel's size (study 0226): 400 joints made in ONE ``joints._batch``.

A made-up model (a root and 400 small box parts in a 20 x 20 grid, built here as the importer lays them out: parts
are children of one model root) gets 400 joints in one batch: 300 on single parts (rotate about Z, slide along X,
alternating) and 100 stacked on top of the first 100 of those (a slide on a rotate, a rotate on a slide). Proves: the
scene is updated a small fixed number of times however many joints (none inside the batch), every joint exists and
moves what it should, a sample of 20 parts (stacked ones included) lands where the maths puts it, and the batch takes
less than a generous limit (the time is printed).
"""

import math
import time

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, joints  # noqa: E402

N = 400
GRID = 20
PITCH = 0.5
HALF = 0.1
LIMIT_S = 60.0                         # generous: measured time is printed
TOL = 1e-4
Z, X = Vector((0, 0, 1)), Vector((1, 0, 0))


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _box_mesh(name):
    v = [(x, y, z) for x in (-HALF, HALF) for y in (-HALF, HALF) for z in (-HALF, HALF)]
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], t)
    me.update()
    return me


def model():
    """The root and 400 parts; returns (scene, [parts])."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = bpy.data.objects.new("MODEL", None)
    sc.collection.objects.link(root)
    root[build.PROP_KIND], root[build.PROP_NAME], root[build.PROP_UID] = "assembly", "MODEL", "MODEL"
    root[build.PROP_ROOT] = True
    root[build.PROP_UID_SCOPE] = ""
    build.set_mat(root, build.PROP_CAD_BASIS, root.matrix_basis)
    build.set_mat(root, build.PROP_REST_BASIS, root.matrix_basis)
    parts = []
    for n in range(N):
        name = f"PART {n:03d}"
        ob = bpy.data.objects.new(name, _box_mesh(name))
        sc.collection.objects.link(ob)
        ob.parent = root
        ob.location = ((n % GRID) * PITCH, (n // GRID) * PITCH, 0.0)
        ob[build.PROP_KIND], ob[build.PROP_NAME], ob[build.PROP_UID] = "part", name, name
        build.set_mat(ob, build.PROP_CAD_BASIS, ob.matrix_basis)
        build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
        parts.append(ob)
    bpy.context.view_layer.update()
    return sc, parts


def update():
    bpy.context.view_layer.update()


def make_all(sc, parts):
    """300 single joints (even parts rotate about their own Z, odd parts slide along X), then 100 stacked on parts
    0..99: a slide on each rotate, a rotate (about the part's own Z, off to the side) on each slide."""
    for n, p in enumerate(parts[:300]):
        at = p.matrix_world.translation
        if n % 2 == 0:
            joints.create(sc, "ROTATE", [p], at, Z, name=f"Turn {n:03d}")
        else:
            joints.create(sc, "SLIDE", [p], at, X, name=f"Slide {n:03d}")
    for n, p in enumerate(parts[:100]):
        at = p.matrix_world.translation + Vector((0.05, 0.0, 0.0))
        if n % 2 == 0:
            joints.create(sc, "SLIDE", [p], at, X, name=f"Top slide {n:03d}")      # rides on Turn n
        else:
            joints.create(sc, "ROTATE", [p], at, Z, name=f"Top turn {n:03d}")      # rides on Slide n


def test_400_joints_in_one_batch(monkeypatch):
    sc, parts = model()
    calls = []
    real = joints._update
    monkeypatch.setattr(joints, "_update", lambda scene: (calls.append(1), real(scene)))

    t0 = time.time()
    with joints._batch(sc):
        before = len(calls)
        make_all(sc, parts)
        inside = len(calls) - before
    dt = time.time() - t0
    update()
    print(f"\n{N} joints in one batch: {dt:.1f} s, {len(calls)} scene updates ({inside} inside the batch)")

    assert inside == 0, f"{inside} scene updates inside the batch"
    assert len(calls) <= 2, len(calls)
    assert dt < LIMIT_S, dt
    assert len(sc.fresing.joints) == N

    # every joint exists and the stacked ones ride on the joint below
    for n in range(100):
        top = joints.find(sc, f"{'Top slide' if n % 2 == 0 else 'Top turn'} {n:03d}")
        below = joints.rides_on(sc, top)
        assert below is not None and below.name == f"{'Turn' if n % 2 == 0 else 'Slide'} {n:03d}", (n, below)
    for n in (100, 101, 299):
        assert joints.rides_on(sc, joints.find(sc, f"{'Turn' if n % 2 == 0 else 'Slide'} {n:03d}")) is None

    # values: a sample of 20 parts, stacked ones included
    sample = [0, 1, 2, 3, 50, 51, 98, 99, 100, 101, 150, 151, 200, 201, 250, 251, 298, 299]
    rest = {n: parts[n].matrix_world.copy() for n in sample}
    ang, dist = math.radians(30), 0.2
    for n in sample:
        if n % 2 == 0:
            joints.set_value(joints.find(sc, f"Turn {n:03d}"), ang)
        else:
            joints.set_value(joints.find(sc, f"Slide {n:03d}"), dist)
    for n in (0, 1, 2, 3):                                         # the stacked ones too
        if n % 2 == 0:
            joints.set_value(joints.find(sc, f"Top slide {n:03d}"), dist)
        else:
            joints.set_value(joints.find(sc, f"Top turn {n:03d}"), ang)
    update()
    for n in sample:
        got = parts[n].matrix_world
        pos0 = rest[n].translation
        if n >= 100:
            want = (Matrix.Translation(pos0) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation(-pos0) @ rest[n]
                    if n % 2 == 0 else Matrix.Translation((dist, 0, 0)) @ rest[n])
        elif n % 2 == 0:
            # rotate about the part's own Z, then the slide (on it) along the turned X by `dist`
            turned = Matrix.Translation(pos0) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation(-pos0) @ rest[n]
            up = Vector((math.cos(ang), math.sin(ang), 0)) * dist if n < 4 else Vector((0, 0, 0))
            want = Matrix.Translation(up) @ turned          # (n < 4: the slide stacked on it is set too)
        else:
            # a slide along X, then a rotate (on it) about Z through the part's own centre as it was
            slid = Matrix.Translation((dist, 0, 0)) @ rest[n]
            if n < 4:
                c = slid.translation + Vector((0.05, 0.0, 0.0))        # the turn's axis rides along on the slide
                want = Matrix.Translation(c) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation(-c) @ slid
            else:
                want = slid
        assert (got.translation - want.translation).length < TOL, (n, got.translation, want.translation)
        assert max(abs(a - b) for ra, rb in zip(got.to_3x3(), want.to_3x3()) for a, b in zip(ra, rb)) < 1e-4, n
    # parts without a joint did not move
    for n in (300, 350, 399):
        assert (parts[n].matrix_world.translation - Vector(((n % GRID) * PITCH, (n // GRID) * PITCH, 0))).length < 1e-6
