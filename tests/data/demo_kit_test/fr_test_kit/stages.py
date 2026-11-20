"""The test kit's stages: import the box, a slide joint and a step, a saved camera, then Build (the app's own)."""

import os

from fresing_app.blender import demo
from fresing_app.blender.demo import Demo as AppDemo
from fresing_app.blender.demo import stage

from . import BOX, CAMERA, FILES, JOINT, TRAVEL


class Demo(AppDemo):
    anim_name = "Test kit"

    def file(self, key: str) -> str:
        return os.path.join(self.model_dir, FILES[key])


@stage("box", "The box on the deck: a slide joint, a step, a saved camera")
def box(d: Demo):
    import bpy
    from mathutils import Vector

    from fresing_app.blender import joints
    res = bpy.ops.fresing.import_step(filepath=d.file("assembly"), quality="draft")
    if res != {"FINISHED"}:
        raise RuntimeError(f"the test box could not be imported: {d.s.last_message}")
    part = d.part("TEST BOX")
    origin = d.mm((1000.0 + BOX / 2, 0.0, BOX / 2))
    jt = joints.create(d.scene, "SLIDE", [part], origin, Vector((1.0, 0.0, 0.0)), name=JOINT)
    jt.slide_min, jt.slide_max, jt.use_limits = 0.0, TRAVEL, True
    d.joint(JOINT, 0.0, 2.0, TRAVEL, slide=True, label="The box slides along the deck")
    d.camera(CAMERA, (2500.0, -9000.0, 3000.0), (2500.0, 0.0, 0.0))
    d.notes.append(f"test kit: joint '{jt.name}', camera '{CAMERA}'")


stage("finish", "Animation")(demo.finish)
