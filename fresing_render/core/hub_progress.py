"""The words and numbers of the "Making the Learning hub" progress card (task 0275). No Blender: tested alone.

The card itself (drawing, clicks) is ``blender/hub_progress.py``; the build's own progress is read by
``tour.read_progress`` (``done`` projects of ``total``, the ``step`` being made)."""

from __future__ import annotations

STEP = 30.0                  # seconds: the time left is shown in steps of this size and moves slowly


def fraction(done: int, total: int) -> float:
    """How full the bar is: the projects finished, 0 … 1."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, done / total))


def project_line(done: int, total: int, step: str = "") -> str:
    """"project 4 of 23 – Crane" (the one being made = done + 1)."""
    total = max(total, 1)
    now = min(max(done, 0) + 1, total)
    return f"project {now} of {total}" + (f" – {step}" if step else "")


def seconds_left(done: int, total: int, elapsed: float, expected_total: float) -> float:
    """What is left, from the time per project so far; before the first project is ready, from the expected total."""
    total = max(total, 1)
    if done <= 0 or elapsed <= 0:
        return max(0.0, expected_total - max(elapsed, 0.0))
    return max(0.0, elapsed / done * (total - done))


def settle(new: float, previous: float | None) -> float:
    """The number to show: in steps of ``STEP``, falling freely but rising by at most one step at a time, so the
    line never jumps up and down."""
    new = STEP * -(-max(new, 0.0) // STEP)                 # round up to a step
    if previous is None or new <= previous:
        return new
    return min(new, previous + STEP)


def left_text(seconds: float) -> str:
    if seconds < 45:
        return "less than a minute left"
    return f"about {max(1, round(seconds / 60))} min left"


def intro(minutes: int) -> str:
    n = max(1, minutes)
    return ("Fresing Render is building small sample projects with every function set up – about "
            f"{n} minute{'s' if n != 1 else ''} on a PC like yours.")


KEEP_WORKING = "You can keep working. The progress also shows in the bottom-left corner."
STOP_ASK = "Stop making the Learning hub? The projects made so far are kept; make it again to finish the rest."
