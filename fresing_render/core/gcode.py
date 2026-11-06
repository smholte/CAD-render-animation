"""G-code reader (task 0026): LinuxCNC programs (RS274NGC) as a timed list of moves. No Blender.

``read(text, ...)`` runs a program the way LinuxCNC would and returns a :class:`Program`:

    moves      every motion in order: rapid and feed lines, arcs (all three planes, helical), dwells,
               tool changes, pauses; each with its line number, start and end point, feed, spindle,
               tool, and its time (start, duration) in seconds of program time
    tools      the tool list: Fusion 360's tool comments at the top of the program, a LinuxCNC tool
               table (tool.tbl) if one was given, and the T numbers the program uses
    problems   everything the reader does not support, with the lines it is on (never silently skipped)
    notes      things that are read but not shown (path blending, tool length offsets ...)

All positions are **machine coordinates in mm** (G53): the app maps them to its X/Y/Z joints. The program's
own coordinates (G54 … G59.3, G92) are turned into machine coordinates with the work offsets: ``g54`` is
where the program's zero is in machine coordinates (the app works it out from the clicked work zero). The
other work offsets are the same as G54 unless the program sets them (G10 L2 / L20).

Supported (what CAM post-processors and hand-written LinuxCNC programs commonly use):

    G0 G1 G2 G3 (I J K or R, P turns, helical)   G4 dwell      G17 G18 G19 planes
    G20 G21 inch / mm      G90 G91 distance      G90.1 G91.1 arc centres      G93 G94 G95 feed modes
    G54-G59 G59.1-G59.3 work offsets, G10 L2 / L20 to set them, G92 G92.1 G92.2 G92.3
    G28 G28.1 G30 G30.1 home positions, G53 machine coordinates
    G80 G81 G82 G83 G73 G85 G86 G89 drilling and boring cycles (expanded into moves; G98 / G99, L repeats)
    G40 G43 G43.1 G49 G61 G61.1 G64 G97 (read; the tool tip is always put at the programmed point)
    F S T, M0 M1 M2 M3 M4 M5 M6 M7 M8 M9 M30 M60 M61 M48 M49 M50-M53 M62-M68 M19
    #1 … #5400, #<named> and #<_global> parameters, [ ] expressions with + - * / MOD ** EQ NE GT GE LT LE
    AND OR XOR and ABS ACOS ASIN ATAN COS EXP FIX FUP ROUND LN SIN SQRT TAN EXISTS (angles in degrees)
    O-words: sub / endsub / call / return, if / elseif / else / endif, while / endwhile, do / while,
    repeat / endrepeat, break, continue; a subroutine file <name>.ngc next to the program
    ( comments ) and ; comments, N line numbers, % and / block delete

Not supported (reported): cutter compensation G41 / G42 (the tool follows the programmed line), rotary and
extra axes A B C U V W (task 0029), threading G33 / G76, splines G5, probing G38, lathe modes, user M-codes
M100-M199.

Times: a rapid takes as long as its slowest axis needs at that axis' rapid speed; a feed move at its feed
(never faster than the axes' rapid speeds). Acceleration is left out: a real machine is a little slower on
short moves.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field

INCH = 25.4
#: arc planes: (first axis, second axis, normal axis) – first x second = normal (right-handed)
PLANES = {17: (0, 1, 2), 18: (2, 0, 1), 19: (1, 2, 0)}
PLANE_NAMES = {17: "G17 (XY)", 18: "G18 (XZ)", 19: "G19 (YZ)"}
MAX_STEPS = 3_000_000           # lines executed before a loop is taken to never end
PECK_CLEAR = 0.010 * INCH       # G83 / G73: how far above the last depth a peck starts again (LinuxCNC's value)
ARC_TOL = 0.01                  # mm: start and end radius of an arc may differ this much (else reported)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Move:
    kind: str                   # RAPID, FEED, ARC, DWELL, TOOL, PAUSE, SPINDLE (its speed changes here)
    line: int                   # line number in the file (1 = first line)
    a: tuple                    # start (x, y, z), machine coordinates, mm
    b: tuple                    # end
    t0: float = 0.0             # start, s of program time
    dur: float = 0.0            # s
    feed: float = 0.0           # mm/min (0 for rapids)
    spindle: float = 0.0        # rpm while this move runs: + clockwise (M3), - counter-clockwise (M4), 0 off
    tool: int = 0               # tool in the spindle (TOOL: the tool put in)
    centre: tuple = ()          # ARC: centre (at the start's height along the normal axis)
    plane: int = 17             # ARC: 17 / 18 / 19
    sweep: float = 0.0          # ARC: angle, radians, + counter-clockwise seen from the + end of the normal axis
    r0: float = 0.0             # ARC: radius at the start and at the end
    r1: float = 0.0
    length: float = 0.0         # mm along the path
    cycle: str = ""             # the drilling cycle it belongs to (G81 …), else ''
    top: int = 0                # the program's own line it comes from (a subroutine call's line)

    def at(self, u: float) -> tuple:
        """The point a fraction ``u`` (0..1) along the move."""
        if u <= 0.0:
            return self.a
        if u >= 1.0:
            return self.b
        if self.kind != "ARC":
            a, b = self.a, self.b
            return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)
        i, j, k = PLANES[self.plane]
        a0 = math.atan2(self.a[j] - self.centre[j], self.a[i] - self.centre[i])
        ang = a0 + self.sweep * u
        r = self.r0 + (self.r1 - self.r0) * u
        p = [0.0, 0.0, 0.0]
        p[i] = self.centre[i] + r * math.cos(ang)
        p[j] = self.centre[j] + r * math.sin(ang)
        p[k] = self.a[k] + (self.b[k] - self.a[k]) * u
        return (p[0], p[1], p[2])

    @property
    def moving(self) -> bool:
        return self.kind in ("RAPID", "FEED", "ARC")


@dataclass
class ToolInfo:
    number: int
    diameter: float = 0.0       # mm (0 = not known)
    corner: float = 0.0         # mm
    angle: float = 0.0          # included tip angle, degrees (drills, V-bits); 0 = not known
    length: float = 0.0         # mm sticking out of the holder (0 = not known)
    kind: str = ""              # FLAT BALL BULL VEE DRILL ('' = not known)
    comment: str = ""
    source: str = ""            # "comment", "table", "program"

    def describe(self) -> str:
        bits = []
        if self.diameter:
            bits.append(f"Ø{self.diameter:g} mm")
        if self.kind == "BULL" and self.corner:
            bits.append(f"R{self.corner:g}")
        name = {"FLAT": "flat end mill", "BALL": "ball end mill", "BULL": "corner radius mill",
                "VEE": "V-bit / chamfer", "DRILL": "drill"}.get(self.kind, "")
        if name:
            bits.append(name)
        return " ".join(bits) or (self.comment or "no size known")


@dataclass
class Problem:
    code: str                   # what it is about, e.g. "G41", "A axis", "unknown G-code G12"
    text: str                   # plain words
    lines: list = field(default_factory=list)

    def describe(self, n: int = 5) -> str:
        if not self.lines:
            return self.text
        shown = ", ".join(str(x) for x in self.lines[:n])
        more = f" and {len(self.lines) - n} more" if len(self.lines) > n else ""
        word = "line" if len(self.lines) == 1 else "lines"
        return f"{self.text} ({word} {shown}{more})"


@dataclass
class Program:
    moves: list = field(default_factory=list)
    tools: dict = field(default_factory=dict)          # number -> ToolInfo
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    lines: int = 0                                      # lines in the file
    steps: int = 0                                      # lines run (loops count every time)
    ended: bool = False                                 # M2 / M30 reached
    name: str = ""                                      # the program's title comment, if any

    @property
    def duration(self) -> float:
        return (self.moves[-1].t0 + self.moves[-1].dur) if self.moves else 0.0

    def tool_numbers(self) -> list:
        return sorted({m.tool for m in self.moves if m.kind == "TOOL"})

    def problem_lines(self) -> list:
        return [p.describe() for p in self.problems]

    def bounds(self, feed_only: bool = False):
        """(min, max) of every point the tool passes (arcs included); None without moves."""
        pts = []
        for m in self.moves:
            if not m.moving or (feed_only and m.kind == "RAPID"):
                continue
            pts += [m.a, m.b]
            if m.kind == "ARC":
                pts += [m.at(k / 16) for k in range(1, 16)]
        if not pts:
            return None
        return (tuple(min(p[i] for p in pts) for i in range(3)), tuple(max(p[i] for p in pts) for i in range(3)))


class GcodeError(RuntimeError):
    """The program cannot be read at all (a broken expression on a line is a problem, not this)."""


class _LineError(Exception):
    pass


# ---------------------------------------------------------------------------
# lines: comments, whitespace, words
# ---------------------------------------------------------------------------

_SIMPLE = re.compile(r"([a-z])([-+]?(?:\d+\.?\d*|\.\d+))")
_SIMPLE_LINE = re.compile(r"^(?:[a-z][-+]?(?:\d+\.?\d*|\.\d+))*$")
_OWORD = re.compile(r"^o(\d+|<[^>]*>)([a-z]+)(.*)$")
_FUNCS = ("abs", "acos", "asin", "atan", "cos", "exp", "fix", "fup", "round", "ln", "sin", "sqrt", "tan",
          "exists")
_BINOPS = [("**", 4), ("*", 3), ("/", 3), ("mod", 3), ("+", 2), ("-", 2), ("eq", 1), ("ne", 1), ("gt", 1),
           ("ge", 1), ("lt", 1), ("le", 1), ("and", 0), ("or", 0), ("xor", 0)]


def split_line(raw: str) -> tuple[str, list]:
    """(code without comments or spaces, lower case; [comment texts])."""
    comments = []
    out = []
    i, n = 0, len(raw)
    while i < n:
        c = raw[i]
        if c == "(":
            j = raw.find(")", i + 1)
            if j < 0:
                comments.append(raw[i + 1:].strip())
                break
            comments.append(raw[i + 1:j].strip())
            i = j + 1
            continue
        if c == ";":
            comments.append(raw[i + 1:].strip())
            break
        if not c.isspace():
            out.append(c)
        i += 1
    return "".join(out).lower(), comments


class _Expr:
    """Reads real values (numbers, #parameters, [expressions], functions) from a code string."""

    def __init__(self, s: str, params):
        self.s = s
        self.i = 0
        self.params = params

    def done(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def number(self) -> float:
        m = re.compile(r"\d+\.?\d*|\.\d+").match(self.s, self.i)
        if not m:
            raise _LineError(f"a number was expected at '{self.s[self.i:self.i + 8]}'")
        self.i = m.end()
        return float(m.group(0))

    def param_ref(self):
        """After '#': the parameter's key (an int, or a name in '<>')."""
        if self.peek() == "<":
            j = self.s.find(">", self.i)
            if j < 0:
                raise _LineError("a parameter name has no closing '>'")
            name = self.s[self.i + 1:j]
            self.i = j + 1
            return name
        v = self.real()
        k = int(round(v))
        if abs(v - k) > 1e-4:
            raise _LineError(f"parameter number {v:g} is not a whole number")
        return k

    def real(self) -> float:
        c = self.peek()
        if c == "[":
            self.i += 1
            v = self.expression()
            if self.peek() != "]":
                raise _LineError("a ']' is missing")
            self.i += 1
            return v
        if c == "-":
            self.i += 1
            return -self.real()
        if c == "+":
            self.i += 1
            return self.real()
        if c == "#":
            self.i += 1
            return self.params.get(self.param_ref())
        if c.isalpha():
            for fn in _FUNCS:
                if self.s.startswith(fn, self.i) and self.s[self.i + len(fn):self.i + len(fn) + 1] == "[":
                    self.i += len(fn)
                    return self.function(fn)
            raise _LineError(f"unknown word '{self.s[self.i:self.i + 6]}' in an expression")
        return self.number()

    def function(self, fn: str) -> float:
        if fn == "exists":
            self.i += 1                                     # '['
            if self.peek() != "#":
                raise _LineError("EXISTS needs a #<name>")
            self.i += 1
            key = self.param_ref()
            if self.peek() != "]":
                raise _LineError("a ']' is missing after EXISTS")
            self.i += 1
            return 1.0 if self.params.exists(key) else 0.0
        a = self.real()                                     # [ ... ]
        if fn == "atan":
            if self.peek() != "/":
                raise _LineError("ATAN needs two values: ATAN[y]/[x]")
            self.i += 1
            b = self.real()
            return math.degrees(math.atan2(a, b))
        try:
            if fn == "abs":
                return abs(a)
            if fn == "acos":
                return math.degrees(math.acos(a))
            if fn == "asin":
                return math.degrees(math.asin(a))
            if fn == "cos":
                return math.cos(math.radians(a))
            if fn == "sin":
                return math.sin(math.radians(a))
            if fn == "tan":
                return math.tan(math.radians(a))
            if fn == "exp":
                return math.exp(a)
            if fn == "ln":
                return math.log(a)
            if fn == "sqrt":
                return math.sqrt(a)
            if fn == "fix":
                return float(math.floor(a))
            if fn == "fup":
                return float(math.ceil(a))
            if fn == "round":
                return float(math.floor(a + 0.5))
        except (ValueError, OverflowError) as exc:
            raise _LineError(f"{fn.upper()}[{a:g}] cannot be worked out ({exc})") from None
        raise _LineError(f"unknown function {fn}")

    def _op(self):
        for op, prec in _BINOPS:
            if self.s.startswith(op, self.i):
                return op, prec
        return None, -1

    def expression(self) -> float:
        """Inside [ ]: values joined by operators (precedence: ** > * / MOD > + - > comparisons > AND OR XOR)."""
        vals = [self.real()]
        ops = []
        while True:
            op, prec = self._op()
            if op is None:
                break
            self.i += len(op)
            while ops and ops[-1][1] >= prec:
                self._reduce(vals, ops)
            ops.append((op, prec))
            vals.append(self.real())
        while ops:
            self._reduce(vals, ops)
        return vals[0]

    @staticmethod
    def _reduce(vals, ops) -> None:
        op, _p = ops.pop()
        b = vals.pop()
        a = vals.pop()
        try:
            if op == "**":
                r = a ** b
            elif op == "*":
                r = a * b
            elif op == "/":
                r = a / b
            elif op == "mod":
                r = math.fmod(a, b)
                if r < 0:
                    r += abs(b)
            elif op == "+":
                r = a + b
            elif op == "-":
                r = a - b
            elif op == "eq":
                r = float(a == b)
            elif op == "ne":
                r = float(a != b)
            elif op == "gt":
                r = float(a > b)
            elif op == "ge":
                r = float(a >= b)
            elif op == "lt":
                r = float(a < b)
            elif op == "le":
                r = float(a <= b)
            elif op == "and":
                r = float(bool(a) and bool(b))
            elif op == "or":
                r = float(bool(a) or bool(b))
            else:
                r = float(bool(a) != bool(b))
        except ZeroDivisionError:
            raise _LineError("division by zero") from None
        except (OverflowError, ValueError) as exc:
            raise _LineError(f"cannot work out {a:g} {op} {b:g} ({exc})") from None
        if isinstance(r, complex):
            raise _LineError(f"{a:g} ** {b:g} has no real value")
        vals.append(float(r))


# ---------------------------------------------------------------------------
# parameters
# ---------------------------------------------------------------------------

class _Params:
    """#1 … #30 and #<name> are local to a subroutine call; everything else is global."""

    def __init__(self):
        self.glob: dict = {}
        self.frames: list = [dict()]
        self.missing: list = []                        # named parameters read before being set
        self.system = None                             # callable(key) -> value or None

    def _scope(self, key):
        if isinstance(key, int):
            return self.frames[-1] if 1 <= key <= 30 else self.glob
        return self.glob if key.startswith("_") else self.frames[-1]

    def get(self, key) -> float:
        if self.system is not None and isinstance(key, int):
            v = self.system(key)
            if v is not None:
                return v
        scope = self._scope(key)
        if key in scope:
            return scope[key]
        if isinstance(key, str):
            self.missing.append(key)
        return 0.0

    def set(self, key, value: float) -> None:
        self._scope(key)[key] = float(value)

    def exists(self, key) -> bool:
        return key in self._scope(key)

    def push(self, args: list) -> None:
        self.frames.append({k + 1: float(v) for k, v in enumerate(args[:30])})

    def pop(self) -> None:
        if len(self.frames) > 1:
            self.frames.pop()


# ---------------------------------------------------------------------------
# tool comments and tool tables
# ---------------------------------------------------------------------------

_FUSION_TOOL = re.compile(r"^\s*T(\d+)\b(.*)$", re.I)
_KV = re.compile(r"\b(D|DIA|CR|TAPER|L|LEN|OL|LB|ZMIN)\s*=\s*([-+]?\d*\.?\d+)", re.I)


def kind_from_words(text: str, corner: float = 0.0, diameter: float = 0.0) -> str:
    t = text.lower()
    if "ball" in t or "kugel" in t or "bol" in t.split():
        return "BALL"
    if "bull" in t or "torus" in t or "radius mill" in t or "corner radius" in t:
        return "BULL"
    if "drill" in t or "bohrer" in t or "boor" in t:
        return "DRILL" if "spot" not in t and "center" not in t and "centre" not in t else "VEE"
    if "chamfer" in t or "engrav" in t or "v-bit" in t or "vbit" in t or "v bit" in t or "spot" in t:
        return "VEE"
    if "end mill" in t or "endmill" in t or "flat" in t or "face mill" in t or "slot" in t or "fräser" in t \
            or "frees" in t:
        if corner > 1e-6 and diameter and corner >= diameter / 2 - 1e-6:
            return "BALL"
        return "BULL" if corner > 1e-6 else "FLAT"
    return ""


def tool_from_comment(text: str):
    """A Fusion 360-style tool comment ``T1 D=6. CR=0. - ZMIN=-12. - flat end mill`` -> ToolInfo, else None."""
    m = _FUSION_TOOL.match(text)
    if not m:
        return None
    rest = m.group(2)
    vals = {k.upper(): float(v) for k, v in _KV.findall(rest)}
    if "D" not in vals and "DIA" not in vals:
        return None
    d = vals.get("D", vals.get("DIA", 0.0))
    cr = vals.get("CR", 0.0)
    taper = vals.get("TAPER", 0.0)
    words = rest.split(" - ")[-1] if " - " in rest else rest
    kind = kind_from_words(words, cr, d) or kind_from_words(rest, cr, d)
    if not kind:
        kind = "BALL" if d and cr >= d / 2 - 1e-6 else ("BULL" if cr > 1e-6 else "FLAT")
    angle = 0.0
    if kind == "DRILL":
        angle = taper if taper > 0 else 118.0
    elif kind == "VEE":
        angle = 2 * taper if 0 < taper < 90 else (taper or 90.0)
    length = vals.get("L", vals.get("LEN", vals.get("OL", 0.0)))
    return ToolInfo(int(m.group(1)), diameter=d, corner=cr, angle=angle, length=length, kind=kind,
                    comment=text.strip(), source="comment")


def read_tool_table(text: str, inch: bool = False) -> dict:
    """A LinuxCNC tool table (``T1 P1 D6.0 Z+30.0 ;6 mm end mill``) -> {number: ToolInfo}."""
    k = INCH if inch else 1.0
    out = {}
    for raw in text.splitlines():
        code, _sep, comment = raw.partition(";")
        words = dict((w[0].upper(), w[1:]) for w in code.split() if len(w) > 1)
        if "T" not in words:
            continue
        try:
            n = int(float(words["T"]))
            d = abs(float(words.get("D", "0"))) * k
            z = abs(float(words.get("Z", "0"))) * k
        except ValueError:
            continue
        kind = kind_from_words(comment) or ("FLAT" if d else "")
        out[n] = ToolInfo(n, diameter=d, length=z, kind=kind, comment=comment.strip(), source="table",
                          angle=118.0 if kind == "DRILL" else (90.0 if kind == "VEE" else 0.0),
                          corner=d / 2 if kind == "BALL" else 0.0)
    return out


# ---------------------------------------------------------------------------
# the reader
# ---------------------------------------------------------------------------

#: G-codes read but not shown, with the note they give (once). Keys: G-number x 10 (G43.1 -> 431).
_NOTED_G = {
    400: "", 490: "", 970: "", 800: "",
    610: "Exact stop (G61): corners are always shown sharp",
    611: "Exact stop (G61.1): corners are always shown sharp",
    640: "Path blending (G64): corners are shown sharp, the real machine rounds them a little",
    430: "Tool length offsets (G43): the app puts the tool's tip at the programmed point, so the tool "
         "lengths come from the model",
    431: "Tool length offsets (G43.1): the app puts the tool's tip at the programmed point",
    432: "Tool length offsets (G43.2): the app puts the tool's tip at the programmed point",
}
_COMP = "Cutter compensation (G41/G42) is not shown: the tool follows the programmed line"
_PROBE = "Probing (G38.x) is not shown"
_UNSUPPORTED_G = {
    410: _COMP, 420: _COMP, 411: _COMP, 421: _COMP,
    330: "Spindle-synchronised motion (G33, threading) is not supported",
    331: "Rigid tapping (G33.1) is not supported",
    760: "Threading cycles (G76) are not supported",
    50: "Splines (G5) are not supported", 51: "Splines (G5.1) are not supported",
    52: "NURBS (G5.2) are not supported", 53: "NURBS (G5.3) are not supported",
    70: "Lathe diameter mode (G7) is not supported", 80: "Lathe radius mode (G8) is not supported",
    960: "Constant surface speed (G96) is not supported: the spindle keeps its S rpm",
    382: _PROBE, 383: _PROBE, 384: _PROBE, 385: _PROBE,
    171: "UVW planes (G17.1 …) are not supported", 181: "UVW planes (G17.1 …) are not supported",
    191: "UVW planes (G17.1 …) are not supported",
}
_MOTION = {0, 10, 20, 30, 800, 810, 820, 830, 730, 850, 860, 890}
_CYCLES = {810: "G81", 820: "G82", 830: "G83", 730: "G73", 850: "G85", 860: "G86", 890: "G89"}
_NOTED_M = {7: "", 8: "", 9: "", 48: "", 49: "", 50: "", 51: "", 52: "", 53: "", 62: "", 63: "", 64: "",
            65: "", 66: "", 67: "", 68: "", 70: "", 71: "", 72: "", 73: ""}


def _gnum(v: float) -> int:
    """G90.1 -> 901, G1 -> 10, G59.3 -> 593: whole number with the decimal."""
    return int(round(v * 10))


class Reader:
    def __init__(self, g54=(0.0, 0.0, 0.0), rapid=(5000.0, 5000.0, 5000.0), home=(0.0, 0.0, 0.0),
                 tools=None, base_dir: str = "", loader=None, start=None):
        self.prog = Program()
        self.rapid = tuple(max(1e-6, float(v)) for v in rapid)
        self.origins = {p: list(g54) for p in range(1, 10)}       # work offsets, machine coordinates
        self.origins_set = {1}                                      # G54 is set by the app
        self.cs = 1
        self.g92 = [0.0, 0.0, 0.0]
        self.g92_saved = [0.0, 0.0, 0.0]
        self.home28 = list(home)
        self.home30 = list(home)
        self.pos = list(start) if start is not None else list(home)  # machine coordinates, mm
        self.inch = False
        self.absolute = True
        self.arc_absolute = False
        self.plane = 17
        self.feed_mode = 94
        self.feed = 0.0
        self.speed = 0.0
        self.spin = 0                                                # +1 M3, -1 M4, 0 off
        self.tool = 0
        self.next_tool = 0
        self.motion = 10                                             # G1 until told otherwise
        self.retract_r = False                                       # G99: back to R (else G98: old Z)
        self.cycle_vals: dict = {}
        self.t = 0.0
        self.params = _Params()
        self.params.system = self._system_param
        self.base_dir = base_dir
        self.loader = loader
        self.line_no = 0
        self.top_line = 0
        self._last_rpm = 0.0
        self._problems: dict = {}
        self._notes: dict = {}
        if tools:
            for n, info in tools.items():
                self.prog.tools[n] = info

    # -- bookkeeping ---------------------------------------------------------
    def problem(self, code: str, text: str) -> None:
        p = self._problems.get(code)
        if p is None:
            p = self._problems[code] = Problem(code, text)
            self.prog.problems.append(p)
        if self.line_no and (not p.lines or p.lines[-1] != self.line_no):
            p.lines.append(self.line_no)

    def note(self, text: str) -> None:
        if text and text not in self._notes:
            self._notes[text] = True
            self.prog.notes.append(text)

    def _system_param(self, key: int):
        if 5161 <= key <= 5163:
            return self.home28[key - 5161] / self._k()
        if 5181 <= key <= 5183:
            return self.home30[key - 5181] / self._k()
        if 5211 <= key <= 5213:
            return self.g92[key - 5211] / self._k()
        if key == 5220:
            return float(self.cs)
        if key == 5400:
            return float(self.tool)
        if key == 5410:
            info = self.prog.tools.get(self.tool)
            return (info.diameter if info else 0.0) / self._k()
        if 5221 <= key <= 5409:
            p, axis = divmod(key - 5221, 20)
            if axis < 3 and 1 + p in self.origins:
                return self.origins[1 + p][axis] / self._k()
            return None
        if 5420 <= key <= 5422:
            return self.work(self.pos)[key - 5420]
        return None

    def _k(self) -> float:
        return INCH if self.inch else 1.0

    def offset(self) -> list:
        o = self.origins[self.cs]
        return [o[i] + self.g92[i] for i in range(3)]

    def work(self, machine) -> list:
        """Machine -> program coordinates (in the program's units)."""
        o = self.offset()
        return [(machine[i] - o[i]) / self._k() for i in range(3)]

    # -- moves ---------------------------------------------------------------
    def _add(self, mv: Move) -> Move:
        mv.t0 = self.t
        mv.top = self.top_line or self.line_no
        mv.spindle = self.speed * self.spin
        if mv.kind != "TOOL":
            mv.tool = self.tool
        self.t += mv.dur
        self.prog.moves.append(mv)
        return mv

    def _spindle_event(self) -> None:
        rpm = self.speed * self.spin
        if rpm != self._last_rpm:
            p = tuple(self.pos)
            self._add(Move("SPINDLE", self.line_no, p, p))
            self._last_rpm = rpm

    def _axis_time(self, a, b) -> float:
        return max(abs(b[i] - a[i]) / self.rapid[i] for i in range(3)) * 60.0

    def rapid_to(self, target, cycle: str = "") -> None:
        a = tuple(self.pos)
        b = tuple(target)
        length = math.dist(a, b)
        if length < 1e-9:
            return
        self._add(Move("RAPID", self.line_no, a, b, dur=self._axis_time(a, b), length=length, cycle=cycle))
        self.pos = list(b)

    def _feed_rate(self, length: float, inverse_f) -> float:
        """mm/min for a feed move (G93: from the F on the line)."""
        if self.feed_mode == 93:
            if not inverse_f:
                self.problem("G93 F", "G93 (inverse time) needs an F on every feed line: shown at the last feed")
                return max(self.feed, 1e-6)
            return length * inverse_f                         # F = 1 / minutes
        if self.feed_mode == 95:
            if self.speed <= 0:
                self.problem("G95 S", "G95 (feed per turn) with the spindle at 0 rpm: shown at the rapid speed")
                return 0.0
            return self.feed * self.speed
        return self.feed

    def feed_to(self, target, inverse_f=None, cycle: str = "") -> None:
        a = tuple(self.pos)
        b = tuple(target)
        length = math.dist(a, b)
        if length < 1e-9:
            return
        f = self._feed_rate(length, inverse_f)
        limit = self._axis_time(a, b)
        if f <= 0:
            self.problem("F0", "A feed move without a feed (F): shown at the rapid speed")
            dur = limit
        else:
            dur = max(length / f * 60.0, limit)
        self._add(Move("FEED", self.line_no, a, b, dur=dur, feed=f, length=length, cycle=cycle))
        self.pos = list(b)

    def arc_to(self, target, cw: bool, words: dict, inverse_f=None) -> None:
        i, j, k = PLANES[self.plane]
        a = list(self.pos)
        b = list(target)
        letters = {0: "i", 1: "j", 2: "k"}
        turns = 1
        if "p" in words:
            turns = int(round(words["p"]))
            if turns < 1:
                self.problem("arc P", "An arc's P (turns) must be 1 or more: P1 used")
                turns = 1
        if "r" in words:
            r = words["r"] * self._k()
            du, dv = b[i] - a[i], b[j] - a[j]
            chord = math.hypot(du, dv)
            if chord < 1e-9:
                self.problem("arc R full", "A full circle cannot be given with R: use I/J/K")
                return
            if chord > 2 * abs(r) + ARC_TOL:
                self.problem("arc R small", "An arc's R is smaller than half the distance to its end point")
            h = math.sqrt(max(0.0, r * r - chord * chord / 4))
            mu, mv = (a[i] + b[i]) / 2, (a[j] + b[j]) / 2
            # centre to the right of the chord for clockwise short arcs (left for counter-clockwise)
            side = (1.0 if cw else -1.0) * (1.0 if r > 0 else -1.0)
            cu = mu + side * h * dv / chord
            cv = mv - side * h * du / chord
        else:
            off = []
            for ax in (i, j):
                key = letters[ax]
                off.append(words.get(key))
            if off[0] is None and off[1] is None:
                self.problem("arc centre", f"An arc in {PLANE_NAMES[self.plane]} needs "
                             f"{letters[i].upper()}/{letters[j].upper()} or R: line skipped")
                return
            ou, ov = (x * self._k() if x is not None else None for x in off)
            if self.arc_absolute:                        # G90.1: the centre in program coordinates
                o = self.offset()
                cu = (ou + o[i]) if ou is not None else a[i]
                cv = (ov + o[j]) if ov is not None else a[j]
            else:
                cu = a[i] + (ou or 0.0)
                cv = a[j] + (ov or 0.0)
        r0 = math.hypot(a[i] - cu, a[j] - cv)
        r1 = math.hypot(b[i] - cu, b[j] - cv)
        if abs(r1 - r0) > ARC_TOL and abs(r1 - r0) > 0.001 * max(r0, r1):
            self.problem("arc radius", "An arc's end point is not on its circle (start and end radius differ): "
                         "drawn as a spiral")
        if r0 < 1e-9:
            self.problem("arc zero", "An arc starts at its own centre: drawn as a straight line")
            self.feed_to(target, inverse_f)
            return
        a0 = math.atan2(a[j] - cv, a[i] - cu)
        a1 = math.atan2(b[j] - cv, b[i] - cu)
        sweep = a1 - a0
        if cw:
            while sweep >= -1e-12:
                sweep -= 2 * math.pi
            if sweep < -2 * math.pi + 1e-9 and math.hypot(b[i] - a[i], b[j] - a[j]) > 1e-7:
                sweep += 2 * math.pi
        else:
            while sweep <= 1e-12:
                sweep += 2 * math.pi
            if sweep > 2 * math.pi - 1e-9 and math.hypot(b[i] - a[i], b[j] - a[j]) > 1e-7:
                sweep -= 2 * math.pi
        sweep += (-1.0 if cw else 1.0) * 2 * math.pi * (turns - 1)
        centre = [0.0, 0.0, 0.0]
        centre[i], centre[j], centre[k] = cu, cv, a[k]
        rm = (r0 + r1) / 2
        length = math.hypot(rm * abs(sweep), b[k] - a[k])
        f = self._feed_rate(length, inverse_f)
        vmax = min(self.rapid[i], self.rapid[j])
        limit = length / vmax * 60.0
        if f <= 0:
            self.problem("F0", "A feed move without a feed (F): shown at the rapid speed")
            dur = limit
        else:
            dur = max(length / f * 60.0, limit)
        self._add(Move("ARC", self.line_no, tuple(a), tuple(b), dur=dur, feed=f, centre=tuple(centre),
                       plane=self.plane, sweep=sweep, r0=r0, r1=r1, length=length))
        self.pos = b

    # -- one block -----------------------------------------------------------
    def target(self, words: dict, machine: bool = False) -> list:
        """Where the axis words of a block go (machine coordinates, mm)."""
        out = list(self.pos)
        k = self._k()
        off = [0.0, 0.0, 0.0] if machine else self.offset()
        for ax, key in enumerate("xyz"):
            if key not in words:
                continue
            v = words[key] * k
            if self.absolute or machine:
                out[ax] = v + off[ax]
            else:
                out[ax] = self.pos[ax] + v
        return out

    def block(self, gs: list, ms: list, words: dict) -> bool:
        """Run one block (modal groups in LinuxCNC's order). Returns False at the program's end."""
        g_set = set(gs)
        # 1 feed mode, feed, speed, tool select
        for g in (930, 940, 950):
            if g in g_set:
                self.feed_mode = g // 10
        inverse_f = None
        if "f" in words:
            if self.feed_mode == 93:
                inverse_f = words["f"]
            else:
                self.feed = words["f"] * self._k()
        if "s" in words:
            self.speed = abs(words["s"])
        if "t" in words:
            self.next_tool = int(round(words["t"]))
            self.prog.tools.setdefault(self.next_tool, ToolInfo(self.next_tool, source="program"))
        # 2 tool change
        if 6 in ms or 61 in ms:
            if 61 in ms:
                if "q" in words:
                    self.next_tool = int(round(words["q"]))
                self.prog.tools.setdefault(self.next_tool, ToolInfo(self.next_tool, source="program"))
            if self.next_tool != self.tool or 61 in ms:
                p = tuple(self.pos)
                self.tool = self.next_tool
                self._add(Move("TOOL", self.line_no, p, p, tool=self.tool, cycle="M61" if 61 in ms else ""))
        # 3 spindle, coolant, overrides
        if 3 in ms:
            self.spin = 1
        if 4 in ms:
            self.spin = -1
        if 5 in ms or 19 in ms:
            self.spin = 0
        self._spindle_event()
        # 4 dwell
        if 40 in g_set:
            p = words.get("p", 0.0)
            if p > 0:
                pt = tuple(self.pos)
                self._add(Move("DWELL", self.line_no, pt, pt, dur=float(p)))
        # 5 plane, units, distance modes, coordinate systems, retract mode
        for g in (170, 180, 190):
            if g in g_set:
                self.plane = g // 10
        if 200 in g_set:
            self.inch = True
        if 210 in g_set:
            self.inch = False
        for g, p in ((540, 1), (550, 2), (560, 3), (570, 4), (580, 5), (590, 6), (591, 7), (592, 8), (593, 9)):
            if g in g_set:
                self.cs = p
                if p not in self.origins_set:
                    self.origins_set.add(p)
                    names = {2: "G55", 3: "G56", 4: "G57", 5: "G58", 6: "G59", 7: "G59.1", 8: "G59.2", 9: "G59.3"}
                    self.problem(f"G5x {p}", f"{names[p]} is used but the program does not set its zero (G10 L2): "
                                 "taken the same as G54")
        if 900 in g_set:
            self.absolute = True
        if 910 in g_set:
            self.absolute = False
        if 901 in g_set:
            self.arc_absolute = True
        if 911 in g_set:
            self.arc_absolute = False
        if 980 in g_set:
            self.retract_r = False
        if 990 in g_set:
            self.retract_r = True
        # 6 non-modal: G10, G28, G30, G92, G53
        machine = 530 in g_set
        if 100 in g_set:
            self._g10(words)
            return True
        if 280 in g_set or 300 in g_set:
            home = self.home28 if 280 in g_set else self.home30
            given = [ax for ax, key in enumerate("xyz") if key in words]
            if given:
                self.rapid_to(self.target(words))
            dest = list(self.pos)
            for ax in (given or [0, 1, 2]):
                dest[ax] = home[ax]
            self.rapid_to(dest)
            return True
        if 281 in g_set:
            self.home28 = list(self.pos)
            return True
        if 301 in g_set:
            self.home30 = list(self.pos)
            return True
        if 920 in g_set:
            k = self._k()
            o = self.origins[self.cs]
            for ax, key in enumerate("xyz"):
                if key in words:
                    self.g92[ax] = self.pos[ax] - o[ax] - words[key] * k
            return True
        if 921 in g_set or 922 in g_set:
            if 921 in g_set:
                self.g92_saved = [0.0, 0.0, 0.0]
            else:
                self.g92_saved = list(self.g92)
            self.g92 = [0.0, 0.0, 0.0]
        if 923 in g_set:
            self.g92 = list(self.g92_saved)
        # 7 motion
        motion = next((g for g in gs if g in _MOTION), None)
        if motion is not None:
            self.motion = motion
            if motion in _CYCLES:
                self.cycle_vals = {}
        has_axis = any(key in words for key in "xyz")
        if self.motion == 800 and has_axis and motion is None:
            self.problem("G80 axis", "Axis words after G80 (cycles off) without G0/G1: no motion mode, "
                         "line skipped")
        elif has_axis or (motion in (20, 30) and ("p" in words)):
            if machine and self.motion not in (0, 10):
                self.problem("G53 mode", "G53 only works with G0 or G1: line skipped")
            elif self.motion == 0:
                self.rapid_to(self.target(words, machine))
            elif self.motion == 10:
                self.feed_to(self.target(words, machine), inverse_f)
            elif self.motion in (20, 30):
                self.arc_to(self.target(words), self.motion == 20, words, inverse_f)
            elif self.motion in _CYCLES:
                self._cycle(words)
        # 8 stop
        if 0 in ms or 1 in ms or 60 in ms:
            pt = tuple(self.pos)
            self._add(Move("PAUSE", self.line_no, pt, pt))
            self.note("M0 / M1 (program pause): the animation goes on without stopping")
        if 2 in ms or 30 in ms:
            self.spin = 0
            self._spindle_event()
            self.prog.ended = True
            return False
        return True

    def _g10(self, words: dict) -> None:
        l_ = int(round(words.get("l", 0)))
        if l_ in (2, 20):
            p = int(round(words.get("p", 0)))
            if p == 0:
                p = self.cs
            if not 1 <= p <= 9:
                self.problem("G10 P", "G10 with a P outside 0 … 9: line skipped")
                return
            k = self._k()
            o = self.origins[p]
            for ax, key in enumerate("xyz"):
                if key in words:
                    if l_ == 2:
                        o[ax] = words[key] * k
                    else:                              # L20: the current point gets this value
                        o[ax] = self.pos[ax] - self.g92[ax] - words[key] * k
            self.origins_set.add(p)
            if "r" in words:
                self.problem("G10 R", "A rotated work offset (G10 … R) is not supported: no rotation used")
        elif l_ in (1, 10, 11):
            self.note("The program sets tool table values (G10 L1/L10/L11): the app uses the tool list instead")
        else:
            self.problem("G10 L", f"G10 L{l_} is not supported")

    def _cycle(self, words: dict) -> None:
        """Drilling and boring cycles, expanded into moves (LinuxCNC's rules, any plane)."""
        i, j, k = PLANES[self.plane]
        letters = "xyz"
        name = _CYCLES[self.motion]
        vals = self.cycle_vals
        kk = self._k()
        for key in ("r", "q", "p"):
            if key in words:
                vals[key] = words[key]
        nkey = letters[k]
        if nkey in words:
            vals["n"] = words[nkey]
        if "r" not in vals or "n" not in vals:
            self.problem(f"{name} RZ", f"A {name} cycle needs R and {nkey.upper()}: line skipped")
            return
        if self.motion in (830, 730) and vals.get("q", 0) <= 0:
            self.problem(f"{name} Q", f"A {name} cycle needs a peck depth Q above 0: line skipped")
            return
        repeats = max(1, int(round(words.get("l", 1))))
        if self.absolute and repeats > 1:
            self.note("Cycle repeats (L) in absolute mode (G90) drill the same hole again")
        old_n = self.pos[k]
        o = self.offset()
        for rep in range(repeats):
            # where: the plane point, R level and depth (machine coordinates)
            if self.absolute:
                r_level = vals["r"] * kk + o[k]
                depth = vals["n"] * kk + o[k]
                pt = list(self.pos)
                for ax in (i, j):
                    if letters[ax] in words:
                        pt[ax] = words[letters[ax]] * kk + o[ax]
            else:
                r_level = old_n + vals["r"] * kk
                depth = r_level + vals["n"] * kk
                pt = list(self.pos)
                for ax in (i, j):
                    if letters[ax] in words:
                        pt[ax] = self.pos[ax] + words[letters[ax]] * kk
            clear = r_level if self.retract_r else max(old_n, r_level)
            if self.pos[k] < r_level:                         # below R: up to R first
                up = list(self.pos)
                up[k] = r_level
                self.rapid_to(up, name)
            over = list(pt)
            over[k] = self.pos[k]
            self.rapid_to(over, name)
            at_r = list(over)
            at_r[k] = r_level
            self.rapid_to(at_r, name)
            bottom = list(at_r)
            bottom[k] = depth
            if self.motion in (830, 730):
                q = vals["q"] * kk
                level = r_level
                while level - q > depth + 1e-9:
                    level -= q
                    p_ = list(at_r)
                    p_[k] = level
                    self.feed_to(p_, cycle=name)
                    back = list(at_r)
                    if self.motion == 830:
                        back[k] = r_level
                        self.rapid_to(back, name)
                        back[k] = level + PECK_CLEAR
                        self.rapid_to(back, name)
                    else:
                        back[k] = level + PECK_CLEAR
                        self.rapid_to(back, name)
                self.feed_to(bottom, cycle=name)
            else:
                self.feed_to(bottom, cycle=name)
            if self.motion in (820, 890) and vals.get("p", 0) > 0:
                p0 = tuple(self.pos)
                self._add(Move("DWELL", self.line_no, p0, p0, dur=float(vals["p"]), cycle=name))
            out = list(bottom)
            if self.motion in (850, 890):                     # feed back out to R, then rapid to the clear level
                out[k] = r_level
                self.feed_to(out, cycle=name)
            elif self.motion == 860:
                self.note("G86 stops the spindle at the bottom of the hole: the app keeps it turning")
            out[k] = clear
            self.rapid_to(out, name)

    # -- the whole program -----------------------------------------------------
    def parse_words(self, code: str):
        """Words of a code line -> (G list, M list, other letters, parameter assignments)."""
        gs, ms, words, sets = [], [], {}, []
        if _SIMPLE_LINE.match(code):
            items = [(m.group(1), float(m.group(2))) for m in _SIMPLE.finditer(code)]
        else:
            items = []
            e = _Expr(code, self.params)
            while not e.done():
                c = e.peek()
                if c == "#":
                    e.i += 1
                    key = e.param_ref()
                    if e.peek() != "=":
                        raise _LineError("a parameter on its own must be set with '='")
                    e.i += 1
                    sets.append((key, e.real()))
                    continue
                if not c.isalpha():
                    raise _LineError(f"unexpected '{code[e.i:e.i + 8]}'")
                e.i += 1
                items.append((c, e.real()))
        for letter, v in items:
            if letter == "g":
                gs.append(_gnum(v))
            elif letter == "m":
                ms.append(int(round(v)))
            elif letter == "n" and not gs and not ms and not words:
                continue
            else:
                if letter in words:
                    raise _LineError(f"the letter {letter.upper()} is on this line twice")
                words[letter] = v
        return gs, ms, words, sets

    def check(self, gs: list, ms: list, words: dict) -> tuple:
        """Report what is not supported; return the codes the block runs."""
        keep_g = []
        for g in gs:
            if g in _UNSUPPORTED_G and _UNSUPPORTED_G[g]:
                self.problem(f"G{g / 10:g}", _UNSUPPORTED_G[g])
                continue
            if g in _NOTED_G:
                self.note(_NOTED_G[g])
                keep_g.append(g)
                continue
            if g in (0, 10, 20, 30, 40, 100, 170, 180, 190, 200, 210, 280, 281, 300, 301, 530, 540, 550, 560,
                     570, 580, 590, 591, 592, 593, 800, 810, 820, 830, 730, 850, 860, 890, 900, 901, 910, 911,
                     920, 921, 922, 923, 930, 940, 950, 980, 990):
                keep_g.append(g)
                continue
            self.problem(f"G{g / 10:g}", f"Unknown or unsupported G-code G{g / 10:g}: left out")
        keep_m = []
        for m in ms:
            if m in (0, 1, 2, 3, 4, 5, 6, 19, 30, 60, 61):
                keep_m.append(m)
            elif m in _NOTED_M:
                continue
            elif 100 <= m <= 199:
                self.problem(f"M{m}", f"User M-code M{m} (runs a script on the machine) is not shown")
            else:
                self.problem(f"M{m}", f"Unknown or unsupported M-code M{m}: left out")
        for letter in "abcuvw":
            if letter in words:
                self.problem(f"{letter.upper()} axis", f"{letter.upper()} axis moves are not supported (only X, Y, "
                             "Z): that axis stays put")
        for letter in words:
            if letter in "eo":
                self.problem(f"word {letter}", f"Unknown word {letter.upper()}: left out")
        return keep_g, keep_m


def _structure(lines: list) -> dict:
    """Match O-word blocks: {index of an o-line: info}. ``lines``: (code, ...) per line."""
    info: dict = {}
    stack: list = []
    for idx, code in enumerate(lines):
        if not code.startswith("o"):
            continue
        m = _OWORD.match(code)
        if not m:
            continue
        label, kw = m.group(1), m.group(2)
        if kw == "while" and any(lab == label and k2 == "do" for lab, k2, _i in stack):
            for n in range(len(stack) - 1, -1, -1):          # the while that closes a do
                if stack[n][0] == label and stack[n][1] == "do":
                    start = stack[n][2]
                    info[start]["end"] = idx
                    info[idx] = {"kw": "dowhile", "start": start}
                    del stack[n:]
                    break
            continue
        if kw in ("sub", "if", "while", "do", "repeat"):
            stack.append((label, kw, idx))
            info[idx] = {"kw": kw, "label": label, "branches": [], "end": None}
        elif kw in ("elseif", "else"):
            for lab, k2, start in reversed(stack):
                if lab == label and k2 == "if":
                    info[start]["branches"].append(idx)
                    info[idx] = {"kw": kw, "start": start}
                    break
        elif kw in ("endsub", "endif", "endwhile", "endrepeat"):
            want = {"endsub": "sub", "endif": "if", "endwhile": "while", "endrepeat": "repeat"}[kw]
            for n in range(len(stack) - 1, -1, -1):
                if stack[n][0] == label and stack[n][1] == want:
                    start = stack[n][2]
                    info[start]["end"] = idx
                    info[idx] = {"kw": kw, "start": start}
                    del stack[n:]
                    break
    return info


def read(text: str, g54=(0.0, 0.0, 0.0), rapid=(5000.0, 5000.0, 5000.0), home=(0.0, 0.0, 0.0), tools=None,
         base_dir: str = "", start=None) -> Program:
    """Run a LinuxCNC program (see the module's docstring). ``g54``: the program's zero in machine
    coordinates (mm); ``rapid``: each axis' rapid speed (mm/min); ``home``: the G28 / G30 position (machine
    coordinates; also where the machine starts unless ``start`` is given); ``tools``: {number: ToolInfo}
    from a tool table; ``base_dir``: where subroutine files (<name>.ngc) are looked for."""
    rd = Reader(g54=g54, rapid=rapid, home=home, tools=tools, base_dir=base_dir, start=start)
    raw_lines = text.splitlines()
    rd.prog.lines = len(raw_lines)
    codes, comments = [], []
    for raw in raw_lines:
        c, com = split_line(raw)
        if c.startswith("/"):
            c = c[1:]
        if c.startswith("%"):
            c = ""
        if c.startswith("n"):
            c = re.sub(r"^n\d+(?:\.\d+)?", "", c)
        codes.append(c)
        comments.append(com)
    # tool comments (Fusion 360 and the like): anywhere in the program, before the tool table entries
    for idx, com in enumerate(comments):
        for text_ in com:
            info = tool_from_comment(text_)
            if info is not None:
                old = rd.prog.tools.get(info.number)
                if old is not None and old.source == "table":      # the table's sizes win, the comment says what
                    info.diameter = old.diameter or info.diameter
                    info.length = old.length or info.length
                    if info.kind == "BALL":
                        info.corner = info.diameter / 2
                    info.source = "table + comment"
                rd.prog.tools[info.number] = info
        if idx < 3 and com and not rd.prog.name and codes[idx] == "":
            t = com[0].strip()
            if t and not tool_from_comment(t):
                rd.prog.name = t
    _run(rd, codes, base_dir)
    for key in sorted(set(rd.params.missing)):
        rd.line_no = 0
        rd.problem(f"param {key}", f"Parameter #<{key}> is read before it is set: 0 used")
    return rd.prog


def _load_sub(rd, name: str):
    """A subroutine file <name>.ngc next to the program: its code lines, or None."""
    if not rd.base_dir:
        return None
    for fn in (f"{name}.ngc", f"{name}.NGC", f"{name}.nc"):
        p = os.path.join(rd.base_dir, fn)
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    return [split_line(x)[0] for x in fh.read().splitlines()]
            except OSError:
                return None
    return None


def _run(rd: Reader, codes: list, base_dir: str) -> None:
    files = {"": codes}                                   # '' = the program; else a subroutine file
    infos = {"": _structure(codes)}
    subs = {}                                             # label -> (file, index of the sub line)
    for idx, d in infos[""].items():
        if d.get("kw") == "sub":
            subs[d["label"]] = ("", idx)
    calls: list = []                                      # (file, return index, loop stack)
    loops: list = []                                      # (file, start index, kind, counter)
    fname, pc = "", 0
    steps = 0
    while True:
        code_list = files[fname]
        if pc >= len(code_list):
            if calls:
                rd.problem("sub end", "A subroutine has no endsub: it ends at the end of its file")
                fname, pc, loops = calls.pop()
                rd.params.pop()
                continue
            break
        steps += 1
        if steps > MAX_STEPS:
            rd.problem("loop", f"Stopped after {MAX_STEPS:,} lines: a loop that never ends?")
            break
        code = code_list[pc]
        if fname == "":
            rd.line_no = pc + 1
        rd.top_line = calls[0][1] if calls else pc + 1
        info = infos[fname]
        if not code:
            pc += 1
            continue
        try:
            if code.startswith("o"):
                m = _OWORD.match(code)
                if not m:
                    raise _LineError("an O-word without a known keyword")
                label, kw, rest = m.group(1), m.group(2), m.group(3)
                e = _Expr(rest, rd.params)
                if kw == "sub":
                    end = info.get(pc, {}).get("end")
                    if end is None:
                        rd.problem("sub", f"o{label} sub has no endsub: the rest of the file is skipped")
                        break
                    pc = end + 1
                    continue
                if kw in ("endsub", "return"):
                    if not calls:
                        if kw == "endsub":
                            pc += 1
                            continue
                        rd.problem("return", "A return outside a subroutine: left out")
                        pc += 1
                        continue
                    if not e.done() and e.peek() == "[":
                        rd.params.set("_value", e.real())
                    fname, pc, loops = calls.pop()
                    rd.params.pop()
                    continue
                if kw == "call":
                    args = []
                    while not e.done():
                        args.append(e.real())
                    target = subs.get(label)
                    if target is None and label.startswith("<"):
                        name = label[1:-1]
                        lines_ = _load_sub(rd, name)
                        if lines_ is not None:
                            files[name] = lines_
                            infos[name] = _structure(lines_)
                            for idx2, d2 in infos[name].items():
                                if d2.get("kw") == "sub" and d2["label"] not in subs:
                                    subs[d2["label"]] = (name, idx2)
                            target = subs.get(label)
                    if target is None:
                        rd.problem(f"call {label}", f"Subroutine o{label} is not in the program (nor a file "
                                   "next to it): the call is left out")
                        pc += 1
                        continue
                    if len(calls) > 50:
                        rd.problem("deep", "Subroutines call each other more than 50 deep: stopped")
                        break
                    calls.append((fname, pc + 1, loops))
                    loops = []
                    rd.params.push(args)
                    fname, pc = target[0], target[1] + 1
                    continue
                if kw == "if":
                    d = info.get(pc)
                    if d is None or d.get("end") is None:
                        raise _LineError(f"o{label} if has no endif")
                    if e.real():
                        pc += 1
                        continue
                    nxt = d["end"]
                    for br in d["branches"]:
                        bm = _OWORD.match(code_list[br])
                        if bm.group(2) == "else":
                            nxt = br
                            break
                        if _Expr(bm.group(3), rd.params).real():
                            nxt = br
                            break
                    pc = nxt + 1
                    continue
                if kw in ("elseif", "else"):
                    start = info.get(pc, {}).get("start")
                    pc = (info[start]["end"] + 1) if start is not None else pc + 1
                    continue
                if kw == "endif":
                    pc += 1
                    continue
                if kw == "while":
                    d = info.get(pc)
                    if d is not None and d.get("kw") == "dowhile":
                        start = d["start"]
                        if e.real():
                            pc = start + 1
                        else:
                            if loops and loops[-1][1] == start:
                                loops.pop()
                            pc += 1
                        continue
                    if d is None or d.get("end") is None:
                        raise _LineError(f"o{label} while has no endwhile")
                    if e.real():
                        if not loops or loops[-1][1] != pc:
                            loops.append((fname, pc, "while", 0))
                        pc += 1
                    else:
                        if loops and loops[-1][1] == pc:
                            loops.pop()
                        pc = d["end"] + 1
                    continue
                if kw == "endwhile":
                    pc = info.get(pc, {}).get("start", pc)
                    continue
                if kw == "do":
                    if not loops or loops[-1][1] != pc:
                        loops.append((fname, pc, "do", 0))
                    pc += 1
                    continue
                if kw == "repeat":
                    d = info.get(pc)
                    if d is None or d.get("end") is None:
                        raise _LineError(f"o{label} repeat has no endrepeat")
                    if loops and loops[-1][1] == pc:
                        f_, s_, k_, left = loops.pop()
                    else:
                        left = int(round(e.real()))
                    if left > 0:
                        loops.append((fname, pc, "repeat", left - 1))
                        pc += 1
                    else:
                        pc = d["end"] + 1
                    continue
                if kw == "endrepeat":
                    pc = info.get(pc, {}).get("start", pc)
                    continue
                if kw in ("break", "continue"):
                    if not loops:
                        rd.problem(kw, f"o{label} {kw} outside a loop: left out")
                        pc += 1
                        continue
                    _f, start, kind, _left = loops[-1]
                    d = info.get(start, {})
                    if kw == "break":
                        loops.pop()
                        pc = (d.get("end") or pc) + 1
                    elif kind == "do":
                        pc = d.get("end") or pc
                    else:
                        pc = start if kind != "repeat" else (d.get("end") or pc)
                    continue
                raise _LineError(f"unknown O-word keyword '{kw}'")
            gs, ms, words, sets = rd.parse_words(code)
            gs, ms = rd.check(gs, ms, words)
            go_on = rd.block(gs, ms, words)
            for key, v in sets:
                rd.params.set(key, v)
            if not go_on:
                in_sub = set()
                for idx2, d in info.items():
                    if d.get("kw") == "sub" and d.get("end") is not None:
                        in_sub |= set(range(idx2, d["end"] + 1))
                rest = [i for i in range(pc + 1, len(code_list)) if code_list[i] and i not in in_sub]
                if rest and fname == "":
                    rd.note(f"The program ends with M2/M30 on line {pc + 1}: the {len(rest)} lines after it are "
                            "not run")
                break
        except _LineError as exc:
            rd.problem(f"line {rd.line_no}", f"Cannot read line {rd.line_no}: {exc}")
        pc += 1
    rd.prog.steps = steps


# ---------------------------------------------------------------------------
# timing for the animation: program time -> video time
# ---------------------------------------------------------------------------

@dataclass
class Timing:
    """How a program plays in the video.

    ``speed``: 'REAL' (as the machine would), 'FASTER' (``factor`` × faster), 'FIT' (the motion fills
    ``fit_seconds``). ``rapid_factor``: rapids go this much faster again. ``tool_change``: seconds each tool
    change takes in the video (the ATC sequence's length when one plays), ``swap``: when in it the new
    tool shows. ``line_from``/``line_to``: only moves on these lines (0 = no end)."""
    speed: str = "REAL"
    factor: float = 1.0
    fit_seconds: float = 10.0
    rapid_factor: float = 1.0
    tool_change: float = 2.0
    swap: float = 1.0
    line_from: int = 0
    line_to: int = 0


@dataclass(slots=True)
class Piece:
    """A move as it plays in the video: v0 .. v0 + vd seconds (from the step's start)."""
    move: Move
    v0: float
    vd: float


class Schedule:
    def __init__(self, prog: Program, timing: Timing):
        self.prog = prog
        self.timing = timing
        lo = max(1, int(timing.line_from or 1))
        hi = int(timing.line_to) if timing.line_to and timing.line_to >= lo else 10 ** 12
        moves = [m for m in prog.moves if lo <= m.top <= hi]
        self.first_tool = 0
        before = [m for m in prog.moves if m.top < lo]
        for m in before:
            if m.kind == "TOOL":
                self.first_tool = m.tool
        self.start_point = moves[0].a if moves else (before[-1].b if before else None)
        self.start_spindle = before[-1].spindle if before else 0.0
        rf = max(1e-6, float(timing.rapid_factor or 1.0))

        def raw(m):
            if m.kind == "TOOL":
                return 0.0
            return m.dur / rf if m.kind == "RAPID" else m.dur

        motion = sum(raw(m) for m in moves)
        changes = sum(1 for m in moves if m.kind == "TOOL" and m.cycle != "M61")
        tc = max(0.0, float(timing.tool_change))
        if timing.speed == "FASTER":
            scale = 1.0 / max(1e-6, float(timing.factor))
        elif timing.speed == "FIT":
            room = max(1e-3, float(timing.fit_seconds) - changes * tc)
            scale = room / motion if motion > 0 else 1.0
        else:
            scale = 1.0
        self.scale = scale
        self.pieces: list = []
        self.tool_events: list = []                         # (video time of the swap, tool, start, length)
        t = 0.0
        for m in moves:
            if m.kind == "TOOL":
                d = 0.0 if m.cycle == "M61" else tc
                self.tool_events.append((t + min(max(0.0, timing.swap), d), m.tool, t, d))
                self.pieces.append(Piece(m, t, d))
                t += d
                continue
            d = raw(m) * scale
            self.pieces.append(Piece(m, t, d))
            t += d
        self.duration = t
        self._starts = [p.v0 for p in self.pieces]

    def piece_at(self, t: float):
        import bisect
        k = bisect.bisect_right(self._starts, t) - 1
        if k < 0:
            return None
        # skip pieces of zero length at the same moment: the last one there wins
        return self.pieces[min(k, len(self.pieces) - 1)]

    def point_at(self, t: float):
        """The tool tip (machine coordinates, mm) ``t`` seconds into the step."""
        if not self.pieces:
            return self.start_point
        if t >= self.duration:
            return self.pieces[-1].move.b
        p = self.piece_at(t)
        if p is None:
            return self.start_point
        if p.vd <= 0:
            return p.move.b
        return p.move.at((t - p.v0) / p.vd)

    def samples(self, fps: float, tol: float = 0.002, per_frame: bool = True):
        """Times (s from the step's start) where the path needs a key so that straight keys between them
        follow it within ``tol`` mm: every move's start and end, and along arcs every frame plus as many
        points as the chord error needs. Returns sorted [(t, (x, y, z))]."""
        out = []
        if self.start_point is None:
            return out
        out.append((0.0, self.start_point))
        for p in self.pieces:
            m = p.move
            if not m.moving:
                if p.vd > 0:
                    out.append((p.v0 + p.vd, m.b))
                continue
            if m.kind == "ARC" and p.vd > 0:
                r = max(m.r0, m.r1, 1e-6)
                step = 2 * math.acos(max(-1.0, 1 - tol / r)) if tol < r else math.pi / 2
                n = max(1, int(math.ceil(abs(m.sweep) / max(step, 1e-6))))
                us = {k / n for k in range(1, n)}
                if per_frame:
                    f0 = math.floor(p.v0 * fps) + 1
                    f1 = math.ceil((p.v0 + p.vd) * fps)
                    us |= {(f / fps - p.v0) / p.vd for f in range(f0, f1)}
                for u in sorted(x for x in us if 0 < x < 1):
                    out.append((p.v0 + u * p.vd, m.at(u)))
            out.append((p.v0 + p.vd, m.b))
        # drop keys that land on the same moment (the later point wins: zero-length pieces)
        clean = []
        for t, pt in out:
            if clean and abs(clean[-1][0] - t) < 1e-9:
                clean[-1] = (t, pt)
            else:
                clean.append((t, pt))
        return clean

    def spindle_keys(self):
        """[(t, rpm)] where the spindle's speed changes (signed rpm, + = clockwise)."""
        out = [(0.0, self.start_spindle)]
        for p in self.pieces:
            if p.move.spindle != out[-1][1]:
                out.append((p.v0, p.move.spindle))
        return out

    def path(self, tol: float = 0.01, max_step: float = 0.0):
        """Polylines of the path for drawing: [(rapid?, [(x, y, z, t)...])], consecutive feed moves joined.
        ``max_step``: split long straight moves so no piece takes longer than this (s), for the "already
        milled" colour; 0 = not split."""
        lines = []
        cur = None
        for p in self.pieces:
            m = p.move
            if not m.moving:
                continue
            rapid = m.kind == "RAPID"
            if cur is None or cur[0] != rapid or math.dist(cur[1][-1][:3], m.a) > 1e-6:
                cur = (rapid, [(m.a[0], m.a[1], m.a[2], p.v0)])
                lines.append(cur)
            n = 1
            if m.kind == "ARC":
                r = max(m.r0, m.r1, 1e-6)
                step = 2 * math.acos(max(-1.0, 1 - tol / r)) if tol < r else math.pi / 2
                n = max(1, int(math.ceil(abs(m.sweep) / max(step, 1e-6))))
            if max_step > 0 and p.vd > max_step:
                n = max(n, int(math.ceil(p.vd / max_step)))
            n = min(n, 2000)
            for k in range(1, n + 1):
                u = k / n
                pt = m.at(u)
                cur[1].append((pt[0], pt[1], pt[2], p.v0 + u * p.vd))
        return lines
