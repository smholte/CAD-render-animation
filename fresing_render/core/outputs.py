"""Format numbers on what the app writes for other readers (task 0353; same style as ``core/compat.py``: a whole
number and one plain line). No Blender here. The rules are written down for the Fresing Viewer in
``docs/OUTPUT-FORMATS.md`` – change both together.

* **The 3D page** (one HTML file, also its data file = the glTF model inside it): the page's settings block has
  ``"v"`` = ``PAGE_FORMAT`` (it has had ``"v": 1`` since the first page) and the model's ``asset.extras`` has
  ``"fresing_format"`` = the same number. A page or model without a number is format 1 (everything written before
  this task). ``PAGE_READS`` = the highest number this app's page code and ``fr_page.js`` read.
* **The House round trip:** both packages carry the House format's own ``version`` ("1.0", FORMAT.md section 2 of
  github.com/smholte/house-scene-format) – the number of that format, not of this app; the bake also says which app
  version made it (``generator``). ``core/house_scene.check_version`` applies it (another major version refused, a
  newer minor read with a note). Nothing new is written there; the words for a newer one are ``newer()`` below.
* **The Toolbox inbox** hands a refusal of a house on in the job's status text unchanged (``toolbox_inbox``).

A number goes UP only when a reader of the old number would show something wrong: a new, optional field a reader
may ignore does not raise it (then the reader just leaves it out). Readers: numbers up to ``reads`` = read; an older
number = read as it is; a newer number = read what can be read and say ``newer()`` once, plainly.
"""

from __future__ import annotations

PAGE_FORMAT = 1                 # the 3D page's format (settings "v", the model's asset.extras "fresing_format")
PAGE_READS = 1                  # the highest page format this app's page code reads
GLB_KEY = "fresing_format"      # asset.extras key in the page's glTF model

OLDER, SAME, NEWER, BAD = "older", "same", "newer", "bad"


def number(value, default: int = 1):
    """The format number a file says: a missing one is ``default`` (written before the numbers existed); a whole
    number of 1 or more is itself; anything else (text, 0, a fraction, True, NaN) is None = not a number."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        if value != value or value in (float("inf"), float("-inf")) or int(value) != value or int(value) < 1:
            return None
    except (OverflowError, ValueError):
        return None
    return int(value)


def judge(value, reads: int = PAGE_READS, default: int = 1) -> str:
    """``OLDER`` / ``SAME`` / ``NEWER`` than ``reads``, or ``BAD`` when ``value`` is no format number."""
    n = number(value, default)
    if n is None:
        return BAD
    return OLDER if n < reads else SAME if n == reads else NEWER


def newer(maker: str = "Fresing Render") -> str:
    """The one plain line for something a newer app made (the page shows exactly this text; ``fr_page.js`` has the
    same words – a test compares them)."""
    return f"Made by a newer {maker} – update to open it fully."


def page_format(settings: dict | None, glb_doc: dict | None = None):
    """The format a page says: the highest of its settings' ``v`` and its model's ``asset.extras`` number (None when
    one of them is not a number). A page with neither is format 1."""
    nums = [number((settings or {}).get("v"))]
    extras = ((glb_doc or {}).get("asset") or {}).get("extras")
    nums.append(number(extras.get(GLB_KEY)) if isinstance(extras, dict) else 1)
    return None if None in nums else max(nums)


def page_state(settings: dict | None, glb_doc: dict | None = None) -> tuple[str, str]:
    """(judge, text) for a page's data: text is "" unless the page is newer or has no good number."""
    n = page_format(settings, glb_doc)
    j = BAD if n is None else judge(n)
    return j, (newer() if j == NEWER else "This 3D page has no format number Fresing Render understands." if j == BAD
               else "")
