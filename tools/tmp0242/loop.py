"""Task 0242 (throw-away): open the staged pages many times, print the state and, for a page that stayed
"loading", its stage marks."""
import collections, html, os, re, subprocess, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from concurrent.futures import ThreadPoolExecutor
from fresing_render.core import web3d_env as env

HERE = os.path.dirname(os.path.abspath(__file__))
last = {}
class P(subprocess.Popen):
    def communicate(self, *a, **k):
        out, err = super().communicate(*a, **k)
        import threading
        last[threading.get_ident()] = out
        return out, err
env.subprocess.Popen = P

JOBS = [("small_st.html", "auto=0&frames=2&t=0.9&places=1"), ("under_st.html", "auto=0&frames=3&t=4")]
def one(i):
    import threading
    name, q = JOBS[i % 2]
    t = time.time()
    try:
        g = env.read_page(os.path.join(HERE, name), env.find_browser(), q, seconds=120)
        st = g["state"]
    except Exception as e:
        st = "EXC " + str(e)
    dom = (last.get(threading.get_ident()) or b"").decode("utf-8", "replace")
    m = re.search(r'data-fr-stages="([^"]*)"', dom)
    stages = json.loads(html.unescape(m.group(1))) if m else None
    return name, st, round(time.time() - t, 1), stages

n, par = int(sys.argv[1]), int(sys.argv[2])
print("browser:", env.find_browser(), flush=True)
with ThreadPoolExecutor(par) as ex:
    res = list(ex.map(one, range(n)))
c = collections.Counter((r[0], r[1].split(" frames")[0][:40]) for r in res)
print(dict(c), "slowest", max(r[2] for r in res), "s")
for r in res:
    if not r[1].startswith("ready"):
        print("NOT READY", r[0], r[1][:80], r[2], "s")
        print("   ", r[3])
ok = [r for r in res if r[1].startswith("ready")]
if ok:
    print("a ready one:", ok[0][0], ok[0][3])
