"""Tool marks on cut faces (task 0061): what the milled mesh tells the cut-face material. No Blender here.

Every triangle of the milled mesh a cutter made knows **the move that made it last** (``core/machining.py`` gives
each cutter solid its own Manifold id). ``blender/machining.py`` writes that as four per-face attributes; the
material of the cut faces (``blender/toolmarks.py``, shader nodes only – it works with scripts off) reads them and
draws the marks. This file is the contract between the two, and the formula in plain Python (the mirror the tests
compare a render with).

The attributes (FACE domain, all in the milled mesh's own space, metres)
------------------------------------------------------------------------
``fr_mk_o``  FLOAT_VECTOR  a point on the tool's axis at the start of the move (the tip), moved back along the feed
                           direction by the path length the bit had already cut before this move, taken modulo the
                           spacing – so the marks of one straight move carry on into the next one
``fr_mk_d``  FLOAT_VECTOR  the feed direction: the move's direction without its part along the tool axis, unit
                           length; (0, 0, 0) for a move along the axis (a plunge, a drilled hole)
``fr_mk_a``  FLOAT_VECTOR  the tool's axis, unit length, from the tip up into the tool
``fr_mk_p``  FLOAT_VECTOR  (kind, radius, spacing): ``kind`` one of the numbers below as a float; ``radius`` the
                           radius of the tool's flat bottom (m; the circle its bottom edge runs on); ``spacing`` the
                           distance between two marks at Mark size Real (m)

With q = P - o (P the shaded point), w = a x d, along = q . d, side = q . w, n the face's normal:

====  ==============  =============================================  ==============================================
kind  name            the number the ridges count (u, metres)        the grooves run along (g)
====  ==============  =============================================  ==============================================
0     NONE            – (not cut, or the move is not known: the material's plain machined look)
1     ARCS            along - sqrt(max(R² - side², 0))               a x (sqrt(..) d + side w) = sqrt(..) w - side d
2     FLANK           along                                          a
3     ALONG           q . a                                          d
4     RINGS           | q - (q . a) a |                              a x q
5     RINGS_WALL      q . a                                          a x q
6     ACROSS          along                                          n x d
====  ==============  =============================================  ==============================================

1 = the bottom of a flat / bull-nose tool or face mill moving sideways (arcs of the tool's radius whose centres
move along the path; the trailing edge's faint cross-hatch uses ``along + sqrt(..)``); 2 = a wall cut with the
side of the tool (lines along the tool axis, one per tooth); 3 = a chamfer / V-bit flank (lines along the path);
4 = the bottom of a plunge or of a drilled hole (rings round the axis); 5 = the wall of a plunged or drilled hole
(rings round the axis, one per turn); 6 = a ball or corner-radius pass (fine arcs across the pass).

A ridge is one period of ``u / (spacing * size)``; ``size`` is the panel's Mark size (1 = Real … 10).
"""

from __future__ import annotations

# attribute names on the milled mesh
ATTR_O, ATTR_D, ATTR_A, ATTR_P = "fr_mk_o", "fr_mk_d", "fr_mk_a", "fr_mk_p"
ATTRS = (ATTR_O, ATTR_D, ATTR_A, ATTR_P)

# kinds (stored as floats in fr_mk_p.x)
NONE, ARCS, FLANK, ALONG, RINGS, RINGS_WALL, ACROSS = 0, 1, 2, 3, 4, 5, 6
KIND_NAMES = {NONE: "none", ARCS: "arcs", FLANK: "flank", ALONG: "along", RINGS: "rings", RINGS_WALL: "rings_wall",
              ACROSS: "across"}

MM = 0.001
# marks are never drawn closer together or further apart than this (m)
SPACING_MIN, SPACING_MAX = 0.01 * MM, 2.0 * MM
# spacing of the marks that do not come from the feed: lines along a chamfer, rings on a drill point / plunge bottom
SPACING_ALONG = 0.06 * MM
SPACING_RINGS = 0.08 * MM
