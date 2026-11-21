"""The equipment file of a built-in crane class (task 0191) – plain Python.

The format of study 0180 section 4 (``core/lifting_library.py`` reads it): ``kind``, ``class``, ``name``, ``units``,
masses and centres of gravity per moving group, ``rig`` (the render-kit sheet's joints / cylinders / poses by part
names, plus what L4 needs to place and move it), ``charts`` (invented SAMPLE charts, ``charts.py``), ``hook_blocks``,
``outriggers`` / ``tracks`` / ``axles``, ``limits``, ``"sample": true`` and ``source``.

The centres of gravity come from the maker's solids (``common.group_cogs``); everything else from ``classes`` and
``charts``. Lengths in m, masses in t; the rig keeps the sheet's own units (mm, degrees) and says so.
"""

from __future__ import annotations

from . import charts as K
from . import classes as C

FORMAT = "fresing-lifting-equipment"
FORMAT_VERSION = "1.0"
SOURCE = "invented sample – Fresing Render"
NOTE = ("SAMPLE DATA – NOT FOR REAL LIFTS. An invented crane of this size class (Fresing Render, task 0191): the charts "
        "have a plausible shape only and belong to no real crane. Enter the chart of your real crane before you plan "
        "a lift.")


def _cls(name_or_cls):
    """A class by name, or a made crane's own dataclass (task 0204: ``params.to_class``)."""
    return C.CLASSES[name_or_cls] if isinstance(name_or_cls, str) else name_or_cls


def groups(name) -> dict:
    """Mass group -> {"parts": sub-assemblies / parts, "exclude": what inside them is another group's, "moves_with":
    the joint that carries it}. The maker works out each group's centre of gravity from these."""
    c = _cls(name)
    if c.kind == "AT":
        beams = [f"OUTRIGGER BEAM {f}{s}.ASM" for f in "FR" for s in "LR"]
        return {
            "carrier": {"parts": ["CARRIER.ASM"] + beams, "exclude": [], "moves_with": None},
            "superstructure": {"parts": ["SUPERSTRUCTURE.ASM", "LUFF CYLINDER BARREL", "LUFF CYLINDER ROD"],
                               "exclude": ["BOOM BASE.ASM", "COUNTERWEIGHT.ASM"], "moves_with": "Slew"},
            "counterweight": {"parts": ["COUNTERWEIGHT.ASM"], "exclude": [], "moves_with": "Slew"},
            "boom": {"parts": ["BOOM BASE.ASM"], "exclude": ["HOOK SWING.ASM"], "moves_with": "Luff"},
            "hook_block": {"parts": ["HOOK BLOCK.ASM"], "exclude": [], "moves_with": "Hoist"},
        }
    if c.kind == "CC":
        g = {
            "lower": {"parts": ["LOWER WORKS.ASM"], "exclude": [], "moves_with": "Travel"},
            "upper": {"parts": ["UPPER WORKS.ASM"] + [f"BOOM PENDANT {k} {s}" for k in ("BAR", "ROD") for s in "LR"],
                      "exclude": ["LATTICE BOOM.ASM", "COUNTERWEIGHT.ASM"], "moves_with": "Slew"},
            "counterweight": {"parts": ["COUNTERWEIGHT.ASM"], "exclude": [], "moves_with": "Slew"},
            "boom": {"parts": ["LATTICE BOOM.ASM"], "exclude": ["HOOK SWING.ASM", "LUFFING JIB.ASM"],
                     "moves_with": "Luff"},
            "hook_block": {"parts": ["HOOK BLOCK.ASM"], "exclude": [], "moves_with": "Hoist"},
        }
        if c.jib_cad > 0:
            g["jib"] = {"parts": ["LUFFING JIB.ASM"] + [f"JIB PENDANT {k} {s}" for k in ("BAR", "ROD") for s in "LR"],
                        "exclude": ["HOOK SWING.ASM"], "moves_with": "Jib"}
        return g
    beams = [f"STABILISER BEAM {f}{s}.ASM" for f in "FR" for s in "LR"]
    return {
        "truck": {"parts": ["TRUCK.ASM"] + beams, "exclude": [], "moves_with": None},
        "column": {"parts": ["COLUMN.ASM", "MAIN CYLINDER BARREL", "MAIN CYLINDER ROD"], "exclude": ["MAIN BOOM.ASM"],
                   "moves_with": "Slew"},
        "main_boom": {"parts": ["MAIN BOOM.ASM", "KNUCKLE CYLINDER BARREL", "KNUCKLE CYLINDER ROD"],
                      "exclude": ["OUTER BOOM.ASM"], "moves_with": "Main boom"},
        "outer_boom": {"parts": ["OUTER BOOM.ASM"], "exclude": ["HOOK SWING.ASM"], "moves_with": "Knuckle"},
        "hook_block": {"parts": ["HOOK BLOCK.ASM"], "exclude": [], "moves_with": "Hoist"},
    }


def masses(name) -> dict:
    c = _cls(name)
    if c.kind == "AT":
        return {"carrier": c.mass_carrier, "superstructure": c.mass_upper, "counterweight": max(c.counterweights),
                "boom": c.mass_boom, "hook_block": c.hook_mass}
    if c.kind == "CC":
        m = {"lower": c.mass_lower, "upper": c.mass_upper, "counterweight": max(c.counterweights),
             "boom": c.mass_boom, "hook_block": c.hook_mass}
        if c.jib_cad > 0:
            m["jib"] = c.mass_jib
        return m
    return {"truck": c.mass_truck, "column": c.mass_column, "main_boom": c.mass_main, "outer_boom": c.mass_outer,
            "hook_block": c.hook_mass}


def _r(v, n=3):
    return round(float(v) / 1000.0, n)


def rig(name, step: str | None = None) -> dict:
    """The rig: the sheet's joints, cylinders and poses (mm, degrees – the STEP's own units) and, for L4, the mass
    groups, the hook, the hoist rope (a cable of 4 Motion > Cables and paths) and the crawler tracks."""
    c = _cls(name)
    L = C.layout(c)
    cyl = [{k: v for k, v in cy.items() if k != "fit"} for cy in L.cylinders]
    r = {
        "step": step or f"{c.name}.step", "units": "mm", "angles": "deg", "up_axis": "Z",
        "frame": "ground z = 0, slew axis = z axis, boom along +x in the CAD pose (joint values 0)",
        "joints": L.joints, "cylinders": cyl, "poses": L.poses, "start_pose": L.poses[0]["name"],
        "groups": {g: {"parts": d["parts"], "moves_with": d["moves_with"]} for g, d in groups(name).items()},
        "hook": {"assembly": L.hook_asm, "point": [round(v, 3) for v in L.hook_point], "joint": "Hoist",
                 "plumb": "the hook swing joints follow the boom's turns (ratio -1): the block hangs plumb"},
        "cables": [{"name": "Hoist rope", "part": "HOIST ROPE", "end_on": L.hook_asm, "look": "ROPE",
                    "note": "drawn in the CAD from the head sheave to the hook block: make it a cable whose end "
                            "stays on the hook block, so it follows the hoist"}],
    }
    if c.kind == "CC":
        r["tracks"] = [{"name": f"{side} track", "wheels": [f"DRIVE SPROCKET {s}", f"IDLER {s}"],
                        "link": f"TRACK LINK {s}", "riders": [f"TRACK SHOE {s}"], "joint": "Travel"}
                       for side, s in (("Left", "L"), ("Right", "R"))]
    return r


def limits(name) -> dict:
    c = _cls(name)
    L = C.layout(c)
    p = L.pts
    out = {"slew": [-180.0, 180.0], "hoist": [0.0, _r(p["hmax"], 2)], "max_line_pull": c.line_pull}
    if c.kind == "AT":
        out.update(boom_angle=[0.0, c.luff_max], boom_length=[_r(c.L0, 2), _r(c.Lmax, 2)],
                   telescope_sections=c.sections - 1, counterweight_steps=list(c.counterweights),
                   outrigger_spreads=[_r(s, 2) for s in c.spread])
    elif c.kind == "CC":
        out.update(boom_angle=[c.luff_min, c.luff_max], boom_lengths=list(c.boom_lengths),
                   model_boom=_r(c.boom_cad, 1), counterweight_steps=list(c.counterweights))
        if c.jib_cad > 0:
            out.update(jib_lengths=list(c.jib_lengths), model_jib=_r(c.jib_cad, 1),
                       jib_angle_to_boom=[-55.0, 5.0], jib_charts_boom_angle=80.0)
    else:
        out.update(slew=[-200.0, 200.0], main_boom_angle=list(c.main_range), knuckle_angle=list(c.knuckle_range),
                   extensions=c.extensions, lifting_moment_tm=c.moment, stabiliser_spreads=[_r(s, 2) for s in c.spread])
    return out


def footprint(name) -> dict:
    """``outriggers`` / ``tracks`` / ``axles`` for the ground checks C5 / C6 (m)."""
    c = _cls(name)
    L = C.layout(c)
    p = L.pts
    if c.kind == "CC":
        tr = p["track"]
        return {"tracks": {"gauge": _r(c.gauge), "length": _r(tr["contact"]), "width": _r(c.shoe_w),
                           "centre": [0.0, 0.0], "joint": "Travel"}}
    jx = p["out_x"]
    pad = 0.6 if c.kind == "AT" and c.rated <= 100 else (0.8 if c.kind == "AT" else 0.4)
    spreads = c.spread
    key = "outriggers"
    out = {key: {"centre": [_r((jx[0] + jx[1]) / 2), 0.0], "a": _r(abs(jx[0] - jx[1]) / 2),
                 "spreads": {lab: _r(s / 2) for lab, s in zip(("full", "middle", "narrow")
                                                               if len(spreads) == 3 else ("full", "narrow"), spreads)},
                 "spread_meaning": "b = half the spread across (pad centre to the crane's middle line)",
                 "stages": C.STAGES, "b_in": _r(p["pad_in"]),
                 "joint_meaning": f"each of the {C.STAGES} beam stages moves the joint's value: "
                                  f"b = b_in + {C.STAGES} x value",
                 "pad": [pad, pad],
                 "joint": "Outriggers" if c.kind == "AT" else "Stabilisers",
                 "jack_joint": "Jacks" if c.kind == "AT" else "Legs"},
           "axles": {"x": [_r(x) for x in p["axles"]], "tyres_per_axle": 2}}
    return out


def hook_blocks(name) -> list:
    c = _cls(name)
    if c.kind == "KB":
        return [{"name": "main", "mass": c.hook_mass, "falls": 1, "wll": round(c.max_cap, 2)}]
    wll = c.rated
    return [{"name": "main", "mass": c.hook_mass, "falls": c.hook_falls, "sheaves": c.hook_falls // 2,
             "wll": wll}]


def reeving(name) -> dict:
    """Task 0232: the hoist rope's reeving (mm, the rig's units): the rope's middle round a head and a block sheave,
    their pitch across the axle, the rope's diameter (from the winch's line pull: a running rope's breaking force
    about 4.5 x the pull, 0.86 kN per mm² of d²), where the block's sheave axle sits above the hook point, and the
    winch drum (centre in the CAD pose, barrel radius, width; it turns with the slew). The drum of a crawler and a
    knuckle-boom crane is not in their model: the app draws it there."""
    import math as _m
    c = _cls(name)
    L = C.layout(c)
    p = L.pts

    def middle(r):
        return r - 1.2 * max(6.0, 0.06 * r)
    rs = p["hook_sheave_r"] if c.kind == "CC" else p["sheave_r"]
    d = 2.0 * _m.ceil(_m.sqrt(4.5 * float(c.line_pull) * 9.80665 / 0.86) / 2.0)
    head_r = middle(rs)
    block_r = min(0.85 * head_r, 0.26 * c.block_h)
    if c.kind == "AT":
        wx, wz, wr = p["winch"]
        drum = {"centre": [round(wx, 1), 0.0, round(wz, 1)], "r": round(wr, 1), "w": round(c.boom_w + 20.0, 1)}
    elif c.kind == "CC":
        wr = 0.22 * c.boom_w
        drum = {"centre": [round(p["xp"] - 1.3 * c.boom_w - wr, 1), 0.0, round(p["turn_top"] + wr + 300.0, 1)],
                "r": round(wr, 1), "w": round(0.9 * c.boom_w, 1)}
    else:
        p1 = p["p1"]
        drum = {"centre": [round(p1[0] - 500.0, 1), 0.0, round(p1[2] - 300.0, 1)], "r": 150.0, "w": 300.0}
    drum["joint"] = "Slew"
    return {"units": "mm", "rope_d": d, "head_r": round(head_r, 1), "block_r": round(block_r, 1),
            "head_pitch": round(3.0 * d, 1), "block_pitch": round(3.0 * d, 1),
            "block_above_hook": round(0.7564 * c.block_h, 1), "drum": drum, "k": 1.04, "bearings": "roller",
            "source": "sheave friction factor K = 1.04 (roller bearings), API RP 9B"}


def data(name, cogs: dict, step: str | None = None, cls_word: str | None = None) -> dict:
    """The whole equipment file of a class; ``cogs`` = group -> [x, y, z] m (from the maker's solids). A made crane
    (task 0204) passes its dataclass, its STEP file name and its size-class word ('AT-120')."""
    c = _cls(name)
    m = masses(name)
    missing = sorted(set(m) - set(cogs))
    if missing:
        raise ValueError(f"{name}: no centre of gravity for {', '.join(missing)}")
    d = {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "kind": C.KINDS[c.kind], "class": cls_word or c.name, "name": c.name,
        "units": {"mass": "t", "length": "m"},
        "mass": m,
        "cog": {g: [round(float(v), 3) for v in cogs[g]] for g in m},
        "rig": rig(name, step),
        "charts": K.charts_of(c),
        "hook_blocks": hook_blocks(name),
        "limits": limits(name),
        "reeving": reeving(name),
        "sample": True,
        "source": SOURCE,
    }
    d.update(footprint(name))
    return d
