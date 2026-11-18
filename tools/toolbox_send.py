"""Send a house to Fresing Render through the Toolbox folder the way House Planner will (task 0217; not shipped).

    python tools/toolbox_send.py "C:\\Users\\me\\Downloads\\My house.hpscene" [--title "My house – version 3"]
    python tools/toolbox_send.py --status            # what happened to the jobs sent so far

Until House Planner sends houses itself, this plays its side: it writes House Planner's manifest into the Toolbox folder
(when it has none) and the house as a job into Fresing Render's inbox. Fresing Render (open, or at its next start)
shows "From House Planner: …" with Bake now in 5 Scene & Render > House from House Planner; the baked package comes back
as a job in ``Toolbox/tools/nl.fresing.house-planner/inbox/``. ``TOOLBOX_HOME`` names another folder (tests).
Plain Python 3.10+, no Blender: run it with any Python, or with the Python inside Fresing Render's Blender folder.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fresing_render.core import toolbox as tb  # noqa: E402


def status(root: Path) -> int:
    inbox = root / "tools" / tb.ME / "inbox"
    if not inbox.is_dir():
        print(f"No Fresing Render inbox in {root} (start Fresing Render once)")
        return 1
    for d in sorted(inbox.iterdir()):
        try:
            job = json.loads((d / "job.json").read_text("utf-8"))
            st = json.loads((d / "status.json").read_text("utf-8")) if (d / "status.json").is_file() else {}
        except (OSError, ValueError):
            continue
        print(f"{d.name}  {job.get('title', '')}: {st.get('state', 'not seen yet')} – {st.get('text', '')}")
        if st.get("reply"):
            print(f"    reply: {root / 'tools' / tb.HOUSE_PLANNER / 'inbox' / st['reply']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("hpscene", nargs="?", help="the house exported from House Planner (.hpscene)")
    ap.add_argument("--title", default="", help="what Fresing Render shows (default: the file's name)")
    ap.add_argument("--status", action="store_true", help="list the jobs in Fresing Render's inbox and their status")
    a = ap.parse_args(argv)
    root = tb.home()
    if a.status:
        return status(root)
    if not a.hpscene:
        ap.error("name the .hpscene file to send (or --status)")
    src = Path(a.hpscene)
    if not src.is_file():
        print(f"No such file: {src}")
        return 1
    if not (root / "tools" / tb.ME / "toolbox.json").is_file():
        print(f"Fresing Render has no manifest in {root}: start Fresing Render once (it makes the folder), then try again")
        return 1
    try:
        jid = tb.play_house_planner(root, src, a.title or src.stem)
    except (ValueError, OSError) as e:
        print(f"Not sent: {e}")
        return 1
    print(f"Sent: {root / 'tools' / tb.ME / 'inbox' / jid}")
    print("In Fresing Render: 5 Scene & Render > House from House Planner > Bake now")
    return 0


if __name__ == "__main__":
    sys.exit(main())
