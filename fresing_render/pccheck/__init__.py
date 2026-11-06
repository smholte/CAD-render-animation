"""PC check (task 0032): one click tests every main function of this version on this PC.

The self-test (``selftest.py``) checks the *installation*; the PC check checks the *features* with the
test models that ship in ``data/``: import, sorting, joints, couplings, milling, surroundings, light
looks, cameras, renders on the graphics card, videos and the queue. It runs in a background Blender,
writes an HTML report on the Desktop and opens it at the end.

    core.py      no Blender: lines, results, history on this PC, speed and picture comparison,
                 the text block for the lead chat, the HTML report
    checks.py    the lines themselves (one function per main function of the app)
    runner.py    runs the lines in a background Blender, takes the pictures, writes the report
    launcher.py  the script the Start-menu shortcuts and Help > PC check start Blender with
    ops.py       Help > Fresing Render PC check… in the app; makes the Start-menu shortcuts on Windows

A task that adds something the owner can see adds its line to ``checks.py`` (CLAUDE.md section 6).
"""


def register():
    from . import ops
    ops.register()


def unregister():
    from . import ops
    ops.unregister()
