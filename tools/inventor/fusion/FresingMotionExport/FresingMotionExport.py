"""Fresing Render – motion export for Fusion (a script).                       draft 0.1, task 0104, 13 Nov 2026

Writes the open design's joints and as-built joints (type, axis, limits, the two occurrences) to
``<design name>.fresing.json`` in a folder you pick, and on request the STEP file next to it. The same file format as
the Inventor rule (tools/inventor/FresingMotionExport.iLogicVb); Fusion keeps its motion in joints, so there are no
constraints to read. Nothing in the design is changed.

How to run: Utilities tab > Add-Ins > Scripts and Add-Ins > the green + next to "My Scripts" > pick this folder
(FresingMotionExport) > select it > Run. See tools/inventor/README.md.

Everything is written in mm and degrees in the root component's coordinates (= the STEP file's). Fusion's API gives
cm and radians.
"""
import datetime
import json
import math
import os
import traceback

import adsk.core
import adsk.fusion

KINDS = ["rigid", "rotational", "slide", "cylindrical", "pin_slot", "planar", "ball"]   # JointTypes 0 .. 6


def _vec(v):
    return None if v is None else [round(v.x, 6), round(v.y, 6), round(v.z, 6)]


def _pt(p):
    return None if p is None else [round(p.x * 10.0, 4), round(p.y * 10.0, 4), round(p.z * 10.0, 4)]


def _limits(lim, factor):
    """JointLimits -> {"min", "max"} in mm / deg (an end that is not switched on is null), or None."""
    if lim is None or not (lim.isMinimumValueEnabled or lim.isMaximumValueEnabled):
        return None
    return {"min": round(lim.minimumValue * factor, 6) if lim.isMinimumValueEnabled else None,
            "max": round(lim.maximumValue * factor, 6) if lim.isMaximumValueEnabled else None}


def _path(occ):
    return occ.fullPathName.split("+") if occ is not None else []


def _joint(j, as_built, problems):
    m = j.jointMotion
    kind = KINDS[m.jointType] if 0 <= m.jointType < len(KINDS) else "other"
    geo = j.geometry if as_built else j.geometryOrOriginOne
    origin = None
    try:
        origin = geo.origin if hasattr(geo, "origin") else geo.geometry.origin     # JointGeometry / JointOrigin
    except Exception:
        problems.append(f"{j.name}: origin not read")
    z = None
    for attr in ("rotationAxisVector", "slideDirectionVector", "normalDirectionVector"):
        if hasattr(m, attr):
            try:
                z = getattr(m, attr)
            except Exception:
                z = None
            if z is not None:
                break
    if z is None and geo is not None and hasattr(geo, "primaryAxisVector"):
        z = geo.primaryAxisVector
    d = {"name": j.name, "type": kind, "assembly": [], "suppressed": bool(j.isSuppressed),
         "locked": bool(getattr(j, "isLocked", False)),
         "one": {"occurrence": _path(j.occurrenceOne), "origin": {"point": _pt(origin), "z": _vec(z), "x": None}},
         "two": {"occurrence": _path(j.occurrenceTwo), "origin": {"point": _pt(origin), "z": _vec(z), "x": None}},
         "angle": None, "linear": None, "angle_limits": None, "linear_limits": None, "as_built": as_built}
    if hasattr(m, "rotationValue"):
        d["angle"] = round(math.degrees(m.rotationValue), 6)
        d["angle_limits"] = _limits(m.rotationLimits, 180.0 / math.pi)
    if hasattr(m, "slideValue"):
        d["linear"] = round(m.slideValue * 10.0, 6)
        d["linear_limits"] = _limits(m.slideLimits, 10.0)
    return d


def run(_context):
    app = adsk.core.Application.get()
    ui = app.userInterface
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox("Open a design first.", "Fresing motion export")
            return
        root = design.rootComponent
        dlg = ui.createFolderDialog()
        dlg.title = "Fresing motion export: folder for the file"
        if dlg.showDialog() != adsk.core.DialogResults.DialogOK:
            return
        folder = dlg.folder
        stem = design.parentDocument.name
        answer = ui.messageBox(f"Also save the STEP file now?\n\n{os.path.join(folder, stem + '.step')}\n\n"
                               "Yes = STEP + motion file (they always match).", "Fresing motion export",
                               adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType)
        if answer == adsk.core.DialogResults.DialogCancel:
            return
        problems, occs, joints = [], [], []
        for occ in root.allOccurrences:
            t = occ.transform2
            m = [t.getCell(r, c) * (10.0 if c == 3 and r < 3 else 1.0) for r in range(4) for c in range(4)]
            occs.append({"path": _path(occ), "kind": "assembly" if occ.childOccurrences.count else "part",
                         "file": occ.component.name, "part_number": occ.component.partNumber,
                         "grounded": bool(occ.isGrounded), "suppressed": False,
                         "visible": bool(occ.isLightBulbOn), "flexible": True, "pattern": False,
                         "matrix": [round(x, 6) for x in m]})
        for coll, as_built in ((root.allJoints, False), (root.allAsBuiltJoints, True)):
            for j in coll:
                try:
                    joints.append(_joint(j, as_built, problems))
                except Exception as exc:
                    problems.append(f"{j.name}: not read ({exc})")
        step = ""
        if answer == adsk.core.DialogResults.DialogYes:
            try:
                path = os.path.join(folder, stem + ".step")
                em = design.exportManager
                em.execute(em.createSTEPExportOptions(path, root))
                step = os.path.basename(path)
            except Exception as exc:
                problems.append(f"STEP file not saved: {exc}")
        data = {"format": "fresing-cad-motion", "version": 1,
                "written_by": {"app": "Fusion", "app_version": app.version, "script": "FresingMotionExport 0.1",
                               "time": datetime.datetime.now().isoformat(timespec="seconds")},
                "document": {"name": stem, "step_file": step}, "units": {"length": "mm", "angle": "deg"},
                "frame": "root component (= the STEP file's coordinates)",
                "occurrences": occs, "constraints": [], "joints": joints, "problems": problems}
        out = os.path.join(folder, stem + ".fresing.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        msg = f"Written: {out}\n{len(occs)} occurrences, {len(joints)} joints."
        if problems:
            msg += "\n\nNot read:\n" + "\n".join(" - " + p for p in problems[:10])
        ui.messageBox(msg, "Fresing motion export")
    except Exception:
        ui.messageBox("Failed:\n" + traceback.format_exc(), "Fresing motion export")
