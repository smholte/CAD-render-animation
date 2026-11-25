"""Task 0344 proof, second pass of ``web3d_measure.py`` (study files only): the same exported pages shot again from
two set camera places, so the background and the pictures can be judged where they show.

    python3 tools/assets_pack_proto/web3d_views.py <work folder of web3d_measure.py>

* background pages (``bg_BEST`` / ``bg_BALANCED`` / ``bg_PHONE``): a level view of the test crane from 10 m, so the
  made-up photo's horizon (buildings, sky) fills the top of the picture;
* picture pages (``tex_2048`` / ``tex_1024`` / ``tex_512``): 0.8 m in front of the base plate's front face (5 x 0.5 m,
  the pack's concrete, one picture per 0.2 m).

Camera places are three.js coordinates (x, z, -y of Blender) for ``frPage.setCamera``. Plain Python + node +
ImageMagick. Adds ``views`` to ``web3d_measure.json`` and writes the crops for the pick page.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHOT = os.path.join(ROOT, "tools", "web3d_env_shot.js")
W, H = 960, 540
LEVEL = ([11.51, 1.73, 5.53], [4.30, 1.43, -1.68])          # Blender eye (11.51, -5.53, 1.73) -> target (4.3, 1.68, 1.43)
CLOSE = ([2.50, 0.30, 0.80], [2.50, 0.25, 0.0])             # Blender eye (2.5, -0.8, 0.3) -> the plate's front face


def shoot(html: str, png: str, place) -> dict:
    ev = f"frPage.setCamera({json.dumps(place[0])}, {json.dumps(place[1])})"
    r = subprocess.run(["node", SHOT, html, png, str(W), str(H), "--query=quality=BEST&auto=0&t=1&soft=0",
                        "--hide-ui", "--wait=2500", f"--eval={ev}"], capture_output=True, text=True, timeout=600)
    try:
        return json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    except ValueError:
        return {"ok": False, "raw": (r.stdout + r.stderr)[-500:]}


def pixels(png: str) -> np.ndarray:
    raw = subprocess.run(["convert", png, "-depth", "8", "rgb:-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)


def cost(a: str, b: str, box=None) -> dict:
    x, y = pixels(a), pixels(b)
    if box:
        x0, y0, x1, y1 = box
        x, y = x[y0:y1, x0:x1], y[y0:y1, x0:x1]
    d = np.abs(x - y)
    mse = float((d ** 2).mean())
    return {"mean_abs": round(float(d.mean()), 2), "p99_abs": round(float(np.percentile(d, 99)), 1),
            "psnr_db": round(10 * math.log10(255 ** 2 / mse), 1) if mse > 0 else None}


def crops(pngs, labels, box, out_jpg, scale=2):
    x0, y0, x1, y1 = box
    tiles = []
    for p, lab in zip(pngs, labels):
        t = p + ".crop.png"
        subprocess.run(["convert", p, "-crop", f"{x1 - x0}x{y1 - y0}+{x0}+{y0}", "+repage", "-filter", "point",
                        "-resize", f"{scale * 100}%", "-gravity", "south", "-background", "#222428", "-fill", "white",
                        "-font", "DejaVu-Sans", "-pointsize", "14", "-splice", "0x24", "-annotate", "+0+4", lab, t],
                       check=True)
        tiles.append(t)
    subprocess.run(["montage", *tiles, "-tile", f"{len(tiles)}x1", "-geometry", "+3+3", "-background", "#222428",
                    "-quality", "86", out_jpg], check=True)


def main():
    work = os.path.abspath(sys.argv[1])
    res = json.load(open(os.path.join(work, "web3d_measure.json"), encoding="utf-8"))
    views = {"level": {}, "close": {}}
    for q in ("BEST", "BALANCED", "PHONE"):
        views["level"][q] = shoot(os.path.join(work, f"bg_{q}.html"), os.path.join(work, f"lv_{q}.png"), LEVEL)
    views["level"]["BEST_again"] = shoot(os.path.join(work, "bg_BEST.html"), os.path.join(work, "lv_BEST_again.png"),
                                         LEVEL)
    for s in (2048, 1024, 512):
        views["close"][str(s)] = shoot(os.path.join(work, f"tex_{s}.html"), os.path.join(work, f"cl_{s}.png"), CLOSE)
    views["close"]["2048_again"] = shoot(os.path.join(work, "tex_2048.html"), os.path.join(work, "cl_2048_again.png"),
                                         CLOSE)
    sky = (0, 0, W, int(H * 0.45))                              # above the model's top: the horizon and the sky
    ref = os.path.join(work, "lv_BEST.png")
    views["level_cost"] = {"noise_floor": cost(ref, os.path.join(work, "lv_BEST_again.png"), sky),
                           **{q: {"sky": cost(ref, os.path.join(work, f"lv_{q}.png"), sky),
                                  "all": cost(ref, os.path.join(work, f"lv_{q}.png"))} for q in ("BALANCED", "PHONE")}}
    cref = os.path.join(work, "cl_2048.png")
    mid = (120, 60, W - 120, H - 60)
    views["close_cost"] = {"noise_floor": cost(cref, os.path.join(work, "cl_2048_again.png"), mid),
                           **{s: {"mid": cost(cref, os.path.join(work, f"cl_{s}.png"), mid),
                                  "all": cost(cref, os.path.join(work, f"cl_{s}.png"))} for s in ("1024", "512")}}
    res["views"] = views
    with open(os.path.join(work, "web3d_measure.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    crops([os.path.join(work, f"lv_{q}.png") for q in ("BEST", "BALANCED", "PHONE")],
          ["Background 4096 px (Best)", "2048 px (Balanced)", "1024 px (Phone)"],
          (W // 2 - 150, int(H * 0.18), W // 2 + 150, int(H * 0.18) + 150), os.path.join(work, "web3d_background.jpg"))
    crops([os.path.join(work, f"cl_{s}.png") for s in (2048, 1024, 512)],
          ["Pictures 2048 px per 0.2 m", "1024 px (the default)", "512 px"],
          (W // 2 - 150, H // 2 - 75, W // 2 + 150, H // 2 + 75), os.path.join(work, "web3d_pictures.jpg"))
    print(json.dumps({k: v for k, v in views.items() if k.endswith("cost")}, indent=1))
    for k in ("level", "close"):
        print(k, {n: (v.get("ok"), v.get("level"), v.get("camera")) for n, v in views[k].items()})


main()
