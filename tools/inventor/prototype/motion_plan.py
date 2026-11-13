"""Task 0104 prototype: an Inventor side file (``*.fresing.json``) -> the joints the app would make.

Pure Python + NumPy, no Blender (a draft of a future ``fresing_render/core/cad_motion.py``). Not part of the app and
not run by any test.

    ~/venv/bin/python tools/inventor/prototype/motion_plan.py tools/inventor/prototype/example.fresing.json

How it works (the design of tasks/0104, "Design"):

1. **Bodies per level.** Each assembly level is worked out on its own, as Inventor does: a part is a body, a *rigid*
   subassembly is one body at its parent's level (its own constraints are worked out at its own level, and its
   joints ride on whatever moves it), a *flexible* subassembly is opened up: its children and its constraints join
   the parent's level.
2. **What a constraint holds.** Every constraint (and Inventor assembly joint) between two bodies is turned into
   rows of a 6 x n matrix: each row is one small motion of body two against body one that the constraint forbids
   (a twist: turn ω + move v; a point x of body two moves by v + ω × x). Plane on plane forbids 3, axis on axis 4,
   Insert 5, a point on a plane 1. A Mate / Flush / Angle **with limits** forbids only what its value does not
   measure: the value is the travel, its limits the joint's limits.
3. **What is left free.** For each pair of bodies the free motions are the null space of their rows (SVD). Nothing
   free -> the two are one rigid group (merged; repeated until nothing changes). One turn -> a rotate joint with its
   exact axis (point + direction); one move -> a slide; a turn and a move along one axis -> a cylinder pair.
4. **Round parts that only spin** (pins, bolts, washers, rollers) ride with the body they sit in, unless a motion
   constraint or limits ask for their turn (gears). "Round" comes from the meshes in the app (``core/paths.is_round``);
   here, without meshes, from the constraints: everything it is constrained by lies on the axis.
5. **The tree.** From the grounded group outwards (breadth first) each group gets one joint against the group it
   hangs on; a group further out *rides on* that joint (a stacked joint). A barrel + rod pair (axis on axis) whose two
   ends each turn on another group is a **hydraulic cylinder** (the app's cylinder, barrel pin + rod pin). Any other
   closed loop is listed (a mechanism, made by hand).
6. **Limits and couplings.** A limited constraint's value is measured from its geometry while the joint moves a
   little: limits in the joint's own units, whatever the sign conventions. Rotate-Rotate / Rotate-Translate motion
   constraints become couplings (follows, ratio).
7. **Check against Inventor.** Where the side file has Inventor's own degrees of freedom of an occurrence
   (``GetDegreesOfFreedom``), the count worked out here must be the same (all constraints, limited ones too):
   a difference means a constraint was read wrongly.
"""
from __future__ import annotations

import json
import math
import sys

import numpy as np

MM = 0.001                    # side file mm -> m (the rows are in metres: points of a machine are 0.01 .. 50 m)
RANK_TOL = 1e-4               # a row counts when its singular value is above this (relative): ~0.1 mm over 1 m
PITCH_TOL = 1e-6
AXIS_TOL = 0.5 * MM           # two axes are the same within 0.5 mm and ...
DIR_TOL = 1e-3                # ... 0.06 degrees


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def perp2(d) -> tuple[np.ndarray, np.ndarray]:
    d = unit(d)
    a = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = unit(np.cross(d, a))
    return e1, np.cross(d, e1)


# --------------------------------------------------------------------------------------------------------------
# rows: small motions of body two against body one that a constraint forbids
# --------------------------------------------------------------------------------------------------------------

def r_point_on_plane(p, n):
    return [np.r_[np.cross(p, n), n]]


def r_point_on_line(p, d):
    return [np.r_[np.cross(p, e), e] for e in perp2(d)]


def r_point_fixed(p):
    return [np.r_[np.cross(p, e), e] for e in np.eye(3)]


def r_parallel(d):
    return [np.r_[e, np.zeros(3)] for e in perp2(d)]


def r_dir_in_plane(d, n):
    return [np.r_[np.cross(d, n), np.zeros(3)]]


class Feature:
    """A point, a line (point + direction) or a plane (point + normal), in metres."""

    def __init__(self, kind: str, p, d=None):
        self.kind, self.p, self.d = kind, np.asarray(p, float), None if d is None else unit(d)


def feature(side: dict, insert: bool = False) -> Feature | None:
    g = side.get("geometry") or {}
    t, inferred = g.get("type", ""), side.get("inferred", "")
    p = np.asarray(g.get("point", (0.0, 0.0, 0.0)), float) * MM
    d = g.get("direction")
    if inferred == "point" or t in ("point", "vertex", "sphere"):
        return Feature("point", p)
    if t == "plane" and inferred != "line":
        return Feature("plane", p, d)
    if t in ("line", "cylinder", "cone", "circle", "arc") and d is not None:
        return Feature("line", p, d)
    return None


def mate_rows(f1: Feature, f2: Feature, limited: bool) -> list:
    """Mate / Flush (also a Mate between axes or points). ``limited``: the distance is the travel (no row for it)."""
    kinds = {f1.kind, f2.kind}
    rows = []
    if kinds == {"plane"}:
        rows += r_parallel(f1.d)
        if not limited:
            rows += r_point_on_plane(f2.p, f1.d)
    elif kinds == {"plane", "line"}:
        pl, ln = (f1, f2) if f1.kind == "plane" else (f2, f1)
        rows += r_dir_in_plane(ln.d, pl.d)
        if not limited:
            rows += r_point_on_plane(ln.p, pl.d)
    elif kinds == {"plane", "point"}:
        pl, pt = (f1, f2) if f1.kind == "plane" else (f2, f1)
        if not limited:
            rows += r_point_on_plane(pt.p, pl.d)
    elif kinds == {"line"}:
        rows += r_parallel(f1.d) + r_point_on_line(f2.p, f1.d)
    elif kinds == {"line", "point"}:
        ln, pt = (f1, f2) if f1.kind == "line" else (f2, f1)
        rows += r_point_on_line(pt.p, ln.d)
    elif kinds == {"point"}:
        rows += r_point_fixed(f2.p)
    return rows


def reference_of(c: dict):
    """An Angle constraint's reference direction ("Explicit reference vector"): written as a direction or as the
    geometry of the edge / axis picked."""
    if c.get("reference"):
        return unit(c["reference"])
    g = c.get("reference_geometry") or {}
    return unit(g["direction"]) if g.get("direction") else None


def direction_of(side: dict) -> np.ndarray | None:
    g = side.get("geometry") or {}
    return None if g.get("direction") is None else unit(g["direction"])


def constraint_rows(c: dict, with_limited: bool = False) -> tuple[list, str]:
    """(rows, why none) for a constraint or an Inventor assembly joint. ``with_limited``: rows of a limited value too
    (for the check against Inventor's own count)."""
    t = c["type"]
    limited = bool(c.get("limits")) and not with_limited
    if t in ("mate", "flush"):
        f1, f2 = feature(c["one"]), feature(c["two"])
        if f1 is None or f2 is None:
            return [], "geometry not read"
        return mate_rows(f1, f2, limited), ""
    if t == "insert":
        f1, f2 = feature(c["one"], True), feature(c["two"], True)
        if f1 is None or f2 is None or f1.kind != "line" or f2.kind != "line":
            return [], "geometry not read"
        rows = r_parallel(f1.d) + r_point_on_line(f2.p, f1.d)
        if not limited:
            rows += r_point_on_plane(f2.p, f1.d)
        if c.get("lock_rotation"):
            rows.append(np.r_[f1.d, np.zeros(3)])
        return rows, ""
    if t == "angle":
        if limited:
            return [], ""
        d1, d2 = direction_of(c["one"]), direction_of(c["two"])
        if d1 is None or d2 is None:
            return [], "geometry not read"
        ref = reference_of(c)
        axis = unit(ref) if ref is not None else unit(np.cross(d1, d2))
        if np.linalg.norm(axis) < 0.5:
            return r_parallel(d1), ""
        return [np.r_[axis, np.zeros(3)]], ""
    if t in ("rotational", "slide", "cylindrical", "planar", "ball", "rigid"):          # Inventor assembly joints
        o = c["one"].get("origin") or {}
        if o.get("point") is None or o.get("z") is None:
            return [], "its origin could not be read"
        p, z = np.asarray(o["point"], float) * MM, unit(o["z"])
        if c.get("locked") or t == "rigid":
            return [np.r_[e, np.zeros(3)] for e in np.eye(3)] + r_point_fixed(p), ""
        rows = {
            "rotational": r_parallel(z) + r_point_on_line(p, z) + r_point_on_plane(p, z),
            "slide": [np.r_[e, np.zeros(3)] for e in np.eye(3)] + r_point_on_line(p, z),
            "cylindrical": r_parallel(z) + r_point_on_line(p, z),
            "planar": r_parallel(z) + r_point_on_plane(p, z),
            "ball": r_point_fixed(p),
        }[t]
        return rows, ""            # (an Inventor joint's limits never hold it: its free motion is the joint)
    return [], {"tangent": "a cam / tangent contact (not a joint)", "transitional": "a cam contact (not a joint)",
                "symmetry": "a symmetry (a coupling, made by hand)", "pin_slot": "a pin-slot joint (a turn + a slide): made by hand",
                "translate_translate": "a translate-translate motion constraint: made by hand",
                "rotate_rotate": "", "rotate_translate": ""}.get(t, f"unknown kind '{t}'")


def free_twists(rows: list) -> np.ndarray:
    """Null space (6 x k) of the rows: the small motions left free."""
    if not rows:
        return np.eye(6)
    A = np.array([r / (np.linalg.norm(r) or 1.0) for r in rows])
    _u, s, vt = np.linalg.svd(A)
    rank = int(np.sum(s > RANK_TOL * max(1.0, s[0])))
    return vt[rank:].T


def classify(N: np.ndarray, centre) -> dict:
    """What a null space is: rotate (axis), slide (direction), cylinder (axis), or other."""
    k = N.shape[1]
    if k == 0:
        return {"type": "rigid"}
    if k == 1:
        w, v = N[:3, 0], N[3:, 0]
        if np.linalg.norm(w) < 1e-6:
            return {"type": "slide", "direction": unit(v), "point": np.asarray(centre)}
        u = unit(w)
        pitch = float(u @ v) / np.linalg.norm(w)
        point = np.cross(w, v) / (w @ w) + centre
        if abs(pitch) > PITCH_TOL:
            return {"type": "helical", "direction": u, "point": point, "pitch": pitch}
        return {"type": "rotate", "direction": u, "point": point}
    if k == 2:
        W = N[:3, :]
        _u, s, vt = np.linalg.svd(W)
        if s[1] < 1e-6 * max(1.0, s[0]):            # one combination turns nothing: a pure move
            tr = N @ vt[1]
            ro = N @ vt[0]
            w, v = ro[:3], ro[3:]
            u = unit(w)
            v = v - (v @ unit(tr[3:])) * unit(tr[3:])        # take the move out: the axis of the turn
            point = np.cross(w, v) / (w @ w) + centre
            if abs(abs(u @ unit(tr[3:])) - 1.0) < DIR_TOL:
                return {"type": "cylinder", "direction": u, "point": point}
    return {"type": f"free in {k} ways"}


# --------------------------------------------------------------------------------------------------------------
# the side file
# --------------------------------------------------------------------------------------------------------------

class Model:
    def __init__(self, data: dict):
        if data.get("format") != "fresing-cad-motion" or int(data.get("version", 0)) != 1:
            raise ValueError("not a Fresing motion file (version 1)")
        u = data.get("units", {})
        if u.get("length", "mm") != "mm" or u.get("angle", "deg") != "deg":
            raise ValueError("the side file must be in mm and degrees")
        self.data = data
        self.occ = {tuple(o["path"]): o for o in data["occurrences"]}
        gone = {p for p, o in self.occ.items() if o.get("suppressed") or o.get("excluded")}
        self.gone = gone
        self.live = {p: o for p, o in self.occ.items() if not any(p[:i] in gone for i in range(1, len(p) + 1))}
        self.items = [dict(c, _joint=False) for c in data.get("constraints", [])] + \
                     [dict(j, _joint=True) for j in data.get("joints", [])]
        pts = []
        for c in self.items:
            for s in ("one", "two"):
                g = (c.get(s) or {}).get("geometry") or (c.get(s) or {}).get("origin") or {}
                if "point" in g:
                    pts.append(g["point"])
        self.centre = (np.mean(pts, axis=0) * MM) if pts else np.zeros(3)

    def children(self, path: tuple) -> list[tuple]:
        return [p for p in self.live if len(p) == len(path) + 1 and p[:len(path)] == path]

    def leaves(self, path: tuple) -> list[tuple]:
        o = self.live.get(path)
        if o is not None and o["kind"] == "part":
            return [path]
        return [lf for c in self.children(path) for lf in self.leaves(c)]

    def is_flexible(self, path: tuple) -> bool:
        return bool(self.live.get(path, {}).get("flexible"))


def side_path(c: dict, s: str) -> tuple:
    return tuple((c.get(s) or {}).get("occurrence") or ())


# --------------------------------------------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------------------------------------------

def _round_by_constraints(model: Model, nodes: list, point, direction) -> bool:
    """Without meshes: a group is round about an axis when every constraint geometry on it lies on that axis
    (a pin, a bolt, a wheel on its shaft). The app asks the meshes instead (core/paths.is_round)."""
    leaves = {lf for n in nodes for lf in model.leaves(n)}
    seen = False
    for c in model.items:
        for s in ("one", "two"):
            if side_path(c, s) not in leaves:
                continue
            g = c[s].get("geometry") or c[s].get("origin") or {}
            if "point" not in g:
                return False
            p = np.asarray(g["point"], float) * MM
            off = (p - point) - ((p - point) @ direction) * direction
            if np.linalg.norm(off) > AXIS_TOL:
                return False
            d = g.get("direction") or g.get("z")
            if g.get("type") in ("line", "cylinder", "circle") and d is not None and abs(abs(unit(d) @ direction) - 1) > DIR_TOL:
                return False
            seen = True
    return seen


class Level:
    """One assembly level: its bodies, its constraints, the groups that come out."""

    def __init__(self, model: Model, path: tuple):
        self.model, self.path = model, path
        self.assemblies = [path]
        self.bodies: list[list[tuple]] = []           # each body: its node paths
        self.own = None                                 # the body that stands for the assembly's own planes
        self._collect(path)
        self.items = [c for c in model.items if tuple(c.get("assembly", ())) in self.assemblies]
        if any(side_path(c, s) == path for c in self.items for s in ("one", "two")):
            self.own = len(self.bodies)
            self.bodies.append([path])

    def _collect(self, path):
        for ch in self.model.children(path):
            o = self.model.live[ch]
            if o["kind"] == "assembly" and o.get("flexible"):
                self.assemblies.append(ch)
                self._collect(ch)
            else:
                self.bodies.append([ch])

    def body_of(self, p: tuple) -> int | None:
        if p == self.path:                              # the assembly's own origin planes / axes: held still
            return self.own
        for i, nodes in enumerate(self.bodies):
            if self.own is not None and i == self.own:
                continue
            if any(p[:len(n)] == n for n in nodes):
                return i
        return None


def plan(data: dict, is_round=None) -> dict:
    """The side file -> {"joints", "cylinders", "couplings", "notes", "left_out"} (the demo joint sheet's form:
    axis point and direction in the STEP's mm, parts as occurrence paths)."""
    model = Model(data)
    out = {"joints": [], "cylinders": [], "couplings": [], "notes": [], "left_out": []}
    round_test = is_round or (lambda nodes, p, d: _round_by_constraints(model, nodes, p, d))
    asked = set()                                       # leaves whose own turn a motion constraint / limits wants
    for c in model.items:
        if c["type"] in ("rotate_rotate", "rotate_translate") and not c.get("suppressed"):
            asked |= {side_path(c, "one"), side_path(c, "two")}
    for c in model.items:
        if c.get("suppressed"):
            continue
        if not c.get("healthy", True):
            out["left_out"].append(f"{c['name']}: not healthy in Inventor (left out)")
    joint_of_leaf: dict[tuple, str] = {}
    _level(model, (), None, round_test, asked, out, joint_of_leaf)
    _couplings(model, out, joint_of_leaf)
    _check_dof(model, out)
    _check_holds(model, out)
    return out


def _level(model, path, carrier_joint, round_test, asked, out, joint_of_leaf):
    lv = Level(model, path)
    nb = len(lv.bodies)
    parent = list(range(nb))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    links = []                                          # (body i, body j, rows, item)
    limited = []                                        # (body i, body j, item)
    where = "the top assembly" if not path else "/".join(path)
    for c in lv.items:
        if c.get("suppressed") or not c.get("healthy", True):
            continue
        a, b = side_path(c, "one"), side_path(c, "two")
        if any(x not in model.live and x not in lv.assemblies for x in (a, b)):
            out["left_out"].append(f"{c['name']} ({where}): one of its parts is suppressed or missing")
            continue
        i, j = lv.body_of(a), lv.body_of(b)
        if i is None or j is None or i == j:
            continue
        rows, why = constraint_rows(c)
        if why:
            out["left_out"].append(f"{c['name']} ({where}, {a[-1]} – {b[-1]}): {why}")
        if c.get("limits") or c.get("angle_limits") or c.get("linear_limits"):
            limited.append((i, j, c))
        if not rows:
            continue                                    # a cam contact, a symmetry, a motion constraint: no link
        links.append((i, j, [_shift(r, model.centre) for r in rows], c))

    def pair_rows():
        g: dict = {}
        for i, j, rows, c in links:
            a, b = find(i), find(j)
            if a == b:
                continue
            key = (min(a, b), max(a, b))
            g.setdefault(key, ([], []))
            g[key][0].extend(rows)
            g[key][1].append(c["name"])
        return g

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    def merge_rigid():
        """Every pair held fully is one group. All of a pass at once: a pair held fully stays so when its groups
        grow (rows are only added), so the order does not matter."""
        while True:
            rigid = [k for k, (rows, _names) in pair_rows().items() if free_twists(rows).shape[1] == 0]
            if not rigid:
                return
            for a, b in rigid:
                union(a, b)
    merge_rigid()

    grounded = [i for i, nodes in enumerate(lv.bodies)
                if i == lv.own or any(model.live[n].get("grounded") for n in nodes)]
    if not grounded:
        grounded = [0] if nb else []
        if nb:
            out["notes"].append(f"{where}: nothing grounded – {lv.bodies[0][0][-1]} (the first) holds still")
    

    def groups():
        g: dict = {}
        for i in range(nb):
            g.setdefault(find(i), []).append(i)
        return g

    frozen: dict = {}

    def nodes_of(root):
        """The group's parts and subassemblies (the assembly's own planes, when in it, last: not a part)."""
        g = frozen or groups()
        return [n for i in sorted(g[root], key=lambda i: i == lv.own) for n in lv.bodies[i]]

    def label(nodes):
        return ", ".join(n[-1] if n != lv.path else "the assembly's own planes" for n in nodes)

    def hops():
        ground = {find(i) for i in grounded}
        adj: dict = {}
        for (a, b), (rows, _n) in pair_rows().items():
            if free_twists(rows).shape[1] < 6:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
        dist = {g: 0 for g in ground}
        todo = list(ground)
        while todo:
            x = todo.pop(0)
            for y in sorted(adj.get(x, ())):
                if y not in dist:
                    dist[y] = dist[x] + 1
                    todo.append(y)
        return dist

    # round parts that only spin ride with the group they sit in
    limited_bodies = {i for i, j, _c in limited} | {j for i, j, _c in limited}
    while True:
        ground = {find(i) for i in grounded}
        pr = pair_rows()
        dist = hops()
        G = groups()
        frozen.update(G)
        by_root: dict = {}
        for k in pr:
            by_root.setdefault(k[0], []).append(k)
            by_root.setdefault(k[1], []).append(k)
        moves = []
        for root in sorted(G, key=lambda r: len(G[r])):
            if root in ground:
                continue
            mine = [(k, classify(free_twists(pr[k][0]), model.centre)) for k in by_root.get(root, ())]
            if not mine or any(c["type"] != "rotate" for _k, c in mine):
                continue
            axis0 = mine[0][1]
            if not all(_same_axis(axis0, c) for _k, c in mine):
                continue
            nodes = nodes_of(root)
            leaves = {lf for n in nodes for lf in model.leaves(n)}
            if leaves & asked or limited_bodies & set(G[root]):
                continue
            if not round_test(nodes, axis0["point"], axis0["direction"]):
                continue
            others = [k[0] if k[1] == root else k[1] for k, _c in mine]
            to = min(others, key=lambda o: dist.get(o, 1 << 30))
            out["notes"].append(f"{label(nodes)}: round, only spins – rides with {label(nodes_of(to)[:1])}")
            moves.append((to, root))
        frozen.clear()
        if not moves:
            break
        for to, root in moves:
            union(to, root)
        merge_rigid()
    frozen.update(groups())                             # the groups stay as they are from here on

    # edges between the groups
    pr = pair_rows()
    edges = {k: (classify(free_twists(rows), model.centre), names) for k, (rows, names) in pr.items()}
    ground = {find(i) for i in grounded}

    # hydraulic cylinders: an axis-on-axis pair whose two ends each turn on another group
    in_cyl = set()
    for (a, b), (cl, names) in edges.items():
        if cl["type"] != "cylinder" or a in ground or b in ground:
            continue
        ea = [(k, e) for k, e in edges.items() if a in k and k != (a, b)]
        eb = [(k, e) for k, e in edges.items() if b in k and k != (a, b)]
        if len(ea) != 1 or len(eb) != 1 or ea[0][1][0]["type"] != "rotate" or eb[0][1][0]["type"] != "rotate":
            continue
        barrel, rod = _barrel_first(model, nodes_of(a), nodes_of(b))
        if barrel != nodes_of(a):
            a, b, ea, eb = b, a, eb, ea
        pa, pb = ea[0][0], eb[0][0]
        ca = pa[0] if pa[1] == a else pa[1]
        cb = pb[0] if pb[1] == b else pb[1]
        out["cylinders"].append({
            "name": f"{nodes_of(a)[0][-1]} cylinder", "barrel": [list(n) for n in nodes_of(a)],
            "rod": [list(n) for n in nodes_of(b)],
            "barrel_pin": _axis_out(dict(ea[0][1][0], point=_on_axis(ea[0][1][0], ea[0][1][1], lv.items))),
            "rod_pin": _axis_out(dict(eb[0][1][0], point=_on_axis(eb[0][1][0], eb[0][1][1], lv.items))),
            "barrel_carrier": [list(n) for n in nodes_of(ca)], "rod_carrier": [list(n) for n in nodes_of(cb)],
            "from": names + ea[0][1][1] + eb[0][1][1]})
        in_cyl |= {a, b}

    edges_at: dict = {}
    for k in sorted(edges):
        edges_at.setdefault(k[0], []).append(k)
        edges_at.setdefault(k[1], []).append(k)

    # the tree: from the ground outwards, one joint per group
    joint_of_group: dict = {g: carrier_joint for g in ground}
    seen = set(ground)
    todo = sorted(ground)
    used = set()
    while todo:
        x = todo.pop(0)
        for k in edges_at.get(x, ()):
            if k in used:
                continue
            y = k[1] if k[0] == x else k[0]
            if y in seen or y in in_cyl:
                continue
            cl, names = edges[k]
            kind = {"rotate": "rotate", "slide": "slide", "cylinder": "slide"}.get(cl["type"])
            if kind is None:
                out["left_out"].append(f"{label(nodes_of(y))} on {label(nodes_of(x)[:1])}: {cl['type']} ({', '.join(names)}) – no joint")
                continue
            used.add(k)
            seen.add(y)
            todo.append(y)
            direction = _nice(cl, names, lv.items, model)
            cl = dict(cl, point=_on_axis(cl, names, lv.items))
            nodes = nodes_of(y)
            name = f"{nodes[0][-1]} {'turn' if kind == 'rotate' else 'slide'}"
            j = {"name": name, "type": kind, "parts": [list(n) for n in nodes],
                 "axis": {"point": [round(float(v) / MM, 3) for v in cl["point"]],
                          "direction": [round(float(v), 6) for v in direction]},
                 "limits": None, "rides_on": joint_of_group.get(x), "on": [list(n) for n in nodes_of(x) if n != lv.path],
                 "from": names}
            if cl["type"] == "cylinder":
                out["notes"].append(f"{name}: turns and slides on one axis ({', '.join(names)}) – made a slide")
            j["limits"] = _limits(model, j, [c for i, jj, c in limited if {find(i), find(jj)} == {x, y}],
                                  nodes, out)
            out["joints"].append(j)
            joint_of_group[y] = name
            for n in nodes:
                for lf in model.leaves(n):
                    joint_of_leaf[lf] = name
    for k, (cl, names) in edges.items():
        if k not in used and not (set(k) & in_cyl) and k[0] in seen and k[1] in seen and cl["type"] != "rigid":
            out["notes"].append(f"closed loop: {label(nodes_of(k[0])[:1])} – {label(nodes_of(k[1])[:1])} "
                                f"({', '.join(names)}): a mechanism, not made")
    for root in groups():
        if root not in seen and root not in in_cyl:
            nodes = nodes_of(root)
            if any(root in k for k in edges):
                continue                                 # already listed as "no joint"
            for n in nodes:
                for lf in model.leaves(n):
                    joint_of_leaf.setdefault(lf, joint_of_group.get(find(grounded[0])) if grounded else None)
    for root in groups():
        for n in nodes_of(root):
            for lf in model.leaves(n):
                joint_of_leaf.setdefault(lf, joint_of_group.get(root))

    # rigid subassemblies: their own level, riding on whatever moves them here
    for i, nodes in enumerate(lv.bodies):
        if i == lv.own:
            continue
        for n in nodes:
            o = model.live[n]
            if o["kind"] == "assembly" and not o.get("flexible"):
                g = find(lv.body_of(n))
                _level(model, n, joint_of_group.get(g), round_test, asked, out, joint_of_leaf)


def _shift(r, centre):
    """A row about the model origin -> the same row about ``centre`` (better numbers in the SVD): with the velocity
    at the centre v_c = v + ω × c the row (a, b) reads (a − c × b)·ω + b·v_c."""
    return np.r_[r[:3] - np.cross(centre, r[3:]), r[3:]]


def _same_axis(a: dict, b: dict) -> bool:
    if abs(abs(a["direction"] @ b["direction"]) - 1.0) > DIR_TOL:
        return False
    off = b["point"] - a["point"]
    off = off - (off @ a["direction"]) * a["direction"]
    return np.linalg.norm(off) < AXIS_TOL


def _on_axis(cl, names, items):
    """A tidy point on the axis: where the first point of the pair's constraint geometry falls on it."""
    for c in items:
        if c["name"] not in names:
            continue
        for s in ("one", "two"):
            g = c[s].get("geometry") or c[s].get("origin") or {}
            if "point" in g:
                p = np.asarray(g["point"], float) * MM
                return cl["point"] + ((p - cl["point"]) @ cl["direction"]) * cl["direction"]
    return cl["point"]


def _barrel_first(model, a, b):
    words_b = ("barrel", "cylinder", "tube", "housing", "cilinder", "zylinder", "huis")
    words_r = ("rod", "piston", "stang", "zuiger", "kolben")

    def score(nodes):
        t = " ".join(n[-1].lower() for n in nodes)
        return (any(w in t for w in words_b)) - (any(w in t for w in words_r))
    return (a, b) if score(a) >= score(b) else (b, a)


def _axis_out(cl):
    return {"point": [round(float(v) / MM, 3) for v in cl["point"]],
            "direction": [round(float(v), 6) for v in cl["direction"]]}


def _nice(cl, names, items, model):
    """The joint's direction: an Inventor joint's own z; else the axis found, pointing along +x / +y / +z."""
    for c in items:
        if c["name"] in names and c.get("_joint"):
            z = unit(c["one"]["origin"]["z"])
            return z
    d = cl["direction"]
    big = int(np.argmax(np.abs(d)))
    return d if d[big] > 0 else -d


def _rot(axis, angle):
    a = unit(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(angle) * K + (1 - math.cos(angle)) * K @ K


def _measure(c, child_side: str, motion) -> float:
    """The constraint's value (deg or mm) with the child side moved by ``motion`` (a function of a point, a
    direction -> moved point, direction)."""
    g1, g2 = c["one"]["geometry"], c["two"]["geometry"]
    p1, d1 = np.asarray(g1["point"], float), unit(g1["direction"])
    p2, d2 = np.asarray(g2["point"], float), unit(g2["direction"])
    if child_side == "two":
        p2, d2 = motion(p2, d2)
    else:
        p1, d1 = motion(p1, d1)
    if c["type"] == "angle":
        sol = c.get("solution", "directed")
        if sol == "undirected":
            return math.degrees(math.acos(max(-1.0, min(1.0, float(d1 @ d2)))))
        ref = reference_of(c)
        ref = ref if ref is not None else unit(np.cross(d1, d2))
        return math.degrees(math.atan2(float(np.cross(d1, d2) @ ref), float(d1 @ d2)))
    return float((p2 - p1) @ d1)                       # Mate / Flush offset: from plane one along its normal


def _limits(model, j, items, nodes, out):
    """Joint limits in the joint's units (deg / mm, 0 = the CAD pose) from limited constraints on this pair."""
    if not items:
        return None
    leaves = {lf for n in nodes for lf in model.leaves(n)}
    pt, d = np.asarray(j["axis"]["point"], float), unit(j["axis"]["direction"])
    lo, hi = -math.inf, math.inf
    for c in items:
        if c.get("_joint"):
            lim = c.get("angle_limits") if j["type"] == "rotate" else c.get("linear_limits")
            if not lim:
                continue
            now = c.get("angle" if j["type"] == "rotate" else "linear") or 0.0
            z = unit(c["one"]["origin"]["z"])
            sign = 1.0 if z @ d > 0 else -1.0
            ends = [((v - now) * sign) if v is not None else None for v in (lim.get("min"), lim.get("max"))]
            if None in ends:
                continue                                # (an open end: the other alone is not used here)
            a, b = sorted(ends)
            lo, hi = max(lo, a), min(hi, b)
            continue
        child = "two" if side_path(c, "two") in leaves else "one"

        def motion(s):
            if j["type"] == "rotate":
                R = _rot(d, math.radians(s))
                return lambda p, dd: (pt + R @ (p - pt), R @ dd)
            return lambda p, dd: (p + d * s, dd)
        h = 0.01
        m0 = _measure(c, child, motion(0.0))
        k = (_measure(c, child, motion(h)) - _measure(c, child, motion(-h))) / (2 * h)
        if abs(m0 - float(c.get("value", m0))) > 0.05:
            out["notes"].append(f"{c['name']}: Inventor says {c.get('value')}, its geometry {m0:.3f} – limits not "
                                f"used (check the sign convention)")
            continue
        if abs(k) < 1e-9:
            out["notes"].append(f"{c['name']}: its value does not change with {j['name']} – limits not used")
            continue
        lim = c["limits"]
        ends = [(v - m0) / k if v is not None else (-math.inf if (v is lim.get("min")) == (k > 0) else math.inf)
                for v in (lim.get("min"), lim.get("max"))]
        a, b = sorted(ends)
        lo, hi = max(lo, a), min(hi, b)
    if not math.isfinite(lo) or not math.isfinite(hi):
        if math.isfinite(lo) or math.isfinite(hi):
            out["notes"].append(f"{j['name']}: only one end of its travel is set in Inventor – no limits made")
        return None
    return [round(lo, 3), round(hi, 3)]


def _couplings(model, out, joint_of_leaf):
    joints = {j["name"]: j for j in out["joints"]}
    for c in model.items:
        if c.get("suppressed") or c["type"] not in ("rotate_rotate", "rotate_translate"):
            continue
        a, b = side_path(c, "one"), side_path(c, "two")
        ja, jb = joints.get(joint_of_leaf.get(a)), joints.get(joint_of_leaf.get(b))
        if ja is None or jb is None or ja is jb:
            out["left_out"].append(f"{c['name']}: its parts have no joints of their own – coupling not made")
            continue
        sign = 1.0 if c.get("forward", True) else -1.0
        da, db = direction_of(c["one"]), direction_of(c["two"])
        if da is not None:
            sign *= 1.0 if da @ unit(ja["axis"]["direction"]) > 0 else -1.0
        if db is not None:
            sign *= 1.0 if db @ unit(jb["axis"]["direction"]) > 0 else -1.0
        if c["type"] == "rotate_rotate":
            ratio = sign * float(c.get("ratio", 1.0))       # turns of two per turn of one (assumed, see the report)
        else:
            ratio = sign * float(c.get("distance", 0.0)) / 360.0  # mm of two per degree of one
        out["couplings"].append({"joint": jb["name"], "follows": ja["name"], "ratio": round(ratio, 6),
                                 "from": c["name"]})


def _check_dof(model, out):
    """Inventor's own count of free motions of an occurrence (others held) against the rows read here."""
    for p, o in model.live.items():
        dof = o.get("dof")
        if dof is None or o["kind"] != "part":
            continue
        rows = []
        for c in model.items:
            if c.get("suppressed") or c["type"] in ("rotate_rotate", "rotate_translate"):
                continue
            if p in (side_path(c, "one"), side_path(c, "two")) and side_path(c, "one") != side_path(c, "two"):
                rows += [_shift(r, model.centre) for r in constraint_rows(c, with_limited=True)[0]]
        if not rows and not any(p in (side_path(c, "one"), side_path(c, "two")) for c in model.items):
            continue
        mine = free_twists(rows).shape[1]
        theirs = len(dof.get("translations", [])) + len(dof.get("rotations", []))
        if mine != theirs:
            out["notes"].append(f"check: {p[-1]} – Inventor counts {theirs} free motions, the file's constraints "
                                f"give {mine}: a constraint was read wrongly")


def _check_holds(model, out, tol_mm: float = 0.05, tol_deg: float = 0.05):
    """Every constraint must hold in the geometry read: axes on axes, planes on planes at the offset, the angle.
    A constraint that does not hold was read in the wrong coordinates (a subassembly's matrix missed, cm left)."""
    for c in model.items:
        if c.get("suppressed") or c.get("_joint") or c["type"] not in ("mate", "flush", "insert", "angle"):
            continue
        a, b = side_path(c, "one"), side_path(c, "two")
        if a not in model.live or b not in model.live:
            continue
        why = ""
        if c["type"] == "angle":
            if not c.get("limits"):
                continue                                 # (with limits the value is measured in _limits)
            m = _measure(c, "two", lambda p, d: (p, d))
            if abs(m - float(c.get("value", m))) > tol_deg:
                why = f"angle {m:.2f}° read, {c.get('value')}° in Inventor"
        else:
            f1, f2 = feature(c["one"], c["type"] == "insert"), feature(c["two"], c["type"] == "insert")
            if f1 is None or f2 is None:
                continue
            if f1.kind in ("line", "plane") and f2.kind in ("line", "plane") and f1.kind == f2.kind:
                if abs(abs(f1.d @ f2.d) - 1.0) > DIR_TOL:
                    why = "the two directions are not parallel"
            if not why and f1.kind == "line" and f2.kind in ("line", "point"):
                off = (f2.p - f1.p) - ((f2.p - f1.p) @ f1.d) * f1.d
                if np.linalg.norm(off) > tol_mm * MM:
                    why = f"the axes are {np.linalg.norm(off) / MM:.2f} mm apart"
            if not why and (f1.kind == "plane" or c["type"] == "insert") and not c.get("limits"):
                gap = float((f2.p - f1.p) @ f1.d) / MM
                want = float(c.get("value", 0.0))
                if min(abs(gap - want), abs(-gap - want)) > tol_mm:
                    why = f"the gap is {gap:.2f} mm, {want} mm in Inventor"
        if why:
            out["notes"].append(f"check: {c['name']} ({a[-1]} – {b[-1]}) does not hold in the file: {why} – read "
                                f"wrongly?")


def main(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        p = plan(json.load(fh))
    for j in p["joints"]:
        print(f"joint  {j['name']:<22} {j['type']:<6} parts {[n[-1] for n in j['parts']]} "
              f"at {j['axis']['point']} dir {j['axis']['direction']} limits {j['limits']} rides on {j['rides_on']}")
    for c in p["cylinders"]:
        print(f"cylinder {c['name']}: barrel {[n[-1] for n in c['barrel']]} pin {c['barrel_pin']}, "
              f"rod {[n[-1] for n in c['rod']]} pin {c['rod_pin']}")
    for c in p["couplings"]:
        print(f"coupling {c['joint']} follows {c['follows']} x {c['ratio']}")
    for n in p["notes"]:
        print("note  ", n)
    for n in p["left_out"]:
        print("left  ", n)
    return p


if __name__ == "__main__":
    main(sys.argv[1])
