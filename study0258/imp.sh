#!/bin/bash
# Task 0258 (throw-away): import at Normal 3 times, print time and triangles
f=$1; for i in 1 2 3; do rm -rf /tmp/imp258; s=$(date +%s.%N); ~/venv/bin/python -m fresing_render.importer.step_reader "$f" /tmp/imp258 --quality normal >/dev/null 2>&1; e=$(date +%s.%N);
 tri=$(~/venv/bin/python -c "
import numpy as np,glob
z=np.load(glob.glob('/tmp/imp258/*.npz')[0]); print(sum(z[k].shape[0] for k in z.files if k.startswith('t') and z[k].ndim==2 and z[k].shape[1]==3))" 2>&1 | tail -1)
 echo "$(basename $f) $(echo "$e - $s" | bc) s  tris=$tri"; done
