"""The copy of toolbox-format v0.1.1 in tests/data/toolbox/tbf-v0.1.1 (task 0245; v0.1 in task 0217) is exactly the pinned tag: every file's
SHA-256 matches the list in its PINNED.md, nothing was added or left out; and the app's copy of the reference code
(fresing_render/core/tbf/) is the tag's, byte for byte, but for the one line that says where types.json lies."""

import hashlib
import os
import re

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "toolbox", "tbf-v0.1.1")
APP = os.path.join(os.path.dirname(HERE), "fresing_render", "core", "tbf")


def _listed():
    text = open(os.path.join(PIN, "PINNED.md"), encoding="utf-8").read()
    assert "tag `v0.1.1`" in text and "cc0356c39c1237c1c89d0c557e9cb83b39962e7b" in text
    return dict((name, digest) for digest, name in re.findall(r"^([0-9a-f]{64})  (\S.*)$", text, re.M))


def test_pinned_files_are_the_tag():
    listed = _listed()
    assert len(listed) == 37
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
            assert hashlib.sha256(fh.read()).hexdigest() == digest, f"{rel} is not the pinned v0.1.1 file"


def _read(*p):
    with open(os.path.join(*p), "rb") as fh:
        return fh.read()


def test_app_copy_is_the_tags_code():
    assert _read(APP, "names.py") == _read(PIN, "tbf", "names.py")
    assert _read(APP, "types.json") == _read(PIN, "types.json")
    ours = _read(APP, "detect.py").decode().splitlines()
    tag = _read(PIN, "tbf", "detect.py").decode().splitlines()
    assert len(ours) == len(tag)
    diff = [(a, b) for a, b in zip(ours, tag) if a != b]
    assert len(diff) == 1 and diff[0][1].startswith("TYPES_FILE = ") and "Fresing Render" in diff[0][0], diff
    notice = _read(APP, "__init__.py").decode()
    assert "MIT License" in notice and "cc0356c39c1237c1c89d0c557e9cb83b39962e7b" in notice
