"""Mobile telescopic crane (all-terrain) AT-40 … AT-500 (task 0191): the STEP assembly of a class.

Tree (sub-assembly names = what the rig's joints move; ``classes.mobile_layout`` has every point)::

    AT-100
      CARRIER.ASM               chassis, carrier cab, wheels, outrigger boxes, slewing ring (stands still)
      OUTRIGGER BEAM FL.ASM     stage 1 > OUTRIGGER BEAM FL 2.ASM (stage 2 + jack housing) > JACK FL.ASM (rod, pad)
      … FR, RL, RR
      SUPERSTRUCTURE.ASM        turntable, frame, lugs, operator's cab, winch, COUNTERWEIGHT.ASM
        BOOM BASE.ASM           base section (luff) > BOOM SECTION 2.ASM > … > BOOM SECTION N.ASM (head, sheave)
                                  > HOOK SWING.ASM (hoist rope) > HOOK BLOCK.ASM (block, hook)
      LUFF CYLINDER BARREL, LUFF CYLINDER ROD   (top level: the app's cylinder moves them)
"""

from __future__ import annotations

import numpy as np

from ..demo_model import geom as g
from ..demo_model.geom import Asm, Part
from . import classes as C
from . import common as K


def build(c: C.Mobile):
    L = C.layout(c)
    p = L.pts
    kit = K.Kit()
    root = Asm(c.name)
    W = c.width
    deck, front, rear = p["deck"], p["front"], p["rear"]
    xp, zp = p["xp"], p["zp"]
    # ---- carrier ------------------------------------------------------------------------------------------------
    car = Asm("CARRIER.ASM")
    K.put(root, car)
    tw = 0.72 * c.wheel_r
    frame_half = W / 2 - tw - 70.0
    bw = p["beam_w"]
    bh = 1.25 * bw
    # the outrigger beams run through the frame (task 0214): frame + boxes one solid; the beams' channels cut into the
    # deck's underside (a skin of 25 mm stays on top: the deck stays one solid)
    chassis = K.frame_with_boxes(g.box(rear + 150.0, -frame_half, deck - 520.0, front - rear - 900.0, 2 * frame_half,
                                       380.0), p["out_x"], bw, bh, p["beam_z"], W)
    below = g.box(rear - 10.0, -W, deck - 1000.0, front - rear + 20.0, 2 * W, 1000.0 - 25.0)
    deck_plate = g.cut(g.box(rear, -W / 2, deck - 140.0, front - rear - 2300.0, W, 140.0),
                       *[g.common(h, below) for h in K.box_shapes(p["out_x"], bw, bh, p["beam_z"], W)[1]])
    K.put(car, Part("CHASSIS FRAME", chassis, K.CARRIER_GREY))
    K.put(car, Part("CARRIER DECK", deck_plate, K.CARRIER_GREY))
    cab_x0 = front - 2300.0
    cab = g.fuse(g.box(cab_x0, W / 2 - 1350.0, deck - 520.0, 2150.0, 1350.0, p["cab_top"] - deck + 520.0 - 150.0),
                 g.box(cab_x0 + 150.0, W / 2 - 1300.0, p["cab_top"] - 150.0, 1700.0, 1250.0, 150.0))
    glass = g.box(front - 160.0, W / 2 - 1250.0, deck + 300.0, 20.0, 1150.0, p["cab_top"] - deck - 600.0)
    K.put(car, Part("CARRIER CAB", g.cut(cab, g.box(front - 170.0, W / 2 - 1255, deck + 295, 40, 1160,
                                                     p["cab_top"] - deck - 590)), K.CAB_WHITE))
    K.put(car, Part("CARRIER CAB WINDOW", glass, K.GLASS))
    bonnet = g.box(cab_x0, -W / 2, deck - 520.0, 2150.0, W - 1400.0, 820.0)
    K.put(car, Part("ENGINE BONNET", bonnet, K.CARRIER_GREY))
    bumper = g.box(front - 150.0, -W / 2, 380.0, 150.0, W, 420.0)
    K.put(car, Part("FRONT BUMPER", bumper, K.CARRIER_GREY))
    ring = g.cyl(0.33 * W, 80.0, (0, 0, deck), (0, 0, 1))
    K.put(car, Part("SLEWING RING", ring, K.STEEL))
    K.wheels(car, kit, p["axles"], c.wheel_r, W / 2)
    # ---- outriggers -------------------------------------------------------------------------------------------
    pad_r = C.mobile_pad_r(c)
    K.outrigger_set(root, kit, "OUTRIGGER", p["out_x"], bw, p["pad_in"], p["out_ext"] / C.STAGES, p["beam_z"], bw, bh,
                    p["pad_z0"], pad_r, car, W, boxes=False)
    # ---- superstructure ---------------------------------------------------------------------------------------
    sup = Asm("SUPERSTRUCTURE.ASM")
    K.put(root, sup)
    tt = p["turn_top"]
    K.put(sup, Part("TURNTABLE", g.cyl(0.31 * W, tt - deck - 80.0, (0, 0, deck + 80.0), (0, 0, 1)), K.BOOM_YELLOW))
    cyl = L.cylinders[0]
    bpin = np.array(cyl["barrel_pin"]["point"])
    rb = cyl["fit"]["barrel_r"]
    frame_top = tt + 300.0
    fx0 = -c.cw_x + 300.0
    fx1 = bpin[0] + 2.2 * rb
    lug_y = c.boom_w / 2 + 40.0
    K.put(sup, Part("UPPER FRAME", g.box(fx0, -lug_y - 160.0, tt, fx1 - fx0, 2 * lug_y + 320.0, frame_top - tt),
                    K.BOOM_YELLOW))
    # boom pivot lugs (outside the boom), the luff pin through them and the boom
    lug_t = 60.0
    pin_r = 0.09 * c.boom_h
    for sy in (-1, 1):
        y0 = lug_y if sy > 0 else -lug_y - lug_t
        lug = g.fuse(g.box(xp - 1.4 * pin_r - 200.0, y0, frame_top - 1.0, 2.8 * pin_r + 400.0, lug_t, zp - frame_top),
                     g.cyl(2.2 * pin_r, lug_t, (xp, y0, zp), (0, 1, 0)))
        K.put(sup, Part("BOOM PIVOT LUG", g.cut(lug, g.cyl(pin_r + 1.0, lug_t + 2, (xp, y0 - 1, zp), (0, 1, 0))),
                        K.BOOM_YELLOW))
    K.put(sup, Part("LUFF PIN", K.pin_across((xp, 0, zp), pin_r, lug_y + lug_t + 40.0), K.STEEL))
    # barrel lugs for the luff cylinder
    ew = 1.6 * cyl["fit"]["rod_r"]
    for shp in K.lug_pair(bpin, (0, 0, -1), ew + 10.0, 40.0, 1.3 * cyl["fit"]["rod_r"], bpin[2] - frame_top + 1.0,
                          0.45 * cyl["fit"]["rod_r"] + 1.0):
        K.put(sup, Part("LUFF CYLINDER LUG", shp, K.BOOM_YELLOW))
    # operator's cab on the right (-y), clear of the boom and lugs
    oc_y1 = -(lug_y + lug_t + 150.0)
    oc_y0 = -W / 2 + 50.0
    oc = g.box(xp + 300.0, oc_y0, tt + 80.0, 2000.0, oc_y1 - oc_y0, 1900.0)
    K.put(sup, Part("OPERATOR CAB", g.cut(oc, g.box(xp + 2280.0, oc_y0 + 80, tt + 900, 40.0, oc_y1 - oc_y0 - 160,
                                                     900.0)), K.CAB_WHITE))
    K.put(sup, Part("OPERATOR CAB WINDOW", g.box(xp + 2290.0, oc_y0 + 85, tt + 905, 15.0, oc_y1 - oc_y0 - 170, 890.0),
                    K.GLASS))
    # hoist winch behind the boom's foot
    secs = p["sections"]
    l_cw = 0.45 * c.cw_x + 600.0
    wx, _wz, wr = p["winch"]                           # between the counterweight and the boom's foot, low
    K.put(sup, Part("HOIST WINCH DRUM", g.cyl(wr, 2 * lug_y - 60, (wx, -lug_y + 30, frame_top + wr + 60.0),
                                             (0, 1, 0)), K.STEEL))
    for sy in (-1, 1):
        y0 = lug_y - 20 if sy > 0 else -lug_y - 40
        K.put(sup, Part("WINCH STAND", g.box(wx - wr - 80, y0, frame_top - 1, 2 * wr + 160, 60.0, wr + 140.0),
                        K.BOOM_YELLOW))
    # counterweight
    cwa = Asm("COUNTERWEIGHT.ASM")
    K.put(sup, cwa)
    w_cw = W - 300.0
    h_cw = max(250.0, max(c.counterweights) / 7.85e-9 / (w_cw * l_cw))
    K.put(cwa, Part("COUNTERWEIGHT", g.box(-c.cw_x - l_cw / 2, -w_cw / 2, frame_top + 1.0, l_cw, w_cw, h_cw),
                    K.COUNTERWEIGHT))
    p["cw_box"] = (-c.cw_x - l_cw / 2, -c.cw_x + l_cw / 2, h_cw)
    # ---- boom ---------------------------------------------------------------------------------------------------
    pv = np.array([xp, 0.0, zp])
    u = np.array([1.0, 0.0, 0.0])
    n = np.array([0.0, 0.0, 1.0])
    parent = sup
    tip_asm = None
    rs = p["sheave_r"]
    for sct in secs:
        k = sct["k"]
        a = Asm("BOOM BASE.ASM" if k == 1 else f"BOOM SECTION {k}.ASM")
        K.put(parent, a)
        last = k == c.sections
        shape = K.box_tube(pv, u, n, sct["a0"], sct["a1"], sct["w"], sct["h"], c.wall, closed=last)
        if k == 1:
            # rod lugs under the base section; a bore for the luff pin
            rpin = np.array(cyl["rod_pin"]["point"])
            lugs = K.lug_pair(rpin, (0, 0, 1), ew + 10.0, 40.0, 1.3 * cyl["fit"]["rod_r"],
                              zp - c.boom_h / 2 - rpin[2] + c.wall, 0.45 * cyl["fit"]["rod_r"] + 1.0)
            foot = g.box(xp + sct["a0"], -sct["w"] / 2, zp - sct["h"] / 2, -sct["a0"] + 2.6 * pin_r, sct["w"], sct["h"])
            shape = g.cut(g.fuse(shape, foot, *lugs), K.pin_across(pv, pin_r + 2.0, lug_y))
        K.put(a, Part("BOOM BASE SECTION" if k == 1 else f"BOOM SECTION {k}", shape, K.BOOM_YELLOW))
        if last:
            tip_asm = a
            sh = np.array(p["sheave"])
            head_len = sh[0] - (xp + sct["a1"]) + 0.8 * rs
            hw = 0.5 * sct["w"]
            plates = []
            for sy in (-1, 1):
                y0 = hw * 0.5 + 10 if sy > 0 else -hw * 0.5 - 10 - 40.0
                plates.append(g.fuse(g.box(xp + sct["a1"] - 1.0, y0, sh[2] - 0.7 * sct["h"] / 2, head_len, 40.0,
                                           0.7 * sct["h"]),
                                     g.cyl(0.85 * rs, 40.0, (sh[0], y0, sh[2]), (0, 1, 0))))
            bridge = g.box(xp + sct["a1"] - 1.0, -hw * 0.5 - 50.0, sh[2] + 0.7 * sct["h"] / 2 - 40.0, head_len - 1.6 * rs,
                           hw + 100.0, 40.0)
            K.put(a, Part("BOOM HEAD", g.fuse(*plates, bridge), K.BOOM_YELLOW))
            K.put(a, K.sheave_part("HEAD SHEAVE", sh, rs, hw * 0.5))
        parent = a
    # ---- hook ---------------------------------------------------------------------------------------------------
    rope_r = max(7.0, 0.035 * rs)
    K.hook_tree(tip_asm, p["sheave"], rs, p["d0"], c.block_h, p["block_w"], rope_r, swings=1)
    # ---- luff cylinder (top level) --------------------------------------------------------------------------------
    barrel, rod = K.cylinder_parts("LUFF CYLINDER BARREL", "LUFF CYLINDER ROD", cyl["barrel_pin"]["point"],
                                   cyl["rod_pin"]["point"], cyl["fit"], eye_w=ew)
    K.put(root, barrel)
    K.put(root, rod)
    return root, L
