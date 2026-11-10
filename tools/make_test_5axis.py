"""Write a small generic mill with a 5-axis trunnion (A tilts, C turns) as a STEP assembly (task 0066).

Nothing of a real machine: all sizes in mm, Z up. The bed and the trunnion's supports stand still; a moving column
carries the tool in X, Y and Z (the same head as make_test_4axis.py). The cradle tilts about the X axis line
y = 0, z = 140 (the rotary table's top); the rotary table turns about the vertical line x = 0, y = 0 and holds a
block.

TEST.5AXIS
  BED                       fixed, top at z = 0
  SUPPORT L, SUPPORT R      fixed: the trunnion's bearings, x -170 .. -130 and 130 .. 170
  A.ASM                     tilts about the line y = 0, z = 140 along X (a rotate joint in the tests)
    CRADLE                  x -130 .. 130, a plate z 90 .. 120 with a cheek at each end
    C.ASM                   turns about the vertical line x = 0, y = 0 (rides on A)
      ROTARY TABLE          Ø140, z 120 .. 140
      BLOCK 60x60x40        the workpiece: x, y -30 .. 30, z 140 .. 180
  X.ASM … TOOL T1 FLAT D6   as in make_test_4axis.py; the tool's tip at (0, 0, 230), 50 above the block

usage: python make_test_5axis.py out.step
"""

import sys

from make_test_4axis import ALU, BLUE, DARK, GREY, Doc, head
from make_test_atc import _box, _cyl, _fuse

A_Z = 140.0
TIP_Z = 230.0


def build(path: str) -> None:
    d = Doc()
    bed = d.part(_box(-250, -150, -60, 500, 300, 60), "BED", BLUE)
    left = d.part(_box(-170, -60, 0, 40, 120, A_Z + 40), "SUPPORT L", BLUE)
    right = d.part(_box(130, -60, 0, 40, 120, A_Z + 40), "SUPPORT R", BLUE)
    cradle = d.part(_fuse(_box(-130, -90, 90, 260, 180, 30), _box(-130, -90, 90, 20, 180, 70),
                          _box(110, -90, 90, 20, 180, 70)), "CRADLE", GREY)
    table = d.part(_cyl(0, 0, 120, 70.0, 20.0), "ROTARY TABLE", DARK)
    block = d.part(_box(-30, -30, A_Z, 60, 60, 40), "BLOCK 60x60x40", ALU)
    c_asm = d.asm("C.ASM", table, block)
    a_asm = d.asm("A.ASM", cradle, c_asm)
    d.asm("TEST.5AXIS", bed, left, right, a_asm, head(d, TIP_Z))
    d.write(path)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "test_5axis.step")
    print("written")
