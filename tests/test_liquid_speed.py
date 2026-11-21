"""The coolant liquid's speed (task 0255): the 255,000-cell scene of the brief (a 1200 x 500 table with T-slots and a
sloped tray under it at 2 mm, 3 l/min moving along a slot) for its first 8 s of pour + 4 s with the flow off, with
the helpers this machine has. A time box against a slow-down; the full 60 + 30 s numbers are in the task report
(``python tests/liquid_scenes.py --speed 0,3,4``)."""

from __future__ import annotations

import liquid_scenes as S
from fresing_render.core import liquid_pool as LP

BOX_MS = 300.0          # ms per frame on average (4-core web machine with 3 helpers: ~70; one process: ~110)


def test_the_speed_scene_stays_within_its_time_box():
    helpers = min(3, LP.default_helpers())
    r = S.speed_scene(helpers=helpers, pour_s=8, off_s=4)
    assert r["balance_l"] < 1e-9
    assert r["stepped_share"] < 0.7                           # dry tiles are skipped
    assert r["ms_per_frame"] < BOX_MS, r
