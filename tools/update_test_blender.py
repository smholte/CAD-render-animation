"""In-app update test, run inside Blender (task 0020). Driven by tools/ci_update_test.py (Linux, real app on a
virtual screen) and tools/ci_windows_install.ps1 (Windows, in the background).

    blender [--app-template fresing_render] [--background] --python tools/update_test_blender.py -- before <out.json>
    blender ... --python tools/update_test_blender.py -- after <out.json>

before  (the old version is installed): the start-up check (window) or a check (background) must find the
        new version (UPDATE_TEST_EXPECT) at FRESING_UPDATE_URL; then Update now, as the button does. The app
        downloads, starts update_helper.py and closes. FRESING_UPDATE_RESTART says how it is started again
        (with "-- after").
after   (started again by the helper): the new version is installed, the panel says "Updated to …", and the
        app template is the new one (Help > Fresing Render user guide exists, which the 0.2.10 template
        had not), "Check for Fresing Render updates" sits under it.

Each phase writes its checks to <out.json> ({"checks": [[name, ok, detail], ...]}) and prints PASS/FAIL lines.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import traceback

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PHASE = ARGS[0] if ARGS else "before"
OUT = os.path.abspath(ARGS[1]) if len(ARGS) > 1 else os.path.join(os.getcwd(), f"update_{PHASE}.json")
EXPECT = os.environ.get("UPDATE_TEST_EXPECT", "")
PROJECT = os.environ.get("UPDATE_TEST_PROJECT", "")     # a saved project with unsaved changes when Update now is pressed
MARKER = "Update test marker"
OLD = os.environ.get("UPDATE_TEST_OLD", "")
SHOTS = os.environ.get("UITEST_OUT", os.path.dirname(OUT))
CHECKS: list[list] = []


def log(*a):
    print("[UITEST]", *a, flush=True)


def check(name, ok, detail=""):
    CHECKS.append([name, bool(ok), str(detail)])
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def save():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".new", "w", encoding="utf-8") as fh:
        json.dump({"phase": PHASE, "checks": CHECKS}, fh, indent=1)
    os.replace(OUT + ".new", OUT)


def ext():
    import addon_utils
    name = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith(".fresing_render")), "")
    if name and name not in bpy.context.preferences.addons:
        addon_utils.enable(name, default_set=True)
    return importlib.import_module(name) if name else None


def shot(name):
    if bpy.app.background or not shutil_which("import"):
        return
    subprocess.run(["import", "-window", "root", os.path.join(SHOTS, name + ".png")], check=False)


def shutil_which(cmd):
    import shutil
    return shutil.which(cmd)


def finish_and_quit():
    passed = sum(1 for c in CHECKS if c[1])
    log(f"RESULT {passed}/{len(CHECKS)} passed ({PHASE})")
    save()
    bpy.ops.wm.quit_blender()


# ---------------------------------------------------------------------------
# before: old version installed -> check -> Update now
# ---------------------------------------------------------------------------

def make_project(part: int = 0):
    """Save a project, then change it: Update now must save the change and open the project again.
    part 1 saves, part 2 changes (a window needs a moment in between, or the change does not count as
    unsaved); 0 does both (background: Blender keeps no undo steps there, so nothing counts as changed:
    the change is saved here and only the reopening is checked)."""
    if not PROJECT:
        return
    os.makedirs(os.path.dirname(PROJECT), exist_ok=True)
    wm = bpy.context.window_manager
    over = {"window": wm.windows[0]} if wm and wm.windows else {}
    with bpy.context.temp_override(**over):
        if part in (0, 1):
            bpy.ops.wm.save_as_mainfile(filepath=PROJECT)
        if part in (0, 2):
            bpy.ops.object.empty_add()
            bpy.context.view_layer.objects.active.name = MARKER
            if bpy.app.background:
                bpy.ops.wm.save_mainfile()
            else:
                bpy.ops.ed.undo_push(message="Update test change")     # like a click: counts as a change


def project_is_dirty():
    if PROJECT and not bpy.app.background:
        check("project saved, then changed (unsaved changes)", bpy.data.filepath == PROJECT and bpy.data.is_dirty,
              f"{bpy.data.filepath} dirty={bpy.data.is_dirty}")


def project_checks():
    if not PROJECT:
        return
    if bpy.app.background and os.path.normcase(bpy.data.filepath) != os.path.normcase(PROJECT):
        bpy.ops.wm.open_mainfile(filepath=PROJECT)
    else:
        check("the same project opened again", os.path.normcase(bpy.data.filepath) == os.path.normcase(PROJECT),
              bpy.data.filepath)
    check("the change was saved before the update", MARKER in bpy.data.objects)


def before_checks(mod) -> bool:
    upd = importlib.import_module(mod.__name__ + ".blender.updates")
    check("old version installed", mod.__version__ == OLD or not OLD, mod.__version__)
    check("installed as an extension", upd.extension_repo() != "", upd.extension_repo())
    check("online access on", bpy.app.online_access)
    want = os.environ.get("UPDATE_TEST_URL") or os.environ.get("FRESING_UPDATE_URL")
    check("update address from the test", upd.index_url()[0] == want, f"{upd.index_url()} expected {want}")
    res = upd._check
    check("update found", res.get("state") == "available" and res.get("version") == EXPECT,
          f"{res.get('state')} {res.get('version')} {res.get('message', '')}")
    check("what's new from the changelog", any(c.get("version") == EXPECT for c in res.get("changes", [])),
          [c.get("version") for c in res.get("changes", [])])
    if not bpy.app.background:
        check("panel 'Update available' shown", upd.FRESING_PT_update.poll(bpy.context))
    check("update helper ready", upd.preflight(bpy.context) == "", upd.preflight(bpy.context))
    return res.get("state") == "available"


def run_before_background():
    mod = ext()
    if mod is None:
        check("extension installed", False)
        return finish_and_quit()
    upd = importlib.import_module(mod.__name__ + ".blender.updates")
    upd.check_now()
    make_project()
    if not before_checks(mod):
        return finish_and_quit()
    save()
    log("Update now")
    try:
        result = bpy.ops.fresing.update_install()          # downloads, starts the helper, closes Blender
    except RuntimeError as exc:
        check("Update now", False, exc)
        return finish_and_quit()
    # in the background Blender closes when this script ends (the helper waits for that)
    check("Update now: downloaded, helper started, Blender closing", result == {"FINISHED"}, result)
    log(f"RESULT {sum(1 for c in CHECKS if c[1])}/{len(CHECKS)} passed ({PHASE})")
    save()


_state = {"t0": time.time(), "step": "wait_check"}


def gui_driver():
    try:
        mod = ext()
        upd = importlib.import_module(mod.__name__ + ".blender.updates")
        step = _state["step"]
        if step == "wait_check":                            # the start-up check runs by itself
            if upd._check.get("state") in ("idle", "checking") and time.time() - _state["t0"] < 120:
                return 0.5
            check("start-up check finished", upd._check.get("state") not in ("idle", "checking"),
                  upd._check.get("state"))
            _state["step"] = "update"
            return 1.0
        if step == "update":
            make_project(1)
            _state["step"] = "change"
            return 1.0
        if step == "change":
            make_project(2)
            _state["step"] = "update2"
            return 1.0
        if step == "update2":
            project_is_dirty()
            ok = before_checks(mod)
            for area in bpy.context.window_manager.windows[0].screen.areas:
                area.tag_redraw()
            save()
            _state["step"] = "shot"
            if not ok:
                finish_and_quit()
                return None
            return 1.5
        if step == "shot":
            shot("update_available")
            log("Update now")
            win = bpy.context.window_manager.windows[0]
            with bpy.context.temp_override(window=win, screen=win.screen):
                bpy.ops.fresing.update_install("EXEC_DEFAULT")       # what the button does after "Update now" in its dialog
            _state.update(step="downloading", t1=time.time())
            return 0.5
        if step == "downloading":                           # the app closes by itself when the download is done
            if time.time() - _state["t1"] > 300:
                check("app closed for the update", False, "still open after 5 minutes: " + str(upd._dl))
                finish_and_quit()
                return None
            if upd._dl.get("error"):
                check("download", False, upd._dl["error"])
                finish_and_quit()
                return None
            if upd._dl.get("active") and upd._dl.get("done", 0) > 0 and "shot_dl" not in _state:
                _state["shot_dl"] = True
                shot("update_downloading")
            return 0.25
    except Exception:  # noqa: BLE001
        check("before: " + _state["step"], False, traceback.format_exc())
        finish_and_quit()
    return None


# ---------------------------------------------------------------------------
# after: started again by the helper
# ---------------------------------------------------------------------------

def run_after():
    mod = ext()
    if mod is None:
        check("extension installed after the update", False)
        return
    upd = importlib.import_module(mod.__name__ + ".blender.updates")
    check("new version runs", mod.__version__ == EXPECT, mod.__version__)
    st = dict(upd._status)
    check("message 'Updated to …'", st.get("ok") and st.get("message") == f"Updated to {EXPECT}.", st)
    check("what's new after the update", any(c.get("version") == EXPECT for c in st.get("changes", [])),
          [c.get("version") for c in st.get("changes", [])])
    check("status file shown once (removed)", not os.path.exists(upd.status_path()))
    if not bpy.app.background:
        check("panel 'Updated to …' shown", upd.FRESING_PT_update.poll(bpy.context) and upd.notice_kind() == "status")
        check("started with the app template", bpy.context.preferences.app_template == "fresing_render",
              bpy.context.preferences.app_template)
        # the template is the new one: its Help menu entry exists (the 0.2.10 template had none)
        funcs = [getattr(f, "__name__", "") for f in bpy.types.TOPBAR_MT_help._dyn_ui_initialize()]
        check("Help > Fresing Render user guide (new template)", "_draw_help_menu" in funcs
              and hasattr(bpy.types, "FRESING_OT_user_guide"), funcs)
        check("Help > Check for updates under it", "_draw_help" in funcs and "_draw_help_menu" in funcs
              and funcs.index("_draw_help") == funcs.index("_draw_help_menu") + 1, funcs)
    tdir = upd.template_dir()
    src = os.path.join(upd.PKG_DIR, "app_template_files", "__init__.py")
    same = bool(tdir) and open(os.path.join(tdir, "__init__.py"), "rb").read() == open(src, "rb").read()
    check("installed app template = the one in the new extension", same, tdir)
    check("no update offered any more", upd.check_now().get("state") == "none", upd._check)
    project_checks()


def gui_after():
    try:
        run_after()
        for area in bpy.context.window_manager.windows[0].screen.areas:
            area.tag_redraw()
        _state["after_shot"] = time.time()
    except Exception:  # noqa: BLE001
        check("after", False, traceback.format_exc())
    bpy.app.timers.register(gui_after_shot, first_interval=1.5)
    return None


def gui_after_shot():
    shot("update_done")
    finish_and_quit()
    return None


if PHASE == "before":
    if bpy.app.background:
        run_before_background()
    else:
        bpy.app.timers.register(gui_driver, first_interval=2.0, persistent=True)
else:
    if bpy.app.background:
        try:
            run_after()
        except Exception:  # noqa: BLE001
            check("after", False, traceback.format_exc())
        finish_and_quit()
    else:
        bpy.app.timers.register(gui_after, first_interval=3.0, persistent=True)
