"""The real bake of the made-up sample house committed for House Planner (task 0114,
tests/data/house/sample-house.fresing.hpbake: Draft, 16 samples, Cycles on the 4-core web machine): the pinned
checker passes it against the sample scene with no ERROR and no WARNING, and its structure is what the writer makes."""

import json
import os
import subprocess
import sys
import zipfile

from fresing_render.core import house_scene as hs

HERE = os.path.dirname(__file__)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
BAKE = os.path.join(HERE, "data", "house", "sample-house.fresing.hpbake")
SCENE = os.path.join(PIN, "samples", "sample-house.hpscene")


def test_committed_bake_passes_the_checker():
    r = subprocess.run([sys.executable, os.path.join(PIN, "check.py"), BAKE, "--scene", SCENE],
                       capture_output=True, text=True, cwd=PIN)
    assert r.returncode == 0 and "ERROR" not in r.stdout and "WARNING" not in r.stdout, r.stdout + r.stderr
    assert not hs.structure_problems(BAKE, hs.read_scene(SCENE))


def test_committed_bake_is_a_real_bake():
    doc = json.loads(zipfile.ZipFile(BAKE).read("bake.json"))
    assert doc["generator"]["app"] == "Fresing Render"
    assert doc["light"] == "SOFT" and doc["quality"]["samples"] == 16
    assert [m["id"] for m in doc["moments"]] == ["summer-morning", "summer-evening", "winter-noon", "winter-night"]
    assert [s["season"] for s in doc["snow"]] == ["winter"] and len(doc["photos"]) == 1
    night = doc["moments"][-1]
    assert night["sun_light"] is None and night["encoding"]["exposure"] > 3.0
