"""Writes the invented big machine the PC check "Heavy" imports (task 0033).

Runs as its own small program (Blender's Python with the bundled OpenCascade), so its memory use does
not count for the app: ``python heavy_scene.py out.step [unique placed]``. No Blender, no relative
imports. The machine is generic: modules of sub-assemblies of generic parts (brackets, gears, shafts,
housings, plates) and many fasteners with supplier-style names; nothing of any real design.

Full size: 600 unique parts, 3,000 placed (about 3 million triangles at the app's "normal" meshing).
Scaled down (GitHub, small machines): a few dozen unique parts and a few hundred placed.
"""

from __future__ import annotations

import math
import random
import sys


def build(path: str, unique: int = 600, placed: int = 3000, seed: int = 7) -> dict:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import (BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder,
                                 BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeTorus)
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_StepModelType
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool

    rnd = random.Random(seed)
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb=None):
        lab = st.AddShape(shape, False)
        name(lab, text)
        if rgb:
            ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB),
                        XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, x=0.0, y=0.0, z=0.0, turn=0.0):
        t = gp_Trsf()
        if turn:
            t.SetRotation(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)).Axis(), turn)
        t2 = gp_Trsf()
        t2.SetTranslation(gp_Vec(x, y, z))
        st.AddComponent(assy, lab, TopLoc_Location(t2.Multiplied(t)))

    def hole_cut(shape, w, d, h, holes):
        """The shape with ``holes`` x holes bored through (more faces: heavier meshes)."""
        for i in range(holes):
            for j in range(holes):
                x = w * (i + 1) / (holes + 1)
                y = d * (j + 1) / (holes + 1)
                cyl = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, -1), gp_Dir(0, 0, 1)),
                                               min(w, d) / (holes * 4.0), h + 2).Shape()
                shape = BRepAlgoAPI_Cut(shape, cyl).Shape()
        return shape

    # ---- unique parts
    colours = [(0.75, 0.76, 0.78), (0.55, 0.57, 0.6), (0.2, 0.35, 0.6), (0.85, 0.65, 0.1), (0.4, 0.4, 0.42),
               (0.7, 0.2, 0.15)]
    kinds = ["BRACKET", "HOUSING", "GEAR", "SHAFT", "PLATE", "FLANGE", "BEARING", "COVER", "ROLLER", "BLOCK"]
    fastener_sizes = [(6, 16), (6, 25), (8, 20), (8, 30), (10, 25), (10, 40), (12, 30), (12, 50), (16, 40),
                      (16, 60), (20, 60), (24, 80)]
    n_fast = min(len(fastener_sizes), max(3, unique // 25))
    parts, fasteners = [], []
    for i, (d, ln) in enumerate(fastener_sizes[:n_fast]):
        kind = ("ISO 4017 M%d x %d - 8.8" if i % 3 == 0 else "DIN 912 M%d x %d - 12.9" if i % 3 == 1
                else "ISO 7380 M%d x %d") % (d, ln)
        fasteners.append(part(BRepPrimAPI_MakeCylinder(d / 2.0, float(ln)).Shape(), kind))
        fasteners.append(part(BRepPrimAPI_MakeCylinder(d * 0.9, d * 0.8).Shape(), f"ISO 4032 M{d}"))
        fasteners.append(part(BRepPrimAPI_MakeCylinder(d * 1.0, 2.0).Shape(), f"WASHER{d}"))
    for i in range(max(1, unique - len(fasteners))):
        kind = kinds[i % len(kinds)]
        s = 80.0 + 400.0 * rnd.random()
        w, d, h = s, s * (0.5 + rnd.random()), 20.0 + 120.0 * rnd.random()
        r = i % 5
        if r == 0:
            shape = hole_cut(BRepPrimAPI_MakeBox(w, d, h).Shape(), w, d, h, 4 + i % 4)
        elif r == 1:
            shape = BRepPrimAPI_MakeCylinder(w / 3.0, h * 3).Shape()
            shape = BRepAlgoAPI_Cut(shape, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, -1), gp_Dir(0, 0, 1)),
                                                                    w / 6.0, h * 3 + 2).Shape()).Shape()
        elif r == 2:
            shape = BRepPrimAPI_MakeTorus(w / 3.0, w / 12.0).Shape()
        elif r == 3:
            shape = BRepPrimAPI_MakeCone(w / 3.0, w / 8.0, h * 2).Shape()
        else:
            shape = BRepPrimAPI_MakeSphere(w / 4.0).Shape()
        parts.append(part(shape, f"{kind} {i + 1:04d}", rnd.choice(colours)))

    # ---- assemblies: root > modules > sub-assemblies > placed parts
    modules = max(2, round(math.sqrt(placed) / 5))
    subs_per = 4
    n_sub = modules * subs_per
    per_sub = max(2, placed // n_sub)
    root = st.NewShape()
    name(root, "HEAVY.MACHINE")
    count = 0
    cols = max(1, round(math.sqrt(modules)))
    pool = parts + [None]
    for m in range(modules):
        mod = st.NewShape()
        name(mod, f"MODULE {m + 1:02d}")
        for k in range(subs_per):
            sub = st.NewShape()
            name(sub, f"UNIT {m + 1:02d}.{k + 1}")
            side = max(1, round(math.sqrt(per_sub)))
            for j in range(per_sub):
                if j % 3 == 2 and fasteners:
                    lab = fasteners[rnd.randrange(len(fasteners))]
                else:
                    lab = parts[(m * 97 + k * 31 + j * 7) % len(parts)]
                place(sub, lab, (j % side) * 450.0, (j // side) * 450.0, 0.0, rnd.random() * 6.28)
                count += 1
            place(mod, sub, (k % 2) * (side + 1) * 450.0, (k // 2) * (side + 1) * 450.0, 0.0)
        place(root, mod, (m % cols) * 6000.0 * math.sqrt(per_sub) / 7.0 * 2.2,
              (m // cols) * 6000.0 * math.sqrt(per_sub) / 7.0 * 2.2, 0.0)
    st.UpdateAssemblies()

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")
    return {"unique": len(parts) + len(fasteners), "placed": count, "modules": modules}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "heavy_machine.step"
    u = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    p = int(sys.argv[3]) if len(sys.argv) > 3 else 3000
    print(build(out, u, p))
