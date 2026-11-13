// Screenshot of a Fresing Render web 3D page (task 0099) in headless Chromium, as a customer's browser shows it.
//
//   node tools/web3d_shot.js <page.html> <out.png> [width] [height] [camera-orbit] [--hide-ui] [--target=<x y z>]
//        [--fov=<deg>deg]   (camera-orbit, target and fov in model-viewer's words, e.g. "45deg 60deg 2m")
//
// Waits until <model-viewer> has loaded the model and drawn it, then saves the picture. Prints one line of JSON:
// {"ok": true, "ms": <load time>, "webgl": "<renderer>"}. Needs Playwright with Chromium (the web sessions have it;
// elsewhere: npm i playwright). Used for the looks check of task 0099 and for the landing page's poster picture.
const path = require('path');
let playwright;
try { playwright = require('playwright'); } catch (e) { playwright = require('/opt/node-tools/node_modules/playwright'); }

(async () => {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const hideUi = process.argv.includes('--hide-ui');
  const opt = name => (process.argv.find(a => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=');
  const target = opt('target'), fov = opt('fov');
  const [page_, out, w = '1200', h = '800', orbit = ''] = args;
  const browser = await playwright.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  const t0 = Date.now();
  await page.goto('file://' + path.resolve(page_));
  const info = await page.evaluate(async ({ orbit, hideUi, target, fov }) => {
    const mv = document.querySelector('model-viewer');
    if (hideUi) document.querySelectorAll('header, .note').forEach(e => e.style.display = 'none');
    if (orbit) { mv.setAttribute('min-camera-orbit', 'auto auto 0m'); mv.setAttribute('camera-orbit', orbit); }
    if (target) mv.setAttribute('camera-target', target);
    if (fov) { mv.setAttribute('min-field-of-view', '1deg'); mv.setAttribute('field-of-view', fov); }
    if (!mv.loaded) await new Promise((res, rej) => { mv.addEventListener('load', res); mv.addEventListener('error', e => rej(String(e.detail && e.detail.type))); setTimeout(() => rej('no load in 120 s'), 120000); });
    if (mv.jumpCameraToGoal) mv.jumpCameraToGoal();
    const c = document.createElement('canvas').getContext('webgl2');
    const dbg = c && c.getExtension('WEBGL_debug_renderer_info');
    return { webgl: dbg ? c.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : (c ? 'webgl2' : 'none') };
  }, { orbit, hideUi, target, fov });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out });
  await browser.close();
  console.log(JSON.stringify({ ok: errors.length === 0, ms: Date.now() - t0, errors, ...info }));
  process.exit(errors.length ? 1 : 0);
})().catch(e => { console.log(JSON.stringify({ ok: false, error: String(e) })); process.exit(1); });
