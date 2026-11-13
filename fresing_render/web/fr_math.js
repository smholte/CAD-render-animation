// Fresing Render web 3D page with surroundings (task 0106): the sea's height and the vessel's motion, the same
// formulas and numbers as the app (blender/surroundings.py _waves_group, core/vessel_motion.py). Plain functions
// on Blender's world coordinates (metres, z up); the page turns them into three.js's (x, z, -y). Also loaded by
// node in tests/test_web3d_env.py, which compares it with the Python side.
var FRMath = (function () {
  'use strict';
  var G = 9.81;

  function smoothstep01(x) {             // Blender's Map Range SMOOTHSTEP between 0 and 1
    x = Math.min(1, Math.max(0, x));
    return x * x * (3 - 2 * x);
  }

  // fade of the waves: 1 inside `near`, 0 beyond 1.6 near (the app's Map Range from near..1.6 near to 1..0)
  function fade(sea, x, y) {
    var r = Math.sqrt(x * x + y * y);
    return 1 - smoothstep01((r - sea.near) / (0.6 * sea.near));
  }

  // height of the water above sea.level at (x, y) metres from the sea's origin, at time t (s)
  function seaHeight(sea, x, y, t) {
    var h = 0;
    for (var i = 0; i < sea.waves.length; i++) {
      var w = sea.waves[i];               // [amp, dx, dy, k, phase]
      var omega = Math.sqrt(G * w[3]);
      h += w[0] * Math.sin(w[3] * (w[1] * x + w[2] * y) + w[4] - omega * t);
    }
    return h * fade(sea, x, y);
  }

  // the sea's own waves only, as a share of their summed amplitude (the app's "fr_crest": foam on the tops)
  function crest(sea, x, y, t) {
    var h = 0, s = 0;
    for (var i = 0; i < sea.own; i++) {
      var w = sea.waves[i];
      h += w[0] * Math.sin(w[3] * (w[1] * x + w[2] * y) + w[4] - Math.sqrt(G * w[3]) * t);
      s += w[0];
    }
    return h * fade(sea, x, y) / Math.max(s, 1e-3);
  }

  // one channel of the vessel's motion: [base, [[amp, omega, phase], ...]] -> base + sum amp sin(phase - omega t)
  function channel(ch, t) {
    var v = ch[0], terms = ch[1];
    for (var i = 0; i < terms.length; i++) v += terms[i][0] * Math.sin(terms[i][2] - terms[i][1] * t);
    return v;
  }

  // 4x4 matrix (column-major, Blender world) of the vessel's motion: T(p + heave z) Ry(pitch) Rx(roll) T(-p).
  // mode 'LEVEL': only the heave (a part that stays level); 'STILL': identity.
  function vesselMatrix(v, t, mode) {
    var p = v.pivot;
    var heave = channel(v.heave, t);                 // metres up (the app's rig adds the pivot's height)
    if (mode === 'STILL') return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
    if (mode === 'LEVEL') return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, heave, 1];
    var r = channel(v.roll, t), q = channel(v.pitch, t);
    var cr = Math.cos(r), sr = Math.sin(r), cq = Math.cos(q), sq = Math.sin(q);
    // R = Ry(q) Rx(r), rows:
    var R = [[cq, sq * sr, sq * cr],
             [0, cr, -sr],
             [-sq, cq * sr, cq * cr]];
    var tx = p[0] - (R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2]);
    var ty = p[1] - (R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2]);
    var tz = p[2] + heave - (R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2]);
    return [R[0][0], R[1][0], R[2][0], 0, R[0][1], R[1][1], R[2][1], 0, R[0][2], R[1][2], R[2][2], 0, tx, ty, tz, 1];
  }

  function apply(m, x, y, z) {
    return [m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13],
            m[2] * x + m[6] * y + m[10] * z + m[14]];
  }

  return { G: G, fade: fade, seaHeight: seaHeight, crest: crest, channel: channel, vesselMatrix: vesselMatrix,
           apply: apply };
})();
if (typeof module !== 'undefined') module.exports = FRMath;
