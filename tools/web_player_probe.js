// Drives a Fresing Render web 3D page (task 0134, the player) in headless Chromium and prints what it saw.
//
//   node tools/web_player_probe.js <page.html> '<steps as JSON>' [--query=…] [--size=900x600] [--mobile]
//
// Steps, one after the other (each adds one entry to "out"):
//   {"wait": ms}                     wait
//   {"key": " "}                     press a key (Playwright's names: " ", "F", "Escape", "ArrowLeft", "1", "?" …)
//   {"click": "<css selector>"}      click the first element it matches
//   {"eval": "<js expression>"}      its value (JSON) – e.g. "frPage.paused"
//   {"frames": ms}                   pictures drawn during ms (frPage.frames before and after)
//   {"freeze": ms}                   no animation frames for ms (Chrome freezes a page in the back/forward cache or a
//                                    covered window this way), no event; then they come again
//   {"hidden": ms}                   the tab hidden for ms as Chrome hides a background tab: document.hidden true, a
//                                    visibilitychange event, no animation frames; then shown again
// (A headless browser never hides or freezes its page itself – CDP's frozen state still runs animation frames – so
// both are acted out by a small script put into the page before it loads.)
//   {"drag": [x0, y0, x1, y1]}       a mouse drag on the view (pixels)
//   {"shot": "<file.png>"}           a screenshot of the page
//   {"reload": true}                 load the page again (same address: the remembered choices stay)
// Prints {"ok", "errors", "out": [...], "state": {...frPage}}; ok is false when the page reported an error.
// Software GL (SwiftShader): the page sees no graphics card; add soft=0 to the query to test the rest as if it had.
const path = require('path');
let playwright;
try { playwright = require('playwright'); } catch (e) { playwright = require('/opt/node-tools/node_modules/playwright'); }

(async () => {
  const args = process.argv.slice(2).filter(a => !a.startsWith('--'));
  const opt = name => (process.argv.find(a => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=');
  const [file, stepsText = '[]'] = args;
  const steps = JSON.parse(stepsText);
  const [w, h] = (opt('size') || '900x600').split('x').map(Number);
  const browser = await playwright.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                                            '--ignore-gpu-blocklist'] });
  const context = await browser.newContext(process.argv.includes('--mobile')
    ? { viewport: { width: w, height: h }, deviceScaleFactor: 3, isMobile: true, hasTouch: true }
    : { viewport: { width: w, height: h }, acceptDownloads: true });
  await context.addInitScript(() => {
    const raf = window.requestAnimationFrame.bind(window);
    let hold = false, hidden = false, queue = [];
    window.requestAnimationFrame = cb => raf(t => { if (hold) queue.push(cb); else cb(t); });
    Object.defineProperty(document, 'hidden', { get: () => hidden, configurable: true });
    Object.defineProperty(document, 'visibilityState', { get: () => hidden ? 'hidden' : 'visible', configurable: true });
    window.__frAct = (what, on) => {
      hold = on;
      if (what === 'hidden') { hidden = on; document.dispatchEvent(new Event('visibilitychange')); }
      if (!on) { const q = queue; queue = []; raf(t => q.forEach(cb => cb(t))); }
    };
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  const url = 'file://' + path.resolve(file) + (opt('query') ? '?' + opt('query') : '');
  const t0 = Date.now();
  const ready = async () => page.waitForFunction(() => window.frPage && (window.frPage.ready && window.frPage.frames > 0 ||
                                                  window.frPage.errors.length), null, { timeout: 180000 });
  await page.goto(url);
  await ready();
  const loadMs = Date.now() - t0;
  const out = [];
  for (const s of steps) {
    if (s.wait != null) { await page.waitForTimeout(s.wait); out.push(null); }
    else if (s.key != null) { await page.keyboard.press(s.key); await page.waitForTimeout(60); out.push(null); }
    else if (s.click != null) { await page.click(s.click); await page.waitForTimeout(60); out.push(null); }
    else if (s.eval != null) out.push(await page.evaluate(s.eval));
    else if (s.frames != null) {
      const f0 = await page.evaluate(() => frPage.frames);
      await page.waitForTimeout(s.frames);
      out.push((await page.evaluate(() => frPage.frames)) - f0);
    } else if (s.freeze != null || s.hidden != null) {
      const what = s.freeze != null ? 'freeze' : 'hidden';
      await page.evaluate(w => window.__frAct(w, true), what);
      const f0 = await page.evaluate(() => frPage.frames);
      await page.waitForTimeout(s.freeze != null ? s.freeze : s.hidden);
      const f1 = await page.evaluate(() => frPage.frames);
      await page.evaluate(w => window.__frAct(w, false), what);
      out.push(f1 - f0);                              // pictures drawn meanwhile: 0
    } else if (s.drag != null) {
      const [x0, y0, x1, y1] = s.drag;
      await page.mouse.move(x0, y0); await page.mouse.down();
      for (let k = 1; k <= 10; k++) await page.mouse.move(x0 + (x1 - x0) * k / 10, y0 + (y1 - y0) * k / 10);
      await page.mouse.up();
      out.push(null);
    } else if (s.shot != null) { await page.screenshot({ path: s.shot }); out.push(s.shot); }
    else if (s.reload) { await page.reload(); await ready(); out.push(null); }
    else out.push('unknown step');
  }
  const state = await page.evaluate(() => ({
    level: frPage.level, auto: frPage.auto, quality: frPage.quality, fps: frPage.fps, frames: frPage.frames,
    lowered: frPage.lowered, raised: frPage.raised, warned: frPage.warned, gpu: frPage.gpu, cap: frPage.cap,
    paused: frPage.paused, time: frPage.time, speed: frPage.speed, duration: frPage.duration, animated: frPage.animated,
    items: frPage.items, on: frPage.on, views: (frPage.views || []).length, turn: frPage.turn, turning: frPage.turning,
    sunLive: frPage.sunLive, sunHour: frPage.sunHour, menuOpen: !!frPage.menuOpen, helpOpen: !!frPage.helpOpen,
    clean: !!frPage.clean, errors: frPage.errors, info: frPage.info, load: window.frLoad || null }));
  await browser.close();
  const all = errors.concat(state.errors);
  console.log(JSON.stringify({ ok: all.length === 0, errors: all, load_ms: loadMs, out, state }));
  process.exit(0);
})().catch(e => { console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e) })); process.exit(1); });
