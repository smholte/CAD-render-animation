"""Study 0300: invented test shapes as CAD-like triangle meshes (no Blender, metres).

The importer gives a part as one mesh with a point normal per vertex (``custom_normal``); a round face is cut into
long strips (a cylinder's side is one quad from bottom to top). These makers do the same, so the deformers are tried
on what an import really gives – not on a mesh made for deforming.
"""

from __future__ import annotations

import math

import numpy as np


def _tube(path: np.ndarray, n1: np.ndarray, n2: np.ndarray, r: float, seg: int):
    """A closed tube of radius r round ``path`` (N x 3) with frames n1, n2; end caps as fans."""
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    ring = np.cos(a)[None, :, None] * n1[:, None, :] + np.sin(a)[None, :, None] * n2[:, None, :]
    v = (path[:, None, :] + r * ring).reshape(-1, 3)
    nrm = ring.reshape(-1, 3)
    N = len(path)
    f = []
    for i in range(N - 1):
        for j in range(seg):
            a0, a1 = i * seg + j, i * seg + (j + 1) % seg
            b0, b1 = a0 + seg, a1 + seg
            f += [(a0, a1, b1), (a0, b1, b0)]
    v = np.vstack([v, path[0], path[-1]])
    t0 = path[1] - path[0]
    t1 = path[-1] - path[-2]
    nrm = np.vstack([nrm, -t0 / np.linalg.norm(t0), t1 / np.linalg.norm(t1)])
    c0, c1 = len(v) - 2, len(v) - 1
    last = (N - 1) * seg
    for j in range(seg):
        f.append((c0, (j + 1) % seg, j))
        f.append((c1, last + j, last + (j + 1) % seg))
    return v, np.array(f, np.int32), nrm


def spring(od=0.040, wire=0.004, free=0.080, turns=10.0, dead=1.0, per_turn=48, seg=16):
    """A compression spring standing on z = 0, axis +z: ``dead`` closed turns (pitch = wire) at each end, the rest
    active. Returns (verts, faces, normals, facts) – facts are what a reader should find."""
    R = (od - wire) / 2
    active = turns - 2 * dead
    h_dead = dead * wire
    h_act = free - wire - 2 * h_dead
    pitch = h_act / active
    n = int(turns * per_turn) + 1
    phi = np.linspace(0, 2 * math.pi * turns, n)
    t = phi / (2 * math.pi)
    zc = wire / 2 + np.interp(t, [0, dead, dead + active, turns], [0, h_dead, h_dead + h_act, 2 * h_dead + h_act])
    path = np.stack([R * np.cos(phi), R * np.sin(phi), zc], 1)
    tan = np.gradient(path, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    er = np.stack([np.cos(phi), np.sin(phi), 0 * phi], 1)
    n2 = np.cross(tan, er)
    n2 /= np.linalg.norm(n2, axis=1)[:, None]
    n1 = np.cross(n2, tan)
    v, f, nrm = _tube(path, n1, n2, wire / 2, seg)
    facts = dict(od=od, wire=wire, free=free, turns=turns, dead=dead, active=active, pitch=pitch,
                 solid=(turns + 1) * wire)
    return v, f, nrm, facts


def revolve(profile, seg=48):
    """A closed solid of revolution about +z from a profile [(r, z), ...] running from the axis round to the axis
    (first and last r = 0 are the poles). Normals per profile corner from the profile's own corners (sharp corners
    get a split, as the importer gives per face)."""
    prof = np.asarray(profile, float)
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    verts, faces, nrms = [], [], []
    # one strip per profile edge with its own vertices (flat normals across the edge = CAD faces kept apart)
    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        dr, dz = r1 - r0, z1 - z0
        nr, nz = dz, -dr                       # outward normal of a profile running round anticlockwise
        ln = math.hypot(nr, nz) or 1.0
        nr, nz = nr / ln, nz / ln
        base = sum(len(x) for x in verts)
        ring0 = np.stack([r0 * np.cos(a), r0 * np.sin(a), np.full(seg, z0)], 1)
        ring1 = np.stack([r1 * np.cos(a), r1 * np.sin(a), np.full(seg, z1)], 1)
        verts.append(np.vstack([ring0, ring1]))
        nn = np.stack([nr * np.cos(a), nr * np.sin(a), np.full(seg, nz)], 1)
        nrms.append(np.vstack([nn, nn]))
        for j in range(seg):
            k = (j + 1) % seg
            a0, a1, b0, b1 = base + j, base + k, base + seg + j, base + seg + k
            if r0 > 1e-9:
                faces.append((a0, a1, b1) if r1 > 1e-9 else (a0, a1, b0))
            if r1 > 1e-9 and r0 > 1e-9:
                faces.append((a0, b1, b0))
            elif r1 > 1e-9:
                faces.append((a0, b1, b0))
    v = np.vstack(verts)
    return v, np.array(faces, np.int32), np.vstack(nrms)


def buffer(d=0.030, h=0.025, ch=0.003, rows=1, seg=48):
    """A rubber buffer (bump stop): a cylinder with a chamfered top, as an import gives it (sides one strip high);
    ``rows`` > 1 = the side cut into that many rows, as an importer told to facet soft parts finer would give."""
    r = d / 2
    side = [(r, (h - ch) * i / rows) for i in range(1, rows + 1)]
    return revolve([(0, 0), (r, 0)] + side + [(r - ch, h), (0, h)], seg=seg)


def bellows(od=0.050, idia=0.030, length=0.120, folds=10, cuff=0.012):
    """A bellows (folding boot) on a rod: two plain cuffs of the inner Ø and ``folds`` V folds between OD and ID.
    A tube (open inside) – here drawn as the outer skin with flat ends, as many vendor models are."""
    ro, ri = od / 2, idia / 2
    prof = [(0, 0), (ri, 0), (ri, cuff)]
    pitch = (length - 2 * cuff) / folds
    z = cuff
    for _ in range(folds):
        prof += [(ro, z + pitch / 2), (ri, z + pitch)]
        z += pitch
    prof += [(ri, length), (0, length)]
    return revolve(prof, seg=40), dict(od=od, id=idia, length=length, folds=folds, cuff=cuff)


def tyre(r_out=0.30, width=0.20, r_rim=0.20, seg=96):
    """A tyre with a round shoulder, axis +z (the wheel's axle), centre at the origin; open at the rim like a
    vendor model is not – closed here by the rim face."""
    w = width / 2
    sh = 0.035
    prof = [(0, -w * 0.7), (r_rim, -w * 0.7), (r_rim, -w * 0.9), (r_out - sh, -w), (r_out, -w + sh), (r_out, w - sh),
            (r_out - sh, w), (r_rim, w * 0.9), (r_rim, w * 0.7), (0, w * 0.7)]     # the inner face hidden in the rim
    # finer along the tread and the walls so the flat and the bulge have points to move (an import would not)
    fine = []
    for (r0, z0), (r1, z1) in zip(prof[:-1], prof[1:]):
        n = 1 if (r0 == 0 or r1 == 0) else 6
        for i in range(n):
            fine.append((r0 + (r1 - r0) * i / n, z0 + (z1 - z0) * i / n))
    fine.append(prof[-1])
    return revolve(fine, seg=seg)


def box(sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    """An axis-aligned box (min corner z = cz), flat normals."""
    v, f, n = [], [], []
    dirs = [((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    for axis in range(3):
        for sgn in (-1, 1):
            nn = np.zeros(3)
            nn[axis] = sgn
            u = np.roll([1.0, 0, 0], axis + 1)
            w = np.roll([1.0, 0, 0], axis + 2)
            if sgn < 0:
                u, w = w, u
            c = nn * 0.5
            base = len(v)
            for (a, b) in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
                p = c + a * u + b * w
                v.append(p)
                n.append(nn)
            f += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    v = np.array(v) * [sx, sy, sz] + [cx, cy, cz + sz / 2]
    return v, np.array(f, np.int32), np.array(n)
