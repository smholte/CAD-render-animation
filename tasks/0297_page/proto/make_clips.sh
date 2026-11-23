#!/bin/bash
# Frames of switch_proto.py (mode clips) -> one GIF per look, both directions, real speed + slow motion.
# usage: make_clips.sh <frames dir> <out dir>
set -e
IN=$1; OUT=$2; mkdir -p "$OUT"
for L in A B C D; do
  for SPEED in real slow; do
    args=()
    for D in fresing blender; do
      files=($(ls "$IN"/f_${L}_${D}_*.png | sort))
      n=${#files[@]}
      for i in "${!files[@]}"; do
        f=${files[$i]}
        if [ "$L" = A ]; then d=40
        elif [ $i -lt 2 ]; then d=50                     # before the click
        elif [ $i -ge $((n - 2)) ]; then d=60            # at rest afterwards
        elif [ $SPEED = real ]; then d=2                 # 10 steps x 20 ms ~ the 150 ms slide (GIF counts in 1/100 s)
        else d=14; fi                                    # about 7 x slower
        [ $i -eq $((n - 1)) ] && d=120
        args+=(-delay $d "$f")
      done
    done
    convert -loop 0 "${args[@]}" -layers Optimize "$OUT/look_${L}_${SPEED}.gif"
  done
done
ls -la "$OUT"
