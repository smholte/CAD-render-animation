#!/bin/bash
# 0381: make every variant of <base.blend> and measure each twice.  run_all.sh <base.blend> <prefix>
set -u
H=$(dirname "$0"); B=$1; P=$2; PY=~/venv/bin/python
$PY $H/s1b_camera.py $B > /dev/null 2>&1
VS="base fasteners_gn repeated_gn rigid_gn_x rigid_joined fasteners_off"
for v in $VS; do [ $v = base ] && continue; $PY $H/s3_variants.py $B $v ${P}_$v.blend 2>&1 | tail -1; done
for run in 1 2; do for v in $VS; do f=${P}_$v.blend; [ $v = base ] && f=$B
  $PY $H/s4_measure.py $f ${P}m${run}_$v.json --playback --render > ${P}m${run}_$v.log 2>&1 || echo "FAIL $v"; done; done
echo done
