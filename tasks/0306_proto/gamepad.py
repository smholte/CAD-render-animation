"""Study 0306 – reading a game controller on Windows from Blender's Python, with nothing installed.

Blender 5.2.3 has no event for a game controller (checked: none of the 196 event types; only the keyboard, the mouse,
a 3D mouse (NDOF_*) and VR controllers inside a VR session). Windows itself has two ways that need no package and no
driver beyond the controller's own, both reachable with ``ctypes`` (as the app already does for ``winplace.py``):

* **XInput** (``xinput1_4.dll``, in every Windows 10 / 11): Xbox controllers and the many pads that act as one
  (wired / wireless Xbox, most "PC" pads, a PlayStation pad through Steam). Up to 4 pads; two sticks, two analogue
  triggers, buttons. ``XInputGetState`` is a plain call that returns at once – it is read from the drive's timer.
* **winmm joystick** (``winmm.dll`` ``joyGetPosEx``): any HID game controller Windows lists under "Set up USB game
  controllers" – a PlayStation pad over USB / Bluetooth, a steering wheel with pedals (Logitech, Thrustmaster), a
  flight stick. Up to 16; six axes 0 … 65535, 32 buttons. Old, but still in Windows 11 and still works.

``open_pad()`` tries XInput first, then winmm, else returns None (the keys work as before). ``FakePad`` stands in for
tests on Linux. A real check needs the owner's PC: a PC-check line "Game controller" (move the stick, see the number).
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import Structure, c_byte, c_short, c_ubyte, c_uint, c_ushort, c_void_p, POINTER, byref, sizeof


class XINPUT_GAMEPAD(Structure):
    _fields_ = [("wButtons", c_ushort), ("bLeftTrigger", c_ubyte), ("bRightTrigger", c_ubyte),
                ("sThumbLX", c_short), ("sThumbLY", c_short), ("sThumbRX", c_short), ("sThumbRY", c_short)]


class XINPUT_STATE(Structure):
    _fields_ = [("dwPacketNumber", c_uint), ("Gamepad", XINPUT_GAMEPAD)]


class JOYINFOEX(Structure):
    _fields_ = [("dwSize", c_uint), ("dwFlags", c_uint), ("dwXpos", c_uint), ("dwYpos", c_uint),
                ("dwZpos", c_uint), ("dwRpos", c_uint), ("dwUpos", c_uint), ("dwVpos", c_uint),
                ("dwButtons", c_uint), ("dwButtonNumber", c_uint), ("dwPOV", c_uint),
                ("dwReserved1", c_uint), ("dwReserved2", c_uint)]


JOY_RETURNALL = 0xFF
XINPUT_A, XINPUT_B, XINPUT_X, XINPUT_Y = 0x1000, 0x2000, 0x4000, 0x8000
XINPUT_START, XINPUT_BACK = 0x0010, 0x0020


class State:
    """What the drive reads: steer -1 … 1 (+ = left), throttle 0 … 1, brake 0 … 1, and named buttons."""

    def __init__(self, steer=0.0, throttle=0.0, brake=0.0, buttons=()):
        self.steer, self.throttle, self.brake, self.buttons = steer, throttle, brake, set(buttons)


class XInputPad:
    kind = "XInput"

    def __init__(self, dll, index: int):
        self.dll, self.index = dll, index
        self._st = XINPUT_STATE()

    def read(self) -> State | None:
        if self.dll.XInputGetState(self.index, byref(self._st)) != 0:
            return None                                       # unplugged
        g = self._st.Gamepad
        b = set()
        for name, bit in (("A", XINPUT_A), ("B", XINPUT_B), ("X", XINPUT_X), ("Y", XINPUT_Y),
                          ("Start", XINPUT_START), ("Back", XINPUT_BACK)):
            if g.wButtons & bit:
                b.add(name)
        return State(steer=-g.sThumbLX / 32768.0, throttle=g.bRightTrigger / 255.0, brake=g.bLeftTrigger / 255.0,
                     buttons=b)


class WinmmPad:
    kind = "Game controller"

    def __init__(self, dll, index: int, pedals: bool = False):
        self.dll, self.index, self.pedals = dll, index, pedals
        self._ji = JOYINFOEX()
        self._ji.dwSize = sizeof(JOYINFOEX)
        self._ji.dwFlags = JOY_RETURNALL

    def read(self) -> State | None:
        if self.dll.joyGetPosEx(self.index, byref(self._ji)) != 0:
            return None
        ji = self._ji
        ax = lambda v: (v - 32767.5) / 32767.5                # noqa: E731
        steer = -ax(ji.dwXpos)
        # a wheel's pedals are usually separate axes (Y = throttle, R = brake, at rest = 65535);
        # a pad's triggers share Z (one goes up, the other down)
        if self.pedals:
            thr, brk = (65535 - ji.dwYpos) / 65535.0, (65535 - ji.dwRpos) / 65535.0
        else:
            z = ax(ji.dwZpos)
            thr, brk = max(-z, 0.0), max(z, 0.0)
        b = {f"B{i + 1}" for i in range(32) if ji.dwButtons & (1 << i)}
        return State(steer=steer, throttle=thr, brake=brk, buttons=b)


class FakePad:
    """A pad driven by a function of time (tests)."""
    kind = "Test pad"

    def __init__(self, fn):
        self.fn, self.t = fn, 0.0

    def read(self) -> State:
        return self.fn(self.t)


def open_pad():
    """The first controller found, or None. Never raises (a missing DLL, no pad: None)."""
    if sys.platform != "win32":
        return None
    try:
        for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                dll = ctypes.WinDLL(name)
                break
            except OSError:
                dll = None
        if dll is not None:
            dll.XInputGetState.argtypes = [c_uint, POINTER(XINPUT_STATE)]
            dll.XInputGetState.restype = c_uint
            for i in range(4):
                pad = XInputPad(dll, i)
                if pad.read() is not None:
                    return pad
        mm = ctypes.WinDLL("winmm")
        mm.joyGetPosEx.argtypes = [c_uint, POINTER(JOYINFOEX)]
        mm.joyGetPosEx.restype = c_uint
        for i in range(16):
            pad = WinmmPad(mm, i)
            if pad.read() is not None:
                return pad
    except Exception:          # noqa: BLE001 – a controller is a nice-to-have, never a failure
        return None
    return None


_ = (c_byte, c_void_p)         # keep the names importable for a later full version
