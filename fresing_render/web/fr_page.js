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
                               turning: false, sunLive: false, sunHour: 13, sunWhy: '', listeners: [] };
  // what the visitor chose last time on this page (fr_player.js writes it; the link's own choices come first)
  var PREF_KEY = 'fresing-player:' + (location.pathname || document.title);
  var PREF = {};
  try { PREF = JSON.parse(window.localStorage.getItem(PREF_KEY) || '{}') || {}; } catch (e) { PREF = {}; }
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
                                     lowered: page.lowered, frames: page.frames });
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
  scene.fog = fog;

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
    sea = new T.Mesh(seaGeometry(L().seg), seaMat);
    sea.position.copy(b2t([S.origin[0], S.origin[1], S.level]));
    sea.frustumCulled = false;
    sea.receiveShadow = !!ST.shadows;
    scene.add(sea);
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
  if (hasSea) controls.maxPolarAngle = Math.PI * 0.497;
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
  controls.addEventListener('start', function () { fly = null; input(); });
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
    flyTo({ pos: v.eye.clone(), target: v.target.clone(), fov: viewFov(v) });
    changed('view');
  };
  page.resetView = function () { flyTo(homeView()); };
  page.cameraState = function () {          // tests: where the camera is (three's coordinates)
    return { pos: camera.position.toArray(), target: controls.target.toArray(), fov: camera.fov, flying: !!fly };
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
    var off_ = page.items.filter(function (n) { return on[n] === false; });
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
  var offList = Q.has('off') ? Q.get('off').split(',') : (PREF.off || []);
  page.items.forEach(function (n) { on[n] = offList.indexOf(n) < 0; });
  if (page.warned && !Q.has('off') && !PREF.off) on.shadows = false;       // no graphics card: no shadows
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
  page.setItem = function (name, value) {
    if (page.items.indexOf(name) < 0) return;
    on[name] = !!value;
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

  function resize() {
    var w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    var l = L();
    // pixels capped by count, not only by ratio (a 2560 x 1440 screen at scale 1.5 asked for 8 million at Best)
    var ratio = Math.min(window.devicePixelRatio || 1, l.pixel_ratio);
    if (l.pixels) ratio = Math.max(0.5, Math.min(ratio, Math.sqrt(l.pixels / Math.max(w * h, 1))));
    if (Math.abs(renderer.getPixelRatio() - ratio) > 1e-3) renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
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
    if (controls.target.y < lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0)) {   // never under the water
      var dy = lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0) - controls.target.y;
      controls.target.y += dy; camera.position.y += dy;
    }
    if (camera.position.y < lowest) camera.position.y = lowest;
    if (mixer) mixer.setTime(ST.animated ? t : 0);
    var vOn = ST.vessel && on.vessel !== false;
    if (ST.vessel) {
      vesselGroup.matrix.copy(vOn ? toThree(M.vesselMatrix(ST.vessel, tScene)) : ONE);
      levelGroup.matrix.copy(vOn ? toThree(M.vesselMatrix(ST.vessel, tScene, 'LEVEL')) : ONE);
      vesselGroup.matrixWorldNeedsUpdate = levelGroup.matrixWorldNeedsUpdate = true;
    }
    var tSea = hasSea && ST.sea.moving ? tScene : 0;
    if (sea) seaUniforms.uTime.value = tSea;
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
      if (on.shadows && !Q.has('off') && !PREF.off) page.setItem('shadows', false);
      changed('warned');
      mark();
    }
    if (!auto) return;
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
  try {
    var s = atob(document.getElementById('fr-glb').textContent.trim()), buf = new Uint8Array(s.length);
    for (var k = 0; k < s.length; k++) buf[k] = s.charCodeAt(k);
    var bad = function (e) { fail('The 3D model in this page could not be read.', 'model: ' + (e && e.message || e)); };
    var go = function () {
      try {
        loader.parse(buf.buffer, '', function (gltf) {
          try { prepare(gltf); resize(); oneLess(); } catch (e) { bad(e); }
        }, bad);
      } catch (e) { bad(e); }
    };
    if (T.MeshoptDecoder.ready) T.MeshoptDecoder.ready.then(go, bad); else go();
  } catch (e) { fail('The 3D model in this page could not be read.', 'model: ' + e); }
  page.setLevel = function (name) { setLevel(name); };
})();
