"""Web 3D model with its surroundings (task 0106): what the project's sea, vessel motion, sky and light are, as the
page needs them. Read only: the project is never changed (``vessel_motion.at_rest`` only mutes the motion while the
export reads the parts).

The panel's fold "Surroundings on the page" (``scene.fresing.web3d.env_*``) starts from the project
(``from_project``) and can be changed for one export; ``choice`` turns it into the plain dict of
``core/web3d_env.default_choice``. ``block`` gives the page's settings block and its pictures.
"""

from __future__ import annotations

import math

import bpy
import numpy as np

from ..core import surroundings as S
from ..core import vessel_motion as core_vm
from ..core import web3d as core
from ..core import web3d_env as env

CHOICE_KEYS = tuple(env.default_choice())


# ---------------------------------------------------------------------------
# what the project has
# ---------------------------------------------------------------------------

def _sur():
    from . import surroundings
    return surroundings


def _vm():
    from . import vessel_motion
    return vessel_motion


def project_sea(scene) -> bool:
    """The project's surroundings have a sea (Open sea, Vessel deck, Quayside)."""
    return scene.fresing.background in S.SEA_KINDS


def light_kind(s) -> str:
    """What lights the project, as ``world.apply`` decides: SKY, OVERCAST, HDRI or a studio look."""
    kind = s.lighting
    if s.background == "HDRI":
        kind = "HDRI"
    elif s.background == "SKY" or s.background in S.SEA_KINDS:
        kind = "SKY"
    if kind == "SKY" and s.sky_weather == "OVERCAST":
        kind = "OVERCAST"
    return kind


def from_project(scene) -> dict:
    """The fold's ticks as the project has them now (Surroundings 'As in the project')."""
    s = scene.fresing
    kind = light_kind(s)
    out = env.default_choice()
    out.update(sea=project_sea(scene), sea_state=s.sea_state, vessel=bool(_vm().effective(scene)),
               sky=True, sky_source="PROJECT", sun_height=float(s.sun_elevation),
               sun_direction=float(s.light_rotation) % 360.0,
               clouds="OVERCAST" if kind == "OVERCAST" else "NONE", shadows=True)
    return out


def fill_from_project(scene) -> None:
    """Set the panel's ticks from the project (the project itself does not change)."""
    w = scene.fresing.web3d
    for k, v in from_project(scene).items():
        if k in ("quality", "auto", "haze_strength", "rain_strength", "haze", "rain"):
            continue
        setattr(w, "env_" + k, v)


def choice(scene) -> dict | None:
    """The panel's choice for this export; None with Surroundings 'None' (today's page)."""
    w = scene.fresing.web3d
    if w.env_mode != "PROJECT":
        return None
    out = {k: getattr(w, "env_" + k) for k in CHOICE_KEYS}
    out["haze_strength"] = float(w.env_haze_strength) / 100.0
    out["rain_strength"] = float(w.env_rain_strength) / 100.0
    if not _vm().effective(scene):
        out["vessel"] = False
    if not out["sea"]:
        out["vessel"] = False
    return out


def vessel_modes(scene) -> dict:
    """{object name: 'STILL' | 'LEVEL'} for every object a Still / Level mark covers (the parts it moves too)."""
    vm = _vm()
    if not vm.effective(scene):
        return {}
    owners = vm._still_owners(scene, vm.marked(scene))
    if not owners:
        return {}
    out = {}
    for ob in scene.objects:
        p = ob
        while p is not None:
            if p.name in owners:
                out[ob.name] = owners[p.name]
                break
            p = p.parent
    return out


def deck_objects(scene, ch: dict | None) -> list:
    """The Vessel deck's own objects (hull, deck, rails …, not the sea), when the page shows the sea of a project
    whose surroundings are the deck: the machine stands on it and it moves with the vessel."""
    if not ch or not ch.get("sea"):
        return []
    sur = _sur()
    root = sur.root_object()
    if root is None or root.get("fr_kind") != "DECK":
        return []
    return [ob for ob in sur._objects(scene) if ob.type == "MESH" and ob.get(sur.TAG) not in ("sea", "root")
            and ob.data is not None and len(ob.data.polygons)]


# ---------------------------------------------------------------------------
# the page's blocks
# ---------------------------------------------------------------------------

def _seconds(scene, frame: float) -> float:
    return float(frame) * scene.render.fps_base / max(scene.render.fps, 1)


def sea_block(scene, ch: dict, model_min, model_max) -> dict | None:
    if not ch.get("sea"):
        return None
    s = scene.fresing
    sur = _sur()
    state = ch.get("sea_state", "CALM")
    p = sur.SEA.get(state, sur.SEA["CALM"])
    swell = []
    if ch.get("vessel"):
        swell = [w.as_tuple() for w in core_vm.swell(state, s.vessel.heading)]
    waves = sur._waves(state, swell)
    own = len(sur._waves(state))
    root = sur.root_object()
    sea_ob = _vm()._sea_object()
    if sea_ob is not None and root is not None and root.get("fr_kind") in S.SEA_KINDS:
        at = sea_ob.matrix_world.translation
        origin, level = (float(at.x), float(at.y)), float(at.z)
        mn, mx = np.array(root.get("fr_min", model_min)), np.array(root.get("fr_max", model_max))
        moving = bool(s.sea_moving)
        foam = bool(s.sea_foam)
    else:                                   # the project has no sea: one under the model, as the Open sea puts it
        mn, mx = np.array(model_min, float), np.array(model_max, float)
        origin = (float(mn[0] + mx[0]) / 2, float(mn[1] + mx[1]) / 2)
        level = float(mn[2]) - s.floor_offset + s.water_level
        moving, foam = True, True
    size = np.maximum(mx - mn, 0.05)
    near = max(40.0, 5.0 * float(max(size[0], size[1])))
    return {"state": state, "level": level, "origin": list(origin), "near": near,
            "waves": [list(map(float, w)) for w in waves], "own": own, "bump": float(p["bump"]),
            "foam": float(p["foam"]) if (foam or state == "ROUGH") else None, "moving": moving,
            "amp": float(p["amp"])}


def vessel_block(scene, ch: dict, sea: dict | None) -> dict | None:
    """Heave, roll and pitch as the app's rig plays them (for the page's sea state), the pivot, the bow."""
    vm = _vm()
    if not ch.get("vessel") or sea is None or not vm.effective(scene):
        return None
    st = vm.core_settings(scene)
    p = vm.pivot(scene)
    h = vm.hull(scene)
    if st is None or p is None or h is None:
        return None
    st.state = sea["state"]
    mo = core_vm.motion(st, core_vm.waves_from_tuples(_sur()._waves(sea["state"])))

    def ch_(c):
        return [float(c.base), [[float(a), float(w), float(ph)] for a, w, ph in c.terms]]

    mx, my = h["middle"]
    return {"pivot": [float(p.x), float(p.y), float(p.z)], "heave": ch_(mo.heave), "roll": ch_(mo.roll),
            "pitch": ch_(mo.pitch),
            "ends": [[float(mx - h["length"] / 2), float(my), float(h["water"])],      # the hull's two ends at the
                     [float(mx + h["length"] / 2), float(my), float(h["water"])]],     # waterline (spray)
            "hull": [float(h["length"]), float(h["beam"])]}


def _image_pixels(img) -> np.ndarray:
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)


def light_picture(scene, ch: dict):
    """(bpy image, rotation in degrees, shown as the background) of the project's light picture, or None for the
    app's sky (drawn on the page)."""
    from . import world
    s = scene.fresing
    kind = light_kind(s)
    if not ch.get("sky", True):
        return world.studio_image(), float(s.light_rotation), False
    if ch.get("sky_source") == "TIME" or kind in ("SKY", "OVERCAST"):
        return None
    if kind == "HDRI":
        img = world._load_hdri(s.hdri_path if s.background == "HDRI" else s.light_hdri_path)
    elif kind in world.LOOK_IMAGES:
        img = world.look_image(kind)
    else:
        img = None
    # the camera sees the picture only with a 360° photo background; else the project's colour (or transparent)
    return (img or world.studio_image()), float(s.light_rotation), s.background == "HDRI"


def sky_block(scene, ch: dict) -> tuple[dict, dict]:
    """(the settings block's ``sky``, pictures {id: (mime, bytes)})."""
    from . import web3d
    s = scene.fresing
    q = env.QUALITY.get(ch.get("quality"), env.QUALITY["BALANCED"])
    pic = light_picture(scene, ch)
    if pic is None:                         # the sky drawn on the page
        if ch.get("sky_source") == "TIME":
            height, turn = float(ch["sun_height"]), float(ch["sun_direction"])
        else:
            height, turn = float(s.sun_elevation), float(s.light_rotation)
        return {"kind": "SKY", "sun": env.sun_vector(height, turn), "strength": float(s.light_strength),
                "exposure": float(s.exposure)}, {}
    img, rotation, shown = pic
    src = _image_pixels(img)
    light = env.shrink(env.equirect_for_page(src, rotation, min(1024, img.size[0])), q["light"])
    sun, share = env.brightest(light)
    band = light[light.shape[0] * 7 // 16: light.shape[0] // 2]          # just above the horizon
    horizon = [float(v) for v in band.reshape(-1, 3).mean(axis=0) * float(s.light_strength)]
    pictures = {"light": ("image/vnd.radiance", env.hdr_bytes(light))}
    block = {"kind": "PHOTO", "sun": sun, "sun_share": min(3.0, share / 6.0), "strength": float(s.light_strength),
             "exposure": float(s.exposure), "light": "light", "photo": None, "horizon": horizon}
    if shown:
        width = min(q["sky"], 2 ** int(math.log2(max(img.size[0], 256))))
        bg = env.equirect_for_page(src, rotation, width) * float(s.light_strength)
        mapped = env.agx(bg, 2.0 ** float(s.exposure) * 1.15)
        rgb = core.to_bytes(core.linear_to_srgb(mapped))
        pictures["photo"] = ("image/jpeg", web3d.jpeg(np.flipud(rgb), env.SKY_JPG_QUALITY))
        block["photo"] = "photo"
    else:                                   # a plain background: the project's colour as the app shows it
        colour = s.background_color if s.background == "COLOR" else (0.9, 0.92, 0.95)
        shown_c = env.agx(np.array([[float(c) for c in colour[:3]]]),
                          2.0 ** float(s.exposure) * 1.15)[0]
        block["background"] = [float(c) for c in shown_c]
        block["horizon"] = [float(c) for c in colour[:3]]
    return block, pictures


def block(scene, ch: dict, model_min, model_max, floor: float) -> tuple[dict, dict]:
    """The page's settings block and its pictures for this export."""
    sea = sea_block(scene, ch, model_min, model_max)
    vessel = vessel_block(scene, ch, sea)
    sky, pictures = sky_block(scene, ch)
    frame = scene.frame_start if scene.fresing.web3d.animation else scene.frame_current
    st = env.settings(ch, model_min, model_max, sea=sea, vessel=vessel, sky=sky,
                      time_start=_seconds(scene, frame))
    st["floor"] = float(floor)
    return st, pictures
