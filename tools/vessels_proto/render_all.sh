#!/bin/bash
# all pictures and clips of study 0312 (one at a time: the web machine has 4 cores)
set -e
cd "$(dirname "$0")/../.."
PY=~/venv/bin/python
for s in vessels beach under; do $PY tools/vessels_proto/render_scenes.py $s 2>&1 | grep -E "still|under |rror"; done
for s in vessels beach under; do $PY tools/vessels_proto/render_scenes.py $s --clip --small 2>&1 | grep -E "frames in|rror"; done
echo ALL DONE
