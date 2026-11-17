"""The built-in knuckle cranes (KB classes, task 0191) in the app (Blender as a Python module): each STEP imported with
the app's importer, rigged from its equipment file (joints, cylinders, poses through the render kit's sheet reader), then every driven joint moved through its range and a few random poses: every
moving sub-assembly where the maker's kinematics puts it (nothing flies apart), every cylinder's rod in its barrel and
in line, the hook at every named pose within 10 mm of the maker's numbers, the hoist rope made a cable that follows the
hook block, the pads on the ground when set up.
"""

from __future__ import annotations

import pytest

pytest.importorskip("bpy")
pytest.importorskip("OCP")

import lifting_rig as LR  # noqa: E402


@pytest.mark.parametrize("name", ["KB-20", "KB-50", "KB-100", "KB-200"])
def test_knuckle_crane_in_the_app(name, tmp_path):
    r = LR.Rigged(name, out=str(tmp_path))
    assert r.n_joints == len(r.sheet["joints"]) and r.n_cylinders == len(r.sheet["cylinders"])
    assert r.n_poses == len(r.sheet["poses"]) >= 3
    assert r.axis_error[0] <= 0.01 and r.axis_error[1] <= 0.1
    m = LR.measure(r)
    assert m["poses"] >= 5 * len(LR.driven(r.sheet))
    assert m["offset_mm"] <= 1.0 and m["angle_deg"] <= 0.05, m
    assert m["cyl_out_mm"] <= 2.0 and m["cyl_bend_deg"] <= 0.1, m
    hooks = LR.hook_errors(r)
    assert max(e for e, _r, _z in hooks.values()) <= 10.0, hooks
    assert len({(round(rr, 1), round(z, 1)) for _e, rr, z in hooks.values()}) >= 2       # two poses at least differ
    work = next(p for p in r.sheet["poses"] if p["name"] == "Working")["values"]
    assert LR.rope_follows(r, work) <= 20.0
    assert LR.rope_follows(r, {**work, "Hoist": work.get("Hoist", 0.0) + 3000.0}) <= 20.0
    assert LR.pads_lowest_mm(r) <= 3.0
