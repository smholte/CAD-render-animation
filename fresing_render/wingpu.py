"""Windows only (task 0296): the PC's graphics adapters and the per-user graphics preference of the app's programs.

* **Adapters** through DXGI (``dxgi.dll``, ctypes, no extra package): ``CreateDXGIFactory1`` -> ``EnumAdapters1`` ->
  ``GetDesc1`` per adapter (name, vendor and device id, own video memory, the software flag), ``EnumOutputs`` (how many
  monitors are plugged into it) and, where Windows has DXGI 1.6 (Windows 10 1803 and newer),
  ``IDXGIFactory6::EnumAdapterByGpuPreference(HIGH_PERFORMANCE)`` for Windows' own "high performance" order. Read
  only; nothing is created on a GPU. ``core/gpu_choice.py`` judges the list.
* **The preference** = what Settings > System > Display > Graphics writes: ``HKCU\\Software\\Microsoft\\DirectX\\
  UserGpuPreferences``, value name = the program's full path, REG_SZ ``GpuPreference=2;`` (High performance). Per user,
  no admin rights. ``ensure`` writes it for the install's ``blender.exe`` and ``Fresing Render.exe`` where the user has
  not chosen (the installer does the same, the uninstaller removes the values of its install folder);
  ``force`` = the notice's "Use the graphics card".

Never raises into the app: a fault returns an empty list / "" and is printed. Tested by GitHub's Windows job (no GPU
there: the Microsoft Basic Render Driver) through the self-test and the PC check, and with a fake registry on Linux.
"""

from __future__ import annotations

import os
import sys

from .core import gpu_choice

DXGI_ERROR_NOT_FOUND = 0x887A0002
DXGI_ADAPTER_FLAG_SOFTWARE = 2
DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE = 2
# vtable places (IUnknown 0-2, IDXGIObject 3-6, IDXGIFactory 7-11, IDXGIFactory1 12-13, IDXGIFactory2 14-24,
# IDXGIFactory3 25, IDXGIFactory4 26-27, IDXGIFactory5 28, IDXGIFactory6 29)
_RELEASE = 2
_ENUM_ADAPTERS1 = 12
_ENUM_BY_PREFERENCE = 29
# IDXGIAdapter: IUnknown 0-2, IDXGIObject 3-6, EnumOutputs 7, GetDesc 8, CheckInterfaceSupport 9; IDXGIAdapter1 GetDesc1 10
_ENUM_OUTPUTS = 7
_GET_DESC1 = 10
IID_IDXGIFactory1 = "{770aae78-f26f-4dba-a829-253c83d1b387}"
IID_IDXGIFactory6 = "{c1b6694f-ff09-44a9-b03c-77900a0a1d17}"
IID_IDXGIAdapter1 = "{29038f61-3839-4626-91fd-086879011a05}"


def log(*args) -> None:
    print("Fresing Render (graphics):", *args, flush=True)


# ---------------------------------------------------------------------------
# DXGI (ctypes)
# ---------------------------------------------------------------------------

class _Dxgi:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        self.HRESULT = ctypes.c_long

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class DESC1(ctypes.Structure):                   # DXGI_ADAPTER_DESC1
            _fields_ = [("Description", wintypes.WCHAR * 128), ("VendorId", wintypes.UINT),
                        ("DeviceId", wintypes.UINT), ("SubSysId", wintypes.UINT), ("Revision", wintypes.UINT),
                        ("DedicatedVideoMemory", ctypes.c_size_t), ("DedicatedSystemMemory", ctypes.c_size_t),
                        ("SharedSystemMemory", ctypes.c_size_t), ("AdapterLuid", LUID), ("Flags", wintypes.UINT)]

        self.GUID, self.DESC1 = GUID, DESC1
        self.dll = ctypes.WinDLL("dxgi.dll")
        self.ole32 = ctypes.WinDLL("ole32.dll")
        self.ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(GUID)]
        self.ole32.CLSIDFromString.restype = self.HRESULT
        self.dll.CreateDXGIFactory1.argtypes = [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        self.dll.CreateDXGIFactory1.restype = self.HRESULT

    def guid(self, text: str):
        g = self.GUID()
        hr = self.ole32.CLSIDFromString(text, self.ct.byref(g))
        if hr < 0:
            raise OSError(f"CLSIDFromString 0x{hr & 0xFFFFFFFF:08X}")
        return g

    def method(self, obj, index: int, *argtypes):
        """The COM method at ``index`` of ``obj``'s vtable, as a callable taking (obj, *args)."""
        ct = self.ct
        vtbl = ct.cast(ct.c_void_p(obj), ct.POINTER(ct.POINTER(ct.c_void_p))).contents
        proto = ct.WINFUNCTYPE(self.HRESULT, ct.c_void_p, *argtypes)
        return proto(vtbl[index])

    def release(self, obj) -> None:
        if obj:
            self.ct.WINFUNCTYPE(self.ct.c_ulong, self.ct.c_void_p)(
                self.ct.cast(self.ct.c_void_p(obj), self.ct.POINTER(self.ct.POINTER(self.ct.c_void_p))).contents[_RELEASE]
            )(obj)

    def query(self, obj, iid: str):
        """QueryInterface: the same object as another interface (None when it does not have it)."""
        ct = self.ct
        out = ct.c_void_p()
        hr = self.method(obj, 0, ct.POINTER(self.GUID), ct.POINTER(ct.c_void_p))(obj, ct.byref(self.guid(iid)),
                                                                                 ct.byref(out))
        return out.value if hr >= 0 and out.value else None

    def describe(self, adapter) -> dict:
        ct = self.ct
        d = self.DESC1()
        hr = self.method(adapter, _GET_DESC1, ct.POINTER(self.DESC1))(adapter, ct.byref(d))
        if hr < 0:
            raise OSError(f"GetDesc1 0x{hr & 0xFFFFFFFF:08X}")
        outputs = 0
        enum = self.method(adapter, _ENUM_OUTPUTS, ct.c_uint, ct.POINTER(ct.c_void_p))
        while outputs < 16:
            out = ct.c_void_p()
            hr = enum(adapter, outputs, ct.byref(out))
            if hr < 0 or not out.value:
                break
            self.release(out.value)
            outputs += 1
        return {"name": d.Description, "vendor_id": int(d.VendorId), "device_id": int(d.DeviceId),
                "dedicated_mb": d.DedicatedVideoMemory / 2 ** 20, "shared_mb": d.SharedSystemMemory / 2 ** 20,
                "software": bool(d.Flags & DXGI_ADAPTER_FLAG_SOFTWARE), "outputs": outputs,
                "luid": f"{d.AdapterLuid.HighPart:08x}{d.AdapterLuid.LowPart:08x}"}

    def adapters(self) -> list:
        ct = self.ct
        factory = ct.c_void_p()
        hr = self.dll.CreateDXGIFactory1(ct.byref(self.guid(IID_IDXGIFactory1)), ct.byref(factory))
        if hr < 0 or not factory.value:
            raise OSError(f"CreateDXGIFactory1 0x{hr & 0xFFFFFFFF:08X}")
        found = []
        try:
            enum = self.method(factory.value, _ENUM_ADAPTERS1, ct.c_uint, ct.POINTER(ct.c_void_p))
            for i in range(32):
                a = ct.c_void_p()
                hr = enum(factory.value, i, ct.byref(a))
                if (hr & 0xFFFFFFFF) == DXGI_ERROR_NOT_FOUND or hr < 0 or not a.value:
                    break
                try:
                    found.append(self.describe(a.value))
                except OSError as exc:              # one adapter that does not answer: the others still count
                    log(f"adapter {i}:", exc)
                finally:
                    self.release(a.value)
            try:
                order = self.high_performance_order(factory.value)
            except OSError as exc:
                log("Windows' high-performance order:", exc)
                order = []
        finally:
            self.release(factory.value)
        for info in found:
            info["high_performance"] = order.index(info["luid"]) if info["luid"] in order else -1
        return found

    def high_performance_order(self, factory) -> list:
        """The adapters' LUIDs in Windows' "high performance" order ([] before Windows 10 1803: no IDXGIFactory6)."""
        ct = self.ct
        f6 = self.query(factory, IID_IDXGIFactory6)
        if not f6:
            return []
        order = []
        try:
            enum = self.method(f6, _ENUM_BY_PREFERENCE, ct.c_uint, ct.c_int, ct.POINTER(self.GUID),
                               ct.POINTER(ct.c_void_p))
            iid = self.guid(IID_IDXGIAdapter1)
            for i in range(32):
                a = ct.c_void_p()
                hr = enum(f6, i, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE, ct.byref(iid), ct.byref(a))
                if hr < 0 or not a.value:
                    break
                try:
                    d = self.DESC1()
                    if self.method(a.value, _GET_DESC1, ct.POINTER(self.DESC1))(a.value, ct.byref(d)) >= 0:
                        order.append(f"{d.AdapterLuid.HighPart:08x}{d.AdapterLuid.LowPart:08x}")
                finally:
                    self.release(a.value)
        finally:
            self.release(f6)
        return order


_CACHE: dict = {}


def adapters(fresh: bool = False) -> list:
    """Windows: the PC's graphics adapters as ``gpu_choice.Adapter`` ([] on another system or when DXGI fails). Read
    once per start (a card does not come or go while the app runs); ``fresh`` reads again."""
    if sys.platform != "win32":
        return []
    if "list" in _CACHE and not fresh:
        return list(_CACHE["list"])
    try:
        rows = _Dxgi().adapters()
    except Exception as exc:  # noqa: BLE001 - a PC without DXGI 1.1, a blocked DLL: the app goes on without the list
        log("could not read the graphics adapters:", exc)
        rows = []
    out = [gpu_choice.Adapter(r["name"], r["vendor_id"], r["device_id"], r["dedicated_mb"], r["shared_mb"],
                              r["software"], r["outputs"], r.get("high_performance", -1), r["luid"]) for r in rows]
    _CACHE["list"] = out
    return list(out)


# ---------------------------------------------------------------------------
# The per-user graphics preference
# ---------------------------------------------------------------------------

class Registry:
    """``HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences`` through ``winreg`` (Windows only); a dict in tests."""

    def read(self, exe: str) -> str | None:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, gpu_choice.PREF_KEY, 0, winreg.KEY_READ) as key:
                value, kind = winreg.QueryValueEx(key, exe)
        except OSError:
            return None
        return value if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str) else None

    def write(self, exe: str, text: str) -> None:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, gpu_choice.PREF_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, exe, 0, winreg.REG_SZ, text)


def programs(binary_path: str) -> list:
    """The programs that start the app's window: Blender's ``blender.exe`` and the app's ``Fresing Render.exe`` next to
    it (when it is there), plus the running program itself – full paths, each once."""
    from . import winexe
    out = []
    if binary_path:
        blender = winexe.blender_exe_of(binary_path)
        for p in (os.path.abspath(binary_path), blender, winexe.copy_path(blender)):
            if p and os.path.isfile(p) and os.path.normcase(p) not in {os.path.normcase(x) for x in out}:
                out.append(p)
    return out


def preferences(exes, registry=None) -> dict:
    """{program: its preference text or None}."""
    reg = registry or Registry()
    out = {}
    for exe in exes:
        try:
            out[exe] = reg.read(exe)
        except Exception:  # noqa: BLE001
            out[exe] = None
    return out


def _apply(exes, rule, registry=None) -> list:
    reg = registry or Registry()
    done = []
    for exe in exes:
        try:
            new = rule(reg.read(exe))
            if new is not None:
                reg.write(exe, new)
                done.append(exe)
        except Exception as exc:  # noqa: BLE001 - never stop the app over a registry value
            log(f"could not set the graphics preference of {os.path.basename(exe)}:", exc)
    return done


def ensure(exes, registry=None) -> list:
    """High performance for these programs where the user has not chosen (the app's start). Returns what was written."""
    return _apply(exes, gpu_choice.auto_preference, registry)


def force(exes, registry=None) -> list:
    """High performance for these programs whatever was set (the notice's "Use the graphics card")."""
    return _apply(exes, gpu_choice.forced_preference, registry)
