// Fresing Render web 3D player (task 0134): the controls round the 3D view that fr_page.js draws. Reads and sets
// window.frPage (its state and functions) and draws nothing in 3D itself. Nothing is fetched from the internet.
//
//   the "no graphics card" bar      page.warned = 'software' (the browser names a software renderer) or 'probably'
//   the settings menu (gear, M)      surroundings items on/off, Quality Auto/Phone/Balanced/Best, live pictures a
//                                    second, the graphics card's name, Auto-turn, Sun / time of day (live light only),
//                                    choices remembered on this PC (localStorage) with a Reset line
//   playback (pages with motion)     Space play/pause, a time slider, speed ½× 1× 2×, ← → two seconds
//   saved views (task 0179)          wide screens and a phone held sideways: one row of buttons that never wraps (it
//                                    scrolls sideways, "All views" at its end when they do not fit); a phone held
//                                    upright: one pill ‹ name › – the arrows step, the name opens the list of all
//                                    views from the bottom (closes on a pick, a tap outside, Esc or Back). Keys 1 … 9
//   lead motions (task 0310)         one Motions button above the saved views: a panel (wide: above the stack between
//                                    the tool columns, the model free to turn; a phone: a sheet from the bottom) with a
//                                    row per lead motion – name, slider between its end labels, ▶ – and Back to start
//   view tools                       Settings (M), Fullscreen (F), Reset view (R), Help and keys (?), Screenshot (S),
//                                    Copy link to this view (L), Clean look (H: hides every control; a faint button
//                                    brings them back). When the column has no room (a phone: at most 5 upright) the
//                                    rarer ones fold into "More tools"
//
// Layout (task 0179): the header (title, one line on a phone), the two tool columns under it and one stack at the
// bottom (from the bottom: the "Made with" line, the play bar, the views control) never overlap and keep out of the
// screen's safe areas (notch, Android gesture bar, iPhone home bar: viewport-fit=cover + env(safe-area-inset-*)).
// What they leave free is handed to fr_page.js (page.setFree): the model is framed in that rectangle. On a phone the
// "Drag to turn …" hint is a bubble shown on the first visit only (until the first touch or 6 s); a long press on a
// button shows its name; the help lists every button with its icon. page.layoutCheck() lists overlaps and controls
// outside the safe area (tests).
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
  var FONT = '"IBM Plex Sans", "Segoe UI", system-ui, sans-serif';
  var BTN = 40, GAP = 6;                      // tool buttons: touch targets of 40 px, 6 px apart

  // ---------------------------------------------------------------- look
  var css = [
    ':root { --sa-t: env(safe-area-inset-top, 0px); --sa-r: env(safe-area-inset-right, 0px);',
    '  --sa-b: env(safe-area-inset-bottom, 0px); --sa-l: env(safe-area-inset-left, 0px); }',
    '.fr-btn { font: 600 13px ' + FONT + '; color: #F4F6F8; cursor: pointer;',
    '  background: rgba(20,28,34,.62); border: 1px solid rgba(255,255,255,.18); border-radius: 6px; min-height: 36px;',
    '  min-width: 36px; padding: 0 10px; display: inline-flex; align-items: center; justify-content: center; gap: 6px;',
    '  -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; -webkit-tap-highlight-color: transparent; }',
    '.fr-btn:hover { background: rgba(20,28,34,.8); }',
    '.fr-btn:focus-visible, .fr-menu input:focus-visible { outline: 3px solid #F2A900; outline-offset: 1px; }',
    '.fr-btn[aria-pressed="true"] { background: #2F6A1B; border-color: #2F6A1B; }',
    '.fr-btn svg { width: 18px; height: 18px; flex: none; fill: none; stroke: currentColor; stroke-width: 2;',
    '  stroke-linecap: round; stroke-linejoin: round; }',
    '.fr-txt { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }',
    // the header: under the warning bar or the site's frame (--fr-top), out of the notch
    'header { top: var(--fr-top, 0px) !important; padding-top: calc(14px + var(--sa-t)) !important;',
    '  padding-left: calc(18px + var(--sa-l)) !important; padding-right: calc(18px + var(--sa-r)) !important; }',
    'html.fr-warned header { padding-top: 14px !important; }',
    'html.fr-compact header { padding-top: calc(10px + var(--sa-t)) !important; padding-bottom: 6px !important;',
    '  padding-left: calc(12px + var(--sa-l)) !important; padding-right: calc(12px + var(--sa-r)) !important; }',
    'html.fr-compact.fr-warned header { padding-top: 10px !important; }',
    'html.fr-compact h1 { font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;',
    '  flex: 1 1 100%; min-width: 0; }',
    'html.fr-compact header .hint { display: none; }',
    // the two tool columns start under the header (--fr-head, measured)
    '#fr-tools { position: absolute; right: calc(12px + var(--sa-r)); top: var(--fr-head, 50px); z-index: 3;',
    '  display: flex; flex-direction: column; gap: ' + GAP + 'px; }',
    '#fr-tools .fr-btn { padding: 0; width: ' + BTN + 'px; height: ' + BTN + 'px; }',
    '#fr-tools .fr-folded { display: none !important; }',
    '#fr-more { position: absolute; z-index: 5; right: calc(' + (12 + BTN + 10) + 'px + var(--sa-r)); display: none;',
    '  flex-direction: column; min-width: 220px; max-width: calc(100vw - 90px); background: rgba(20,28,34,.94);',
    '  border-radius: 8px; padding: 6px; box-shadow: 0 6px 24px rgba(0,0,0,.35); }',
    '#fr-more .fr-btn { justify-content: flex-start; background: transparent; border: 0; min-height: 44px; gap: 10px;',
    '  font-weight: 500; font-size: 14px; }',
    '#fr-more .fr-btn:hover { background: rgba(255,255,255,.1); }',
    '#fr-more kbd { margin-left: auto; opacity: .7; font: 12px ui-monospace, Consolas, monospace; }',
    // one stack at the bottom: the views control, the play bar, the "Made with" line (bottom first)
    '#fr-bottom { position: absolute; left: calc(12px + var(--sa-l)); right: calc(12px + var(--sa-r));',
    '  bottom: calc(8px + var(--sa-b)); z-index: 2; display: flex; flex-direction: column; align-items: flex-start;',
    '  gap: 6px; pointer-events: none; }',
    '#fr-bottom > * { pointer-events: auto; max-width: 100%; }',
    // the empty parts of the views line and the note line turn the model like the rest of the view
    '#fr-bottom > #fr-views, #fr-bottom .note { pointer-events: none; }',
    '#fr-views > *, #fr-bottom .note a { pointer-events: auto; }',
    '#fr-bottom .note { position: static; line-height: 1.35; }',
    'html.fr-compact #fr-bottom { align-items: stretch; }',
    // a short screen where the part tools reach down to the stack: the stack starts right of them
    'html.fr-beside #fr-bottom { left: calc(' + (12 + BTN + 10) + 'px + var(--sa-l)); }',
    'html.fr-compact #fr-bottom .note { font-size: 11px; }',
    '#fr-views { display: flex; align-items: center; gap: 6px; min-width: 0; }',
    '#fr-views .fr-vscroll { display: flex; gap: 6px; overflow-x: auto; overflow-y: hidden; min-width: 0;',
    '  scrollbar-width: none; overscroll-behavior-x: contain; }',
    '#fr-views .fr-vscroll::-webkit-scrollbar { display: none; }',
    '#fr-views .fr-vscroll.fr-fade-r { -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent);',
    '  mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); }',
    '#fr-views .fr-vscroll.fr-fade-l { -webkit-mask-image: linear-gradient(to left, #000 calc(100% - 28px), transparent);',
    '  mask-image: linear-gradient(to left, #000 calc(100% - 28px), transparent); }',
    '#fr-views .fr-vscroll.fr-fade-l.fr-fade-r { -webkit-mask-image: linear-gradient(to right, transparent, #000 28px,',
    '  #000 calc(100% - 28px), transparent); mask-image: linear-gradient(to right, transparent, #000 28px,',
    '  #000 calc(100% - 28px), transparent); }',
    '#fr-views .fr-vbtn { flex: none; max-width: 220px; min-height: 40px; }',
    '#fr-views .fr-all { flex: none; min-height: 40px; white-space: nowrap; }',
    '#fr-views.fr-pill { background: rgba(20,28,34,.72); border: 1px solid rgba(255,255,255,.18); border-radius: 22px;',
    '  gap: 0; padding: 1px; }',
    '#fr-views.fr-pill .fr-btn { background: transparent; border: 0; min-height: 42px; border-radius: 20px; }',
    '#fr-views.fr-pill .fr-step { width: 44px; padding: 0; flex: none; }',
    '#fr-views.fr-pill .fr-vname { flex: 1 1 auto; min-width: 0; padding: 0 6px; justify-content: center; }',
    '#fr-views.fr-pill .fr-vname .fr-count { flex: none; font-weight: 400; color: #D5DBE0; font-size: 12px;',
    '  font-variant-numeric: tabular-nums; }',
    '#fr-views.fr-pill.fr-moved .fr-vname .fr-txt { opacity: .7; }',
    '#fr-views .fr-vbtn.fr-moved[aria-pressed="true"] { background: rgba(47,106,27,.55); }',
    '#fr-playbar { display: flex; flex-wrap: nowrap; align-items: center; gap: 6px; background: rgba(20,28,34,.62);',
    '  border-radius: 8px; padding: 2px 6px; color: #F4F6F8; font: 13px ' + FONT + ';',
    '  width: min(560px, 100%); box-sizing: border-box; }',
    'html.fr-compact #fr-playbar { width: 100%; font-size: 12px; gap: 4px; }',
    '#fr-playbar input[type=range] { flex: 1 1 auto; min-width: 40px; accent-color: #F2A900; height: 28px; margin: 0; }',
    '#fr-playbar .fr-btn { background: transparent; border: 0; min-height: 40px; }',
    '#fr-playbar .fr-play { width: 40px; padding: 0; flex: none; }',
    '#fr-playbar .fr-time { font-variant-numeric: tabular-nums; white-space: nowrap; flex: none; }',
    '#fr-playbar .fr-speed { display: flex; flex: none; }',
    '#fr-playbar .fr-speed .fr-btn { padding: 0 4px; min-width: 34px; }',
    '#fr-playbar .fr-speed .fr-btn[aria-pressed="true"] { background: rgba(255,255,255,.22); }',
    // task 0252: the Film button; lit (orange) when the visitor left the Film and one press takes them back
    '#fr-playbar .fr-film { width: 40px; padding: 0; flex: none; }',
    '#fr-playbar .fr-film.fr-back { color: #F2A900; box-shadow: inset 0 0 0 2px #F2A900; }',
    '#fr-playbar .fr-film[aria-pressed="true"] { background: #2F6A1B; color: #F4F6F8; box-shadow: none; }',
    '#fr-film-labels { position: absolute; left: 0; top: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }',
    '#fr-film-cap { position: absolute; z-index: 1; pointer-events: none; display: none; text-align: center;',
    '  transform: translate(-50%, 50%); color: #fff; background: rgba(0,0,0,.45); border-radius: 4px;',
    '  text-shadow: 0 1px 3px rgba(0,0,0,.6); font-family: ' + FONT + '; line-height: 1.2; padding: .15em .4em;',
    '  overflow-wrap: anywhere; box-sizing: border-box; }',
    '#fr-film-card { position: absolute; inset: 0; z-index: 1; pointer-events: none; display: none; overflow: hidden;',
    '  font-family: ' + FONT + '; text-align: center; }',
    '#fr-film-card div { position: absolute; left: 7.5%; right: 7.5%; transform: translateY(50%); line-height: 1.15;',
    '  overflow-wrap: anywhere; }',
    '#fr-film-card img { position: absolute; object-fit: contain; }',
    // task 0310: the Motions button and its panel (one row per lead motion)
    '#fr-motions { display: flex; }',
    '#fr-bottom > #fr-motions { pointer-events: none; }',
    '#fr-motions > * { pointer-events: auto; }',
    '#fr-motions .fr-mbtn { min-height: 40px; }',
    '#fr-motions .fr-mbtn[aria-expanded="true"] { background: #2F6A1B; border-color: #2F6A1B; }',
    '#fr-motions .fr-count { font-weight: 400; color: #D5DBE0; font-size: 12px; font-variant-numeric: tabular-nums; }',
    '#fr-mpanel { position: absolute; z-index: 4; display: none; flex-direction: column; box-sizing: border-box;',
    '  left: calc(' + (12 + BTN + 10) + 'px + var(--sa-l)); bottom: calc(var(--fr-stack, 90px) + 6px);',
    '  width: min(420px, calc(100% - 2 * (' + (12 + BTN + 10) + 'px + max(var(--sa-l), var(--sa-r)))));',
    '  max-height: calc(100% - var(--fr-head, 50px) - var(--fr-stack, 90px) - 12px);',
    '  background: rgba(20,28,34,.94); color: #F4F6F8; border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,.35);',
    '  font: 13px ' + FONT + '; }',
    'html.fr-narrow #fr-mpanel { position: fixed; z-index: 8; left: 0; right: 0; bottom: 0; width: auto;',
    '  max-height: min(55%, 520px); border-radius: 14px 14px 0 0; padding-bottom: var(--sa-b);',
    '  background: #141C22; box-shadow: 0 -6px 24px rgba(0,0,0,.35);',
    '  padding-left: var(--sa-l); padding-right: var(--sa-r); }',
    '#fr-mpanel .fr-vhead { display: flex; align-items: center; justify-content: space-between; padding: 4px 4px 2px 14px;',
    '  border-bottom: 1px solid rgba(255,255,255,.12); }',
    '#fr-mpanel h2 { font-size: 14px; margin: 0; font-weight: 600; }',
    '#fr-mpanel .fr-x { background: transparent; border: 0; width: 44px; height: 44px; padding: 0; }',
    '#fr-mpanel .fr-mlist { overflow-y: auto; overscroll-behavior: contain; padding: 4px 0; }',
    '#fr-mpanel .fr-mrow { padding: 4px 12px 2px 14px; }',
    '#fr-mpanel .fr-mtop { display: flex; align-items: baseline; gap: 8px; min-width: 0; }',
    '#fr-mpanel .fr-mname { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }',
    '#fr-mpanel .fr-mby { color: #F2A900; font-size: 12px; white-space: nowrap; margin-left: auto; }',
    '#fr-mpanel .fr-mabout { color: #D5DBE0; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '#fr-mpanel .fr-mline { display: flex; align-items: center; gap: 6px; }',
    '#fr-mpanel .fr-mline .fr-btn { width: 40px; min-height: 40px; padding: 0; flex: none; background: transparent; border: 0; }',
    '#fr-mpanel .fr-mline .fr-btn[aria-pressed="true"] { background: rgba(255,255,255,.18); }',
    '#fr-mpanel input[type=range] { flex: 1 1 auto; min-width: 60px; accent-color: #F2A900; height: 32px; margin: 0; }',
    '#fr-mpanel .fr-mend { flex: none; font-size: 12px; color: #D5DBE0; font-variant-numeric: tabular-nums; white-space: nowrap; }',
    '#fr-mpanel .fr-mfoot { display: flex; justify-content: flex-end; padding: 4px 8px 8px; border-top: 1px solid rgba(255,255,255,.12); }',
    '#fr-mpanel .fr-mfoot .fr-btn { min-height: 40px; }',
    // the list of all views: a sheet from the bottom (a phone), a panel above the stack (wide)
    '#fr-vback { position: fixed; inset: 0; z-index: 7; background: rgba(0,0,0,.28); display: none; }',
    '#fr-vlist { position: fixed; z-index: 8; left: 0; right: 0; bottom: 0; display: none; flex-direction: column;',
    '  max-height: min(62%, 560px); background: rgba(20,28,34,.97); color: #F4F6F8; border-radius: 14px 14px 0 0;',
    '  box-shadow: 0 -6px 24px rgba(0,0,0,.35); font: 14px ' + FONT + '; padding-bottom: var(--sa-b);',
    '  padding-left: var(--sa-l); padding-right: var(--sa-r); }',
    'html:not(.fr-narrow) #fr-vlist { left: 50%; right: auto; width: min(460px, calc(100vw - 24px));',
    '  transform: translateX(-50%); bottom: calc(8px + var(--sa-b)); border-radius: 10px; padding: 0; }',
    '#fr-vlist .fr-vhead { display: flex; align-items: center; justify-content: space-between; padding: 6px 6px 4px 16px;',
    '  border-bottom: 1px solid rgba(255,255,255,.12); }',
    '#fr-vlist h2 { font-size: 14px; margin: 0; font-weight: 600; }',
    '#fr-vlist .fr-x { background: transparent; border: 0; width: 44px; height: 44px; padding: 0; }',
    '#fr-vlist ol { list-style: none; margin: 0; padding: 4px 0 8px; overflow-y: auto; overscroll-behavior: contain; }',
    '#fr-vlist li .fr-btn { width: 100%; justify-content: flex-start; text-align: left; background: transparent; border: 0;',
    '  border-radius: 0; min-height: 46px; padding: 6px 16px; gap: 12px; font-weight: 500; font-size: 14px; }',
    '#fr-vlist li .fr-btn:hover { background: rgba(255,255,255,.08); }',
    '#fr-vlist li .fr-n { flex: none; min-width: 26px; height: 26px; border-radius: 13px; display: inline-flex;',
    '  align-items: center; justify-content: center; font-size: 12px; font-variant-numeric: tabular-nums;',
    '  background: rgba(255,255,255,.12); }',
    '#fr-vlist li .fr-btn[aria-current="true"] { background: rgba(47,106,27,.45); }',
    '#fr-vlist li .fr-btn[aria-current="true"] .fr-n { background: #2F6A1B; }',
    '#fr-vlist li .fr-name { overflow-wrap: anywhere; }',
    '.fr-menu { position: absolute; right: calc(' + (12 + BTN + 10) + 'px + var(--sa-r)); top: var(--fr-head, 50px);',
    '  z-index: 4; width: min(320px, calc(100vw - 86px)); max-height: calc(100% - var(--fr-head, 50px) - 12px - var(--sa-b));',
    '  overflow: auto; background: rgba(20,28,34,.9); color: #F4F6F8;',
    '  border-radius: 8px; padding: 12px 14px; font: 13px ' + FONT + ';',
    '  box-shadow: 0 6px 24px rgba(0,0,0,.35); display: none; box-sizing: border-box; }',
    '.fr-menu h2 { font-size: 14px; margin: -6px -8px 4px 0; display: flex; align-items: center; justify-content: space-between; }',
    '.fr-menu .fr-x { background: transparent; border: 0; width: 40px; height: 40px; padding: 0; }',
    '.fr-menu h3 { font-size: 12px; margin: 12px 0 4px; color: #D5DBE0; font-weight: 600; text-transform: uppercase;',
    '  letter-spacing: .04em; }',
    '.fr-menu label { display: flex; align-items: center; gap: 8px; min-height: 30px; cursor: pointer; }',
    '.fr-menu input[type=checkbox] { width: 18px; height: 18px; accent-color: #2F6A1B; }',
    '.fr-menu input[type=range] { width: 100%; accent-color: #F2A900; }',
    '.fr-menu .fr-seg { display: flex; gap: 4px; flex-wrap: wrap; }',
    '.fr-menu .fr-seg .fr-btn { flex: 1; min-height: 34px; padding: 0 6px; font-size: 12px; }',
    '.fr-menu .fr-small { color: #D5DBE0; font-size: 12px; margin: 4px 0; overflow-wrap: anywhere; }',
    '.fr-menu .fr-grey { opacity: .45; }',
    '.fr-menu a { color: #F2A900; cursor: pointer; }',
    '#fr-warn { position: absolute; left: 0; right: 0; top: 0; z-index: 5; background: #8A1C1C; color: #fff;',
    '  font: 14px ' + FONT + '; padding: calc(10px + var(--sa-t)) calc(14px + var(--sa-r)) 10px calc(14px + var(--sa-l));',
    '  display: none; align-items: flex-start; gap: 12px; }',
    '#fr-warn p { margin: 0; flex: 1; }',
    '#fr-warn code { background: rgba(0,0,0,.25); padding: 0 4px; border-radius: 3px; }',
    '#fr-help { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); z-index: 6; display: none;',
    '  background: rgba(20,28,34,.95); color: #F4F6F8; border-radius: 8px; padding: 14px 18px; min-width: 260px;',
    '  max-width: min(520px, calc(100vw - 24px)); max-height: calc(100% - 24px); overflow: auto; box-sizing: border-box;',
    '  font: 13px ' + FONT + '; box-shadow: 0 6px 24px rgba(0,0,0,.4); }',
    '#fr-help h2 { font-size: 15px; margin: 0 0 2px; overflow-wrap: anywhere; }',
    '#fr-help h3 { font-size: 12px; margin: 12px 0 4px; color: #D5DBE0; font-weight: 600; text-transform: uppercase;',
    '  letter-spacing: .04em; }',
    '#fr-help table { border-collapse: collapse; }',
    '#fr-help td { padding: 3px 10px 3px 0; vertical-align: middle; }',
    '#fr-help td:first-child { white-space: nowrap; }',
    '#fr-help td svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round;',
    '  stroke-linejoin: round; display: block; }',
    '#fr-help kbd { display: inline-block; min-width: 18px; text-align: center; border: 1px solid rgba(255,255,255,.4);',
    '  border-radius: 4px; padding: 0 5px; font: 12px ui-monospace, Consolas, monospace; }',
    '#fr-help .fr-close { color: #D5DBE0; font-size: 12px; margin: 10px 0 0; }',
    // short messages (a toast, the quality note, the first visit's hint): above the bottom stack, between the columns
    '.fr-bubble { position: absolute; left: 50%; bottom: calc(var(--fr-stack, 90px) + 8px); transform: translateX(-50%);',
    '  z-index: 6; display: none; background: rgba(20,28,34,.9); color: #fff; padding: 8px 14px; border-radius: 6px;',
    '  font: 13px ' + FONT + '; box-sizing: border-box; text-align: center; pointer-events: none;',
    '  max-width: min(440px, calc(100% - 2 * (' + (12 + BTN + 8) + 'px + max(var(--sa-l), var(--sa-r)))));',
    '  overflow-wrap: anywhere; }',
    '#fr-toast { pointer-events: auto; }',
    '#fr-first { transition: opacity .4s; }',
    '#fr-tip { position: fixed; z-index: 9; display: none; background: #F4F6F8; color: #14202A; padding: 6px 10px;',
    '  border-radius: 6px; font: 600 13px ' + FONT + '; box-shadow: 0 3px 12px rgba(0,0,0,.35); max-width: 240px;',
    '  pointer-events: none; }',
    '#fr-quality, #quality { display: none !important; }',
    '#fr-show { position: absolute; right: calc(8px + var(--sa-r)); bottom: calc(8px + var(--sa-b)); z-index: 6;',
    '  display: none; opacity: .28; }',
    '#fr-show:hover, #fr-show:focus-visible { opacity: .9; }',
    'html.fr-clean header, html.fr-clean .note, html.fr-clean #quality, html.fr-clean #fr-tools,',
    'html.fr-clean #fr-bottom, html.fr-clean .fr-menu, html.fr-clean #fr-help, html.fr-clean #fr-warn,',
    'html.fr-clean #fr-site, html.fr-clean #fr-vlist, html.fr-clean #fr-vback, html.fr-clean #fr-more, html.fr-clean #fr-mpanel,',
    'html.fr-clean #fr-first, html.fr-clean #fr-tip { display: none !important; }',
    'html.fr-clean #fr-show { display: inline-flex; }',
    '@media (max-width: 600px), (max-height: 480px) { #fr-help { left: 0; right: 0; top: auto; bottom: 0; transform: none;',
    '  border-radius: 12px 12px 0 0; max-height: 55%; min-width: 0; max-width: none; z-index: 7;',
    '  padding-bottom: calc(14px + var(--sa-b)); } }',
    '@media (max-height: 480px) { #fr-help { right: calc(' + (12 + BTN + 10) + 'px + var(--sa-r)); max-height: 75%; } }'
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
    pause: '<path d="M7 4v16M17 4v16" stroke-width="4"/>',
    more: '<circle cx="5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="19" cy="12" r="1.6" fill="currentColor"/>',
    left: '<path d="M15 5l-7 7 7 7"/>',
    right: '<path d="M9 5l7 7-7 7"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    close: '<path d="M6 6l12 12M18 6L6 18"/>',
    film: '<rect x="2" y="5" width="15" height="14" rx="2"/><path d="M17 10l5-3v10l-5-3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>'
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
    if (key) b.dataset.key = key;
    b.addEventListener('click', function () { fn(); b.blur(); page.input && page.input(); });
    if (parent) parent.appendChild(b);
    return b;
  }
  function visible(e) {
    if (!e || !e.isConnected) return false;
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity < 0.05) return false;
    var r = e.getBoundingClientRect();
    return r.width > 0.5 && r.height > 0.5 && (e.offsetParent !== null || cs.position === 'fixed');
  }

  // ---------------------------------------------------------------- screen size
  var TOUCH = !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches);
  page.touch = TOUCH;
  var narrow = false, compact = false;
  function measureMode() {
    narrow = window.innerWidth < 600;                       // a phone held upright
    compact = narrow || window.innerHeight < 480;           // … or sideways
    root.classList.toggle('fr-narrow', narrow);
    root.classList.toggle('fr-compact', compact);
  }
  measureMode();

  // ---------------------------------------------------------------- remembered choices
  var HINT_KEY = page.prefKey + ':hint';                    // task 0179: the phone's hint was seen
  function save() {
    // 0147 row 21d: only what the visitor switched (the page's own "no shadows without a graphics card" is not kept)
    var p = { quality: page.quality, off: page.visitorOff(), chose: page.chosenItems(), turn: !!page.turn,
              speed: page.speed };
    if (page.toolPrefs) p.tools = page.toolPrefs();                   // task 0135: the part tools' choices
    try { window.localStorage.setItem(page.prefKey, JSON.stringify(p)); page.saved = true; } catch (e) { page.saved = false; }
  }
  page.savePrefs = save;                     // task 0135: the part tools' choices are kept with the rest
  function forget() {
    try { window.localStorage.removeItem(page.prefKey); window.localStorage.removeItem(HINT_KEY); }
    catch (e) { /* private window: nothing was kept */ }
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
    layout();
  }, warn);
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
    layout();
  }

  // ---------------------------------------------------------------- tools (top right)
  var tools = el('div', { id: 'fr-tools', role: 'toolbar', 'aria-label': 'View tools' });
  var menuBtn = button('gear', 'Settings', 'M', function () { toggleMenu(); }, tools);
  menuBtn.setAttribute('aria-expanded', 'false');
  var canFull = !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
  var fullBtn = canFull ? button('full', 'Fullscreen', 'F', fullscreen, tools) : null;
  var resetBtn = button('reset', 'Reset view', 'R', function () { page.resetView(); }, tools);
  var shotBtn = button('shot', 'Screenshot', 'S', screenshot, tools);
  var linkBtn = button('link', 'Copy link to this view', 'L', copyLink, tools);
  var helpBtn = button('help', 'Help and keys', '?', function () { toggleHelp(); }, tools);
  var cleanBtn = button('eye', 'Clean look: hide the controls', 'H', function () { clean(true); }, tools);
  var moreBtn = button('more', 'More tools', '', function () { toggleMore(); }, tools);
  moreBtn.id = 'fr-more-btn';
  moreBtn.setAttribute('aria-expanded', 'false');
  moreBtn.setAttribute('aria-haspopup', 'true');
  // the column keeps these first when it has no room for all (the rest fold into More tools)
  var KEEP = [menuBtn, resetBtn, fullBtn, helpBtn, shotBtn, linkBtn, cleanBtn].filter(Boolean);
  document.body.appendChild(tools);
  var more = el('div', { id: 'fr-more', role: 'menu', 'aria-label': 'More tools' });
  document.body.appendChild(more);
  var show = button('eye', 'Show the controls', 'H', function () { clean(false); });
  show.id = 'fr-show';
  document.body.appendChild(show);

  function folded() { return KEEP.filter(function (b) { return b.classList.contains('fr-folded'); }); }
  // as many buttons as fit between the header and the bottom stack (a phone upright: at most 5), the rest in More
  function fitTools(stackTop) {
    var top = tools.getBoundingClientRect().top;
    var room = Math.max(2, Math.floor((stackTop - 8 - top + GAP) / (BTN + GAP)));
    if (narrow) room = Math.min(room, 5);
    var keep = KEEP.length <= room ? KEEP.length : room - 1;
    KEEP.forEach(function (b, k) { b.classList.toggle('fr-folded', k >= keep); });
    moreBtn.style.display = keep < KEEP.length ? '' : 'none';
    if (keep >= KEEP.length) toggleMore(false);
    page.toolsShown = KEEP.length > keep ? keep + 1 : keep;
  }
  function toggleMore(on) {
    page.moreOpen = on == null ? !page.moreOpen : !!on;
    if (page.moreOpen) {
      toggleMenu(false); toggleHelp(false); openList(false);
      more.innerHTML = '';
      folded().forEach(function (b) {
        var item = el('button', { type: 'button', 'class': 'fr-btn', role: 'menuitem' }, b.innerHTML);
        item.appendChild(el('span', { text: b.getAttribute('aria-label') }));
        if (b.dataset.key && !TOUCH) item.appendChild(el('kbd', { text: b.dataset.key }));
        item.addEventListener('click', function () { toggleMore(false); b.click(); });
        more.appendChild(item);
      });
      more.style.display = 'flex';
      var r = moreBtn.getBoundingClientRect(), h = more.offsetHeight;
      var limit = (bottom.getBoundingClientRect().top || window.innerHeight) - 8;
      more.style.top = Math.max(8, Math.min(r.top, limit - h)) + 'px';
    } else more.style.display = 'none';
    moreBtn.setAttribute('aria-expanded', page.moreOpen ? 'true' : 'false');
    moreBtn.setAttribute('aria-pressed', page.moreOpen ? 'true' : 'false');
    if (page.moreOpen) opened(); else closed();
  }

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
    var SPELL = { 'ø': 'o', 'Ø': 'O', 'æ': 'ae', 'Æ': 'AE', 'ß': 'ss', 'œ': 'oe',
                  'Œ': 'OE', 'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'þ': 'th',
                  'Þ': 'Th', 'ð': 'd', 'Ð': 'D', 'ı': 'i' };
    t = t.replace(/[øØæÆßœŒłŁđĐþÞðÐı]/g,
                  function (c) { return SPELL[c]; });
    t = t.replace(/[‐-―]/g, '-').replace(/[̀-ͯ]/g, '').replace(/[^\x20-\x7e]+/g, '')
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

  // ---------------------------------------------------------------- short messages
  var toastEl = el('div', { id: 'fr-toast', 'class': 'fr-bubble', role: 'status' }), toastTimer = null, toastKind = '';
  document.body.appendChild(toastEl);
  function toast(text, seconds, kind) {
    clearTimeout(toastTimer);
    toastKind = kind || 'toast';
    toastEl.textContent = text;
    toastEl.style.display = 'block';
    hint.style.display = 'none';            // the first visit's hint makes room, and comes back after it
    toastTimer = setTimeout(function () {
      toastEl.style.display = 'none'; toastKind = '';
      if (hintOn && compact) hint.style.display = 'block';
    }, (seconds || 2.5) * 1000);
  }
  // task 0179: fr_page.js's quality note ("Quality Phone: lowered to keep it smooth") as a short message for ~4 s (it
  // stood on top of "Made with Fresing Render"); the level itself stays readable in the settings menu
  page.notify = function (text, seconds) {
    if (!text) {
      if (toastKind === 'note') {
        clearTimeout(toastTimer); toastEl.style.display = 'none'; toastKind = '';
        if (hintOn && compact) hint.style.display = 'block';
      }
      return;
    }
    toast(text, Math.min(seconds || 4, 4), 'note');
  };
  function clean(on) {
    page.clean = !!on;
    root.classList.toggle('fr-clean', page.clean);
    if (page.clean) { toggleMenu(false); toggleHelp(false); toggleMore(false); openList(false); }
    page.wake();
    layout();
  }

  // the first visit on a phone: "Drag to turn …" as a bubble until the first touch or 6 s (it took two lines of the
  // header over the model); later visits go without it, the help keeps it
  var hintText = document.querySelector('header .hint');
  // 0147 row 21e: a phone has no right button and no keys
  var HINT = TOUCH ? 'Drag to turn · pinch to zoom · two fingers to move' : 'Drag to turn · scroll to zoom · right-drag to move';
  if (hintText) hintText.textContent = TOUCH ? HINT + ' · tools on the left' : hintText.textContent + ' · ? for keys';
  var hint = el('div', { id: 'fr-first', 'class': 'fr-bubble', 'aria-hidden': 'true', text: HINT });
  document.body.appendChild(hint);
  var hintSeen = false;
  try { hintSeen = window.localStorage.getItem(HINT_KEY) === '1'; } catch (e) { hintSeen = false; }
  var hintOn = (compact || TOUCH) && !hintSeen, hintTimer = null;
  function hideHint() {
    if (!hintOn) return;
    hintOn = false;
    clearTimeout(hintTimer);
    hint.style.opacity = '0';
    setTimeout(function () { hint.style.display = 'none'; }, 450);
    try { window.localStorage.setItem(HINT_KEY, '1'); } catch (e) { /* private window: shown again next time */ }
  }
  page.hideHint = hideHint;
  function showHint() {
    if (!hintOn || !compact) return;
    if (toastEl.style.display !== 'block') hint.style.display = 'block';
    hintTimer = setTimeout(hideHint, 6000);
  }
  ['pointerup', 'keydown', 'wheel'].forEach(function (ev) {
    window.addEventListener(ev, function () { if (hintOn && page.ready) setTimeout(hideHint, 200); }, { passive: true });
  });

  // a long press on a button (touch: no tooltip) shows its name; the press then does not click it
  var tip = el('div', { id: 'fr-tip', role: 'tooltip' }), press = null, swallow = null, tipTimer = null;
  document.body.appendChild(tip);
  function showTip(b) {
    tip.textContent = b.getAttribute('aria-label');
    tip.style.display = 'block';
    var r = b.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, W = window.innerWidth;
    var x = r.left + r.width / 2 > W / 2 ? r.left - w - 8 : r.right + 8, y = r.top + (r.height - h) / 2;
    if (x < 4 || x + w > W - 4) { x = Math.min(W - w - 4, Math.max(4, r.left + (r.width - w) / 2)); y = r.top - h - 8; }
    tip.style.left = Math.round(x) + 'px';
    tip.style.top = Math.round(Math.max(4, y)) + 'px';
    page.lastTip = tip.textContent;
    clearTimeout(tipTimer);
    tipTimer = setTimeout(function () { tip.style.display = 'none'; }, 2000);
  }
  document.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'mouse') return;
    var b = e.target && e.target.closest && e.target.closest('.fr-btn[aria-label]');
    if (!b) return;
    var p = press = { b: b, x: e.clientX, y: e.clientY, long: false };
    p.timer = setTimeout(function () { p.long = true; showTip(b); }, 450);
  }, true);
  document.addEventListener('pointermove', function (e) {
    if (press && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 10) { clearTimeout(press.timer); press = null; }
  }, true);
  function endPress() {
    if (!press) return;
    clearTimeout(press.timer);
    if (press.long) { swallow = press.b; setTimeout(function () { swallow = null; }, 600); }
    press = null;
  }
  document.addEventListener('pointerup', endPress, true);
  document.addEventListener('pointercancel', endPress, true);
  document.addEventListener('click', function (e) {
    if (swallow && e.target && e.target.closest && e.target.closest('.fr-btn') === swallow) {
      e.preventDefault(); e.stopPropagation(); swallow = null;
    }
  }, true);
  document.addEventListener('contextmenu', function (e) {
    if (e.target && e.target.closest && e.target.closest('.fr-btn')) e.preventDefault();
  }, true);

  // ---------------------------------------------------------------- Back closes what is open
  // (Android's back gesture, the browser's button): one history entry while a sheet, a menu or the list is open
  var pushed = false, ignorePop = 0, popping = false;
  function anyOpen() { return !!(page.listOpen || page.helpOpen || page.menuOpen || page.moreOpen || page.motionsOpen); }
  function opened() {
    if (pushed || popping) return;
    try { history.pushState({ frSheet: 1 }, ''); pushed = true; } catch (e) { pushed = false; }
  }
  function closed() {
    if (!pushed || popping || anyOpen()) return;
    pushed = false;
    ignorePop++;
    try { history.back(); } catch (e) { ignorePop--; }
  }
  window.addEventListener('popstate', function () {
    if (ignorePop > 0) { ignorePop--; return; }
    if (!pushed) return;
    pushed = false;
    popping = true;
    try { toggleMenu(false); toggleHelp(false); toggleMore(false); openList(false); openMotions(false); }
    finally { popping = false; }
  });

  // ---------------------------------------------------------------- the settings menu
  var menu = el('div', { 'class': 'fr-menu', id: 'fr-menu', role: 'dialog', 'aria-label': 'Settings' });
  document.body.appendChild(menu);
  function toggleMenu(on) {
    page.menuOpen = on == null ? !page.menuOpen : !!on;
    if (page.menuOpen) { toggleHelp(false); toggleMore(false); openList(false); openMotions(false); fillMenu(); }
    menu.style.display = page.menuOpen ? 'block' : 'none';
    menuBtn.setAttribute('aria-expanded', page.menuOpen ? 'true' : 'false');
    menuBtn.setAttribute('aria-pressed', page.menuOpen ? 'true' : 'false');
    if (page.menuOpen) opened(); else closed();
  }
  var fpsEl = null, levelEl = null, segBtns = {}, sunText = null;
  function fillMenu() {
    menu.innerHTML = '';
    var mh = el('h2', { text: 'Settings' });
    var mx = button('close', 'Close the settings', 'Esc', function () { toggleMenu(false); }, mh);
    mx.classList.add('fr-x');
    menu.appendChild(mh);
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
    levelEl = el('p', { 'class': 'fr-small', id: 'fr-level' });
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
    lt.appendChild(document.createTextNode('Auto-turn (after 8 s without a touch, or flick the model)'));
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
    menu.appendChild(el('h3', { text: 'Remembered in this browser' }));
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
      (page.auto ? ' (Auto: lower when it cannot keep up, higher again when there is room)' : '') +
      (page.lowered && page.auto && page.level !== page.settings.quality ? ' – lowered to keep it smooth' : '');
    fpsEl.textContent = page.fps > 0 ? Math.round(page.fps) + ' pictures a second (at most ' + page.cap + ')'
      : page.moving() ? 'Counting the pictures a second …'
      : 'No pictures drawn while nothing moves (at most ' + page.cap + ' a second)';
    if (sunText) sunText.textContent = page.sunLive ? hhmm(page.sunHour) + (Math.abs(page.sunHour - 13) < 0.01
      ? ' (as exported)' : '') : page.sunWhy;
    var boxes = menu.querySelectorAll('input[data-item]');
    for (var i = 0; i < boxes.length; i++) boxes[i].checked = page.on[boxes[i].dataset.item] !== false;
  }

  // ---------------------------------------------------------------- help: the title, every button, the keys
  var GESTURES = TOUCH ? [['One finger', 'turn'], ['Two fingers', 'move'], ['Pinch', 'zoom'],
                          ['Tap', 'with a part tool on: pick a part or a face'], ['Long press', 'on a part: what it is; '
                          + 'on a button: its name']]
    : [['Drag', 'turn'], ['Right-drag / two fingers', 'move'], ['Scroll / pinch', 'zoom']];
  var help = el('div', { id: 'fr-help', role: 'dialog', 'aria-label': 'Help and keys' });
  document.body.appendChild(help);
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function fillHelp() {
    var h1 = document.querySelector('header h1');
    var html = '<h2>' + esc(h1 ? h1.textContent : document.title) + '</h2>';
    html += '<h3>' + (TOUCH ? 'Touch' : 'Mouse') + '</h3><table>' + GESTURES.map(function (r) {
      return '<tr><td>' + r[0] + '</td><td>' + r[1] + '</td></tr>';
    }).join('') + '</table>';
    // every button with its icon and name (a phone has no tooltips)
    var btns = [].slice.call(document.querySelectorAll('#fr-parts > .fr-btn, #fr-tools > .fr-btn'))
      .filter(function (b) { return b !== moreBtn; });
    html += '<h3>Buttons</h3><table>' + btns.map(function (b) {
      var icon = b.querySelector('svg');
      return '<tr><td>' + (icon ? icon.outerHTML : '') + '</td><td>' + esc(b.getAttribute('aria-label')) +
        (b.dataset.key && !TOUCH ? ' <kbd>' + esc(b.dataset.key) + '</kbd>' : '') + '</td></tr>';
    }).join('');
    if (!moreBtn.style.display) html += '<tr><td>' + svg('more') + '</td><td>More tools: ' +
      folded().map(function (b) { return esc(b.getAttribute('aria-label')); }).join(', ') + '</td></tr>';
    if (page.views.length > 1) {
      html += '<tr><td>' + svg(mode === 'pill' ? 'left' : 'list') + '</td><td>' + (mode === 'pill'
        ? 'Saved views: ‹ › the previous / next one, tap the name for the list of all ' + page.views.length
        : 'Saved views: one button each' + (page.views.length > 3 ? ', All views for the list' : '')) + '</td></tr>';
    }
    if (mBtn) html += '<tr><td>' + svg('sliders') + '</td><td>Motions: one slider per function of the machine, ' +
      '▶ plays it, Back to start puts them all at 0 %</td></tr>';
    html += '</table>';
    var rows = [];
    if (!TOUCH) {
      if (page.animated) rows.push(['Space', 'play / pause'], ['← →', 'two seconds back / on']);
      if (page.views.length) rows.push([page.views.length > 1 ? '1 … ' + Math.min(9, page.views.length) : '1',
                                        page.views.length > 1 ? 'saved views' : 'the saved view']);
      rows.push(['M', 'settings']);
      if (canFull) rows.push(['F', 'fullscreen']);
      rows.push(['R', 'reset view'], ['S', 'screenshot (PNG)'], ['L', 'copy link to this view'],
                ['H', 'hide / show the controls']);
      (page.toolKeys || []).forEach(function (r) { rows.push(r); });      // task 0135: the part tools
      rows.push(['?', 'this help'], ['Esc', 'close']);
      html += '<h3>Keys</h3><table>' + rows.map(function (r) {
        return '<tr><td>' + r[0].split(' / ').map(function (k) { return /^(Space|Esc|[A-Z?]|← →|\d( … \d)?)$/.test(k) ? '<kbd>' + k + '</kbd>' : k; })
          .join(' / ') + '</td><td>' + r[1] + '</td></tr>';
      }).join('') + '</table>';
    }
    html += '<p class="fr-close">' + (TOUCH ? 'Tap to close' : 'Click or Esc to close') + '</p>';
    help.innerHTML = html;
    page.helpKeys = rows.length + btns.length;
  }
  function toggleHelp(on) {
    page.helpOpen = on == null ? !page.helpOpen : !!on;
    if (page.helpOpen) { fillHelp(); toggleMenu(false); toggleMore(false); openList(false); openMotions(false); }
    help.style.display = page.helpOpen ? 'block' : 'none';
    if (page.helpOpen) opened(); else closed();
  }
  help.addEventListener('click', function () { toggleHelp(false); });

  // ---------------------------------------------------------------- bottom: saved views, playback, the note line
  var bottom = el('div', { id: 'fr-bottom' });
  var viewsBox = el('div', { id: 'fr-views', role: 'group', 'aria-label': 'Saved views' });
  var play = el('div', { id: 'fr-playbar' });
  var motionsBox = el('div', { id: 'fr-motions' });          // task 0310
  motionsBox.style.display = 'none';
  bottom.appendChild(motionsBox);
  bottom.appendChild(viewsBox);
  bottom.appendChild(play);
  document.body.appendChild(bottom);
  var noteLine = document.querySelector('body > .note');
  if (noteLine) bottom.appendChild(noteLine);
  play.style.display = 'none';
  viewsBox.style.display = 'none';
  var playBtn, slider, timeEl, speedBtns = {}, dragging = false, wasPaused = false, filmBtn = null;
  function fmt(s) {
    s = Math.max(0, s);
    return Math.floor(s / 60) + ':' + ('0' + (s % 60).toFixed(1)).slice(-4);
  }
  var built = false;
  function buildBottom() {
    if (built) return;
    built = true;
    wrapViews();
    buildViews();
    buildMotions();
    if (!page.animated) return;
    play.style.display = 'flex';
    playBtn = button('pause', 'Play / pause', 'Space', function () { page.paused = !page.paused; }, play);
    playBtn.classList.add('fr-play');
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
    if (page.film) {                          // task 0252: the motion seen through the video's camera
      filmBtn = button('film', "Play the video's camera moves", '', function () {
        page.setFilm(!page.filmOn(), true);
      }, play);
      filmBtn.classList.add('fr-film');
    }
    refreshPlay();
  }
  function refreshPlay() {
    if (!slider) return;
    var t = page.duration > 0 ? page.time % page.duration : 0;
    if (!dragging) slider.value = String(t);
    // a phone upright: the moment only (the whole length is the slider's end)
    timeEl.textContent = fmt(t) + (narrow && window.innerWidth < 380 ? '' : ' / ' + fmt(page.duration));
    // task 0252: a phone narrower than 330 px with the Film button: the time line alone shows the moment
    timeEl.style.display = filmBtn && window.innerWidth < 330 ? 'none' : '';
    playBtn.innerHTML = svg(page.paused ? 'play' : 'pause');
    playBtn.setAttribute('aria-label', page.paused ? 'Play' : 'Pause');
    playBtn.setAttribute('aria-pressed', page.paused ? 'false' : 'true');
    for (var s in speedBtns) speedBtns[s].setAttribute('aria-pressed', +s === page.speed ? 'true' : 'false');
    refreshFilm();
  }
  function refreshFilm() {
    if (!filmBtn) return;
    var st = page.filmState(), on = !!(st && st.on);
    filmBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
    filmBtn.classList.toggle('fr-back', !on && !!(st && st.left));
    var label = on ? 'Film: on – drag to look around' : st && st.left ? 'Back to the Film (the video\'s camera)'
      : "Play the video's camera moves";
    filmBtn.setAttribute('aria-label', label);
    filmBtn.title = label;
  }

  // ---- the views control (task 0179): one row that never wraps, or one pill ‹ name › on a phone held upright
  var cur = -1, moved = false, mode = '', scroller = null, allBtn = null, pillName = null;
  page.currentView = function () { return cur; };
  function wrapViews() {
    var go = page.goView, back = page.resetView;
    page.goView = function (k) {
      go.call(page, k);
      if (!page.views[k]) return;
      cur = k; moved = false;
      refreshViews();
    };
    page.resetView = function () { back.call(page); cur = -1; moved = false; refreshViews(); };
    if (page.three && page.three.controls) {
      page.three.controls.addEventListener('start', function () { if (cur >= 0 && !moved) { moved = true; refreshViews(); } });
    }
  }
  function vname(k) { return page.views[k].name; }
  function buildRow(all) {
    viewsBox.className = '';
    scroller = el('div', { 'class': 'fr-vscroll' });
    page.views.forEach(function (v, k) {
      var b = button('', v.name, k < 9 ? String(k + 1) : '', function () { page.goView(k); }, scroller);
      b.innerHTML = '';
      b.appendChild(el('span', { 'class': 'fr-txt', text: v.name }));
      b.classList.add('fr-vbtn');
      b.dataset.view = String(k);
    });
    scroller.addEventListener('scroll', fades, { passive: true });
    viewsBox.appendChild(scroller);
    if (all) {
      allBtn = button('list', 'All views', '', function () { openList(true); }, viewsBox);
      allBtn.appendChild(el('span', { text: 'All views' }));
      allBtn.classList.add('fr-all');
    }
  }
  function buildPill() {
    viewsBox.className = 'fr-pill';
    var n = page.views.length;
    var prev = button('left', 'Previous view', '', function () { page.goView(cur < 0 ? n - 1 : (cur - 1 + n) % n); }, viewsBox);
    prev.classList.add('fr-step');
    pillName = button('', 'All saved views', '', function () { openList(true); }, viewsBox);
    pillName.classList.add('fr-vname');
    pillName.setAttribute('aria-haspopup', 'dialog');
    var next = button('right', 'Next view', '', function () { page.goView(cur < 0 ? 0 : (cur + 1) % n); }, viewsBox);
    next.classList.add('fr-step');
  }
  function buildViews() {
    viewsBox.innerHTML = '';
    scroller = allBtn = pillName = null;
    var n = page.views.length;
    if (!n) { viewsBox.style.display = 'none'; mode = 'none'; page.viewMode = mode; return; }
    viewsBox.style.display = 'flex';
    mode = 'row';
    if (narrow && n > 1) {
      buildRow(false);                      // 2–3 short names may still fit as buttons
      if (n > 3 || scroller.scrollWidth > scroller.clientWidth + 1 ||
          [].some.call(scroller.children, function (b) { var t = b.firstChild; return t.scrollWidth > t.clientWidth + 1; })) {
        viewsBox.innerHTML = '';
        scroller = null;
        buildPill();
        mode = 'pill';
      }
    } else buildRow(n > 1);
    page.viewMode = mode;
    refreshViews();
  }
  function fades() {
    if (!scroller) return;
    var over = scroller.scrollWidth > scroller.clientWidth + 1;
    scroller.classList.toggle('fr-fade-l', over && scroller.scrollLeft > 2);
    scroller.classList.toggle('fr-fade-r', over && scroller.scrollLeft < scroller.scrollWidth - scroller.clientWidth - 2);
  }
  function rowOverflow() {
    if (mode !== 'row' || !scroller) return;
    if (allBtn) {
      allBtn.style.display = '';
      allBtn.style.display = scroller.scrollWidth > scroller.clientWidth + 1 ? '' : 'none';
    }
    fades();
  }
  function refreshViews() {
    if (mode === 'pill' && pillName) {
      pillName.innerHTML = '';
      var txt = cur >= 0 ? vname(cur) : 'Saved views';
      pillName.appendChild(el('span', { 'class': 'fr-txt', text: txt }));
      pillName.appendChild(el('span', { 'class': 'fr-count', text: cur >= 0 ? (cur + 1) + '/' + page.views.length
                                                                         : String(page.views.length) }));
      pillName.title = (cur >= 0 ? vname(cur) + ' – ' : '') + 'all ' + page.views.length + ' saved views';
      pillName.setAttribute('aria-label', (cur >= 0 ? 'Saved view ' + (cur + 1) + ': ' + vname(cur) + '. ' : '') +
                            'Show all ' + page.views.length + ' saved views');
      viewsBox.classList.toggle('fr-moved', moved);
    } else if (scroller) {
      [].forEach.call(scroller.children, function (b, k) {
        b.setAttribute('aria-pressed', k === cur ? 'true' : 'false');
        b.classList.toggle('fr-moved', k === cur && moved);
      });
      if (cur >= 0 && scroller.children[cur]) {
        var b = scroller.children[cur], l = b.offsetLeft - scroller.offsetLeft, r = l + b.offsetWidth;
        if (l < scroller.scrollLeft || r > scroller.scrollLeft + scroller.clientWidth) {
          scroller.scrollLeft = Math.max(0, l - (scroller.clientWidth - b.offsetWidth) / 2);
        }
        fades();
      }
    }
    if (page.listOpen) fillList();
  }

  // the list of every saved view (a sheet from the bottom on a phone)
  var vback = el('div', { id: 'fr-vback' }), vlist = el('div', { id: 'fr-vlist', role: 'dialog', 'aria-label': 'Saved views' });
  document.body.appendChild(vback);
  document.body.appendChild(vlist);
  vback.addEventListener('click', function () { openList(false); });
  function fillList() {
    vlist.innerHTML = '';
    var head = el('div', { 'class': 'fr-vhead' });
    head.appendChild(el('h2', { text: 'Saved views (' + page.views.length + ')' }));
    var x = button('close', 'Close', '', function () { openList(false); }, head);
    x.classList.add('fr-x');
    vlist.appendChild(head);
    var ol = el('ol');
    page.views.forEach(function (v, k) {
      var li = el('li'), b = button('', v.name, k < 9 ? String(k + 1) : '', function () {
        openList(false);
        page.goView(k);
      }, li);
      b.innerHTML = '';
      b.appendChild(el('span', { 'class': 'fr-n', text: String(k + 1) }));
      b.appendChild(el('span', { 'class': 'fr-name', text: v.name }));
      b.dataset.view = String(k);
      if (k === cur) b.setAttribute('aria-current', 'true');
      ol.appendChild(li);
    });
    vlist.appendChild(ol);
    return ol;
  }
  function openList(on) {
    on = !!on && page.views.length > 0;
    if (on === !!page.listOpen) return;
    page.listOpen = on;
    if (on) {
      toggleMenu(false); toggleHelp(false); toggleMore(false); openMotions(false);
      var ol = fillList();
      vback.style.display = 'block';
      vlist.style.display = 'flex';
      var c = ol.querySelector('[aria-current]');
      if (c) ol.scrollTop = Math.max(0, c.parentNode.offsetTop - ol.clientHeight / 2 + c.offsetHeight / 2);
      (c || ol.querySelector('button') || vlist).focus({ preventScroll: true });
      opened();
    } else {
      vback.style.display = 'none';
      vlist.style.display = 'none';
      closed();
    }
  }
  page.openViews = openList;

  // ---------------------------------------------------------------- task 0310: lead motions as sliders
  // One Motions button above the saved views; its panel has a row per lead motion: the name (and "moved by …" when
  // another lead motion set one of its joints since, as in the app), the slider between its two end labels (the
  // joint's own values for a lead motion of one joint, else 0 % / 100 %), ▶ (plays it over its seconds; at 100 % back
  // to 0 %; pressed while playing: stops). Back to start puts every slider at 0 %. Moving one pauses the animation.
  var mBtn = null, mpanel = el('div', { id: 'fr-mpanel', role: 'dialog', 'aria-label': 'Motions' }), mRows = [];
  document.body.appendChild(mpanel);
  function buildMotions() {
    var ms = page.motions || [];
    if (!ms.length) return;
    motionsBox.style.display = 'flex';
    mBtn = button('sliders', 'Motions: one slider per function', '', function () { openMotions(!page.motionsOpen); }, motionsBox);
    mBtn.classList.add('fr-mbtn');
    mBtn.appendChild(el('span', { 'class': 'fr-txt', text: 'Motions' }));
    mBtn.appendChild(el('span', { 'class': 'fr-count', text: String(ms.length) }));
    mBtn.setAttribute('aria-expanded', 'false');
    var head = el('div', { 'class': 'fr-vhead' });
    head.appendChild(el('h2', { text: 'Motions (' + ms.length + ')' }));
    var x = button('close', 'Close', '', function () { openMotions(false); }, head);
    x.classList.add('fr-x');
    mpanel.appendChild(head);
    var list = el('div', { 'class': 'fr-mlist' });
    ms.forEach(function (m, k) {
      var row = el('div', { 'class': 'fr-mrow' }), top = el('div', { 'class': 'fr-mtop' });
      top.appendChild(el('span', { 'class': 'fr-mname', text: m.name, title: m.about || m.name }));
      var by = el('span', { 'class': 'fr-mby' });
      top.appendChild(by);
      row.appendChild(top);
      if (m.about) row.appendChild(el('div', { 'class': 'fr-mabout', text: m.about, title: m.about }));
      var line = el('div', { 'class': 'fr-mline' });
      var pb = button('play', 'Play ' + m.name, '', function () { page.playMotion(k); }, line);
      line.appendChild(el('span', { 'class': 'fr-mend', text: m.ends[0] }));
      var sl = el('input', { type: 'range', min: '0', max: '100', step: '0.1', 'aria-label': m.name + ': slider, 0 to 100 %' });
      sl.value = String(m.pos);
      var drag = false;
      sl.addEventListener('pointerdown', function () { drag = true; });
      sl.addEventListener('input', function () { page.setMotion(k, +sl.value); });
      sl.addEventListener('change', function () { drag = false; page.setMotion(k, +sl.value); });
      line.appendChild(sl);
      line.appendChild(el('span', { 'class': 'fr-mend', text: m.ends[1] }));
      row.appendChild(line);
      list.appendChild(row);
      mRows.push({ play: pb, slider: sl, by: by, dragging: function () { return drag; } });
    });
    mpanel.appendChild(list);
    var foot = el('div', { 'class': 'fr-mfoot' });
    button('', 'Back to start', '', function () { page.motionsBack(); }, foot).title = 'Every slider to 0 %';
    mpanel.appendChild(foot);
    refreshMotions();
  }
  function refreshMotions() {
    var st = page.leadState && page.leadState();
    if (!st || !mRows.length) return;
    st.motions.forEach(function (m, k) {
      var r = mRows[k];
      if (!r) return;
      if (!r.dragging()) r.slider.value = String(m.pos);
      var on = st.playing === k;
      r.play.innerHTML = svg(on ? 'pause' : 'play');
      r.play.setAttribute('aria-pressed', on ? 'true' : 'false');
      r.play.setAttribute('aria-label', (on ? 'Stop ' : m.pos >= 99.95 ? 'Play back ' : 'Play ') + m.name);
      r.by.textContent = m.movedBy ? 'moved by ' + m.movedBy : '';
    });
  }
  function openMotions(on) {
    on = !!on && !!mBtn;
    if (on === !!page.motionsOpen) return;
    page.motionsOpen = on;
    if (on) { toggleMenu(false); toggleHelp(false); toggleMore(false); openList(false); }
    mpanel.style.display = on ? 'flex' : 'none';
    if (mBtn) mBtn.setAttribute('aria-expanded', on ? 'true' : 'false');
    if (on) { refreshMotions(); opened(); } else closed();
  }
  page.openMotions = openMotions;

  // ---------------------------------------------------------------- layout: header, columns, stack, free area
  var headerEl = document.querySelector('header');
  function stackTop() {
    var top = window.innerHeight;
    [].forEach.call(bottom.children, function (c) { if (visible(c)) top = Math.min(top, c.getBoundingClientRect().top); });
    return top;
  }
  var laying = false;
  function layout() {
    if (laying) return;
    laying = true;
    try {
      var wasNarrow = narrow;
      measureMode();
      if (built && wasNarrow !== narrow) buildViews();
      if (built) refreshPlay();
      var H = window.innerHeight;
      var head = page.clean || !headerEl ? 0 : headerEl.getBoundingClientRect().bottom;
      root.style.setProperty('--fr-head', Math.round(Math.max(head, 0) + 6) + 'px');
      // the part tools' column (fr_tools.js) is never folded: when it reaches the stack, the stack moves beside it
      root.classList.remove('fr-beside');
      rowOverflow();
      var parts = document.getElementById('fr-parts'), top = stackTop();
      if (visible(parts) && parts.getBoundingClientRect().bottom > top - 6) {
        root.classList.add('fr-beside');
        rowOverflow();
        top = stackTop();
      }
      root.style.setProperty('--fr-stack', Math.round(H - top) + 'px');
      fitTools(top);
      if (page.moreOpen) toggleMore(true);
      if (page.ready && page.setFree) {
        var f = page.clean ? { top: 0, bottom: 0 } : { top: head, bottom: H - top + 4 };
        if (page.setFree(f) && page.refit) page.refit();
      }
    } finally { laying = false; }
  }
  page.layout = layout;
  var layoutFrame = 0;
  window.addEventListener('resize', function () {
    if (root.classList.contains('fr-warned')) place();
    cancelAnimationFrame(layoutFrame);
    layoutFrame = requestAnimationFrame(layout);
  });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { layout(); });

  // tests: every visible control, any two that overlap, any outside the screen's safe area
  page.layoutCheck = function () {
    var probe = el('div');
    probe.style.cssText = 'position:fixed;visibility:hidden;padding:var(--sa-t) var(--sa-r) var(--sa-b) var(--sa-l)';
    document.body.appendChild(probe);
    var cs = getComputedStyle(probe);
    var sa = { t: parseFloat(cs.paddingTop) || 0, r: parseFloat(cs.paddingRight) || 0,
               b: parseFloat(cs.paddingBottom) || 0, l: parseFloat(cs.paddingLeft) || 0 };
    probe.remove();
    var items = [];
    function add(name, e) {
      if (visible(e)) items.push({ name: name, r: e.getBoundingClientRect() });
    }
    add('title', document.querySelector('header h1'));
    add('header hint', document.querySelector('header .hint'));
    [].forEach.call(document.querySelectorAll('#fr-tools > .fr-btn'), function (b) { add('tools: ' + b.getAttribute('aria-label'), b); });
    [].forEach.call(document.querySelectorAll('#fr-parts > .fr-btn'), function (b) { add('parts: ' + b.getAttribute('aria-label'), b); });
    if (mode === 'pill') [].forEach.call(viewsBox.children, function (b) { add('views: ' + b.getAttribute('aria-label'), b); });
    else if (scroller) { add('views row', scroller); add('views: All views', allBtn); }
    add('motions', mBtn);                                            // task 0310
    if (!narrow) add('motions panel', page.motionsOpen ? mpanel : null);
    add('play bar', play.style.display === 'none' ? null : play);
    if (filmBtn) items.push({ name: 'play: Film', r: filmBtn.getBoundingClientRect(), inner: true });
    add('note', noteLine);
    add('message', toastEl);
    add('hint', hint);
    add('show controls', show);
    add('site', document.getElementById('fr-site'));
    add('part tool panel', document.getElementById('fr-tpanel'));   // task 0189: the part tools' panel (fr_tools.js)
    var W = window.innerWidth, H = window.innerHeight, overlaps = [], outside = [];
    // task 0252: content wider than the screen widens the page itself (a phone then scrolls sideways or zooms out)
    if (document.documentElement.scrollWidth > W + 0.5 || play.scrollWidth > play.clientWidth + 0.5) {
      outside.push('page wider than the screen');
    }
    items.forEach(function (a, i) {
      var r = a.r;
      if (r.left < sa.l - 0.5 || r.top < sa.t - 0.5 || r.right > W - sa.r + 0.5 || r.bottom > H - sa.b + 0.5) outside.push(a.name);
      for (var j = i + 1; j < items.length; j++) {
        var s = items[j].r;
        if ((a.inner && items[j].name === 'play bar') || (items[j].inner && a.name === 'play bar')) continue;
        if (Math.min(r.right, s.right) - Math.max(r.left, s.left) > 0.5 && Math.min(r.bottom, s.bottom) - Math.max(r.top, s.top) > 0.5) {
          overlaps.push([a.name, items[j].name]);
        }
      }
    });
    var small = items.filter(function (a) { return /^(tools|parts|views|play):|^motions$/.test(a.name) && (a.r.width < 39.5 || a.r.height < 39.5); })
      .map(function (a) { return a.name; });
    return { size: [W, H], safe: sa, items: items.map(function (a) { return a.name; }), overlaps: overlaps,
             outside: outside, small: small, mode: mode, tools: page.toolsShown, free: page.freeArea ? page.freeArea() : null };
  };

  // ---------------------------------------------------------------- task 0252: what the Film shows over the model
  // The video's captions, part labels and title / end card (the export's tick boxes): only while the Film is on.
  // Placed in the render's frame (page.filmFrame), sized as the video sizes them for its picture height.
  var F = page.film && page.film.src, header0 = document.querySelector('header');
  var capEl = null, cardEl = null, lblCanvas = null, lblCtx = null;
  function before(e) { document.body.insertBefore(e, header0 || document.body.firstChild); }
  if (F && F.captions) { capEl = el('div', { id: 'fr-film-cap', 'aria-live': 'polite' }); before(capEl); }
  if (F && F.cards) { cardEl = el('div', { id: 'fr-film-card' }); before(cardEl); }
  if (F && F.labels && F.labels.items && F.labels.items.length) {
    lblCanvas = el('canvas', { id: 'fr-film-labels' });
    before(lblCanvas);
    lblCtx = lblCanvas.getContext('2d');
    page.afterDraw.push(drawLabels);
  }
  function fade(t, a, b, s) {               // 0 … 1: in over s from a, out over s to b (the video's fades)
    if (t < a || t > b) return 0;
    s = Math.max(0, Math.min(s, (b - a) / 2));
    return s <= 1e-9 ? 1 : Math.max(0, Math.min(1, (t - a) / s, (b - t) / s));
  }
  function filmT() { var st = page.filmState(); return st ? st.time : 0; }
  var shownCard = '';
  function filmOverlays() {
    var on = page.film && page.filmOn(), card = on && page.filmCard ? page.filmCard() : null;
    if (cardEl) {
      var kind = card ? card.kind : '';
      if (kind !== shownCard) { fillCard(kind); shownCard = kind; }
      if (card) {
        var t = card.all - card.left;
        cardEl.style.display = 'block';
        // the title card fades into the film at its end, the end card in from the film at its start (0.4 s)
        cardEl.style.opacity = String(Math.max(0, Math.min(1, (kind === 'title' ? card.left : t) / 0.4)));
      } else cardEl.style.display = 'none';
    }
    if (capEl) {
      var tt = filmT(), cur = null, al = 0;
      if (on && !card) {
        for (var i = 0; i < F.captions.length; i++) {
          var c = F.captions[i], x = fade(tt, c.a, c.b, 0.3);
          if (x > 0) { cur = c; al = x; break; }
        }
      }
      if (cur) {
        var fr = page.filmFrame();
        if (capEl.textContent !== cur.text) capEl.textContent = cur.text;
        capEl.style.display = 'block';
        capEl.style.left = (fr.left + fr.width / 2) + 'px';
        capEl.style.bottom = (window.innerHeight - fr.top - fr.height + 0.09 * fr.height) + 'px';
        capEl.style.fontSize = Math.max(10, 0.05 * fr.height) + 'px';
        capEl.style.maxWidth = (0.9 * fr.width) + 'px';
        capEl.style.opacity = String(al);
      } else capEl.style.display = 'none';
    }
    if (lblCanvas && !(on && !card)) clearLabels();
  }
  function fillCard(kind) {
    cardEl.innerHTML = '';
    if (!kind) return;
    var C = F.cards, fr = page.filmFrame ? page.filmFrame() : { height: window.innerHeight };
    var H = window.innerHeight, W = window.innerWidth;
    cardEl.style.background = C.bg || '#1A2027';
    cardEl.style.color = C.fg || '#FFFFFF';
    var line = function (text, size, y) {   // y: 0 … 1 from the bottom of the screen, size: of the screen's height
      if (!text) return;
      var d = el('div', { text: text });
      d.style.bottom = (y * 100) + '%';
      d.style.fontSize = Math.max(11, size * Math.min(H, fr.height || H)) + 'px';
      cardEl.appendChild(d);
    };
    if (kind === 'title') {
      line(C.title.title, 0.09, 0.56);
      line(C.title.sub, 0.045, 0.40);
    } else if (kind === 'end') {
      var logo = C.end.logo;
      if (logo) {
        var img = el('img', { src: logo, alt: '' });
        img.style.left = (W * 0.325) + 'px'; img.style.width = (W * 0.35) + 'px';
        img.style.bottom = '50%'; img.style.height = '35%';
        cardEl.appendChild(img);
      }
      line(C.end.text, 0.04, logo ? 0.34 : 0.5);
    }
  }
  page.filmOverlays = function () {         // tests: what the Film shows over the model now
    var lab = page.filmLabels || [];
    return { caption: capEl && capEl.style.display !== 'none' ? capEl.textContent : '',
             card: cardEl && cardEl.style.display !== 'none' ? shownCard : '',
             cardText: cardEl && cardEl.style.display !== 'none' ? cardEl.textContent : '',
             labels: lab };
  };

  // labels: the video's rule (core/callouts.place_labels) in the render's frame, y from the bottom
  function clearLabels() {
    if (lblCtx && lblCanvas.dataset.drawn === '1') {
      lblCtx.clearRect(0, 0, lblCanvas.width, lblCanvas.height);
      lblCanvas.dataset.drawn = '0';
    }
    page.filmLabels = [];
  }
  function placeLabels(anchors, sizes, W, H, outline) {
    var short = Math.min(W, H), gap = 0.012 * short, margin = 0.02 * short, taken = [], out = [];
    var o = outline || [W * 0.25, H * 0.2, W * 0.75, H * 0.8];
    var area = function (a, b) {
      var dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      return Math.max(0, dx) * Math.max(0, dy);
    };
    var ob = { x: o[0], y: o[1], w: o[2] - o[0], h: o[3] - o[1] };
    for (var n = 0; n < anchors.length; n++) {
      var ax = anchors[n][0], ay = anchors[n][1], w = sizes[n][0], h = sizes[n][1], best = null;
      var sx = { L: o[0] - gap - w, R: o[2] + gap }, sy = { T: o[3] + gap, B: o[1] - gap - h }, slide = h + gap;
      ['L', 'R', 'T', 'B'].forEach(function (side) {
        for (var k = 0; k < 12; k++) {
          (k === 0 ? [1] : [1, -1]).forEach(function (sign) {
            var off = sign * k * slide, x, y;
            if (side in sx) { x = sx[side]; y = ay - h / 2 + off; } else { x = ax - w / 2 + off; y = sy[side]; }
            x = Math.min(Math.max(x, margin), Math.max(margin, W - margin - w));
            y = Math.min(Math.max(y, margin), Math.max(margin, H - margin - h));
            var b = { x: x, y: y, w: w, h: h }, ov = 0;
            taken.forEach(function (t) { ov += area(b, t); });
            var m2 = margin / 2, inside = b.x >= m2 - 1e-6 && b.y >= m2 - 1e-6 && b.x + w <= W - m2 + 1e-6 && b.y + h <= H - m2 + 1e-6;
            var dx = Math.max(b.x - ax, 0, ax - (b.x + w)), dy = Math.max(b.y - ay, 0, ay - (b.y + h));
            var score = Math.hypot(dx, dy) + (area(b, ob) > 0 ? 0.35 * short : 0) + (inside ? 0 : 1e9) + (ov > 0 ? 1e7 : 0);
            var c = [ov > 0 ? 1 : 0, ov, score];
            if (!best || c[0] < best.c[0] || (c[0] === best.c[0] && (c[1] < best.c[1] || (c[1] === best.c[1] && c[2] < best.c[2])))) best = { c: c, b: b };
          });
        }
      });
      taken.push(best.b);
      out.push(best.b);
    }
    return out;
  }
  var v3 = null, corners = null;
  function drawLabels() {
    var three = page.three, T = three && three.T;
    if (!T || !page.filmOn() || page.filmCard()) { clearLabels(); return; }
    var dpr = window.devicePixelRatio || 1, cw = window.innerWidth, ch = window.innerHeight;
    if (lblCanvas.width !== Math.round(cw * dpr) || lblCanvas.height !== Math.round(ch * dpr)) {
      lblCanvas.width = Math.round(cw * dpr); lblCanvas.height = Math.round(ch * dpr);
    }
    var ctx = lblCtx, cam = three.camera, L = F.labels, fr = page.filmFrame(), t = filmT();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cw, ch);
    lblCanvas.dataset.drawn = '1';
    v3 = v3 || new T.Vector3();
    var W = fr.width, H = fr.height;
    var toFrame = function (v) {            // a three world point -> the frame's pixels (y from the bottom) or null
      v3.copy(v).applyMatrix4(cam.matrixWorldInverse);
      if (v3.z > -1e-6) return null;        // behind the camera
      v3.applyMatrix4(cam.projectionMatrix);
      var sx = (v3.x + 1) / 2 * cw, sy = (1 - v3.y) / 2 * ch;
      return [sx - fr.left, fr.top + fr.height - sy];
    };
    if (!corners) {                         // the model's box (Blender world) in three's world
      var mn = page.settings.model.min, mx = page.settings.model.max;
      corners = [];
      for (var c = 0; c < 8; c++) {
        var x = c & 1 ? mx[0] : mn[0], y = c & 2 ? mx[1] : mn[1], z = c & 4 ? mx[2] : mn[2];
        corners.push(new T.Vector3(x, z, -y));
      }
    }
    var ox0 = 1e9, oy0 = 1e9, ox1 = -1e9, oy1 = -1e9, any = false;
    corners.forEach(function (p) {
      var q = toFrame(p);
      if (q) { any = true; ox0 = Math.min(ox0, q[0]); ox1 = Math.max(ox1, q[0]); oy0 = Math.min(oy0, q[1]); oy1 = Math.max(oy1, q[1]); }
    });
    var px = Math.max(8, Math.round(H * (L.size || 0.036))), todo = [];
    var font = px + 'px ' + FONT;
    ctx.font = font;
    var wp = new T.Vector3(), s3 = new T.Vector3();
    L.items.forEach(function (it) {
      var ob = page.nodes && page.nodes[it.node];
      if (!ob) return;
      ob.updateWorldMatrix(true, false);
      s3.setFromMatrixScale(ob.matrixWorld);
      if (Math.min(s3.x, s3.y, s3.z) < 1e-6) return;          // hidden by the motion (scale 0)
      var vis = true;
      for (var o = ob; o; o = o.parent) if (o.visible === false) { vis = false; break; }
      if (!vis) return;
      var al = it.w ? fade(t, it.w[0], it.w[1], 0.3) : 1;
      if (al <= 0.001) return;
      wp.set(it.at[0], it.at[1], it.at[2]).applyMatrix4(ob.matrixWorld);
      var a = toFrame(wp);
      if (!a || a[0] < 0 || a[0] > W || a[1] < 0 || a[1] > H) return;     // out of the picture, as in the video
      var text = it.text;
      if (text == null && it.texts) {
        text = it.texts[0][1];
        for (var k = 0; k < it.texts.length && it.texts[k][0] <= t + 1e-6; k++) text = it.texts[k][1];
      }
      var rows = String(text || '').split('\n'), tw = 0;
      rows.forEach(function (r) { tw = Math.max(tw, ctx.measureText(r || ' ').width); });
      var th = rows.length > 1 ? px * (1 + 1.25 * (rows.length - 1)) : px, pad = 0.45 * px;
      todo.push({ text: text, rows: rows, a: a, al: al, size: [tw + 2 * pad, th + 2 * pad * 0.8] });
    });
    var boxes = placeLabels(todo.map(function (d) { return d.a; }), todo.map(function (d) { return d.size; }), W, H,
                            any ? [ox0, oy0, ox1, oy1] : null);
    var X = function (x) { return fr.left + x; }, Y = function (y) { return fr.top + H - y; };
    var lw = Math.max(1.5, H * 0.0028);
    page.filmLabels = [];
    [true, false].forEach(function (edge) {                 // the dark edge first, then the line and its dot
      todo.forEach(function (d, i) {
        var b = boxes[i];
        ctx.globalAlpha = d.al;
        ctx.strokeStyle = ctx.fillStyle = edge ? (L.box || '#1A2027') : (L.fg || '#FFFFFF');
        ctx.lineWidth = edge ? lw * 2.2 : lw;
        ctx.beginPath(); ctx.moveTo(X(d.a[0]), Y(d.a[1])); ctx.lineTo(X(b.x + b.w / 2), Y(b.y + b.h / 2)); ctx.stroke();
        ctx.beginPath(); ctx.arc(X(d.a[0]), Y(d.a[1]), edge ? lw * 2.6 : lw * 1.7, 0, 2 * Math.PI); ctx.fill();
      });
    });
    todo.forEach(function (d, i) {
      var b = boxes[i];
      ctx.globalAlpha = d.al * 0.88;
      ctx.fillStyle = L.box || '#1A2027';
      ctx.fillRect(X(b.x), Y(b.y + b.h), b.w, b.h);
      ctx.globalAlpha = d.al;
      ctx.fillStyle = L.fg || '#FFFFFF';
      ctx.textBaseline = 'middle';
      var multi = d.rows.length > 1;
      ctx.textAlign = multi ? 'left' : 'center';
      d.rows.forEach(function (r, k) {
        var y = b.y + b.h / 2 + (multi ? ((d.rows.length - 1) / 2 - k) * 1.25 * px : 0);
        ctx.fillText(r, multi ? X(b.x + 0.45 * px) : X(b.x + b.w / 2), Y(y));
      });
      page.filmLabels.push({ text: d.text, anchor: [X(d.a[0]), Y(d.a[1])], box: [X(b.x), Y(b.y + b.h), b.w, b.h],
                             alpha: d.al });
    });
    ctx.globalAlpha = 1;
  }

  // ---------------------------------------------------------------- keys
  window.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target && e.target.tagName) || '';
    if (tag === 'TEXTAREA' || (tag === 'INPUT' && e.target.type !== 'range' && e.target.type !== 'checkbox')) return;
    var k = e.key, done = true;
    if (page.listOpen && k !== 'Escape' && k !== 'Tab' && !/^[1-9]$/.test(k) && k !== 'Enter' && k !== ' ') return;
    if (k === ' ' || k === 'Spacebar') {
      if (tag === 'BUTTON') return;          // Space on a focused button presses it
      if (page.animated) page.paused = !page.paused; else done = false;
    }
    else if (k === 'f' || k === 'F') fullscreen();
    else if (k === 'r' || k === 'R') page.resetView();
    else if (k === 's' || k === 'S') screenshot();
    else if (k === 'l' || k === 'L') copyLink();
    else if (k === 'h' || k === 'H') clean(!page.clean);
    else if (k === 'm' || k === 'M') toggleMenu();
    else if (k === '?') toggleHelp();
    else if (k === 'Escape') { toggleMenu(false); toggleHelp(false); toggleMore(false); openList(false); openMotions(false); }
    else if ((k === 'ArrowLeft' || k === 'ArrowRight') && page.animated && tag !== 'INPUT') {
      page.setTime(Math.max(0, page.time + (k === 'ArrowLeft' ? -2 : 2)));
    } else if (/^[1-9]$/.test(k) && +k <= page.views.length) { openList(false); page.goView(+k - 1); }
    else done = false;
    if (done) { e.preventDefault(); page.input(); page.lastKey = k; }
  });
  // a tap outside the More menu closes it
  document.addEventListener('pointerdown', function (e) {
    if (page.moreOpen && !more.contains(e.target) && !moreBtn.contains(e.target)) toggleMore(false);
  }, true);

  // ---------------------------------------------------------------- follow the page
  page.listeners.push(function (what) {
    if (what === 'time' || what === 'paused' || what === 'speed' || what === 'film') refreshPlay();
    if (what === 'motions') refreshMotions();
    if (what === 'film' || what === 'card' || what === 'time') filmOverlays();
    else if (what === 'ready') { buildBottom(); showWarn(); layout(); showHint(); }
    else if (what === 'warned') showWarn();
    if (what !== 'time' || page.frames % 20 === 0) refreshMenu();
  });
  layout();
  if (page.ready) { buildBottom(); showWarn(); layout(); showHint(); }

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
      var turn0 = page.turn;                           // task 0256: a flick spins it, a slow drag does not, a press stops it
      page.setTurn(false);
      var fast = page.flickFrom([{ t: 0, dx: 0 }, { t: 30, dx: 25 }, { t: 60, dx: 25 }], 10);
      var spun = page.turning && page.spinning() && page.spinning().speed > 0;
      page.input();
      var stopped = !page.turning && !page.spinning();
      var slow = page.flickFrom([{ t: 0, dx: 0 }, { t: 50, dx: 1 }, { t: 100, dx: 1 }], 10);
      r.flick = !!(fast && spun && stopped && !slow && !page.turning);
      page.setTurn(turn0);
      var lc = page.layoutCheck();                     // task 0179: no two controls on top of each other
      r.overlaps = lc.overlaps.length;
      r.ok = r.menu && r.help && r.link && r.space !== false && r.overlaps === 0 && r.flick;
      root.dataset.frSelftest = JSON.stringify(r);
    };
    // at once when the page is ready (a browser without a window may stop soon after: no timer to wait for)
    if (page.ready) test();
    else page.listeners.push(function (what) { if (what === 'ready' && !root.dataset.frSelftest) test(); });
  }
})();
