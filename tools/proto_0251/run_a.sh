#!/bin/bash
cd /home/user/CAD-render-animation
BL=~/blender-5.2.3/blender-5.2.3-linux-x64/blender
log() { echo "$(date +%T) $*" >> /tmp/p251/queue.log; }
while pgrep -f "flip_s.py" > /dev/null; do sleep 10; done; log flip_bake
FR=$(python3 -c "print(','.join(str(i) for i in range(96)))")
FLIP_RES=96 $BL -b --factory-startup --python-expr "import sys; sys.argv=['render_s.py','flip','/tmp/p251/flip96','/tmp/p251/out_s_flip','$FR','CYCLES']; sys.path.insert(0,'tools/proto_0251'); import render_s; render_s.main()" > /tmp/p251/r_s_flip.log 2>&1; log s_flip A_done
