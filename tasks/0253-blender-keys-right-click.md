# 0253 – Blender's harmful keys swallowed, F12 / Ctrl+F12 render with the app, a short Fresing right-click menu (0222 package B)

**Who:** worker · **Status:** open – waits for 0260 (same lane, owner 21 Nov 14:44) · **Branch:** `task/0253-keys-right-click`
**Started by:** lead, 21 Nov 2026 (study 0222 package B; the owner's answers 20 Nov 16:22) · **Model:** Opus · effort Medium
**Area:** Start & learn lane –
- `blender/lock.py`: the key list and its keymap code (`_KEYS`, `_add_keys`, `_remove_keys`, `blender_ui`) – the Client
  view's own lock must keep working exactly as today (0213, 0227);
- a **new** `blender/context_menu.py` (the right-click menu), registered where 0241 registers `quiet.py`;
- `blender/quiet.py` only if its `swap` helper is reused for the right-click menu (do not change what it already swaps);
- the tour stop (below) in `blender/tour.py` – **only** a new stop in the crane hub set (`HUB_SET`, next to
  `start_here`), no other set;
- `core/functions.py` (new entries, `since=`), the PC-check line, `docs/USER-GUIDE.md` (+ picture via
  `tools/guide_screens.py`), real-app test, tests, CHANGELOG, CLAUDE.md section 3's `lock.py` / new file lines.

**Not:** the top-bar menus and Blender's side-panel tabs (package C, next in this lane), `welcome.py`, `ui_topbar.py`,
the test models, any other tour set (0233, 0234, 0249 and 0252 are running in their own sets / lanes).

## Goal

A user who does not know Blender cannot lose or break parts by pressing a Blender key by accident. Outside **Full
access** (and outside **Fresing > Show all of Blender**, which switches to Full access), Blender's harmful keys do
nothing but show one line saying how to get them; F12 and Ctrl+F12 make the app's own render image and render
animation; a right-click on the model opens a short Fresing menu instead of Blender's editing menu.

## Background

- Study 0222 (`tasks/0222-study-blender-parts-new-users.md`, rows "Keys a new user hits by accident" and "Right-click
  menu in the view") lists the keys and the menu. Package A (0241, 0.2.184, `quiet.py`) made the quiet window;
  `lock.blender_ui(on)` switches it with Full access.
- **Owner's answers (20 Nov 16:22):** F12 / Ctrl+F12 = the app's Render image / Render animation; right-click on a
  part = a short Fresing menu (zoom to it, show in the tree, hide / show only this, label here, add joint here);
  **H stays** (Blender's hide is kept for those who know it); the way back is Full access **and** the Fresing-menu
  entry (0241's `fresing.blender_all`).
- The Client view already swallows X / Delete / Tab / Ctrl+Shift+S with `lock._KEYS` (a key whose operator's `poll` is
  False passes on to Blender's own key – CLAUDE.md section 8). 0227 fixed X / Delete getting through on Windows (the
  owner still has to confirm it on his PC). Whatever 0227 learned applies here: read its report first.
- The owner's aim: the app as simple as possible for non-Blender users, Blender's tools easy to open for those who know
  them.

## What to build

**A. Keys outside Full access** (every workspace but Full access; the Client view keeps its own, stricter message):
- **Swallow** with one status-bar / report line *"That is a Blender key – Fresing > Show all of Blender gives you
  Blender's keys"*: X, Delete, Shift+X, Shift+Delete (delete); Tab, Ctrl+Tab (modes); Shift+D, Alt+D (duplicate);
  Ctrl+J (join); Ctrl+P, Alt+P (parent); Ctrl+A (apply); M, Shift+M (collections); Shift+A (add); Ctrl+H (hide
  collections); Ctrl+0 … Ctrl+5 (subdivision); Ctrl+Page Up / Down (workspace – no tab to come back while the tabs are
  hidden); I, Alt+I, K (keyframes over the app's built keys).
- **F12** = the app's Render image (`fresing.render`, as the blue button), **Ctrl+F12** = the app's Render animation
  (the same call as Make's "Render animation" button, today `fresing.queue_add` in `ui_top.py`). In Full access
  Blender's own F12 / Ctrl+F12 come back.
- **Keep:** H / Alt+H / Shift+H, A, G / R / S (parts are locked in place anyway), Home, numpad views, Z, Space,
  Ctrl+Space, Ctrl+Z / Ctrl+Shift+Z, F3, N, F11, Ctrl+S / Ctrl+O.
- The swallowing operator pushes no undo step and changes nothing. Switching to Full access gives every key back at
  once, switching away takes them again (the same switch `blender_ui` already is); a project opened in Full access has
  Blender's keys.
- Say in the report what a Blender user's own key-map changes do (a key they moved elsewhere passes – fine, say so).

**B. Right-click in the 3D view** (outside Full access): Blender's object context menu is replaced by a short
**Fresing** menu. Right-click on a part makes that part the selected one (as a left click would), then shows:
- **Zoom to it** (frame the part), **Show in 2 Structure** (its row selected and scrolled into view),
- **Hide**, **Show only this** (and **Show all** when something is hidden / shown only – the app's own operators,
  `fresing.hide_selected`, `fresing.show_only_selected`, `fresing.show_only_end`),
- **Add a label here** (a label pointing at the clicked spot on that part – the Labels function's own add),
- **Add joint here…** (starts the Motion panel's Add joint with this part; if the clicked face can seed the axis pick,
  do it, else say in the report why not).
Right-click on empty space: **Zoom to all**, **Show all**. In the **Client view** only the viewing entries (zoom, show
in the tree, hide, show only, show all). Keep items other add-ons appended to the menu (swap only Blender's own draw,
as `quiet.swap` does). Full access shows Blender's menu again. Every entry has a tooltip.

## Done when

- [ ] Every swallowed key does nothing to the scene outside Full access and shows the line (test each key: object
      count, names, parents, modes and keys unchanged); in Full access each does Blender's thing again
- [ ] The Client view still refuses as before (its tests unchanged and green); H still hides
- [ ] F12 / Ctrl+F12 start the app's render image / render animation outside Full access, Blender's in Full access
- [ ] The right-click menu: each entry works on the part under the mouse (real-app test with simulated right-clicks;
      remember: the first click into a region only focuses it, and the splash swallows keys – Esc first)
- [ ] Function-list entries (`since=`), guide section + anchor ("Keys and the right-click menu"), one picture of the menu
      (test crane), PC-check line `app.keys` (keys swallowed / back in Full access, F12 bound to the app), tour stop in
      `HUB_SET` (`since=`, `changed=` on the set, `tour_versions.py --record`), CHANGELOG
- [ ] Windows: the key handling has no Windows-only code; if any appears, an independent review
- [ ] Tests added; full suite + GitHub green; report filled in

## Not in this task

Package C (shorter File / Edit / Render / Window menus, Blender's side-panel tabs Tool / View / Animation / Item / glTF
Variants) – next in this lane. The timeline header (package D, later). Other tour sets.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 21 Nov 2026.

**What changed:**
- `blender/lock.py`: a second key list `BLENDER_KEYS` (27 keys: X / Delete with any modifier, Tab, Ctrl+Tab, Shift+D,
  Alt+D, Ctrl+J, Ctrl+P, Alt+P, Ctrl+A, M, Shift+M, Shift+A, Ctrl+H, Ctrl+0 … 5, Ctrl+Page Up / Down, I, Alt+I, K in the
  3D view; I / Alt+I over a setting; X / Delete in an Outliner) → `fresing.blender_key` (changes nothing, no undo step,
  one status-bar line). `APP_KEYS`: F12 / Ctrl+F12 → `fresing.key_render` (the app's Render image / the picked
  animation's Render animation), right mouse / Menu key → `fresing.view_menu`. Every poll asks `keys_quiet()` = the
  quiet window's switch (`blender_ui`), so Full access gives every key back at once and a project opened in Full access
  has Blender's keys. In the Client view a swallowed key gives the lock's own message and counts in `SWALLOWED`; the
  lock's own `_KEYS` and `client_locked` are unchanged (one `_add_keys` puts both lists in, also from `blender_ui`).
- New `blender/context_menu.py`: the right-click picks the part under the mouse, selects it as a left click (its
  subassembly in the pick mode "Subassembly") and opens Blender's `VIEW3D_MT_object_context_menu`, whose own draw is
  swapped (`quiet.swap`) for the Fresing menu – other add-ons' items stay. Entries `fresing.ctx_*`: Zoom to it (frames
  the part's box; works where parts cannot be selected), Show in 2 Structure (row opened, picked, the section opened,
  the side panel shown on the Fresing tab), Hide, Show only this, Show all (as 2 Structure's buttons, incl. taking a
  built animation off), Add a label here (at the clicked spot, opens 6 Animation > Labels), Add joint here… (selects it
  and starts Add joint's axis pick). Empty space: Zoom to all, Show all. Client view: only the viewing entries, and
  they hide in the view only (`hide_set`, mark `fr_cv_hide`): renders, built keys and the project unchanged; leaving
  the Client view shows them again. Another mode than Object Mode or Full access: Blender's own menu. A user with
  right-click select keeps Blender's.
- **Add joint here does not seed the axis from the right-clicked face:** the right-click picks *what moves*; its pivot
  is nearly always somewhere else (a pin, a bore). Taking the clicked face as the axis would make a wrong joint
  silently; the axis pick starts with the hover highlight instead.
- Function list `help.blender_keys`, `help.right_click`; guide section "Keys and the right-click menu" (anchor
  `keys-and-right-click`) with `docs/img/view_right_click.png` (made by `tools/guide_screens.py` window mode, new step);
  PC-check line `app.keys`; tour stop `keys` in the crane set (`changed=` on the set, `tour_versions.py --record`);
  usage: the swallowed key, F12 and the menu's entries are not counted (the menu counts once when it opens).
- **A Blender user's own key map:** the swallowed keys are the physical keys above in the keymaps named. An action a
  user moved to another key is not swallowed on that key (only on the keys listed); a key a user gave another action
  in Object Mode (say X) is swallowed outside Full access too. Full access gives all of them back.

**Tested and measured** (4-core web machine, test crane):
- `tests/test_keys_right_click.py` (14 tests, bpy module): key list, polls per workspace, swallowing changes nothing
  (objects, parents, visibility, mode, actions, collections) and pushes no undo step, the Client view's message, the
  menu's entries on a part / empty space / Client view, every entry's operator, the Client view's view-only hide shown
  again when it is left, other add-ons' items kept through the swap.
- Real app `tools/ui_test_keys.py` (group pccheck-b, 30 checks, 0.7 min): the 27 keys pressed with the boom selected and
  the mouse on it – all swallowed, nothing changed; H / Alt+H still hide / show; F12 / Ctrl+F12 run the app's render;
  a simulated right-click opens the Fresing menu on the boom (selected, another add-on's item drawn), Return on its
  first entry zooms; each entry; empty space; the Client view (nothing selected, view-only hide, Shift+D swallowed by
  the lock); Full access: Blender's menu, Delete deletes, F12 is Blender's.
- The existing real-app tests of this area unchanged and green: clientkeys 12/12, quiet 78/78, lock 19/19, left 31/31.
- PC-check line `app.keys` (bpy module): OK.
- No Windows-only code: no independent review needed. Subagents: none (small task).

**Open points / follow-up tasks:**
- The owner on his PC: press Delete / Shift+D on a part outside Full access, F12, right-click a part (tour stop
  "Keys and the right-click menu").
- The menu's title row is Blender's word "Object" (a registered menu's title cannot be changed); the part's name is the
  first line under it.
- Keys in the timeline / dope sheet (X deletes keyframes there) are not swallowed: package D (the timeline header).
- No lesson step: the right-click menu and the keys are not a step of the crane or mill lesson.

**GitHub runs:** 
