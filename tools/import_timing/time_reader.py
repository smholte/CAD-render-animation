"""The STEP reader's stages, timed one by one (task 0301). No Blender; run with the venv's Python.

    python tools/import_timing/time_reader.py model.step out_dir [--helpers N] [--quality normal]
           [--no-occ-parallel] [--json result.json]

Runs the same steps as ``importer/step_reader._read_step`` (same functions, same order, same cache) with a clock
round each one, plus: CPU seconds of the reader and of its helpers, each helper's time per part (read the part's
binary copy, mesh it, make the arrays), the biggest part's time (the floor with many cores) and how busy the helpers
were. ``--helpers 0`` meshes in the reader itself (OpenCascade may still use several threads inside one part);
``--helpers 1`` is allowed here (the app needs 2 or more). ``--no-occ-parallel``: BRepMesh without its own threads.
The cache it writes is the app's (tree.json + meshes.npz), so the Blender build can be timed from it.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from fresing_render.importer import step_reader as sr  # noqa: E402
from fresing_render.importer import step_meta  # noqa: E402
from fresing_render.core import cad_materials  # noqa: E402

WORKER = os.path.join(HERE, "time_worker.py")


class Helpers(sr._Helpers):
    """The app's helper pool, started with time_worker.py (the same loop, plus a clock per part)."""

    def __init__(self, n: int, occ_parallel: bool):
        import subprocess
        self.procs = []
        self.started = 0
        self._job = None
        env = dict(os.environ)
        env["FR_TIMING_OCC_PARALLEL"] = "1" if occ_parallel else "0"
        cmd = [sys.executable, WORKER, "--worker", str(os.getpid())]
        for _ in range(n):
            self.procs.append(subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env,
                                               preexec_fn=sr._die_with_parent))


def cpu() -> tuple:
    s = resource.getrusage(resource.RUSAGE_SELF)
    c = resource.getrusage(resource.RUSAGE_CHILDREN)
    return s.ru_utime + s.ru_stime, c.ru_utime + c.ru_stime


def patch_occ_parallel(occ_parallel: bool) -> None:
    if occ_parallel:
        return
    real = sr._occ

    def occ():
        d = real()
        mesh = d["BRepMesh_IncrementalMesh"]
        d["BRepMesh_IncrementalMesh"] = lambda shape, defl, rel, ang, _par: mesh(shape, defl, rel, ang, False)
        return d
    sr._occ = occ


def run(path: str, out_dir: str, quality: str = "normal", helpers_n: int = 0, occ_parallel: bool = True) -> dict:
    T: dict = {}
    t_all = time.time()
    patch_occ_parallel(occ_parallel)
    t = time.time()
    helpers = Helpers(helpers_n, occ_parallel) if helpers_n >= 1 else None
    T["helpers_start_call"] = time.time() - t
    try:
        return _run(path, out_dir, quality, helpers, T, t_all)
    finally:
        if helpers is not None:
            helpers.close()


def _run(path, out_dir, quality, helpers, T, t_all) -> dict:
    occ = sr._occ()
    lin_rel, ang = sr.QUALITY[quality]
    facets = sr.FACETS[quality]
    os.makedirs(out_dir, exist_ok=True)

    t = time.time()
    app = occ["XCAFApp_Application"].GetApplication_s()
    doc = occ["TDocStd_Document"](occ["TCollection_ExtendedString"]("XmlXCAF"))
    app.InitDocument(doc)
    reader = occ["STEPCAFControl_Reader"]()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(False)
    reader.SetPropsMode(False)
    if reader.ReadFile(path) != occ["IFSelect_RetDone"]:
        raise RuntimeError("read failed")
    T["read_parse"] = time.time() - t
    t = time.time()
    if not reader.Transfer(doc):
        raise RuntimeError("transfer failed")
    T["transfer"] = time.time() - t

    t = time.time()
    face_looks: dict = {}
    cad_meta = step_meta.read(path, faces=face_looks)
    T["material_names"] = time.time() - t

    t = time.time()
    stool = occ["XCAFDoc_DocumentTool"].ShapeTool_s(doc.Main())
    ctool = occ["XCAFDoc_DocumentTool"].ColorTool_s(doc.Main())
    nodes, mesh_index, mesh_labels, mesh_names = [], {}, [], []

    def add_node(label, parent, trsf, inst_label, counts):
        own = sr._label_name(occ, label)
        name = own or (sr._label_name(occ, inst_label) if inst_label is not None else "") or "Unnamed"
        counts[name] = counts.get(name, 0) + 1
        puid = nodes[parent]["uid"] if parent >= 0 else ""
        node = {"uid": f"{puid}/{name}#{counts[name]}" if puid else f"{name}#{counts[name]}", "name": name,
                "instance": sr._instance_name(occ, inst_label), "parent": parent,
                "matrix": sr._trsf_to_matrix(trsf) if trsf is not None else None, "kind": "assembly", "mesh": -1,
                "color": None}
        meta = cad_meta.get(own.strip()) if cad_meta and own else None
        if meta:
            look = cad_materials.pick(meta["appearance"], meta["material"])
            if look:
                node["material"] = look
        idx = len(nodes)
        nodes.append(node)
        col = sr._color_of(occ, ctool, inst_label) if inst_label is not None else None
        node["color"] = col or sr._color_of(occ, ctool, label)
        node["inherited_color"] = node["color"] or (nodes[parent].get("inherited_color") if parent >= 0 else None)
        if occ["XCAFDoc_ShapeTool"].IsAssembly_s(label):
            comps = occ["Sequence_TDF_Label"]()
            occ["XCAFDoc_ShapeTool"].GetComponents_s(label, comps, False)
            c2: dict = {}
            for i in range(1, comps.Length() + 1):
                comp = comps.Value(i)
                ref = occ["TDF_Label"]()
                if not occ["XCAFDoc_ShapeTool"].GetReferredShape_s(comp, ref):
                    continue
                add_node(ref, idx, occ["XCAFDoc_ShapeTool"].GetLocation_s(comp).Transformation(), comp, c2)
        else:
            node["kind"] = "part"
            entry = sr._label_entry(occ, label)
            if entry not in mesh_index:
                mesh_index[entry] = len(mesh_labels)
                mesh_labels.append(label)
                mesh_names.append(name)
            node["mesh"] = mesh_index[entry]

    free = occ["Sequence_TDF_Label"]()
    stool.GetFreeShapes(free)
    rc: dict = {}
    for i in range(1, free.Length() + 1):
        lab = free.Value(i)
        add_node(lab, -1, occ["XCAFDoc_ShapeTool"].GetLocation_s(lab).Transformation(), None, rc)
    T["tree"] = time.time() - t

    t = time.time()
    shapes = [occ["XCAFDoc_ShapeTool"].GetShape_s(lab) for lab in mesh_labels]
    face_colours = [sr._face_colour_list(occ, shapes[m], sr._face_colors(occ, stool, ctool, lab))
                    for m, lab in enumerate(mesh_labels)]
    standard = [sr.is_standard_part(mesh_names[m]) for m in range(len(mesh_labels))]
    T["face_colours"] = time.time() - t

    results = [None] * len(mesh_labels)
    per_part: list = []

    def store(reply):
        results[reply[0]] = reply

    t_mesh = time.time()
    pending = list(range(len(mesh_labels)))
    used = 0
    if helpers is not None:
        t = time.time()
        jobs = [[m, sr._part_blob(occ, shapes[m]), face_colours[m], lin_rel, ang, facets, standard[m]]
                for m in range(len(shapes))]
        T["copy_out"] = time.time() - t
        T["copy_bytes_mb"] = sum(len(j[1]) for j in jobs) / 1e6
        jobs.sort(key=lambda j: -len(j[1]))

        def got(reply):
            store(reply)
            if len(reply) > 6:
                per_part.append(reply[6])
        lost, left = helpers.run(jobs, got)
        used = helpers.started
        pending = sorted([j[0] for j in left] + [m for m, _ in lost])
        T["mesh_helpers_wall"] = time.time() - t_mesh - T["copy_out"]
    t = time.time()
    for m in pending:
        t1 = time.time()
        axes = sr._Axes()
        starts: list = []
        res = sr._mesh_shape(occ, shapes[m], lin_rel, ang, face_colours[m], axes=axes, face_starts=starts,
                             facets=facets, standard=standard[m])
        store((m, res, axes.axes, axes.faces, None, starts))
        per_part.append({"mid": m, "total": time.time() - t1})
    T["mesh_here"] = time.time() - t
    T["mesh_stage"] = time.time() - t_mesh

    t = time.time()
    arrays, metas, tri_total = {}, [], 0
    for m in range(len(mesh_labels)):
        res = results[m][1]
        if res is None:
            metas.append({"name": mesh_names[m], "tris": 0, "palette": [], "bbox": None, "axes": [],
                          "axis_faces": []})
            continue
        pos, nrm, tri, tcol, pal = res
        arrays[f"p{m}"], arrays[f"n{m}"], arrays[f"t{m}"] = pos, nrm, tri
        if pal:
            arrays[f"c{m}"] = tcol
        st = results[m][5]
        if len(st) >= 2 and st[-1] == len(tri):
            arrays[f"f{m}"] = sr.np.asarray(st, dtype=sr.np.int32)
        metas.append({"name": mesh_names[m], "tris": int(len(tri)), "palette": pal,
                      "bbox": [pos.min(axis=0).tolist(), pos.max(axis=0).tolist()], "axes": results[m][2],
                      "axis_faces": results[m][3]})
        tri_total += len(tri)
    for n in nodes:
        if n["kind"] == "part" and n["color"] is None:
            n["color"] = n.get("inherited_color")
        n.pop("inherited_color", None)
    T["collect"] = time.time() - t

    t = time.time()
    sr.np.savez(os.path.join(out_dir, "meshes.npz"), **arrays)
    T["write_npz"] = time.time() - t
    t = time.time()
    info = {"version": sr.CACHE_VERSION, "source": os.path.abspath(path), "source_size": os.path.getsize(path),
            "source_mtime": os.path.getmtime(path), "quality": quality, "units": "m", "nodes": nodes,
            "meshes": metas, "stats": {}}
    with open(os.path.join(out_dir, "tree.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    T["write_json"] = time.time() - t
    T["total"] = time.time() - t_all

    busy = sum(p.get("total", 0.0) for p in per_part)
    biggest = max(per_part, key=lambda p: p.get("total", 0.0)) if per_part else {}
    for key in ("bin_read", "mesh", "arrays"):
        T["helper_sum_" + key] = sum(p.get(key, 0.0) for p in per_part)
    T["part_seconds_sum"] = busy
    T["biggest_part_s"] = biggest.get("total", 0.0)
    T["biggest_part_name"] = mesh_names[biggest["mid"]] if biggest else ""
    T["helpers"] = used
    T["unique"] = len(mesh_labels)
    T["placed"] = sum(1 for n in nodes if n["kind"] == "part")
    T["nodes"] = len(nodes)
    T["triangles_unique"] = int(tri_total)
    T["file_mb"] = os.path.getsize(path) / 1e6
    T["npz_mb"] = os.path.getsize(os.path.join(out_dir, "meshes.npz")) / 1e6
    T["json_mb"] = os.path.getsize(os.path.join(out_dir, "tree.json")) / 1e6
    T["cpu_reader_s"], T["cpu_helpers_s"] = cpu()
    T["peak_rss_reader_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return T


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("out_dir")
    ap.add_argument("--helpers", type=int, default=0)
    ap.add_argument("--quality", default="normal")
    ap.add_argument("--no-occ-parallel", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    T = run(a.step, a.out_dir, a.quality, a.helpers, not a.no_occ_parallel)
    T.update(model=os.path.basename(a.step), quality=a.quality, occ_parallel=not a.no_occ_parallel,
             helpers_asked=a.helpers)
    txt = json.dumps(T, indent=1, default=float)
    if a.json:
        with open(a.json, "w") as fh:
            fh.write(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
