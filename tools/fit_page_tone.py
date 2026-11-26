"""Fit the web page's tone curve to the app's (task 0369).

The app renders with Blender's AgX view and the look "AgX - Medium High Contrast" (``blender/render.apply_quality``):
a 3D table (``AgX_Base_sRGB.cube``) and a contrast grade in OpenColorIO. three.js's own AgX is a simpler formula and
draws dark warm colours greyer and lighter (rust 152/98/67 where the app shows 137/68/20). The page uses a curve of
three's form – a 3x3 matrix in, log2, a polynomial, a matrix out, a power, Rec.2020 -> sRGB – with its numbers fitted
to what Blender itself makes of 40,000 colours (``core/web3d_env.TONE``, the same numbers in ``web/fr_page.js``).

    ~/venv/bin/python tools/fit_page_tone.py            # needs bpy (Blender as a module) and scipy (pip install scipy)

Prints the fitted numbers as Python (for ``core/web3d_env.py``) and the errors against Blender in 0 … 255.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def blender_view(x: np.ndarray, look: str = "AgX - Medium High Contrast") -> np.ndarray:
    """What Blender's AgX view with ``look`` makes of linear sRGB ``x`` (n, 3): display sRGB 0 … 1."""
    import bpy
    n = len(x)
    w = 200
    h = (n + w - 1) // w
    px = np.zeros((h * w, 4), np.float32)
    px[:n, :3] = x
    px[:, 3] = 1.0
    img = bpy.data.images.new("fr tone", w, h, float_buffer=True)
    img.pixels.foreach_set(px.ravel())
    sc = bpy.context.scene
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    path = os.path.join(tempfile.mkdtemp(), "tone.png")
    img.save_render(path, scene=sc)
    out = bpy.data.images.load(path)
    out.colorspace_settings.name = "Non-Color"
    a = np.empty(h * w * 4, np.float32)
    out.pixels.foreach_get(a)
    return a.reshape(-1, 4)[:n, :3].astype(np.float64)


def samples(n: int = 40000, seed: int = 1) -> np.ndarray:
    """Surface colours (many dark, some fully saturated) under light from 1/64 to 11 x, and a grey ramp."""
    rng = np.random.default_rng(seed)
    alb = rng.random((n, 3)) ** 2.2
    sat = rng.random(n) < 0.3
    alb[sat] = alb[sat] * (rng.random((int(sat.sum()), 3)) < 0.5)
    x = alb * (2.0 ** rng.uniform(-6, 3.5, n))[:, None]
    grey = 2.0 ** np.linspace(-12, 5, 400)
    return np.vstack([x, np.repeat(grey[:, None], 3, 1)])


def main() -> int:
    from scipy.optimize import least_squares
    from fresing_render.core import web3d_env as env

    x = samples()
    y = blender_view(x)
    grey = (x[:, 0] == x[:, 1]) & (x[:, 1] == x[:, 2])
    weight = np.where(grey, 6.0, 1.0)[:, None]              # grey stays grey

    def res(p):
        return ((env.tone(x, params=env.unpack_tone(p), encode=True) - y) * 255.0 * weight).ravel()

    p0 = env.pack_tone(env.TONE)
    fit = least_squares(res, p0, method="lm", max_nfev=40000, x_scale="jac")
    best = env.unpack_tone(fit.x)
    err = np.abs(env.tone(x, params=best, encode=True) - y) * 255.0
    sat = (x.max(1) - x.min(1)) / np.maximum(x.max(1), 1e-9)
    print(json.dumps({k: (np.round(v, 7).tolist() if hasattr(v, "tolist") else round(float(v), 7))
                      for k, v in best.items()}, indent=1))
    for name, m in (("all", np.ones(len(x), bool)), ("saturation < 0.8", sat < 0.8)):
        print(f"{name}: mean {err[m].mean():.2f}, 99 % {np.percentile(err[m], 99):.1f}, max {err[m].max():.1f}")
    three = np.abs(env.srgb_encode(env.agx_three(x)) - y) * 255.0
    print(f"three.js AgX against the app: mean {three.mean():.2f}, 99 % {np.percentile(three, 99):.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
