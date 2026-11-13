// Screenshot and measurement of a Fresing Render web 3D page WITH surroundings (task 0106) in headless Chromium.
//
//   node tools/web3d_env_shot.js <page.html> <out.png|-> [width] [height] [--query=quality=BEST&auto=0&t=12]
//        [--wait=<ms after it is ready, default 1500>] [--measure=<ms>] [--hide-ui]
//
// Prints one line of JSON: {"ok", "load_ms" (until the first picture is drawn), "fps" (frames per second over
// --measure ms), "level", "lowered", "errors", "webgl", "info"}. Software GL (SwiftShader) is not a graphics card:
// its frames per second only compare quality levels with each other. Needs Playwright with Chromium (web sessions
// have it). The page without surroundings (model-viewer) uses tools/web3d_shot.js.
const path = require('path');
let playwright;
try { playwright = require('playwright'); } catch (e) { playwright = require('/opt/node-tools/node_modules/playwright'); }

(async () => {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const opt = name => (process.argv.find(a => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=');
  const [page_, out, w = '1200', h = '800'] = args;
  const query = opt('query'), wait = +(opt('wait') || 1500), measure = +(opt('measure') || 0);
  const browser = await playwright.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                                            '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: +w, height: +h } });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  const t0 = Date.now();
  await page.goto('file://' + path.resolve(page_) + (query ? '?' + query : ''));
  await page.waitForFunction(() => window.frPage && (window.frPage.ready && window.frPage.frames > 0 ||
                                    window.frPage.errors.length), null, { timeout: 180000 });
  const loadMs = Date.now() - t0;
  if (process.argv.includes('--hide-ui')) {
    await page.evaluate(() => document.querySelectorAll('header, .note, #quality').forEach(e => e.style.display = 'none'));
  }
  await page.waitForTimeout(wait);
  let fps = null;
  if (measure) {
    const f0 = await page.evaluate(() => window.frPage.frames);
    await page.waitForTimeout(measure);
    const f1 = await page.evaluate(() => window.frPage.frames);
    fps = (f1 - f0) / (measure / 1000);
  }
  if (out && out !== '-') await page.screenshot({ path: out, timeout: 300000 });
  const st = await page.evaluate(() => ({ level: frPage.level, lowered: frPage.lowered, errors: frPage.errors,
                                          webgl: frPage.info.webgl, info: frPage.info }));
  await browser.close();
  const all = errors.concat(st.errors);
  console.log(JSON.stringify({ ok: all.length === 0, load_ms: loadMs, fps, level: st.level, lowered: st.lowered,
                               errors: all, webgl: st.webgl, info: st.info }));
  process.exit(all.length ? 1 : 0);
})().catch(e => { console.log(JSON.stringify({ ok: false, error: String(e) })); process.exit(1); });
