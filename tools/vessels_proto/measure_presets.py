"""Apply the presets to invented hulls and print / store the numbers (study 0312)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vessels_proto import hulls, presets as P

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)


def hull_of(p):
    if p.hull == "cat":
        return hulls.catamaran(p.length, p.beam, p.beam * 0.3, p.depth, p.draught + 0.3)
    if p.hull == "box":
        return hulls.box(p.length, p.beam, p.depth, -p.draught)
    return hulls.monohull(p.length, p.beam, p.depth, p.draught + 0.6)


rows = []
for p in P.KINDS:
    v, f = hull_of(p)
    t = time.perf_counter()
    r = P.apply(p, v, f)
    r["ms"] = (time.perf_counter() - t) * 1000
    r["key"] = p.key
    r["tris"] = len(f)
    rows.append(r)
    print(f"{p.key:9s} L{p.length:5.0f} B{p.beam:4.1f} -> draught {r['draught']:.2f} m (preset {p.draught}), "
          f"LWL {r['lwl']:.1f}, Cb {r['cb']:.2f}, roll {r['roll_period']:.1f} s -> GM {r['gm']:.2f} m, KG {r['kg_share']*100:.0f} % of depth, "
          f"heave {r['heave_period']:.1f} s, {r['tris']} tris, {r['ms']:.0f} ms")
json.dump(rows, open(os.path.join(OUT, "presets.json"), "w"), indent=1)
