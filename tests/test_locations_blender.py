"""Locations in the app (task 0272, ``blender/locations.py``): a fresh user's ready-made folders, the old Shared
library moved, a set-up file first (own folders off + the note), set-ups copied / linked / updated, every list with
badges, saving asks where, the export places and "also a copy", an unreachable folder never slows the start, and no
reader building its own library path."""

import os
import re
import time

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import locations as L  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture()
def loc(tmp_path, monkeypatch):
    from fresing_render.blender import locations, prefs
    monkeypatch.setenv(locations.ENV, str(tmp_path / "config é" / L.STATE_FILE))
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs ü"))
    for k in ("FRESING_RULE_SETS_DIR", "FRESING_WORKSPACES_DIR", "FRESING_BRAND_KITS_DIR"):
        monkeypatch.delenv(k, raising=False)
    p = prefs.get()
    p.library_path = ""
    locations.forget()
    yield locations
    p.library_path = ""
    locations.forget()


def _setup_file(tmp_path, name, sid="acme", version=1, level="company", label="", **kw):
    content = kw.pop("content", None)
    s = L.Setup(id=sid, name=name, level=level, label=label, version=version, **kw)
    path = str(tmp_path / f"{name}.frsetup")
    L.write_setup(path, s, content)
    return path


def _folder(tmp_path, name, files):
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    for f, text in files.items():
        (d / f).write_text(text, encoding="utf-8")
    return str(d)


def _rule_set_file(folder, name):
    from fresing_render.core import rule_sets as RS
    os.makedirs(folder, exist_ok=True)
    RS.save_in(folder, RS.empty(name))


# ---------------------------------------------------------------------------------------------------------------------

def test_a_fresh_user_gets_ready_made_folders_and_never_a_no_library_message(loc, tmp_path):
    from fresing_render.blender import decals, lifting, ops_lifting_make, rule_sets, workspaces
    loc.load()
    root = tmp_path / "Docs ü" / "Fresing Render" / "Library"
    for k in L.KINDS:
        assert (root / k.sub).is_dir(), k.sub
        assert [f["on"] for f in loc.mine_list(k.key)] == [True]
    loc.wait_reach()
    assert rule_sets.folder()[2] == "" and rule_sets.folder()[0] == str(root / "Rule sets")
    assert workspaces.folder()[0] == str(root / "Workspaces")
    assert ops_lifting_make.make_library() == str(root / "Lifting equipment")
    assert lifting.user_folder() == str(root / "Lifting equipment")
    assert decals.library_folders() == [str(root / "Logos"), str(root / "Stickers")]
    assert not loc.state()["note_off"]


def test_a_library_folder_of_before_becomes_mine(loc, tmp_path):
    from fresing_render.blender import prefs
    lib = tmp_path / "Shared lib"
    prefs.get().library_path = str(lib)
    loc.load()
    for k in L.KINDS:
        assert loc.mine_list(k.key) == [{"path": os.path.join(str(lib), k.sub), "on": True, "ready": False}]
    assert not (tmp_path / "Docs ü" / "Fresing Render" / "Library").exists()      # nothing new made
    assert loc.state()["migrated"]
    prefs.get().library_path = str(tmp_path / "other")                           # used once only
    loc.forget()
    loc.load()
    assert loc.mine_list("logos")[0]["path"] == os.path.join(str(lib), "Logos")


def test_a_setup_first_makes_own_folders_off_with_one_note(loc, tmp_path, monkeypatch):
    it = tmp_path / "IT share"
    it.mkdir()
    logos = _folder(tmp_path, "company logos", {"acme.png": "x"})
    _setup_file(it, "Company", content={"logos": logos})
    monkeypatch.setenv(loc.ENV_SETUP_FOLDER, str(it))
    loc.load()
    assert [e["mode"] for e in loc.state()["setups"]] == ["link"]
    assert all(not f["on"] for k in L.KIND_KEYS for f in loc.mine_list(k))
    assert (tmp_path / "Docs ü" / "Fresing Render" / "Library" / "Logos").is_dir()  # made, but off
    assert loc.state()["note_off"]
    loc.wait_reach()
    assert [os.path.basename(p) for _k, _n, p, _l in loc.items("logos", (".png",))] == ["acme.png"]
    i = 0
    loc.set_on("logos", i, True)
    assert loc.mine_list("logos")[0]["on"] and loc.state()["note_off"]          # others still off
    bpy.ops.fresing.loc_mine_all_on()
    assert not loc.state()["note_off"]
    assert all(f["on"] for k in L.KIND_KEYS for f in loc.mine_list(k))


def test_setups_add_copy_link_badges_and_same_names(loc, tmp_path):
    from fresing_render.blender import decals, rule_sets
    loc.load()
    loc.wait_reach()
    root = tmp_path / "Docs ü" / "Fresing Render" / "Library"
    _rule_set_file(str(root / "Rule sets"), "Fresing")
    (root / "Logos" / "mine.png").write_text("m")
    com_rules = str(tmp_path / "server" / "Rule sets")
    _rule_set_file(com_rules, "Fresing")
    _rule_set_file(com_rules, "Acme")
    c = _setup_file(tmp_path, "Company", content={"logos": _folder(tmp_path, "c logos", {"acme.png": "c"})},
                    locations={"rule_sets": [com_rules]})
    d = _setup_file(tmp_path, "Offshore", sid="off", level="department", label="Offshore department",
                    content={"logos": _folder(tmp_path, "d logos", {"acme.png": "d"})})
    assert bpy.ops.fresing.loc_setup_add(filepath=c, mode="COPY") == {"FINISHED"}
    assert bpy.ops.fresing.loc_setup_add(filepath=d, mode="LINK") == {"FINISHED"}
    loc.wait_reach()
    names = [label for label, _p in decals.library_pictures()]
    assert names == ["Logos: acme  ·  Company", "Logos: acme  ·  Offshore department", "Logos: mine  ·  Mine"]
    lib = rule_sets.library(force=True)
    assert sorted(lib) == ["Acme", "Fresing", "Fresing (Mine)"]           # same name: both, never one hidden
    assert os.path.dirname(lib["Fresing"][0]) == com_rules
    assert [e["mode"] for e in loc.state()["setups"]] == ["copy", "link"]
    assert os.path.isfile(os.path.join(loc.setups_dir(), "acme" + L.SETUP_EXT))
    os.remove(c)                                                          # a copy does not need the file
    loc.forget()
    loc.load()
    loc.wait_reach()
    assert "Logos: acme  ·  Company" in [label for label, _p in decals.library_pictures()]


def test_saving_asks_where_mine_first_and_never_inside_a_setup(loc, tmp_path):
    loc.load()
    loc.wait_reach()
    share = tmp_path / "company rules"
    share.mkdir()
    c = _setup_file(tmp_path, "Company", locations={"rule_sets": [str(share)]},
                    content={"rule_sets": _folder(tmp_path, "packed", {"x.json": "{}"})})
    loc.install(c, "copy")
    loc.wait_reach()
    ch = loc.save_choices("rule_sets")
    assert [p for p, _l in ch] == [os.path.join(str(tmp_path / "Docs ü"), "Fresing Render", "Library", "Rule sets"),
                                   str(share)]
    assert ch[0][1].startswith("Mine: ") and ch[1][1].startswith("Company: ")
    from fresing_render.blender import ops_rule_sets
    items = [i[0] for i in ops_rule_sets.locations.where_items("rule_sets")(None, None)]
    assert items == [p for p, _l in ch]


def test_a_renamed_newer_linked_file_updates_with_a_change_list(loc, tmp_path):
    loc.load()
    folder = tmp_path / "net"
    folder.mkdir()
    a = _setup_file(folder, "Company v3", version=3)
    loc.install(a, "link")
    loc.wait_reach()
    new = str(folder / "Company v3.frsetup")
    L.write_setup(new, L.Setup(id="acme", name="Company v3", version=4,
                               locations={"logos": [str(tmp_path / "new logos")]}))
    os.utime(new, (time.time() + 5, time.time() + 5))
    out = loc.refresh()
    assert out == ["Company set-up updated (3 → 4)"]
    u = loc.state()["updated"][-1]
    assert "Version 3 → 4" in u["lines"] and any("folder added" in x for x in u["lines"])
    renamed = _setup_file(tmp_path, "Some other file name", version=5)                # same id, other name
    new_s, old_s, lines = loc.check(renamed)
    assert old_s is not None and old_s.version == 4 and L.compare(old_s, new_s) == "newer"
    (tmp_path / "x").mkdir()
    new_s, old_s, _lines = loc.check(_setup_file(tmp_path / "x", "Older", version=2))
    assert L.compare(old_s, new_s) == "older"


def test_a_damaged_setup_is_refused_in_plain_words(loc, tmp_path):
    loc.load()
    bad = tmp_path / "bad.frsetup"
    bad.write_bytes(b"not a zip")
    with pytest.raises(RuntimeError, match="not a Fresing set-up file"):
        bpy.ops.fresing.loc_setup_add(filepath=str(bad))
    assert loc.state()["setups"] == []


def test_save_as_a_setup_file_and_bring_it_in_elsewhere(loc, tmp_path):
    from fresing_render.blender import prefs
    loc.load()
    p = prefs.get()
    p.keep_howto = True
    try:
        logos = tmp_path / "Docs ü" / "Fresing Render" / "Library" / "Logos"
        (logos / "ours.png").write_text("o")
        loc.add_mine("rule_sets", "\\\\server\\share\\Rule sets")
        loc.state()["exports"]["own"].append({"name": "Marketing", "path": "\\\\server\\mkt", "project_sub": True})
        out = str(tmp_path / "Ours é.frsetup")
        pack = [k.key == "logos" for k in L.KINDS]
        assert bpy.ops.fresing.loc_setup_save(filepath=out, name="Ours", level="department", label="Team",
                                              pack=pack) == {"FINISHED"}
        s = L.read_setup(out)
        assert s.level == "department" and s.badge == "Team" and s.version == 1
        assert s.settings.get("keep_howto") is True
        assert s.locations == {"rule_sets": ["\\\\server\\share\\Rule sets"]}
        assert s.content == {"logos": ["ours.png"]} and s.exports[0]["name"] == "Marketing"
        assert bpy.ops.fresing.loc_setup_save(filepath=out, sid=s.id, name="Ours", level="department",
                                              label="Team") == {"FINISHED"}
        assert L.read_setup(out).version == 2                  # saved over the same set-up: its version raised
    finally:
        p.keep_howto = False


def test_different_from_standard_and_back(loc, tmp_path):
    from fresing_render.blender import prefs
    loc.load()
    p = prefs.get()
    p.keep_sections = True
    try:
        rows = {r.key: r for r in loc.differences()}
        assert rows["setting:keep_sections"].source == "Mine" and rows["setting:keep_sections"].own
        assert not any(k.startswith("folder:") for k in rows)                 # the ready-made ones are standard
        assert bpy.ops.fresing.loc_back(key="setting:keep_sections") == {"FINISHED"}
        assert p.keep_sections is False
    finally:
        p.keep_sections = False


def test_export_places_and_also_a_copy(loc, tmp_path):
    from fresing_render.blender import locations, render
    loc.load()
    scene = bpy.context.scene
    s = scene.fresing
    s.out_folder = ""
    s.out_place = ""
    pics = render.pictures_dir()
    assert locations.output_dir(scene) == os.path.join(pics, "Fresing Render")      # never saved: as before
    assert bpy.ops.fresing.out_place(place="pictures") == {"FINISHED"}
    assert s.out_place == "pictures"
    share = tmp_path / "share"
    bpy.ops.fresing.loc_place_add(directory=str(share), name="Marketing", project_sub=False)
    assert bpy.ops.fresing.loc_also_to(place="mine:Marketing") == {"FINISHED"}
    assert locations.also_dir(scene) == str(share)
    still = tmp_path / "out.png"
    still.write_text("png")
    copy = locations.copy_also(scene, str(still))
    assert copy == str(share / "out.png") and os.path.isfile(copy)
    frames = tmp_path / "video_1"
    frames.mkdir()
    (frames / "0001.png").write_text("f")
    assert os.path.isfile(os.path.join(locations.copy_also(scene, str(frames)), "0001.png"))
    assert render.default_output_dir(scene) == locations.output_dir(scene)
    s.out_folder = str(tmp_path / "own")
    assert render.default_output_dir(scene) == str(tmp_path / "own")                # an own folder wins
    s.out_folder = ""
    s.out_place = ""
    bpy.ops.fresing.loc_also(on=False)
    assert locations.also_dir(scene) == ""


def test_the_queue_job_carries_the_copy_place(loc, tmp_path):
    src = open(os.path.join(ROOT, "fresing_render", "blender", "queue.py"), encoding="utf-8").read()
    assert '"also_dir": also' in src
    runner = open(os.path.join(ROOT, "fresing_render", "queue_runner.py"), encoding="utf-8").read()
    assert 'job.get("also_dir")' in runner and "copy_output" in runner


def test_an_unreachable_folder_does_not_slow_the_start(loc, tmp_path, monkeypatch):
    dead = str(tmp_path / "dead server")
    monkeypatch.setenv(L.SLOW_ENV, f"{dead}=3")
    loc.load()
    loc.add_mine("logos", os.path.join(dead, "Logos"))
    loc.forget()
    t0 = time.monotonic()
    loc.load()
    from fresing_render.blender import decals
    pics = decals.library_pictures()
    folders = loc.folders("logos")
    took = time.monotonic() - t0
    assert took < 0.5, took
    assert [f.reach for f in folders if f.path.startswith(dead)] == [None]           # being looked at
    assert pics == []


def test_no_reader_builds_its_own_library_path():
    """Every reader goes through locations.py: ``library_path`` is read only by the migration (and kept by the
    settings file)."""
    allowed = {os.path.join("blender", n) for n in ("locations.py", "prefs.py", "settings_store.py")}
    bad = []
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "fresing_render")):
        for f in files:
            if not f.endswith(".py"):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, os.path.join(ROOT, "fresing_render"))
            text = open(full, encoding="utf-8").read()
            if re.search(r"\.library_path\b", text) and rel not in allowed:
                bad.append(rel)
            if "No library folder" in text:
                bad.append(rel + " (No library folder)")
    assert bad == []


def test_the_settings_window_has_locations_and_exports_after_general():
    from fresing_render.blender import ui_settings
    assert ui_settings.KEYS[:3] == ("general", "locations", "exports")
    assert ui_settings.LATER == () and "materials" in ui_settings.KEYS      # task 0273 added its page
    assert "locations" in ui_settings.draw_all(bpy.context) and "exports" in ui_settings.draw_all(bpy.context)
