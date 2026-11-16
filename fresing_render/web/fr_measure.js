// Fresing Render web 3D page: the measuring maths of the part tools (task 0135). Plain functions on points
// [x, y, z] in metres (the model's own coordinates, Blender's axes: z up); fr_tools.js turns clicks into "picks" and
// draws what these return. Also loaded by node in tests/test_web_tools.py.
//
// A pick: {kind: 'point' | 'flat' | 'round' | 'axis', p: the clicked point,
//          n: the flat face's normal (unit)            – flat
//          o, d, r: a point on the axis, its direction (unit), the face's own radius (0: no single one) – round, axis}
// measure(a, b, mode) -> {type, dist, angle, from, to, lines: [text …], vec}
//   mode 'points': always the straight distance between the two clicked points
//   mode 'faces' : by what was clicked – two flat faces: the distance between the planes (parallel within 1°) or
//                  the angle between them; two round faces: centre to centre (between the axes); a flat face and a
//                  round face: from the plane to the axis; anything else: point to point
// ``from`` / ``to`` are the ends of the line drawn, ``vec`` = to - from (its X/Y/Z parts are shown as arrows).
var FRMeasure = (function () {
  'use strict';
  var PARALLEL_DEG = 1.0;

  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function mul(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function len(a) { return Math.sqrt(dot(a, a)); }
  function unit(a) { var l = len(a) || 1; return mul(a, 1 / l); }
  function deg(rad) { return rad * 180 / Math.PI; }
  // angle between two directions taken as lines (0 … 90°)
  function lineAngle(u, v) { return deg(Math.acos(Math.min(1, Math.abs(dot(unit(u), unit(v)))))); }
  // the foot of p on the line (o, d)
  function onLine(p, o, d) { return add(o, mul(d, dot(sub(p, o), d))); }
  // the foot of p on the plane through q with normal n
  function onPlane(p, q, n) { return sub(p, mul(n, dot(sub(p, q), n))); }

  // numbers as the owner reads them: mm with one decimal (two below 10 mm), a thin space between thousands
  function mm(m) {
    var v = m * 1000, a = Math.abs(v), s = a < 10 ? a.toFixed(2) : a.toFixed(1);
    var parts = s.split('.'), whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return (v < 0 && a >= 0.005 ? '−' : '') + whole + '.' + parts[1] + ' mm';
  }
  function angleText(a) { return a.toFixed(1) + '°'; }

  function points(a, b) {
    var v = sub(b.p, a.p);
    return { type: 'points', dist: len(v), from: a.p, to: b.p, vec: v, lines: ['Distance ' + mm(len(v))] };
  }

  function planes(a, b) {
    var ang = lineAngle(a.n, b.n);
    if (ang <= PARALLEL_DEG) {
      // the mean normal (one sign) gives the gap; the line goes square from b's click onto a's plane
      var n = dot(a.n, b.n) < 0 ? mul(b.n, -1) : b.n, nm = unit(add(a.n, n));
      var foot = onPlane(b.p, a.p, nm), v = sub(b.p, foot), dist = Math.abs(dot(sub(b.p, a.p), nm));
      return { type: 'planes', dist: dist, angle: ang, from: foot, to: b.p, vec: v,
               lines: ['Between the planes ' + mm(dist), ang > 0.05 ? '(parallel within ' + angleText(ang) + ')' : 'parallel'] };
    }
    var p = points(a, b);
    return { type: 'angle', dist: p.dist, angle: ang, from: a.p, to: b.p, vec: p.vec,
             lines: ['Angle between the planes ' + angleText(ang), 'Not parallel; points ' + mm(p.dist) + ' apart'] };
  }

  // the shortest line between two axis lines: its two ends (parallel: square to them, near the clicks)
  function axes(a, b) {
    var ang = lineAngle(a.d, b.d);
    var c1, c2;
    if (ang <= PARALLEL_DEG) {
      c1 = onLine(a.p, a.o, a.d);
      c2 = onLine(c1, b.o, b.d);
      var v = sub(c2, c1), dist = len(v);
      var lines = dist < 1e-6 ? ['Centre to centre 0.00 mm', 'On one axis'] : ['Centre to centre ' + mm(dist)];
      if (ang > 0.05) lines.push('(axes parallel within ' + angleText(ang) + ')');
      return { type: 'axes', dist: dist, angle: ang, from: c1, to: c2, vec: v, lines: lines };
    }
    var w = cross(a.d, b.d), wl = len(w), r = sub(b.o, a.o);
    var t1 = dot(cross(r, b.d), w) / (wl * wl), t2 = dot(cross(r, a.d), w) / (wl * wl);
    c1 = add(a.o, mul(a.d, t1));
    c2 = add(b.o, mul(b.d, t2));
    var v2 = sub(c2, c1), d2 = len(v2);
    return { type: 'axes', dist: d2, angle: ang, from: c1, to: c2, vec: v2,
             lines: [(d2 < 1e-6 ? 'The axes cross' : 'Shortest between the axes ' + mm(d2)),
                     'Angle between the axes ' + angleText(ang)] };
  }

  function faceAxis(f, r) {        // f flat, r round / axis
    var s = Math.abs(dot(f.n, r.d));
    var ang = deg(Math.asin(Math.min(1, s)));              // 0: the axis lies along the face
    if (ang <= PARALLEL_DEG) {
      var c = onLine(r.p, r.o, r.d), foot = onPlane(c, f.p, f.n), v = sub(c, foot), dist = Math.abs(dot(sub(c, f.p), f.n));
      var lines = ['Face to centre ' + mm(dist)];
      if (ang > 0.05) lines.push('(axis along the face within ' + angleText(ang) + ')');
      return { type: 'face-axis', dist: dist, angle: ang, from: foot, to: c, vec: v, lines: lines };
    }
    // the axis goes through the face's plane: where, and at what angle
    var t = dot(sub(f.p, r.o), f.n) / dot(r.d, f.n), x = add(r.o, mul(r.d, t)), v2 = sub(x, f.p);
    return { type: 'face-axis', dist: 0, angle: ang, from: f.p, to: x, vec: v2,
             lines: ['The axis meets the face at ' + angleText(ang), 'Click to crossing ' + mm(len(v2))] };
  }

  function isRound(k) { return k.kind === 'round' || k.kind === 'axis'; }

  function measure(a, b, mode) {
    if (mode !== 'points') {
      if (a.kind === 'flat' && b.kind === 'flat') return planes(a, b);
      if (isRound(a) && isRound(b)) return axes(a, b);
      if (a.kind === 'flat' && isRound(b)) return faceAxis(a, b);
      if (isRound(a) && b.kind === 'flat') return flip(faceAxis(b, a));
    }
    return points(a, b);
  }
  function flip(r) { var f = r.from; r.from = r.to; r.to = f; r.vec = mul(r.vec, -1); return r; }

  // one click: what the face itself says
  function single(a) {
    if (a.kind === 'round' && a.r > 0) return { type: 'diameter', dist: 2 * a.r, lines: ['Ø ' + mm(2 * a.r) + '  (radius ' + mm(a.r) + ')'] };
    if (a.kind === 'axis') return { type: 'axis', lines: ['Round face (no single diameter: a cone or a rounded edge)'] };
    if (a.kind === 'flat') return { type: 'flat', lines: ['Flat face'] };
    return { type: 'point', lines: ['Point'] };
  }

  // the X / Y / Z parts of a vector as three arrows one after the other (a staircase from ``from``)
  function parts(from, vec) {
    var out = [], at = from.slice(), names = ['X', 'Y', 'Z'];
    for (var i = 0; i < 3; i++) {
      if (Math.abs(vec[i]) < 1e-7) continue;
      var to = at.slice();
      to[i] += vec[i];
      out.push({ axis: names[i], from: at, to: to, value: vec[i], text: names[i] + ' ' + mm(vec[i]) });
      at = to;
    }
    return out;
  }

  // a ROW of the file's face data (core/web3d_faces.py) in the mesh's written coordinates -> a pick in the model's
  // coordinates. ``m`` (16 numbers, column-major) takes written points to the model's; the clicked point ``p``
  // (model coordinates) is put on the face.
  function fromRow(row, m, p) {
    function pt(v) { return [m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13],
                             m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14]]; }
    function dir(v) { return [m[0] * v[0] + m[4] * v[1] + m[8] * v[2], m[1] * v[0] + m[5] * v[1] + m[9] * v[2],
                              m[2] * v[0] + m[6] * v[1] + m[10] * v[2]]; }
    var kind = row ? Math.round(row[0]) : 0;
    if (kind === 1) {
      var n0 = [row[1], row[2], row[3]], q0 = mul(n0, row[4]);          // a point on the plane
      // normals go with the inverse transpose: a point and two directions in the face, crossed
      var t1 = unit(cross(n0, Math.abs(n0[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0])), t2 = cross(n0, t1);
      var q = pt(q0), n = unit(cross(dir(t1), dir(t2)));
      if (dot(n, dir(n0)) < 0) n = mul(n, -1);
      return { kind: 'flat', p: onPlane(p, q, n), n: n };
    }
    if (kind === 2 || kind === 3) {
      var d0 = unit([row[4], row[5], row[6]]), o = pt([row[1], row[2], row[3]]), d = unit(dir(d0));
      var u = unit(cross(d0, Math.abs(d0[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0])), w = cross(d0, u);
      var r = Math.abs(row[7]) * 0.5 * (len(dir(u)) + len(dir(w)));    // across the axis, in the part's own scale
      var c = onLine(p, o, d), off = sub(p, c), ol = len(off);
      // the clicked point onto the round face (the drawn triangles lie a little inside it)
      var ps = kind === 2 && ol > 1e-9 ? add(c, mul(off, r / ol)) : p;
      return { kind: kind === 2 ? 'round' : 'axis', p: ps, o: o, d: d, r: kind === 2 ? r : 0 };
    }
    return { kind: 'point', p: p };
  }

  return { measure: measure, single: single, parts: parts, fromRow: fromRow, mm: mm, angleText: angleText,
           PARALLEL_DEG: PARALLEL_DEG, lineAngle: lineAngle };
})();
if (typeof module !== 'undefined') module.exports = FRMeasure;
