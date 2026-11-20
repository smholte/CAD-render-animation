// Fresing Render web 3D player: the part tools (task 0135). A column of four buttons on the left of the 3D view:
//
//   Part info (I)        click a part: a card at it with its label or name (pages exported with Hide part names: the
//                        part's material group, never its name) and what the clicked face is (flat, round Ø …)
//   Measure (D)          two clicks. Faces (default): two flat faces – the distance between the planes (parallel
//                        within 1°) or the angle between them; two round faces – centre to centre (between the
//                        axes); a flat and a round face – from the plane to the axis; one round face – its
//                        diameter. Task 0219: near a CAD edge the pointer picks the EDGE (it lights up as a line):
//                        a straight edge measures like an axis, a round edge (a hole's rim, a rounding) by its centre
//                        and shows its Ø (fr_measure.js says which pair gives what). Points: the straight distance
//                        between the two clicked points. X / Y / Z parts (X): every measurement also as three arrows
//                        in the axis colours, each with its own number. The numbers never cover each other: a label
//                        that would is moved aside with a short line to where it belongs (FRMeasure.layout)
//   Slice (C)            task 0218 (was Cutaway): Add slice, then click a face (flat: in its plane; round: through
//                        its axis, square to the view) or choose X / Y / Z. The side away from the camera stays, Flip
//                        keeps the other side. Up to 8 slices at once, numbered and listed with Edit, Hide / Show and
//                        Delete; all of them cut together. Editing shows the plane with handles: the arrow moves it,
//                        the two yellow knobs turn it about two axes in its plane (or type mm and degrees). The cut
//                        faces show the app's cap colour. Only the model is cut (not the sea, the sky or the seabed);
//                        the planes move with the vessel. Clicks of the other tools go through the slices onto what
//                        is kept. (The key stays C: S is the player's screenshot.)
//   Fade the rest (T)    click a part: it stays solid, everything else goes see-through; click empty space or Esc
//
// Phone and tablet: tap = click; a long press (half a second) on a part shows its card whatever tool is on. A click
// is a press and release without a drag, so turning the view never picks a part. Hover (mouse) lights up the part,
// or the face under the pointer while measuring.
//
// Measurements use the file's face data (``extras.fr_faces``, core/web3d_faces.py): the exact plane of a flat face,
// the exact axis and radius of a round face. A page without it (exported without "Faces for measuring") measures
// between points. Clicked points stay on their parts: a measurement follows the animation.
//
// Reads and sets window.frPage (fr_page.js) and uses FRMeasure (fr_measure.js) for the numbers. For tests:
// frPage.partTools = {pickAt(x, y), screenOf(blender point), click(x, y), state(), …}.
(function () {
  'use strict';
  var page = window.frPage, M = window.FRMeasure, T = window.FRTHREE;
  if (!page || !page.listeners || !M || !T) return;
  var Q = new URLSearchParams(location.search);
  var root = document.documentElement;
  var CAP = 'vec3(0.80, 0.10, 0.10)';            // the app's cap colour (3 Looks > Cutaway: 0.62, 0.012, 0.012 linear)
  var AXIS_COLOUR = { X: '#E5484D', Y: '#46A758', Z: '#3E7BFA' };      // as Blender: X red, Y green, Z blue

  // the cut faces: a part's inside seen through the cut shows the cap colour (only materials with a cut plane; never
  // the shadow pass, the highlights or the faded parts)
  T.ShaderChunk.clipping_planes_fragment += '\n#if NUM_CLIPPING_PLANES > 0 && !defined(DEPTH_PACKING) && !defined(FR_NO_CAP)\n' +
    '  if ( ! gl_FrontFacing ) { gl_FragColor = vec4( ' + CAP + ', 1.0 ); return; }\n#endif\n';

  // ---------------------------------------------------------------- look
  var css = [
    // task 0179: under the header (--fr-head, measured by fr_player.js), out of the safe area, 40 px touch targets
    '#fr-parts { position: absolute; left: calc(12px + var(--sa-l, 0px)); top: var(--fr-head, 50px); z-index: 3; display: flex;',
    '  flex-direction: column; gap: 6px; }',
    '#fr-parts .fr-btn { padding: 0; width: 40px; height: 40px; }',
    '#fr-tpanel { position: absolute; left: calc(62px + var(--sa-l, 0px)); top: var(--fr-head, 50px); z-index: 4;',
    '  width: min(300px, calc(100vw - 140px)); max-height: calc(100% - var(--fr-head, 50px) - var(--fr-stack, 110px) - 8px);',
    '  overflow: auto; box-sizing: border-box;',
    '  background: rgba(20,28,34,.9); color: #F4F6F8; border-radius: 8px; padding: 10px 12px;',
    '  font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; box-shadow: 0 6px 24px rgba(0,0,0,.35); display: none; }',
    '#fr-tpanel h2 { font-size: 14px; margin: 0 0 6px; display: flex; justify-content: space-between; align-items: center; }',
    '#fr-tpanel h3 { font-size: 12px; margin: 10px 0 4px; color: #D5DBE0; font-weight: 600; text-transform: uppercase;',
    '  letter-spacing: .04em; }',
    '#fr-tpanel .fr-seg { display: flex; gap: 4px; }',
    '#fr-tpanel .fr-seg .fr-btn { flex: 1; min-height: 32px; padding: 0 6px; font-size: 12px; }',
    '#fr-tpanel label { display: flex; align-items: center; gap: 8px; min-height: 30px; cursor: pointer; }',
    '#fr-tpanel input[type=checkbox] { width: 18px; height: 18px; accent-color: #2F6A1B; }',
    '#fr-tpanel input[type=range] { width: 100%; accent-color: #F2A900; height: 28px; }',
    '#fr-tpanel .fr-hint { color: #D5DBE0; font-size: 12px; margin: 4px 0; }',
    '#fr-tpanel .fr-result { font-size: 15px; font-weight: 600; margin: 6px 0 2px; font-variant-numeric: tabular-nums; }',
    '#fr-tpanel .fr-result div + div { font-size: 12px; font-weight: 400; color: #D5DBE0; }',
    '#fr-tpanel .fr-x { background: transparent; border: 0; min-height: 28px; min-width: 28px; }',
    '#fr-marks { position: absolute; inset: 0; pointer-events: none; z-index: 2; overflow: hidden; }',
    '#fr-marks .fr-lbl { position: absolute; transform: translate(-50%, -50%); white-space: nowrap; padding: 2px 6px;',
    '  border-radius: 4px; background: rgba(20,28,34,.82); color: #fff; font: 600 12px "IBM Plex Sans", "Segoe UI",',
    '  system-ui, sans-serif; font-variant-numeric: tabular-nums; border-left: 3px solid #F2A900; }',
    '#fr-marks .fr-edges { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }',
    '#fr-marks .fr-edges path { fill: none; stroke-width: 3.5; stroke-linecap: round; stroke-linejoin: round;',
    '  filter: drop-shadow(0 0 1px rgba(0,0,0,.55)); }',
    '#fr-marks .fr-lead { position: absolute; height: 0; border-top: 1.5px solid rgba(255,255,255,.85);',
    '  transform-origin: 0 0; box-shadow: 0 0 2px rgba(0,0,0,.6); }',
    '#fr-marks .fr-dot { position: absolute; width: 10px; height: 10px; margin: -5px 0 0 -5px; border-radius: 50%;',
    '  background: #F2A900; border: 2px solid #fff; box-sizing: border-box; }',
    '#fr-card { position: absolute; z-index: 3; transform: translate(-50%, calc(-100% - 12px)); display: none;',
    '  background: rgba(20,28,34,.92); color: #F4F6F8; border-radius: 6px; padding: 6px 10px; max-width: min(280px, 80vw);',
    '  font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; pointer-events: none; box-shadow: 0 3px 12px rgba(0,0,0,.35); }',
    '#fr-tpanel .fr-slrow { display: flex; align-items: center; gap: 4px; min-height: 34px; }',
    '#fr-tpanel .fr-slrow span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '#fr-tpanel .fr-slrow.fr-editing span { color: #F2A900; font-weight: 600; }',
    '#fr-tpanel .fr-slrow.fr-off span { color: #9AA5AE; text-decoration: line-through; }',
    '#fr-tpanel .fr-slrow .fr-btn { min-height: 30px; padding: 0 8px; font-size: 12px; }',
    '#fr-tpanel .fr-num { display: flex; align-items: center; gap: 6px; min-height: 32px; }',
    '#fr-tpanel .fr-num span { flex: 1; }',
    '#fr-tpanel .fr-num input { width: 76px; box-sizing: border-box; font: inherit; padding: 3px 6px; border-radius: 4px;',
    '  border: 1px solid rgba(255,255,255,.3); background: rgba(255,255,255,.08); color: inherit; text-align: right; }',
    '#fr-tpanel .fr-edit { border-left: 3px solid #F2A900; padding-left: 8px; margin: 6px 0; }',
    '#fr-card b { display: block; font-weight: 600; overflow-wrap: anywhere; }',
    '#fr-card span { color: #D5DBE0; font-size: 12px; }',
    'html.fr-clean #fr-parts, html.fr-clean #fr-tpanel { display: none !important; }',
    '@media (max-width: 600px) {',
    '  #fr-tpanel { left: calc(12px + var(--sa-l, 0px)); right: calc(62px + var(--sa-r, 0px)); width: auto; top: auto;',
    '    bottom: 8px; max-height: 38%; z-index: 5; background: rgba(20,28,34,.96); } }',
    // task 0189 (0183 row 12): sideways too the panel ends above the bottom stack (views, time line; --fr-stack)
    '@media (max-height: 480px) { #fr-tpanel { max-height: calc(100% - var(--fr-head, 50px) - var(--fr-stack, 110px) - 8px); } }'
  ].join('\n');
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var ICON = {
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-5M12 8h.01"/>',
    ruler: '<path d="M2.5 16.5L16.5 2.5l5 5-14 14z"/><path d="M7 12l2 2M10 9l2 2M13 6l2 2"/>',
    cut: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 21L21 3"/><path d="M12 21h7a2 2 0 0 0 2-2v-7z" fill="currentColor" stroke="none"/>',
    fade: '<rect x="3" y="8" width="11" height="11" rx="1.5"/><rect x="10" y="4" width="11" height="11" rx="1.5" stroke-dasharray="2 2.2"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>'
  };
  function svg(name) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[name] + '</svg>'; }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  }
  function button(icon, label, key, fn, parent) {
    var b = el('button', { type: 'button', 'class': 'fr-btn', title: label + (key ? ' (' + key + ')' : ''),
                           'aria-label': label });
    if (icon) b.innerHTML = svg(icon); else b.textContent = label;
    b.addEventListener('click', function () { fn(); b.blur(); if (page.input) page.input(); });
    if (parent) parent.appendChild(b);
    return b;
  }

  // ---------------------------------------------------------------- state
  var pref = (page.pref && page.pref.tools) || {};
  var st = {
    tool: null,                                   // 'info' | 'measure' | 'fade' | null (what a click does)
    mode: pref.mode === 'points' ? 'points' : 'faces',
    xyz: pref.xyz === true,
    slices: [],                                   // task 0218: {id, num, how, o, n0, e1, e2, a, b, t, flip, hidden, size}
    sliceOpen: false,                             // the Slice part of the panel is shown
    adding: false,                                // the next click on the model places a new slice
    editing: null,                                // the slice whose handles are shown
    picks: [],                                    // measure: {mesh, local, row, run} (follows its part)
    card: null,                                   // {mesh, local, part, text, face}
    fade: null,                                   // the part that stays solid
    hover: null
  };
  page.toolPrefs = function () { return { mode: st.mode, xyz: st.xyz }; };
  page.toolKeys = [['I', 'part info: click a part'], ['D', 'measure: click two faces or points'],
                   ['X', 'X / Y / Z parts of a measurement'], ['C', 'slice: add, edit and delete slices'], ['T', 'fade the rest: click a part'],
                   ['Esc', 'clear the measurement / card / fade, then close the tool']];

  // ---------------------------------------------------------------- the column and the panel
  var col = el('div', { id: 'fr-parts', role: 'toolbar', 'aria-label': 'Part tools' });
  var btn = {
    info: button('info', 'Part info: click a part', 'I', function () { setTool('info'); }, col),
    measure: button('ruler', 'Measure: click two faces or points', 'D', function () { setTool('measure'); }, col),
    cut: button('cut', 'Slice: cut the model open along faces or X / Y / Z', 'C', function () { openSlices(!st.sliceOpen); }, col),
    fade: button('fade', 'Fade the rest: click a part', 'T', function () { setTool('fade'); }, col)
  };
  document.body.appendChild(col);
  var panel = el('div', { id: 'fr-tpanel', role: 'dialog', 'aria-label': 'Part tool' });
  document.body.appendChild(panel);
  var marks = el('div', { id: 'fr-marks' });
  document.body.appendChild(marks);
  var card = el('div', { id: 'fr-card', role: 'status' });
  document.body.appendChild(card);

  function pressed() {
    ['info', 'measure', 'fade'].forEach(function (k) { btn[k].setAttribute('aria-pressed', st.tool === k ? 'true' : 'false'); });
    btn.cut.setAttribute('aria-pressed', st.sliceOpen ? 'true' : 'false');
  }
  var resultEl = null, hintEl = null;
  function fillPanel() {
    panel.innerHTML = '';
    if (!st.tool && !st.sliceOpen) { panel.style.display = 'none'; pressed(); return; }
    panel.style.display = 'block';
    if (page.hideHint) page.hideHint();        // task 0189: the first-visit bubble sits where the panel goes on a phone
    var titles = { info: 'Part info', measure: 'Measure', fade: 'Fade the rest' };
    if (st.tool) {
      var h = el('h2', {}, titles[st.tool]);
      var x = button('close', 'Close the tool', 'Esc', function () { setTool(null); });
      x.className = 'fr-btn fr-x';
      h.appendChild(x);
      panel.appendChild(h);
    }
    if (st.tool === 'measure') {
      var seg = el('div', { 'class': 'fr-seg', role: 'group', 'aria-label': 'Measure between' });
      [['faces', 'Faces'], ['points', 'Points']].forEach(function (m) {
        var b = button('', m[1], '', function () { setMode(m[0]); }, seg);
        b.dataset.mode = m[0];
        b.setAttribute('aria-pressed', st.mode === m[0] ? 'true' : 'false');
        b.title = m[0] === 'faces' ? 'Flat faces: planes; round faces: diameter, centre to centre'
          : 'The straight distance between two clicked points';
      });
      panel.appendChild(seg);
      var lx = el('label'), bx = el('input', { type: 'checkbox', id: 'fr-xyz' });
      bx.checked = st.xyz;
      bx.addEventListener('change', function () { setXyz(bx.checked); });
      lx.appendChild(bx);
      lx.appendChild(document.createTextNode('X / Y / Z parts as arrows'));
      panel.appendChild(lx);
    }
    if (st.tool) {
      resultEl = el('div', { 'class': 'fr-result', id: 'fr-result', 'aria-live': 'polite' });
      hintEl = el('p', { 'class': 'fr-hint', id: 'fr-hint' });
      panel.appendChild(resultEl);
      panel.appendChild(hintEl);
    } else { resultEl = hintEl = null; }
    if (st.sliceOpen) slicePanel();
    pressed();
    refresh();
    placePanel();
  }
  // a phone: the panel sits above the saved views and the play bar (it covered them), left of the right-hand buttons
  function placePanel() {
    if (window.innerWidth > 600 || panel.style.display === 'none') { panel.style.bottom = ''; return; }
    var bottom = document.getElementById('fr-bottom'), top = window.innerHeight;
    if (bottom) {
      [].forEach.call(bottom.children, function (c) {
        var r = c.getBoundingClientRect();
        if (r.height > 0 && c.offsetParent !== null && !c.classList.contains('note')) top = Math.min(top, r.top);
      });
    }
    panel.style.bottom = Math.max(8, window.innerHeight - top + 8) + 'px';
  }
  window.addEventListener('resize', placePanel);

  // ---------------------------------------------------------------- the 3D side (once the page is ready)
  var facesLoaded = null;
  var three = null, ray = null, faces = null, faceMeshes = {}, primStart = {}, ready = false;
  var hiPart = null, hiFace = null, pickFaces = [];     // highlight overlays
  var HI = null, HI_FACE = null, HI_PICK = null, lineMat = null, lines = null, arrows = [];
  var hiEdge = null, pointerKind = 'mouse';               // task 0219: the edge under the pointer {mesh, i, row}
  var SNAP_PX = 9, SNAP_TOUCH_PX = 18;                   // how near (CSS px) the pointer must be to pick an edge
  var live = [], gz = null, drag = null;              // task 0218: the planes that cut now; the handles
  var faded = new Map(), fadeClones = new Map();         // mesh -> its own material; material -> see-through copy
  var tmpM = new T.Matrix4(), tmpV = new T.Vector3();

  function setup() {
    three = page.three;
    ray = new T.Raycaster();
    HI = new T.MeshBasicMaterial({ color: 0xF2A900, transparent: true, opacity: 0.32, depthWrite: false,
                                   polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, side: T.DoubleSide });
    HI_FACE = HI.clone(); HI_FACE.opacity = 0.45;
    HI_PICK = HI.clone(); HI_PICK.color = new T.Color(0x2F9BFF); HI_PICK.opacity = 0.45;
    [HI, HI_FACE, HI_PICK].forEach(function (m) { m.defines = { FR_NO_CAP: '' }; });
    lineMat = new T.LineBasicMaterial({ color: 0xF2A900, depthTest: false, transparent: true });
    lines = new T.LineSegments(new T.BufferGeometry(), lineMat);
    lines.frustumCulled = false;
    lines.renderOrder = 999;
    lines.visible = false;
    three.scene.add(lines);
    makeHandles();
    // the face data: two accessors per mesh (runs, rows), read once
    var json = page.gltf && page.gltf.parser && page.gltf.parser.json;
    var fx = json && json.extras && json.extras.fr_faces;
    if (fx && fx.meshes) {
      var keys = Object.keys(fx.meshes);
      var jobs = keys.map(function (k) {
        var a = fx.meshes[k];
        return Promise.all(a.slice(0, 3).map(function (i) { return page.gltf.parser.getDependency('accessor', i); }))
          .then(function (r) { faceMeshes[k] = { runs: r[0].array, rows: r[1].array, edges: r[2] ? r[2].array : null }; });
      });
      facesLoaded = Promise.all(jobs).then(function () { faces = fx; refresh(); }, function (e) {
        page.errors.push('face data: ' + (e && e.message || e));
      });
      // where each primitive's triangles start in its mesh (the runs count the mesh's triangles in order)
      (json.meshes || []).forEach(function (m, i) {
        var at = 0, s = [];
        m.primitives.forEach(function (p) { s.push(at); at += (json.accessors[p.indices].count / 3) | 0; });
        s.push(at);
        primStart[i] = s;
      });
    }
    page.beforeDraw.push(beforeDraw);
    ready = true;
    fillPanel();
  }

  // ---------------------------------------------------------------- picking
  function shown(o) {
    for (var p = o; p; p = p.parent) if (!p.visible) return false;
    return true;
  }
  function targets() {
    var out = [];
    three.top.traverseVisible(function (o) { if (o.isMesh && !o.userData.frOverlay) out.push(o); });
    return out;
  }
  function partOf(o) {
    for (var p = o; p; p = p.parent) if (p.userData && p.userData.frPart) return p;
    return null;
  }
  // the first part under a screen point (CSS pixels of the view), not cut away
  function pickAt(x, y) {
    if (!ready) return null;
    var c = three.canvas, w = c.clientWidth || 1, h = c.clientHeight || 1;
    three.camera.updateMatrixWorld();            // before the first picture the camera's matrix is not set yet
    ray.setFromCamera(new T.Vector2(x / w * 2 - 1, -(y / h) * 2 + 1), three.camera);
    three.scene.updateMatrixWorld();
    var hits = ray.intersectObjects(targets(), false).concat(tubeHits());
    hits.sort(function (a, b) { return a.distance - b.distance; });
    for (var i = 0; i < hits.length; i++) {
      var hit = hits[i];
      if (live.length && !keptW(hit.point)) continue;                              // in a part cut away
      if (!shown(hit.object)) continue;
      var part = partOf(hit.object);
      if (!part || part.userData.fr_decal) continue;      // a decal is a thin sticker on its part: look through it
      var out = { mesh: hit.object, point: hit.point.clone(), faceIndex: hit.faceIndex, part: part, tube: !!hit.tube };
      // the inside of a cut part seen through the cut: the visitor sees the red cap, i.e. the cut plane itself
      if (hit.face && !hit.tube) {
        var nW = hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
        if (hit.object.matrixWorld.determinant() < 0) nW.negate();
        out.tri = dirToModel(nW);                         // the triangle's own normal (a slice on a page without faces)
        if (live.length && nW.dot(ray.ray.direction) > 0) {
          // the inside of a cut part: the visitor sees the red cap, i.e. the slice where the ray enters the kept room
          var c = M.slice.capAt(live.map(function (pl) {
            return { n: pl.normal.toArray(), q: pl.normal.clone().multiplyScalar(-pl.constant).toArray() }; }),
            ray.ray.origin.toArray(), ray.ray.direction.toArray(), hit.distance);
          if (c) { out.point = new T.Vector3().fromArray(c.p); out.cap = sliceOfPlane(live[c.i]); }
        }
      }
      return out;
    }
    return null;
  }
  // the page's drawn cables, ropes and hoses (task 0142): their shape is made on the graphics card, so the ray is
  // tested against their centre lines and radius
  function tubeHits() {
    var out = [];
    if (!page.tubeLines) return out;
    var a = new T.Vector3(), b = new T.Vector3(), onRay = new T.Vector3(), onSeg = new T.Vector3();
    page.tubeLines().forEach(function (tl) {
      if (!tl.shown || !tl.count || !shown(tl.mesh)) return;
      tl.node.updateWorldMatrix(true, false);
      var m = tl.node.matrixWorld, best = null;
      for (var i = 0; i + 1 < tl.count; i++) {
        a.set(tl.cp[3 * i], tl.cp[3 * i + 1], tl.cp[3 * i + 2]).applyMatrix4(m);
        b.set(tl.cp[3 * i + 3], tl.cp[3 * i + 4], tl.cp[3 * i + 5]).applyMatrix4(m);
        var d2 = ray.ray.distanceSqToSegment(a, b, onRay, onSeg);
        if (d2 <= tl.r * tl.r) {
          var dist = onRay.distanceTo(ray.ray.origin) - Math.sqrt(Math.max(tl.r * tl.r - d2, 0));
          if (dist > 0 && (!best || dist < best.distance)) {
            best = { distance: dist, point: ray.ray.at(dist, new T.Vector3()), object: tl.mesh, tube: true };
          }
        }
      }
      if (best) out.push(best);
    });
    return out;
  }

  // the row of the file's face data under a hit: null for a face without data (or a page without)
  function runOf(mesh, faceIndex) {
    if (!faces || !page.gltf) return null;
    var as = page.gltf.parser.associations.get(mesh);
    if (!as || as.meshes == null) return null;
    var fm = faceMeshes[String(as.meshes)], starts = primStart[as.meshes];
    if (!fm || !starts) return null;
    var tri = starts[as.primitives || 0] + faceIndex, runs = fm.runs;
    var lo = 0, hi = runs.length / 2 - 1;
    if (hi < 0 || tri < runs[0]) return null;
    while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (runs[2 * mid] <= tri) lo = mid; else hi = mid - 1; }
    var r = runs[2 * lo + 1];
    if (r === 0xFFFFFFFF) return null;
    var n = faces.row || 8;
    var end = lo + 1 < runs.length / 2 ? runs[2 * lo + 2] : starts[starts.length - 1];
    return { row: Array.prototype.slice.call(fm.rows, r * n, r * n + n), first: runs[2 * lo], end: end,
             prim: as.primitives || 0, starts: starts, ri: r, key: String(as.meshes) };
  }
  // task 0219: the edge of the hit's CAD face nearest the pointer (x, y), when it is within a few pixels: {i, row}
  function edgeAt(hit, x, y, touch) {
    if (!hit || !hit.run || hit.tube || hit.cap) return null;
    var fm = faceMeshes[hit.run.key], E = fm && fm.edges;
    if (!E) return null;
    if (!fm.byRow) {                                   // the edges of each face row (records of 9 or 12 numbers)
      fm.byRow = {};
      for (var at = 0; at + 9 <= E.length; at += Math.round(E[at]) === 5 ? 12 : 9) {
        [E[at + 1], E[at + 2]].forEach(function (r) { if (r >= 0) (fm.byRow[r] = fm.byRow[r] || []).push(at); });
      }
    }
    var list = fm.byRow[hit.run.ri];
    if (!list) return null;
    var m = modelMatrix(hit.mesh).elements, p = toModel(hit.point), best = null, lim = touch ? SNAP_TOUCH_PX : SNAP_PX;
    list.forEach(function (i) {
      var row = Array.prototype.slice.call(E, i, i + (Math.round(E[i]) === 5 ? 12 : 9)), k = M.fromEdge(row, m, p);
      if (!k) return;
      var q = screenOfWorld(toWorld(M.nearEdge(k, p).q)), d = Math.hypot(q.x - x, q.y - y);
      if (d <= lim && (!best || d < best.d)) best = { i: i, row: row, d: d };
    });
    return best;
  }

  // the model's own coordinates (Blender's axes, the vessel at rest)
  function modelMatrix(obj) {             // obj's coordinates -> the model's: T2B * inverse(vessel) * obj
    tmpM.copy(three.vessel.matrixWorld).invert();
    return new T.Matrix4().multiplyMatrices(three.T2B, tmpM).multiply(obj.matrixWorld);
  }
  function toModel(v) {                   // a world point (three) -> the model's [x, y, z]
    tmpM.copy(three.vessel.matrixWorld).invert();
    var p = v.clone().applyMatrix4(tmpM);
    return [p.x, -p.z, p.y];
  }
  function toWorld(a) {                   // the model's [x, y, z] -> a world point (three)
    return new T.Vector3(a[0], a[2], -a[1]).applyMatrix4(three.vessel.matrixWorld);
  }
  function dirToWorld(a) { return new T.Vector3(a[0], a[2], -a[1]).transformDirection(three.vessel.matrixWorld); }
  function dirToModel(v) {
    tmpM.copy(three.vessel.matrixWorld).invert();
    var d = v.clone().transformDirection(tmpM);
    return [d.x, -d.z, d.y];
  }
  function screenOfWorld(v) {
    three.camera.updateMatrixWorld();
    var p = v.clone().project(three.camera), c = three.canvas;
    return { x: (p.x + 1) / 2 * c.clientWidth, y: (1 - p.y) / 2 * c.clientHeight, behind: p.z > 1 };
  }

  // a stored click (mesh, its own point, its face) -> the measuring pick now (the part may have moved)
  function pickNow(k) {
    var w = k.mesh.localToWorld(k.local.clone());
    if (k.cap) {                          // the cut face: a flat face in its slice's plane, facing out of what is kept
      var n = st.slices.indexOf(k.cap) >= 0 ? M.slice.plane(k.cap).n : k.capN;
      return { kind: 'flat', p: toModel(w), n: [-n[0], -n[1], -n[2]], face: 1, cap: true };
    }
    if (k.edge) {                         // task 0219: a CAD edge
      var e = M.fromEdge(k.edge.row, modelMatrix(k.mesh).elements, toModel(w));
      e.face = 0;
      return e;
    }
    var p = M.fromRow(k.run ? k.run.row : null, modelMatrix(k.mesh).elements, toModel(w));
    p.face = k.run ? k.run.row[0] : 0;
    return p;
  }
  function keep(hit) {
    return { mesh: hit.mesh, local: hit.mesh.worldToLocal(hit.point.clone()), part: hit.part, cap: hit.cap || null,
             capN: hit.cap ? M.slice.plane(hit.cap).n : null, edge: hit.edge || null,
             run: hit.cap || hit.tube || hit.edge ? null : runOf(hit.mesh, hit.faceIndex) };
  }

  // ---------------------------------------------------------------- highlights
  function clearOverlay(list) {
    (list || []).forEach(function (o) { if (o.parent) o.parent.remove(o); if (o.userData.own) o.geometry.dispose(); });
  }
  function overlayPart(part, mat) {
    var out = [];
    part.traverse(function (o) {
      if (o.isMesh && !o.userData.frOverlay) {
        var m = new T.Mesh(o.geometry, mat);
        m.userData.frOverlay = true;
        m.matrixAutoUpdate = false;
        m.renderOrder = 5;
        o.add(m);
        out.push(m);
      }
    });
    return out;
  }
  function overlayFace(mesh, run, mat) {         // the triangles of one CAD face of ``mesh``
    var g = mesh.geometry, idx = g.index, pos = g.attributes.position;
    var a = Math.max(0, run.first - run.starts[run.prim]), b = Math.min(run.end, run.starts[run.prim + 1]) - run.starts[run.prim];
    var n = Math.max(0, b - a), arr = new Float32Array(n * 9);
    for (var t = 0; t < n; t++) {
      for (var c = 0; c < 3; c++) {
        var v = idx ? idx.getX(3 * (a + t) + c) : 3 * (a + t) + c;
        arr[9 * t + 3 * c] = pos.getX(v); arr[9 * t + 3 * c + 1] = pos.getY(v); arr[9 * t + 3 * c + 2] = pos.getZ(v);
      }
    }
    var fg = new T.BufferGeometry();
    fg.setAttribute('position', new T.BufferAttribute(arr, 3));
    var m = new T.Mesh(fg, mat);
    m.userData.frOverlay = true;
    m.userData.own = true;
    m.matrixAutoUpdate = false;
    m.renderOrder = 6;
    mesh.add(m);
    return [m];
  }
  function setHover(hit) {
    var faceWise = st.tool === 'measure' || st.adding;
    var key = hit ? (faceWise && hit.edge ? hit.mesh.uuid + ':e' + hit.edge.i :
                     faceWise && hit.run ? hit.mesh.uuid + ':' + hit.run.first : hit.part.uuid) : '';
    if (key === (st.hover || '')) return;
    st.hover = key;
    clearOverlay(hiPart); hiPart = null;
    clearOverlay(hiFace); hiFace = null;
    hiEdge = hit && faceWise && hit.edge ? { mesh: hit.mesh, row: hit.edge.row } : null;
    if (hit) {
      if (hiEdge) { /* the edge is drawn as a line (beforeDraw) */ }
      else if (faceWise && hit.run) hiFace = overlayFace(hit.mesh, hit.run, HI_FACE);
      else hiPart = overlayPart(hit.part, HI);
      clip([HI, HI_FACE]);
    }
    page.wake();
  }
  function showPicks() {
    clearOverlay(pickFaces); pickFaces = [];
    st.picks.forEach(function (k) {
      if (k.run) pickFaces = pickFaces.concat(overlayFace(k.mesh, k.run, HI_PICK));
    });
  }

  // ---------------------------------------------------------------- fade the rest
  function fadedOf(m) {
    var f = fadeClones.get(m);
    if (!f) {
      f = m.clone();
      f.onBeforeCompile = m.onBeforeCompile;          // the drawn tubes and the baked light are made there
      f.customProgramCacheKey = m.customProgramCacheKey;
      f.clippingPlanes = null;                        // a copy of the plane would stay where it was: set by clip()
      f.transparent = true;
      f.opacity = 0.12;
      f.depthWrite = false;
      f.defines = Object.assign({}, f.defines || {}, { FR_NO_CAP: '' });
      fadeClones.set(m, f);
    }
    return f;
  }
  function setFade(part) {
    unfade();
    st.fade = part;
    if (part) {
      var keepSet = new Set();
      part.traverse(function (o) { keepSet.add(o); });
      three.top.traverse(function (o) {
        if (!o.isMesh || o.userData.frOverlay || keepSet.has(o)) return;
        faded.set(o, o.material);
        o.material = Array.isArray(o.material) ? o.material.map(fadedOf) : fadedOf(o.material);
      });
      clip(materials());
    }
    page.wake();
    refresh();
  }
  function unfade() {
    faded.forEach(function (mat, o) { o.material = mat; });
    faded.clear();
    st.fade = null;
  }

  // ---------------------------------------------------------------- cutaway
  function materials() {
    var set = new Set();
    three.top.traverse(function (o) {
      if (!o.isMesh || o.userData.frOverlay) return;
      (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) { if (m) set.add(m); });
    });
    faded.forEach(function (mat) { (Array.isArray(mat) ? mat : [mat]).forEach(function (m) { if (m) set.add(m); }); });
    return Array.from(set);
  }
  // every material cut by the live planes (always the live Plane objects, never copies)
  function clip(list) {
    var want = live.length ? live : null;
    list.forEach(function (m) {
      var cur = m.clippingPlanes || [];
      var same = want ? cur.length === want.length && want.every(function (p, i) { return cur[i] === p; }) : !cur.length;
      if (same) return;
      var recompile = cur.length !== (want ? want.length : 0);
      m.clippingPlanes = want ? want.slice() : null;
      m.clipShadows = !!want;
      if (recompile) m.needsUpdate = true;
    });
  }

  // ---------------------------------------------------------------- slices (task 0218)
  var MAX_SLICES = 8, nextId = 1;
  function boxOf() { return { lo: page.settings.model.min, hi: page.settings.model.max }; }
  function diag() {
    var b = boxOf();
    return Math.max(1e-3, Math.hypot(b.hi[0] - b.lo[0], b.hi[1] - b.lo[1], b.hi[2] - b.lo[2]));
  }
  function viewModel() { three.camera.updateMatrixWorld(); return dirToModel(three.camera.getWorldDirection(new T.Vector3())); }
  function keptW(p) {
    for (var i = 0; i < live.length; i++) if (live[i].distanceToPoint(p) < -1e-6) return false;
    return true;
  }
  function sliceOfPlane(pl) {
    for (var i = 0; i < st.slices.length; i++) if (st.slices[i].plane === pl) return st.slices[i];
    return null;
  }
  function sliceById(id) {
    for (var i = 0; i < st.slices.length; i++) if (st.slices[i].id === id) return st.slices[i];
    return null;
  }
  // each slice's live plane in the world (the vessel moves) and the list of planes that cut now
  function placeSlices() {
    if (!ready) return;
    three.vessel.updateMatrixWorld();
    st.slices.forEach(function (s) {
      var P = M.slice.plane(s);
      s.plane.setFromNormalAndCoplanarPoint(dirToWorld(P.n), toWorld(P.q));
    });
  }
  function relist() {                     // after a slice was added, deleted, hidden or shown
    if (!ready) return;
    placeSlices();
    live = st.slices.filter(function (s) { return !s.hidden; }).map(function (s) { return s.plane; });
    three.renderer.localClippingEnabled = live.length > 0;
    clip(materials().concat([HI, HI_FACE, HI_PICK]));
    page.wake();
  }
  function addSlice(base, how) {
    if (st.slices.length >= MAX_SLICES) return null;
    var num = st.slices.reduce(function (m, x) { return Math.max(m, x.num); }, 0) + 1;
    var s = Object.assign(base, { id: nextId++, num: num, how: how, hidden: false, size: diag() * 0.5, plane: new T.Plane() });
    st.slices.push(s);
    st.adding = false;
    st.editing = s.id;
    relist();
    fillPanel();
    return s;
  }
  function addAcross(axis, frac) {
    if (!ready) return null;
    var b = boxOf(), i = { X: 0, Y: 1, Z: 2 }[axis];
    var at = [0, 1, 2].map(function (k) { return (b.lo[k] + b.hi[k]) / 2; });
    if (frac != null) at[i] = b.lo[i] + (b.hi[i] - b.lo[i]) * frac;
    return addSlice(M.slice.across(axis, at, viewModel()), 'across ' + axis);
  }
  function addOnHit(hit) {
    var k = keep(hit), p = pickNow(k);
    var how = p.cap ? 'on a cut face' : p.kind === 'flat' ? 'on a flat face'
      : p.kind === 'round' || p.kind === 'axis' ? 'through an axis' : 'on a face';
    return addSlice(M.slice.fromPick(p, viewModel(), hit.tri || null), how);
  }
  function deleteSlice(id) {
    var s = sliceById(id);
    if (!s) return;
    st.slices.splice(st.slices.indexOf(s), 1);
    if (st.editing === id) st.editing = null;
    st.picks = st.picks.filter(function (k) { return k.cap !== s; });
    relist(); showPicks(); fillPanel();
  }
  function setHidden(id, hidden) {
    var s = sliceById(id);
    if (!s) return;
    s.hidden = !!hidden;
    if (s.hidden && st.editing === id) st.editing = null;
    relist(); fillPanel();
  }
  function editSlice(id) {
    st.editing = sliceById(id) ? id : null;
    st.adding = false;
    fillPanel(); page.wake();
  }
  // a change to the slice being edited: {t (m), a, b (degrees), flip, size}
  function change(id, patch) {
    var s = sliceById(id);
    if (!s) return null;
    if (patch.t != null && isFinite(patch.t)) {
      var r = M.slice.moveRange(s, boxOf().lo, boxOf().hi), pad = diag() * 0.02;
      s.t = Math.max(r[0] - pad, Math.min(r[1] + pad, +patch.t));
    }
    ['a', 'b'].forEach(function (k) {
      if (patch[k] != null && isFinite(patch[k])) { var v = +patch[k]; while (v > 180) v -= 360; while (v < -180) v += 360; s[k] = v; }
    });
    if (patch.flip != null) s.flip = !!patch.flip;
    if (patch.size != null && isFinite(patch.size)) s.size = Math.max(diag() * 0.02, +patch.size);
    placeSlices();
    syncInputs();
    page.wake();
    return s;
  }
  function openSlices(on) {
    st.sliceOpen = !!on;
    if (!st.sliceOpen) { st.adding = false; st.editing = null; }
    else if (!st.slices.length) st.adding = true;     // the first time: straight to "click a face"
    setHover(null);
    fillPanel();
    page.wake();
  }
  function startAdding(on) { st.adding = !!on && st.slices.length < MAX_SLICES; if (st.adding) st.editing = null; setHover(null); fillPanel(); }

  // the Slice part of the panel
  var inputs = {};
  function numRow(parent, label, key, unit, step, title) {
    var row = el('label', { 'class': 'fr-num' }), sp = el('span', {}, label);
    var inp = el('input', { type: 'number', step: String(step), id: 'fr-slice-' + key, 'aria-label': label });
    inp.title = title;
    inp.addEventListener('change', function () {
      var v = parseFloat(String(inp.value).replace(',', '.'));
      if (!isFinite(v) || st.editing == null) return;
      var patch = {}; patch[key] = key === 't' ? v / 1000 : v;
      change(st.editing, patch);
    });
    row.appendChild(sp); row.appendChild(inp); row.appendChild(el('span', { style: 'flex:none' }, unit));
    parent.appendChild(row);
    inputs[key] = inp;
  }
  function syncInputs() {
    var s = sliceById(st.editing);
    if (!s) return;
    var val = { t: (s.t * 1000).toFixed(1), a: s.a.toFixed(1), b: s.b.toFixed(1) };
    Object.keys(val).forEach(function (k) {
      if (inputs[k] && document.activeElement !== inputs[k]) inputs[k].value = val[k];
    });
    if (inputs.size && document.activeElement !== inputs.size) inputs.size.value = String(s.size / diag());
  }
  function slicePanel() {
    inputs = {};
    var h3 = el('h3', {}, 'Slice');
    if (!st.tool) {                                       // the panel's own title row with the close button
      h3 = el('h2', {}, 'Slice');
      var x = button('close', 'Close the slice list (the slices stay on)', 'C', function () { openSlices(false); });
      x.className = 'fr-btn fr-x';
      h3.appendChild(x);
    }
    panel.appendChild(h3);
    var top = el('div', { 'class': 'fr-seg' });
    var add = button('', st.adding ? 'Cancel' : 'Add slice', '', function () { startAdding(!st.adding); }, top);
    add.id = 'fr-slice-add';
    add.title = st.adding ? 'Stop placing a new slice' : 'Place a new slice: click a face, or choose X, Y or Z';
    add.setAttribute('aria-pressed', st.adding ? 'true' : 'false');
    if (st.slices.length >= MAX_SLICES && !st.adding) { add.disabled = true; add.title = 'At most ' + MAX_SLICES + ' slices'; }
    if (st.slices.length > 1) {
      var all = button('', 'Delete all', '', function () {
        st.slices.slice().forEach(function (s) { deleteSlice(s.id); });
      }, top);
      all.id = 'fr-slice-all';
      all.title = 'Delete every slice: the whole model again';
    }
    panel.appendChild(top);
    if (st.adding) {
      panel.appendChild(el('p', { 'class': 'fr-hint', id: 'fr-slice-hint' },
        'Click a face: a flat face slices in its plane, a round face through its axis. Or slice across:'));
      var ax = el('div', { 'class': 'fr-seg', role: 'group', 'aria-label': 'Slice across' });
      ['X', 'Y', 'Z'].forEach(function (a) {
        var b = button('', a, '', function () { addAcross(a); }, ax);
        b.dataset.axis = a;
        b.title = 'A slice across the ' + a + ' axis, through the middle of the model';
      });
      panel.appendChild(ax);
    }
    st.slices.forEach(function (s) {
      var row = el('div', { 'class': 'fr-slrow' + (st.editing === s.id ? ' fr-editing' : '') + (s.hidden ? ' fr-off' : '') });
      row.dataset.slice = String(s.num);
      row.appendChild(el('span', {}, 'Slice ' + s.num + ' · ' + s.how));
      var ed = button('', st.editing === s.id ? 'Done' : 'Edit', '', function () {
        editSlice(st.editing === s.id ? null : s.id); }, row);
      ed.title = st.editing === s.id ? 'Stop editing slice ' + s.num + ' (Esc)' : 'Edit slice ' + s.num + ': move and turn it';
      ed.dataset.act = 'edit';
      var hd = button('', s.hidden ? 'Show' : 'Hide', '', function () { setHidden(s.id, !s.hidden); }, row);
      hd.title = s.hidden ? 'Cut with slice ' + s.num + ' again' : 'Leave slice ' + s.num + ' off for now (kept in the list)';
      hd.dataset.act = 'hide';
      var del = button('close', 'Delete slice ' + s.num, '', function () { deleteSlice(s.id); }, row);
      del.className = 'fr-btn fr-x';
      del.dataset.act = 'delete';
      panel.appendChild(row);
      if (st.editing === s.id) {
        var box = el('div', { 'class': 'fr-edit', id: 'fr-slice-edit' });
        numRow(box, 'Move', 't', 'mm', 1, 'How far the slice is moved along its arrow from where it was placed (mm)');
        numRow(box, 'Turn', 'a', '°', 1, 'Turn about the first axis in the slice (degrees; or drag a yellow knob)');
        numRow(box, 'Turn', 'b', '°', 1, 'Turn about the second axis in the slice (degrees; or drag the other knob)');
        var sz = el('input', { type: 'range', min: '0.05', max: '1.5', step: '0.01', id: 'fr-slice-size',
                               'aria-label': 'Size of the drawn plane' });
        sz.title = 'Size of the drawn plane only: the slice always cuts the whole model';
        sz.addEventListener('input', function () { change(s.id, { size: +sz.value * diag() }); });
        inputs.size = sz;
        box.appendChild(sz);
        var fl = el('div', { 'class': 'fr-seg' });
        var fb = button('', 'Flip', '', function () { change(s.id, { flip: !s.flip }); fillPanel(); }, fl);
        fb.id = 'fr-slice-flip';
        fb.title = 'Keep the other side of slice ' + s.num;
        fb.setAttribute('aria-pressed', s.flip ? 'true' : 'false');
        var dn = button('', 'Done', 'Esc', function () { editSlice(null); }, fl);
        dn.id = 'fr-slice-done';
        box.appendChild(fl);
        box.appendChild(el('p', { 'class': 'fr-hint' }, 'Drag the arrow to move the slice, a yellow knob to turn it.'));
        panel.appendChild(box);
      }
    });
    if (!st.slices.length && !st.adding) panel.appendChild(el('p', { 'class': 'fr-hint' }, 'No slices: the whole model.'));
    syncInputs();
  }

  // the handles of the slice being edited: its plane, an arrow to move it, two knobs to turn it
  function makeHandles() {
    var basic = function (c, o) {
      var m = new T.MeshBasicMaterial({ color: c, transparent: true, opacity: o, depthTest: false, depthWrite: false,
                                        side: T.DoubleSide });
      m.defines = { FR_NO_CAP: '' };
      return m;
    };
    gz = new T.Group();
    gz.visible = false;
    gz.renderOrder = 1000;
    var quad = new T.Mesh(new T.PlaneGeometry(1, 1), basic(0x2F9BFF, 0.12));
    var edge = new T.LineSegments(new T.EdgesGeometry(new T.PlaneGeometry(1, 1)),
                                  new T.LineBasicMaterial({ color: 0x2F9BFF, transparent: true, depthTest: false }));
    var arm = basic(0xF4F6F8, 0.95), knob = basic(0xF2A900, 0.95);
    var shaft = new T.Mesh(new T.CylinderGeometry(0.25, 0.25, 2, 10), arm);
    var up = new T.Mesh(new T.ConeGeometry(0.7, 1.6, 16), arm), down = new T.Mesh(new T.ConeGeometry(0.7, 1.6, 16), arm);
    var k1 = new T.Mesh(new T.SphereGeometry(1, 16, 12), knob), k2 = new T.Mesh(new T.SphereGeometry(1, 16, 12), knob);
    [quad, edge, shaft, up, down, k1, k2].forEach(function (o) {
      o.matrixAutoUpdate = false; o.frustumCulled = false; o.renderOrder = 1000; o.userData.frOverlay = true; gz.add(o);
    });
    gz.userData = { frOverlay: true, quad: quad, edge: edge, shaft: shaft, up: up, down: down, k1: k1, k2: k2 };
    three.scene.add(gz);
  }
  // where the handles are now (world, and their size on the screen)
  function handles() {
    var s = sliceById(st.editing);
    if (!s || s.hidden) return null;
    var P = M.slice.plane(Object.assign({}, s, { flip: false }));
    var q = toWorld(P.q), n = dirToWorld(P.n), e1 = dirToWorld(P.e1), e2 = dirToWorld(P.e2);
    var r = Math.max(q.distanceTo(three.camera.position), 1e-6) * 0.012;      // a knob's radius: ~same size on screen
    var L = Math.max(r * 8, Math.min(s.size * 0.3, r * 14));
    return { s: s, q: q, n: n, e1: e1, e2: e2, r: r, L: L, size: s.size,
             kb: q.clone().addScaledVector(e1, s.size / 2),           // turns about e2 (b)
             ka: q.clone().addScaledVector(e2, s.size / 2) };         // turns about the first e1 (a)
  }
  function drawHandles() {
    var H = handles();
    gz.visible = !!H;
    if (!H) return;
    var u = gz.userData, Y = new T.Vector3(0, 1, 0), m = new T.Matrix4(), qt = new T.Quaternion();
    m.makeBasis(H.e1, H.e2, H.n).scale(new T.Vector3(H.size, H.size, H.size)).setPosition(H.q);
    u.quad.matrix.copy(m); u.edge.matrix.copy(m);
    qt.setFromUnitVectors(Y, H.n);
    var sc = new T.Vector3(H.r, H.r, H.r);
    u.shaft.matrix.compose(H.q, qt, new T.Vector3(H.r, H.L / 2, H.r));
    u.up.matrix.compose(H.q.clone().addScaledVector(H.n, H.L / 2 + H.r * 0.8), qt, sc);
    u.down.matrix.compose(H.q.clone().addScaledVector(H.n, -H.L / 2 - H.r * 0.8),
                          new T.Quaternion().setFromUnitVectors(Y, H.n.clone().negate()), sc);
    u.k1.matrix.compose(H.ka, qt, sc.clone().multiplyScalar(1.1));
    u.k2.matrix.compose(H.kb, qt, sc.clone().multiplyScalar(1.1));
  }
  function segDist(p, a, b) {
    var dx = b.x - a.x, dy = b.y - a.y, l2 = dx * dx + dy * dy;
    var t = l2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / l2)) : 0;
    return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy);
  }
  // which handle is under a screen point: 'a' | 'b' (the knobs) | 't' (the arrow) | null
  function handleAt(x, y, touch) {
    var H = handles();
    if (!H) return null;
    var p = { x: x, y: y }, reach = touch ? 24 : 12;
    var sa = screenOfWorld(H.ka), sb = screenOfWorld(H.kb);
    var da = sa.behind ? 1e9 : Math.hypot(sa.x - x, sa.y - y), db = sb.behind ? 1e9 : Math.hypot(sb.x - x, sb.y - y);
    if (Math.min(da, db) <= reach + 4) return da <= db ? 'a' : 'b';
    var t0 = screenOfWorld(H.q.clone().addScaledVector(H.n, -H.L / 2 - H.r * 1.6));
    var t1 = screenOfWorld(H.q.clone().addScaledVector(H.n, H.L / 2 + H.r * 1.6));
    if (!t0.behind && !t1.behind && segDist(p, t0, t1) <= reach) return 't';
    return null;
  }
  function rayThrough(x, y) {
    var c = three.canvas;
    three.camera.updateMatrixWorld();
    ray.setFromCamera(new T.Vector2(x / (c.clientWidth || 1) * 2 - 1, -(y / (c.clientHeight || 1)) * 2 + 1), three.camera);
    return ray.ray;
  }
  // the drag's number at a screen point: metres along the arrow, or the angle (degrees) about the turning axis
  function dragValue(g, x, y) {
    var r = rayThrough(x, y);
    if (g.kind === 't') {                 // the point of the arrow's line nearest to the pointer's ray
      var w0 = r.origin.clone().sub(g.q), b = r.direction.dot(g.n), den = 1 - b * b;
      if (den < 1e-4) return null;
      return (g.n.dot(w0) - b * r.direction.dot(w0)) / den;
    }
    var hit = r.intersectPlane(new T.Plane().setFromNormalAndCoplanarPoint(g.axis, g.q), new T.Vector3());
    if (!hit) return null;
    var v = hit.sub(g.q);
    return Math.atan2(v.dot(g.v2), v.dot(g.v1)) * 180 / Math.PI;
  }
  function startDrag(kind, x, y, id) {
    var H = handles();
    if (!H) return false;
    var s = H.s, g = { kind: kind, id: id, q: H.q, n: H.n, s: s };
    if (kind !== 't') {
      // a: about the first e1 (fixed), b: about the turned e2
      g.axis = kind === 'a' ? dirToWorld(s.e1) : H.e2;
      g.v1 = (kind === 'a' ? H.ka : H.kb).clone().sub(H.q).normalize();
      g.v2 = new T.Vector3().crossVectors(g.axis, g.v1);
      g.v0 = s[kind];
    } else g.v0 = s.t;
    g.start = dragValue(g, x, y);
    if (g.start == null) return false;
    g.last = g.start; g.acc = 0;
    drag = g;
    three.controls.enabled = false;
    return true;
  }
  function moveDrag(x, y) {
    var v = dragValue(drag, x, y);
    if (v == null) return;
    var patch = {};
    if (drag.kind === 't') patch.t = drag.v0 + (v - drag.start);
    else {
      var dv = v - drag.last;
      while (dv > 180) dv -= 360;
      while (dv < -180) dv += 360;
      drag.acc += dv; drag.last = v;
      patch[drag.kind] = drag.v0 + drag.acc;
    }
    change(drag.s.id, patch);
  }
  function endDrag() { drag = null; three.controls.enabled = true; syncInputs(); }

  // ---------------------------------------------------------------- tools
  function setTool(t) {
    st.tool = st.tool === t ? null : t;
    if (st.tool !== 'measure') clearMeasure();
    if (st.tool !== 'info') closeCard();
    setHover(null);
    fillPanel();
  }
  function setMode(m) { st.mode = m === 'points' ? 'points' : 'faces'; save(); fillPanel(); page.wake(); }
  function setXyz(v) { st.xyz = !!v; save(); refresh(); page.wake(); }
  function save() { if (page.savePrefs) page.savePrefs(); }
  page.resetTools = function () { st.mode = 'faces'; st.xyz = false; fillPanel(); };
  function clearMeasure() { st.picks = []; showPicks(); refresh(); page.wake(); }
  function closeCard() { st.card = null; card.style.display = 'none'; page.wake(); }

  function faceText(p) {
    if (p.cap) return 'Cut face';
    if (p.kind === 'line') return 'Straight edge ' + M.mm(p.len);
    if (p.kind === 'circle') return 'Round edge Ø ' + M.mm(2 * p.r);
    if (p.kind === 'round') return 'Round face Ø ' + M.mm(2 * p.r);
    if (p.kind === 'axis') return 'Round face (cone or rounded edge)';
    if (p.kind === 'flat') return 'Flat face';
    return '';
  }
  function openCard(hit) {
    var k = keep(hit);
    var text = String(hit.part.userData.fr_card || '');
    var face = faceText(pickNow(k));
    st.card = { mesh: k.mesh, local: k.local, run: k.run, part: hit.part, text: text, face: face };
    card.innerHTML = '';
    card.appendChild(el('b', {}, text || 'Part'));
    var lines_ = (text ? [] : ['No name on this page']).concat(face ? [face] : []);
    lines_.forEach(function (t, i) {
      if (i) card.appendChild(el('br'));
      card.appendChild(el('span', {}, t));
    });
    card.style.display = 'block';
    page.wake();
  }

  function onClick(x, y) {
    if (!ready) return;
    var hit = pickAt(x, y);
    if (st.adding) {                     // "Add slice": this click places it (empty space: keep waiting)
      if (hit) addOnHit(hit);
      return;
    }
    if (st.tool === 'info' || (!st.tool && st.card)) {
      if (hit) openCard(hit); else closeCard();
    } else if (st.tool === 'fade') {
      setFade(hit ? hit.part : null);
    } else if (st.tool === 'measure') {
      if (!hit) { clearMeasure(); return; }
      if (st.mode === 'faces' && faces && !hit.tube && !hit.cap) {
        hit.run = runOf(hit.mesh, hit.faceIndex);
        hit.edge = edgeAt(hit, x, y, pointerKind !== 'mouse');
      }
      var k = keep(hit);
      if (st.mode === 'faces' && !faces) k.run = null;
      if (st.picks.length >= 2) st.picks = [];
      st.picks.push(k);
      showPicks();
      refresh();
      page.wake();
    }
    page.lastPick = hit ? { card: String(hit.part.userData.fr_card || ''), name: hit.part.name } : null;
  }
  function onLongPress(x, y) {
    var hit = pickAt(x, y);
    if (hit) openCard(hit);
  }

  // ---------------------------------------------------------------- the result: panel text, lines, numbers
  var result = null;
  function compute() {
    result = null;
    if (st.picks.length === 1) {
      var a = pickNow(st.picks[0]);
      result = M.single(st.mode === 'points' ? { kind: 'point', p: a.p } : a);
      result.picks = [a];
    } else if (st.picks.length === 2) {
      var p0 = pickNow(st.picks[0]), p1 = pickNow(st.picks[1]);
      result = M.measure(p0, p1, st.mode);
      result.picks = [p0, p1];
      result.parts = st.xyz && result.vec ? M.parts(result.from, result.vec) : [];
    }
    return result;
  }
  function refresh() {
    if (!resultEl) return;
    var hint = '';
    if (st.tool === 'measure') {
      compute();
      resultEl.innerHTML = '';
      (result ? result.lines : []).forEach(function (t) { resultEl.appendChild(el('div', {}, t)); });
      if (result && result.parts && result.parts.length) {
        result.parts.forEach(function (q) {
          var d = el('div', {}, q.text);
          d.style.color = AXIS_COLOUR[q.axis];
          resultEl.appendChild(d);
        });
      }
      if (st.mode === 'faces' && !faces) hint = 'This page has no face data (exported without “Faces for measuring”): it measures between points.';
      else if (!st.picks.length) hint = st.mode === 'faces' ? 'Click a face (flat or round) or an edge: near an edge the pointer picks the edge (it lights up as a line).' : 'Click a first point.';
      else if (st.picks.length === 1) hint = st.mode === 'faces' ? 'Click a second face or edge, or a round face’s diameter is shown.' : 'Click a second point.';
      else hint = 'Click again for a new measurement · empty space or Esc clears it.';
    } else if (st.tool === 'info') {
      resultEl.innerHTML = '';
      hint = 'Click a part: its name or label. Phone: tap; a long press works with any tool.';
    } else if (st.tool === 'fade') {
      resultEl.innerHTML = '';
      hint = st.fade ? 'Click another part, or empty space / Esc to bring the rest back.' : 'Click a part: it stays solid, the rest goes see-through.';
    }
    if (hintEl) hintEl.textContent = hint;
  }

  // labels: asked for one by one while drawing, then placed together so none covers another (task 0219)
  var labelEls = [], leadEls = [], labelAsk = [], labelBoxes = [];
  function label(k, text, at, colour) {
    var e = labelEls[k];
    if (!e) { e = labelEls[k] = el('div', { 'class': 'fr-lbl' }); marks.appendChild(e); }
    var s = screenOfWorld(at);
    if (e.textContent !== text) e.textContent = text;
    e.style.borderLeftColor = colour || '#F2A900';
    e.style.display = s.behind ? 'none' : 'block';
    e.className = colour ? 'fr-lbl' : 'fr-lbl fr-main';
    if (!s.behind) labelAsk.push({ e: e, x: s.x, y: s.y });
    return k + 1;
  }
  function placeLabels(dots) {
    var boxes = labelAsk.map(function (a) { return { x: a.x, y: a.y, w: a.e.offsetWidth || 60, h: a.e.offsetHeight || 20 }; });
    var fixed = dots.map(function (d) { return { x: d.x, y: d.y, w: 10, h: 10 }; });
    var at = M.layout(boxes, fixed), nLead = 0;
    labelBoxes = [];
    at.forEach(function (q, i) {
      var e = labelAsk[i].e;
      e.style.left = q.x + 'px'; e.style.top = q.y + 'px';
      labelBoxes.push({ x: q.x, y: q.y, w: boxes[i].w, h: boxes[i].h, text: e.textContent, moved: q.moved });
      if (!q.moved) return;
      var L = M.leader({ x: q.x, y: q.y, w: boxes[i].w, h: boxes[i].h }, labelAsk[i]), l = leadEls[nLead];
      if (!l) { l = leadEls[nLead] = el('div', { 'class': 'fr-lead' }); marks.insertBefore(l, marks.firstChild); }
      var dx = L[2] - L[0], dy = L[3] - L[1];
      l.style.left = L[0] + 'px'; l.style.top = L[1] + 'px'; l.style.width = Math.hypot(dx, dy) + 'px';
      l.style.transform = 'rotate(' + Math.atan2(dy, dx) + 'rad)';
      l.style.display = 'block';
      nLead++;
    });
    for (var i = nLead; i < leadEls.length; i++) leadEls[i].style.display = 'none';
    labelAsk = [];
  }
  var dotEls = [];
  function dot(k, at) {
    var e = dotEls[k];
    if (!e) { e = dotEls[k] = el('div', { 'class': 'fr-dot' }); marks.appendChild(e); }
    var s = screenOfWorld(at);
    e.style.left = s.x + 'px'; e.style.top = s.y + 'px';
    e.style.display = s.behind ? 'none' : 'block';
    return k + 1;
  }
  // edges drawn on the screen, 3 px wide (a WebGL line is 1 px): an SVG over the view
  var edgeSvg = null, edgeEls = [];
  function edgeLine(n, k, colour) {
    if (!edgeSvg) {
      edgeSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      edgeSvg.setAttribute('class', 'fr-edges');
      marks.insertBefore(edgeSvg, marks.firstChild);
    }
    var e = edgeEls[n];
    if (!e) { e = edgeEls[n] = document.createElementNS('http://www.w3.org/2000/svg', 'path'); edgeSvg.appendChild(e); }
    var d = '', pen = false;
    M.edgePoints(k, 64).forEach(function (q) {
      var sc = screenOfWorld(toWorld(q));
      if (sc.behind) { pen = false; return; }
      d += (pen ? 'L' : 'M') + sc.x.toFixed(1) + ' ' + sc.y.toFixed(1);
      pen = true;
    });
    e.setAttribute('d', d);
    e.setAttribute('stroke', colour);
    e.style.display = '';
    return n + 1;
  }
  function beforeDraw() {
    if (st.slices.length) { placeSlices(); drawHandles(); } else if (gz) gz.visible = false;
    var nl = 0, nd = 0, ne = 0, segs = [], cols = [], dots = [];
    labelAsk = [];
    if (hiEdge && st.tool === 'measure') {
      three.scene.updateMatrixWorld();
      var he = M.fromEdge(hiEdge.row, modelMatrix(hiEdge.mesh).elements, [0, 0, 0]);
      if (he) ne = edgeLine(ne, he, '#F2A900');
    }
    if (st.tool === 'measure' && st.picks.length) {
      three.scene.updateMatrixWorld();
      compute();
      if (result) {
        result.picks.forEach(function (p) {
          if (p.kind === 'line' || p.kind === 'circle') ne = edgeLine(ne, p, '#2F9BFF');
          var w = toWorld(p.p), sc = screenOfWorld(w);
          if (!sc.behind) dots.push(sc);
          nd = dot(nd, w);
        });
        if (result.from && result.to) {
          var a = toWorld(result.from), b = toWorld(result.to);
          segs.push(a, b); cols.push([0.95, 0.66, 0], [0.95, 0.66, 0]);
          var mid = a.clone().add(b).multiplyScalar(0.5);
          nl = label(nl, result.type === 'angle' ? M.angleText(result.angle) : M.mm(result.dist), mid);
          (result.parts || []).forEach(function (q) {
            var qa = toWorld(q.from), qb = toWorld(q.to), c = new T.Color(AXIS_COLOUR[q.axis]);
            segs.push(qa, qb); cols.push([c.r, c.g, c.b], [c.r, c.g, c.b]);
            // an arrow head: two short strokes back from the end, in the screen's plane
            var dir = qb.clone().sub(qa), l = dir.length();
            if (l > 1e-9) {
              dir.divideScalar(l);
              var side = new T.Vector3().crossVectors(dir, three.camera.getWorldDirection(tmpV)).normalize();
              var head = Math.min(l * 0.3, qb.distanceTo(three.camera.position) * 0.02);
              [-1, 1].forEach(function (s) {
                segs.push(qb, qb.clone().addScaledVector(dir, -head).addScaledVector(side, s * head * 0.45));
                cols.push([c.r, c.g, c.b], [c.r, c.g, c.b]);
              });
            }
            // one part only: it is the measurement itself (its number already stands there)
            if (result.parts.length > 1) nl = label(nl, q.text, qa.clone().add(qb).multiplyScalar(0.5), AXIS_COLOUR[q.axis]);
          });
        } else if (result.type === 'diameter') {
          nl = label(nl, 'Ø ' + M.mm(result.dist), toWorld(result.picks[0].p));
        }
      }
    }
    if (st.card) {
      three.scene.updateMatrixWorld();
      var s = screenOfWorld(st.card.mesh.localToWorld(st.card.local.clone()));
      card.style.left = s.x + 'px'; card.style.top = s.y + 'px';
      card.style.display = s.behind ? 'none' : 'block';
    }
    for (var i = nl; i < labelEls.length; i++) labelEls[i].style.display = 'none';
    for (i = ne; i < edgeEls.length; i++) edgeEls[i].style.display = 'none';
    placeLabels(dots);
    for (i = nd; i < dotEls.length; i++) dotEls[i].style.display = 'none';
    var g = lines.geometry;
    if (segs.length) {
      var pos = new Float32Array(segs.length * 3), col = new Float32Array(segs.length * 3);
      segs.forEach(function (v, k) { pos[3 * k] = v.x; pos[3 * k + 1] = v.y; pos[3 * k + 2] = v.z; });
      cols.forEach(function (c, k) { col[3 * k] = c[0]; col[3 * k + 1] = c[1]; col[3 * k + 2] = c[2]; });
      g.setAttribute('position', new T.BufferAttribute(pos, 3));
      g.setAttribute('color', new T.BufferAttribute(col, 3));
      lineMat.vertexColors = true;
      g.computeBoundingSphere();
    }
    lines.visible = segs.length > 0;
    if (st.tool === 'measure' && st.picks.length && page.frames % 10 === 0) refresh();
  }

  // ---------------------------------------------------------------- pointer: click, tap, long press, hover
  var downs = {}, nDown = 0, press = null, longTimer = null, hoverAt = null, hoverBusy = false, hoverCost = 0;
  function local(e) {
    var r = three.canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }
  function bind() {
    var c = three.canvas;
    // task 0218: a press on a slice's handle drags it – the view does not turn and nothing is clicked
    c.addEventListener('pointerdown', function (e) {
      if (drag || st.editing == null || (e.pointerType === 'mouse' && e.button !== 0)) return;
      var p = local(e), kind = handleAt(p.x, p.y, e.pointerType !== 'mouse');
      if (!kind || !startDrag(kind, p.x, p.y, e.pointerId)) return;
      e.stopImmediatePropagation(); e.preventDefault();
      try { c.setPointerCapture(e.pointerId); } catch (err) { /* fine */ }
    }, true);
    c.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      e.stopImmediatePropagation();
      var p = local(e);
      moveDrag(p.x, p.y);
    }, true);
    var endIt = function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      e.stopImmediatePropagation();
      endDrag();
    };
    c.addEventListener('pointerup', endIt, true);
    c.addEventListener('pointercancel', endIt, true);
    c.addEventListener('pointerdown', function (e) {
      downs[e.pointerId] = true; nDown++;
      pointerKind = e.pointerType || 'mouse';
      clearTimeout(longTimer);
      if (nDown > 1) { press = null; return; }
      var p = local(e);
      press = { x: p.x, y: p.y, t: performance.now(), button: e.button, long: false };
      if (e.pointerType === 'mouse') return;          // a slow mouse click is a click (a long press is for touch)
      longTimer = setTimeout(function () {
        if (press && nDown === 1) { press.long = true; onLongPress(press.x, press.y); }
      }, 550);
    });
    c.addEventListener('pointermove', function (e) {
      var p = local(e);
      if (press && Math.hypot(p.x - press.x, p.y - press.y) > 6) { clearTimeout(longTimer); press.moved = true; }
      if (e.pointerType === 'mouse' && !e.buttons && (st.tool || st.adding)) { pointerKind = 'mouse'; hover(p.x, p.y); }
    });
    var up = function (e) {
      if (downs[e.pointerId]) { delete downs[e.pointerId]; nDown = Math.max(0, nDown - 1); }
      clearTimeout(longTimer);
      var pr = press;
      press = null;
      if (!pr || pr.moved || pr.long || pr.button !== 0 || e.type === 'pointercancel') return;
      var p = local(e);
      if (Math.hypot(p.x - pr.x, p.y - pr.y) > 6) return;
      onClick(p.x, p.y);
    };
    c.addEventListener('pointerup', up);
    c.addEventListener('pointercancel', up);
    c.addEventListener('pointerleave', function () { if (st.tool || st.adding) setHover(null); });
    c.addEventListener('contextmenu', function (e) { if (press && press.long) e.preventDefault(); });
  }
  function hover(x, y) {                 // at most one look a frame; none while a look costs too much (big model)
    hoverAt = [x, y];
    if (hoverBusy || hoverCost > 40) return;
    hoverBusy = true;
    requestAnimationFrame(function () {
      hoverBusy = false;
      if (!hoverAt || !(st.tool || st.adding)) return;
      var t0 = performance.now();
      var hit = pickAt(hoverAt[0], hoverAt[1]);
      hoverCost = performance.now() - t0;
      if (hit) hit.run = runOf(hit.mesh, hit.faceIndex);
      if (hit && st.tool === 'measure' && !st.adding && st.mode === 'faces') hit.edge = edgeAt(hit, hoverAt[0], hoverAt[1], false);
      setHover(hit);
    });
  }

  // ---------------------------------------------------------------- keys
  window.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'TEXTAREA' || (tag === 'INPUT' && e.target.type !== 'range' && e.target.type !== 'checkbox')) return;
    var k = e.key, done = true;
    if (k === 'i' || k === 'I') setTool('info');
    else if (k === 'd' || k === 'D') setTool('measure');
    else if (k === 't' || k === 'T') setTool('fade');
    else if (k === 'c' || k === 'C') openSlices(!st.sliceOpen);
    else if ((k === 'x' || k === 'X') && st.tool === 'measure') { setXyz(!st.xyz); fillPanel(); }
    else if (k === 'Escape') { if (page.helpOpen || page.menuOpen) done = false; else escape(); }   // closes those first
    else done = false;
    if (done) { e.preventDefault(); page.lastKey = k; }
  }, true);                                // before the player's own keys (it closes the help on Esc)
  function escape() {
    if (drag) endDrag();
    else if (st.editing != null) editSlice(null);
    else if (st.adding) startAdding(false);
    else if (st.picks.length) clearMeasure();
    else if (st.card) closeCard();
    else if (st.fade) setFade(null);
    else if (st.tool) setTool(null);
    else if (st.sliceOpen) openSlices(false);             // the slices stay on
    refresh();
  }

  // ---------------------------------------------------------------- tests and the PC check
  page.partTools = {
    state: function () {
      var r = compute();
      return { tool: st.tool, mode: st.mode, xyz: st.xyz, picks: st.picks.length,
               slices: st.slices.map(sliceState), sliceOpen: st.sliceOpen, adding: st.adding,
               editing: st.editing != null ? (sliceById(st.editing) || {}).num || null : null,
               handles: !!(gz && gz.visible), cutting: live.length,
               card: st.card ? { text: st.card.text, face: st.card.face, shown: card.style.display !== 'none',
                                 html: card.textContent } : null,
               fade: st.fade ? String(st.fade.userData.fr_card || st.fade.name) : null, faded: faded.size,
               faces: !!faces, hover: st.hover || '',
               result: r ? { type: r.type, dist: r.dist, angle: r.angle, lines: r.lines,
                             parts: (r.parts || []).map(function (q) { return [q.axis, q.value]; }),
                             picks: r.picks.map(function (p) { return { kind: p.kind, r: p.r || 0, p: p.p, len: p.len || 0,
                                                                         c: p.c || null, sweep: p.sweep || 0 }; }) } : null,
               lines: lines ? lines.visible : false,
               labels: labelEls.filter(function (e) { return e.style.display !== 'none'; }).map(function (e) { return e.textContent; }),
               // task 0219: where the labels stand on the screen (tests check that none covers another)
               labelBoxes: labelBoxes.map(function (b) { return { x: b.x, y: b.y, w: b.w, h: b.h, text: b.text, moved: b.moved }; }),
               leaders: leadEls.filter(function (e) { return e.style.display !== 'none'; }).length,
               hoverEdge: !!hiEdge,
               edgesDrawn: edgeEls.filter(function (e) { return e.style.display !== 'none' && e.getAttribute('d'); }).length,
               clipped: ready ? materials().filter(function (m) { return m.clippingPlanes && m.clippingPlanes.length; }).length : 0,
               // every cut material uses the one live plane (not a copy left where the slider was)
               stale: ready ? materials().filter(function (m) {
                 return m.clippingPlanes && m.clippingPlanes.length && (m.clippingPlanes.length !== live.length ||
                   m.clippingPlanes.some(function (p, i) { return p !== live[i]; })); }).length : 0 };
    },
    hover: function (x, y) {             // as a mouse resting there (the next frame lights the face or edge up)
      var h = pickAt(x, y);
      if (h) { h.run = runOf(h.mesh, h.faceIndex); if (st.tool === 'measure' && st.mode === 'faces') h.edge = edgeAt(h, x, y, false); }
      setHover(h);
      return st.hover || '';
    },
    // a point of the model (Blender's world, metres) on the screen (CSS pixels of the view)
    screenOf: function (a) { three.scene.updateMatrixWorld(); return screenOfWorld(toWorld(a)); },
    pickAt: function (x, y) {
      var h = pickAt(x, y);
      if (!h) return null;
      if (st.mode === 'faces' && !h.tube && !h.cap) { h.run = runOf(h.mesh, h.faceIndex); h.edge = edgeAt(h, x, y, false); }
      var k = keep(h), p = pickNow(k);
      return { card: String(h.part.userData.fr_card || ''), name: h.part.name, kind: p.kind, r: p.r || 0, p: p.p,
               n: p.n || null, d: p.d || null, len: p.len || 0, c: p.c || null, sweep: p.sweep || 0 };
    },
    click: function (x, y) { onClick(x, y); return page.partTools.state(); },
    longPress: function (x, y) { onLongPress(x, y); return page.partTools.state(); },
    setTool: function (t) { if (st.tool !== t) setTool(t); return st.tool; },
    // slices (task 0218); a slice is named by its number ("Slice 2")
    openSlices: function (on) { openSlices(on); return st.sliceOpen; },
    addAcross: function (axis, frac, flip) {
      if (!st.sliceOpen) openSlices(true);
      var s = addAcross(axis, frac);
      if (s && flip) change(s.id, { flip: true });
      return s ? sliceState(s) : null;
    },
    addAt: function (x, y) {             // as "Add slice" + a click there
      if (!st.sliceOpen) openSlices(true);
      startAdding(true); onClick(x, y);
      return page.partTools.state();
    },
    change: function (num, patch) { var s = byNum(num); if (s) change(s.id, patch); return s ? sliceState(s) : null; },
    edit: function (num) { var s = byNum(num); editSlice(s ? s.id : null); return st.editing; },
    hide: function (num, hidden) { var s = byNum(num); if (s) setHidden(s.id, hidden); return s ? sliceState(s) : null; },
    remove: function (num) { var s = byNum(num); if (s) deleteSlice(s.id); return st.slices.length; },
    // the screen points of the handles of the slice being edited (tests drag them)
    handles: function () {
      three.scene.updateMatrixWorld();
      var H = handles();
      if (!H) return null;
      var f = function (v) { var p = screenOfWorld(v); return [p.x, p.y]; };
      return { a: f(H.ka), b: f(H.kb), t: f(H.q.clone().addScaledVector(H.n, H.L / 2)), q: f(H.q) };
    },
    escape: escape
  };

  function byNum(num) {
    for (var i = 0; i < st.slices.length; i++) if (st.slices[i].num === num) return st.slices[i];
    return null;
  }
  function sliceState(s) {
    var P = M.slice.plane(s);
    return { num: s.num, how: s.how, n: P.n, q: P.q, t: s.t, a: s.a, b: s.b, flip: s.flip, hidden: s.hidden,
             cuts: live.indexOf(s.plane) >= 0 };
  }

  function selftest() {                    // ?selftest=1: the tools on the page itself (data-fr-tools on <html>)
    var r = { faces: !!faces, buttons: col.querySelectorAll('button').length };
    var c = three.canvas, w = c.clientWidth, h = c.clientHeight, found = null;
    for (var i = 0; i < 25 && !found; i++) {           // a part somewhere near the middle of the view
      var x = w * (0.3 + 0.1 * (i % 5)), y = h * (0.3 + 0.1 * Math.floor(i / 5));
      if (pickAt(x, y)) found = [x, y];
    }
    r.pick = !!found;
    if (found) {
      setTool('info'); onClick(found[0], found[1]); r.card = !!st.card; closeCard();
      setTool('measure'); onClick(found[0], found[1]); onClick(found[0] + 3, found[1] + 3);
      var m = compute(); r.measure = !!(m && isFinite(m.dist)); clearMeasure();
      setTool('fade'); onClick(found[0], found[1]); r.fade = faded.size >= 0 && !!st.fade; setFade(null); setTool(null);
    }
    // task 0218: six slices cut together, then none
    openSlices(true);
    ['X', 'Y', 'Z', 'X', 'Y', 'Z'].forEach(function (a, i) { addAcross(a, i < 3 ? 0.1 : 0.9); });
    r.slices = st.slices.length;
    r.slice = r.slices === 6 && materials().every(function (m) { return m.clippingPlanes && m.clippingPlanes.length === 6; });
    st.slices.slice().forEach(function (s) { deleteSlice(s.id); });
    r.slice = r.slice && live.length === 0 && materials().every(function (m) { return !m.clippingPlanes || !m.clippingPlanes.length; });
    openSlices(false);
    // task 0219: the edges read from the file, and two labels on one spot laid out apart
    r.edges = 0;
    Object.keys(faceMeshes).forEach(function (k) {
      var E = faceMeshes[k].edges;
      for (var at = 0; E && at + 9 <= E.length; at += Math.round(E[at]) === 5 ? 12 : 9) r.edges++;
    });
    var lay = M.layout([{ x: 50, y: 50, w: 80, h: 20 }, { x: 52, y: 51, w: 80, h: 20 }], []);
    r.labels = !M.overlaps({ x: lay[0].x, y: lay[0].y, w: 80, h: 20 }, { x: lay[1].x, y: lay[1].y, w: 80, h: 20 }, 0);
    r.ok = r.buttons === 4 && r.pick && r.card && r.measure && r.fade && r.slice && r.labels;
    root.dataset.frTools = JSON.stringify(r);
  }

  function start() {
    if (ready || !page.three) return;
    setup();
    bind();
    if (Q.get('selftest') === '1') {
      // face data comes in a moment after the page is ready (accessors are read once)
      var go = function () { try { selftest(); } catch (e) { root.dataset.frTools = JSON.stringify({ ok: false, error: String(e) }); } };
      if (facesLoaded) facesLoaded.then(go, go); else go();
    }
  }
  page.listeners.push(function (what) { if (what === 'ready') start(); else if (what === 'items' && ready) clip(materials()); });
  if (page.ready) start();
  pressed();
})();
