"""Task 0356: the app's with-pack tests on the REAL Fresing assets pack (not the made-up test pack).

Run only where a real pack is at hand – ``FRESING_ASSETS_REAL=<the folder holding pack.json>``: the "Real pack" job of
tests.yml (the pinned download), the by-hand workflow "Check an assets pack" (any ``assets-*`` release, before a branch
moves the pin) and a worker's session before it uploads a pack (CLAUDE.md section 5, "Assets pack checks"). Not in a
pytest group (``tools/ci_groups.py`` takes only ``tests/test_*.py``): without the variable every test here is skipped.

A plug-in task that wires a kind (0360 looks, 0361 light, …) adds its with-pack checks here, next to its test-pack
tests: they then run on every real pack before an app release names it.
"""

import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REAL = os.environ.get("FRESING_ASSETS_REAL", "")

pytestmark = pytest.mark.skipif(not REAL, reason="FRESING_ASSETS_REAL is not set: no real assets pack here")

from fresing_render.core import assets_pack as ap  # noqa: E402
from fresing_render.core import assets_registry as reg  # noqa: E402


def _app_version() -> str:
    with open(os.path.join(ROOT, "fresing_render", "__init__.py"), encoding="utf-8") as f:
        return re.search(r'^__version__\s*=\s*"([^"]+)"', f.read(), re.M).group(1)


@pytest.fixture(scope="module")
def found():
    assert os.path.isfile(os.path.join(REAL, ap.PACK_JSON)), f"{REAL} holds no pack.json"
    return ap.read(REAL, _app_version())


def test_this_app_reads_the_pack_with_no_note(found):
    assert found.state == "ok" and found.note == "" and found.pack.left_out == [], ap.describe(found)


def test_every_file_is_there_with_its_sha256(found):
    v = ap.verify(found.pack)
    assert v.ok, v.problems[:20]


def test_the_registry_takes_every_item_and_each_has_its_code_look(found):
    r = reg.Registry.build(found)
    assert r.refused == [] and r.note == "" and r.problems() == [], (r.refused[:10], r.note)
    code = reg.code_ids()
    for full_id, a in r.usable.items():
        assert r.resolve(full_id).source == "pack", full_id
        without = r.resolve(full_id, use_pack=False)
        assert without.source == "code" and without.id, full_id            # the app without the pack still answers
        if a.kind in reg.TWIN_ONLY:
            assert a.code_id in code[a.kind], full_id


def test_the_found_pack_is_what_find_gives_with_the_variable(found, monkeypatch):
    monkeypatch.setenv(ap.ENV, REAL)
    again = ap.find(_app_version())
    assert again.state == "ok" and again.pack.version == found.pack.version
