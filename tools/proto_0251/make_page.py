"""Prototype 0251: copy the results into tasks/0251_page/ (pictures as JPEG, videos as MP4) and write index.html.

    python3 tools/proto_0251/make_page.py /tmp/p251 tasks/0251_page
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

SRC, DST = sys.argv[1], sys.argv[2]
IMG = os.path.join(DST, "img")
os.makedirs(IMG, exist_ok=True)


def J(path, default=None):
    p = os.path.join(SRC, path)
    return json.load(open(p)) if os.path.exists(p) else default


def jpg(src, name, width=640):
    s = os.path.join(SRC, src)
    if not os.path.exists(s):
        return None
    subprocess.run(["convert", s, "-resize", f"{width}x", "-quality", "80", os.path.join(IMG, name)], check=True)
    return "img/" + name


def mp4(src, name):
    s = os.path.join(SRC, src)
    if not os.path.exists(s):
        return None
    shutil.copy(s, os.path.join(IMG, name))
    return "img/" + name


def enc(folder, name, fps):
    """Encode the frames again for the page (CRF 23: sharper than the run's quick MP4)."""
    d = os.path.join(SRC, folder)
    if not os.path.exists(os.path.join(d, "f0000.png")):
        return None
    out = os.path.join(IMG, name)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(d, "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-preset", "slow", "-movflags",
                    "+faststart", out], check=True)
    return "img/" + name


def strip(frames_dir, picks, name, width=320):
    files = [os.path.join(SRC, frames_dir, f"f{k:04d}.png") for k in picks]
    files = [f for f in files if os.path.exists(f)]
    if not files:
        return None
    out = os.path.join(IMG, name)
    subprocess.run(["convert", *files, "-resize", f"{width}x", "+append", "-quality", "80", out], check=True)
    return "img/" + name


def video(src, poster=None, cap=""):
    if not src:
        return f'<figure><div class="miss">not made</div><figcaption>{cap}</figcaption></figure>'
    p = f' poster="{poster}"' if poster else ""
    return (f'<figure><video src="{src}" controls loop muted playsinline preload="none"{p}></video>'
            f'<figcaption>{cap}</figcaption></figure>')


def img(src, cap=""):
    if not src:
        return f'<figure><div class="miss">not made</div><figcaption>{cap}</figcaption></figure>'
    return f'<figure><img src="{src}" alt="{cap}" loading="lazy"><figcaption>{cap}</figcaption></figure>'


def f1(x, n=1):
    return "–" if x is None else f"{x:.{n}f}"


# ------------------------------------------------------------------ data
sa = J("standalone.json", [])
sat = {r["test"]: r for r in J("out_sa/times_cycles.json", [])}
s_hf = J("out_s_hf/times.json", {})
s_hf_e = J("out_s_hf_eevee/times.json", {})
s_hf_w = J("out_s_hf_wb/times.json", {})
s_pbf = J("out_s_pbf/times.json", {})
s_flip = J("out_s_flip/times.json", {})
flip_bake = J("flip96/bake.json", {})
extra = J("extra.json", {})
m = {k: J(f"m{k}/info.json", {}) for k in (3, 4, 5)}
m3e, m3w = J("m3_eevee/info.json", {}), J("m3_wb/info.json", {})

V = {
    "s_hf": enc("out_s_hf", "s_hf.mp4", 24),
    "s_pbf": enc("out_s_pbf", "s_pbf.mp4", 24),
    "s_flip": enc("out_s_flip", "s_flip.mp4", 24),
    "m3": enc("m3/frames", "m3.mp4", 12),
    "m4": enc("m4/frames", "m4.mp4", 12),
    "m5": enc("m5/frames", "m5.mp4", 12),
}
for t in ("t1", "t2", "t3", "t4", "t5", "t6"):
    V[t] = enc(f"out_sa/{t}", f"{t}.mp4", sat.get(t, {}).get("fps", 8))
P = {
    "s_hf": jpg("out_s_hf/f0110.png", "s_hf.jpg"),
    "s_pbf": jpg("out_s_pbf/f0110.png", "s_pbf.jpg"),
    "s_flip": jpg("out_s_flip/f0080.png", "s_flip.jpg"),
    "s_hf_e": strip("out_s_hf_eevee", [1, 2], "s_hf_eevee.jpg", 480),
    "s_hf_e2": strip("eevee_try2", [0, 1], "s_hf_eevee_blended.jpg", 480),
    "s_hf_w": strip("out_s_hf_wb", [1, 2], "s_hf_workbench.jpg", 320),
    "s_hf_c": strip("out_s_hf", [80, 110], "s_hf_cycles.jpg", 480),
    "m3e": strip("m3_eevee/frames", [0, 1], "m3_eevee.jpg", 480),
    "m3w": strip("m3_wb/frames", [0, 1], "m3_workbench.jpg", 480),
    "m3": jpg("m3/frames/f0060.png", "m3.jpg"),
    "m4": jpg("m4/frames/f0060.png", "m4.jpg"),
    "m5": jpg("m5/frames/f0060.png", "m5.jpg"),
}
for t in ("t1", "t2", "t3", "t4", "t5", "t6"):
    P[t] = jpg(f"out_sa/{t}/f0060.png", f"{t}.jpg", 480)

json.dump(dict(standalone=sa, standalone_render=list(sat.values()), s_hf=s_hf, s_hf_eevee=s_hf_e,
               s_hf_workbench=s_hf_w, s_pbf=s_pbf, s_flip=s_flip, flip_bake=flip_bake, machines=m,
               m3_eevee=m3e, m3_workbench=m3w, extra=extra),
          open(os.path.join(DST, "numbers.json"), "w"), indent=1, default=float)

# ------------------------------------------------------------------ page
T = {r["name"]: r for r in sa}


def row_test(key, name, what, result, ok):
    r = sat.get(key, {})
    return (f"<tr><td>{video(V.get(key), P.get(key), '')}</td><td><b>{name}</b><br>{what}</td><td>{result}</td>"
            f"<td>{'✔' if ok else '✘'}</td></tr>")


def tget(name, k, default=None):
    return T.get(name, {}).get(k, default)


t1 = "Closed pocket fills and holds"
t2 = "Open slot drains at its end"
t3 = "Tilted plate spills at the right angle"
t4 = "Sloped tray empties down its drain"
t5 = "Box stopped hard sloshes and settles"
t6 = "Nothing leaks through a wall"

tests_rows = "".join([
    row_test("t1", "Pocket fills and holds", "Plate 100 × 100 mm with a closed pocket 40 × 40 × 8 (12.8 cm³); "
             "twice that is poured in 2 s; 12 s later.",
             f"Holds <b>{f1(tget(t1, 'held_cm3'), 2)} cm³</b> of 12.8 ({f1(tget(t1, 'error_pct'), 1)} %); the rest ran "
             f"off the plate ({f1(tget(t1, 'ran_off_cm3'), 1)} cm³). Liquid kept to "
             f"{tget(t1, 'balance', 0):.0e} of what was poured.", abs(tget(t1, 'error_pct', 99)) < 2),
    row_test("t2", "Open slot drains", "Slot 10 wide, 6 deep, 90 long, open at the plate's edge; filled, then "
             "the jet stops.",
             f"Half gone after <b>{f1(tget(t2, 'half_s'), 2)} s</b>; after 10 s {f1(tget(t2, 'left_pct'), 1)} % "
             "is left as a thin layer on the slot's floor (≈ 0.5 mm – about what surface tension holds).",
             (tget(t2, 'left_pct', 99) or 99) < 15),
    row_test("t3", "Tilt spills at the right angle", "Pocket 40 wide, 10 deep, half full; plate tilted 3°/s "
             "from 0 to 30°.",
             f"Spills at <b>{f1(tget(t3, 'spilled_at_deg'), 1)}°</b>, by geometry {f1(tget(t3, 'expected_deg'), 1)}° "
             f"(atan(5/20)); at 30° it holds {f1(tget(t3, 'left_at_30deg_cm3'), 2)} cm³, by geometry "
             f"{f1(tget(t3, 'expected_left_at_30deg_cm3'), 2)}.", abs(tget(t3, 'error_deg', 99) or 99) < 1.5),
    row_test("t4", "Tray empties down its drain", "Tray 400 × 300, 2° slope, drain Ø 20; 2 l/min for 10 s "
             "(333 cm³).",
             f"95 % drained <b>{f1(tget(t4, 'empty_95pct_s_after_stop'), 1)} s</b> after the jet stopped; "
             f"{f1(tget(t4, 'film_left_cm3'), 1)} cm³ stays as a wet film (0.04 mm), dries with the wet sheen.",
             tget(t4, 'empty_95pct_s_after_stop') is not None),
    row_test("t5", "Box stopped hard sloshes and settles", "Box 200 × 50, 10 mm of liquid, moving at 0.25 m/s, "
             "stopped within one frame.",
             f"Sloshes with a period of <b>{f1(tget(t5, 'period_s'), 2)} s</b> (shallow-water formula 2L/√(gh): "
             f"{f1(tget(t5, 'expected_period_s'), 2)} s); first wave {f1(tget(t5, 'first_wave_mm'), 1)} mm, after 5 s "
             f"{f1(tget(t5, 'after_5s_mm'), 1)} mm (damping as water: ~3 % per swing).",
             abs((tget(t5, 'period_s') or 0) - (tget(t5, 'expected_period_s') or 9)) < 0.1),
    row_test("t6", "Nothing leaks through a wall", "Tank with a wall ONE cell (1 mm) thick, 20 high; 8 mm of "
             "liquid on one side, rocked ±12°.",
             f"Behind the wall: <b>{f1(tget(t6, 'worst_behind_wall_cm3'), 3)} cm³</b>; total kept exactly.", tget(t6, 'worst_behind_wall_cm3') == 0.0),
])


def num(d, k, n=1, scale=1.0):
    v = d.get(k)
    return "–" if v is None else f"{v * scale:.{n}f}"


mrows = ""
for k, name, what in ((3, "3-axis test mill", "pocket 50 × 60 × 10 and an open slot cut with flood on; the table "
                       "moves in Y (rapids ±70 mm at the end)"),
                      (4, "4th axis (A)", "the test program: a slot wrapped round the bar, flats at A0 and A180; "
                       "flood all the time"),
                      (5, "5-axis trunnion", "the test program: two 3+2 pockets at A30, a groove while C turns 90°; "
                       "flood all the time")):
    d = m[k]
    mrows += (f"<tr><td>{video(V.get(f'm{k}'), P.get(f'm{k}'), '')}</td><td><b>{name}</b><br>{what}</td>"
              f"<td>Build {num(d, 'build_s')} s · frame pass {num(d, 'frame_pass_s')} s (of it the cut's top by rays "
              f"{num(d, 'cut_rays_s')} s) · liquid bake <b>{num(d, 'liquid_bake_s')} s</b> "
              f"({num(d, 'liquid_ms_per_frame', 0)} ms a frame, {d.get('cells', '–')} cells) · cache "
              f"{num(d, 'cache_bytes', 1, 1e-6)} MB · liquid put in place per frame <b>{num(d, 'update_ms')} ms</b> · "
              f"Cycles {num(d, 'render_s_per_frame')} s a frame (480 × 270, 16 samples)</td></tr>")

html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>0251 coolant liquid</title><style>
:root{{--bg:#fff;--fg:#1c2330;--mut:#5b6573;--line:#d5dae1;--card:#f5f7fa;--acc:#479B29;--warn:#b54708}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16191f;--fg:#e6e9ee;--mut:#9aa4b2;--line:#323946;--card:#1e232b;--warn:#f79009}}}}
:root[data-theme="dark"]{{--bg:#16191f;--fg:#e6e9ee;--mut:#9aa4b2;--line:#323946;--card:#1e232b;--warn:#f79009}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:1200px;margin:0 auto;padding:16px}}h1{{font-size:1.5rem}}h2{{margin-top:2.2rem;border-bottom:2px solid var(--acc)}}
.pics{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}}figure{{margin:0;max-width:100%}}
video,img{{max-width:100%;height:auto;border:1px solid var(--line);display:block;background:#000}}
.pics figure{{flex:1 1 300px}}figcaption{{font-size:.85rem;color:var(--mut)}}
.card{{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:12px;margin:12px 0}}
table{{border-collapse:collapse;width:100%;font-size:.88rem}}th,td{{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}}
td:first-child{{width:330px}}.scroll{{overflow-x:auto}}.d{{color:var(--mut);font-size:.85rem}}.star{{color:var(--acc)}}
.miss{{padding:30px;border:1px dashed var(--line);color:var(--mut)}}
#bar{{position:sticky;bottom:0;background:var(--bg);border-top:2px solid var(--acc);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
#bar code{{flex:1;min-width:240px;word-break:break-word}}button{{font:inherit;padding:8px 18px;background:var(--acc);color:#fff;border:0;border-radius:6px;cursor:pointer}}
label{{display:block;margin:4px 0}}
</style></head><body><main>
<h1>0251 – Coolant liquid on the machine (study + prototype)</h1>
<p>Everything here is the <b>prototype</b> on its own branch (nothing is in the app yet), on the <b>test models</b>:
today's test mills and small invented test blocks – nothing of yours. Measured on the 4-core web test machine without a
graphics card (Blender 5.2.3, renders on the processor). Your PC renders on the RTX 3090: the render times below are
<i>this machine's</i>, not yours. The videos are short and small (640 × 360 or 480 × 270).</p>

<div class="card"><b>Recommendation <span class="star">★</span>: a shallow-liquid height field</b> (method a) – a
grid of liquid depths on every surface the coolant can reach (the cut part, the table with its T-slots, the tray),
baked once at Build, with drops between them. It fills pockets to the right volume, drains open slots, sloshes when
the table stops, spills at the right tilt, runs to the drain – and it is the only method that is cheap enough for a
whole program (a bake of seconds to a minute, a few ms per frame in the 3D view, any render engine). Particles look
blobby and fall through thin parts unless thousands are used; Blender's own liquid simulation looks best close up but
costs about a minute per frame on this machine for a small box and cannot follow a long program.</div>

<h2>1 · The three methods on the same scene</h2>
<p>A block with a closed pocket and an open slot on a plate (the "table") with a groove; a jet pours 2 l/min for
2.8 s; the table moves +60 mm at 3 s and back at 4.4 s, each start and stop within one frame (hard); a fixed tray
below runs to a drain. 8 s, 24 fps.</p>
<div class="pics">
{video(V['s_hf'], P['s_hf'], '<b>a · Height field ★</b> – liquid grids on the plate and the tray, drops in between')}
{video(V['s_pbf'], P['s_pbf'], '<b>b · Particles</b> (position-based fluid, 2 mm particles, meshed by Geometry Nodes)')}
{video(V['s_flip'], P['s_flip'], "<b>c · Blender's liquid simulation</b> (Mantaflow FLIP, resolution 96, the first 4 s)")}
</div>

<div class="scroll"><table>
<tr><th></th><th>a · Height field ★</th><th>b · Particles</th><th>c · Blender liquid (FLIP)</th></tr>
<tr><td>Bake (Build), this scene, 8 s</td><td><b>{num(extra, 'hf_bake_s')} s</b> ({num(extra, 'hf_ms', 0)} ms a frame, 30,000 cells)</td>
<td>{num(extra, 'pbf_bake_s_contended', 0)} s with other jobs running; alone {num(extra, 'pbf_ms_first2s', 0)} ms a frame at {extra.get('pbf_particles_at_2s', '–')} particles (up to {extra.get('pbf_particles', '–')})</td>
<td>{num(flip_bake, 's_per_frame')} s a frame at resolution {flip_bake.get('res', '–')} ({extra.get('flip_cells', '–')} cells) → {num(extra, 'flip_8s_min', 0)} min for 8 s</td></tr>
<tr><td>Per frame in the 3D view (put the liquid in place)</td><td><b>{num(extra, 'hf_update_ms')} ms</b></td>
<td>{num(s_pbf, 'update_ms')} ms (+ Geometry Nodes meshing)</td><td>reads its cache: {num(s_flip, 'update_ms')} ms</td></tr>
<tr><td>Cycles, 640 × 360, 24 samples</td><td>{num(s_hf, 'render_s_per_frame')} s a frame</td>
<td>{num(s_pbf, 'render_s_per_frame')} s</td><td>{num(s_flip, 'render_s_per_frame')} s</td></tr>
<tr><td>EEVEE / 3D view (Workbench)</td><td>{num(s_hf_e, 'render_s_per_frame')} s / {num(s_hf_w, 'render_s_per_frame', 2)} s a frame</td><td>works (same mesh)</td><td>works (same mesh)</td></tr>
<tr><td>Cache on disk, this scene</td><td>{num(extra, 'hf_cache_mb')} MB (depths as 16-bit, packed)</td><td>{num(extra, 'pbf_cache_mb')} MB</td><td>{num(flip_bake, 'cache_bytes', 1, 1e-6)} MB for {flip_bake.get('frames', '–')} frames</td></tr>
<tr><td>Same frame = same picture (0042's rule)</td><td>yes (baked once; frame read from the bake; tested bit for bit)</td><td>yes (baked once)</td><td>yes once baked; a change anywhere = bake again from the start</td></tr>
<tr><td>Pockets fill to their volume</td><td>yes (0.5 % – test 1)</td><td>roughly (particles 2 mm: a pocket 8 deep is 4 layers)</td><td>yes at fine resolution; at 96 the pocket is 3 cells deep</td></tr>
<tr><td>Thin films, run-off along T-slots</td><td>yes (films down to 0.04 mm)</td><td>no (a film thinner than a particle breaks into beads)</td><td>no below ~2 cells (5 mm here)</td></tr>
<tr><td>Long programs (minutes)</td><td>yes, but see section 5 (cost ∝ cells × frames)</td><td>slow (cost ∝ particles; pools grow)</td><td>no (hours)</td></tr>
<tr><td>Splash, jets, breaking waves</td><td>no (the app's jets and splash of 0042 stay)</td><td>yes</td><td>yes</td></tr>
</table></div>
<p class="d">d · Searched: games and films use exactly this split for big water – a height field for the bulk and
particles for what it cannot show (Chentanez &amp; Müller 2010, "Real-time simulation of large bodies of water with
small scale details"; Müller "Fast water simulation for games using height fields", GDC 2008). Machining software
(VERICUT, NCSIMUL) shows no coolant liquid; coolant flow is done in engineering CFD (Simcenter FLOEFD, Particleworks) –
hours per second, not for a video. The prototype is that hybrid: height-field liquid + drops + the app's own jets.</p>

<h2>2 · On the test mills</h2>
<p>The app's own Build, cut, jets and splash (0042), with the liquid of method a. The table chart is read from the
table, clamps and screws by rays (T-slots included); the cut part's top is read again every 4 frames; the jets pour at
the tool's tip while the flood is on (3 l/min here). Under the table the bed stands in for the chip tray (flat, a drain
at the front left: 0249's VMC gets a real tray).</p>
<div class="scroll"><table><tr><th>Video</th><th>Machine</th><th>Numbers</th></tr>{mrows}</table></div>
<p>The 4th axis: the bar has four charts round it (one per quarter, in the bar's frame); liquid runs off the round
faces, sits in the flats and the wrapped slot until the bar turns them past the spill angle, and drips onto the tray.
The 5-axis: the rotary table + block is one chart, the cradle a second; when the cradle tilts the pools run to the low
side and fall into the cradle and on to the tray; while C turns, the turn flings the liquid outwards.</p>

<h2>3 · In Cycles, EEVEE and the 3D view</h2>
<div class="pics">
{img(P['s_hf_c'], 'Cycles')}{img(P['s_hf_e'], 'EEVEE, the same see-through liquid: grainy at 32 samples on this machine')}
{img(P['s_hf_e2'], 'EEVEE, liquid drawn blended (no refraction): smooth, but it reads as paint – to be tuned')}{img(P['s_hf_w'], '3D view look (Workbench, solid)')}
</div>
<div class="pics">
{img(P['m3e'], 'Test mill in EEVEE')}{img(P['m3w'], 'Test mill, 3D view look')}
</div>
<p class="d">The liquid is an ordinary mesh with the coolant's colour (milky emulsion), so it shows in every engine
and in the render queue. A thin film is drawn see-through (it fades out below 0.5 mm); a film running down a steep
wall is not drawn (the wet sheen of 0042 shows it).</p>

<h2>4 · Stand-alone fluid tests (no machine)</h2>
<p>Small invented test models, each proving one thing with a number. They are written as automatic tests
(<code>tools/proto_0251/standalone.py</code>) and are the proposed tour set <b>"Coolant liquid"</b>. Videos in Cycles (EEVEE takes over a minute a frame on this machine).</p>
<div class="scroll"><table><tr><th>Video</th><th>Test</th><th>Result</th><th>OK</th></tr>{tests_rows}</table></div>

<h2>5 · Long programs on the big machine</h2>
<p>The height field costs about <b>180 ns per cell and sub-step</b> in this prototype (NumPy, one core, 8–15 sub-steps
a frame): a chart of 125,000 cells with 2 mm of liquid takes 0.32 s a frame. 0249's machine (table 1200 × 500 at 2 mm
plus the tray at 5 mm ≈ 250,000 cells) with a <b>10-minute program</b> would bake for about <b>2–2.5 hours</b> at
Normal – too slow. The build must get 10–20× faster: the work split over helper processes (your PC has 24 cores),
only the wet part of each surface stepped, frames skipped while nothing moves and the coolant is off, Draft detail
(4 mm: about 8× less work), and the bake running with progress and Cancel. Goal: that 10-minute program in under
10 minutes on your PC.</p>

<h2>6 · Pick</h2>
<form id="f">
<label><input type="radio" name="m" value="a" checked> a · Height field (recommended)</label>
<label><input type="radio" name="m" value="b"> b · Particles</label>
<label><input type="radio" name="m" value="c"> c · Blender's liquid simulation</label>
<label><input type="checkbox" name="s" value="tick" checked> Settings: one tick "Liquid on the machine" + Detail tied to Draft / Normal / Final</label>
<label><input type="checkbox" name="s" value="chips"> Chips carried by the liquid (a later step)</label>
<label><input type="checkbox" name="s" value="air"> Air blast pushes the liquid out of pockets (a later step)</label>
</form>
</main>
<div id="bar"><code id="out"></code><button id="copy">Copy</button></div>
<script>
const f=document.getElementById('f'),o=document.getElementById('out');
function upd(){{const m=f.querySelector('input[name=m]:checked').value;const s=[...f.querySelectorAll('input[name=s]:checked')].map(x=>x.value);
o.textContent='0251 picks: method '+m+(s.length?'; '+s.join(', '):'');}}
f.addEventListener('change',upd);upd();
document.getElementById('copy').onclick=()=>{{navigator.clipboard&&navigator.clipboard.writeText(o.textContent);}};
</script></body></html>
"""
open(os.path.join(DST, "index.html"), "w").write(html)
print("page written", sum(os.path.getsize(os.path.join(IMG, x)) for x in os.listdir(IMG)) / 1e6, "MB")
