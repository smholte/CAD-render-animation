"""Study 0270: the pick page ``tasks/0270_page/index.html`` from the renders of ``tools/finish_sheet.py``.

    ~/venv/bin/python tools/finish_page.py --img dist/f/img --out tasks/0270_page

Converts the PNGs to JPG (ImageMagick), one card per finish with its pictures, real size, cost, settings, web-model
bake, verdict and a pick tick; a Copy line at the bottom ("0270 picks: 1, 3, …"), the same way as 0197's page.
Branch-only prototype of study 0270."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# my judgement per finish: (recommended?, effort for 0274, web 3D model, verdict text)
JUDGE = {
    "knurl_diamond": (True, "S", "average (the pattern follows each face's own axis: no shared 0.2 m tile)",
                      "Looks real at once and is exactly the owner's knob. Seamless round every face (whole number of "
                      "teeth), no UV map. Needs the face data written once per mesh (fast, ~ms)."),
    "knurl_straight": (True, "S", "average", "Same machinery as the diamond knurl; one setting apart."),
    "spun": (True, "S", "average (no anisotropy in the web model)",
             "The radial highlight on the cap is the whole look of a spun part; reuses the turned-marks idea on each "
             "face's own centre."),
    "faced": (False, "S", "average", "Visible spiral only in a close-up; spun covers most uses. Cheap add-on to spun."),
    "crosshatch": (True, "M", "holds at 2048 px tiles (normal map); 1024 px blurs it",
                   "Works on the double-curved cup without stretching; on 45° slopes the three projections blend and "
                   "the grid goes softer (visible in the close-up only)."),
    "fabric": (True, "S", "average colour + roughness (0.5 mm threads are 2.5 texels)",
               "Convincing speaker cloth in a product shot; threads show only at close range."),
    "grille": (True, "S", "holds (alpha mask) – pitch must divide 200 mm for a seamless tile",
               "Real see-through holes; far away it becomes the right haze instead of moiré. On the 1 mm test disc "
               "each hole also shows the disc's back face (the dashes in the close-up): fine for a thin sheet, odd "
               "on a thick one."),
    "soft_touch": (True, "S", "plain factors (sheen is lost)",
                   "No pattern: the right numbers (rough 0.6, low specular, sheen) are the whole finish. Almost free."),
    "bead_blasted": (True, "S", "average roughness", "A finish every machine builder uses; cheap, one setting."),
    "shot_blasted": (True, "S", "average roughness + colour", "Bare steel before paint: cheap; good for frames and "
                                                               "fabrication drawings."),
    "hammertone": (True, "S", "holds (colour + normal, 5 mm marks)", "Classic machine paint; colour from the group."),
    "wrinkle": (False, "S", "holds at 2048", "Reads as a wrinkle structure up close; at product distance it is a "
                                              "slightly rough matte paint."),
    "antiskid": (True, "S", "holds", "Decks and walkways of the vessel and the machines; colour from the group."),
    "tread": (True, "M", "holds (8 lenses per 0.2 m tile, seamless)",
              "Bump only: the lenses do not stand out of the silhouette (plate edges stay flat). Good from 0.3 m on."),
    "perforated": (True, "S", "holds (alpha); hex rows do not divide 200 mm – a square pitch for the web or an own "
                              "bake", "Guards, steps, covers; real holes; fades to the right see-through grey far away."),
    "expanded": (True, "M", "holds roughly (alpha + normal)",
                 "Walkways and guards; the strands' slope is only a bump – no real thickness at the openings."),
    "carbon": (False, "M", "colour + normal hold, the alternating sheen is lost",
               "The twill reads on flat faces; on the curved cup the box projection breaks the weave at 45° "
               "(a seam you can see). Fine for flat panels only."),
    "vdi": (True, "S", "average roughness", "Mostly a roughness class with a fine grain in a macro shot; three "
                                            "classes look clearly different. Cheap."),
    "leather": (True, "S", "holds (1.6 mm cells, ~8 texels)", "Cushions, grips, housings; reads well from 0.2 m."),
    "spangle": (True, "S", "colour + roughness hold, sheen per crystal lost",
                "Big galvanised parts look much more real; crystals 9 mm."),
    "weld": (False, "L", "own bake of the bead; the tint needs a per-part bake",
             "Looks right (rippled bead, straw → purple → blue tint) from a line kept on each part + a bead object. "
             "Needs a 'pick the seam' tool, a bead that follows the line and model-update care: a task of its own, "
             "not a finish. Tick it to ask for that task."),
    "as_cast": (True, "S", "holds", "Castings, housings; cast iron gets a better grain too."),
    "rust": (True, "M", "colour holds, the corner build-up (AO) does not", "As a slider next to Wear (0 … 1), not a "
                                                                          "material: flash rust to heavy."),
    "honed": (False, "S", "average", "Only seen when a bore is cut open (section views); cheap add-on to the turned "
                                     "marks."),
    "scraped": (True, "S", "holds (pitch 12.5 mm divides 200 mm)", "The flaked ways of a mill – a detail machine "
                                                                     "people recognise at once."),
    "grip": (False, "S", "average", "Same code as the knurl at 3 mm; flat ends stay plain."),
    "perlage": (False, "M", "the swirl's sheen is lost", "Reads more as scales than as overlapping brushed circles; "
                                                         "would need more work. A niche (covers, watches)."),
}


def jpg(src, dst, width=960, quality=82):
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    subprocess.run(["convert", src, "-resize", f"{width}x", "-quality", str(quality), dst], check=True)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", default="dist/f/img")
    ap.add_argument("--out", default="tasks/0270_page")
    ap.add_argument("--no-convert", action="store_true")
    a = ap.parse_args(argv)
    from fresing_render.blender import finishes_proto as fp   # noqa: needs bpy only for the module's import
    times = json.load(open(os.path.join(a.img, "times.json")))
    imgdir = os.path.join(a.out, "img")
    cards = []
    for fid, spec in fp.FINISHES.items():
        if "n" not in spec:
            continue
        tags = [fid + "_" + v.replace(" ", "") for v in spec.get("variants", {})] or [fid]
        pics = []
        for tag in tags:
            for shot in ("close", "product"):
                src = os.path.join(a.img, f"{tag}_{shot}.png")
                name = f"{tag}_{shot}.jpg"
                if a.no_convert or jpg(src, os.path.join(imgdir, name)):
                    cap = (tag.split("_", 1)[1] + " · " if tag != fid else "") + ("close-up" if shot == "close"
                                                                                else "product shot")
                    pics.append((name, cap))
        row = times.get(tags[0], {})
        parts = []
        for ck, size in (("_960", "960 × 540"), ("", "1920 × 1080")):
            if "cost_pattern_s" + ck in row and "cost_plain_s" + ck in row:
                pl, pa = row["cost_plain_s" + ck], row["cost_pattern_s" + ck]
                parts.append(f"{size}: {pa:.1f} s vs {pl:.1f} s plain ({(pa / pl - 1) * 100:+.0f} %)")
        cost = " · ".join(parts)
        rec, effort, bake, verdict = JUDGE.get(fid, (False, "?", "?", ""))
        cards.append(dict(n=spec["n"], id=fid, label=spec["label"], pics=pics, size=spec["size"],
                          settings=spec["settings"], offer=spec["offer"], source=spec["source"], cost=cost,
                          nodes=row.get("nodes", "?"), rec=rec, effort=effort, bake=bake, verdict=verdict))
    extra = []
    for nm in ("headset.png", "headset_close.png", "copies.png", "far_machine.png", "far_machine_nofade.png",
               "far_far.png", "far_far_nofade.png"):
        if a.no_convert or jpg(os.path.join(a.img, nm), os.path.join(imgdir, nm.replace(".png", ".jpg")), 1600, 84):
            extra.append(nm.replace(".png", ".jpg"))
    # crops of the far shots, 2x, so the shimmer (or its absence) is seen
    for nm in ("far_far.png", "far_far_nofade.png"):
        src = os.path.join(a.img, nm)
        if os.path.exists(src) and not a.no_convert:
            subprocess.run(["convert", src, "-gravity", "center", "-crop", "480x270+0+0", "+repage", "-filter", "point",
                            "-resize", "200%", "-quality", "88", os.path.join(imgdir, nm.replace(".png", "_crop.jpg"))],
                           check=True)
    thumbs = sorted(f for f in os.listdir(a.img) if f.startswith("thumb_") and f.endswith("_32.png"))
    for t in thumbs:
        if not a.no_convert:
            jpg(os.path.join(a.img, t), os.path.join(imgdir, t.replace(".png", ".jpg")), 256, 88)
    write(a.out, cards, extra, times, [t.replace(".png", ".jpg") for t in thumbs])


CSS = """:root{--bg:#fff;--fg:#1c2330;--mut:#5b6573;--line:#d5dae1;--card:#f5f7fa;--acc:#479B29}
@media(prefers-color-scheme:dark){:root{--bg:#16191f;--fg:#e6e9ee;--mut:#9aa4b2;--line:#323946;--card:#1e232b}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:16px}h1{font-size:1.5rem}h2{margin-top:2.2rem;border-bottom:2px solid var(--acc)}
.item{display:flex;gap:12px;border:1px solid var(--line);background:var(--card);border-radius:8px;padding:12px;margin:12px 0}
.pick{flex:0 0 64px;font-size:1.1rem}.pick input{width:20px;height:20px}.star{color:var(--acc)}
.body{flex:1;min-width:0}h3{margin:0 0 6px;font-size:1.05rem}.tag{font-weight:normal;color:var(--mut);font-size:.85rem}
.pics{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px;margin-top:8px}
figure{margin:0}figure img{width:100%;height:auto;border:1px solid var(--line);display:block}
figcaption{color:var(--mut);font-size:.8rem}dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:6px 0;font-size:.92rem}
dt{color:var(--mut)}dd{margin:0}.wide img{width:100%;height:auto;border:1px solid var(--line)}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid var(--line);padding:5px 7px;text-align:left}
.scroll{overflow-x:auto}.thumbs{display:flex;flex-wrap:wrap;gap:8px}.thumbs img{width:128px;height:128px}
#bar{position:sticky;bottom:0;background:var(--bg);border-top:2px solid var(--acc);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
#bar code{flex:1;min-width:240px;word-break:break-word}button{font:inherit;padding:8px 18px;background:var(--acc);color:#fff;border:0;border-radius:6px;cursor:pointer}
@media(max-width:640px){.item{flex-direction:column}.pick{flex:none}}"""


def write(out, cards, extra, times, thumbs):
    e = html.escape
    h = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
         "content='width=device-width,initial-scale=1'><title>0270 new finishes</title><style>", CSS,
         "</style></head><body><main>",
         "<h1>0270 – New finishes: pick what the app should get</h1>",
         "<p>Every picture is the real app's renderer (Cycles, 64 samples, the app's Product studio light) on invented "
         "shapes that came in through the app's own STEP importer – coarse CAD meshes, <b>no UV maps</b>. "
         "Rendered on the 4-core web machine (no graphics card). ★ = my recommendation (ticked to start with). Tick what "
         "task 0274 should build, press <b>Copy</b> and paste the line to the lead.</p>"]
    if "headset.jpg" in extra:
        h.append("<h2>Like the photo: an invented headphone-like set with the best picks</h2>"
                 "<p>Knob: diamond knurl 0.8 mm with spun end · cap: spun aluminium · cups: moulded cross-hatch "
                 "(colour from the group) · headband: soft-touch · yokes: bead-blasted aluminium · cushions: leather "
                 "grain · grille: speaker cloth. 1920 × 1080, 96 samples.</p><div class='wide'>"
                 "<img src='img/headset.jpg' alt='headphone-like set'>"
                 + ("<img src='img/headset_close.jpg' alt='close-up of knob and cup'>" if "headset_close.jpg" in extra
                    else "") + "</div>")
    h.append("<h2>The finishes</h2>")
    for c in sorted(cards, key=lambda c: c["n"]):
        chk = " checked" if c["rec"] else ""
        star = " <span class='star' title='recommended'>★</span>" if c["rec"] else ""
        h.append(f"<section class='item' id='f{c['n']}'><label class='pick'><input type='checkbox' name='pick' "
                 f"value='{c['n']}'{chk}> <b>{c['n']}</b>{star}</label><div class='body'>"
                 f"<h3>{e(c['label'])} <span class='tag'>effort {c['effort']} · {c['nodes']} nodes</span></h3>"
                 f"<p>{e(c['verdict'])}</p><dl>"
                 f"<dt>Real size</dt><dd>{e(c['size'])}</dd>"
                 f"<dt>Direction from</dt><dd>{e(c['source'])}</dd>"
                 f"<dt>Render cost</dt><dd>{e(c['cost'] or 'not measured')} (product shot, 64 samples, 4-core CPU)</dd>"
                 f"<dt>Settings</dt><dd>{e(c['settings'])}</dd>"
                 f"<dt>Offered with</dt><dd>{e(c['offer'])}</dd>"
                 f"<dt>Web 3D model</dt><dd>{e(c['bake'])}</dd></dl><div class='pics'>")
        for name, cap in c["pics"]:
            h.append(f"<figure><a href='img/{name}'><img loading='lazy' src='img/{name}' alt='{e(c['label'])} "
                     f"{e(cap)}'></a><figcaption>{e(cap)}</figcaption></figure>")
        h.append("</div></div></section>")
    if any(x.startswith("far_") for x in extra):
        h.append("<h2>Far away: no shimmer</h2><p>The plate finishes at 4 m (a whole machine in the picture) and 15 m. "
                 "Left: as built (a pattern finer than ~2 pixels fades to its average). Right: the fade switched off – "
                 "regular holes and grids turn into moiré and sparkle. The crops are the centre, enlarged 2×.</p>"
                 "<div class='pics'>")
        for nm, cap in (("far_machine.jpg", "4 m, with fade"), ("far_machine_nofade.jpg", "4 m, fade off"),
                        ("far_far.jpg", "15 m, with fade"), ("far_far_nofade.jpg", "15 m, fade off"),
                        ("far_far_crop.jpg", "15 m, with fade – centre 2×"),
                        ("far_far_nofade_crop.jpg", "15 m, fade off – centre 2×")):
            h.append(f"<figure><a href='img/{nm}'><img loading='lazy' src='img/{nm}' alt='{cap}'></a>"
                     f"<figcaption>{cap}</figcaption></figure>")
        h.append("</div>")
    if "copies.jpg" in extra:
        rs = times.get("_copies", {}).get("reimport_same", {})
        h.append("<h2>Copies, turned, scaled, mirrored</h2><p>Knurled knob (face axes) and scraped block (box axes): as "
                 "imported, turned, scaled ×1.5, mirrored. The pattern sits the same on every copy; a scaled copy's "
                 "pattern grows with it (Inventor parts are not scaled; 0274 can divide by the object's scale). Same "
                 "STEP imported again (a model update): face data identical – "
                 + e(", ".join(f"{k}: {'yes' if v else 'NO'}" for k, v in rs.items())) +
                 ".</p><div class='wide'><img src='img/copies.jpg' alt='copies'></div>")
    th = times.get("_thumbs", {})
    if th:
        h.append("<h2>Thumbnails for the material picker (0273)</h2><p>Proposed swatch: a chamfered block with a "
                 "knurled knob on it and a spun cap leaning in front – shows marks, rings, knurl, holes and grain at "
                 "once. 256 × 256 px, Cycles on the 4-core CPU, 32 samples + denoise:</p><div class='thumbs'>")
        for t in thumbs:
            h.append(f"<img src='img/{t}' alt='{t}'>")
        h.append("</div><div class='scroll'><table><tr><th>Material</th><th>16 samples (s)</th><th>32 samples (s)</th>"
                 "<th>EEVEE (s)</th></tr>")
        for fid in ("plain", "knurl_diamond", "spun", "perforated", "carbon", "hammertone", "crosshatch", "rust"):
            if f"{fid}_16" in th:
                h.append(f"<tr><td>{fid}</td><td>{th.get(f'{fid}_16')}</td><td>{th.get(f'{fid}_32')}</td>"
                         f"<td>{e(str(th.get(f'{fid}_eevee', '–')))}</td></tr>")
        h.append("</table></div>")
    h.append("<div id='bar'><code id='line'></code><button id='copy'>Copy</button></div></main><script>"
             "function upd(){var p=[].slice.call(document.querySelectorAll('input[name=pick]:checked')).map(function(e)"
             "{return e.value}).sort(function(a,b){return a-b});document.getElementById('line').textContent="
             "'0270 picks: '+p.join(', ');}document.addEventListener('change',upd);upd();"
             "document.getElementById('copy').onclick=function(){var t=document.getElementById('line').textContent,"
             "b=this;function fb(){var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);"
             "a.select();try{document.execCommand('copy')}catch(e){}a.remove()}if(navigator.clipboard&&navigator."
             "clipboard.writeText){navigator.clipboard.writeText(t).catch(fb)}else fb();b.textContent='Copied';"
             "setTimeout(function(){b.textContent='Copy'},1500)};</script></body></html>")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w").write("".join(h))
    print("written", os.path.join(out, "index.html"), len(cards), "cards")


if __name__ == "__main__":
    main()
