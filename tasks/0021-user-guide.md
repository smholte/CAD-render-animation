# 0021 – User guide (and the tooltip standard)

**Who:** worker · **Status:** done (0.2.10) · **Branch:** `task/0021-user-guide`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Docs (only `docs/`, `tools/` screenshot helpers,
`installer/` to ship the guide, the app template for a Help-menu link) – no clash with other lanes.

## Goal

A short, clear user guide for the owner and his colleagues: what each section 1–7 is for and how
to work through it step by step, with pictures. Opened from the app (Help menu) and shipped with
the installer.

## Background

- The side panel: 1 Import, 2 Structure, 3 Looks (with Find & sort parts, sorting rules, schemes
  & templates), 4 Motion, 5 Scene & Render, 6 Animation, 7 Render queue. `CHANGELOG.md` says what
  each version added; `docs/README-install.txt` covers installing.
- 0.2.9 (task 0010) added "Paint faces" to 3 Looks and painted faces from CAD: describe them
  (see the report in `tasks/0010-face-painting.md`).
- Other chats are changing panels right now (lanes in `TASKS.md`). Write the guide for what is in
  `main`; each later task updates its own section (rule in `CLAUDE.md`).
- **Tooltips** (owner's wish: hovering over a button shows what it does and how to use it): the
  rule is in `CLAUDE.md` section 6; each lane adds them for its own panels (0010: panels 1–3,
  0012: panels 4, 6, 7, 0016: panel 5). Not in this task's files – but this task writes the
  **tooltip style guide** (examples of good tooltips) at the top of the guide's source, and at the
  end lists buttons that still have a weak or missing tooltip (a script can read every operator
  and property description) as follow-ups for the lanes.
- Public repository: screenshots and examples only with the generic test models
  (`tests/data/`), never the owner's machines.

## What to build

1. `docs/USER-GUIDE.md` (source) and a nicely laid out HTML or PDF made from it: getting started
   (install, first import, first render in 10 minutes), then one chapter per section 1–7 with
   numbered steps and screenshots (`tools/ui_screens.py` and real-app shots of the test crane),
   tips (export settings for Inventor/Fusion: AP214/AP242 – see task 0008's report), and a
   troubleshooting page (self-test, where renders go, queue).
2. Help menu entry "Fresing Render user guide" (app template or extension registration) that
   opens the shipped guide; the installer copies it next to the app.
3. Tooltip style guide + the list of weak/missing tooltips (as above).

## Done when

- [x] Guide complete for the current `main`, screenshots from test models only; opens from the
      Help menu in the real app (Linux test) and is in the installer zip
- [x] Tooltip report made; `CLAUDE.md` rule references the style guide
- [x] Report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Changing tooltips in `blender/` files (the lanes do that).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 4–5 Nov 2026 → version 0.2.10

**What changed:**
- `docs/USER-GUIDE.md`: the user guide – how the app is laid out, getting started (install, moving
  around, first render), one chapter per section 1–7 with numbered steps, tips (Inventor/Fusion
  export: AP214/AP242, from 0008's report; faster renders), troubleshooting (self-test, where
  renders go, missing tab, import and render problems). 22 pictures in `docs/img/`, all of the
  generic test crane (`tests/data/test_crane_a.step`). Every claim was checked against the code
  (cameras, cores, Esc, stay-awake, render folders, time-test folder).
- The **tooltip style guide** is the HTML comment at the top of `USER-GUIDE.md` (12 rules + good
  examples); it is not shown in the guide. `CLAUDE.md` section 6 points to it.
- `tools/build_guide.py`: Markdown → one self-contained HTML page (pictures inside, contents list,
  no internet needed, prints to PDF). 0.8 MB.
- `tools/guide_screens.py`: makes the guide's pictures in the real app (modes panels / window /
  render). Each lane re-runs it for its own panels.
- **Help > Fresing Render user guide** (first entry of the Help menu, in the app template): opens
  the guide shipped inside the installed extension (`<extension>/guide/user_guide.html`), so an
  update brings the matching guide. Missing file → message "run Install.bat again".
- Release: `tools/build_release.py` builds the guide into the extension and puts
  "User guide.html" next to Install.bat; the installer adds a Start-menu shortcut
  "Fresing Render - User guide". `README-install.txt` mentions it.
- `tools/tooltip_report.py`: reads every button and setting the side panel draws and grades its
  tooltip (missing / weak / fine, with the reason). `docs/TOOLTIPS-TODO.md`: the snapshot on `main`
  `e8365b8` – 203 buttons and settings, **83 without a tooltip, 31 weak**, 89 fine – split per lane,
  each with a suggested text checked against the code.
- `tests/test_user_guide.py` (new tests): guide builds with every chapter in order, pictures
  inside, notes kept out, no unused or oversized pictures, missing picture is an error, the
  Help-menu operator finds and opens the guide (and reports a missing one), the tooltip report reads
  the panels.
- `CLAUDE.md`: test table (guide pictures, guide page, tooltip check, Help-menu test), guide and
  tooltip rules, `markdown` in the set-up line, three lessons learned (operator tooltips via
  `get_rna_type()`, see-through side panel in screenshots, no Pillow in Blender's Python).

**Tested and measured** (name the machine and the model):
All on the 2-core Linux test machine without a graphics card, test models only:
- Full suite: 1,261 passed (9 new in `tests/test_user_guide.py`).
- Real app, Help menu (`tools/guide_test_app.py`, guide inside the installed extension): 8/8 –
  entry is the first item of Help, clicking it opens `<extension>/guide/user_guide.html`, a missing
  guide gives "run Install.bat again" and opens nothing.
- Real app, side panel clicks: `ui_test_app.py` 22/22, `ui_test_app2.py` 29/29; paths with spaces,
  accents, apostrophe and dash (`paths_test_blender.py`): 8/8.
- Packaged install (`tools/test_install_linux.py`): guide present in the installed extension
  (0.8 MB); self-test all OK except "Render HD on graphics card" (no GPU here, as before).
- Release zip: "User guide.html" next to Install.bat and `guide/user_guide.html` inside
  `fresing_render-0.2.10.zip`; extension zip 48.6 MB, of which the guide is 0.8 MB.
- Guide page looked at in a browser at desktop and phone width (no sideways scrolling, no outside
  links or fonts: works offline). All 22 pictures checked by eye: test crane only.
- Windows-only code (installer shortcut, `os.startfile` in the Help entry) reviewed by an
  independent helper: no blocking problems; its one small point (installer header comment) fixed.
  Not tested on Windows: the owner's PC confirms (open points).

**Open points / follow-up tasks:**
- The lanes write the 114 tooltips in `docs/TOOLTIPS-TODO.md` for their own panels (Looks 35,
  Scene & Render 25, Motion 54) and delete their rows when done.
- Each later task that changes a panel updates its guide chapter and pictures (rule in
  `CLAUDE.md` section 6). Panels changed by the running tasks 0010, 0011, 0016 and 0019 are not in
  this guide yet.
- For task 0020 (updates from GitHub): the Help-menu entry lives in the app template, which only
  Install.bat copies. An in-app update of the extension brings the new guide file, but changes to
  the app template (this entry included) arrive only by running Install.bat. 0020 should either
  update the template too or move such entries into the extension. (Found by the independent
  review.) For 0.2.10 the owner installs with Install.bat, so the entry is there.
- On the owner's PC (cannot be tested here): Help > Fresing Render user guide opens the guide in
  the web browser; the Start-menu shortcut "Fresing Render - User guide" works.
- The Inventor export advice (AP214) is still not checked with an Inventor file (same as 0008).
- For the Quality lane (0019): `tools/ui_test_app.py` only passes with a warm import cache. Its
  first step sends Esc (to close the splash) and then starts the import; the Esc is handled after
  the import has started and cancels it, so the test waits 30 minutes for a model that never comes.
  Reinstalling the extension empties the cache, and a fresh machine (GitHub) never has one. Fix:
  send the Esc and the panel drag in one step and start the import in the next. Not changed here
  (another lane's file); lesson added to `CLAUDE.md` section 8.
