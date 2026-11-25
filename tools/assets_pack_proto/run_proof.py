"""Task 0344 proof driver (study files only): run every step of ``try_pack.py`` in its own Blender and collect
the numbers in ``<work>/results.json`` and a Markdown table ``<work>/results.md``.

    python3 tools/assets_pack_proto/run_proof.py <blender> <work folder>

Plain Python (no bpy). Makes the test pack 1.0.0 and 1.1.0 first when they are not there.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
METHODS = ("append_ext", "append_packed", "link", "link_packed")


def blender(exe: str, script: str, *args: str) -> str:
    cmd = [exe, "-b", "--factory-startup", "--python", os.path.join(HERE, script), "--", *args]
    t0 = time.perf_counter()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    out = p.stdout + p.stderr
    if p.returncode != 0 or "Traceback" in out:
        print(out[-4000:])
        raise SystemExit(f"failed: {' '.join(args[:2])}")
    print(f"  {script} {args[0] if args else ''} {' '.join(os.path.basename(a) for a in args[1:4])}: "
          f"{time.perf_counter() - t0:.1f} s")
    return out


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extras(exe: str, work: str) -> dict:
    """Variant: the pack's own .blend files hold their pictures packed (as 0286's remote library did). Then
    'link + pack' carries the pictures too. And: can packed pictures use Cycles' texture cache (.tx)?"""
    out = {}
    pp10, pp11 = os.path.join(work, "pack10p"), os.path.join(work, "pack11p")
    for folder, ver in ((pp10, "1.0.0"), (pp11, "1.1.0")):
        if not os.path.exists(os.path.join(folder, "fresing_assets", "pack.json")):
            blender(exe, "make_test_pack.py", folder, ver, "packed")
    r10, r11 = os.path.join(pp10, "fresing_assets"), os.path.join(pp11, "fresing_assets")
    out["pack_bytes_packed_variant"] = sum(os.path.getsize(os.path.join(dp, n)) for dp, _, ns in os.walk(r10)
                                           for n in ns if n.endswith(".blend"))
    for m in ("link_packed", "append"):
        d = os.path.join(work, "p_" + m)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        proj = os.path.join(d, "project.blend")
        blender(exe, "try_pack.py", "bring", r10, proj, m if m != "append" else "append_ext", os.path.join(d, "b.json"))
        row = {"bring": load(os.path.join(d, "b.json"))}
        client = os.path.join(work, "p_" + m + "_client")
        shutil.rmtree(client, ignore_errors=True)
        os.makedirs(client)
        shutil.copy2(proj, os.path.join(client, "project.blend"))
        os.rename(pp10, pp10 + "_hidden")
        try:
            blender(exe, "try_pack.py", "open", os.path.join(client, "project.blend"), os.path.join(client, "o.json"),
                    "render")
        finally:
            os.rename(pp10 + "_hidden", pp10)
        row["client_without_pack"] = load(os.path.join(client, "o.json"))
        upd = os.path.join(work, "p_" + m + "_update")
        shutil.rmtree(upd, ignore_errors=True)
        os.makedirs(upd)
        shutil.copy2(proj, os.path.join(upd, "project.blend"))
        blender(exe, "try_pack.py", "update", os.path.join(upd, "project.blend"), r11, os.path.join(upd, "u.json"))
        row["update"] = load(os.path.join(upd, "u.json"))
        # the updated project on a client's PC: does it still stand alone?
        uc = os.path.join(work, "p_" + m + "_update_client")
        shutil.rmtree(uc, ignore_errors=True)
        os.makedirs(uc)
        shutil.copy2(row["update"]["saved"], os.path.join(uc, "project.blend"))
        os.rename(pp11, pp11 + "_hidden")
        try:
            blender(exe, "try_pack.py", "open", os.path.join(uc, "project.blend"), os.path.join(uc, "o.json"), "render")
        finally:
            os.rename(pp11 + "_hidden", pp11)
        row["updated_client_without_pack"] = load(os.path.join(uc, "o.json"))
        out[m] = row
    p10 = os.path.join(work, "pack10", "fresing_assets")
    o = os.path.join(work, "mem_4k_packed_tx.json")
    blender(exe, "try_pack.py", "memory", p10, "4k", "packed_tx", o)
    out["memory_4k_packed_tx"] = load(o)
    return out


def main():
    exe, work = sys.argv[1], os.path.abspath(sys.argv[2])
    if len(sys.argv) > 3 and sys.argv[3] == "--extras":
        res = load(os.path.join(work, "results.json"))
        res["extras"] = extras(exe, work)
        with open(os.path.join(work, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        print(json.dumps(res["extras"], indent=1)[:6000])
        return
    os.makedirs(work, exist_ok=True)
    p10, p11 = os.path.join(work, "pack10"), os.path.join(work, "pack11")
    for folder, ver in ((p10, "1.0.0"), (p11, "1.1.0")):
        if not os.path.exists(os.path.join(folder, "fresing_assets", "pack.json")):
            blender(exe, "make_test_pack.py", folder, ver)
    r10, r11 = os.path.join(p10, "fresing_assets"), os.path.join(p11, "fresing_assets")
    res = {"blender": exe, "methods": {}}

    for m in METHODS:
        d = os.path.join(work, m)
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
        proj = os.path.join(d, "project.blend")
        row = {}
        blender(exe, "try_pack.py", "bring", r10, proj, m, os.path.join(d, "bring.json"))
        row["bring"] = load(os.path.join(d, "bring.json"))
        blender(exe, "try_pack.py", "open", proj, os.path.join(d, "open_with_pack.json"), "render")
        row["with_pack"] = load(os.path.join(d, "open_with_pack.json"))
        # a client's PC: the project file alone, in another folder, and no pack anywhere
        client = os.path.join(work, m + "_client")
        shutil.rmtree(client, ignore_errors=True)
        os.makedirs(client)
        shutil.copy2(proj, os.path.join(client, "project.blend"))
        hidden = p10 + "_hidden"
        os.rename(p10, hidden)
        try:
            blender(exe, "try_pack.py", "open", os.path.join(client, "project.blend"),
                    os.path.join(client, "open_without_pack.json"), "render")
        finally:
            os.rename(hidden, p10)
        row["client_without_pack"] = load(os.path.join(client, "open_without_pack.json"))
        # "Use the new Fresing looks": pack 1.0.0 -> 1.1.0
        upd = os.path.join(work, m + "_update")
        shutil.rmtree(upd, ignore_errors=True)
        os.makedirs(upd)
        shutil.copy2(proj, os.path.join(upd, "project.blend"))
        try:
            blender(exe, "try_pack.py", "update", os.path.join(upd, "project.blend"), r11,
                    os.path.join(upd, "update.json"))
            row["update"] = load(os.path.join(upd, "update.json"))
            blender(exe, "try_pack.py", "open", row["update"]["saved"], os.path.join(upd, "open_updated.json"),
                    "render")
            row["updated_open"] = load(os.path.join(upd, "open_updated.json"))
        except SystemExit as e:
            row["update"] = {"failed": str(e)}
        res["methods"][m] = row

    blender(exe, "try_pack.py", "reuse", r10, os.path.join(work, "reuse.json"))
    res["reuse_local_id"] = load(os.path.join(work, "reuse.json"))

    res["memory"] = []
    for k in ("1k", "2k", "4k"):
        for mode in ("ext", "tx", "packed"):
            out = os.path.join(work, f"mem_{k}_{mode}.json")
            blender(exe, "try_pack.py", "memory", r10, k, mode, out)
            res["memory"].append(load(out))

    res["pack_bytes"] = {k: sum(os.path.getsize(os.path.join(dp, n)) for dp, _, ns in os.walk(r) for n in ns)
                         for k, r in (("1.0.0", r10), ("1.1.0", r11))}
    with open(os.path.join(work, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    lines = ["| Method | bring ms | save ms | project kB | open ms (pack) | client: missing libs / pictures / "
             "placeholders | client render magenta / mean | update ms | after update kB |",
             "|---|---|---|---|---|---|---|---|---|"]
    for m, row in res["methods"].items():
        b, w, c, u = row["bring"], row["with_pack"], row["client_without_pack"], row.get("update", {})
        lines.append(f"| {m} | {b['bring_ms']} | {b['save_ms']} | {b['bytes'] // 1024} | {w['open_ms']} | "
                     f"{c['missing_libraries']} / {c['missing_images']} / {c['placeholders']} | "
                     f"{c.get('magenta_share')} / {c.get('mean_rgb')} | {u.get('update_ms', u.get('failed'))} | "
                     f"{u.get('bytes', 0) // 1024} |")
    lines += ["", "| Pictures | mode | render ms | Cycles memory MB (its stats line) | .tx kB | project kB |",
              "|---|---|---|---|---|---|"]
    for r in res["memory"]:
        lines.append(f"| {r['k']} | {r['mode']} | {r['render_ms']} | {r['cycles_mem_mb']} | "
                     f"{r['tx_bytes'] // 1024} | {r['project_bytes'] // 1024} |")
    with open(os.path.join(work, "results.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
