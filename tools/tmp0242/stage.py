"""Task 0242 (throw-away): a copy of a page with stage marks on <html> (data-fr-stages)."""
import sys
PRE = """<script>(function(){var t0=Date.now();window.__st=function(s){var d=document.documentElement.dataset;
var a=d.frStages?JSON.parse(d.frStages):[];a.push([s,Math.round(performance.now()),Date.now()-t0]);
if(a.length>200)a.splice(100,1);d.frStages=JSON.stringify(a);};__st('script');})();</script>"""
SUBS = [
    ("(function holdTestClock() {", "(function holdTestClock() { __st('hold?');"),
    ("if (++n > 5000 || page.ready || page.errors.length) { URL.revokeObjectURL(url); return; }",
     "if (n % 250 === 0) __st('f' + n); if (++n > 5000 || page.ready || page.errors.length) { __st('hold-end n=' + n + ' ready=' + page.ready + ' err=' + page.errors.length); URL.revokeObjectURL(url); return; }"),
    ("fetch(url).then(again, function () { URL.revokeObjectURL(url); });",
     "fetch(url).then(again, function (e) { __st('fetch-rejected ' + e); URL.revokeObjectURL(url); });"),
    ("page.loadTimes = { read: performance.now() - t0 };", "page.loadTimes = { read: performance.now() - t0 }; __st('read');"),
    ("{ page.loadTimes.unpack = performance.now() - t1;", "{ __st('unpacked'); page.loadTimes.unpack = performance.now() - t1;"),
    ("loader.parse(buf, '', function (gltf) {", "__st('parse'); loader.parse(buf, '', function (gltf) { __st('parsed');"),
    ("setupTubes(gltf).then(function () {", "setupTubes(gltf).then(function () { __st('tubes');"),
    ("function oneLess() { if (--waiting === 0) start(); }", "function oneLess() { __st('oneLess ' + (waiting - 1)); if (--waiting === 0) start(); }"),
    ("    page.ready = true;\n", "    page.ready = true; __st('ready');\n"),
    ("function fail(text, why) {", "function fail(text, why) { __st('fail ' + why);"),
]
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
for a, b in SUBS:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
i = s.index("<script")
s = s[:i] + PRE + s[i:]
open(dst, "w", encoding="utf-8").write(s)
