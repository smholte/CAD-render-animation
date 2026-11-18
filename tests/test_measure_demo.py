"""Task 0195: tools/measure_demo.py runs on a small made-up project and writes its text block and numbers.

The tool itself is for the big demo project (and the owner's PC, with a window); here it runs as Blender as a Python
module in a process of its own (it reads factory settings and opens the project, as on the owner's PC) on a scene with
one of each kind it measures: a part, a copy sharing its mesh, a Geometry Nodes modifier, a Child Of constraint, a
driver, keys over 60 frames and a joint."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import measure_demo  # noqa: E402

CRANE = os.path.join(HERE, "data", "test_crane_a.step")

MAKE = r'''
import sys
sys.path.insert(0, sys.argv[1])
import bpy, addon_utils
from mathutils import Vector
import fresing_render
from fresing_render.blender import build, joints
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
assert bpy.ops.fresing.import_step(filepath=sys.argv[3], quality="draft") == {"FINISHED"}
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 60
def ob(name):
    return sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))[0]
pin = ob("BOOM.PIN")
origin, direction, _d = joints.axis_from_hit(pin, 0, Vector((0.1, 0.3, 0.42)), Vector((0, 0, 1)))
joints.create(sc, "ROTATE", [ob("BOOM.ASM")], origin, direction, ref=pin, name="Boom")
coll = bpy.data.collections.new("Machine")
sc.collection.children.link(coll)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
a = bpy.context.active_object
a.name = "Part A"
for c in list(a.users_collection):
    c.objects.unlink(a)
coll.objects.link(a)
b = a.copy()                                  # a copy sharing the mesh
b.name = "Part B"
b.location.x = 3
coll.objects.link(b)
c = a.copy()
c.data = a.data.copy()                        # an identical mesh that is NOT shared
c.name = "Part C"
c.location.x = -3
coll.objects.link(c)
ng = bpy.data.node_groups.new("FR flex", "GeometryNodeTree")
ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
i, o = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
ng.links.new(i.outputs[0], o.inputs[0])
m = b.modifiers.new("FR flex", "NODES")
m.node_group = ng
rig = bpy.data.objects.new("FR Vessel", None)
sc.collection.objects.link(rig)
for x in (a, b, c):
    con = x.constraints.new("CHILD_OF")
    con.target = rig
    con.set_inverse_pending = False
rig.keyframe_insert("location", frame=1)
rig.location.z = 2
rig.keyframe_insert("location", frame=60)
fc = c.driver_add("scale", 2)
fc.driver.type = "AVERAGE"
v = fc.driver.variables.new()
v.targets[0].id = rig
v.targets[0].data_path = "location.z"
a["fr_arr"] = [0.0] * 1000
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[2])
'''


def test_helpers():
    assert measure_demo.plain("FR flex.003") == "FR flex"
    assert measure_demo.plain("Hose 12") == "Hose"
    r = measure_demo.Result()
    r.head("A")
    r.line("one")
    r.frame_costs += [("small", 0.1), ("big", 9.0)]
    r.action_costs += [("save", 2.0)]
    t = r.text()
    assert "## A" in t and "one" in t
    assert t.index("big") < t.index("small")                 # the top list is sorted, biggest first
    assert "## Slowest actions" in t and "save" in t


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    d = tmp_path_factory.mktemp("measure")
    blend = str(d / "small project.blend")
    make = subprocess.run([sys.executable, "-c", MAKE, ROOT, blend, CRANE], capture_output=True, text=True, timeout=600)
    if make.returncode != 0 or not os.path.isfile(blend):
        pytest.fail(make.stdout[-3000:] + make.stderr[-3000:])
    out, txt = str(d / "r.json"), str(d / "r.txt")
    run = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "measure_demo.py"), blend, "--quick",
                          "--out", out, "--text", txt], capture_output=True, text=True, timeout=900, cwd=ROOT)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-3000:]
    with open(out, encoding="utf-8") as fh:
        data = json.load(fh)
    with open(txt, encoding="utf-8") as fh:
        text = fh.read()
    return data, text


def test_writes_every_section(measured):
    data, text = measured
    assert not data.get("failed"), data.get("failed")
    for head in ("# Fresing measure", "## Make-up", "## Per frame (no drawing)", "## Actions", "## Memory",
                 "## Top 10 per-frame costs", "## Slowest actions"):
        assert head in text, head
    assert "no window" in text                               # says where it was measured


def test_make_up_counts(measured):
    data, _text = measured
    c = data["counts"]
    assert c["mesh_objects"] > c["unique_meshes"]               # B shares A's mesh (and the crane's copies)
    assert c["triangles"] > 0
    assert any(k.startswith("GN FR flex") for k in data["modifiers"])
    assert any(k.startswith("Child_Of") for k in data["constraints"])
    assert sum(data["drivers"].values()) >= 1 and c["keyed_curves"] >= 3
    assert any(n == "Sphere" and k == 2 for _t, n, k in data["duplicates"])   # A and C: identical, not shared


def test_per_frame_split(measured):
    data, _text = measured
    assert data["playing_ms"] > 0 and data["scrubbing_ms"] > 0
    assert any("depsgraph_update_post" in k or "frame_change" in k for k in data["handlers_playing_ms"])
    abl = data["ablation_ms"]
    assert any(k.startswith("modifiers GN FR flex") for k in abl)
    assert any(k.startswith("collection 'Machine'") for k in abl)
    assert "all per-frame Python handlers" in abl


def test_actions_and_memory(measured):
    data, text = measured
    assert len(data["select_ms"]) >= 1
    assert data["save"]["mb"] > 0
    assert "light look" in text and "hover" in text
    assert data["joint_live_ms"] and data["joint_live_ms"][0][1] == "Boom"   # the joint moved live
    assert data["memory"]["mesh_mb"] > 0
    assert data["memory"]["idprops_mb"] > 0                  # fr_arr: 1,000 numbers


def test_puts_everything_back(measured):
    """Every kind switched off for a moment is on again afterwards: same counts of shown modifiers, enabled
    constraints, live drivers, included collections and handlers as before."""
    data, text = measured
    assert "could not switch off" not in text
    assert data["restored"]["before"] == data["restored"]["after"]
