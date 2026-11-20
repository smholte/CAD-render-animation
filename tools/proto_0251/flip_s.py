"""Prototype 0251, method c: Blender's own liquid simulation (Mantaflow FLIP) on scene S.

    ~/venv/bin/python tools/proto_0251/flip_s.py <cache dir> <resolution> [frames]   # bake, print times
    ~/venv/bin/python tools/proto_0251/render_s.py flip <cache dir> <out dir> ...    # render the baked liquid

The domain is a box round the plate's whole travel and the tray; the plate and block are collision effectors moved by
keys (Mantaflow reads the motion from them), the tray a still effector, the jet a liquid inflow switched by a key on
``use_inflow``, the drain an outflow.
"""

from __future__ import annotations

import json
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scene_s as S  # noqa: E402

MM = 1e-3
RES = int(os.environ.get("FLIP_RES", "128"))


def _key_carrier(carrier):
    mats = S.plate_mats()
    from mathutils import Matrix
    for f in range(S.FRAMES):
        carrier.matrix_world = Matrix(mats[f].tolist())
        carrier.keyframe_insert("location", frame=f)
    for fc in carrier.animation_data.action.fcurves if hasattr(carrier.animation_data.action, "fcurves") else []:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"


def setup_render(cache, sc, carrier, place, res=None, frames=None, bake=None):
    res = res or RES
    _key_carrier(carrier)
    sc.frame_start, sc.frame_end = 0, (frames or S.FRAMES) - 1
    for nm in ("Plate", "Block", "Tray floor", "Wall -x", "Wall +x", "Wall -y", "Wall +y"):
        ob = bpy.data.objects[nm]
        dec = ob.modifiers.new("Coarse", "DECIMATE")       # the height-map meshes are dense; Mantaflow voxelises
        dec.decimate_type = "DISSOLVE"                     # every effector each step: flat faces merged first
        dec.angle_limit = 0.02
        m = ob.modifiers.new("Fluid", "FLUID")
        m.fluid_type = "EFFECTOR"
        m.effector_settings.effector_type = "COLLISION"
        m.effector_settings.use_effector = True
        m.effector_settings.subframes = 1 if nm in ("Plate", "Block") else 0
    # domain
    x0, x1, y0, y1, _, wall = S.TRAY
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, 0.105))
    dom = bpy.context.object
    dom.name = "Liquid domain"
    dom.scale = (x1 - x0 + 0.02, y1 - y0 + 0.02, 0.23)
    bpy.ops.object.transform_apply(scale=True)
    m = dom.modifiers.new("Fluid", "FLUID")
    m.fluid_type = "DOMAIN"
    d = m.domain_settings
    d.domain_type = "LIQUID"
    d.resolution_max = res
    d.use_mesh = True
    d.cache_type = "ALL"
    d.cache_directory = cache
    d.cache_frame_start = 0
    d.cache_frame_end = (frames or S.FRAMES) - 1
    d.use_collision_border_top = False
    d.use_flip_particles = True
    d.mesh_scale = 1
    import bl
    dom.data.materials.append(bl.liquid_material("Liquid flip"))
    dom.data.materials[0].node_tree.nodes["Mix Shader"].inputs["Fac"].default_value = 1.0
    # take the depth fade out (the FLIP mesh has no depth attribute)
    mt = dom.data.materials[0].node_tree
    for l in list(mt.links):
        if l.to_node.name == "Mix Shader" and l.to_socket.name == "Fac":
            mt.links.remove(l)
    # jet: an inflow cylinder at the nozzle, switched by keys
    p = S.JET[0]
    bpy.ops.mesh.primitive_cylinder_add(radius=max(5 * MM, 1.2 * (x1 - x0) / res), depth=0.01,
                                        location=(p[0], p[1], p[2] - 0.01))
    jet = bpy.context.object
    jet.name = "Jet inflow"
    jm = jet.modifiers.new("Fluid", "FLUID")
    jm.fluid_type = "FLOW"
    fs = jm.flow_settings
    fs.flow_type = "LIQUID"
    fs.flow_behavior = "INFLOW"
    fs.flow_source = "MESH"
    fs.use_initial_velocity = True
    fs.velocity_coord = (0.0, 0.0, -1.0)
    a, b = S.JET[2], S.JET[3]
    for f, on in ((0, False), (int(a * S.FPS), True), (int(b * S.FPS), False)):
        fs.use_inflow = on
        fs.keyframe_insert("use_inflow", frame=f)
    jet.hide_render = True
    # drain: an outflow in the hole
    dx, dy, r = S.DRAIN
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=0.02, location=(dx, dy, 0.0))
    dr = bpy.context.object
    dr.name = "Drain outflow"
    dm = dr.modifiers.new("Fluid", "FLUID")
    dm.fluid_type = "FLOW"
    dm.flow_settings.flow_type = "LIQUID"
    dm.flow_settings.flow_behavior = "OUTFLOW"
    dr.hide_render = True
    if bake is not None:
        t0 = time.perf_counter()
        with bpy.context.temp_override(object=dom, active_object=dom, scene=sc):
            bpy.ops.fluid.bake_all()
        bake["seconds"] = time.perf_counter() - t0
        bake["cache_bytes"] = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs_ in os.walk(cache)
                                  for f in fs_)
        bake["res"] = res
        bake["cells"] = list(d.domain_resolution)

    def update(f):
        place(f)
    return update


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    cache, res = argv[0], int(argv[1])
    frames = int(argv[2]) if len(argv) > 2 else S.FRAMES
    import render_s
    sc, carrier, place = render_s.build_static()
    info = {}
    setup_render(cache, sc, carrier, place, res=res, frames=frames, bake=info)
    info["frames"] = frames
    info["s_per_frame"] = info["seconds"] / frames
    print(json.dumps(info))
    json.dump(info, open(os.path.join(cache, "bake.json"), "w"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(cache, "flip_s.blend"))


if __name__ == "__main__":
    main()
