// Fresing Render web 3D page: the measuring maths of the part tools (task 0135). Plain functions on points
// [x, y, z] in metres (the model's own coordinates, Blender's axes: z up); fr_tools.js turns clicks into "picks" and
// draws what these return. Also loaded by node in tests/test_web_tools.py.
//
// A pick: {kind: 'point' | 'flat' | 'round' | 'axis' | 'line' | 'circle', p: the clicked point,
//          n: the flat face's normal (unit)            – flat
//          o, d, r: a point on the axis, its direction (unit), the face's own radius (0: no single one) – round, axis
//          o, d, a, b, len: a straight edge: its line (o = a, d unit) and its two ends – line (task 0219)
//          o, d, c, r, s, sweep: a round edge: centre (o = c), axis (unit), radius, where the arc starts, its angle
//          (radians, 2π: a whole circle) – circle (task 0219)}
// measure(a, b, mode) -> {type, dist, angle, from, to, lines: [text …], vec}
//   mode 'points': always the straight distance between the two clicked points
//   mode 'faces' : by what was clicked – two flat faces: the distance between the planes (parallel within 1°) or
//                  the angle between them; two round faces: centre to centre (between the axes); a flat face and a
//                  round face: from the plane to the axis; anything else: point to point.
//                  Edges (task 0219): a straight edge is a line like an axis – edge to edge (parallel: the gap,
//                  else the shortest line + the angle), edge to an axis, edge to a flat face (along it: the gap, else
//                  where and at what angle it meets the plane), a point to the edge. A round edge counts by its
//                  centre – to another circle's centre (+ across and along the axes when they are parallel), to an
//                  axis or a straight edge (square to it), to a flat face (square to the plane), to a point.
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
    var c1, c2, ea = a.kind === 'line', eb = b.kind === 'line';
    var what = ea && eb ? 'Edge to edge ' : ea || eb ? 'Edge to centre ' : 'Centre to centre ';
    var them = ea && eb ? 'edges' : ea || eb ? 'edge and the axis' : 'axes';
    if (ang <= PARALLEL_DEG) {
      c1 = onLine(a.p, a.o, a.d);
      c2 = onLine(c1, b.o, b.d);
      var v = sub(c2, c1), dist = len(v);
      var lines = dist < 1e-6 ? [what + '0.00 mm', ea && eb ? 'On one line' : 'On one axis'] : [what + mm(dist)];
      if (ang > 0.05) lines.push('(' + them + ' parallel within ' + angleText(ang) + ')');
      return { type: ea || eb ? 'edges' : 'axes', dist: dist, angle: ang, from: c1, to: c2, vec: v, lines: lines };
    }
    var w = cross(a.d, b.d), wl = len(w), r = sub(b.o, a.o);
    var t1 = dot(cross(r, b.d), w) / (wl * wl), t2 = dot(cross(r, a.d), w) / (wl * wl);
    c1 = add(a.o, mul(a.d, t1));
    c2 = add(b.o, mul(b.d, t2));
    var v2 = sub(c2, c1), d2 = len(v2);
    return { type: ea || eb ? 'edges' : 'axes', dist: d2, angle: ang, from: c1, to: c2, vec: v2,
             lines: [(d2 < 1e-6 ? 'The ' + them + ' cross' : 'Shortest between the ' + them + ' ' + mm(d2)),
                     'Angle between the ' + them + ' ' + angleText(ang)] };
  }

  function faceAxis(f, r) {        // f flat, r round / axis / straight edge
    var s = Math.abs(dot(f.n, r.d)), edge = r.kind === 'line', it = edge ? 'edge' : 'axis';
    var ang = deg(Math.asin(Math.min(1, s)));              // 0: the axis lies along the face
    if (ang <= PARALLEL_DEG) {
      var c = onLine(r.p, r.o, r.d), foot = onPlane(c, f.p, f.n), v = sub(c, foot), dist = Math.abs(dot(sub(c, f.p), f.n));
      var lines = [(edge ? 'Face to edge ' : 'Face to centre ') + mm(dist)];
      if (ang > 0.05) lines.push('(' + it + ' along the face within ' + angleText(ang) + ')');
      return { type: edge ? 'face-edge' : 'face-axis', dist: dist, angle: ang, from: foot, to: c, vec: v, lines: lines };
    }
    // the axis goes through the face's plane: where, and at what angle
    var t = dot(sub(f.p, r.o), f.n) / dot(r.d, f.n), x = add(r.o, mul(r.d, t)), v2 = sub(x, f.p);
    return { type: edge ? 'face-edge' : 'face-axis', dist: 0, angle: ang, from: f.p, to: x, vec: v2,
             lines: ['The ' + it + ' meets the face at ' + angleText(ang), 'Click to crossing ' + mm(len(v2))] };
  }

  // a round edge (task 0219): from its centre to the other pick
  function fromCircle(c, o) {
    var at = c.o, to, what, lines;
    if (o.kind === 'circle') {
      var v = sub(o.o, at), d = len(v);
      lines = ['Centre to centre ' + mm(d)];
      if (lineAngle(c.d, o.d) <= PARALLEL_DEG && d > 1e-9) {
        var along = Math.abs(dot(v, c.d)), across = Math.sqrt(Math.max(0, d * d - along * along));
        if (along > 1e-6 && across > 1e-6) lines.push('Across the axes ' + mm(across) + ' · along ' + mm(along));
        else if (along <= 1e-6) lines.push('In one plane');
        else lines.push('On one axis');
      }
      return { type: 'circles', dist: d, from: at, to: o.o, vec: v, lines: lines };
    }
    if (o.kind === 'flat') {
      to = onPlane(at, o.p, o.n); what = 'Centre to face ';
    } else if (isRound(o) || o.kind === 'line') {
      to = onLine(at, o.o, o.d); what = o.kind === 'line' ? 'Centre to edge ' : 'Centre to axis ';
    } else {
      to = o.p; what = 'Centre to point ';
    }
    var w = sub(to, at), dist = len(w);
    lines = [what + mm(dist)];
    if ((isRound(o) || o.kind === 'line') && lineAngle(c.d, o.d) > PARALLEL_DEG) {
      lines.push('Angle between the axes ' + angleText(lineAngle(c.d, o.d)));
    }
    return { type: 'circle-' + (o.kind === 'round' || o.kind === 'axis' ? 'axis' : o.kind === 'line' ? 'edge' : o.kind === 'flat' ? 'face' : 'point'),
             dist: dist, from: at, to: to, vec: w, lines: lines };
  }
  function pointLine(pt, l) {      // a point to a straight edge
    var f = onLine(pt.p, l.o, l.d), v = sub(pt.p, f);
    return { type: 'point-edge', dist: len(v), from: f, to: pt.p, vec: v, lines: ['Point to edge ' + mm(len(v))] };
  }

  function isRound(k) { return k.kind === 'round' || k.kind === 'axis'; }
  function isLine(k) { return isRound(k) || k.kind === 'line'; }

  function measure(a, b, mode) {
    if (mode !== 'points') {
      if (a.kind === 'circle') return fromCircle(a, b);
      if (b.kind === 'circle') return flip(fromCircle(b, a));
      if (a.kind === 'flat' && b.kind === 'flat') return planes(a, b);
      if (isLine(a) && isLine(b)) return axes(a, b);
      if (a.kind === 'flat' && isLine(b)) return faceAxis(a, b);
      if (isLine(a) && b.kind === 'flat') return flip(faceAxis(b, a));
      if (a.kind === 'line') return flip(pointLine(b, a));
      if (b.kind === 'line') return pointLine(a, b);
    }
    return points(a, b);
  }
  function flip(r) { var f = r.from; r.from = r.to; r.to = f; r.vec = mul(r.vec, -1); return r; }

  // one click: what the face itself says
  function single(a) {
    if (a.kind === 'round' && a.r > 0) return { type: 'diameter', dist: 2 * a.r, lines: ['Ø ' + mm(2 * a.r) + '  (radius ' + mm(a.r) + ')'] };
    if (a.kind === 'axis') return { type: 'axis', lines: ['Round face (no single diameter: a cone or a rounded edge)'] };
    if (a.kind === 'flat') return { type: 'flat', lines: ['Flat face'] };
    if (a.kind === 'line') return { type: 'edge', dist: a.len, lines: ['Straight edge, ' + mm(a.len) + ' long'] };
    if (a.kind === 'circle') {
      var whole = a.sweep >= 2 * Math.PI - 1e-3;
      return { type: 'diameter', dist: 2 * a.r, lines: ['Ø ' + mm(2 * a.r) + '  (radius ' + mm(a.r) + ')',
                                                        whole ? 'Round edge (a whole circle)' : 'Round edge, an arc of ' + angleText(deg(a.sweep))] };
    }
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

  // ---------------------------------------------------------------- edges (task 0219)
  // an EDGE RECORD of the file's face data (core/web3d_faces.py: kind, row a, row b, 6 or 9 numbers) in the mesh's
  // written coordinates -> a pick in the model's coordinates; the clicked point ``p`` is put on the edge
  function fromEdge(row, m, p) {
    function pt(v) { return [m[0] * v[0] + m[4] * v[1] + m[8] * v[2] + m[12], m[1] * v[0] + m[5] * v[1] + m[9] * v[2] + m[13],
                             m[2] * v[0] + m[6] * v[1] + m[10] * v[2] + m[14]]; }
    function dir(v) { return [m[0] * v[0] + m[4] * v[1] + m[8] * v[2], m[1] * v[0] + m[5] * v[1] + m[9] * v[2],
                              m[2] * v[0] + m[6] * v[1] + m[10] * v[2]]; }
    var kind = Math.round(row[0]);
    if (kind === 4) {
      var a = pt([row[3], row[4], row[5]]), b = pt([row[6], row[7], row[8]]), ab = sub(b, a), l = len(ab), d = unit(ab);
      var t = Math.max(0, Math.min(l, dot(sub(p, a), d)));
      return { kind: 'line', p: add(a, mul(d, t)), o: a, d: d, a: a, b: b, len: l };
    }
    if (kind === 5) {
      var c = pt([row[3], row[4], row[5]]), s = pt([row[6], row[7], row[8]]), k = [row[9], row[10], row[11]];
      var sweep = len(k), n = unit(dir(k)), r = len(sub(s, c));
      if (dot(cross(dir([1, 0, 0]), dir([0, 1, 0])), dir([0, 0, 1])) < 0) n = mul(n, -1);   // a mirrored part
      return { kind: 'circle', p: onCircle(p, c, n, r), o: c, c: c, d: n, r: r, s: s, sweep: sweep };
    }
    return null;
  }
  function onCircle(p, c, n, r) {                      // the point of the circle nearest p
    var w = sub(p, c), q = sub(w, mul(n, dot(w, n))), l = len(q);
    if (l < 1e-12) q = frame(n).e1, l = 1;
    return add(c, mul(q, r / l));
  }
  // the points to draw an edge pick (model coordinates): a line's two ends, an arc as a polyline
  function edgePoints(k, segs) {
    if (k.kind === 'line') return [k.a, k.b];
    if (k.kind !== 'circle') return [];
    var n = Math.max(2, Math.ceil((segs || 64) * k.sweep / (2 * Math.PI))), out = [], u = sub(k.s, k.c);
    for (var i = 0; i <= n; i++) out.push(add(k.c, rot(u, k.d, deg(k.sweep * i / n))));
    return out;
  }
  // how far (m) a point is from an edge pick, and the nearest point on it
  function nearEdge(k, p) {
    var q;
    if (k.kind === 'line') {
      var t = Math.max(0, Math.min(k.len, dot(sub(p, k.a), k.d)));
      q = add(k.a, mul(k.d, t));
    } else {
      q = onCircle(p, k.c, k.d, k.r);
      if (k.sweep < 2 * Math.PI - 1e-3) {              // outside the arc: its nearer end
        var u = unit(sub(k.s, k.c)), v = cross(k.d, u), w = sub(q, k.c);
        var ang = Math.atan2(dot(w, v), dot(w, u));
        if (ang < 0) ang += 2 * Math.PI;
        if (ang > k.sweep) {
          var e = add(k.c, rot(sub(k.s, k.c), k.d, deg(k.sweep)));
          q = len(sub(p, k.s)) < len(sub(p, e)) ? k.s : e;
        }
      }
    }
    return { dist: len(sub(p, q)), q: q };
  }

  // ---------------------------------------------------------------- labels apart (task 0219)
  // Screen boxes (CSS pixels) placed so that none covers another. ``boxes``: [{x, y, w, h}] – x, y where the label
  // belongs (its centre), most important first (it stays where it belongs when it can); ``fixed``: [{x, y, w, h}]
  // that must stay uncovered too (the dots of the clicked points). -> [{x, y, moved}] the centres to draw at;
  // ``moved``: far enough from where it belongs to draw a short leader line to it.
  var GAP = 3;
  function overlaps(a, b, gap) {
    return Math.abs(a.x - b.x) * 2 < a.w + b.w + 2 * gap && Math.abs(a.y - b.y) * 2 < a.h + b.h + 2 * gap;
  }
  function overlapArea(a, b) {
    var ox = Math.max(0, (a.w + b.w) / 2 - Math.abs(a.x - b.x)), oy = Math.max(0, (a.h + b.h) / 2 - Math.abs(a.y - b.y));
    return ox * oy;
  }
  function layout(boxes, fixed, gap) {
    gap = gap == null ? GAP : gap;
    var placed = (fixed || []).map(function (f) { return { x: f.x, y: f.y, w: f.w, h: f.h }; }), out = [];
    boxes.forEach(function (b) {
      var sy = (b.h + gap) / 2, sx = (b.w + gap) / 4, best = null, bestCost = Infinity;
      var tries = [[0, 0]];
      for (var k = 1; k <= 14; k++) {
        tries.push([0, -k * sy], [0, k * sy], [k * sx, -k * sy], [-k * sx, -k * sy], [k * sx, k * sy],
                   [-k * sx, k * sy], [2 * k * sx, 0], [-2 * k * sx, 0]);
      }
      for (var i = 0; i < tries.length; i++) {
        var c = { x: b.x + tries[i][0], y: b.y + tries[i][1], w: b.w, h: b.h }, free = true, cost = 0;
        for (var j = 0; j < placed.length; j++) {
          if (overlaps(c, placed[j], gap)) { free = false; cost += overlapArea(c, placed[j]) + 1; }
        }
        if (free) { best = c; break; }
        if (cost < bestCost) { bestCost = cost; best = c; }
      }
      placed.push(best);
      var dx = best.x - b.x, dy = best.y - b.y;
      out.push({ x: best.x, y: best.y, moved: Math.abs(dx) > b.w / 2 || Math.abs(dy) > b.h / 2 });
    });
    return out;
  }
  // a leader line from a moved label's box (centre x, y, size w, h) to the point it belongs to: [x1, y1, x2, y2]
  // (from the box's edge, so it does not cross its text)
  function leader(box, at) {
    var dx = at.x - box.x, dy = at.y - box.y, hw = box.w / 2, hh = box.h / 2;
    var s = Math.min(dx ? hw / Math.abs(dx) : Infinity, dy ? hh / Math.abs(dy) : Infinity, 1);
    return [box.x + dx * s, box.y + dy * s, at.x, at.y];
  }

  // ---------------------------------------------------------------- slices (task 0218)
  // A slice: {o: the point it turns about, n0, e1, e2: its first frame (n0 points into the KEPT side, e1 x e2 = n0),
  //           a, b: turns in degrees about e1, then about the turned e2, t: moved along its normal (m), flip}
  // plane(s) -> {n, q, e1, e2}: what is kept is every point x with (x - q) . n >= 0
  var FACE_EPS = 2e-5;      // a slice in a clicked face lies 0.02 mm in front of it: the face itself stays whole

  function rot(v, k, deg_) {                           // v turned about the unit axis k (Rodrigues)
    var a = deg_ * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)));
  }
  function frame(n) {                                  // e1 level where it can be, e1 x e2 = n
    n = unit(n);
    var e1 = cross([0, 0, 1], n);
    if (len(e1) < 1e-6) e1 = [1, 0, 0];
    e1 = unit(e1);
    return { n0: n, e1: e1, e2: cross(n, e1) };
  }
  function make(o, n, eps) {
    var f = frame(n);
    return { o: eps ? sub(o, mul(f.n0, eps)) : o.slice(), n0: f.n0, e1: f.e1, e2: f.e2, a: 0, b: 0, t: 0, flip: false };
  }
  // a slice from a click: view = the direction the camera looks (model coordinates). The side away from the camera
  // stays (the near side is cut away, so the cut is seen); Flip keeps the other side.
  //   flat face: in the face's plane;  round face / axis: through the axis, square to the view;  a point: across the
  //   triangle's own normal ``tri`` (a page without face data)
  function sliceFromPick(pick, view, tri) {
    view = unit(view);
    if (pick.kind === 'round' || pick.kind === 'axis') {
      var d = unit(pick.d), w = sub(view, mul(d, dot(view, d)));
      if (len(w) < 1e-6) w = frame(d).e1;              // looking along the axis: any plane through it
      return make(onLine(pick.p, pick.o, d), w, 0);
    }
    var n = pick.kind === 'flat' ? pick.n : tri;
    if (!n || len(n) < 1e-9) n = view;
    n = unit(n);
    if (dot(n, view) < 0) n = mul(n, -1);              // into the part, away from the camera
    return make(pick.p, n, FACE_EPS);
  }
  // across X, Y or Z through ``at`` (a point), keeping the side away from the camera
  function sliceAcross(axis, at, view) {
    var i = { X: 0, Y: 1, Z: 2 }[axis], n = [0, 0, 0];
    n[i] = (view && view[i] < 0) ? -1 : 1;
    return make(at, n, 0);
  }
  function plane(s) {
    var n = rot(s.n0, s.e1, s.a || 0), e2 = rot(s.e2, s.e1, s.a || 0);
    var e1 = rot(s.e1, e2, s.b || 0);
    n = unit(rot(n, e2, s.b || 0));
    var q = add(s.o, mul(n, s.t || 0));
    return { n: s.flip ? mul(n, -1) : n, q: q, e1: e1, e2: e2 };
  }
  // what every plane keeps (a point exactly on a plane is kept)
  function kept(planes, p, eps) {
    for (var i = 0; i < planes.length; i++) if (dot(sub(p, planes[i].q), planes[i].n) < -(eps || 1e-9)) return false;
    return true;
  }
  // where a ray (from, dir) enters what all planes keep, before ``maxT``: the cut face it sees there.
  // -> {i: the plane, t, p} or null
  function capAt(planes, from, dir, maxT) {
    var best = null;
    for (var i = 0; i < planes.length; i++) {
      var dn = dot(dir, planes[i].n);
      if (dn <= 1e-12) continue;                        // leaves the kept side or runs along the plane
      var t = dot(sub(planes[i].q, from), planes[i].n) / dn;
      if (t > maxT + 1e-9) continue;
      if (!best || t > best.t) best = { i: i, t: t };
    }
    if (!best) return null;
    best.p = add(from, mul(dir, best.t));
    return kept(planes, best.p, 1e-7) ? best : null;
  }
  // how far a slice can move (m): from the box's nearest corner to its farthest, along the turned normal
  function moveRange(s, lo, hi) {
    var p = plane(Object.assign({}, s, { t: 0, flip: false })), a = Infinity, b = -Infinity;
    for (var k = 0; k < 8; k++) {
      var c = [k & 1 ? hi[0] : lo[0], k & 2 ? hi[1] : lo[1], k & 4 ? hi[2] : lo[2]], d = dot(sub(c, p.q), p.n);
      a = Math.min(a, d); b = Math.max(b, d);
    }
    return [a, b];
  }
  var slice = { fromPick: sliceFromPick, across: sliceAcross, plane: plane, kept: kept, capAt: capAt,
                moveRange: moveRange, frame: frame, FACE_EPS: FACE_EPS };

  return { measure: measure, single: single, parts: parts, fromRow: fromRow, mm: mm, angleText: angleText,
           PARALLEL_DEG: PARALLEL_DEG, lineAngle: lineAngle, slice: slice,
           fromEdge: fromEdge, edgePoints: edgePoints, nearEdge: nearEdge, layout: layout, leader: leader,
           overlaps: overlaps };
})();
if (typeof module !== 'undefined') module.exports = FRMeasure;
