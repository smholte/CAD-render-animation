"""0141: other ways into the same function. Built moving-part model: at a late frame, type the same layback again /
set the same water level again; not built: the same at a late frame."""
import sys, tempfile
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repeat
from repeat import *  # noqa
folder = tempfile.mkdtemp()
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
for built in (True, False):
    for what in ("layback", "water_level", "weather_speed"):
        sc = load(folder)
        paths.set_up_moving_model(sc)
        s = sc.fresing
        a = s.animations[paths.MOVING_ANIMATION]
        if built:
            animation.bake(sc, a)
        it = paths.find(sc, paths.MOVING_CABLE)
        ref = np.array(it.sea_start), float(it.sea_mark)
        sc.frame_set(289)
        it = paths.find(sc, paths.MOVING_CABLE)
        if what == "layback":
            it.sea_layback = float(it.sea_layback)          # the same number typed again
        elif what == "water_level":
            s.water_level = float(s.water_level)
        else:
            s.weather.vessel_speed = float(s.weather.vessel_speed)
        it = paths.find(sc, paths.MOVING_CABLE)
        d = float(np.linalg.norm(np.array(it.sea_start) - ref[0]))
        print(f"{'built' if built else 'not built'}, frame 289 shown, the same {what} set again: touch-down moved {d:.3f} m, "
              f"mark {ref[1]:.3f} -> {float(it.sea_mark):.3f}", flush=True)
