"""Study 0306 – a live drive in the real Blender (under xvfb): a modal operator with a 60 Hz timer moves a stand-in
vehicle by the drive model while simulated keys are held; measures the tick intervals and the key events.

    xvfb-run -a -s "-screen 0 1600x900x24" blender --factory-startup --enable-event-simulate \
        --python tasks/0306_proto/drive_live_blender.py -- <out.json>

Keys: W / Up = throttle, S / Down = brake (held at a standstill: reverse), A / D = steer.
"""

import json
import math
import os
import sys
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drive as D            # noqa: E402
import ground as G           # noqa: E402
from spec import CAR         # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/drive_live.json"
STATE = {"ticks": [], "events": [], "done": False, "t_last": None}

# a ground of ~350,000 triangles on screen and a stand-in car (boxes)
g = G.offroad(G.flat(-15.0, -8.0, 95.0, 8.0, 0.05), seed=4, roughness=0.1, x_from=10.0)
STEP = int(os.environ.get("GROUND_STEP", "2"))
z = g.z[::STEP, ::STEP]
bpy.ops.mesh.primitive_grid_add(x_subdivisions=z.shape[0] - 1, y_subdivisions=z.shape[1] - 1, size=1.0)
gr = bpy.context.object
n = len(gr.data.vertices)
co = np.zeros(n * 3, np.float32)
gr.data.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
co[:, 0] = co[:, 0] * 110.0 + 40.0
co[:, 1] = co[:, 1] * 16.0
gr.data.vertices.foreach_set("co", co.ravel())
gr.data.update()
for o in list(bpy.data.objects):
    if o.name in ("Cube",):
        bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.4, 0, 0.9))
car = bpy.context.object
car.scale = (4.6, 1.9, 1.1)
bpy.ops.object.transform_apply(scale=True)
car.name = "Car"

KEYS = {"W": "throttle", "UP_ARROW": "throttle", "S": "brake", "DOWN_ARROW": "brake", "A": "left", "D": "right"}


class DRIVE_OT_live(bpy.types.Operator):
    bl_idname = "fresing_proto.drive"
    bl_label = "Drive"

    def invoke(self, context, event):
        self.drv = D.Driver(CAR)
        self.held = set()
        self.t0 = time.perf_counter()
        self.last = self.t0
        wm = context.window_manager
        self.timer = wm.event_timer_add(1.0 / 60.0, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        now = time.perf_counter()
        if event.type in KEYS and event.value in ("PRESS", "RELEASE"):
            STATE["events"].append((round(now - self.t0, 4), event.type, event.value, bool(event.is_repeat)))
            if event.value == "PRESS":
                self.held.add(KEYS[event.type])
            else:
                self.held.discard(KEYS[event.type])
            return {"RUNNING_MODAL"}
        if event.type == "TIMER":
            dt = now - self.last
            self.last = now
            STATE["ticks"].append(dt)
            inp = D.Inputs(throttle=1.0 if "throttle" in self.held else 0.0,
                           brake=1.0 if "brake" in self.held else 0.0,
                           steer=(1.0 if "left" in self.held else 0.0) - (1.0 if "right" in self.held else 0.0))
            self.drv.tick(inp, dt)
            d = self.drv
            car.location = (d.x, d.y, 0.0)
            car.rotation_euler = (0.0, 0.0, d.heading)
            return {"RUNNING_MODAL"}
        if event.type == "ESC":
            context.window_manager.event_timer_remove(self.timer)
            STATE["samples"] = len(self.drv.samples)
            STATE["end"] = (self.drv.x, self.drv.y, self.drv.heading)
            STATE["done"] = True
            return {"FINISHED"}
        return {"PASS_THROUGH"}


bpy.utils.register_class(DRIVE_OT_live)

# the script: (seconds after start, key, PRESS/RELEASE)
PLAN = [(0.5, "W", "PRESS"), (4.0, "A", "PRESS"), (5.5, "A", "RELEASE"), (7.0, "W", "RELEASE"), (7.0, "D", "PRESS"),
        (8.0, "D", "RELEASE"), (8.0, "S", "PRESS"), (11.0, "S", "RELEASE"), (11.5, "ESC", "PRESS")]


def window_area():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas), key=lambda a: a.width * a.height)
    if area.type != "VIEW_3D":
        area.type = "VIEW_3D"
    return win, area


def start():
    win, area = window_area()
    region = next(r for r in area.regions if r.type == "WINDOW")
    for sp in area.spaces:
        if sp.type == "VIEW_3D":
            sp.shading.type = "SOLID"
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    with bpy.context.temp_override(window=win, area=area, region=region):
        bpy.ops.fresing_proto.drive("INVOKE_DEFAULT")
    STATE["t0"] = time.perf_counter()
    STATE["plan"] = list(PLAN)
    STATE["xy"] = (x, y)
    bpy.app.timers.register(feed, first_interval=0.05)
    return None


def feed():
    win, _area = window_area()
    t = time.perf_counter() - STATE["t0"]
    while STATE["plan"] and STATE["plan"][0][0] <= t:
        _t, key, val = STATE["plan"].pop(0)
        x, y = STATE["xy"]
        win.event_simulate(type=key, value=val, x=x, y=y)
    if STATE["done"] or (not STATE["plan"] and t > 14):
        tk = np.array(STATE["ticks"][1:])
        res = {"ticks": int(len(tk)), "mean_ms": round(float(tk.mean() * 1000), 2),
               "median_ms": round(float(np.median(tk) * 1000), 2), "p95_ms": round(float(np.percentile(tk, 95) * 1000), 2),
               "max_ms": round(float(tk.max() * 1000), 2), "rate_hz": round(float(1 / tk.mean()), 1),
               "events": STATE["events"], "end": STATE.get("end"), "samples": STATE.get("samples"),
               "ground_triangles": len(gr.data.polygons) * 2, "done": STATE["done"]}
        with open(OUT, "w") as f:
            json.dump(res, f, indent=1)
        print("DRIVE_LIVE", json.dumps({k: v for k, v in res.items() if k != "events"}))
        bpy.ops.wm.quit_blender()
        return None
    return 0.01


bpy.app.timers.register(start, first_interval=2.0)
