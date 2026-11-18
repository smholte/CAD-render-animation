"""Helper of the crane tests (task 0191, not a test file): a built-in crane class imported with the app's importer and
rigged from its equipment file – the joints, cylinders and poses through the app's sheet reader
(``fresing_render/blender/sheet.py``, task 0201; before it the render kit's copy), the crawler tracks through the app's tracks (``blender/tracks.py``) – and what the
tests compare: where every moving sub-assembly is against the maker's own kinematics (``lifting_model/classes.py``).

Blender as a Python module. ``rigged(name)`` makes a fresh scene each time.
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")
for _p in (ROOT, KIT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def app():
    import bpy  # noqa: F401
    import fresing_render
    if not hasattr(bpy.types.Scene, "fresing"):
        fresing_render.register()
    return fresing_render


def data_of(name: str, folder: str = BUILTIN) -> dict:
    with open(os.path.join(folder, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def sheet_of(data: dict) -> dict:
    """The render-kit sheet of an equipment file's rig."""
    r = data["rig"]
    return {"model": data["class"], "step": r["step"], "joints": r["joints"], "cylinders": r["cylinders"],
            "poses": r["poses"], "start_pose": r["start_pose"]}


class Rigged:
    """A class imported and rigged in the current scene."""

    def __init__(self, name: str, folder: str = BUILTIN, quality: str = "draft", out: str = "", tracks: bool = True,
                 cls=None):
        import bpy
        from fresing_render.lifting_model import classes as C
        import make_site_pictures as kit
        from fresing_render.blender import sheet as projects
        self.pkg = app()
        self.name = name
        self.data = data_of(name, folder)
        self.layout = C.layout(cls if cls is not None else name)       # cls: a made crane's dataclass (task 0204)
        self.C = C
        self.projects = projects
        step = os.path.join(folder, name, f"{name}.step")
        if not out:
            import tempfile
            out = tempfile.mkdtemp(prefix="fr_lifting_")
        self.scene = kit.fresh_import(self.pkg, step, quality, "Z", out)
        self.sheet = sheet_of(self.data)
        m = projects.Model(self.scene, self.sheet)
        self.m = m
        self.n_joints = projects.make_joints(self.scene, m)
        self.axis_error = projects.axis_errors(self.scene, m)
        self.n_cylinders = projects.make_cylinders(self.scene, m)
        self.set({})
        # every jointed sub-assembly's CAD world matrix (all joints 0)
        self.cad = {j["name"]: [np.array(m.one(p).matrix_world) for p in j["parts"]] for j in self.sheet["joints"]}
        self.cyl_cad = {c["name"]: (np.array(m.one(c["barrel"][0]).matrix_world),
                                    np.array(m.one(c["rod"][0]).matrix_world)) for c in self.sheet["cylinders"]}
        self.tracks = []
        if tracks and self.data["rig"].get("tracks"):
            self.add_tracks()
            self.set({})
        self.n_poses = projects.make_poses(self.scene, m)
        self.set({})
        bpy.context.view_layer.update()

    # -- the app's side ------------------------------------------------------------------------------------------
    def set(self, values: dict) -> None:
        """Joint values as the sheet writes them (deg, mm); the rest 0. Updates twice (drivers, constraints)."""
        import bpy
        self.projects.set_values(self.scene, values)
        from fresing_render.blender import cylinders
        cylinders.refresh_all(self.scene) if hasattr(cylinders, "refresh_all") else None
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()

    def add_tracks(self) -> None:
        from fresing_render.blender import tracks
        for t in self.data["rig"]["tracks"]:
            wheels = [self.part(w) for w in t["wheels"]]
            it = tracks.add(self.scene, wheels, self.part(t["link"]), [self.part(r) for r in t["riders"]],
                            joint=t["joint"], name=t["name"])
            self.tracks.append(it.name)

    def part(self, name: str):
        """The first object of that CAD name (a part placed many times: any copy)."""
        hits = self.m.by_name.get(name, [])
        if not hits:
            raise KeyError(name)
        return hits[0]

    def scale(self) -> float:
        """Scene units per mm."""
        return float(np.linalg.norm(np.array(self.m.root.matrix_world)[:3, 0])) / 1000.0

    def world(self, p_mm) -> np.ndarray:
        return np.array(self.m.point(p_mm))

    # -- comparisons ---------------------------------------------------------------------------------------------
    def expected(self, values: dict) -> dict:
        """Joint -> expected world matrix of each of its sub-assemblies (the maker's kinematics)."""
        mot = self.C.motions(self.layout, values)
        R = np.array(self.m.root.matrix_world)
        Ri = np.linalg.inv(R)
        S = np.diag([1000.0, 1000.0, 1000.0, 1.0])            # scene m -> sheet mm inside the root's frame
        out = {}
        for jn, cads in self.cad.items():
            Mw = R @ np.linalg.inv(S) @ mot[jn] @ S @ Ri
            out[jn] = [Mw @ c for c in cads]
        return out

    def worst(self, values: dict) -> tuple[float, float, str]:
        """(largest offset in mm, largest angle in degrees, joint) between where the app put every jointed
        sub-assembly and where the maker's kinematics says it is."""
        self.set(values)
        exp = self.expected(values)
        s = self.scale()
        worst = (0.0, 0.0, "")
        for jn, mats in exp.items():
            j = next(x for x in self.sheet["joints"] if x["name"] == jn)
            for M, pname in zip(mats, j["parts"]):
                A = np.array(self.m.one(pname).matrix_world)
                d = float(np.linalg.norm(A[:3, 3] - M[:3, 3])) / s
                Ra = A[:3, :3] / np.linalg.norm(A[:3, :3], axis=0)
                Rb = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
                c = (np.trace(Ra.T @ Rb) - 1.0) / 2.0
                ang = math.degrees(math.acos(max(-1.0, min(1.0, c))))
                if d > worst[0] or ang > worst[1]:
                    worst = (max(worst[0], d), max(worst[1], ang), jn)
        return worst

    def hook_world_mm(self) -> np.ndarray:
        """The hook point now, in the sheet's mm (model frame)."""
        jn = "Hoist"
        A = np.array(self.m.one(self.data["rig"]["hook"]["assembly"]).matrix_world)
        C0 = self.cad[jn][0]
        p = A @ np.linalg.inv(C0) @ np.r_[self.world(self.data["rig"]["hook"]["point"]), 1.0]
        R = np.array(self.m.root.matrix_world)
        return (np.linalg.inv(R) @ p)[:3] * 1000.0

    def cylinder_state(self, name: str) -> dict:
        """Pin to pin length (mm) and the angle (deg) between the barrel's and the rod's axes, from the parts'
        world matrices against their CAD ones."""
        c = next(x for x in self.sheet["cylinders"] if x["name"] == name)
        Bc, Rc = self.cyl_cad[name]
        B = np.array(self.m.one(c["barrel"][0]).matrix_world)
        Rm = np.array(self.m.one(c["rod"][0]).matrix_world)
        bp = B @ np.linalg.inv(Bc) @ np.r_[self.world(c["barrel_pin"]["point"]), 1.0]
        rp = Rm @ np.linalg.inv(Rc) @ np.r_[self.world(c["rod_pin"]["point"]), 1.0]
        ax_b = (B @ np.linalg.inv(Bc))[:3, :3] @ (self.world(c["rod_pin"]["point"]) -
                                                 self.world(c["barrel_pin"]["point"]))
        ax_r = (Rm @ np.linalg.inv(Rc))[:3, :3] @ (self.world(c["rod_pin"]["point"]) -
                                                  self.world(c["barrel_pin"]["point"]))
        cosang = float(ax_b @ ax_r / np.linalg.norm(ax_b) / np.linalg.norm(ax_r))
        along = (rp - bp)[:3]
        cos2 = float(along @ ax_b / np.linalg.norm(along) / np.linalg.norm(ax_b))
        return {"length": float(np.linalg.norm(along)) / self.scale(),
                "bend": math.degrees(math.acos(max(-1.0, min(1.0, cosang)))),
                "off_axis": math.degrees(math.acos(max(-1.0, min(1.0, cos2))))}


def driven(sheet: dict) -> list:
    """The joints a user drives (not followers), with their limits."""
    return [j for j in sheet["joints"] if not j.get("follows") and j.get("limits")]


def sweep_values(sheet: dict, steps: int = 4):
    """Each driven joint alone from its minimum to its maximum (the others 0): (joint, values) pairs."""
    for j in driven(sheet):
        lo, hi = j["limits"]
        for k in range(steps + 1):
            yield j["name"], {j["name"]: lo + (hi - lo) * k / steps}


def random_poses(sheet: dict, n: int, seed: int = 1):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        yield {j["name"]: float(rng.uniform(*j["limits"])) for j in driven(sheet)}


# ---------------------------------------------------------------------------------------------------------------------
# What the in-app tests measure (tests/test_lifting_cranes_<kind>.py)

def evaluated_points(ob) -> np.ndarray:
    """The object's evaluated vertices in world space (a track part's or a cable's geometry moved by its modifier)."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    e = ob.evaluated_get(dg)
    me = e.to_mesh()
    v = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    M = np.array(e.matrix_world)
    e.to_mesh_clear()
    v = v.reshape(-1, 3)
    return v @ M[:3, :3].T + M[:3, 3]


def measure(r: Rigged, steps: int = 4, randoms: int = 3) -> dict:
    """Every driven joint from its minimum to its maximum, then a few random poses with all of them: the worst
    offset / angle of any jointed sub-assembly against the maker's kinematics, and of every cylinder its pin to pin
    length (mm) against its range and how far its rod bends off its barrel's axis (deg)."""
    fits = {c["name"]: c["fit"] for c in r.layout.cylinders}
    out = {"offset_mm": 0.0, "angle_deg": 0.0, "where": "", "cyl_out_mm": 0.0, "cyl_bend_deg": 0.0, "poses": 0}

    def look(label, vals):
        d, a, jn = r.worst(vals)
        if d > out["offset_mm"] or a > out["angle_deg"]:
            out["where"] = f"{label}: {jn}"
        out["offset_mm"], out["angle_deg"] = max(out["offset_mm"], d), max(out["angle_deg"], a)
        for name, f in fits.items():
            st = r.cylinder_state(name)
            beyond = max(0.0, f["dmin"] - st["length"], st["length"] - f["dmax"])
            out["cyl_out_mm"] = max(out["cyl_out_mm"], beyond)
            out["cyl_bend_deg"] = max(out["cyl_bend_deg"], st["bend"], st["off_axis"])
        out["poses"] += 1
    for jn, vals in sweep_values(r.sheet, steps):
        look(jn, vals)
    for k, vals in enumerate(random_poses(r.sheet, randoms)):
        look(f"random {k}", vals)
    return out


def hook_errors(r: Rigged) -> dict:
    """Pose name -> (mm between the app's hook and the maker's, the maker's radius m, height m)."""
    out = {}
    for p in r.sheet["poses"]:
        r.set(p["values"])
        h = r.hook_world_mm()
        e = np.asarray(r.C.hook_point(r.layout, p["values"]))
        rad, z = r.C.hook_radius_height(r.layout, p["values"])
        out[p["name"]] = (float(np.linalg.norm(h - e)), rad, z)
    return out


def pads_lowest_mm(r: Rigged, pose: str = "Set up") -> float:
    """The lowest point of every outrigger / stabiliser pad at a pose, mm above the ground (max over the four)."""
    p = next(x for x in r.sheet["poses"] if x["name"] == pose)
    r.set(p["values"])
    R = np.linalg.inv(np.array(r.m.root.matrix_world))
    lows = []
    for name, obs in r.m.by_name.items():
        if " PAD " in name and obs[0].type == "MESH":
            pts = evaluated_points(obs[0]) @ R[:3, :3].T + R[:3, 3]
            lows.append(float(pts[:, 2].min()) * 1000.0)
    if len(lows) != 4:
        raise RuntimeError(f"{len(lows)} pads")
    return max(abs(z) for z in lows)


def rope_follows(r: Rigged, values: dict) -> float:
    """The hoist rope made a cable of 4 Motion > Cables and paths (end on the hook block), then posed: mm between the
    rope's end and where it enters the hook block (moved with the block)."""
    from fresing_render.blender import paths
    sc = r.scene
    cab = r.data["rig"]["cables"][0]
    if paths.find(sc, cab["name"]) is None:
        r.set({})                                  # read in the CAD pose
        it = paths.add_cable(sc, cab["name"])
        paths.read_cad(sc, it, r.part(cab["part"]))
        it = paths.find(sc, cab["name"])
        sh = paths.shape_now(sc, it)
        hb = r.part("HOOK BLOCK")
        c = np.array(hb.matrix_world.translation)
        r.rope_end = "a" if np.linalg.norm(sh[0] - c) < np.linalg.norm(sh[-1] - c) else "b"
        r.rope_cad = (sh[0] if r.rope_end == "a" else sh[-1]).copy()
        r.block_cad = np.array(hb.matrix_world)
        paths.set_end(sc, it, r.rope_end, hb)
    r.set(values)
    paths.refresh(sc, force=True)
    sh = paths.shape_now(sc, paths.find(sc, cab["name"]))
    end = sh[0] if r.rope_end == "a" else sh[-1]
    M = np.array(r.part("HOOK BLOCK").matrix_world) @ np.linalg.inv(r.block_cad)
    want = (M @ np.r_[r.rope_cad, 1.0])[:3]
    return float(np.linalg.norm(end - want)) / r.scale()


def ground_shoe_slip_mm(r: Rigged, travel: float = 1000.0) -> float:
    """Drive ``travel`` mm: how far the three shoes in the middle of each track's ground run moved in the world, mm
    (the crane stands at x = 0 before it drives)."""
    import bpy
    r.set({})
    worst = 0.0
    for side in ("L", "R"):
        shoes = r.m.by_name[f"TRACK SHOE {side}"]
        cen = {o.name: evaluated_points(o).mean(axis=0) for o in shoes}
        zmin = min(c[2] for c in cen.values())
        ground = [n for n in cen if cen[n][2] < zmin + 0.01]          # the ground run …
        low = sorted(ground, key=lambda n: abs(cen[n][0]))[:3]        # … its middle (well clear of the wheels)
        r.set({"Travel": travel})
        for n in low:
            worst = max(worst, float(np.linalg.norm(evaluated_points(bpy.data.objects[n]).mean(axis=0) - cen[n])))
        r.set({})
    return worst / r.scale()


def sweep_animation(r: Rigged, seconds: float = 0.5, fps: int = 24, start: str = "") -> dict:
    """Task 0204: an animation that moves every driven joint alone from 0 to its maximum, back, to its minimum and
    back (followers with it), from the pose ``start`` (the first pose with outriggers set up, else the CAD pose); the
    clash check is run on it (``clash_rows``)."""
    poses = [p["name"] for p in r.sheet["poses"]]
    start = start or next((p for p in ("Set up", "Working") if p in poses), "")
    vals = dict(next((p["values"] for p in r.sheet["poses"] if p["name"] == start), {}))
    steps, t = [], 0.0
    if start:
        steps.append({"kind": "POSE", "pose": start, "start": 0.0, "seconds": 0.0})
    skip = {"Outriggers", "Jacks", "Stabilisers", "Legs", "Travel"}      # set by the pose (pads on the ground)
    for j in driven(r.sheet):
        if j["name"] in skip:
            continue
        lo, hi = j["limits"]
        here = float(vals.get(j["name"], 0.0))
        for to in (hi, here, lo, here):
            if abs(to - here) < 1e-9 and to != here:
                continue
            steps.append({"kind": "JOINT", "joint": j["name"], "to": float(to), "start": t, "seconds": seconds,
                          "easing": "LINEAR"})
            t += seconds
    return {"name": "Sweep", "fps": fps, "steps": steps}


def pose_tour(r: Rigged, seconds: float = 1.5, fps: int = 24) -> dict:
    """Task 0204: the crane's own motion – from its first pose through every named pose of its file and back to the
    first (each a POSE step, every joint moving at once, as the app's Go to pose)."""
    names = [p["name"] for p in r.sheet["poses"]]
    steps = [{"kind": "POSE", "pose": names[0], "start": 0.0, "seconds": 0.0}]
    t = 0.0
    for n in names[1:] + names[:1]:
        steps.append({"kind": "POSE", "pose": n, "start": t, "seconds": seconds, "easing": "LINEAR"})
        t += seconds
    return {"name": "Own motion", "fps": fps, "steps": steps}


def clash_rows(r: Rigged, spec: dict | None = None) -> list:
    """An animation (default: ``pose_tour``) built and checked by the app's clash check, the hoist rope left out (in
    the app it is a cable of 4 Motion > Cables and paths): the clash rows' texts ([] = clean)."""
    import bpy
    from fresing_render.blender import animation, clash, logic
    from fresing_render.core import clash as core
    logic.exclude(r.m.by_name.get("HOIST ROPE", []))
    spec = spec or pose_tour(r)
    a = r.projects.make_animation(r.scene, r.m, spec)
    animation.bake(r.scene, a)
    rows = clash.check(r.scene, store=False).rows
    bpy.context.scene.frame_set(r.scene.frame_start)
    # a cylinder's own barrel and rod (a pendant's bar and rod) slide in each other: the rod in a bore up to 30 m
    # long, where the clash check's inside test is unsure; ``measure`` checks them instead (in line, in their range)
    own = set()
    for cy in r.sheet["cylinders"]:
        own |= {frozenset((b, rd)) for b in cy["barrel"] for rd in cy["rod"]}
    return [core.row_text(x) for x in rows if x.kind == "CLASH" and frozenset((x.a, x.b)) not in own]


def overlap_changes(r: Rigged, limit_mm: float = 2.0, between=(0.25, 0.5, 0.75)) -> list:
    """Task 0214 (bug hunt 0209 row 17): every pair of the crane's parts that move against each other, measured in
    every pose of its file and ``between`` consecutive poses (the joints in a straight line, as a Go to pose step
    moves them): how deep they are in each other (the clash check's own measure, ``clash.narrow``). The clash check
    reports an overlap that is deeper than at the animation's first moment, so a pair whose depth changes by more than
    ``limit_mm`` gives clash rows in some pose animation. Pin joints (an eye round its pin) keep their depth; a
    cylinder's own barrel and rod and the hoist rope (a cable in the app) are left out. Returns texts ([] = clean)."""
    import bpy
    from fresing_render.blender import build, clash
    poses = [p["name"] for p in r.sheet["poses"]]
    vals = {p["name"]: p["values"] for p in r.sheet["poses"]}
    keys = sorted({k for v in vals.values() for k in v})
    order, at = [], {}
    for a, b in zip(poses, poses[1:] + poses[:1]):
        order.append(a)
        at[a] = {k: float(vals[a].get(k, 0.0)) for k in keys}
        for f in between:
            nm = f"{a} > {b} at {f:g}"
            at[nm] = {k: (1 - f) * float(vals[a].get(k, 0.0)) + f * float(vals[b].get(k, 0.0)) for k in keys}
            order.append(nm)
    own = set()
    for cy in r.sheet["cylinders"]:
        own |= {frozenset((b, rd)) for b in cy["barrel"] for rd in cy["rod"]}
    parts = [o for o in [r.m.root] + list(r.m.root.children_recursive) if o.type == "MESH"
             and o.get(build.PROP_KIND) == "part" and "ROPE" not in str(o.get(build.PROP_NAME, "")).upper()]
    meshes = {o.name: clash._mesh_from(o.data) for o in parts}
    names = [o.name for o in parts]
    label = {o.name: str(o.get(build.PROP_NAME, o.name)) for o in parts}
    mats = {}
    for nm in order:
        r.set(at[nm])
        bpy.context.view_layer.update()
        mats[nm] = {o.name: np.array(o.matrix_world) for o in parts}
    r.set({})
    corners = {}
    for n in names:
        m = meshes[n]
        corners[n] = np.array([[x, y, z, 1.0] for x in (m.lo[0], m.hi[0]) for y in (m.lo[1], m.hi[1])
                               for z in (m.lo[2], m.hi[2])])
    depth: dict = {}
    for nm in order:
        W = mats[nm]
        box = {n: ((W[n] @ corners[n].T).T[:, :3].min(0), (W[n] @ corners[n].T).T[:, :3].max(0)) for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if frozenset((label[a], label[b])) in own:
                    continue
                if np.any(box[a][0] > box[b][1]) or np.any(box[b][0] > box[a][1]):
                    continue
                depth.setdefault((a, b), {})[nm] = clash.narrow(meshes[a], meshes[b],
                                                               np.linalg.inv(W[a]) @ W[b])[0] * 1000.0
    out = []
    for (a, b), got in depth.items():
        rel = [np.linalg.inv(mats[nm][a]) @ mats[nm][b] for nm in order]
        if all(np.allclose(rel[0], x, atol=1e-5) for x in rel):
            continue                                     # one rigid body: the CAD's own (not the motion's)
        lo = min(got.get(nm, 0.0) for nm in order)
        worst = max(got, key=got.get)
        if got[worst] - lo > limit_mm:
            out.append(f"{label[a]} x {label[b]}: {got[worst]:.1f} mm in '{worst}' (least {lo:.1f} mm)")
    return out
