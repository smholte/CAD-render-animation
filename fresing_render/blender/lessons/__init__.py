"""The lessons, one module per learning set (task 0230). Each registers itself with ``lesson.lesson(Lesson(...))``.

A new lesson (CLAUDE.md section 6, the lesson rule): a module here named after its tour set, its steps' ``do`` = the
button's own call (or for a click on the model the function the click ends in), its set's build in ``tour.py`` runs
``lesson.run(scene, "<set>")`` first, and every function a step teaches gets ``lesson="<set>:<step>"`` in
``core/functions.py``.
"""

from . import crane, mill, weather  # noqa: F401 - each registers its lesson
