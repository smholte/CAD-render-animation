"""Knuckle-boom (loader) crane on a truck, KB-20 … KB-200 (task 0191): the STEP assembly of a class.

Tree (sub-assembly names = what the rig's joints move; ``classes.knuckle_layout`` has every point)::

    KB-50
      TRUCK.ASM                 chassis, cab (towards -x), bed, wheels, stabiliser boxes, crane base
      STABILISER BEAM FL.ASM    stage 1 > STABILISER BEAM FL 2.ASM > STABILISER LEG FL.ASM   (… FR, RL, RR)
      COLUMN.ASM                (Slew) the column
        MAIN BOOM.ASM           (Main boom)
          OUTER BOOM.ASM        (Knuckle) > EXTENSION 1.ASM > … > EXTENSION N.ASM (tip with sheave)
                                  > HOOK SWING.ASM > HOOK SWING 2.ASM > rope + HOOK BLOCK.ASM
      MAIN CYLINDER BARREL/ROD, KNUCKLE CYLINDER BARREL/ROD   (top level: the app's cylinders move them)
"""

from __future__ import annotations

import numpy as np

from ..demo_model import geom as g
from ..demo_model.geom import Asm, Part
from . import classes as C
from . import common as K


def build(c: C.Knuckle):
    L = C.layout(c)
    p = L.pts
    kit = K.Kit()
    root = Asm(c.name)
    W = c.width
    deck, front, rear = p["deck"], p["front"], p["rear"]
    # ---- truck --------------------------------------------------------------------------------------------------
    tr = Asm("TRUCK.ASM")
    K.put(root, tr)
    tw = 0.72 * c.wheel_r
    fh = W / 2 - tw - 80.0
    bw = p["beam_w"]
    # the stabiliser beams run through the chassis (task 0214): chassis + boxes one solid
    K.put(tr, Part("TRUCK CHASSIS", K.frame_with_boxes(g.box(front + 300.0, -fh, deck - 330.0, rear - front - 300.0,
                                                             2 * fh, 330.0), p["out_x"], bw, 1.3 * bw, p["beam_z"], W),
                   K.CARRIER_GREY))
    cab_x1 = front + p["cab_len"]
    cab = g.fuse(g.box(front, -W / 2, deck - 500.0, p["cab_len"], W, 2300.0),
                 g.box(front + 300.0, -W / 2 + 100, deck + 1800.0, p["cab_len"] - 400.0, W - 200, 400.0))
    K.put(tr, Part("TRUCK CAB", g.cut(cab, g.box(front - 10, -W / 2 + 120, deck + 650, 40, W - 240, 1000)),
                   K.TRUCK_BLUE))
    K.put(tr, Part("TRUCK CAB WINDOW", g.box(front + 5, -W / 2 + 125, deck + 655, 20, W - 250, 990), K.GLASS))
    K.put(tr, Part("FRONT BUMPER", g.box(front - 120.0, -W / 2, 350.0, 140.0, W, 420.0), K.CARRIER_GREY))
    base_r = 0.28 * W
    bed_x0 = max(p["out_x"][0] + 600.0, base_r + 60.0)          # clear of the crane base's round top (task 0214)
    bed = g.cut(g.box(bed_x0, -W / 2, deck, rear - bed_x0, W, 500.0),
                g.box(bed_x0 + 80, -W / 2 + 80, deck + 120, rear - bed_x0 - 160, W - 160, 500.0))
    K.put(tr, Part("LOAD BED", bed, K.CARRIER_GREY))
    K.wheels(tr, kit, p["axles"], c.wheel_r, W / 2)
    K.put(tr, Part("CRANE BASE", g.fuse(g.box(-0.55 * W / 2, -W / 2 + 60, deck - 1.0, 0.55 * W, W - 120, 300.0),
                                        g.cyl(base_r, 1.0, (0, 0, deck + 299.0), (0, 0, 1))), K.BOOM_YELLOW))
    # the control stand on the crane base (it does not slew: on the column it swung into the truck cab, task 0204),
    # on the left – the side the boom does not swing to in the class's poses
    cr0 = 0.32 * c.boom_w + 60.0
    K.put(tr, Part("CONTROL STAND", g.box(cr0 + 80.0, W / 2 - 560.0, deck + 299.0, 340.0, 400.0, 1000.0),
                   K.CARRIER_GREY))
    # ---- stabilisers --------------------------------------------------------------------------------------------
    K.outrigger_set(root, kit, "STABILISER", p["out_x"], bw, p["pad_in"], p["out_ext"] / C.STAGES, p["beam_z"], bw,
                    1.3 * bw, p["pad_z0"], C.knuckle_pad_r(c), tr, W, color=K.BOOM_YELLOW,
                    boxes=False)
    # ---- column (slew) ------------------------------------------------------------------------------------------
    col = Asm("COLUMN.ASM")
    K.put(root, col)
    p1 = np.array(p["p1"])
    cr = 0.32 * c.boom_w + 60.0
    cyl = {cy["name"]: cy for cy in L.cylinders}
    mc = cyl["Main boom cylinder"]
    b1 = np.array(mc["barrel_pin"]["point"])
    ew1 = 1.6 * mc["fit"]["rod_r"]
    pin_r = 0.12 * c.boom_h
    lug_y = c.boom_w / 2 + 30.0
    head_z = p1[2] - 0.62 * c.boom_h                   # under the main boom foot's sweep
    column = K.one(g.cyl(cr, head_z - deck - 300.0, (0, 0, deck + 300.0), (0, 0, 1)),
                   g.cyl(base_r, 120.0, (0, 0, deck + 300.0), (0, 0, 1)),
                   g.box(-1.8 * pin_r, -lug_y - 50.0, head_z - 200.0, 3.6 * pin_r, 2 * lug_y + 100.0, 201.0))
    for sy in (-1, 1):
        y0 = lug_y if sy > 0 else -lug_y - 50.0
        column = g.fuse(column, g.box(-1.6 * pin_r, y0, head_z - 1.0, 3.2 * pin_r, 50.0, p1[2] - head_z + 1.0),
                        g.cyl(1.6 * pin_r, 50.0, (p1[0], y0, p1[2]), (0, 1, 0)))
    # a notch where the main cylinder's barrel swings over the main boom's range (task 0214, 0209 row 17: the barrel
    # went 89-120 mm into the round column, deeper as the boom luffed)
    mj = next(j for j in L.joints if j["name"] == "Main boom")
    q1c = np.array(mc["rod_pin"]["point"])
    sweep_b = []
    for t in np.linspace(mj["limits"][0], mj["limits"][1], 9):
        q = (C.about(mj["point"], mj["direction"], t) @ np.r_[q1c, 1.0])[:3]
        d = (q - b1) / np.linalg.norm(q - b1)
        sweep_b.append(g.cyl(mc["fit"]["barrel_r"] + 25.0, mc["fit"]["barrel_len"],
                             b1 + 0.9 * mc["fit"]["rod_r"] * d, d))
    ew_b = 1.6 * mc["fit"]["rod_r"] + 20.0               # and round the barrel's eye (the pin is at the column's skin)
    sweep_b.append(g.cyl(1.3 * mc["fit"]["rod_r"] + 25.0, ew_b, b1 - np.array([0.0, ew_b / 2, 0.0]), (0, 1, 0)))
    column = K.one(g.cut(column, *sweep_b))
    column = g.fuse(column, *K.lug_pair(b1, (-1, 0, 0), 2.0 * mc["fit"]["barrel_r"] + 30.0, 35.0,
                                        1.3 * mc["fit"]["rod_r"], b1[0] + 1.0,
                                        0.45 * mc["fit"]["rod_r"] + 1.0))
    column = g.cut(column, K.pin_across(p1, pin_r + 1.0, lug_y + 100.0))
    K.put(col, Part("CRANE COLUMN", column, K.BOOM_YELLOW))
    K.put(col, Part("BOOM PIN", K.pin_across(p1, pin_r, lug_y + 80.0), K.STEEL))
    # ---- main boom ----------------------------------------------------------------------------------------------
    mb = Asm("MAIN BOOM.ASM")
    K.put(col, mb)
    um, nm = C.boom_dir(c.main_cad), C.boom_up(c.main_cad)
    p2 = np.array(p["p2"])
    kc = cyl["Knuckle cylinder"]
    ew2 = 1.6 * kc["fit"]["rod_r"]
    q1 = np.array(mc["rod_pin"]["point"])
    b2 = np.array(kc["barrel_pin"]["point"])
    sweep = 0.55 * c.boom_h                            # the outer boom's round foot turns within this of the pin
    body = K.box_tube(p1, um, nm, 2.0 * pin_r, c.main_len - sweep, c.boom_w, c.boom_h, 0.05 * c.boom_w, closed=True)
    foot = K.solid_box(p1, um, nm, -1.4 * pin_r, 2.2 * pin_r, c.boom_w, c.boom_h)
    lugs = K.lug_pair(q1, nm, ew1 + 10.0, 30.0, 1.3 * mc["fit"]["rod_r"], float((p1 - q1) @ nm) - c.boom_h / 2 + 5.0,
                      0.45 * mc["fit"]["rod_r"] + 1.0)
    lugs += K.lug_pair(b2, -nm, ew2 + 10.0, 30.0, 1.3 * kc["fit"]["rod_r"], float((b2 - p1) @ nm) - c.boom_h / 2 + 5.0,
                       0.45 * kc["fit"]["rod_r"] + 1.0)
    # the fork: a bridge behind the outer boom's foot and a plate each side of it, out to the knuckle pin
    fork_y = lug_y + 20.0
    bridge = K.solid_box(p1, um, nm, c.main_len - sweep - 2.5 * pin_r, c.main_len - sweep, 2 * (fork_y + 20.0),
                         c.boom_h)
    ko = []
    for sy in (-1, 1):
        ko.append(K.solid_box(p1, um, nm, c.main_len - sweep - 2.5 * pin_r, c.main_len, 40.0, 3.2 * pin_r,
                              dy=sy * fork_y))
        ko.append(g.cyl(1.6 * pin_r, 40.0, p2 + np.array([0.0, sy * fork_y - 20.0, 0.0]), (0, 1, 0)))
    shape = g.cut(K.one(body, foot, bridge, *lugs, *ko), K.pin_across(p1, pin_r + 1.0, lug_y),
                  K.pin_across(p2, pin_r + 1.0, lug_y + 100.0))
    K.put(mb, Part("MAIN BOOM", shape, K.BOOM_YELLOW))
    K.put(mb, Part("KNUCKLE PIN", K.pin_across(p2, pin_r, lug_y + 60.0), K.STEEL))
    # ---- outer boom + extensions ----------------------------------------------------------------------------------
    ob = Asm("OUTER BOOM.ASM")
    K.put(mb, ob)
    uo, no = C.boom_dir(c.main_cad + c.knuckle_cad), C.boom_up(c.main_cad + c.knuckle_cad)
    q2 = np.array(kc["rod_pin"]["point"])
    wall = 0.05 * c.boom_w
    gap = 18.0
    tube = K.box_tube(p2, uo, no, 0.0, c.outer_len - 300.0, c.boom_w, c.boom_h, wall)
    # the round foot keeps the tube's inside free from just behind the retracted extensions (task 0214: extension 1
    # ran 17-54 mm into a solid foot)
    ofoot = g.cut(g.cyl(sweep - 20.0, c.boom_w, p2 - np.array([0.0, c.boom_w / 2, 0.0]), (0, 1, 0)),
                  K.solid_box(p2, uo, no, 2.2 * pin_r + 40.0, sweep + 10.0, c.boom_w - 2 * wall,
                              c.boom_h - 2 * wall))
    olugs = K.lug_pair(q2, p2 - q2, ew2 + 10.0, 40.0, 1.3 * kc["fit"]["rod_r"], float(np.linalg.norm(q2 - p2)),
                       0.45 * kc["fit"]["rod_r"] + 1)
    oshape = g.cut(K.one(tube, ofoot, *olugs), K.pin_across(p2, pin_r + 1.0, lug_y))
    K.put(ob, Part("OUTER BOOM", oshape, K.BOOM_YELLOW))
    parent = ob
    w, h = c.boom_w, c.boom_h
    a_front = c.outer_len - 300.0
    rs = p["sheave_r"]
    ewall, egap = max(6.0, 0.025 * c.boom_w), 10.0
    for k in range(1, c.extensions + 1):
        w, h = w - 2 * (wall if k == 1 else ewall) - 2 * egap, h - 2 * (wall if k == 1 else ewall) - 2 * egap
        a1 = a_front + k * 30.0
        a0 = a1 - (c.outer_len - 2.2 * pin_r - 300.0) + k * 30.0
        ext = Asm(f"EXTENSION {k}.ASM")
        K.put(parent, ext)
        last = k == c.extensions
        K.put(ext, Part(f"EXTENSION {k}", K.box_tube(p2, uo, no, a0, a1, w, h, ewall, closed=last), K.BOOM_YELLOW))
        if last:
            tip = np.array(p["tip"])
            head_len = float((tip - p2) @ uo) - a1 + 0.8 * rs
            plates = [K.solid_box(p2, uo, no, a1 - 1.0, a1 + head_len, 25.0, 0.8 * h, dy=sy * (0.2 * w + 12.5))
                      for sy in (-1, 1)]
            K.put(ext, Part("BOOM TIP", K.one(*plates, K.solid_box(p2, uo, no, a1 - 1.0, a1 + 40.0, 0.4 * w + 50.0,
                                                                  0.8 * h)), K.BOOM_YELLOW))
            K.put(ext, K.sheave_part("TIP SHEAVE", tip, rs, 0.3 * w))
            K.hook_tree(ext, tip, rs, p["d0"], c.block_h, 0.6 * w + 80.0, max(5.0, 0.04 * rs), swings=2)
        parent = ext
    # ---- cylinders (top level) ------------------------------------------------------------------------------------
    for cy in L.cylinders:
        bar, rod = K.cylinder_parts(cy["barrel"][0], cy["rod"][0], cy["barrel_pin"]["point"], cy["rod_pin"]["point"],
                                    cy["fit"], eye_w=1.6 * cy["fit"]["rod_r"])
        K.put(root, bar)
        K.put(root, rod)
    return root, L
