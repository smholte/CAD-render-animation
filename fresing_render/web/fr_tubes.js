// Fresing Render web 3D page: moving cables, ropes, hoses and the rope on a spool (task 0142).
//
// A part the app draws as a tube carries extras.fr_tube in the file (core/web3d_tubes.py, blender/web3d_drawn.py):
// its centre line at a few kept moments (16-bit per point, each point its own range), the first ring's turn and the
// length along the cable at each moment, the metres paid out (the cable look's offset) and, for a spool, the cut it
// shows. FRTubes.make(spec, arrays) gives an object whose at(t) works out, for the time t (s), every ring's centre,
// length along the cable, turn (normal) and direction (tangent) – the same as core.web3d_tubes.at in Python, which the
// tests compare with the app. fr_page.js writes them into a small float texture; the tube's vertex shader builds the
// rings from it. Plain JavaScript, no three.js: node runs this file in the tests.
(function (root) {
  'use strict';

  // the moment pair around t: [k, k + 1, w]; held before the first and after the last
  function seek(times, t) {
    var n = times ? times.length : 0;
    if (n < 2 || t <= times[0]) return [0, 0, 0];
    if (t >= times[n - 1]) return [n - 1, n - 1, 0];
    var lo = 0, hi = n - 1;
    while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (times[mid] <= t) lo = mid; else hi = mid; }
    var span = times[hi] - times[lo];
    return [lo, hi, span > 0 ? (t - times[lo]) / span : 0];
  }

  // a channel: a number or numbers per kept moment, blended; ``dim`` numbers each
  function channel(times, values, dim, t, out) {
    var s = seek(times, t), a = s[0] * dim, b = s[1] * dim, w = s[2];
    for (var c = 0; c < dim; c++) out[c] = values[a + c] * (1 - w) + values[b + c] * w;
    return out;
  }

  function unit(v, i) {
    var l = Math.sqrt(v[i] * v[i] + v[i + 1] * v[i + 1] + v[i + 2] * v[i + 2]);
    if (l > 1e-300) { v[i] /= l; v[i + 1] /= l; v[i + 2] /= l; }
    return l;
  }

  // octahedral int16 -> unit vector
  function octDecode(x, y, out, i) {
    x /= 32767; y /= 32767;
    var z = 1 - Math.abs(x) - Math.abs(y), t = Math.max(-z, 0);
    x += x >= 0 ? -t : t; y += y >= 0 ? -t : t;
    out[i] = x; out[i + 1] = y; out[i + 2] = z;
    unit(out, i);
  }

  function Tube(spec, a) {
    this.spec = spec;
    this.a = a;
    this.n = spec.n | 0;
    this.k = spec.k | 0 || 1;
    this.rings = this.n + 2;                 // the geometry's rings: a copy of the first and the last at the ends
    this.unit = +spec.unit || 1;
    this.tmin = +spec.tmin || 0;
    var m = this.n;
    this.p = new Float64Array(m * 3);        // the line now (before a spool's cut)
    this.s = new Float64Array(m);
    this.cp = new Float64Array((m + 2) * 3); // after the cut
    this.cs = new Float64Array(m + 2);
    this.tg = new Float64Array((m + 2) * 3);
    this.nr = new Float64Array((m + 2) * 3);
    this.count = 0;
    this.pay = 0;
    // texels for the shader: per ring [x, y, z, s], [normal, 0], [tangent, 0]
    this.data = new Float32Array(this.rings * 12);
    this.moves = this.k > 1 || !!a.trim_t || !!a.pay_t;
    var ends = [];
    ['times', 'pay_t', 'trim_t'].forEach(function (key) { if (a[key] && a[key].length) ends.push(a[key][a[key].length - 1]); });
    this.duration = ends.length ? Math.max.apply(null, ends) : 0;
  }

  Tube.prototype.at = function (t) {
    var a = this.a, n = this.n, k = this.k, i, c, j;
    var sk = seek(k > 1 ? a.times : null, t), ka = sk[0], kb = sk[1], w = sk[2];
    var p = this.p, s = this.s;
    for (i = 0; i < n; i++) {
      for (c = 0; c < 3; c++) {
        var v = a.lo[i * 3 + c];
        if (k > 1 && a.step[i] > 0) {
          var qa = a.q[(i * k + ka) * 3 + c], qb = a.q[(i * k + kb) * 3 + c];
          v += a.step[i] * (qa * (1 - w) + qb * w);
        }
        p[i * 3 + c] = v;
      }
    }
    var n0 = [0, 0, 0];
    channel(k > 1 ? a.times : null, a.n0, 3, t, n0);
    var s0 = channel(k > 1 ? a.times : null, a.s0, 1, t, [0])[0];
    if (a.s) {
      for (i = 0; i < n; i++) s[i] = a.s[i];
    } else if (a.slo) {
      for (i = 0; i < n; i++) {
        var sv = a.slo[i];
        if (k > 1 && a.sq && a.sstep[i] > 0) sv += a.sstep[i] * (a.sq[i * k + ka] * (1 - w) + a.sq[i * k + kb] * w);
        s[i] = sv;
      }
    } else {
      s[0] = s0;
      for (i = 1; i < n; i++) {
        var dx = p[i * 3] - p[i * 3 - 3], dy = p[i * 3 + 1] - p[i * 3 - 2], dz = p[i * 3 + 2] - p[i * 3 - 1];
        s[i] = s[i - 1] + Math.sqrt(dx * dx + dy * dy + dz * dz) * this.unit;
      }
    }
    // a spool shows a cut of its wound path: points before lo dropped, the first past hi moved back onto hi
    var cp = this.cp, cs = this.cs, m = 0;
    if (a.trim) {
      var tr = channel(a.trim_t || null, a.trim, 2, t, [0, 0]), lo = tr[0], hi = tr[1];
      if (a.trim_n0) channel(a.trim_t || null, a.trim_n0, 3, t, n0);
      for (i = 0; i < n; i++) {
        var prev = s[i > 0 ? i - 1 : 0];
        if (s[i] < lo || prev > hi) continue;
        if (s[i] > hi) {
          j = i > 0 ? i - 1 : 0;
          var ln = s[i] - s[j], ww = ln <= 1e-9 ? 0 : Math.min(1, Math.max(0, (hi - s[j]) / ln));
          for (c = 0; c < 3; c++) cp[m * 3 + c] = p[j * 3 + c] * (1 - ww) + p[i * 3 + c] * ww;
          cs[m] = hi;
        } else {
          for (c = 0; c < 3; c++) cp[m * 3 + c] = p[i * 3 + c];
          cs[m] = s[i];
        }
        m++;
      }
    } else {
      for (i = 0; i < n * 3; i++) cp[i] = p[i];
      for (i = 0; i < n; i++) cs[i] = s[i];
      m = n;
    }
    this.count = m;
    this._tangents(m);
    this._normals(m, n0, ka, kb, w);
    this.pay = a.pay ? channel(a.pay_t || null, a.pay, 1, t, [0])[0] : (+this.spec.pay || 0);
    return this;
  };

  // Blender's poly-curve rule: the sum of the unit pieces on both sides; with tmin, pieces are looked past until
  // they add up to tmin on each side (16-bit points: a piece a fraction of a millimetre long has a noisy direction)
  Tube.prototype._tangents = function (m) {
    var p = this.cp, tg = this.tg, tmin = this.tmin, i, c;
    var cum = this._cum || (this._cum = new Float64Array(this.n + 2));
    cum[0] = 0;
    for (i = 1; i < m; i++) {
      var ex = p[i * 3] - p[i * 3 - 3], ey = p[i * 3 + 1] - p[i * 3 - 2], ez = p[i * 3 + 2] - p[i * 3 - 1];
      cum[i] = cum[i - 1] + Math.sqrt(ex * ex + ey * ey + ez * ez);
    }
    var back = 0, ahead = 0;
    for (i = 0; i < m; i++) {
      var d = [0, 0, 0], j, k, l;
      if (tmin > 0) {
        while (back + 1 < m && cum[back + 1] <= cum[i] - tmin) back++;   // the last point at least tmin behind
        j = back;
        if (ahead < i) ahead = i;
        while (ahead < m - 1 && cum[ahead] < cum[i] + tmin) ahead++;     // the first point at least tmin ahead
        k = ahead;
      } else { j = i > 0 ? i - 1 : 0; k = i < m - 1 ? i + 1 : m - 1; }
      if (j !== i) {
        l = Math.sqrt(Math.pow(p[i * 3] - p[j * 3], 2) + Math.pow(p[i * 3 + 1] - p[j * 3 + 1], 2) + Math.pow(p[i * 3 + 2] - p[j * 3 + 2], 2));
        if (l > 1e-12) for (c = 0; c < 3; c++) d[c] += (p[i * 3 + c] - p[j * 3 + c]) / l;
      }
      if (k !== i) {
        l = Math.sqrt(Math.pow(p[k * 3] - p[i * 3], 2) + Math.pow(p[k * 3 + 1] - p[i * 3 + 1], 2) + Math.pow(p[k * 3 + 2] - p[i * 3 + 2], 2));
        if (l > 1e-12) for (c = 0; c < 3; c++) d[c] += (p[k * 3 + c] - p[i * 3 + c]) / l;
      }
      tg[i * 3] = d[0]; tg[i * 3 + 1] = d[1]; tg[i * 3 + 2] = d[2];
    }
    // a point on pieces of length 0: the nearest direction
    var lastGood = -1;
    for (i = 0; i < m; i++) {
      if (unit(tg, i * 3) > 1e-12) { lastGood = i; continue; }
      tg[i * 3] = NaN;
    }
    if (lastGood < 0) { for (i = 0; i < m; i++) { tg[i * 3] = 0; tg[i * 3 + 1] = 0; tg[i * 3 + 2] = 1; } return; }
    for (i = 0; i < m; i++) {
      if (tg[i * 3] === tg[i * 3]) continue;
      var nb = -1;
      for (var r = 1; r < m && nb < 0; r++) {
        if (i + r < m && tg[(i + r) * 3] === tg[(i + r) * 3]) nb = i + r;
        else if (i - r >= 0 && tg[(i - r) * 3] === tg[(i - r) * 3]) nb = i - r;
      }
      for (c = 0; c < 3; c++) tg[i * 3 + c] = tg[nb * 3 + c];
    }
  };

  // the ring's turn: the app's own per point (nq), else carried from the first by the smallest turn (minimum twist)
  Tube.prototype._normals = function (m, n0, ka, kb, w) {
    var tg = this.tg, nr = this.nr, a = this.a, i, c, k = this.k;
    if (a.nq && !a.trim) {
      var na = [0, 0, 0], nb = [0, 0, 0];
      for (i = 0; i < m; i++) {
        octDecode(a.nq[(i * k + ka) * 2], a.nq[(i * k + ka) * 2 + 1], na, 0);
        octDecode(a.nq[(i * k + kb) * 2], a.nq[(i * k + kb) * 2 + 1], nb, 0);
        for (c = 0; c < 3; c++) nr[i * 3 + c] = na[c] * (1 - w) + nb[c] * w;
        orth(nr, tg, i * 3);
      }
      return;
    }
    var v = [n0[0], n0[1], n0[2]];
    var tmp = new Float64Array(3);
    tmp[0] = v[0]; tmp[1] = v[1]; tmp[2] = v[2];
    for (i = 0; i < m; i++) {
      if (i > 0) rotate(tmp, tg, (i - 1) * 3, i * 3);
      orth(tmp, tg, 0, i * 3);
      nr[i * 3] = tmp[0]; nr[i * 3 + 1] = tmp[1]; nr[i * 3 + 2] = tmp[2];
    }
  };

  // v (at vi) made square to tg (at ti, default vi) and unit
  function orth(v, tg, vi, ti) {
    if (ti === undefined) ti = vi;
    var d = v[vi] * tg[ti] + v[vi + 1] * tg[ti + 1] + v[vi + 2] * tg[ti + 2];
    v[vi] -= d * tg[ti]; v[vi + 1] -= d * tg[ti + 1]; v[vi + 2] -= d * tg[ti + 2];
    unit(v, vi);
  }

  // v turned by the smallest turn taking the unit tangent at ia to the one at ib (Rodrigues)
  function rotate(v, tg, ia, ib) {
    var ax = tg[ia + 1] * tg[ib + 2] - tg[ia + 2] * tg[ib + 1];
    var ay = tg[ia + 2] * tg[ib] - tg[ia] * tg[ib + 2];
    var az = tg[ia] * tg[ib + 1] - tg[ia + 1] * tg[ib];
    var sn = Math.sqrt(ax * ax + ay * ay + az * az);
    if (sn < 1e-12) return;
    var cs = Math.max(-1, Math.min(1, tg[ia] * tg[ib] + tg[ia + 1] * tg[ib + 1] + tg[ia + 2] * tg[ib + 2]));
    ax /= sn; ay /= sn; az /= sn;
    var ang = Math.atan2(sn, cs), co = Math.cos(ang), si = Math.sin(ang);
    var kv = ax * v[0] + ay * v[1] + az * v[2];
    var cx = ay * v[2] - az * v[1], cy = az * v[0] - ax * v[2], cz = ax * v[1] - ay * v[0];
    v[0] = v[0] * co + cx * si + ax * kv * (1 - co);
    v[1] = v[1] * co + cy * si + ay * kv * (1 - co);
    v[2] = v[2] * co + cz * si + az * kv * (1 - co);
  }

  // the rings for the shader: ring 0 = the first point, rings 1 … count = the points, the rest = the last point
  Tube.prototype.fill = function () {
    var d = this.data, m = this.count, r, src;
    for (r = 0; r < this.rings; r++) {
      src = r === 0 ? 0 : Math.min(r - 1, m - 1);
      var o = r * 12;
      d[o] = this.cp[src * 3]; d[o + 1] = this.cp[src * 3 + 1]; d[o + 2] = this.cp[src * 3 + 2]; d[o + 3] = this.cs[src];
      d[o + 4] = this.nr[src * 3]; d[o + 5] = this.nr[src * 3 + 1]; d[o + 6] = this.nr[src * 3 + 2]; d[o + 7] = 0;
      d[o + 8] = this.tg[src * 3]; d[o + 9] = this.tg[src * 3 + 1]; d[o + 10] = this.tg[src * 3 + 2]; d[o + 11] = 0;
    }
    return d;
  };

  // the ring positions at the angle of side j (of ``sides``) – tests (B = tangent x normal, as Blender's rings)
  Tube.prototype.ringPoint = function (i, j) {
    var sides = this.spec.sides, r = this.spec.r, ph = 2 * Math.PI * j / sides, co = Math.cos(ph), si = Math.sin(ph);
    var P = this.cp, N = this.nr, T = this.tg, o = i * 3;
    var bx = T[o + 1] * N[o + 2] - T[o + 2] * N[o + 1], by = T[o + 2] * N[o] - T[o] * N[o + 2], bz = T[o] * N[o + 1] - T[o + 1] * N[o];
    return [P[o] + r * (co * N[o] + si * bx), P[o + 1] + r * (co * N[o + 1] + si * by), P[o + 2] + r * (co * N[o + 2] + si * bz)];
  };

  var FRTubes = {
    KEYS: ['times', 'lo', 'step', 'q', 'n0', 's0', 'pay_t', 'pay', 'trim_t', 'trim', 'trim_n0', 's', 'slo', 'sstep', 'sq', 'nq'],
    make: function (spec, arrays) { return new Tube(spec, arrays); },
    seek: seek
  };
  root.FRTubes = FRTubes;
  if (typeof module !== 'undefined' && module.exports) module.exports = FRTubes;
})(typeof window !== 'undefined' ? window : globalThis);
