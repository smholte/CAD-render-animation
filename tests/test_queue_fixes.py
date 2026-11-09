"""Render queue and video fixes from the bug hunt (task 0054): rows 7, 8, 9, 10, 17a-e, 18, 20b."""

import json
import math
import os
import subprocess
import sys

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
PIVOT = Vector((0.1, 0.3, 0.4))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, callouts, cameras, joints, queue, states  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path, monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    monkeypatch.setattr(queue, "_RUNTIME", {"pid": 0, "dir": "", "killed": False, "project": ""})
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name):
    return sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))[0]


def boom_joint(sc):
    pin = ob(sc, "BOOM.PIN")
    origin, direction, _desc = joints.axis_from_hit(pin, 0, PIVOT + Vector((0, 0, 0.02)), Vector((0, 0, 1)))
    return joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], origin, direction, ref=pin)


def luff(sc, j, orbit=True):
    """2 s: the boom up 60°, the cover hidden at 1 s, the camera orbiting 90°."""
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Luff", "25", 0.0
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration = "JOINT", j.name, 0.0, 2.0
    b.use_from, b.from_angle, b.to_angle = False, 0.0, math.radians(60)
    h = a.blocks.add()
    cover = ob(sc, "COVER")
    h.kind, h.start, h.target_uid, h.target_name = "HIDE", 1.0, cover[build.PROP_UID], "COVER"
    if orbit:
        c = a.blocks.add()
        c.kind, c.camera_mode, c.orbit_angle, c.start, c.duration = "CAMERA", "ORBIT", math.radians(90), 0.0, 2.0
    return a


def close(a, b, tol=1e-4):
    return (Vector(a) - Vector(b)).length < tol


# ---------------------------------------------------------------------------
# row 7: "Add image" while scrubbed in a built animation queues what the view shows
# ---------------------------------------------------------------------------


def test_add_image_in_a_built_animation_queues_the_frame_shown(scene):
    s = scene.fresing
    j = boom_joint(scene)
    a = luff(scene, j)
    cam0 = scene.camera
    animation.bake(scene, a)
    scene.frame_set(40)
    cover = ob(scene, "COVER")
    assert cover.hide_render and scene.camera.get("fr_anim_camera")
    view_matrix = scene.camera.matrix_world.copy()
    value = joints.get_value(j)
    assert value > 0.5
    assert bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}
    job = s.queue[-1]
    shot = s.shots[job.shot]
    assert shot.get(queue.QUEUE_ONLY)
    assert shot.camera is not None and shot.camera.get(queue.QUEUE_ONLY) and not shot.camera.get("fr_anim_camera")
    assert cover[build.PROP_UID] in [h.uid for h in shot.own_visibility.hidden]
    # what the runner does with the copy: the keys go, the saved scene comes back
    for w in states.apply_shot(scene, job.shot):
        raise AssertionError(w)
    bpy.context.view_layer.update()
    assert not s.anim_baked
    assert cover.hide_render, "the cover hidden at this frame stays hidden"
    assert scene.camera is shot.camera
    assert close(scene.camera.matrix_world.translation, view_matrix.translation, 1e-4)
    assert abs(joints.get_value(j) - value) < 1e-4
    # the hidden camera is not offered anywhere, and goes with its job
    assert shot.camera not in cameras.fr_cameras(scene)
    cam_name, shot_name = shot.camera.name, shot.name
    scene.camera = cam0
    s.queue_index = len(s.queue) - 1
    assert bpy.ops.fresing.queue_remove() == {"FINISHED"}
    assert shot_name not in s.shots and cam_name not in bpy.data.objects


def test_add_image_without_animation_keeps_the_camera(scene):
    s = scene.fresing
    cam = scene.camera
    cover = ob(scene, "COVER")
    from fresing_render.blender import logic
    logic.set_hidden(cover, True)
    assert bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}
    shot = s.shots[s.queue[-1].shot]
    assert shot.camera is cam
    assert [h.uid for h in shot.own_visibility.hidden] == [cover[build.PROP_UID]]
    assert not [o for o in bpy.data.objects if o.get(queue.QUEUE_ONLY)]


# ---------------------------------------------------------------------------
# row 8: a stopped job never mixes old frames into a new video
# ---------------------------------------------------------------------------


def _png(path):
    img = bpy.data.images.new("f", 4, 4)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def test_old_frames_are_dropped(tmp_path, monkeypatch):
    folder = str(tmp_path / "frames")
    os.makedirs(folder)
    for f in range(1, 7):
        _png(os.path.join(folder, f"frame_{f:04d}.png"))
    with open(os.path.join(folder, queue.FINGERPRINT), "w") as fh:
        fh.write("same\n")
    # same animation, now 3 frames long: frames 4-6 go
    queue.keep_frames(folder, "same", 3)
    assert sorted(f for f in os.listdir(folder) if f.startswith("frame_")) == \
        ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    # the video takes only frames 1..end, even when more are there
    for f in range(4, 7):
        _png(os.path.join(folder, f"frame_{f:04d}.png"))
    from fresing_render.blender import video
    seen = []

    class Done(Exception):
        pass

    def grab(enc, files, *args, **kwargs):
        seen.extend(os.path.basename(f) for f in files)
        raise Done()

    monkeypatch.setattr(video, "build_sequence", grab)
    with pytest.raises(Done):
        queue.encode_mp4(folder, str(tmp_path / "v.mp4"), 4, 4, 25, last=3)
    assert seen == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    os.remove(os.path.join(folder, "frame_0002.png"))
    with pytest.raises(RuntimeError, match="missing"):
        queue.encode_mp4(folder, str(tmp_path / "v.mp4"), 4, 4, 25, last=3)
    # another animation or other settings: every old frame goes
    queue.keep_frames(folder, "changed", 3)
    assert not [f for f in os.listdir(folder) if f.startswith("frame_")]
    assert open(os.path.join(folder, queue.FINGERPRINT)).read().strip() == "changed"


def test_fingerprint_follows_the_animation(scene):
    s = scene.fresing
    j = boom_joint(scene)
    a = luff(scene, j)
    a.out_resolution, a.quality = "preview", "draft"
    job = {"animation": a.name, "quality": "draft", "id": "x", "out_dir": s.out_folder}

    def fp():
        setup = queue._setup_animation(scene, job, lambda *_: None)
        return queue.fingerprint(scene, setup)

    first = fp()
    assert fp() == first, "nothing changed: the frames are kept"
    a.blocks[0].to_angle = math.radians(50)
    second = fp()
    assert second != first, "another move"
    a.blocks[1].start = 1.5
    assert fp() != second, "the cover hides later"
    job["quality"] = "preview"
    assert fp() != second, "another quality"


# ---------------------------------------------------------------------------
# row 9: a running queue stays with its own project
# ---------------------------------------------------------------------------


def test_running_queue_stays_in_its_project(scene, tmp_path):
    s = scene.fresing
    a_path, b_path = str(tmp_path / "A.blend"), str(tmp_path / "B.blend")
    qdir = str(tmp_path / "_queue" / "a")
    os.makedirs(qdir)
    with open(os.path.join(qdir, "queue.json"), "w") as fh:
        json.dump({"jobs": [{"id": "aaaa", "kind": "STILL", "shot": "", "animation": "", "camera": "",
                             "quality": "draft", "label": "Image: A"}]}, fh)
    with open(os.path.join(qdir, "status.json"), "w") as fh:
        json.dump({"pid": os.getpid(), "running": True, "jobs": {"aaaa": {"status": "RUNNING"}}}, fh)
    bpy.ops.wm.save_as_mainfile(filepath=a_path)
    queue._RUNTIME.update(pid=os.getpid(), dir=qdir, killed=False,
                          project=os.path.normcase(os.path.abspath(a_path)))
    s.queue_dir, s.queue_pid = qdir, os.getpid()
    assert queue.current(scene) == (os.getpid(), qdir)
    # another project is opened (here: saved under another name, with no queue of its own)
    s.queue_dir, s.queue_pid = "", 0
    bpy.ops.wm.save_as_mainfile(filepath=b_path)
    assert queue.current(scene) == (0, "")
    assert not queue.is_running(scene)
    queue.sync(scene)
    assert not len(s.queue) and s.queue_dir == "", "B does not take A's jobs"
    assert not queue.belongs_here(scene)
    # B's own old queue has ended: that does not make the app forget A's
    own = str(tmp_path / "_queue" / "b")
    os.makedirs(own)
    open(os.path.join(own, "queue.json"), "w").write('{"jobs": []}')
    s.queue_dir, s.queue_pid = own, _dead_pid()
    assert not queue.sync(scene)
    assert s.queue_pid == 0 and queue._RUNTIME["pid"] == os.getpid()
    s.queue_dir = ""
    # the project saved under a new name while its queue runs keeps it (the scene names the folder)
    s.queue_dir = qdir
    assert queue.current(scene) == (os.getpid(), qdir)


# ---------------------------------------------------------------------------
# row 10: videos keep the sharp spot on a moving part
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("orbit", [True, False])
def test_video_keeps_the_sharp_spot(scene, orbit):
    s = scene.fresing
    j = boom_joint(scene)
    cam = scene.camera
    s.camera_blur = "LITTLE"
    tip_part = ob(scene, "BOOM")
    cameras.set_focus(cam, scene, tip_part, tip_part.matrix_world @ Vector((1.5, 0, 0)))
    stale = cam.data.dof.focus_distance
    joints.set_value(j, math.radians(60))           # the start scene has the boom up
    states.save_shot(scene, "Up")
    joints.set_value(j, 0.0)
    bpy.context.view_layer.update()
    a = luff(scene, j, orbit=orbit)
    a.blocks[0].use_from, a.blocks[0].from_angle = True, math.radians(60)
    a.blocks[0].to_angle = 0.0
    a.start_shot = "Up"
    animation.bake(scene, a)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    true = cameras.focus_distance(cam, scene)
    assert abs(true - stale) > 0.05, "the spot moved with the boom"
    assert cam.data.dof.focus_distance == pytest.approx(true, abs=1e-4), "worked out again at the start"
    video_cam = scene.camera
    if orbit:
        assert video_cam.get("fr_anim_camera")
        assert video_cam.data.dof.focus_object is cameras.focus_marker(cam), "follows the spot on every frame"
    else:
        assert video_cam is cam


# ---------------------------------------------------------------------------
# row 17: five small queue faults
# ---------------------------------------------------------------------------


def _dead_pid() -> int:
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_removed_job_is_skipped_by_the_running_queue(scene, tmp_path, monkeypatch):
    s = scene.fresing
    queue.add_job(scene, "STILL", shot="One")
    queue.add_job(scene, "STILL", shot="Two")
    ids = [j.job_id for j in s.queue]
    qdir = str(tmp_path / "q")
    os.makedirs(qdir)
    with open(os.path.join(qdir, "queue.json"), "w") as fh:
        json.dump({"jobs": [{"id": i, "kind": "STILL", "shot": n, "animation": "", "camera": "", "quality": "draft",
                             "label": "Image: " + n} for i, n in zip(ids, ("One", "Two"))]}, fh)
    with open(os.path.join(qdir, "status.json"), "w") as fh:
        json.dump({"pid": 1, "running": True, "jobs": {i: {"status": "WAITING"} for i in ids}}, fh)
    s.queue_dir = qdir
    monkeypatch.setattr(queue, "is_running", lambda sc: True)
    s.queue_index = 1
    assert bpy.ops.fresing.queue_remove() == {"FINISHED"}
    assert os.path.exists(os.path.join(qdir, "skip_" + ids[1]))
    queue.sync(scene)
    assert [j.job_id for j in s.queue] == [ids[0]], "it does not come back"


def test_runner_leaves_out_a_removed_job(tmp_path):
    qdir = str(tmp_path / "q")
    os.makedirs(qdir)
    blend = str(tmp_path / "p.blend")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    with open(os.path.join(qdir, "queue.json"), "w") as fh:
        json.dump({"blend": blend, "jobs": [{"id": "gone", "kind": "STILL", "shot": "X", "animation": "",
                                             "camera": "", "quality": "draft", "label": "Image: X",
                                             "out_dir": str(tmp_path)}]}, fh)
    open(os.path.join(qdir, "skip_gone"), "w").close()
    env = dict(os.environ, PYTHONPATH=os.path.dirname(queue.PACKAGE_DIR))
    subprocess.run(queue.runner_command(qdir), env=env, cwd=qdir, timeout=120, capture_output=True)
    st = queue.read_status(qdir)
    assert st["jobs"]["gone"]["status"] == "STOPPED" and st["jobs"]["gone"]["message"] == "Removed from the queue"
    assert os.path.exists(blend) is False, "the copy is removed at the end"


def test_every_saved_scene_leaves_out_hidden_queue_scenes(scene):
    s = scene.fresing
    states.save_shot(scene, "Side")
    assert bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}       # a hidden "Queue …" scene
    s.queue.clear()
    assert bpy.ops.fresing.queue_add(kind="ALL_SHOTS") == {"FINISHED"}
    assert [j.shot for j in s.queue] == ["Side"]


def test_renaming_an_animation_keeps_the_job_names(scene):
    s = scene.fresing
    a = s.animations.add()
    a.name = "Lift"
    s.wm_on = True
    queue.add_job(scene, "ANIMATION", animation="Lift")
    queue.add_job(scene, "TEST", animation="Lift")
    assert [j.label for j in s.queue] == ["Animation: Lift (with watermark)", "Time test: Lift"]
    a.name = "Lift high"
    assert [j.label for j in s.queue] == ["Animation: Lift high (with watermark)", "Time test: Lift high"]
    states.save_shot(scene, "Side")
    queue.add_job(scene, "STILL", shot="Side")
    s.shots["Side"].name = "Front"
    assert s.queue[-1].shot == "Front" and s.queue[-1].label == "Image: Front (with watermark)"


def test_deleted_saved_scene_fails_the_job(scene):
    with pytest.raises(RuntimeError, match="was deleted"):
        queue.run_job(scene, {"kind": "STILL", "shot": "Gone", "out_dir": scene.fresing.out_folder,
                              "quality": "draft"}, lambda *_: None, lambda: False)


def test_runner_that_died_before_its_status_fails_the_jobs(scene, tmp_path):
    s = scene.fresing
    queue.add_job(scene, "STILL", shot="One")
    queue.add_job(scene, "STILL", shot="Later")          # added after the queue started: stays waiting
    qdir = str(tmp_path / "q")
    os.makedirs(qdir)
    with open(os.path.join(qdir, "queue.json"), "w") as fh:
        json.dump({"jobs": [{"id": s.queue[0].job_id, "kind": "STILL", "shot": "One", "animation": "",
                             "camera": "", "quality": "draft", "label": "Image: One"}]}, fh)
    with open(os.path.join(qdir, "log.txt"), "w") as fh:
        fh.write("Error: could not start\n")
    s.queue_dir, s.queue_pid = qdir, _dead_pid()
    assert not queue.sync(scene)
    assert s.queue[0].status == "FAILED" and "could not start" in s.queue[0].message
    assert s.queue[1].status == "WAITING"


# ---------------------------------------------------------------------------
# row 18: '//' paths still work in the queue's copy
# ---------------------------------------------------------------------------


def test_relative_paths_work_in_the_queue_copy(scene, tmp_path, monkeypatch):
    s = scene.fresing
    proj = tmp_path / "project"
    proj.mkdir()
    path = str(proj / "machine.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    s["brand_logo"] = "//logo.png"
    s["brand_font"] = "//fonts/card.ttf"
    s["hdri_path"] = "//sky.hdr"
    a = s.animations.add()
    a.name = "Lift"
    a.music_file = "//music.wav"
    card = a.cards.add()
    card.path = "//photo.jpg"
    states.save_shot(scene, "Outside")
    s.shots["Outside"].world = json.dumps({"background": "HDRI", "hdri_path": "//sky.hdr"})
    queue.add_job(scene, "STILL", shot="Outside")

    class FakeProc:
        pid = _dead_pid()

        def poll(self):
            return 0

    monkeypatch.setattr(queue.subprocess, "Popen", lambda *a, **k: FakeProc())
    monkeypatch.setattr(queue, "_PROCS", {})
    qdir = queue.start(bpy.context)
    # the project itself keeps its '//' paths
    assert s.brand_logo == "//logo.png" and a.music_file == "//music.wav" and card.path == "//photo.jpg"
    assert json.loads(s.shots["Outside"].world)["hdri_path"] == "//sky.hdr"
    copy = json.load(open(os.path.join(qdir, "queue.json")))["blend"]
    assert os.path.dirname(copy) != str(proj)
    bpy.ops.wm.open_mainfile(filepath=copy)
    c = bpy.context.scene.fresing
    want = lambda name: os.path.normpath(os.path.join(str(proj), name))  # noqa: E731
    assert c.brand_logo == want("logo.png")
    assert c.brand_font == want(os.path.join("fonts", "card.ttf"))
    assert c.hdri_path == want("sky.hdr")
    assert c.animations["Lift"].music_file == want("music.wav")
    assert c.animations["Lift"].cards[0].path == want("photo.jpg")
    assert json.loads(c.shots["Outside"].world)["hdri_path"] == want("sky.hdr")


# ---------------------------------------------------------------------------
# row 20b: the labels pass reads the parts' boxes once
# ---------------------------------------------------------------------------


def test_part_boxes_give_the_same_outline(scene):
    j = boom_joint(scene)
    cover = ob(scene, "COVER")
    size = (640, 480)
    boxes = callouts.PartBoxes(scene)
    for value, hide in ((0.0, False), (math.radians(50), True)):
        joints.set_value(j, value)
        cover.hide_render = hide
        bpy.context.view_layer.update()
        mat = callouts.camera_matrix(scene, size)
        slow = callouts.model_outline(scene, size, mat)
        fast = callouts.model_outline(scene, size, mat, boxes)
        assert np.allclose(slow, fast, atol=1e-3), (slow, fast)
    corners = boxes.world_corners(scene)
    shown = [o for o in scene.objects if o.type == "MESH" and o.get(build.PROP_KIND) == "part" and not o.hide_render]
    assert len(corners) == 8 * len(shown)
