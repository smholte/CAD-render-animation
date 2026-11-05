"""In-app update, end to end with the real Blender program (task 0020). Linux; used by ci_real_app.py ("update")
and usable on a chat machine:

    python3 tools/ci_update_test.py --blender <blender> --wheels <linux wheels dir> --out <dir> [--gui]
    python3 tools/ci_update_test.py --blender <blender> --wheels <dir> --out <dir> --github [--expect 0.2.14]

What it does:
 1. builds this code twice with Linux wheels: as an "old" version 0.0.1 that ships the app template of 0.2.10
    (no Help-menu entry for the user guide), and as the current version;
 2. installs the old one into a fresh settings folder (BLENDER_USER_RESOURCES) with the old app template,
    online access on - as Install.bat leaves a PC;
 3. serves the current version from a local web server laid out like GitHub's releases
    (/releases/latest/download/index.json redirects to /releases/download/v<version>/index.json, the zip
    redirects to /assets/…), the way the release job publishes it (full download addresses in index.json);
 4. starts the old app (with --gui: the real window on a virtual screen, the start-up check; without: in the
    background) with tools/update_test_blender.py: it must find the update, press Update now, close;
    update_helper.py installs and starts the app again with "-- after", which checks the new version,
    the message, the new app template and its Help menu;
 5. checks the files: installed version, template, update log; prints "RESULT n/m".

--github  instead of 3-4: the real update address on GitHub. The app's check and download (size, SHA-256)
          run against the newest published release, as the Windows extension it is; installing needs
          Windows (done by the release check job on GitHub).
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_release  # noqa: E402
import test_install_linux  # noqa: E402

from fresing_render import __version__  # noqa: E402
from fresing_render.core import updates as core  # noqa: E402

OLD = "0.0.1"
OLD_TEMPLATE = os.path.join(ROOT, "tests", "data", "old_app_template")
SCRIPT = os.path.join(ROOT, "tools", "update_test_blender.py")
RESULTS: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), str(detail)))
    print(("[UITEST] PASS " if ok else "[UITEST] FAIL ") + name + (f" ({detail})" if detail and not ok else ""),
          flush=True)


def run(cmd, env, timeout=600, quiet=False):
    p = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                       timeout=timeout)
    if not quiet or p.returncode:
        print(p.stdout[-6000:], flush=True)
    return p


class GitHubLike(http.server.SimpleHTTPRequestHandler):
    """Serves <root>/<version>/… like GitHub's release downloads, with its redirects."""
    version = ""

    def do_GET(self):  # noqa: N802
        p = self.path.split("?")[0]
        latest = "/releases/latest/download/"
        if p.startswith(latest):
            self.send_response(302)
            self.send_header("Location", f"/releases/download/v{self.version}/{p[len(latest):]}")
            self.end_headers()
            return
        tagged = f"/releases/download/v{self.version}/"
        if p.startswith(tagged) and p.endswith(".zip"):
            self.send_response(302)                     # GitHub sends assets from another host
            self.send_header("Location", "/assets/" + p[len(tagged):] + "?sig=x")
            self.end_headers()
            return
        if p.startswith(tagged):
            self.path = "/" + p[len(tagged):]
        elif p.startswith("/assets/"):
            self.path = "/" + p[len("/assets/"):]
        else:
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, fmt, *args):
        print("[server]", fmt % args, flush=True)


def serve(folder: str, version: str):
    handler = type("H", (GitHubLike,), {"version": version})

    def factory(*a, **k):
        return handler(*a, directory=folder, **k)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), factory)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def start_xvfb():
    for n in range(91, 120):
        if os.path.exists(f"/tmp/.X11-unix/X{n}") or os.path.exists(f"/tmp/.X{n}-lock"):
            continue
        proc = subprocess.Popen(["Xvfb", f":{n}", "-screen", "0", "1800x1400x24", "-nolisten", "tcp"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(50):
            if os.path.exists(f"/tmp/.X11-unix/X{n}"):
                return proc, f":{n}"
            time.sleep(0.1)
        proc.kill()
    raise RuntimeError("no free display for Xvfb")


def wait_for(path, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if os.path.isfile(path):
            return True
        time.sleep(0.5)
    return False


def read_checks(path, label):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        check(f"{label}: results written", False, exc)
        return
    for name, ok, detail in data.get("checks", []):
        check(f"{label}: {name}", ok, detail)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", required=True)
    ap.add_argument("--wheels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gui", action="store_true", help="the real window on a virtual screen (Xvfb)")
    ap.add_argument("--github", action="store_true", help="check + download against the real GitHub release")
    ap.add_argument("--expect", default="", help="with --github: the version that must be offered")
    ap.add_argument("--timeout-min", type=float, default=12)
    args = ap.parse_args(argv)

    blender = os.path.abspath(args.blender)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="fr_update_")
    user_res = os.path.join(work, "blender user é")
    env = dict(os.environ, BLENDER_USER_RESOURCES=user_res, PYTHONUNBUFFERED="1", UITEST_OUT=out,
               UPDATE_TEST_OLD=OLD)
    env["NO_PROXY"] = env["no_proxy"] = ",".join(x for x in ("127.0.0.1", "localhost", env.get("NO_PROXY", "")) if x)

    # 1. two builds of this code
    t0 = time.time()
    old_zip = test_install_linux.build_linux_zip(args.wheels, os.path.join(work, "old"), blender=blender,
                                                 version=OLD, template_src=OLD_TEMPLATE)
    new_zip = test_install_linux.build_linux_zip(args.wheels, os.path.join(work, "new"), blender=blender)
    print(f"== built {os.path.basename(old_zip)} and {os.path.basename(new_zip)} in {time.time() - t0:.0f} s", flush=True)

    # 2. the old version installed as Install.bat leaves it
    p = run([blender, "--command", "extension", "install-file", "-r", "user_default", "-e", old_zip], env, quiet=True)
    check("old version installed", p.returncode == 0)
    tdir = os.path.join(user_res, "scripts", "startup", "bl_app_templates_user", "fresing_render")
    os.makedirs(tdir, exist_ok=True)
    shutil.copy2(os.path.join(OLD_TEMPLATE, "__init__.py"), tdir)
    shutil.copy2(os.path.join(ROOT, "app_template", "fresing_render", "splash.png"), tdir)
    run([blender, "--background", "--python-expr",
         "import bpy; bpy.context.preferences.system.use_online_access = True; bpy.ops.wm.save_userpref()"],
        env, quiet=True)
    ext_dir = os.path.join(user_res, "extensions", "user_default", "fresing_render")

    if args.github:
        return github_check(blender, env, args, out, work)

    # 3. the new version, published like a GitHub release
    pub = os.path.join(work, "published")
    os.makedirs(pub)
    srv, port = serve(pub, __version__)
    base = f"http://127.0.0.1:{port}"
    build_release.write_update_repo(pub, new_zip, [blender, "--factory-startup", "--command", "extension"],
                                    base_url=f"{base}/releases/download/v{__version__}")
    env["FRESING_UPDATE_URL"] = f"{base}/releases/latest/download/index.json"
    env["UPDATE_TEST_EXPECT"] = __version__

    # 4. the old app finds the update, updates, starts again
    before, after = os.path.join(out, "update_before.json"), os.path.join(out, "update_after.json")
    for f in (before, after):
        if os.path.exists(f):
            os.remove(f)
    xvfb = None
    env["UPDATE_TEST_PROJECT"] = os.path.join(work, "Projecten é", "Kraan – update test.blend")
    after_args = ["--python-exit-code", "1", "--python", SCRIPT, "--", "after", after]
    if args.gui:
        xvfb, display = start_xvfb()
        env["DISPLAY"] = display
        app = [blender, "--app-template", "fresing_render"]
        # the app's own restart command (program, app template, the project), plus the test script
        env["FRESING_UPDATE_RESTART_EXTRA"] = json.dumps(after_args)
    else:
        app = [blender, "--background"]
        env["FRESING_UPDATE_RESTART"] = json.dumps(app + after_args)
    log = open(os.path.join(out, "blender_before.log"), "w", encoding="utf-8")
    t1 = time.time()
    proc = subprocess.Popen(app + ["--python-exit-code", "1", "--python", SCRIPT, "--", "before", before], env=env,
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    limit = args.timeout_min * 60
    try:
        code = proc.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        code = None
    log.close()
    print(open(os.path.join(out, "blender_before.log"), encoding="utf-8", errors="replace").read()[-5000:], flush=True)
    check("old app closed for the update", code is not None, f"exit code {code}")
    read_checks(before, "before")
    got = wait_for(after, max(10.0, limit - (time.time() - t1)))
    secs = time.time() - t1
    check("app started again after the update", got, f"{secs:.0f} s")
    if got:
        read_checks(after, "after")
    time.sleep(2)
    # 5. the files
    log_text = ""
    try:
        log_text = open(os.path.join(user_res, "config", "fresing_update", "update.log"), encoding="utf-8").read()
    except OSError:
        pass
    print("---- update.log ----\n" + log_text[-4000:], flush=True)
    check("update.log: installed and started again", f"OK: Updated to {__version__}." in log_text
          and "started again:" in log_text)
    try:
        ver = open(os.path.join(ext_dir, "blender_manifest.toml"), encoding="utf-8").read()
    except OSError:
        ver = ""
    check(f"installed manifest says {__version__}", f'version = "{__version__}"' in ver)
    new_t = open(os.path.join(ROOT, "app_template", "fresing_render", "__init__.py"), "rb").read()
    check("app template on disk is the current one", open(os.path.join(tdir, "__init__.py"), "rb").read() == new_t)
    check("downloaded zip removed", not any(f.endswith(".zip") for f in os.listdir(
        os.path.join(user_res, "config", "fresing_update"))))
    print(f"== update took {secs:.0f} s from start of the old app to the new app's checks", flush=True)
    srv.shutdown()
    if xvfb is not None:
        xvfb.kill()
    return finish(work)


def github_check(blender, env, args, out, work) -> int:
    """The installed old version asks the real GitHub address; download of the Windows zip checked."""
    env = dict(env, FRESING_UPDATE_PLATFORM="windows-x64")
    env.pop("FRESING_UPDATE_URL", None)
    code = (
        "import addon_utils, importlib, json, os, sys\n"
        "name = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith('.fresing_render'))\n"
        "addon_utils.enable(name, default_set=True)\n"
        "c = importlib.import_module(name + '.core.updates')\n"
        "u = importlib.import_module(name + '.blender.updates')\n"
        "res = u.check_now()\n"
        "ok = ''\n"
        "if res.get('state') == 'available':\n"
        "    try:\n"
        "        c.download(res['url'], os.path.join(os.environ['UPD_WORK'], 'got.zip'), size=res['size'],"
        " sha256=res['sha256'])\n"
        "        ok = 'yes'\n"
        "    except Exception as e:\n"
        "        ok = 'failed: %s' % e\n"
        "res['downloaded'] = ok\n"
        "res['index_url_used'] = u.index_url()[0]\n"
        "json.dump(res, open(os.environ['UPD_OUT'], 'w'), indent=1)\n"
    )
    res_path = os.path.join(out, "github_check.json")
    run([blender, "--background", "--python-expr", code], dict(env, UPD_WORK=work, UPD_OUT=res_path), quiet=True)
    try:
        res = json.load(open(res_path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        check("check against GitHub ran", False, exc)
        return finish(work)
    print(json.dumps({k: v for k, v in res.items() if k != "changes"}, indent=1), flush=True)
    check("address is GitHub's newest release", res.get("index_url_used") == core.DEFAULT_INDEX_URL)
    check("GitHub offers an update", res.get("state") == "available", f"{res.get('state')} {res.get('message', '')}")
    if args.expect:
        check(f"offered version is {args.expect}", res.get("version") == args.expect, res.get("version"))
    check("download address is the release's", f"/releases/download/v{res.get('version')}/" in res.get("url", ""),
          res.get("url"))
    check("what's new read from the release", any(c.get("version") == res.get("version") for c in res.get("changes", [])))
    check("zip downloaded, size and SHA-256 right", res.get("downloaded") == "yes", res.get("downloaded"))
    return finish(work)


def finish(work) -> int:
    failed = [r for r in RESULTS if not r[1]]
    print(f"[UITEST] RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed", flush=True)
    for name, _ok, detail in failed:
        print(f"[UITEST] FAIL {name}: {detail[:500]}", flush=True)
    shutil.rmtree(work, ignore_errors=True)
    return 0 if RESULTS and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
