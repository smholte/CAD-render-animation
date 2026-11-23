"""Study 0306 – writes tasks/0306_page/index.html from the measured files next to this script (charts as inline SVG).

    python3 tasks/0306_proto/make_page.py
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "0306_page", "index.html")
J = lambda n: json.load(open(os.path.join(HERE, n)))   # noqa: E731


def svg_lines(series, w=640, h=230, xlabel="", ylabel="", pad=(44, 14, 30, 10), equal=False, points=()):
    """series: [(xs, ys, colour, label, dash)] -> an SVG chart with axes (no library)."""
    xs = np.concatenate([np.asarray(s[0], float) for s in series])
    ys = np.concatenate([np.asarray(s[1], float) for s in series])
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    if y1 - y0 < 1e-9:
        y1 = y0 + 1
    L, R_, B, T = pad
    W, H = w - L - R_, h - T - B
    if equal:
        k = min(W / (x1 - x0), H / (y1 - y0))
        sx = sy = k
    else:
        sx, sy = W / (x1 - x0), H / (y1 - y0)
    X = lambda x: L + (x - x0) * sx                         # noqa: E731
    Y = lambda y: T + H - (y - y0) * sy                     # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" style="width:100%;max-width:{w}px;height:auto">',
           f'<rect x="{L}" y="{T}" width="{W}" height="{H}" fill="none" stroke="var(--line)"/>']
    for v in np.linspace(y0, y1, 5):
        out.append(f'<text x="{L - 4}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="10" fill="var(--mut)">{v:.3g}</text>')
    for v in np.linspace(x0, x1, 6):
        out.append(f'<text x="{X(v):.1f}" y="{T + H + 14}" text-anchor="middle" font-size="10" fill="var(--mut)">{v:.3g}</text>')
    if y0 < 0 < y1:
        out.append(f'<line x1="{L}" x2="{L + W}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="var(--line)"/>')
    leg = T + 8
    for xs_, ys_, col, lab, dash in series:
        pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(xs_, ys_))
        d = ' stroke-dasharray="5 4"' if dash else ""
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.8"{d}/>')
        out.append(f'<rect x="{L + 8}" y="{leg}" width="14" height="3" fill="{col}"/>'
                   f'<text x="{L + 26}" y="{leg + 5}" font-size="11" fill="var(--fg)">{lab}</text>')
        leg += 14
    for (px, py, col) in points:
        out.append(f'<circle cx="{X(px):.1f}" cy="{Y(py):.1f}" r="3.4" fill="{col}" stroke="var(--bg)"/>')
    out.append(f'<text x="{L + W / 2}" y="{h - 4}" text-anchor="middle" font-size="11" fill="var(--mut)">{xlabel}</text>')
    out.append(f'<text x="12" y="{T + H / 2}" font-size="11" fill="var(--mut)" transform="rotate(-90 12 {T + H / 2})" '
               f'text-anchor="middle">{ylabel}</text></svg>')
    return "\n".join(out)


cur = J("curves.json")
chart_steer = svg_lines([(cur["catmull"]["s"], cur["catmull"]["steer"], "#c2410c", "camera path's curve (today)", False),
                         (cur["spline"]["s"], cur["spline"]["steer"], "#479B29", "smooth-steering spline", False)],
                        xlabel="metres along the path", ylabel="front wheel angle (deg)")
dr = J("drives.json")
kb = dr[0]
ser, pts = [], []
raw = np.array(kb["pieces"][0]["drive"])
ser.append((raw[:, 0], raw[:, 1], "#9aa4b2", "driven (keys, ~60 Hz)", True))
cols = ["#479B29", "#c2410c", "#2563eb"]
for i, p in enumerate(kb["pieces"]):
    rt = np.array(p["route"])
    ser.append((rt[:, 0], rt[:, 1], cols[i % 3] if not p["reverse"] else "#c2410c",
                ("editable path" if i == 0 else "reverse piece" if p["reverse"] else "forward again"), False))
    pts += [(x, y, "#c2410c" if p["reverse"] else "#1c2330") for x, y in p["xy_points"]]
chart_drive = svg_lines(ser, h=300, xlabel="x (m)", ylabel="y (m)", equal=True, points=pts)
rc = np.load(os.path.join(HERE, "ride_car.npz"))
n = int(np.argmin(np.abs(rc["origin"][:, 0] - 32)))
xa = rc["origin"][:n, 0]
chart_ride = svg_lines([(xa, np.degrees(rc["pitch"][:n]), "#2563eb", "pitch, deg", False),
                        (xa, rc["travel"][0, :n] * 100, "#c2410c", "front left travel, cm", False),
                        (xa - 0.0, rc["travel"][2, :n] * 100, "#479B29", "rear left travel, cm", True)],
                       xlabel="front axle's place along the road (m) – the bump lies at 16.2 … 19.9 m", ylabel="pitch nose up + · travel bump +")
bc, bt = J("bake_car.json"), J("bake_truck.json")
live = J("drive_live.json")

ROWS_DRIVE = "".join(
    f"<tr><td>{d['name']}</td><td class='n'>{d['seconds']} s</td><td class='n'>{d['ticks']}</td>"
    f"<td>{' + '.join(('reverse ' if p['reverse'] else '') + str(p['driven_m']) + ' m' for p in d['pieces'])}</td>"
    f"<td class='n'>{' + '.join(str(p['points']) for p in d['pieces'])}</td>"
    f"<td class='n'>{max(p['max_dev_mm'] for p in d['pieces']):.0f} mm</td>"
    f"<td class='n'>{' + '.join(str(p['speed_keys']) for p in d['pieces'])}</td><td class='n'>{d['fit_s'] * 1000:.0f} ms</td></tr>"
    for d in dr)

TASKS = [
    ("A", True, "Vehicle rig and a drawn path on flat ground", "work L · Opus · High · Vehicles lane (new) · first",
     "A new <b>Vehicles</b> workspace and a step window (0282's function windows): <b>1 Vehicle</b> – pick a kind (car, van, "
     "2-axle truck, 3-axle truck) and click the wheels (the app proposes them: round parts with tyre / wheel / band / Rad / "
     "Reifen / wiel names, paired into axles), the steered axle, the body; <b>2 Path</b> – click on the ground, a smooth "
     "path that steers smoothly (the spline of section 3, not the camera path's curve), drag points, a red stretch where it "
     "is tighter than full lock; <b>3 Speed</b> – one speed, slower in bends by itself, a stop at the end. Build keys the "
     "vehicle along it: steering by Ackermann on each front wheel (a table coupling, scripts off), every wheel turning "
     "with its own rolled distance, the steering wheel in the cab with its ratio. Test models: the invented car and truck "
     "of this study; tour stop, PC-check line, lesson step, guide.",
     "Gain: the owner's first wish – a vehicle driving a path – with no ground or suspension yet."),
    ("B", True, "Ground with height and the ride", "work L · Opus · High · Vehicles lane · after A",
     "The ground under the path becomes a height grid at Build (rays on 5 cm over the strip the vehicle drives: "
     f"{bc['strip_100m_x_8m_s_by_rays']} s for 100 m × 8 m measured; any mesh – the app's floor, an imported terrain, a CAD "
     "kerb), each wheel rests on it as a rigid wheel (rolling envelope), the body rides on springs and dampers (pitch, "
     "roll, heave; wheels can leave the ground; bump stops; braking and corners lean the body). Ready-made <b>speed bump</b> "
     "props (long round hump, short hump, raised crossing) and an <b>off-road</b> ground (waves, ruts, potholes) until "
     "0311's terrain maker exists. Suspension kinds: double wishbone and MacPherson and trailing arm as 0014 mechanisms "
     "(a table follower on a 'wheel travel' joint), solid axles as two stacked joints (heave + roll).",
     f"Measured: the car's 20 s drive solves in {bc['ride_total_s']} s, the mechanisms ~1 ms a frame, the keys ~4 ms a "
     "frame; the pictures above."),
    ("C", True, "Drive it yourself, recorded, made into a path", "work M–L · Opus · High · Vehicles lane · after A · shared with 0312",
     "<b>Drive…</b> in the Path step: the view follows the vehicle (chase camera), W A S D / arrows; the brake held at a "
     "standstill goes backwards; Esc or Enter ends. The drive is kept as driven (steering and speed over distance: exact) "
     "and turned into pieces – forward / reverse – each an editable path with few points and a few speed keys (table "
     "above). The core (drive model, recorder, fitting) is one module that 0312's vessels use with their own motion model "
     "(section 6).",
     "Measured: a 33 s keyboard drive → 3 pieces, 35 points, within 2.5 cm, fitted in 62 ms."),
    ("D", True, "Game controller", "work S–M · Opus · Medium · Vehicles lane · with or after C · Windows-only: independent review",
     "Xbox-type pads through XInput, every other pad, a steering wheel with pedals through Windows' joystick call – both "
     "with ctypes, nothing installed (gamepad.py in this study). Settings: dead zone, steering curve, which pedal is "
     "which. A PC-check line 'Game controller' (move the stick, see the number) – only your PC can test it.",
     "Gain: smooth steering and throttle; the keyboard stays."),
    ("E", True, "Vehicle presets, saved and shared", "work M · Opus · Medium · Vehicles lane · after B",
     "Per kind: mass, centre of mass, springs, dampers, tyres, anti-roll, lock, comfortable speeds (the truck preset needs "
     "a stiffer roll than this study's: it leaned 4.5° at 0.18 g). Adjust in the step window, <b>Save as my / department / "
     "company preset</b> (0272's locations, .frsetup). Also the Lifting lane's mobile cranes (AT classes) as presets, so a "
     "crane drives onto site before it sets up.",
     "Gain: a sales person picks 'Truck' and gets a believable ride without numbers."),
    ("F", False, "Springs, dampers and tie rods that stretch; leaf springs that bend", "work M · Opus · Medium · after 0300's picks",
     "In this study's pictures the springs ride along rigidly (a shortcut). With 0300's coil spring and rubber work they "
     "stretch between their two eyes, a leaf spring bends with its axle's travel.",
     "Gain: close-ups of the suspension look right."),
    ("G", False, "Trailers, all-wheel steering, tracked machines", "work L · Opus · High · Vehicles lane · after B",
     "A trailer on a hitch follows its truck (the hitch angle from the path – a trailer cuts the corner, as a real one); "
     "several steered axles (mobile cranes: rear axles steer the other way, crab steering); tracked machines turn by "
     "their tracks' speed difference, the road wheels on bogies on the ground (tracks.py's loop).",
     "Gain: cable-drum trailers, cranes and crawlers on site."),
    ("H", True, "Wheels that look right at speed", "work S · Sonnet · Medium · Vehicles lane · with A",
     "Motion blur on in vehicle videos by default (Cycles), and a note in the Speed step where the rims would seem to turn "
     "backwards at the video's frame rate (a 5-spoke car rim at 25 fps: from 20 km/h, standing still at 41 km/h).",
     "Gain: no 'wagon wheel' effect in the owner's videos."),
]


def task_html(t):
    k, star, title, tag, body, why = t
    return (f'<section class="item"><label class="pick"><input type="checkbox" value="{k}"{" checked" if star else ""}> '
            f'<b>{k}</b>{" <span class=star>★</span>" if star else ""}</label><div class="body"><h3>{title} '
            f'<span class="tag">{tag}</span></h3><p>{body}</p><p class="why">{why}</p></div></section>')


HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vehicles workspace study</title><style>
:root{{--bg:#fff;--fg:#1c2330;--mut:#5b6573;--line:#d5dae1;--card:#f5f7fa;--acc:#479B29;--warn:#b54708}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16191f;--fg:#e6e9ee;--mut:#9aa4b2;--line:#323946;--card:#1e232b;--warn:#f79009}}}}
:root[data-theme="dark"]{{--bg:#16191f;--fg:#e6e9ee;--mut:#9aa4b2;--line:#323946;--card:#1e232b;--warn:#f79009}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:16px}}h1{{font-size:1.5rem}}h2{{margin-top:2.2rem;border-bottom:2px solid var(--acc);font-size:1.2rem}}
.card{{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:12px;margin:12px 0}}
.item{{display:flex;gap:12px;border:1px solid var(--line);background:var(--card);border-radius:8px;padding:12px;margin:12px 0}}
.pick{{flex:0 0 64px;font-size:1.1rem}}.pick input{{width:20px;height:20px}}.star{{color:var(--acc)}}
.body{{flex:1;min-width:0}}h3{{margin:0 0 6px;font-size:1rem}}.tag{{font-weight:normal;color:var(--mut);font-size:.85rem}}
.why{{color:var(--mut);font-size:.92rem;margin:4px 0}}
.pics{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start;margin-top:8px}}
figure{{margin:0;max-width:100%;flex:1 1 300px}}figure img{{width:100%;height:auto;border:1px solid var(--line);display:block}}
figcaption,.d{{font-size:.85rem;color:var(--mut)}}
.tbl{{overflow-x:auto}}table{{border-collapse:collapse;font-size:.92rem;min-width:520px}}
th,td{{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}}th{{background:var(--card)}}
td.n{{text-align:right;white-space:nowrap}}
.mock{{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:10px;max-width:360px;font-size:.9rem}}
.mock .st{{border-left:3px solid var(--acc);padding:4px 8px;margin:6px 0;background:var(--bg)}}.mock .b{{display:inline-block;border:1px solid var(--line);border-radius:4px;padding:1px 8px;margin:2px 4px 2px 0;background:var(--bg)}}
.mock .p{{background:#2563eb;color:#fff;border-color:#2563eb}}
#bar{{position:sticky;bottom:0;background:var(--bg);border-top:2px solid var(--acc);padding:10px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
#bar code{{flex:1;min-width:0;word-break:break-word}}#bar button{{font:inherit;padding:6px 16px;cursor:pointer}}
</style></head><body><main>
<h1>A Vehicles workspace (study 0306)</h1>
<div class="card"><b>In short.</b> A vehicle can be rigged from its STEP in a few clicks, driven along a path over a speed bump or a rough
track, and ride on its springs – all worked out once at Build and played back as plain keys, like the app's cables. A first try
does it for an invented car and truck: the whole ride of a 20 s drive takes <b>{bc['ride_total_s']} s</b> to work out, the app's
existing mechanism solver already moves a double wishbone and a MacPherson strut without a change, and a drive you steer yourself with
the keys becomes an editable path of a few points within 2.5 cm in 0.06 s. Two findings change the design: a vehicle path needs a
<b>different curve</b> from the camera path's (or the steering jumps at every point), and Blender itself <b>cannot read a game
controller</b> – Windows can, with no install. Below: what was measured, the design, and <b>8 build tasks</b> to tick. ★ = recommended.</div>

<h2>1 · What it looks like for the user</h2>
<div class="pics"><div class="mock"><b>Vehicles</b> – step window (sketch)
<div class="st"><b>1 Vehicle</b> · Kind: <span class="b">Car ▾</span><br>Wheels: 4 found – <span class="b">Show</span><span class="b">Pick again</span><br>
Steered: front · Body: "Body" · Suspension: front double wishbone (found), rear trailing arm (found)</div>
<div class="st"><b>2 Ground</b> · <span class="b">The floor</span><span class="b">+ Speed bump</span><span class="b">Off-road</span><span class="b">My terrain…</span></div>
<div class="st"><b>3 Path</b> · <span class="b">Draw on the ground</span><span class="b">Drive…</span><br><span class="d">2 pieces · 31 points · tightest bend 6.2 m (ok)</span></div>
<div class="st"><b>4 Speed</b> · 30 km/h · slower in bends ✓ · stop at the end ✓</div>
<div><span class="b p">Build &amp; play</span></div></div>
<div style="flex:1 1 300px"><p>The same pattern as the Set-up window of the mill and the crane: steps top to bottom, the app proposes, the user corrects.
What the app finds by itself from the STEP (to be built in A / B, partly tried here):</p><ul>
<li><b>Wheels</b>: parts that are round about one axis with a big diameter, named tyre / tire / wheel / band / Reifen / Rad / wiel (EN / NL / DE), paired across into axles; twin tyres as one wheel.</li>
<li><b>The upright / knuckle</b>: the part the wheel's axis goes through. <b>Arms</b>: parts with round eyes that join the upright to the body (0014's "pins from shared round faces").</li>
<li><b>Kind</b>: two arms → double wishbone; one arm + a long part from the upright up to the body → MacPherson; one arm turning about the vehicle's width → trailing arm; one beam between both wheels → solid axle.</li>
<li><b>Steering</b>: the steered axle's uprights turn about the line through their ball joints (kingpin); each wheel by Ackermann.</li></ul></div></div>

<h2>2 · Suspension kinds (point A)</h2>
<div class="tbl"><table><tr><th>Kind</th><th>Where</th><th>How it is rigged</th><th>Tried here</th></tr>
<tr><td>Double wishbone</td><td>cars' front, vans, machines</td><td>a four-bar in the front view on the app's mechanism solver (0014); input = lower arm</td><td>table of 37 rows in 16 ms; camber +0.7° … −2.2° over the travel</td></tr>
<tr><td>MacPherson strut</td><td>most cars' front</td><td>the same with the upright sliding along the strut</td><td>332 ms; camber +2.1° … −0.8°</td></tr>
<tr><td>Trailing arm</td><td>rear of cars, trailers, many machines</td><td>one turning joint</td><td>6 ms; wheel moves 20 mm fore-aft</td></tr>
<tr><td>Solid axle (leaf or coil)</td><td>trucks, vans' rear, off-road</td><td>two stacked joints on the axle: up/down + tilt; the wheels and the steering ride on it</td><td>truck front and rear</td></tr>
<tr><td>Multi-link</td><td>modern cars' rear</td><td>not one plane: the wheel carrier moves along its travel (straight or an arc); small camber / toe changes left out</td><td>– (designed)</td></tr>
<tr><td>Bogies, tracks</td><td>cranes, crawlers, machines</td><td>bogie = a turning joint between two wheels; tracks = tracks.py's loop, turning by speed difference</td><td>– (task G)</td></tr>
</table></div>
<p class="d">The study car's front: double wishbone, steered; rear: trailing arm. The truck: solid axles on leaf springs, twin tyres at the rear. Full lock: car inner wheel 35.5°, outer 26.9° (Ackermann), turning circle of the rear axle's middle 4.8 m; truck 40.1° / 31.8°, 6.7 m.</p>

<h2>3 · Following a path over a bump and a rough track (point B)</h2>
<div class="pics"><figure><img src="img/car_f0151.jpg" alt="car on the bump"><figcaption>Front wheels on the 75 mm hump: nose up.</figcaption></figure>
<figure><img src="img/car_f0166.jpg" alt="car after the bump"><figcaption>Front off, rear on: nose down.</figcaption></figure>
<figure><img src="img/car_f0378.jpg" alt="car off-road"><figcaption>Off-road at 20 km/h: ruts, waves, potholes.</figcaption></figure></div>
<div class="pics"><figure><img src="img/car_xray_f0150.jpg" alt="suspension on the bump"><figcaption>Body hidden: both front wheels up on the hump, arms turned by the mechanism.</figcaption></figure>
<figure><img src="img/car_xray_f0330.jpg" alt="suspension off-road"><figcaption>Off-road: each wheel its own travel and steer.</figcaption></figure>
<figure><img src="img/truck_f0366.jpg" alt="truck"><figcaption>The truck (18 t) on the rough stretch: the axles tilt under the frame.</figcaption></figure></div>
{chart_ride}
<p class="d">The car's drive, measured: path + speed {bc['ride_parts_s']['path + speed'] * 1000:.0f} ms, wheels on the ground {bc['ride_parts_s']['wheels on the ground'] * 1000:.0f} ms, the ride in 1 ms steps {bc['ride_parts_s']['ride (1 ms steps)'] * 1000:.0f} ms for {bc['frames']} frames (20 s) – about 1.2 ms per frame; the
mechanisms ~{bc['mechanism_ms_per_frame']:.0f} ms per frame; writing keys for 28 parts ~{bc['keys_ms_per_frame_all_parts']:.0f} ms per frame. Pitch {bc['pitch_deg'][0]}° … {bc['pitch_deg'][1]}°, roll {bc['roll_deg'][0]}° … {bc['roll_deg'][1]}°,
wheel travel {bc['travel_mm'][0]} … {bc['travel_mm'][1]} mm, {bc['airborne_frames']} frames with a wheel off the ground (potholes). The truck: {bt['frames']} frames in {bt['ride_total_s']} s. A 20 m circle at the
comfortable speed: the car rolls 1.3° at 0.31 g (about 4° per g – a normal car); the truck 4.5° at 0.18 g (too soft – its preset needs anti-roll). Web machine, 4 cores, no graphics card.</p>
<p>How: a speed along the path (slower in bends at a comfortable sideways acceleration, ramps up and down), the body heading along the
path, each wheel's centre on the ground as a <b>rigid wheel</b> (it climbs a step with its round front, not with its lowest point),
the body on springs and dampers per wheel, tyres as springs that can leave the ground, bump stops, the body leaning in braking and
corners. Everything ends as keys: it plays with scripts off, in the render queue and on another PC.</p>

<h2>4 · Paths: drawn, or driven yourself (point C)</h2>
<h3>A drawn path needs a curve that steers smoothly</h3>
{chart_steer}
<p class="d">The same 8 clicks (a road with two bends). The camera path's curve (Catmull–Rom, task 0087) is smooth in direction but its
<b>bend changes in jumps at every point</b> – and a vehicle's steering angle is the bend: the front wheels jump 12° within 10 cm, which would
need 1,108°/s of steering at 30 km/h. A spline through the same points (smooth bend, plain NumPy) needs 25°/s at most. Points closer than
~1 m to each other still make a sharp bend between them: the path tool keeps them apart and shows a red stretch tighter than full lock.</p>
<h3>Driving yourself</h3>
<p>Blender 5.2.3 has <b>no event for a game controller</b> (checked: none of its 196 event types – only keyboard, mouse, a 3D mouse and VR
controllers inside a VR session). Windows has two calls that need nothing installed, both reachable from the app's Python with ctypes as
it already does for window places: <b>XInput</b> (Xbox-type pads) and the <b>joystick call of winmm</b> (any game controller, steering
wheels with pedals). Written and structure-checked here (gamepad.py); it can only be tried on your PC.</p>
<p>The live drive: a timer ~60 times a second moves the vehicle by a simple drive model (the rear axle never slides sideways; steering by
keys ramps to full lock in 1.3 s and back to the middle when let go, less lock at speed; the brake held at a standstill drives backwards).
Tried in the real Blender under a virtual screen: the keys arrive once per press / release; the timer ran only 6–7 times a second because
this machine draws the window without a graphics card (~135 ms per redraw, even with a small scene) – the drive model steps in 20 ms
pieces, so after 52 m it ended within 1.5 m of an ideal 60-a-second drive. How smooth it feels on your RTX 3090 is a PC-check item.</p>
{chart_drive}
<p class="d">The keyboard drive with the car (33 s): off, two bends, a stop, back into a bay, out again. Grey: what was driven; coloured: the
editable pieces (red = reverse); dots: their points.</p>
<div class="tbl"><table><tr><th>Drive</th><th>Length</th><th>Ticks</th><th>Pieces</th><th>Points</th><th>Furthest off</th><th>Speed keys</th><th>Fit</th></tr>{ROWS_DRIVE}</table></div>
<p class="d">Ticks at an irregular ~60 a second with hitches (a redraw of a big model). Where a full-lock bend was steered while creeping, the fitted
path is up to 15 % tighter for a few decimetres (1 stretch in the car's drive): the drive itself is kept as driven (exact), the points are
for editing, and Build holds the steering at full lock there.</p>

<h2>5 · Ground (point D)</h2>
<p>Every ground becomes one <b>height grid</b> at Build (5 cm), read for every wheel at once: 0.15 µs per point against {bc['ray_cast_us_per_ray']:.0f} µs
per ray onto the mesh. Making the grid from any meshes by rays over the strip the vehicle drives: {bc['strip_100m_x_8m_s_by_rays']} s for 100 m × 8 m at
5 cm (one core; 4× less at 10 cm). Kinds: the floor, a <b>speed bump</b> (long round hump 75 mm × 3.7 m, short hump 70 mm × 0.9 m, raised crossing),
an <b>off-road</b> track (waves of a few metres, stones, two ruts 6 cm deep, potholes 12 cm), an imported terrain. The terrain itself
(height maps, painted layers, roads) is study <b>0311</b>'s: the hand-over is only "a mesh under the path" – any mesh works.</p>

<h2>6 · The drive / path tool shared with the vessels (0312)</h2>
<ul><li>One recorder: live input (keys / controller) → a <b>motion model</b> per kind (here: a car's bicycle; vessels: their own –
turning circle, drift, thrusters sideways) → samples → pieces (forward / backward) → editable spline + speed keys over the share of the way.</li>
<li>Vessels also need <b>heading keys</b> apart from the path (a ship crabbing sideways on DP faces another way than it moves); cars use the path's direction.</li>
<li>The same spline for drawn paths of both; ground-following only for vehicles; for vessels the sea's motion is added at Build (0085).</li></ul>

<h2>7 · Build tasks – tick what to build</h2>
<p class="d">A new <b>Vehicles lane</b> (blender/vehicles*.py, core/vehicle*.py, core/drive_path.py). Work: S ≈ half a day of a worker chat, M ≈ a day, L ≈ two or more.</p>
{''.join(task_html(t) for t in TASKS)}
<div id="bar"><code id="line"></code><button id="copy">Copy</button></div>
<p class="d">Pictures: tasks/0306_page/img; numbers: tasks/0306_proto/*.json; the prototype (vehicle maker, ground, ride, drive, controller,
kinematics, Blender bake) in tasks/0306_proto on the branch task/0306-study-vehicles. The test vehicles are invented (no real make).</p>
</main><script>
function upd(){{var v=[].slice.call(document.querySelectorAll('.pick input:checked')).map(function(e){{return e.value}});
document.getElementById('line').textContent='0306 pick: '+(v.join(' ')||'none');}}
document.addEventListener('change',upd);upd();
document.getElementById('copy').onclick=function(){{var t=document.getElementById('line').textContent,b=this;
function fb(){{var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{{document.execCommand('copy')}}catch(e){{}}a.remove()}}
try{{if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(t).catch(fb)}}else fb()}}catch(e){{fb()}}
b.textContent='Copied';setTimeout(function(){{b.textContent='Copy'}},1500)}};
</script></body></html>"""
with open(PAGE, "w") as f:
    f.write(HTML)
print("wrote", PAGE, len(HTML), "bytes")
