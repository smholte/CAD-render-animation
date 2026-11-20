"""'Fresing Render.exe': Blender's program under the app's own name and icon (task 0177).

Task Manager, the "Open with" list and the crash dialog show a program's name from its version resource, so the app
showed as "Blender". The installer (and, for a PC that updated with Update now, the app at start) makes a copy of
``blender.exe`` next to it – the same folder, so Blender finds its DLLs, ``blender.shared``, the ``5.2`` folder and the
portable settings exactly as before – with four changes:

* the Authenticode signature taken off (a changed file would otherwise carry a *broken* Blender signature);
* the PE subsystem set to GUI, so no console window opens (``blender.exe`` is a console program; Blender's
  ``blender-launcher.exe`` exists only to hide that window);
* the version resource: FileDescription / ProductName "Fresing Render", CompanyName "Fresing"; version numbers, the
  GPL notice and the original file name kept; Comments say what it is;
* both icon groups: the Fresing Render icon.

The copy is used only after it answered ``--version`` like Blender. It is not made, and an existing one is taken out of
use, while Windows 11's Smart App Control is on or evaluating (it blocks unsigned programs). A stamp file next to it
says what it was made from; a new Blender, icon or maker makes it again.

The byte work is plain Python (tested on Linux, ``tests/test_winexe.py``); the resources are written with Windows'
own ``BeginUpdateResourceW`` / ``UpdateResourceW`` / ``EndUpdateResourceW``.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import time

COPY_NAME = "Fresing Render.exe"
STAMP_NAME = "fresing-render-exe.json"
NAME = "Fresing Render"
COMPANY = "Fresing"
MAKER = 1                                   # raise when the copy must be made again on every PC
RT_ICON, RT_GROUP_ICON, RT_VERSION = 3, 14, 16
ICON_IDS_FROM = 101                         # Blender's own icons are 1..8: ours never replace them by number
SAC_KEY = r"SYSTEM\CurrentControlSet\Control\CI\Policy"
SAC_VALUE = "VerifiedAndReputablePolicyState"        # 0 off, 1 on, 2 evaluation


def log(*args) -> None:
    print("Fresing Render (program name):", *args, flush=True)


# ---------------------------------------------------------------------------
# The version resource (VS_VERSIONINFO): read, change, write – plain Python
# ---------------------------------------------------------------------------

class Node:
    """One block of a version resource: key, type (1 = text), value bytes, children."""

    def __init__(self, key: str, wtype: int, value: bytes = b"", children=None, value_len: int | None = None):
        self.key, self.wtype, self.value = key, wtype, value
        self.children = list(children or [])
        self.value_len = value_len                 # as stored (text: characters), None = worked out

    def text(self) -> str:
        return self.value.decode("utf-16-le").rstrip("\0")

    def set_text(self, text: str) -> None:
        self.value = (text + "\0").encode("utf-16-le")
        self.value_len = None

    def find(self, key: str):
        return next((c for c in self.children if c.key == key), None)


def _pad(n: int) -> int:
    return (4 - n % 4) % 4


def parse_node(data: bytes, off: int = 0) -> tuple[Node, int]:
    """One block at ``off``; returns it and the offset of the next one (aligned)."""
    length, vlen, wtype = struct.unpack_from("<HHH", data, off)
    end = off + length
    p = off + 6
    k = p
    while data[k:k + 2] != b"\0\0":
        k += 2
    key = data[p:k].decode("utf-16-le")
    p = k + 2
    p += _pad(p)
    nbytes = vlen * 2 if wtype == 1 else vlen
    nbytes = min(nbytes, max(0, end - p))
    value = data[p:p + nbytes]
    p += nbytes
    p += _pad(p)
    children = []
    while p < end:
        child, p = parse_node(data, p)
        children.append(child)
    nxt = end + _pad(end)
    return Node(key, wtype, value, children, vlen), nxt


def write_node(node: Node) -> bytes:
    key = (node.key + "\0").encode("utf-16-le")
    head = 6 + len(key)
    body = bytearray(key + b"\0" * _pad(head))
    body += node.value
    if node.children:
        body += b"\0" * _pad(6 + len(body))
        for i, child in enumerate(node.children):
            blob = write_node(child)
            body += blob
            if i < len(node.children) - 1:
                body += b"\0" * _pad(6 + len(body))
    vlen = node.value_len if node.value_len is not None else (len(node.value) // 2 if node.wtype == 1 else len(node.value))
    return struct.pack("<HHH", 6 + len(body), vlen, node.wtype) + bytes(body)


def parse_version(data: bytes) -> Node:
    root, _ = parse_node(data, 0)
    if root.key != "VS_VERSION_INFO":
        raise ValueError("not a version resource")
    return root


def strings(root: Node) -> dict[str, str]:
    """Every StringTable's entries (the first table wins a clash)."""
    out: dict[str, str] = {}
    sfi = root.find("StringFileInfo")
    for table in (sfi.children if sfi else []):
        for s in table.children:
            out.setdefault(s.key, s.text())
    return out


def rebranded(data: bytes, blender_version: str = "") -> bytes:
    """Blender's version resource with the app's name: FileDescription and ProductName "Fresing Render",
    CompanyName "Fresing", Comments saying it is Blender. Everything else (fixed version numbers, GPL notice,
    original file name, translation) stays."""
    root = parse_version(data)
    sfi = root.find("StringFileInfo")
    if sfi is None or not sfi.children:
        raise ValueError("version resource without strings")
    note = f"Blender {blender_version} started as Fresing Render" if blender_version else "Blender, started as Fresing Render"
    for table in sfi.children:
        have = {s.key: s for s in table.children}
        for key, value in (("FileDescription", NAME), ("ProductName", NAME), ("CompanyName", COMPANY),
                           ("Comments", note)):
            if key in have:
                have[key].set_text(value)
            else:
                n = Node(key, 1)
                n.set_text(value)
                table.children.append(n)
    return write_node(root)


# ---------------------------------------------------------------------------
# Icons: an .ico file as RT_GROUP_ICON + RT_ICON resources
# ---------------------------------------------------------------------------

def icon_resources(ico: bytes, first_id: int = ICON_IDS_FROM) -> tuple[bytes, list[tuple[int, bytes]]]:
    """The group (GRPICONDIR with 14-byte entries holding resource ids) and the images, one per size."""
    reserved, kind, count = struct.unpack_from("<HHH", ico, 0)
    if reserved != 0 or kind != 1 or count == 0:
        raise ValueError("not an .ico file")
    group = bytearray(struct.pack("<HHH", 0, 1, count))
    images = []
    for i in range(count):
        w, h, colours, res, planes, bpp, size, off = struct.unpack_from("<BBBBHHII", ico, 6 + 16 * i)
        rid = first_id + i
        group += struct.pack("<BBBBHHIH", w, h, colours, res, planes, bpp, size, rid)
        images.append((rid, bytes(ico[off:off + size])))
    return bytes(group), images


# ---------------------------------------------------------------------------
# PE header edits: signature off, GUI subsystem
# ---------------------------------------------------------------------------

def _optional_header(pe) -> tuple[int, int]:
    """(offset of the optional header, offset of the data directories)."""
    if bytes(pe[:2]) != b"MZ":
        raise ValueError("not a Windows program (no MZ)")
    lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    if bytes(pe[lfanew:lfanew + 4]) != b"PE\0\0":
        raise ValueError("not a Windows program (no PE header)")
    opt = lfanew + 24
    magic = struct.unpack_from("<H", pe, opt)[0]
    if magic == 0x20B:
        return opt, opt + 112
    if magic == 0x10B:
        return opt, opt + 96
    raise ValueError(f"unknown optional header {magic:#x}")


def subsystem(pe) -> int:
    opt, _ = _optional_header(pe)
    return struct.unpack_from("<H", pe, opt + 68)[0]


def signature(pe) -> tuple[int, int]:
    """The certificate table (file offset, size); (0, 0) when the program is not signed."""
    _, dirs = _optional_header(pe)
    return struct.unpack_from("<II", pe, dirs + 4 * 8)


def unsigned_gui(pe: bytearray) -> bytearray:
    """The program without its signature (entry zeroed, the certificate bytes cut from the end), with the GUI
    subsystem and checksum 0 (Windows checks a checksum only for drivers)."""
    opt, dirs = _optional_header(pe)
    off, size = signature(pe)
    if size:
        if off + size + 8 < len(pe) or off < 0x200:
            raise ValueError("the signature is not at the end of the file")
        del pe[off:]
        struct.pack_into("<II", pe, dirs + 4 * 8, 0, 0)
    struct.pack_into("<H", pe, opt + 68, 2)              # IMAGE_SUBSYSTEM_WINDOWS_GUI
    struct.pack_into("<I", pe, opt + 64, 0)              # CheckSum
    return pe


# ---------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------

def copy_path(blender_exe: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(blender_exe)), COPY_NAME)


def is_copy(path: str) -> bool:
    return os.path.basename(path or "").lower() == COPY_NAME.lower()


LOG_NAME = "Fresing Render console.log"


def output_to_file(binary_path: str) -> str:
    """Started as "Fresing Render.exe" from a shortcut (a windowed program), Python has no console: ``sys.stdout`` and
    ``sys.stderr`` are None, and code that writes to them would fail. They then go to a log file next to the program
    (the console text Window > Toggle System Console showed before), started afresh at every start. Returns its path."""
    if sys.stdout is not None and sys.stderr is not None:
        return ""
    path = os.path.join(os.path.dirname(os.path.abspath(binary_path or ".")), LOG_NAME)
    try:
        fh = open(path, "w", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        fh = open(os.devnull, "w", encoding="utf-8")
        path = os.devnull
    if sys.stdout is None:
        sys.stdout = fh
    if sys.stderr is None:
        sys.stderr = fh
    return path


def is_blender_program(path_or_name: str) -> bool:
    """Blender's program under either name: "blender…" or the app's copy (found by the independent review: five places
    took only names starting with "blender", so the queue and the mesh import broke when the app ran as the copy)."""
    name = os.path.basename(path_or_name or "").lower()
    return name.startswith("blender") or name == COPY_NAME.lower()


def blender_exe_of(binary_path: str) -> str:
    """``blender.exe`` next to the running program (the copy or Blender itself)."""
    folder = os.path.dirname(os.path.abspath(binary_path or ""))
    exe = os.path.join(folder, "blender.exe")
    return exe if os.path.isfile(exe) else (binary_path or "")


def console_exe(binary_path: str) -> str:
    """The program for runs that show their own console window (PC check, self-test): ``blender.exe``."""
    return blender_exe_of(binary_path) if is_copy(binary_path) else (binary_path or "")


def stamp_for(blender_exe: str, icon: str) -> dict:
    st = os.stat(blender_exe)
    with open(icon, "rb") as fh:
        icon_sha = hashlib.sha256(fh.read()).hexdigest()[:16]
    return {"maker": MAKER, "blender_size": st.st_size, "blender_mtime": int(st.st_mtime), "icon": icon_sha}


def read_stamp(blender_exe: str) -> dict:
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(blender_exe)), STAMP_NAME), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def usable(blender_exe: str) -> bool:
    """The copy exists and the stamp says it was made and checked for this blender.exe (any icon)."""
    st = read_stamp(blender_exe)
    try:
        b = os.stat(blender_exe)
    except OSError:
        return False
    return (os.path.isfile(copy_path(blender_exe)) and st.get("ok") is True
            and st.get("blender_size") == b.st_size and st.get("blender_mtime") == int(b.st_mtime))


def app_exe(binary_path: str) -> str:
    """The program that starts the app with a window: the copy when it is usable, else Blender's launcher, else the
    program itself."""
    if sys.platform != "win32" or not binary_path:
        return binary_path or ""
    blender = blender_exe_of(binary_path)
    if usable(blender) and sac_state() == 0:
        return copy_path(blender)
    launcher = os.path.join(os.path.dirname(os.path.abspath(blender)), "blender-launcher.exe")
    return launcher if os.path.isfile(launcher) else binary_path


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def sac_state() -> int:
    """Smart App Control: 0 off (or not on this Windows), 1 on, 2 evaluation. ``FRESING_SAC`` overrides (tests)."""
    fake = os.environ.get("FRESING_SAC", "")
    if fake.isdigit():
        return int(fake)
    if sys.platform != "win32":
        return 0
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SAC_KEY) as k:
            return int(winreg.QueryValueEx(k, SAC_VALUE)[0])
    except (OSError, ValueError):
        return 0


def _k32():
    import ctypes
    from ctypes import wintypes as wt
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.LoadLibraryExW.argtypes = [wt.LPCWSTR, wt.HANDLE, wt.DWORD]
    k.LoadLibraryExW.restype = wt.HMODULE
    k.FreeLibrary.argtypes = [wt.HMODULE]
    k.FindResourceW.argtypes = [wt.HMODULE, ctypes.c_void_p, ctypes.c_void_p]
    k.FindResourceW.restype = wt.HANDLE
    k.SizeofResource.argtypes = [wt.HMODULE, wt.HANDLE]
    k.SizeofResource.restype = wt.DWORD
    k.LoadResource.argtypes = [wt.HMODULE, wt.HANDLE]
    k.LoadResource.restype = wt.HANDLE
    k.LockResource.argtypes = [wt.HANDLE]
    k.LockResource.restype = ctypes.c_void_p
    k.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
    k.BeginUpdateResourceW.restype = wt.HANDLE
    k.UpdateResourceW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.WORD, ctypes.c_void_p, wt.DWORD]
    k.UpdateResourceW.restype = wt.BOOL
    k.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]
    k.EndUpdateResourceW.restype = wt.BOOL
    return ctypes, k


def read_resource(path: str, rtype: int, name) -> bytes:
    """A resource's bytes from a program file, read as data (nothing of it runs)."""
    ctypes, k = _k32()
    h = k.LoadLibraryExW(path, None, 0x00000002 | 0x00000020)   # AS_DATAFILE | AS_IMAGE_RESOURCE
    if not h:
        raise OSError(f"cannot open {path} as data ({ctypes.get_last_error()})")
    try:
        r = k.FindResourceW(h, name, rtype)
        if not r:
            raise OSError(f"resource {rtype}/{name} not found ({ctypes.get_last_error()})")
        size = k.SizeofResource(h, r)
        p = k.LockResource(k.LoadResource(h, r))
        return ctypes.string_at(p, size)
    finally:
        k.FreeLibrary(h)


def update_resources(path: str, items: list[tuple[int, object, int, bytes]]) -> None:
    """Replace or add resources (type, name, language, data) in a program file, all at once."""
    ctypes, k = _k32()
    h = k.BeginUpdateResourceW(path, False)
    if not h:
        raise OSError(f"BeginUpdateResource failed ({ctypes.get_last_error()})")
    ok = False
    try:
        for rtype, name, lang, data in items:
            buf = ctypes.create_string_buffer(data, len(data))
            if not k.UpdateResourceW(h, rtype, name, lang, buf, len(data)):
                raise OSError(f"UpdateResource {rtype}/{name} failed ({ctypes.get_last_error()})")
        ok = True
    finally:
        if not k.EndUpdateResourceW(h, not ok) and ok:
            raise OSError(f"EndUpdateResource failed ({ctypes.get_last_error()})")


def make(blender_exe: str, icon: str, dst: str) -> None:
    """Write the branded copy of ``blender_exe`` to ``dst`` (nothing checked yet)."""
    with open(blender_exe, "rb") as fh:
        pe = unsigned_gui(bytearray(fh.read()))
    with open(dst, "wb") as fh:
        fh.write(pe)
    version = read_resource(blender_exe, RT_VERSION, 1)
    blender_version = strings(parse_version(version)).get("ProductVersion", "")
    with open(icon, "rb") as fh:
        group, images = icon_resources(fh.read())
    lang = 1033
    items = [(RT_VERSION, 1, lang, rebranded(version, blender_version))]
    items += [(RT_ICON, rid, lang, img) for rid, img in images]
    items += [(RT_GROUP_ICON, "APPICON", lang, group), (RT_GROUP_ICON, 1, lang, group)]
    update_resources(dst, items)


def answers(exe: str, timeout: float = 90.0) -> tuple[bool, str]:
    """Start the program with ``--version`` (no window, nothing loaded but Blender's start): it must say Blender."""
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, cwd=os.path.dirname(exe),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    out = (r.stdout or "") + (r.stderr or "")
    return (r.returncode == 0 and "Blender" in out), (out.strip().splitlines() or [f"exit code {r.returncode}"])[0]


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def take_out(blender_exe: str, why: str) -> None:
    """Stop using the copy: the stamp is cleared (``usable`` is False) and the copy deleted when it is not running."""
    folder = os.path.dirname(os.path.abspath(blender_exe))
    _remove(os.path.join(folder, STAMP_NAME))
    copy = copy_path(blender_exe)
    if os.path.isfile(copy):
        for _ in range(6):                         # task 0242: a scan may hold it a moment after its first start
            _remove(copy)                          # (a running copy stays: ~0.5 s, and only while it runs)
            if not os.path.isfile(copy):
                break
            time.sleep(0.1)
        log("copy taken out of use:" if not os.path.isfile(copy) else
            "copy taken out of use (still there while it runs or is held):", why)


def swap_in(tmp: str, dst: str, old: str, tries: int = 30, wait: float = 0.1) -> None:
    """Put ``tmp`` in the place of ``dst``. A running copy (this app) cannot be replaced but can be renamed: it is moved
    aside to ``old`` first. Task 0242: a copy deleted a moment ago can still hold its name while Windows (a virus scan
    after its first start) has it open – "delete pending": the rename onto it is refused and the name is gone a moment
    later (WinError 2 in run 44776685998). Then it is simply tried again, for up to about 3 s."""
    for k in range(tries):
        try:
            os.replace(tmp, dst)
            return
        except PermissionError:
            if k == tries - 1:
                raise
        try:
            os.replace(dst, old)                   # the copy is running: move it aside
        except (FileNotFoundError, PermissionError):
            time.sleep(wait)                       # pending delete: wait for its name to go, then try again
            continue
        try:
            os.replace(tmp, dst)
            return
        except OSError:
            os.replace(old, dst)                   # put the running one back: never leave no copy at all
            raise


def ensure(blender_exe: str, icon: str) -> str:
    """Windows: the usable copy's path, made (or made again) when needed; '' when the app must stay on Blender's own
    programs (not Windows, Smart App Control, any fault – the reason is printed)."""
    if sys.platform != "win32" or not os.path.isfile(blender_exe) or not os.path.isfile(icon):
        return ""
    folder = os.path.dirname(os.path.abspath(blender_exe))
    dst = copy_path(blender_exe)
    old = os.path.join(folder, "Fresing Render.old.exe")
    _remove(old)                                   # left by an earlier swap while the copy was running
    sac = sac_state()
    if sac in (1, 2):
        take_out(blender_exe, "Smart App Control is " + ("on" if sac == 1 else "evaluating") +
                 " and blocks programs without a signature")
        return ""
    want = stamp_for(blender_exe, icon)
    have = read_stamp(blender_exe)
    if os.path.isfile(dst) and have.get("ok") is True and all(have.get(k) == v for k, v in want.items()):
        return dst
    same_blender = all(have.get(k) == want[k] for k in ("blender_size", "blender_mtime"))
    if have.get("gone") and same_blender:
        return ""                                  # it vanished once already for this Blender: not again
    if have.get("ok") is True and same_blender and not os.path.isfile(dst):
        # made, checked, and then removed by something else (an antivirus?): do not make it again for this Blender –
        # the app stays on Blender's own programs; Install.bat (a new Blender) or deleting the stamp tries again
        with open(os.path.join(folder, STAMP_NAME), "w", encoding="utf-8") as fh:
            json.dump(dict(want, ok=False, gone=True), fh)
        log("the copy was removed by something else (an antivirus?): the app stays on blender.exe")
        return ""
    tmp = os.path.join(folder, "Fresing Render.new.exe")
    try:
        _remove(tmp)
        make(blender_exe, icon, tmp)
        ok, said = answers(tmp)
        if not ok:
            raise OSError(f"the copy did not start ({said})")
        swap_in(tmp, dst, old)
        with open(os.path.join(folder, STAMP_NAME), "w", encoding="utf-8") as fh:
            json.dump(dict(want, ok=True, said=said), fh)
        log("made", dst, "-", said)
        return dst
    except Exception as exc:  # noqa: BLE001 - the app keeps Blender's own programs
        _remove(tmp)
        if usable(blender_exe):                    # an older copy for this Blender still works: keep it
            log("could not make the copy again, the earlier one stays:", exc)
            return dst
        take_out(blender_exe, str(exc))
        log("could not make the copy, the app stays on blender.exe:", exc)
        return ""
