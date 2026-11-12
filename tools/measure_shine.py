"""Task 0098: how wide is the highlight along and across the marks? (bpy module, Cycles CPU, small renders)

Plate (brushed, ground) long in X; shaft (turned) long in X. Prints the highlight's width at half its peak in X and
in Y (pixels). Brushed/ground: Y (across the lines) must be the longer one; turned: X (along the axis) the longer."""
import sys

import bpy
import numpy as np

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from fresing_render.blender import materials  # noqa: E402


def scene(kind, material, iso=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 128
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 160
    sc.render.film_transparent = False
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = w
    if kind == "plate":
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        ob = bpy.context.object
        ob.scale = (0.3, 0.2, 0.01)
        ob.location = (0, 0, -0.005)
    else:   # shaft lying along X, top at z=0
        bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=0.3, vertices=96)
        ob = bpy.context.object
        ob.rotation_euler = (0, np.pi / 2, 0)
        ob.location = (0, 0, -0.1)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    me = ob.data
    for p in me.polygons:
        p.use_smooth = kind != "plate"
    materials.part_axes(me)
    mat = bpy.data.materials.new("m")
    materials.build_nodes(mat, material)
    if iso:     # control: the same look without anisotropy (shows what the view alone does)
        next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").inputs["Anisotropic"].default_value = 0
    me.materials.append(mat)
    bpy.ops.object.light_add(type="POINT", location=(0.3, 0, 0.6))
    L = bpy.context.object
    L.data.energy = 12
    L.data.shadow_soft_size = 0.004
    bpy.ops.object.camera_add(location=(-0.3, 0, 0.6))
    cam = bpy.context.object
    cam.rotation_euler = (0, np.radians(45), 0) if False else (np.radians(45), 0, 0)
    # look at origin from (-0.3,0,0.6)
    d = np.array([0.3, 0, -0.6]); d /= np.linalg.norm(d)
    cam.rotation_mode = "QUATERNION"
    from mathutils import Vector
    cam.rotation_quaternion = Vector(d.tolist()).to_track_quat("-Z", "Y")
    cam.data.lens = 90
    sc.camera = cam
    return sc


def widths(path):
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)[:, :, :3].mean(2)
    cy, cx = np.unravel_index(px.argmax(), px.shape)
    peak = px[cy, cx]
    hx = (px[cy, :] > peak / 2)
    hy = (px[:, cx] > peak / 2)
    def run(m, c):
        a = b = c
        while a > 0 and m[a - 1]: a -= 1
        while b < len(m) - 1 and m[b + 1]: b += 1
        return b - a + 1
    # the image's x axis is world X as the camera looks along X; its y axis is world Y rotated into view
    return run(hy, cy), run(hx, cx), peak     # (world X = image vertical, world Y = image horizontal)


CASES = (("plate", "stainless_brushed", 0), ("plate", "steel_ground", 0), ("shaft", "steel_turned", 0),
         ("plate", "steel_ground", 1), ("shaft", "steel_turned", 1))


def main():
    """{(material, control): width along the axis / width round or across it}; prints a line per case."""
    res = {}
    for kind, material, iso in CASES:
        sc = scene(kind, material, iso)
        out = sc.render.filepath = f"/tmp/shine_{material}{'_c' if iso else ''}.png"
        bpy.ops.render.render(write_still=True)
        wx, wy, peak = widths(out)
        res[(material, iso)] = wx / wy
        print(f"{material:18s}{' (control)' if iso else '':11s} along-X {wx:3d} px, across-Y {wy:3d} px "
              f"(ratio X/Y {wx / wy:.2f}, peak {peak:.2f})")
    return res


if __name__ == "__main__":
    main()
