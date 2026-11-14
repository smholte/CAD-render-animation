"""The crane lesson (task 0123 – PROTOTYPE): the test crane set up from the plain import, one function per step.

Each step's ``do`` is the call the test tour's crane set build makes (tour.py ``build_crane``): in the build task the
set build is *made of* these steps (``tour.build_crane`` = run every step's ``do`` in order, then the tour's extra
shots), so there is one recipe for View, Show me and Build it yourself.
"""

from __future__ import annotations

import math
import tempfile

import bpy

from . import tour
from .lesson import Lesson, Step, lesson

BOOM_UP = math.radians(35)


def _b(scene):
    return tour.Build(scene, tempfile.gettempdir(), "lesson")


def _joint_on(scene, part: str, kind: str):
    for j in scene.fresing.joints:
        if j.kind == kind and any(m.obj is not None and m.obj.get("fr_name") == part for m in j.members):
            return j
    return None


def _wiggle(part: str, kind: str, amount: float):
    """Show me, after making a joint: it moves there and back once, so you see what it does."""
    def show(scene, t):
        from . import joints
        j = _joint_on(scene, part, kind)
        if j is not None:
            joints.set_value(j, amount * math.sin(math.pi * t))
    return show


def _anim(scene):
    return scene.fresing.animations.get("Boom up")


lesson(Lesson("crane", "Test crane: from the plain import to a video", "test_crane_a.step", [
    Step("import.step", "Import the model",
         "Import STEP… reads the crane. It stands still, every part in its CAD place.",
         more="Draft is quick for trying things; Normal for pictures. A model update later keeps all your work.",
         do=None, done=lambda sc: sc.fresing.model_count > 0),
    Step("looks.light_look", "Pick a light look",
         "Product studio sets the background, the light and the floor in one click.",
         more="The looks are starting points: every setting below them can still be changed. The look you picked "
              "stays pressed while the settings match it.",
         do=lambda sc: tour._look("PRODUCT"),
         done=lambda sc: _look_is(sc, "PRODUCT")),
    Step("joints.rotate", "The boom turns: a rotate joint",
         "The boom is selected. Add rotate joint, then click the boom's pin: it turns about that pin.",
         more="A click on a hole or a shaft gives the axis through its centre. The boom must turn up with a plus "
              "angle: Flip turns the arrow round if it goes down.",
         parts=("BOOM.ASM", "BOOM.PIN"), select=("BOOM.ASM",),
         do=lambda sc: tour._boom_joint(sc),
         done=lambda sc: _joint_on(sc, "BOOM.ASM", "ROTATE") is not None,
         show=_wiggle("BOOM.ASM", "ROTATE", math.radians(25))),
    Step("joints.stack", "The trolley runs along the boom",
         "Add slide joint, then click along the boom. It rides on the boom's joint: the moves add up.",
         more="A joint added to a part that already moves with another joint sits on top of it (a stack). The panel "
              "says so above the buttons before you click.",
         parts=("TROLLEY.ASM",), select=("TROLLEY.ASM",),
         do=lambda sc: _trolley(sc),
         done=lambda sc: _joint_on(sc, "TROLLEY.ASM", "SLIDE") is not None,
         show=_wiggle("TROLLEY.ASM", "SLIDE", 0.35)),
    Step("scene.camera", "A camera view of your own",
         "The import made a first camera. Add one more: 3/4 hero, high.",
         more="Views: front, side, top, isometric and two 3/4 hero views; More has the rest. The camera fits the "
              "whole model.",
         # the button's own call (the tour build's "ISO" camera has no button of its own: only in More)
         do=lambda sc: bpy.ops.fresing.camera_add(view="HIGH"),
         # the import already makes one camera: a check compares with the plain import, never "is there one"
         done=lambda sc: sum(1 for o in sc.objects if o.get("fr_camera")) >= 2),
    Step("scene.save", "Save the scene",
         "Saved scene keeps the camera, the look, the pose and what is hidden, under a name.",
         do=lambda sc: tour._shot(_b(sc), "Tour view"),
         done=lambda sc: len(sc.fresing.shots) > 0),
    Step("animation.add", "An animation", "+ in 6 Animation makes an empty animation that starts from your scene.",
         do=lambda sc: tour._animation(_b(sc), "Boom up", "Tour view"),
         done=lambda sc: len(sc.fresing.animations) > 0),
    Step("animation.joint_step", "A step: the boom goes up",
         "Add a joint step: Boom from 0° to 35° in 2 seconds.",
         more="Steps that overlap in time play together: add a Trolley step at 0 s and both move at once.",
         parts=("BOOM.ASM",),
         do=lambda sc: tour._joint_step(_anim(sc) or sc.fresing.animations[0], _joint_on(sc, "BOOM.ASM", "ROTATE").name,
                                        0.0, 2.0, BOOM_UP, label="Boom goes up"),
         done=lambda sc: any(b.kind == "JOINT" for a in sc.fresing.animations for b in a.blocks)),
    Step("animation.build", "Build and play", "Build & play bakes the steps into the time line and plays them.",
         do=lambda sc: tour._bake(sc, _anim(sc) or sc.fresing.animations[0]),
         done=lambda sc: bool(sc.fresing.anim_baked)),
    Step("poses.explode", "Exploded view", "Explode moves the crane's subassemblies apart: a picture of how it goes "
         "together. Everything back to CAD position undoes it.",
         do=lambda sc: _explode(sc), done=lambda sc: any(s.name == "Exploded" for s in sc.fresing.shots)),
    Step("queue.still", "Render it", "Add a picture of the saved scene to the render queue; Start renders it.",
         more="The queue renders in the background: you can go on working. Start later renders tonight.",
         do=lambda sc: _queue(sc), done=lambda sc: len(sc.fresing.queue) > 0),
]))


def _look_is(scene, look: str) -> bool:
    from ..core import studio
    return studio.look_matches(look, scene.fresing)


def _trolley(scene):
    from mathutils import Vector

    from . import joints
    t = tour._ob(scene, "TROLLEY.ASM")
    return joints.create(scene, "SLIDE", [t], t.matrix_world.translation.copy(), Vector((1, 0, 0)),
                         base=tour._ob(scene, "BOOM.ASM"), name="Trolley")


def _explode(scene):
    from . import build, states
    states.explode(scene, build.model_roots(scene)[0], 0.6)
    bpy.context.view_layer.update()
    states.save_shot(scene, "Exploded")
    states.reset_pose(scene)


def _queue(scene):
    from . import queue
    queue.add_job(scene, "STILL", shot=scene.fresing.shots[0].name)
