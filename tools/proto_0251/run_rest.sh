#!/bin/bash
cd /home/user/CAD-render-animation
export PYTHONPATH=/home/user/CAD-render-animation
PY=~/venv/bin/python
BL=~/blender-5.2.3/blender-5.2.3-linux-x64/blender
log() { echo "$(date +%T) $*" >> /tmp/p251/queue.log; }
while pgrep -f "render_s.py pbf" > /dev/null; do sleep 10; done; log s_pbf
rm -rf /tmp/p251/flip96; mkdir -p /tmp/p251/flip96
$BL -b --factory-startup --python tools/proto_0251/flip_s.py -- /tmp/p251/flip96 96 96 > /tmp/p251/flip96.log 2>&1; log flip_bake
FR=$(python3 -c "print(','.join(str(i) for i in range(96)))")
FLIP_RES=96 $BL -b --factory-startup --python-expr "import sys; sys.argv=['render_s.py','flip','/tmp/p251/flip96','/tmp/p251/out_s_flip','$FR','CYCLES']; sys.path.insert(0,'tools/proto_0251'); import render_s; render_s.main()" > /tmp/p251/r_s_flip.log 2>&1; log s_flip
for k in 3 5 4; do
  P251_RES=480x270 P251_SAMPLES=16 P251_STEP=2 $PY tools/proto_0251/machine.py $k /tmp/p251/m$k all CYCLES > /tmp/p251/m$k.log 2>&1; log m$k
done
$PY tools/proto_0251/render_standalone.py /tmp/p251/standalone.npz /tmp/p251/out_sa CYCLES > /tmp/p251/r_sa.log 2>&1; log standalone_videos
P251_RES=640x360 $PY tools/proto_0251/machine.py 3 /tmp/p251/m3_eevee 120,200 EEVEE > /tmp/p251/m3e.log 2>&1; log m3_eevee
P251_RES=640x360 $PY tools/proto_0251/machine.py 3 /tmp/p251/m3_wb 120,200 WORKBENCH > /tmp/p251/m3w.log 2>&1; log m3_wb
log done
