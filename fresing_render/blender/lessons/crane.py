"""The crane lesson (task 0230; written out in study 0123): the test crane from the plain import to a video, 11 steps.

Each step's ``do`` is the button's own call (``bpy.ops.fresing.…``), or for a click on the model the function the
click ends in (the boom's pin → ``tour._boom_joint``). The test tour's crane set (the hub) runs these steps first
(``tour.build_crane``), then its own extra shots: View, Show me and Build it yourself make the same project.
"""

from __future__ import annotations

import math

import bpy

from ..lesson import Lesson, Step, import_model, lesson

BOOM_UP = math.radians(35)
SCENE = "Hero view"               # the saved scene the lesson makes (the tour adds its own "Tour view")
ANIM = "Boom up"
EXPLODED = "Exploded view"        # = the test tour's stop "explode" (its shot is named after the stop's title)


def _tour():
    from .. import tour
    return tour


def joint_on(scene, part: str, kind: str):
    """The joint of this kind that moves the part (by its name), or None."""
    for j in scene.fresing.joints:
        if j.kind == kind and any(m.obj is not None and m.obj.get("fr_name") == part for m in j.members):
            return j
    return None


def _wiggle(part: str, kind: str, amount: float):
    """Show me, after making a joint: it moves there and back once, so you see what it does."""
    def show(scene, t):
        from .. import joints
        j = joint_on(scene, part, kind)
        if j is not None:
            joints.set_value(j, amount * math.sin(math.pi * min(1.0, max(0.0, t))))
    return show


def _look_is(scene, look: str) -> bool:
    from ...core import studio
    return studio.look_matches(look, scene.fresing)


def _cameras(scene) -> int:
    return sum(1 for o in scene.objects if o.get("fr_camera"))


def _anim(scene):
    s = scene.fresing
    return s.animations.get(ANIM) or (s.animations[0] if len(s.animations) else None)


def _boom(scene):
    return _tour()._boom_joint(scene)


def _trolley(scene):
    from mathutils import Vector

    from .. import joints
    t = _tour()
    trolley = t._ob(scene, "TROLLEY.ASM")
    return joints.create(scene, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                         base=t._ob(scene, "BOOM.ASM"), name="Trolley")


def _camera(scene):
    res = bpy.ops.fresing.camera_add(view="HIGH")
    if res != {"FINISHED"}:
        raise RuntimeError(f"Add camera returned {res}")


def _save(scene):
    res = bpy.ops.fresing.shot_save(name=SCENE)
    if res != {"FINISHED"}:
        raise RuntimeError(f"Save scene returned {res}")


def _animation(scene):
    s = scene.fresing
    if s.shots.get(SCENE) is not None:
        s.active_shot = SCENE                          # (the + starts the animation from the scene picked)
    res = bpy.ops.fresing.anim_add()
    if res != {"FINISHED"}:
        raise RuntimeError(f"New animation returned {res}")
    a = s.animations[s.animations_index]
    a.name = ANIM
    a.tail, a.fps = 0.0, "25"
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _step(scene):
    s = scene.fresing
    a = _anim(scene)
    j = joint_on(scene, "BOOM.ASM", "ROTATE")
    s.animations_index = list(s.animations).index(a)
    s.joints_index = list(s.joints).index(j)
    res = bpy.ops.fresing.block_add(kind="JOINT")
    if res != {"FINISHED"}:
        raise RuntimeError(f"Add step returned {res}")
    b = a.blocks[len(a.blocks) - 1]
    b.start, b.duration, b.easing, b.use_from, b.to_angle = 0.0, 2.0, "SMOOTH", True, BOOM_UP
    b.name = "Boom goes up"


def _has_joint_step(scene) -> bool:
    names = {j.name for j in scene.fresing.joints}
    return any(b.kind == "JOINT" and b.joint in names for a in scene.fresing.animations for b in a.blocks)


def _build(scene):
    s = scene.fresing
    a = _anim(scene)
    s.animations_index = list(s.animations).index(a)
    res = bpy.ops.fresing.anim_build()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Build & play returned {res}")


def _root(scene):
    from .. import build
    return build.model_roots(scene)[:1]


def _explode(scene):
    from .. import states
    res = bpy.ops.fresing.explode()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Explode returned {res}")
    bpy.context.view_layer.update()
    states.save_shot(scene, EXPLODED)                 # (the Save scene button, with this name)
    states.reset_pose(scene)                          # (Reset pose: back to CAD)


def _exploded_scene(scene) -> bool:
    return any(len(sh.own_pose.places) >= 2 for sh in scene.fresing.shots)


def _queue(scene):
    s = scene.fresing
    if s.shots.get(SCENE) is not None:
        s.shots_index = s.shots.find(SCENE)            # (the scene picked in the list)
    res = bpy.ops.fresing.queue_add(kind="SHOT")
    if res != {"FINISHED"}:
        raise RuntimeError(f"Add to queue returned {res}")


CRANE = lesson(Lesson(
    "crane", "Crane: from the plain import to a video",
    "Light look, rotate and stacked joints, a camera, a saved scene, an animation, an exploded view, the render queue",
    [
        Step("import.step", "Import the model",
             "Import STEP… read the test crane. It stands still, every part in its CAD place.",
             more="Draft is quick for trying things; Normal for pictures. A model update later keeps all your work.",
             do=import_model("crane"), done=lambda sc: sc.fresing.model_count > 0),
        Step("looks.light_look", "Pick a light look",
             "Product studio sets the background, the light and the floor in one click.",
             more="The looks are starting points: every setting below them can still be changed. The look you picked "
                  "stays pressed while the settings match it.",
             do=lambda sc: _tour()._look("PRODUCT"), done=lambda sc: _look_is(sc, "PRODUCT")),
        Step("joints.rotate", "The boom turns: a rotate joint",
             "The boom is selected. Add rotate joint, then click the boom's pin: the boom turns about it.",
             more="A click on a hole or a shaft gives the axis through its centre. The boom must go up with a plus "
                  "angle: Flip turns the arrow round if it goes down. The luffing cylinder under the boom follows it.",
             parts=("BOOM.ASM", "BOOM.PIN"), select=("BOOM.ASM",), do=_boom,
             done=lambda sc: joint_on(sc, "BOOM.ASM", "ROTATE") is not None,
             show=_wiggle("BOOM.ASM", "ROTATE", math.radians(25))),
        Step("joints.stack", "The trolley runs along the boom",
             "The trolley is selected. Add slide joint, then click along the boom: the trolley rides on the boom's "
             "joint, the two moves add up.",
             more="A joint added to a part that already moves with another joint sits on top of it (a stack). The "
                  "panel says so above the buttons before you click.",
             parts=("TROLLEY.ASM",), select=("TROLLEY.ASM",), do=_trolley,
             done=lambda sc: joint_on(sc, "TROLLEY.ASM", "SLIDE") is not None,
             show=_wiggle("TROLLEY.ASM", "SLIDE", 0.35)),
        Step("scene.camera", "A camera view of your own",
             "The import made a first camera. Add one more: 3/4 hero, high.",
             more="Views: front, side, top, isometric and two 3/4 hero views; More has the rest. The camera frames "
                  "the whole model and becomes the active camera.",
             do=_camera, done=lambda sc: _cameras(sc) >= 2),
        Step("scene.save", "Save the scene",
             f"Save scene keeps the camera, the look, the pose and what is hidden, under a name ('{SCENE}').",
             more="A saved scene is a starting point for pictures and animations: Use scene puts it all back.",
             do=_save, done=lambda sc: len(sc.fresing.shots) > 0),
        Step("animation.add", "An animation",
             "The + in 6 Animation makes an empty animation that starts from your saved scene.",
             more="An animation is a list of steps on a time line. Its start scene sets the camera and the look.",
             do=_animation, done=lambda sc: len(sc.fresing.animations) > 0),
        Step("animation.joint_step", "A step: the boom goes up",
             "Add a step to the animation: Move joint, the boom from 0° to 35° in 2 seconds.",
             more="Steps that overlap in time play together: add a Trolley step at 0 s and both move at once.",
             parts=("BOOM.ASM",), do=_step, done=_has_joint_step),
        Step("animation.build", "Build and play",
             "Build & play turns the steps into the time line and plays them: the boom goes up.",
             more="Build again after a change to the steps. Space plays and stops the animation in the view.",
             do=_build, done=lambda sc: bool(sc.fresing.anim_baked)),
        Step("poses.explode", "An exploded view",
             "Explode moves the crane's subassemblies apart. Save it as a scene, then Reset pose puts it back.",
             more="Distance sets how far the pieces go; Pieces picks the subassemblies or every part. The saved scene "
                  "keeps the exploded places for a picture.",
             select=_root, do=_explode, done=_exploded_scene),
        Step("queue.still", "Render it",
             f"Add a picture of the saved scene '{SCENE}' to the render queue; Start queue renders it.",
             more="The queue renders in the background: you can go on working. Start later renders tonight.",
             do=_queue, done=lambda sc: len(sc.fresing.queue) > 0,
             point={"panel": "FRESING_PT_shots", "button": "fresing.queue_add", "text": "Queue this"}),
    ]))
