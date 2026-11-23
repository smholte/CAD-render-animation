"""Real-app tests in one go: for the automatic tests on GitHub, and usable on a chat machine.

Installs the extension (built with Linux wheels) and the app template into a real Blender with
its own, fresh settings folder (BLENDER_USER_RESOURCES), then runs:

    ui1    tools/ui_test_app.py   - the real app on a virtual screen, simulated clicks, screenshots
    ui2    tools/ui_test_app2.py  - the remaining buttons, undo/redo
    faces  tools/ui_test_faces.py - painted faces: from CAD, 'Paint faces' with clicks in the view
    decals tools/ui_test_decals.py - logos & stickers: 'Add decal…' with a click, move with the mouse, one copy
    surroundings  tools/ui_test_surroundings.py - sea, deck, halls, props, queue (Cycles + EEVEE)
    studio  tools/ui_test_studio.py - light looks, camera views, blur + sharp spot, turntable in the queue
    callouts  tools/ui_test_callouts.py - labels on parts, picture card and music in a queued MP4, a still with a label
    video  tools/ui_test_video.py - brand kit in the library, logo, title/end card, captions, watermark in a queued MP4 and stills
    rulesets  tools/ui_test_rule_sets.py - rule sets: copy, change, save, switch with preview, undo
    milling  tools/ui_test_milling.py - milling: pick bit and block in the view, the cut follows the timeline; chips
    cylinder tools/ui_test_cylinder.py - cylinders: barrel and rod, clicks on the two pins, follow / drive, undo
    linkage tools/ui_test_linkage.py - mechanisms: Base, Add mechanism (scissor, four-bar), height, undo, Lift height
           step, save and open again, Remove
    gcode  tools/ui_test_gcode.py - CNC machine: axes, tool, workpiece, clicked work zero; Run G-code program step,
           the tip follows the program, tool change, toolpath, save and open again
    waycover tools/ui_test_waycover.py - way covers: Add way cover, axis, Add section x5, Make it, the axis drives the covers, Flip,
           Remove section, save and open again, Remove way cover
    flex   tools/ui_test_flex.py - hoses and drag chains: a click on a hose, Add hose, the arm luffs, Add cable, Find and
           add all, a hose too short warns; a click on one chain link, Add drag chain, X moves, undo, save and open again
    cables tools/ui_test_paths.py - cables and paths: a click on the rope, a mouse click on Add cable, a click on a row of
           What it touches, Remove and Add (+) with the click picker (Esc, hover highlight), Flip side, undo and redo;
           Build animation: the rope follows the luffing frame and the sheaves turn, save and open again, Remove
    spool  tools/ui_test_spool.py - drums and carousels: Add drum and a click on the drum (hover highlight), the fleet
           angle warns, "This joint follows the layer" + "level" typed in its search; Add carousel and a click on the
           turntable, undo and redo, the arm follows, its tick box off and on; Build animation, save and open again
    clash  tools/ui_test_clash.py - clash check: Build, Check for clashes, click the row (frame, red, zoom), Cancel,
           the queue note, Build again clears the result, save and open again
    paths  tools/paths_test_blender.py - paths with spaces, accents, an apostrophe and an en dash
    pccheck  the PC check (Full), started like its Tools-folder shortcut: the launcher inside the installed
           extension, in a background Blender; judged by tools/ci_check_pccheck.py (task 0032)
    update tools/ci_update_test.py --gui - in-app update: an old version with the 0.2.10 app template finds
           this version on a local GitHub-like server, Update now, closes, is updated and starts again

    python3 tools/ci_real_app.py --blender <blender program> --wheels <linux wheels dir> --out <dir>
                                 [--only ui1,paths | --group ui] [--timeout-min 40]

Needs xvfb-run and ImageMagick ("import") for ui1/ui2. Every test's log and screenshots land in
<out>/<test>/; the verdict per test is printed, written to <out>/summary.md and to the GitHub job
summary. Exit code 1 when any test failed, did not finish, or reported no RESULT line.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import test_install_linux  # noqa: E402

SCREEN = "-screen 0 1800x2600x24"
RESULT_RE = re.compile(r"RESULT (\d+)/(\d+)")
# Fewest checks each test must report: a check that silently disappears turns the run red.
# Raise these when a test gets new checks (never lower them without saying why in the commit).
MIN_CHECKS = {"ui1": 32, "ui2": 50, "faces": 10, "decals": 13, "surroundings": 23, "rulesets": 19, "studio": 21,
              "milling": 25, "video": 14, "callouts": 15, "cylinder": 22, "linkage": 25, "waycover": 16, "gcode": 29,
              "paths": 8, "pccheck": 43, "pccheck2": 4, "pccheckheavy": 17, "update": 32, "tour": 100, "tour2": 2, "tourui": 31, "layout": 66,
              "panel": 39, "start": 56, "setup": 46, "highlight": 74, "usage": 33, "lesson": 41, "lessoni": 38,
              "doublearm": 19, "clash": 21, "vessel": 15, "flex": 31, "cables": 36,
              "spool": 43, "undorebake": 4, "lifting": 22, "liftingmake": 25, "setupcrane": 32, "lock": 19, "quiet": 90, "left": 42, "settings": 52, "locations": 17, "toolbox": 19,
              "clientkeys": 12, "keys": 30, "demokits": 25, "drawn": 25, "backups": 23, "forms": 29,
              "move": 14, "importagain": 18, "place": 22, "jointfold": 11}
MIN_CHECKS_QUICK = {"ui1": 27, "surroundings": 17, "studio": 20, "video": 9, "callouts": 8}   # UITEST_QUICK=1 skips renders and the queue

# The real-app tests run on GitHub as parallel jobs, one per group (task 0036, regrouped in task 0063 so that no job
# takes more than about 8 minutes; task 0108: pccheck had grown to 14 min, two EEVEE lines moved to pccheck-b). Seconds of the tests on a runner (run 42815485418, 10 Nov 2026): pccheck (Full, first
# part, ~44 lines) ~250 | pccheck-b: pccheck2 (video.labels + queue.time_test) ~215 + ui2 51 + faces 14 + rulesets 32 +
# decals 20 | callouts 442 (its queued video varies most: alone) | paths 130 + pccheckheavy ~330 | tour ~210 | ui1 377 |
# surroundings 403 | video 219 + studio 96 + update 28 | milling 32 + cylinder 24 + linkage 27 + waycover + gcode + tourui
# + clash (task 0065).
# Add about 1 minute of set-up per job. A new test goes into the group with the fewest minutes
# (add it to TESTS and MIN_CHECKS too); a test that is in no group, or in two, fails the precheck
# (tools/ci_precheck.py). The longest job sets the run's length (with the queued-render test of test_air.py, ~10 min).
GROUPS = {
    "pccheck": ["pccheck"],             # the PC check (Full) in two halves, task 0063: lines of tools/ci_pccheck_lines.py
    "pccheck-b": ["pccheck2", "lock", "clientkeys", "keys", "demokits", "drawn", "quiet", "lesson", "move", "jointfold"],   # jointfold: task 0290 (~40 s)   # move: task 0307 (~40 s)   # lesson: task 0230 (~1.5 min)   # quiet: task 0241 (~40 s)   # drawn: task 0240 (~0.5 min); demokits: task 0228 (~1 min)   # lock: task 0213 (~1 min); clientkeys: task 0227 (~40 s)          # task 0108: + the two EEVEE lines (~495 s); its small tests moved below
    "callouts": ["callouts", "importagain", "place"],      # importagain: task 0289 (~0.5 min); place: task 0292 (~40 s)
    "paths-heavy": ["pccheckheavy", "panel", "setup"],   # task 0062: + the side panel and the Set-up window (~2.5 min)     # task 0108: paths (~130 s) moved to machines (this job took 9.4-11.7 min)
    "tour": ["tour", "toolbox", "forms"],   # forms: task 0282 (~1 min); toolbox: task 0217 (~2 min: two small house bakes); the automatic test tour (task 0060: with paths-heavy it took 18 min);
    "tour-b": ["tour2", "highlight", "start"],   # task 0062: + the lesson highlight (~1.5 min)                # task 0108: in two halves (729 s of stops in one job, 10-13 min)
    "ui": ["ui1", "spool", "layout", "left", "settings", "locations"],     # spool: task 0080, about 1 minute; left: task 0260; settings: 0271; locations: 0272 (~40 s)
    "scenes": ["surroundings", "vessel", "rulesets", "decals", "usage", "setupcrane", "backups", "lessoni"],   # backups: 0246 (~1.5 min); lessoni: 0230 (~3 min)   # usage: task 0181 (~1 min);
    # setupcrane: task 0203 (~4 min)
    "motion": ["video", "studio", "update", "ui2", "faces", "lifting", "liftingmake"],   # lifting: 0201; liftingmake: 0204
    "machines": ["milling", "cylinder", "linkage", "waycover", "gcode", "tourui", "doublearm", "clash", "flex",
                 "cables", "paths", "undorebake"],
}

TESTS = {
    "importagain": ("Real app: a dropped STEP file comes in as with Import STEP…, Import again from the cache, a "
                    "model's Up axis + Undo, Remove from cache (ui_test_import_again.py)", "ui_test_import_again.py",
                    True),
    "ui1": ("Real app: import, looks, joints, animation, queue (ui_test_app.py)", "ui_test_app.py", True),
    "ui2": ("Real app: remaining buttons, undo/redo (ui_test_app2.py)", "ui_test_app2.py", True),
    "faces": ("Real app: painted faces (ui_test_faces.py)", "ui_test_faces.py", True),
    "decals": ("Real app: logos & stickers – add with a click, move with the mouse (ui_test_decals.py)",
               "ui_test_decals.py", True),
    "surroundings": ("Real app: surroundings, props, queue (ui_test_surroundings.py)",
                     "ui_test_surroundings.py", True),
    "rulesets": ("Real app: rule sets – copy, save, switch, undo (ui_test_rule_sets.py)",
                 "ui_test_rule_sets.py", True),
    "studio": ("Real app: light looks, views, blur, turntable (ui_test_studio.py)", "ui_test_studio.py", True),
    "video": ("Real app: brand kit, logo, cards, captions, watermark in a queued video (ui_test_video.py)",
              "ui_test_video.py", True),
    "callouts": ("Real app: labels, picture card, music in a queued video (ui_test_callouts.py)",
                 "ui_test_callouts.py", True),
    "milling": ("Real app: milling – pick bit and block, cut follows the timeline (ui_test_milling.py)",
                "ui_test_milling.py", True),
    "cylinder": ("Real app: cylinders – barrel, rod, clicks on the pins, follow / drive (ui_test_cylinder.py)",
                 "ui_test_cylinder.py", True),
    "linkage": ("Real app: mechanisms – scissor lift, four-bar, height, Lift height step (ui_test_linkage.py)",
                "ui_test_linkage.py", True),
    "waycover": ("Real app: way covers – axis, five sections, Make it, the axis drives them (ui_test_waycover.py)",
                 "ui_test_waycover.py", True),
    "flex": ("Real app: hoses and drag chains – click a hose, Add hose, the arm luffs; click one link, Add drag "
             "chain, X moves; undo, save and open (ui_test_flex.py)", "ui_test_flex.py", True),
    "drawn": ("Real app: Draw hose – the picker's hover on the fittings, a click, Backspace, the clicks again, Enter; "
              "the CAD hose replaced, the arm luffs; one click and Esc; undo and redo (ui_test_drawn.py)",
              "ui_test_drawn.py", True),
    "cables": ("Real app: cables and paths – a mouse click on Add cable, a row of What it touches, Add (+) with a click "
               "in the view, Flip side, undo and redo; Build: the rope follows the luffing frame, the sheaves turn; "
               "save and open (ui_test_paths.py)", "ui_test_paths.py", True),
    "lifting": ("Real app: 8 Lifting plan – first use, a crane placed by mouse, every crane class with its poses, "
                "Remove, the load and its CoG, Hook to here by a click, save and open (ui_test_lifting.py)",
                "ui_test_lifting.py", True),
    "setupcrane": ("Real app: Set up a crane – the AT-40, CC-750 and KB-50 rigged from their bare STEP through the "
                   "Set-up window by names, every step drawn, Check, Save = the built-in rig, placed again Hook to here "
                   "as the built-in (ui_test_setup_crane.py)", "ui_test_setup_crane.py", True),
    "liftingmake": ("Real app: 8 Lifting plan > Equipment > Make a crane… – the dialog, refused numbers, Make in the "
                    "background, the crane in the library, Place now, Cancel leaves nothing (ui_test_lifting_make.py)",
                    "ui_test_lifting_make.py", True),
    "toolbox": ("Real app: a house from House Planner by itself – the app's Toolbox watcher, Bake now switches to the "
                "house's own scene and bakes, the package goes back, the owner's scene again; cancel.json stops a "
                "bake (ui_test_toolbox.py)", "ui_test_toolbox.py", True),
    "undorebake": ("Real app: Undo after a cable re-bake works the cables out again for the motion the scene has "
                   "(ui_test_undo_rebake.py)", "ui_test_undo_rebake.py", True),
    "spool": ("Real app: drums and carousels – Add drum / Add carousel with a click in the view, a joint follows the "
              "layer (search), undo and redo, off and on; Build, save and open (ui_test_spool.py)", "ui_test_spool.py",
              True),
    "gcode": ("Real app: CNC machine and Run G-code program – clicks, tip on the path, tool change "
              "(ui_test_gcode.py)", "ui_test_gcode.py", True),
    "doublearm": ("Real app: double-arm tool changer – click the hub and the hinge, Check, hand-overs "
                  "(ui_test_doublearm.py)", "ui_test_doublearm.py", True),
    "paths": ("Paths with spaces, accents, ' and – (paths_test_blender.py)", "paths_test_blender.py", False),
    "pccheck": ("PC check, Full, first part (all lines but four), from the installed launcher (pccheck/launcher.py)", "",
                "pccheck"),
    "pccheck2": ("PC check, Full, second part (the four longest lines: video with labels, queue time test, the two "
                 "EEVEE queue lines)", "",
                 "pccheck"),
    "pccheckheavy": ("PC check, Heavy (scaled down), from the installed launcher", "", "pccheck"),
    "tour": ("Test tour, the automatic run (PC check mode Tour) from the installed launcher: every other stop "
             "(the rest in tour2, task 0108)", "", "pccheck"),
    "tour2": ("Test tour, the automatic run: the other half of the stops (tools/ci_pccheck_lines.py tour2)", "",
              "pccheck"),
    "layout": ("Real app: the layout kept on open, Live preview kept, the header button (ui_test_layout.py)",
               "ui_test_layout.py", True),
    "tourui": ("Real app: test tour – make, open, Go here and in another project, OK / Problem, Copy results "
               "(ui_test_tour.py)", "ui_test_tour.py", True),
    "clash": ("Real app: clash check – Build, Check for clashes, click the row (frame, red, zoom), Cancel, queue note, "
              "Build again clears it (ui_test_clash.py)", "ui_test_clash.py", True),
    "vessel": ("Real app: vessel motion – tick it, the crane and deck move, sea and camera stay, still parts, scripts "
               "off (blender -Y) (ui_test_vessel.py)", "ui_test_vessel.py", True),
    "update": ("In-app update: old version + 0.2.10 template -> Update now -> new version (ci_update_test.py)",
               "ci_update_test.py", None),
    "panel": ("Real app: the side panel – folded start, titles, Ctrl+click, tabs, workspaces, families, an own "
              "workspace, the Client view's lock with clicks and keys, an older project, Make (ui_test_panel.py)",
              "ui_test_panel.py", True),
    "jointfold": ("Real app: 4 Motion's Joints fold opens with a click on its title, a clicked joint shows what it "
                  "moves, 'Beyond limits' on the value row and the rows under it stay put (ui_test_joint_fold.py)",
                  "ui_test_joint_fold.py", True),
    "highlight": ("Real app: the lesson highlight – six looks point at a button, a folded section and a part; "
                  "nothing left after clear (ui_test_highlight.py)", "ui_test_highlight.py", True),
    "start": ("Real app: Start here – the welcome of a new user (three starts, Later, never, Take the test tour), What's "
              "new after an update (functions, the tour of only the new and changed models), the Fresing menu in "
              "every workspace (ui_test_start.py)", "ui_test_start.py", True),
    "settings": ("Real app: Fresing Settings – Fresing > Settings… opens one window, each tab clicked draws its page, "
                 "it stays open, opens again on the last tab, My usage… opens it on My usage, the Client view opens it; "
                 "a played animation with no input adds no time to My usage; a setting of each tab kept over a restart "
                 "with the app template, a damaged settings file gives the defaults and a note (ui_test_settings.py)",
                 "ui_test_settings.py", True),
    "forms": ("Real app: function windows – Make a crane… opens a window with only its form, stays open after a click in "
              "the main window, no second window, what was typed stays; a second function window beside it; Esc over "
              "one closes it; its size kept in the settings file and used again; Return saves a pose (undo step); a "
              "refused Save says why; the Client view refuses as before; another project closes them "
              "(ui_test_forms.py)", "ui_test_forms.py", True),
    "locations": ("Real app: Locations and Exports – two set-up files (company copied, department linked) and the "
                  "user's own folder: a logo and a rule set of each with its badge, the same name twice shown twice, a "
                  "company rule set used, saving asks where, Settings opens on Locations / Exports, a renamed newer "
                  "set-up updates with its change list, a dead server does not slow the start, Save to and also a "
                  "copy (ui_test_locations.py)", "ui_test_locations.py", True),
    "usage": ("Real app: the usage tracker – the favourites bar sorted at a start, a click on a favourite, a click counted "
              "with its panel, the question about an unused panel and Hide, My usage, Back as it came "
              "(ui_test_usage.py)", "ui_test_usage.py", True),
    "lock": ("Real app: the Client view's lock holds – Ctrl+Z after an import, every way back to an Outliner (menu, "
             "Shift+F9, a new window, another workspace, Ctrl+Space), the Set-up step through Ctrl+Z (ui_test_lock.py)",
             "ui_test_lock.py", True),
    "demokits": ("Real app: demo kits – the Make window's list, Add a demo kit…, a broken zip and an old kit refused, "
                 "Add / Remove off in the Client view, the list with no app demo, Make with the test kit in the "
                 "background, Open it, Remove (ui_test_demo_kits.py)", "ui_test_demo_kits.py", True),
    "clientkeys": ("Real app: the Client view – a part selected before, Ctrl+Z, a click, A, a part freed by a script: "
                   "nothing selected; X, Delete, Shift+X, Shift+Delete, Tab and Object > Delete delete nothing; Full "
                   "access: Delete works again (ui_test_client_keys.py)", "ui_test_client_keys.py", True),
    "keys": ("Real app: Blender's keys outside Full access – 27 keys pressed on a selected part change nothing, H / Alt+H "
             "still hide and show, F12 / Ctrl+F12 run the app's render, the right-click menu on a part (Return on its first entry, "
             "each entry), on empty space, in the Client view; Full access: Blender's menu and Delete (ui_test_keys.py)",
             "ui_test_keys.py", True),
    "move": ("Real app: G / R in the 3D view – on the fresh import the boom is locked in place: G moves nothing and the "
             "status bar says how to unlock it; the right-click menu's Unlock so it can move; then G, X, 100, Enter, G "
             "with the mouse and R, Z, 30, Enter move and turn it and it stays; after Build the message, after Stop it "
             "moves again (ui_test_move.py)", "ui_test_move.py", True),
    "place": ("Real app: Place and Remove – the boom's lock opened, Place open shows the arrows and rings, a + step moves "
              "the boom and its joint and Ctrl+Z puts both back, Move with mouse X 100 Enter moves it 100 mm and it "
              "stays; Delete opens the Remove window (nothing gone yet), Remove takes the crane with its joints and "
              "cylinder, Ctrl+Z brings everything back; the Client view swallows Delete (ui_test_place.py)",
              "ui_test_place.py", True),
    "lesson": ("Real app: lessons – Fresing > Learn…, Build it yourself on the crane by clicking where the highlight "
               "points and Do it for me, a step done another way, Show me from the learning list at its step, Back, "
               "saved half-way and going on, nothing left after Stop (ui_test_lesson.py)", "ui_test_lesson.py", True),
    "lessoni": ("Real app: lessons, the independent tester's run – Ctrl+Z and redo after Build, the side panel closed and "
                "on another tab, Blender's column shown and hidden, another project opened, saved half-way, the Client "
                "view, both lessons to the end with Play on (ui_test_lesson_independent.py)",
                "ui_test_lesson_independent.py", True),
    "quiet": ("Real app: a quiet window – the 3D view header, tool header, top bar, splash and File > New / Ctrl+N "
              "without Blender's editing parts; Fresing > Show all of Blender / Back, Full access, the Client view, "
              "Edit Mode, a dummy add-on's items kept, projects open quiet, header width measured (ui_test_quiet.py)",
              "ui_test_quiet.py", True),
    "backups": ("Real app: automatic backups – the timer makes one after a change, the project keeps its path, unsaved "
                "mark and undo, the save handlers keep out, none when idle, in the Client view or during a clash check, "
                "Restore, the start question for a saved and an unsaved project (ui_test_backups.py)",
                "ui_test_backups.py", True),
    "setup": ("Real app: the Set-up window – opens with its tab, Next / Back, a click in the main window, save and "
              "open, close (ui_test_setup.py)", "ui_test_setup.py", True),
    "left": ("Real app: two panels – the left panel at a readable width without Blender's tools, its order, fold to the "
             "strip and back, Full access and back, the Client view, scrolling, an old project saved narrow; Make's "
             "output windows open, stay open on a click elsewhere, no second one, close; the Learning hub switch "
             "(ui_test_left.py)", "ui_test_left.py", True),
}


def run(cmd, env, log_path, timeout):
    """Run cmd, write all output to log_path (and echo it). Returns (exit code or None, seconds, text)."""
    t0 = time.time()
    out: list[str] = []
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", start_new_session=True)

        def pump():
            for line in proc.stdout:
                log.write(line)
                log.flush()
                out.append(line)
                sys.stdout.write(line)
                sys.stdout.flush()

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)    # Blender and xvfb (a render queue has its own session)
            except ProcessLookupError:
                pass
            proc.wait()
            code = None
        reader.join(timeout=30)
        if code is None:
            log.write(f"\n*** stopped after {timeout / 60:.0f} minutes ***\n")
    return code, time.time() - t0, "".join(out)


def install(blender: str, wheels: str, user_res: str, work: str) -> str:
    """Build the Linux zip, install + enable it in a fresh settings folder, copy the app template."""
    env = dict(os.environ, BLENDER_USER_RESOURCES=user_res)
    zip_path = test_install_linux.build_linux_zip(wheels, os.path.join(work, "build"), blender=blender)
    subprocess.check_call([blender, "--factory-startup", "--command", "extension", "install-file",
                           "-r", "user_default", "-e", zip_path], env=env, timeout=600)
    dst = os.path.join(user_res, "scripts", "startup", "bl_app_templates_user", "fresing_render")
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "app_template", "fresing_render"), dst,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return zip_path


def judge(key: str, code, text: str, timeout_min: float, quick: bool = False):
    """Verdict of one test from its exit code (None = stopped at the timeout) and its output.

    Returns (passed, detail, failure lines)."""
    lines = text.splitlines()
    fails = [ln.strip() for ln in lines if re.match(r"^(\[UITEST\] )?FAIL ", ln.strip()) or "ERROR in" in ln]
    m = None
    for m in RESULT_RE.finditer(text):
        pass
    # Python errors outside the test steps (a panel that fails to draw, a handler, an operator)
    # do not show up as a failed check: count them separately.
    stray = [i for i, ln in enumerate(lines) if "Traceback (most recent call last)" in ln and "ERROR in" not in ln]
    minimum = (MIN_CHECKS_QUICK if quick else {}).get(key, MIN_CHECKS[key])
    if key in ("tour", "tour2"):                  # each job runs its half of the stops (task 0108): all of that half
        import ci_pccheck_lines
        minimum = len(ci_pccheck_lines.ids_for("tour1" if key == "tour" else "tour2"))
    if code is None:
        verdict, detail = False, f"did not finish within {timeout_min:.0f} minutes"
    elif m is None:
        verdict, detail = False, f"no RESULT line (Blender exit code {code}): it stopped half-way"
    else:
        passed, total = int(m.group(1)), int(m.group(2))
        verdict = passed == total and total >= minimum
        detail = f"{passed}/{total} passed"
        if total < minimum:
            detail += f", but at least {minimum} checks expected"
    if stray:
        verdict = False
        i = stray[0]
        err = next((ln.strip() for ln in lines[i + 1:i + 40] if re.match(r"^\w*(Error|Exception)\b", ln.strip())), "")
        detail += f"; {len(stray)} Python error(s) outside the test steps"
        fails.append(f"Python error: {err or lines[i].strip()} (see blender_output.log)")
    return verdict, detail, fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", required=True)
    ap.add_argument("--wheels", required=True, help="folder with the Linux OpenCascade wheels")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=",".join(TESTS), help="tests to run, comma-separated (default: all)")
    ap.add_argument("--group", help="run one group of GROUPS (a parallel job on GitHub) instead of --only")
    ap.add_argument("--timeout-min", type=float, default=15, help="per test (they take 1-7 minutes)")
    args = ap.parse_args(argv)

    blender = os.path.abspath(args.blender)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fr_ci_")
    user_res = os.path.join(work, "blender_user")
    print("== installing the extension and the app template into", user_res, flush=True)
    t0 = time.time()
    install(blender, os.path.abspath(args.wheels), user_res, work)
    print(f"== installed in {time.time() - t0:.0f} s", flush=True)

    base_env = dict(os.environ, BLENDER_USER_RESOURCES=user_res, PYTHONUNBUFFERED="1",
                    TOOLBOX_HOME=os.path.join(work, "Toolbox é"))   # task 0217: never the runner's own home folder
    timeout = args.timeout_min * 60
    rows = []
    keys = GROUPS[args.group] if args.group else [k.strip() for k in args.only.split(",") if k.strip()]
    for key in keys:
        title, script, gui = TESTS[key]
        folder = os.path.join(out, key)
        os.makedirs(folder, exist_ok=True)
        env = dict(base_env, UITEST_OUT=folder)
        if key == "start":                           # task 0199: the welcome shows although events are simulated
            env.update(FRESING_WELCOME_TEST="1")
        if key == "backups":                         # task 0246: backups and the start question with simulated events
            env.update(FRESING_BACKUP_TEST="1")
        if key in ("usage", "settings"):             # task 0181 / 0271: the usage tracker counts although events are simulated
            env.update(FRESING_USAGE_TEST="1")
        if key == "rulesets":                        # its own rule-set library; folds open so it can click in them
            env.update(FRESING_RULE_SETS_DIR=os.path.join(folder, "library", "Rule sets"), FRESING_UI_OPEN_FOLDS="1")
        script_path = os.path.join(ROOT, "tools", script)
        if gui == "pccheck":                         # as the Tools-folder shortcut starts it (screen: for EEVEE)
            launcher = os.path.join(user_res, "extensions", "user_default", "fresing_render", "pccheck", "launcher.py")
            env.update(FRESING_PCCHECK_DIR=os.path.join(folder, "history"), FRESING_PCCHECK_NO_OPEN="1")
            cmd = ["xvfb-run", "-a", "-s", SCREEN, blender, "--background", "--online-mode", "--python-exit-code", "1",
                   "--python", launcher, "--", folder, {"pccheckheavy": "heavy", "tour": "tour", "tour2": "tour"}.get(key, "full")]
            if key in ("pccheck", "pccheck2"):         # Full is split over two jobs (task 0063, tools/ci_pccheck_lines.py)
                import ci_pccheck_lines
                part = "linux1" if key == "pccheck" else "linux2"
                env["FRESING_PCCHECK_ONLY"] = ",".join(ci_pccheck_lines.ids_for(part))
            if key in ("tour", "tour2"):               # the tour in two jobs (task 0108)
                import ci_pccheck_lines
                env["FRESING_PCCHECK_ONLY"] = ",".join(ci_pccheck_lines.ids_for("tour1" if key == "tour" else "tour2"))
            if key == "pccheckheavy":
                env["FRESING_PCCHECK_HEAVY_SMALL"] = "1"
        elif gui is None:                            # a driver of its own (own settings folder and screen)
            cmd = [sys.executable, script_path, "--gui", "--blender", blender, "--wheels", os.path.abspath(args.wheels),
                   "--out", folder, "--timeout-min", str(args.timeout_min)]
        elif gui:
            # --python-exit-code: an error while loading the script closes Blender instead of
            # leaving it open with nothing to drive it until the timeout
            cmd = ["xvfb-run", "-a", "-s", SCREEN, blender, "--app-template", "fresing_render",
                   "--enable-event-simulate", "--python-exit-code", "1", "--python", script_path]
        else:
            pdir = os.path.join(work, "pad test", "Mijn Projecten é ü", "Klant O'Brien – 2026")
            os.makedirs(pdir, exist_ok=True)
            for src, name in (("test_crane_a.step", "Kraan ontwerp – rev A é.step"),
                              ("test_crane_b.step", "Kraan ontwerp – rev B é.step")):
                shutil.copy2(os.path.join(ROOT, "tests", "data", src), os.path.join(pdir, name))
            env["PATHS_TEST_DIR"] = pdir
            cmd = [blender, "--background", "--python-exit-code", "1", "--python", script_path]
        print(f"\n== {title}", flush=True)
        crash_files = [os.path.join(tempfile.gettempdir(), n) for n in ("blender.crash.txt",)]
        for cf in crash_files:
            if os.path.isfile(cf):
                os.remove(cf)
        code, secs, text = run(cmd, env, os.path.join(folder, "blender_output.log"), timeout)
        if code not in (0, 1):                       # Blender itself stopped (139 = it crashed): show where
            import glob
            for cf in sorted(set(crash_files + glob.glob(os.path.join(tempfile.gettempdir(), "*.crash.txt")))):
                if os.path.isfile(cf):
                    with open(cf, encoding="utf-8", errors="replace") as fh:
                        print(f"-- Blender's crash file {cf} (exit code {code}):\n" + fh.read()[:6000], flush=True)
        verdict, detail, fails = judge(key, code, text, args.timeout_min, bool(os.environ.get("UITEST_QUICK")))
        if gui == "pccheck":                         # skips only for "no graphics card", every line there
            import ci_check_pccheck
            block = os.path.join(folder, "history", "last_run.txt")
            text_block = open(block, encoding="utf-8").read() if os.path.isfile(block) else ""
            import ci_pccheck_lines
            _rows, problems = ci_check_pccheck.judge(
                text_block, {"pccheckheavy": ci_check_pccheck.MIN_LINES_HEAVY,
                             "tour": len(ci_pccheck_lines.ids_for("tour1")),
                             "tour2": len(ci_pccheck_lines.ids_for("tour2")),
                             "pccheck": len(ci_pccheck_lines.ids_for("linux1")),
                             "pccheck2": len(ci_pccheck_lines.ids_for("linux2"))}.get(key, ci_check_pccheck.MIN_LINES_FULL))
            if problems:
                verdict = False
                detail += "; " + "; ".join(problems[:3])
                fails += problems
        rows.append((title, verdict, detail, secs, fails))
        print(f"== {title}: {'PASS' if verdict else 'FAIL'} - {detail} ({secs:.0f} s)", flush=True)

    lines = [f"### Real app (Linux, virtual screen){f' - group {args.group}' if args.group else ''}", "", "| Test | Result | Time |", "| --- | --- | --- |"]
    for title, ok, detail, secs, _ in rows:
        lines.append(f"| {title} | {'✅' if ok else '❌'} {detail} | {secs / 60:.1f} min |")
    for title, ok, detail, secs, fails in rows:
        if fails:
            lines += ["", f"**{title}** - failing checks:", ""] + [f"- `{f[:200]}`" for f in fails[:30]]
    summary = "\n".join(lines) + "\n"
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    print("\n" + summary)
    for title, ok, detail, _, fails in rows:
        if not ok:
            print(f"::error title={title}::{detail}" + (f" - first failure: {fails[0][:200]}" if fails else ""))
    shutil.rmtree(work, ignore_errors=True)
    return 0 if rows and all(r[1] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
