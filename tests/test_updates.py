"""Updates from GitHub without Blender: versions, listing, changelog, download, the update helper (task 0020)."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import textwrap
import time
import zipfile

import pytest

from fresing_render import __version__, update_helper
from fresing_render.core import updates as U

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---- versions ----------------------------------------------------------------------------

def test_version_order():
    assert U.is_newer("0.2.14", "0.2.13")
    assert U.is_newer("0.10.0", "0.9.9")                  # numbers, not text
    assert U.is_newer("1.0", "0.99.99")
    assert not U.is_newer("0.2.13", "0.2.13")
    assert not U.is_newer("0.3", "0.3.0")                 # 0.3 == 0.3.0
    assert U.is_newer("0.2.14", "0.2.14-rc.1")            # a release is newer than its pre-release
    assert U.is_newer("0.2.14-rc.1", "0.2.13")
    assert U.is_newer("v0.2.14", "0.2.13")                # tag names
    assert U.is_newer("0.0.1", "nonsense")                # unreadable sorts lowest


# ---- listing -----------------------------------------------------------------------------

def _item(version, platforms=("windows-x64",), lo="5.2.0", hi="5.3.0", url=None):
    return {"id": "fresing_render", "version": version, "platforms": list(platforms), "blender_version_min": lo,
            "blender_version_max": hi, "archive_url": url or f"./fresing_render-{version}.zip",
            "archive_size": 3, "archive_hash": "sha256:" + "ab" * 32}


def test_pick_package_filters_platform_and_blender():
    index = {"data": [_item("0.2.14"), _item("0.2.15", platforms=("linux-x64",)),
                      _item("0.3.0", lo="5.3.0", hi="5.4.0"), {"id": "other", "version": "9.0.0"}]}
    best, newest = U.pick_package(index, platform_name="windows-x64", blender_version=(5, 2, 3))
    assert best["version"] == "0.2.14"
    assert newest["version"] == "0.3.0"                    # exists, but needs a newer Blender
    best, _ = U.pick_package(index, platform_name="linux-x64", blender_version=(5, 2, 3))
    assert best["version"] == "0.2.15"
    best, _ = U.pick_package(index, platform_name="windows-x64", blender_version=(5, 3, 1))
    assert best["version"] == "0.3.0"
    assert U.pick_package({}, platform_name="windows-x64") == (None, None)


def test_archive_url_relative_and_absolute():
    idx = "https://github.com/a/b/releases/latest/download/index.json"
    assert U.archive_url(idx, "./fresing_render-1.zip") == "https://github.com/a/b/releases/latest/download/fresing_render-1.zip"
    assert U.archive_url("https://x/repo/", "./z.zip") == "https://x/repo/z.zip"
    assert U.archive_url("https://x/repo", "./z.zip") == "https://x/repo/z.zip"
    assert U.archive_url(idx, "https://y/z.zip") == "https://y/z.zip"
    assert U.sibling_url("file:///C:/share/index.json", "changelog.json") == "file:///C:/share/changelog.json"
    assert U.sha256_of({"archive_hash": "sha256:ABC"}) == "abc"
    assert U.sha256_of({}) == ""


def test_release_page():
    assert U.release_page("0.2.14", U.DEFAULT_INDEX_URL) == U.RELEASES_PAGE + "/tag/v0.2.14"
    assert U.release_page("", U.DEFAULT_INDEX_URL) == U.RELEASES_PAGE
    assert U.release_page("0.2.14", "file:///srv/fresing/index.json") == "file:///srv/fresing/"


# ---- changelog ---------------------------------------------------------------------------

def test_parse_changelog_of_this_repository():
    entries = U.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert entries[0]["version"] == __version__, "the newest CHANGELOG entry must be the version being built"
    versions = [e["version"] for e in entries]
    assert len(versions) == len(set(versions)) >= 10
    assert all(U.is_newer(a, b) for a, b in zip(versions, versions[1:])), "newest first"
    for e in entries:
        assert e["date"] and e["text"], e["version"]
        assert "Commit `" not in e["text"]                # developers' line left out


def test_changelog_text_and_whats_new():
    md = textwrap.dedent("""\
        # Changelog

        Intro text.

        ## 0.2.15 – 6 Nov 2026 – updates in the app (task 0020)

        Commit `abc1234`.

        Panel 1
        - **Update now** in the Fresing tab: saves, closes, updates
          and opens again.
        - Uses `index.json` from [GitHub](https://github.com).

        **Once by hand:** run this installer once
        over the old version.

        ## 0.2.14 – 5 Nov 2026 – something

        - A thing.

        ## 0.2.13 – 5 Nov 2026

        - Older.
        """)
    entries = U.parse_changelog(md)
    assert [e["version"] for e in entries] == ["0.2.15", "0.2.14", "0.2.13"]
    assert entries[0]["date"] == "6 Nov 2026" and entries[0]["title"] == "updates in the app (task 0020)"
    assert entries[2]["title"] == ""
    picked = U.changes_between(entries, "0.2.13", "0.2.15")
    assert [e["version"] for e in picked] == ["0.2.15", "0.2.14"]
    paras = U.whats_new_paragraphs(picked)
    assert paras[0][0] == "0.2.15 – updates in the app (task 0020)"
    assert paras[0][1] == ["Panel 1", "• Update now in the Fresing tab: saves, closes, updates and opens again.",
                           "• Uses index.json from GitHub.", "Once by hand: run this installer once over the old version."]


# ---- check (file:// addresses work like https://) -------------------------------------------

def _make_repo(tmp_path, items, changelog=None):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "index.json").write_text(json.dumps({"version": "v1", "blocklist": [], "data": items}), encoding="utf-8")
    if changelog is not None:
        (repo / "changelog.json").write_text(json.dumps({"versions": changelog}), encoding="utf-8")
    return repo, (repo / "index.json").as_uri()


def test_check_available_with_whats_new(tmp_path):
    log = [{"version": "0.2.16", "date": "7 Nov 2026", "title": "", "text": "- c"},
           {"version": "0.2.15", "date": "6 Nov 2026", "title": "", "text": "- b"},
           {"version": "0.2.14", "date": "5 Nov 2026", "title": "", "text": "- a"}]
    repo, url = _make_repo(tmp_path, [_item("0.2.15"), _item("0.2.14")], log)
    res = U.check(url, "0.2.14", (5, 2, 3), platform_name="windows-x64")
    assert res["state"] == "available" and res["version"] == "0.2.15"
    assert res["url"] == (repo / "fresing_render-0.2.15.zip").as_uri()
    assert res["sha256"] == "ab" * 32 and res["size"] == 3
    assert [c["version"] for c in res["changes"]] == ["0.2.15"] and res["date"] == "6 Nov 2026"


def test_check_none_needs_installer_and_errors(tmp_path):
    _repo, url = _make_repo(tmp_path, [_item("0.2.14")])          # no changelog.json: still fine
    assert U.check(url, "0.2.14", (5, 2, 3), platform_name="windows-x64")["state"] == "none"
    assert U.check(url, "0.2.15", (5, 2, 3), platform_name="windows-x64")["state"] == "none"   # newer installed
    res = U.check(url, "0.2.13", (5, 2, 3), platform_name="windows-x64")
    assert res["state"] == "available" and res["changes"] == []
    _repo, url = _make_repo(tmp_path, [_item("0.3.0", lo="5.3.0", hi="5.4.0")])
    res = U.check(url, "0.2.14", (5, 2, 3), platform_name="windows-x64")
    assert res["state"] == "needs_installer" and res["version"] == "0.3.0"
    res = U.check((tmp_path / "nothing" / "index.json").as_uri(), "0.2.14", (5, 2, 3))
    assert res["state"] == "error" and "could not reach" in res["message"]
    (tmp_path / "bad.json").write_text("<html>not json", encoding="utf-8")
    res = U.check((tmp_path / "bad.json").as_uri(), "0.2.14", (5, 2, 3))
    assert res["state"] == "error" and res["message"] == "the update listing could not be read"
    _repo, url = _make_repo(tmp_path, [{"id": "else", "version": "1.0.0"}])
    assert "no Fresing Render" in U.check(url, "0.2.14", (5, 2, 3))["message"]


def test_describe_http_errors():
    import socket
    import urllib.error
    assert "HTTP 404" in U.describe_error(urllib.error.HTTPError("u", 404, "nf", {}, None))
    assert "HTTP 503" in U.describe_error(urllib.error.HTTPError("u", 503, "x", {}, None))
    assert "time-out" in U.describe_error(urllib.error.URLError(socket.timeout()))
    assert "time-out" in U.describe_error(TimeoutError())


# ---- download ------------------------------------------------------------------------------

def test_download_checks_size_and_checksum(tmp_path):
    src = tmp_path / "src.zip"
    data = os.urandom(3 * (1 << 20) + 17)
    src.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    seen = []
    dest = tmp_path / "dl" / "got.zip"
    U.download(src.as_uri(), str(dest), size=len(data), sha256=sha, progress=lambda d, t: seen.append((d, t)))
    assert dest.read_bytes() == data and seen[-1] == (len(data), len(data)) and len(seen) >= 3
    with pytest.raises(U.DownloadError, match="damaged"):
        U.download(src.as_uri(), str(tmp_path / "x.zip"), sha256="00" * 32)
    with pytest.raises(U.DownloadError, match="incomplete"):
        U.download(src.as_uri(), str(tmp_path / "y.zip"), size=len(data) + 1)
    with pytest.raises(U.DownloadError, match="stopped"):
        U.download(src.as_uri(), str(tmp_path / "z.zip"), should_stop=lambda: True)
    assert not list(tmp_path.glob("*.part")) and not (tmp_path / "x.zip").exists()


# ---- address ------------------------------------------------------------------------------

def test_update_address_order(tmp_path):
    assert U.index_url_from(str(tmp_path), env={}) == (U.DEFAULT_INDEX_URL, "GitHub")
    (tmp_path / U.URL_FILE).write_bytes(b"\xef\xbb\xbf" + json.dumps({"url": "file://SRV/share/index.json"}).encode())
    url, src = U.index_url_from(str(tmp_path), env={})                   # PowerShell writes a BOM
    assert url == "file://SRV/share/index.json" and src.endswith(U.URL_FILE)
    url, src = U.index_url_from(str(tmp_path), env={U.URL_ENV: "https://x/index.json"})
    assert url == "https://x/index.json" and U.URL_ENV in src
    (tmp_path / U.URL_FILE).write_text("{broken", encoding="utf-8")
    assert U.index_url_from(str(tmp_path), env={})[0] == U.DEFAULT_INDEX_URL


# ---- update helper ------------------------------------------------------------------------

FAKE_BLENDER = r'''#!{python}
# Stands in for "blender --command extension install-file -r REPO -e ZIP" (tests only).
import os, sys, zipfile, shutil
args = sys.argv[1:]
assert args[:3] == ["--command", "extension", "install-file"], args
log = os.environ["FAKE_BLENDER_LOG"]
open(log, "a").write(" ".join(args) + "\n")
if os.environ.get("FAKE_BLENDER_FAIL"):
    print("Error: could not install")
    sys.exit(3)
if os.environ.get("FAKE_BLENDER_BREAK"):      # Blender's own installer removed the old folder, then the swap failed
    shutil.rmtree(os.environ["FAKE_EXT_DIR"], ignore_errors=True)
    print("Error: could not rename the new folder in (in use by another process)")
    sys.exit(1)
ext_dir = os.environ["FAKE_EXT_DIR"]
tmp = ext_dir + "@"
shutil.rmtree(tmp, ignore_errors=True)
with zipfile.ZipFile(args[-1]) as zf:
    zf.extractall(tmp)
shutil.rmtree(ext_dir, ignore_errors=True)
os.rename(tmp, ext_dir)
print("Installed")
'''


def _ext_zip(path, version, template_text):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("blender_manifest.toml", f'id = "fresing_render"\nversion = "{version}"\n')
        zf.writestr("__init__.py", f'__version__ = "{version}"\n')
        zf.writestr(f"{update_helper.TEMPLATE_FILES_DIR}/__init__.py", template_text)
        zf.writestr(f"{update_helper.TEMPLATE_FILES_DIR}/splash.png", b"png")
    return str(path)


@pytest.fixture()
def helper_env(tmp_path, monkeypatch):
    if sys.platform == "win32":
        pytest.skip("the fake Blender is a script with a #! line")
    fake = tmp_path / "blender"
    fake.write_text(FAKE_BLENDER.replace("{python}", sys.executable), encoding="utf-8")
    fake.chmod(0o755)
    ext_dir = tmp_path / "extensions" / "user_default" / "fresing_render"
    ext_dir.mkdir(parents=True)
    (ext_dir / "blender_manifest.toml").write_text('version = "0.2.14"\n', encoding="utf-8")
    tdir = tmp_path / "templates" / "fresing_render"
    tdir.mkdir(parents=True)
    (tdir / "__init__.py").write_text("# old template\n", encoding="utf-8")
    (tdir / "splash.png").write_bytes(b"png")
    (tdir / "__pycache__").mkdir()
    monkeypatch.setenv("FAKE_BLENDER_LOG", str(tmp_path / "fake.log"))
    monkeypatch.setenv("FAKE_EXT_DIR", str(ext_dir))
    marker = tmp_path / "restarted.txt"
    plan = {"blender": str(fake), "wait_pid": 0, "zip": _ext_zip(tmp_path / "dl.zip", "0.2.15", "# new template\n"),
            "expected_version": "0.2.15", "old_version": "0.2.14", "repo": "user_default", "ext_dir": str(ext_dir),
            "template_dir": str(tdir),
            "restart": [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('again')"],
            "status_file": str(tmp_path / "cfg" / "status.json"), "log_file": str(tmp_path / "update.log")}
    return plan, marker


def _status(plan):
    return json.loads(pathlib.Path(plan["status_file"]).read_text(encoding="utf-8"))


def _wait_for(path, seconds=20):
    end = time.time() + seconds
    while time.time() < end and not pathlib.Path(path).exists():
        time.sleep(0.05)
    return pathlib.Path(path).exists()


def test_helper_installs_copies_template_and_restarts(helper_env, tmp_path):
    plan, marker = helper_env
    assert update_helper.run(plan)
    st = _status(plan)
    assert st["ok"] and st["installed"] == "0.2.15" and st["message"] == "Updated to 0.2.15."
    assert update_helper.installed_version(plan["ext_dir"]) == "0.2.15"
    tdir = pathlib.Path(plan["template_dir"])
    assert (tdir / "__init__.py").read_text() == "# new template\n"
    assert not (tdir / "__pycache__").exists()                     # old compiled template gone
    assert not os.path.exists(plan["zip"])                          # download cleaned up
    assert "install-file -r user_default -e" in (tmp_path / "fake.log").read_text()
    assert _wait_for(marker)
    assert "OK: Updated to 0.2.15." in pathlib.Path(plan["log_file"]).read_text()


def test_helper_failure_keeps_old_version_and_still_restarts(helper_env, monkeypatch):
    plan, marker = helper_env
    monkeypatch.setenv("FAKE_BLENDER_FAIL", "1")
    plan["retry_waits"] = [0.1, 0.1]
    assert not update_helper.run(plan)
    st = _status(plan)
    assert not st["ok"] and "exit code 3" in st["message"] and st["installed"] == "0.2.14"
    assert pathlib.Path(plan["template_dir"], "__init__.py").read_text() == "# old template\n"
    assert os.path.exists(plan["zip"])                              # kept for a look in the log
    assert _wait_for(marker)


def test_helper_wrong_version_after_install(helper_env, tmp_path):
    plan, _marker = helper_env
    plan["expected_version"] = "0.2.16"                             # the zip holds 0.2.15
    plan["retry_waits"] = [0.1, 0.1, 0.1]
    t0 = time.time()
    assert not update_helper.run(plan)
    assert "instead of 0.2.16" in _status(plan)["message"]
    assert (tmp_path / "fake.log").read_text().count("install-file") == 4     # tried four times
    assert time.time() - t0 < 30


def test_helper_waits_for_the_app_to_close(helper_env):
    plan, _marker = helper_env
    app = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
    plan["wait_pid"] = app.pid
    t0 = time.time()
    assert update_helper.run(plan)
    assert time.time() - t0 >= 1.4
    app.wait()


def test_helper_gives_up_when_the_app_stays_open(helper_env, tmp_path):
    plan, marker = helper_env
    app = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        plan.update(wait_pid=app.pid, wait_seconds=0.5)
        assert not update_helper.run(plan)
        assert "did not close" in _status(plan)["message"]
        assert not (tmp_path / "fake.log").exists()                 # nothing installed
        assert not marker.exists()                                  # the app is still open: no second one
    finally:
        app.kill()
        app.wait()


def test_helper_main_with_plan_file_and_crash(helper_env, tmp_path):
    plan, marker = helper_env
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    # as the app starts it: a copy of the helper outside the extension, Python in isolated mode
    copy = tmp_path / "run" / "update_helper.py"
    copy.parent.mkdir()
    copy.write_bytes(pathlib.Path(update_helper.__file__).read_bytes())
    proc = subprocess.run([sys.executable, "-I", str(copy), str(plan_file)], capture_output=True, text=True,
                          timeout=60, env=dict(os.environ))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _status(plan)["ok"]
    # a plan without the needed fields: a status that says so, and the app still starts again
    assert _wait_for(marker)
    marker.unlink()
    bad = dict(plan)
    del bad["zip"]
    plan_file.write_text(json.dumps(bad), encoding="utf-8")
    assert update_helper.main([str(plan_file)]) == 1
    assert not _status(plan)["ok"] and "error" in _status(plan)["message"]
    assert _wait_for(marker)


def test_copy_template_only_what_differs(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / "__init__.py").write_text("new", encoding="utf-8")
    (src / "splash.png").write_bytes(b"same")
    (src / "x.pyc").write_bytes(b"compiled")
    assert update_helper.copy_template(str(src), str(dst)) == ["__init__.py", "splash.png"]
    assert update_helper.copy_template(str(src), str(dst)) == []
    assert not (dst / "x.pyc").exists()
    assert update_helper.copy_template(str(tmp_path / "missing"), str(dst)) == []


def test_pid_alive():
    assert update_helper.pid_alive(os.getpid())
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    assert not update_helper.pid_alive(p.pid)
    assert not update_helper.pid_alive(0)


# ---- the build puts the template and the changelog inside the extension ---------------------

def test_stage_extension_contents(tmp_path):
    pytest.importorskip("markdown")
    sys.path.insert(0, str(ROOT / "tools"))
    import build_release
    stage = tmp_path / "stage" / "fresing_render"
    build_release.stage_extension(str(stage), template_src=str(ROOT / "tests" / "data" / "old_app_template"),
                                  version="0.0.1")
    assert (stage / update_helper.TEMPLATE_FILES_DIR / "splash.png").is_file()      # taken from the current one
    assert "user_guide" not in (stage / update_helper.TEMPLATE_FILES_DIR / "__init__.py").read_text(encoding="utf-8")
    assert '__version__ = "0.0.1"' in (stage / "__init__.py").read_text(encoding="utf-8")
    assert 'version = "0.0.1"' in (stage / "blender_manifest.toml").read_text(encoding="utf-8")
    assert 'schema_version = "1.0.0"' in (stage / "blender_manifest.toml").read_text(encoding="utf-8")
    log = json.loads((stage / "changelog.json").read_text(encoding="utf-8"))
    assert log["versions"][0]["version"] == __version__
    assert (stage / "guide" / "user_guide.html").is_file()
    stage2 = tmp_path / "stage2" / "fresing_render"
    build_release.stage_extension(str(stage2))
    assert (stage2 / update_helper.TEMPLATE_FILES_DIR / "__init__.py").read_bytes() == \
        (ROOT / "app_template" / "fresing_render" / "__init__.py").read_bytes()
    assert '__version__ = "' + __version__ in (stage2 / "__init__.py").read_text(encoding="utf-8")


def test_update_repo_with_full_download_address(tmp_path):
    pytest.importorskip("bpy")
    sys.path.insert(0, str(ROOT / "tools"))
    import build_release
    import test_install_linux
    tool = test_install_linux.blender_ext_tool()
    stage = tmp_path / "stage" / "fresing_render"
    build_release.stage_extension(str(stage))
    man = (stage / "blender_manifest.toml").read_text(encoding="utf-8")
    import re
    (stage / "blender_manifest.toml").write_text(re.sub(r"wheels = \[[^\]]*\]", "wheels = []", man, flags=re.S),
                                                 encoding="utf-8")
    subprocess.check_call([sys.executable, tool, "build", "--source-dir", str(stage), "--output-dir", str(tmp_path)])
    ext_zip = next(tmp_path.glob("fresing_render-*.zip"))
    with zipfile.ZipFile(ext_zip) as zf:
        names = zf.namelist()
    assert f"{update_helper.TEMPLATE_FILES_DIR}/__init__.py" in names and "changelog.json" in names
    base = f"https://github.com/{U.REPO}/releases/download/v{__version__}"
    repo = tmp_path / "repo"
    build_release.write_update_repo(str(repo), str(ext_zip), tool, base_url=base)
    index = json.loads((repo / "index.json").read_text(encoding="utf-8"))
    item = index["data"][0]
    assert item["archive_url"] == f"{base}/{ext_zip.name}"
    assert item["archive_hash"] == "sha256:" + hashlib.sha256(ext_zip.read_bytes()).hexdigest()
    assert item["permissions"]["network"]
    assert json.loads((repo / "changelog.json").read_text(encoding="utf-8"))["versions"][0]["version"] == __version__
    # what the app reads from it
    best, _ = U.pick_package(index, platform_name="windows-x64", blender_version=(5, 2, 3))
    assert best["version"] == __version__ and U.archive_url(U.DEFAULT_INDEX_URL, best["archive_url"]) == item["archive_url"]


# ---- the release job ------------------------------------------------------------------------

def test_release_plan():
    sys.path.insert(0, str(ROOT / "tools"))
    import release_tools
    v = release_tools.manifest_version()
    assert v == __version__
    assert release_tools.plan("refs/heads/main", "7", False, exists=lambda tag: False) == \
        {"version": v, "tag": f"v{v}", "prerelease": "false", "publish": "true"}
    assert release_tools.plan("refs/heads/main", "7", False, exists=lambda tag: True)["publish"] == "false"
    assert release_tools.plan("refs/heads/task/x", "42", True, exists=lambda tag: True) == \
        {"version": v, "tag": f"v{v}-rehearsal.42", "prerelease": "true", "publish": "true"}
    assert release_tools.plan("refs/heads/task/x", "42", False)["publish"] == "false"


def test_release_files_and_text(tmp_path):
    sys.path.insert(0, str(ROOT / "tools"))
    import release_tools
    repo = tmp_path / "listing"
    repo.mkdir()
    (repo / f"fresing_render-{__version__}.zip").write_bytes(b"zip")
    (repo / "index.json").write_text(json.dumps({"version": "v1", "data": [
        {"id": "fresing_render", "version": __version__, "archive_url": f"./fresing_render-{__version__}.zip"}]}))
    (repo / "changelog.json").write_text(json.dumps({"versions": []}))
    files = release_tools.prepare(str(repo), str(tmp_path / "out"), f"v{__version__}-rehearsal.3", "o/r")
    assert files == [f"fresing_render-{__version__}.zip", "index.json", "changelog.json"]
    index = json.loads((tmp_path / "out" / "index.json").read_text())
    assert index["data"][0]["archive_url"] == \
        f"https://github.com/o/r/releases/download/v{__version__}-rehearsal.3/fresing_render-{__version__}.zip"
    notes = (tmp_path / "out" / "notes.md").read_text(encoding="utf-8")
    assert "Update now" in notes and f"FresingRender-{__version__}-windows.zip" in notes
    entry = U.parse_changelog((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))[0]
    assert entry["text"].splitlines()[0] in notes


# ---- review findings (task 0020) ----------------------------------------------------------------

def test_local_paths_of_update_addresses():
    lp = U.local_path
    assert lp("https://github.com/x/index.json") == ""
    assert lp("file:///C:/Fresing/update%20listing%20%C3%A9/index.json", windows=True) == \
        "C:\\Fresing\\update listing é\\index.json"
    assert lp("file://SERVER/share/fresing/index.json", windows=True) == "\\\\SERVER\\share\\fresing\\index.json"
    assert lp("file:////SERVER/share/index.json", windows=True) == "\\\\SERVER\\share\\index.json"
    assert lp("file://localhost/C:/x/index.json", windows=True) == "C:\\x\\index.json"
    assert lp("\\\\SERVER\\share\\index.json", windows=True) == "\\\\SERVER\\share\\index.json"     # plain paths
    assert lp("C:\\x\\index.json", windows=True) == "C:\\x\\index.json"
    assert lp("file:///srv/fresing/index.json", windows=False) == "/srv/fresing/index.json"
    assert U.archive_url("\\\\SERVER\\share\\index.json", "./z.zip") == "\\\\SERVER\\share\\z.zip"


def test_check_and_download_from_a_plain_path(tmp_path):
    data = b"zipdata"
    (tmp_path / "fresing_render-9.0.0.zip").write_bytes(data)
    item = _item("9.0.0")
    item.update(archive_size=len(data), archive_hash="sha256:" + hashlib.sha256(data).hexdigest())
    (tmp_path / "index.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"data": [item]}).encode())   # with a BOM
    res = U.check(str(tmp_path / "index.json"), "0.2.15", (5, 2, 3), platform_name="windows-x64")
    assert res["state"] == "available" and res["url"] == str(tmp_path / "fresing_render-9.0.0.zip")
    U.download(res["url"], str(tmp_path / "dl" / "x.zip"), size=res["size"], sha256=res["sha256"])
    assert (tmp_path / "dl" / "x.zip").read_bytes() == data
    assert "could not reach" in U.check(str(tmp_path / "nope" / "index.json"), "0.2.15")["message"]


def test_helper_survives_a_console_that_cannot_print_every_character(helper_env, tmp_path, monkeypatch):
    """Blocker found in the review: a hidden console's code page cannot print '–' or 'é'; printing raised,
    the error handler marked a good update as failed and started the app a second time."""
    import io
    plan, marker = helper_env
    count = tmp_path / "starts.txt"
    plan["restart"] = [sys.executable, "-c", f"open({str(count)!r}, 'a').write('x')", "Kraan – é ř ’.blend"]
    ascii_out = io.TextIOWrapper(io.BytesIO(), encoding="cp437", errors="strict")
    monkeypatch.setattr(sys, "stdout", ascii_out)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    assert update_helper.main([str(plan_file)]) == 0
    assert _status(plan)["ok"]
    assert _wait_for(count)
    time.sleep(1.0)
    assert count.read_text() == "x"                                 # started once, not twice
    assert "Kraan – é ř ’.blend" in pathlib.Path(plan["log_file"]).read_text(encoding="utf-8")


def test_helper_restart_happens_once_even_after_an_error(helper_env, tmp_path, monkeypatch):
    plan, marker = helper_env
    count = tmp_path / "starts.txt"
    plan["restart"] = [sys.executable, "-c", f"open({str(count)!r}, 'a').write('x')"]
    real_restart = update_helper.restart

    calls = []

    def restart_then_fail(p):
        calls.append(1)
        real_restart(p)                       # the real one starts the app only once
        if len(calls) == 1:
            raise RuntimeError("something after the restart")
    monkeypatch.setattr(update_helper, "restart", restart_then_fail)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    assert update_helper.main([str(plan_file)]) == 1
    assert len(calls) == 2                    # asked twice (after the error too)
    assert _status(plan)["ok"]                                       # the good result stays
    assert _wait_for(count)
    time.sleep(1.0)
    assert count.read_text() == "x"


def test_helper_tries_again_when_the_installer_fails(helper_env, tmp_path, monkeypatch):
    """A virus scanner or an Explorer window can hold a file for a moment: Blender's installer then stops
    with an error. The helper waits and tries again."""
    plan, marker = helper_env
    flag = tmp_path / "fail_once"
    flag.write_text("1")
    fake = pathlib.Path(plan["blender"])
    fake.write_text(fake.read_text().replace(
        'if os.environ.get("FAKE_BLENDER_FAIL"):',
        f'if os.path.exists({str(flag)!r}):\n    os.remove({str(flag)!r})\n    print("locked by another process")\n'
        '    sys.exit(1)\nif os.environ.get("FAKE_BLENDER_FAIL"):'))
    plan["retry_waits"] = [0.2, 0.2]
    assert update_helper.run(plan)
    log = pathlib.Path(plan["log_file"]).read_text(encoding="utf-8")
    assert "exit code 1: trying again" in log and _status(plan)["installed"] == "0.2.15"
    assert (tmp_path / "fake.log").read_text().count("install-file") == 2


def test_helper_marks_itself_busy_while_installing(helper_env, tmp_path, monkeypatch):
    plan, _marker = helper_env
    seen = {}
    real = update_helper.run_install

    def spy(p):
        busy = os.path.join(os.path.dirname(p["status_file"]), update_helper.BUSY_FILE)
        seen["busy"] = json.loads(pathlib.Path(busy).read_text())
        return real(p)
    monkeypatch.setattr(update_helper, "run_install", spy)
    assert update_helper.run(plan)
    assert seen["busy"]["pid"] == os.getpid() and seen["busy"]["to"] == "0.2.15"
    assert abs(seen["busy"]["started"] - time.time()) < 60 and seen["busy"]["exe"] == sys.executable
    assert not os.path.exists(os.path.join(os.path.dirname(plan["status_file"]), update_helper.BUSY_FILE))


def test_check_and_download_over_http(tmp_path):
    """Web addresses (GitHub) go through urllib; a local web server stands in for GitHub."""
    import functools
    import http.server
    import threading
    data = b"zip over http"
    (tmp_path / "fresing_render-9.0.0.zip").write_bytes(data)
    item = _item("9.0.0")
    item.update(archive_size=len(data), archive_hash="sha256:" + hashlib.sha256(data).hexdigest())
    (tmp_path / "index.json").write_text(json.dumps({"data": [item]}), encoding="utf-8")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        old = {k: os.environ.pop(k, None) for k in ("http_proxy", "HTTP_PROXY")}
        url = f"http://127.0.0.1:{srv.server_address[1]}/index.json"
        res = U.check(url, "0.2.15", (5, 2, 3), platform_name="windows-x64")
        assert res["state"] == "available", res
        U.download(res["url"], str(tmp_path / "dl" / "x.zip"), size=res["size"], sha256=res["sha256"])
        assert (tmp_path / "dl" / "x.zip").read_bytes() == data
        assert "HTTP 404" in U.check(url.replace("index.json", "nope.json"), "0.2.15")["message"]
    finally:
        srv.shutdown()
        for k, v in old.items():
            if v is not None:
                os.environ[k] = v


# ---- task 0053: safe updates (bug hunt 0045 rows 12, 14, 19c) ------------------------------------

def _fake_blender_process(folder, seconds):
    """A running process whose program file is ``folder``/blender (a copy of ``sleep``): stands in for a second
    app window, a queued render or the PC check of the same install."""
    import shutil
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / "blender"
    shutil.copy2(shutil.which("sleep"), exe)
    proc = subprocess.Popen([str(exe), str(seconds)])
    end = time.time() + 5
    while time.time() < end and not update_helper.process_image(proc.pid).endswith("blender"):
        time.sleep(0.02)
    return proc


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc")
def test_process_image_and_other_blenders(tmp_path):
    assert os.path.realpath(update_helper.process_image(os.getpid())) == os.path.realpath(sys.executable)
    assert update_helper.process_image(0) == ""
    app = _fake_blender_process(tmp_path / "Blender é" / "bin", 30)
    elsewhere = _fake_blender_process(tmp_path / "other install", 30)
    try:
        assert update_helper.other_blenders(str(tmp_path / "Blender é")) == [app.pid]
        assert update_helper.other_blenders(str(tmp_path / "Blender é"), exclude=(app.pid,)) == []
        assert update_helper.other_blenders(str(tmp_path / "Blender")) == []          # a prefix is not the folder
        assert update_helper.other_blenders("") == []
    finally:
        for p in (app, elsewhere):
            p.kill()
            p.wait()
    assert update_helper.other_blenders(str(tmp_path / "Blender é")) == []


def _write_busy(path, **info):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info), encoding="utf-8")
    return path


def test_busy_file_of_a_killed_helper_is_removed(tmp_path):
    """Row 12: a helper killed mid-install left installing.json for good; the app said "being installed"
    at every start and never showed Update now again."""
    busy = tmp_path / "cfg" / update_helper.BUSY_FILE
    now = time.time()
    # a helper that really works: kept
    _write_busy(busy, pid=os.getpid(), to="0.3.0", started=now - 60, exe=sys.executable)
    assert update_helper.busy_helper(str(busy))["to"] == "0.3.0" and busy.exists()
    # older than any helper can take (power cut; the number now belongs to some process): removed
    _write_busy(busy, pid=os.getpid(), to="0.3.0", started=now - update_helper.BUSY_MAX_SECONDS - 5,
                exe=sys.executable)
    assert update_helper.busy_helper(str(busy)) is None and not busy.exists()
    # the helper's process has ended
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    _write_busy(busy, pid=gone.pid, to="0.3.0", started=now)
    assert update_helper.busy_helper(str(busy)) is None and not busy.exists()
    # an older helper wrote no start time: the file's own time counts
    _write_busy(busy, pid=os.getpid(), to="0.3.0")
    assert update_helper.busy_helper(str(busy)) is not None
    old = now - update_helper.BUSY_MAX_SECONDS - 60
    os.utime(busy, (old, old))
    assert update_helper.busy_helper(str(busy)) is None and not busy.exists()
    # no file, a broken file
    assert update_helper.busy_helper(str(busy)) is None
    busy.write_text("{broken", encoding="utf-8")
    assert update_helper.busy_helper(str(busy)) is None
    assert update_helper.BUSY_MAX_SECONDS >= update_helper.WAIT_SECONDS + 4 * update_helper.INSTALL_SECONDS


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc")
def test_busy_file_whose_number_now_belongs_to_another_program(tmp_path):
    """Windows reuses process numbers: a fresh-looking file whose number is now another program is old."""
    busy = tmp_path / update_helper.BUSY_FILE
    other = subprocess.Popen(["sleep", "30"])
    try:
        _write_busy(busy, pid=other.pid, to="0.3.0", started=time.time(), exe=r"C:\Fresing\python\bin\python.exe")
        assert update_helper.busy_helper(str(busy)) is None and not busy.exists()
    finally:
        other.kill()
        other.wait()


def test_helper_backs_up_and_cleans_up_after_a_good_update(helper_env, tmp_path):
    plan, _marker = helper_env
    assert update_helper.run(plan)
    log = pathlib.Path(plan["log_file"]).read_text(encoding="utf-8")
    assert "backup of 0.2.14 made" in log
    assert not (tmp_path / "cfg" / update_helper.BACKUP_DIR / "fresing_render").exists()     # removed again


def test_failed_swap_puts_the_old_version_back(helper_env, tmp_path, monkeypatch):
    """Row 14: Blender's installer removes the old folder before it renames the new one in. When that rename
    fails every time, the app opened as plain Blender: no Fresing tab, no message, no Update now."""
    plan, marker = helper_env
    (pathlib.Path(plan["ext_dir"]) / "wheels").mkdir()
    (pathlib.Path(plan["ext_dir"]) / "wheels" / "x.whl").write_bytes(b"wheel")
    monkeypatch.setenv("FAKE_BLENDER_BREAK", "1")
    plan["retry_waits"] = [0.1]
    assert not update_helper.run(plan)
    assert update_helper.installed_version(plan["ext_dir"]) == "0.2.14"              # the old version is back
    assert (pathlib.Path(plan["ext_dir"]) / "wheels" / "x.whl").read_bytes() == b"wheel"
    st = _status(plan)
    assert not st["ok"] and st["installed"] == "0.2.14"
    assert "old version 0.2.14 was put back" in st["message"] and "rename" not in st["message"]
    assert "exit code 1" in st["message"]
    assert _wait_for(marker)                                                          # the app opens again
    assert not (tmp_path / "cfg" / update_helper.BUSY_FILE).exists()
    assert "old version 0.2.14 put back" in pathlib.Path(plan["log_file"]).read_text(encoding="utf-8")


def test_helper_error_after_the_old_folder_is_gone_puts_it_back(helper_env, tmp_path, monkeypatch):
    import shutil
    plan, marker = helper_env

    def broken(p):
        shutil.rmtree(p["ext_dir"])
        raise RuntimeError("the helper itself stopped")
    monkeypatch.setattr(update_helper, "run_install", broken)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    assert update_helper.main([str(plan_file)]) == 1
    assert update_helper.installed_version(plan["ext_dir"]) == "0.2.14"
    assert not _status(plan)["ok"] and _status(plan)["installed"] == "0.2.14"
    assert _wait_for(marker)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc")
def test_helper_waits_for_other_blenders_of_the_same_install(helper_env, tmp_path):
    """Row 19c: the helper waited only for the app itself, not for a queued render or the PC check started
    from the same Blender (they use the files the installer swaps)."""
    plan, _marker = helper_env
    other = _fake_blender_process(pathlib.Path(plan["blender"]).parent / "queue", 1.5)
    t0 = time.time()
    try:
        assert update_helper.run(plan)
    finally:
        other.kill()
        other.wait()
    assert time.time() - t0 >= 1.2
    assert "waiting for the other Blender(s)" in pathlib.Path(plan["log_file"]).read_text(encoding="utf-8")
    assert update_helper.installed_version(plan["ext_dir"]) == "0.2.15"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc")
def test_helper_gives_up_when_another_blender_stays_open(helper_env, tmp_path):
    plan, marker = helper_env
    other = _fake_blender_process(pathlib.Path(plan["blender"]).parent / "pc check", 30)
    try:
        plan["wait_seconds"] = 0.5
        assert not update_helper.run(plan)
    finally:
        other.kill()
        other.wait()
    st = _status(plan)
    assert not st["ok"] and "Another Fresing Render was still open" in st["message"]
    assert not (tmp_path / "fake.log").exists()                      # nothing installed
    assert update_helper.installed_version(plan["ext_dir"]) == "0.2.14"
    assert not (tmp_path / "cfg" / update_helper.BUSY_FILE).exists()
    assert _wait_for(marker)                                          # the app (closed by now) opens again


def test_put_back_over_what_is_left_of_a_half_done_swap(tmp_path, monkeypatch):
    """Review: a read-only file (or one a virus scanner holds) left in the extension folder made the put-back
    fail, the case it is there for."""
    ext = tmp_path / "extensions" / "fresing_render"
    ext.mkdir(parents=True)
    (ext / "blender_manifest.toml").write_text('version = "0.2.14"\n', encoding="utf-8")
    (ext / "wheels").mkdir()
    (ext / "wheels" / "a.whl").write_bytes(b"old")
    plan = {"ext_dir": str(ext), "backup_dir": str(tmp_path / "upd" / "backup" / "fresing_render"),
            "log_file": str(tmp_path / "log.txt")}
    old = pathlib.Path(plan["backup_dir"])
    old.mkdir(parents=True)
    (old / "stale.txt").write_text("an older backup", encoding="utf-8")
    backup = update_helper.make_backup(plan)
    assert backup and not (old / "stale.txt").exists()
    # half-done swap: the manifest is gone, a read-only file of the new version is left
    (ext / "blender_manifest.toml").unlink()
    (ext / "new.py").write_text("new", encoding="utf-8")
    (ext / "new.py").chmod(0o444)
    assert update_helper.restore_backup(plan, backup)
    assert update_helper.installed_version(str(ext)) == "0.2.14" and not (ext / "new.py").exists()
    # the folder cannot be deleted at all: the backup is copied over it
    backup = update_helper.make_backup(plan)
    (ext / "blender_manifest.toml").unlink()
    monkeypatch.setattr(update_helper, "_remove_tree", lambda path, tries=3: not os.path.exists(path))
    assert update_helper.restore_backup(plan, backup)
    assert update_helper.installed_version(str(ext)) == "0.2.14"
    assert (ext / "wheels" / "a.whl").read_bytes() == b"old"
