// Fresing Render web 3D page with surroundings (task 0106). Reads the settings block (#fr-env), the model (#fr-glb)
// and the pictures (#fr-pic-*) written by core/web3d_env.py, and shows the machine with its sea, vessel motion,
// sky, clouds, haze, rain, spray and a live sun – each only when the settings ask for it. Uses FRTHREE (three.js
// r180, three-viewer.min.js) and FRMath (fr_math.js). Nothing is fetched from the internet.
//
// URL options (for tests and for looking): ?quality=PHONE|BALANCED|BEST  ?auto=0  ?t=<seconds> (time stands still)
// ?orbit=<theta deg>,<phi deg>,<distance in model radii>  ?probe=<x>,<y>;<x>,<y>… (screen places 0 … 1 from the top
// left: their pixel colours after each frame go into data-fr-probe on <html>, for tests)
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
                               info: {}, light: { light: null, materials: 0, meshes: 0, plain: plain } };
  // the page's state in its own HTML (data-fr-state on <html>): the PC check reads it with a headless browser
  function mark() {
    var root = document.documentElement.dataset;
    root.frState = page.errors.length ? 'error: ' + page.errors.join(' | ').slice(0, 300)
      : page.ready ? 'ready ' + page.level + ' frames ' + page.frames : 'loading';
    if (ST.light || plain) root.frLight = JSON.stringify(page.light);
  }
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

  var scene = new T.Scene();
  var mn = b2t(ST.model.min), mx = b2t(ST.model.max);
  var box = new T.Box3().setFromPoints([mn, mx]);
  var centre = box.getCenter(new T.Vector3());
  var R = Math.max(box.getSize(new T.Vector3()).length() / 2, 0.05);
  var floorY = ST.floor != null ? ST.floor : ST.model.min[2];
  var hasSea = !!ST.sea;
  var camera = new T.PerspectiveCamera(30, 1, R * 0.01, hasSea ? 30000 : R * 400);

  // ---------------------------------------------------------------- level of quality
  var level = Q.get('quality') && LEVELS.indexOf(Q.get('quality').toUpperCase()) >= 0
    ? Q.get('quality').toUpperCase() : ST.quality;
  var auto = Q.has('auto') ? Q.get('auto') !== '0' : !!ST.auto;
  var frozen = Q.has('t') && isFinite(parseFloat(Q.get('t'))) ? parseFloat(Q.get('t')) : null;
  var maxFrames = Q.has('frames') ? parseInt(Q.get('frames'), 10) || 0 : 0;
  function L() { return ST.levels[level]; }

  // ---------------------------------------------------------------- the sun
  var sunDirB = ST.sky.sun;
  var sunDir = b2t(sunDirB).normalize();
  var elev = ST.sky.elevation;
  var clouds = ST.sky.clouds || 'NONE';
  var photo = ST.sky.kind === 'PHOTO';
  var strength = ST.sky.strength == null ? 1 : ST.sky.strength;
  var low = 1 - T.MathUtils.smoothstep(elev, 2, 35);           // 1 at sunrise, 0 above 35 degrees
  var sunColour = new T.Color(1.0, 0.96, 0.9).lerp(new T.Color(1.0, 0.62, 0.36), low);
  var sunPower = photo ? T.MathUtils.clamp(ST.sky.sun_share || 1, 0.3, 3.0)
                       : 3.2 * T.MathUtils.clamp(Math.sin(elev * Math.PI / 180) * 4, 0.05, 1);
  if (!photo && clouds === 'SOME') sunPower *= 0.8;
  if (!photo && clouds === 'OVERCAST') sunPower *= 0.12;
  var sun = new T.DirectionalLight(sunColour, sunPower * strength);
  scene.add(sun, sun.target);
  sun.position.copy(sunDir);          // the light comes from here (fitShadow moves both with shadows on); without this
                                      // three's default put the sun straight overhead when shadows were off
  sun.castShadow = !!ST.shadows;
  sun.shadow.bias = -0.0004;
  // a studio's or a photo's main light is broad, an overcast sun weak: lighter shadows than a clear sun's
  sun.shadow.intensity = photo ? 0.65 : clouds === 'OVERCAST' ? 0.4 : 1.0;

  // colours of the far distance (haze) and the ground below the horizon
  var horizon = ST.sky.horizon ? new T.Color().fromArray(ST.sky.horizon)
    : new T.Color(0.55, 0.64, 0.76).lerp(new T.Color(0.86, 0.6, 0.45), low * 0.8);
  if (!photo && clouds === 'OVERCAST') horizon = new T.Color(0.52, 0.55, 0.58);
  var skyBright = photo ? 1 : (0.35 + 0.65 * T.MathUtils.smoothstep(elev, -2, 25));
  if (!ST.sky.horizon) horizon.multiplyScalar(skyBright);
  var ground = hasSea ? new T.Color(0.012, 0.045, 0.055) : new T.Color(0.33, 0.32, 0.30).multiplyScalar(skyBright);

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
    scene.environment = pmrem.fromScene(envScene, 0, 0.1, 5000).texture;
    scene.environmentIntensity = strength;
  }

  // ---------------------------------------------------------------- haze
  if (ST.haze) scene.fog = new T.FogExp2(horizon.clone(), ST.haze.density);

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
    var S = ST.sea, waves = [], phases = [], ampOwn = 0;
    for (var i = 0; i < MAXW; i++) {
      var w = S.waves[i];
      waves.push(w ? new T.Vector4(w[0], w[1], w[2], w[3]) : new T.Vector4(0, 1, 0, 0.01));
      phases.push(w ? w[4] : 0);
      if (w && i < S.own) ampOwn += w[0];
    }
    seaUniforms = {
      uTime: { value: 0 }, uWave: { value: waves }, uPhase: { value: phases },
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
                 ' uniform float uPhase[' + MAXW + ']; uniform int uCount, uOwn; uniform sampler2D uRipple;' +
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
          '  float s = sin(ph), c = cos(ph);',
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
  var mixer = null, meshes = [], baked = null;

  // ---------------------------------------------------------------- baked light (task 0107)
  // Light factor F = scale * texel ^ curve (texel: the occlusion map read through UV channel 1, or the mesh's
  // _FR_LIGHT attribute, linear 0 … 1): the light a white matte surface gets there, 1 = open sky above. The page
  // multiplies it by its OWN light on an up-facing surface (sky: getIBLIrradiance(up) x environment intensity, in
  // place of the environment's own matte light iblIrradiance; with ALL also the sun on an up-facing surface, added to
  // the matte light ``irradiance`` that RE_IndirectDiffuse turns into Lambert light, as the live sun's). Reflections
  // stay, dimmed by min(1, luminance F) in corners. ALL: the sun gives no matte light on baked surfaces (it is in
  // the bake), only its highlight. A 360° photo or studio light has no sun of its own: both choices bake all of it,
  // so they work as ALL. three's own occlusion map (which multiplies) is not used on these materials.
  var BAKED_GLOBAL = [
    'uniform float uFrScale;',
    'uniform float uFrCurve;',
    'uniform vec3 uFrSunUp;'].join('\n');
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
                     uFrSunUp: { value: new T.Vector3() } };
    var patches = {}, sunAt = new T.Vector3();
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
          'iblIrradiance += frF * getIBLIrradiance( normalize( ( viewMatrix * vec4( 0.0, 1.0, 0.0, 0.0 ) ).xyz ) );'),
        '#if defined( RE_IndirectDiffuse )',      // the sun as plain Lambert light, as RE_Direct_Physical gives it
        '  irradiance += frF * uFrSunUp;',
        '#endif',
        '#if defined( RE_IndirectSpecular )',
        '  float frOcc = min( 1.0, dot( frF, vec3( 0.2126, 0.7152, 0.0722 ) ) );',
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
    return {
      sunUp: function () {                 // the sun on an up-facing surface (three's units: colour x intensity)
        var v = uniforms.uFrSunUp.value;
        if (!all) { v.set(0, 0, 0); return; }
        var d = sunAt.subVectors(sun.position, sun.target.position).normalize();    // as three lights with it
        var k = sun.intensity * Math.max(d.y, 0);
        v.set(sun.color.r * k, sun.color.g * k, sun.color.b * k);
      }
    };
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
            var s = ST.rain.strength;
            m.roughness = m.roughness * (1 - 0.45 * s);
            m.color.multiplyScalar(1 - 0.25 * s);
          });
        }
      }
      var vm = o.userData && o.userData.fr_vm;
      if (vm === 'STILL' || vm === 'LEVEL') moves.push([o, vm]);
    });
    if (ST.light) { baked = bakedLight(meshes); baked.sunUp(); }
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
      gltf.animations.forEach(function (clip) { mixer.clipAction(clip).play(); });
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
  function firstView() {
    var o = (Q.get('orbit') || '').split(',').map(parseFloat);
    var theta = (isFinite(o[0]) ? o[0] : 45) * Math.PI / 180, phi = (isFinite(o[1]) ? o[1] : 65) * Math.PI / 180;
    var vf = camera.fov * Math.PI / 360, hf = Math.atan(Math.tan(vf) * Math.max(camera.aspect, 0.2));
    var dist = isFinite(o[2]) ? o[2] * R : R / Math.sin(Math.min(vf, hf)) * 1.02;
    camera.position.set(centre.x + dist * Math.sin(phi) * Math.sin(theta), centre.y + dist * Math.cos(phi),
                        centre.z + dist * Math.sin(phi) * Math.cos(theta));
    controls.update();
  }

  // ---------------------------------------------------------------- quality
  var noteEl = document.getElementById('quality');
  function setLevel(name, why) {
    level = name;
    page.level = name;
    var l = L();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, l.pixel_ratio));
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
    if (why) {
      noteEl.textContent = why;
      noteEl.style.display = 'block';
    }
  }

  function resize() {
    var w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);

  // ---------------------------------------------------------------- every frame
  var clock = new T.Clock(), elapsed = 0, fpsFrames = 0, fpsSince = performance.now(), warmSince = fpsSince;
  var lastBurst = -10, burst = 0, tmp = new T.Matrix4();
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

  function frame() {
    var dt = Math.min(clock.getDelta(), 0.1);
    elapsed += dt;
    var t = frozen != null ? frozen : elapsed;
    var tScene = ST.time.start + t;
    var dist = camera.position.distanceTo(controls.target);
    camera.near = T.MathUtils.clamp(dist * 0.01, 0.002, 20);
    camera.updateProjectionMatrix();
    controls.update();
    if (controls.target.y < lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0)) {   // never under the water
      var dy = lowest - (hasSea ? 1.5 * (ST.sea.amp || 0.25) + 0.3 : 0) - controls.target.y;
      controls.target.y += dy; camera.position.y += dy;
    }
    if (camera.position.y < lowest) camera.position.y = lowest;
    if (mixer) mixer.setTime(ST.animated ? t : 0);
    if (ST.vessel) {
      vesselGroup.matrix.copy(toThree(M.vesselMatrix(ST.vessel, tScene)));
      levelGroup.matrix.copy(toThree(M.vesselMatrix(ST.vessel, tScene, 'LEVEL')));
      vesselGroup.matrixWorldNeedsUpdate = levelGroup.matrixWorldNeedsUpdate = true;
    }
    var tSea = hasSea && ST.sea.moving ? tScene : 0;
    if (sea) seaUniforms.uTime.value = tSea;
    domeUniforms.uTime.value = t;
    if (skyMesh) skyMesh.position.copy(camera.position);
    dome.position.copy(camera.position);
    if (baked) baked.sunUp();
    if (rain) {
      rainUniforms.uTime.value = t;
      var bx = T.MathUtils.clamp(dist * 1.6, 6, 140);
      rainUniforms.uBox.value = bx;
      rainUniforms.uLen.value = Math.max(0.3, bx * 0.02);
      rainUniforms.uCentre.value.copy(camera.position).lerp(controls.target, 0.4);
    }
    if (spray && hullEnds.length) {
      var vmB = ST.vessel ? M.vesselMatrix(ST.vessel, tScene) : null;
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
    if (ST.shadows) fitShadow();
    renderer.render(scene, camera);
    page.frames++;
    if (probes.length) probe();
    if (page.frames < 4 || page.frames % 60 === 0) mark();
    if (maxFrames && page.frames >= maxFrames) return;     // ?frames=N: stop drawing (pictures in tests)
    // frames per second (real clock time) and Auto
    var now = performance.now();
    if (document.hidden) { fpsFrames = 0; fpsSince = now; }
    else {
      fpsFrames++;
      var span = (now - fpsSince) / 1000;
      if (span >= 2 || (fpsFrames >= 2 && span >= 1 && fpsFrames / span < 10)) {
        page.fps = fpsFrames / span;
        if (auto && now - warmSince > 2500 && page.fps < 0.9 * 30 && LEVELS.indexOf(level) > 0) {
          var lower = LEVELS[LEVELS.indexOf(level) - 1];
          page.lowered++;
          setLevel(lower, 'Quality ' + lower.charAt(0) + lower.slice(1).toLowerCase() + ': lowered to keep it smooth');
          warmSince = performance.now();
        }
        fpsFrames = 0; fpsSince = performance.now();
      }
    }
    requestAnimationFrame(frame);
  }

  function start() {
    document.getElementById('loading').style.display = 'none';
    setLevel(level);
    firstView();
    page.ready = true;
    fpsSince = warmSince = performance.now();
    mark();
    // probing (tests): draw the first frame now – a headless browser may take its picture of the page before the
    // next animation frame comes
    if (probes.length) frame(); else requestAnimationFrame(frame);
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
  resize();
  page.setLevel = function (name) { setLevel(name); };
})();
