"""0381: profile of the per-update cost (11,500 mesh objects, Blender as a module): py-spy record --native -r 200 -f raw -o prof.txt -- python s2b_profile.py"""
import sys, time
sys.argv=[sys.argv[0], "/dev/null"]
exec(open("/home/user/CAD-render-animation/tasks/0381/s2_scaling.py").read().split("out = {}")[0])
sc, obs = scene_of(11500)
vl = bpy.context.view_layer; m = obs[5000]
t0=time.time()
for k in range(1500):
    m.location.z = 0.001*k; vl.update()
print("ms", (time.time()-t0)/1.5)
