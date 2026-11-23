"""Study 0303 prototype: a low-poly mannequin on the person's own rig (no Blender, NumPy only).

Every piece is a faceted loft or a small ball fixed to ONE of the 17 bones of ``core/person_rig`` (rigid skinning:
no stretching at the joints – the ball joints hide the gaps, as on an artist's wooden mannequin). The figure is made
in the rig's rest pose, so ``person_rig.skin(fig, verts, W, pose)`` (and Blender's Armature modifier with one vertex
group per bone) moves it exactly like today's person: walk paths, actions, IK, carrying.

``mannequin(height, outfit, helmet, plain)`` -> dict(verts (n,3), faces [list of index tuples], mat [per face],
bone [per vertex], W (n,17), materials [names]). Figure space: metres, z up, faces -y, right hand at -x.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from fresing_render.core import person_rig as R          # noqa: E402

COLOURS = {   # outfit -> (body / trousers, top, helmet, boots)   (the same colours as today's person's outfits)
    "WORKSHOP": ("lp_navy", "lp_navy", "lp_helmet_yellow", "lp_boots"),
    "OFFSHORE": ("lp_orange", "lp_orange", "lp_helmet_white", "lp_boots"),
    "OFFICE": ("lp_trousers", "lp_hivis", "lp_helmet_white", "lp_boots"),
}


class _Mesh:
    def __init__(self):
        self.v, self.f, self.m, self.b = [], [], [], []
        self.mats: list[str] = []

    def _mat(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def loft(self, rings, mat, bone, caps=True):
        """Rings of equal point count -> quads between them, n-gon caps."""
        mi = self._mat(mat)
        n = len(rings[0])
        base = len(self.v)
        for r in rings:
            self.v.extend(np.asarray(p, float) for p in r)
            self.b.extend([bone] * n)
        for j in range(len(rings) - 1):
            for i in range(n):
                a, c = base + j * n + i, base + j * n + (i + 1) % n
                self.f.append((a, c, c + n, a + n))
                self.m.append(mi)
        if caps:
            self.f.append(tuple(base + i for i in reversed(range(n))))
            self.m.append(mi)
            last = base + (len(rings) - 1) * n
            self.f.append(tuple(last + i for i in range(n)))
            self.m.append(mi)

    def ball(self, c, r, mat, bone, nu=6, nv=4, frame=None, sz=(1.0, 1.0, 1.0)):
        F = np.eye(3) if frame is None else frame
        rings = []
        for j in range(1, nv):
            lat = -math.pi / 2 + math.pi * j / nv
            rings.append([c + F @ (np.array((math.cos(lat) * math.cos(2 * math.pi * i / nu + 0.3),
                                              math.cos(lat) * math.sin(2 * math.pi * i / nu + 0.3),
                                              math.sin(lat))) * r * np.asarray(sz)) for i in range(nu)])
        mi = self._mat(mat)
        base = len(self.v)
        self.loft(rings, mat, bone, caps=False)
        bot, top = len(self.v), len(self.v) + 1
        self.v += [c + F @ (np.array((0, 0, -r)) * sz), c + F @ (np.array((0, 0, r)) * sz)]
        self.b += [bone, bone]
        last = base + (len(rings) - 1) * nu
        for i in range(nu):
            self.f.append((bot, base + (i + 1) % nu, base + i))
            self.m.append(mi)
            self.f.append((last + i, last + (i + 1) % nu, top))
            self.m.append(mi)


def _ring(c, X, Y, rx, ry, n, rot=0.0):
    return [c + X * (rx * math.cos(2 * math.pi * i / n + rot)) + Y * (ry * math.sin(2 * math.pi * i / n + rot))
            for i in range(n)]


def mannequin(height=1.75, outfit="WORKSHOP", helmet=True, plain=False) -> dict:
    fig = R.Figure(height)
    k = fig.k
    sk = fig.rest_fk
    legs, top, hat, boots = COLOURS.get(outfit, COLOURS["WORKSHOP"])
    skin = "lp_skin"
    if plain:
        legs = top = boots = skin = "lp_plain"
        hat = "lp_helmet_white"
    me = _Mesh()

    def seg(bone, stations, mat, n=6, caps=True, rot=math.pi / 6):
        head, Rb, tail = sk[bone]
        X, Y = Rb[:, 0], Rb[:, 1]
        rings = [_ring(head + (tail - head) * t + X * dx * k + Y * dy * k, X, Y, rx * k, ry * k, n, rot)
                 for t, rx, ry, dx, dy in [(s + (0.0, 0.0))[:5] if len(s) == 3 else s for s in stations]]
        me.loft(rings, mat, bone, caps)

    # torso: hips, belly, chest (six-sided blocks)
    seg("pelvis", ((-0.6, 0.105, 0.075), (-0.15, 0.16, 0.105), (0.5, 0.165, 0.105), (1.0, 0.145, 0.095)), legs)
    seg("spine", ((0.0, 0.14, 0.092), (1.0, 0.15, 0.1)), top)
    seg("chest", ((-0.05, 0.15, 0.1, 0, 0), (0.55, 0.19, 0.112, 0, -0.01), (0.92, 0.18, 0.1),
                  (1.04, 0.1, 0.07)), top)
    seg("neck", ((-0.2, 0.045, 0.045), (1.0, 0.042, 0.044)), skin, n=6)
    # head: an egg without a face, a little forward of the neck
    hh, Rh, ht = sk["head"]
    me.ball(hh + (ht - hh) * 0.5 + Rh[:, 1] * (-0.008 * k), 0.11 * k, skin, "head", nu=8, nv=5, frame=Rh,
            sz=(0.7, 0.86, 1.0))
    if helmet:
        c = hh + (ht - hh) * 0.66
        X, Y, Z = Rh[:, 0], Rh[:, 1], Rh[:, 2]
        dome = [_ring(c + Z * (dz * k), X, Y, rx * k, ry * k, 8, 0.0) for dz, rx, ry in
                ((-0.01, 0.112, 0.135), (0.0, 0.104, 0.124), (0.07, 0.09, 0.108), (0.115, 0.05, 0.06))]
        me.loft(dome, hat, "head")
        brim = [_ring(c + Z * (-0.012 * k) - Y * 0.02 * k, X, Y, rx * k, ry * k, 8, 0.0) for rx, ry in
                ((0.11, 0.13), (0.118, 0.16))]
        me.loft([brim[0], brim[1], [p + Z * 0.012 * k for p in brim[1]], [p + Z * 0.012 * k for p in brim[0]]],
                hat, "head", caps=False)
    for side in "lr":
        seg(f"{side}_arm", ((0.08, 0.05, 0.05), (0.92, 0.04, 0.042)), top)
        seg(f"{side}_forearm", ((0.1, 0.04, 0.041), (0.9, 0.031, 0.03)), top)
        # mitten hand: a flat block with a thumb
        seg(f"{side}_hand", ((0.08, 0.018, 0.035), (0.5, 0.016, 0.046), (0.95, 0.011, 0.035)), skin, n=4,
            rot=math.pi / 4)
        head, Rb, tail = sk[f"{side}_hand"]
        sd = 1.0 if side == "l" else -1.0
        tb = head + (tail - head) * 0.18 + Rb[:, 1] * (-0.04 * k) + Rb[:, 0] * (-0.006 * sd * k)
        d = (tail - head) / np.linalg.norm(tail - head)
        tt = tb + (d * 0.04 + Rb[:, 1] * -0.025) * k
        me.loft([_ring(tb, Rb[:, 0], Rb[:, 2], 0.011 * k, 0.011 * k, 4), _ring(tt, Rb[:, 0], Rb[:, 2], 0.008 * k,
                                                                              0.008 * k, 4)], skin, f"{side}_hand")
        seg(f"{side}_thigh", ((0.05, 0.08, 0.082), (0.92, 0.058, 0.06)), legs)
        seg(f"{side}_shin", ((0.08, 0.055, 0.056), (0.3, 0.058, 0.06, 0, 0.006), (0.9, 0.042, 0.043)), legs)
        # boot: a wedge from heel to toe
        fh, Rf, _ft = sk[f"{side}_foot"]
        X, F, U = Rf[:, 0], -Rf[:, 1], Rf[:, 2]
        rings = []
        for s, w, z0, z1 in ((-0.065, 0.038, -0.085, 0.02), (0.02, 0.046, -0.085, 0.04), (0.12, 0.05, -0.085, -0.02),
                             (0.2, 0.042, -0.085, -0.045), (0.225, 0.02, -0.08, -0.06)):
            c = fh + F * (s * k) + U * ((z0 + z1) / 2 * k)
            rings.append([c + X * (sx * w * k) + U * (sz * (z1 - z0) / 2 * k) for sx, sz in
                          ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        me.loft(rings, boots, f"{side}_foot")
        # ball joints (each on the bone below it: it turns about its own centre)
        for bone, r in ((f"{side}_arm", 0.055), (f"{side}_forearm", 0.04), (f"{side}_hand", 0.026),
                        (f"{side}_shin", 0.052), (f"{side}_foot", 0.04)):
            mat = top if "arm" in bone else (skin if "hand" in bone else legs)
            me.ball(sk[bone][0], r * k, mat, bone, nu=6, nv=4)
    me.ball(sk["spine"][0], 0.12 * k, legs, "spine", nu=6, nv=4, sz=(1.15, 0.8, 0.6))
    verts = np.asarray(me.v)
    bones = np.asarray([R.BONES.index(b) for b in me.b])
    W = np.zeros((len(verts), len(R.BONES)))
    W[np.arange(len(verts)), bones] = 1.0
    return dict(verts=verts, faces=me.f, mat=np.asarray(me.m), bone=bones, W=W, materials=me.mats)


def triangles(faces) -> int:
    return sum(len(f) - 2 for f in faces)


if __name__ == "__main__":
    for plain in (False, True):
        d = mannequin(plain=plain)
        print("plain" if plain else "worker", "points", len(d["verts"]), "triangles", triangles(d["faces"]),
              "z", d["verts"][:, 2].min().round(3), d["verts"][:, 2].max().round(3))
