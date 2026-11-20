"""The Toolbox folder without Blender (task 0217, core/toolbox.py): the manifest, reading a job of the inbox, every kind
of bad job refused with its code, the clear sentence for version 0.2, jobs left by an earlier run, two copies and one
job, a busy app, Not now, cancel.json, the reply (and the result kept when House Planner cannot take it), a write that
Windows refuses tried again, cleaning up without following a link – and everything written passes the pinned checker
of toolbox-format v0.1."""

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from fresing_render.core import toolbox as tb

HERE = Path(__file__).parent
PIN = HERE / "data" / "toolbox" / "tbf-v0.1.1"
SAMPLES = PIN / "samples"
HP = "nl.fresing.house-planner"
HOUSE = HERE / "data" / "house" / "hsf-v1.0.1" / "samples" / "sample-house.hpscene"


def checker():
    """The pinned tag's checker (needs jsonschema): ``check(path) -> Report``."""
    pytest.importorskip("jsonschema")
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "tbf" or k.startswith("tbf.")}
    sys.path.insert(0, str(PIN))
    try:
        import tbf.check as chk
        return chk.check
    finally:
        sys.path.remove(str(PIN))
        for k in [k for k in sys.modules if k == "tbf" or k.startswith("tbf.")]:
            sys.modules[f"_pinned_{k}"] = sys.modules.pop(k)
        sys.modules.update(saved)


def errors(root: Path) -> list[str]:
    """The checker's errors, without the one the format allows: the files of a final job deleted (FORMAT.md 7.4 says
    a tool MAY; the v0.1 checker still asks for them – reported to the toolbox lead)."""
    rep = checker()(root)
    out = []
    for e in rep.errors:
        if "is missing" in e and "/inbox/" in e:
            job = e.split("/inbox/")[1].split(":")[0]
            tool = e.split("tools/")[1].split("/")[0]
            st = json.loads((root / "tools" / tool / "inbox" / job / "status.json").read_text("utf-8"))
            if st["state"] in tb.FINAL:
                continue
        out.append(e)
    return out


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def root(tmp_path):
    """A Toolbox folder in a path with a space and an accent, with House Planner's sample manifest."""
    r = tmp_path / "Tool box é" / "Toolbox"
    (r / "tools" / HP).mkdir(parents=True)
    shutil.copyfile(SAMPLES / "Toolbox" / "tools" / HP / "toolbox.json", r / "tools" / HP / "toolbox.json")
    return r


def inbox(root, tmp_path, clock=None, start=True):
    ib = tb.Inbox(root, "0.2.999", "/opt/Fresing Render/blender-launcher", ["--app-template", "fresing_render"],
                  keep_dir=tmp_path / "kept", clock=clock or Clock())
    if start:
        ib.start()
    return ib


def send(root, files=(HOUSE,), action="bake-house", **kw):
    kw.setdefault("ret", "import-bake")
    return tb.send(root, HP, tb.ME, action, [Path(f) for f in files], title="Sample house – version 3", **kw)


def status(root, jid):
    return json.loads((root / "tools" / tb.ME / "inbox" / jid / "status.json").read_text("utf-8"))


def make_job(root, jid="20261118-120000-abcdef", files=(("sample-house.hpscene", HOUSE),), **over):
    """A job written by hand (to break it on purpose)."""
    d = root / "tools" / tb.ME / "inbox" / jid
    d.mkdir(parents=True)
    listed = []
    for name, src in files:
        shutil.copyfile(src, d / name)
        listed.append({"name": name, "type": "hpscene", "size": os.path.getsize(src)})
    doc = {"format": "toolbox-job", "version": "0.1", "job": jid, "created": "2026-11-18T12:00:00+01:00", "from": HP,
           "to": tb.ME, "action": "bake-house", "files": listed, "return": "import-bake", "title": "A house"}
    doc.update(over)
    (d / "job.json").write_text(json.dumps({k: v for k, v in doc.items() if v is not None}), "utf-8")
    return d


# ---------------------------------------------------------------------------

def test_samples_read_and_the_manifest_passes_the_checker(root, tmp_path):
    for p, kind in ((SAMPLES / "Toolbox" / "tools" / tb.ME / "toolbox.json", "tool"),
                    (SAMPLES / "Toolbox" / "tools" / tb.ME / "alive.json", "alive"),
                    (SAMPLES / "Toolbox" / "toolbox-folder.json", "folder")):
        assert tb.read_doc(p, kind)["version"] == "0.1"
    ours = tb.manifest("0.2.999", "C:/Users/a b/AppData/Local/FresingRender/Fresing Render.exe")
    sample = json.loads((SAMPLES / "Toolbox" / "tools" / tb.ME / "toolbox.json").read_text("utf-8"))
    assert ours["actions"] == sample["actions"] and ours["id"] == sample["id"]
    ib = inbox(root, tmp_path)
    assert ib.start() and ib.problem == ""
    assert (root / "toolbox-folder.json").is_file()
    ib.write_alive()
    assert errors(root) == []
    doc = tb.read_doc(root / "tools" / tb.ME / "toolbox.json", "tool")
    assert doc["start"]["program"] == "/opt/Fresing Render/blender-launcher" and doc["app_version"] == "0.2.999"


def test_the_sample_folders_jobs_are_taken_up_as_the_format_says(tmp_path, monkeypatch):
    # the inbox deletes a job a day after its status became final (FORMAT.md 7.4): look at the sample as on the
    # evening it was made, not today (task 0227: from 19 Nov 2026 20:15 on this test failed with the real clock)
    from datetime import datetime
    made = datetime.fromisoformat("2026-11-18T21:00:00+01:00").timestamp()
    clean = tb.Inbox.clean
    monkeypatch.setattr(tb.Inbox, "clean", lambda self, at=None: clean(self, made if at is None else at))
    root = tmp_path / "Toolbox"
    shutil.copytree(SAMPLES / "Toolbox", root)
    ib = inbox(root, tmp_path)
    ib.look()
    # the sample's second job was "working" with a cancel.json when the "earlier run" closed: cancelled now
    assert status(root, "20261118-203000-c81e55")["state"] == "cancelled"
    assert status(root, "20261118-195100-9f3c2a")["state"] == "done"        # final: left as it is
    assert ib.jobs == {}
    ib.clean(made + 2 * tb.DAY)                                               # a day after final: deleted
    assert not (root / "tools" / tb.ME / "inbox" / "20261118-195100-9f3c2a").exists()


def test_a_house_arrives_waits_and_is_answered(root, tmp_path):
    clock = Clock()
    ib = inbox(root, tmp_path, clock)
    jid = send(root)
    events = ib.look()
    assert events and "From House Planner: Sample house – version 3" in events[0]
    st = status(root, jid)
    assert st["state"] == "waiting" and st["text"] == "Waiting for you in Fresing Render: press Bake now"
    assert ib.begin(jid, "Importing the house") == ""
    assert status(root, jid)["state"] == "working"
    clock.t += 0.5
    assert not ib.progress(jid, 0.3, "Baking summer noon")           # at most once a second
    clock.t += 1.0
    assert ib.progress(jid, 0.4, "Baking summer noon (3 of 8)")
    assert status(root, jid)["fraction"] == 0.4
    bake = tmp_path / "Sample house.hpbake"
    shutil.copyfile(SAMPLES / "files" / "sample-house.hpbake", bake)
    rid, text = ib.reply(jid, [bake], "Baked 4 moments")
    st = status(root, jid)
    assert st["state"] == "done" and st["reply"] == rid and text.endswith("sent back to House Planner")
    reply = json.loads((root / "tools" / HP / "inbox" / rid / "job.json").read_text("utf-8"))
    assert reply["action"] == "import-bake" and reply["reply_to"] == {"tool": tb.ME, "job": jid}
    assert reply["title"] == "Sample house – version 3" and "return" not in reply
    assert sorted(os.listdir(root / "tools" / tb.ME / "inbox" / jid)) == ["job.json", "status.json"]
    assert not (tmp_path / "kept").exists()                       # no copy kept: the reply job is the result
    assert errors(root) == []


def test_no_house_planner_manifest_keeps_the_bake_and_says_where(root, tmp_path):
    ib = inbox(root, tmp_path)
    jid = send(root)
    ib.look()
    ib.begin(jid, "Importing")
    shutil.rmtree(root / "tools" / HP)
    bake = tmp_path / "Sample house.hpbake"
    shutil.copyfile(SAMPLES / "files" / "sample-house.hpbake", bake)
    rid, text = ib.reply(jid, [bake], "Baked 1 moment")
    kept = tmp_path / "kept" / "Sample house.hpbake"
    assert rid is None and kept.is_file()
    st = status(root, jid)
    assert st["state"] == "done" and "reply" not in st and str(kept) in st["text"]


@pytest.mark.parametrize("case, code", [
    ("unknown-action", "unknown-action"), ("wrong-type", "wrong-type"), ("zip-renamed", "wrong-type"),
    ("reserved-name", "bad-job"), ("path-in-name", "bad-job"), ("too-big", "bad-job"), ("wrong-to", "bad-job"),
    ("id-not-folder", "bad-job"), ("unknown-field", "bad-job"), ("link", "bad-job"),
    ("not-json", "bad-job"), ("from-is-to", "bad-job"), ("job-json-folder", "bad-job"), ("size-too-big", "bad-job"),
    ("name-too-long", "bad-job")])
def test_bad_jobs_are_refused_with_their_code(root, tmp_path, case, code):
    jid = "20261118-120000-abcdef"
    if case == "unknown-action":
        d = make_job(root, action="render-movie")
    elif case == "wrong-type":                                        # a STEP file sent as a house
        d = make_job(root, files=(("sample-house.hpscene", SAMPLES / "files" / "sample-part.step"),))
    elif case == "zip-renamed":
        d = make_job(root, files=(("sample-house.hpscene", SAMPLES / "files" / "sample-archive.zip"),))
    elif case == "reserved-name":
        d = make_job(root, files=(("CON.hpscene", HOUSE),))
    elif case == "path-in-name":
        d = make_job(root)
        doc = json.loads((d / "job.json").read_text())
        doc["files"][0]["name"] = "../sample-house.hpscene"
        (d / "job.json").write_text(json.dumps(doc))
    elif case == "too-big":
        d = make_job(root)
        with open(d / "sample-house.hpscene", "ab") as fh:
            fh.write(b"0")
    elif case == "wrong-to":
        d = make_job(root, to="nl.fresing.other")
    elif case == "id-not-folder":
        d = make_job(root, job="20261118-120000-ffffff")
    elif case == "unknown-field":
        d = make_job(root, priority="high")
    elif case == "size-too-big":                 # toolbox-format 0.1.1: no file has this size – refused at once,
        d = make_job(root)                           # not after a minute as "not complete yet"
        doc = json.loads((d / "job.json").read_text())
        doc["files"][0]["size"] = 2**53
        (d / "job.json").write_text(json.dumps(doc))
    elif case == "name-too-long":                # 0.1.1: a name of 120 characters the PC cannot hold (here 338 bytes)
        d = make_job(root)
        doc = json.loads((d / "job.json").read_text())
        doc["files"][0]["name"] = "\u20ac" * 110 + ".hpscene"
        (d / "job.json").write_text(json.dumps(doc))
    elif case == "link":
        d = make_job(root)
        os.remove(d / "sample-house.hpscene")
        os.symlink(HOUSE, d / "sample-house.hpscene")
    elif case == "not-json":
        d = make_job(root)
        (d / "job.json").write_text('{"format": "toolbox-job",')
    elif case == "from-is-to":
        d = make_job(root, **{"from": tb.ME})
    else:
        d = make_job(root)
        os.remove(d / "job.json")
        (d / "job.json").mkdir()
    ib = inbox(root, tmp_path)
    ib.look()
    st = status(root, jid)
    assert st["state"] == "failed" and st["code"] == code, st
    assert ib.jobs == {} and ib.notes and "refused" in ib.notes[-1]
    assert d.is_dir() and HOUSE.is_file()                        # nothing outside the job folder was touched


def test_a_key_written_twice_the_last_counts(root, tmp_path):
    """toolbox-format 0.1.1: a reader takes a key written twice as JavaScript does – the last counts (FORMAT.md 3.4;
    only the checker refuses it). Before, Fresing Render refused such a job that House Planner's own code reads."""
    d = make_job(root)
    text = (d / "job.json").read_text()
    (d / "job.json").write_text(text[:-1] + ', "title": "Twice"}')
    ib = inbox(root, tmp_path)
    ib.look()
    assert status(root, d.name)["state"] == "waiting"
    assert ib.jobs[d.name].title == "Twice"


def test_a_newer_version_is_refused_with_the_clear_sentence(root, tmp_path):
    make_job(root, version="0.2")
    ib = inbox(root, tmp_path)
    ib.look()
    st = status(root, "20261118-120000-abcdef")
    assert st["state"] == "failed" and st["code"] == "bad-job"
    assert st["text"] == ("This job was written by a newer tool (toolbox format 0.2). Update Fresing Render to read "
                          "it.")


def test_a_file_still_short_is_not_read_early(root, tmp_path):
    clock = Clock()
    d = make_job(root)
    data = (d / "sample-house.hpscene").read_bytes()
    (d / "sample-house.hpscene").write_bytes(data[:100])
    ib = inbox(root, tmp_path, clock)
    ib.look()
    assert not (d / "status.json").exists()                     # waits
    clock.t += 30
    ib.look()
    assert not (d / "status.json").exists()
    (d / "sample-house.hpscene").write_bytes(data)              # now whole
    ib.look()
    assert status(root, d.name)["state"] == "waiting"
    d2 = make_job(root, jid="20261118-120000-bbbbbb")
    (d2 / "sample-house.hpscene").write_bytes(data[:100])
    ib.look()
    clock.t += 61
    ib.look()
    st = status(root, d2.name)
    assert st["state"] == "failed" and st["code"] == "bad-job" and "minute" in st["text"]


def test_jobs_left_by_an_earlier_run(root, tmp_path):
    a = make_job(root, jid="20261118-120000-aaaaaa")
    b = make_job(root, jid="20261118-120000-bbbbbb")
    tb.write_json(a / "status.json", tb.status_doc(a.name, "waiting", text="Waiting for you"))
    tb.write_json(b / "status.json", tb.status_doc(b.name, "working", fraction=0.5, text="Baking"))
    ib = inbox(root, tmp_path)
    ib.look()
    assert list(ib.jobs) == [a.name]                            # asked again
    st = status(root, b.name)
    assert st["state"] == "failed" and st["code"] == "error" and st["text"] == tb.CLOSED_TEXT


def test_two_copies_one_job(root, tmp_path):
    one, two = inbox(root, tmp_path), inbox(root, tmp_path)
    one.start()
    two.start()
    jid = send(root)
    one.look()
    two.look()
    assert jid in one.jobs and jid not in two.jobs
    # a copy started while another one watches leaves that copy's jobs alone (the independent tester, 0217)
    one.write_alive()
    three = inbox(root, tmp_path)
    three.look()
    assert jid not in three.jobs
    assert one.begin(jid, "Importing") == ""
    assert three.begin(jid, "Importing") == "This job is no longer there"
    # once no other copy has been heard of for a while, a later copy takes up what was left (FORMAT.md 6.3)
    four = inbox(root, tmp_path, start=False)
    four.clock.t = 1000.0
    (root / "tools" / tb.ME / "alive.json").unlink()          # the other copies were closed
    four.look()
    assert status(root, jid)["state"] == "failed" and status(root, jid)["code"] == "error"


def test_a_busy_app_keeps_the_job_waiting(root, tmp_path):
    ib = inbox(root, tmp_path)
    jid = send(root)
    ib.look(busy="Web 3D export")
    st = status(root, jid)
    assert st["state"] == "waiting" and st["text"] == "Fresing Render is busy (Web 3D export); the house waits"
    ib.look()
    assert status(root, jid)["text"] == "Waiting for you in Fresing Render: press Bake now"


def test_not_now_and_cancel(root, tmp_path):
    ib = inbox(root, tmp_path)
    a, b, c = send(root), send(root), send(root)
    ib.look()
    ib.not_now(a)
    assert status(root, a) | {"updated": 0} == status(root, a) | {"updated": 0}
    assert status(root, a)["state"] == "cancelled" and status(root, a)["text"] == "You said not now in Fresing Render"
    tb.write_json(root / "tools" / tb.ME / "inbox" / b / "cancel.json",
                  {"format": "toolbox-cancel", "version": "0.1", "job": b, "asked": tb.now()})
    ib.look()
    assert status(root, b)["state"] == "cancelled" and b not in ib.jobs           # while waiting
    ib.begin(c, "Baking")
    tb.write_json(root / "tools" / tb.ME / "inbox" / c / "cancel.json",
                  {"format": "toolbox-cancel", "version": "0.1", "job": c, "asked": tb.now()})
    ib.look()
    assert ib.jobs[c].cancel_asked and status(root, c)["state"] == "working"      # the app stops the bake
    ib.finish(c, "cancelled", "Cancelled by House Planner; nothing was sent")
    assert status(root, c)["state"] == "cancelled"
    assert errors(root) == []


def test_a_status_write_windows_refuses_is_tried_again(root, tmp_path, monkeypatch):
    ib = inbox(root, tmp_path)
    jid = send(root)
    ib.look()
    real = os.replace
    refuse = {"on": True}

    def replace(a, b):
        if refuse["on"] and str(b).endswith("status.json"):
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real(a, b)

    monkeypatch.setattr(os, "replace", replace)
    assert ib.begin(jid, "Importing the house") == ""             # no crash; the write waits
    assert status(root, jid)["state"] == "waiting"
    assert not [p for p in (root / "tools" / tb.ME / "inbox" / jid).iterdir() if p.name.endswith(".tmp")]
    ib.look()
    assert status(root, jid)["state"] == "waiting"                # still refused
    refuse["on"] = False
    ib.look()
    assert status(root, jid)["state"] == "working"


def test_clean_up_after_a_day_never_through_a_link(root, tmp_path):
    ib = inbox(root, tmp_path)
    jid = send(root)
    ib.look()
    ib.not_now(jid)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep me")
    link = root / "tools" / tb.ME / "inbox" / "20261118-120000-linked"
    os.symlink(outside, link, target_is_directory=True)
    assert ib.clean() == 0                                         # not yet a day
    old = os.path.getmtime(outside)
    assert ib.clean(at=tb.time.time() + 2 * tb.DAY) == 1
    assert not (root / "tools" / tb.ME / "inbox" / jid).exists()
    assert (outside / "precious.txt").read_text() == "keep me" and os.path.islink(link)
    assert ib.clean(at=tb.time.time() + 40 * tb.DAY) == 0 and (outside / "precious.txt").exists()
    assert os.path.getmtime(outside) == old


def test_alive_is_removed_only_by_the_copy_that_wrote_it(root, tmp_path):
    one, two = inbox(root, tmp_path), inbox(root, tmp_path)
    one.start()
    two.start()
    one.write_alive()
    import time
    time.sleep(1.1)
    two.write_alive()
    assert not one.remove_alive()
    assert (root / "tools" / tb.ME / "alive.json").exists()
    assert two.remove_alive() and not (root / "tools" / tb.ME / "alive.json").exists()


def test_install_and_uninstall_touch_only_our_folder(root, tmp_path):
    tb.install(root, "0.2.999", "C:/x/Fresing Render.exe")
    assert tb.read_doc(root / "tools" / tb.ME / "toolbox.json", "tool")["start"]["program"] == "C:/x/Fresing Render.exe"
    tb.install(root, "0.3.0")                                     # an update writes it again
    assert tb.read_doc(root / "tools" / tb.ME / "toolbox.json", "tool")["app_version"] == "0.3.0"
    assert tb.uninstall(root)
    assert not (root / "tools" / tb.ME).exists()
    assert (root / "tools" / HP / "toolbox.json").is_file() and (root / "toolbox-folder.json").is_file()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    os.symlink(outside, root / "tools" / tb.ME, target_is_directory=True)
    assert not tb.uninstall(root) and (outside / "keep.txt").exists()


def test_a_folder_that_cannot_be_made_leaves_the_app_as_it_was(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("not a folder")
    ib = tb.Inbox(blocker / "Toolbox", "0.2.999", keep_dir=tmp_path / "kept")
    assert not ib.start() and "cannot be used" in ib.problem
    assert ib.look() == []                                        # and the look does not raise


def test_the_toolbox_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOLBOX_HOME", str(tmp_path / "x"))
    assert tb.home() == tmp_path / "x"
    monkeypatch.delenv("TOOLBOX_HOME")
    assert tb.home().name == "Toolbox"


def test_send_refuses_what_the_receiver_does_not_take(root, tmp_path):
    with pytest.raises(ValueError):
        tb.send(root, tb.ME, HP, "import-bake", [SAMPLES / "files" / "sample-part.step"])
    with pytest.raises(ValueError):
        tb.send(root, tb.ME, "nl.fresing.nobody", "x", [SAMPLES / "files" / "sample-house.hpbake"])
    assert not (root / "tools" / HP / "inbox").exists() or not os.listdir(root / "tools" / HP / "inbox")
    z = tmp_path / "a.hpbake"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("x.txt", "not a bake")
    with pytest.raises(ValueError):
        tb.send(root, tb.ME, HP, "import-bake", [z])


def test_the_send_helper_plays_house_planner(root, tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(HERE.parent / "tools"))
    try:
        import toolbox_send
    finally:
        sys.path.remove(str(HERE.parent / "tools"))
    monkeypatch.setenv("TOOLBOX_HOME", str(root))
    assert toolbox_send.main([str(HOUSE)]) == 1                   # Fresing Render has not made its folder yet
    ib = inbox(root, tmp_path)
    shutil.rmtree(root / "tools" / HP)                            # House Planner's manifest: written by the helper
    assert toolbox_send.main([str(HOUSE), "--title", "My house"]) == 0
    ib.look()
    assert [j.title for j in ib.jobs.values()] == ["My house"]
    assert toolbox_send.main(["--status"]) == 0
    assert "My house: waiting" in capsys.readouterr().out
    assert errors(root) == []


def test_the_installer_files_are_plain_ascii():
    """Windows PowerShell 5.1 reads a .ps1 without a byte-order mark as the PC's code page: a dash "–" in the
    uninstaller became "â€“", whose last byte is a typographic quote PowerShell ends a string at – the whole
    uninstaller failed to parse on GitHub's Windows (task 0217). The installer's files stay plain ASCII."""
    for p in sorted((HERE.parent / "installer").iterdir()):
        if p.suffix.lower() in (".ps1", ".bat"):
            data = p.read_bytes()
            bad = [i for i, b in enumerate(data) if b > 127]
            assert not bad, f"{p.name}: a non-ASCII byte at {bad[0]}: {data[max(0, bad[0] - 40):bad[0] + 10]!r}"
