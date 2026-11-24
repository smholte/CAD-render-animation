"""Always the graphics card (task 0296): the rules, no Blender, no Windows – tested with made-up adapter lists.

Two separate choices decide how fast the app is on a PC that has built-in graphics (in the processor) **and** a
graphics card (NVIDIA, AMD, Intel Arc):

1. **Which GPU draws the window** (the 3D view, EEVEE, Live preview's display). Windows decides per program. Blender's
   ``blender.exe`` (5.2.3, measured) exports ``NvOptimusEnablement = 1``, which asks NVIDIA's driver for the card, but
   has no ``AmdPowerXpressRequestHighPerformance``: on a PC with AMD built-in graphics and an AMD card, Windows may
   draw on the built-in one. The app writes the per-user Windows preference "High performance" for its programs
   (``HKCU\\Software\\Microsoft\\DirectX\\UserGpuPreferences``, value name = the program's full path, data
   ``GpuPreference=2;`` – what Settings > System > Display > Graphics writes): ``auto_preference`` /
   ``forced_preference`` work out the new text.
2. **Which devices Cycles renders on.** Cycles lists the devices per backend (OptiX, CUDA, HIP, oneAPI, Metal); an AMD
   processor's built-in Radeon and an AMD card are both HIP devices, and using both slows the card down.
   ``render_plan`` keeps only the graphics cards when there is one, else what there is (as before).

``kind`` tells a graphics card from built-in graphics by the name the driver gives (the same names in Windows' adapter
list, Cycles' device list and the OpenGL renderer text), with the adapter's own video memory as the fallback.
``decide_notice`` says when the app may show its calm notice; ``guide_steps`` are the steps of "Show me how".

The state is one small file in Blender's settings folder (``<config>/fresing_gpu.json``; extension preferences are
not kept over a restart with the app template, CLAUDE.md section 8)::

    {"never_for": "",            the GPUs (``signature``) the user said "Don't ask again" for ('' = not said)
     "render_device": "AUTO",    AUTO, CPU or a Cycles device id (Settings > General > Graphics)
     "auto_done": [...],         programs whose preference the app's start already set once (a later "Let Windows
                                 decide" by the user is then kept)
     "window": {...}}            what the app's last start saw: renderer, kind, time (the self-test and PC check
                                 run in the background and cannot see the window themselves)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

FILE_NAME = "fresing_gpu.json"
ORDER = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")         # Cycles' backends, the fastest first
AUTO, CPU = "AUTO", "CPU"
CARD, BUILT_IN, SOFTWARE, UNKNOWN = "card", "built-in", "software", "unknown"
VENDORS = {0x10DE: "NVIDIA", 0x1002: "AMD", 0x1022: "AMD", 0x8086: "Intel", 0x1414: "Microsoft", 0x106B: "Apple"}
CARD_MB = 2048            # an adapter of an unknown kind with at least this much own video memory counts as a card
SLOW_DRAW_S = 2.0         # a 3D-view frame that takes longer than this is "clearly slow" ...
SLOW_DRAWS = 3            # ... this many times in a row
PREF_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
HIGH_PERFORMANCE = "2"
SETTINGS_URI = "ms-settings:display-advancedgraphics"       # Windows: Settings > System > Display > Graphics


# ---------------------------------------------------------------------------
# Names: graphics card or built-in graphics
# ---------------------------------------------------------------------------

def norm(name: str) -> str:
    """'AMD Radeon(TM) RX 6700 XT/PCIe/SSE2' -> 'amd radeon rx 6700 xt' (marks, bus suffixes and spaces cleaned)."""
    n = (name or "").lower()
    n = re.sub(r"\((r|tm|c)\)|[®™]", " ", n)
    n = re.sub(r"/(pcie|sse2|pci|agp)\b.*$", "", n)
    n = re.sub(r"\s*\(.*?\)\s*", " ", n)                     # '(radeonsi, navi22, llvm ...)' and similar driver notes
    return " ".join(n.replace("_", " ").split())


def vendor(name: str = "", vendor_id: int = 0) -> str:
    if vendor_id in VENDORS:
        return VENDORS[vendor_id]
    n = norm(name)
    if re.search(r"\b(nvidia|geforce|quadro|tesla|titan)\b|\brtx\b|\bgtx\b", n):
        return "NVIDIA"
    if re.search(r"\b(amd|ati|radeon|firepro|instinct)\b", n):
        return "AMD"
    if re.search(r"\bintel\b|\biris\b|\buhd graphics\b|\bhd graphics\b|\barc\b", n):
        return "Intel"
    if re.search(r"\bapple\b", n):
        return "Apple"
    if re.search(r"microsoft|basic render|basic display", n):
        return "Microsoft"
    return ""


_SOFTWARE = re.compile(r"microsoft basic|basic render|basic display|llvmpipe|softpipe|swiftshader|\bwarp\b|"
                       r"lavapipe|software rasterizer|gdi generic|virtual display|parsec virtual|remote display")
_INTEL_CARD = re.compile(r"\barc\b.*\b(a|b)\s?\d{3}m?\b|\barc pro\b|\biris xe max\b|data center gpu|\bdg[12]\b")
_AMD_APU_VEGA = re.compile(r"\bvega \d{1,2} graphics\b")
_AMD_CARD = re.compile(r"\brx ?\d|\brx vega\b|\bradeon pro\b|\bpro w\d|\bw\d{4}\b|radeon vii|\bfirepro\b|\binstinct\b|"
                       r"\bvega (56|64|frontier)\b|\br9 \w|\br7 \d{3}\b|\bhd \d{4}\b(?! ?d)")
_AMD_BUILT_IN = re.compile(r"radeon graphics\b|\bradeon \d{3,4}[ms]\b|\bradeon r\d graphics\b|\bhd \d{4}d\b|"
                           r"\bradeon \d{3,4}[ms] graphics\b|\bradeon vega\b(?!.*\b(56|64|frontier)\b)")


def kind(name: str, vendor_id: int = 0, dedicated_mb: float | None = None, software: bool = False) -> str:
    """CARD (a graphics card: NVIDIA, AMD Radeon RX / Pro, Intel Arc A / B), BUILT_IN (in the processor), SOFTWARE
    (drawn by the processor: Microsoft Basic Render Driver, llvmpipe) or UNKNOWN."""
    n = norm(name)
    if software or _SOFTWARE.search(n):
        return SOFTWARE
    v = vendor(name, vendor_id)
    if v == "NVIDIA":
        return CARD
    if v == "Apple":
        return BUILT_IN
    if v == "Intel":
        return CARD if _INTEL_CARD.search(n) else BUILT_IN
    if v == "AMD":
        if _AMD_APU_VEGA.search(n):                 # 'Radeon RX Vega 11 Graphics' is a Ryzen 2400G's built-in one
            return BUILT_IN
        if _AMD_CARD.search(n):
            return CARD
        if _AMD_BUILT_IN.search(n):
            return BUILT_IN
    if dedicated_mb is not None and dedicated_mb > 0:
        return CARD if dedicated_mb >= CARD_MB else BUILT_IN
    return UNKNOWN


def short(name: str) -> str:
    """The name to show: the driver's marks taken off ('AMD Radeon(TM) Graphics' -> 'AMD Radeon Graphics')."""
    n = re.sub(r"\((R|TM|C)\)|[®™]", "", name or "", flags=re.I)
    n = re.sub(r"/(PCIe|SSE2).*$", "", n, flags=re.I)
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n)                 # Cycles' ' (Display)', '(16GB)', llvmpipe's notes
    return " ".join(n.split())


def same_gpu(a: str, b: str) -> bool:
    """Whether two names (an adapter, a Cycles device, the renderer text) are the same GPU."""
    x, y = _bare(a), _bare(b)
    if not (x and y):
        return False
    if x == y:
        return True
    few, many = sorted((x.split(), y.split()), key=len)        # 'geforce rtx 3090' in 'nvidia geforce rtx 3090 ...'
    return any(any(c.isdigit() for c in t) for t in few) and all(t in many for t in few)


def _bare(name: str) -> str:
    n = norm(name)
    n = re.sub(r"^(nvidia|amd|ati|intel|apple)\s+", "", n)
    n = re.sub(r"\s+(graphics|gpu)$", "", n)
    return n.strip()


# ---------------------------------------------------------------------------
# The adapters (Windows' list; made up in the tests)
# ---------------------------------------------------------------------------

@dataclass
class Adapter:
    name: str
    vendor_id: int = 0
    device_id: int = 0
    dedicated_mb: float = 0.0
    shared_mb: float = 0.0
    software: bool = False
    outputs: int = -1                  # monitors plugged into it (-1 = not known)
    high_performance: int = -1         # its place in Windows' "high performance" order (0 = first; -1 = not known)
    luid: str = ""

    @property
    def kind(self) -> str:
        return kind(self.name, self.vendor_id, self.dedicated_mb, self.software)

    def as_dict(self) -> dict:
        return {"name": self.name, "vendor_id": self.vendor_id, "device_id": self.device_id,
                "dedicated_mb": round(self.dedicated_mb), "shared_mb": round(self.shared_mb),
                "software": self.software, "outputs": self.outputs, "high_performance": self.high_performance,
                "kind": self.kind}


def hardware(adapters) -> list:
    """The real GPUs: software adapters and doubles (the same GPU listed twice) left out."""
    out, seen = [], set()
    for a in adapters or ():
        if a.kind == SOFTWARE:
            continue
        key = a.luid or (a.vendor_id, a.device_id, norm(a.name))
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def cards(adapters) -> list:
    """The graphics cards, the best first: Windows' own "high performance" order when known, then video memory."""
    found = [a for a in hardware(adapters) if a.kind == CARD]
    return sorted(found, key=lambda a: (a.high_performance if a.high_performance >= 0 else 99, -a.dedicated_mb))


def built_in(adapters) -> list:
    return [a for a in hardware(adapters) if a.kind == BUILT_IN]


def signature(adapters=(), names=()) -> str:
    """One text for the set of GPUs in this PC: a new card (or one taken out) asks again after "Don't ask again"."""
    keys = [f"{a.vendor_id:04x}:{a.device_id:04x}:{_bare(a.name)}" for a in hardware(adapters)]
    keys += [_bare(n) for n in names if n and kind(n) != SOFTWARE]
    return "|".join(sorted(set(keys)))


def cable_in_motherboard(adapters) -> bool:
    """A monitor is plugged into the built-in graphics (the motherboard's video port) and none into the card: Windows
    then draws everything on the built-in graphics. Only known on Windows (``outputs``)."""
    hw = hardware(adapters)
    c = [a for a in hw if a.kind == CARD]
    b = [a for a in hw if a.kind == BUILT_IN]
    return bool(c and b) and any(a.outputs > 0 for a in b) and all(a.outputs == 0 for a in c)


# ---------------------------------------------------------------------------
# 1. The window
# ---------------------------------------------------------------------------

def window_state(renderer: str, adapters=()) -> dict:
    """What draws the window: {"state", "drawn", "kind", "card"}. ``state``:

    * ``card`` – a graphics card draws it;
    * ``built_in_with_card`` – built-in graphics draw it while the PC has a card (the notice);
    * ``built_in`` – built-in graphics, and no card in this PC (nothing to switch to);
    * ``software`` – drawn by the processor (no GPU driver; a test server; a remote desktop);
    * ``unknown`` – the name says nothing and Windows' list is not known.
    """
    hw = hardware(adapters)
    match = next((a for a in hw if same_gpu(a.name, renderer)), None)
    k = match.kind if match else kind(renderer)
    best = cards(adapters)
    card = short(best[0].name) if best else ""
    if k == CARD:
        state = "card"
        card = short(match.name if match else renderer)
    elif k == BUILT_IN:
        state = "built_in_with_card" if best else "built_in"
    elif k == SOFTWARE:
        state = "software"
    else:
        state = "unknown"
    return {"state": state, "drawn": short(renderer), "kind": k, "card": card}


def parse_preference(text: str | None) -> dict:
    """'SwapEffectUpgradeEnable=1;GpuPreference=2;' -> {'SwapEffectUpgradeEnable': '1', 'GpuPreference': '2'}."""
    out = {}
    for part in (text or "").split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            if k.strip():
                out[k.strip()] = v.strip()
    return out


def format_preference(values: dict) -> str:
    return "".join(f"{k}={v};" for k, v in values.items())


def auto_preference(current: str | None) -> str | None:
    """The installer and the app's start: "High performance" where the user has not chosen (no value, or "Let Windows
    decide" = 0). A user's own "Power saving" (1) is left alone – the notice asks. None = nothing to write. Other
    settings in the same text (e.g. Windows' "Optimizations for windowed games") are kept."""
    values = parse_preference(current)
    if values.get("GpuPreference", "0") not in ("", "0"):
        return None
    values["GpuPreference"] = HIGH_PERFORMANCE
    return format_preference(values)


def forced_preference(current: str | None) -> str | None:
    """"Use the graphics card" in the notice: High performance whatever was there. None = already so."""
    values = parse_preference(current)
    if values.get("GpuPreference") == HIGH_PERFORMANCE:
        return None
    values["GpuPreference"] = HIGH_PERFORMANCE
    return format_preference(values)


def preference_name(text: str | None) -> str:
    v = parse_preference(text).get("GpuPreference", "")
    return {"": "not set (Windows decides)", "0": "Windows decides", "1": "Power saving",
            "2": "High performance"}.get(v, f"GpuPreference={v}")


# ---------------------------------------------------------------------------
# 2. Cycles
# ---------------------------------------------------------------------------

@dataclass
class Device:
    backend: str          # OPTIX, CUDA, HIP, ONEAPI, METAL or CPU
    name: str
    id: str = ""

    @property
    def kind(self) -> str:
        return CPU if self.backend == CPU else kind(self.name)


@dataclass
class Plan:
    backend: str = "NONE"                    # the compute_device_type for Cycles; NONE = the processor
    ids: list = field(default_factory=list)  # the devices to switch on (ids); every other one off
    names: list = field(default_factory=list)
    left_out: list = field(default_factory=list)      # built-in graphics of the same backend, switched off
    note: str = ""

    @property
    def gpu(self) -> bool:
        return self.backend != "NONE" and bool(self.ids)

    def text(self) -> str:
        """What ``render.setup_gpu`` returns: 'GPU (HIP): AMD Radeon RX 6700 XT' or 'CPU' (callers test 'GPU')."""
        if not self.gpu:
            return "CPU"
        out = f"GPU ({self.backend}): " + ", ".join(sorted({short(n) for n in self.names}))
        if self.left_out:
            out += " (built-in " + ", ".join(sorted({short(n) for n in self.left_out})) + " left out)"
        return out


def devices_from(items) -> list:
    """Cycles' devices as ``Device`` from (type, name, id) rows."""
    return [Device(str(t), str(n), str(i)) for t, n, i in items]


def render_plan(devices, choice: str = AUTO, order=ORDER) -> Plan:
    """Which Cycles devices to use. ``choice`` = AUTO (the graphics cards of the fastest backend that has one; with no
    card anywhere, every GPU of the fastest backend that has one – built-in graphics, as before), CPU, or a device id
    (that device alone, on its backend; a device no longer there falls back to AUTO with a note)."""
    gpus = [d for d in devices if d.backend != CPU and d.backend in order]
    if choice == CPU:
        return Plan(note="the processor (your choice in Settings)")
    note = ""
    if choice and choice != AUTO:
        hit = next((d for d in gpus if d.id == choice), None)
        if hit:
            return Plan(hit.backend, [hit.id], [hit.name], note="your choice in Settings")
        note = "the device chosen in Settings is not there: chosen automatically"
    for backend in order:
        mine = [d for d in gpus if d.backend == backend]
        good = [d for d in mine if d.kind != BUILT_IN]
        if good:
            left = [d.name for d in mine if d.kind == BUILT_IN]
            return Plan(backend, [d.id for d in good], [d.name for d in good], left, note)
    for backend in order:
        mine = [d for d in gpus if d.backend == backend]
        if mine:
            return Plan(backend, [d.id for d in mine], [d.name for d in mine],
                        note=(note + "; " if note else "") + "built-in graphics only (no graphics card found)")
    return Plan(note=note or "no GPU Cycles can use")


def choices(devices, order=ORDER) -> list:
    """The list in Settings > General > Graphics: (id, label, description); AUTO first, CPU last. A card on two
    backends (OptiX and CUDA) is listed once per backend."""
    out = [(AUTO, "Automatic (the graphics card)", "The graphics card on its fastest backend; built-in graphics "
                                                    "only when the PC has no graphics card")]
    for backend in order:
        for d in devices:
            if d.backend == backend:
                tag = "built-in graphics" if d.kind == BUILT_IN else "graphics card"
                out.append((d.id, f"{short(d.name)} ({backend_name(backend)})",
                            f"Render on {short(d.name)} only ({tag}, {backend_name(backend)})"))
    out.append((CPU, "Processor", "Render on the processor only (slow; for a check or when the graphics card "
                                  "has a problem)"))
    return out


def backend_name(backend: str) -> str:
    return {"OPTIX": "OptiX", "CUDA": "CUDA", "HIP": "HIP", "ONEAPI": "oneAPI", "METAL": "Metal"}.get(backend, backend)


# ---------------------------------------------------------------------------
# The notice
# ---------------------------------------------------------------------------

def fresh() -> dict:
    return {"never_for": "", "render_device": AUTO, "window": {}, "auto_done": []}


def load(path: str) -> dict:
    """The state in ``path``; a missing or damaged file gives a fresh state (never breaks a start)."""
    out = fresh()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    if isinstance(data.get("never_for"), str):
        out["never_for"] = data["never_for"]
    if isinstance(data.get("render_device"), str) and data["render_device"]:
        out["render_device"] = data["render_device"]
    if isinstance(data.get("auto_done"), list):
        out["auto_done"] = [p for p in data["auto_done"] if isinstance(p, str)]
    if isinstance(data.get("window"), dict):
        out["window"] = {k: v for k, v in data["window"].items() if isinstance(v, (str, int, float, bool))}
    return out


def save(path: str, state: dict) -> None:
    """Write the state (a temporary file first, so a crash never leaves half a file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, path)


def decide_notice(state: dict, sig: str, window: dict, slow: bool = False, shown: bool = False,
                  pending: bool = False) -> str:
    """What this start may show: "built_in" (the window is drawn by built-in graphics while a card exists), "slow"
    (the 3D view is clearly slow), or "" (nothing). Never twice in one start (``shown``), never after "Don't ask
    again" for the same GPUs, never while a preference written at this start waits for the next start
    (``pending``)."""
    if shown:
        return ""
    if state.get("never_for") and state.get("never_for") == sig:
        return ""
    st = (window or {}).get("state", "")
    if st == "built_in_with_card":
        return "" if pending else "built_in"
    if slow:
        return "slow"
    return ""


class DrawTimes:
    """The 3D view's frame times (seconds): ``slow`` once ``SLOW_DRAWS`` frames in a row took over ``SLOW_DRAW_S``."""

    def __init__(self, limit: float = SLOW_DRAW_S, count: int = SLOW_DRAWS):
        self.limit, self.count, self.run, self.worst = limit, count, 0, 0.0

    def add(self, seconds: float) -> bool:
        self.worst = max(self.worst, seconds)
        self.run = self.run + 1 if seconds > self.limit else 0
        return self.slow

    @property
    def slow(self) -> bool:
        return self.run >= self.count


def notice_text(kind_: str, window: dict, slow_s: float = 0.0) -> list:
    """The lines of the notice."""
    if kind_ == "built_in":
        return [f"Fresing Render is running on your processor's built-in graphics ({window.get('drawn') or '?'}).",
                f"Your PC has a faster graphics card: {window.get('card') or '?'}.",
                "Use the graphics card sets Windows' graphics preference for Fresing Render to High performance; "
                "it takes effect when you start the app again."]
    lines = [f"The 3D view is slow on this PC: a frame took {slow_s:.1f} s."]
    st = window.get("state", "")
    if st == "card":
        lines.append(f"It is drawn by your graphics card ({window.get('card')}): a big model or Live preview at a "
                     "high quality can be slow. Show me how lists what helps.")
    elif st in ("built_in", "software"):
        lines.append(f"It is drawn by {window.get('drawn') or 'the processor'}: this PC has no graphics card the app "
                     "can use. Show me how lists what helps.")
    else:
        lines.append("Check that Fresing Render uses your graphics card: Show me how.")
    return lines


def guide_steps(card: str = "", exes=(), cable: bool = False) -> list:
    """"Show me how": the steps to put Fresing Render on the graphics card (Windows 10 and 11). ``exes`` = the
    programs to choose in Windows' list."""
    names = " and ".join(f'"{p}"' for p in exes) if exes else '"Fresing Render.exe" (in the app\'s Blender folder)'
    steps = []
    if cable:
        steps.append("Your monitor is plugged into the motherboard's video port. Plug the monitor cable into the "
                     "graphics card instead (the ports low on the back of the PC, in a horizontal row), then start "
                     "the app again. Windows draws everything on the GPU the monitor is plugged into.")
    steps += [
        "Close Fresing Render (save your project first).",
        "Windows 11: Settings > System > Display > Graphics. Windows 10: Settings > System > Display > Graphics "
        "settings.",
        f"Find Fresing Render in the list. If it is not there: Add desktop app (Windows 10: Browse) and choose {names}.",
        "Click it > Options (Windows 11: the GPU preference list) > High performance"
        + (f" ({card})" if card else "") + " > Save.",
        "NVIDIA card: NVIDIA Control Panel > Manage 3D settings > Program Settings > Add > the same program > "
        "Preferred graphics processor: High-performance NVIDIA processor > Apply.",
        "AMD card: AMD Software (Adrenalin) needs no change for this on a desktop PC – Windows' setting above and the "
        "monitor cable decide. Keep the AMD driver up to date (AMD Software > System > Check for updates).",
        "Start Fresing Render again, open Fresing > Settings > General > Graphics: it should say the window is drawn "
        "by the graphics card.",
    ]
    if not cable:
        steps.append("Still built-in graphics? Check that the monitor cable is plugged into the graphics card, not "
                     "into the motherboard's video port.")
    return steps
