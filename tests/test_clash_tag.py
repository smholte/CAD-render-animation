"""Task 0247: "left out of the clash check" as a tag stored in the project (``clash.NO_CLASH``, ``clash.leave_out``).

A demo kit's ROV and the demo's wind park were left out by code registered in ``clash.HOOKS`` (task 0228's open point:
a kit's code is loaded only while the kit is built, so in the reopened project the ROV was checked again). The tag is a
custom property on an object (a model root, an assembly, a part): every part under it is left out – through a save, a
reopen and a model update, with nothing registered. The clash test model (``tests/data/test_clash.step``).
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, clash  # noqa: E402

MODEL = os.path.join(HERE, "data", "test_clash.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    return sc


def _names(sc) -> set:
    return {o.name for o in clash.objects(sc)}


def _cad(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def test_a_tagged_assembly_and_its_parts_are_left_out(scene):
    sc = scene
    every = _names(sc)
    asm = _cad(sc, "ARM.A.ASM")
    under = {o.name for o in build.iter_parts(sc) if clash.left_out(o)}
    assert not under and len(every) > 3
    clash.leave_out(asm)
    under = {o.name for o in build.iter_parts(sc) if clash.left_out(o)}
    assert under and under < every and _names(sc) == every - under
    assert _cad(sc, "ARM.A").name in under and _cad(sc, "POST").name not in under
    clash.leave_out(asm, False)
    assert _names(sc) == every and clash.NO_CLASH not in asm


def test_the_tag_on_a_model_root_stays_through_save_reopen_and_a_model_update(scene, tmp_path):
    sc = scene
    root = build.model_roots(sc)[0]
    clash.leave_out(root)
    assert not _names(sc)                                   # the whole model left out
    assert not any(getattr(f, "__module__", "").endswith(("demo", "demo_park", "demo_rov")) for f in clash.HOOKS)
    path = str(tmp_path / "tagged.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    root = build.model_roots(sc)[0]
    assert root.get(clash.NO_CLASH) and not _names(sc) and len(list(build.iter_parts(sc))) > 3
    # a model update with the same file: a new root object with the same part ID – the scene's list keeps its tag
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft", update_root=root.name) == {"FINISHED"}
    bpy.context.view_layer.update()
    roots = build.model_roots(sc)
    assert len(roots) == 1 and roots[0].get(build.PROP_UID) in sc[clash.NO_CLASH]    # (a new object, the same ID)
    assert clash.left_out(roots[0], sc) and len(list(build.iter_parts(sc))) > 3 and not _names(sc)
    clash.leave_out(roots[0], False)                        # and it can be taken off again
    assert clash.NO_CLASH not in sc and len(_names(sc)) > 3
    res = clash.check(sc, store=False) if sc.fresing.animations else None
    assert res is None or not [r for r in res.rows if r.kind == "CLASH"]
