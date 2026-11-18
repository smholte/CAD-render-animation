"""Measure where the time goes in a big Fresing Render project – the cable-lay demo above all (task 0195).

Not app code: a measuring tool. It changes the project only for a moment (hides a group, mutes a modifier kind, a
light look, a sea state, a joint value) and puts every change back; in the app it opens the saved project again at
the end, so nothing it did stays. It refuses to start on a project with unsaved changes.

**On the owner's PC (the app, with its window):**

1. Open the demo project (Help > Make demo project, or File > Open) and save it once (Ctrl+S) if it asks.
2. At the top of the window click the tab **Scripting**.
3. In the text editor in the middle click **Open**, pick ``measure_demo.py`` (from the release page or the
   repository's ``tools`` folder) and click **Open Text**.
4. Click **Run Script** (the ▶ button above the text). The window stands still for 3–10 minutes and flickers while it
   plays and turns the view: do not click.
5. When it is done the text editor shows "Fresing measure" – click in it, Ctrl+A, Ctrl+C and paste it into the chat.
   The same text is saved next to the project as ``<project> - measure.txt`` – after every part of the run, so if
   Blender closes during it (Material Preview comes last, after everything else), open that file in Notepad and
   paste what it holds.

Quick form (about 1–2 minutes): put ``QUICK = True`` below line 60 before Run Script.

**Here (no window, Blender as a Python module, no graphics card):**

    ~/venv/bin/python tools/measure_demo.py <project.blend> [--quick] [--out result.json] [--text result.txt]

and in the real app under xvfb (window, but software drawing – its drawing numbers are not the PC's):

    xvfb-run -a -s "-screen 0 1920x1080x24" <blender> --app-template fresing_render <project.blend> \
        --python tools/measure_demo.py -- [--quick] [--out result.json] [--text result.txt] [--quit]

What it measures (each number with how often it was repeated; a section that fails says why and the others go on):

- make-up: objects, unique meshes vs copies, triangles per collection, modifiers by kind, constraints by kind,
  drivers, keys, Geometry Nodes instances, images, ID-property arrays, meshes that are identical but not shared
- per frame: playing (runs of consecutive frames) and scrubbing (frames far apart): ms a frame, split into the app's
  Python handlers (each by name) and Blender's own update; then the same with one kind switched off at a time
  (modifier kinds, constraint kinds, drivers, each top collection hidden) – the difference is what that kind costs
- the window only: drawing a frame in Solid and in Material Preview, turning the view, playing with drawing, the
  graphics card's memory (``nvidia-smi``), each Fresing panel's own draw time, Undo / Redo and an undo step
- actions: select a part, the hover of the axis pickers, a joint moved live, a light look, a sea state, saving a copy,
  opening the project (app only: the last step)
- memory: the process, meshes by collection and by kind, the app's hidden shapes meshes, ID-property arrays, images
"""

from __future__ import annotations

import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict

QUICK = False                   # True: fewer frames and repeats (about 1–2 minutes instead of 3–10)
TEXT_NAME = "Fresing measure"
VERSION = 1                     # of this tool's text block (the lead reads it)

# --------------------------------------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------------------------------------


def now() -> float:
    return time.perf_counter()


def rss_mb() -> float:
    """Resident memory of this process in MB (Linux /proc, Windows psapi); 0 when unknown."""
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/self/status", encoding="ascii") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return pmc.WorkingSetSize / 1048576.0
    except Exception:  # noqa: BLE001 - memory is a nice-to-have line
        pass
    return 0.0


def gpu_memory_mb() -> str:
    """Used / total memory of the NVIDIA card (nvidia-smi), or why not."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,name", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, creationflags=flags)
        if out.returncode == 0 and out.stdout.strip():
            used, total, name = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",", 2)]
            return f"{used} / {total} MB ({name})"
        return "n/a (nvidia-smi gave nothing)"
    except Exception as exc:  # noqa: BLE001
        return f"n/a ({type(exc).__name__})"


def gpu_used_mb() -> float:
    m = re.match(r"(\d+)", gpu_memory_mb())
    return float(m.group(1)) if m else -1.0


def plain(name: str) -> str:
    """A modifier's / node group's / object's name without its number (".001", " 3")."""
    name = re.sub(r"\.\d{3}$", "", name)
    return re.sub(r"[ _]\d+$", "", name).strip()


def app_pkg():
    """The app's package: ``fresing_render`` from the repository, or the installed extension's module."""
    import addon_utils
    for m in addon_utils.modules():
        if m.__name__.endswith("fresing_render"):
            return m.__name__
    return "fresing_render"


def app(sub: str):
    import importlib
    return importlib.import_module(app_pkg() + "." + sub)


# --------------------------------------------------------------------------------------------------------------------
# the result: sections of lines (the text block) + the numbers (JSON)
# --------------------------------------------------------------------------------------------------------------------


class Result:
    def __init__(self):
        self.lines: list[str] = []
        self.data: dict = {}
        self.frame_costs: list[tuple[str, float]] = []      # (what, ms a frame)
        self.save_to = ""                                   # the text file, written again after every section
        self.action_costs: list[tuple[str, float]] = []     # (what, s)

    def head(self, title: str):
        self.lines.append("")
        self.lines.append(f"## {title}")

    def line(self, text: str):
        self.lines.append(text)
        print("[measure]", text, flush=True)

    def section(self, title: str, fn, *args):
        self.head(title)
        t0 = now()
        try:
            fn(self, *args)
        except Exception as exc:  # noqa: BLE001 - one section failing must not stop the others
            self.line(f"FAILED: {type(exc).__name__}: {exc}")
            self.data.setdefault("failed", {})[title] = traceback.format_exc()
            print(traceback.format_exc(), flush=True)
        self.data.setdefault("section_seconds", {})[title] = round(now() - t0, 1)
        self.flush()

    def flush(self):
        """Write what there is so far (if Blender stops in a later section, the file still has these)."""
        if self.save_to:
            try:
                with open(self.save_to, "w", encoding="utf-8") as fh:
                    fh.write(self.text())
            except OSError:
                pass

    def text(self) -> str:
        out = list(self.lines)
        out.append("")
        out.append("## Top 10 per-frame costs (ms a frame, from the sections above)")
        for what, ms in sorted(self.frame_costs, key=lambda r: -r[1])[:10]:
            out.append(f"{ms:8.2f}  {what}")
        out.append("")
        out.append("## Slowest actions (s)")
        for what, s in sorted(self.action_costs, key=lambda r: -r[1])[:10]:
            out.append(f"{s:8.2f}  {what}")
        return "\n".join(out).strip() + "\n"


# --------------------------------------------------------------------------------------------------------------------
# make-up of the scene
# --------------------------------------------------------------------------------------------------------------------

ITEM_BYTES = {"FLOAT": 4, "INT": 4, "FLOAT_VECTOR": 12, "FLOAT_COLOR": 16, "BYTE_COLOR": 4, "STRING": 0,
              "BOOLEAN": 1, "FLOAT2": 8, "INT8": 1, "INT16_2D": 4, "INT32_2D": 8, "QUATERNION": 16,
              "FLOAT4X4": 64}


def top_collection(scene) -> dict:
    """object name -> 'top collection / second collection' (the first collection the object lies in)."""
    where = {}

    def walk(coll, path):
        for ob in coll.objects:
            where.setdefault(ob.name, " / ".join(path) if path else "(scene)")
        for ch in coll.children:
            walk(ch, (path + [ch.name])[:2])
    walk(scene.collection, [])
    return where


def mesh_tris(me) -> int:
    import numpy as np
    n = len(me.polygons)
    if n == 0:
        return 0
    lt = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get("loop_total", lt)
    return int(lt.sum() - 2 * n)


def mesh_bytes(me) -> int:
    """What a mesh's arrays take (positions and other attributes, corners, edges, faces), not Blender's caches."""
    b = len(me.edges) * 8 + len(me.loops) * 8 + len(me.polygons) * 4
    for a in me.attributes:
        if a.name in (".corner_vert", ".corner_edge", ".edge_verts"):
            continue
        try:
            b += len(a.data) * ITEM_BYTES.get(a.data_type, 4)
        except Exception:  # noqa: BLE001
            pass
    return b


def idprop_bytes(idblock) -> tuple[int, list]:
    """Bytes of the array / string ID properties on a datablock, and its biggest keys."""
    total, keys = 0, []
    try:
        names = list(idblock.keys())
    except Exception:  # noqa: BLE001
        return 0, []
    for k in names:
        try:
            v = idblock[k]
        except Exception:  # noqa: BLE001
            continue
        b = 0
        if hasattr(v, "typecode"):
            b = len(v) * (8 if v.typecode == "d" else 4)
        elif isinstance(v, str):
            b = len(v)
        elif hasattr(v, "to_list") or isinstance(v, (list, tuple)):
            try:
                b = len(json.dumps(v.to_list() if hasattr(v, "to_list") else v))
            except Exception:  # noqa: BLE001
                b = 0
        if b:
            total += b
            keys.append((k, b))
    return total, keys


def fcurves_of(anim) -> list:
    """All F-curves of an animation_data's action (5.x layered actions; older flat actions)."""
    out = []
    act = getattr(anim, "action", None)
    if act is None:
        return out
    try:
        slot = getattr(anim, "action_slot", None)
        for layer in act.layers:
            for strip in layer.strips:
                if slot is not None:
                    cb = strip.channelbag(slot)
                    if cb is not None:
                        out.extend(cb.fcurves)
                else:
                    for cb in strip.channelbags:
                        out.extend(cb.fcurves)
        return out
    except AttributeError:
        return list(getattr(act, "fcurves", []))


def all_anim_owners():
    import bpy
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.node_groups, bpy.data.scenes,
                 bpy.data.worlds, bpy.data.cameras, bpy.data.lights, bpy.data.shape_keys):
        for idb in coll:
            ad = getattr(idb, "animation_data", None)
            if ad is not None:
                yield idb, ad
            nt = getattr(idb, "node_tree", None)
            if nt is not None and nt.animation_data is not None:
                yield nt, nt.animation_data


def driver_kind(idb, path: str) -> str:
    kind = type(idb).__name__
    if path.startswith('["'):
        return f"{kind} custom property"
    if path.startswith("modifiers"):
        return f"{kind} modifier input"
    if path.startswith("nodes"):
        return f"{kind} node value"
    if path.split(".")[0] in ("location", "rotation_euler", "rotation_quaternion", "scale", "delta_location",
                              "delta_rotation_euler"):
        return f"{kind} transform"
    if path.startswith("hide"):
        return f"{kind} visibility"
    return f"{kind} {path.split('.')[0].split('[')[0]}"


def makeup(r: Result, scene):
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    where = top_collection(scene)
    obs = list(scene.objects)
    by_type = defaultdict(int)
    for ob in obs:
        by_type[ob.type] += 1
    r.line(f"objects {len(obs)}: " + ", ".join(f"{k} {v}" for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])))
    meshes = [ob for ob in obs if ob.type == "MESH"]
    unique = {ob.data.name for ob in meshes if ob.data is not None}
    shared = sum(1 for ob in meshes if ob.data is not None and ob.data.users > 1)
    r.line(f"mesh objects {len(meshes)}, unique meshes {len(unique)} ({shared} objects share a mesh with another)")
    # triangles as drawn (evaluated, visible objects) per collection
    tris_by = defaultdict(lambda: [0, 0, 0])            # collection -> [objects, triangles, own mesh triangles]
    tri_obs = []
    total = 0
    hidden = 0
    for ob in obs:
        if ob.type not in ("MESH", "CURVE", "FONT", "CURVES", "POINTCLOUD"):
            continue
        if not ob.visible_get():
            hidden += 1
            continue
        ev = ob.evaluated_get(dg)
        t = 0
        try:
            if ev.type == "MESH":
                t = mesh_tris(ev.data)
        except Exception:  # noqa: BLE001
            t = 0
        g = where.get(ob.name, "(other)")
        tris_by[g][0] += 1
        tris_by[g][1] += t
        total += t
        tri_obs.append((t, ob.name, g))
    inst = defaultdict(int)
    for oi in dg.object_instances:
        if oi.is_instance:
            inst[plain(oi.instance_object.name) if oi.instance_object else "?"] += 1
    r.line(f"triangles drawn (shown objects, after modifiers) {total / 1e6:.2f} M; {hidden} mesh-like objects hidden")
    r.data["triangles_by_collection"] = {k: v for k, v in tris_by.items()}
    for g, (n, t, _o) in sorted(tris_by.items(), key=lambda kv: -kv[1][1])[:14]:
        r.line(f"  {t / 1e6:6.2f} M tris  {n:5d} objects  {g}")
    r.line("  biggest objects: " + "; ".join(f"{n} {t / 1e3:.0f} k" for t, n, _g in sorted(tri_obs, reverse=True)[:8]))
    r.data["biggest_objects"] = sorted(tri_obs, reverse=True)[:40]
    if inst:
        r.line(f"Geometry Nodes / collection instances {sum(inst.values())}: "
               + ", ".join(f"{k} {v}" for k, v in sorted(inst.items(), key=lambda kv: -kv[1])[:6]))
    # modifiers, constraints
    mods = defaultdict(lambda: [0, 0])                  # kind -> [count, shown]
    for ob in obs:
        for m in ob.modifiers:
            k = mod_kind(m)
            mods[k][0] += 1
            mods[k][1] += int(m.show_viewport and ob.visible_get())
    r.data["modifiers"] = {k: v for k, v in mods.items()}
    r.line(f"modifiers {sum(v[0] for v in mods.values())}: " + ", ".join(
        f"{k} {v[0]} ({v[1]} on shown objects)" for k, v in sorted(mods.items(), key=lambda kv: -kv[1][0])[:12]))
    cons = defaultdict(int)
    for ob in obs:
        for c in ob.constraints:
            cons[cons_kind(c)] += 1
    r.data["constraints"] = dict(cons)
    r.line(f"constraints {sum(cons.values())}: " + ", ".join(
        f"{k} {v}" for k, v in sorted(cons.items(), key=lambda kv: -kv[1])[:10]))
    # drivers and keys
    drv = defaultdict(int)
    simple = 0
    keyed_curves = 0
    keys = 0
    for idb, ad in all_anim_owners():
        for fc in ad.drivers:
            drv[driver_kind(idb, fc.data_path)] += 1
            simple += int(fc.driver.type != "SCRIPTED" or fc.driver.is_simple_expression)
        for fc in fcurves_of(ad):
            keyed_curves += 1
            keys += len(fc.keyframe_points)
    nd = sum(drv.values())
    r.data["drivers"] = dict(drv)
    r.line(f"drivers {nd} ({nd - simple} need Python): " + ", ".join(
        f"{k} {v}" for k, v in sorted(drv.items(), key=lambda kv: -kv[1])[:8]))
    r.line(f"keyed F-curves {keyed_curves}, keys {keys}")
    # materials, images
    img_mb = 0.0
    for im in bpy.data.images:
        try:
            w, h = im.size
            img_mb += w * h * max(1, im.channels) * (4 if im.is_float else 1) / 1048576.0
        except Exception:  # noqa: BLE001
            pass
    r.line(f"materials {len(bpy.data.materials)}, node groups {len(bpy.data.node_groups)}, images "
           f"{len(bpy.data.images)} ({img_mb:.0f} MB as pixels)")
    r.data["counts"] = {"objects": len(obs), "mesh_objects": len(meshes), "unique_meshes": len(unique),
                        "triangles": total, "drivers": nd, "keyed_curves": keyed_curves, "keys": keys,
                        "materials": len(bpy.data.materials), "images": len(bpy.data.images),
                        "image_mb": round(img_mb, 1), "instances": sum(inst.values())}
    # identical meshes that are not shared (instancing would save their memory, not their drawing)
    sig = defaultdict(list)
    for me in bpy.data.meshes:
        if me.users == 0 or len(me.vertices) < 50:
            continue
        sig[(len(me.vertices), len(me.polygons), tuple(round(x, 4) for x in bbox_size(me)))].append(me)
    dup_meshes = dup_tris = 0
    dup_rows = []
    for k, group in sig.items():
        if len(group) > 1:
            extra = len(group) - 1
            dup_meshes += extra
            t = mesh_tris(group[0]) * extra
            dup_tris += t
            dup_rows.append((t, plain(group[0].name), len(group)))
    r.line(f"identical meshes NOT shared: {dup_meshes} extra copies, {dup_tris / 1e6:.2f} M triangles of mesh data "
           "(sharing saves memory and file size, not drawing)")
    for t, n, c in sorted(dup_rows, reverse=True)[:5]:
        r.line(f"  {c} x {n}: {t / 1e3:.0f} k extra triangles")
    r.data["duplicates"] = sorted(dup_rows, reverse=True)[:30]


def bbox_size(me):
    import numpy as np
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return tuple((co.max(0) - co.min(0)).tolist())


def mod_kind(m) -> str:
    if m.type == "NODES":
        return "GN " + plain(m.name)
    return m.type.title()


def cons_kind(c) -> str:
    tgt = getattr(c, "target", None)
    return c.type.title() + (f" -> {plain(tgt.name)}" if tgt is not None and c.type == "CHILD_OF" else "")


# --------------------------------------------------------------------------------------------------------------------
# per frame: playing and scrubbing, handlers and switched-off kinds
# --------------------------------------------------------------------------------------------------------------------

HANDLER_LISTS = ("frame_change_pre", "frame_change_post", "depsgraph_update_pre", "depsgraph_update_post")


class HandlerTimer:
    """Wraps every function in the four per-frame handler lists; counts calls and seconds per function."""

    def __init__(self):
        self.t = defaultdict(float)
        self.n = defaultdict(int)
        self.saved = []

    def __enter__(self):
        import bpy
        for lst_name in HANDLER_LISTS:
            lst = getattr(bpy.app.handlers, lst_name)
            for i, fn in enumerate(list(lst)):
                label = f"{lst_name}: {getattr(fn, '__module__', '?').split('.')[-1]}.{getattr(fn, '__name__', '?')}"
                lst[i] = self._wrap(fn, label)
                self.saved.append((lst, i, fn))
        return self

    def _wrap(self, fn, label):
        def wrapper(*args, **kw):
            t0 = now()
            try:
                return fn(*args, **kw)
            finally:
                self.t[label] += now() - t0
                self.n[label] += 1
        return wrapper

    def __exit__(self, *exc):
        for lst, i, fn in self.saved:
            if i < len(lst):
                lst[i] = fn

    def reset(self):
        self.t.clear()
        self.n.clear()


def frame_sets(scene, quick: bool):
    f0, f1 = int(scene.frame_start), int(scene.frame_end)
    span = max(1, f1 - f0)
    runs = 3 if quick else 5
    run_len = 20 if quick else 40
    play = []
    for k in range(runs):
        s = f0 + int(span * (k + 0.5) / runs)
        play.append(list(range(s, min(f1, s + run_len) + 1)))
    n = 30 if quick else 80
    scrub = [f0 + int(span * ((k * 0.618034) % 1.0)) for k in range(n)]      # far apart, all over the range
    return play, scrub


def ms_per_frame(scene, runs) -> float:
    """ms a frame over runs of frames (the first frame of each run is not counted: it is a jump)."""
    tot, n = 0.0, 0
    for run in runs:
        scene.frame_set(run[0])
        t0 = now()
        for f in run[1:]:
            scene.frame_set(f)
        tot += now() - t0
        n += len(run) - 1
    return 1000.0 * tot / max(1, n)


def ms_scrub(scene, frames) -> float:
    t0 = now()
    for f in frames:
        scene.frame_set(f)
    return 1000.0 * (now() - t0) / max(1, len(frames))


def switched_on(scene) -> list:
    """What the ablations switch off, counted (to check it is all back afterwards)."""
    import bpy
    mods = sum(int(m.show_viewport) for ob in scene.objects for m in ob.modifiers)
    cons = sum(int(c.enabled) for ob in scene.objects for c in ob.constraints)
    drv = sum(int(not fc.mute) for _idb, ad in all_anim_owners() for fc in ad.drivers)
    excl = sum(int(lc.exclude) for lc in bpy.context.view_layer.layer_collection.children)
    hand = [len(getattr(bpy.app.handlers, n)) for n in HANDLER_LISTS]
    return [mods, cons, drv, excl] + hand


def per_frame(r: Result, scene, quick: bool):
    import bpy
    play, scrub = frame_sets(scene, quick)
    nplay = sum(len(x) - 1 for x in play)
    r.line(f"frames {scene.frame_start}–{scene.frame_end} at {scene.render.fps} fps; playing = {len(play)} runs of "
           f"{len(play[0])} frames ({nplay} timed), scrubbing = {len(scrub)} frames far apart")
    ms_per_frame(scene, [play[0][:6]])                   # warm up
    with HandlerTimer() as ht:
        ht.reset()
        playing = ms_per_frame(scene, play)
        hp = {k: 1000.0 * v / nplay for k, v in ht.t.items()}
        hn = dict(ht.n)
        ht.reset()
        scrubbing = ms_scrub(scene, scrub)
        hs = {k: 1000.0 * v / len(scrub) for k, v in ht.t.items()}
    hsum = sum(hp.values())
    r.line(f"playing {playing:.1f} ms a frame ({1000 / playing:.0f} fps without drawing): app handlers "
           f"{hsum:.1f} ms, Blender's own update {playing - hsum:.1f} ms")
    r.line(f"scrubbing {scrubbing:.1f} ms a frame: app handlers {sum(hs.values()):.1f} ms")
    r.data["playing_ms"] = round(playing, 2)
    r.data["scrubbing_ms"] = round(scrubbing, 2)
    r.data["handlers_playing_ms"] = {k: round(v, 3) for k, v in hp.items()}
    r.data["handlers_scrubbing_ms"] = {k: round(v, 3) for k, v in hs.items()}
    r.frame_costs.append(("Blender's own update while playing (all of it)", playing - hsum))
    for k in sorted(set(hp) | set(hs), key=lambda k: -(hp.get(k, 0) + hs.get(k, 0))):
        r.line(f"  {hp.get(k, 0):7.3f} ms playing  {hs.get(k, 0):7.3f} ms scrubbing  "
               f"({hn.get(k, 0) / max(1, nplay):.1f} calls a frame)  {k}")
        r.frame_costs.append((f"handler {k}", hp.get(k, 0)))
    # switched off one kind at a time
    r.line("switched off one at a time (playing ms a frame less = what it costs; ± ~0.5 ms is noise):")
    first_state = switched_on(scene)
    base_runs = [x[:10] if quick else x[:24] for x in play]
    ms_per_frame(scene, [base_runs[0][:3]])
    last_on = [ms_per_frame(scene, base_runs)]          # all on: measured between every two switch-offs
    bases = list(last_on)
    rows = []

    def ablate(label, off, on):
        """Off, measured; on again, measured: the cost is the mean of the two 'on' times around it minus 'off'
        (a slow drift of the machine cancels out)."""
        try:
            off()
            try:
                ms_per_frame(scene, [base_runs[0][:3]])
                ms = ms_per_frame(scene, base_runs)
            finally:
                on()
            ms_per_frame(scene, [base_runs[0][:3]])
            on_ms = ms_per_frame(scene, base_runs)
            rows.append((0.5 * (last_on[0] + on_ms) - ms, label))
            last_on[0] = on_ms
            bases.append(on_ms)
        except Exception as exc:  # noqa: BLE001
            r.line(f"  could not switch off {label}: {exc}")
    # modifier kinds
    kinds = defaultdict(list)
    for ob in scene.objects:
        for m in ob.modifiers:
            if m.show_viewport:
                kinds[mod_kind(m)].append(m)
    for k, ms in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
        ablate(f"modifiers {k} ({len(ms)})", lambda ms=ms: [setattr(m, "show_viewport", False) for m in ms],
               lambda ms=ms: [setattr(m, "show_viewport", True) for m in ms])
    # constraint kinds
    ck = defaultdict(list)
    for ob in scene.objects:
        for c in ob.constraints:
            if c.enabled:
                ck[cons_kind(c)].append(c)
    for k, cs in sorted(ck.items(), key=lambda kv: -len(kv[1])):
        if len(cs) < 3:
            continue
        ablate(f"constraints {k} ({len(cs)})", lambda cs=cs: [setattr(c, "enabled", False) for c in cs],
               lambda cs=cs: [setattr(c, "enabled", True) for c in cs])
    # drivers by kind
    dk = defaultdict(list)
    for idb, ad in all_anim_owners():
        for fc in ad.drivers:
            if not fc.mute:
                dk[driver_kind(idb, fc.data_path)].append(fc)
    for k, fcs in sorted(dk.items(), key=lambda kv: -len(kv[1])):
        if len(fcs) < 5:
            continue
        ablate(f"drivers {k} ({len(fcs)})", lambda fcs=fcs: [setattr(f, "mute", True) for f in fcs],
               lambda fcs=fcs: [setattr(f, "mute", False) for f in fcs])
    # each top collection left out of the scene
    vl = bpy.context.view_layer
    for lc in vl.layer_collection.children:
        if lc.exclude:
            continue
        n = len(lc.collection.all_objects)
        ablate(f"collection '{lc.name}' left out ({n} objects)", lambda lc=lc: setattr(lc, "exclude", True),
               lambda lc=lc: setattr(lc, "exclude", False))
    # the app's handlers as a whole
    saved = {}

    def handlers_off():
        for nm in HANDLER_LISTS:
            lst = getattr(bpy.app.handlers, nm)
            saved[nm] = list(lst)
            lst.clear()

    def handlers_on():
        for nm, fns in saved.items():
            lst = getattr(bpy.app.handlers, nm)
            lst.clear()
            lst.extend(fns)
    before = first_state
    ablate("all per-frame Python handlers", handlers_off, handlers_on)
    r.data["restored"] = {"before": before, "after": switched_on(scene)}
    if before != r.data["restored"]["after"]:
        r.line(f"  WARNING: not everything was put back: {before} -> {r.data['restored']['after']}")
    r.data["ablation_ms"] = {lab: round(d, 2) for d, lab in rows}
    for d, lab in sorted(rows, reverse=True):
        if abs(d) >= 0.3 or "handlers" in lab:
            r.line(f"  {d:7.2f} ms  {lab}")
        r.frame_costs.append((lab, d))
    import statistics
    r.data["ablation_base_ms"] = [round(x, 2) for x in bases]
    r.line(f"  (all on: {statistics.median(bases):.1f} ms a frame median, {min(bases):.1f}–{max(bases):.1f} over "
           f"{len(bases)} measurements = the noise; kinds under 0.3 ms not listed)")


# --------------------------------------------------------------------------------------------------------------------
# the window: drawing, panels, undo (only in the app)
# --------------------------------------------------------------------------------------------------------------------


def view3d():
    import bpy
    best = None
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                reg = next((x for x in area.regions if x.type == "WINDOW"), None)
                if reg is not None and (best is None or area.width * area.height > best[1].width * best[1].height):
                    best = (win, area, reg)
    return best


def redraw(win, area, region, kind="DRAW_WIN_SWAP", n=1) -> float:
    """ms per redraw (``wm.redraw_timer``): DRAW = this region, DRAW_WIN_SWAP = the whole window shown."""
    import bpy
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        t0 = now()
        bpy.ops.wm.redraw_timer(type=kind, iterations=n)
        return 1000.0 * (now() - t0) / n


def software_drawing() -> bool:
    """No graphics card: Mesa's llvmpipe / a software renderer (the web machines, GitHub)."""
    try:
        import gpu
        name = (gpu.platform.renderer_get() + " " + gpu.platform.vendor_get()).lower()
        return any(w in name for w in ("llvmpipe", "software", "softpipe", "swiftshader", "microsoft basic"))
    except Exception:  # noqa: BLE001
        return True


def drawing(r: Result, scene, quick: bool, shades=("SOLID",)):
    import bpy
    v = view3d()
    if v is None:
        r.line("no 3D view in the window")
        return
    win, area, region = v
    space = area.spaces.active
    shading_was = space.shading.type
    try:
        import gpu
        r.line(f"graphics: {gpu.platform.renderer_get()} ({gpu.platform.backend_type_get()}), 3D view "
               f"{region.width} x {region.height} px, window {win.width} x {win.height}")
    except Exception:  # noqa: BLE001
        pass
    r.line(f"graphics card memory at the start: {gpu_memory_mb()}")
    play, _scrub = frame_sets(scene, quick)
    n = 10 if quick else 30
    out = {}
    try:
        for shade in shades:
            g0 = gpu_used_mb()
            t0 = now()
            space.shading.type = shade
            first = redraw(win, area, region, "DRAW_WIN_SWAP", 1)
            first_s = now() - t0
            if shade == "MATERIAL":                         # shaders compile in the background: wait for them
                t1 = now()
                for _ in range(600):
                    redraw(win, area, region, "DRAW_WIN_SWAP", 1)
                    if not bpy.app.is_job_running("SHADER_COMPILATION") if hasattr(bpy.app, "is_job_running") \
                            else True:
                        break
                    time.sleep(0.05)
                first_s += now() - t1
            still = redraw(win, area, region, "DRAW_WIN_SWAP", n)
            region_only = redraw(win, area, region, "DRAW", n)
            # turn the view (orbit) 10° a step
            r3d = space.region_3d
            rot = r3d.view_rotation.copy()
            from mathutils import Quaternion
            t0 = now()
            steps = 12 if quick else 36
            for k in range(steps):
                r3d.view_rotation = Quaternion((0, 0, 1), math.radians(10 * (k + 1))) @ rot
                redraw(win, area, region, "DRAW_WIN_SWAP", 1)
            orbit = 1000.0 * (now() - t0) / steps
            r3d.view_rotation = rot
            # play with drawing: frame + the window drawn, as Play does
            t_play = now()
            cnt = 0
            for seq in play[:2]:
                scene.frame_set(seq[0])
                for f in seq[1:]:
                    scene.frame_set(f)
                    redraw(win, area, region, "DRAW_WIN_SWAP", 1)
                    cnt += 1
            playing = 1000.0 * (now() - t_play) / max(1, cnt)
            g1 = gpu_used_mb()
            name = {"SOLID": "Solid", "MATERIAL": "Material Preview"}[shade]
            out[shade] = {"first_s": round(first_s, 2), "first_draw_ms": round(first, 1), "still_ms": round(still, 2),
                          "region_ms": round(region_only, 2), "orbit_ms": round(orbit, 2),
                          "play_ms": round(playing, 2), "gpu_mb": [g0, g1]}
            r.line(f"{name}: switch + first picture {first_s:.1f} s; a still picture {still:.1f} ms (3D view alone "
                   f"{region_only:.1f} ms); turning the view {orbit:.1f} ms a step ({1000 / orbit:.0f} fps); playing "
                   f"with drawing {playing:.1f} ms a frame ({1000 / playing:.0f} fps)")
            if g0 >= 0:
                r.line(f"  graphics card memory {g0:.0f} -> {g1:.0f} MB")
            r.frame_costs.append((f"drawing a frame in {name} (window)", still))
            r.action_costs.append((f"switch to {name} + first picture", first_s))
    finally:
        space.shading.type = shading_was
    r.data.setdefault("drawing", {}).update(out)
    if "SOLID" in shades:
        r.line("(a redraw with swap may wait for the screen's refresh: about 16.7 ms at 60 Hz is the floor)")


def drawing_material(r: Result, scene, quick: bool):
    """Material Preview (EEVEE): last of all, after the text file was written – a crash here loses nothing."""
    if software_drawing():
        r.line("left out: no graphics card here (software drawing); EEVEE crashed Blender on it (task 0195)")
        return
    drawing(r, scene, quick, shades=("MATERIAL",))


def sidebar_region():
    import bpy
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for reg in area.regions:
                    if reg.type == "UI":
                        return win, area, reg
    return None


PANELS: dict = {"clones": [], "times": defaultdict(float), "shown_was": None, "now_ms": None, "category": ""}


def show_sidebar() -> None:
    """Step 1 (a tick before measuring): the side panel shown, so the window gives it its size."""
    s = sidebar_region()
    if s is None:
        return
    space = s[1].spaces.active
    PANELS["shown_was"] = space.show_region_ui
    space.show_region_ui = True


def sidebar_redraw(n: int) -> float:
    """ms per window redraw with the side panel marked for a new layout (its panels' draw functions run; the other
    regions are only put on screen again)."""
    import bpy
    win, area, reg = sidebar_region()
    t = 0.0
    for _ in range(n):
        reg.tag_redraw()
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=reg):
            t0 = now()
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)      # (DRAW_WIN skips the panels' layout)
            t += now() - t0
    return 1000.0 * t / n


def prepare_panels(quick: bool) -> None:
    """Step 2 (a tick later): the side panel as the owner has it open, timed."""
    s = sidebar_region()
    if s is None or s[2].width <= 1:
        return
    try:
        PANELS["category"] = s[2].active_panel_category or "?"
    except Exception:  # noqa: BLE001
        PANELS["category"] = "?"
    PANELS["now_ms"] = sidebar_redraw(3 if quick else 8)


def add_panel_copies() -> None:
    """Every Fresing panel registered again as an open copy in the side panel's current tab; their draw timed."""
    import bpy
    s = sidebar_region()
    if s is None:
        return
    try:
        cat = s[2].active_panel_category or "Fresing"
    except Exception:  # noqa: BLE001
        cat = "Fresing"
    times = PANELS["times"]
    suffix = "__measure"

    def timed(fn, label):
        def draw(self, context):
            t0 = now()
            try:
                return fn(self, context)
            finally:
                times[label] += now() - t0
        return draw
    for base in app_panels():
        name = base.__dict__.get("bl_idname") or base.__name__
        attrs = {"bl_idname": name + suffix, "bl_category": cat,
                 "bl_options": set(getattr(base, "bl_options", set())) - {"DEFAULT_CLOSED"}}
        parent = getattr(base, "bl_parent_id", "")
        if parent:
            attrs["bl_parent_id"] = parent + suffix
        attrs["draw"] = timed(base.draw, name)
        if hasattr(base, "draw_header"):
            attrs["draw_header"] = timed(base.draw_header, name + " (header)")
        try:
            clone = type(name + suffix, (base,), attrs)
            bpy.utils.register_class(clone)
            PANELS["clones"].append(clone)
        except Exception:  # noqa: BLE001 - a panel that cannot be copied is left out
            pass


def app_panels() -> list:
    """The app's registered panel classes (Python classes: ``bpy.types.<name>`` may give Blender's own type without
    the draw function), parents before their sub-panels."""
    import bpy
    seen, out, todo = set(), [], list(bpy.types.Panel.__subclasses__())
    while todo:
        c = todo.pop()
        todo.extend(c.__subclasses__())
        idn = c.__dict__.get("bl_idname") or c.__name__
        if idn.startswith("FRESING_PT_") and not idn.endswith("__measure") and idn not in seen and \
                hasattr(c, "bl_rna") and "draw" in dir(c):
            seen.add(idn)
            out.append(c)
    parent = {(c.__dict__.get("bl_idname") or c.__name__): getattr(c, "bl_parent_id", "") for c in out}

    def depth(c):
        n, d = c.__dict__.get("bl_idname") or c.__name__, 0
        while parent.get(n) and d < 20:
            n, d = parent[n], d + 1
        return d
    return sorted(out, key=lambda c: (depth(c), c.__name__))


def drop_panels() -> None:
    import bpy
    for cls in reversed(PANELS["clones"]):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
    PANELS["clones"].clear()
    s = sidebar_region()
    if s is not None and PANELS["shown_was"] is not None:
        s[1].spaces.active.show_region_ui = PANELS["shown_was"]


def panels(r: Result, scene, quick: bool):
    """Each Fresing panel's own draw time (open copies of all of them, for a moment) and the side panel's redraw."""
    s = sidebar_region()
    try:
        if s is None or s[2].width <= 1:
            r.line("no side panel shown")
            return
        win, area, reg = s
        if PANELS["now_ms"] is not None:
            r.line(f"window redraw with the side panel as it was open (tab '{PANELS['category']}'): "
                   f"{PANELS['now_ms']:.1f} ms")
            r.data["sidebar_now_ms"] = round(PANELS["now_ms"], 2)
        add_panel_copies()
        if not PANELS["clones"]:
            r.line("the panels could not be copied")
            return
        times = PANELS["times"]
        n = 3 if quick else 8
        sidebar_redraw(2)                                 # first layout of the copies
        times.clear()
        whole = sidebar_redraw(n)
        rows = sorted(((1000.0 * t / n, k) for k, t in times.items()), reverse=True)
        tot = sum(ms for ms, _k in rows)
        r.line(f"window redraw with every Fresing panel open as well: {whole:.1f} ms ({len(PANELS['clones'])} panels;"
               f" their Python {tot:.1f} ms of it; {n} redraws; side panel {reg.width} x {reg.height} px)")
        for ms, k in rows[:12]:
            r.line(f"  {ms:7.2f} ms  {k.replace('FRESING_PT_', '')}")
        r.data["panels_ms"] = {k: round(ms, 3) for ms, k in rows}
        r.data["sidebar_ms"] = round(whole, 2)
        r.data["panels_python_ms"] = round(tot, 2)
        r.action_costs.append(("side panel redraw, every panel open", whole / 1000.0))
    finally:
        drop_panels()


def undo(r: Result, scene, quick: bool):
    """An undo step (Blender writes the whole project into memory for it), Undo and Redo. Last of the app steps."""
    import bpy
    v = view3d()
    if v is None:
        return
    win, area, region = v
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        ob = next((o for o in scene.objects if o.type == "MESH" and o.visible_get()), None)
        if ob is None:
            return
        rows = []
        for k in range(2 if quick else 3):
            ob.select_set(not ob.select_get())
            t0 = now()
            bpy.ops.ed.undo_push(message="measure")
            push = now() - t0
            t0 = now()
            bpy.ops.ed.undo()
            u = now() - t0
            t0 = now()
            bpy.ops.ed.redo()
            rd = now() - t0
            rows.append((push, u, rd))
            scene = bpy.context.scene
            ob = next((o for o in scene.objects if o.type == "MESH" and o.visible_get()), None)
        push, u, rd = (min(x) for x in zip(*rows))
        r.line(f"an undo step (after every change) {push:.2f} s; Undo {u:.2f} s; Redo {rd:.2f} s "
               f"(best of {len(rows)})")
        r.data["undo"] = {"push_s": round(push, 3), "undo_s": round(u, 3), "redo_s": round(rd, 3)}
        r.action_costs += [("undo step (after every change)", push), ("Undo", u), ("Redo", rd)]


# --------------------------------------------------------------------------------------------------------------------
# actions
# --------------------------------------------------------------------------------------------------------------------


def actions(r: Result, scene, quick: bool):
    import bpy
    import numpy as np
    from mathutils import Vector
    dg = bpy.context.evaluated_depsgraph_get()
    vl = bpy.context.view_layer
    parts = [ob for ob in scene.objects if ob.type == "MESH" and ob.visible_get() and ob.get("fr_name") is not None]
    if not parts:
        parts = [ob for ob in scene.objects if ob.type == "MESH" and ob.visible_get()]
    rng = np.random.default_rng(195)
    pick = [parts[i] for i in rng.choice(len(parts), size=min(len(parts), 6 if quick else 15), replace=False)]
    side = sidebar_region() if not bpy.app.background else None
    # select a part
    active_was = vl.objects.active
    sel_was = [o for o in scene.objects if o.select_get()]
    ts = []
    with HandlerTimer() as ht:
        for ob in pick:
            for o in sel_was:
                o.select_set(False)
            t0 = now()
            ob.select_set(True)
            vl.objects.active = ob
            dg.update()
            if side is not None:
                redraw(*side, "DRAW", 1)
            ts.append(now() - t0)
            ob.select_set(False)
        sel_h = {k: 1000.0 * v / len(pick) for k, v in ht.t.items()}
    vl.objects.active = active_was
    for o in sel_was:
        o.select_set(True)
    what = "update + side panel redraw" if side is not None else "update only (no window)"
    r.line(f"select a part: {1000 * np.median(ts):.0f} ms median, {1000 * max(ts):.0f} ms worst ({len(ts)} parts; "
           f"{what})")
    r.action_costs.append(("select a part (worst)", max(ts)))
    r.data["select_ms"] = [round(1000 * x, 1) for x in ts]
    r.data["select_handlers_ms"] = {k: round(v, 2) for k, v in sel_h.items()}
    for k, v in sorted(sel_h.items(), key=lambda kv: -kv[1])[:4]:
        if v >= 1.0:
            r.line(f"  {v:7.1f} ms of it in {k}")
    # hover of the axis pickers (one mouse move = one ray)
    try:
        hover = app("blender.hover")
        cam = scene.camera
        eye = cam.matrix_world.translation if cam is not None else Vector((0, -80, 30))
        first, rest = [], []
        for ob in pick:
            c = ob.matrix_world @ (sum((Vector(b) for b in ob.bound_box), Vector()) / 8.0)
            d = (c - eye).normalized()
            h = hover.look(scene, dg, eye, d)
            first.append(h.ms)
            h = hover.look(scene, dg, eye, d)
            rest.append(h.ms)
        r.line(f"hover (Add joint's picker, one mouse move): first time on a part {np.median(first):.1f} ms median, "
               f"{max(first):.0f} ms worst; again {np.median(rest):.1f} ms")
        r.data["hover_ms"] = {"first": [round(x, 1) for x in first], "again": [round(x, 1) for x in rest]}
        r.action_costs.append(("hover, first mouse move over a part (worst)", max(first) / 1000.0))
    except Exception as exc:  # noqa: BLE001
        r.line(f"hover: not measured ({exc})")
    # a joint moved live (as the slider in 4 Motion does)
    try:
        joints = app("blender.joints")
        js = [j for j in scene.fresing.joints if j.frame is not None]
        js = [js[i] for i in rng.choice(len(js), size=min(len(js), 4 if quick else 10), replace=False)] if js else []
        rows = []
        ht = HandlerTimer().__enter__()
        for j in js:
            v0 = joints.get_value(j)
            step = 2.0 if j.kind in ("ROTATE", "REVOLUTE", "TURN") else 0.01
            t0 = now()
            for k in range(1, 6):
                joints.set_value(j, v0 + step * k)
                dg.update()
            rows.append((1000.0 * (now() - t0) / 5, j.name))
            joints.set_value(j, v0)
            dg.update()
        ht.__exit__()
        joint_h = {k: 1000.0 * v / max(1, 6 * len(js)) for k, v in ht.t.items()}
        r.data["joint_live_handlers_ms"] = {k: round(v, 2) for k, v in joint_h.items()}
        if rows:
            ms = [x for x, _n in rows]
            r.line(f"a joint moved live: {np.median(ms):.1f} ms a step median, {max(ms):.0f} ms worst "
                   f"('{max(rows)[1]}'; {len(rows)} joints x 5 steps; update only)")
            r.data["joint_live_ms"] = sorted(((round(x, 1), n) for x, n in rows), reverse=True)
            r.action_costs.append(("a joint moved live, one step (worst)", max(ms) / 1000.0))
            for k, v in sorted(joint_h.items(), key=lambda kv: -kv[1])[:3]:
                if v >= 0.5:
                    r.line(f"  {v:7.1f} ms a step of it in {k}")
    except Exception as exc:  # noqa: BLE001
        r.line(f"joint live: not measured ({exc})")
    # light look and sea state (the scene's surroundings are made again)
    s = scene.fresing
    try:
        studio = app("core.studio")
        world = app("blender.world")
        keys = set()
        for lk in studio.LOOKS:
            try:
                keys |= set(studio.look_settings(lk, s.background))
            except Exception:  # noqa: BLE001
                pass
        was = {k: (tuple(getattr(s, k)) if hasattr(getattr(s, k), "__len__") and not isinstance(getattr(s, k), str)
                   else getattr(s, k)) for k in keys if hasattr(s, k)}
        t0 = now()
        with bpy.context.temp_override(scene=scene):
            bpy.ops.fresing.light_look(look="OVERCAST")
        dg.update()
        look_s = now() - t0
        live = s.live_update
        s.live_update = False
        for k, v in was.items():
            setattr(s, k, v)
        s.live_update = live
        t0 = now()
        world.apply(scene, s)
        dg.update()
        back_s = now() - t0
        r.line(f"light look Overcast: {look_s:.2f} s; back to the project's: {back_s:.2f} s")
        r.action_costs.append(("light look", look_s))
        r.data["light_look_s"] = [round(look_s, 2), round(back_s, 2)]
    except Exception as exc:  # noqa: BLE001
        r.line(f"light look: not measured ({exc})")
    try:
        if s.sea_state:
            # The built cables / hoses are worked out again for the new sea (in the window: a long job afterwards,
            # with progress and Cancel). That re-bake is measured by task 0192; here it is left out for a moment,
            # so the number is the sea itself.
            fx, pa = app("blender.flex"), app("blender.paths")
            saved = (fx.motion_changed, pa.motion_changed)
            asked = []
            fx.motion_changed = lambda *a, **k: asked.append("hoses")
            pa.motion_changed = lambda *a, **k: asked.append("cables")
            try:
                was = s.sea_state
                other = "ROUGH" if was != "ROUGH" else "CALM"
                t0 = now()
                s.sea_state = other
                dg.update()
                t1 = now() - t0
                t0 = now()
                s.sea_state = was
                dg.update()
                t2 = now() - t0
            finally:
                fx.motion_changed, pa.motion_changed = saved
            rb = (" the check for a re-bake of the built cables and hoses, and any re-bake, left out: task 0192 "
                  "measures it") if asked else " no re-bake asked"
            r.line(f"sea state {other.title()}: {t1:.2f} s; back: {t2:.2f} s (the sea made again;{rb})")
            r.action_costs.append(("sea state (without the re-bake)", t1))
            r.data["sea_state_s"] = [round(t1, 2), round(t2, 2), sorted(set(asked))]
    except Exception as exc:  # noqa: BLE001
        r.line(f"sea state: not measured ({exc})")
    # saving
    try:
        path = os.path.join(tempfile.gettempdir(), "fresing_measure_copy.blend")
        t0 = now()
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, check_existing=False)
        save_s = now() - t0
        mb = os.path.getsize(path) / 1e6
        os.remove(path)
        r.line(f"save a copy: {save_s:.1f} s, {mb:.0f} MB (compressed: "
               f"{bpy.context.preferences.filepaths.use_file_compression})")
        r.action_costs.append(("save", save_s))
        r.data["save"] = {"s": round(save_s, 2), "mb": round(mb, 1)}
    except Exception as exc:  # noqa: BLE001
        r.line(f"save: not measured ({exc})")


# --------------------------------------------------------------------------------------------------------------------
# memory
# --------------------------------------------------------------------------------------------------------------------


def memory(r: Result, scene):
    import bpy
    where = top_collection(scene)
    r.line(f"this Blender uses {rss_mb():.0f} MB now")
    by_coll = defaultdict(float)
    by_mesh = []
    done = set()
    for ob in scene.objects:
        if ob.type != "MESH" or ob.data is None or ob.data.name in done:
            continue
        done.add(ob.data.name)
        b = mesh_bytes(ob.data)
        by_coll[where.get(ob.name, "(other)")] += b
        by_mesh.append((b, ob.data.name))
    other = 0
    for me in bpy.data.meshes:
        if me.name not in done:
            b = mesh_bytes(me)
            other += b
            by_mesh.append((b, me.name))
    tot = sum(by_coll.values()) + other
    r.line(f"mesh data {tot / 1048576:.0f} MB (positions, corners, faces, attributes; not Blender's draw caches)")
    for g, b in sorted(by_coll.items(), key=lambda kv: -kv[1])[:8]:
        r.line(f"  {b / 1048576:7.1f} MB  {g}")
    if other:
        r.line(f"  {other / 1048576:7.1f} MB  meshes on no object in this scene")
    r.line("  biggest meshes: " + "; ".join(f"{plain(n)} {b / 1048576:.1f} MB" for b, n in sorted(by_mesh,
                                                                                                    reverse=True)[:6]))
    idp = 0
    idkeys = defaultdict(int)
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.scenes, bpy.data.materials):
        for idb in coll:
            b, ks = idprop_bytes(idb)
            idp += b
            for k, kb in ks:
                idkeys[k] += kb
    r.line(f"ID-property arrays {idp / 1048576:.1f} MB: " + ", ".join(
        f"{k} {b / 1048576:.1f}" for k, b in sorted(idkeys.items(), key=lambda kv: -kv[1])[:6]))
    r.data["memory"] = {"rss_mb": round(rss_mb()), "mesh_mb": round(tot / 1048576, 1),
                        "mesh_by_collection_mb": {k: round(v / 1048576, 2) for k, v in by_coll.items()},
                        "biggest_meshes": [(n, round(b / 1048576, 2)) for b, n in sorted(by_mesh, reverse=True)[:25]],
                        "idprops_mb": round(idp / 1048576, 2),
                        "idprop_keys_mb": {k: round(v / 1048576, 2) for k, v in idkeys.items() if v > 1e5}}


# --------------------------------------------------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------------------------------------------------


def header(r: Result, scene):
    import bpy
    try:
        ver = sys.modules[app_pkg()].__dict__.get("__version__", "?")
    except Exception:  # noqa: BLE001
        ver = "?"
    path = bpy.data.filepath
    r.lines.append(f"# Fresing measure v{VERSION}{' (quick)' if QUICK else ''} – {time.strftime('%Y-%m-%d %H:%M')}")
    r.lines.append(f"app {ver}, Blender {bpy.app.version_string}, {platform.system()} {platform.release()}, "
                   f"{os.cpu_count()} logical cores, {'no window' if bpy.app.background else 'window'}")
    try:
        r.lines.append(f"processor: {platform.processor() or platform.machine()}")
    except Exception:  # noqa: BLE001
        pass
    r.lines.append(f"project: {os.path.basename(path)} ({os.path.getsize(path) / 1e6:.0f} MB on disk)"
                   if path and os.path.isfile(path) else "project: (not saved)")
    r.data["header"] = list(r.lines)


def default_text_path() -> str:
    import bpy
    return os.path.splitext(bpy.data.filepath)[0] + " - measure.txt" if bpy.data.filepath else ""


def run(quick: bool = False, text_path: str = "") -> Result:
    """All sections on the current project (the app: inside a window's context; ``reopen`` afterwards)."""
    import bpy
    global QUICK
    QUICK = quick or QUICK
    scene = bpy.context.scene
    r = Result()
    r.save_to = text_path or default_text_path()
    header(r, scene)
    t_all = now()
    if not hasattr(scene, "fresing"):
        r.line("Fresing Render is not switched on in this Blender")
        return r
    a = scene.fresing
    r.lines.append(f"animation frames {scene.frame_start}–{scene.frame_end}; joints {len(a.joints)}; "
                   f"cables {len(getattr(a, 'cables', []))}; spools {len(getattr(a, 'spools', []))}; "
                   f"tracks {len(getattr(a, 'tracks', []))}; built: "
                   f"{any(getattr(x, 'built', False) for x in getattr(a, 'animations', []))}")
    r.data["rss_start_mb"] = round(rss_mb())
    r.section("Make-up", makeup, scene)
    r.section("Per frame (no drawing)", per_frame, scene, QUICK)
    if not bpy.app.background:
        r.section("Drawing (this PC's graphics card)", drawing, scene, QUICK)
        r.section("Side panel", panels, scene, QUICK)
    r.section("Actions", actions, scene, QUICK)
    r.section("Memory", memory, scene)
    if not bpy.app.background:
        r.section("Undo", undo, bpy.context.scene, QUICK)
        r.section("Drawing in Material Preview", drawing_material, bpy.context.scene, QUICK)
    r.data["total_s"] = round(now() - t_all, 1)
    r.line(f"(measuring took {r.data['total_s']:.0f} s)")
    return r


def reopen(r: Result):
    """Open the saved project again (puts back everything this tool changed); the time it takes is measured."""
    import bpy
    path = bpy.data.filepath
    if not path:
        return
    r.head("Open")
    try:
        t0 = now()
        bpy.ops.wm.open_mainfile(filepath=path)
        s_open = now() - t0
        r.line(f"open the project again (puts back everything this tool changed): {s_open:.1f} s; "
               f"Blender uses {rss_mb():.0f} MB after it")
        r.action_costs.append(("open the project", s_open))
        r.data["open_s"] = round(s_open, 2)
    except Exception as exc:  # noqa: BLE001
        r.line(f"FAILED: {exc} - close Blender WITHOUT saving")


def publish(r: Result, text_path: str = "", json_path: str = ""):
    import bpy
    text = r.text()
    txt = bpy.data.texts.get(TEXT_NAME) or bpy.data.texts.new(TEXT_NAME)
    txt.from_string(text)
    text_path = text_path or r.save_to or default_text_path()
    if text_path:
        with open(text_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    if json_path:
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(r.data, fh, indent=1, default=str)
    if not bpy.app.background:                           # show it in the Scripting tab's text editor
        try:
            ws = bpy.data.workspaces.get("Scripting")
            for win in bpy.context.window_manager.windows:
                if ws is not None:
                    win.workspace = ws
                for scr in ([*ws.screens] if ws is not None else []) + [win.screen]:
                    for area in scr.areas:
                        if area.type == "TEXT_EDITOR":
                            area.spaces.active.text = txt
                            area.tag_redraw()
        except Exception:  # noqa: BLE001 - the text is also in the file next to the project
            pass
    print(text, flush=True)
    return text


def args_after_dashes(argv):
    return argv[argv.index("--") + 1:] if "--" in argv else []


def main_module(argv) -> int:
    """Blender as a Python module (this repository's app)."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--text", default="")
    a = ap.parse_args(argv)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    import bpy  # noqa: I001
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    t0 = now()
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.project))
    s_open = now() - t0
    r = run(quick=a.quick, text_path=a.text)
    r.action_costs.append(("open the project (no window)", s_open))
    r.lines.insert(len(r.data["header"]), f"opened in {s_open:.1f} s (no window)")
    publish(r, a.text, a.out)
    fresing_render.unregister()
    return 0


def main_app():
    """Inside Blender (Run Script, or --python at start-up)."""
    import bpy
    opts = args_after_dashes(sys.argv)
    quick = "--quick" in opts
    out = opts[opts.index("--out") + 1] if "--out" in opts else ""
    text = opts[opts.index("--text") + 1] if "--text" in opts else ""
    quit_after = "--quit" in opts
    if bpy.data.is_dirty and bpy.data.filepath and "--force" not in opts:
        msg = "Save your project first (Ctrl+S), then Run Script again: this tool opens the saved project at the end."
        print(msg)
        try:
            bpy.context.window_manager.popup_menu(lambda self, _c: self.layout.label(text=msg), title="Fresing measure",
                                                  icon="ERROR")
        except Exception:  # noqa: BLE001
            pass
        return

    def steps():
        show_sidebar()                                   # the window gives the side panel its size …
        yield 0.5
        try:
            prepare_panels(quick)                        # … then the panels' copies go in and are laid out once
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        yield 0.5
        r = None
        try:
            v = view3d()
            if v is None:
                r = run(quick=quick, text_path=text)
            else:
                win, area, region = v
                with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                    r = run(quick=quick, text_path=text)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        finally:
            drop_panels()
        if r is not None:
            reopen(r)                                    # outside the window's context: the file's screens change
            try:
                publish(r, text, out)
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        if quit_after:
            bpy.ops.wm.quit_blender()
    gen = steps()

    def tick():
        try:
            return next(gen)
        except StopIteration:
            return None
    # always from a timer: Run Script finishes first (opening the project again frees this script's text)
    bpy.app.timers.register(tick, first_interval=1.0 if bpy.context.window is not None else 3.0, persistent=True)


def _in_blender_exe() -> bool:
    try:
        import bpy
        return bool(bpy.app.binary_path) and not bpy.app.binary_path.endswith(("python", "python3", "python.exe"))
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    if "bpy" in sys.modules and _in_blender_exe():
        main_app()
    else:
        sys.exit(main_module(sys.argv[1:]))
