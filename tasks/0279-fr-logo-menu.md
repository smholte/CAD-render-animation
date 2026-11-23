# 0279 – The Fr mark replaces Blender's logo at the left of the top bar, with its own menu

**Who:** worker · **Status:** done (0.2.209) ·
**Branch:** `task/0279-fr-logo-menu`
**Started by:** lead, 21 Nov 2026 (owner 20:49, screenshot of the main window: "under the Fr logo there is a blender
logo" – the window's title bar shows the Fr app icon, the top bar's first item is still Blender's logo menu; owner's
pick: **Fr logo, own menu**, Blender's items under a "Blender" submenu) · **Model:** Opus · effort Low
**Area:**
- `blender/ui_topbar.py` – the top bar's left part;
- `blender/lock.py` – only where it draws `TOPBAR_MT_editor_menus.draw_collapsible` (~line 554), if needed;
- one small Fr mark picture inside the extension (from `site/brand/fresing-render/` – the reversed / light one that
  reads on the dark top bar), loaded with `bpy.utils.previews`;
- tests, guide, PC check, tour stop, function list.
May run beside 0278 (no shared files). Two fix tasks never share a file: if 0278 is running, don't touch its files.

## What the owner sees today

The window's title bar shows the Fr app icon. Right under it, at the left of the top bar, stands Blender's logo; it
opens Blender's own menu (Splash screen, About Blender, Install application template…, Support). For a non-Blender
user this reads as "this is Blender", not as Fresing Render.

## What to do

1. **The Fr mark in place of Blender's logo**, in every workspace: Full access (Blender's own top bar drawing), every
   other workspace and the Client view (lock.py's drawing). Same size and place as Blender's logo; it reads on the dark
   top bar at UI scale 1 and 2. Tooltip "Fresing Render".
2. **Its menu** (click on the Fr mark):
   - **About Fresing Render…** (the About window / Settings > About, whichever 0271 left as the way in);
   - **Fresing Settings…**;
   - a line, then a **Blender** submenu holding Blender's own logo menu unchanged (Splash screen, About Blender,
     Install application template…, Support …) – reuse Blender's `TOPBAR_MT_blender` as the submenu, don't copy its
     items, so a Blender update keeps them right. Blender's icon may stand beside "Blender" in the submenu line.
   The **Fresing** menu after Help stays as it is.
3. **Clean undo:** turning the extension off gives Blender its own logo menu back (unregister restores the original
   drawing). Nothing else in the top bar moves (File, Edit, Render, Window, Help, Fresing; workspace tabs in Full
   access).
4. If Blender does not let an add-on replace the logo cleanly in one of the drawings, stop at what works, say in the
   report which drawing keeps Blender's logo and why, and suggest the way out – don't patch Blender's own files.

## Checks (tick in the report)

- [x] Real-app test (xvfb): the top bar's first item is the Fr mark in Full access, another workspace and the Client
      view; its menu opens with About Fresing Render…, Fresing Settings…, Blender ▸; the Blender submenu shows
      Blender's own items; the extension turned off → Blender's logo is back.
- [x] Every new menu line has a tooltip; the guide's top-bar picture and text, PC-check line, tour stop and function
      list entry (`since=`) updated.
- [ ] Owner's check on his PC (below).

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 22–23 Nov 2026 – 0.2.209

**What changed:** `ui_topbar.py` swaps only Blender's own entry in `TOPBAR_MT_editor_menus`' draw list for one that runs
Blender's draw through a layout whose `TOPBAR_MT_blender` line becomes the Fr mark's menu (`TOPBAR_MT_fresing_mark`,
icon from `brand/fresing-render-mark_reversed_128px.png`, made from the site's reversed mark). File … Help and the
Fresing menu stay Blender's / as they were; both drawings (Full access and lock.py's) go through it, lock.py untouched.
Menu: About Fresing Render…, Fresing Settings…, line, Blender ▸ (Blender's `TOPBAR_MT_blender` itself). Unregister puts
Blender's draw back and redraws the top bar. Guide section "The Fr mark in the top bar" (`fr-mark`), function
`help.fr_mark`, PC-check line `app.fr_mark`, tour stop `fr_mark` (crane set), CHANGELOG. `tools/ci_groups.py`:
`test_web3d_film_blender.py` joins `SKIPS_ON_GITHUB` (the first run put it in one group with `test_web3d_keys.py`: 2 skips).

**Tested and measured:** `tests/test_fr_mark.py` (5); `ui_test_quiet.py` 90/90 on the web machine: the mark drawn with its
picture and its green seen in screenshots (19 px) in the quiet window, Full access and the Client view; its menu drawn;
turned off → Blender's logo (0 green px), on again → the mark. PC-check line OK (bpy module). No new guide picture.

**Runs on GitHub:** 5 – two red (two by-design skips in one pytest group; the first PC-check half past 15 min twice, queue.video moved to the second half), the rest version clashes (0.2.206–0.2.208 taken meanwhile).
the group fix.

**Open points / follow-up tasks:** a screenshot of the open menu was not caught by the test (its drawing was).

**Owner's check on your PC:** after the update: 1. Start Fresing Render. 2. Far left of the top bar: the green-white
"Fr", no Blender logo. 3. Click it: About Fresing Render…, Fresing Settings…, Blender. 4. Point at Blender: Blender's
own menu. 5. Workspace Full access, then Client view: the Fr mark stays.
