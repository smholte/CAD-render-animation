"""The test kit's model maker: ``python -m fr_test_kit.make <folder> [--small] [--progress <file.json>]``."""

import argparse
import json
import os

from fresing_app.demo_model import geom

from . import BOX, DECK, FILES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--progress", default="")
    a = ap.parse_args(argv)
    if a.progress:
        with open(a.progress, "w", encoding="utf-8") as fh:
            json.dump({"text": "Writing the test box", "done": 0, "total": 1}, fh)
    root = geom.Asm("TEST KIT")
    root.add(geom.Part("TEST DECK", geom.box(0.0, -DECK[1] / 2, -DECK[2], DECK[0], DECK[1], DECK[2]),
                       color=(0.45, 0.47, 0.5)))
    root.add(geom.Part("TEST BOX", geom.box(1000.0, -BOX / 2, 0.0, BOX, BOX, BOX), color=(0.9, 0.45, 0.1)))
    os.makedirs(a.out, exist_ok=True)
    geom.write_step(root, os.path.join(a.out, FILES["assembly"]))
    print("test kit: written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
