"""Independent tests of fresing_render/core/toolbox.py (task 0217), written from the toolbox format v0.1
(tests/data/toolbox/tbf-v0.1/FORMAT.md) by someone who did not write the module. Plain Python, no Blender.

The pinned checker (``tbf.check`` of the tag) is the judge of what the Inbox writes. One known checker gap: after a
final status the job's own files are deleted on purpose (FORMAT.md 7.4 allows it) and the checker then says
"the file X is missing" – that exact message is treated as expected (``_errors``).
"""
from __future__ import annotations

import copy
import importlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

from fresing_render.core import toolbox as tb

PIN = Path(__file__).resolve().parent / "data" / "toolbox" / "tbf-v0.1"
SAMPLES = PIN / "samples"
FILES = SAMPLES / "files"
ME = "nl.fresing.render"
HP = "nl.fresing.house-planner"


# ---------------------------------------------------------------- the pinned checker (top-level package ``tbf``)
def _checker():
    if str(PIN) not in sys.path:
        sys.path.insert(0, str(PIN))
    mod = importlib.import_module("tbf.check")
    assert Path(mod.__file__).resolve().is_relative_to(PIN), "a different tbf package was imported"
    return mod


CHECK = _checker()


def _errors(path: Path, allow_missing: bool = True) -> list[str]:
    rep = CHECK.check(path)
    errs = rep.errors
    if allow_missing:
        errs = [e for e in errs if not ("the file " in e and e.endswith(" is missing"))]
    return errs


# ---------------------------------------------------------------- set-up
class Clock:
    def __init__(self, t: float = 1_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def root(tmp_path) -> Path:
    """The sample Toolbox folder with an empty inbox for Fresing Render (House Planner's manifest kept)."""
    r = tmp_path / "Toolbox"
    shutil.copytree(SAMPLES / "Toolbox", r)
    inbox = r / "tools" / ME / "inbox"
    shutil.rmtree(inbox)
    inbox.mkdir()
    (r / "tools" / ME / "alive.json").unlink()
    return r


@pytest.fixture
def clock() -> Clock:
    return Clock()


def inbox_of(root: Path, me: str = ME) -> Path:
    return root / "tools" / me / "inbox"


def make_inbox(root, tmp_path, clock, **kw) -> tb.Inbox:
    ib = tb.Inbox(root, "9.9.9", keep_dir=tmp_path / "kept", clock=clock, **kw)
    assert ib.start(), ib.problem
    return ib


_N = [0]


def job_id() -> str:
    _N[0] += 1
    return f"20261118-1200{_N[0]:02d}-abc{_N[0]:03d}"


def make_job(root: Path, files=(("sample-house.hpscene", FILES / "sample-house.hpscene", "hpscene"),),
             action="bake-house", jid=None, folder_name=None, write_job=True, **over) -> Path:
    """A job as a sender writes it: files first, job.json last. ``files``: (name, source path or bytes, type)."""
    jid = jid or job_id()
    d = inbox_of(root) / (folder_name or jid)
    d.mkdir()
    listed = []
    for name, src, typ in files:
        data = src if isinstance(src, bytes) else Path(src).read_bytes()
        (d / name).write_bytes(data)
        listed.append({"name": name, "type": typ, "size": len(data)})
    doc = {"format": "toolbox-job", "version": "0.1", "job": jid, "created": "2026-11-18T19:51:00+01:00",
           "from": HP, "to": ME, "action": action, "files": listed, "return": "import-bake", "title": "A house"}
    if action != "bake-house":
        doc.pop("return")
    for k, v in over.items():
        if v is None:
            doc.pop(k, None)
        else:
            doc[k] = v
    if write_job:
        (d / "job.json").write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    return d


def status(d: Path) -> dict | None:
    p = d / "status.json"
    return json.loads(p.read_text("utf-8")) if p.is_file() else None


# ================================================================ a good job, end to end
def test_a_good_job_waits_and_everything_written_passes_the_checker(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ev = ib.look()
    assert ev, "a new job gives an event line"
    st = status(d)
    assert st["state"] == "waiting" and st["job"] == d.name
    assert d.name in ib.jobs
    assert (root / "tools" / ME / "alive.json").is_file()
    assert _errors(root, allow_missing=False) == []
    # a second look changes nothing and raises nothing
    ib.look()
    assert status(d)["state"] == "waiting"


def test_begin_progress_finish_and_files_deleted(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ib.look()
    clock.t += 5
    assert ib.begin(d.name, "Baking") == ""
    assert status(d)["state"] == "working"
    # progress at most once a second (7.1)
    assert ib.progress(d.name, 0.3, "step 1") is False
    clock.t += 1.5
    assert ib.progress(d.name, 0.3, "step 1") is True
    assert status(d)["fraction"] == pytest.approx(0.3)
    clock.t += 0.2
    assert ib.progress(d.name, 0.4, "step 2") is False
    assert status(d)["fraction"] == pytest.approx(0.3)
    # out-of-range fraction never reaches the file
    clock.t += 2
    ib.progress(d.name, 7.0, "x" * 500)
    st = status(d)
    assert 0 <= st["fraction"] <= 1 and len(st["text"]) <= 200
    assert _errors(root, allow_missing=False) == []
    ib.finish(d.name, "done", "Baked")
    assert status(d)["state"] == "done"
    assert sorted(p.name for p in d.iterdir()) == ["job.json", "status.json"]
    assert _errors(root) == []
    # final is final: another look never changes it
    ib.look()
    assert status(d)["state"] == "done"


# ================================================================ refused jobs
def _bad_cases():
    hp = ("sample-house.hpscene", FILES / "sample-house.hpscene", "hpscene")
    zipf = ("house.hpscene", FILES / "sample-archive.zip", "hpscene")       # a zip renamed .hpscene
    return {
        "wrong-to": (dict(to="nl.example.other"), [hp], "bad-job"),
        "from-is-to": (dict(**{"from": ME}), [hp], "bad-job"),
        "unknown-action": (dict(action="paint-house"), [hp], "unknown-action"),
        "unknown-field": (dict(colour="red"), [hp], "bad-job"),
        "missing-created": (dict(created=None), [hp], "bad-job"),
        "missing-files": (dict(files=None), [hp], "bad-job"),
        "empty-files": (dict(files=[]), [hp], "bad-job"),
        "bad-created": (dict(created="2026-02-30T10:00:00Z"), [hp], "bad-job"),
        "title-too-long": (dict(title="t" * 121), [hp], "bad-job"),
        "reply-to-other-tool": (dict(reply_to={"tool": "nl.example.other", "job": "20261118-000000-aaaaaa"},
                                     **{"return": None}), [hp], "bad-job"),
        "reply-with-return": (dict(reply_to={"tool": HP, "job": "20261118-000000-aaaaaa"}), [hp], "bad-job"),
        "zip-renamed-hpscene": ({}, [zipf], "wrong-type"),
        "step-for-bake": ({}, [("p.step", FILES / "sample-part.step", "step")], "wrong-type"),
        "claims-hpscene-is-step": ({}, [("sample-house.hpscene", FILES / "sample-house.hpscene", "step")],
                                   "wrong-type"),
        "ifc-named-step": (dict(action="import-step"), [("b.step", FILES / "sample-building.ifc", "step")],
                           "wrong-type"),
        "reserved-con": ({}, [("CON.hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "reserved-lpt9": ({}, [("lpt9.x.hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "trailing-dot": ({}, [("house.hpscene.", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "leading-space": ({}, [(" house.hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "named-status": ({}, [("Status.JSON", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "colon": ({}, [("a:b.hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "case-duplicate": ({}, [("a.hpscene", FILES / "sample-house.hpscene", "hpscene"),
                                ("A.hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
        "too-long-name": ({}, [("h" * 113 + ".hpscene", FILES / "sample-house.hpscene", "hpscene")], "bad-job"),
    }


@pytest.mark.parametrize("case", sorted(_bad_cases()))
def test_bad_jobs_are_refused_with_the_right_code(root, tmp_path, clock, case):
    over, files, code = _bad_cases()[case]
    ib = make_inbox(root, tmp_path, clock)
    over = dict(over)
    listed = over.pop("files", "<keep>")
    d = make_job(root, files=files, action=over.pop("action", "bake-house"), **over)
    if listed != "<keep>":
        doc = json.loads((d / "job.json").read_text())
        if listed is None:
            del doc["files"]
        else:
            doc["files"] = listed
        (d / "job.json").write_text(json.dumps(doc))
    if case == "case-duplicate" and not (d / "A.hpscene").exists():
        pytest.skip("case-insensitive file system")
    ib.look()
    st = status(d)
    assert st is not None, f"{case}: no status written"
    assert st["state"] == "failed" and st.get("code") == code, (case, st)
    assert d.name not in ib.jobs
    assert 0 < len(st.get("text", "")) <= 200
    # what the Inbox wrote is a valid status.json (job.json may be the broken thing itself)
    rep = CHECK.Report("x")
    assert CHECK.read_doc(d / "status.json", "status-0", rep, "status") is not None, rep.errors


def test_files_with_a_wrong_name_or_size_are_never_opened(root, tmp_path, clock, monkeypatch):
    opened = []
    real = tb.detect
    monkeypatch.setattr(tb, "detect", lambda p, types: opened.append(Path(p).name) or real(p, types))
    ib = make_inbox(root, tmp_path, clock)
    bad_name = make_job(root, files=[("NUL.hpscene", FILES / "sample-house.hpscene", "hpscene")])
    big = make_job(root)
    doc = json.loads((big / "job.json").read_text())
    doc["files"][0]["size"] -= 1           # the file is LONGER than stated
    (big / "job.json").write_text(json.dumps(doc))
    ib.look()
    assert status(bad_name)["code"] == "bad-job" and status(big)["code"] == "bad-job"
    assert opened == []


def test_a_newer_version_is_refused_with_the_clear_sentence(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root, version="0.2", colour="x")        # a 0.2 job may well have fields 0.1 does not know
    ib.look()
    st = status(d)
    assert st["state"] == "failed" and st["code"] == "bad-job"
    assert ("This job was written by a newer tool (toolbox format 0.2). Update Fresing Render to read it."
            in st["text"]), st["text"]


def test_folder_name_not_the_job_id(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root, jid="20261118-000000-aaaaaa", folder_name="20261118-000000-bbbbbb")
    ib.look()
    assert status(d)["code"] == "bad-job"


def test_folders_that_are_no_job_ids_and_stray_entries_are_left_alone(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    upper = make_job(root, jid="ABCDEFGH-12345")
    (inbox_of(root) / "x.crswap").write_bytes(b"half")
    (inbox_of(root) / "short").mkdir()
    ib.look()
    assert status(upper) is None and not (inbox_of(root) / "short" / "status.json").exists()


@pytest.mark.parametrize("payload", [
    b"\xef\xbb\xbf{}", b"{\"a\": NaN}", b"[1, 2]", b"not json", b"\xff\xfe{",
    b"{\"format\": \"toolbox-job\", \"format\": \"toolbox-job\"}", b"{" * 100000,
])
def test_broken_job_json_is_refused_not_crashed(root, tmp_path, clock, payload):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    (d / "job.json").write_bytes(payload)
    ib.look()
    st = status(d)
    assert st is not None and st["code"] == "bad-job", st
    assert not ib.notes or "could not be read" not in ib.notes[-1]


def test_job_json_larger_than_1_mib_is_refused(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root, options={"pad": "x" * (2**20)})
    ib.look()
    st = status(d)
    assert st is not None and st["code"] == "bad-job", st


def test_an_empty_job_json_is_not_there_yet(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    good = (d / "job.json").read_bytes()
    (d / "job.json").write_bytes(b"")
    ib.look()
    assert status(d) is None                                       # FORMAT 2: empty = not there yet
    (d / "job.json").write_bytes(good)
    ib.look()
    assert status(d)["state"] == "waiting"


def test_a_job_json_that_is_a_folder_is_refused(root, tmp_path, clock):
    """FORMAT 6.3 step 4: anything wrong -> status failed. A job.json that is a directory will never become a file."""
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root, write_job=False)
    (d / "job.json").mkdir()
    for _ in range(3):
        ib.look()
        clock.t += 61
    st = status(d)
    assert st is not None and st["state"] == "failed", "a job.json that is a folder is never answered"


def test_a_file_name_with_a_lone_surrogate_does_not_block_the_inbox(root, tmp_path, clock):
    """A job whose file name is a lone UTF-16 surrogate (valid JSON escape) must not stop the jobs after it."""
    ib = make_inbox(root, tmp_path, clock)
    bad = make_job(root, jid="20261118-000000-aaaaa1")
    doc = json.loads((bad / "job.json").read_text())
    doc["files"][0]["name"] = "\ud800.hpscene"
    (bad / "job.json").write_text(json.dumps(doc))           # ensure_ascii: written as \ud800
    good = make_job(root, jid="20261118-000000-bbbbb2")
    ib.look()
    assert status(good) is not None and status(good)["state"] == "waiting", ib.notes[-1:]
    assert status(bad) is not None and status(bad)["code"] == "bad-job"


# ================================================================ links (FORMAT 7.4, 10)
def test_a_link_in_place_of_a_job_folder_is_never_taken(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    real = make_job(root, jid="20261118-000000-real01")
    outside = tmp_path / "outside-job"
    shutil.move(str(real), outside)
    link = inbox_of(root) / "20261118-000000-real01"
    link.symlink_to(outside, target_is_directory=True)
    ib.look()
    ib.clean(at=time.time() + 400 * tb.DAY)
    assert not (outside / "status.json").exists()
    assert link.is_symlink() and sorted(p.name for p in outside.iterdir()) == ["job.json", "sample-house.hpscene"]


def test_a_link_in_place_of_job_json_or_a_file(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    secret = tmp_path / "secret.hpscene"
    shutil.copy(FILES / "sample-house.hpscene", secret)
    d1 = make_job(root)
    (d1 / "sample-house.hpscene").unlink()
    (d1 / "sample-house.hpscene").symlink_to(secret)
    d2 = make_job(root)
    target = tmp_path / "job-elsewhere.json"
    shutil.move(str(d2 / "job.json"), target)
    (d2 / "job.json").symlink_to(target)
    ib.look()
    assert status(d1)["code"] == "bad-job"
    assert status(d2) is not None and status(d2)["state"] == "failed"
    # the final job's files go – but never through the link
    ib.look()
    assert secret.is_file() and target.is_file()
    ib.clean(at=time.time() + 400 * tb.DAY)
    assert secret.is_file() and target.is_file()


def test_status_json_a_link_is_never_written_through(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ib.look()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    (d / "status.json").unlink()
    (d / "status.json").symlink_to(victim)
    ib.begin(d.name, "Baking")
    ib.finish(d.name, "done", "x")
    ib.look()
    assert victim.read_text() == "keep me"


# ================================================================ waiting for a short file
def test_a_short_file_waits_a_minute_then_fails(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    full = (d / "sample-house.hpscene").read_bytes()
    (d / "sample-house.hpscene").write_bytes(full[:50])
    ib.look()
    clock.t += 59
    ib.look()
    assert status(d) is None
    clock.t += 2
    ib.look()
    assert status(d)["state"] == "failed" and status(d)["code"] == "bad-job"


def test_a_short_file_that_completes_in_time_is_taken(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    full = (d / "sample-house.hpscene").read_bytes()
    (d / "sample-house.hpscene").write_bytes(full[:50])
    ib.look()
    clock.t += 50
    (d / "sample-house.hpscene").write_bytes(full)
    ib.look()
    assert status(d)["state"] == "waiting"


# ================================================================ jobs left by an earlier run, two copies
def _left(root, state, cancel=False):
    d = make_job(root)
    (d / "status.json").write_text(json.dumps(tb.status_doc(d.name, state, text="x")))
    if cancel:
        (d / "cancel.json").write_text(json.dumps({"format": "toolbox-cancel", "version": "0.1", "job": d.name,
                                                   "asked": "2026-11-18T20:31:03+01:00"}))
    return d


def test_jobs_left_by_an_earlier_run(root, tmp_path, clock):
    w = _left(root, "working")
    wc = _left(root, "working", cancel=True)
    wa = _left(root, "waiting")
    dn = _left(root, "done")
    ib = make_inbox(root, tmp_path, clock)
    ib.look()
    assert status(w)["state"] == "failed" and status(w)["code"] == "error"
    assert status(wc)["state"] == "cancelled"
    assert wa.name in ib.jobs and status(wa)["state"] == "waiting"
    assert status(dn)["state"] == "done"
    assert _errors(root) == []


def test_the_text_of_a_cancelled_left_job_spells_the_app_name(root, tmp_path, clock):
    wc = _left(root, "working", cancel=True)
    make_inbox(root, tmp_path, clock)
    assert "Fresing Render" in status(wc)["text"], status(wc)["text"]


def test_two_copies_only_one_takes_a_job(root, tmp_path, clock):
    a = make_inbox(root, tmp_path, clock)
    b = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    a.look()
    b.look()
    assert (d.name in a.jobs) != (d.name in b.jobs)


def test_a_second_window_started_later_does_not_take_or_kill_the_first_windows_job(root, tmp_path, clock):
    """FORMAT 2 / 6.3: a tool may run as several copies; only one copy takes a job. A second window opened while the
    first waits for its user, or bakes, must neither hold the same job nor end it as 'closed while it worked'."""
    a = make_inbox(root, tmp_path, clock)
    d1, d2 = make_job(root), make_job(root)
    a.look()
    assert a.begin(d1.name, "Baking") == ""
    b = make_inbox(root, tmp_path, clock)
    b.look()
    assert status(d1)["state"] == "working", status(d1)
    assert d2.name not in b.jobs, "the waiting job is held by both windows"


def test_cancel_while_waiting(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ib.look()
    (d / "cancel.json").write_text(json.dumps({"format": "toolbox-cancel", "version": "0.1", "job": d.name,
                                               "asked": "2026-11-18T20:31:03+01:00"}))
    ib.look()
    assert status(d)["state"] == "cancelled" and d.name not in ib.jobs
    assert _errors(root) == []


def test_not_now_is_final(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ib.look()
    ib.not_now(d.name)
    assert status(d)["state"] == "cancelled"
    assert ib.begin(d.name, "x") != ""


# ================================================================ replies (7.2)
def _working(root, tmp_path, clock, **kw):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root, **kw)
    ib.look()
    assert ib.begin(d.name, "Baking") == ""
    return ib, d


def test_the_reply_is_written_before_the_status_done(root, tmp_path, clock, monkeypatch):
    ib, d = _working(root, tmp_path, clock)
    order = []
    real = tb.write_json

    def spy(path, doc):
        order.append((Path(path).name, doc.get("state")))
        return real(path, doc)
    monkeypatch.setattr(tb, "write_json", spy)
    rid, text = ib.reply(d.name, [FILES / "sample-house.hpbake"], "Baked")
    assert rid
    assert order.index(("job.json", None)) < order.index(("status.json", "done"))
    st = status(d)
    assert st["state"] == "done" and st["reply"] == rid
    rj = json.loads((inbox_of(root, HP) / rid / "job.json").read_text())
    assert rj["reply_to"] == {"tool": ME, "job": d.name} and "return" not in rj
    assert rj["action"] == "import-bake" and rj["to"] == HP and rj["from"] == ME
    assert rj["title"] == "A house"
    assert _errors(root) == []


@pytest.mark.parametrize("how", ["no-manifest", "does-not-accept", "no-return", "broken-manifest"])
def test_a_reply_nobody_takes_is_kept_and_the_text_says_where(root, tmp_path, clock, how):
    hp = root / "tools" / HP / "toolbox.json"
    kw = {}
    if how == "no-manifest":
        shutil.rmtree(root / "tools" / HP)
    elif how == "does-not-accept":
        doc = json.loads(hp.read_text())
        doc["actions"][0]["accepts"] = ["glb"]
        hp.write_text(json.dumps(doc))
    elif how == "no-return":
        kw["return"] = None
    else:
        hp.write_text('{"format": "toolbox-tool", "version": "0.2"}')
    ib, d = _working(root, tmp_path, clock, **kw)
    rid, text = ib.reply(d.name, [FILES / "sample-house.hpbake"], "Baked")
    assert rid is None
    kept = list((tmp_path / "kept").iterdir())
    assert len(kept) == 1 and kept[0].read_bytes() == (FILES / "sample-house.hpbake").read_bytes()
    st = status(d)
    assert st["state"] == "done" and "reply" not in st
    assert str(tmp_path / "kept") in st["text"] or kept[0].name in st["text"], st["text"]
    assert len(st["text"]) <= 200
    if how != "no-manifest":
        assert not list(inbox_of(root, HP).glob("2026*-*")) or all(
            p.name == "20261118-201500-4b7d10" for p in inbox_of(root, HP).iterdir())


def test_a_reply_with_two_files_that_differ_only_in_capitals(root, tmp_path, clock):
    """3.3: no two files of one job with the same name when capitals are ignored. The reply must not write such a
    job into the sender's inbox."""
    ib, d = _working(root, tmp_path, clock)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    shutil.copy(FILES / "sample-house.hpbake", tmp_path / "a" / "house.hpbake")
    shutil.copy(FILES / "sample-house.hpbake", tmp_path / "b" / "HOUSE.hpbake")
    ib.reply(d.name, [tmp_path / "a" / "house.hpbake", tmp_path / "b" / "HOUSE.hpbake"], "Baked")
    assert _errors(root) == []


def test_a_reply_when_the_keep_folder_cannot_be_made_still_ends_the_job(root, tmp_path, clock):
    shutil.rmtree(root / "tools" / HP)
    ib, d = _working(root, tmp_path, clock)
    (tmp_path / "kept").write_text("a file where the folder should be")
    try:
        ib.reply(d.name, [FILES / "sample-house.hpbake"], "Baked")
    except OSError:
        pass
    assert status(d)["state"] in tb.FINAL, "the job stays 'working' for ever"


# ================================================================ Windows refusals (FORMAT 2)
def test_a_refused_replace_is_tried_again_at_the_next_look(root, tmp_path, clock, monkeypatch):
    ib, d = _working(root, tmp_path, clock)
    real = os.replace

    def refuse(src, dst, *a, **k):
        raise PermissionError(13, "The process cannot access the file", str(dst))
    monkeypatch.setattr(os, "replace", refuse)
    ib.finish(d.name, "done", "Baked")
    clock.t += 30
    ib.look()                                                  # still refused: never raises
    assert status(d)["state"] == "working"
    assert not list(d.glob(".*.tmp")), "temporary files left behind"
    monkeypatch.setattr(os, "replace", real)
    clock.t += 2
    ib.look()
    assert status(d)["state"] == "done"
    assert (root / "tools" / ME / "alive.json").is_file(), "alive.json was not tried again"
    assert _errors(root) == []


def test_a_refused_delete_is_tried_again(root, tmp_path, clock, monkeypatch):
    ib, d = _working(root, tmp_path, clock)
    real = os.unlink

    def refuse(p, *a, **k):
        if str(p).endswith(".hpscene"):
            raise PermissionError(13, "in use", str(p))
        return real(p, *a, **k)
    monkeypatch.setattr(os, "unlink", refuse)
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: refuse(self))
    ib.finish(d.name, "done", "Baked")
    ib.look()
    assert (d / "sample-house.hpscene").exists()
    monkeypatch.undo()
    clock.t += 2
    ib.look()
    assert not (d / "sample-house.hpscene").exists()


def test_a_refused_exclusive_create_does_not_stop_the_other_jobs(root, tmp_path, clock, monkeypatch):
    """On Windows a create can fail with PermissionError (a scanner holds the folder). One such job must not keep the
    others from being taken at the same look."""
    ib = make_inbox(root, tmp_path, clock)
    first, second = make_job(root, jid="20261118-000000-aaaaa1"), make_job(root, jid="20261118-000000-bbbbb2")
    import builtins
    real_open = builtins.open

    def flaky(file, mode="r", *a, **k):
        if "x" in mode and str(file).startswith(str(first)):
            raise PermissionError(13, "in use", str(file))
        return real_open(file, mode, *a, **k)
    monkeypatch.setattr(builtins, "open", flaky)
    ib.look()
    monkeypatch.undo()
    assert status(second) is not None and status(second)["state"] == "waiting"
    ib.look()
    assert status(first) is not None


# ================================================================ the folder itself
def test_an_inbox_that_is_a_file(tmp_path, clock):
    r = tmp_path / "Toolbox"
    (r / "tools" / ME).mkdir(parents=True)
    (r / "tools" / ME / "inbox").write_text("not a folder")
    ib = tb.Inbox(r, "1", keep_dir=tmp_path / "k", clock=clock)
    assert ib.look() == []
    assert ib.problem


def test_the_toolbox_deleted_while_running(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = make_job(root)
    ib.look()
    shutil.rmtree(root)
    clock.t += 20
    ib.look()
    ib.progress(d.name, 0.5, "x")
    ib.finish(d.name, "done", "x")
    ib.look()


def test_the_toolbox_path_is_a_file(tmp_path, clock):
    f = tmp_path / "Toolbox"
    f.write_text("x")
    ib = tb.Inbox(f, "1", keep_dir=tmp_path / "k", clock=clock)
    assert ib.look() == [] and ib.problem


# ================================================================ clean-up (7.4)
def test_clean_after_a_day_and_after_thirty_days(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    fresh = _left(root, "done")
    no_status = make_job(root)
    os.utime(no_status, (time.time() - 31 * tb.DAY,) * 2)
    held = make_job(root)
    ib.look()                                    # takes `held`
    ib.clean(at=time.time() + 3600)
    assert fresh.exists()
    ib.clean(at=time.time() + 1.1 * tb.DAY)
    assert not fresh.exists() and held.exists()
    assert not no_status.exists() or status(no_status) is not None


def test_clean_never_goes_through_a_link_inside_a_job(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    d = _left(root, "done")
    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "precious.txt").write_text("x")
    (d / "sub").symlink_to(keep, target_is_directory=True)
    (d / "file-link").symlink_to(keep / "precious.txt")
    ib.clean(at=time.time() + 40 * tb.DAY)
    assert (keep / "precious.txt").read_text() == "x"


# ================================================================ alive.json (6.4)
def test_alive_removed_only_by_the_copy_that_wrote_the_newest(root, tmp_path, clock, monkeypatch):
    a = make_inbox(root, tmp_path, clock)
    b = tb.Inbox(root, "9.9.9", keep_dir=tmp_path / "k2", clock=clock)
    b.start()
    a.write_alive()
    b.write_alive()                     # same second, same app version: the same bytes
    assert a.remove_alive() is False, "copy A deleted the alive.json copy B wrote last"


def test_alive_is_valid_and_fresh(root, tmp_path, clock):
    ib = make_inbox(root, tmp_path, clock)
    ib.look()
    rep = CHECK.Report("x")
    doc = CHECK.read_doc(root / "tools" / ME / "alive.json", "alive-0", rep, "alive")
    assert doc is not None, rep.errors
    clock.t += 11
    before = (root / "tools" / ME / "alive.json").stat().st_mtime_ns
    time.sleep(0.01)
    ib.look()
    assert (root / "tools" / ME / "alive.json").stat().st_mtime_ns != before


# ================================================================ install / uninstall
def test_install_writes_a_manifest_the_checker_takes(tmp_path):
    r = tmp_path / "Toolbox"
    p = tb.install(r, "1.2.3", program="C:\\Program Files\\Fresing\\Fresing Render.exe", args=["--x"])
    assert p == r / "tools" / ME / "toolbox.json"
    assert _errors(r, allow_missing=False) == []
    m = json.loads(p.read_text())
    assert [a["id"] for a in m["actions"]] == ["import-step", "bake-house"]
    assert m["actions"][1]["accepts"] == ["hpscene"] and m["actions"][1]["returns"] == ["hpbake"]


def test_install_never_through_a_link(tmp_path):
    r = tmp_path / "Toolbox"
    (r / "tools").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (r / "tools" / ME).symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(OSError):
        tb.install(r, "1")
    assert list(elsewhere.iterdir()) == []


def test_uninstall_removes_only_our_folder(root):
    assert tb.uninstall(root)
    assert not (root / "tools" / ME).exists()
    assert (root / "tools" / HP / "toolbox.json").is_file()


def test_uninstall_never_through_a_link(tmp_path):
    r = tmp_path / "Toolbox"
    (r / "tools").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "inbox").mkdir(parents=True)
    (elsewhere / "toolbox.json").write_text("{}")
    (r / "tools" / ME).symlink_to(elsewhere, target_is_directory=True)
    tb.uninstall(r)
    assert (elsewhere / "toolbox.json").is_file()


def test_uninstall_when_tools_is_a_link_deletes_nothing_outside(tmp_path):
    """FORMAT 7.4/10: never deleted through a link. Here ``Toolbox/tools`` itself is a link to another folder."""
    r = tmp_path / "Toolbox"
    r.mkdir()
    other = tmp_path / "other-tools"
    (other / ME / "inbox").mkdir(parents=True)
    (other / ME / "toolbox.json").write_text("{}")
    (r / "tools").symlink_to(other, target_is_directory=True)
    tb.uninstall(r)
    assert (other / ME / "toolbox.json").is_file(), "uninstall deleted a folder outside the Toolbox through a link"


def test_install_when_tools_is_a_link_writes_nothing_outside(tmp_path):
    r = tmp_path / "Toolbox"
    r.mkdir()
    other = tmp_path / "other-tools"
    other.mkdir()
    (r / "tools").symlink_to(other, target_is_directory=True)
    try:
        tb.install(r, "1")
    except OSError:
        pass
    assert list(other.iterdir()) == [], "install wrote through the link Toolbox/tools"


# ================================================================ read_doc against the pinned checker
_KIND_SCHEMA = {"job": "job-0", "status": "status-0", "cancel": "cancel-0", "alive": "alive-0", "tool": "tool-0",
                "folder": "folder-0"}
_SAMPLE_DOCS = {
    "job": SAMPLES / "Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/job.json",
    "status": SAMPLES / "Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/status.json",
    "cancel": SAMPLES / "Toolbox/tools/nl.fresing.render/inbox/20261118-203000-c81e55/cancel.json",
    "alive": SAMPLES / "Toolbox/tools/nl.fresing.render/alive.json",
    "tool": SAMPLES / "Toolbox/tools/nl.fresing.house-planner/toolbox.json",
    "folder": SAMPLES / "Toolbox/toolbox-folder.json",
}
_VALUES = [None, True, False, 0, 1, -1, 5.0, 0.5, 1.5, "", " ", "x", "x" * 41, "x" * 61, "x" * 121, "x" * 201,
           "x" * 301, "x" * 401, "0.1", "0.2", "1.0", "١.٠", "20261118-195100-9f3c2a", "nl.fresing.render",
           "ext:xyz", "ext:", "step", "Step", "https://a", "http://a", "C:/x.exe", "2026-11-18T19:51:00Z",
           "2026-11-18T19:51:00", "2026-13-18T19:51:00Z", "2026-11-18T19:51:00.1234Z", "2026-11-18T24:00:00Z",
           "waiting", "native", "inbox", [], ["step"], ["step", "step"], [1], {}, {"a": 1}, [{}],
           "café", "x\u2028y", "nl.fresing.render\u00a0", "20261118-195100-9F3C2A"]


def _mutants(doc):
    """Yield (label, mutated doc): every field removed / set to many values, nested lists and objects too."""
    yield "unchanged", doc
    yield "extra field", dict(doc, extra=1)
    for k in list(doc):
        m = dict(doc)
        del m[k]
        yield f"-{k}", m
        for v in _VALUES:
            m = dict(doc)
            m[k] = v
            yield f"{k}={v!r}"[:60], m
        if isinstance(doc[k], list) and doc[k] and isinstance(doc[k][0], dict):
            for kk in list(doc[k][0]):
                for v in _VALUES + ["<missing>"]:
                    m = copy.deepcopy(doc)
                    if v == "<missing>":
                        del m[k][0][kk]
                    else:
                        m[k][0][kk] = v
                    yield f"{k}/0/{kk}={v!r}"[:60], m
            m = copy.deepcopy(doc)
            m[k][0]["extra"] = 1
            yield f"{k}/0 extra", m
        if isinstance(doc[k], dict):
            for kk in list(doc[k]) + ["extra"]:
                for v in _VALUES[:20]:
                    m = copy.deepcopy(doc)
                    m[k][kk] = v
                    yield f"{k}/{kk}={v!r}"[:60], m


def _checker_ok(path: Path, kind: str) -> bool:
    rep = CHECK.Report("x")
    doc = CHECK.read_doc(path, _KIND_SCHEMA[kind], rep, "x")
    if doc is None:
        return False
    CHECK._times(doc, ["created", "updated", "asked", "seen"], rep, "x")
    return rep.ok


def _mine_ok(path: Path, kind: str) -> bool:
    try:
        tb.read_doc(path, kind)
        return True
    except tb.Bad:
        return False


@pytest.mark.parametrize("kind", sorted(_SAMPLE_DOCS))
def test_read_doc_agrees_with_the_pinned_checker(tmp_path, kind):
    base = json.loads(_SAMPLE_DOCS[kind].read_text("utf-8"))
    if kind == "tool":                    # make the native manifest's optional fields present too
        base = dict(base, icon="icon.png", types=[])
    p = tmp_path / "doc.json"
    differ = []
    n = 0
    for label, m in _mutants(base):
        p.write_text(json.dumps(m, ensure_ascii=False), "utf-8")
        n += 1
        mine, theirs = _mine_ok(p, kind), _checker_ok(p, kind)
        if mine != theirs:
            differ.append(f"{label}: toolbox.py {'takes' if mine else 'refuses'}, checker "
                          f"{'takes' if theirs else 'refuses'}")
    assert n > 100
    assert differ == [], "\n".join(differ[:20])


@pytest.mark.parametrize("raw", [
    b'{"format": "toolbox-folder", "version": "0.1"}',
    b'\xef\xbb\xbf{"format": "toolbox-folder", "version": "0.1"}',
    b'{"format": "toolbox-folder", "version": "0.1", "version": "0.1"}',
    b'{"format": "toolbox-folder", "version": "0.1\\n"}',
    b'{"format": "toolbox-folder", "version": "0.1\\u0000"}',
    b'{"format": "toolbox-folder", "version": "0.1", "x": Infinity}',
    b'{"format": "toolbox-folder", "version": "0.1", "x": -Infinity}',
    b'{"format": "toolbox-folder", "version": "0.1"} trailing',
    b'{"format": "toolbox-folder", "version": "0.1"}\n\n',
    b'{"format": "toolbox-folder", "version": 0.1}',
    b'{"format": "toolbox-folder", "version": "00.1"}',
    b'{"format": "toolbox-folder", "version": "0.10"}',
    b'{"format": "toolbox-folder", "version": "0.1", "\\t": 1}',
    b'{"format": "toolbox-folder", "version": "0.1", "\\u007f": 1}',
    '{"format": "toolbox-folder", "version": "0.1", "é": 1}'.encode("latin-1"),
    b'{"format": "toolbox-folder", "version": "0.1"' + b' ' * (2**20) + b'}',
])
def test_raw_bytes_agree_with_the_pinned_checker(tmp_path, raw):
    p = tmp_path / "toolbox-folder.json"
    p.write_bytes(raw)
    assert _mine_ok(p, "folder") == _checker_ok(p, "folder"), raw[:80]
