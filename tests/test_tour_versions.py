"""Task 0199: the test tour's version fields and their fingerprints (tools/tour_versions.py), the precheck's rule."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import tour_versions as tv  # noqa: E402

SRC = '''
HUB_SET = "crane"

def _shared(b):
    return 1

def _only_mill(scene):
    return "a check only the mill uses – é"

@tour_set(HUB_SET, "Crane", "crane.step", added="0.2.47", changed="0.2.100")
def build_crane(b):
    _shared(b)

@tour_set("mill", "Milling", "mill.step", added="0.2.50")
def build_mill(b):
    _shared(b)   # a comment

stop("joint", MOTION, HUB_SET, "Joint: the boom turns", "The boom turns → up.", since="0.2.47")
stop("chips", MACH, "mill", "Chips fly", "Chips fly – off the bit…", check=_only_mill, since="0.2.50")
'''

BLOBS = {"crane.step": "aaa", "mill.step": "bbb"}


def fps(src=SRC, blobs=BLOBS):
    return tv.fingerprints(src, lambda m: blobs.get(m, ""))


def test_reads_sets_stops_and_versions():
    f = fps()
    assert set(f) == {"crane", "mill"}
    assert f["crane"]["added"] == "0.2.47" and f["crane"]["changed"] == "0.2.100"
    assert f["mill"]["stops"]["chips"]["since"] == "0.2.50"
    assert f["mill"]["helpers"] == ["_only_mill"]          # the shared helper is in neither


def test_version_words_comments_and_layout_do_not_change_the_fingerprint():
    a = fps()
    src = SRC.replace('since="0.2.50")', 'since="0.2.50", changed="0.2.160")')
    src = src.replace('changed="0.2.100"', 'changed="0.2.161"').replace("# a comment", "# another comment")
    src = src.replace('"Chips fly", "Chips', '"Chips fly",\n     "Chips')
    b = fps(src)
    assert {k: v["fp"] for k, v in a.items()} == {k: v["fp"] for k, v in b.items()}


def test_what_changes_a_set():
    a = fps()
    assert fps(SRC.replace("off the bit", "off the cutter"))["mill"]["fp"] != a["mill"]["fp"]      # its stop
    assert fps(SRC.replace("é", "e"))["mill"]["fp"] != a["mill"]["fp"]                            # its own helper
    assert fps(blobs=dict(BLOBS, **{"mill.step": "ccc"}))["mill"]["fp"] != a["mill"]["fp"]        # its test model
    b = fps(SRC.replace("return 1", "return 2"))                                                   # a shared helper
    assert b["mill"]["fp"] == a["mill"]["fp"] and b["crane"]["fp"] == a["crane"]["fp"]


def test_a_changed_set_without_a_raised_changed_fails_and_recording_fixes_it():
    main = tv.as_record(fps())["sets"]
    changed = fps(SRC.replace("off the bit", "off the cutter"))
    # the branch raised the version to 0.2.153 but forgot changed=
    problems, _ = tv.check(changed, main, main, version="0.2.153", raised=True)
    assert any("test tour set 'mill' changed" in p and 'changed="0.2.153"' in p for p in problems), problems
    assert any("tools/tour_versions.py --record" in p for p in problems)
    # still building (version not raised): only notes, the lane run goes on
    problems, notes = tv.check(changed, main, main, version="0.2.152", raised=False)
    assert problems == [] and any("'mill'" in n for n in notes)
    # changed= written, but the file not recorded again
    fixed_src = SRC.replace("off the bit", "off the cutter").replace('"mill.step", added="0.2.50"',
                                                                     '"mill.step", added="0.2.50", changed="0.2.153"')
    fixed = fps(fixed_src)
    problems, _ = tv.check(fixed, main, main, version="0.2.153", raised=True)
    assert problems and all("out of date" in p for p in problems), problems
    # recorded: fine
    problems, _ = tv.check(fixed, tv.as_record(fixed)["sets"], main, version="0.2.153", raised=True)
    assert problems == []


def test_a_new_set_needs_added_and_a_stop_needs_since():
    main = tv.as_record(fps())["sets"]
    src = SRC + '''
@tour_set("new", "New one", "mill.step", added="0.2.50")
def build_new(b):
    pass

stop("fresh", MACH, "new", "Fresh", "New.")
'''
    f = fps(src)
    problems, _ = tv.check(f, tv.as_record(f)["sets"], main, version="0.2.153", raised=True)
    assert any("test tour set 'new' is new" in p and 'added="0.2.153"' in p for p in problems), problems
    assert any("test tour stop 'fresh': write since=" in p for p in problems), problems


def test_the_repository_is_recorded_and_complete():
    """Every set has added=, every stop since=, and tests/data/tour_versions.json matches tour.py."""
    f = tv.current(ROOT)
    with open(os.path.join(ROOT, tv.RECORD), encoding="utf-8") as fh:
        record = tv.read_record(fh.read())
    problems, notes = tv.check(f, record, None, version="9.9.9", raised=True)
    assert problems == [], problems
    assert len(f) >= 44 and sum(len(s["stops"]) for s in f.values()) >= 74


def test_the_precheck_runs_the_rule(monkeypatch):
    import ci_precheck
    monkeypatch.setattr(ci_precheck, "git", lambda *a, **k: "")
    problems, notes = ci_precheck.check_tour_versions("9.9.9", raised=True)
    assert problems == []
