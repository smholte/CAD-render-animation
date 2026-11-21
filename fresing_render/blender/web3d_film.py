"""Film on the web 3D page (task 0252): the video's Animation camera, read while the export reads the motion.

``Film`` is made by ``web3d.Job._motion`` before it steps through the frames; ``read`` takes the camera's place,
turn and field of view at each frame (the same frames and frame rate as the page's motion), and – when the export's
tick boxes ask for them – the labels' words on the frames where they hold live numbers. ``block`` gives the page's
``films`` entry (``core/web3d_film.encode`` + captions, labels, title and end card).

What the video shows is read from the same places the video reads it: the captions from ``video.captions_of`` /
``core/brand.caption_list``, the labels from ``scene.fresing.callouts`` (``callouts.usable``, ``window_for``,
``label_text``), the cards from the animation's finishing settings and the brand kit (``video._kit_fields``,
``video._logo_path``). Nothing here changes the project.
"""

from __future__ import annotations

import base64
import math
import os

import numpy as np

import bpy

from ..core import web3d_film as core

LOGO_PX = 640                     # the end card's logo on the page: at most this wide (a 2400 px logo is 100s of KB)


def camera(scene):
    """The built Animation camera (``animation._anim_camera``, keyed by Build), or None."""
    from . import animation
    if not animation.has_keys(scene):
        return None
    ob = next((o for o in scene.objects if o.get("fr_anim_camera") and o.type == "CAMERA"), None)
    if ob is None or not ob.get(animation.TAG):
        return None
    ad = ob.animation_data
    if ad is None or ad.action is None:
        return None
    return ob


def built_animation(scene):
    s = scene.fresing
    return s.animations.get(s.anim_baked) if s.anim_baked else None


def picture_aspect(scene) -> float:
    r = scene.render
    return (r.resolution_x * r.pixel_aspect_x) / max(1.0, r.resolution_y * r.pixel_aspect_y)


def cut_frames(scene) -> list[int]:
    """Scene frames where the video cuts (a Cut step: the camera is the new one from that frame on)."""
    from . import animation
    anim = built_animation(scene)
    if anim is None:
        return []
    return sorted({animation.frame_of(anim, b.start) for b in anim.blocks
                   if b.enabled and b.kind == "CAMERA" and b.camera_mode == "CUT"})


def _logo_url(path: str) -> str:
    """The brand kit's logo as a data address for the page, at most ``LOGO_PX`` wide (PNG)."""
    if not path or not os.path.isfile(path):
        return ""
    from ..core import web3d as w
    from ..core import web3d_env as env
    img = None
    try:
        img = bpy.data.images.load(path, check_existing=False)
        wd, ht = img.size
        if wd <= LOGO_PX and os.path.getsize(path) < 200_000:
            mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
            with open(path, "rb") as fh:
                return f"data:{mime};base64," + base64.b64encode(fh.read()).decode("ascii")
        px = np.empty(wd * ht * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(ht, wd, 4)[::-1]
        px = env.shrink(px, LOGO_PX)
        return "data:image/png;base64," + base64.b64encode(w.png(w.to_bytes(px))).decode("ascii")
    except Exception as exc:  # noqa: BLE001 - a logo never stops an export
        print("Fresing Render: web film logo:", exc)
        return ""
    finally:
        if img is not None:
            bpy.data.images.remove(img)


class Film:
    """One film of the page: the Animation camera over the export's frames."""

    def __init__(self, scene, nodes, place, captions: bool = False, labels: bool = False, cards: bool = False):
        """``nodes``: the export's (object, glTF node) pairs; ``place(ob)``: the node's matrix (Blender world, as the
        node holds it at the frame shown)."""
        from . import callouts
        self.scene = scene
        self.cam = camera(scene)
        self.anim = built_animation(scene)
        self.want = {"captions": captions, "labels": labels, "cards": cards}
        self.mats: list = []
        self.vfov: list = []
        self.frames: list = []
        self.labels: list = []
        size = callouts.picture_size(scene)
        self.size = size
        if labels and scene.fresing.callouts_on:
            node_of = {ob.name: n for ob, n in nodes}
            for c in scene.fresing.callouts:
                if not callouts.usable(c) or c.part.name not in node_of:
                    continue
                anchor = np.array(c.part.matrix_world, np.float64) @ np.array([*c.local, 1.0])
                local = np.linalg.inv(np.array(place(c.part), np.float64)) @ anchor
                win = callouts.window_for(self.anim, c)
                self.labels.append({"c": c, "node": int(node_of[c.part.name]),
                                    "at": [round(float(v), 6) for v in local[:3]],
                                    "w": [round(float(win[0]), 4), round(float(win[1]), 4)] if win else None,
                                    "live": bool(callouts.C.fields_in(c.text)), "texts": []})

    def read(self, frame: int) -> None:
        """The camera (and the labels' live words) at the frame the scene shows now."""
        cam = self.cam
        dg = bpy.context.evaluated_depsgraph_get()
        ev = cam.evaluated_get(dg)
        mw = np.array(ev.matrix_world, np.float64)
        p = np.array(ev.calc_matrix_camera(dg, x=self.size[0], y=self.size[1], scale_x=1.0, scale_y=1.0))
        if ev.data.type == "ORTHO":       # the page has only perspective: the angle that shows the frame at the model
            from . import animation
            fwd = -mw[:3, 2] / max(np.linalg.norm(mw[:3, 2]), 1e-12)
            c = np.array(animation._model_centre(self.scene))
            dist = max(float(np.dot(c - mw[:3, 3], fwd)), 0.01)
            vf = 2.0 * math.atan((1.0 / p[1, 1]) / dist)
        else:
            vf = 2.0 * math.atan(1.0 / p[1, 1])
        self.mats.append(mw)
        self.vfov.append(math.degrees(vf))
        self.frames.append(frame)
        if self.labels:
            from . import callouts
            for it in self.labels:
                if it["live"] or not it["texts"]:
                    text = callouts.label_text(self.scene, it["c"])
                    if not it["texts"] or it["texts"][-1][1] != text:
                        it["texts"].append([len(self.frames) - 1, text])

    def block(self, fps: float, size_m: float) -> dict | None:
        """The page's ``films`` entry, or None (fewer than two frames read)."""
        if len(self.mats) < 2:
            return None
        pos, quat = core.pose(np.array(self.mats))
        f0 = self.frames[0]
        cuts = [f - f0 for f in cut_frames(self.scene) if f0 < f <= self.frames[-1]]
        cuts = sorted(set(cuts) | set(core.find_cuts(pos, quat, self.vfov, size_m)))
        out = core.encode(pos, quat, self.vfov, fps, picture_aspect(self.scene), size_m, cuts=cuts)
        n = len(self.mats)
        from . import video
        anim = self.anim
        if self.want["captions"] and anim is not None:
            caps = core.captions(video.captions_of(anim, self.scene), fps, n)
            if caps:
                out["captions"] = caps
        if self.labels:
            s = self.scene.fresing
            kit = video._kit_fields(s)
            from ..core import callouts as C
            items = []
            for it in self.labels:
                one = {"node": it["node"], "at": it["at"], "w": it["w"]}
                if len(it["texts"]) == 1:
                    one["text"] = it["texts"][0][1]
                else:
                    one["texts"] = [[round(k / fps, 4), t] for k, t in it["texts"]]
                items.append(one)
            out["labels"] = {"size": C.SIZES.get(s.callout_size, C.SIZES["MEDIUM"]), "box": kit["color1"],
                             "fg": kit["color2"], "items": items}
        if self.want["cards"] and anim is not None and (anim.fin_title_on or anim.fin_end_on):
            s = self.scene.fresing
            kit = video._kit_fields(s)
            cards = {"bg": kit["color1"], "fg": kit["color2"]}
            if anim.fin_title_on and anim.fin_title_seconds > 0:
                cards["title"] = {"s": float(anim.fin_title_seconds), "title": anim.fin_title,
                                  "sub": anim.fin_subtitle}
            if anim.fin_end_on and anim.fin_end_seconds > 0:
                cards["end"] = {"s": float(anim.fin_end_seconds), "text": kit["end_text"],
                                "logo": _logo_url(video._logo_path(s))}
            if "title" in cards or "end" in cards:
                out["cards"] = cards
        return out


# ---------------------------------------------------------------------------
# the test set-up shared by the tests and the PC check (task 0252)
# ---------------------------------------------------------------------------

TEST_ANIM = "Film"
CUT_AT, END_AT = 4.0, 5.0


def set_up_test(scene, extras: bool = True):
    """The test crane (``test_crane_a.step`` imported) with a built animation whose camera does it all: rides on the
    boom (0–2 s), flies a path round the crane watching the trolley with a glide-in (2–4 s; ``tour.camera_rides``),
    cuts to a second camera at 4 s and keeps the trolley in the middle from there while it runs back (4–5 s).
    ``extras``: a label on the trolley (during its run back), captions from the labelled steps, a title and an end
    card. Returns the animation."""
    from mathutils import Vector

    from . import animation, build, callouts, cameras, joints, tour
    s = scene.fresing
    tour._boom_joint(scene)
    trolley = tour._ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=tour._ob(scene, "BOOM.ASM"), name="Trolley")
    if scene.camera is None:
        scene.camera = cameras.add_camera(scene, "ISO")
    start = scene.camera
    cut_cam = cameras.add_camera(scene, "ISO_BACK", lens=35.0, name="Film cut")
    scene.camera = start                       # the film starts on the project's camera (add_camera takes over)
    a = s.animations.add()
    a.name, a.tail, a.fps = TEST_ANIM, 0.0, "25"
    tour.camera_rides(scene, a)
    cut = a.blocks.add()
    cut.kind, cut.camera_mode, cut.start, cut.duration = "CAMERA", "CUT", CUT_AT, 0.0
    cut.camera = cut_cam
    aim = a.blocks.add()
    aim.kind, aim.camera_mode, aim.start, aim.duration = "CAMERA", "AIM", CUT_AT, END_AT - CUT_AT
    t_ob = tour._ob(scene, "TROLLEY")
    aim.aim_uid, aim.aim_name = t_ob[build.PROP_UID], "TROLLEY"
    tour._joint_step(a, "Trolley", CUT_AT, END_AT - CUT_AT, 0.1, slide=True, label="The trolley runs back")
    if extras:
        mid = sum((Vector(v) for v in t_ob.bound_box), Vector()) / 8.0       # the label points at its middle
        c = callouts.add(scene, t_ob, t_ob.matrix_world @ mid, text="Trolley", step="The trolley runs back")
        c.enabled = True
        s.callouts_on = True
        a.fin_captions = True
        a.fin_title_on, a.fin_title, a.fin_subtitle, a.fin_title_seconds = True, "Crane", "Test film", 1.0
        a.fin_end_on, a.fin_end_seconds = True, 1.0
    s.animations_index = len(s.animations) - 1
    info = animation.bake(scene, a)
    if info["warnings"]:
        raise RuntimeError("; ".join(info["warnings"][:2]))
    scene.frame_set(scene.frame_start)
    return a
