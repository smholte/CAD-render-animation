"""Independent tests of task 0272's locations (written by a reviewer who did not write the code, from the brief).

They try to break ``core/locations.py`` and ``blender/locations.py`` – above all the Windows parts that cannot run
here: zip names that would leave the set-up's folder on Windows, UNC / mapped-drive / relative paths (``ntpath`` stands
in for Windows where a function only does path text), ``file:`` update addresses, a server that does not answer.
A test marked ``xfail(strict=True)`` shows a fault that is still there (FINDING n in the reviewer's report)."""

import ntpath
import os
import threading
import time
import types
import zipfile

import pytest

from fresing_render.core import locations as L


# ---------------------------------------------------------------------------------------------------------------------
# helpers

def _zip(path, names, setup=None):
    """A set-up file with these entries (name -> bytes) and a valid setup.json."""
    import json
    data = setup or {"format": L.FORMAT, "id": "acme", "name": "Company", "level": "company", "version": 1}
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(L.SETUP_JSON, json.dumps(data))
        for n, b in names.items():
            zf.writestr(zipfile.ZipInfo(n), b)
    return str(path)


def _windows_os(monkeypatch, environ=None):
    """``L.os`` as on Windows for path text (ntpath); file calls still go to the real os."""
    fake = types.SimpleNamespace(**{k: getattr(os, k) for k in ("listdir", "makedirs", "replace", "remove",
                                                              "access", "W_OK", "walk", "stat", "close")})
    fake.path = ntpath
    fake.sep = "\\"
    fake.name = "nt"
    fake.environ = os.environ if environ is None else environ
    monkeypatch.setattr(L, "os", fake)
    return fake


# ---------------------------------------------------------------------------------------------------------------------
# zip names: what the checks refuse (these pass)

@pytest.mark.parametrize("bad", [
    "/etc/evil.png", "\\Windows\\evil.png", "C:evil.png", "C:\\evil.png", "c:/evil.png",
    "\\\\server\\share\\evil.png", "//server/share/evil.png", "\\\\?\\C:\\evil.png", "\\\\.\\C:\\evil.png",
    "Logos/../../evil.png", "Logos\\..\\..\\evil.png", "..\\evil.png", "Logos/sub/../../../evil.png",
])
def test_absolute_and_climbing_names_are_refused_before_anything_is_written(tmp_path, bad):
    dest = tmp_path / "unpacked é"
    (dest / "Logos").mkdir(parents=True)
    (dest / "Logos" / "old.png").write_bytes(b"old")
    f = _zip(tmp_path / "bad.frsetup", {"Logos/ok.png": b"x", bad: b"evil"})
    with pytest.raises(L.SetupError, match="refused"):
        L.read_setup(f)
    with pytest.raises(L.SetupError):
        L.unpack(f, str(dest))
    assert (dest / "Logos" / "old.png").read_bytes() == b"old"          # a refused file leaves the old content
    assert not (tmp_path / "evil.png").exists()


def test_backslash_names_unpack_into_their_kind(tmp_path):
    f = _zip(tmp_path / "Firma Ølsen.frsetup", {"Logos\\sub dir\\a é.png": b"a", "Rule sets/x.json": b"{}"})
    s = L.read_setup(f)
    assert s.content == {"logos": ["sub dir/a é.png"], "rule_sets": ["x.json"]}
    out = L.unpack(f, str(tmp_path / "dest ü"))
    assert (tmp_path / "dest ü" / "Logos" / "sub dir" / "a é.png").read_bytes() == b"a"
    assert set(out) == {"logos", "rule_sets"}


def test_the_drive_trick_really_leaves_the_folder_on_windows():
    """Why FINDING 1 matters: on Windows a later component with another drive throws the folder away."""
    target = ntpath.join("C:\\Users\\Ann\\config\\fresing_setups\\acme", "Logos", "D:", "evil.exe")
    assert ntpath.splitdrive(target)[0] == "D:"


def test_a_drive_letter_inside_a_name_is_refused():
    assert L._bad_name("Logos/D:/evil.exe")


@pytest.mark.parametrize("name", ["Logos/a.png:hidden", "Logos/CON", "Logos/nul.png", "Logos/COM1.txt",
                                  "Logos/a.png.", "Logos/a.png ", "Logos/.. /x.png", "Logos/a<b>.png",
                                  "Logos/a?.png"])
def test_names_windows_cannot_hold_are_refused(tmp_path, name):
    f = _zip(tmp_path / "w.frsetup", {name: b"x"})
    with pytest.raises(L.SetupError):
        L.read_setup(f)


def test_names_that_differ_only_in_case_are_refused_or_kept_apart(tmp_path):
    f = _zip(tmp_path / "c.frsetup", {"Logos/Acme.png": b"1", "logos/acme.png": b"2"})
    with pytest.raises(L.SetupError):
        L.read_setup(f)


def test_a_folder_entry_with_a_backslash_is_a_folder(tmp_path):
    f = _zip(tmp_path / "ps.frsetup", {"Logos\\": b"", "Logos\\acme.png": b"x"})
    s = L.read_setup(f)
    assert s.content == {"logos": ["acme.png"]}


def test_a_failed_unpack_keeps_the_old_content(tmp_path, monkeypatch):
    dest = tmp_path / "acme"
    old = _zip(tmp_path / "old.frsetup", {"Logos/old.png": b"old"})
    L.unpack(old, str(dest))
    new = _zip(tmp_path / "new.frsetup", {"Logos/a.png": b"a", "Logos/b.png": b"b"})
    import shutil
    real, calls = shutil.copyfileobj, []

    def flaky(src, dst, *a):
        calls.append(1)
        if len(calls) == 2:
            raise PermissionError(13, "The process cannot access the file because it is being used")
        return real(src, dst, *a)
    monkeypatch.setattr(shutil, "copyfileobj", flaky)
    with pytest.raises(OSError):
        L.unpack(new, str(dest))
    assert (dest / "Logos" / "old.png").read_bytes() == b"old"


def test_windows_system_files_are_not_packed(tmp_path):
    src = tmp_path / "logos"
    src.mkdir()
    for n in ("acme.png", "Thumbs.db", "desktop.ini"):
        (src / n).write_bytes(b"x")
    s = L.Setup(id="acme", name="Company")
    L.write_setup(str(tmp_path / "c.frsetup"), s, {"logos": str(src)})
    assert s.content == {"logos": ["acme.png"]}


# ---------------------------------------------------------------------------------------------------------------------
# folders in a set-up, as Windows reads them

def test_relative_folders_on_a_share_stay_on_the_share(monkeypatch):
    _windows_os(monkeypatch)
    base = "\\\\server\\share\\Fresing set-ups"
    assert L.resolve("Logos", base) == "\\\\server\\share\\Fresing set-ups\\Logos"
    assert L.resolve("..\\Company Logos", base) == "\\\\server\\share\\Company Logos"
    assert L.resolve("../Rule sets/Offshore", base) == "\\\\server\\share\\Rule sets\\Offshore"
    assert L.resolve("..\\..\\..\\x", base).startswith("\\\\server\\share")      # never above the share
    assert L.resolve("X:\\Fresing\\Logos", base) == "X:\\Fresing\\Logos"
    assert L.resolve("x:/Fresing/Logos", base) == "x:/Fresing/Logos"
    assert L.resolve("\\\\other\\lib$\\Logos", base) == "\\\\other\\lib$\\Logos"      # a hidden share keeps its $


def test_a_synced_folder_relative_path(monkeypatch):
    _windows_os(monkeypatch)
    base = "C:\\Users\\Åsa Ölund\\OneDrive - Acme AS\\Fresing"
    assert L.resolve("..\\Shared Logos", base) == "C:\\Users\\Åsa Ölund\\OneDrive - Acme AS\\Shared Logos"


def test_environment_variables_in_a_setup_folder(monkeypatch):
    monkeypatch.setenv("FR_TEST_SHARE", "\\\\srv\\lib")
    _windows_os(monkeypatch)
    assert L.resolve("%FR_TEST_SHARE%\\Logos", "C:\\x") == "\\\\srv\\lib\\Logos"


def test_a_drive_relative_folder_comes_out_absolute(monkeypatch):
    _windows_os(monkeypatch)
    assert ntpath.isabs(L.resolve("X:Logos", "\\\\server\\share\\setups"))


def test_same_path_ignores_case_and_slashes_on_windows(monkeypatch):
    _windows_os(monkeypatch)
    assert L.same_path("C:\\Library\\Logos", "c:/library/logos/")
    assert L.same_path("\\\\Server\\Share\\Logos", "//server/share/Logos")
    assert not L.same_path("C:\\Library\\Logos", "C:\\Library\\Logos 2")


def test_migration_of_a_unc_library_folder(monkeypatch):
    _windows_os(monkeypatch)
    st = L.empty_state()
    assert L.migrate(st, "\\\\server\\Fresing lib", "C:\\Users\\A\\Documents", False) == []
    assert st["mine"]["backgrounds"][0]["path"] == "\\\\server\\Fresing lib\\HDRI"
    assert st["mine"]["rule_sets"][0]["path"] == "\\\\server\\Fresing lib\\Rule sets"
    assert L.migrate(st, "", "C:\\Users\\A\\Documents", False) == []              # once only


def test_place_folders_on_windows(monkeypatch):
    _windows_os(monkeypatch)
    pics = "D:\\OneDrive - Acme\\Bilder"
    proj = "\\\\srv\\Projects\\Kran é\\Kran é.blend"
    assert L.place_folder(L.Place("project", "", ""), proj, "Kran é", pics) == "\\\\srv\\Projects\\Kran é\\Renders"
    assert L.place_folder(L.Place("pictures", "", ""), proj, "Kran é", pics) == "D:\\OneDrive - Acme\\Bilder\\" \
                                                                                 "Fresing Render\\Kran é"
    m = L.Place("acme:Marketing", "Marketing", "\\\\srv\\Marketing share")
    assert L.place_folder(m, proj, "Kran: v2?", pics) == "\\\\srv\\Marketing share\\Kran_ v2_"


@pytest.mark.parametrize("name", ["con", "NUL", "COM1", "lpt1", "Aux.blend"])
def test_safe_folder_avoids_reserved_names(name):
    assert L.safe_folder(name).split(".")[0].upper() not in {"CON", "NUL", "COM1", "LPT1", "AUX", "PRN"}


def test_copy_output_into_a_folder_with_spaces_and_accents(tmp_path):
    src = tmp_path / "Renders" / "Kran é.png"
    src.parent.mkdir()
    src.write_bytes(b"png")
    frames = tmp_path / "Renders" / "Kran frames"
    frames.mkdir()
    (frames / "0001.png").write_bytes(b"1")
    dest = tmp_path / "Marketing share ü" / "Kran é"
    a = L.copy_output(str(src), str(dest))
    b = L.copy_output(str(src), str(dest))
    c = L.copy_output(str(frames) + os.sep, str(dest))
    assert os.path.basename(a) == "Kran é.png" and os.path.basename(b) == "Kran é_2.png"
    assert os.path.isfile(os.path.join(c, "0001.png"))


def test_writable_does_not_trust_os_access_alone(monkeypatch):
    monkeypatch.setattr(L.os, "access", lambda p, m: True)      # what Windows answers for any folder
    assert not L.writable("/proc/1")                              # a folder no file can be made in


def test_write_state_round_trip_with_accents(tmp_path):
    p = tmp_path / "config ü" / L.STATE_FILE
    st = L.empty_state()
    st["mine"]["logos"].append({"path": "\\\\srv\\Logos é", "on": True, "ready": False})
    L.write_state(str(p), st)
    back, note = L.read_state(str(p))
    assert note == "" and back["mine"]["logos"][0]["path"] == "\\\\srv\\Logos é"


def test_write_state_cleans_up_when_the_file_is_held(tmp_path, monkeypatch):
    p = tmp_path / L.STATE_FILE
    monkeypatch.setattr(L.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError(13, "held")))
    with pytest.raises(OSError):
        L.write_state(str(p), L.empty_state())
    assert not (tmp_path / (L.STATE_FILE + ".tmp")).exists()


# ---------------------------------------------------------------------------------------------------------------------
# reachable or not

def test_reach_never_blocks_and_takes_a_late_answer(tmp_path, monkeypatch):
    slow = tmp_path / "slow server"
    slow.mkdir()
    monkeypatch.setenv(L.SLOW_ENV, f"{slow}=0.4")
    r = L.Reach(timeout=0.1, wait=0.01)
    t0 = time.monotonic()
    assert r.state(str(slow)) is None
    assert time.monotonic() - t0 < 0.1
    time.sleep(0.15)
    assert r.state(str(slow)) is False                 # no answer in time
    time.sleep(0.4)
    assert r.state(str(slow)) is True                  # the late answer counts


def test_many_calls_from_threads_at_once(tmp_path):
    r = L.Reach(wait=0.0)
    dirs = [str(tmp_path / f"d{i}") for i in range(20)]
    for d in dirs[::2]:
        os.mkdir(d)
    errors = []

    def ask():
        try:
            for _ in range(20):
                for d in dirs:
                    r.state(d)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
    ts = [threading.Thread(target=ask) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    r.settle(dirs, timeout=3)
    assert not errors
    assert [r.state(d) for d in dirs] == [i % 2 == 0 for i in range(20)]


def test_a_dead_server_does_not_starve_local_folders(tmp_path, monkeypatch):
    dead = str(tmp_path / "dead server")
    monkeypatch.setenv(L.SLOW_ENV, f"{dead}=2")
    local = tmp_path / "Documents" / "Logos"
    local.mkdir(parents=True)
    r = L.Reach(timeout=0.3, wait=0.0)
    for k in ("Logos", "Stickers", "Rule sets", "HDRI"):
        r.state(os.path.join(dead, k))
    r.state(str(local))
    time.sleep(0.5)
    assert r.state(str(local)) is True


# ---------------------------------------------------------------------------------------------------------------------
# the Blender side

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402


@pytest.fixture(scope="module")
def addon():
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture()
def loc(addon, tmp_path, monkeypatch):
    from fresing_render.blender import locations, prefs
    monkeypatch.setenv(locations.ENV, str(tmp_path / "config é" / L.STATE_FILE))
    monkeypatch.delenv(locations.ENV_SETUP_FOLDER, raising=False)
    monkeypatch.delenv("FRESING_UPDATE_URL", raising=False)
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs ü"))
    for k in ("FRESING_RULE_SETS_DIR", "FRESING_WORKSPACES_DIR", "FRESING_BRAND_KITS_DIR"):
        monkeypatch.delenv(k, raising=False)
    p = prefs.get()
    p.library_path = ""
    locations.forget()
    yield locations
    p.library_path = ""
    locations.forget()


def _approved(monkeypatch, loc, url):
    from fresing_render.blender import updates
    monkeypatch.setattr(updates, "index_url", lambda: (url, "test"))
    fake = types.SimpleNamespace(name="nt", path=os.path, environ={})
    monkeypatch.setattr(loc, "os", fake)
    try:
        return loc.approved_folder().replace("\\", "/")
    finally:
        monkeypatch.setattr(loc, "os", os)


def test_approved_folder_from_file_addresses(loc, monkeypatch):
    assert _approved(monkeypatch, loc, "file:///C:/Fresing%20R%C3%A9/approved/index.json") == \
        "C:/Fresing Ré/approved"
    assert _approved(monkeypatch, loc, "file://SERVER/share/fresing/index.json") == "//SERVER/share/fresing"
    assert _approved(monkeypatch, loc, "file:////SERVER/share/fresing/index.json") == "//SERVER/share/fresing"
    assert _approved(monkeypatch, loc, "https://github.com/x/index.json") == ""


def test_approved_folder_agrees_with_the_update_reader(loc, monkeypatch):
    assert _approved(monkeypatch, loc, "file://localhost/C:/Fresing/index.json") == "C:/Fresing"
    assert _approved(monkeypatch, loc, "ftp://server/fresing/index.json") == ""


def test_the_approved_folder_is_never_waited_for(loc, tmp_path, monkeypatch):
    dead = str(tmp_path / "dead server")
    from fresing_render.blender import updates
    monkeypatch.setattr(updates, "index_url", lambda: (os.path.join(dead, "fresing", "index.json"), "test"))
    loc.load()
    real = os.path.isdir

    def slow(p):
        if str(p).startswith(dead):
            time.sleep(1.0)
        return real(p)
    monkeypatch.setattr(os.path, "isdir", slow)
    t0 = time.monotonic()
    loc.refresh()
    assert time.monotonic() - t0 < 0.5


def test_pick_up_does_not_read_known_setups_again(loc, tmp_path, monkeypatch):
    it = tmp_path / "IT share é"
    it.mkdir()
    L.write_setup(str(it / "Company.frsetup"), L.Setup(id="acme", name="Company"))
    monkeypatch.setenv(loc.ENV_SETUP_FOLDER, str(it))
    loc.load()
    assert [e["id"] for e in loc.state()["setups"]] == ["acme"]
    reads = []
    real = L.read_setup

    def counting(p):
        if str(p).startswith(str(it)):
            reads.append(p)
        return real(p)
    monkeypatch.setattr(L, "read_setup", counting)
    loc.refresh()
    loc.refresh()
    assert reads == []


def _relative_setup(tmp_path):
    synced = tmp_path / "OneDrive - Acme AS"
    logos = synced / "Shared Logos"
    logos.mkdir(parents=True)
    (logos / "acme.png").write_bytes(b"x")
    (synced / "Fresing").mkdir()
    f = str(synced / "Fresing" / "Company.frsetup")
    L.write_setup(f, L.Setup(id="acme", name="Company", locations={"logos": ["..\\Shared Logos"]}))
    return f, str(logos)


def test_a_relative_folder_of_a_linked_setup(loc, tmp_path):
    f, logos = _relative_setup(tmp_path)
    loc.load()
    loc.install(f, "link")
    loc.wait_reach()
    assert logos in loc.paths("logos")


def test_a_relative_folder_of_a_copied_setup(loc, tmp_path):
    f, logos = _relative_setup(tmp_path)
    loc.load()
    loc.install(f)                                     # Auto: a local path is copied
    loc.wait_reach()
    assert logos in loc.paths("logos")


def test_items_of_an_unreachable_folder_are_left_out_quickly(loc, tmp_path, monkeypatch):
    dead = str(tmp_path / "dead server")
    monkeypatch.setenv(L.SLOW_ENV, f"{dead}=2")
    loc.load()
    loc.wait_reach()
    for k in ("logos", "stickers", "rule_sets", "templates"):
        loc.add_mine(k, os.path.join(dead, k))
    t0 = time.monotonic()
    for _ in range(3):
        loc.items("logos", (".png",))
        loc.save_choices("rule_sets")
    assert time.monotonic() - t0 < 1.0


def test_badge_of_a_file_beside_a_folder_with_a_longer_name(loc, tmp_path):
    loc.load()
    a = tmp_path / "Logos"
    b = tmp_path / "Logos 2"
    a.mkdir()
    b.mkdir()
    loc.set_mine_root("")
    loc.add_mine("logos", str(a))
    loc.wait_reach()
    assert loc.badge_of(str(a / "x.png"), "logos") == "Mine"
    assert loc.badge_of(str(b / "x.png"), "logos") == ""          # 'Logos 2' is not inside 'Logos'
