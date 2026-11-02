"""The STEP reader and the background job runner, without Blender."""

import json
import os
import time

import numpy as np
import pytest

pytest.importorskip("OCP")

from fresing_render.importer import runner, step_reader  # noqa: E402

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")


def test_reader_output(tmp_path):
    info = step_reader.read_step(STEP, str(tmp_path), "draft")
    nodes = info["nodes"]
    assert info["stats"]["unique_parts"] == 6
    assert info["stats"]["placed_parts"] == 11
    names = [n["name"] for n in nodes]
    assert names[0] == "TEST.MACHINE"
    frame = next(n for n in nodes if n["name"] == "FRAME")
    assert frame["color"] == [0.976, 0.659, 0.0] or tuple(frame["color"]) == (0.976, 0.659, 0.0)
    arrays = np.load(tmp_path / "meshes.npz")
    p = arrays[f"p{frame['mesh']}"]
    assert np.allclose(p.max(axis=0) - p.min(axis=0), [1.0, 0.6, 0.05], atol=1e-4)
    n = arrays[f"n{frame['mesh']}"]
    assert np.allclose(np.linalg.norm(n, axis=1), 1.0, atol=1e-3)
    t = arrays[f"t{frame['mesh']}"]
    assert t.max() < len(p)
    # placement of a component is a translation in metres
    bolts = [n for n in nodes if n["name"].startswith("ISO 4017")]
    assert len(bolts) == 4 and len({b["mesh"] for b in bolts}) == 1
    xs = sorted(round(b["matrix"][0][3], 3) for b in bolts)
    assert xs == [0.05, 0.05, 0.95, 0.95]


def test_quality_changes_detail(tmp_path):
    draft = step_reader.read_step(STEP, str(tmp_path / "d"), "draft")["stats"]["triangles_unique"]
    fine = step_reader.read_step(STEP, str(tmp_path / "f"), "fine")["stats"]["triangles_unique"]
    assert fine > draft


def test_job_runs_in_background_and_caches(tmp_path):
    job = runner.ImportJob(STEP, "draft", str(tmp_path))
    assert not job.cached
    job.start()
    t0 = time.time()
    while not job.poll():
        assert time.time() - t0 < 120
        time.sleep(0.1)
    assert job.error is None, job.error
    assert job.cached
    with open(os.path.join(job.cache_dir, "tree.json")) as fh:
        assert json.load(fh)["stats"]["placed_parts"] == 11
    # same file + quality -> same cache; other quality -> other cache
    assert runner.ImportJob(STEP, "draft", str(tmp_path)).cache_dir == job.cache_dir
    assert runner.ImportJob(STEP, "fine", str(tmp_path)).cache_dir != job.cache_dir


def test_job_reports_bad_file(tmp_path):
    bad = tmp_path / "broken.step"
    bad.write_text("this is not a STEP file")
    job = runner.ImportJob(str(bad), "draft", str(tmp_path / "cache"))
    job.start()
    t0 = time.time()
    while not job.poll():
        assert time.time() - t0 < 60
        time.sleep(0.1)
    assert job.error
    assert not job.cached
