import sys, bpy
sys.argv = ['render_s.py', 'hf', '/tmp/p251/s_hf.npz', '/tmp/p251/eevee_try2', '80,110', 'EEVEE']
sys.path.insert(0, 'tools/proto_0251')
import render_s, bl
orig = bl.engine
def engine(name="CYCLES", samples=32):
    orig(name, samples)
    e = bpy.context.scene.eevee
    e.use_raytracing = True
    bpy.context.scene.camera.data.clip_start = 0.08
    for m in bpy.data.materials:
        if m.name.startswith("Liquid") or m.name.startswith("Drops"):
            m.surface_render_method = "BLENDED"
            p = m.node_tree.nodes.get("Principled BSDF")
            if p: p.inputs["Transmission Weight"].default_value = 0.0; p.inputs["Alpha"].default_value = 0.3
            m.use_transparency_overlap = False if hasattr(m, "use_transparency_overlap") else None
bl.engine = engine
render_s.main()
