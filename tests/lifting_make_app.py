"""Helper of the made-crane tests (task 0204, not a test file): a random valid set of numbers of a kind (``params``)
made by the maker (STEP + equipment file), imported with the app's importer and rigged from its file
(``lifting_rig.Rigged`` with the made crane's own dataclass), then 0191's checks – every driven joint from its minimum
to its maximum and random poses against the maker's kinematics, every cylinder in line and in its range, the hook at
every pose – and the clash check of the crane's own motion (its poses one after the other, ``lifting_rig.pose_tour``).

``tests/test_lifting_make_app_<kind>_<part>.py`` each run ``SETS_PER_FILE`` sets; four files per kind give the
brief's 20 per kind (a set takes 15–40 s for a mobile or knuckle-boom crane, 60–180 s for a crawler, mostly the clash
check: one file stays within a few minutes). The seeds are fixed: a failure names its set and its numbers.

The clash check (most of the time) runs on every 4th set – 5 per kind – and on all of them with
``FRESING_ALL_CLASH=1`` (task 0204 ran all 60 on the web machine: clean). Every set gets the kinematic checks.

The own motion is checked at 0.6 s per pose (15 frames at 24 fps): with 0.25 s the clash check's in-between places of
nested telescope sections (each a screw motion of its own) put them 4 mm into each other where they never are.
"""

from __future__ import annotations

import json
import os
import random

import lifting_rig as LR

SETS_PER_FILE = 5
FILES = 4
SEED = {"AT": 1101, "CC": 2202, "KB": 3303}


def sets(kind: str, part: int) -> list:
    """The numbers of this file's sets (the same every run)."""
    from fresing_render.lifting_model import params as P
    rng = random.Random(SEED[kind])
    allsets = [P.random_values(kind, rng) for _ in range(FILES * SETS_PER_FILE)]
    return allsets[part * SETS_PER_FILE:(part + 1) * SETS_PER_FILE]


def check_one(kind: str, i: int, values: dict, out) -> dict:
    """Make, import, rig and check one set. Returns what was measured (the test asserts on it)."""
    from fresing_render.lifting_model import make as M
    from fresing_render.lifting_model import params as P
    name = f"R{kind}{i}"
    folder = out / name
    M.make_crane({"kind": kind, "name": name, "start": P.nearest_class(kind, values), "values": values},
                 str(folder), picture=False)
    cls = P.to_class(kind, values, name)
    r = LR.Rigged(name, folder=str(out), out=str(out / "cache"), cls=cls)
    res = {"set": f"{kind} #{i}", "numbers": json.dumps(values, default=list),
           "joints": (r.n_joints, len(r.sheet["joints"])), "cylinders": (r.n_cylinders, len(r.sheet["cylinders"])),
           "axis_error": r.axis_error}
    res["measure"] = LR.measure(r, steps=4, randoms=2)
    hooks = LR.hook_errors(r)
    res["hook_mm"] = max(e for e, _r, _z in hooks.values())
    every = 1 if os.environ.get("FRESING_ALL_CLASH") else 4
    res["clash"] = LR.clash_rows(r, LR.pose_tour(r, seconds=0.6)) if i % every == 0 else []
    return res


def assert_ok(res: dict) -> None:
    where = f"{res['set']} {res['numbers']}"
    assert res["joints"][0] == res["joints"][1] and res["cylinders"][0] == res["cylinders"][1], where
    assert res["axis_error"][0] <= 0.05 and res["axis_error"][1] <= 0.1, where     # mm, deg (float32 of the app)
    m = res["measure"]
    assert m["offset_mm"] <= 1.0 and m["angle_deg"] <= 0.05, (m, where)
    assert m["cyl_out_mm"] <= 2.0 and m["cyl_bend_deg"] <= 0.1, (m, where)
    assert res["hook_mm"] <= 10.0, (res["hook_mm"], where)
    assert res["clash"] == [], (res["clash"], where)
