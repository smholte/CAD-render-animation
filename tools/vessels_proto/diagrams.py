"""Top views and profiles of study 0312 (matplotlib) -> tasks/0312_page/img/*.png, out/extra.json."""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from vessels_proto import presets as P, drive as D, shore as SH, floaters as FL
from fresing_render.core import sea as sea_core

OUT = os.path.join(HERE, "out")
IMG = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tasks", "0312_page", "img")
GREEN, GREY, ORANGE, BLUE = "#479B29", "#5b6573", "#d9480f", "#1f5fa8"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def outline(ax, x, y, psi, L, B, color):
    ol = FL.hull_outline(L, B)
    c, s = math.cos(psi), math.sin(psi)
    pts = np.column_stack([x + c * ol[:, 0] - s * ol[:, 1], y + s * ol[:, 0] + c * ol[:, 1]])
    ax.fill(pts[:, 0], pts[:, 1], color=color, alpha=0.8, lw=0)


# 1 drive -> path
rec = np.load(os.path.join(OUT, "drive_rec.npy"))
ctv = P.BY_KEY["CTV"]
ep = D.smooth(rec, ctv.length)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 4.0), gridspec_kw={"width_ratios": [1.5, 1]})
a1.plot(rec[:, 1], rec[:, 2], color=GREY, lw=3, alpha=0.35, label=f"driven with the keys ({len(rec)} samples)")
a1.plot(ep.path.dense[:, 0], ep.path.dense[:, 1], color=GREEN, lw=1.4, label="the editable path")
a1.plot(ep.points[:, 0], ep.points[:, 1], "o", color=GREEN, ms=5, label=f"{len(ep.points)} path points to drag")
for k in range(0, len(rec), 300):
    outline(a1, rec[k, 1], rec[k, 2], rec[k, 3], ctv.length, ctv.beam, ORANGE)
a1.set_aspect("equal")
a1.set_xlabel("m")
a1.legend(loc="upper left", fontsize=8, frameon=False)
a1.set_title("A crew transfer vessel driven 80 s with the keyboard", fontsize=10)
seg = np.r_[0.0, np.cumsum(np.hypot(*np.diff(rec[:, 1:3], axis=0).T))]
a2.plot(seg, rec[:, 4] / D.KNOT, color=GREY, lw=3, alpha=0.35, label="recorded speed")
a2.plot(ep.speed_keys[:, 0], ep.speed_keys[:, 1], "o-", color=GREEN, ms=4, lw=1.2,
        label=f"{len(ep.speed_keys)} speed keys")
a2.set_xlabel("m along the path")
a2.set_ylabel("knots")
a2.legend(fontsize=8, frameon=False)
a2.set_title("Speed along it", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "drive_path.png"), dpi=130)
plt.close(fig)

# 2 follow a drawn path
drawn = np.load(os.path.join(OUT, "drawn.npy"))
fig, ax = plt.subplots(figsize=(8.4, 4.6))
from fresing_render.core import camera_path
dp = camera_path.Path(np.column_stack([drawn, np.zeros(len(drawn))]))
ax.plot(dp.dense[:, 0], dp.dense[:, 1], "--", color="black", lw=1.2, label="the path drawn on the water")
ax.plot(drawn[:, 0], drawn[:, 1], "s", color="black", ms=4)
for key, col in (("TUG", BLUE), ("CTV", ORANGE), ("PSV", GREEN)):
    r = np.load(os.path.join(OUT, f"follow_{key}.npy"))
    p = P.BY_KEY[key]
    ax.plot(r[:, 1], r[:, 2], color=col, lw=1.6, label=f"{p.name} ({p.length:.0f} m) drives it")
    for k in range(0, len(r), max(len(r) // 7, 1)):
        outline(ax, r[k, 1], r[k, 2], r[k, 3], p.length, p.beam, col)
ax.set_aspect("equal")
ax.legend(fontsize=8, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
ax.set_xlabel("m")
ax.set_title("One drawn path, three vessels: each drives it as it can", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "follow.png"), dpi=130)
plt.close(fig)

# 3 floaters top view
fl = np.load(os.path.join(OUT, "floaters.npy"))
tr = np.load(os.path.join(OUT, "floaters_tug.npy"))
tug = P.BY_KEY["TUG"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.6), gridspec_kw={"width_ratios": [1.6, 1]})
sel = (tr[:, 1] > -40) & (tr[:, 1] < 80)
a1.plot(tr[sel, 1], tr[sel, 2], color=BLUE, lw=1, alpha=0.6)
for t in (40.0, 45.7, 50.0):
    i = np.searchsorted(tr[:, 0], t)
    outline(a1, tr[i, 1], tr[i, 2], tr[i, 3], tug.length, tug.beam, BLUE)
for j, (name, col) in enumerate((("container 20 ft, 10 t inside", ORANGE), ("buoy", "#c99a00"), ("pallet", GREY))):
    a1.plot(fl[:, 1 + 6 * j], fl[:, 2 + 6 * j], color=col, lw=2, label=name)
    a1.plot(fl[0, 1 + 6 * j], fl[0, 2 + 6 * j], "o", color=col, ms=4)
a1.annotate("hit at 45.7 s", (fl[np.searchsorted(fl[:, 0], 45.7), 1], fl[np.searchsorted(fl[:, 0], 45.7), 2]),
            (-30, 25), fontsize=8, arrowprops=dict(arrowstyle="->", lw=0.8))
a1.set_aspect("equal")
a1.set_xlim(-40, 80)
a1.legend(fontsize=8, frameon=False, loc="upper left")
a1.set_title("Tug at 7 kn through floating things (60 s, from above)", fontsize=10)
a2.plot(fl[:, 0], fl[:, 3], color=ORANGE, lw=1.2, label="container: height (m)")
a2.plot(fl[:, 0], np.degrees(fl[:, 4]) / 10, color=GREY, lw=1, label="container: roll / 10 (°)")
a2.axvline(45.7, color="black", lw=0.6, ls=":")
a2.set_xlabel("s")
a2.legend(fontsize=8, frameon=False)
a2.set_title("It rides the waves, the bow wave rolls it", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "floaters.png"), dpi=130)
plt.close(fig)

# 4 shore profile
fig, ax = plt.subplots(figsize=(8.0, 3.4))
for bft, col in ((3.0, BLUE), (5.0, ORANGE)):
    sh = SH.Shore(sea_core.components(bft, 20.0))
    xs, Phi, A, KX, foam, q, hs = sh.tables()
    ax.plot(xs, hs, color=col, lw=1.6, label=f"wave height Hs, Beaufort {bft:g}")
    ax.fill_between(xs, 0, foam * hs.max() * 0.4, color=col, alpha=0.18, lw=0, label=f"breaking (foam), Bft {bft:g}")
ax2 = ax.twinx()
ax2.plot(xs, -sh.depth(xs), color="black", lw=1)
ax2.set_ylabel("sea floor (m)")
ax.set_xlim(-400, 5)
ax.set_xlabel("m from the waterline on the beach")
ax.set_ylabel("Hs (m)")
ax.legend(fontsize=8, frameon=False, loc="upper left")
ax.set_title("Waves feel the bottom (slope 1:30): shorter, steeper, then they break", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(IMG, "shore.png"), dpi=130)
plt.close(fig)

# 5 push-on: how much the CTV's bow moves up and down at a boat landing (plane fit under the hull, 120 s)
extra = {}
for bft in (3.0, 4.0, 5.0):
    comps = sea_core.components(bft, 20.0)
    L, B = ctv.length * 0.8, ctv.beam * 0.8
    U, V = np.meshgrid(np.linspace(-L / 2, L / 2, 9), np.linspace(-B / 2, B / 2, 5), indexing="ij")
    zs = []
    for t in np.arange(0, 120, 0.1):
        H = sea_core.height(U.ravel(), V.ravel(), t, comps)
        A_ = np.column_stack([np.ones(U.size), U.ravel(), V.ravel()])
        c = np.linalg.lstsq(A_, H, rcond=None)[0]
        zs.append(c[0] + c[1] * ctv.length / 2)
    zs = np.array(zs)
    extra[f"bft{bft:g}"] = {"hs": sea_core.hs(comps), "bow_up_down_m": float(zs.max() - zs.min()),
                           "bow_speed_max_ms": float(np.abs(np.diff(zs)).max() / 0.1)}
print(extra)
json.dump(extra, open(os.path.join(OUT, "pushon.json"), "w"), indent=1)
