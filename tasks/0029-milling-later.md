# 0029 – Milling, later: no-CAM toolpaths and 4/5-axis

**Who:** worker · **Model:** Opus · **Status:** later (after 0026–0028; owner decides) ·
**Branch:** `task/0029-milling-later` · **Started by:** lead chat, 5 Nov 2026 · **Lane:** Machining

## Goal (to be detailed when it starts)

1. **Milling without a CAM program:** the owner picks the stock and the finished CAD part; the app
   makes a believable roughing + finishing path itself (layers and a parallel finishing pass that
   follows the part's surface – "drop cutter"), so a marketing animation needs no Fusion CAM.
   OpenCAMLib (LGPL, drop-cutter/waterline) does exactly this but has no Python 3.13 wheels
   (latest 2023.1.11: Python 3.7–3.11): build it for Blender's Python on GitHub's runners, or
   write a simple drop-cutter in numpy.
2. **Rotary axes A/B/C** (4th axis, 5-axis): G-code reader and joints already allow rotate
   joints; material removal needs a volume method (dexels/voxels or SDF grids) instead of a
   height map.

---

## Report (filled in by the chat that did the task)
