"""Task 0168 – the page that compares every highlight look in six colours (branch only, never merged).

    python3 tools/lesson_looks_page.py /tmp/full tasks/0168_page

Reads <src>/clips/*.mp4|jpg and <src>/clips_*.json (descriptions and costs, from tools/lesson_clips_app.py), writes
<dst>/index.html, <dst>/clips/, <dst>/fonts/. One self-made page, nothing loaded from outside the folder.
"""

import glob
import json
import os
import shutil
import subprocess
import sys

SRC, DST = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = [("Fresing Green", "479B29"), ("Green Bright", "5CBF37"), ("Amber", "F5B700"), ("Hi-vis orange", "FF6A13"),
           ("Cyan", "1FB5D6"), ("White", "F2F2F2")]
BLUE_HEX = "4772B3"
ROUND1 = {"button": set("ABCDEF"), "section": set("123"), "part": set("123")}
TITLES = {"button": "Buttons", "section": "Closed sections", "part": "Parts"}
INTRO = {
    "button": "The button the lesson points at, in the side panel. Seen at step 3 (<i>Add rotate joint</i>, joined to "
              "<i>Add slide joint</i>).",
    "section": "A section that is closed but holds the next button, seen at step 7 (<i>6 Animation</i>).",
    "part": "The part on the model, with the text card. Seen at step 3 (the boom).",
}

meta = {"costs": {}, "desc": {}}
for f in glob.glob(os.path.join(SRC, "clips_*.json")):
    m = json.load(open(f))
    meta["costs"].update(m["costs"])
    meta["desc"].update(m["desc"])

os.makedirs(os.path.join(DST, "clips"), exist_ok=True)
os.makedirs(os.path.join(DST, "fonts"), exist_ok=True)
for f in glob.glob(os.path.join(SRC, "clips", "*")):
    shutil.copy(f, os.path.join(DST, "clips", os.path.basename(f)))
for n in ("IBMPlexSans-Regular-Latin1.woff2", "IBMPlexSans-SemiBold-Latin1.woff2", "OFL-IBM-Plex.txt"):
    shutil.copy(os.path.join(HERE, "..", "site", "fonts", n), os.path.join(DST, "fonts", n))


def size(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip().split(",")
    return int(out[0]), int(out[1])


data = {"colours": [{"name": n, "hex": h} for n, h in COLOURS], "blue": BLUE_HEX, "groups": []}
for kind in ("button", "section", "part"):
    looks = []
    for key, desc in sorted((k.split(" ", 1)[1], v) for k, v in meta["desc"].items() if k.startswith(kind + " ")):
        have = {h for _, h in COLOURS if os.path.exists(os.path.join(DST, "clips", f"{kind}_{key}_{h}.mp4"))}
        blue = os.path.exists(os.path.join(DST, "clips", f"{kind}_{key}_{BLUE_HEX}.mp4"))
        if not have and not blue:
            continue
        cost = meta["costs"].get(f"{kind} {key} #479B29") or meta["costs"].get(f"{kind} {key} #{BLUE_HEX}")
        looks.append({"key": key, "desc": desc, "new": key not in ROUND1[kind], "cost": cost, "blue": blue})
    w = h = 0
    for p in glob.glob(os.path.join(DST, "clips", f"{kind}_*.mp4"))[:1]:
        w, h = size(p)
    data["groups"].append({"kind": kind, "title": TITLES[kind], "intro": INTRO[kind], "looks": looks, "w": w, "h": h})

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Highlight looks round 2</title>
<style>
@font-face{font-family:"IBM Plex Sans";font-weight:400;src:url(fonts/IBMPlexSans-Regular-Latin1.woff2) format("woff2")}
@font-face{font-family:"IBM Plex Sans";font-weight:600;src:url(fonts/IBMPlexSans-SemiBold-Latin1.woff2) format("woff2")}
:root{--green:#479B29;--green-bright:#5CBF37;--deep:#1A2027;--panel:#252E36;--line:#3A4650;--text:#E8ECEF;--mute:#9AA6B0;
--sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--accent:#479B29}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--deep);color:var(--text);font:16px/1.5 var(--sans)}
header.top{position:sticky;top:0;z-index:5;background:rgba(26,32,39,.96);border-bottom:1px solid var(--line);
padding:10px 16px;display:flex;gap:16px;align-items:center;min-height:56px;padding-right:min(430px,52vw)}
header.top a{color:var(--text);text-decoration:none;font-weight:600;padding:4px 10px;border-radius:6px;white-space:nowrap}
header.top a:hover{background:var(--panel)}
#picker{position:fixed;top:8px;right:8px;z-index:10;background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:8px 10px;box-shadow:0 4px 18px rgba(0,0,0,.4);max-width:calc(100vw - 16px)}
#picker .sw{display:flex;gap:6px}
#picker button{width:30px;height:30px;border-radius:50%;border:2px solid transparent;cursor:pointer;padding:0;
outline:1px solid rgba(255,255,255,.25)}
#picker button[aria-pressed=true]{border-color:#fff;outline:2px solid var(--deep);transform:scale(1.12)}
#picker .nm{font-size:13px;margin-top:5px;color:var(--text);white-space:nowrap}
#picker .nm b{font-weight:600}
main{max-width:1120px;margin:0 auto;padding:16px}
h1{font-size:26px;margin:18px 0 6px}
h2{font-size:21px;margin:36px 0 4px;padding-top:6px;border-top:1px solid var(--line)}
p.lead{color:var(--mute);margin:4px 0 12px;max-width:70ch}
label.opt{display:inline-flex;gap:8px;align-items:center;cursor:pointer;margin:4px 16px 4px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;margin-top:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:8px}
.card.picked{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.card h3{margin:0;font-size:17px;display:flex;gap:8px;align-items:center}
.card h3 .k{display:inline-flex;min-width:28px;height:28px;border-radius:6px;background:var(--accent);color:#111;font-weight:600;
align-items:center;justify-content:center;padding:0 6px}
.tag{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;background:#fff;color:#111;border-radius:4px;padding:1px 6px}
.card p{margin:0;color:var(--text);font-size:15px}
.vids{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-start}
.vid{background:#111;border-radius:6px;overflow:hidden;line-height:0;max-width:100%}
.vid video{display:block;width:100%;height:auto}
.vid small{display:block;line-height:1.3;padding:3px 6px;color:var(--mute);font-size:12px;background:#161b21}
.meta{color:var(--mute);font-size:13px}
.pick{display:inline-flex;gap:8px;align-items:center;cursor:pointer;font-weight:600}
.pick input{width:20px;height:20px;accent-color:var(--accent)}
#answer{position:sticky;bottom:0;background:var(--panel);border-top:1px solid var(--line);padding:12px 16px;margin:32px -16px 0;
display:flex;gap:12px;align-items:center;flex-wrap:wrap}
#answer code{flex:1 1 320px;background:#111;border-radius:6px;padding:8px 10px;font-size:14px;word-break:break-word}
#answer button{font:inherit;font-weight:600;background:var(--green);color:#fff;border:0;border-radius:8px;padding:8px 18px;cursor:pointer}
#answer button:hover{background:var(--green-bright)}
.note{color:var(--mute);font-size:13px;margin-top:6px}
@media (max-width:640px){header.top{padding-right:16px;flex-wrap:wrap}#picker{position:fixed;top:auto;bottom:70px;right:8px}
#picker button{width:34px;height:34px}.grid{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>
<header class="top"><strong>Looks 2</strong><a href="#button">Buttons</a><a href="#section">Closed sections</a><a href="#part">Parts</a><a href="#answer">Answer</a></header>
<div id="picker" role="group" aria-label="Colour"><div class="sw" id="sw"></div><div class="nm" id="nm"></div></div>
<main>
<h1>Highlight looks, round 2</h1>
<p class="lead">Every look from round 1 plus new ones, each moving as it will in the app (the test crane, a 3 s loop).
Choose the colour top right (or press keys 1 to 6): every clip changes. Tick the look you like in each group (two
ticks if you want to compare), then copy the line at the bottom and send it back.</p>
<label class="opt"><input type="checkbox" id="side"> Side by side with Fresing Green</label>
<label class="opt"><input type="checkbox" id="onlynew"> Only the new looks</label>
<div id="groups"></div>
<div id="answer"><code id="line"></code><button id="copy" type="button">Copy</button><span id="ok" class="meta"></span></div>
<p class="note">Costs are the app's drawing time per redraw on a test machine with no graphics card (software OpenGL),
Python side only. They do not depend on the colour. Look F stays Blender's own blue in every colour.</p>
</main>
<script>
const DATA = __DATA__;
const $ = (s, r = document) => r.querySelector(s);
const state = {ci: 0, side: false, onlynew: false, picks: {button: [], section: [], part: []}};
try { const s = JSON.parse(localStorage.getItem("fr0168") || "{}");
  if (s && typeof s === "object") { state.ci = Math.min(Math.max(+s.ci || 0, 0), DATA.colours.length - 1);
    for (const k of ["button", "section", "part"]) if (Array.isArray(s.picks && s.picks[k])) state.picks[k] = s.picks[k].slice(0, 2);
    state.side = !!s.side; state.onlynew = !!s.onlynew; } } catch (e) {}
const save = () => { try { localStorage.setItem("fr0168", JSON.stringify(state)); } catch (e) {} };
const hex = () => DATA.colours[state.ci].hex;
const clip = (kind, key, h) => `clips/${kind}_${key}_${h}`;
const io = ("IntersectionObserver" in window) ? new IntersectionObserver(es => es.forEach(e => {
  const v = e.target;
  if (e.isIntersecting) { if (!v.getAttribute("src")) v.src = v.dataset.src; v.play().catch(() => {}); }
  else { v.pause(); }
}), {rootMargin: "120px"}) : null;

function vid(kind, g, look, h, label) {
  const d = document.createElement("div"); d.className = "vid"; d.style.width = (g.w / 2) + "px";
  const v = document.createElement("video");
  v.muted = true; v.loop = true; v.playsInline = true; v.setAttribute("playsinline", ""); v.preload = "none";
  v.dataset.src = clip(kind, look.key, h) + ".mp4"; v.dataset.h = h; v.poster = clip(kind, look.key, h) + ".jpg";
  v.setAttribute("aria-label", `${g.title} ${look.key} ${label}`);
  d.appendChild(v);
  if (label) { const s = document.createElement("small"); s.textContent = label; d.appendChild(s); }
  if (io) io.observe(v); else { v.src = v.dataset.src; v.autoplay = true; }
  return d;
}
function build() {
  const root = $("#groups"); root.textContent = "";
  for (const g of DATA.groups) {
    const sec = document.createElement("section"); sec.id = g.kind;
    sec.innerHTML = `<h2>${g.title}</h2><p class="lead">${g.intro}</p>`;
    const grid = document.createElement("div"); grid.className = "grid"; sec.appendChild(grid);
    for (const look of g.looks) {
      if (state.onlynew && !look.new) continue;
      const card = document.createElement("div"); card.className = "card"; card.dataset.kind = g.kind; card.dataset.key = look.key;
      const picked = state.picks[g.kind].includes(look.key); if (picked) card.classList.add("picked");
      card.innerHTML = `<h3><span class="k">${look.key}</span>${look.new ? '<span class="tag">new</span>' : ""}</h3>`;
      const p = document.createElement("p"); p.textContent = look.desc; card.appendChild(p);
      const vids = document.createElement("div"); vids.className = "vids"; card.appendChild(vids);
      const blueOnly = look.blue;
      const h = blueOnly ? DATA.blue : hex();
      const green = DATA.colours[0];
      if (state.side && !blueOnly && h !== green.hex) {
        vids.appendChild(vid(g.kind, g, look, h, DATA.colours[state.ci].name));
        vids.appendChild(vid(g.kind, g, look, green.hex, green.name));
      } else vids.appendChild(vid(g.kind, g, look, h, blueOnly ? "stays Blender blue" : ""));
      const m = document.createElement("div"); m.className = "meta";
      m.textContent = look.cost != null ? `Drawing: ${look.cost.toFixed(2)} ms per redraw` : "";
      card.appendChild(m);
      const lab = document.createElement("label"); lab.className = "pick";
      lab.innerHTML = `<input type="checkbox" ${picked ? "checked" : ""}> Pick ${look.key}`;
      lab.firstChild.addEventListener("change", e => {
        let a = state.picks[g.kind].filter(x => x !== look.key);
        if (e.target.checked) { a.push(look.key); if (a.length > 2) a.shift(); }
        state.picks[g.kind] = a; save(); build(); line();
      });
      card.appendChild(lab); grid.appendChild(card);
    }
    root.appendChild(sec);
  }
}
function recolour() {
  document.documentElement.style.setProperty("--accent", "#" + hex());
  $("#nm").innerHTML = `<b>${DATA.colours[state.ci].name}</b> #${hex()}`;
  document.querySelectorAll("#sw button").forEach((b, i) => b.setAttribute("aria-pressed", i === state.ci));
  if (state.side) { build(); return; }
  document.querySelectorAll("video").forEach(v => {
    if (v.dataset.h === DATA.blue) return;
    const kind = v.closest(".card").dataset.kind, key = v.closest(".card").dataset.key, t = v.currentTime;
    v.dataset.h = hex(); v.dataset.src = clip(kind, key, hex()) + ".mp4"; v.poster = clip(kind, key, hex()) + ".jpg";
    if (v.getAttribute("src")) { v.src = v.dataset.src; v.addEventListener("loadedmetadata", () => { try { v.currentTime = t; } catch (e) {} v.play().catch(() => {}); }, {once: true}); }
  });
}
function line() {
  const part = (k, n) => state.picks[k].length ? `${n} ${state.picks[k].join(" + ")}` : `${n} -`;
  $("#line").textContent = `0168 pick: ${part("button", "button")}, ${part("section", "section")}, ${part("part", "part")}, colour ${DATA.colours[state.ci].name}`;
}
function setColour(i) { state.ci = i; save(); recolour(); line(); }
DATA.colours.forEach((c, i) => {
  const b = document.createElement("button"); b.type = "button"; b.style.background = "#" + c.hex;
  b.title = `${i + 1}: ${c.name} #${c.hex}`; b.setAttribute("aria-label", `${c.name} ${c.hex}`);
  b.addEventListener("click", () => setColour(i)); $("#sw").appendChild(b);
});
addEventListener("keydown", e => { if (e.target.tagName === "INPUT" || e.ctrlKey || e.metaKey || e.altKey) return;
  const n = parseInt(e.key, 10); if (n >= 1 && n <= DATA.colours.length) setColour(n - 1); });
$("#side").checked = state.side; $("#onlynew").checked = state.onlynew;
$("#side").addEventListener("change", e => { state.side = e.target.checked; save(); build(); recolour(); });
$("#onlynew").addEventListener("change", e => { state.onlynew = e.target.checked; save(); build(); recolour(); });
$("#copy").addEventListener("click", async () => {
  const t = $("#line").textContent;
  try { await navigator.clipboard.writeText(t); $("#ok").textContent = "Copied"; }
  catch (e) { const r = document.createRange(); r.selectNodeContents($("#line")); const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    $("#ok").textContent = "Select and copy the line"; }
  setTimeout(() => $("#ok").textContent = "", 2500);
});
build(); recolour(); line();
</script></body></html>
"""
open(os.path.join(DST, "index.html"), "w").write(HTML.replace("__DATA__", json.dumps(data)))
total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(DST) for f in fs)
print(f"page written, folder {total / 1e6:.1f} MB, {sum(len(g['looks']) for g in data['groups'])} looks")
