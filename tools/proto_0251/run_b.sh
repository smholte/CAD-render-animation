#!/bin/bash
cd /home/user/CAD-render-animation
export PYTHONPATH=/home/user/CAD-render-animation
PY=~/venv/bin/python
log() { echo "$(date +%T) $*" >> /tmp/p251/queue.log; }
for k in 3 5 4; do
  P251_RES=480x270 P251_SAMPLES=16 P251_STEP=2 $PY tools/proto_0251/machine.py $k /tmp/p251/m$k all CYCLES > /tmp/p251/m$k.log 2>&1; log m$k
done
$PY tools/proto_0251/render_standalone.py /tmp/p251/standalone.npz /tmp/p251/out_sa CYCLES > /tmp/p251/r_sa.log 2>&1; log standalone_videos
P251_RES=640x360 $PY tools/proto_0251/machine.py 3 /tmp/p251/m3_eevee 120,200 EEVEE > /tmp/p251/m3e.log 2>&1; log m3_eevee
P251_RES=640x360 $PY tools/proto_0251/machine.py 3 /tmp/p251/m3_wb 120,200 WORKBENCH > /tmp/p251/m3w.log 2>&1; log m3_wb
rm -rf /tmp/p251/out_s_pbf
$PY tools/proto_0251/render_s.py pbf /tmp/p251/s_pbf.npz /tmp/p251/out_s_pbf all CYCLES > /tmp/p251/r_s_pbf.log 2>&1; log s_pbf_video B_done
