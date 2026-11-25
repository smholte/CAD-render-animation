"""Task 0344 proof (study files only): append vs link of pack items into a project, in Blender 5.2.3.

Not part of the app. Each step runs in its own background Blender (``run_proof.py`` starts them in order):

    blender -b --factory-startup --python try_pack.py -- bring  <pack root> <project.blend> <method> <out.json>
    blender -b --factory-startup --python try_pack.py -- open   <project.blend> <out.json> [render]
    blender -b --factory-startup --python try_pack.py -- update <project.blend> <new pack root> <out.json>
    blender -b --factory-startup --python try_pack.py -- memory <pack root> <1k|2k|4k> <ext|tx|packed> <out.json>

Methods:
    append_ext     append; the pictures stay files in the pack folder (the project points at them)
    append_packed  append, then pack every picture into the project (the app's recommended way)
    link           link to the pack's .blend files
    link_packed    link + pack the linked data into the project (Blender 5.x "packed linked data")

The project stands in for a Fresing project: five parts whose group material "FR group A" is the app's own material
with the pack's node group as its look (Material Output <- group node "FRP paint_satin"; the app's wrappers – fade,
section, wet – sit between the two, as on today's looks), a floor with the pack's concrete material, the pack's world,
its workshop collection and a pallet. Every pack datablock carries ``fr_asset`` (id, pack, version, contract).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
STEP = argv[0]


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 1)


def _write(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print("FR0344", STEP, json.dumps(data))


def _pack_json(root: str) -> dict:
    with open(os.path.join(root, "pack.json"), encoding="utf-8") as f:
        return json.load(f)


def _asset(idb) -> dict:
    try:
        return json.loads(idb.get("fr_asset", "") or "{}")
    except ValueError:
        return {}


def _find_local(asset_id: str, version: str, coll: str):
    """The app's own dedupe: a datablock of this id and version already in the project (never '.001' copies)."""
    for idb in getattr(bpy.data, coll):
        a = _asset(idb)
        if a.get("id") == asset_id and a.get("version") == version and idb.library is None:
            return idb
    return None


def bring_item(root: str, row: dict, method: str):
    coll, name = row["datablock"]
    a_ver = _pack_json(root)["version"]
    if method.startswith("append"):
        have = _find_local(row["id"], a_ver, coll)
        if have is not None:
            return have
    path = os.path.join(root, row["file"])
    link = method.startswith("link")
    with bpy.data.libraries.load(path, link=link, pack=(method == "link_packed"), relative=False) as (src, dst):
        setattr(dst, coll, [name])
    return getattr(dst, coll)[0]


def _dedupe_materials():
    """Pack .blend files stand alone, so an environment brings its own copy of a material the project may have:
    keep one per (id, version)."""
    seen = {}
    for m in list(bpy.data.materials):
        a = _asset(m)
        if not a or m.library is not None:
            continue
        key = (a.get("id"), a.get("version"))
        if key in seen:
            m.user_remap(seen[key])
            bpy.data.materials.remove(m)
        else:
            seen[key] = m


def _group_material(ng):
    """Like the app's 'FR <group>' material, with the pack's node group as the look."""
    mat = bpy.data.materials.new("FR group A")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = ng
    node.name = "FR look"
    node.inputs["Colour"].default_value = (0.9, 0.55, 0.05, 1.0)        # the group's own colour: stays the project's
    node.inputs["Wear"].default_value = 0.2
    nt.links.new(node.outputs["Shader"], out.inputs["Surface"])
    mat["fr_material"] = "paint_satin"
    mat["fr_look_src"] = "pack"                                         # the app's switch, per material
    return mat


def _box(name, size, loc, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    ob.data.materials.append(mat)
    return ob


def step_bring():
    root, project, method, out = argv[1], argv[2], argv[3], argv[4]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    rows = {r["id"]: r for r in _pack_json(root)["assets"]}
    t0 = time.perf_counter()
    ng = bring_item(root, rows["material:paint_satin"], method)
    mat = _group_material(ng)
    for i in range(5):
        _box(f"part {i + 1}", (0.4, 0.4, 0.4), (i * 0.6 - 1.2, 0, 0.2), mat)
    concrete = bring_item(root, rows["material:concrete_floor"], method)
    _box("floor", (6, 6, 0.02), (0, 0, -0.01), concrete)
    sc.world = bring_item(root, rows["world:studio_soft"], method)
    col = bring_item(root, rows["environment:workshop_small"], method)
    sc.collection.children.link(col)
    pallet = bring_item(root, rows["prop:euro_pallet"], method)
    sc.collection.objects.link(pallet)
    if method.startswith("append"):
        _dedupe_materials()
    bring_ms = _ms(t0)
    t0 = time.perf_counter()
    packed = 0
    if method == "append_packed":
        for img in bpy.data.images:
            if img.source == "FILE" and img.packed_file is None:
                img.pack()
                packed += 1
    pack_ms = _ms(t0)
    from mathutils import Vector
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.location = Vector((0.6, -3.6, 1.5))
    cam.rotation_euler = (Vector((0.0, 0.3, 0.2)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam
    t0 = time.perf_counter()
    bpy.ops.wm.save_as_mainfile(filepath=project, check_existing=False)
    save_ms = _ms(t0)
    _write(out, {"method": method, "bring_ms": bring_ms, "pack_images_ms": pack_ms, "images_packed": packed,
                 "save_ms": save_ms, "bytes": os.path.getsize(project),
                 "libraries": [lib.filepath for lib in bpy.data.libraries],
                 "materials": sorted(m.name for m in bpy.data.materials),
                 "node_groups": sorted(g.name for g in bpy.data.node_groups),
                 "images": sorted(i.name for i in bpy.data.images)})


def _render_check(tag: str) -> dict:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 320, 180, 100
    path = os.path.join(os.path.dirname(bpy.data.filepath), f"render_{tag}.png")
    sc.render.filepath = path
    t0 = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    ms = _ms(t0)
    img = bpy.data.images.load(path)
    px = list(img.pixels)
    n = len(px) // 4
    magenta = sum(1 for i in range(n) if px[4 * i] > 0.9 and px[4 * i + 1] < 0.1 and px[4 * i + 2] > 0.9)
    mean = [round(sum(px[c::4]) / n, 3) for c in range(3)]
    return {"render_ms": ms, "magenta_share": round(magenta / n, 3), "mean_rgb": mean, "picture": path}


def step_open():
    project, out = argv[1], argv[2]
    render = len(argv) > 3 and argv[3] == "render"
    t0 = time.perf_counter()
    bpy.ops.wm.open_mainfile(filepath=project, load_ui=False)
    open_ms = _ms(t0)
    libs = [{"path": lib.filepath, "missing": bool(lib.is_missing), "packed": lib.packed_file is not None}
            for lib in bpy.data.libraries]
    imgs = []
    for img in bpy.data.images:
        if img.source != "FILE":
            continue
        packed = img.packed_file is not None
        path = bpy.path.abspath(img.filepath, library=img.library)
        ok = packed or os.path.exists(path)
        imgs.append({"name": img.name, "packed": packed, "linked_packed": bool(img.is_linked_packed),
                     "found": ok, "path": img.filepath})
    placeholders = sum(1 for c in ("materials", "node_groups", "worlds", "collections", "objects")
                       for i in getattr(bpy.data, c) if getattr(i, "is_missing", False))
    mat = bpy.data.materials.get("FR group A")
    look = None
    if mat is not None:
        n = mat.node_tree.nodes.get("FR look")
        look = {"group": n.node_tree.name if n and n.node_tree else None,
                "group_has_nodes": bool(n and n.node_tree and len(n.node_tree.nodes)),
                "colour_kept": [round(v, 3) for v in n.inputs["Colour"].default_value] if n else None,
                "asset": _asset(n.node_tree) if n and n.node_tree else {}}
    res = {"project": project, "open_ms": open_ms, "libraries": libs, "images": imgs,
           "missing_images": sum(1 for i in imgs if not i["found"]),
           "missing_libraries": sum(1 for lib in libs if lib["missing"]),
           "placeholders": placeholders, "look": look}
    if render:
        res.update(_render_check(os.path.splitext(os.path.basename(out))[0]))
    _write(out, res)


def step_update():
    """'Use the new Fresing looks': every pack datablock whose source changed is replaced by the new pack's one;
    the project's own settings on top (the group node's colour, wear) stay where they are."""
    project, new_root, out = argv[1], argv[2], argv[3]
    bpy.ops.wm.open_mainfile(filepath=project, load_ui=False)
    pack = _pack_json(new_root)
    rows = {r["id"]: r for r in pack["assets"]}
    t0 = time.perf_counter()
    done, how = [], ""
    libs = list(bpy.data.libraries)
    was_packed = any(getattr(i, "is_linked_packed", False) for c in ("node_groups", "materials", "worlds", "images")
                     for i in getattr(bpy.data, c))
    if libs:                                        # linked (packed or not): point the library at the new file
        for lib in libs:
            rel = None
            for r in rows.values():
                if os.path.basename(r["file"]) == os.path.basename(lib.filepath):
                    rel = r["file"]
            if rel is None:
                continue
            how = "link_packed: relocate + reload, then pack_libraries again" if was_packed else "link: relocate + reload"
            lib.filepath = os.path.join(new_root, rel)
            try:
                lib.reload()
                done.append(rel)
            except Exception as e:                  # noqa: BLE001 - report it
                done.append(f"{rel}: {e}")
        if was_packed:
            try:
                bpy.ops.file.pack_libraries()
                done.append("pack_libraries: ok")
            except Exception as e:                  # noqa: BLE001 - report it
                done.append(f"pack_libraries: {e}")
    else:
        how = "append: append the new one, user_remap the old one onto it, remove the old one, pack its pictures"
        for coll in ("node_groups", "materials", "worlds", "collections", "objects"):
            for idb in list(getattr(bpy.data, coll)):
                a = _asset(idb)
                row = rows.get(a.get("id"))
                if not a or row is None or a.get("version") == pack["version"] or idb.library is not None:
                    continue
                path = os.path.join(new_root, row["file"])
                with bpy.data.libraries.load(path, link=False) as (src, dst):
                    setattr(dst, coll, [row["datablock"][1]])
                new = getattr(dst, coll)[0]
                if coll == "collections":           # a collection: swap it in the scene's children
                    for sc in bpy.data.scenes:
                        if idb.name in sc.collection.children:
                            sc.collection.children.unlink(idb)
                            sc.collection.children.link(new)
                    for ob in list(idb.all_objects):
                        if ob.users <= 1:
                            bpy.data.objects.remove(ob)
                else:
                    idb.user_remap(new)
                old_name = idb.name
                getattr(bpy.data, coll).remove(idb)
                new.name = old_name
                done.append(f"{coll}:{a['id']} {a['version']} -> {pack['version']}")
        _dedupe_materials()
        for img in bpy.data.images:
            if img.source == "FILE" and img.packed_file is None and img.users:
                img.pack()
        for img in list(bpy.data.images):          # pictures of the old version nobody uses any more
            if img.users == 0:
                bpy.data.images.remove(img)
    update_ms = _ms(t0)
    newp = project.replace(".blend", "_updated.blend")
    bpy.ops.wm.save_as_mainfile(filepath=newp, check_existing=False)
    mat = bpy.data.materials.get("FR group A")
    n = mat.node_tree.nodes.get("FR look") if mat else None
    rough = None
    if n is not None and n.node_tree is not None:
        b = next((x for x in n.node_tree.nodes if x.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        rough = round(b.inputs["Roughness"].default_value, 3) if b else None
    _write(out, {"how": how, "done": done, "update_ms": update_ms, "saved": newp, "bytes": os.path.getsize(newp),
                 "look_roughness_after": rough,
                 "colour_kept": [round(v, 3) for v in n.inputs["Colour"].default_value] if n else None,
                 "node_groups": sorted(g.name for g in bpy.data.node_groups),
                 "materials": sorted(m.name for m in bpy.data.materials),
                 "images": sorted(i.name for i in bpy.data.images)})


def step_memory():
    """Cycles CPU: memory and time of a close-up of the concrete floor at 1k / 2k / 4k pictures.
    ext = picture files, Blender's texture cache on (its default) but no .tx files; tx = the same with .tx files made
    first (``render.generate_texture_cache``); packed = the pictures packed into the project."""
    root, k, mode, out = argv[1], argv[2], argv[3], argv[4]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    tmpdir = os.path.join(os.path.dirname(out), f"mem_{k}_{mode}")
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.makedirs(tmpdir)
    src = os.path.join(root, "textures", k)
    texdir = os.path.join(tmpdir, "textures")
    shutil.copytree(src, texdir)                    # its own copy: .tx files land next to it
    mat = bpy.data.materials.new("concrete")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    for key, cs in (("color", "sRGB"), ("rough", "Non-Color"), ("normal", "Non-Color")):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(texdir, f"concrete_{key}." + ("jpg" if key == "color" else "png")))
        node.image.colorspace_settings.name = cs
        nt.links.new(tc.outputs["UV"], node.inputs["Vector"])
        sock = {"color": "Base Color", "rough": "Roughness"}.get(key)
        if sock:
            nt.links.new(node.outputs["Color"], bsdf.inputs[sock])
        else:
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nt.links.new(node.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        if mode in ("packed", "packed_tx"):
            node.image.pack()
    bpy.ops.mesh.primitive_plane_add(size=2.0)
    bpy.context.active_object.data.materials.append(mat)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.location = (0, 0, 2.2)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sc.collection.objects.link(sun)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 960, 540, 100
    proj = os.path.join(tmpdir, "mem.blend")
    bpy.ops.wm.save_as_mainfile(filepath=proj, check_existing=False)
    tx_ms, tx_bytes = None, 0
    if mode in ("tx", "packed_tx"):
        t0 = time.perf_counter()
        bpy.ops.render.generate_texture_cache()
        tx_ms = _ms(t0)
        tx_bytes = sum(os.path.getsize(os.path.join(d, n)) for d, _, ns in os.walk(tmpdir) for n in ns
                       if n.endswith(".tx"))
    stats = []

    def _stats(text, *_):
        stats.append(str(text))
    bpy.app.handlers.render_stats.append(_stats)
    t0 = time.perf_counter()
    bpy.ops.render.render(write_still=False)
    ms = _ms(t0)
    bpy.app.handlers.render_stats.remove(_stats)
    import re
    mem = [float(x) for line in stats for x in re.findall(r"Mem: ?([\d.]+)M", line)]
    _write(out, {"k": k, "mode": mode, "render_ms": ms, "cycles_mem_mb": max(mem) if mem else None, "use_texture_cache": sc.render.use_texture_cache,
                 "tx_ms": tx_ms, "tx_bytes": tx_bytes,
                 "tx_files": sorted(os.path.relpath(os.path.join(d, n), tmpdir) for d, _, ns in os.walk(tmpdir)
                                    for n in ns if n.endswith(".tx")),
                 "project_bytes": os.path.getsize(proj)})


def step_reuse():
    """Does Blender's own ``reuse_local_id`` stop a second append of the same item making a '.001' copy?"""
    root, out = argv[1], argv[2]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path = os.path.join(root, "materials", "paint_satin.blend")
    res = {}
    for reuse in (False, True):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        for _ in range(2):
            with bpy.data.libraries.load(path, link=False, reuse_local_id=reuse) as (src, dst):
                dst.node_groups = ["FRP paint_satin"]
        res[f"reuse_local_id={reuse}"] = sorted(g.name for g in bpy.data.node_groups)
    _write(out, res)


{"bring": step_bring, "open": step_open, "update": step_update, "memory": step_memory, "reuse": step_reuse}[STEP]()
