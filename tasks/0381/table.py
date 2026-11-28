"""0381: the two runs of each variant as one table (median of 2 = mean)."""
import json, sys
P = sys.argv[1]
VS = "base fasteners_gn repeated_gn rigid_gn_x rigid_joined fasteners_off".split()
K = ("objects", "ids_in_depsgraph", "drag_ms", "lone_empty_ms", "playback_ms_frame", "build_s", "render_s", "open_s",
     "save_mb", "save_s", "rss_after_open_mb", "render_rss_gain_mb", "peak_rss_mb")
print("| " + " | ".join(["variant"] + list(K)) + " |")
for v in VS:
    a = [json.load(open(f"{P}m{r}_{v}.json")) for r in (1, 2)]
    row = []
    for k in K:
        xs = [x.get(k) for x in a]
        row.append(str(round(sum(xs) / 2, 2)) if all(isinstance(x, (int, float)) for x in xs) else str(xs))
    print("| " + " | ".join([v] + row) + " |")
    print("   picks", [(p["object"], p["same_as_instance_matrix"]) for p in a[0]["picks"]], a[0].get("playback_error"))
