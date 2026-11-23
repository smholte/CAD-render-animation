"""Task 0286 proof: register the test library as a REMOTE asset library in the real app and use it.

    FR0286_URL=http://127.0.0.1:8286/ FR0286_OUT=<dir> FR0286_STEP=add|check \
      xvfb-run -a blender --app-template fresing_render --online-mode --python try_in_blender.py

step "add": add the remote library, open an Asset Browser on it, wait for the listing, download every asset,
place them (pallet at real size, the material on a block, the sky as the world, the workshop corner), save the
preferences, screenshots + a JSON of what happened (times, paths, sizes).  step "check": a second start in the same
settings folder: is the library still there, are the downloads still in the cache (offline use)?
"""
import json
import os
import sys
import time
from pathlib import Path

import bpy

URL = os.environ.get("FR0286_URL", "http://127.0.0.1:8286/")
OUT = Path(os.environ.get("FR0286_OUT", "/tmp/fr0286_out"))
STEP = os.environ.get("FR0286_STEP", "add")
NAME = "Fresing standard (test)"
OUT.mkdir(parents=True, exist_ok=True)
LOG = {"step": STEP, "online_access": bpy.app.online_access, "template": bpy.context.preferences.app_template
       if hasattr(bpy.context.preferences, "app_template") else None, "events": []}
T0 = time.time()


def log(*a):
    msg = " ".join(str(x) for x in a)
    LOG["events"].append([round(time.time() - T0, 2), msg])
    print("FR0286", msg, flush=True)


def shot(name):
    """bpy.ops.screen.screenshot gives a black picture under xvfb: grab the X screen with ImageMagick instead."""
    import subprocess
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    subprocess.run(["import", "-window", "root", str(OUT / (name + ".png"))], check=False)
    log("screenshot", name)


def lib():
    for lb in bpy.context.preferences.filepaths.asset_libraries:
        if lb.name == NAME:
            return lb
    return None


def browser_area():
    win = bpy.context.window_manager.windows[0]
    areas = sorted(win.screen.areas, key=lambda a: a.width * a.height, reverse=True)
    return win, areas


STATE = {"i": 0, "wait": 0, "assets": []}


def libs_now():
    return [(lb.name, lb.use_remote_url, lb.remote_url, lb.path, lb.import_method, lb.enabled)
            for lb in bpy.context.preferences.filepaths.asset_libraries]


def s_start():
    log("online_access", bpy.app.online_access, "libraries", libs_now())
    log("essentials on", bpy.context.preferences.asset_libraries.use_online_essentials,
        "essentials cache", bpy.types.AssetLibrary.online_assets_cache_path(),
        "exists", os.path.isdir(bpy.types.AssetLibrary.online_assets_cache_path()))
    log("remote libs experimental flag", bpy.context.preferences.experimental.use_remote_asset_libraries)
    if STEP == "check":
        lb = lib()
        log("CHECK library kept over restart:", lb is not None)
        if lb:
            p = Path(lb.path)
            files = sorted(str(f.relative_to(p)) for f in p.rglob("*.blend")) if p.exists() else []
            log("CHECK cached .blend files:", files)
        return True
    t = time.time()
    r = bpy.ops.preferences.asset_library_add(type="REMOTE", remote_url=URL, name=NAME)
    log("asset_library_add ->", r, "in", round(time.time() - t, 3), "s; now", libs_now())
    # Adding a REMOTE library starts its listing download at once (Blender's own sync, needs online access).
    STATE["t_list"] = time.time()
    return True


def s_browser():
    win, areas = browser_area()
    a = areas[0]
    LOG["area_was"] = a.ui_type
    a.ui_type = "ASSETS"
    sp = a.spaces.active
    items = [e.identifier for e in sp.params.bl_rna.properties["asset_library_reference"].enum_items] \
        if sp.params else []
    log("asset browser area", a.width, "x", a.height, "library choices", items)
    return True


def s_pick_library():
    """The library choice is a dynamic list: bl_rna only shows its fixed part, so set the name and read it back."""
    win, areas = browser_area()
    a = [x for x in areas if x.ui_type == "ASSETS"][0]
    sp = a.spaces.active
    if sp.params is None:
        return False
    try:
        sp.params.asset_library_reference = NAME
    except TypeError as ex:
        STATE["wait"] += 1
        if STATE["wait"] in (1, 30):
            log("library not offered yet:", str(ex)[:400])
        return STATE["wait"] > 40
    log("asset browser shows", sp.params.asset_library_reference)
    sp.params.display_size_discrete = "LARGE" if "LARGE" in [
        e.identifier for e in sp.params.bl_rna.properties["display_size_discrete"].enum_items] \
        else sp.params.display_size_discrete
    return True


def s_wait_listing():
    lb = lib()
    p = Path(lb.path)
    page = list(p.glob("_v1/assets-*.json")) if p.exists() else []
    thumbs = list(p.rglob("*.webp")) if p.exists() else []
    if page and len(thumbs) >= 4:
        log("listing + 4 pictures in the cache after", round(time.time() - STATE["t_list"], 2), "s; cache", lb.path,
            "files", sorted(str(f.relative_to(p)) for f in p.rglob("*") if f.is_file()))
        return True
    STATE["wait"] += 1
    if STATE["wait"] > 60:
        log("TIMEOUT waiting for the listing; cache", lb.path, "exists", p.exists(),
            [str(f) for f in p.rglob("*")] if p.exists() else [])
        return True
    return False


def s_shot_browser():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()
    shot("01_asset_browser_remote")
    return True


def s_select_and_list():
    win, areas = browser_area()
    a = [x for x in areas if x.ui_type == "ASSETS"][0]
    reg = [r for r in a.regions if r.type == "WINDOW"][0]
    with bpy.context.temp_override(window=win, area=a, region=reg):
        bpy.ops.file.select_all(action="SELECT")
        sel = list(bpy.context.selected_assets or [])
        for s in sel:
            md = s.metadata
            props = {k: (list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v) for k, v in md.items()} \
                if hasattr(md, "items") else {}
            STATE["assets"].append({"name": s.name, "id_type": s.id_type, "is_online": s.is_online,
                                    "full_library_path": s.full_library_path, "full_path": s.full_path,
                                    "author": md.author, "license": md.license, "props": props})
    log("assets seen", json.dumps(STATE["assets"], default=str))
    return True


def s_download():
    win, areas = browser_area()
    a = [x for x in areas if x.ui_type == "ASSETS"][0]
    reg = [r for r in a.regions if r.type == "WINDOW"][0]
    STATE["t_dl"] = time.time()
    with bpy.context.temp_override(window=win, area=a, region=reg):
        r = bpy.ops.asset.assets_download()
    log("assets_download ->", r)
    return True


def s_wait_download():
    lb = lib()
    p = Path(lb.path)
    blends = list(p.rglob("*.blend"))
    if len(blends) >= 4:
        log("4 .blend files downloaded after", round(time.time() - STATE["t_dl"], 2), "s:",
            [(str(b.relative_to(p)), b.stat().st_size) for b in blends])
        return True
    STATE["wait"] += 1
    if STATE["wait"] > 120:
        log("TIMEOUT waiting for downloads", [str(b) for b in blends])
        return True
    return False


def s_relist():
    STATE["assets"].clear()
    s_select_and_list()
    shot("02_asset_browser_downloaded")
    return True


def s_place():
    sc = bpy.context.scene
    lb = Path(lib().path)
    placed = {}
    for blend in sorted(lb.rglob("*.blend")):
        with bpy.data.libraries.load(str(blend), link=False, assets_only=True) as (src, dst):
            dst.objects, dst.materials, dst.worlds, dst.collections = src.objects, src.materials, src.worlds, src.collections
        for ob in dst.objects or []:
            if ob and ob.asset_data and ob.name not in [o.name for c in dst.collections or [] for o in c.objects]:
                sc.collection.objects.link(ob)
                ob.location = (2.5, -1.5, 0)
                placed["prop"] = [ob.name, [round(d, 4) for d in ob.dimensions], dict(ob.asset_data.items())]
        for c in dst.collections or []:
            if c and c.asset_data:
                sc.collection.children.link(c)
                placed["environment"] = [c.name, len(c.objects)]
        for w in dst.worlds or []:
            if w and w.asset_data:
                sc.world = w
                placed["world"] = w.name
        for m in dst.materials or []:
            if m and m.asset_data:
                bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, -1.5, 0.5))
                bpy.context.object.data.materials.append(m)
                placed["material"] = m.name
    imgs = [(i.name, bool(i.packed_file), i.size[:]) for i in bpy.data.images]
    log("placed", json.dumps(placed, default=str), "images (name, packed, size)", imgs)
    LOG["placed"] = placed
    LOG["images"] = imgs
    # look at it: the browser area back to the 3D view, material preview, from a camera-ish angle
    for a in bpy.context.window_manager.windows[0].screen.areas:
        if a.ui_type == "ASSETS":
            a.ui_type = LOG.get("area_was") or "VIEW_3D"
    for a in bpy.context.window_manager.windows[0].screen.areas:
        if a.type == "VIEW_3D":
            sp = a.spaces.active
            sp.shading.type = "MATERIAL"
            r3 = sp.region_3d
            from mathutils import Vector, Quaternion
            r3.view_location = Vector((-0.5, 1.0, 1.0))
            r3.view_distance = 14.0
            r3.view_rotation = Quaternion((0.82, 0.42, 0.18, 0.35)).normalized()
    return True


def s_shot_scene():
    STATE["wait"] += 1
    if STATE["wait"] < 8:      # material preview compiles its shaders first
        return False
    shot("03_placed_in_the_app")
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 32
    sc.render.resolution_x, sc.render.resolution_y = 640, 400
    cam = bpy.data.objects.new("proof_cam", bpy.data.cameras.new("proof_cam"))
    sc.collection.objects.link(cam)
    cam.location = (6.5, -8.0, 3.6)
    cam.rotation_euler = (1.25, 0, 0.62)
    cam.data.lens = 28
    sc.camera = cam
    t = time.time()
    sc.render.filepath = str(OUT / "04_render.png")
    bpy.ops.render.render(write_still=True)
    log("cycles 640x400 32 samples in", round(time.time() - t, 1), "s")
    # packing on save: a project that travels
    for i in bpy.data.images:
        if not i.packed_file:
            i.pack()
    p = OUT / "project_with_assets.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(p), copy=True, compress=True)
    log("project saved with the assets inside:", p.stat().st_size, "bytes")
    return True


def s_save_prefs():
    bpy.ops.wm.save_userpref()
    log("preferences saved; userpref", bpy.utils.user_resource("CONFIG"),
        sorted(os.listdir(bpy.utils.user_resource("CONFIG"))))
    return True


def s_quit():
    (OUT / f"log_{STEP}.json").write_text(json.dumps(LOG, indent=1, default=str))
    bpy.ops.wm.quit_blender()
    return True


def s_shot_offline():
    STATE["wait"] += 1
    if STATE["wait"] < 6:      # give the browser a few redraws to read the cached listing
        return False
    shot("05_offline_after_restart")
    return True


STEPS = [s_start, s_browser, s_pick_library, s_shot_offline, s_quit] if STEP == "check" else [
    s_start, s_browser, s_pick_library, s_wait_listing, s_shot_browser, s_select_and_list, s_download,
    s_wait_download, s_relist, s_place, s_shot_scene, s_save_prefs, s_quit]


def tick():
    try:
        f = STEPS[STATE["i"]]
        if f():
            STATE["i"] += 1
            STATE["wait"] = 0
    except Exception as ex:  # keep going: a proof logs its snags
        import traceback
        log("ERROR in", STEPS[STATE["i"]].__name__, repr(ex), traceback.format_exc()[-600:])
        STATE["i"] += 1
    return None if STATE["i"] >= len(STEPS) else 0.5


bpy.app.timers.register(tick, first_interval=6.0)
