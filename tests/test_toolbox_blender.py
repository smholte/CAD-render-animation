"""A house from House Planner by itself, in Blender (task 0217): a job made the way House Planner makes it (the real
sample package of house-scene-format v1.0.1) lands in a Toolbox folder in a path with a space and an accent; the
inbox's look says `waiting`; Bake now imports it into a scene of its own, bakes (first moment, 4 samples) and sends
the .hpbake back as a reply job; the status is `done`; the house scene is gone and the owner's project – a model, the
app's world with its own sky – is exactly as it was. Then Cancel (cancel.json while it works), a busy app, Not now and
the panel's lines."""

import json
import os
import shutil
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

os.environ["FRESING_NO_TOOLBOX"] = "1"           # the app's own watcher stays off: the test makes its own
import fresing_render  # noqa: E402
from fresing_render.blender import house_import, ops_house, toolbox_inbox as ti  # noqa: E402
from fresing_render.core import house_scene as hs  # noqa: E402
from fresing_render.core import toolbox as tb  # noqa: E402

HERE = Path(__file__).parent
PIN = HERE / "data" / "toolbox" / "tbf-v0.1.1"
HOUSE = HERE / "data" / "house" / "hsf-v1.0.1" / "samples" / "sample-house.hpscene"
HP = "nl.fresing.house-planner"


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    ti._S["inbox"] = None
    fresing_render.unregister()


def _project():
    """The owner's project: a part, the app's world with the sky at 30°, the weather off."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.name = "Cable lay"
    me = bpy.data.meshes.new("Part")
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new("Part", me)
    sc.collection.objects.link(ob)
    from fresing_render.blender import world
    sc.fresing.background = "SKY"
    sc.fresing.sun_elevation = 30.0
    world.apply(sc, sc.fresing)
    return sc


def _state(sc):
    w = sc.world
    nodes = None
    if w is not None and w.node_tree is not None:
        nodes = sorted((n.bl_idname, tuple(round(float(i.default_value), 4) for i in n.inputs
                                           if isinstance(getattr(i, "default_value", None), float)))
                       for n in w.node_tree.nodes)
    return {"scenes": sorted(s.name for s in bpy.data.scenes), "objects": sorted(o.name for o in sc.objects),
            "world": w.name if w else None, "nodes": nodes, "engine": sc.render.engine,
            "background": sc.fresing.background, "weather": sc.fresing.weather.enabled, "house": house_import.has_house(sc),
            "shown": sorted((o.name, o.hide_render, o.hide_viewport) for o in sc.objects)}


def _folder(tmp: Path, hp_manifest=True) -> Path:
    root = tmp / "Tool box é"
    if hp_manifest:
        (root / "tools" / HP).mkdir(parents=True)
        shutil.copyfile(PIN / "samples" / "Toolbox" / "tools" / HP / "toolbox.json", root / "tools" / HP / "toolbox.json")
    return root


def _status(root, jid):
    return json.loads((root / "tools" / tb.ME / "inbox" / jid / "status.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def round_trip(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("toolbox")
    sc = _project()
    before = _state(sc)
    root = _folder(tmp)
    ib = ti.use_folder(root, keep=tmp / "kept", timer=False, samples=4, photo_samples=4, quick=True)
    jid = tb.send(root, HP, tb.ME, "bake-house", [HOUSE], title="Sample house – version 3", ret="import-bake")
    events = ti.look()
    waiting = _status(root, jid)
    shown = ti.to_show() and [j.id for j in ti.waiting()] == [jid]
    with bpy.context.temp_override(scene=sc):
        why = ti.start(bpy.context, jid)
    return {"root": root, "jid": jid, "events": events, "waiting": waiting, "why": why, "before": before,
            "after": _state(sc), "ib": ib, "tmp": tmp, "shown": shown, "sc": sc}


def test_the_house_waits_for_bake_now(round_trip):
    assert round_trip["events"] and "From House Planner: Sample house – version 3" in round_trip["events"][0]
    assert round_trip["waiting"]["state"] == "waiting"
    assert round_trip["waiting"]["text"] == "Waiting for you in Fresing Render: press Bake now"
    assert round_trip["shown"]


def test_bake_now_sends_the_bake_back(round_trip):
    root, jid = round_trip["root"], round_trip["jid"]
    assert round_trip["why"] == ""
    st = _status(root, jid)
    assert st["state"] == "done" and st["text"] == "Baked 1 moment; sent back to House Planner", st
    rid = st["reply"]
    reply = root / "tools" / HP / "inbox" / rid
    job = json.loads((reply / "job.json").read_text("utf-8"))
    assert job["action"] == "import-bake" and job["reply_to"] == {"tool": tb.ME, "job": jid}
    bake = reply / job["files"][0]["name"]
    assert bake.suffix == ".hpbake" and job["files"][0]["type"] == "hpbake"
    house = hs.read_scene(str(HOUSE))
    assert hs.structure_problems(str(bake), house) == []
    assert sorted(os.listdir(root / "tools" / tb.ME / "inbox" / jid)) == ["job.json", "status.json"]
    assert not (round_trip["tmp"] / "kept").exists()


def test_the_project_is_as_it_was(round_trip):
    assert round_trip["after"] == round_trip["before"]
    assert ti._S["bake"] is None and not any(s.name.startswith("House –") for s in bpy.data.scenes)
    assert ti.last_result() == "Sent back to House Planner"


def test_everything_written_passes_the_pinned_checker(round_trip):
    from test_toolbox import errors
    assert errors(round_trip["root"]) == []


def _job(tmp, name, **kw):
    root = _folder(tmp / name)
    ib = ti.use_folder(root, keep=tmp / name / "kept", timer=False, samples=4, photo_samples=4, quick=True)
    jid = tb.send(root, HP, tb.ME, "bake-house", [HOUSE], title="Sample house", ret="import-bake")
    ti.look()
    return root, ib, jid


def test_cancel_json_while_it_bakes_stops_it(tmp_path, monkeypatch):
    sc = _project()
    before = _state(sc)
    root, ib, jid = _job(tmp_path, "cancel")
    seen = {}

    def bake(job):                           # the bake's own loop, as the modal sees it: running, then cancel.json
        rt = ops_house.runtime(job.scene)
        rt["running"] = True
        tb.write_json(root / "tools" / tb.ME / "inbox" / jid / "cancel.json",
                      {"format": "toolbox-cancel", "version": "0.1", "job": jid, "asked": tb.now()})
        ti.look()                            # the timer: sees cancel.json, asks the bake to stop
        seen["cancel"] = rt.get("cancel")
        rt["running"] = False
        ops_house._ended(job.scene, "cancelled", None, job.path)
        raise RuntimeError("cancelled")

    monkeypatch.setattr(ops_house, "run_at_once", bake)
    with bpy.context.temp_override(scene=sc):
        assert ti.start(bpy.context, jid) == ""
    assert seen["cancel"] is True
    st = _status(root, jid)
    assert st["state"] == "cancelled" and st["text"] == "Cancelled by House Planner; nothing was sent"
    assert not (root / "tools" / HP / "inbox").exists() or not os.listdir(root / "tools" / HP / "inbox")
    assert _state(sc) == before


def test_a_house_that_cannot_be_read_fails_and_leaves_the_project(tmp_path, monkeypatch):
    sc = _project()
    before = _state(sc)
    root, ib, jid = _job(tmp_path, "broken")

    def broken(*a, **k):
        raise hs.FormatError("This house package is broken (made-up fault)")

    monkeypatch.setattr(house_import, "import_scene", broken)
    with bpy.context.temp_override(scene=sc):
        assert "broken" in ti.start(bpy.context, jid)
    st = _status(root, jid)
    assert st["state"] == "failed" and st["code"] == "error" and "broken" in st["text"]
    assert _state(sc) == before


def _house_version(tmp: Path, version: str) -> Path:
    """The sample house with another format version in its scene.json (task 0353)."""
    import json
    import zipfile
    out = tmp / f"house-{version}.hpscene"
    with zipfile.ZipFile(HOUSE) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "scene.json":
                doc = json.loads(data)
                doc["version"] = version
                data = json.dumps(doc).encode()
            zout.writestr(info, data)
    return out


def test_a_house_of_a_newer_or_older_format_says_so_plainly(tmp_path):
    """Task 0353: the inbox hands the format's plain refusal on in the job's status; the project stays as it was."""
    sc = _project()
    before = _state(sc)
    for version, words in (("2.0", "was made by a newer House Planner (format 2.0). Update Fresing Render to read it."),
                           ("0.9", "was made by an older House Planner (format 0.9)")):
        root = _folder(tmp_path / version)
        ib = ti.use_folder(root, keep=tmp_path / version / "kept", timer=False, samples=4, photo_samples=4, quick=True)
        jid = tb.send(root, HP, tb.ME, "bake-house", [_house_version(tmp_path, version)], title="Format test",
                      ret="import-bake")
        ti.look()
        with bpy.context.temp_override(scene=sc):
            ti.start(bpy.context, jid)
        st = _status(root, jid)
        assert st["state"] == "failed" and words in st["text"], st
        assert _state(sc) == before


def test_a_busy_app_keeps_the_house_waiting(tmp_path):
    sc = _project()
    rt = ops_house.runtime(sc)
    rt["running"] = True                               # a house bake of the owner's own
    try:
        root, ib, jid = _job(tmp_path, "busy")
        st = _status(root, jid)
        assert st["state"] == "waiting" and st["text"] == "Fresing Render is busy (House bake); the house waits"
        with bpy.context.temp_override(scene=sc):
            assert "busy" in ti.start(bpy.context, jid)
        assert _status(root, jid)["state"] == "waiting"
    finally:
        rt["running"] = False
    ti.look()
    assert _status(root, jid)["text"] == "Waiting for you in Fresing Render: press Bake now"


def test_not_now_and_the_panel(tmp_path):
    sc = _project()
    root, ib, jid = _job(tmp_path, "notnow")
    assert bpy.types.FRESING_PT_house.poll(bpy.context)          # the panel shows with no house in the project
    with bpy.context.temp_override(scene=sc):
        assert bpy.ops.fresing.toolbox_not_now(job=jid) == {"FINISHED"}
    st = _status(root, jid)
    assert st["state"] == "cancelled" and st["text"] == "You said not now in Fresing Render"
    assert ti.waiting() == []
    for op in ("fresing.toolbox_start", "fresing.toolbox_not_now", "fresing.toolbox_cancel"):
        mod, name = op.split(".")
        assert getattr(getattr(bpy.ops, mod), name).get_rna_type().description, op
