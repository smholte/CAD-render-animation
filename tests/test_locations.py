"""Locations (task 0272, ``core/locations.py``, no Blender): the set-up file, merging, reachability, export places,
the migration of the old Shared library, "Different from standard"."""

import json
import os
import time
import zipfile

import pytest

from fresing_render.core import locations as L


def _setup(sid="acme01", version=1, **kw):
    return L.Setup(id=sid, name=kw.pop("name", "Acme standard"), level=kw.pop("level", "company"),
                   version=version, **kw)


def _content(tmp_path, kind_sub, files):
    d = tmp_path / ("src " + kind_sub)
    d.mkdir()
    for n, text in files.items():
        (d / n).write_text(text)
    return str(d)


# ---------------------------------------------------------------------------------------------------------------------
# the set-up file

def test_save_and_read_back_with_content(tmp_path):
    logos = _content(tmp_path, "Logos", {"acme.png": "png", "other.png": "x"})
    s = _setup(locations={"rule_sets": ["\\\\server\\share\\Rule sets"]}, settings={"default_rule_set": "Acme"},
               exports=[{"name": "Marketing", "path": "\\\\server\\mkt", "project_sub": True}])
    path = str(tmp_path / "Acme set-up é.frsetup")
    L.write_setup(path, s, {"logos": logos})
    back = L.read_setup(path)
    assert back.id == "acme01" and back.version == 1 and back.badge == "Company"
    assert back.content == {"logos": ["acme.png", "other.png"]}
    assert back.settings == {"default_rule_set": "Acme"}
    assert back.exports[0]["name"] == "Marketing"
    out = L.unpack(path, str(tmp_path / "unpacked"))
    assert os.path.isfile(os.path.join(out["logos"], "acme.png"))


def test_a_renamed_newer_file_is_the_same_setup(tmp_path):
    a = str(tmp_path / "company.frsetup")
    b = str(tmp_path / "Company set-up NEW (2).frsetup")
    L.write_setup(a, _setup(version=3))
    L.write_setup(b, _setup(version=4, locations={"logos": ["L:\\Logos"]}))
    old, new = L.read_setup(a), L.read_setup(b)
    assert old.id == new.id
    assert L.compare(old, new) == "newer"
    lines = L.changes(old, new)
    assert "Version 3 → 4" in lines
    assert any("Logos: folder added L:\\Logos" in x for x in lines)


def test_an_older_file_and_the_same_version(tmp_path):
    a, b = _setup(version=4), _setup(version=2)
    assert L.compare(a, b) == "older"
    assert L.compare(a, _setup(version=4)) == "same"
    assert L.changes(a, _setup(version=4)) == []


def test_content_changed_is_named(tmp_path):
    logos = _content(tmp_path, "Logos", {"acme.png": "one"})
    p1 = str(tmp_path / "a.frsetup")
    L.write_setup(p1, _setup(), {"logos": logos})
    L.unpack(p1, str(tmp_path / "in"))
    with open(os.path.join(logos, "acme.png"), "w") as fh:
        fh.write("two!")
    p2 = str(tmp_path / "b.frsetup")
    L.write_setup(p2, _setup(), {"logos": logos})
    assert L.content_changed(str(tmp_path / "in"), p2) == ["Logos: acme.png changed"]


def test_a_damaged_zip_is_refused_in_plain_words(tmp_path):
    p = tmp_path / "broken.frsetup"
    p.write_bytes(b"PK\x03\x04 this is not really a zip")
    with pytest.raises(L.SetupError, match="not a Fresing set-up file"):
        L.read_setup(str(p))


def test_no_setup_json_and_not_fresing(tmp_path):
    p = tmp_path / "x.frsetup"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("Logos/a.png", "x")
    with pytest.raises(L.SetupError, match="no setup.json"):
        L.read_setup(str(p))
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("setup.json", json.dumps({"format": "something-else"}))
    with pytest.raises(L.SetupError, match="not a Fresing set-up file"):
        L.read_setup(str(p))


@pytest.mark.parametrize("bad", ["../evil.png", "Logos/../../evil.png", "/etc/evil", "C:/Windows/evil.png",
                                 "Logos\\..\\..\\evil.png"])
def test_a_path_outside_its_folder_is_refused(tmp_path, bad):
    p = tmp_path / "evil.frsetup"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("setup.json", json.dumps(_setup().to_data()))
        zf.writestr(bad, "x")
    with pytest.raises(L.SetupError, match="refused"):
        L.read_setup(str(p))
    with pytest.raises(L.SetupError):
        L.unpack(str(p), str(tmp_path / "dest"))
    assert not (tmp_path / "evil.png").exists()


def test_unknown_content_kind_and_newer_format(tmp_path):
    p = tmp_path / "x.frsetup"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("setup.json", json.dumps(_setup().to_data()))
        zf.writestr("Sounds/beep.wav", "x")
    with pytest.raises(L.SetupError, match="'Sounds' is no kind"):
        L.read_setup(str(p))
    data = dict(_setup().to_data(), format_version=L.FORMAT_VERSION + 1, robots={"x": 1})
    data["locations"]["teleporters"] = ["X:\\"]
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("setup.json", json.dumps(data))
    s = L.read_setup(str(p))
    assert any("newer app" in n and "robots" in n for n in s.notes)
    assert any("teleporters" in n for n in s.notes)


def test_a_file_over_the_size_limit_is_named(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "MAX_FILE", 10)
    p = tmp_path / "big.frsetup"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("setup.json", json.dumps(_setup().to_data()))
        zf.writestr("Logos/huge.png", "x" * 100)
    with pytest.raises(L.SetupError, match="'Logos/huge.png' is"):
        L.read_setup(str(p))


def test_bad_id_and_level(tmp_path):
    p = tmp_path / "x.frsetup"
    for data, msg in (({"format": L.FORMAT, "id": ""}, "no valid id"),
                      ({"format": L.FORMAT, "id": "a b/c"}, "no valid id"),
                      ({"format": L.FORMAT, "id": "ok", "level": "mine"}, "neither company nor department")):
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("setup.json", json.dumps(data))
        with pytest.raises(L.SetupError, match=msg):
            L.read_setup(str(p))


# ---------------------------------------------------------------------------------------------------------------------
# folders, merging

def test_resolve_relative_unc_and_absolute(tmp_path):
    base = str(tmp_path / "synced")
    assert L.resolve("Logos", base) == os.path.join(base, "Logos")
    assert L.resolve("..\\Shared/Rule sets", base) == os.path.normpath(os.path.join(base, "..", "Shared", "Rule sets"))
    assert L.resolve("\\\\server\\share\\x", base) == "\\\\server\\share\\x"
    assert L.resolve("C:\\Fresing\\x", base) == "C:\\Fresing\\x"
    assert L.resolve("/abs/x", base) == "/abs/x"


def test_locations_order_company_department_mine():
    st = L.empty_state()
    st["mine"]["logos"] = [{"path": "/mine/logos", "on": True}, {"path": "/mine/off", "on": False}]
    dep = (_setup("dep", level="department", label="Offshore", locations={"logos": ["/dep/logos"]}), "/d", "")
    com = (_setup("com", locations={"logos": ["/com/logos"]}, content={"logos": ["a.png"]}), "/c", "/unpacked/com")
    locs = L.locations(st, [dep, com], "logos")
    assert [(x.badge, x.path) for x in locs] == [("Company", os.path.join("/unpacked/com", "Logos")),
                                                 ("Company", "/com/logos"), ("Offshore", "/dep/logos"),
                                                 ("Mine", "/mine/logos")]
    assert locs[0].packed and not locs[1].packed
    assert len(L.locations(st, [dep, com], "logos", include_off=True)) == 5


def test_same_names_both_kept_with_badges():
    a = L.Loc("rule_sets", "/c", "company", "Company", "c")
    b = L.Loc("rule_sets", "/m", "mine", "Mine", "mine")
    merged = L.merge([("Fresing", b, 1), ("acme", a, 2), ("Fresing", a, 3)])
    assert [(n, loc.badge) for n, loc, _p in merged] == [("acme", "Company"), ("Fresing", "Company"),
                                                         ("Fresing", "Mine")]
    assert L.unique_keys([("Fresing", "Company"), ("Fresing", "Mine"), ("fresing", "Mine")]) == \
        ["Fresing", "Fresing (Mine)", "fresing (Mine 2)"]


def test_writable(tmp_path, monkeypatch):
    assert L.writable(str(tmp_path / "not yet" / "there"))         # the first folder above it that exists counts
    ro = tmp_path / "ro"
    ro.mkdir()
    real = os.access
    monkeypatch.setattr(L.os, "access", lambda p, m: False if os.path.abspath(p) == str(ro) else real(p, m))
    assert not L.writable(str(ro))
    assert not L.writable(str(ro / "sub"))


def test_an_unreachable_folder_is_never_waited_for(tmp_path, monkeypatch):
    slow = str(tmp_path / "server")
    monkeypatch.setenv(L.SLOW_ENV, f"{slow}=1.5")
    r = L.Reach(wait=0.05, timeout=0.5)
    t0 = time.monotonic()
    assert r.state(slow) is None                 # being looked at
    assert r.state(str(tmp_path)) is True        # a local folder answers at once
    assert time.monotonic() - t0 < 0.4
    time.sleep(0.6)
    assert r.state(slow) is False                # no answer within the time-out: not there
    r.settle([slow], timeout=3)
    assert r.state(slow) is False                # the late answer: not there


# ---------------------------------------------------------------------------------------------------------------------
# the state file, the migration

def test_migration_with_a_library_folder(tmp_path):
    st = L.empty_state()
    made = L.migrate(st, "\\\\server\\Library", str(tmp_path / "Docs"), has_setups=False)
    assert made == []
    assert st["mine"]["backgrounds"] == [{"path": os.path.join("\\\\server\\Library", "HDRI"), "on": True,
                                          "ready": False}]
    assert all(len(st["mine"][k]) == 1 for k in L.KIND_KEYS)
    assert L.migrate(st, "", "x", False) == []           # once only


def test_migration_without_one_makes_the_ready_made_folders(tmp_path):
    docs = tmp_path / "Docs"
    (docs / "Fresing Render" / "Rule sets").mkdir(parents=True)
    (docs / "Fresing Render" / "Rule sets" / "old.json").write_text("{}")
    st = L.empty_state()
    made = L.migrate(st, "", str(docs), has_setups=False)
    root = os.path.join(str(docs), "Fresing Render", "Library")
    assert os.path.join(root, "Lifting equipment") in made
    assert st["mine"]["lifting"] == [{"path": os.path.join(root, "Lifting equipment"), "on": True, "ready": True}]
    assert [f["path"] for f in st["mine"]["rule_sets"]] == [os.path.join(root, "Rule sets"),
                                                            os.path.join(str(docs), "Fresing Render", "Rule sets")]
    assert not st["note_off"]


def test_migration_with_a_setup_first_makes_them_off(tmp_path):
    st = L.empty_state()
    L.migrate(st, "", str(tmp_path), has_setups=True)
    assert all(not f["on"] for k in L.KIND_KEYS for f in st["mine"][k])
    assert st["note_off"]


def test_state_file_round_trip_and_damaged(tmp_path):
    p = str(tmp_path / "loc é" / L.STATE_FILE)
    st = L.empty_state()
    st["mine"]["logos"].append({"path": "/x", "on": False, "ready": False})
    st["exports"]["own"].append({"name": "Marketing", "path": "/m", "project_sub": False})
    L.write_state(p, st)
    back, note = L.read_state(p)
    assert note == "" and back["mine"]["logos"] == st["mine"]["logos"]
    assert back["exports"]["own"][0]["project_sub"] is False
    with open(p, "w") as fh:
        fh.write("{ not json")
    back, note = L.read_state(p)
    assert "could not be read" in note and back["mine"]["logos"] == []
    assert os.path.isfile(p + ".damaged")


# ---------------------------------------------------------------------------------------------------------------------
# export places

def test_place_folders(tmp_path):
    st = L.empty_state()
    st["exports"]["own"].append({"name": "Mine flat", "path": "/flat", "project_sub": False})
    sets = [(_setup(exports=[{"name": "Marketing", "path": "Exports", "project_sub": True}]), "/share", "")]
    places = L.places(st, sets)
    assert [p.key for p in places] == ["project", "pictures", "acme01:Marketing", "mine:Mine flat"]
    proj = "/work/Crane.blend"
    pics = "/home/u/Pictures"
    f = {p.key: L.place_folder(p, proj, "Crane", pics) for p in places}
    assert f["project"] == "/work/Renders"
    assert f["pictures"] == os.path.join(pics, "Fresing Render", "Crane")
    assert f["acme01:Marketing"] == os.path.join("/share", "Exports", "Crane")
    assert f["mine:Mine flat"] == "/flat"
    assert L.place_folder(places[0], "", "", pics) == os.path.join(pics, "Fresing Render")   # never saved: as before


def test_copy_output_never_overwrites(tmp_path):
    src = tmp_path / "a.png"
    src.write_text("1")
    dst = tmp_path / "share"
    c1 = L.copy_output(str(src), str(dst))
    c2 = L.copy_output(str(src), str(dst))
    assert os.path.basename(c1) == "a.png" and os.path.basename(c2) == "a_2.png"
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "0001.png").write_text("f")
    c3 = L.copy_output(str(frames), str(dst))
    assert os.path.isfile(os.path.join(c3, "0001.png"))


def test_safe_folder():
    assert L.safe_folder('Crane: "v2"/A') == "Crane_ _v2_A"
    assert L.safe_folder("   ") == "Project"


# ---------------------------------------------------------------------------------------------------------------------
# different from standard

def test_differences_name_where_each_comes_from():
    st = L.empty_state()
    st["mine"]["logos"] = [{"path": "/ready", "on": True, "ready": True}, {"path": "/own", "on": True}]
    st["exports"]["default"] = "pictures"
    com = (_setup(version=4, settings={"default_rule_set": "Acme"}, locations={"logos": ["/c"]}), "/", "")
    rows = L.differences({"default_rule_set": "Acme", "keep_howto": True, "backup_minutes": 5},
                         {"default_rule_set": "Standard", "keep_howto": False, "backup_minutes": 5}, [com], st)
    by = {(r.what, r.value): r for r in rows}
    assert by[("default_rule_set", "Acme")].source == "Company v4" and not by[("default_rule_set", "Acme")].own
    assert by[("keep_howto", "on")].source == "Mine" and by[("keep_howto", "on")].own
    assert ("Logos", "/c") in by and ("Logos", "/own") in by and ("Logos", "/ready") not in by
    assert by[("Default export place", "pictures")].own
    assert not any(r.what == "backup_minutes" for r in rows)
