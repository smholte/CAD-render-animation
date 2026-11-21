"""The demo's ship and its wind park (tasks 0076, 0153, 0166; task 0247: "Vessel in a wind park"): geometry, layout
and the joint sheet.

Ships with the extension (task 0077): ``make.py`` runs it as its own program with Blender's Python and the bundled
OpenCascade (Help > Make demo project, ``blender/demo.py``). No Blender, no imports from the rest of the app. Nothing of
it is a real vessel, company or design: generic shapes from general engineering knowledge, sizes from one parameter
set (``params.ShipParams``).

  params.py    the ship's and the cable's parameters, the park's (``ParkParams``)
  route.py     pure Python + NumPy: straights and arcs, rope paths round sheaves
  geom.py      OpenCascade shapes and the scene tree (parts, assemblies, joints) and the STEP writer – the shape library
               of every test model too
  vessel.py    the ship: hull, superstructure, thrusters, lifeboats, its own deck crane with its hoist (a plain deck)
  deck.py      the quay
  layout.py    the files (ship, park, quay) and the two sheets
  park.py      the wind park round the ship (task 0166, its own file): turbine.py (an invented turbine sized from the
               IEA 15 MW public numbers; its foot and nacelle from turbine_parts.py, shared with the site), substation.py,
               the power cable from turbine A down onto the seabed and along it
  occ.py, turbine_parts.py   moved here from tools/site_projects/ (task 0166): the site's turbine uses them too
"""
