"""Task 0310: the lead motions as sliders on the web 3D page, Blender as a Python module.

The test crane with its Film animation built (``web3d_film.set_up_test``: the boom and trolley move, the camera rides)
and the tour's three lead motions – "Boom up and out" (two windows), "Boom up", "Trolley out" – saved as a web 3D model
with its animation. The file must hold one clip per joint the lead motions use (kept out of the animation), the page
data their rows; the page's sum of the clips must give Blender's places at every tested slider position, alone and
mixed as the app mixes them (a joint in two lead motions: the one moved last wins – the trolley stays out when "Boom
up" moves after "Boom up and out"); and in the browser the sliders pause the animation, play gives the parts back.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, lead_motions, tour, web3d, web3d_film  # noqa: E402
from fresing_render.core import lead_motions as lm  # noqa: E402
from fresing_render.core import web3d as core  # noqa: E402
from fresing_render.core import web3d_env as env  # noqa: E402
from fresing_render.core import web3d_lead as lead  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
DEG = math.radians
POS_TOL = 5e-4          # m: the clips keep every read value within 0.1 mm; between them a turn's chord adds a little
ROT_TOL = 2e-4          # matrix entries (≈ 0.01°)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def add_lead_motions(sc):
    lead_motions.add(sc, "Boom up and out", [lm.Row("Boom", 0.0, DEG(30), 0, 60),
                                             lm.Row("Trolley", 0.0, tour.TROLLEY_RUN, 40, 100, "LINEAR")],
                     description="The boom goes up, then the trolley runs out")
    lead_motions.add(sc, "Boom up", [lm.Row("Boom", 0.0, DEG(35))], seconds=3.0)
    lead_motions.add(sc, "Trolley out", [lm.Row("Trolley", 0.0, tour.TROLLEY_RUN, easing="LINEAR")], seconds=3.0)
    for x in sc.fresing.lead_motions:
        x["position"] = 0.0


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lead")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    web3d_film.set_up_test(sc, extras=False)
    add_lead_motions(sc)
    sc.frame_set(sc.frame_start + 30)                 # the export's pose: the animation's boom partly up
    shown = {j.name: joints.get_value(j) for j in sc.fresing.joints}
    job = web3d.Job(sc, str(tmp / "lead.glb"), size=256, animation=True)
    out = job.run()
    data = open(out["path"], "rb").read()
    doc, binary = core.read_glb(data)
    st = env.page_settings(open(out["html"], encoding="utf-8").read())
    plain = web3d.export(sc, str(tmp / "plain.glb"), size=256, animation=True, lead_motions=False)
    after = {j.name: joints.get_value(j) for j in sc.fresing.joints}
    return {"sc": sc, "job": job, "out": out, "data": data, "doc": doc, "binary": binary, "st": st, "plain": plain,
            "shown": shown, "after": after, "frame": sc.frame_current}


def nodes(m):
    return [(ob, n) for ob, n in m["job"]._nodes]


def blender_places(m, lms_and_positions):
    """Blender's places of every node with these lead motions moved in this order (the app's sliders), then back."""
    sc = m["sc"]
    keep = {j.name: joints.get_value(j) for j in sc.fresing.joints}
    for name, p in lms_and_positions:
        lead_motions.apply(sc, sc.fresing.lead_motions[name], p, refresh=True)
    bpy.context.view_layer.update()
    out = np.array([np.array(ob.matrix_world) for ob, _n in nodes(m)], np.float64)
    for name, v in keep.items():
        joints.set_value(joints.find(sc, name), v, use_limits=False)
    bpy.context.view_layer.update()
    return out


def node_ids(m):
    return [n for _ob, n in nodes(m)]


def trs(t, q, s):
    return lead._trs(t, q, s)


def page_places(m, moves):
    """What the page shows (core/web3d_lead.page_places on the file's clips) after these slider moves [(name, %)]."""
    names = [x["name"] for x in m["st"]["lead"]["motions"]]
    return lead.page_places(m["doc"], m["binary"], m["st"]["lead"], node_ids(m),
                            [(names.index(n), p) for n, p in moves])


def close(a, b):
    dt = np.abs(a[:, :3, 3] - b[:, :3, 3]).max()
    dr = np.abs(a[:, :3, :3] - b[:, :3, :3]).max()
    return dt, dr


def test_one_clip_per_joint_kept_out_of_the_animation(made):
    st, doc = made["st"], made["doc"]
    assert core.problems(made["data"]) == []
    L = st["lead"]
    assert [x["name"] for x in L["motions"]] == ["Boom up and out", "Boom up", "Trolley out"]
    assert len(L["joints"]) == 2                                  # Boom and Trolley: each joint once
    boom, trolley = sorted(range(2), key=lambda j: -L["joints"][j]["parts"])
    assert L["joints"][trolley]["apply"] < L["joints"][boom]["apply"]      # the boom carries the trolley: last
    assert L["joints"][boom]["kind"] == "ROTATE" and L["joints"][trolley]["kind"] == "SLIDE"
    clips = {J["clip"] for J in L["joints"]}
    names = [a["name"] for a in doc["animations"]]
    assert {names[c] for c in clips} == {"Joint 1", "Joint 2"}    # Hide part names: no joint names either
    assert len(doc["animations"]) == 3 and "fr_lead_joint" in doc["animations"][L["joints"][0]["clip"]]["extras"]
    assert doc["extras"]["fr_lead"]["motions"] == L["motions"]   # the same data for other viewers
    up_out = L["motions"][0]
    assert up_out["about"] == "The boom goes up, then the trolley runs out" and up_out["ends"] == ["0 %", "100 %"]
    assert L["motions"][1]["ends"] == ["0°", "35°"] and L["motions"][1]["seconds"] == 3.0
    assert [r["start"] for r in up_out["rows"]] == [0.0, 40.0] and up_out["rows"][1]["easing"] == "LINEAR"
    fps = made["sc"].render.fps / made["sc"].render.fps_base
    assert L["t"] == pytest.approx(30 / fps)                      # the moment of the frame shown
    assert made["out"]["lead_motions"] == 3 and "3 lead motions as sliders" in made["out"]["text"]
    assert made["after"] == pytest.approx(made["shown"]) and made["frame"] == made["sc"].frame_start + 30
    plain_doc, _b = core.read_glb(open(made["plain"]["path"], "rb").read())
    assert len(plain_doc["animations"]) == 1 and "lead" not in env.page_settings(
        open(made["plain"]["html"], encoding="utf-8").read())


@pytest.mark.parametrize("name", ["Boom up and out", "Boom up", "Trolley out"])
def test_each_slider_alone_gives_blenders_places(made, name):
    for p in (0.0, 20.0, 45.0, 50.0, 77.7, 100.0):
        want = blender_places(made, [(name, p)])
        dt, dr = close(page_places(made, [(name, p)]), want)
        assert dt <= POS_TOL and dr <= ROT_TOL, (name, p, dt, dr)


def test_sliders_mixed_as_in_the_app(made):
    for moves in ([("Trolley out", 100.0), ("Boom up", 50.0)],       # a trolley on a boom: the boom carries it
                  [("Boom up", 50.0), ("Trolley out", 60.0)],
                  [("Boom up and out", 100.0), ("Boom up", 50.0)],   # a shared joint: the trolley stays out
                  [("Boom up", 80.0), ("Boom up and out", 30.0)]):   # … and the other way round
        want = blender_places(made, moves)
        dt, dr = close(page_places(made, moves), want)
        assert dt <= POS_TOL and dr <= ROT_TOL, (moves, dt, dr)
    trolley = made["st"]["lead"]["motions"][0]["rows"][1]["j"]
    v = lead.joint_values(made["st"]["lead"]["motions"], [100.0, 50.0, 0.0], [1, 2, 0])
    assert v[trolley] == pytest.approx(tour.TROLLEY_RUN)


def test_the_page_plays_the_sliders(made):
    """The page in headless Chromium: slider positions give Blender's places (``?places=1``) and the joint values of
    core/lead_motions.py; a slider pauses the animation, play gives the parts back and the sliders go back."""
    from test_web_player import NODE, _browser_works, probe
    if not NODE or not _browser_works(os.path.dirname(made["out"]["html"])):
        pytest.skip("no browser (GitHub's Linux runners): the page's sum is checked above in Python")
    names = [x["name"] for x in made["st"]["lead"]["motions"]]
    steps = [{"eval": "frPage.leadState()"},
             {"eval": f"frPage.setMotion({names.index('Boom up and out')}, 100), "
                      f"frPage.setMotion({names.index('Boom up')}, 50), frPage.leadState()"},
             {"wait": 300},
             {"eval": "JSON.parse(document.documentElement.dataset.frPlaces || 'null')"},
             {"eval": "frPage.paused"},
             {"eval": "frPage.paused = false, frPage.leadState()"},
             {"eval": f"frPage.setMotion({names.index('Trolley out')}, 40), frPage.setTime(1.0), frPage.leadState()"},
             {"eval": f"frPage.setMotion(0, 10), frPage.playMotion({names.index('Boom up')})"},
             {"wait": 3600},
             {"eval": "frPage.leadState()"}]
    out = probe(made["out"]["html"], steps, query="soft=0&places=1")
    assert out["ok"], out
    o = out["out"]
    at = [x["at"] or 0.0 for x in made["st"]["lead"]["motions"]]
    assert at[1] > 5.0                                            # the export's boom partly up: "Boom up" not at 0 %
    assert o[0]["on"] is False and [x["pos"] for x in o[0]["motions"]] == pytest.approx(at, abs=1e-3)
    st = o[1]
    assert st["on"] is True and st["motions"][0]["movedBy"] == "Boom up"
    vals = lead.joint_values(made["st"]["lead"]["motions"], [100.0, 50.0, 0.0], [1, 2, 0])
    for j, v in vals.items():
        assert st["joints"][j] == pytest.approx(v, abs=1e-9)
    want = blender_places(made, [("Boom up and out", 100.0), ("Boom up", 50.0)])
    places = o[3]
    for k, (_ob, node) in enumerate(nodes(made)):
        if str(node) not in places:
            continue
        x = np.array(places[str(node)], np.float64)
        got = trs(x[:3], x[3:7], x[7:])
        assert np.abs(got[:3, 3] - want[k][:3, 3]).max() <= POS_TOL, node
        assert np.abs(got[:3, :3] - want[k][:3, :3]).max() <= ROT_TOL, node
    assert o[4] is True                                           # a slider paused the animation
    assert o[5]["on"] is False and all(x["used"] == 0 for x in o[5]["motions"])     # play: the animation rules again
    assert [x["pos"] for x in o[5]["motions"]] == pytest.approx(at, abs=1e-3)       # … the sliders where they began
    assert o[6]["on"] is False                                    # the time line too
    end = o[9]
    assert end["playing"] == -1 and end["motions"][names.index("Boom up")]["pos"] == 100.0       # ▶ ran to 100 %
