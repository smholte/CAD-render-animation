"""Study 0300: read a coil spring from its mesh alone (no Blender): axis, outer Ø, wire Ø, free length, turns,
active pitch, dead (closed) turns at the ends, solid length. Works in any placement (the import's coordinates)."""

from __future__ import annotations

import math

import numpy as np


def volume(v: np.ndarray, f: np.ndarray) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def _frame(u):
    a = np.array([1.0, 0, 0]) if abs(u[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = np.cross(u, a)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(u, e1)


def _spread(x, pts, u0, e1, e2):
    u = u0 + x[0] * e1 + x[1] * e2
    u = u / np.linalg.norm(u)
    c = x[2] * e1 + x[3] * e2
    q = pts - c
    r = np.linalg.norm(q - np.outer(q @ u, u), axis=1)
    return r.std(), u, c


def _nelder_mead(fn, x0, step, n=400):
    pts = [np.asarray(x0, float)] + [np.asarray(x0, float) + np.eye(len(x0))[i] * step[i] for i in range(len(x0))]
    val = [fn(p) for p in pts]
    for _ in range(n):
        o = np.argsort(val)
        pts = [pts[i] for i in o]
        val = [val[i] for i in o]
        c = np.mean(pts[:-1], 0)
        xr = c + (c - pts[-1])
        fr = fn(xr)
        if fr < val[0]:
            xe = c + 2 * (c - pts[-1])
            fe = fn(xe)
            pts[-1], val[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < val[-2]:
            pts[-1], val[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c)
            fc = fn(xc)
            if fc < val[-1]:
                pts[-1], val[-1] = xc, fc
            else:
                pts = [pts[0] + 0.5 * (p - pts[0]) for p in pts]
                val = [fn(p) for p in pts]
    return pts[int(np.argmin(val))]


def _axis(v: np.ndarray):
    """The axis of a round part: the line about which the points' distance varies least (PCA to start, then a
    4-number search: direction tilt + offset)."""
    c0 = v.mean(0)
    pts = v[:: max(1, len(v) // 3000)] - c0
    _, _, vt = np.linalg.svd(pts, full_matrices=False)
    best = None
    for u0 in vt:
        e1, e2 = _frame(u0)
        size = np.ptp(pts, 0).max()
        x = _nelder_mead(lambda x: _spread(x, pts, u0, e1, e2)[0], [0, 0, 0, 0], [0.05, 0.05, size / 20, size / 20])
        sd, u, c = _spread(x, pts, u0, e1, e2)
        q = pts - c
        r = np.linalg.norm(q - np.outer(q @ u, u), axis=1)
        score = sd / (r.mean() + 1e-12)
        if best is None or score < best[0]:
            best = (score, u, c + c0)
    return best[1], best[2]


def spring(v: np.ndarray, f: np.ndarray) -> dict:
    u, c = _axis(v)
    q = v - c
    h = q @ u
    lo = h.min()
    if h.max() - lo < 1e-9:
        raise ValueError("flat part: not a coil spring")
    origin = c + u * lo                              # the bottom seat's centre
    h = h - lo
    rv = q - np.outer(q @ u, u)
    r = np.linalg.norm(rv, axis=1)
    od, idia = 2 * r.max(), 2 * r.min()
    wire = (od - idia) / 2
    R = (od - wire) / 2
    free = float(h.max())
    ref = rv[np.argmax(r)] / r.max()
    side = np.cross(u, ref)
    th = np.arctan2(rv @ side, rv @ ref)
    # turns from the volume: wire cross-section x the centreline's length (~2 pi R a turn; pitch adds < 1 %)
    turns_vol = volume(v, f) / (math.pi * wire * wire / 4) / (2 * math.pi * R)
    # the outer helix line: points on the wire's outside (dz ~ 0), sorted by height = sorted along the wire
    band = r > R + 0.47 * wire
    if band.sum() < 20:
        raise ValueError("no coils found: not a coil spring")
    order = np.argsort(h[band])
    hg = h[band][order]
    ang = np.unwrap(th[band][order])
    # smooth over about a tenth of a turn's points (the band's height noise is +-0.17 wire)
    w = max(3, len(hg) // 200)
    ker = np.ones(w) / w
    hg = np.convolve(hg, ker, "valid")
    ang = np.convolve(ang, ker, "valid")
    sign = 1.0 if ang[-1] >= ang[0] else -1.0
    ang = ang * sign
    hand = "right" if sign > 0 else "left"
    # turns: the centreline's whole angle (wire/2 .. free - wire/2) from the slices, ends extended by the local slope
    k = max(2, int(np.searchsorted(hg, hg[0] + wire)))
    s0 = (ang[k] - ang[0]) / (hg[k] - hg[0])
    s1 = (ang[-1] - ang[-1 - k]) / (hg[-1] - hg[-1 - k])
    a0 = ang[0] + s0 * (wire / 2 - hg[0])
    a1 = ang[-1] + s1 * (free - wire / 2 - hg[-1])
    turns = (a1 - a0) / (2 * math.pi)
    # local pitch over about one wire height: dead (closed) turns have pitch ~ wire, active ones more
    lp = np.full(len(hg), np.nan)
    for i in range(len(hg)):
        j0, j1 = max(0, i - k), min(len(hg) - 1, i + k)
        if ang[j1] > ang[j0]:
            lp[i] = 2 * math.pi * (hg[j1] - hg[j0]) / (ang[j1] - ang[j0])
    med = np.nanmedian(lp)
    act = lp > (wire + med) / 2
    if act.sum() < 3:
        act[:] = True
    ia = np.where(act)[0]
    slope, icpt = np.polyfit(hg[ia], ang[ia], 1)
    pitch = 2 * math.pi / slope
    z1, z2 = float(hg[ia[0]]), float(hg[ia[-1]])
    active = (z2 - z1) / pitch
    dead = max(0.0, (turns - active) / 2)
    phi1 = sign * (slope * z1 + icpt)            # the wire's angle round the axis where the active part starts
    return dict(axis=u.tolist(), origin=origin.tolist(), ref=ref.tolist(), od=od, wire=wire, free=free,
                turns=turns, turns_by_volume=turns_vol, active=active, dead=dead, pitch=pitch, hand=hand, z1=float(z1), z2=float(z2),
                phi1=float(math.remainder(phi1, 2 * math.pi)) % (2 * math.pi),
                solid=(turns + 1) * wire)
