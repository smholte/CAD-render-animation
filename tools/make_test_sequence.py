"""Write a small test model for the Assembly sequence step as a STEP assembly (task 0100; generic, no owner data).

All sizes in mm. A spindle unit stands on a base plate; every part of the unit is round about the Z axis (except the
bolts, which stand round the cover), so it comes apart straight up, part by part, and goes together the same way.

TEST.SEQUENCE
  BASE PLATE              x -200 … 200, y -200 … 200, z -20 … 0, corners and top edges chamfered, four holes Ø18
  SPINDLE.UNIT            (the subassembly the step takes apart: 12 parts, 5 of them fasteners)
    HOUSING               a cup: Ø120, z 0 … 100, inside Ø80 from z 15 up (open at the top); a foot flange Ø150
                          (z 0 … 12) and three cooling fins Ø140 (z 30 … 66); 4 holes Ø8.4 at radius 50 from z 85 up
    BEARING 6205          two rings Ø52 / Ø25, 15 high (outer corners chamfered): z 15 … 30 and z 70 … 85
    SPACER                ring Ø40 / Ø25, z 30 … 70
    SHAFT                 Ø24.8, z 15 … 150, ends chamfered, a keyway 8 wide at the top (z 126 … 150, open upwards)
    COVER                 disc Ø120, z 100 … 115 with a spigot into the housing (Ø79, z 94 … 100) and a seal boss
                          (Ø56, up to z 119); centre hole Ø26, 4 holes Ø8.4 at radius 50
    PULLEY                two-groove V-belt pulley Ø64, z 125 … 145, bore Ø25 with its key in the shaft's keyway (clear
                          of the bolt heads seen from above)
    SKF KM 5 Locknut M25x1.5  shaft lock nut KM5: Ø38, 7 high, bore Ø25, 4 slots 5 x 2 in the rim, z 145 … 152
    ISO 4762 M8x30        4 x: socket head Ø13 z 115 … 123 with its hex socket, shank Ø8 z 85 … 115, at radius 50,
                          45° + k 90°

No two parts overlap: rings fit round the shaft with 0.1 mm play, the bolts in their holes with 0.2 mm, the key in its
keyway with 0.2 … 1 mm. The details of task 0122 (fins, keyway, grooves, spigot) block no part's way up that was
free before: the order (fasteners, pulley, cover, bearing, spacer, bearing, shaft, housing) is the one of task 0100.

Task 0129: ``--frame`` writes a second model, test_sequence_frame.step: a portal frame (outside the subassembly)
stands over a slide unit, so parts that would fly up run into its beam and must go another way.

TEST.SEQUENCE.FRAME
  BASE PLATE              as above
  PORTAL FRAME            one solid: posts x ±170 … ±190, y -20 … 20, z 0 … 170; beam x -190 … 190, z 150 … 170
  SLIDE.UNIT              (the subassembly: 7 parts, 2 of them fasteners)
    RAIL BLOCK            x -150 … 150, y -60 … 60, z 0 … 40 (on the base plate; two blind holes Ø8.4 for the bolts)
    COVER                 x -140 … -60, y -50 … 50, z 40 … 50, two holes Ø8.4 at x -100, y ±40
    ISO 4762 M8x25        2 x, at x -100, y ±40: heads on the cover (z 50 … 58), clear of the beam (|y| > 20)
    CARRIAGE              x -40 … 40, y -50 … 50, z 40 … 80 (the tests put it on a slide joint on the rail block)
    GRIPPER BLOCK         x -20 … 20, y -30 … 30, z 80 … 120 (the tests put it on a joint on the carriage: a rider)
    SPLIT PIN             a small pin on the rail block at x 120, y 0 under the beam (z 40 … 60): it must go sideways

usage: python make_test_sequence.py out.step
       python make_test_sequence.py --frame out.step
"""

import math
import os
import sys

from OCP.gp import gp_Trsf, gp_Vec
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fresing_render.demo_model import geom as g  # noqa: E402
from model_details import chamfer, chamfered_rect, hex_prism, socket_screw  # noqa: E402

BOLT_R = 50.0                       # the bolts' circle
BOLT_ANGLES = (45.0, 135.0, 225.0, 315.0)
PARTS = 12                          # in SPINDLE.UNIT
FASTENERS = 5


def _bolt_holes(shape, z0, z1):
    holes = [g.cyl(4.2, z1 - z0, (BOLT_R * math.cos(math.radians(a)), BOLT_R * math.sin(math.radians(a)), z0))
             for a in BOLT_ANGLES]
    return g.cut(shape, *holes)


def base_plate():
    plate = g.polygon_prism(chamfered_rect(-200, -200, 400, 400, 20), 20.0, g.T(0, 0, -20))
    plate = chamfer(plate, 3.0, lambda p: abs(p[2]) < 1e-6)
    holes = []
    for x in (-170.0, 170.0):
        for y in (-170.0, 170.0):
            holes.append(g.cyl(9.0, 22.0, (x, y, -21)))                                 # for M16 anchor bolts
    return g.cut(plate, *holes)


def housing():
    prof = [(0.0, 0.0), (75.0, 0.0), (75.0, 12.0), (60.0, 12.0)]
    for z in (30.0, 46.0, 62.0):                                     # cooling fins
        prof += [(60.0, z), (70.0, z), (70.0, z + 4), (60.0, z + 4)]
    prof += [(60.0, 100.0), (40.0, 100.0), (40.0, 15.0), (0.0, 15.0)]
    return _bolt_holes(g.revolve(prof), 85, 101)


def bearing():
    """6205: Ø52 / Ø25 x 15 on z 0 … 15, the outer ring's corners rounded off (chamfered)."""
    return g.revolve([(12.5, 0.0), (25.0, 0.0), (26.0, 1.0), (26.0, 14.0), (25.0, 15.0), (12.5, 15.0)])


def spacer():
    return g.revolve([(12.5, 30.0), (20.0, 30.0), (20.0, 70.0), (12.5, 70.0)])


def shaft():
    s = g.revolve([(0.0, 15.0), (11.4, 15.0), (12.4, 16.0), (12.4, 149.0), (11.4, 150.0), (0.0, 150.0)])
    return g.cut(s, g.box(8.4, -4.0, 126.0, 5.0, 8.0, 25.0))        # the keyway, open at the top


def cover():
    prof = [(13.0, 94.0), (39.5, 94.0), (39.5, 100.0), (60.0, 100.0), (60.0, 115.0), (28.0, 115.0), (28.0, 119.0),
            (13.0, 119.0)]
    return _bolt_holes(g.revolve(prof), 99, 116)


def pulley():
    prof = [(12.5, 125.0), (32.0, 125.0), (32.0, 128.0), (26.0, 131.0), (32.0, 134.0), (32.0, 136.0), (26.0, 139.0),
            (32.0, 142.0), (32.0, 145.0), (12.5, 145.0)]
    key = g.box(8.9, -3.8, 127.0, 4.0, 7.6, 16.0)                   # in the shaft's keyway (x 8.4 …, y ±4, z 126 …)
    return g.fuse(g.revolve(prof), key)


def nut():
    """Shaft lock nut KM5 (task 0264): M25 x 1.5, Ø38, 7 high (z 145 … 152), bore Ø25, four slots 5 wide and 2 deep
    in the rim (90° apart), the top edge chamfered."""
    body = g.revolve([(12.5, 145.0), (19.0, 145.0), (19.0, 152.0), (12.5, 152.0)])
    body = chamfer(body, 1.0, lambda p: abs(p[2] - 152.0) < 1e-6 and p[0] ** 2 + p[1] ** 2 > 18.0 ** 2)
    for bx in (g.box(-20.0, -2.5, 150.0, 40.0, 5.0, 3.0), g.box(-2.5, -20.0, 150.0, 5.0, 40.0, 3.0)):
        body = g.cut(body, g.cut(bx, g.cyl(17.0, 4.0, (0, 0, 149.5))))     # the two bars' ends = four rim slots
    return body


def bolt():
    """At the origin of its own placement: the shank's axis is Z, the head's underside at z = 115."""
    return g.xform(socket_screw(8, 30.0), g.T(0, 0, 115.0))


def portal_frame():
    posts = [g.box(x0, -20.0, 0.0, 20.0, 40.0, 170.0) for x0 in (-190.0, 170.0)]
    beam = g.box(-190.0, -20.0, 150.0, 380.0, 40.0, 20.0)
    return chamfer(g.fuse(beam, *posts), 2.0, lambda p: abs(p[2] - 170.0) < 1e-6)


def rail_block():
    b = chamfer(g.box(-150.0, -60.0, 0.0, 300.0, 120.0, 40.0), 2.0, lambda p: abs(p[2] - 40.0) < 1e-6)
    return g.cut(b, *[g.cyl(4.2, 16.0, (-100.0, y, 25.0)) for y in (-40.0, 40.0)])


def slide_cover():
    c = g.box(-140.0, -50.0, 40.0, 80.0, 100.0, 10.0)
    return g.cut(c, *[g.cyl(4.2, 12.0, (-100.0, y, 39.0)) for y in (-40.0, 40.0)])


def carriage():
    return chamfer(g.box(-40.0, -50.0, 40.0, 80.0, 100.0, 40.0), 1.5, lambda p: abs(p[2] - 80.0) < 1e-6)


def gripper_block():
    return chamfer(g.box(-20.0, -30.0, 80.0, 40.0, 60.0, 40.0), 1.5, lambda p: abs(p[2] - 120.0) < 1e-6)


def split_pin():
    return g.cyl(5.0, 20.0, (120.0, 0.0, 40.0))


def build_frame(path: str) -> None:
    """The second model (task 0129): the slide unit under a portal frame."""
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
        if g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
        lab = st.AddShape(shape, False)
        name(lab, text)
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, trsf=None):
        st.AddComponent(assy, lab, TopLoc_Location(trsf if trsf is not None else gp_Trsf()))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, orange, steel, dark, yellow = ((0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.95, 0.45, 0.05),
                                               (0.8, 0.8, 0.82), (0.15, 0.15, 0.17), (0.95, 0.78, 0.1))
    base = part(base_plate(), "BASE PLATE", grey)
    frame = part(portal_frame(), "PORTAL FRAME", yellow)
    unit = asm("SLIDE.UNIT")
    place(unit, part(rail_block(), "RAIL BLOCK", blue))
    place(unit, part(slide_cover(), "COVER", steel))
    b = part(g.xform(socket_screw(8, 25.0), g.T(0, 0, 50.0)), "ISO 4762 M8x25", dark)
    for y in (-40.0, 40.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(-100.0, y, 0))
        place(unit, b, t)
    place(unit, part(carriage(), "CARRIAGE", orange))
    place(unit, part(gripper_block(), "GRIPPER BLOCK", steel))
    place(unit, part(split_pin(), "SPLIT PIN", dark))
    root = asm("TEST.SEQUENCE.FRAME")
    place(root, base)
    place(root, frame)
    place(root, unit)
    st.UpdateAssemblies()
    _write(doc, path)


def _write(doc, path: str) -> None:
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError("STEP write failed")


def build(path: str) -> None:
    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def name(label, text):
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(text))

    def part(shape, text, rgb):
        if g.solids(shape) != 1:
            raise RuntimeError(f"{text}: {g.solids(shape)} solids (a test model part is one solid)")
        lab = st.AddShape(shape, False)
        name(lab, text)
        ct.SetColor(lab, Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_sRGB), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
        return lab

    def place(assy, lab, trsf=None):
        st.AddComponent(assy, lab, TopLoc_Location(trsf if trsf is not None else gp_Trsf()))

    def asm(text):
        lab = st.NewShape()
        name(lab, text)
        return lab

    grey, blue, orange, steel, dark = ((0.55, 0.57, 0.6), (0.075, 0.267, 0.486), (0.95, 0.45, 0.05),
                                       (0.8, 0.8, 0.82), (0.15, 0.15, 0.17))
    base = part(base_plate(), "BASE PLATE", grey)
    unit = asm("SPINDLE.UNIT")
    place(unit, part(housing(), "HOUSING", blue))
    brg = part(bearing(), "BEARING 6205", steel)
    for z in (15.0, 70.0):
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(0, 0, z))
        place(unit, brg, t)
    place(unit, part(spacer(), "SPACER", steel))
    place(unit, part(shaft(), "SHAFT", steel))
    place(unit, part(cover(), "COVER", blue))
    place(unit, part(pulley(), "PULLEY", orange))
    place(unit, part(nut(), "SKF KM 5 Locknut M25x1.5", dark))
    b = part(bolt(), "ISO 4762 M8x30", dark)
    for a in BOLT_ANGLES:
        t = gp_Trsf()
        t.SetTranslation(gp_Vec(BOLT_R * math.cos(math.radians(a)), BOLT_R * math.sin(math.radians(a)), 0))
        place(unit, b, t)
    root = asm("TEST.SEQUENCE")
    place(root, base)
    place(root, unit)
    st.UpdateAssemblies()
    _write(doc, path)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--frame"]
    if "--frame" in sys.argv[1:]:
        build_frame(args[0] if args else "test_sequence_frame.step")
    else:
        build(args[0] if args else "test_sequence.step")
    print("written")
