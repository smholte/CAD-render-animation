"""The Fresing icon on Windows (task 0169): shortcuts, the app's windows and the taskbar.

* **Icon file.** ``brand/fresing-render.ico`` ships inside the extension (made by ``tools/make_app_icon.py``). The
  installer, and the app at every start, copy it to ``<install folder>\\fresing-render.ico`` - a place that does not
  move when an update replaces the extension - and every shortcut points there.
* **Shortcuts.** Install.bat makes them with that icon. A PC installed before 0169 got the new version through
  Update now, so the app refreshes them itself at start (Windows, started as Fresing Render, in a thread): the
  "Fresing Render" shortcut on the Desktop and in the Start menu, every ``.lnk`` in the Tools folder and among the
  pinned taskbar icons whose target lies inside the install folder gets the icon; the ones that start the app
  (``--app-template fresing_render``) also get the AppUserModelID ``APP_ID``. A shortcut that is already right is not
  written.
* **One shortcut only (task 0212).** The Desktop and the Start menu hold only "Fresing Render.lnk" (directly in
  Programs). The extras – self-test, PC check quick / full / heavy, safe start, user guide – live in the Tools folder
  of the install folder (``TOOLS``) and in the app's Fresing menu. Older installs had them on the Desktop and in a
  Start-menu folder "Fresing Render": ``tidy_plan`` removes those by name, only when their target lies inside the
  install folder, moves the app's own Start-menu shortcut out of that folder, and the empty folder goes. Install.bat
  does the same in PowerShell; the app at start for a PC that got the new version through Update now.
* **Windows and taskbar.** The running program is Blender's, so its windows carry Blender's icon. At start the app
  sets the Fresing icon on its windows (``WM_SETICON``) and on their window class (windows Blender opens later -
  render window, preferences - are of the same class), and the AppUserModelID on the process and on each window
  (with the relaunch command and icon, so "Pin to taskbar" from the running app pins Fresing Render). The taskbar
  then groups the window with the shortcuts of the same ID and shows their icon.

Never in a background run, never on another system, never with ``FRESING_NO_APPICON`` set; a fault only prints a line
(the app must start whatever happens here). The planning (``plan``, ``install_dir`` …) is plain Python and tested on
Linux; the ctypes/COM part runs only on Windows and is tested by GitHub's Windows job (``tools/appicon_test.py``).
"""

from __future__ import annotations

import os
import sys
import threading

APP_ID = "Fresing.Render"                  # the shortcuts' System.AppUserModel.ID = the process' and windows' ID
ICON_FILE = "fresing-render.ico"
HERE = os.path.dirname(os.path.abspath(__file__))
SHIPPED_ICON = os.path.join(HERE, "brand", ICON_FILE)
APP_ARGS = "--app-template fresing_render"
APP_LNK = "Fresing Render.lnk"                     # the one shortcut on the Desktop and in the Start menu (0212)
START_MENU_FOLDER = "Fresing Render"               # the Start-menu folder of installs before 0212 (cleaned up)
TOOLS_FOLDER = "Tools"                             # <install folder>\Tools: the extras (task 0212)
SAFE_START = "Safe start.lnk"                      # task 0177: the app on Blender's own launcher, never retargeted
# the Tools folder's shortcuts, by kind (task 0212)
TOOLS = {"selftest": "Self test.lnk", "quick": "PC check (quick).lnk", "full": "PC check (full).lnk",
         "heavy": "PC check (heavy).lnk", "safe": SAFE_START, "guide": "User guide.lnk"}
DESKTOP_NAMES = (APP_LNK,)
# what installs before 0212 made (removed by name when their target lies inside the install folder)
OLD_DESKTOP = ("Fresing Render - PC check.lnk", "Fresing Render - PC check (heavy).lnk")
OLD_START_MENU = ("Fresing Render - safe start.lnk", "Fresing Render - Self test.lnk",
                  "Fresing Render - PC check (quick).lnk", "Fresing Render - PC check (full).lnk",
                  "Fresing Render - PC check (heavy).lnk", "Fresing Render - User guide.lnk")
OLD_SAFE_START = "Fresing Render - safe start.lnk"
PINNED = os.path.join("Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar")
STATE = {"windows": 0, "shortcuts": "", "error": ""}       # what the start-up hook did (tests, the console)


def log(*args) -> None:
    print("Fresing Render (icon):", *args, flush=True)


# ---------------------------------------------------------------------------
# Plain Python: where things are, what a shortcut needs
# ---------------------------------------------------------------------------

def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path))) if path else ""


def is_inside(path: str, folder: str) -> bool:
    p, f = _norm(path), _norm(folder)
    return bool(p and f) and (p == f or p.startswith(f.rstrip("\\/") + os.sep))


def install_dir(binary_path: str) -> str:
    """The install folder of Install.bat (``%LOCALAPPDATA%\\FresingRender``: Blender's folder in it, and
    ``installed.txt``), '' for any other Blender."""
    if not binary_path:
        return ""
    parent = os.path.dirname(os.path.dirname(os.path.abspath(binary_path)))
    return parent if os.path.isfile(os.path.join(parent, "installed.txt")) else ""


def ensure_icon(folder: str, shipped: str = SHIPPED_ICON) -> str:
    """Copy the shipped icon into ``folder`` when it is missing or differs. Returns its path ('' if none)."""
    dst = os.path.join(folder, ICON_FILE)
    try:
        with open(shipped, "rb") as fh:
            new = fh.read()
        old = b""
        if os.path.isfile(dst):
            with open(dst, "rb") as fh:
                old = fh.read()
        if old != new:
            tmp = f"{dst}.{os.getpid()}.{threading.get_ident()}.new"
            try:
                with open(tmp, "wb") as fh:
                    fh.write(new)
                os.replace(tmp, dst)
                STATE["icon_changed"] = True            # shortcuts that already point here show a cached picture
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
        return dst
    except OSError as exc:
        log("could not copy the icon:", exc)
        return dst if os.path.isfile(dst) else ""


def tools_dir(folder: str) -> str:
    """The Tools folder of an install folder ('' for none)."""
    return os.path.join(folder, TOOLS_FOLDER) if folder else ""


def shortcut_paths(desktop: str, programs: str, appdata: str = "", tools: str = "") -> list[str]:
    """Every shortcut the app may refresh: the app's Desktop and Start-menu shortcut, the Tools folder (task 0212),
    the pinned taskbar icons."""
    out = [os.path.join(desktop, n) for n in DESKTOP_NAMES] if desktop else []
    if programs:
        out.append(os.path.join(programs, APP_LNK))
    folders = [tools] if tools else []
    if appdata:
        folders.append(os.path.join(appdata, PINNED))
    for folder in folders:
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        out += [os.path.join(folder, n) for n in names if n.lower().endswith(".lnk")]
    return [p for p in out if os.path.isfile(p)]


def old_shortcuts(desktop: str, programs: str) -> list[str]:
    """The shortcuts an install before 0212 made on the Desktop and in its Start-menu folder (those that are there),
    the app's own shortcut in that folder last."""
    out = [os.path.join(desktop, n) for n in OLD_DESKTOP] if desktop else []
    if programs:
        menu = os.path.join(programs, START_MENU_FOLDER)
        out += [os.path.join(menu, n) for n in OLD_START_MENU + (APP_LNK,)]
    return [p for p in out if os.path.isfile(p)]


def tidy_plan(found: dict, folder: str, programs: str) -> list[tuple[str, str, str]]:
    """What to do with an older install's shortcuts (task 0212). ``found``: {path: target as read ('' = could not be
    read)}. Returns (action, path, where): ("remove", path, "") or ("move", path, new path) for the app's own Start-menu
    shortcut when ``Programs\\Fresing Render.lnk`` is missing (it keeps its pin, icon and ID). A shortcut whose target
    lies outside the install folder - or cannot be read - is someone else's: left alone."""
    out = []
    new_app = os.path.join(programs, APP_LNK) if programs else ""
    for path, target in found.items():
        if not (target and folder and is_inside(target, folder)):
            continue
        if os.path.basename(path).lower() == APP_LNK.lower() and new_app and not os.path.isfile(new_app):
            out.append(("move", path, new_app))
        else:
            out.append(("remove", path, ""))
    return out


def tools_specs(folder: str, blender: str, desktop: str, extension: str) -> dict:
    """The Tools folder's shortcuts (task 0212), by kind: {kind: dict(path, target, arguments, workdir, description)}.
    ``blender``: blender.exe of the install (the console runs: self-test, PC checks); ``extension``: the installed
    extension's folder. A kind whose file is not there is left out (no self-test launcher, no guide)."""
    from .pccheck import core as pc_core
    tools = tools_dir(folder)
    bdir = os.path.dirname(blender) if blender else ""
    out = {}
    launcher = os.path.join(folder, "selftest_launcher.py")
    if blender and os.path.isfile(launcher):
        out["selftest"] = dict(target=blender, arguments=f'--background --python "{launcher}" -- "{desktop}"',
                               workdir=bdir, description="Check this PC and write a report on the Desktop")
    pc = os.path.join(extension, "pccheck", "launcher.py") if extension else ""
    if blender and pc and os.path.isfile(pc):
        for mode in ("quick", "full", "heavy"):
            out[mode] = dict(target=blender, arguments=pc_core.shortcut_arguments(pc, desktop, mode), workdir=bdir,
                             description=pc_core.SHORTCUT_TEXT[mode])
    gui = os.path.join(bdir, "blender-launcher.exe") if bdir else ""
    if gui and os.path.isfile(gui):
        out["safe"] = dict(target=gui, arguments=APP_ARGS, workdir=bdir, description=SAFE_TEXT)
    guide = os.path.join(extension, "guide", "user_guide.html") if extension else ""
    if guide and os.path.isfile(guide):
        out["guide"] = dict(target=guide, arguments="", workdir="", description="How to use Fresing Render, step by step")
    for kind, spec in out.items():
        spec["path"] = os.path.join(tools, TOOLS[kind])
    return out


def is_app_shortcut(arguments: str) -> bool:
    return APP_ARGS in " ".join((arguments or "").split())


def is_pinned(path: str) -> bool:
    return os.path.normcase(os.path.normpath(PINNED)) in _norm(path)


def plan(info: dict, folder: str, icon: str, pinned: bool = False, app_target: str = "",
         keep_target: bool = False) -> dict:
    """What one shortcut needs. ``info``: target, arguments, icon (path), icon_index, app_id as read.
    Returns {"icon": bool, "app_id": str or ""}: nothing for a shortcut whose target is outside the install folder
    (never touch someone else's shortcut). A pinned taskbar icon is changed only when it starts the app: a pin of
    plain Blender from this folder keeps Blender's icon, since it starts Blender, not Fresing Render.
    ``app_target`` (task 0177): the program the app's shortcuts start ("Fresing Render.exe", or Blender's launcher when
    the copy cannot be used); "target" in the answer is the new target, '' = keep it."""
    nothing = {"icon": False, "app_id": "", "target": ""}
    if not is_inside(info.get("target", ""), folder) or (pinned and not is_app_shortcut(info.get("arguments", ""))):
        return nothing
    wrong_icon = _norm(info.get("icon", "")) != _norm(icon) or int(info.get("icon_index") or 0) != 0
    app = is_app_shortcut(info.get("arguments", ""))
    want_id = APP_ID if app and info.get("app_id", "") != APP_ID else ""
    target = app_target if (app and app_target and is_inside(app_target, folder)
                            and _norm(info.get("target", "")) != _norm(app_target)) else ""
    if keep_target:
        target = ""
    return {"icon": wrong_icon, "app_id": want_id, "target": target}


def relaunch_command(binary_path: str) -> str:
    """How Windows starts the app again from a pin made on the running window: "Fresing Render.exe" when it can be
    used (task 0177), else Blender's launcher."""
    from . import winexe
    exe = winexe.app_exe(binary_path) if sys.platform == "win32" else ""
    if not exe:
        folder = os.path.dirname(os.path.abspath(binary_path))
        gui = os.path.join(folder, "blender-launcher.exe")
        exe = gui if os.path.isfile(gui) else binary_path
    return f'"{exe}" {APP_ARGS}'


# ---------------------------------------------------------------------------
# Windows: COM (shortcuts, property stores) and Win32 (window icons) with ctypes
# ---------------------------------------------------------------------------

class _Win:
    """ctypes set-up, made once on Windows."""

    def __init__(self):
        import ctypes
        import uuid
        from ctypes import wintypes as wt
        self.ct, self.wt = ctypes, wt

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

        class PROPERTYKEY(ctypes.Structure):
            _fields_ = [("fmtid", GUID), ("pid", wt.DWORD)]

        class PROPVARIANT(ctypes.Structure):          # 24 bytes on 64-bit: vt, 3 reserved, a 16-byte union
            _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                        ("r3", ctypes.c_ushort), ("p", ctypes.c_void_p), ("p2", ctypes.c_void_p)]

        def guid(text):
            u = uuid.UUID(text)
            return GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))

        self.GUID, self.PROPERTYKEY, self.PROPVARIANT, self.guid = GUID, PROPERTYKEY, PROPVARIANT, guid
        self.CLSID_ShellLink = guid("00021401-0000-0000-C000-000000000046")
        self.IID_IShellLinkW = guid("000214F9-0000-0000-C000-000000000046")
        self.IID_IPersistFile = guid("0000010b-0000-0000-C000-000000000046")
        self.IID_IPropertyStore = guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
        fmt = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"           # PKEY_AppUserModel_*
        self.PKEY_ID = PROPERTYKEY(guid(fmt), 5)
        self.PKEY_RELAUNCH_COMMAND = PROPERTYKEY(guid(fmt), 2)
        self.PKEY_RELAUNCH_ICON = PROPERTYKEY(guid(fmt), 3)
        self.PKEY_RELAUNCH_NAME = PROPERTYKEY(guid(fmt), 4)

        self.ole32 = ctypes.WinDLL("ole32")
        self.shell32 = ctypes.WinDLL("shell32")
        self.user32 = ctypes.WinDLL("user32")
        self.kernel32 = ctypes.WinDLL("kernel32")
        self.kernel32.GetCurrentProcessId.restype = wt.DWORD
        self.kernel32.GetCurrentThreadId.restype = wt.DWORD
        o, s, u = self.ole32, self.shell32, self.user32
        o.CoInitializeEx.argtypes = [ctypes.c_void_p, wt.DWORD]
        o.CoInitializeEx.restype = ctypes.c_long
        o.CoUninitialize.argtypes = []
        o.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, wt.DWORD, ctypes.POINTER(GUID),
                                       ctypes.POINTER(ctypes.c_void_p)]
        o.CoCreateInstance.restype = ctypes.c_long
        o.PropVariantClear.argtypes = [ctypes.POINTER(PROPVARIANT)]
        o.PropVariantClear.restype = ctypes.c_long
        o.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        s.SHGetPropertyStoreForWindow.argtypes = [wt.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        s.SHGetPropertyStoreForWindow.restype = ctypes.c_long
        s.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]
        s.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        s.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        s.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
        s.SHChangeNotify.argtypes = [ctypes.c_long, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        s.SHChangeNotify.restype = None
        u.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        u.LoadImageW.restype = wt.HANDLE
        u.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
        u.SendMessageW.restype = wt.LPARAM
        u.SetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_void_p]
        u.SetClassLongPtrW.restype = ctypes.c_void_p
        u.GetSystemMetrics.argtypes = [ctypes.c_int]
        u.GetSystemMetrics.restype = ctypes.c_int
        u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        u.GetWindowThreadProcessId.restype = wt.DWORD
        u.IsWindowVisible.argtypes = [wt.HWND]
        u.IsWindowVisible.restype = wt.BOOL
        u.GetWindow.argtypes = [wt.HWND, ctypes.c_uint]
        u.GetWindow.restype = wt.HWND
        self.WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        u.EnumWindows.argtypes = [self.WNDENUMPROC, wt.LPARAM]
        u.EnumWindows.restype = wt.BOOL
        try:
            u.GetDpiForWindow.argtypes = [wt.HWND]
            u.GetDpiForWindow.restype = ctypes.c_uint
            u.GetSystemMetricsForDpi.argtypes = [ctypes.c_int, ctypes.c_uint]
            u.GetSystemMetricsForDpi.restype = ctypes.c_int
            self.per_dpi = True
        except AttributeError:                              # before Windows 10 1607
            self.per_dpi = False

    # -- COM helpers --------------------------------------------------------
    def method(self, obj, index: int, *argtypes):
        """Method ``index`` of the COM object ``obj`` (its vtable), returning an HRESULT."""
        ct = self.ct
        vtbl = ct.cast(obj, ct.POINTER(ct.POINTER(ct.c_void_p)))[0]
        proto = ct.WINFUNCTYPE(ct.c_long, ct.c_void_p, *argtypes)
        fn = proto(vtbl[index])

        def call(*args):
            hr = fn(obj, *args)
            if hr < 0:
                raise OSError(f"COM error 0x{hr & 0xFFFFFFFF:08X}")
            return hr
        return call

    def release(self, obj) -> None:
        if obj:
            ct = self.ct
            vtbl = ct.cast(obj, ct.POINTER(ct.POINTER(ct.c_void_p)))[0]
            ct.WINFUNCTYPE(ct.c_ulong, ct.c_void_p)(vtbl[2])(obj)

    def query(self, obj, iid):
        out = self.ct.c_void_p()
        self.method(obj, 0, self.ct.POINTER(self.GUID), self.ct.POINTER(self.ct.c_void_p))(
            self.ct.byref(iid), self.ct.byref(out))
        return out

    def com_init(self) -> bool:
        """Start COM on this thread. True when it must be undone (``CoUninitialize``)."""
        hr = self.ole32.CoInitializeEx(None, 0x2)               # COINIT_APARTMENTTHREADED
        return hr in (0, 1)                                    # S_OK / S_FALSE; RPC_E_CHANGED_MODE: leave it

    # -- property stores ----------------------------------------------------
    def get_string(self, store, key) -> str:
        ct = self.ct
        pv = self.PROPVARIANT()
        self.method(store, 5, ct.POINTER(self.PROPERTYKEY), ct.POINTER(self.PROPVARIANT))(ct.byref(key), ct.byref(pv))
        try:
            return ct.wstring_at(pv.p) if pv.vt == 31 and pv.p else ""          # VT_LPWSTR
        finally:
            self.ole32.PropVariantClear(ct.byref(pv))

    def set_string(self, store, key, value: str) -> None:
        ct = self.ct
        buf = ct.create_unicode_buffer(value)
        pv = self.PROPVARIANT()
        pv.vt = 31
        pv.p = ct.cast(buf, ct.c_void_p)
        self.method(store, 6, ct.POINTER(self.PROPERTYKEY), ct.POINTER(self.PROPVARIANT))(ct.byref(key), ct.byref(pv))

    # -- shortcuts ----------------------------------------------------------
    def open_link(self, path: str, write: bool, new: bool = False):
        ct = self.ct
        link = ct.c_void_p()
        hr = self.ole32.CoCreateInstance(ct.byref(self.CLSID_ShellLink), None, 0x1,       # CLSCTX_INPROC_SERVER
                                         ct.byref(self.IID_IShellLinkW), ct.byref(link))
        if hr < 0:
            raise OSError(f"CoCreateInstance(ShellLink) 0x{hr & 0xFFFFFFFF:08X}")
        try:
            pf = self.query(link, self.IID_IPersistFile)
        except OSError:
            self.release(link)
            raise
        if new:                                        # a new shortcut: nothing to load
            return link, pf
        try:
            self.method(pf, 5, self.wt.LPCWSTR, self.wt.DWORD)(path, 0x2 if write else 0x0)   # Load, STGM_READWRITE
        except OSError:
            self.release(pf)
            self.release(link)
            raise
        return link, pf

    def read_link(self, link) -> dict:
        ct, wt = self.ct, self.wt
        n = 2048
        target, args, icon = (ct.create_unicode_buffer(n) for _ in range(3))
        index = ct.c_int(0)
        self.method(link, 3, wt.LPWSTR, ct.c_int, ct.c_void_p, wt.DWORD)(target, n, None, 0)      # GetPath
        self.method(link, 10, wt.LPWSTR, ct.c_int)(args, n)                                         # GetArguments
        self.method(link, 16, wt.LPWSTR, ct.c_int, ct.POINTER(ct.c_int))(icon, n, ct.byref(index))  # GetIconLocation
        app_id = ""
        try:
            store = self.query(link, self.IID_IPropertyStore)
            try:
                app_id = self.get_string(store, self.PKEY_ID)
            finally:
                self.release(store)
        except OSError:
            pass
        return {"target": target.value, "arguments": args.value, "icon": icon.value, "icon_index": index.value,
                "app_id": app_id}

    def notify(self, path: str) -> None:
        """Tell Explorer a shortcut changed (its icon is cached)."""
        try:
            buf = self.ct.create_unicode_buffer(path)
            self.shell32.SHChangeNotify(0x00002000, 0x0005, self.ct.cast(buf, self.ct.c_void_p), None)  # UPDATEITEM, PATHW
        except Exception:  # noqa: BLE001
            pass

    # -- windows ------------------------------------------------------------
    def own_windows(self) -> list[int]:
        """The visible top-level windows of this process that no other window owns."""
        ct, u = self.ct, self.user32
        me = self.kernel32.GetCurrentProcessId()
        thread = self.kernel32.GetCurrentThreadId()
        found: list[int] = []

        def each(hwnd, _lparam):
            pid = self.wt.DWORD()
            # this thread's own windows only: Blender's windows belong to its main thread (where this runs); a
            # console window reports its client process but belongs to conhost - a message to it could block
            tid = u.GetWindowThreadProcessId(hwnd, ct.byref(pid))
            if pid.value == me and tid == thread and u.IsWindowVisible(hwnd) and not u.GetWindow(hwnd, 4):  # GW_OWNER
                found.append(hwnd)
            return True

        u.EnumWindows(self.WNDENUMPROC(each), 0)
        return found

    def icon_size(self, hwnd, big: bool) -> int:
        idx = 11 if big else 49                                # SM_CXICON / SM_CXSMICON
        if self.per_dpi:
            dpi = self.user32.GetDpiForWindow(hwnd) or 96
            return self.user32.GetSystemMetricsForDpi(idx, dpi)
        return self.user32.GetSystemMetrics(idx)


_W: _Win | None = None


def _win() -> _Win:
    global _W
    if _W is None:
        _W = _Win()
    return _W


def read_shortcut(path: str) -> dict:
    """Windows: what a shortcut holds (target, arguments, icon, icon_index, app_id)."""
    w = _win()
    undo = w.com_init()
    try:
        link, pf = w.open_link(path, write=False)
        try:
            return w.read_link(link)
        finally:
            w.release(pf)
            w.release(link)
    finally:
        if undo:
            w.ole32.CoUninitialize()


def fix_shortcut(path: str, folder: str, icon: str, app_target: str = "") -> str:
    """Windows: give one shortcut the Fresing icon (and the app's ID when it starts the app) when it needs them.
    Returns what was changed ('' = nothing)."""
    w = _win()
    link, pf = w.open_link(path, write=True)
    try:
        todo = plan(w.read_link(link), folder, icon, pinned=is_pinned(path), app_target=app_target,
                    keep_target=os.path.basename(path).lower() in (SAFE_START.lower(), OLD_SAFE_START.lower()))
        if not (todo["icon"] or todo["app_id"] or todo["target"]):
            return ""
        done = []
        if todo["target"]:
            w.method(link, 20, w.wt.LPCWSTR)(todo["target"])                          # SetPath
            done.append("starts " + os.path.basename(todo["target"]))
        if todo["icon"]:
            w.method(link, 17, w.wt.LPCWSTR, w.ct.c_int)(icon, 0)                     # SetIconLocation
            done.append("icon")
        if todo["app_id"]:
            store = w.query(link, w.IID_IPropertyStore)
            try:
                w.set_string(store, w.PKEY_ID, todo["app_id"])
                w.method(store, 7)()                                                   # Commit
            finally:
                w.release(store)
            done.append("app id")
        w.method(pf, 6, w.wt.LPCWSTR, w.wt.BOOL)(None, True)                          # Save
    finally:
        w.release(pf)
        w.release(link)
    w.notify(path)
    return " + ".join(done)


def refresh_shortcuts(folder: str, icon: str, paths: list[str], app_target: str = "") -> list[str]:
    """Windows: ``fix_shortcut`` on every path; one fault does not stop the others. Returns "<name>: <what>".
    Without an icon file nothing is written (an empty icon path would take the icon away)."""
    if not icon or not os.path.isfile(icon):
        log("no icon file: shortcuts left as they are")
        return []
    w = _win()
    undo = w.com_init()
    out = []
    try:
        for path in paths:
            try:
                what = fix_shortcut(path, folder, icon, app_target)
                if what:
                    out.append(f"{os.path.basename(path)}: {what}")
            except Exception as exc:  # noqa: BLE001 - a locked or broken shortcut: leave it
                log(f"could not refresh {os.path.basename(path)}:", exc)
    finally:
        if undo:
            w.ole32.CoUninitialize()
    return out


def known_folders() -> tuple[str, str, str]:
    """Windows: Desktop, Start-menu Programs, Roaming AppData."""
    from .pccheck import runner
    return (runner._known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641"),        # FOLDERID_Desktop
            runner._known_folder("A77F5D77-2E2B-44C3-A6A2-ABA601054A51"),        # FOLDERID_Programs
            runner._known_folder("3EB685DB-65F9-4CF6-A03A-E3EF65729F3D"))        # FOLDERID_RoamingAppData


def make_shortcut(path: str, target: str, arguments: str, workdir: str, icon: str, description: str) -> None:
    """Windows: a new shortcut (the safe start for PCs that updated with Update now)."""
    w = _win()
    undo = w.com_init()
    try:
        link, pf = w.open_link(path, write=True, new=True)
        try:
            w.method(link, 20, w.wt.LPCWSTR)(target)                     # SetPath
            w.method(link, 11, w.wt.LPCWSTR)(arguments)                  # SetArguments
            w.method(link, 9, w.wt.LPCWSTR)(workdir)                     # SetWorkingDirectory
            w.method(link, 7, w.wt.LPCWSTR)(description)                 # SetDescription
            w.method(link, 17, w.wt.LPCWSTR, w.ct.c_int)(icon, 0)        # SetIconLocation
            w.method(pf, 6, w.wt.LPCWSTR, w.wt.BOOL)(path, True)         # Save
        finally:
            w.release(pf)
            w.release(link)
    finally:
        if undo:
            w.ole32.CoUninitialize()


SAFE_TEXT = ("Starts Fresing Render with Blender's own program. Use it only if Fresing Render does not start from its "
             "usual shortcut (for example when a virus scanner removed Fresing Render.exe)")


def tidy_old(folder: str, desktop: str, programs: str) -> list[str]:
    """Windows (task 0212): an older install's extra shortcuts on the Desktop and in the Start-menu folder "Fresing
    Render" removed (only ours: target inside the install folder), the app's own Start-menu shortcut moved directly
    into Programs, the folder removed when it is empty. Returns what was done."""
    found = {}
    for path in old_shortcuts(desktop, programs):
        try:
            found[path] = read_shortcut(path).get("target", "")
        except Exception as exc:  # noqa: BLE001 - unreadable: someone else's or broken, leave it
            log(f"could not read {os.path.basename(path)}:", exc)
            found[path] = ""
    done = []
    for action, path, where in tidy_plan(found, folder, programs):
        try:
            if action == "move":
                os.replace(path, where)
                done.append(f"{os.path.basename(path)}: moved out of the Start-menu folder")
            else:
                os.remove(path)
                done.append(f"{os.path.basename(path)}: removed (now in the Tools folder)")
        except OSError as exc:
            log(f"could not tidy {os.path.basename(path)}:", exc)
    menu = os.path.join(programs, START_MENU_FOLDER) if programs else ""
    if menu and os.path.isdir(menu):
        try:
            left = [n for n in os.listdir(menu) if n.lower() != "desktop.ini"]     # Explorer's own file
            if not left:
                for n in os.listdir(menu):
                    os.remove(os.path.join(menu, n))
                os.rmdir(menu)
                done.append("Start-menu folder Fresing Render: removed")
        except OSError as exc:
            log("could not remove the old Start-menu folder:", exc)
    return done


def ensure_tools(folder: str, binary_path: str, desktop: str, icon: str) -> list[str]:
    """Windows (task 0212): the Tools folder made and its shortcuts made when missing (a PC that got this version
    through Update now). One that is there is left as it is (``refresh_shortcuts`` fixes its icon)."""
    from . import winexe
    blender = winexe.blender_exe_of(binary_path)
    specs = tools_specs(folder, blender, desktop, HERE)
    if not specs:
        return []
    os.makedirs(tools_dir(folder), exist_ok=True)
    done = []
    for kind, spec in specs.items():
        if os.path.isfile(spec["path"]):
            continue
        try:
            make_shortcut(spec["path"], spec["target"], spec["arguments"], spec["workdir"], icon, spec["description"])
            done.append(f"{TOOLS[kind]}: made in the Tools folder")
        except Exception as exc:  # noqa: BLE001
            log(f"could not make {TOOLS[kind]}:", exc)
    return done


def ensure_installed_apps(folder: str, icon: str = "") -> list[str]:
    """Windows (task 0265): the entry in Settings > Apps > Installed apps, made for an install that does not have it
    yet and its version set after an update (``core/installed_apps.py``)."""
    from . import __version__
    from .core import installed_apps
    return installed_apps.ensure(folder, str(__version__), icon if icon and os.path.isfile(icon) else "")


def app_target_for(binary_path: str, icon: str) -> str:
    """Windows (task 0177): make "Fresing Render.exe" when needed; the program the app's shortcuts should start – the
    copy, or Blender's launcher when the copy cannot be used ('' when there is neither)."""
    from . import winexe
    blender = winexe.blender_exe_of(binary_path)
    copy = winexe.ensure(blender, icon)
    if copy:
        return copy
    launcher = os.path.join(os.path.dirname(os.path.abspath(blender)), "blender-launcher.exe")
    return launcher if os.path.isfile(launcher) else ""


def refresh_installed(binary_path: str, desktop: str = "", programs: str = "", appdata: str = "",
                      icon: str = "") -> list[str]:
    """Windows: the icon file into the install folder, "Fresing Render.exe" made (task 0177), and every shortcut of
    this install refreshed (the app at start for PCs installed before 0169 / 0177); an older install's extra shortcuts
    tidied away and the Tools folder made (task 0212)."""
    folder = install_dir(binary_path)
    if not folder:
        return []
    icon = icon or ensure_icon(folder)
    if not (desktop and programs):
        d, p, a = known_folders()
        desktop, programs, appdata = desktop or d, programs or p, appdata or a
    done = []
    # task 0212: tidy and the Tools folder need no icon file of their own (the shipped one serves for new shortcuts)
    for name, step in (("tidy", lambda: tidy_old(folder, desktop, programs)),
                       ("tools", lambda: ensure_tools(folder, binary_path, desktop, icon or SHIPPED_ICON)),
                       ("installed-apps entry", lambda: ensure_installed_apps(folder, icon))):
        try:
            done += step()
        except Exception as exc:  # noqa: BLE001 - one step's fault does not stop the others
            log(f"could not {name} the shortcuts:", exc)
    if not icon:
        return done
    target = app_target_for(binary_path, icon)
    STATE["app_exe"] = target
    paths = shortcut_paths(desktop, programs, appdata, tools_dir(folder))
    done = refresh_shortcuts(folder, icon, paths, target) + done
    if STATE.pop("icon_changed", False):
        redraw_icons(paths)
        done.append("icon file replaced: Explorer told to redraw")
    return done


def redraw_icons(paths: list[str]) -> None:
    """Windows: the icon file changed under shortcuts that point at it (a new icon in an update): tell Explorer to
    draw those shortcuts again, and to drop its icon cache (SHCNE_ASSOCCHANGED)."""
    w = _win()
    for path in paths:
        w.notify(path)
    try:
        w.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)       # SHCNE_ASSOCCHANGED, SHCNF_IDLIST
    except Exception:  # noqa: BLE001
        pass


def set_process_app_id(app_id: str = APP_ID) -> None:
    hr = _win().shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    if hr < 0:
        raise OSError(f"SetCurrentProcessExplicitAppUserModelID 0x{hr & 0xFFFFFFFF:08X}")


def process_app_id() -> str:
    w = _win()
    p = w.ct.c_void_p()
    if w.shell32.GetCurrentProcessExplicitAppUserModelID(w.ct.byref(p)) < 0 or not p.value:
        return ""
    try:
        return w.ct.wstring_at(p.value)
    finally:
        w.ole32.CoTaskMemFree(p)


def load_icon(path: str, size: int) -> int:
    h = _win().user32.LoadImageW(None, path, 1, size, size, 0x10)        # IMAGE_ICON, LR_LOADFROMFILE
    if not h:
        raise OSError(f"LoadImage failed for {path}")
    return h


def set_window_icon(hwnd: int, icon: str, *, relaunch: str = "", app_id: str = APP_ID) -> dict:
    """Windows: the Fresing icon on one window (big + small, and on its window class so later windows of the class
    have it too) and the app's ID on the window (+ how to start it again from a pin). Returns the icon handles."""
    w = _win()
    big, small = load_icon(icon, w.icon_size(hwnd, True)), load_icon(icon, w.icon_size(hwnd, False))
    w.user32.SendMessageW(hwnd, 0x0080, 1, big)                  # WM_SETICON, ICON_BIG
    w.user32.SendMessageW(hwnd, 0x0080, 0, small)                # ICON_SMALL
    w.user32.SetClassLongPtrW(hwnd, -14, big)                    # GCLP_HICON
    w.user32.SetClassLongPtrW(hwnd, -34, small)                  # GCLP_HICONSM
    if app_id:
        undo = w.com_init()
        try:
            store = w.ct.c_void_p()
            hr = w.shell32.SHGetPropertyStoreForWindow(hwnd, w.ct.byref(w.IID_IPropertyStore), w.ct.byref(store))
            if hr < 0:
                raise OSError(f"SHGetPropertyStoreForWindow 0x{hr & 0xFFFFFFFF:08X}")
            try:
                if relaunch:            # the relaunch keys only count when the ID is set too: set them first
                    w.set_string(store, w.PKEY_RELAUNCH_COMMAND, relaunch)
                    w.set_string(store, w.PKEY_RELAUNCH_ICON, icon + ",0")
                    w.set_string(store, w.PKEY_RELAUNCH_NAME, "Fresing Render")
                w.set_string(store, w.PKEY_ID, app_id)
            finally:
                w.release(store)
        finally:
            if undo:
                w.ole32.CoUninitialize()
    return {"big": big, "small": small}


def window_icon(hwnd: int, big: bool = True) -> int:
    return _win().user32.SendMessageW(hwnd, 0x007F, 1 if big else 0, 0)       # WM_GETICON


def window_app_id(hwnd: int) -> str:
    w = _win()
    undo = w.com_init()
    try:
        store = w.ct.c_void_p()
        if w.shell32.SHGetPropertyStoreForWindow(hwnd, w.ct.byref(w.IID_IPropertyStore), w.ct.byref(store)) < 0:
            return ""
        try:
            return w.get_string(store, w.PKEY_ID)
        finally:
            w.release(store)
    finally:
        if undo:
            w.ole32.CoUninitialize()


def own_windows() -> list[int]:
    return _win().own_windows()


# ---------------------------------------------------------------------------
# Start-up hook (the extension's register())
# ---------------------------------------------------------------------------

def wanted(platform: str, background: bool, template: str, env: dict) -> bool:
    """Whether the start-up hook runs: Windows, a window (not background), started as Fresing Render."""
    return platform == "win32" and not background and template == "fresing_render" and not env.get("FRESING_NO_APPICON")


def _template() -> str:
    import bpy
    try:
        return bpy.context.preferences.app_template or ""
    except AttributeError:
        return ""


def _icon_for(binary_path: str) -> str:
    """The icon in the install folder (copied there if needed), else the one inside the extension."""
    folder = install_dir(binary_path)
    icon = ensure_icon(folder) if folder else ""
    return icon if icon and os.path.isfile(icon) else SHIPPED_ICON


def _apply_windows(binary_path: str, icon: str) -> bool:
    """Set the icon on the app's windows once one exists. True when done (or given up)."""
    folder = install_dir(binary_path)
    if not os.path.isfile(icon):
        return True
    hwnds = own_windows()
    if not hwnds:
        return False
    relaunch = relaunch_command(binary_path) if folder else ""
    for hwnd in hwnds:
        set_window_icon(hwnd, icon, relaunch=relaunch)
    STATE["windows"] = len(hwnds)
    log(f"set on {len(hwnds)} window(s)")
    return True


def startup() -> bool:
    """Called from the extension's register(). Returns whether it scheduled anything."""
    import bpy
    if sys.platform != "win32" or bpy.app.background or os.environ.get("FRESING_NO_APPICON"):
        return False
    tries = {"n": 0, "icon": ""}

    def tick():
        tries["n"] += 1
        try:
            if not wanted(sys.platform, bpy.app.background, _template(), os.environ):
                return None
            if tries["n"] == 1:
                set_process_app_id()                 # windows made from now on
                # the icon file is copied here, once, before the shortcut thread starts (no two writers)
                tries["icon"] = _icon_for(bpy.app.binary_path)
                if install_dir(bpy.app.binary_path) and tries["icon"] != SHIPPED_ICON:
                    threading.Thread(target=_shortcuts, args=(bpy.app.binary_path, tries["icon"]), daemon=True).start()
            if _apply_windows(bpy.app.binary_path, tries["icon"]) or tries["n"] >= 30:
                return None
        except Exception as exc:  # noqa: BLE001 - never stop the app from starting
            STATE["error"] = str(exc)
            log("could not set the icon:", exc)
            return None
        return 1.0

    bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
    return True


def _shortcuts(binary_path: str, icon: str) -> None:
    try:
        done = refresh_installed(binary_path, icon=icon)
        STATE["shortcuts"] = "; ".join(done)
        if done:
            log("shortcuts refreshed:", "; ".join(done))
    except Exception as exc:  # noqa: BLE001
        STATE["error"] = str(exc)
        log("could not refresh the shortcuts:", exc)
