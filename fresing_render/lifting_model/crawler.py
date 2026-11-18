"""Crawler lattice-boom crane CC-100 … CC-1600 (task 0191): the STEP assembly of a class.

Tree (sub-assembly names = what the rig's joints move; ``classes.crawler_layout`` has every point)::

    CC-300
      CRANE.ASM                 (Travel) everything that drives along
        LOWER WORKS.ASM         carbody, track frames, sprockets, idlers, TRACK LINK L/R, TRACK SHOE L/R (the app's
                                tracks run them on Travel)
        UPPER WORKS.ASM         (Slew) turntable, frame, cab, machinery house, gantry, COUNTERWEIGHT.ASM
          LATTICE BOOM.ASM      (Luff) foot, chords + lacing, head with sheave, pendant lugs [, jib strut]
            [LUFFING JIB.ASM]   (Jib) on the boom head
              HOOK SWING.ASM > [HOOK SWING 2.ASM >] hoist rope + HOOK BLOCK.ASM
      BOOM PENDANT BAR/ROD L/R, [JIB PENDANT BAR/ROD L/R]   (top level: the app's cylinders keep them on their pins)

The pendants stand for the boom's luffing ropes: a bar and a rod that slide in each other as the boom luffs.
"""

from __future__ import annotations

import math

import numpy as np

from ..demo_model import geom as g
from ..demo_model.geom import Asm, Part
from . import classes as C
from . import common as K


def _link_shapes(pp: float, hh: float, s: float, sw: float):
    """Inner and outer chain link (local: origin between its two pins, x along pin -> pin, y across, z outward)."""
    pr = 0.16 * pp                                       # pin radius
    t = 0.06 * sw                                        # plate thickness

    def plates(y0, y1, holes):
        # straight plates (round ends cost ~half the track's triangles); the hinges stay round
        L = 1.25 * pp if holes else pp + 1.6 * pr
        sh = g.box(-L / 2, y0, -hh, L, y1 - y0, 2 * hh)
        if holes:
            sh = g.cut(sh, g.cyl(pr + 1, 4 * s, (-pp / 2, -2 * s, 0), (0, 1, 0)),
                       g.cyl(pr + 1, 4 * s, (pp / 2, -2 * s, 0), (0, 1, 0)))
        return sh
    bush = [g.cut(g.cyl(pr + 0.45 * pr, 2 * (s - t), (x, -(s - t), 0), (0, 1, 0)),
                  g.cyl(pr + 1, 2 * s, (x, -s, 0), (0, 1, 0))) for x in (-pp / 2, pp / 2)]
    inner = g.fuse(plates(-s, -(s - t), True), plates(s - t, s, True), *bush)
    outer = g.fuse(plates(-(s + 1.1 * t), -(s + 0.1 * t), False), plates(s + 0.1 * t, s + 1.1 * t, False),
                   g.cyl(pr, 2 * (s + 1.1 * t), (-pp / 2, -(s + 1.1 * t), 0), (0, 1, 0)),
                   g.cyl(pr, 2 * (s + 1.1 * t), (pp / 2, -(s + 1.1 * t), 0), (0, 1, 0)))
    return inner, outer, pr


def _shoe_shape(pp: float, hh: float, sw: float, st: float):
    plate_t = 0.6 * st
    plate = g.box(-pp / 2 + 6.0, -sw / 2, hh, pp - 12.0, sw, plate_t)
    grouser = g.box(-0.12 * pp, -sw / 2, hh + plate_t - 1.0, 0.24 * pp, sw, st - plate_t + 1.0)
    return g.fuse(plate, grouser)


def _sprocket_shape(R: float, nt: int, hh: float, pr: float, width: float, bore: float):
    """A wheel inside the chain's bushes (its rim stays under the bushes; no teeth: the file stays small)."""
    disc = g.cyl(R - 1.45 * pr - 10.0, width, (0, -width / 2, 0), (0, 1, 0))
    hub = g.cyl(0.32 * R, 1.6 * width, (0, -0.8 * width, 0), (0, 1, 0))
    return g.cut(g.fuse(disc, hub), g.cyl(bore, 4 * width, (0, -2 * width, 0), (0, 1, 0)))


def _track(lower: Asm, kit: K.Kit, c: C.Crawler, tr: dict, side: str, yc: float) -> None:
    pp, hh, R, a, zs = c.pitch, tr["hh"], tr["R"], tr["a"], tr["zs"]
    sw = c.shoe_w
    s = 0.32 * sw
    # each side its own shapes: the STEP writer gives one shape one name (the left links would be called "R")
    inner, outer, pr = _link_shapes(pp, hh, s, sw)
    shoe_shape = _shoe_shape(pp, hh, sw, tr["shoe_t"])
    li = Part(f"TRACK LINK {side}", inner, K.TRACK_DARK)
    lo = Part(f"TRACK LINK {side}", outer, K.TRACK_DARK)
    shoe = Part(f"TRACK SHOE {side}", shoe_shape, K.TRACK_DARK)
    pins = tr["pins"]
    n = len(pins)
    for k in range(n):
        p0, p1 = np.array(pins[k]), np.array(pins[(k + 1) % n])
        mid = (p0 + p1) / 2
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        o = np.array([-d[1], d[0]])
        ref = np.array([max(-a, min(a, mid[0])), zs])
        if (mid - ref) @ o < 0:
            o = -o
        M = g.Frame((mid[0], yc, mid[1]), (d[0], 0.0, d[1]), (o[0], 0.0, o[1]))
        K.put(lower, li if k % 2 == 0 else lo, M)
        K.put(lower, shoe, M)
    width = 0.42 * s
    shaft_r = 0.12 * R
    spr = _sprocket_shape(R, c.teeth, hh, pr, width, shaft_r + 2.0)
    K.put(lower, Part(f"DRIVE SPROCKET {side}", g.xform(spr, g.T(-a, yc, zs)), K.STEEL))
    K.put(lower, Part(f"IDLER {side}", g.xform(spr, g.T(a, yc, zs)), K.STEEL))
    # the track frame between the runs, a slot round each wheel; the shafts through it
    fw = s + 0.1 * sw
    fz = R - hh - 0.25 * pp
    frame = g.box(-a, yc - fw, zs - fz, 2 * a, 2 * fw, 2 * fz)
    slot_r = R + 0.35 * hh + 40.0
    slots = [g.cyl(slot_r, width + 80.0, (x, yc - width / 2 - 40.0, zs), (0, 1, 0)) for x in (-a, a)]
    K.put(lower, Part(f"TRACK FRAME {side}", g.cut(frame, *slots), K.CARRIER_GREY))
    for x in (-a, a):
        K.put(lower, Part("SPROCKET SHAFT", g.cyl(shaft_r, 2 * fw, (x, yc - fw, zs), (0, 1, 0)), K.STEEL))


def build(c: C.Crawler):
    L = C.layout(c)
    p = L.pts
    tr = p["track"]
    kit = K.Kit()
    root = Asm(c.name)
    crane = Asm("CRANE.ASM")
    K.put(root, crane)
    W = c.boom_w
    xp, zp, top, tt = p["xp"], p["zp"], p["top"], p["turn_top"]
    # ---- lower works ----------------------------------------------------------------------------------------------
    low = Asm("LOWER WORKS.ASM")
    K.put(crane, low)
    for side, yc in (("L", c.gauge / 2), ("R", -c.gauge / 2)):
        _track(low, kit, c, tr, side, yc)
    sw = c.shoe_w
    fw = 0.32 * sw + 0.1 * sw
    zs, R, hh = tr["zs"], tr["R"], tr["hh"]
    fz = R - hh - 0.25 * c.pitch
    inner_y = c.gauge / 2 - sw / 2 - 40.0
    body = g.box(-0.3 * tr["contact"], -inner_y, zs - fz + 1.0, 0.6 * tr["contact"], 2 * inner_y, top - (zs - fz))
    beams = [g.box(x - 0.08 * tr["contact"], -(c.gauge / 2 - fw) - 1.0, zs - 0.6 * fz, 0.16 * tr["contact"],
                   c.gauge - 2 * fw + 2.0, 1.2 * fz) for x in (-0.22 * tr["contact"], 0.22 * tr["contact"])]
    K.put(low, Part("CARBODY", g.fuse(body, *beams), K.CARRIER_GREY))
    K.put(low, Part("SLEWING RING", g.cyl(0.26 * c.gauge, 60.0, (0, 0, top), (0, 0, 1)), K.STEEL))
    # ---- upper works ------------------------------------------------------------------------------------------
    up = Asm("UPPER WORKS.ASM")
    K.put(crane, up)
    K.put(up, Part("TURNTABLE", g.cyl(0.25 * c.gauge, tt - top - 60.0, (0, 0, top + 60.0), (0, 0, 1)), K.CARRIER_GREY))
    frame_top = tt + 300.0
    lug_y = W / 2 + 60.0
    cw_l = min(0.5 * c.cw_x, 0.35 * c.cw_x + 900.0)
    fx0 = -c.cw_x + 0.3 * cw_l
    K.put(up, Part("UPPER FRAME", g.box(fx0, -lug_y - 200.0, tt, xp + 0.3 * W - fx0, 2 * lug_y + 400.0, 300.0),
                   K.BOOM_YELLOW))
    pin_r = 0.07 * W
    for sy in (-1, 1):
        y0 = lug_y if sy > 0 else -lug_y - 100.0
        lug = g.fuse(g.box(xp - 2.2 * pin_r, y0, frame_top - 1.0, 4.4 * pin_r, 100.0, zp - frame_top),
                     g.cyl(2.2 * pin_r, 100.0, (xp, y0, zp), (0, 1, 0)))
        K.put(up, Part("BOOM FOOT LUG", g.cut(lug, g.cyl(pin_r + 1, 102.0, (xp, y0 - 1, zp), (0, 1, 0))),
                       K.BOOM_YELLOW))
    K.put(up, Part("BOOM FOOT PIN", K.pin_across((xp, 0, zp), pin_r, lug_y + 140.0), K.STEEL))
    house_x1 = xp - 0.75 * W - 300.0
    house_x0 = -c.cw_x + cw_l / 2 + 100.0
    house_h = 0.5 * W + 1400.0
    K.put(up, Part("MACHINERY HOUSE", g.box(house_x0, -lug_y - 150.0, frame_top - 1.0, house_x1 - house_x0,
                                            2 * lug_y + 300.0, house_h), K.CAB_WHITE))
    cab_y0 = lug_y + 300.0
    cab = g.box(xp - 0.6 * W - 600.0, cab_y0, frame_top - 1.0, 2200.0, 1300.0, 2000.0)
    K.put(up, Part("OPERATOR CAB", g.cut(cab, g.box(xp - 0.6 * W + 1560, cab_y0 + 80, frame_top + 900, 60, 1140,
                                                     900)), K.CAB_WHITE))
    K.put(up, Part("OPERATOR CAB WINDOW", g.box(xp - 0.6 * W + 1570, cab_y0 + 85, frame_top + 905, 20, 1130, 890),
                   K.GLASS))
    K.put(up, Part("CAB PLATFORM", g.box(xp - 0.6 * W - 600.0, lug_y + 99.0, frame_top - 120.0, 2200.0,
                                         cab_y0 - lug_y - 98.0, 120.0), K.BOOM_YELLOW))
    # gantry: lug plates down from each pendant pin, a cross tie behind the pins
    gpt = np.array(p["gantry"])
    cyls = {cy["name"]: cy for cy in L.cylinders}
    bp = cyls["Boom pendant L"]
    rr = bp["fit"]["rod_r"]
    ew = 1.6 * rr
    pend_y = bp["barrel_pin"]["point"][1]
    shapes = []
    for sy in (-1, 1):
        pin = gpt + np.array([0.0, sy * pend_y, 0.0])
        shapes += K.lug_pair(pin, (0, 0, -1), ew + 20.0, 90.0, 1.6 * rr, pin[2] - frame_top + 1.0, 0.45 * rr + 1.0)
    span = pend_y + ew / 2 + 120.0
    shapes.append(g.box(gpt[0] - 1.2 * rr, -span, frame_top + 0.25 * (gpt[2] - frame_top), 2.4 * rr, 2 * span,
                        2.4 * rr))
    shapes.append(g.box(gpt[0] - 1.2 * rr, -span, gpt[2] - 1.6 * rr - 3.4 * rr, 2.4 * rr, 2 * span, 2.4 * rr))
    K.put(up, Part("GANTRY", K.one(shapes[-1], *shapes[:-1]), K.BOOM_YELLOW))
    cwa = Asm("COUNTERWEIGHT.ASM")
    K.put(up, cwa)
    cw_w = min(0.85 * c.gauge, c.gauge - 400.0)
    cw_h = max(c.counterweights) / 7.85e-9 / (cw_w * cw_l)
    K.put(cwa, Part("COUNTERWEIGHT", g.box(-c.cw_x - cw_l / 2, -cw_w / 2, frame_top - 1.0, cw_l, cw_w, cw_h),
                    K.COUNTERWEIGHT))
    # ---- lattice boom -----------------------------------------------------------------------------------------
    boom = Asm("LATTICE BOOM.ASM")
    K.put(up, boom)
    th = c.luff_cad
    u, n = C.boom_dir(th), C.boom_up(th)
    y = np.array([0.0, 1.0, 0.0])
    pv = np.array([xp, 0.0, zp])
    Lb = c.boom_cad
    chord_r = 0.045 * W
    K.lattice(boom, kit, "BOOM", pv, u, n, W, 0.25 * W, Lb - 0.75 * W, chord_r, 0.018 * W)
    foot = g.cut(K.solid_box(pv, u, n, -1.5 * pin_r, 0.30 * W, W + 2 * chord_r, W + 2 * chord_r),
                 K.pin_across(pv, pin_r + 2.0, W))
    K.put(boom, Part("BOOM FOOT", foot, K.BOOM_YELLOW))
    head = np.array(p["boom_head"])
    rs = p["sheave_r"]
    hw = 0.3 * W
    plates = [K.solid_box(pv, u, n, Lb - 0.80 * W, Lb + 0.2 * rs, 40.0, 0.9 * W, dy=sy * (0.5 * hw + 20.0))
              for sy in (-1, 1)]
    cap = K.solid_box(pv, u, n, Lb - 0.80 * W, Lb - 0.70 * W, W + 2 * chord_r, W + 2 * chord_r)
    tl = np.array(p["tip_lug"])
    lug_shapes = []
    for sy in (-1, 1):
        pin = tl + sy * pend_y * y
        lug_shapes += K.lug_pair(pin, -n, ew + 20.0, 60.0, 1.5 * rr, float((tl - head) @ n) + 0.45 * W, 0.45 * rr + 1)
    tl_n = float((tl - pv) @ n)
    tie = K.solid_box(pv, u, n, Lb - 0.80 * W, Lb - 0.70 * W, 2 * (pend_y + ew / 2 + 80.0),
                      tl_n - 1.6 * rr - 0.4 * W, dn=(tl_n - 1.6 * rr + 0.4 * W) / 2)
    K.put(boom, Part("BOOM HEAD", K.one(cap, *plates, tie, *lug_shapes), K.BOOM_YELLOW))
    K.put(boom, K.sheave_part("HEAD SHEAVE", head, rs, 0.8 * hw))
    tip = boom
    swings = 1
    if c.jib_cad > 0:
        Wj = p["jib_w"]
        jp = np.array(p["jib_pin"])
        st = np.array(p["strut"])
        jcy = cyls["Jib pendant L"]
        jrr = jcy["fit"]["rod_r"]
        jew = 1.6 * jrr
        jy = jcy["barrel_pin"]["point"][1]
        # jib strut (on the boom head): posts up to the jib pendants' upper pins, a cross tie at the top
        sshapes = []
        foot = head - 0.6 * W * u - 0.3 * W * n
        for sy in (-1, 1):
            pin = st + sy * jy * y
            sshapes.append(K.solid_box(foot, unit(st - foot), np.cross(y, unit(st - foot)), 0.0,
                                       float(np.linalg.norm(st - foot)) - 2.0 * jrr, jew + 140.0, 2.0 * jrr,
                                       dy=sy * jy))      # (the pair is symmetric: either sign of y is right)
            sshapes += K.lug_pair(pin, foot - st, jew + 20.0, 50.0, 1.5 * jrr, 3.0 * jrr, 0.45 * jrr + 1)
        sshapes.append(K.solid_box(foot, u, n, -1.4 * jrr, 1.4 * jrr, 2 * (jy + jew / 2 + 80.0), 2.8 * jrr))
        K.put(boom, Part("JIB STRUT", K.one(sshapes[-1], *sshapes[:-1]), K.BOOM_YELLOW))
        # jib foot lugs under the boom head
        jpin_r = 0.07 * Wj
        jl = []
        for sy in (-1, 1):
            y0 = Wj / 2 + 30.0 if sy > 0 else -Wj / 2 - 30.0 - 80.0
            c0 = jp + np.array([0.0, y0, 0.0])
            jl.append(g.fuse(g.cyl(2.2 * jpin_r, 80.0, c0, y),
                             K.solid_box(jp, n, u, 0.0, float((head - jp) @ n), 80.0, 4.4 * jpin_r,
                                         dy=y0 + 40.0)))
        for lg in jl:
            K.put(boom, Part("JIB FOOT LUG", g.cut(lg, K.pin_across(jp, jpin_r + 1, W)), K.BOOM_YELLOW))
        K.put(boom, Part("JIB FOOT PIN", K.pin_across(jp, jpin_r, Wj / 2 + 150.0), K.STEEL))
        jib = Asm("LUFFING JIB.ASM")
        K.put(boom, jib)
        ju, jn = C.boom_dir(th + c.jib_angle), C.boom_up(th + c.jib_angle)
        Lj = c.jib_cad
        jcr = 0.045 * Wj
        K.lattice(jib, kit, "JIB", jp, ju, jn, Wj, 0.30 * Wj, Lj - 0.75 * Wj, jcr, 0.02 * Wj)
        jfoot = g.cut(K.solid_box(jp, ju, jn, -1.5 * jpin_r, 0.35 * Wj, Wj + 2 * jcr, Wj + 2 * jcr),
                      K.pin_across(jp, jpin_r + 2.0, Wj))
        K.put(jib, Part("JIB FOOT", jfoot, K.BOOM_YELLOW))
        jtip = np.array(p["jib_tip"])
        rsj = p["jib_sheave_r"]
        hwj = 0.3 * Wj
        jcap = K.solid_box(jp, ju, jn, Lj - 0.80 * Wj, Lj - 0.70 * Wj, Wj + 2 * jcr, Wj + 2 * jcr)
        jplates = [K.solid_box(jp, ju, jn, Lj - 0.80 * Wj, Lj + 0.2 * rsj, 30.0, 0.9 * Wj, dy=sy * (0.5 * hwj + 15.0))
                   for sy in (-1, 1)]
        jlg = np.array(p["jib_lug"])
        jlugs = []
        for sy in (-1, 1):
            pin = jlg + sy * jy * y
            jlugs += K.lug_pair(pin, -jn, jew + 20.0, 40.0, 1.5 * jrr, float((jlg - jtip) @ jn) + 0.45 * Wj,
                                0.45 * jrr + 1)
        jl_n = float((jlg - jp) @ jn)
        jtie = K.solid_box(jp, ju, jn, Lj - 0.80 * Wj, Lj - 0.70 * Wj, 2 * (jy + jew / 2 + 60.0),
                           jl_n - 1.6 * jrr - 0.4 * Wj, dn=(jl_n - 1.6 * jrr + 0.4 * Wj) / 2)
        K.put(jib, Part("JIB HEAD", K.one(jcap, *jplates, jtie, *jlugs), K.BOOM_YELLOW))
        K.put(jib, K.sheave_part("JIB HEAD SHEAVE", jtip, rsj, 0.8 * hwj))
        tip = jib
        swings = 2
    # ---- hook -----------------------------------------------------------------------------------------------------
    hs = p["hook_sheave_r"]
    K.hook_tree(tip, p["sheave"], hs, p["d0"], c.block_h, 0.45 * W + 300.0, max(10.0, 0.03 * hs), swings=swings)
    # ---- pendants (top level) ---------------------------------------------------------------------------------
    for cy in L.cylinders:
        bar, rod = K.cylinder_parts(cy["barrel"][0], cy["rod"][0], cy["barrel_pin"]["point"], cy["rod_pin"]["point"],
                                    cy["fit"], barrel_color=K.ROPE)
        K.put(root, bar)
        K.put(root, rod)
    return root, L


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)
