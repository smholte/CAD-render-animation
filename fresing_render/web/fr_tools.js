// Fresing Render web 3D player: the part tools (task 0135). A column of four buttons on the left of the 3D view:
//
//   Part info (I)        click a part: a card at it with its label or name (pages exported with Hide part names: the
//                        part's material group, never its name) and what the clicked face is (flat, round Ø …)
//   Measure (D)          two clicks. Faces (default): two flat faces – the distance between the planes (parallel
//                        within 1°) or the angle between them; two round faces – centre to centre (between the
//                        axes); a flat and a round face – from the plane to the axis; one round face – its
//                        diameter. Points: the straight distance between the two clicked points. X / Y / Z parts (X):
//                        every measurement also as three arrows in the axis colours, each with its own number
//   Cutaway (C)          one plane across X, Y or Z, moved by a slider, Flip keeps the other side; the cut faces show
//                        the app's cap colour. Only the model is cut (not the sea, the sky or the seabed); the plane
//                        moves with the vessel
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
    '#fr-parts { position: absolute; left: 12px; top: calc(var(--fr-top, 0px) + 50px); z-index: 3; display: flex;',
    '  flex-direction: column; gap: 6px; }',
    '#fr-parts .fr-btn { padding: 0; width: 40px; height: 40px; }',
    '#fr-tpanel { position: absolute; left: 62px; top: calc(var(--fr-top, 0px) + 50px); z-index: 4;',
    '  width: min(300px, calc(100vw - 140px)); max-height: calc(100% - var(--fr-top, 0px) - 160px); overflow: auto;',
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
    '#fr-marks .fr-dot { position: absolute; width: 10px; height: 10px; margin: -5px 0 0 -5px; border-radius: 50%;',
    '  background: #F2A900; border: 2px solid #fff; box-sizing: border-box; }',
    '#fr-card { position: absolute; z-index: 3; transform: translate(-50%, calc(-100% - 12px)); display: none;',
    '  background: rgba(20,28,34,.92); color: #F4F6F8; border-radius: 6px; padding: 6px 10px; max-width: min(280px, 80vw);',
    '  font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; pointer-events: none; box-shadow: 0 3px 12px rgba(0,0,0,.35); }',
    '#fr-card b { display: block; font-weight: 600; overflow-wrap: anywhere; }',
    '#fr-card span { color: #D5DBE0; font-size: 12px; }',
    'html.fr-clean #fr-parts, html.fr-clean #fr-tpanel { display: none !important; }',
    '@media (max-width: 600px) { #fr-parts { top: calc(var(--fr-top, 0px) + 70px); left: 8px; }',
    '  #fr-tpanel { left: 8px; right: 8px; width: auto; top: auto; bottom: 8px; max-height: 42%; z-index: 5; } }',
    '@media (max-height: 480px) { #fr-parts { top: calc(var(--fr-top, 0px) + 44px); gap: 4px; }',
    '  #fr-parts .fr-btn { width: 34px; height: 34px; min-height: 34px; min-width: 34px; }',
    '  #fr-tpanel { left: 54px; top: calc(var(--fr-top, 0px) + 44px); max-height: calc(100% - var(--fr-top, 0px) - 52px); } }'
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
    cut: { on: false, axis: 'X', flip: false, at: 0.5 },
    picks: [],                                    // measure: {mesh, local, row, run} (follows its part)
    card: null,                                   // {mesh, local, part, text, face}
    fade: null,                                   // the part that stays solid
    hover: null
  };
  page.toolPrefs = function () { return { mode: st.mode, xyz: st.xyz }; };
  page.toolKeys = [['I', 'part info: click a part'], ['D', 'measure: click two faces or points'],
                   ['X', 'X / Y / Z parts of a measurement'], ['C', 'cutaway'], ['T', 'fade the rest: click a part'],
                   ['Esc', 'clear the measurement / card / fade, then close the tool']];

  // ---------------------------------------------------------------- the column and the panel
  var col = el('div', { id: 'fr-parts', role: 'toolbar', 'aria-label': 'Part tools' });
  var btn = {
    info: button('info', 'Part info: click a part', 'I', function () { setTool('info'); }, col),
    measure: button('ruler', 'Measure: click two faces or points', 'D', function () { setTool('measure'); }, col),
    cut: button('cut', 'Cutaway', 'C', function () { setCut(!st.cut.on); }, col),
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
    btn.cut.setAttribute('aria-pressed', st.cut.on ? 'true' : 'false');
  }
  var resultEl = null, hintEl = null, slider = null;
  function fillPanel() {
    panel.innerHTML = '';
    if (!st.tool && !st.cut.on) { panel.style.display = 'none'; pressed(); return; }
    panel.style.display = 'block';
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
    if (st.cut.on) {
      var h3 = el('h3', {}, 'Cutaway');
      panel.appendChild(h3);
      var cs = el('div', { 'class': 'fr-seg', role: 'group', 'aria-label': 'Cut across' });
      ['X', 'Y', 'Z'].forEach(function (a) {
        var b = button('', a, '', function () { st.cut.axis = a; updateCut(); fillPanel(); }, cs);
        b.dataset.axis = a;
        b.title = 'Cut across the ' + a + ' axis';
        b.setAttribute('aria-pressed', st.cut.axis === a ? 'true' : 'false');
      });
      var fb = button('', 'Flip', '', function () { st.cut.flip = !st.cut.flip; updateCut(); fillPanel(); }, cs);
      fb.id = 'fr-cut-flip';
      fb.title = 'Keep the other side';
      fb.setAttribute('aria-pressed', st.cut.flip ? 'true' : 'false');
      panel.appendChild(cs);
      slider = el('input', { type: 'range', min: '0', max: '1', step: '0.001', id: 'fr-cut', 'aria-label': 'Where the cut is' });
      slider.value = String(st.cut.at);
      slider.addEventListener('input', function () { st.cut.at = +slider.value; updateCut(); });
      panel.appendChild(slider);
      var off = button('', 'Cutaway off', '', function () { setCut(false); }, panel);
      off.id = 'fr-cut-off';
    }
    pressed();
    refresh();
  }

  // ---------------------------------------------------------------- the 3D side (once the page is ready)
  var facesLoaded = null;
  var three = null, ray = null, faces = null, faceMeshes = {}, primStart = {}, ready = false;
  var hiPart = null, hiFace = null, pickFaces = [];     // highlight overlays
  var HI = null, HI_FACE = null, HI_PICK = null, lineMat = null, lines = null, arrows = [];
  var cutPlane = null, cutLocal = null, cutMats = [];
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
    cutPlane = new T.Plane();
    cutLocal = new T.Plane();
    // the face data: two accessors per mesh (runs, rows), read once
    var json = page.gltf && page.gltf.parser && page.gltf.parser.json;
    var fx = json && json.extras && json.extras.fr_faces;
    if (fx && fx.meshes) {
      var keys = Object.keys(fx.meshes);
      var jobs = keys.map(function (k) {
        var a = fx.meshes[k];
        return Promise.all([page.gltf.parser.getDependency('accessor', a[0]), page.gltf.parser.getDependency('accessor', a[1])])
          .then(function (r) { faceMeshes[k] = { runs: r[0].array, rows: r[1].array }; });
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
    var hits = ray.intersectObjects(targets(), false);
    for (var i = 0; i < hits.length; i++) {
      var hit = hits[i];
      if (st.cut.on && cutPlane.distanceToPoint(hit.point) < 0) continue;      // in the part cut away
      if (!shown(hit.object)) continue;
      var part = partOf(hit.object);
      if (!part) continue;
      return { mesh: hit.object, point: hit.point.clone(), faceIndex: hit.faceIndex, part: part };
    }
    return null;
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
             prim: as.primitives || 0, starts: starts };
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
  function screenOfWorld(v) {
    three.camera.updateMatrixWorld();
    var p = v.clone().project(three.camera), c = three.canvas;
    return { x: (p.x + 1) / 2 * c.clientWidth, y: (1 - p.y) / 2 * c.clientHeight, behind: p.z > 1 };
  }

  // a stored click (mesh, its own point, its face) -> the measuring pick now (the part may have moved)
  function pickNow(k) {
    var w = k.mesh.localToWorld(k.local.clone());
    var p = M.fromRow(k.run ? k.run.row : null, modelMatrix(k.mesh).elements, toModel(w));
    p.face = k.run ? k.run.row[0] : 0;
    return p;
  }
  function keep(hit) {
    return { mesh: hit.mesh, local: hit.mesh.worldToLocal(hit.point.clone()), part: hit.part,
             run: runOf(hit.mesh, hit.faceIndex) };
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
    var key = hit ? (st.tool === 'measure' && hit.run ? hit.mesh.uuid + ':' + hit.run.first : hit.part.uuid) : '';
    if (key === (st.hover || '')) return;
    st.hover = key;
    clearOverlay(hiPart); hiPart = null;
    clearOverlay(hiFace); hiFace = null;
    if (hit) {
      if (st.tool === 'measure' && hit.run) hiFace = overlayFace(hit.mesh, hit.run, HI_FACE);
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
  function clip(list) {
    list.forEach(function (m) {
      var want = st.cut.on ? [cutPlane] : null;
      if ((m.clippingPlanes && m.clippingPlanes.length ? 1 : 0) !== (want ? 1 : 0)) {
        m.clippingPlanes = want;
        m.clipShadows = !!want;
        m.needsUpdate = true;
      }
    });
  }
  function updateCut() {
    if (!ready) return;
    var mn = page.settings.model.min, mx = page.settings.model.max, i = { X: 0, Y: 1, Z: 2 }[st.cut.axis];
    var at = mn[i] + (mx[i] - mn[i]) * T.MathUtils.clamp(st.cut.at, 0, 1);
    var n = [0, 0, 0];
    n[i] = st.cut.flip ? 1 : -1;            // kept: below the plane (Flip: above it)
    cutLocal.normal.set(n[0], n[2], -n[1]);
    cutLocal.constant = st.cut.flip ? -at : at;
    three.vessel.updateMatrixWorld();
    cutPlane.copy(cutLocal).applyMatrix4(three.vessel.matrixWorld);
    page.wake();
  }
  function setCut(on) {
    st.cut.on = !!on;
    if (ready) {
      three.renderer.localClippingEnabled = st.cut.on;
      updateCut();
      clip(materials().concat([HI, HI_FACE, HI_PICK]));
    }
    fillPanel();
    page.wake();
  }

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
    if (st.tool === 'info' || (!st.tool && st.card)) {
      if (hit) openCard(hit); else closeCard();
    } else if (st.tool === 'fade') {
      setFade(hit ? hit.part : null);
    } else if (st.tool === 'measure') {
      if (!hit) { clearMeasure(); return; }
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
      else if (!st.picks.length) hint = st.mode === 'faces' ? 'Click a face: flat or round (a round face shows its diameter).' : 'Click a first point.';
      else if (st.picks.length === 1) hint = st.mode === 'faces' ? 'Click a second face, or a round face’s diameter is shown.' : 'Click a second point.';
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

  var labelEls = [];
  function label(k, text, at, colour) {
    var e = labelEls[k];
    if (!e) { e = labelEls[k] = el('div', { 'class': 'fr-lbl' }); marks.appendChild(e); }
    var s = screenOfWorld(at);
    e.textContent = text;
    e.style.borderLeftColor = colour || '#F2A900';
    e.style.left = s.x + 'px'; e.style.top = s.y + 'px';
    e.style.display = s.behind ? 'none' : 'block';
    e.className = colour ? 'fr-lbl' : 'fr-lbl fr-main';
    return k + 1;
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
  function beforeDraw() {
    if (st.cut.on) {
      three.vessel.updateMatrixWorld();
      cutPlane.copy(cutLocal).applyMatrix4(three.vessel.matrixWorld);
    }
    var nl = 0, nd = 0, segs = [], cols = [];
    if (st.tool === 'measure' && st.picks.length) {
      three.scene.updateMatrixWorld();
      compute();
      if (result) {
        result.picks.forEach(function (p) { nd = dot(nd, toWorld(p.p)); });
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
    c.addEventListener('pointerdown', function (e) {
      downs[e.pointerId] = true; nDown++;
      clearTimeout(longTimer);
      if (nDown > 1) { press = null; return; }
      var p = local(e);
      press = { x: p.x, y: p.y, t: performance.now(), button: e.button, long: false };
      longTimer = setTimeout(function () {
        if (press && nDown === 1) { press.long = true; onLongPress(press.x, press.y); }
      }, 550);
    });
    c.addEventListener('pointermove', function (e) {
      var p = local(e);
      if (press && Math.hypot(p.x - press.x, p.y - press.y) > 6) { clearTimeout(longTimer); press.moved = true; }
      if (e.pointerType === 'mouse' && !e.buttons && st.tool) hover(p.x, p.y);
    });
    var up = function (e) {
      if (downs[e.pointerId]) { delete downs[e.pointerId]; nDown = Math.max(0, nDown - 1); }
      clearTimeout(longTimer);
      var pr = press;
      press = null;
      if (!pr || pr.moved || pr.long || pr.button !== 0 || e.type === 'pointercancel') return;
      var p = local(e);
      if (Math.hypot(p.x - pr.x, p.y - pr.y) > 6 || performance.now() - pr.t > 700) return;
      onClick(p.x, p.y);
    };
    c.addEventListener('pointerup', up);
    c.addEventListener('pointercancel', up);
    c.addEventListener('pointerleave', function () { if (st.tool) setHover(null); });
    c.addEventListener('contextmenu', function (e) { if (press && press.long) e.preventDefault(); });
  }
  function hover(x, y) {                 // at most one look a frame; none while a look costs too much (big model)
    hoverAt = [x, y];
    if (hoverBusy || hoverCost > 40) return;
    hoverBusy = true;
    requestAnimationFrame(function () {
      hoverBusy = false;
      if (!hoverAt || !st.tool) return;
      var t0 = performance.now();
      var hit = pickAt(hoverAt[0], hoverAt[1]);
      hoverCost = performance.now() - t0;
      if (hit) hit.run = runOf(hit.mesh, hit.faceIndex);
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
    else if (k === 'c' || k === 'C') setCut(!st.cut.on);
    else if ((k === 'x' || k === 'X') && st.tool === 'measure') { setXyz(!st.xyz); fillPanel(); }
    else if (k === 'Escape') escape();
    else done = false;
    if (done) { e.preventDefault(); page.lastKey = k; }
  });
  function escape() {
    if (st.picks.length) clearMeasure();
    else if (st.card) closeCard();
    else if (st.fade) setFade(null);
    else if (st.tool) setTool(null);
    else if (st.cut.on) setCut(false);
    refresh();
  }

  // ---------------------------------------------------------------- tests and the PC check
  page.partTools = {
    state: function () {
      var r = compute();
      return { tool: st.tool, mode: st.mode, xyz: st.xyz, cut: Object.assign({}, st.cut), picks: st.picks.length,
               card: st.card ? { text: st.card.text, face: st.card.face, shown: card.style.display !== 'none',
                                 html: card.textContent } : null,
               fade: st.fade ? String(st.fade.userData.fr_card || st.fade.name) : null, faded: faded.size,
               faces: !!faces, hover: st.hover || '',
               result: r ? { type: r.type, dist: r.dist, angle: r.angle, lines: r.lines,
                             parts: (r.parts || []).map(function (q) { return [q.axis, q.value]; }),
                             picks: r.picks.map(function (p) { return { kind: p.kind, r: p.r || 0, p: p.p }; }) } : null,
               lines: lines ? lines.visible : false,
               labels: labelEls.filter(function (e) { return e.style.display !== 'none'; }).map(function (e) { return e.textContent; }),
               clipped: ready ? materials().filter(function (m) { return m.clippingPlanes && m.clippingPlanes.length; }).length : 0 };
    },
    // a point of the model (Blender's world, metres) on the screen (CSS pixels of the view)
    screenOf: function (a) { three.scene.updateMatrixWorld(); return screenOfWorld(toWorld(a)); },
    pickAt: function (x, y) {
      var h = pickAt(x, y);
      if (!h) return null;
      var k = keep(h), p = pickNow(k);
      return { card: String(h.part.userData.fr_card || ''), name: h.part.name, kind: p.kind, r: p.r || 0, p: p.p,
               n: p.n || null, d: p.d || null };
    },
    click: function (x, y) { onClick(x, y); return page.partTools.state(); },
    longPress: function (x, y) { onLongPress(x, y); return page.partTools.state(); },
    setTool: function (t) { if (st.tool !== t) setTool(t); return st.tool; },
    setCut: function (on, axis, at, flip) {
      if (axis) st.cut.axis = axis;
      if (at != null) st.cut.at = at;
      if (flip != null) st.cut.flip = !!flip;
      setCut(on);
      return Object.assign({}, st.cut);
    },
    escape: escape
  };

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
    setCut(true); r.cut = materials().some(function (m) { return m.clippingPlanes && m.clippingPlanes.length; }); setCut(false);
    r.ok = r.buttons === 4 && r.pick && r.card && r.measure && r.fade && r.cut;
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
