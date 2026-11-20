"""A made-up demo kit for the app's tests (task 0228): a deck plate and a box that slides on it. Nothing of any real
or demo vessel. ``make.py`` writes the model, ``stages.py`` makes the project (see ``core/demo_kits.py``)."""

FILES = {"assembly": "test_kit_box.step"}
DECK = (6000.0, 3000.0, 200.0)        # mm: the plate, its top at z = 0, from x = 0
BOX = 500.0                           # mm: the box's side, its near face at x = 1000
TRAVEL = 3.0                          # m the box slides along +x in the animation
JOINT = "Box slide"
CAMERA = "Box from the side"
