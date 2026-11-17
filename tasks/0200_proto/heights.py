"""Task 0200: where the drawn content of a sidebar picture ends (the rows below it are plain background)."""
import glob
import sys

from PIL import Image

for path in sorted(glob.glob(sys.argv[1] + "/hs_*.png")):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[w // 2, h - 4]
    last = 0
    for y in range(h - 4, -1, -1):
        if any(sum(abs(a - b) for a, b in zip(px[x, y], bg)) > 12 for x in range(4, w - 30, 2)):
            last = y + 1
            break
    print(path.split("/")[-1], "content height", last, "of", h)
