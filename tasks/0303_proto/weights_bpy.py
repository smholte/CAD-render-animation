"""Study 0303: Blender's automatic weights (bone heat) for a base mesh on the rig's 17 bones fitted to its A-pose.
Run: blender -b --factory-startup --python weights_bpy.py -- <body> <in .npz> <out .npz>"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import realistic as RL  # noqa: E402

body, src, dst = sys.argv[sys.argv.index("--") + 1:]
d = np.load(src)
co = d["co"].astype(float)
co[:, 0] -= co[:, 0].mean()
polys = RL.polys_of(d)
me = bpy.data.meshes.new("body")
me.from_pydata(co.tolist(), [], polys)
ob = bpy.data.objects.new("body", me)
bpy.context.scene.collection.objects.link(ob)
arm_d = bpy.data.armatures.new("rig")
arm = bpy.data.objects.new("rig", arm_d)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
fb = RL.fitted_bones(body)
for b in RL.R.BONES:
    e = arm_d.edit_bones.new(b)
    e.head, e.tail = tuple(fb[b][0]), tuple(fb[b][1])
for b in RL.R.BONES:
    par = RL.R.PARENT[b]
    if par:
        arm_d.edit_bones[b].parent = arm_d.edit_bones[par]
bpy.ops.object.mode_set(mode="OBJECT")
for o in bpy.context.view_layer.objects:
    o.select_set(False)
ob.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
W = np.zeros((len(co), len(RL.R.BONES)))
names = {g.index: g.name for g in ob.vertex_groups}
for v in me.vertices:
    for g in v.groups:
        W[v.index, RL.R.BONES.index(names[g.group])] = g.weight
s = W.sum(axis=1)
print("points without weight:", int((s < 1e-6).sum()), "of", len(co))
W[s < 1e-6, 0] = 1.0
W /= W.sum(axis=1, keepdims=True)
np.savez_compressed(dst, W=W, co=co)
