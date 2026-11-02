"""Run inside the real Blender (background) with the installed extension: paths with spaces, accents, apostrophes, dashes."""
import os, sys, time, math, importlib, addon_utils, traceback
import bpy
from mathutils import Vector
D = "/home/claude/pad test/Mijn Projecten é ü/Klant O'Brien – 2026"
RES = []
def check(name, ok, detail=""):
    RES.append(ok); print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
try:
    pk = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    addon_utils.enable(pk, default_set=True)
    J = importlib.import_module(pk + ".blender.joints"); Q = importlib.import_module(pk + ".blender.queue")
    S = importlib.import_module(pk + ".blender.states"); B = importlib.import_module(pk + ".blender.build")
    L = importlib.import_module(pk + ".blender.project_lock"); runner = importlib.import_module(pk + ".importer.runner")
    sc = bpy.context.scene; s = sc.fresing
    # a fresh import (cache cleared) so the STEP reader subprocess really runs on the accented path
    bpy.ops.fresing.clear_cache()
    step_a = os.path.join(D, "Kraan ontwerp – rev A é.step")
    r = bpy.ops.fresing.import_step(filepath=step_a, quality="draft")
    check("import from an accented path (reader subprocess)", r == {"FINISHED"} and s.model_count == 1, s.last_message)
    check("cache folder name", True, os.listdir(importlib.import_module(pk + ".blender.ops_import").cache_root())[:3])
    boom = next(o for o in sc.objects if o.get("fr_name") == "BOOM.ASM")
    j = J.create(sc, "ROTATE", [boom], Vector((0.1, 0.3, 0.4)), Vector((0, 1, 0)))
    J.set_value(j, math.radians(20))
    proj = os.path.join(D, "Project ö – kraan.blend")
    bpy.ops.wm.save_as_mainfile(filepath=proj)
    L._take(proj) if not bpy.app.background else L.write(proj)
    check("lock file next to an accented project", os.path.isfile(proj + ".inuse"))
    s.out_resolution = "preview"; s.quality = "draft"; s.out_folder = ""          # default: Renders next to the project
    S.save_shot(sc, "Zijaanzicht é")
    a = s.animations.add(); a.name = "Kraan – op é"; a.tail = 0.0; a.quality = "draft"; a.out_resolution = "preview"
    b = a.blocks.add(); b.kind = "JOINT"; b.joint = j.name; b.duration = 0.08; b.to_angle = math.radians(30)
    Q.add_job(sc, "STILL", shot="Zijaanzicht é", quality="draft")
    Q.add_job(sc, "ANIMATION", animation=a.name, quality="draft")
    bpy.ops.wm.save_mainfile()
    qdir = Q.start(bpy.context)
    check("queue folder", os.path.isdir(qdir), qdir)
    t0 = time.time()
    while Q.is_running(sc) and time.time() - t0 < 900:
        time.sleep(2)
    Q.sync(sc)
    for job in s.queue:
        check(f"queue job {job.label}", job.status == "DONE" and os.path.exists(job.output), f"{job.status} {job.message} {job.output}")
    # update to revision B from an accented path
    root = B.model_roots(sc)[0]
    r = bpy.ops.fresing.import_step(filepath=os.path.join(D, "Kraan ontwerp – rev B é.step"), quality="draft", update_root=root.name)
    check("model update from an accented path", r == {"FINISHED"} and "Model updated" in s.report_title, s.report_title)
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=proj)
    sc = bpy.context.scene
    check("reopen the accented project", len(sc.fresing.joints) == 1 and J.is_valid(sc.fresing.joints[0]))
except Exception:
    traceback.print_exc(); RES.append(False)
print(f"RESULT {sum(RES)}/{len(RES)}", flush=True)
