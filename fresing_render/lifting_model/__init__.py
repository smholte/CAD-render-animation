"""Ready-rigged generic lifting equipment (task 0191, Lifting lane L3): invented cranes in size classes.

``classes`` (pure Python) holds the 12 crane classes – mobile telescopic AT-40…500, crawler lattice CC-100…1600,
knuckle-boom KB-20…200 –, their layout in the model's frame and the forward kinematics of the hook; ``charts`` their
invented SAMPLE load charts; ``equipment`` the equipment file of a class (study 0180 section 4, read by
``core/lifting_library.py``). ``mobile``, ``crawler``, ``knuckle`` (OpenCascade) make the STEP assembly of a class
with the pattern of ``demo_model``: one solid per part, moving groups as named sub-assemblies. ``make`` writes the
built-in folders ``fresing_render/data/lifting/<class>/``; ``tools/make_lifting_cranes.py`` is the command line.

Everything here is invented: no maker's name, model, chart or picture. Every chart is marked SAMPLE.
"""
