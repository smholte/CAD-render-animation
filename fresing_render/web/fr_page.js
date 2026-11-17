// Fresing Render web 3D page with surroundings (task 0106). Reads the settings block (#fr-env), the model (#fr-glb)
// and the pictures (#fr-pic-*) written by core/web3d_env.py, and shows the machine with its sea, vessel motion,
// sky, clouds, haze, rain, spray and a live sun – each only when the settings ask for it. Uses FRTHREE (three.js
// r180, three-viewer.min.js) and FRMath (fr_math.js). Nothing is fetched from the internet.
//
// URL options (for tests and for looking): ?quality=PHONE|BALANCED|BEST  ?auto=0  ?t=<seconds> (time stands still)
// ?orbit=<theta deg>,<phi deg>,<distance in model radii>  ?probe=<x>,<y>;<x>,<y>… (screen places 0 … 1 from the top
// left: their pixel colours after each frame go into data-fr-probe on <html>, for tests)
// Task 0134 (the player; fr_player.js draws its controls): ?at=<x>,<y>,<z> (the point the view turns about, three's
// coordinates, m) ?time=<s> (the moment to start at) ?paused=1 ?speed=0.5|1|2 ?off=sea,haze,… (items switched off)
// ?turn=1 (auto-turn) ?soft=0 (tests: never judge the browser as drawing without a graphics card) ?fov=<deg>.
// Task 0175: ?places=1 (the animated nodes' places into data-fr-places), ?b64=slow (the old per-letter model read).
// Task 0142: ?tubes=1 (the drawn cables' centre lines after each frame into data-fr-tubes, Blender world, for tests).
//
// Drawing (task 0134): at most 60 pictures a second (30 without a graphics card); a picture only when something
// changed – the view moves, the animation, sea, vessel or rain plays, a menu choice, the window's size – and none
// while the tab is hidden. Auto quality judges only pictures drawn one after the other (a pause, a hidden tab or a
// frozen page is not a slow picture: before 0134 the time a tab spent hidden counted as one long frame, and Auto
// lowered the quality when the visitor came back) and steps up again when there is room.
//
// Baked light (task 0107, settings ``light`` = {light: SOFT | ALL, scale, curve}): parts whose material has an
// occlusion map read through UV channel 1, or whose mesh has the attribute _FR_LIGHT, get their matte sky light
// from it (bakedLight below). ``plain``: Surroundings None with baked light – no sky drawn, the light background
// of the model-viewer page; the sky or the light picture still lights the model.
(function () {
  'use strict';
  var T = window.FRTHREE, M = window.FRMath;
  var ST = JSON.parse(document.getElementById('fr-env').textContent);
  var Q = new URLSearchParams(location.search);
  var LEVELS = ['PHONE', 'BALANCED', 'BEST'];
  var plain = !!ST.plain;
  var probes = (Q.get('probe') || '').split(';').map(function (p) { return p.split(',').map(parseFloat); })
    .filter(function (p) { return p.length === 2 && isFinite(p[0]) && isFinite(p[1]); });
  var page = window.frPage = { ready: false, settings: ST, level: null, fps: 0, frames: 0, errors: [], lowered: 0,
                               info: {}, light: { light: null, materials: 0, meshes: 0, plain: plain },
                               paused: false, time: 0,     // task 0111: a page around it may pause the motion
                               // task 0134: the player (fr_player.js reads and sets these)
                               raised: 0, speed: 1, duration: 0, animated: false, auto: false, quality: 'AUTO',
                               warned: '', gpu: '', cap: 60, items: [], on: {}, views: [], turn: false,
                               turning: false, sunLive: false, sunHour: 13, sunWhy: '', listeners: [],
                               beforeDraw: [] };   // task 0135: the part tools' work before each picture
  // what the visitor chose last time on this page (fr_player.js writes it; the link's own choices come first)
  var PREF_KEY = 'fresing-player:' + (location.pathname || document.title);
  var PREF = {};
  try { PREF = JSON.parse(window.localStorage.getItem(PREF_KEY) || '{}') || {}; } catch (e) { PREF = {}; }
  // 0147 row 16: a remembered field of the wrong type (a corrupt write, another version under the same key) stopped
  // the page for good – every field is checked and a bad one dropped
  PREF = (function (p) {
    var ok = {};
    if (!p || typeof p !== 'object' || Array.isArray(p)) return ok;
    if (typeof p.quality === 'string') ok.quality = p.quality;
    if (Array.isArray(p.off)) ok.off = p.off.filter(function (x) { return typeof x === 'string'; });
    if (Array.isArray(p.chose)) ok.chose = p.chose.filter(function (x) { return typeof x === 'string'; });
    if (typeof p.turn === 'boolean') ok.turn = p.turn;
    if (typeof p.speed === 'number' && isFinite(p.speed)) ok.speed = p.speed;
    if (p.tools && typeof p.tools === 'object' && !Array.isArray(p.tools)) ok.tools = p.tools;   // task 0135
    return ok;
  })(PREF);
  page.prefKey = PREF_KEY;
  page.pref = PREF;
  function changed(what) {                  // tell the player (menu, time line) that something changed
    for (var i = 0; i < page.listeners.length; i++) {
      try { page.listeners[i](what); } catch (e) { /* a broken listener never stops the page */ }
    }
  }
  // the page's state in its own HTML (data-fr-state on <html>): the PC check reads it with a headless browser
  function mark() {
    var root = document.documentElement.dataset;
    root.frState = page.errors.length ? 'error: ' + page.errors.join(' | ').slice(0, 300)
      : page.ready ? 'ready ' + page.level + ' frames ' + page.frames : 'loading';
    if (ST.light || plain) root.frLight = JSON.stringify(page.light);
    root.frPlayer = JSON.stringify({ warned: page.warned, gpu: page.gpu, level: page.level, auto: page.auto,
                                     paused: page.paused, duration: page.duration, views: page.views.length,
                                     items: page.items, fps: Math.round(page.fps * 10) / 10, raised: page.raised,
                                     lowered: page.lowered, frames: page.frames,
                                     under: page.underState ? page.underState() : null });
  }
  page.mark = mark;
  window.addEventListener('error', function (e) { page.errors.push(String(e.message || e)); mark(); });
  window.addEventListener('unhandledrejection', function (e) {
    fail('The 3D model in this page could not be shown.', String(e.reason && e.reason.message || e.reason));
  });

  // what went wrong: shown on the page (``text``; default: no WebGL) and kept in frPage.errors / data-fr-state
  function fail(text, why) {
    document.getElementById('loading').style.display = 'none';
    var f = document.getElementById('fail');
    if (text) f.textContent = text;
    f.style.display = 'flex';
    page.errors.push(String(why || text));
    mark();
  }

  // Blender world (x, y, z up) -> three (x, y up, z = -y)
  function b2t(v) { return new T.Vector3(v[0], v[2], -v[1]); }
  var B2T = new T.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1);
  var T2B = B2T.clone().invert();

  // ---------------------------------------------------------------- renderer, scene, camera
  var canvas = document.getElementById('view');
  var renderer;
  try {
    // plain form: a see-through canvas over the page's light background (as the model-viewer page)
    renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, powerPreference: 'high-performance',
                                     alpha: plain, preserveDrawingBuffer: probes.length > 0 });
  } catch (e) {              // no WebGL: the page says so; the PC check does not count it as the page's fault
    fail('', 'no-webgl: ' + e);
    document.documentElement.dataset.frState = 'no-webgl';
    return;
  }
  renderer.outputColorSpace = T.SRGBColorSpace;
  renderer.toneMapping = T.AgXToneMapping;
  renderer.toneMappingExposure = Math.pow(2, ST.sky.exposure || 0) * 1.15;
  renderer.shadowMap.enabled = !!ST.shadows;
  renderer.shadowMap.type = T.PCFSoftShadowMap;
  if (plain) renderer.setClearColor(0x000000, 0);
  // a shader that does not compile is the page's fault: say so (three only writes it to the console)
  renderer.debug.onShaderError = function (g, program, vs, fs) {
    var log = [vs, fs].map(function (sh) { return g.getShaderInfoLog(sh) || ''; }).join(' ').trim();
    page.errors.push('shader: ' + (log || g.getProgramInfoLog(program) || 'did not compile').slice(0, 200));
    mark();
  };
  var gl = renderer.getContext();
  var dbg = gl.getExtension('WEBGL_debug_renderer_info');
  page.info.webgl = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'webgl';
  // task 0134: a browser that draws without the graphics card (Chrome after a graphics-card reset: "Microsoft Basic
  // Render Driver", WARP; headless browsers: SwiftShader; Linux without a driver: llvmpipe) – say so, draw lightly
  page.gpu = dbg ? String(page.info.webgl || '') : '';
  var SOFTWARE = /basic render|warp|swiftshader|llvmpipe|softpipe|software/i;
  if (page.gpu && SOFTWARE.test(page.gpu) && Q.get('soft') !== '0') page.warned = 'software';

  var scene = new T.Scene();
  var mn = b2t(ST.model.min), mx = b2t(ST.model.max);
  var box = new T.Box3().setFromPoints([mn, mx]);
  var centre = box.getCenter(new T.Vector3());
  var R = Math.max(box.getSize(new T.Vector3()).length() / 2, 0.05);
  var floorY = ST.floor != null ? ST.floor : ST.model.min[2];
  var hasSea = !!ST.sea;
  var camera = new T.PerspectiveCamera(30, 1, R * 0.01, hasSea ? 30000 : R * 400);

  // ---------------------------------------------------------------- under the sea (task 0143)
  // ST.under (the open sea only): the seabed, the cut-away box behind the stern (a box of water taken away, from the
  // sky down to the seabed), the soil section under it (0148) and the water's clarity. What the camera sees through
  // water fades into the water's colour as in the app (core/sea.py): seen = behind x T + colour x (1 - T),
  // T = e^(-sigma d), d = the metres of the straight line from the camera that lie under the water's level and
  // outside the box. Every material gets that through three's fog chunks (USE_FOG): with ST.under the page's fog is
  // a plain Fog whose ``near`` carries the haze's density (0: none) and ``far`` the water's light (0: off), so the
  // menu switches it without compiling a program again. The numbers of the box and the water are written into the
  // shader as constants (one page = one project).
  var UW = hasSea && ST.under ? ST.under : null;
  var uwLevel = UW ? UW.bed + UW.depth : 0;              // three y of the water's level and of the seabed
  var uwBed = UW ? UW.bed : 0;
  var uwCut = UW && UW.cut ? UW.cut : null, uwGround = uwCut && UW.ground ? UW.ground : null;
  var uwO = uwCut ? new T.Vector2(uwCut.origin[0], -uwCut.origin[1]) : null;     // three (x, z) of the box's front
  var uwU = uwCut ? new T.Vector2(uwCut.dir[0], -uwCut.dir[1]) : null;           // aft
  var uwV = uwCut ? new T.Vector2(-uwU.y, uwU.x) : null;                          // across
  function inBox(x, z) {                  // a three (x, z) inside the cut-away box
    if (!uwCut) return false;
    var dx = x - uwO.x, dz = z - uwO.y, a = dx * uwU.x + dz * uwU.y, b = dx * uwV.x + dz * uwV.y;
    return a > 0 && a < uwCut.length && Math.abs(b) < uwCut.width / 2;
  }
  function glf(v) { v = +v; return isFinite(v) ? (Math.abs(v - Math.round(v)) < 1e-9 ? v.toFixed(1) : String(v)) : '0.0'; }
  var UW_GLSL = '';
  if (UW) {
    var wc = UW.colour;
    UW_GLSL = [
      '#ifndef FR_UW_GLSL', '#define FR_UW_GLSL',
      '#define FR_LEVEL ' + glf(uwLevel),
      '#define FR_SIGMA ' + glf(UW.sigma),
      '#define FR_WATER vec3(' + glf(wc[0]) + ', ' + glf(wc[1]) + ', ' + glf(wc[2]) + ')',
      uwCut ? '#define FR_CUT' : '',
      uwCut ? '#define FR_CUT_O vec2(' + glf(uwO.x) + ', ' + glf(uwO.y) + ')' : '',
      uwCut ? '#define FR_CUT_U vec2(' + glf(uwU.x) + ', ' + glf(uwU.y) + ')' : '',
      uwCut ? '#define FR_CUT_V vec2(' + glf(uwV.x) + ', ' + glf(uwV.y) + ')' : '',
      uwCut ? '#define FR_CUT_L ' + glf(uwCut.length) : '',
      uwCut ? '#define FR_CUT_W ' + glf(uwCut.width / 2) : '',
      // the water's colour (core.sea.UNDERWATER) a little lighter looking up, darker looking down
      'vec3 frWaterColour(vec3 dir) { return FR_WATER * (0.75 + 0.5 * smoothstep(-1.0, 1.0, dir.y)); }',
      'bool frInBox(vec2 p) {',
      '#ifdef FR_CUT',
      '  vec2 d = p - FR_CUT_O; float a = dot(d, FR_CUT_U), b = dot(d, FR_CUT_V);',
      '  return a > 0.0 && a < FR_CUT_L && abs(b) < FR_CUT_W;',
      '#else',
      '  return false;',
      '#endif',
      '}',
      'void frSlab(float p0, float dp, float mn, float mx, inout float lo, inout float hi) {',
      '  if (abs(dp) < 1e-6) { if (p0 <= mn || p0 >= mx) { lo = 1.0; hi = 0.0; } return; }',
      '  float ta = (mn - p0) / dp, tb = (mx - p0) / dp;',
      '  lo = max(lo, min(ta, tb)); hi = min(hi, max(ta, tb));',
      '}',
      // metres of water on the straight line a -> b (three's coordinates): under the level, outside the box
      'float frWaterLen(vec3 a, vec3 b) {',
      '  vec3 d = b - a; float n = length(d);',
      '  if (n < 1e-5) return 0.0;',
      '  float t0 = 0.0, t1 = 1.0, za = a.y - FR_LEVEL;',
      '  if (abs(d.y) < 1e-6) { if (za >= 0.0) return 0.0; }',
      '  else { float tc = -za / d.y; if (d.y < 0.0) t0 = max(t0, tc); else t1 = min(t1, tc); }',
      '  if (t1 <= t0) return 0.0;',
      '  float total = (t1 - t0) * n;',
      '#ifdef FR_CUT',
      '  float lo = t0, hi = t1; vec2 a2 = a.xz - FR_CUT_O;',
      '  frSlab(dot(a2, FR_CUT_U), dot(d.xz, FR_CUT_U), 0.0, FR_CUT_L, lo, hi);',
      '  frSlab(dot(a2, FR_CUT_V), dot(d.xz, FR_CUT_V), -FR_CUT_W, FR_CUT_W, lo, hi);',
      '  if (hi > lo) total -= (hi - lo) * n;',
      '#endif',
      '  return max(total, 0.0);',
      '}', '#endif'].filter(Boolean).join('\n') + '\n';
    var C = T.ShaderChunk;
    C.fog_pars_vertex = C.fog_pars_vertex + '\n#ifdef USE_FOG\nvarying vec3 vFrW;\n#endif\n';
    C.fog_vertex = C.fog_vertex + '\n#ifdef USE_FOG\n' +
      'vFrW = transpose(mat3(viewMatrix)) * (mvPosition.xyz - viewMatrix[3].xyz);\n#endif\n';
    C.fog_pars_fragment = C.fog_pars_fragment + '\n#if defined(USE_FOG) && !defined(FOG_EXP2)\n' +
      'varying vec3 vFrW;\nfloat frL = 0.0;\n' + UW_GLSL +
      'vec3 frWaterMix(vec3 c) {\n' +
      '  if (fogFar <= 0.0) return c;\n' +
      '  frL = frWaterLen(cameraPosition, vFrW);\n' +
      '  float tr = exp(-FR_SIGMA * frL);\n' +
      '  return c * tr + frWaterColour(normalize(vFrW - cameraPosition)) * fogFar * (1.0 - tr);\n}\n#endif\n';
    C.opaque_fragment = C.opaque_fragment + '\n#if defined(USE_FOG) && !defined(FOG_EXP2) && !defined(FR_NO_WATER)\n' +
      'gl_FragColor.rgb = frWaterMix(gl_FragColor.rgb);\n#endif\n';      // (the sea seen from above: its own look)
    // the haze (three's FogExp2) over the stretch in air only
    C.fog_fragment = '#ifdef USE_FOG\n#ifdef FOG_EXP2\n' +
      'float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );\n#else\n' +
      'float frAir = vFogDepth * max(0.0, 1.0 - frL / max(length(vFrW - cameraPosition), 1e-5));\n' +
      'float fogFactor = 1.0 - exp( - fogNear * fogNear * frAir * frAir );\n#endif\n' +
      'gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );\n#endif\n';
  }

  // ---------------------------------------------------------------- level of quality
  // the order: the link (?quality=, ?auto=), else the visitor's own choice last time (menu), else the export's
  var urlQ = Q.get('quality') && LEVELS.indexOf(Q.get('quality').toUpperCase()) >= 0 ? Q.get('quality').toUpperCase()
    : null;
  var prefQ = PREF.quality === 'AUTO' || LEVELS.indexOf(PREF.quality) >= 0 ? PREF.quality : null;
  var level = urlQ || (prefQ && prefQ !== 'AUTO' ? prefQ : ST.quality);
  var auto = Q.has('auto') ? Q.get('auto') !== '0' : prefQ ? prefQ === 'AUTO' : !!ST.auto;
  var topLevel = level;                    // Auto steps up again, never above where it started
  var chosen = !!(urlQ || (prefQ && prefQ !== 'AUTO'));
  if (page.warned && !chosen) { level = 'PHONE'; }   // no graphics card: the lightest settings
  page.cap = page.warned ? 30 : 60;
  page.auto = auto;
  page.quality = auto ? 'AUTO' : level;
  var frozen = Q.has('t') && isFinite(parseFloat(Q.get('t'))) ? parseFloat(Q.get('t')) : null;
  var maxFrames = Q.has('frames') ? parseInt(Q.get('frames'), 10) || 0 : 0;
  var wantTubes = Q.get('tubes') === '1';      // tests: the drawn tubes' centre lines into data-fr-tubes (task 0142)
  var wantPlaces = Q.get('places') === '1';    // tests: the animated nodes' places into data-fr-places (task 0175)
  function L() { return ST.levels[level]; }

  // ---------------------------------------------------------------- the sun
  var sunDir = b2t(ST.sky.sun).normalize();
  var elev = ST.sky.elevation;
  var clouds = ST.sky.clouds || 'NONE';
  var photo = ST.sky.kind === 'PHOTO';
  var strength = ST.sky.strength == null ? 1 : ST.sky.strength;
  var low, sunColour, sunPower, horizon, skyBright, ground;
  function sunLook() {                  // the sun's colour and strength, the haze and the ground for its height
    low = 1 - T.MathUtils.smoothstep(elev, 2, 35);             // 1 at sunrise, 0 above 35 degrees
    sunColour = new T.Color(1.0, 0.96, 0.9).lerp(new T.Color(1.0, 0.62, 0.36), low);
    sunPower = photo ? T.MathUtils.clamp(ST.sky.sun_share || 1, 0.3, 3.0)
                     : 3.2 * T.MathUtils.clamp(Math.sin(elev * Math.PI / 180) * 4, 0.05, 1);
    if (!photo && clouds === 'SOME') sunPower *= 0.8;
    if (!photo && clouds === 'OVERCAST') sunPower *= 0.12;
    // colours of the far distance (haze) and the ground below the horizon
    horizon = ST.sky.horizon ? new T.Color().fromArray(ST.sky.horizon)
      : new T.Color(0.55, 0.64, 0.76).lerp(new T.Color(0.86, 0.6, 0.45), low * 0.8);
    if (!photo && clouds === 'OVERCAST') horizon = new T.Color(0.52, 0.55, 0.58);
    skyBright = photo ? 1 : (0.35 + 0.65 * T.MathUtils.smoothstep(elev, -2, 25));
    if (!ST.sky.horizon) horizon.multiplyScalar(skyBright);
    ground = hasSea ? new T.Color(0.012, 0.045, 0.055) : new T.Color(0.33, 0.32, 0.30).multiplyScalar(skyBright);
  }
  sunLook();
  var sun = new T.DirectionalLight(sunColour, sunPower * strength);
  scene.add(sun, sun.target);
  sun.position.copy(sunDir);          // the light comes from here (fitShadow moves both with shadows on); without this
                                      // three's default put the sun straight overhead when shadows were off
  sun.castShadow = !!ST.shadows;
  sun.shadow.bias = -0.0004;
  // a studio's or a photo's main light is broad, an overcast sun weak: lighter shadows than a clear sun's
  sun.shadow.intensity = photo ? 0.65 : clouds === 'OVERCAST' ? 0.4 : 1.0;

  // ---------------------------------------------------------------- the sky (procedural) and the dome
  var skyMesh = null, dome = null;
  var envScene = new T.Scene();
  var domeUniforms = {
    uCover: { value: clouds === 'OVERCAST' ? 1.0 : clouds === 'SOME' ? 0.45 : 0.0 },
    uTime: { value: 0 }, uHaze: { value: ST.haze ? Math.min(1, ST.haze.strength * 1.4) : 0 },
    uSunDir: { value: sunDir.clone() }, uSunCol: { value: sunColour.clone().multiplyScalar(skyBright) },
    uHazeCol: { value: horizon.clone() }, uGround: { value: ground.clone() },
    uCloudCol: { value: (clouds === 'OVERCAST' ? new T.Color(0.42, 0.44, 0.46) : new T.Color(0.95, 0.95, 0.97))
                         .multiplyScalar(skyBright) },
    uSky: { value: photo ? 0 : 1 }
  };
  var domeMat = new T.ShaderMaterial({
    uniforms: domeUniforms, transparent: true, depthWrite: false, side: T.BackSide, toneMapped: false,
    vertexShader: [
      'varying vec3 vDir;',
      'void main() {',
      '  vDir = normalize((modelMatrix * vec4(position, 0.0)).xyz);',
      '  gl_Position = projectionMatrix * viewMatrix * vec4((modelMatrix * vec4(position, 1.0)).xyz, 1.0);',
      '  gl_Position.z = gl_Position.w;',
      '}'].join('\n'),
    fragmentShader: [
      'varying vec3 vDir;',
      'uniform float uCover, uTime, uHaze, uSky; uniform vec3 uSunDir, uSunCol, uHazeCol, uGround, uCloudCol;',
      'float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      'float noise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);',
      '  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }',
      'float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + 7.1; a *= 0.5; } return v; }',
      'void main() {',
      '  vec3 d = normalize(vDir);',
      '  vec4 col = vec4(0.0);',
      '  if (d.y > 0.0) {',
      '    if (uCover > 0.0) {',
      '      vec2 p = d.xz / (d.y + 0.12) * 1.6 + vec2(0.011, 0.004) * uTime;',
      '      float n = fbm(p);',
      '      float c = smoothstep(1.05 - uCover * 0.75, 1.25 - uCover * 0.75, n + 0.2) * smoothstep(0.0, 0.08, d.y);',
      '      if (uCover >= 1.0) c = max(c, 0.92 * smoothstep(0.0, 0.05, d.y));',
      '      float lit = 0.75 + 0.25 * fbm(p * 2.0 + 3.0) + 0.35 * pow(max(dot(d, uSunDir), 0.0), 8.0);',
      '      col = vec4(uCloudCol * lit, c);',
      '    }',
      '    float h = uHaze * (1.0 - smoothstep(0.0, 0.25 + 0.3 * uHaze, d.y));',
      '    col.rgb = mix(col.rgb, uHazeCol, h); col.a = col.a + h * (1.0 - col.a);',
      '    if (uSky < 0.5) col.a *= step(0.001, uCover + uHaze);',
      '  } else {',
      '    float k = smoothstep(0.0, 0.06, -d.y);',
      '    col = vec4(mix(uHazeCol, uGround, k), uSky);',
      '  }',
      '  gl_FragColor = col;',
      '  #include <colorspace_fragment>',
      '}'].join('\n')
  });
  function makeDome() {
    var m = new T.Mesh(new T.SphereGeometry(1, 48, 24), domeMat);
    m.scale.setScalar(900);
    m.frustumCulled = false;
    m.renderOrder = -1;
    return m;
  }
  if (!photo) {
    skyMesh = new T.Sky();
    skyMesh.scale.setScalar(1000);
    skyMesh.frustumCulled = false;
    var su = skyMesh.material.uniforms;
    su.turbidity.value = clouds === 'OVERCAST' ? 10 : clouds === 'SOME' ? 5 : 3;
    su.rayleigh.value = clouds === 'OVERCAST' ? 0.6 : 1.4 + low;
    su.mieCoefficient.value = 0.004;
    su.mieDirectionalG.value = 0.8;
    su.sunPosition.value.copy(sunDir);
    // three's sky is drawn as it is (AgX turns its blue grey) at half its strength; the light it gives is the same
    su.uSkyGain = { value: 0.5 };
    skyMesh.material.onBeforeCompile = function (sh) {
      sh.uniforms.uSkyGain = su.uSkyGain;
      sh.fragmentShader = 'uniform float uSkyGain;\n' + sh.fragmentShader.replace('#include <tonemapping_fragment>',
        'gl_FragColor.rgb *= uSkyGain;');
    };
    skyMesh.material.toneMapped = false;
    skyMesh.renderOrder = -2;
    if (!plain) scene.add(skyMesh);
    var envSky = new T.Sky();
    envSky.material = skyMesh.material;
    envSky.scale.setScalar(1000);
    envScene.add(envSky);
  }
  dome = makeDome();
  if (!plain) scene.add(dome);
  envScene.add(makeDome());
  if (plain) {                                        // the model-viewer page's look: dark text on a light ground
    var css = document.documentElement.style;
    css.setProperty('--bg', '#F1F3F5'); css.setProperty('--ink', '#252E36'); css.setProperty('--muted', '#5B6670');
    document.body.style.background = 'radial-gradient(#ffffff, #F1F3F5)';
    [].forEach.call(document.querySelectorAll('header, .note'), function (el) { el.style.textShadow = 'none'; });
    page.light.background = getComputedStyle(document.body).backgroundImage;
  }

  // ---------------------------------------------------------------- light from the sky or the picture
  var pmrem = new T.PMREMGenerator(renderer);
  function picture(id) {
    var el = document.getElementById('fr-pic-' + id);
    if (!el) return null;
    var s = atob(el.textContent.trim()), a = new Uint8Array(s.length);
    for (var i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);
    return URL.createObjectURL(new Blob([a], { type: el.dataset.type || 'application/octet-stream' }));
  }
  var waiting = 1;                                    // the model; pictures add theirs
  function oneLess() { if (--waiting === 0) start(); }
  if (photo) {
    var bgUrl = ST.sky.photo && !plain ? picture(ST.sky.photo) : null;
    if (bgUrl) {
      waiting++;
      new T.TextureLoader().load(bgUrl, function (tex) {
        tex.mapping = T.EquirectangularReflectionMapping;
        tex.colorSpace = T.SRGBColorSpace;
        scene.background = tex;
        oneLess();
      }, undefined, function (e) { page.errors.push('background picture: ' + e); oneLess(); });
    }
    var lightUrl = ST.sky.light ? picture(ST.sky.light) : null;
    if (lightUrl) {
      waiting++;
      new T.HDRLoader().setDataType(T.HalfFloatType).load(lightUrl, function (tex) {
        tex.mapping = T.EquirectangularReflectionMapping;
        scene.environment = pmrem.fromEquirectangular(tex).texture;
        scene.environmentIntensity = strength;
        tex.dispose();
        oneLess();
      }, undefined, function (e) { page.errors.push('light picture: ' + e); oneLess(); });
    }
    if (!bgUrl && !plain) {
      scene.background = ST.sky.background ? new T.Color().fromArray(ST.sky.background) : horizon.clone();
    }
  } else {
    var envTarget = pmrem.fromScene(envScene, 0, 0.1, 5000);
    scene.environment = envTarget.texture;
    scene.environmentIntensity = strength;
  }

  // ---------------------------------------------------------------- haze
  var fog = ST.haze ? new T.FogExp2(horizon.clone(), ST.haze.density) : null;
  var waterFog = UW ? new T.Fog(horizon.clone(), ST.haze ? ST.haze.density : 0, UW.light) : null;   // task 0143
  scene.fog = waterFog || fog;

  // ---------------------------------------------------------------- the sea
  var sea = null, seaUniforms = null, rippleTex = null;
  function rippleTexture(n) {
    // tileable ripples: sums of sines with whole wave numbers (so the picture wraps); xy = slope, a = foam noise
    var rnd = mulberry(7), waves = [], foamW = [];
    for (var i = 0; i < 28; i++) {
      var kx = Math.round((rnd() * 2 - 1) * (4 + i)), ky = Math.round((rnd() * 2 - 1) * (4 + i));
      if (!kx && !ky) kx = 3;
      waves.push([kx, ky, rnd() * 6.283, 1 / Math.sqrt(kx * kx + ky * ky)]);
    }
    for (i = 0; i < 40; i++) {           // foam: a fractal noise (big patches broken up into streaks), as the app's
      var span = 3 + Math.pow(i / 39, 1.6) * 70;
      kx = Math.round((rnd() * 2 - 1) * span); ky = Math.round((rnd() * 2 - 1) * span);
      if (!kx && !ky) ky = 2;
      foamW.push([kx, ky, rnd() * 6.283, Math.pow(kx * kx + ky * ky, -0.42)]);
    }
    var gx = new Float32Array(n * n), gy = new Float32Array(n * n), f = new Float32Array(n * n);
    var sx = new Float32Array(n), cx = new Float32Array(n), sy = new Float32Array(n), cy = new Float32Array(n);
    function add(list, slope) {
      for (var w = 0; w < list.length; w++) {
        var W = list[w];
        for (var j = 0; j < n; j++) {
          var ax = 6.283185 * W[0] * j / n, ay = 6.283185 * W[1] * j / n;
          sx[j] = Math.sin(ax); cx[j] = Math.cos(ax);
          sy[j] = Math.sin(ay + W[2]); cy[j] = Math.cos(ay + W[2]);
        }
        for (var y = 0; y < n; y++) {
          for (var x = 0; x < n; x++) {
            var c = cx[x] * cy[y] - sx[x] * sy[y];          // cos(ax + ay + phase)
            var k = y * n + x;
            if (slope) { gx[k] += W[0] * W[3] * c; gy[k] += W[1] * W[3] * c; }
            else f[k] += W[3] * (sx[x] * cy[y] + cx[x] * sy[y]);
          }
        }
      }
    }
    add(waves, true); add(foamW, false);
    var data = new Uint8Array(n * n * 4), gs = 0, fs = 0;
    for (k = 0; k < n * n; k++) { gs = Math.max(gs, Math.abs(gx[k]), Math.abs(gy[k])); fs = Math.max(fs, Math.abs(f[k])); }
    for (var k = 0; k < n * n; k++) {
      data[4 * k] = 127.5 + 127 * gx[k] / gs;
      data[4 * k + 1] = 127.5 + 127 * gy[k] / gs;
      data[4 * k + 2] = 255;
      data[4 * k + 3] = 127.5 + 110 * f[k] / fs;
    }
    var tex = new T.DataTexture(data, n, n, T.RGBAFormat);
    tex.wrapS = tex.wrapT = T.RepeatWrapping;
    tex.magFilter = T.LinearFilter;
    tex.minFilter = T.LinearMipmapLinearFilter;
    tex.generateMipmaps = true;
    tex.anisotropy = 4;
    tex.needsUpdate = true;
    return tex;
  }
  function mulberry(a) {
    return function () { a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }
  function seaGeometry(seg) {
    var S = ST.sea, rings = [], r = Math.max(0.4, S.near * 0.004), step = 1 + 2 * Math.PI / seg;
    while (r < S.near * 1.6) { rings.push(r); r *= step; }
    while (r < S.radius) { r = Math.min(S.radius, r * 1.45); rings.push(r); }
    var pos = new Float32Array((1 + rings.length * seg) * 3), idx = [];
    for (var j = 0; j < rings.length; j++) {
      var rim = T.MathUtils.clamp((rings[j] - 0.75 * S.radius) / (0.25 * S.radius), 0, 1);
      for (var i = 0; i < seg; i++) {
        var a = 2 * Math.PI * i / seg, o = 3 * (1 + j * seg + i);
        pos[o] = rings[j] * Math.cos(a); pos[o + 1] = S.rim * rim * rim; pos[o + 2] = -rings[j] * Math.sin(a);
      }
    }
    for (i = 0; i < seg; i++) idx.push(0, 1 + i, 1 + (i + 1) % seg);
    for (j = 0; j < rings.length - 1; j++) {
      var a0 = 1 + j * seg, b0 = 1 + (j + 1) * seg;
      for (i = 0; i < seg; i++) {
        var i1 = (i + 1) % seg;
        idx.push(a0 + i, b0 + i, b0 + i1, a0 + i, b0 + i1, a0 + i1);
      }
    }
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(pos, 3));
    g.setIndex(idx);
    return g;
  }
  var MAXW = 16;
  if (hasSea) {
    var S = ST.sea, waves = [], phases = [], ampOwn = 0; var fadeR = [];
    for (var i = 0; i < MAXW; i++) {
      var w = S.waves[i];
      waves.push(w ? new T.Vector4(w[0], w[1], w[2], w[3]) : new T.Vector4(0, 1, 0, 0.01));
      phases.push(w ? w[4] : 0);
      var fd = (w && S.fade) ? S.fade[i] : null;
      fadeR.push(fd ? new T.Vector2(fd[0], fd[1]) : new T.Vector2(0, 0));
      if (w && i < S.own) ampOwn += w[0];
    }
    seaUniforms = {
      uTime: { value: 0 }, uWave: { value: waves }, uPhase: { value: phases }, uFadeR: { value: fadeR },
      uCount: { value: Math.min(S.waves.length, MAXW) }, uOwn: { value: S.own }, uNear: { value: S.near },
      uAmpOwn: { value: Math.max(ampOwn, 1e-3) }, uRipple: { value: null }, uBump: { value: S.bump * 2.2 },
      uFoamAt: { value: S.foam == null ? -1 : S.foam }, uRipScale: { value: 1 / 9 },
      uFoamMax: { value: S.state === 'ROUGH' ? 0.85 : 0.4 }
    };
    var seaMat = new T.MeshStandardMaterial({ color: new T.Color(0.006, 0.03, 0.035), roughness: 0.035,
                                              metalness: 0.0 });
    seaMat.onBeforeCompile = function (sh) {
      Object.assign(sh.uniforms, seaUniforms);
      var pars = 'uniform float uTime, uNear, uAmpOwn, uBump, uFoamAt, uRipScale, uFoamMax; uniform vec4 uWave[' + MAXW + '];' +
                 ' uniform float uPhase[' + MAXW + ']; uniform vec2 uFadeR[' + MAXW + '];' +
                 ' uniform int uCount, uOwn; uniform sampler2D uRipple;' +
                 ' varying float vCrest; varying vec2 vRip;\n';
      sh.vertexShader = pars + sh.vertexShader
        .replace('#include <beginnormal_vertex>', [
          'vec2 bxy = vec2(position.x, -position.z);',
          'float fadeW = 1.0 - smoothstep(uNear, 1.6 * uNear, length(bxy));',
          'float hW = 0.0, hx = 0.0, hy = 0.0, cr = 0.0;',
          'for (int i = 0; i < ' + MAXW + '; i++) {',
          '  if (i >= uCount) break;',
          '  vec4 w = uWave[i];',
          '  float ph = w.w * (w.y * bxy.x + w.z * bxy.y) + uPhase[i] - sqrt(9.81 * w.w) * uTime;',
          '  float wf = uFadeR[i].y > 0.0 ? clamp((uFadeR[i].y - length(bxy)) / (uFadeR[i].y - uFadeR[i].x), 0.0, 1.0) : 1.0;',
          '  float s = sin(ph) * wf, c = cos(ph) * wf;',
          '  hW += w.x * s; hx += w.x * w.w * w.y * c; hy += w.x * w.w * w.z * c;',
          '  if (i < uOwn) cr += w.x * s;',
          '}',
          'vCrest = cr * fadeW / uAmpOwn;',
          'vec3 objectNormal = normalize(vec3(-hx * fadeW, 1.0, hy * fadeW));'].join('\n'))
        .replace('#include <begin_vertex>', [
          'vec3 transformed = vec3(position.x, position.y + hW * fadeW, position.z);',
          'vRip = (modelMatrix * vec4(transformed, 1.0)).xz;'].join('\n'));
      sh.fragmentShader = pars + sh.fragmentShader
        .replace('#include <color_fragment>', [
          '#include <color_fragment>',
          'float foam = 0.0;',
          'if (uFoamAt > 0.0) {',
          '  float fn = 0.6 * texture2D(uRipple, vRip * uRipScale * 0.55 + vec2(0.021, 0.013) * uTime).a',
          '           + 0.4 * texture2D(uRipple, vRip * uRipScale * 1.9 - vec2(0.017, 0.029) * uTime).a;',
          '  foam = uFoamMax * smoothstep(uFoamAt - 0.04, uFoamAt + 0.16, vCrest + 0.35 * fn);',
          '}',
          'diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.75, 0.78, 0.8), foam);'].join('\n'))
        .replace('#include <roughnessmap_fragment>',
                 '#include <roughnessmap_fragment>\nroughnessFactor = mix(roughnessFactor, 0.6, foam);')
        .replace('#include <normal_fragment_maps>', [
          '#include <normal_fragment_maps>',
          'vec4 r1 = texture2D(uRipple, vRip * uRipScale + vec2(0.013, 0.007) * uTime);',
          'vec4 r2 = texture2D(uRipple, vRip * uRipScale * 0.37 + vec2(-0.004, 0.011) * uTime);',
          'vec2 dr = (r1.xy * 2.0 - 1.0) + 0.8 * (r2.xy * 2.0 - 1.0);',
          'float kR = uBump / (1.0 + length(vViewPosition) * 0.004);',
          'normal = normalize(normal + (viewMatrix * vec4(-dr.x * kR, 0.0, -dr.y * kR, 0.0)).xyz);'].join('\n'));
    };
    var seaBelow = null;
    if (UW) {                              // task 0143: open inside the cut-away box; seen from below too
      seaUniforms.uCutOn = { value: 0 };
      seaUniforms.uBelow = { value: new T.Color().fromArray(UW.colour).multiplyScalar(3.0 * UW.light) };
      var seaCompile = seaMat.onBeforeCompile;
      var underCompile = function (sh) {
        seaCompile(sh);
        sh.uniforms.uCutOn = seaUniforms.uCutOn;
        sh.uniforms.uBelow = seaUniforms.uBelow;
        sh.fragmentShader = UW_GLSL + 'uniform float uCutOn; uniform vec3 uBelow;\n' + sh.fragmentShader
          .replace('#include <color_fragment>', '#include <color_fragment>\n' +
                   'if (uCutOn > 0.5 && frInBox(vRip)) discard;')
          // from below: the surface lit through (lighter than the water far away, which the fade gives)
          .replace('#include <opaque_fragment>', '#ifdef FR_BELOW\noutgoingLight = uBelow;\n#endif\n' +
                   '#include <opaque_fragment>');
      };
      // the side seen from above carries no water code (it covers most of the screen: without a graphics card the
      // fade's code alone cost half the pictures a second); the side seen from below is a second mesh
      var belowMat = seaMat.clone();
      seaMat.defines = { FR_NO_WATER: '' };
      seaMat.onBeforeCompile = underCompile;
      seaMat.customProgramCacheKey = function () { return 'fr-sea-above'; };
      belowMat.side = T.BackSide;
      belowMat.defines = { FR_BELOW: '' };
      belowMat.onBeforeCompile = underCompile;
      belowMat.customProgramCacheKey = function () { return 'fr-sea-below'; };
      seaBelow = new T.Mesh(new T.BufferGeometry(), belowMat);
      seaBelow.frustumCulled = false;
    }
    sea = new T.Mesh(seaGeometry(L().seg), seaMat);
    sea.position.copy(b2t([S.origin[0], S.origin[1], S.level]));
    sea.frustumCulled = false;
    sea.receiveShadow = !!ST.shadows;
    scene.add(sea);
    if (seaBelow) { seaBelow.position.copy(sea.position); scene.add(seaBelow); }
  }

  // ---------------------------------------------------------------- the seabed, the box's walls, the soil (0143)
  var seabed = null, bedAround = null, cutWalls = null, soil = null, bedUniforms = null;
  var BED_REACH = 6;                       // x the clarity: how far the seabed is drawn round the box and the camera
  if (UW) {
    var sand = UW.sand, rp = UW.ripple;
    bedUniforms = { uBedOff: { value: new T.Vector2(UW.bed_xy[0], UW.bed_xy[1]) }, uGroundOn: { value: 0 } };
    var bedMat = new T.MeshStandardMaterial({ color: 0xffffff, roughness: 0.92, metalness: 0.0 });
    bedMat.onBeforeCompile = function (sh) {
      Object.assign(sh.uniforms, bedUniforms);
      sh.vertexShader = 'varying vec3 vBedW;\n' + sh.vertexShader.replace('#include <worldpos_vertex>',
        '#include <worldpos_vertex>\nvBedW = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      var v3 = function (c) { return 'vec3(' + glf(c[0]) + ', ' + glf(c[1]) + ', ' + glf(c[2]) + ')'; };
      sh.fragmentShader = [UW_GLSL + 'varying vec3 vBedW; uniform vec2 uBedOff; uniform float uGroundOn;',
        'float frHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
        'float frNoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);',
        '  return mix(mix(frHash(i), frHash(i + vec2(1, 0)), f.x), mix(frHash(i + vec2(0, 1)), frHash(i + vec2(1, 1)), f.x), f.y); }',
        'float frFbm(vec2 p) { return 0.5 * frNoise(p) + 0.3 * frNoise(p * 2.1 + 5.3) + 0.2 * frNoise(p * 4.3 + 1.7); }',
        ''].join('\n') + sh.fragmentShader
        .replace('#include <color_fragment>', ['#include <color_fragment>',
          'if (uGroundOn > 0.5 && frInBox(vBedW.xz)) discard;',       // the seabed is open over the soil section
          // core.sea.seabed_ripples in the seabed's own coordinates (Blender x, y), and its slope
          'vec2 bp = vec2(vBedW.x, -vBedW.z) - uBedOff;',
          'float rk = 6.2831853 / ' + glf(rp[0]) + ';',
          'float s1 = 0.13 * bp.x - 0.07 * bp.y, s2 = 0.21 * bp.y + 0.4;',
          'float ph = rk * (0.96 * bp.x + 0.28 * bp.y) + 0.9 * sin(s2) + 0.5 * sin(s1);',
          'float rr = sin(ph);',
          'float phx = rk * 0.96 + 0.5 * 0.13 * cos(s1), phy = rk * 0.28 + 0.9 * 0.21 * cos(s2) - 0.5 * 0.07 * cos(s1);',
          'float fw = clamp(1.5 - fwidth(ph), 0.0, 1.0);',       // far away the ripples are finer than a pixel
          'float hx = ' + glf(rp[1]) + ' * cos(ph) * phx * fw + 0.12 * 0.23 * cos(0.23 * bp.x + 0.9) * sin(0.17 * bp.y + 0.3);',
          'float hy = ' + glf(rp[1]) + ' * cos(ph) * phy * fw + 0.12 * 0.17 * sin(0.23 * bp.x + 0.9) * cos(0.17 * bp.y + 0.3);',
          'float patches = frFbm(bp * 0.04);',
          'vec3 sandC = mix(' + v3(sand[1]) + ', ' + v3(sand[0]) + ', smoothstep(0.35, 0.7, patches));',
          'sandC = mix(sandC, ' + v3(sand[1]) + ' * 0.7, (1.0 - smoothstep(-1.0, 0.2, rr)) * 0.35 * fw);',
          'float grain = frNoise(bp * 9.0);',
          'sandC = mix(sandC, ' + v3(sand[0]) + ' * 0.75, smoothstep(0.3, 0.7, grain) * 0.25 * clamp(1.0 - fwidth(bp.x * 9.0), 0.0, 1.0));',
          'diffuseColor.rgb = sandC;'].join('\n'))
        .replace('#include <normal_fragment_maps>', ['#include <normal_fragment_maps>',
          'normal = normalize((viewMatrix * vec4(-hx, 1.0, hy, 0.0)).xyz);'].join('\n'));
    };
    bedMat.customProgramCacheKey = function () { return 'fr-seabed'; };
    // only where it can be seen: beyond BED_REACH x the clarity of water nothing is left of it (e^-18), and the
    // water's colour behind (waterDome) is what the camera sees there. A patch round the box (seen from above) and
    // one that follows the camera under water: a plane under the whole sea cost its shader on every pixel of the sea
    // without a graphics card
    var reach = BED_REACH * UW.clarity;
    seabed = new T.Group();
    var patch = function (w, h) {
      var m = new T.Mesh(new T.PlaneGeometry(w, h, 4, 4), bedMat);
      m.rotation.x = -Math.PI / 2;
      m.receiveShadow = !!ST.shadows;
      m.frustumCulled = false;
      m.renderOrder = 1;                   // after the sea: where the sea hides it, its shader need not run
      seabed.add(m);
      return m;
    };
    if (uwCut) {
      var bx = [0, 1].map(function (a) { return [-1, 1].map(function (b) {
        return uwO.clone().addScaledVector(uwU, a * uwCut.length).addScaledVector(uwV, b * uwCut.width / 2); }); });
      var flat = [].concat(bx[0], bx[1]);
      var x0 = Math.min.apply(null, flat.map(function (p) { return p.x; })) - reach;
      var x1 = Math.max.apply(null, flat.map(function (p) { return p.x; })) + reach;
      var z0 = Math.min.apply(null, flat.map(function (p) { return p.y; })) - reach;
      var z1 = Math.max.apply(null, flat.map(function (p) { return p.y; })) + reach;
      patch(x1 - x0, z1 - z0).position.set((x0 + x1) / 2, uwBed, (z0 + z1) / 2);
    }
    bedAround = patch(2 * reach, 2 * reach);
    bedAround.visible = false;
    bedAround.position.y = uwBed;
    scene.add(seabed);
    page.info.under = { seabed: true, cut: !!uwCut, ground: !!uwGround };
  }
  if (uwCut) {
    // the walls of the box (faces into it): the bright line along their top where the water was cut, darker with
    // depth (core.sea.CUT_EDGE, CUT_DARK); the top follows the waves (the sea's own sum)
    var wallBottom = uwGround ? uwBed + uwGround.top : uwBed - 2.0;
    var corners = [[0, -1], [1, -1], [1, 1], [0, 1]].map(function (c) {
      return uwO.clone().addScaledVector(uwU, c[0] * uwCut.length).addScaledVector(uwV, c[1] * uwCut.width / 2);
    });
    var wp = [], wtop = [], wd = [], widx = [], topY = uwLevel - uwCut.top;
    for (var c = 0; c < 4; c++) {
      var ca = corners[c], cb = corners[(c + 1) % 4], nseg = Math.max(1, Math.ceil(ca.distanceTo(cb) / 1.0));
      for (var q = 0; q <= nseg; q++) {
        var pq = ca.clone().lerp(cb, q / nseg), base = wp.length / 3;
        wp.push(pq.x, topY, pq.y, pq.x, wallBottom, pq.y);
        wtop.push(1, 0);
        wd.push(0, topY - wallBottom);
        if (q < nseg) widx.push(base, base + 1, base + 3, base, base + 3, base + 2);
      }
    }
    var wg = new T.BufferGeometry();
    wg.setAttribute('position', new T.BufferAttribute(new Float32Array(wp), 3));
    wg.setAttribute('aTop', new T.BufferAttribute(new Float32Array(wtop), 1));
    wg.setAttribute('aDtop', new T.BufferAttribute(new Float32Array(wd), 1));
    wg.setIndex(widx);
    // which way the faces look: into the box (the box's middle on their front side)
    var mid = uwO.clone().addScaledVector(uwU, uwCut.length / 2), pa = corners[0], pb = corners[1];
    var nrm = new T.Vector3(-(pb.y - pa.y), 0, pb.x - pa.x);      // (top -> bottom) x (top -> next bottom)
    var inward = nrm.x * (mid.x - pa.x) + nrm.z * (mid.y - pa.y) > 0;
    var wl = UW.light, dark = uwCut.dark;
    var wallUniforms = { uTime: seaUniforms.uTime, uWave: seaUniforms.uWave, uPhase: seaUniforms.uPhase,
                         uFadeR: seaUniforms.uFadeR, uCount: seaUniforms.uCount, uNear: seaUniforms.uNear,
                         uLight: { value: wl } };
    var so = ST.sea.origin;
    cutWalls = new T.Mesh(wg, new T.ShaderMaterial({
      uniforms: wallUniforms, transparent: true, depthWrite: false, side: inward ? T.FrontSide : T.BackSide,
      vertexShader: ['uniform float uTime, uNear; uniform vec4 uWave[' + MAXW + ']; uniform float uPhase[' + MAXW + '];',
        'uniform vec2 uFadeR[' + MAXW + ']; uniform int uCount; attribute float aTop, aDtop; varying float vDtop;',
        'void main() {',
        '  vec3 p = position;',
        '  if (aTop > 0.5) {',
        '    vec2 bxy = vec2(p.x - ' + glf(so[0]) + ', -p.z - ' + glf(so[1]) + ');',
        '    float fadeW = 1.0 - smoothstep(uNear, 1.6 * uNear, length(bxy)), hW = 0.0;',
        '    for (int i = 0; i < ' + MAXW + '; i++) {',
        '      if (i >= uCount) break;',
        '      vec4 w = uWave[i];',
        '      float ph = w.w * (w.y * bxy.x + w.z * bxy.y) + uPhase[i] - sqrt(9.81 * w.w) * uTime;',
        '      float wf = uFadeR[i].y > 0.0 ? clamp((uFadeR[i].y - length(bxy)) / (uFadeR[i].y - uFadeR[i].x), 0.0, 1.0) : 1.0;',
        '      hW += w.x * sin(ph) * wf;',
        '    }',
        '    p.y += hW * fadeW;',
        '  }',
        '  vDtop = aDtop;',
        '  gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(p, 1.0);',
        '}'].join('\n'),
      fragmentShader: ['uniform float uLight; varying float vDtop;',
        'void main() {',
        '  float line = (1.0 - smoothstep(0.0, ' + glf(uwCut.edge) + ', vDtop)) * 0.85;',
        '  float dim = smoothstep(0.0, ' + glf(dark[1]) + ', vDtop) * ' + glf(dark[0]) + ';',
        '  vec3 shade = vec3(' + glf(wc[0] * 0.25) + ', ' + glf(wc[1] * 0.25) + ', ' + glf(wc[2] * 0.25) + ') * uLight;',
        '  vec3 edge = vec3(0.55, 0.80, 0.78) * uLight * 1.4;',
        '  float a = 1.0 - (1.0 - dim) * (1.0 - line);',
        '  vec3 col = (shade * dim * (1.0 - line) + edge * line) / max(a, 1e-4);',
        '  gl_FragColor = vec4(col, a);',
        '  #include <tonemapping_fragment>',
        '  #include <colorspace_fragment>',
        '}'].join('\n')
    }));
    cutWalls.frustumCulled = false;
    scene.add(cutWalls);
  }
  if (uwGround) {
    // the soil section (task 0148): the box's walls from just over the seabed down to the pit's floor, and the
    // floor, faces into the box; layers from sand to clay by the depth under the seabed (core.sea.SOIL_LAYERS)
    var gTop = uwBed + uwGround.top, gBot = uwBed - uwGround.depth;
    var sp = [], sidx = [];
    var gc = [[0, -1], [1, -1], [1, 1], [0, 1]].map(function (c) {
      return uwO.clone().addScaledVector(uwU, c[0] * uwCut.length).addScaledVector(uwV, c[1] * uwCut.width / 2);
    });
    gc.forEach(function (pc) { sp.push(pc.x, gTop, pc.y); });
    gc.forEach(function (pc) { sp.push(pc.x, gBot, pc.y); });
    for (var gi = 0; gi < 4; gi++) { var gj = (gi + 1) % 4; sidx.push(gi, gj, 4 + gj, gi, 4 + gj, 4 + gi); }
    sidx.push(4, 5, 6, 4, 6, 7);
    var sg2 = new T.BufferGeometry();
    sg2.setAttribute('position', new T.BufferAttribute(new Float32Array(sp), 3));
    sg2.setIndex(sidx);
    sg2 = sg2.toNonIndexed();
    sg2.computeVertexNormals();
    var layers = uwGround.layers, soilMat = new T.MeshStandardMaterial({ color: 0xffffff, roughness: 0.95,
                                                                           side: T.DoubleSide });
    soilMat.onBeforeCompile = function (sh) {
      sh.vertexShader = 'varying vec3 vSoilW;\n' + sh.vertexShader.replace('#include <worldpos_vertex>',
        '#include <worldpos_vertex>\nvSoilW = (modelMatrix * vec4(transformed, 1.0)).xyz;');
      var steps = ['vec3 sc = vec3(' + layers[0][1].map(glf).join(', ') + ');'];
      for (var li = 1; li < layers.length; li++) {
        steps.push('sc = mix(sc, vec3(' + layers[li][1].map(glf).join(', ') + '), smoothstep(' +
                   glf(layers[li][0] - 0.12) + ', ' + glf(layers[li][0] + 0.12) + ', sd));');
      }
      sh.fragmentShader = ['varying vec3 vSoilW;',
        'float sHash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }',
        'float sNoise(vec3 p) { vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);',
        '  return mix(mix(mix(sHash(i), sHash(i + vec3(1,0,0)), f.x), mix(sHash(i + vec3(0,1,0)), sHash(i + vec3(1,1,0)), f.x), f.y),',
        '             mix(mix(sHash(i + vec3(0,0,1)), sHash(i + vec3(1,0,1)), f.x), mix(sHash(i + vec3(0,1,1)), sHash(i + vec3(1,1,1)), f.x), f.y), f.z); }',
        ''].join('\n') + sh.fragmentShader.replace('#include <color_fragment>', ['#include <color_fragment>',
          'float sd = ' + glf(uwBed) + ' - vSoilW.y + (sNoise(vSoilW * 0.12) - 0.5) * ' + glf(2 * uwGround.wobble) + ';']
          .concat(steps).concat([
          'sc = mix(sc, vec3(0.0), smoothstep(0.3, 0.7, sNoise(vSoilW * 7.0)) * 0.2);',
          'diffuseColor.rgb = sc;']).join('\n'));
    };
    soilMat.customProgramCacheKey = function () { return 'fr-soil'; };
    soil = new T.Mesh(sg2, soilMat);
    soil.receiveShadow = !!ST.shadows;
    soil.renderOrder = 1;
    scene.add(soil);
  }
  // the water seen from under it where nothing is in the way (the sky does not show through water)
  var waterDome = null;
  if (UW) {
    // at the far plane, after the sky (transparent, drawn where nothing else is): below the horizon only while the
    // camera is above the water (seen through the cut-away's walls), all round under it
    waterDome = new T.Mesh(new T.SphereGeometry(1, 24, 12), new T.ShaderMaterial({
      uniforms: { uLight: { value: UW.light }, uFull: { value: 0 } }, side: T.BackSide, depthWrite: false,
      transparent: true,
      vertexShader: 'varying vec3 vDir;\nvoid main() { vDir = position;\n' +
        '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);\n' +
        '  gl_Position.z = gl_Position.w; }',
      fragmentShader: UW_GLSL + 'uniform float uLight, uFull; varying vec3 vDir;\nvoid main() {\n' +
        '  vec3 d = normalize(vDir);\n  if (uFull < 0.5 && d.y > 0.0) discard;\n' +
        '  gl_FragColor = vec4(frWaterColour(d) * uLight, 1.0);\n' +
        '  #include <tonemapping_fragment>\n  #include <colorspace_fragment>\n}' }));
    waterDome.scale.setScalar(800);
    waterDome.renderOrder = -0.5;          // after the sky's dome (-1), before the box's walls
    waterDome.frustumCulled = false;
    waterDome.visible = false;
    scene.add(waterDome);
  }

  // a floor that only shows the shadow (no sea)
  var catcher = null;
  if (!hasSea && ST.shadows) {
    catcher = new T.Mesh(new T.PlaneGeometry(R * 16, R * 16), new T.ShadowMaterial({ opacity: 0.35 }));
    catcher.rotation.x = -Math.PI / 2;
    catcher.position.set(centre.x, floorY - R * 0.0005, centre.z);
    catcher.receiveShadow = true;
    scene.add(catcher);
  }

  // ---------------------------------------------------------------- rain and spray (moved on the graphics card)
  var rain = null, rainUniforms = null, spray = null, sprayUniforms = null;
  var RAIN_MAX = ST.levels.BEST.rain, SPRAY_BURSTS = 4, SPRAY_MAX = ST.levels.BEST.spray;
  if (ST.rain) {
    var rr = mulberry(11), seeds = new Float32Array(RAIN_MAX * 2 * 3), ends = new Float32Array(RAIN_MAX * 2);
    for (i = 0; i < RAIN_MAX; i++) {
      var a = rr(), b = rr(), c = rr();
      for (var e = 0; e < 2; e++) { seeds.set([a, b, c], (2 * i + e) * 3); ends[2 * i + e] = e; }
    }
    var rg = new T.BufferGeometry();
    rg.setAttribute('position', new T.BufferAttribute(new Float32Array(RAIN_MAX * 2 * 3), 3));
    rg.setAttribute('aSeed', new T.BufferAttribute(seeds, 3));
    rg.setAttribute('aEnd', new T.BufferAttribute(ends, 1));
    rainUniforms = { uTime: { value: 0 }, uBox: { value: 20 }, uCentre: { value: new T.Vector3() },
                     uSpeed: { value: 9 }, uLen: { value: 0.35 }, uAlpha: { value: 0.25 + 0.35 * ST.rain.strength },
                     uColour: { value: horizon.clone().lerp(new T.Color(0.9, 0.92, 0.95), 0.5) } };
    rain = new T.LineSegments(rg, new T.ShaderMaterial({
      uniforms: rainUniforms, transparent: true, depthWrite: false,
      vertexShader: [
        'attribute vec3 aSeed; attribute float aEnd; uniform float uTime, uBox, uSpeed, uLen; uniform vec3 uCentre;',
        'varying float vA;',
        'void main() {',
        '  vec3 p;',
        '  p.xz = mod(aSeed.xz * uBox - uCentre.xz, uBox) - 0.5 * uBox + uCentre.xz;',
        '  p.y = mod(aSeed.y * uBox - uTime * uSpeed - uCentre.y, uBox) - 0.5 * uBox + uCentre.y;',
        '  p += aEnd * vec3(0.12, 1.0, 0.05) * uLen;',
        '  vA = 1.0 - abs(p.y - uCentre.y) / (0.5 * uBox);',
        '  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);',
        '}'].join('\n'),
      fragmentShader: 'uniform float uAlpha; uniform vec3 uColour; varying float vA;\n' +
        'void main() { gl_FragColor = vec4(uColour, uAlpha * clamp(vA * 2.0, 0.0, 1.0));\n' +
        '#include <colorspace_fragment>\n}'
    }));
    rain.frustumCulled = false;
    scene.add(rain);
    if (ST.rain.spray && hasSea) {
      var sr = mulberry(23), sb = new Float32Array(SPRAY_MAX * SPRAY_BURSTS), sd = new Float32Array(SPRAY_MAX * SPRAY_BURSTS * 3);
      for (i = 0; i < SPRAY_MAX * SPRAY_BURSTS; i++) {
        sb[i] = i % SPRAY_BURSTS;
        sd.set([sr() * 2 - 1, sr(), sr() * 2 - 1], 3 * i);
      }
      var sg = new T.BufferGeometry();
      sg.setAttribute('position', new T.BufferAttribute(new Float32Array(SPRAY_MAX * SPRAY_BURSTS * 3), 3));
      sg.setAttribute('aBurst', new T.BufferAttribute(sb, 1));
      sg.setAttribute('aRand', new T.BufferAttribute(sd, 3));
      var origins = [], starts = [];
      for (i = 0; i < SPRAY_BURSTS; i++) { origins.push(new T.Vector3()); starts.push(-100); }
      sprayUniforms = { uTime: { value: 0 }, uOrigin: { value: origins }, uStart: { value: starts },
                        uScale: { value: 1 }, uPix: { value: 1 } };
      spray = new T.Points(sg, new T.ShaderMaterial({
        uniforms: sprayUniforms, transparent: true, depthWrite: false,
        vertexShader: [
          'attribute float aBurst; attribute vec3 aRand; uniform float uTime, uScale, uPix;',
          'uniform vec3 uOrigin[' + SPRAY_BURSTS + ']; uniform float uStart[' + SPRAY_BURSTS + ']; varying float vA;',
          'void main() {',
          '  int b = int(aBurst + 0.5); vec3 o = uOrigin[0]; float s = uStart[0];',
          '  for (int i = 1; i < ' + SPRAY_BURSTS + '; i++) if (i == b) { o = uOrigin[i]; s = uStart[i]; }',
          '  float age = uTime - s;',
          '  if (age < 0.0 || age > 2.2) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 0.0; vA = 0.0; return; }',
          '  vec3 v = vec3(aRand.x * 3.5, 3.0 + 7.0 * aRand.y, aRand.z * 3.5) * uScale;',
          '  vec3 p = o + v * age + vec3(0.0, -4.9 * uScale, 0.0) * age * age;',
          '  vec4 mv = viewMatrix * vec4(p, 1.0);',
          '  gl_Position = projectionMatrix * mv;',
          '  gl_PointSize = uPix * uScale * (0.25 + 0.5 * aRand.y) * 320.0 / max(-mv.z, 0.1);',
          '  vA = 0.75 * (1.0 - age / 2.2);',
          '}'].join('\n'),
        fragmentShader: 'varying float vA;\nvoid main() { vec2 c = gl_PointCoord - 0.5; float r = dot(c, c);\n' +
          '  if (r > 0.25) discard; gl_FragColor = vec4(0.92, 0.95, 0.97, vA * (1.0 - 4.0 * r));\n' +
          '#include <colorspace_fragment>\n}'
      }));
      spray.frustumCulled = false;
      scene.add(spray);
    }
  }

  // ---------------------------------------------------------------- the model
  var top = new T.Group();          // everything the animation may move
  var vesselGroup = new T.Group(), levelGroup = new T.Group(), stillGroup = new T.Group();
  vesselGroup.matrixAutoUpdate = levelGroup.matrixAutoUpdate = false;
  top.add(vesselGroup, levelGroup, stillGroup);
  scene.add(top);
  var mixer = null, meshes = [], baked = null, wet = [];

  // ---------------------------------------------------------------- baked light (task 0107)
  // Light factor F = scale * texel ^ curve (texel: the occlusion map read through UV channel 1, or the mesh's
  // _FR_LIGHT attribute, linear 0 … 1): the light a white matte surface gets there, divided by the light on an open
  // up-facing surface. The page multiplies it by its OWN sky light on an up-facing surface (getIBLIrradiance(up) x
  // environment intensity, in place of the environment's own matte light iblIrradiance). With ALL that reference
  // also held Cycles' sun: ST.light.sun = Cycles' sun / sky on an up-facing surface, so the page uses
  // (1 + sun) x its sky – the baked parts keep the render's balance of sun and sky light, and a shaded wall gets
  // the same light as with SOFT. Reflections stay, dimmed by min(1, luminance F / (1 + sun)) in corners. ALL: the
  // live sun gives no matte light on baked surfaces (it is in the bake), only its highlight. A 360° photo or studio
  // light has no sun of its own: both choices bake all of it (sun 0), so they work as ALL. three's own occlusion
  // map (which multiplies) is not used on these materials.
  var BAKED_GLOBAL = [
    'uniform float uFrScale;',
    'uniform float uFrCurve;',
    'uniform float uFrSun;'].join('\n');
  var BAKED_NO_SUN = [                    // the sun's matte light off, its highlight kept
    'void RE_Direct_FrBaked( const in IncidentLight directLight, const in vec3 geometryPosition,',
    '    const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal,',
    '    const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {',
    '  vec3 frKeep = reflectedLight.directDiffuse;',
    '  RE_Direct_Physical( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal,',
    '                      material, reflectedLight );',
    '  reflectedLight.directDiffuse = frKeep;',
    '}',
    '#undef RE_Direct',
    '#define RE_Direct RE_Direct_FrBaked'].join('\n');
  var IBL_DIFFUSE = 'iblIrradiance += getIBLIrradiance( geometryNormal );';

  function bakedLight(list) {
    var all = ST.light.light === 'ALL' || photo;
    var uniforms = { uFrScale: { value: +ST.light.scale || 1 }, uFrCurve: { value: +ST.light.curve || 2 },
                     uFrSun: { value: all && !photo ? Math.max(0, +ST.light.sun || 0) : 0 } };
    var patches = {};
    function patch(kind) {                 // one function per kind: three shares the programs of a kind
      if (patches[kind]) return patches[kind];
      var maps = T.ShaderChunk.lights_fragment_maps;
      var problem = function (what) {
        page.errors.push('baked light: three.js shader has changed (' + what + ')'); mark();
      };
      if (maps.indexOf(IBL_DIFFUSE) < 0) problem('lights_fragment_maps');
      var texel = kind === 'map' ? 'texture2D( aoMap, vAoMapUv ).rgb' : 'vFrLight';
      var lights = [
        'vec3 frF = uFrScale * pow( max( ' + texel + ', vec3( 0.0 ) ), vec3( uFrCurve ) );',
        maps.replace(IBL_DIFFUSE,
          'iblIrradiance += frF * ( 1.0 + uFrSun ) * ' +
          'getIBLIrradiance( normalize( ( viewMatrix * vec4( 0.0, 1.0, 0.0, 0.0 ) ).xyz ) );'),
        '#if defined( RE_IndirectSpecular )',
        '  float frOcc = min( 1.0, dot( frF, vec3( 0.2126, 0.7152, 0.0722 ) ) * ( 1.0 + uFrSun ) );',
        '  radiance *= frOcc;',
        '  clearcoatRadiance *= frOcc;',
        '#endif'].join('\n');
      var fn = function (sh) {
        Object.assign(sh.uniforms, uniforms);
        var f = sh.fragmentShader;
        ['#include <lights_physical_pars_fragment>', '#include <lights_fragment_maps>', '#include <aomap_fragment>']
          .forEach(function (inc) { if (f.indexOf(inc) < 0) problem(inc); });
        f = f.replace('#include <lights_physical_pars_fragment>', '#include <lights_physical_pars_fragment>\n' +
                      BAKED_GLOBAL + (kind === 'vtx' ? '\nvarying vec3 vFrLight;' : '') + (all ? '\n' + BAKED_NO_SUN : ''))
             .replace('#include <lights_fragment_maps>', lights)
             .replace('#include <aomap_fragment>', '');
        sh.fragmentShader = f;
        if (kind === 'vtx') {
          sh.vertexShader = 'attribute vec3 frLight;\nvarying vec3 vFrLight;\n' +
            sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvFrLight = frLight;');
        }
      };
      var key = 'fr-baked-' + kind + (all ? '-all' : '-soft');
      patches[kind] = { fn: fn, key: function () { return key; } };
      return patches[kind];
    }
    // which meshes: a vertex light first, else an occlusion map on UV channel 1 (with the mesh's UV1)
    var kindOf = function (o, m) {
      var g = o.geometry;
      if (!m || !m.isMeshStandardMaterial) return null;
      if (m.transmission > 0 || (m.transparent && m.opacity < 0.5)) return null;   // glass keeps its live light
      if (g.getAttribute('_fr_light')) return 'vtx';
      if (m.aoMap && m.aoMap.channel === 1 && g.getAttribute('uv1')) return 'map';
      return null;
    };
    var uses = new Map();                  // material -> {kind: count}, so one shared with unbaked parts is copied
    list.forEach(function (o) {
      (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) {
        var u = uses.get(m) || {};
        var k = kindOf(o, m) || 'none';
        u[k] = (u[k] || 0) + 1;
        uses.set(m, u);
      });
    });
    var made = new Map(), count = 0;
    function bakedMaterial(m, kind) {
      var id = m.uuid + kind;
      if (made.has(id)) return made.get(id);
      var only = Object.keys(uses.get(m)).length === 1;
      var b = only ? m : m.clone();      // shared with another kind of part: its own copy (textures stay shared)
      var p = patch(kind);
      b.onBeforeCompile = p.fn;
      b.customProgramCacheKey = p.key;
      b.needsUpdate = true;
      made.set(id, b);
      return b;
    }
    list.forEach(function (o) {
      var arr = Array.isArray(o.material), mats = arr ? o.material.slice() : [o.material], hit = false;
      for (var i = 0; i < mats.length; i++) {
        var kind = kindOf(o, mats[i]);
        if (!kind) continue;
        if (kind === 'vtx' && !o.geometry.getAttribute('frLight')) {
          o.geometry.setAttribute('frLight', o.geometry.getAttribute('_fr_light'));
        }
        mats[i] = bakedMaterial(mats[i], kind);
        hit = true;
      }
      if (!hit) return;
      o.material = arr ? mats : mats[0];
      count++;
    });
    page.light.light = ST.light.light;
    page.light.materials = made.size;
    page.light.meshes = count;
    page.light.sunMatte = !all;
    page.light.sun = uniforms.uFrSun.value;
    return {};
  }

  // ---------------------------------------------------------------- moving cables, ropes, hoses (task 0142)
  // A part with userData.fr_tube is drawn by the page: fr_tubes.js works out its rings at the time shown, a float
  // texture (3 texels a ring) carries them to the vertex shader, which builds each ring (Blender's: ring point j at
  // angle 2πj/sides, centre + r (cos N + sin (T x N))). The file's own mesh of it (the frame shown) is not drawn. The
  // cable looks (cable_looks.py) are a patch of the part's own material: the power cable's stripes, the wire rope's
  // strands, wires and grease, the served cable's yarn and marker bands (task 0158), from s (metres along the cable),
  // the angle round it and the metres paid out.
  var tubes = [];
  var TUBE_HEAD = [
    'uniform highp sampler2D uFrTube;',
    'uniform int uFrW;',
    'uniform float uFrR;',
    'uniform float uFrSides;',
    'uniform float uFrLast;',
    'attribute vec3 frRing;',
    'varying vec2 vFrSt;',
    'vec4 frTex( int i ) { return texelFetch( uFrTube, ivec2( i % uFrW, i / uFrW ), 0 ); }',
    'void frTubePoint( out vec3 p, out vec3 n ) {',
    '  int ri = int( frRing.x + 0.5 );',
    '  vec4 a = frTex( ri * 3 );',
    '  vec3 N = frTex( ri * 3 + 1 ).xyz;',
    '  vec3 Tg = frTex( ri * 3 + 2 ).xyz;',
    '  vec3 B = cross( Tg, N );',
    '  float th = frRing.y / uFrSides;',
    '  float ph = 6.283185307179586 * th;',
    '  vec3 radial = cos( ph ) * N + sin( ph ) * B;',
    '  p = a.xyz + ( frRing.z > 1.5 ? vec3( 0.0 ) : uFrR * radial );',
    '  n = frRing.z > 0.5 ? ( frRing.x < 0.5 ? -Tg : Tg ) : radial;',
    '  vFrSt = vec2( a.w, th );',
    '}'].join('\n');
  var LOOK_HEAD = [
    'varying vec2 vFrSt;',
    'uniform float uFrPay;',
    'uniform float uFrPitch;',
    'uniform float uFrStarts;',
    'uniform float uFrWidth;',
    'uniform vec3 uFrStripe;',
    'uniform float uFrStripeRough;',
    'uniform float uFrEdge;',
    'uniform float uFrWires;',
    'uniform float uFrSlant;',
    'uniform vec3 uFrGrease;',
    'uniform float uFrGreaseAmount;',
    'uniform float uFrGreaseMetal;',
    'uniform float uFrGreaseRough;',
    'uniform float uFrWireDark;',
    'uniform float uFrStrandR;',
    'uniform float uFrWireH;',
    'uniform float uFrBump;',
    // the served cable (task 0158)
    'uniform float uFrCount;',
    'uniform float uFrGap;',
    'uniform float uFrYarnPitch;',
    'uniform float uFrYarnStarts;',
    'uniform float uFrRadius;',
    'uniform float uFrWear;',
    'uniform float uFrBandWear;',
    'uniform float uFrBandStarts;',
    'uniform vec3 uFrYarn;',
    'uniform vec3 uFrBand;',
    'uniform vec3 uFrDust;',
    'uniform float uFrVariation;',
    'uniform float uFrFibres;',
    'uniform float uFrRag;',
    'uniform float uFrStrandH;',
    'uniform float uFrYarnRough;',
    'uniform float uFrPaintRough;',
    // value noise 0 … 1 (not Blender's numbers, the same kind of look)
    'float frHash( vec3 p ) { p = fract( p * 0.3183099 + 0.1 ); p *= 17.0;',
    '  return fract( p.x * p.y * p.z * ( p.x + p.y + p.z ) ); }',
    'float frNoise( vec3 x ) { vec3 i = floor( x ), f = fract( x ); f = f * f * ( 3.0 - 2.0 * f );',
    '  return mix( mix( mix( frHash( i ), frHash( i + vec3( 1, 0, 0 ) ), f.x ),',
    '                   mix( frHash( i + vec3( 0, 1, 0 ) ), frHash( i + vec3( 1, 1, 0 ) ), f.x ), f.y ),',
    '              mix( mix( frHash( i + vec3( 0, 0, 1 ) ), frHash( i + vec3( 1, 0, 1 ) ), f.x ),',
    '                   mix( frHash( i + vec3( 0, 1, 1 ) ), frHash( i + vec3( 1, 1, 1 ) ), f.x ), f.y ), f.z ); }',
    'float frFbm( vec3 x ) { return 0.5 * frNoise( x ) + 0.3 * frNoise( 2.03 * x ) + 0.2 * frNoise( 4.01 * x ); }',
    'float frBand( float x, float c, float hw, float px ) {',
    '  float d = min( abs( x - c ), min( abs( x - c + uFrPitch ), abs( x - c - uFrPitch ) ) );',
    '  return clamp( ( hw - d ) / px + 0.5, 0.0, 1.0 ); }',
    // a height (m) on the surface -> the normal it gives (screen-space derivatives, like a Bump node)
    'vec3 frBumped( vec3 pos, vec3 nrm, float h, float strength ) {',
    '  vec3 sx = dFdx( pos ), sy = dFdy( pos );',
    '  vec3 r1 = cross( sy, nrm ), r2 = cross( nrm, sx );',
    '  float det = dot( sx, r1 );',
    '  vec3 grad = sign( det ) * ( dFdx( h ) * r1 + dFdy( h ) * r2 );',
    '  vec3 bumped = normalize( abs( det ) * nrm - grad );',
    '  return normalize( mix( nrm, bumped, strength ) );',
    '}'].join('\n');
  var POWER_COLOR = [
    '  float frU = ( vFrSt.x - uFrPay ) / uFrPitch;',
    '  float frPh = frU + floor( uFrStarts + 0.5 ) * vFrSt.y;',
    '  float frHalf = 0.5 * uFrWidth;',
    '  float frDist = abs( fract( frPh - frHalf + 0.5 ) - 0.5 );',
    '  float frE = max( max( min( uFrEdge, min( uFrWidth, 1.0 - uFrWidth ) ), 1e-6 ), 0.75 * fwidth( frPh ) );',
    '  float frLook = clamp( ( frHalf - frDist ) / frE + 0.5, 0.0, 1.0 );',
    '  diffuseColor.rgb = mix( diffuseColor.rgb, uFrStripe, frLook );'].join('\n');
  var ROPE_COLOR = [
    '  float frN = max( abs( floor( uFrStarts + 0.5 ) ), 1.0 );',
    '  float frU = ( vFrSt.x - uFrPay ) / uFrPitch;',
    '  float frNu = frN * frU;',
    '  float frPh = frNu + floor( uFrStarts + 0.5 ) * vFrSt.y;',
    '  float frF = fract( frPh );',
    '  float frX = 2.0 * frF - 1.0;',
    '  float frH = sqrt( max( 1.0 - frX * frX, 0.0 ) );',
    '  float frWire = abs( sin( ( frF - frNu * ( 1.0 + uFrSlant ) ) * uFrWires * 3.141592653589793 ) );',
    '  float frPx = 1.0 / max( fwidth( frPh ), 1e-6 );',                // pixels per strand
    '  float frFadeS = smoothstep( 1.5, 4.0, frPx );',
    '  float frFadeW = smoothstep( 1.5, 4.0, frPx / max( uFrWires, 1.0 ) );',
    '  float frGreaseK = clamp( clamp( ( 0.7 - frH ) / 0.5, 0.0, 1.0 ) * uFrGreaseAmount, 0.0, 1.0 );',
    '  float frLine = clamp( ( 1.0 - frWire ) * frFadeW * uFrWireDark, 0.0, 1.0 );',
    '  diffuseColor.rgb = mix( mix( diffuseColor.rgb, vec3( 0.0 ), frLine ), uFrGrease, frGreaseK );',
    '  float frLook = frGreaseK;',
    '  float frRelief = ( frH * frFadeS + frWire * frFadeW * uFrWireH ) * uFrPitch * uFrStrandR;'].join('\n');

  var SERVED_COLOR = [
    '  float frSp = vFrSt.x - uFrPay;',
    '  float frTh = 6.283185307179586 * vFrSt.y;',
    '  vec2 frCs = vec2( cos( frTh ), sin( frTh ) );',
    '  float frG = frSp / uFrYarnPitch + floor( uFrYarnStarts + 0.5 ) * vFrSt.y;',
    '  float frX = 2.0 * fract( frG ) - 1.0;',
    '  float frH = sqrt( max( 1.0 - frX * frX, 0.0 ) );',
    '  float frNa = abs( floor( uFrYarnStarts + 0.5 ) );',
    '  float frStrand = mod( floor( frG ), frNa > 0.5 ? frNa : 1.0e7 );',   // round the serving: no seam
    '  float frGm = fract( frG ) + frStrand;',
    '  float frShade = 1.0 + ( frHash( vec3( frStrand, 0.37, 1.7 ) ) - 0.5 ) * 2.0 * uFrVariation;',
    '  float frAlong = uFrRadius / ( 4.0 * uFrYarnPitch );',
    '  float frFibre = clamp( ( frNoise( vec3( frGm * uFrFibres, frCs * frAlong ) ) - 0.3 ) / 0.4, 0.0, 1.0 );',
    '  vec3 frWhere = vec3( frSp, frCs * uFrRadius );',
    '  float frLo = 0.75 - 0.3 * uFrWear;',
    '  float frDust = clamp( clamp( ( frFbm( frWhere * 14.0 ) - frLo ) / max( 0.8 - frLo, 1e-3 ), 0.0, 1.0 )',
    '                        * ( 1.2 - frH ) * ( 0.8 * uFrWear + 0.1 ), 0.0, 1.0 );',
    '  float frPx = max( length( fwidth( vec2( frSp, frCs.x * uFrRadius ) ) ), 1e-5 );',
    '  float frHalf = 0.5 * uFrWidth;',
    '  float frXb = mod( frSp + floor( uFrBandStarts + 0.5 ) * uFrPitch * vFrSt.y, uFrPitch );',
    '  float frJag = ( frFbm( frWhere * 40.0 ) - 0.5 ) * 1.4 + ( frHash( vec3( frStrand, 5.1, 0.3 ) ) - 0.5 ) * 0.6;',
    '  float frXr = frXb + frJag * 2.0 * uFrRag * ( 0.33 + 0.67 * uFrBandWear );',
    '  float frC2 = uFrWidth + uFrGap + frHalf;',
    '  float frDrawn = max( frBand( frXr, frHalf, frHalf, frPx ),',
    '                       uFrCount > 1.5 ? frBand( frXr, frC2, frHalf, frPx ) : 0.0 );',
    '  float frSLo = 0.62 - 0.18 * uFrBandWear;',
    '  float frSmudge = clamp( clamp( ( frFbm( frWhere * 6.0 ) - frSLo ) / 0.12, 0.0, 1.0 ) * ( 0.8 * uFrBandWear + 0.1 ), 0.0, 1.0 );',
    '  float frThin = ( 1.0 - frH ) * ( 1.0 - frH ) * uFrBandWear;',
    '  float frLook = frDrawn * ( 1.0 - max( frSmudge, frThin ) );',
    '  float frK = frShade * ( 1.0 + ( frFibre - 0.5 ) * 0.5 ) * ( 0.55 + 0.45 * frH );',
    '  vec3 frYarnC = mix( uFrYarn * frK, uFrDust, frDust );',
    '  diffuseColor.rgb = mix( frYarnC, uFrBand * ( 0.75 + 0.25 * frH ), frLook );',
    '  float frFade = smoothstep( 1.5, 4.0, uFrYarnPitch / frPx );',
    '  float frRelief = ( 0.85 * frH + 0.15 * frFibre ) * frFade * uFrYarnPitch * uFrStrandH;'].join('\n');

  function tubeMaterial(src, tb) {
    var look = tb.spec.look || null, kind = look ? look.kind : 'PLAIN';
    var m = src.clone();
    if (src.userData && src.userData.frWet) {          // rain on/off in the menu reaches the copy too
      m.userData.frWet = true;
      m.userData.frDry = { roughness: src.userData.frDry.roughness, color: src.userData.frDry.color.clone() };
      wet.push(m);
    }
    var u = tb.uniforms;
    m.onBeforeCompile = function (sh) {
      Object.assign(sh.uniforms, u);
      var v = sh.vertexShader;
      if (v.indexOf('#include <beginnormal_vertex>') < 0 || v.indexOf('#include <begin_vertex>') < 0) {
        page.errors.push('tubes: three.js shader has changed (vertex)'); mark();
      }
      sh.vertexShader = TUBE_HEAD + '\n' + v
        .replace('#include <beginnormal_vertex>', 'vec3 frP; vec3 frNr; frTubePoint( frP, frNr );\nvec3 objectNormal = frNr;')
        .replace('#include <begin_vertex>', 'vec3 transformed = frP;');
      if (kind === 'PLAIN') return;
      var f = sh.fragmentShader;
      ['#include <color_fragment>', '#include <roughnessmap_fragment>', '#include <metalnessmap_fragment>',
       '#include <normal_fragment_maps>'].forEach(function (inc) {
        if (f.indexOf(inc) < 0) { page.errors.push('tubes: three.js shader has changed (' + inc + ')'); mark(); }
      });
      f = LOOK_HEAD + '\n' + f.replace('#include <color_fragment>', '#include <color_fragment>\n' +
                                       (kind === 'ROPE' ? ROPE_COLOR : kind === 'SERVED' ? SERVED_COLOR : POWER_COLOR));
      if (kind === 'SERVED') {
        f = f.replace('#include <roughnessmap_fragment>',
                      '#include <roughnessmap_fragment>\nroughnessFactor = mix( uFrYarnRough, uFrPaintRough, frLook );')
             .replace('#include <metalnessmap_fragment>',
                      '#include <metalnessmap_fragment>\nmetalnessFactor = 0.0;')
             .replace('#include <normal_fragment_maps>',
                      '#include <normal_fragment_maps>\nnormal = frBumped( - vViewPosition, normal, frRelief, uFrBump );');
      } else if (kind === 'ROPE') {
        f = f.replace('#include <roughnessmap_fragment>',
                      '#include <roughnessmap_fragment>\nroughnessFactor = mix( roughnessFactor, uFrGreaseRough, frLook );')
             .replace('#include <metalnessmap_fragment>',
                      '#include <metalnessmap_fragment>\nmetalnessFactor = mix( metalnessFactor, uFrGreaseMetal, frLook );')
             .replace('#include <normal_fragment_maps>',
                      '#include <normal_fragment_maps>\nnormal = frBumped( - vViewPosition, normal, frRelief, uFrBump );');
      } else {
        f = f.replace('#include <roughnessmap_fragment>',
                      '#include <roughnessmap_fragment>\nroughnessFactor = mix( roughnessFactor, uFrStripeRough, frLook );');
      }
      sh.fragmentShader = f;
    };
    m.customProgramCacheKey = function () { return 'fr-tube-' + kind; };
    m.needsUpdate = true;
    return m;
  }

  function depthMaterial(tb) {
    var d = new T.MeshDepthMaterial({ depthPacking: T.RGBADepthPacking });
    d.onBeforeCompile = function (sh) {
      Object.assign(sh.uniforms, tb.uniforms);
      sh.vertexShader = TUBE_HEAD + '\n' + sh.vertexShader.replace('#include <begin_vertex>',
        'vec3 frP; vec3 frNr; frTubePoint( frP, frNr );\nvec3 transformed = frP;');
    };
    d.customProgramCacheKey = function () { return 'fr-tube-depth'; };
    return d;
  }

  // the tube's triangles: (sides + 1) points a ring (the seam twice: the angle runs 0 … 1), a cap at both ends
  function tubeGeometry(rings, sides) {
    var wall = rings * (sides + 1), cap = sides + 2, nv = wall + 2 * cap;
    var ring = new Float32Array(nv * 3), idx = [], r, j, o;
    for (r = 0; r < rings; r++) {
      for (j = 0; j <= sides; j++) { o = (r * (sides + 1) + j) * 3; ring[o] = r; ring[o + 1] = j; ring[o + 2] = 0; }
    }
    for (r = 0; r < rings - 1; r++) {
      for (j = 0; j < sides; j++) {
        var a = r * (sides + 1) + j, b = a + 1, c = a + sides + 1, d = c + 1;
        idx.push(a, c, b, b, c, d);
      }
    }
    [0, rings - 1].forEach(function (rr, e) {
      var base = wall + e * cap;
      o = base * 3; ring[o] = rr; ring[o + 1] = 0; ring[o + 2] = 2;               // the cap's middle
      for (j = 0; j <= sides; j++) { o = (base + 1 + j) * 3; ring[o] = rr; ring[o + 1] = j; ring[o + 2] = 1; }
      for (j = 0; j < sides; j++) {
        if (e === 0) idx.push(base, base + 2 + j, base + 1 + j); else idx.push(base, base + 1 + j, base + 2 + j);
      }
    });
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(new Float32Array(nv * 3), 3));
    g.setAttribute('frRing', new T.BufferAttribute(ring, 3));
    g.setIndex(idx);
    return g;
  }

  function lookUniforms(look) {
    var L0 = look || {};
    var c = function (v) { return new T.Vector3(v[0], v[1], v[2]); };
    return {
      uFrPay: { value: 0 }, uFrPitch: { value: +L0.pitch || 1 }, uFrStarts: { value: +L0.starts || 0 },
      uFrWidth: { value: +L0.width || 0 }, uFrStripe: { value: c(L0.stripe || [1, 1, 0]) },
      uFrStripeRough: { value: L0.stripe_rough != null ? +L0.stripe_rough : 0.4 }, uFrEdge: { value: +L0.edge || 0.01 },
      uFrWires: { value: +L0.wires || 6 }, uFrSlant: { value: +L0.slant || 0 }, uFrGrease: { value: c(L0.grease || [0, 0, 0]) },
      uFrGreaseAmount: { value: +L0.grease_amount || 0 }, uFrGreaseMetal: { value: +L0.grease_metallic || 0 },
      uFrGreaseRough: { value: +L0.grease_rough || 0.5 }, uFrWireDark: { value: +L0.wire_dark || 0 },
      uFrStrandR: { value: +L0.strand_radius || 0 }, uFrWireH: { value: +L0.wire_height || 0 },
      uFrBump: { value: +L0.bump || 0 },
      uFrCount: { value: +L0.count || 1 }, uFrGap: { value: +L0.gap || 0 },
      uFrYarnPitch: { value: +L0.yarn_pitch || 0.0025 }, uFrYarnStarts: { value: +L0.yarn_starts || 0 },
      uFrRadius: { value: +L0.radius || 0.15 }, uFrWear: { value: +L0.wear || 0 },
      uFrBandWear: { value: +L0.band_wear || 0 }, uFrBandStarts: { value: +L0.band_starts || 0 }, uFrYarn: { value: c(L0.yarn || [0.005, 0.005, 0.005]) },
      uFrBand: { value: c(L0.band || [0.88, 0.55, 0]) }, uFrDust: { value: c(L0.dust || [0.1, 0.1, 0.09]) },
      uFrVariation: { value: +L0.variation || 0 }, uFrFibres: { value: +L0.fibres || 5 },
      uFrRag: { value: +L0.rag || 0 }, uFrStrandH: { value: +L0.strand_height || 0 },
      uFrYarnRough: { value: L0.yarn_rough != null ? +L0.yarn_rough : 0.8 },
      uFrPaintRough: { value: L0.paint_rough != null ? +L0.paint_rough : 0.6 } };
  }

  // the parts with extras.fr_tube: their arrays read from the file, then the drawn tube put in place of the mesh
  function setupTubes(gltf) {
    var holders = [];
    gltf.scene.traverse(function (o) { if (o.userData && o.userData.fr_tube) holders.push(o); });
    if (!holders.length || !window.FRTubes) return Promise.resolve();
    var parser = gltf.parser;
    return Promise.all(holders.map(function (o) {
      var spec = o.userData.fr_tube, keys = window.FRTubes.KEYS.filter(function (k) {
        return typeof spec[k] === 'number' && spec[k] === Math.floor(spec[k]) && (k !== 'pay' || spec.pay_t != null);
      });
      return Promise.all(keys.map(function (k) { return parser.getDependency('accessor', spec[k]); })).then(function (got) {
        var a = {};
        keys.forEach(function (k, i) { a[k] = got[i].array; });
        var tb = window.FRTubes.make(spec, a);
        var w = Math.min(tb.rings * 3, 2048), h = Math.ceil(tb.rings * 3 / w);
        var buf = new Float32Array(w * h * 4);
        var tex = new T.DataTexture(buf, w, h, T.RGBAFormat, T.FloatType);
        tex.minFilter = tex.magFilter = T.NearestFilter;
        tex.generateMipmaps = false;
        tb.texture = tex;
        tb.buffer = buf;
        tb.uniforms = Object.assign({ uFrTube: { value: tex }, uFrW: { value: w }, uFrR: { value: +spec.r || 0.01 },
                                      uFrSides: { value: +spec.sides || 12 }, uFrLast: { value: tb.rings - 1 } },
                                    lookUniforms(spec.look));
        var src = null;
        o.traverse(function (c) {
          if (c.isMesh && !c.userData.frTube) {
            if (!src) src = Array.isArray(c.material) ? c.material[0] : c.material;
            c.geometry.setDrawRange(0, 0);          // the file's own shape of it (the frame shown): not drawn
            c.castShadow = false;
          }
        });
        var mesh = new T.Mesh(tubeGeometry(tb.rings, +spec.sides || 12),
                              tubeMaterial(src || new T.MeshStandardMaterial({ color: 0x222222 }), tb));
        mesh.userData.frTube = true;
        mesh.frustumCulled = false;
        mesh.castShadow = mesh.receiveShadow = !!ST.shadows;
        mesh.customDepthMaterial = depthMaterial(tb);
        mesh.name = (o.name || 'tube') + ' (drawn)';
        o.add(mesh);
        tb.mesh = mesh;
        tb.node = o;
        tb.last = null;
        tubes.push(tb);
      });
    })).then(function () {
      page.info.tubes = tubes.length;
      tubes.forEach(function (tb) { page.duration = Math.max(page.duration, tb.duration); });
      page.animated = !!ST.animated && page.duration > 0;
      updateTubes(0);
    });
  }

  function updateTubes(t) {
    for (var i = 0; i < tubes.length; i++) {
      var tb = tubes[i];
      if (tb.last !== null && (!tb.moves || tb.last === t)) continue;
      tb.at(t);
      var d = tb.fill();
      tb.mesh.visible = !tb.empty;
      if (!tb.empty) { tb.buffer.set(d); tb.texture.needsUpdate = true; }
      tb.uniforms.uFrPay.value = tb.pay;
      tb.last = t;
    }
  }

  // task 0135: the drawn tubes' centre lines for the part tools (their shape is made on the graphics card: a ray
  // cannot hit their triangles); cp in the node's coordinates (three's axes), r in metres
  page.tubeLines = function () {
    return tubes.map(function (tb) {
      return { node: tb.node, mesh: tb.mesh, cp: tb.cp, count: tb.count, r: tb.uniforms.uFrR.value, shown: tb.mesh.visible };
    });
  };

  // tests (?tubes=1): every drawn tube's centre line now, Blender world coordinates (m), at most 64 points each
  function tubeProbe() {
    var out = [], v = new T.Vector3();
    tubes.forEach(function (tb) {
      tb.node.updateWorldMatrix(true, false);
      var pts = [], step = Math.max(1, Math.ceil(tb.count / 64));
      for (var i = 0; i < tb.count; i += step) {
        v.set(tb.cp[i * 3], tb.cp[i * 3 + 1], tb.cp[i * 3 + 2]).applyMatrix4(tb.node.matrixWorld);
        pts.push([+v.x.toFixed(5), +(-v.z).toFixed(5), +v.y.toFixed(5)]);
      }
      out.push({ name: tb.node.name, count: tb.count, pay: tb.pay, points: pts });
    });
    document.documentElement.dataset.frTubes = JSON.stringify(out);
  }

  // ?places=1 (task 0175): every animated node's place as three.js plays it – {node index: [x y z, qx qy qz qw,
  // sx sy sz]} in the file's own coordinates – so the tests compare the packed keys with the app's frames
  var placed = null;
  function placeProbe() {
    var gltf = page.gltf;
    if (!gltf) return;
    if (!placed) {
      placed = [];
      gltf.scene.traverse(function (o) {
        var as = gltf.parser.associations.get(o);
        if (as && as.nodes != null) placed.push([as.nodes, o]);
      });
    }
    var out = {};
    placed.forEach(function (p) {
      var o = p[1];
      out[p[0]] = [o.position.x, o.position.y, o.position.z, o.quaternion.x, o.quaternion.y, o.quaternion.z,
                   o.quaternion.w, o.scale.x, o.scale.y, o.scale.z];
    });
    document.documentElement.dataset.frPlaces = JSON.stringify(out);
  }

  // ?probe=: the colours of a few pixels of the frame just drawn (tests)
  function probe() {
    var w = gl.drawingBufferWidth, h = gl.drawingBufferHeight, px = new Uint8Array(4);
    var out = probes.map(function (p) {
      var x = Math.round(T.MathUtils.clamp(p[0], 0, 1) * (w - 1));
      var y = Math.round((1 - T.MathUtils.clamp(p[1], 0, 1)) * (h - 1));
      gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
      return [px[0], px[1], px[2], px[3]];
    });
    page.probe = out;
    document.documentElement.dataset.frProbe = JSON.stringify(out);
  }

  function prepare(gltf) {
    var root = gltf.scene;
    vesselGroup.add(root);
    root.updateMatrixWorld(true);
    var model = root.getObjectByName('Model') || root;
    page.gltf = gltf;                  // task 0135: the part tools read the file's face data and its meshes
    model.children.forEach(function (c) { c.userData.frPart = true; });    // a part's node: what a click picks
    var moves = [];
    model.traverse(function (o) {
      if (o.isMesh) {
        o.castShadow = !!ST.shadows; o.receiveShadow = !!ST.shadows;
        meshes.push(o);
        if (ST.rain) {
          var mats = Array.isArray(o.material) ? o.material : [o.material];
          mats.forEach(function (m) {
            if (m.userData.frWet || m.roughness === undefined) return;
            m.userData.frWet = true;
            m.userData.frDry = { roughness: m.roughness, color: m.color.clone() };   // rain off in the menu
            wet.push(m);
            var s = ST.rain.strength;
            m.roughness = m.roughness * (1 - 0.45 * s);
            m.color.multiplyScalar(1 - 0.25 * s);
          });
        }
      }
      var vm = o.userData && o.userData.fr_vm;
      if (vm === 'STILL' || vm === 'LEVEL') moves.push([o, vm]);
    });
    if (ST.light) { baked = bakedLight(meshes); }
    moves.forEach(function (pair) {   // parts that keep their place in the world (or stay level)
      var g = pair[1] === 'STILL' ? stillGroup : levelGroup;
      var holder = g.getObjectByName('fr-holder');
      if (!holder) {
        holder = new T.Group();
        holder.name = 'fr-holder';
        holder.quaternion.copy(model.quaternion);
        g.add(holder);
      }
      holder.add(pair[0]);
    });
    if (gltf.animations && gltf.animations.length) {
      mixer = new T.AnimationMixer(top);
      gltf.animations.forEach(function (clip) {
        mixer.clipAction(clip).play();
        page.duration = Math.max(page.duration, clip.duration);
      });
      page.animated = !!ST.animated && page.duration > 0;
    }
  }

  // ---------------------------------------------------------------- controls and the first view
  var controls = new T.OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = true;
  controls.target.copy(centre);
  controls.minDistance = R * 0.05;
  controls.maxDistance = hasSea ? Math.min(12000, R * 60) : R * 30;
  var HORIZON = Math.PI * 0.497;
  if (hasSea) controls.maxPolarAngle = HORIZON;
  // task 0143: the camera may dive (Camera under water); 0147 row 11: a saved view below the water or the floor is
  // shown where it is – no clamp while the camera is on a saved view, until the visitor drags
  var onView = false;
  function diveOn() { return !!UW && on.under !== false && on.dive !== false && on.sea !== false; }
  function polarNow() {
    var off = camera.position.clone().sub(controls.target), d = Math.max(off.length(), 1e-9);
    return Math.acos(T.MathUtils.clamp(off.y / d, -1, 1));
  }
  function limitPolar() {
    if (!hasSea) return;                  // the plain page never had a limit
    if (diveOn() || onView) { controls.maxPolarAngle = Math.PI; return; }
    // back to the horizon, never with a jump: the limit follows the camera up from where it is
    controls.maxPolarAngle = Math.max(HORIZON, Math.min(controls.maxPolarAngle, polarNow() + 1e-6));
  }
  controls.autoRotateSpeed = 1.0;            // auto-turn: one turn a minute
  var FOV = 30;

  // a view: {pos, target, fov}. The home view looks from theta (deg, about the vertical, 0 = +z) and phi (deg from
  // straight above) at ``at`` (default the model's middle), at ``o[2]`` model radii or far enough to see it all
  function homeView(o, at, fov) {
    o = o || [];
    var theta = (isFinite(o[0]) ? o[0] : 45) * Math.PI / 180, phi = (isFinite(o[1]) ? o[1] : 65) * Math.PI / 180;
    var target = at ? at.clone() : centre.clone();
    var f = fov || FOV;
    var vf = f * Math.PI / 360, hf = Math.atan(Math.tan(vf) * Math.max(camera.aspect, 0.2));
    var dist = isFinite(o[2]) ? o[2] * R : R / Math.sin(Math.min(vf, hf)) * 1.02;
    return { pos: new T.Vector3(target.x + dist * Math.sin(phi) * Math.sin(theta), target.y + dist * Math.cos(phi),
                                target.z + dist * Math.sin(phi) * Math.cos(theta)), target: target, fov: f };
  }
  function put(v) {
    camera.position.copy(v.pos);
    controls.target.copy(v.target);
    camera.fov = v.fov;
    camera.updateProjectionMatrix();
    controls.update();
  }
  function numbers(name, n) {
    var a = (Q.get(name) || '').split(',').map(parseFloat);
    return a.length === n && a.every(isFinite) ? a : null;
  }
  function firstView() {
    var at = numbers('at', 3), f = parseFloat(Q.get('fov'));
    put(homeView((Q.get('orbit') || '').split(',').map(parseFloat), at ? new T.Vector3(at[0], at[1], at[2]) : null,
                 isFinite(f) ? T.MathUtils.clamp(f, 5, 100) : FOV));
  }

  // flying to a view (saved views, Reset view): 0.9 s, eased
  var fly = null;
  function flyTo(v, seconds) {
    fly = { pos: camera.position.clone(), target: controls.target.clone(), fov: camera.fov, to: v,
            t0: performance.now(), ms: 1000 * (seconds == null ? 0.9 : seconds) };
    stopTurn();
    wake();
  }
  function stepFly(now) {
    var k = T.MathUtils.clamp((now - fly.t0) / Math.max(fly.ms, 1), 0, 1), e = k * k * (3 - 2 * k);
    camera.position.lerpVectors(fly.pos, fly.to.pos, e);
    controls.target.lerpVectors(fly.target, fly.to.target, e);
    camera.fov = fly.fov + (fly.to.fov - fly.fov) * e;
    camera.updateProjectionMatrix();
    if (k >= 1) { fly = null; changed('view'); }
  }
  controls.addEventListener('start', function () { fly = null; onView = false; moved = true; limitPolar(); input(); });
  controls.addEventListener('change', function () { wake(); });

  // the project's saved cameras (task 0134; Blender world, ``vfov``/``hfov`` of the render in degrees): the page
  // shows at least the render's frame, whatever the window's shape
  page.views = (ST.views || []).map(function (v, k) {
    return { name: String(v.name || 'View ' + (k + 1)), eye: b2t(v.eye), target: b2t(v.target),
             vfov: +v.vfov || FOV, hfov: +v.hfov || 0 };
  });
  function viewFov(v) {
    var f = v.vfov;
    if (v.hfov) f = Math.max(f, 2 * Math.atan(Math.tan(v.hfov * Math.PI / 360) / Math.max(camera.aspect, 0.2)) * 180 / Math.PI);
    return T.MathUtils.clamp(f, 5, 100);
  }
  page.goView = function (k) {
    var v = page.views[k];
    if (!v) return;
    onView = true;
    limitPolar();
    flyTo({ pos: v.eye.clone(), target: v.target.clone(), fov: viewFov(v) });
    changed('view');
  };
  page.resetView = function () { onView = false; moved = false; flyTo(homeView()); };
  // task 0179: the start view framed again when the free area changed (the player's controls laid out, the phone
  // turned) – only while the visitor has not moved the camera and no saved view is shown
  var moved = false;
  page.refit = function () {
    if (!page.ready || moved || onView || fly) return false;
    firstView();
    wake();
    return true;
  };
  page.drawInfo = function () {           // tests: what one picture costs (draw calls, triangles, programs)
    var r = renderer.info;
    return { calls: r.render.calls, triangles: r.render.triangles, programs: (r.programs || []).length };
  };
  page.setCamera = function (pos, target) {   // tests, the PC check: a camera place (three's coordinates), as a drag
    fly = null; onView = false; moved = true;
    camera.position.fromArray(pos); controls.target.fromArray(target);
    limitPolar(); controls.update(); wake();
  };
  page.cameraState = function () {          // tests: where the camera is (three's coordinates)
    return { pos: camera.position.toArray(), target: controls.target.toArray(), fov: camera.fov, flying: !!fly,
             onView: onView, under: underNow, dive: diveOn(), maxPolar: controls.maxPolarAngle };
  };

  // the view as a link: camera, moment and menu choices in the address (task 0134)
  page.viewLink = function () {
    var off = camera.position.clone().sub(controls.target), d = Math.max(off.length(), 1e-9);
    var theta = Math.atan2(off.x, off.z) * 180 / Math.PI, phi = Math.acos(T.MathUtils.clamp(off.y / d, -1, 1)) * 180 / Math.PI;
    var p = ['orbit=' + theta.toFixed(1) + ',' + phi.toFixed(1) + ',' + (d / R).toFixed(4),
             'at=' + [controls.target.x, controls.target.y, controls.target.z].map(function (x) { return x.toFixed(3); }).join(',')];
    if (Math.abs(camera.fov - FOV) > 0.05) p.push('fov=' + camera.fov.toFixed(1));
    if (moving() || page.paused || page.animated) p.push('time=' + elapsed.toFixed(2));
    if (page.paused) p.push('paused=1');
    if (page.speed !== 1) p.push('speed=' + page.speed);
    if (!auto) p.push('quality=' + level, 'auto=0');
    var off_ = page.items.filter(function (n) { return on[n] === false && !pageOff[n]; });
    if (off_.length) p.push('off=' + off_.join(','));
    if (page.turn) p.push('turn=1');
    if (page.sunLive && Math.abs(page.sunHour - 13) > 0.01) p.push('sun=' + page.sunHour.toFixed(2));
    return location.href.split('#')[0].split('?')[0] + '?' + p.join('&');
  };

  // ---------------------------------------------------------------- what is on the page (the settings menu)
  var on = {};
  page.items = [];
  if (hasSea) page.items.push('sea');
  if (ST.vessel) page.items.push('vessel');
  if (!plain) page.items.push('sky');
  if (ST.haze) page.items.push('haze');
  if (ST.rain) page.items.push('rain');
  if (ST.shadows) page.items.push('shadows');
  if (UW) page.items.push('under', 'dive');      // task 0143: Under the sea, Camera under water
  var offList = Q.has('off') ? Q.get('off').split(',') : (PREF.off || []);
  // the visitor chose Under the sea (link, or switched it): Auto leaves it alone (task 0135: a saved "off: []" from
  // another choice no longer counts)
  var underKept = Q.has('off') || (PREF.chose || []).indexOf('under') >= 0 || (PREF.off || []).indexOf('under') >= 0;
  page.items.forEach(function (n) { on[n] = offList.indexOf(n) < 0; });
  // 0147 row 21d: what the page itself switched off (no graphics card: shadows; Auto: Under the sea) is not the
  // visitor's choice – the link to the view leaves it out (the receiver's own browser decides)
  var pageOff = {}, switched = {};
  (PREF.chose || []).forEach(function (n) { switched[n] = true; });
  if (page.warned && !Q.has('off') && on.shadows !== false && !switched.shadows) { on.shadows = false; pageOff.shadows = true; }
  page.visitorOff = function () { return page.items.filter(function (n) { return on[n] === false && !pageOff[n]; }); };
  page.chosenItems = function () { return Object.keys(switched); };
  page.resetChosen = function () { switched = {}; };
  page.on = on;
  var PLAIN_BG = new T.Color('#F1F3F5'), bgKeep = null;
  function lightGround(yes) {             // dark text on a light ground (the plain form, or the sky switched off)
    var css = document.documentElement.style;
    css.setProperty('--bg', yes ? '#F1F3F5' : '#8FA6B5');
    css.setProperty('--ink', yes ? '#252E36' : '#F4F6F8');
    css.setProperty('--muted', yes ? '#5B6670' : '#D5DBE0');
    document.documentElement.classList.toggle('fr-light', !!yes);
  }
  function recompile() {
    scene.traverse(function (o) {
      (Array.isArray(o.material) ? o.material : o.material ? [o.material] : []).forEach(function (m) { m.needsUpdate = true; });
    });
    warm(2500);
  }
  function applyItems(first) {
    if (sea) sea.visible = on.sea !== false;
    if (rain) rain.visible = on.rain !== false;
    if (spray) spray.visible = on.rain !== false && on.sea !== false;
    wet.forEach(function (m) {
      var d = m.userData.frDry, s = on.rain === false ? 0 : ST.rain.strength;
      m.roughness = d.roughness * (1 - 0.45 * s);
      m.color.copy(d.color).multiplyScalar(1 - 0.25 * s);
    });
    if (!plain) {
      var skyOn = on.sky !== false;
      if (skyMesh) skyMesh.visible = skyOn;
      dome.visible = skyOn;
      if (!skyOn && scene.background !== PLAIN_BG) { bgKeep = scene.background; scene.background = PLAIN_BG; }
      if (skyOn && scene.background === PLAIN_BG) scene.background = bgKeep;
      lightGround(!skyOn);
    }
    var hz = ST.haze && on.haze !== false;
    var fogWas = scene.fog;
    scene.fog = hz ? fog : null;
    if (UW) {                              // task 0143: one fog for the haze and the water
      var uOn = on.under !== false && on.sea !== false;
      // off: the haze's own fog (or none), so no program carries the water's code (it costs the most without a
      // graphics card)
      scene.fog = uOn ? waterFog : hz ? fog : null;
      waterFog.near = hz ? ST.haze.density : 0;
      waterFog.far = uOn ? UW.light : 0;
      seaUniforms.uCutOn.value = uOn && uwCut ? 1 : 0;
      bedUniforms.uGroundOn.value = uOn && uwGround ? 1 : 0;
      seabed.visible = uOn;
      if (cutWalls) cutWalls.visible = uOn;
      if (soil) soil.visible = uOn;
      limitPolar();
    }
    domeUniforms.uHaze.value = hz ? Math.min(1, ST.haze.strength * 1.4) : 0;
    var sh = !!ST.shadows && on.shadows !== false, shWas = renderer.shadowMap.enabled;
    sun.castShadow = sh;
    renderer.shadowMap.enabled = sh;
    if (catcher) catcher.visible = sh;
    if (!sh) { sun.position.copy(sunDir); sun.target.position.set(0, 0, 0); }
    if (!first && (shWas !== sh || fogWas !== scene.fog)) recompile();
    wake();
    changed('items');
  }
  page.setItem = function (name, value, byPage) {
    if (page.items.indexOf(name) < 0) return;
    on[name] = !!value;
    if (byPage && !value) pageOff[name] = true; else { delete pageOff[name]; if (!byPage) switched[name] = true; }
    if (name === 'under') underKept = true;
    applyItems();
    if (!moving()) chain = false;
  };

  // ---------------------------------------------------------------- the sun over the day (live light only)
  var el0 = ST.sky.elevation, az0 = ST.sky.azimuth != null ? ST.sky.azimuth : 0, lastEnv = 0;
  page.sunLive = !ST.light && !photo;
  page.sunWhy = ST.light ? 'Light is baked into this model' : photo ? "The light comes from the project's 360° picture" : '';
  // hour 5 … 21: the export's sun at 13:00, rising and setting at 5 and 21, turning 100° each way
  page.setSunHour = function (h, final) {
    if (!page.sunLive) return;
    h = T.MathUtils.clamp(+h || 13, 5, 21);
    page.sunHour = h;
    elev = Math.max(0.5, el0 * Math.sin(Math.PI * (h - 5) / 16));
    var az = (az0 + (h - 13) / 8 * 100) * Math.PI / 180, e = elev * Math.PI / 180;
    sunLook();
    sunDir.copy(b2t([Math.sin(az) * Math.cos(e), Math.cos(az) * Math.cos(e), Math.sin(e)])).normalize();
    sun.color.copy(sunColour);
    sun.intensity = sunPower * strength;
    if (!sun.castShadow) { sun.position.copy(sunDir); sun.target.position.set(0, 0, 0); }
    domeUniforms.uSunDir.value.copy(sunDir);
    domeUniforms.uSunCol.value.copy(sunColour).multiplyScalar(skyBright);
    domeUniforms.uHazeCol.value.copy(horizon);
    domeUniforms.uGround.value.copy(ground);
    domeUniforms.uCloudCol.value.copy(clouds === 'OVERCAST' ? new T.Color(0.42, 0.44, 0.46) : new T.Color(0.95, 0.95, 0.97))
      .multiplyScalar(skyBright);
    if (skyMesh) {
      skyMesh.material.uniforms.sunPosition.value.copy(sunDir);
      skyMesh.material.uniforms.rayleigh.value = clouds === 'OVERCAST' ? 0.6 : 1.4 + low;
    }
    if (fog) fog.color.copy(horizon);
    if (waterFog) waterFog.color.copy(horizon);
    if (rainUniforms) rainUniforms.uColour.value.copy(horizon).lerp(new T.Color(0.9, 0.92, 0.95), 0.5);
    var now = performance.now();
    if (final || now - lastEnv > 300) {        // the sky's light on the parts: worked out again (a few ms)
      lastEnv = now;
      if (envTarget) envTarget.dispose();
      envTarget = pmrem.fromScene(envScene, 0, 0.1, 5000);
      scene.environment = envTarget.texture;
    }
    wake();
    changed('sun');
  };

  // ---------------------------------------------------------------- auto-turn: after ~8 s without input
  var lastInput = performance.now(), turnTimer = null;
  page.turn = Q.has('turn') ? Q.get('turn') === '1' : !!PREF.turn;
  function stopTurn() {
    if (page.turning) { page.turning = false; controls.autoRotate = false; changed('turn'); }
  }
  function armTurn() {
    clearTimeout(turnTimer);
    if (!page.turn) return;
    turnTimer = setTimeout(function () {
      if (page.turn && !fly && page.ready && performance.now() - lastInput >= 7900) {
        page.turning = true; controls.autoRotate = true; wake(); changed('turn');
      } else armTurn();
    }, Math.max(50, 8000 - (performance.now() - lastInput)));
  }
  function input() { lastInput = performance.now(); stopTurn(); armTurn(); }
  page.input = input;
  page.setTurn = function (v) { page.turn = !!v; if (!v) stopTurn(); armTurn(); changed('turn'); };
  canvas.addEventListener('pointerdown', input);
  canvas.addEventListener('wheel', input, { passive: true });

  // ---------------------------------------------------------------- quality
  var noteEl = document.getElementById('quality'), noteTimer = null;
  function note(text, seconds) {
    page.lastNote = text;
    // task 0179: the player shows it as a short message above its controls (it covered "Made with" on a phone)
    if (page.notify) { page.notify(text, seconds); if (noteEl) noteEl.textContent = text; return; }
    if (!noteEl) return;
    clearTimeout(noteTimer);
    noteEl.textContent = text;
    noteEl.style.display = text ? 'block' : 'none';
    if (text && seconds) noteTimer = setTimeout(function () { noteEl.style.display = 'none'; }, seconds * 1000);
  }
  function setLevel(name, why) {
    level = name;
    page.level = name;
    var l = L();
    resize();
    if (sea) {
      sea.geometry.dispose();
      sea.geometry = seaGeometry(l.seg);
      if (seaBelow) seaBelow.geometry = sea.geometry;
      if (rippleTex) rippleTex.dispose();
      rippleTex = rippleTexture(l.ripple);
      seaUniforms.uRipple.value = rippleTex;
      page.info.seaPoints = sea.geometry.attributes.position.count;
    }
    if (ST.shadows) {
      sun.shadow.mapSize.set(l.shadow, l.shadow);
      if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
    }
    if (rain) {
      var n = Math.round(l.rain * (0.3 + 0.7 * ST.rain.strength));
      rain.geometry.setDrawRange(0, 2 * n);
      page.info.rain = n;
    }
    if (spray) spray.geometry.setDrawRange(0, l.spray * SPRAY_BURSTS);
    if (why) note(why, 8);
    page.quality = auto ? 'AUTO' : level;
    warm(2000);
    wake();
    changed('quality');
  }
  page.setQuality = function (q) {
    if (q === 'AUTO') {
      auto = true;
      topLevel = ST.quality;
      setLevel(page.warned ? 'PHONE' : ST.quality);
    } else if (LEVELS.indexOf(q) >= 0) {
      auto = false;
      topLevel = q;
      setLevel(q);
    }
    page.auto = auto;
    page.quality = auto ? 'AUTO' : level;
    note('');
    changed('quality');
  };

  // task 0179: the part of the view the player's controls leave free (CSS px from each edge). The camera's frame (its
  // fov and aspect) is that rectangle, its middle the view's middle; the rest of the screen shows more round it
  // (three.js view offset). So the start view, Reset and every saved view sit in the free area, not behind buttons.
  var free = { top: 0, bottom: 0, left: 0, right: 0 };
  page.setFree = function (f) {
    var n = { top: +f.top || 0, bottom: +f.bottom || 0, left: +f.left || 0, right: +f.right || 0 };
    if (['top', 'bottom', 'left', 'right'].every(function (k) { return Math.abs(n[k] - free[k]) < 0.5; })) return false;
    free = n;
    resize();
    return true;
  };
  page.freeArea = function () {
    var w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    var f = freeOf(w, h);
    return { left: f.l, top: f.t, width: f.w, height: f.h };
  };
  function freeOf(w, h) {
    // never less than 40 % of the screen each way (a huge stack of controls must not shrink the model to a dot)
    var t = Math.max(0, free.top), b = Math.max(0, free.bottom), l = Math.max(0, free.left), r = Math.max(0, free.right);
    var sv = Math.min(1, 0.6 * h / Math.max(t + b, 1e-6)), sh = Math.min(1, 0.6 * w / Math.max(l + r, 1e-6));
    t *= sv; b *= sv; l *= sh; r *= sh;
    return { t: t, l: l, w: Math.max(1, w - l - r), h: Math.max(1, h - t - b) };
  }

  function resize() {
    var w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    var l = L();
    // pixels capped by count, not only by ratio (a 2560 x 1440 screen at scale 1.5 asked for 8 million at Best)
    var ratio = Math.min(window.devicePixelRatio || 1, l.pixel_ratio);
    if (l.pixels) ratio = Math.max(0.5, Math.min(ratio, Math.sqrt(l.pixels / Math.max(w * h, 1))));
    if (Math.abs(renderer.getPixelRatio() - ratio) > 1e-3) renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    var f = freeOf(w, h);
    camera.aspect = f.w / Math.max(f.h, 1);
    if (f.t || f.l || f.w !== w || f.h !== h) camera.setViewOffset(f.w, f.h, -f.l, -f.t, w, h);
    else camera.clearViewOffset();
    camera.updateProjectionMatrix();
    page.info.pixels = gl.drawingBufferWidth * gl.drawingBufferHeight;
    page.info.pixelRatio = ratio;
    wake();
  }
  window.addEventListener('resize', resize);

  // ---------------------------------------------------------------- drawing
  var elapsed = 0, lastBurst = -10, burst = 0, tmp = new T.Matrix4(), ONE = new T.Matrix4();
  if (Q.has('time') && isFinite(parseFloat(Q.get('time')))) elapsed = Math.max(0, parseFloat(Q.get('time')));
  var paused = Q.get('paused') === '1';
  Object.defineProperty(page, 'paused', {           // the site's own button (task 0111) sets it directly
    get: function () { return paused; },
    set: function (v) { paused = !!v; chain = false; wake(); changed('paused'); }, enumerable: true });
  var sp = parseFloat(Q.get('speed'));
  if (sp === 0.5 || sp === 1 || sp === 2) page.speed = sp;
  else if (PREF.speed === 0.5 || PREF.speed === 2) page.speed = PREF.speed;
  page.setTime = function (s) { elapsed = Math.max(0, +s || 0); page.time = elapsed; chain = false; wake(); changed('time'); };
  page.setSpeed = function (v) { page.speed = v === 0.5 || v === 2 ? v : 1; changed('speed'); };
  // the two ends of the hull at the waterline: spray where one dips into a wave (which end is the bow depends on how
  // the model was drawn)
  var midY = (ST.model.min[1] + ST.model.max[1]) / 2;
  var hullEnds = ST.vessel && ST.vessel.ends ? ST.vessel.ends
    : hasSea ? [[ST.model.min[0], midY, ST.sea.level], [ST.model.max[0], midY, ST.sea.level]] : [];
  var prevGap = hullEnds.map(function () { return 0; });
  var lowest = hasSea ? ST.sea.level + 1.5 * (ST.sea.amp || 0.25) + 0.3 : floorY;   // the camera stays above this

  // task 0143: under the sea
  var underNow = false;
  function bottomAt(x, z) {              // the lowest the camera (or what it looks at) may go: just over the seabed,
    if (uwGround && inBox(x, z)) return uwBed - uwGround.depth + 0.4;     // in the cut-away's pit over its floor
    return uwBed + 0.4;
  }
  function cameraUnder(tSea) {           // the camera is in the water (not in the cut-away box): a little either way
    if (!UW || on.sea === false) return false;           // of the wave's height, so a wave never makes it flicker
    var cx = camera.position.x, cz = camera.position.z;
    if (on.under !== false && inBox(cx, cz)) return false;
    var h = ST.sea.level + M.seaHeight(ST.sea, cx - ST.sea.origin[0], -cz - ST.sea.origin[1], tSea);
    return camera.position.y < h + (underNow ? 0.04 : -0.04);
  }
  function bedOffset(t, out) {           // where the seabed's own coordinates start at t (core.web3d_env.bed_offset)
    var mo = UW.motion;
    if (!mo) { out.set(UW.bed_xy[0], UW.bed_xy[1]); return out; }
    var ts = mo.t, span = ts[ts.length - 1];
    if (span > 0) t = t % span;
    var k = 0;
    while (k < ts.length - 2 && ts[k + 1] < t) k++;
    var f = T.MathUtils.clamp((t - ts[k]) / Math.max(ts[k + 1] - ts[k], 1e-9), 0, 1);
    out.set(mo.xy[k][0] + (mo.xy[k + 1][0] - mo.xy[k][0]) * f, mo.xy[k][1] + (mo.xy[k + 1][1] - mo.xy[k][1]) * f);
    return out;
  }
  page.underState = function () {        // tests: what the page does under the sea now
    return { under: !!UW, cut: !!uwCut, ground: !!uwGround, camera: underNow, dive: diveOn(), onView: onView,
             fog: scene.fog ? [scene.fog.near, scene.fog.far] : null,
             bed: UW ? bedOffset(ST.animated ? page.time % Math.max(page.duration, 1e-9) : 0, new T.Vector2()).toArray() : null };
  };

  function toThree(mB) {                // a column-major Blender matrix -> three: B2T * m * T2B
    tmp.fromArray(mB);
    return new T.Matrix4().multiplyMatrices(B2T, tmp).multiply(T2B);
  }

  function fitShadow() {
    // sideways the box follows what the camera sees (sharp shadows close up); along the sun it always holds the
    // whole model, so parts towards the sun still cast
    var dist = camera.position.distanceTo(controls.target);
    var r = Math.min(R * 1.15, Math.max(dist * 1.5, R * 0.06));
    var c = r < R ? controls.target : centre;
    sun.target.position.copy(c);
    sun.position.copy(c).addScaledVector(sunDir, R * 2.5);
    var cam = sun.shadow.camera;
    cam.left = cam.bottom = -r; cam.right = cam.top = r;
    cam.near = R * 0.02; cam.far = R * 5.5;
    cam.updateProjectionMatrix();
    sun.shadow.normalBias = 2.5 * r / L().shadow;
  }

  // something keeps moving: then a picture is drawn every frame (up to page.cap a second), else only on a change
  function moving() {
    if (frozen != null || paused) return false;
    return page.animated || (hasSea && !!ST.sea.moving && on.sea !== false) || (!!ST.vessel && on.vessel !== false) ||
      (!!rain && on.rain !== false);
  }
  page.moving = moving;

  function draw() {
    var t = frozen != null ? frozen : elapsed;
    page.time = elapsed;
    var tScene = ST.time.start + t;
    var dist = camera.position.distanceTo(controls.target);
    camera.near = T.MathUtils.clamp(dist * 0.01, 0.002, 20);
    camera.updateProjectionMatrix();
    limitPolar();
    if (onView) {
      // a saved view stays where it was saved (0147 row 11), also below the water or the floor
    } else if (diveOn()) {                 // task 0143: under the water, never into the seabed
      var tb = bottomAt(controls.target.x, controls.target.z);
      if (controls.target.y < tb) { camera.position.y += tb - controls.target.y; controls.target.y = tb; }
      var cb = bottomAt(camera.position.x, camera.position.z);
      if (camera.position.y < cb) camera.position.y = cb;
    } else {
      if (controls.target.y < lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0)) {   // never under the water
        var dy = lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0) - controls.target.y;
        controls.target.y += dy; camera.position.y += dy;
      }
      if (camera.position.y < lowest) camera.position.y = lowest;
    }
    if (mixer) mixer.setTime(ST.animated ? t : 0);
    if (wantPlaces) placeProbe();
    if (tubes.length) {            // the moment the mixer shows: the animation repeats (t = its length is its start)
      var tt = ST.animated ? t : 0;
      if (page.duration > 0) tt = tt % page.duration;
      updateTubes(tt);
      if (wantTubes) tubeProbe();
    }
    var vOn = ST.vessel && on.vessel !== false;
    if (ST.vessel) {
      vesselGroup.matrix.copy(vOn ? toThree(M.vesselMatrix(ST.vessel, tScene)) : ONE);
      levelGroup.matrix.copy(vOn ? toThree(M.vesselMatrix(ST.vessel, tScene, 'LEVEL')) : ONE);
      vesselGroup.matrixWorldNeedsUpdate = levelGroup.matrixWorldNeedsUpdate = true;
    }
    var tSea = hasSea && ST.sea.moving ? tScene : 0;
    if (sea) seaUniforms.uTime.value = tSea;
    if (UW) {                              // task 0143: the seabed's drift; the water round a camera under it
      var tb2 = ST.animated ? t : 0;
      if (page.duration > 0) tb2 = tb2 % page.duration;
      bedOffset(tb2, bedUniforms.uBedOff.value);
      var under = cameraUnder(tSea);
      if (under !== underNow) { underNow = under; changed('under'); }
      var skyOn = on.sky !== false && !plain, uOn2 = on.under !== false && on.sea !== false;
      waterDome.visible = uOn2;
      waterDome.material.uniforms.uFull.value = under ? 1 : 0;
      waterDome.position.copy(camera.position);
      bedAround.visible = uOn2 && under;
      // the sea seen from below only when the camera is low enough to see it (its waves cost every point again)
      if (seaBelow) seaBelow.visible = uOn2 && camera.position.y < ST.sea.level + 2 * (ST.sea.amp || 0.25) + 0.5;
      bedAround.position.x = camera.position.x;
      bedAround.position.z = camera.position.z;
      if (skyMesh) skyMesh.visible = skyOn && !under;
      if (dome) dome.visible = skyOn && !under;
    }
    domeUniforms.uTime.value = t;
    if (skyMesh) skyMesh.position.copy(camera.position);
    dome.position.copy(camera.position);

    if (rain) {
      rainUniforms.uTime.value = t;
      var bx = T.MathUtils.clamp(dist * 1.6, 6, 140);
      rainUniforms.uBox.value = bx;
      rainUniforms.uLen.value = Math.max(0.3, bx * 0.02);
      rainUniforms.uCentre.value.copy(camera.position).lerp(controls.target, 0.4);
    }
    if (spray && hullEnds.length && spray.visible) {
      var vmB = vOn ? M.vesselMatrix(ST.vessel, tScene) : null;
      var limit = 0.25 * seaUniforms.uAmpOwn.value;
      for (var e = 0; e < hullEnds.length; e++) {
        var end = hullEnds[e];
        var at = vmB ? M.apply(vmB, end[0], end[1], end[2]) : end;
        var hs = M.seaHeight(ST.sea, at[0] - ST.sea.origin[0], at[1] - ST.sea.origin[1], tSea);
        var gap = hs - (at[2] - ST.sea.level);          // water above this end's waterline
        if (gap > limit && prevGap[e] <= limit && t - lastBurst > 1.0) {
          sprayUniforms.uOrigin.value[burst].copy(b2t(at));
          sprayUniforms.uStart.value[burst] = t;
          burst = (burst + 1) % SPRAY_BURSTS;
          lastBurst = t;
          page.info.bursts = (page.info.bursts || 0) + 1;
        }
        prevGap[e] = gap;
      }
      sprayUniforms.uTime.value = t;
      sprayUniforms.uScale.value = T.MathUtils.clamp((ST.vessel ? ST.vessel.hull[1] : R) / 12, 0.15, 3);
      sprayUniforms.uPix.value = renderer.getPixelRatio() * canvas.clientHeight / 800;
    }
    if (sun.castShadow) fitShadow();
    for (var bd = 0; bd < page.beforeDraw.length; bd++) {      // task 0135: the part tools (cut plane, lines, card)
      try { page.beforeDraw[bd](t); } catch (e) { page.errors.push('tools: ' + (e && e.message || e)); }
    }
    renderer.render(scene, camera);
    page.frames++;
    if (probes.length) probe();
    if (page.frames < 4 || page.frames % 60 === 0) mark();
  }

  // the picture as a PNG (Screenshot): drawn now, without the page's buttons; the plain form on its light ground
  page.screenshot = function () {
    draw();
    var out = canvas;
    if (plain) {
      out = document.createElement('canvas');
      out.width = canvas.width; out.height = canvas.height;
      var c2 = out.getContext('2d');
      c2.fillStyle = '#F1F3F5';
      c2.fillRect(0, 0, out.width, out.height);
      c2.drawImage(canvas, 0, 0);
    }
    return out.toDataURL('image/png');
  };

  // frames per second: only pictures drawn one right after the other count (a pause, a hidden tab, a frozen page
  // or the first pictures after a change, while the graphics card prepares its programs, are not slow pictures)
  var scheduled = false, dirty = true, chain = false, lastDraw = 0, fpsTime = 0, fpsCount = 0, warmUntil = 0;
  var idleTimer = null, goodWindows = 0, lastLower = -1e9, lastRaise = -1e9;
  function warm(ms) { warmUntil = performance.now() + (ms || 1500); fpsTime = fpsCount = 0; goodWindows = 0; chain = false; }
  function wake() { dirty = true; schedule(); }
  page.wake = wake;
  function schedule() {
    if (scheduled || !page.ready || document.hidden || (maxFrames && page.frames >= maxFrames)) return;
    scheduled = true;
    requestAnimationFrame(tick);
  }
  function idle() {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      if (!scheduled && page.fps !== 0) { page.fps = 0; changed('fps'); mark(); }
    }, 1500);
  }
  function judge(now) {
    if (fpsTime < 2000) return;
    page.fps = fpsCount * 1000 / fpsTime;
    fpsTime = fpsCount = 0;
    changed('fps');
    var k = LEVELS.indexOf(level);
    // no graphics card named (the browser hides it) and still slow at the lightest level: probably software
    if (!page.warned && !page.gpu && level === 'PHONE' && page.fps < 15 && Q.get('soft') !== '0') {
      page.warned = 'probably';
      page.cap = 30;
      if (on.shadows && !Q.has('off') && !switched.shadows) page.setItem('shadows', false, true);
      changed('warned');
      mark();
    }
    if (!auto) return;
    // task 0143: at Phone and still slow, Auto switches Under the sea off (once; not when the visitor chose it)
    if (page.fps < 0.9 * AUTO_FPS && k === 0 && UW && on.under !== false && !underKept) {
      underKept = true;
      page.setItem('under', false, true);
      note('Under the sea switched off to keep it smooth (settings: switch it on again)', 8);
      return;
    }
    if (page.fps < 0.9 * AUTO_FPS && k > 0) {
      var lower = LEVELS[k - 1];
      page.lowered++;
      lastLower = now;
      goodWindows = 0;
      setLevel(lower, 'Quality ' + lower.charAt(0) + lower.slice(1).toLowerCase() + ': lowered to keep it smooth');
    } else if (!page.warned && page.fps >= Math.min(50, 0.8 * page.cap) && k < LEVELS.indexOf(topLevel)) {
      // room to spare twice in a row: one step up again; not soon after it had to come down from there
      goodWindows++;
      var wait = lastRaise > lastLower ? 8000 : now - lastRaise < 30000 ? 60000 : 8000;
      if (goodWindows >= 2 && now - lastLower > wait) {
        var higher = LEVELS[k + 1];
        page.raised++;
        lastRaise = now;
        setLevel(higher, 'Quality ' + higher.charAt(0) + higher.slice(1).toLowerCase() + ': raised again');
      }
    } else goodWindows = 0;
  }
  var AUTO_FPS = 30;

  function tick(now) {
    scheduled = false;
    if (document.hidden) { chain = false; return; }        // visibilitychange wakes it again
    var run = moving() || page.turning || !!fly || (probes.length > 0 && page.frames < (maxFrames || 4));
    // at most page.cap pictures a second (a 165 Hz screen asked for 165)
    if (lastDraw && now - lastDraw < 1000 / page.cap - 2) {
      if (run || dirty || chain) { scheduled = true; requestAnimationFrame(tick); }
      return;
    }
    var dt = chain ? Math.min((now - lastDraw) / 1000, 0.1) : 0;
    if (moving()) elapsed += dt * page.speed;
    if (fly) stepFly(now);
    var moved = controls.update(dt > 0 ? dt : null);       // damping after a drag, auto-turn
    if (!(dirty || run || moved)) { chain = false; idle(); return; }
    dirty = false;
    draw();
    if (chain && now > warmUntil && now - lastDraw < 1000) { fpsTime += now - lastDraw; fpsCount++; }
    lastDraw = now;
    chain = true;
    judge(now);
    changed('time');
    if (run || moved || dirty || page.turning) schedule();
    else { chain = false; idle(); }
  }
  function frame() { dirty = true; tick(performance.now()); }   // draw now (the first picture of a probing test)
  document.addEventListener('visibilitychange', function () {
    chain = false;
    warm(1500);
    if (!document.hidden) wake();
  });
  window.addEventListener('pageshow', function () { chain = false; warm(1500); wake(); });

  function start() {
    // task 0135: what the part tools (fr_tools.js) work with
    page.three = { T: T, scene: scene, camera: camera, renderer: renderer, controls: controls, canvas: canvas,
                   top: top, vessel: vesselGroup, B2T: B2T, T2B: T2B, box: box, R: R };
    var ld = document.getElementById('loading');
    if (ld) ld.style.display = 'none';
    page.ready = true;
    setLevel(level);
    applyItems(true);
    firstView();
    var sh = parseFloat(Q.get('sun'));
    if (page.sunLive && isFinite(sh)) page.setSunHour(sh, true);
    page.time = elapsed;
    warm(2500);
    mark();
    changed('ready');
    armTurn();
    // probing (tests): draw the first frame now – a headless browser may take its picture of the page before the
    // next animation frame comes
    if (probes.length) frame(); else wake();
  }

  // ---------------------------------------------------------------- load the model
  var loader = new T.GLTFLoader();
  loader.setMeshoptDecoder(T.MeshoptDecoder);
  // task 0175: the model's text read by the browser itself (a data: address; the old per-letter loop took 2 s on
  // the demo) and, in a packed page, unpacked by its own gzip (DecompressionStream)
  function slowBytes(text) {
    var s = atob(text), a = new Uint8Array(s.length);
    for (var k = 0; k < s.length; k++) a[k] = s.charCodeAt(k);
    return a.buffer;
  }
  function modelBytes(el) {
    var text = el.textContent.trim(), t0 = performance.now();
    var got = (window.fetch && Q.get('b64') !== 'slow' ?
      fetch('data:application/octet-stream;base64,' + text).then(function (r) { return r.arrayBuffer(); })
        .catch(function () { return slowBytes(text); }) :
      Promise.resolve().then(function () { return slowBytes(text); }));
    if (el.getAttribute('data-gzip') !== '1') return got;
    return got.then(function (buf) {
      if (typeof DecompressionStream === 'undefined')
        throw new Error('this browser cannot unpack the model (DecompressionStream): use a current Edge, Chrome, ' +
                        'Firefox or Safari');
      page.loadTimes = { read: performance.now() - t0 };
      var t1 = performance.now();
      return new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
        .then(function (out) { page.loadTimes.unpack = performance.now() - t1; return out; });
    });
  }
  try {
    var bad = function (e) { fail('The 3D model in this page could not be read.', 'model: ' + (e && e.message || e)); };
    var buf = null;
    var go = function () {
      try {
        loader.parse(buf, '', function (gltf) {
          try {
            prepare(gltf);
            setupTubes(gltf).then(function () { resize(); oneLess(); }, bad);   // task 0142
          } catch (e) { bad(e); }
        }, bad);
      } catch (e) { bad(e); }
    };
    modelBytes(document.getElementById('fr-glb')).then(function (b) {
      buf = b;
      if (T.MeshoptDecoder.ready) T.MeshoptDecoder.ready.then(go, bad); else go();
    }, bad);
  } catch (e) { fail('The 3D model in this page could not be read.', 'model: ' + e); }
  page.setLevel = function (name) { setLevel(name); };
})();
