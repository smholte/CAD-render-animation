"""Task 0246: the rules of the automatic backups (core/backups.py), no Blender."""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fresing_render.core import backups as B  # noqa: E402


def _b(name, when: datetime, size=10, folder="/x"):
    return B.Backup(os.path.join(folder, B.backup_name(name, when)), when, size, when.timestamp())


def _files(folder, name, times):
    paths = []
    for t in times:
        p = os.path.join(folder, B.backup_name(name, t))
        with open(p, "wb") as f:
            f.write(b"x" * 10)
        os.utime(p, (t.timestamp(), t.timestamp()))
        paths.append(p)
    return paths


def test_name_and_parse_round_trip():
    t = datetime(2026, 11, 20, 14, 35)
    n = B.backup_name("Crane A", t)
    assert n == "Crane A backup 2026-11-20 14-35.blend"
    assert B.parse(n, "Crane A") == t
    assert B.parse(B.backup_name("Crane A", datetime(2026, 11, 20, 14, 35, 7), seconds=True), "Crane A") == \
        datetime(2026, 11, 20, 14, 35, 7)


def test_parse_refuses_other_files():
    for other in ("Crane A.blend", "Crane A backup 2026-11-20 14-35.blend1", "Crane B backup 2026-11-20 14-35.blend",
                  "Crane A backup 2026-13-20 14-35.blend", "Crane A backup 2026-11-20 14-35 copy.blend",
                  "Crane A backup  2026-11-20 14-35.blend", "notes.txt", "Crane A backup 2026-11-20.blend"):
        assert B.parse(other, "Crane A") is None, other
    # a project whose own name looks like a backup's start is not mixed up with a longer name
    assert B.parse("Crane A x backup 2026-11-20 14-35.blend", "Crane A") is None


def test_project_name():
    assert B.project_name(os.path.join("C:", "jobs", "Mill.blend")) == "Mill"
    assert B.project_name("") == B.UNSAVED_NAME


def test_keep_last_and_one_a_day_with_a_day_boundary():
    today = date(2026, 11, 20)
    times = [datetime(2026, 11, 20, 10, m) for m in range(0, 60, 5)]            # 12 today
    times += [datetime(2026, 11, 19, 23, 59), datetime(2026, 11, 19, 8, 0)]    # yesterday, late and early
    times += [datetime(2026, 11, 20, 0, 0)]                                     # just after midnight
    times += [datetime(2026, 11, 13, 12, 0), datetime(2026, 11, 14, 12, 0)]    # 7 and 6 days ago
    items = [_b("P", t) for t in times]
    kept = {b.when for b in items if b.path in B.keep(items, 5, 7, today)}
    newest5 = sorted(times, reverse=True)[:5]
    assert set(newest5) <= kept
    assert datetime(2026, 11, 19, 23, 59) in kept           # newest of yesterday
    assert datetime(2026, 11, 19, 8, 0) not in kept         # an older one of that day goes
    assert datetime(2026, 11, 14, 12, 0) in kept            # 6 days ago: day 7 of 7 counting today
    assert datetime(2026, 11, 13, 12, 0) not in kept        # 7 days ago: outside
    assert datetime(2026, 11, 20, 0, 0) not in kept         # today's newest is already kept
    assert len(kept) == 5 + 2


def test_keep_n_zero_and_d_zero():
    today = date(2026, 11, 20)
    items = [_b("P", datetime(2026, 11, d, 12, 0)) for d in range(10, 21)]
    assert B.keep(items, 0, 0, today) == set()
    assert len(B.keep(items, 3, 0, today)) == 3
    by_day = B.keep(items, 0, 3, today)
    assert {b.when.day for b in items if b.path in by_day} == {18, 19, 20}


def test_a_backup_from_the_future_is_kept():
    today = date(2026, 11, 20)
    items = [_b("P", datetime(2026, 11, 21, 9, 0)), _b("P", datetime(2026, 11, 1, 9, 0))]
    assert items[0].path in B.keep(items, 0, 0, today)


def test_clean_leaves_foreign_files_and_the_project(tmp_path):
    folder = str(tmp_path)
    times = [datetime(2026, 11, 20, 10, m) for m in range(8)]
    paths = _files(folder, "Mill", times)
    foreign = ["Mill.blend", "Mill.blend1", "Mill backup notes.txt", "Lathe backup 2026-11-20 10-00.blend",
               "Mill backup 2026-11-20 10-00.blend.tmp"]
    for n in foreign:
        (tmp_path / n).write_bytes(b"y")
    (tmp_path / "Mill backup 2026-11-01 10-00.blend").mkdir()          # a folder with a backup's name stays
    gone = B.clean(folder, "Mill", 3, 0, date(2026, 11, 20))
    assert sorted(gone) == sorted(paths[:5])
    left = sorted(os.listdir(folder))
    for n in foreign:
        assert n in left
    assert sorted(os.path.basename(p) for p in paths[5:]) == sorted(
        n for n in left if B.parse(n, "Mill") and os.path.isfile(os.path.join(folder, n)))
    assert (tmp_path / "Mill backup 2026-11-01 10-00.blend").is_dir()


def test_free_name_never_overwrites(tmp_path):
    t = datetime(2026, 11, 20, 14, 35, 10)
    a = B.free_name(str(tmp_path), "P", t)
    open(a, "wb").close()
    b = B.free_name(str(tmp_path), "P", t)
    assert b != a and B.parse(os.path.basename(b), "P") is not None
    open(b, "wb").close()
    c = B.free_name(str(tmp_path), "P", t)
    assert c not in (a, b) and B.parse(os.path.basename(c), "P") is not None


def test_listing_newest_first_and_sizes(tmp_path):
    times = [datetime(2026, 11, 20, 10, 0), datetime(2026, 11, 20, 12, 0), datetime(2026, 11, 19, 12, 0)]
    _files(str(tmp_path), "P", times)
    found = B.listing(str(tmp_path), "P")
    assert [b.when for b in found] == sorted(times, reverse=True)
    assert B.total_size(found) == 30
    assert B.listing(str(tmp_path / "missing"), "P") == []


def test_due_space_and_newer():
    assert not B.due(1000.0, 800.0, 5)
    assert B.due(1100.0, 800.0, 5)
    assert B.enough_space(200, 100) and not B.enough_space(199, 100)
    b = B.Backup("/x", datetime(2026, 11, 20), 1, 1000.0)
    assert B.newer_than_saved(b, 900.0)
    assert not B.newer_than_saved(b, 999.0)                 # within the margin: the same moment
    assert not B.newer_than_saved(None, 0.0)
    assert B.newest_newer([b], 2000.0) is None


def test_unsaved_offer_window_and_handled(tmp_path):
    now = time.time()
    young = B.Backup("/u/a", datetime.now(), 1, now - 3600)
    old = B.Backup("/u/b", datetime.now(), 1, now - 30 * 3600)
    assert B.unsaved_offer([young, old], now, []) is young
    assert B.unsaved_offer([young, old], now, ["a"]) is None              # handled, and the next one is too old
    assert B.unsaved_offer([old], now, []) is None
    state = str(tmp_path / "cfg" / B.STATE_FILE)
    B.mark_handled(state, ["/u/a"])
    assert B.load_state(state)["handled"] == ["a"]
    (tmp_path / "bad.json").write_text("[1, 2")
    assert B.load_state(str(tmp_path / "bad.json"))["handled"] == []


def test_folders_and_texts():
    docs = os.path.join("D", "Docs")
    assert B.folders("", docs) == [os.path.join(docs, "Fresing Render", "Backups", "Unsaved projects")]
    proj = os.path.join("D", "jobs", "Mill.blend")
    f = B.folders(proj, docs)
    assert f[0] == os.path.join(os.path.dirname(os.path.abspath(proj)), "Backups")
    assert os.path.dirname(f[1]).endswith(os.path.join("Fresing Render", "Backups", "Projects"))
    assert os.path.basename(f[1]).startswith("Mill ")
    other = B.fallback_folder(docs, os.path.join("E", "other", "Mill.blend"))
    assert other != f[1]                            # same name, another place: never one folder
    assert B.size_text(226 * 1024 ** 2) == "226 MB" and B.size_text(3 * 1024 ** 3) == "3.0 GB"
    t = datetime.now().replace(hour=14, minute=35)
    b = B.Backup("/x", t, 1, t.timestamp())
    assert "14:35" in B.offer_text(b, t.replace(minute=10).timestamp())
    assert "never saved" in B.offer_text(b, None)
    assert B.clamp(0, B.RANGE_MINUTES) == 1 and B.clamp(99, B.RANGE_KEEP) == 50


def test_unsaved_backups_carry_the_first_models_name(tmp_path):
    """Task 0291: a never-saved project's backups are named after its first model, and every one is found."""
    assert B.unsaved_name("Test crane") == "Test crane"
    assert B.unsaved_name("") == B.unsaved_name("  ") == B.UNSAVED_NAME
    t = datetime(2026, 11, 24, 10, 5)
    assert B.parse_any(B.backup_name("Test crane", t)) == ("Test crane", t)
    assert B.parse_any(B.backup_name("A backup plan", t, seconds=True)) == ("A backup plan", t)
    assert B.parse_any("Test crane.blend") is None and B.parse_any("notes backup x.blend") is None
    assert B.parse_any(" backup 2026-11-24 10-05.blend") is None
    folder = tmp_path / "Unsaved projects"
    folder.mkdir()
    _files(str(folder), "Test crane", [t])
    _files(str(folder), B.UNSAVED_NAME, [datetime(2026, 11, 24, 9, 0)])
    (folder / "Test crane.blend").write_bytes(b"x")
    found = B.listing(str(folder), None)
    assert [os.path.basename(b.path) for b in found] == [B.backup_name("Test crane", t),
                                                          B.backup_name(B.UNSAVED_NAME, datetime(2026, 11, 24, 9, 0))]
    docs = str(tmp_path / "docs")
    unsaved = B.unsaved_folder(docs)
    os.makedirs(unsaved)
    _files(unsaved, "Test crane", [t])
    assert len(B.all_backups("", docs)) == 1
    assert len(B.listing(unsaved, "Test crane")) == 1 and B.listing(unsaved, B.UNSAVED_NAME) == []
