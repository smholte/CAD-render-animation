"""The copy of house-scene-format v1.0 in tests/data/house/hsf-v1.0 (task 0114) is exactly the pinned tag: every
file's SHA-256 matches the list in its PINNED.md, and nothing was added or left out."""

import hashlib
import os
import re

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
ROOT = os.path.dirname(HERE)


def _listed():
    text = open(os.path.join(PIN, "PINNED.md"), encoding="utf-8").read()
    assert "tag `v1.0`" in text and "52c0352d28c70ba4add21d8fbcfc362da698f397" in text
    return dict((name, digest) for digest, name in re.findall(r"^([0-9a-f]{64})  (\S+)$", text, re.M))


def test_pinned_files_are_the_tag():
    listed = _listed()
    assert len(listed) == 14
    found = set()
    for base, dirs, files in os.walk(PIN):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), PIN).replace(os.sep, "/")
            if rel != "PINNED.md":
                found.add(rel)
    assert found == set(listed), f"files added or missing: {sorted(found ^ set(listed))}"
    for rel, digest in listed.items():
        with open(os.path.join(PIN, rel), "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == digest, f"{rel} is not the pinned v1.0 file"


def test_sample_scene_in_the_extension_is_the_pinned_sample():
    with open(os.path.join(ROOT, "fresing_render", "data", "sample-house.hpscene"), "rb") as a, \
            open(os.path.join(PIN, "samples", "sample-house.hpscene"), "rb") as b:
        assert a.read() == b.read(), "copy tests/data/house/hsf-v1.0/samples/sample-house.hpscene to fresing_render/data/"
