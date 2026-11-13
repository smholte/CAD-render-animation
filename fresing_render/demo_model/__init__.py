"""The invented cable-lay vessel spread (tasks 0076, 0084): geometry, layout, route and joint sheet.

Ships with the extension (task 0077): ``make.py`` runs it as its own program with Blender's Python and the bundled
OpenCascade (Help > Make demo project, ``blender/demo.py``); ``tools/make_demo_cable_lay.py`` and
``tests/test_demo_cable_lay.py`` use it too. No Blender, no imports from the rest of the app. Nothing of it is a
real vessel, company or design: generic shapes from general engineering knowledge, sizes from one parameter set
(``params.Params``).

  params.py    the parameter set (cable Ø, MBR, vessel, carousel, tensioner …) and what follows from it
  route.py     pure Python + NumPy: straights and arcs, the cable route, rope paths round sheaves, checks
  geom.py      OpenCascade shapes and the scene tree (parts, assemblies, joints) and the STEP writer
  machines.py  vessel, carousel, tensioner (lift + tilt; pads made for the cable Ø), winch (fairlead on a level
               wind), drums (spiral, Lebus), horns (chutes)
  deck.py      the owner's deck (0084): loading tower + arch, V roller highways, walkways, radius controllers,
               D-quadrant, quadrant handler, rails, cable engine, swivel sheaves, CPS sets / rack / ramp, quay
  layout.py    everything placed on the vessel, the routes, the joint sheet, the files (incl. the quay file)
"""
