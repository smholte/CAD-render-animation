"""The mill lesson (task 0230): the test mill cuts a slot – axes, bit, workpiece, raw steel, chips, a close-up camera,
the cut as an animation, Build and a picture of the cut. 12 steps.

The test tour's set "Milling a slot" runs these steps (``tour.build_mill``): its stops (cut faces, chips) show what the
lesson made. Each ``do`` is the button's own call; a click on the model (the bit, the block) is the selection the
button reads.
"""

from __future__ import annotations

import bpy

from ..lesson import Lesson, Step, import_model, lesson

STOCK = "STOCK 200x200x40"
BIT = "END MILL D10"
AXES = (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1)))
SLOT = (("Z", 0.0, 0.8, -25.0), ("X", 0.8, 1.6, 60.0))      # joint, start s, seconds, to mm: plunge, then along X
SCENE = "Close-up"
ANIM = "Mill a slot"


def _tour():
    from .. import tour
    return tour


def _machining():
    from .. import machining
    return machining


def _look_is(scene, look: str) -> bool:
    from .crane import _look_is as look_is
    return look_is(scene, look)


def _slides(scene) -> int:
    """How many of the three axes have a slide joint."""
    from .crane import joint_on
    return sum(1 for _n, part, _d in AXES if joint_on(scene, part, "SLIDE") is not None)


def _axes(scene):
    from mathutils import Vector

    from .. import joints
    from .crane import joint_on
    t = _tour()
    for name, part, d in AXES:
        if joint_on(scene, part, "SLIDE") is None:
            o = t._ob(scene, part)
            joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)


def _need_library():
    from ...core import machining as mcore
    if not mcore.available():
        raise RuntimeError("the Manifold library did not load: run Install.bat again")


def _bit(scene):
    _need_library()
    res = bpy.ops.fresing.mill_add_bit()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Use as bit returned {res}")


def _workpiece(scene):
    _need_library()
    res = bpy.ops.fresing.mill_set_workpiece()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Use as workpiece returned {res}")
    _tour()._hide_finished(scene)                     # the finished part lies on the block (the More text says so)


def _stock_group(scene):
    stock = _tour()._ob(scene, STOCK)
    return scene.fresing.groups.get(stock.get("fr_group", ""))


def _raw(scene):
    s = scene.fresing
    g = _stock_group(scene)
    if g is None:
        raise RuntimeError("the block has no material group")
    s.groups_index = s.groups.find(g.name)            # (the block's group picked in the list)
    g.material = "steel_raw"                          # (Ready-made material… > Raw steel, mill scale)


def _chips(scene):
    _machining().settings(scene).chips = "FEW"


def _camera(scene):
    scene.fresing.view_frame = "SELECTION"            # (Frame: Selection – the block is selected)
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
        s.active_shot = SCENE
    res = bpy.ops.fresing.anim_add()
    if res != {"FINISHED"}:
        raise RuntimeError(f"New animation returned {res}")
    a = s.animations[s.animations_index]
    a.name = ANIM
    a.tail, a.fps = 0.0, "25"
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _anim(scene):
    s = scene.fresing
    return s.animations.get(ANIM) or (s.animations[0] if len(s.animations) else None)


def _steps(scene):
    s = scene.fresing
    a = _anim(scene)
    s.animations_index = list(s.animations).index(a)
    from .crane import joint_on
    parts = {name: part for name, part, _d in AXES}
    for axis, start, seconds, to in SLOT:
        j = joint_on(scene, parts[axis], "SLIDE")          # the axis's joint, whatever the user called it
        if j is None:
            raise RuntimeError(f"no slide joint moves {parts[axis]}")
        joint = j.name
        s.joints_index = s.joints.find(joint)
        res = bpy.ops.fresing.block_add(kind="JOINT")
        if res != {"FINISHED"}:
            raise RuntimeError(f"Add step returned {res}")
        b = a.blocks[len(a.blocks) - 1]
        b.joint, b.start, b.duration, b.easing = joint, start, seconds, "LINEAR"
        b.use_from, b.to_dist = True, to * 0.001


def _joint_steps(scene) -> int:
    """Move joint steps on joints that exist."""
    names = {j.name for j in scene.fresing.joints}
    return sum(1 for a in scene.fresing.animations for b in a.blocks if b.kind == "JOINT" and b.joint in names)


def _build(scene):
    s = scene.fresing
    a = _anim(scene)
    s.animations_index = list(s.animations).index(a)
    res = bpy.ops.fresing.anim_build()
    if res != {"FINISHED"}:
        raise RuntimeError(f"Build & play returned {res}")


def _still(scene):
    scene.frame_set(scene.frame_end)                  # the end of the cut (the time line's last frame)
    res = bpy.ops.fresing.queue_add(kind="STILL")
    if res != {"FINISHED"}:
        raise RuntimeError(f"Add to queue returned {res}")


MILL = lesson(Lesson(
    "mill", "Milling a slot: the bit cuts the block",
    "Three slide axes, a bit and a workpiece, raw steel, chips, a close-up, the cut as an animation and a picture of it",
    [
        Step("import.step", "Import the model",
             "Import STEP… read the test mill: a table, a head, an end mill and a steel block, all standing still.",
             more="Draft is quick for trying things; Normal for pictures.",
             do=import_model("mill"), done=lambda sc: sc.fresing.model_count > 0),
        Step("looks.light_look", "Pick a light look",
             "Product studio sets the background, the light and the floor in one click.",
             do=lambda sc: _tour()._look("PRODUCT"),
             done=lambda sc: _look_is(sc, "PRODUCT")),
        Step("joints.slide", "The axes: three slide joints",
             "Add slide joint three times: the saddle along Y, the table along X, the head along Z.",
             more="Click a long straight edge or a rail for the direction. Name them Y, X and Z: the steps of the cut "
                  "below move them. On this machine the table carries the block: X points to the left, so a positive "
                  "X moves the tool to the right on the block, as on the machine.",
             parts=("Y.ASM", "X.ASM", "Z.ASM"), select=("Y.ASM",), do=_axes,
             done=lambda sc: _slides(sc) == 3),
        Step("milling.cut", "The bit",
             "The end mill is selected. Use as bit (4 Motion > Milling): its shape is read from the part.",
             more="Click the bit itself, not its holder. The list shows what was read: flat end mill, 10 mm.",
             parts=(BIT,), select=(BIT,), do=_bit, done=lambda sc: len(_machining().bits(sc)) > 0),
        Step("milling.workpiece", "The workpiece",
             "The steel block is selected. Use as workpiece: from now on material disappears where the bit moves "
             "through it.",
             more="The test mill's finished part lies on the block and a second bit sits beside the first: both are "
                  "hidden, or the bit would cut them too.",
             parts=(STOCK,), select=(STOCK,), do=_workpiece,
             done=lambda sc: _machining().settings(sc).workpiece is not None),
        Step("looks.materials", "Raw steel",
             "The block's group gets Raw steel (mill scale) in 3 Looks: the cut faces will look freshly machined.",
             more="Ready-made material… lists the looks. The walls and floor of the slot get the machined look by "
                  "themselves.",
             parts=(STOCK,), do=_raw,
             done=lambda sc: _stock_group(sc) is not None and _stock_group(sc).material == "steel_raw",
             point={"panel": "FRESING_PT_looks", "button": "fresing.group_preset"}),
        Step("milling.chips", "Chips",
             "Chips: Few. Chips fly off the bit while it cuts and land on the table and the block.",
             more="Few is quick; Realistic makes as many chips as the material removed would.",
             do=_chips, done=lambda sc: _machining().settings(sc).chips != "NONE"),
        Step("scene.camera", "A close-up camera",
             "The block is selected: Frame Selection, then 3/4 hero, high – a camera close on the block.",
             more="Whole model frames the whole machine; Selection only what is selected.",
             parts=(STOCK,), select=(STOCK,), do=_camera,
             done=lambda sc: sum(1 for o in sc.objects if o.get("fr_camera")) >= 2),
        Step("scene.save", "Save the scene",
             f"Save scene keeps the close-up, the look and what is hidden ('{SCENE}').",
             do=_save, done=lambda sc: len(sc.fresing.shots) > 0),
        Step("animation.add", "An animation",
             "The + in 6 Animation makes an empty animation that starts from your saved scene.",
             do=_animation, done=lambda sc: len(sc.fresing.animations) > 0),
        Step("animation.joint_step", "The cut: two steps",
             "Two Move joint steps: Z down 25 mm in 0.8 s (the plunge), then X 60 mm along in 1.6 s (the slot).",
             more="Linear: the bit moves at one speed, as a machine does when it cuts.",
             parts=(BIT,), do=_steps, done=lambda sc: _joint_steps(sc) >= 2),
        Step("animation.build", "Build and play",
             "Build & play: the bit plunges, cuts the slot, the chips fly and the block shows its cut.",
             do=_build, done=lambda sc: bool(sc.fresing.anim_baked)),
        Step("queue.still", "A picture of the cut",
             "At the end of the time line: Current view in 7 Render queue adds a picture of the cut; Start queue "
             "renders it.",
             do=_still, done=lambda sc: any(j.kind == "STILL" for j in sc.fresing.queue),
             point={"panel": "FRESING_PT_queue", "button": "fresing.queue_add", "text": "Current view"}),
    ]))
