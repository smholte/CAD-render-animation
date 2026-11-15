"""Task 0133 – the comparison sheets and clips from tools/lesson_looks_app.py's pictures (ImageMagick, no Blender).

    python3 tools/lesson_looks_sheets.py /tmp/looks tasks/img

Writes 0133_buttons.jpg, 0133_sections.jpg, 0133_parts.jpg and 0133_look_<A…F>.gif into the second folder.
"""

import os
import subprocess
import sys
import tempfile

SRC, DST = sys.argv[1], sys.argv[2]
os.makedirs(DST, exist_ok=True)
TMP = tempfile.mkdtemp()
BG, FG, GREEN = "#1A2027", "white", "#5CBF37"
FONT = "DejaVu-Sans"

# the texts of fresing_render/blender/lesson.py (kept short for the sheets)
BUTTONS = {
    "A": "Soft green glow, breathes slowly",
    "B": "Thin outline + moving arrow + step number",
    "C": "Spotlight: the rest of the panel dimmed",
    "D": "Green bar on the left + green tint",
    "E": "Corner brackets close in once, then stay",
    "F": "Blender-blue outline, a light runs round it",
}
SECTIONS = {"1": "Dot with a growing ring", "2": "Whole header tinted green", "3": "Ring at the fold triangle + 'Open'"}
PARTS = {"1": "Glow (see-through green)", "2": "Outline (edges in green)", "3": "The rest faded"}


def im(*args):
    subprocess.run(["convert", *args], check=True)


def label(text, width, size=15, colour=FG, height=None):
    out = os.path.join(TMP, f"l{abs(hash((text, width, size, colour)))}.png")
    extra = ["-extent", f"{width}x{height}"] if height else []
    im("-background", BG, "-fill", colour, "-font", FONT, "-pointsize", str(size), "-size", f"{width}x",
       f"caption:{text or ' '}", "-gravity", "west", *extra, out)
    return out


def column(parts, out):
    im("-background", BG, *parts, "-append", out)
    return out


def row(parts, out, gap=10):
    args = []
    for p in parts:
        args += [p, "-size", f"{gap}x1", f"xc:{BG}"]
    im("-background", BG, *args[:-3], "+append", out)
    return out


def pad(path, n=12):
    im(path, "-bordercolor", BG, "-border", str(n), path)
    return path


# --- buttons: one row per look, step 2 (next to the blue button) and step 3 (two aligned buttons) ---
rows = [row([label("Look", 300, 12, "#AAB", height=26), label("Step 2: Product studio, beside the blue button", 292, 12, "#AAB"),
             label("Step 3: Add rotate joint, aligned with Add slide joint", 292, 12, "#AAB")],
            os.path.join(TMP, "head.png"))]
for k, text in BUTTONS.items():
    lab = label(f"{k}  –  {text}", 300, 17, height=150)
    rows.append(row([lab, os.path.join(SRC, f"b2_{k}.png"), os.path.join(SRC, f"b3_{k}.png")],
                    os.path.join(TMP, f"row_{k}.png")))
title = label("Task 0133 – button looks (test crane, Build it yourself). Clips: 0133_look_A.gif … F.gif", 904, 16,
              GREEN)
out = column([title] + rows, os.path.join(TMP, "buttons.png"))
im(pad(out), "-quality", "88", os.path.join(DST, "0133_buttons.jpg"))

# --- sections: step 7, 6 Animation closed ---
cells = []
for k, text in SECTIONS.items():
    cells.append(column([label(f"{k}  –  {text}", 292, 14, height=30), os.path.join(SRC, f"section_{k}.png")],
                        os.path.join(TMP, f"sec_{k}.png")))
title = label("Task 0133 – a closed section that holds the next button (step 7: open 6 Animation)", 896, 16, GREEN)
out = column([title, row(cells, os.path.join(TMP, "secrow.png"))], os.path.join(TMP, "sections.png"))
im(pad(out), "-quality", "88", os.path.join(DST, "0133_sections.jpg"))

# --- parts: step 3, the boom ---
cells = []
for k, text in PARTS.items():
    small = os.path.join(TMP, f"part_{k}.png")
    im(os.path.join(SRC, f"part_{k}.png"), "-gravity", "center", "-crop", "70%x62%+0+20", "+repage", "-resize",
       "520x", small)
    cells.append(column([label(f"{k}  –  {text}", 520, 15, height=30), small], os.path.join(TMP, f"pc_{k}.png")))
title = label("Task 0133 – the part on the model (step 3: the boom), the same text card", 1580, 16, GREEN)
out = column([title, row(cells, os.path.join(TMP, "partrow.png"))], os.path.join(TMP, "parts.png"))
im(pad(out), "-quality", "85", os.path.join(DST, "0133_parts.jpg"))

# --- one clip per button look: the frames at their real times, looped ---
for k in BUTTONS:
    d = os.path.join(SRC, f"clip_{k}")
    if not os.path.isdir(d):
        continue
    times = [float(t) for t in open(os.path.join(d, "times.txt")).read().split()]
    frames = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    args = []
    for i, f in enumerate(frames):
        dt = (times[i + 1] - times[i]) if i + 1 < len(times) else (times[-1] - times[0]) / max(len(times) - 1, 1)
        args += ["-delay", str(max(2, round(dt * 100))), os.path.join(d, f)]
    gif = os.path.join(DST, f"0133_look_{k}.gif")
    im(*args, "-loop", "0", "-colors", "96", "-layers", "Optimize", gif)
    print(gif, os.path.getsize(gif), "bytes")
for n in ("buttons", "sections", "parts"):
    p = os.path.join(DST, f"0133_{n}.jpg")
    print(p, os.path.getsize(p), "bytes")
