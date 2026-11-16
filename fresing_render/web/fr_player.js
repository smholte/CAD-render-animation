// Fresing Render web 3D player (task 0134): the controls round the 3D view that fr_page.js draws. Reads and sets
// window.frPage (its state and functions) and draws nothing in 3D itself. Nothing is fetched from the internet.
//
//   the "no graphics card" bar      page.warned = 'software' (the browser names a software renderer) or 'probably'
//   the settings menu (gear, M)      surroundings items on/off, Quality Auto/Phone/Balanced/Best, live pictures a
//                                    second, the graphics card's name, Auto-turn, Sun / time of day (live light only),
//                                    choices remembered on this PC (localStorage) with a Reset line
//   playback (pages with motion)     Space play/pause, a time slider, speed ½× 1× 2×, ← → two seconds
//   saved views                      one button each (keys 1 … 9): the camera flies there
//   view tools                       Fullscreen (F), Reset view (R), Screenshot (S), Copy link to this view (L),
//                                    Keyboard help (?), Clean look (H: hides every control; a faint button brings them back)
//
// ?selftest=1 (PC check, headless): after the page is ready it opens the menu, presses Space twice and the help key,
// and writes what happened into data-fr-selftest on <html>.
(function () {
  'use strict';
  var page = window.frPage;
  if (!page || !page.listeners) return;       // no WebGL: fr_page.js stopped early, its own message shows
  var Q = new URLSearchParams(location.search);
  var root = document.documentElement;
  var LEVELS = ['AUTO', 'PHONE', 'BALANCED', 'BEST'];
  var NAMES = { sea: 'Sea', vessel: 'Vessel motion', sky: 'Sky', haze: 'Haze', rain: 'Rain', shadows: 'Sun shadows',
                under: 'Under the sea', dive: 'Camera under water' };     // task 0143: the seabed, the cut-away
  if (page.settings.rain && page.settings.rain.spray) NAMES.rain = 'Rain and spray';

  // ---------------------------------------------------------------- look
  var css = [
    '.fr-btn { font: 600 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; color: #F4F6F8; cursor: pointer;',
    '  background: rgba(20,28,34,.62); border: 1px solid rgba(255,255,255,.18); border-radius: 6px; min-height: 36px;',
    '  min-width: 36px; padding: 0 10px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }',
    '.fr-btn:hover { background: rgba(20,28,34,.8); }',
    '.fr-btn:focus-visible, .fr-menu input:focus-visible { outline: 3px solid #F2A900; outline-offset: 1px; }',
    '.fr-btn[aria-pressed="true"] { background: #2F6A1B; border-color: #2F6A1B; }',
    '.fr-btn svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round;',
    '  stroke-linejoin: round; }',
    '#fr-tools { position: absolute; right: 12px; top: calc(var(--fr-top, 0px) + 50px); z-index: 3; display: flex;',
    '  flex-direction: column; flex-wrap: wrap-reverse; align-content: flex-start; gap: 6px;',
    '  max-height: calc(100% - var(--fr-top, 0px) - 120px); }',
    '#fr-tools .fr-btn { padding: 0; width: 40px; height: 40px; }',
    '#fr-bottom { position: absolute; left: 12px; right: 62px; bottom: 10px; z-index: 2; display: flex; flex-direction: column;',
    '  align-items: flex-start; gap: 6px; pointer-events: none; }',
    '#fr-bottom > * { pointer-events: auto; }',
    '#fr-bottom .note { position: static; pointer-events: auto; }',
    '#fr-views { display: flex; flex-wrap: wrap; gap: 6px; max-width: 100%; }',
    '#fr-playbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; background: rgba(20,28,34,.62); border-radius: 8px;',
    '  padding: 4px 8px; color: #F4F6F8; font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;',
    '  width: min(560px, 100%); box-sizing: border-box; }',
    '#fr-playbar input[type=range] { flex: 1; min-width: 80px; accent-color: #F2A900; height: 28px; }',
    '#fr-playbar .fr-btn { background: transparent; border: 0; min-height: 32px; }',
    '#fr-playbar .fr-time { font-variant-numeric: tabular-nums; white-space: nowrap; }',
    '#fr-playbar .fr-speed .fr-btn { padding: 0 6px; min-width: 30px; }',
    '#fr-playbar .fr-speed .fr-btn[aria-pressed="true"] { background: rgba(255,255,255,.22); }',
    '.fr-menu { position: absolute; right: 62px; top: calc(var(--fr-top, 0px) + 50px); z-index: 4; width: min(320px, calc(100vw - 86px));',
    '  max-height: calc(100% - var(--fr-top, 0px) - 160px); overflow: auto; background: rgba(20,28,34,.9); color: #F4F6F8;',
    '  border-radius: 8px; padding: 12px 14px; font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;',
    '  box-shadow: 0 6px 24px rgba(0,0,0,.35); display: none; }',
    '.fr-menu h2 { font-size: 14px; margin: 0 0 8px; }',
    '.fr-menu h3 { font-size: 12px; margin: 12px 0 4px; color: #D5DBE0; font-weight: 600; text-transform: uppercase;',
    '  letter-spacing: .04em; }',
    '.fr-menu label { display: flex; align-items: center; gap: 8px; min-height: 30px; cursor: pointer; }',
    '.fr-menu input[type=checkbox] { width: 18px; height: 18px; accent-color: #2F6A1B; }',
    '.fr-menu input[type=range] { width: 100%; accent-color: #F2A900; }',
    '.fr-menu .fr-seg { display: flex; gap: 4px; flex-wrap: wrap; }',
    '.fr-menu .fr-seg .fr-btn { flex: 1; min-height: 32px; padding: 0 6px; font-size: 12px; }',
    '.fr-menu .fr-small { color: #D5DBE0; font-size: 12px; margin: 4px 0; overflow-wrap: anywhere; }',
    '.fr-menu .fr-grey { opacity: .45; }',
    '.fr-menu a { color: #F2A900; cursor: pointer; }',
    '#fr-warn { position: absolute; left: 0; right: 0; top: 0; z-index: 5; background: #8A1C1C; color: #fff;',
    '  font: 14px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; padding: 10px 14px; display: none;',
    '  align-items: flex-start; gap: 12px; }',
    '#fr-warn p { margin: 0; flex: 1; }',
    '#fr-warn code { background: rgba(0,0,0,.25); padding: 0 4px; border-radius: 3px; }',
    '#fr-help { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); z-index: 6; display: none;',
    '  background: rgba(20,28,34,.94); color: #F4F6F8; border-radius: 8px; padding: 14px 18px; min-width: 260px;',
    '  font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; box-shadow: 0 6px 24px rgba(0,0,0,.4); }',
    '#fr-help h2 { font-size: 14px; margin: 0 0 8px; }',
    '#fr-help table { border-collapse: collapse; }',
    '#fr-help td { padding: 3px 10px 3px 0; vertical-align: top; }',
    '#fr-help kbd { display: inline-block; min-width: 18px; text-align: center; border: 1px solid rgba(255,255,255,.4);',
    '  border-radius: 4px; padding: 0 5px; font: 12px ui-monospace, Consolas, monospace; }',
    '#fr-toast { position: absolute; left: 50%; bottom: 90px; transform: translateX(-50%); z-index: 6; display: none;',
    '  background: rgba(20,28,34,.9); color: #fff; padding: 8px 14px; border-radius: 6px;',
    '  font: 13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; max-width: 90vw; overflow-wrap: anywhere; }',
    '#fr-show { position: absolute; right: 8px; bottom: 8px; z-index: 6; display: none; opacity: .28; }',
    '#fr-show:hover, #fr-show:focus-visible { opacity: .9; }',
    'html.fr-clean header, html.fr-clean .note, html.fr-clean #quality, html.fr-clean #fr-tools,',
    'html.fr-clean #fr-bottom, html.fr-clean .fr-menu, html.fr-clean #fr-help, html.fr-clean #fr-warn,',
    'html.fr-clean #fr-site { display: none !important; }',
    'html.fr-clean header { display: none !important; }',
    'html.fr-clean #fr-show { display: inline-flex; }',
    'header { top: var(--fr-top, 0px) !important; }',
    '#quality { bottom: 10px; }',
    '@media (max-width: 600px) { #fr-tools { top: calc(var(--fr-top, 0px) + 70px); right: 8px; }',
    '  .fr-menu { right: 56px; top: calc(var(--fr-top, 0px) + 70px); }',
    '  #fr-playbar { font-size: 12px; } .fr-hide-small { display: none; } }',
    // 0147 row 21e: a phone held sideways (844 x 390) – the buttons smaller so they stay one column, the menu
    // higher and longer; on a phone the help is a sheet from the bottom (it covered the tool column and the title)
    '@media (max-height: 480px) { header { padding: 8px 14px; } h1 { font-size: 15px; }',
    '  #fr-tools { top: calc(var(--fr-top, 0px) + 44px); gap: 4px; max-height: calc(100% - var(--fr-top, 0px) - 52px); }',
    '  #fr-tools .fr-btn { width: 34px; height: 34px; min-height: 34px; min-width: 34px; }',
    '  .fr-menu { right: 54px; top: calc(var(--fr-top, 0px) + 8px); max-height: calc(100% - var(--fr-top, 0px) - 16px); } }',
    '@media (max-width: 600px), (max-height: 480px) { #fr-help { left: 0; right: 0; top: auto; bottom: 0; transform: none;',
    '  border-radius: 12px 12px 0 0; max-height: 45%; overflow: auto; min-width: 0; z-index: 7; } }',
    '@media (max-height: 480px) { #fr-help { right: 54px; max-height: 70%; } }'
  ].join('\n');
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var ICON = {
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    full: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    reset: '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    shot: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
    help: '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    eye: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    play: '<path d="M7 4l13 8-13 8z" fill="currentColor"/>',
    pause: '<path d="M7 4v16M17 4v16" stroke-width="4"/>'
  };
  function svg(name) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[name] + '</svg>'; }
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) {
      if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]);
    }
    if (html != null) e.innerHTML = html;
    return e;
  }
  function button(icon, label, key, fn, parent) {
    var b = el('button', { type: 'button', 'class': 'fr-btn', title: label + (key ? ' (' + key + ')' : ''),
                           'aria-label': label }, icon ? svg(icon) : '');
    if (!icon) b.textContent = label;
    b.addEventListener('click', function () { fn(); b.blur(); page.input && page.input(); });
    if (parent) parent.appendChild(b);
    return b;
  }

  // ---------------------------------------------------------------- remembered choices
  function save() {
    // 0147 row 21d: only what the visitor switched (the page's own "no shadows without a graphics card" is not kept)
    var p = { quality: page.quality, off: page.visitorOff(), chose: page.chosenItems(), turn: !!page.turn,
              speed: page.speed };
    if (page.toolPrefs) p.tools = page.toolPrefs();                   // task 0135: the part tools' choices
    try { window.localStorage.setItem(page.prefKey, JSON.stringify(p)); page.saved = true; } catch (e) { page.saved = false; }
  }
  page.savePrefs = save;                     // task 0135: the part tools' choices are kept with the rest
  function forget() {
    try { window.localStorage.removeItem(page.prefKey); } catch (e) { /* private window: nothing was kept */ }
    page.setQuality(page.settings.auto ? 'AUTO' : page.settings.quality);
    page.resetChosen();
    page.items.forEach(function (n) { page.setItem(n, n === 'shadows' && page.warned ? false : true, true); });
    if (page.resetTools) page.resetTools();                            // task 0135
    page.setTurn(false);
    page.setSpeed(1);
    if (page.sunLive) page.setSunHour(13, true);
    toast('Back to the page’s own settings');
  }

  // ---------------------------------------------------------------- the "no graphics card" bar
  var warn = el('div', { id: 'fr-warn', role: 'alert' });
  var warnText = el('p');
  warn.appendChild(warnText);
  button('', 'Hide', '', function () {
    warn.style.display = 'none'; root.classList.remove('fr-warned'); root.style.removeProperty('--fr-top');
    page.warnHidden = true;
  }, warn);
  window.addEventListener('resize', function () { if (root.classList.contains('fr-warned')) place(); });
  function place() { root.style.setProperty('--fr-top', warn.offsetHeight + 'px'); }
  document.body.appendChild(warn);
  function showWarn() {
    if (!page.warned || page.warnHidden) return;
    var maybe = page.warned === 'probably' ? 'probably ' : '';
    warnText.innerHTML = 'This browser is ' + maybe + 'drawing the 3D model without the graphics card, so it is slow. ' +
      'Fix: type <code>chrome://restart</code> (Edge: <code>edge://restart</code>) in the address bar. Still slow: ' +
      'Settings → System → “Use graphics acceleration when available” on, then restart.';
    warn.style.display = 'flex';
    root.classList.add('fr-warned');
    place();
  }

  // ---------------------------------------------------------------- tools (top right)
  var tools = el('div', { id: 'fr-tools' });
  var menuBtn = button('gear', 'Settings', 'M', function () { toggleMenu(); }, tools);
  menuBtn.setAttribute('aria-expanded', 'false');
  var canFull = !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
  if (canFull) button('full', 'Fullscreen', 'F', fullscreen, tools);
  button('reset', 'Reset view', 'R', function () { page.resetView(); }, tools);
  button('shot', 'Screenshot', 'S', screenshot, tools);
  button('link', 'Copy link to this view', 'L', copyLink, tools);
  button('help', 'Keyboard help', '?', function () { toggleHelp(); }, tools);
  button('eye', 'Clean look: hide the controls', 'H', function () { clean(true); }, tools);
  document.body.appendChild(tools);
  var show = button('eye', 'Show the controls', 'H', function () { clean(false); });
  show.id = 'fr-show';
  document.body.appendChild(show);

  function fullscreen() {
    var d = document;
    if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
    else {
      var r = root.requestFullscreen || root.webkitRequestFullscreen;
      if (r) { try { var p = r.call(root); if (p && p.catch) p.catch(function () {}); } catch (e) { /* refused */ } }
    }
  }
  function screenshot() {
    var url = page.screenshot();
    var a = el('a', { href: url, download: fileName(document.title) + '.png' });
    document.body.appendChild(a);
    a.click();
    a.remove();
    page.lastScreenshot = url.length;
    toast('Screenshot saved to your downloads');
  }
  // 0147 row 21f: a title with letters outside ASCII ("… – Fresing Render", "Plåt") saved as "download" without .png
  // in Chrome: the name folded to plain letters
  function fileName(title) {
    var t = String(title || 'view');
    try { t = t.normalize('NFKD'); } catch (e) { /* old browser: as it is */ }
    t = t.replace(/[\u2010-\u2015]/g, '-').replace(/[\u0300-\u036f]/g, '').replace(/[^\x20-\x7e]+/g, '')
      .replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim();
    return t || 'view';
  }
  page.fileName = fileName;
  function copyLink() {
    var url = page.viewLink();
    page.lastLink = url;
    var done = function () { toast('Link to this view copied'); };
    var fallback = function () {
      var t = el('textarea');
      t.value = url;
      t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.appendChild(t);
      t.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      t.remove();
      if (ok) done(); else toast('Copy this link: ' + url, 12);
    };
    try {
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(done, fallback);
      else fallback();
    } catch (e) { fallback(); }
  }
  var toastEl = el('div', { id: 'fr-toast', role: 'status' }), toastTimer = null;
  document.body.appendChild(toastEl);
  function toast(text, seconds) {
    clearTimeout(toastTimer);
    toastEl.textContent = text;
    toastEl.style.display = 'block';
    toastTimer = setTimeout(function () { toastEl.style.display = 'none'; }, (seconds || 2.5) * 1000);
  }
  function clean(on) {
    page.clean = !!on;
    root.classList.toggle('fr-clean', page.clean);
    if (page.clean) { toggleMenu(false); toggleHelp(false); }
    page.wake();
  }

  // ---------------------------------------------------------------- the settings menu
  var menu = el('div', { 'class': 'fr-menu', id: 'fr-menu', role: 'dialog', 'aria-label': 'Settings' });
  document.body.appendChild(menu);
  function toggleMenu(on) {
    page.menuOpen = on == null ? !page.menuOpen : !!on;
    if (page.menuOpen) { toggleHelp(false); fillMenu(); }
    menu.style.display = page.menuOpen ? 'block' : 'none';
    menuBtn.setAttribute('aria-expanded', page.menuOpen ? 'true' : 'false');
    menuBtn.setAttribute('aria-pressed', page.menuOpen ? 'true' : 'false');
  }
  var fpsEl = null, levelEl = null, segBtns = {}, sunText = null;
  function fillMenu() {
    menu.innerHTML = '';
    menu.appendChild(el('h2', { text: 'Settings' }));
    if (page.items.length) {
      menu.appendChild(el('h3', { text: 'On the page' }));
      page.items.forEach(function (n) {
        var lab = el('label'), box = el('input', { type: 'checkbox', 'data-item': n });
        box.checked = page.on[n] !== false;
        box.addEventListener('change', function () { page.setItem(n, box.checked); save(); page.input(); });
        lab.appendChild(box);
        lab.appendChild(document.createTextNode(NAMES[n] || n));
        menu.appendChild(lab);
      });
    }
    menu.appendChild(el('h3', { text: 'Quality' }));
    var seg = el('div', { 'class': 'fr-seg', role: 'group', 'aria-label': 'Quality' });
    segBtns = {};
    LEVELS.forEach(function (q) {
      segBtns[q] = button('', q.charAt(0) + q.slice(1).toLowerCase(), '', function () { page.setQuality(q); save(); }, seg);
      segBtns[q].dataset.quality = q;
    });
    menu.appendChild(seg);
    levelEl = el('p', { 'class': 'fr-small' });
    fpsEl = el('p', { 'class': 'fr-small' });
    menu.appendChild(levelEl);
    menu.appendChild(fpsEl);
    menu.appendChild(el('h3', { text: 'Graphics card' }));
    menu.appendChild(el('p', { 'class': 'fr-small', text: page.gpu || 'The browser does not name it' }));
    if (page.warned) {
      menu.appendChild(el('p', { 'class': 'fr-small', text: page.warned === 'probably'
        ? 'Probably drawing without the graphics card (slow).' : 'Drawing without the graphics card (slow).' }));
    }
    menu.appendChild(el('h3', { text: 'Motion' }));
    var lt = el('label'), tb = el('input', { type: 'checkbox', id: 'fr-turn' });
    tb.checked = !!page.turn;
    tb.addEventListener('change', function () { page.setTurn(tb.checked); save(); });
    lt.appendChild(tb);
    lt.appendChild(document.createTextNode('Auto-turn (after 8 s without a touch)'));
    menu.appendChild(lt);
    menu.appendChild(el('h3', { text: 'Sun / time of day' }));
    var sunBox = el('div', page.sunLive ? {} : { 'class': 'fr-grey' });
    var sl = el('input', { type: 'range', min: '5', max: '21', step: '0.25', id: 'fr-sun',
                           'aria-label': 'Sun: time of day' });
    sl.value = String(page.sunHour);
    sl.disabled = !page.sunLive;
    sunText = el('p', { 'class': 'fr-small' });
    sl.addEventListener('input', function () { page.setSunHour(+sl.value, false); });
    sl.addEventListener('change', function () { page.setSunHour(+sl.value, true); });
    sunBox.appendChild(sl);
    sunBox.appendChild(sunText);
    menu.appendChild(sunBox);
    menu.appendChild(el('h3', { text: 'Remembered on this PC' }));
    var p = el('p', { 'class': 'fr-small' });
    p.appendChild(document.createTextNode('Your choices here are kept for your next visit. '));
    var a = el('a', { role: 'button', tabindex: '0', id: 'fr-forget', text: 'Reset' });
    a.addEventListener('click', forget);
    a.addEventListener('keydown', function (e) { if (e.key === 'Enter') forget(); });
    p.appendChild(a);
    menu.appendChild(p);
    refreshMenu();
  }
  function hhmm(h) {
    var m = Math.round(h * 60);
    return Math.floor(m / 60) + ':' + ('0' + m % 60).slice(-2);
  }
  function refreshMenu() {
    if (!page.menuOpen) return;
    for (var q in segBtns) segBtns[q].setAttribute('aria-pressed', page.quality === q ? 'true' : 'false');
    levelEl.textContent = 'Now: ' + (page.level || '').charAt(0) + (page.level || '').slice(1).toLowerCase() +
      (page.auto ? ' (Auto: lower when it cannot keep up, higher again when there is room)' : '');
    fpsEl.textContent = page.fps > 0 ? Math.round(page.fps) + ' pictures a second (at most ' + page.cap + ')'
      : page.moving() ? 'Counting the pictures a second \u2026'
      : 'No pictures drawn while nothing moves (at most ' + page.cap + ' a second)';
    if (sunText) sunText.textContent = page.sunLive ? hhmm(page.sunHour) + (Math.abs(page.sunHour - 13) < 0.01
      ? ' (as exported)' : '') : page.sunWhy;
    var boxes = menu.querySelectorAll('input[data-item]');
    for (var i = 0; i < boxes.length; i++) boxes[i].checked = page.on[boxes[i].dataset.item] !== false;
  }

  // ---------------------------------------------------------------- keyboard help
  var TOUCH = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  page.touch = TOUCH;
  var KEYS = TOUCH ? [['One finger', 'turn'], ['Two fingers', 'move'], ['Pinch', 'zoom'],
                      ['Tap', 'with a part tool on: pick a part or a face'], ['Long press', 'what a part is']]
    : [['Drag', 'turn'], ['Right-drag / two fingers', 'move'], ['Scroll / pinch', 'zoom']];
  var help = el('div', { id: 'fr-help', role: 'dialog', 'aria-label': 'Keyboard help' });
  document.body.appendChild(help);
  function fillHelp() {
    var rows = KEYS.slice();
    if (page.animated) rows.push(['Space', 'play / pause'], ['← →', 'two seconds back / on']);
    if (page.views.length) rows.push([page.views.length > 1 ? '1 … ' + Math.min(9, page.views.length) : '1',
                                      page.views.length > 1 ? 'saved views' : 'the saved view']);
    rows.push(['M', 'settings']);
    if (canFull) rows.push(['F', 'fullscreen']);
    rows.push(['R', 'reset view'], ['S', 'screenshot (PNG)'], ['L', 'copy link to this view'],
              ['H', 'hide / show the controls']);
    (page.toolKeys || []).forEach(function (r) { rows.push(r); });      // task 0135: the part tools
    rows.push(['?', 'this help'], ['Esc', 'close']);
    help.innerHTML = '<h2>Keys</h2><table>' + rows.map(function (r) {
      return '<tr><td>' + r[0].split(' / ').map(function (k) { return /^(Space|Esc|[A-Z?]|← →|\d( … \d)?)$/.test(k) ? '<kbd>' + k + '</kbd>' : k; })
        .join(' / ') + '</td><td>' + r[1] + '</td></tr>';
    }).join('') + '</table>';
    page.helpKeys = rows.length;
  }
  function toggleHelp(on) {
    page.helpOpen = on == null ? !page.helpOpen : !!on;
    if (page.helpOpen) { fillHelp(); toggleMenu(false); }
    help.style.display = page.helpOpen ? 'block' : 'none';
  }
  help.addEventListener('click', function () { toggleHelp(false); });

  // ---------------------------------------------------------------- bottom: saved views, playback, the note line
  var bottom = el('div', { id: 'fr-bottom' });
  var viewsRow = el('div', { id: 'fr-views', role: 'group', 'aria-label': 'Saved views' });
  var play = el('div', { id: 'fr-playbar' });
  bottom.appendChild(viewsRow);
  bottom.appendChild(play);
  document.body.appendChild(bottom);
  var noteLine = document.querySelector('body > .note');
  if (noteLine) bottom.appendChild(noteLine);
  play.style.display = 'none';
  var playBtn, slider, timeEl, speedBtns = {}, dragging = false, wasPaused = false;
  function fmt(s) {
    s = Math.max(0, s);
    return Math.floor(s / 60) + ':' + ('0' + (s % 60).toFixed(1)).slice(-4);
  }
  function buildBottom() {
    viewsRow.innerHTML = '';
    page.views.forEach(function (v, k) {
      var b = button('', v.name, k < 9 ? String(k + 1) : '', function () { page.goView(k); }, viewsRow);
      b.dataset.view = String(k);
    });
    if (!page.animated) return;
    play.style.display = 'flex';
    playBtn = button('pause', 'Play / pause', 'Space', function () { page.paused = !page.paused; }, play);
    slider = el('input', { type: 'range', min: '0', max: String(page.duration), step: '0.01', id: 'fr-slider',
                           'aria-label': 'Moment in the animation' });
    play.appendChild(slider);
    slider.addEventListener('pointerdown', function () { dragging = true; wasPaused = page.paused; page.paused = true; });
    slider.addEventListener('input', function () { page.setTime(+slider.value); });
    slider.addEventListener('change', function () {
      page.setTime(+slider.value);
      if (dragging) { dragging = false; page.paused = wasPaused; }
    });
    timeEl = el('span', { 'class': 'fr-time' });
    play.appendChild(timeEl);
    var sp = el('span', { 'class': 'fr-speed', role: 'group', 'aria-label': 'Speed' });
    [[0.5, '½×'], [1, '1×'], [2, '2×']].forEach(function (s) {
      speedBtns[s[0]] = button('', s[1], '', function () { page.setSpeed(s[0]); save(); }, sp);
      speedBtns[s[0]].setAttribute('aria-label', 'Speed ' + s[0]);
    });
    play.appendChild(sp);
    refreshPlay();
  }
  function refreshPlay() {
    if (!slider) return;
    var t = page.duration > 0 ? page.time % page.duration : 0;
    if (!dragging) slider.value = String(t);
    timeEl.textContent = fmt(t) + ' / ' + fmt(page.duration);
    playBtn.innerHTML = svg(page.paused ? 'play' : 'pause');
    playBtn.setAttribute('aria-label', page.paused ? 'Play' : 'Pause');
    playBtn.setAttribute('aria-pressed', page.paused ? 'false' : 'true');
    for (var s in speedBtns) speedBtns[s].setAttribute('aria-pressed', +s === page.speed ? 'true' : 'false');
  }

  // ---------------------------------------------------------------- keys
  window.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'TEXTAREA' || (tag === 'INPUT' && e.target.type !== 'range' && e.target.type !== 'checkbox')) return;
    var k = e.key, done = true;
    if (k === ' ' || k === 'Spacebar') { if (page.animated) page.paused = !page.paused; else done = false; }
    else if (k === 'f' || k === 'F') fullscreen();
    else if (k === 'r' || k === 'R') page.resetView();
    else if (k === 's' || k === 'S') screenshot();
    else if (k === 'l' || k === 'L') copyLink();
    else if (k === 'h' || k === 'H') clean(!page.clean);
    else if (k === 'm' || k === 'M') toggleMenu();
    else if (k === '?') toggleHelp();
    else if (k === 'Escape') { toggleMenu(false); toggleHelp(false); }
    else if ((k === 'ArrowLeft' || k === 'ArrowRight') && page.animated && tag !== 'INPUT') {
      page.setTime(Math.max(0, page.time + (k === 'ArrowLeft' ? -2 : 2)));
    } else if (/^[1-9]$/.test(k) && +k <= page.views.length) page.goView(+k - 1);
    else done = false;
    if (done) { e.preventDefault(); page.input(); page.lastKey = k; }
  });

  // ---------------------------------------------------------------- follow the page
  page.listeners.push(function (what) {
    if (what === 'time' || what === 'paused' || what === 'speed') refreshPlay();
    else if (what === 'ready') { buildBottom(); showWarn(); }
    else if (what === 'warned') showWarn();
    if (what !== 'time' || page.frames % 20 === 0) refreshMenu();
  });
  var hint = document.querySelector('header .hint');
  // 0147 row 21e: a phone has no right button and no keys
  if (hint) hint.textContent = TOUCH ? 'Drag to turn · pinch to zoom · two fingers to move · tools on the left'
    : hint.textContent + ' · ? for keys';
  if (page.ready) { buildBottom(); showWarn(); }

  // ---------------------------------------------------------------- self-test (PC check, headless)
  if (Q.get('selftest') === '1') {
    var test = function () {
      var r = { warned: page.warned, gpu: page.gpu, animated: page.animated };
      toggleMenu(true);
      r.menu = menu.style.display === 'block' && !!menu.querySelector('[data-quality="AUTO"]');
      r.items = menu.querySelectorAll('input[data-item]').length;
      toggleMenu(false);
      var key = function (k) { window.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true })); };
      var p0 = page.paused;
      key(' ');
      var p1 = page.paused;
      key(' ');
      r.space = page.animated ? p1 !== p0 && page.paused === p0 : null;
      key('?');
      r.help = !!page.helpOpen && page.helpKeys > 5;
      key('Escape');
      r.link = /orbit=/.test(page.viewLink());
      r.ok = r.menu && r.help && r.link && r.space !== false;
      root.dataset.frSelftest = JSON.stringify(r);
    };
    // at once when the page is ready (a browser without a window may stop soon after: no timer to wait for)
    if (page.ready) test();
    else page.listeners.push(function (what) { if (what === 'ready' && !root.dataset.frSelftest) test(); });
  }
})();
