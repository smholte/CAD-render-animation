"""The invented cable-lay vessel spread (task 0076): geometry, layout, route and joint sheet.

Used by ``tools/make_demo_cable_lay.py`` and ``tests/test_demo_cable_lay.py``. Nothing of it is a real vessel, company
or design: generic shapes from general engineering knowledge, sizes from one parameter set (``params.Params``).

  params.py    the parameter set (cable Ø, MBR, vessel, carousel, tensioner …) and what follows from it
  route.py     pure Python + NumPy: straights and arcs, the cable route, rope paths round sheaves, checks
  geom.py      OpenCascade shapes and the scene tree (parts, assemblies, joints) and the STEP writer
  machines.py  the machines: vessel, carousel + loading arm, tensioner, winch, drums, chute, quadrant, CPS
  layout.py    everything placed on the vessel, the cable route, the joint sheet, the files
"""
