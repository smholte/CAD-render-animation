"""Prototype 0251: Blender side – meshes from height maps, the liquid's grid redrawn per frame from a bake, drops,
the liquid material, a plain studio, rendering frames and an MP4. Runs in Blender as a Python module (~/venv) or in
the real Blender. Not app code.
"""

from __future__ import annotations

import os
import subprocess
import time

import bpy
import numpy as np

LIQUID = (0.80, 0.86, 0.86)     # near the app's emulsion colour (core/coolant.py LIQUIDS["EMULSION"])
SUNK = 0.4e-3                   # a dry vertex sits this far under the surface (hidden in the part)
_CACHE = {}


# ---------------------------------------------------------------------------------------------------------------
# meshes
# ---------------------------------------------------------------------------------------------------------------

def grid_faces(ny, nx, valid=None):
    j, i = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    a = j * nx + i
    q = np.stack([a, a + 1, a + nx + 1, a + nx], -1).reshape(-1, 4)
    if valid is not None:
        v = valid.reshape(-1)
        q = q[v[q].all(1)]
    return q


def mesh(name, verts, quads=None, tris=None):
    me = bpy.data.meshes.new(name)
    verts = np.asarray(verts, np.float32).reshape(-1, 3)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    polys = []
    if quads is not None and len(quads):
        polys.append(np.asarray(quads, np.int32))
    if tris is not None and len(tris):
        polys.append(np.asarray(tris, np.int32))
    if polys:
        sizes = np.concatenate([np.full(len(p), p.shape[1], np.int32) for p in polys])
        loops = np.concatenate([p.ravel() for p in polys]).astype(np.int32)
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(sizes))
        me.polygons.foreach_set("loop_start", starts)
    me.update()
    me.validate()
    return me


def obj(name, me, mat=None, parent=None):
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def solid_from_bed(name, bed, cell, x0, y0, bottom, mat=None, parent=None, smooth=False):
    """A closed solid: the height map's top (vertices at the cell centres), a skirt round its border down to
    ``bottom`` and a bottom face. NaN cells are left out of the top (no skirt round them)."""
    ny, nx = bed.shape
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell)
    B = np.nan_to_num(bed, nan=bottom)
    top = np.stack([X, Y, B], -1).reshape(-1, 3)
    quads = grid_faces(ny, nx, ~np.isnan(bed))
    # border ring, anticlockwise seen from above
    ring = ([(0, i) for i in range(nx)] + [(j, nx - 1) for j in range(1, ny)] +
            [(ny - 1, i) for i in range(nx - 2, -1, -1)] + [(j, 0) for j in range(ny - 2, 0, -1)])
    ri = np.array([j * nx + i for j, i in ring])
    low = top[ri].copy()
    low[:, 2] = bottom
    base = len(top)
    verts = np.vstack([top, low])
    n = len(ri)
    k = np.arange(n)
    side = np.stack([ri[(k + 1) % n], ri[k], base + k, base + (k + 1) % n], -1)
    me = mesh(name, verts, np.vstack([quads, side]))
    bot = me.polygons  # bottom as an n-gon
    me2 = bpy.data.meshes.new(name)
    # add the bottom n-gon with bmesh (simplest)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    try:
        bm.faces.new([bm.verts[base + i] for i in range(n)])
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me2)
    bm.free()
    bpy.data.meshes.remove(me)
    me2.name = name
    for p in me2.polygons:
        p.use_smooth = smooth
    return obj(name, me2, mat, parent)


def liquid_grid(name, bed, cell, x0, y0, mat, parent=None):
    """The liquid's surface: one vertex per cell (fixed topology); its z is set per frame from the bake."""
    ny, nx = bed.shape
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell)
    B = np.nan_to_num(bed, nan=np.nanmin(bed) - 0.01)
    verts = np.stack([X, Y, B - SUNK], -1).reshape(-1, 3)
    me = mesh(name, verts, grid_faces(ny, nx, ~np.isnan(bed)))
    me.attributes.new("fr_depth", "FLOAT", "POINT")
    for p in me.polygons:
        p.use_smooth = True
    ob = obj(name, me, mat, parent)
    ob["fr_bed"] = B.ravel().tolist() if B.size < 2000 else None
    _CACHE[name] = dict(bed=B.ravel().astype(np.float32), xy=verts[:, :2].astype(np.float32), shape=bed.shape)
    return ob


def set_liquid(ob, depth, show=0.06e-3, bed=None):
    """Put the liquid's depth (ny, nx) onto its grid: wet vertices at bed + depth, dry ones under the surface;
    a dry vertex next to a wet one is pulled up to the wet level (the liquid meets the wall instead of diving)."""
    c = _CACHE[ob.name]
    d = np.asarray(depth, np.float32).reshape(c["shape"])
    if bed is None:
        bed = c["bed"].reshape(c["shape"])
    else:
        bed = np.nan_to_num(np.asarray(bed, np.float32), nan=float(np.min(c["bed"])))
    wet = d > show
    lvl = np.where(wet, bed + d, -np.inf)
    # the highest wet neighbour's level (4-neighbours)
    nb = np.full_like(lvl, -np.inf)
    nb[1:, :] = np.maximum(nb[1:, :], lvl[:-1, :])
    nb[:-1, :] = np.maximum(nb[:-1, :], lvl[1:, :])
    nb[:, 1:] = np.maximum(nb[:, 1:], lvl[:, :-1])
    nb[:, :-1] = np.maximum(nb[:, :-1], lvl[:, 1:])
    z = np.where(wet, bed + d, bed - SUNK)
    edge = ~wet & np.isfinite(nb) & (nb < bed)      # a dry cell higher than its wet neighbour: a wall
    z = np.where(edge, np.maximum(nb, bed - 2.5e-3), z)
    co = np.concatenate([c["xy"], z.reshape(-1, 1).astype(np.float32)], 1)
    me = ob.data
    me.vertices.foreach_set("co", co.ravel())
    me.attributes["fr_depth"].data.foreach_set("value", np.where(wet, d, 0.0).ravel().astype(np.float32))
    me.update()


def drops_object(name, mat, size=1.0):
    """Points (one vertex per drop) drawn as small spheres by Geometry Nodes, radius from the attribute fr_r."""
    me = mesh(name, np.zeros((0, 3)))
    me.attributes.new("fr_r", "FLOAT", "POINT")
    ob = obj(name, me, None)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = ng.nodes
    gi, go = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    m2p = n.new("GeometryNodeMeshToPoints")
    ico = n.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 2
    inst = n.new("GeometryNodeInstanceOnPoints")
    att = n.new("GeometryNodeInputNamedAttribute")
    att.data_type = "FLOAT"
    att.inputs["Name"].default_value = "fr_r"
    real = n.new("GeometryNodeRealizeInstances")
    sm = n.new("GeometryNodeSetMaterial")
    sm.inputs["Material"].default_value = mat
    sh = n.new("GeometryNodeSetShadeSmooth")
    L_ = ng.links
    L_.new(gi.outputs[0], m2p.inputs["Mesh"])
    L_.new(m2p.outputs[0], inst.inputs["Points"])
    L_.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    L_.new(att.outputs["Attribute"], inst.inputs["Scale"])
    L_.new(inst.outputs[0], real.inputs[0])
    L_.new(real.outputs[0], sh.inputs[0])
    L_.new(sh.outputs[0], sm.inputs[0])
    L_.new(sm.outputs[0], go.inputs[0])
    mod = ob.modifiers.new("Drops", "NODES")
    mod.node_group = ng
    return ob


def set_drops(ob, P, r):
    me = ob.data
    me.clear_geometry()
    if len(P):
        me.vertices.add(len(P))
        me.vertices.foreach_set("co", np.asarray(P, np.float32).ravel())
        if "fr_r" not in me.attributes:
            me.attributes.new("fr_r", "FLOAT", "POINT")
        me.attributes["fr_r"].data.foreach_set("value", np.asarray(r, np.float32))
    me.update()


def drop_radii(vols, cap=1.6e-3, floor=0.35e-3):
    r = np.cbrt(np.maximum(vols, 0) * 3 / (4 * np.pi))
    return np.clip(r * 1.4, floor, cap)


def split_drops(P, vols, cap=1.6e-3, step=None, seed_axis=2):
    """A big volume is drawn as a short stream of drops (deterministic: spaced along -z)."""
    vcap = 4 / 3 * np.pi * (cap / 1.4) ** 3
    out_p, out_r = [], []
    for p, v in zip(P, vols):
        k = int(min(12, max(1, np.ceil(v / vcap))))
        r = drop_radii(np.array([v / k]))[0]
        for i in range(k):
            q = np.array(p, float)
            q[seed_axis] += i * 1.6 * r
            out_p.append(q)
            out_r.append(r)
    return np.array(out_p).reshape(-1, 3), np.array(out_r)


# ---------------------------------------------------------------------------------------------------------------
# materials, studio
# ---------------------------------------------------------------------------------------------------------------

def liquid_material(name="Liquid", colour=LIQUID, thin=0.5e-3):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    n = nt.nodes
    p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*colour, 1)
    p.inputs["Roughness"].default_value = 0.03
    p.inputs["IOR"].default_value = 1.34
    p.inputs["Transmission Weight"].default_value = 0.85
    p.inputs["Subsurface Weight"].default_value = 0.0
    p.inputs["Coat Weight"].default_value = 0.0
    att = n.new("ShaderNodeAttribute")
    att.attribute_type = "GEOMETRY"
    att.attribute_name = "fr_depth"
    mr = n.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = thin
    mr.inputs["To Min"].default_value = 0.15
    mr.inputs["To Max"].default_value = 1.0
    tr = n.new("ShaderNodeBsdfTransparent")
    mix = n.new("ShaderNodeMixShader")
    out = n["Material Output"]
    nt.links.new(att.outputs["Fac"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(p.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    m.surface_render_method = "BLENDED" if hasattr(m, "surface_render_method") else None
    return m


def drop_material(name="Drops", colour=LIQUID):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*colour, 1)
    p.inputs["Roughness"].default_value = 0.05
    p.inputs["IOR"].default_value = 1.34
    p.inputs["Transmission Weight"].default_value = 0.55
    return m


def metal(name, colour, rough=0.35, metallic=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*colour, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metallic
    return m


def studio(target, dist=0.55, elev=32, azim=-55, lens=50, res=(640, 360)):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.055, 1)
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[1].color = (0.30, 0.32, 0.36, 1)
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bg.inputs[0])
    bg.inputs[1].default_value = 0.6
    import math
    from mathutils import Vector
    t = Vector(target)
    a, e = math.radians(azim), math.radians(elev)
    pos = t + dist * Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    sc.collection.objects.link(cam)
    cam.data.lens = lens
    cam.data.clip_start = 0.005
    cam.location = pos
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (t - pos).to_track_quat("-Z", "Y")
    sc.camera = cam
    for nm, loc, power, size in (("Key", (0.4, -0.5, 0.9), 70, 0.5), ("Fill", (-0.6, 0.3, 0.6), 20, 0.8)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy = power
        ld.size = size
        lo = bpy.data.objects.new(nm, ld)
        sc.collection.objects.link(lo)
        lo.location = (t[0] + loc[0], t[1] + loc[1], t[2] + loc[2])
        lo.rotation_mode = "QUATERNION"
        lo.rotation_quaternion = (t - lo.location).to_track_quat("-Z", "Y")
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    return cam


def engine(name="CYCLES", samples=32):
    sc = bpy.context.scene
    if name == "CYCLES":
        sc.render.engine = "CYCLES"
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.device = "CPU"
        sc.cycles.max_bounces = 8
        sc.cycles.transmission_bounces = 8
        sc.cycles.transparent_max_bounces = 16
        sc.cycles.use_adaptive_sampling = True
    elif name == "EEVEE":
        sc.render.engine = "BLENDER_EEVEE"
        e = sc.eevee
        e.taa_render_samples = samples
        if hasattr(e, "use_raytracing"):
            e.use_raytracing = True
    else:
        sc.render.engine = "BLENDER_WORKBENCH"
        sh = sc.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_specular_highlight = True
    sc.view_settings.view_transform = "AgX" if name != "WORKBENCH" else "Standard"


def render_frames(frames, folder, update, prefix="f"):
    """Render the given frames to PNGs, ``update(frame)`` puts the liquid in place first. Returns s per frame."""
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    times = []
    for k, f in enumerate(frames):
        sc.frame_set(f)
        update(f)
        sc.render.filepath = os.path.join(folder, f"{prefix}{k:04d}.png")
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        times.append(time.perf_counter() - t0)
    return times


def mp4(folder, out, fps=24, prefix="f", crf=28):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i",
                    os.path.join(folder, prefix + "%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf",
                    str(crf), "-preset", "slow", "-movflags", "+faststart", out], check=True)
    return os.path.getsize(out)


def still_jpg(png, out, quality=82):
    subprocess.run(["convert", png, "-quality", str(quality), out], check=True)
