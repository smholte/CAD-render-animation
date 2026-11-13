"""G-code reader (task 0026): LinuxCNC programs (RS274NGC) as a timed list of moves. No Blender.

``read(text, ...)`` runs a program the way LinuxCNC would and returns a :class:`Program`:

    moves      every motion in order: rapid and feed lines, arcs (all three planes, helical), dwells,
               tool changes, pauses; each with its line number, start and end point, feed, spindle,
               tool, and its time (start, duration) in seconds of program time
    tools      the tool list: Fusion 360's tool comments at the top of the program, a LinuxCNC tool
               table (tool.tbl) if one was given, and the T numbers the program uses
    problems   everything the reader does not support, with the lines it is on (never silently skipped)
    notes      things that are read but not shown (path blending, tool length offsets ...)

All positions are **machine coordinates in mm** (G53): the app maps them to its X/Y/Z joints. The rotary axes
A, B and C (task 0066) are kept in **degrees** next to them (``Move.ra`` / ``Move.rb``), as the program says them
(LinuxCNC ``trivkins``: just joint angles); what they turn is the app's business (blender/gcode.py, rotary.py). The program's
own coordinates (G54 … G59.3, G92) are turned into machine coordinates with the work offsets: ``g54`` is
where the program's zero is in machine coordinates (the app works it out from the clicked work zero). The
other work offsets are the same as G54 unless the program sets them (G10 L2 / L20).

Supported (what CAM post-processors and hand-written LinuxCNC programs commonly use):

    G0 G1 G2 G3 (I J K or R, P turns, helical)   G4 dwell      G17 G18 G19 planes
    G20 G21 inch / mm      G90 G91 distance      G90.1 G91.1 arc centres      G93 G94 G95 feed modes
    G54-G59 G59.1-G59.3 work offsets, G10 L2 / L20 to set them, G92 G92.1 G92.2 G92.3
    G28 G28.1 G30 G30.1 home positions, G53 machine coordinates
    G80 G81 G82 G83 G73 G85 G86 G89 drilling and boring cycles (expanded into moves; G98 / G99, L repeats)
    G40 G43 G43.1 G49 G61 G61.1 G64 G97 (read; the tool tip is put at the programmed point, except after an M6
    without a G43 for the new tool: the old tool's length offset stays, as on the machine - task 0096)
    F S T, M0 M1 M2 M3 M4 M5 M6 M7 M8 M9 M30 M60 M61 M48 M49 M50-M53 M62-M68 M19
    #1 … #5400, #<named> and #<_global> parameters, [ ] expressions with + - * / MOD ** EQ NE GT GE LT LE
    AND OR XOR and ABS ACOS ASIN ATAN COS EXP FIX FUP ROUND LN SIN SQRT TAN EXISTS (angles in degrees)
    O-words: sub / endsub / call / return, if / elseif / else / endif, while / endwhile, do / while,
    repeat / endrepeat, break, continue; a subroutine file <name>.ngc next to the program
    ( comments ) and ; comments, N line numbers, % and / block delete

Rotary axes A B C (task 0066): on G0 G1 G2 G3 (an arc's rotary part goes evenly along the arc), G28 G30 G53
G92 G10 L2 / L20; degrees, never inch; "wrapped" axes (LinuxCNC ``WRAPPED_ROTARY``) count 0 … 360 and an absolute
move goes the way its sign says (A90 the + way to 90°, A-90 the - way to 90°), as LinuxCNC does.
Feed with rotary words (LinuxCNC's rule): F is mm/min along X/Y/Z when they move; a move of the rotary axes only
uses F as degrees per minute (their combined angle); G93 inverse time (F = 1 / minutes for the whole move) and
back with G94.

Not supported (reported): cutter compensation G41 / G42 (the tool follows the programmed line), extra axes U V W,
threading G33 / G76, splines G5, probing G38, lathe modes, user M-codes M100-M199.

Times: a rapid takes as long as its slowest axis needs at that axis' rapid speed (rotary axes in degrees per
minute); a feed move at its feed (never faster than the axes' rapid speeds). With ``accel`` (task 0103) every move
then speeds up and slows down with the axes' maximum accelerations (:func:`plan_accel`: trapezoid speed profiles,
G61 exact stop, G64 corner blending, arcs at most √(a·r)); without it every move runs at its full speed from start
to end.
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
ROT = "abc"                     # the rotary axes' letters (task 0066)
NO_TURN = (0.0, 0.0, 0.0)
TURN_EPS = 1e-9                 # degrees: a smaller change of a rotary axis is no move


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
    ra: tuple = ()              # rotary axes A, B, C at the start, degrees (task 0066); () = all 0
    rb: tuple = ()              # … and at the end; they change evenly along the move (also along an arc)
    h: int = 0                  # task 0096: the tool whose length offset (G43 Hn) is in force when that is not the
                                # tool in the spindle (an M6 without a new G43); 0: the tool in the spindle's own
    blend: float = 0.0          # task 0103: path control at this move's end: -1 exact stop (G61 / G61.1), 0 blending
                                # without a tolerance (G64), > 0 the tolerance of G64 P (mm)
    dur0: float = -1.0          # task 0103: the time without acceleration (s); -1: not planned (``dur`` is that time)
    prof: tuple = ()            # task 0103: the speed profile (vs, vp, ve, a, S, t1, t2), see :func:`plan_accel`;
                                # () = constant speed (the place goes evenly with the time)

    def u_of(self, tau: float) -> float:
        """The share of the path (0..1) done after the share ``tau`` (0..1) of this move's time (task 0103)."""
        if tau <= 0.0:
            return 0.0
        if tau >= 1.0:
            return 1.0
        if not self.prof:
            return tau
        vs, vp, ve, a, S, t1, t2 = self.prof
        t = tau * self.dur
        d1 = (vs + vp) * 0.5 * t1
        if t <= t1:
            s = vs * t + 0.5 * a * t * t
        elif t <= t2:
            s = d1 + vp * (t - t1)
        else:
            dt = t - t2
            s = d1 + vp * (t2 - t1) + vp * dt - 0.5 * a * dt * dt
        return min(1.0, max(0.0, s / S))

    def tau_of(self, u: float) -> float:
        """The share of this move's time after which the share ``u`` of its path is done (inverse of ``u_of``)."""
        if u <= 0.0:
            return 0.0
        if u >= 1.0:
            return 1.0
        if not self.prof or self.dur <= 0:
            return u
        vs, vp, ve, a, S, t1, t2 = self.prof
        s = u * S
        d1 = (vs + vp) * 0.5 * t1
        d2 = d1 + vp * (t2 - t1)
        if s <= d1:
            t = (-vs + math.sqrt(max(0.0, vs * vs + 2 * a * s))) / a if a > 0 else 0.0
        elif s <= d2:
            t = t1 + (s - d1) / vp if vp > 0 else t1
        else:
            ds = s - d2
            t = t2 + ((vp - math.sqrt(max(0.0, vp * vp - 2 * a * ds))) / a if a > 0 else 0.0)
        return min(1.0, max(0.0, t / self.dur))

    def velocity(self, tau: float) -> tuple:
        """d(point)/d(share of the move's time) at ``tau`` (mm per whole move time; task 0103): divide by the
        piece's length in seconds for mm/s."""
        if self.prof and self.dur > 0:
            vs, vp, ve, a, S, t1, t2 = self.prof
            t = min(max(tau, 0.0), 1.0) * self.dur
            v = vs + a * t if t <= t1 else (vp if t <= t2 else vp - a * (t - t2))
            du = max(v, 0.0) * self.dur / S                     # d(share of the path) / d(share of the time)
        else:
            du = 1.0
        u = self.u_of(tau)
        if self.kind != "ARC":
            return tuple((self.b[n] - self.a[n]) * du for n in range(3))
        i, j, k = PLANES[self.plane]
        a0 = math.atan2(self.a[j] - self.centre[j], self.a[i] - self.centre[i])
        ang = a0 + self.sweep * u
        r = self.r0 + (self.r1 - self.r0) * u
        dr = self.r1 - self.r0
        out = [0.0, 0.0, 0.0]
        out[i] = (dr * math.cos(ang) - r * math.sin(ang) * self.sweep) * du
        out[j] = (dr * math.sin(ang) + r * math.cos(ang) * self.sweep) * du
        out[k] = (self.b[k] - self.a[k]) * du
        return tuple(out)

    def phase_times(self) -> tuple:
        """(t1, t2) in shares of the move's time: where speeding up ends and slowing down starts; () without a
        profile."""
        if not self.prof or self.dur <= 0:
            return ()
        return (self.prof[5] / self.dur, self.prof[6] / self.dur)

    def rot_at(self, u: float) -> tuple:
        """A, B, C (degrees) a fraction ``u`` (0..1) along the move."""
        ra = self.ra or NO_TURN
        rb = self.rb or ra
        if u <= 0.0:
            return ra
        if u >= 1.0:
            return rb
        return (ra[0] + (rb[0] - ra[0]) * u, ra[1] + (rb[1] - ra[1]) * u, ra[2] + (rb[2] - ra[2]) * u)

    @property
    def turn(self) -> float:
        """The rotary axes' combined change in this move, degrees (0: no rotary axis moves)."""
        ra = self.ra or NO_TURN
        rb = self.rb or ra
        return math.sqrt(sum((b - a) ** 2 for a, b in zip(ra, rb)))

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
    # coolant / air codes (M7 M8 M9, user codes M100-M199; task 0039): (moves before it, M number, line)
    m_events: list = field(default_factory=list)
    # Tn without M6 on its line (task 0064): (moves before it, T, line) - a double-arm changer turns its magazine
    # to that tool's pot while the machine still cuts
    t_events: list = field(default_factory=list)
    # rotary axes the program moves (task 0066): {'a': first line, ...}
    rotary: dict = field(default_factory=dict)
    # task 0103: True when the moves are timed with acceleration (``plan_accel``); ``plain_duration`` is then the
    # program's time without it (s)
    accel: bool = False
    plain_duration: float = 0.0

    @property
    def duration(self) -> float:
        return (self.moves[-1].t0 + self.moves[-1].dur) if self.moves else 0.0

    @property
    def duration_without_accel(self) -> float:
        """The program's time with every move at its full speed from start to end (task 0103)."""
        return self.plain_duration if self.accel else self.duration

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
    610: "Exact stop (G61): corners are shown sharp; with acceleration on, the machine stops at every corner",
    611: "Exact stop (G61.1): corners are shown sharp; with acceleration on, the machine stops at every corner",
    640: "Path blending (G64): corners are shown sharp, the real machine rounds them a little (with acceleration "
         "on it slows down at corners as the machine does)",
    430: "Tool length offsets (G43): the tool lengths come from the tool list (an M6 without a G43 for the new "
         "tool keeps the old tool's offset, as on the machine)",
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
                 tools=None, base_dir: str = "", loader=None, start=None, rot_rapid=(3600.0, 3600.0, 3600.0),
                 wrapped=(False, False, False), start_rot=None):
        self.prog = Program()
        self.rapid = tuple(max(1e-6, float(v)) for v in rapid)
        # rotary axes A, B, C (task 0066): degrees; rapid in degrees per minute
        self.rot_rapid = tuple(max(1e-6, float(v)) for v in rot_rapid)
        self.wrapped = tuple(bool(w) for w in wrapped)
        self.rot = [float(v) for v in start_rot] if start_rot is not None else [0.0, 0.0, 0.0]
        self.origins_rot = {p: [0.0, 0.0, 0.0] for p in range(1, 10)}
        self.g92_rot = [0.0, 0.0, 0.0]
        self.g92_rot_saved = [0.0, 0.0, 0.0]
        self.home28_rot = [0.0, 0.0, 0.0]
        self.home30_rot = [0.0, 0.0, 0.0]
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
        self.h = None                                                # G43 Hn in force (task 0096); None: G49 / none
        self.motion = 10                                             # G1 until told otherwise
        self.blend = 0.0                                             # G64 (task 0103): -1 G61, > 0 G64 P
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
        if 5164 <= key <= 5166:
            return self.home28_rot[key - 5164]
        if 5181 <= key <= 5183:
            return self.home30[key - 5181] / self._k()
        if 5184 <= key <= 5186:
            return self.home30_rot[key - 5184]
        if 5211 <= key <= 5213:
            return self.g92[key - 5211] / self._k()
        if 5214 <= key <= 5216:
            return self.g92_rot[key - 5214]
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
            if axis < 6 and 1 + p in self.origins_rot:
                return self.origins_rot[1 + p][axis - 3]
            return None
        if 5420 <= key <= 5422:
            return self.work(self.pos)[key - 5420]
        if 5423 <= key <= 5425:
            return self.work_rot()[key - 5423]
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

    def offset_rot(self) -> list:
        o = self.origins_rot[self.cs]
        return [o[i] + self.g92_rot[i] for i in range(3)]

    def work_rot(self) -> list:
        """The rotary axes in program coordinates (degrees; a wrapped axis 0 … 360)."""
        o = self.offset_rot()
        out = [self.rot[i] - o[i] for i in range(3)]
        return [v % 360.0 if w else v for v, w in zip(out, self.wrapped)]

    # -- moves ---------------------------------------------------------------
    def _add(self, mv: Move) -> Move:
        if not mv.ra:                                        # a move that does not turn: the axes stay
            mv.ra = mv.rb = tuple(self.rot)
        mv.blend = self.blend
        mv.t0 = self.t
        mv.top = self.top_line or self.line_no
        mv.spindle = self.speed * self.spin
        if mv.kind != "TOOL":
            mv.tool = self.tool
        mv.h = self.h if self.h and self.h != mv.tool else 0
        self.t += mv.dur
        self.prog.moves.append(mv)
        return mv

    def _spindle_event(self) -> None:
        rpm = self.speed * self.spin
        if rpm != self._last_rpm:
            p = tuple(self.pos)
            self._add(Move("SPINDLE", self.line_no, p, p))
            self._last_rpm = rpm

    def _axis_time(self, a, b, ra=None, rb=None) -> float:
        t = max(abs(b[i] - a[i]) / self.rapid[i] for i in range(3))
        if ra is not None and rb is not None:
            t = max([t] + [abs(rb[i] - ra[i]) / self.rot_rapid[i] for i in range(3)])
        return t * 60.0

    def _turn(self, rot) -> tuple:
        """(start, end) of the rotary axes for a move to ``rot`` (None: they stay)."""
        ra = tuple(self.rot)
        rb = tuple(float(v) for v in rot) if rot is not None else ra
        return ra, rb

    def rapid_to(self, target, cycle: str = "", rot=None) -> None:
        a = tuple(self.pos)
        b = tuple(target)
        ra, rb = self._turn(rot)
        length = math.dist(a, b)
        turn = math.dist(ra, rb)
        if length < 1e-9 and turn < TURN_EPS:
            return
        self._add(Move("RAPID", self.line_no, a, b, dur=self._axis_time(a, b, ra, rb), length=length, cycle=cycle,
                       ra=ra, rb=rb))
        self.pos = list(b)
        self.rot = list(rb)

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

    def feed_to(self, target, inverse_f=None, cycle: str = "", rot=None) -> None:
        a = tuple(self.pos)
        b = tuple(target)
        ra, rb = self._turn(rot)
        length = math.dist(a, b)
        turn = math.dist(ra, rb)
        if length < 1e-9 and turn < TURN_EPS:
            return
        # LinuxCNC: F is along X/Y/Z when they move; a move of the rotary axes only takes F as degrees per minute
        span = length if length >= 1e-9 else turn
        f = self._feed_rate(span, inverse_f)
        limit = self._axis_time(a, b, ra, rb)
        if f <= 0:
            self.problem("F0", "A feed move without a feed (F): shown at the rapid speed")
            dur = limit
        else:
            dur = max(span / f * 60.0, limit)
        self._add(Move("FEED", self.line_no, a, b, dur=dur, feed=f, length=length, cycle=cycle, ra=ra, rb=rb))
        self.pos = list(b)
        self.rot = list(rb)

    def arc_to(self, target, cw: bool, words: dict, inverse_f=None, rot=None) -> None:
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
            self.feed_to(target, inverse_f, rot=rot)
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
        ra, rb = self._turn(rot)
        limit = max(limit, max(abs(rb[n] - ra[n]) / self.rot_rapid[n] for n in range(3)) * 60.0)
        if f <= 0:
            self.problem("F0", "A feed move without a feed (F): shown at the rapid speed")
            dur = limit
        else:
            dur = max(length / f * 60.0, limit)
        self._add(Move("ARC", self.line_no, tuple(a), tuple(b), dur=dur, feed=f, centre=tuple(centre),
                       plane=self.plane, sweep=sweep, r0=r0, r1=r1, length=length, ra=ra, rb=rb))
        self.pos = b
        self.rot = list(rb)

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

    def rot_target(self, words: dict, machine: bool = False):
        """Where the rotary words of a block turn the axes (degrees, machine), or None without any. A wrapped axis
        (absolute) goes the way the number's sign says, to the number's angle in 0 … 360 (LinuxCNC's
        ``unwrap_rotary``); the value kept goes on from the current one, so a key moves the short way it turns."""
        if not any(key in words for key in ROT):
            return None
        out = list(self.rot)
        off = [0.0, 0.0, 0.0] if machine else self.offset_rot()
        for ax, key in enumerate(ROT):
            if key not in words:
                continue
            self.prog.rotary.setdefault(key, self.top_line or self.line_no)
            v = float(words[key])
            if not (self.absolute or machine):
                out[ax] = self.rot[ax] + v
            elif self.wrapped[ax]:
                cur = (self.rot[ax] - off[ax]) % 360.0
                want = abs(v) % 360.0
                if v >= 0 and not math.copysign(1.0, v) < 0:
                    goal = want if want >= cur else want + 360.0
                else:
                    goal = want if want <= cur else want - 360.0
                out[ax] = self.rot[ax] + (goal - cur)
            else:
                out[ax] = v + off[ax]
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
            if 6 not in ms and 61 not in ms:
                self.prog.t_events.append((len(self.prog.moves), self.next_tool, self.top_line or self.line_no))
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
        # 8 (LinuxCNC's step 'tool length offset', run after the change): G43 Hn - without H the tool in the spindle;
        # G43.1 / G43.2 / G49: the app's own rule (every tool by its own length)
        if 430 in g_set:
            self.h = int(round(words["h"])) if "h" in words else self.tool
        if 431 in g_set or 432 in g_set or 490 in g_set:
            self.h = None
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
        # path control (task 0103): G61 / G61.1 exact stop, G64 blending (P: its tolerance)
        if 610 in g_set or 611 in g_set:
            self.blend = -1.0
        if 640 in g_set:
            self.blend = max(0.0, words.get("p", 0.0) * self._k())
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
            home_r = self.home28_rot if 280 in g_set else self.home30_rot
            given = [ax for ax, key in enumerate("xyz") if key in words]
            given_r = [ax for ax, key in enumerate(ROT) if key in words]
            if given or given_r:                              # first to the point on the line, then home
                self.rapid_to(self.target(words), rot=self.rot_target(words))
            dest = list(self.pos)
            dest_r = list(self.rot)
            if not given and not given_r:                     # no axis words: every axis goes home
                given, given_r = [0, 1, 2], [0, 1, 2]
            for ax in given:
                dest[ax] = home[ax]
            for ax in given_r:                                # (a wrapped axis: the short way, without whole turns)
                dest_r[ax] = (self.rot[ax] + ((home_r[ax] - self.rot[ax] + 180.0) % 360.0 - 180.0)
                              if self.wrapped[ax] else home_r[ax])
            self.rapid_to(dest, rot=dest_r)
            return True
        if 281 in g_set:
            self.home28 = list(self.pos)
            self.home28_rot = list(self.rot)
            return True
        if 301 in g_set:
            self.home30 = list(self.pos)
            self.home30_rot = list(self.rot)
            return True
        if 920 in g_set:
            k = self._k()
            o = self.origins[self.cs]
            for ax, key in enumerate("xyz"):
                if key in words:
                    self.g92[ax] = self.pos[ax] - o[ax] - words[key] * k
            o_r = self.origins_rot[self.cs]
            for ax, key in enumerate(ROT):
                if key in words:
                    self.g92_rot[ax] = self.rot[ax] - o_r[ax] - words[key]
            return True
        if 921 in g_set or 922 in g_set:
            if 921 in g_set:
                self.g92_saved = [0.0, 0.0, 0.0]
                self.g92_rot_saved = [0.0, 0.0, 0.0]
            else:
                self.g92_saved = list(self.g92)
                self.g92_rot_saved = list(self.g92_rot)
            self.g92 = [0.0, 0.0, 0.0]
            self.g92_rot = [0.0, 0.0, 0.0]
        if 923 in g_set:
            self.g92 = list(self.g92_saved)
            self.g92_rot = list(self.g92_rot_saved)
        # 7 motion
        motion = next((g for g in gs if g in _MOTION), None)
        if motion is not None:
            self.motion = motion
            if motion in _CYCLES:
                self.cycle_vals = {}
        has_axis = any(key in words for key in "xyzabc")
        if self.motion == 800 and has_axis and motion is None:
            self.problem("G80 axis", "Axis words after G80 (cycles off) without G0/G1: no motion mode, "
                         "line skipped")
        elif has_axis or (motion in (20, 30) and ("p" in words)):
            if machine and self.motion not in (0, 10):
                self.problem("G53 mode", "G53 only works with G0 or G1: line skipped")
            elif self.motion == 0:
                self.rapid_to(self.target(words, machine), rot=self.rot_target(words, machine))
            elif self.motion == 10:
                self.feed_to(self.target(words, machine), inverse_f, rot=self.rot_target(words, machine))
            elif self.motion in (20, 30):
                self.arc_to(self.target(words), self.motion == 20, words, inverse_f, rot=self.rot_target(words))
            elif self.motion in _CYCLES:
                if any(key in words for key in ROT):
                    self.problem("cycle ABC", "A, B or C on a drilling cycle line is left out (turn the axis on a "
                                 "line of its own before the cycle)")
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
            o_r = self.origins_rot[p]
            for ax, key in enumerate(ROT):
                if key in words:
                    o_r[ax] = words[key] if l_ == 2 else self.rot[ax] - self.g92_rot[ax] - words[key]
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
            if m in (7, 8, 9) or 100 <= m <= 199:            # air / coolant switches (task 0039)
                self.prog.m_events.append((len(self.prog.moves), m, self.top_line or self.line_no))
            if m in (0, 1, 2, 3, 4, 5, 6, 19, 30, 60, 61):
                keep_m.append(m)
            elif m in _NOTED_M:
                continue
            elif 100 <= m <= 199:
                self.problem(f"M{m}", f"User M-code M{m} (runs a script on the machine) is not shown")
            else:
                self.problem(f"M{m}", f"Unknown or unsupported M-code M{m}: left out")
        for letter in "uvw":
            if letter in words:
                self.problem(f"{letter.upper()} axis", f"{letter.upper()} axis moves are not supported (only X, Y, "
                             "Z, A, B, C): that axis stays put")
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
         base_dir: str = "", start=None, rot_rapid=(3600.0, 3600.0, 3600.0), wrapped=(False, False, False),
         start_rot=None, accel=None, rot_accel=None) -> Program:
    """Run a LinuxCNC program (see the module's docstring). ``g54``: the program's zero in machine
    coordinates (mm); ``rapid``: each axis' rapid speed (mm/min); ``home``: the G28 / G30 position (machine
    coordinates; also where the machine starts unless ``start`` is given); ``tools``: {number: ToolInfo}
    from a tool table; ``base_dir``: where subroutine files (<name>.ngc) are looked for. Rotary axes A, B, C
    (task 0066): ``rot_rapid`` degrees per minute, ``wrapped`` per axis, ``start_rot`` where they are at the start
    (degrees; else 0). ``accel`` (task 0103): each axis' maximum acceleration X, Y, Z in mm/s² – the moves are then
    timed with :func:`plan_accel` (``rot_accel``: A, B, C in °/s²); None: without acceleration."""
    rd = Reader(g54=g54, rapid=rapid, home=home, tools=tools, base_dir=base_dir, start=start, rot_rapid=rot_rapid,
                wrapped=wrapped, start_rot=start_rot)
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
    if accel is not None:
        plan_accel(rd.prog, accel, rot_accel if rot_accel is not None else (3600.0, 3600.0, 3600.0))
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
# acceleration (task 0103): every move timed as the machine runs it
# ---------------------------------------------------------------------------

#: a corner sharper than this (cosine of the turn between the two moves) counts as straight on
STRAIGHT_COS = 1.0 - 1e-9
#: the machine's default maximum accelerations when nothing is typed: X, Y, Z mm/s², A, B, C °/s²
DEFAULT_ACCEL = (1000.0, 1000.0, 1000.0)
DEFAULT_ROT_ACCEL = (3600.0, 3600.0, 3600.0)


def _shape(m: Move, acc: tuple):
    """(S, start tangent, end tangent, a, speed cap) of a moving move in the six-axis space (X/Y/Z mm, A/B/C degrees
    counted as mm): S its length, the tangents unit vectors, ``a`` the largest acceleration along the path every axis
    allows, the cap the speed a circle allows (v² / r <= a of its plane's axes; inf for straight moves)."""
    ra = m.ra or NO_TURN
    rb = m.rb or ra
    drot = [rb[n] - ra[n] for n in range(3)]
    if m.kind == "ARC":
        i, j, k = PLANES[m.plane]
        rm = 0.5 * (m.r0 + m.r1)
        lp = rm * abs(m.sweep)
        dz = m.b[k] - m.a[k]
        S = math.sqrt(lp * lp + dz * dz + sum(x * x for x in drot))
        if S < 1e-12:
            return None
        sg = 1.0 if m.sweep > 0 else -1.0
        a0 = math.atan2(m.a[j] - m.centre[j], m.a[i] - m.centre[i])
        tans = []
        for ang in (a0, a0 + m.sweep):
            t = [0.0] * 6
            t[i] = -math.sin(ang) * sg * lp / S
            t[j] = math.cos(ang) * sg * lp / S
            t[k] = dz / S
            for n in range(3):
                t[3 + n] = drot[n] / S
            tans.append(t)
        spans = [(acc[i], lp), (acc[j], lp), (acc[k], abs(dz))] + [(acc[3 + n], abs(drot[n])) for n in range(3)]
        a = min((ax * S / d for ax, d in spans if d > 1e-12), default=float("inf"))
        a_n = min(acc[i], acc[j])
        cap = math.sqrt(a_n * rm) * S / lp if lp > 1e-12 and rm > 1e-12 else float("inf")
        return S, tans[0], tans[1], a, cap
    d = [m.b[n] - m.a[n] for n in range(3)] + drot
    S = math.sqrt(sum(x * x for x in d))
    if S < 1e-12:
        return None
    t = [x / S for x in d]
    a = min((acc[n] * S / abs(d[n]) for n in range(6) if abs(d[n]) > 1e-12), default=float("inf"))
    return S, t, t, a, float("inf")


def corner_speed(t_end, t_start, s_prev: float, s_next: float, a: float, tol: float, cap: float) -> float:
    """The speed (mm/s) a blended corner (G64) is taken at – LinuxCNC-like, not its exact planner: the corner is
    rounded by a circle that touches both moves, no bigger than half of the shorter move and (``tol`` > 0, G64 P)
    no further from the corner than ``tol``; the speed is the one that circle allows, v = √(a·R). A straight
    junction keeps the speed (``cap``), a reversal stops."""
    c = sum(x * y for x, y in zip(t_end, t_start))
    if c >= STRAIGHT_COS:
        return cap
    if c <= -STRAIGHT_COS:
        return 0.0
    half = 0.5 * math.acos(max(-1.0, min(1.0, c)))
    r = 0.5 * min(s_prev, s_next) / math.tan(half)
    if tol > 0:
        k = 1.0 / math.cos(half) - 1.0
        if k > 0:
            r = min(r, tol / k)
    return min(cap, math.sqrt(max(0.0, a * r)))


def profile(S: float, vs: float, ve: float, vm: float, a: float) -> tuple:
    """Trapezoid (or triangle) speed profile of a move of length ``S`` entered at ``vs`` and left at ``ve``,
    cruising at most at ``vm``, speeding up and slowing down at ``a``: (vs, vp, ve, a, S, t1, t2, T) – ``t1`` where
    speeding up ends, ``t2`` where slowing down starts, ``T`` its time."""
    vp = min(vm, math.sqrt(a * S + 0.5 * (vs * vs + ve * ve)))
    vp = max(vp, vs, ve, 1e-12)
    t1 = (vp - vs) / a
    t3 = (vp - ve) / a
    d1 = 0.5 * (vs + vp) * t1
    d3 = 0.5 * (vp + ve) * t3
    tc = max(0.0, S - d1 - d3) / vp
    return vs, vp, ve, a, S, t1, t1 + tc, t1 + tc + t3


def plan_accel(prog: Program, accel, rot_accel=DEFAULT_ROT_ACCEL) -> Program:
    """Time every move with acceleration (task 0103). ``accel``: X, Y, Z maximum acceleration (mm/s²),
    ``rot_accel``: A, B, C (°/s²). Each move keeps the speed it had without acceleration as its top speed (its feed,
    or for rapids its slowest axis at its rapid speed) and gets a trapezoid speed profile: speeding up and slowing
    down as fast as the slowest axis allows along the move's direction; arcs at most at √(a·r) (v² / r <= a). At a
    move's end the machine stops when G61 / G61.1 is in force, before and after a dwell, a tool change or a pause,
    and where the path turns back; with G64 (the default) it takes the corner at :func:`corner_speed`, so a line cut
    in many short pieces runs through. Forward and backward passes make every move's start and end speeds reachable
    (the usual look-ahead). Sets ``Move.dur`` (``dur0``: the old time), ``Move.prof``, every ``t0``, and
    ``prog.accel`` / ``plain_duration``."""
    acc = tuple(max(1e-6, float(x)) for x in accel) + tuple(max(1e-6, float(x)) for x in rot_accel)
    prog.plain_duration = prog.duration
    runs, cur = [], []
    for m in prog.moves:
        if m.moving:
            sh = _shape(m, acc)
            if sh is None or m.dur <= 0:
                if cur:
                    runs.append(cur)
                    cur = []
                continue
            cur.append((m, sh))
        elif m.kind != "SPINDLE":                              # a dwell, a tool change or a pause: the machine stops
            if cur:
                runs.append(cur)
                cur = []
    if cur:
        runs.append(cur)
    for run in runs:
        n = len(run)
        vm = [min(sh[0] / m.dur, sh[4]) for m, sh in run]
        v = [0.0] * (n + 1)
        for q in range(1, n):
            (mp, sp), (mn, sn) = run[q - 1], run[q]
            if mp.blend < 0:
                continue
            v[q] = corner_speed(sp[2], sn[1], sp[0], sn[0], min(sp[3], sn[3]), mp.blend, min(vm[q - 1], vm[q]))
        for q in range(n - 1, -1, -1):                         # every slow-down must be reachable …
            S, a = run[q][1][0], run[q][1][3]
            v[q] = min(v[q], math.sqrt(v[q + 1] ** 2 + 2 * a * S))
        for q in range(n):                                     # … and every speed-up
            S, a = run[q][1][0], run[q][1][3]
            v[q + 1] = min(v[q + 1], math.sqrt(v[q] ** 2 + 2 * a * S))
        for q, (m, sh) in enumerate(run):
            S, a = sh[0], sh[3]
            if not math.isfinite(a):
                continue
            p = profile(S, v[q], v[q + 1], vm[q], a)
            m.dur0 = m.dur
            m.dur = p[7]
            m.prof = p[:7]
    t = 0.0
    for m in prog.moves:
        m.t0 = t
        t += m.dur
    prog.accel = True
    return prog


def read_ini(text: str) -> dict:
    """The axes' limits from a LinuxCNC machine file (.ini, task 0103): {letter: {"velocity": per minute,
    "accel": per s²}} for the letters x y z a b c it gives. Linear axes in mm (``[TRAJ] LINEAR_UNITS`` inch is turned
    into mm), rotary axes in degrees. ``MAX_VELOCITY`` is per second in the file (× 60 here, as the app's rapid speeds
    are per minute). Read from ``[AXIS_X]`` … (LinuxCNC 2.8 and newer), else from ``[JOINT_n]`` with ``[TRAJ]
    COORDINATES`` (or ``[KINS] COORDINATES``) saying which letter each joint is, else from the old ``[AXIS_n]``
    sections (2.7: AXIS_0 = X …). A value that is not a plain number (``#INI`` references and the like) is left out."""
    sections: dict = {}
    cur = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and "]" in line:
            cur = sections.setdefault(line[1:line.index("]")].strip().upper(), {})
            continue
        if cur is None or "=" not in line:
            continue
        key, val = line.split("=", 1)
        cur.setdefault(key.strip().upper(), val.strip())

    def num(sec, key):
        try:
            return float(sections.get(sec, {}).get(key, ""))
        except ValueError:
            return None

    units = sections.get("TRAJ", {}).get("LINEAR_UNITS", "mm").strip().lower()
    k_lin = INCH if units in ("inch", "in", "imperial") else (1.0 if units in ("mm", "metric", "") else None)
    if k_lin is None:
        try:
            k_lin = float(units)                              # LINEAR_UNITS may be a number: mm per unit
        except ValueError:
            k_lin = 1.0
    letters = "xyzabc"
    found: dict = {}
    for letter in letters:
        sec = f"AXIS_{letter.upper()}"
        if sec in sections:
            found[letter] = sec
    if not found:
        coords = (sections.get("TRAJ", {}).get("COORDINATES") or sections.get("KINS", {}).get("COORDINATES") or "")
        coords = [c for c in coords.lower() if c.isalpha()]
        for n, letter in enumerate(coords):
            if letter in letters and letter not in found and f"JOINT_{n}" in sections:
                found[letter] = f"JOINT_{n}"
        if not found:
            for n, letter in enumerate(coords or letters):
                if letter in letters and letter not in found and f"AXIS_{n}" in sections:
                    found[letter] = f"AXIS_{n}"
    out: dict = {}
    for letter, sec in found.items():
        k = k_lin if letter in "xyz" else 1.0
        vel, acc = num(sec, "MAX_VELOCITY"), num(sec, "MAX_ACCELERATION")
        row = {}
        if vel is not None and vel > 0:
            row["velocity"] = vel * k * 60.0
        if acc is not None and acc > 0:
            row["accel"] = acc * k
        if row:
            out[letter] = row
    return out


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
    clean: float = 0.0              # s at the end: "Blow the part clean" (task 0039); 0 = none
    clean_sweep: bool = True        # air through the spindle: the tool goes over the part while it blows
    changer: object = None          # core.toolchange.Changer (task 0041); None: every change is a pause of
                                    # ``tool_change`` s with the swap at ``swap``


CLEAN = "CLEAN"                     # Move.cycle of the moves the app adds for "Blow the part clean"
CLEAN_LIFT = 15.0                   # mm above the highest cutting move: where the tool blows from
CLEAN_LANE = 25.0                   # mm between the passes over the part (at most CLEAN_LANES of them)
CLEAN_LANES = 8
CLEAN_SWEEP = 0.75                  # share of the clean time the passes take; then the tool stays still


def merge_spans(spans) -> list:
    """Overlapping or touching (start, end) spans joined, sorted."""
    out = []
    for a, b in sorted((float(a), float(b)) for a, b in spans if b > a):
        if out and a <= out[-1][1] + 1e-9:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def clean_moves(prog: Program, last, seconds: float, sweep: bool) -> list:
    """The moves of "Blow the part clean": up to CLEAN_LIFT mm above the cutting moves, then (``sweep``)
    passes over the area the program cut, then still. Returns [(Move, seconds)] that fill ``seconds``."""
    box = prog.bounds(feed_only=True) or prog.bounds()
    last = tuple(last)
    if box is None or seconds <= 0:
        return [(Move("DWELL", 0, last, last, cycle=CLEAN), seconds)] if seconds > 0 else []
    (x0, y0, _z0), (x1, y1, z1) = box
    zc = max(z1 + CLEAN_LIFT, last[2]) if not sweep else z1 + CLEAN_LIFT
    pts = [last]
    if sweep:
        n = max(2, min(CLEAN_LANES, int(math.ceil((y1 - y0) / CLEAN_LANE)) + 1))
        ys = [y0 + (y1 - y0) * k / (n - 1) for k in range(n)]
        pts.append((x0, ys[0], zc) if abs(last[2] - zc) < 1e-6 else (last[0], last[1], zc))
        for k, y in enumerate(ys):
            a, b = (x0, x1) if k % 2 == 0 else (x1, x0)
            pts += [(a, y, zc), (b, y, zc)]
    elif last[2] < zc - 1e-6:
        pts.append((last[0], last[1], zc))
    clean = []
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) > 1e-6:
            clean.append((a, b))
    total = sum(math.dist(a, b) for a, b in clean)
    move_s = seconds * (CLEAN_SWEEP if sweep else min(CLEAN_SWEEP, 0.25))
    out = []
    for a, b in clean:
        d = move_s * math.dist(a, b) / total if total > 0 else 0.0
        out.append((Move("FEED", 0, a, b, length=math.dist(a, b), cycle=CLEAN), d))
    end = clean[-1][1] if clean else last
    rest = seconds - sum(d for _m, d in out)
    if rest > 1e-9:
        out.append((Move("DWELL", 0, end, end, cycle=CLEAN), rest))
    return out


@dataclass(slots=True)
class Piece:
    """A move as it plays in the video: v0 .. v0 + vd seconds (from the step's start). A tool change carries its
    :class:`toolchange.Change` (the head's travel, the carousel, the swap)."""
    move: Move
    v0: float
    vd: float
    change: object = None


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
        self.start_rot = ((moves[0].ra or NO_TURN) if moves else ((before[-1].rb or NO_TURN) if before else NO_TURN))
        self.start_spindle = before[-1].spindle if before else 0.0
        rf = max(1e-6, float(timing.rapid_factor or 1.0))

        def raw(m):
            if m.kind == "TOOL":
                return 0.0
            return m.dur / rf if m.kind == "RAPID" else m.dur

        motion = sum(raw(m) for m in moves)
        from . import toolchange as TC
        tc = max(0.0, float(timing.tool_change))
        ch = timing.changer
        legacy = ch is None
        if legacy:
            ch = TC.Changer(pause=tc)
        self._tn = self._tn_moves(prog, moves) if ch.arm else {}
        # a double-arm changer turns its magazine at the Tn before an M6 while the machine cuts; when that is not
        # done before the arm wants the pot, that change does it at its M6 instead (planned again without it)
        late: set = set()
        for _round in range(len(self._tn) + 1):
            t = self._plan_place(moves, timing, ch, legacy, motion, raw, rf, tc, late)
            more = self._late_preps() - late
            if not more:
                break
            late |= more
        self.pocket_table = dict(ch.pockets)
        self.program_end = t
        self.clean_span = None                              # (start, end) of "Blow the part clean", s
        if timing.clean > 0 and self.pieces:
            last = self.pieces[-1].move
            for mv, d in clean_moves(prog, last.b, float(timing.clean), bool(timing.clean_sweep)):
                mv.spindle, mv.tool, mv.line, mv.top = last.spindle, last.tool, last.line, last.top
                mv.ra = mv.rb = last.rb or NO_TURN
                self.pieces.append(Piece(mv, t, d))
                t += d
            self.clean_span = (self.program_end, t)
        self.duration = t
        self._starts = [p.v0 for p in self.pieces]
        self._moves = moves

    @staticmethod
    def _tn_moves(prog: Program, moves: list) -> dict:
        """{index in ``moves`` of an M6: (index in ``moves`` of the first move after its Tn)} for the M6s that have
        a Tn of the same tool after the change before (task 0064)."""
        if not prog.t_events:
            return {}
        index = {id(m): i for i, m in enumerate(prog.moves)}
        pidx = [index.get(id(m), -1) for m in moves]
        out = {}
        prev = -1
        for k, m in enumerate(moves):
            if m.kind != "TOOL" or m.cycle == "M61":
                continue
            p = pidx[k]
            hits = [cnt for cnt, n, _line in prog.t_events if n == m.tool and prev < cnt <= p]
            if hits:
                cnt = hits[-1]
                out[k] = next((j for j in range(k + 1) if pidx[j] >= cnt), k)
            prev = p
        return out

    def _plan_place(self, moves, timing, ch, legacy, motion, raw, rf, tc, late) -> float:
        from . import toolchange as TC
        # every tool change planned first (its length), then the motion gets the rest of "Fit into"
        plans = {}
        cur = self.first_tool or ch.start_tool
        offs = self._length_tools(moves, cur)
        self.first_h = offs.get(-1, cur)
        v = ch.carousel_start
        where = dict(ch.pockets)                            # double-arm: the old tool lands in the new one's pot
        n_arm = 0
        for k, m in enumerate(moves):
            if m.kind != "TOOL":
                continue
            if m.cycle == "M61":
                cur = m.tool
                continue
            h_old, h_new = offs.get(k, (cur, m.tool))
            if ch.arm:
                c, v = TC.plan_arm(cur, m.tool, m.b, ch, v, where, rf, pre=k in self._tn and k not in late,
                                   h_old=h_old, h_new=h_new)
                if c.kind == "arm":
                    c.index = n_arm
                    n_arm += 1
                    where.pop(m.tool, None)
                    if cur:
                        where[cur] = c.new_pocket
                elif m.tool != cur:
                    where.pop(cur, None)
            else:
                c = TC.plan(cur, m.tool, m.b, ch, v, rf, h_old=h_old, h_new=h_new)
            c.h_old, c.h = h_old, h_new
            if legacy:
                c.phases = [TC.Phase("pause", tc, a=m.b, b=m.b, least=min(tc, TC.MIN_PAUSE))] if tc > 0 else []
            for _t0, _t1, _v0, v1 in c.turns():
                v = v1
            plans[k] = c
            cur = m.tool
        self.changes = list(plans.values())
        self._plans = plans
        total = sum(c.total(1.0) for c in self.changes)
        if timing.speed == "FASTER":
            scale = 1.0 / max(1e-6, float(timing.factor))
            k_tc = 1.0
        elif timing.speed == "FIT":
            fit_s = float(timing.fit_seconds)
            k_tc = TC.fit(self.changes, TC.CHANGE_SHARE * fit_s) if total > TC.CHANGE_SHARE * fit_s else 1.0
            used = sum(c.total(k_tc) for c in self.changes)
            room = max(1e-3, fit_s - used)
            scale = room / motion if motion > 0 else 1.0
        else:
            scale = 1.0
            k_tc = 1.0
        self.scale = scale
        self.change_scale = k_tc
        self.pieces: list = []
        self.tool_events: list = []                         # (video time of the swap, tool, start, length)
        t = 0.0
        for k, m in enumerate(moves):
            if m.kind == "TOOL":
                c = plans.get(k)
                if c is None:                               # M61: the tool is set, nothing moves
                    self.tool_events.append((t, m.tool, t, 0.0))
                    self.pieces.append(Piece(m, t, 0.0))
                    continue
                TC.place(c, t, k_tc)
                if legacy and c.length > 0:
                    c.swap = c.drop = t + min(max(0.0, timing.swap), c.length)
                d = c.length
                self.tool_events.append((c.swap, m.tool, t, d))
                self.pieces.append(Piece(m, t, d, c))
                t += d
                continue
            d = raw(m) * scale
            self.pieces.append(Piece(m, t, d))
            t += d
        # the magazine's work at the Tn (double-arm): from the Tn, once the change before has tipped its pot up
        free = 0.0
        for k, c in plans.items():
            if c.prep:
                j = self._tn[k]
                c.pre_at = self.pieces[j].v0 if j < len(self.pieces) else t
                TC.place_prep(c, max(c.pre_at, free), k_tc)
            if c.kind == "arm":
                free = c.start + c.length
        return t

    @staticmethod
    def _length_tools(moves: list, first: int) -> dict:
        """Whose length offset is in force (task 0096): {index of an M6 in ``moves``: (tool before, tool after)} and
        {-1: tool at the step's start}. The tool after an M6 is the one its first move after it runs with: the new
        tool, or with no G43 for it the tool of the offset still in force (``Move.h``)."""
        out: dict = {}
        before = first
        start = None
        pending = None                                     # the M6 waiting for its first move
        changed = False
        for k, m in enumerate(moves):
            if m.kind == "TOOL":
                changed = True
                if m.cycle == "M61":
                    before, pending = m.tool, None
                    continue
                out[k] = (before, m.tool)
                before, pending = m.tool, k
                continue
            if not m.moving:
                continue
            h = m.h or m.tool or before
            if start is None and not changed:
                start = h
            if pending is not None:
                out[pending] = (out[pending][0], h)
                pending = None
            before = h
        out[-1] = start if start is not None else first
        return out

    def _late_preps(self) -> set:
        """Indexes (in the step's moves) of the M6s whose magazine work at the Tn is not done in time."""
        from . import toolchange as TC
        out = set()
        for k, c in self._plans.items():
            if c.prep and c.prep[-1].t0 + c.prep[-1].dur > TC.arm_start(c) + 1e-9:
                out.add(k)
        return out

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
        if p.change is not None:
            return p.change.point_at(t, p.move.b)
        return p.move.at(p.move.u_of((t - p.v0) / p.vd))

    def rot_at(self, t: float) -> tuple:
        """The rotary axes A, B, C (degrees) ``t`` seconds into the step (task 0066). They stay put during a tool
        change and while the part is blown clean."""
        if not self.pieces:
            return tuple(self.start_rot)
        if t >= self.duration:
            return tuple(self.pieces[-1].move.rb or NO_TURN)
        p = self.piece_at(t)
        if p is None:
            return tuple(self.start_rot)
        if p.vd <= 0 or p.change is not None:
            return tuple(p.move.rb or NO_TURN)
        return p.move.rot_at(p.move.u_of((t - p.v0) / p.vd))

    @property
    def turns(self) -> bool:
        """True when a rotary axis moves in this step."""
        return any(p.move.moving and p.move.turn > TURN_EPS for p in self.pieces)

    def turns_or_turned(self) -> bool:
        """True when a rotary axis moves in this step or stands away from 0 in it."""
        return self.turns or any(abs(x) > TURN_EPS for p in self.pieces[:1] for x in (p.move.ra or NO_TURN))

    def turn_spans(self) -> list:
        """[(start, end)] seconds of the moves in which a rotary axis turns (joined where they touch)."""
        return merge_spans((p.v0, p.v0 + p.vd) for p in self.pieces
                           if p.move.moving and p.move.turn > TURN_EPS and p.vd > 0)

    def velocity_at(self, t: float, side: int) -> tuple:
        """The tool tip's velocity (mm/s) at ``t`` coming in (``side`` -1) or going on (+1) (task 0103); (0, 0, 0)
        where nothing moves."""
        import bisect
        if not self.pieces:
            return (0.0, 0.0, 0.0)
        if side < 0:
            k = bisect.bisect_left(self._starts, t) - 1          # the piece that started before t
        else:
            k = bisect.bisect_right(self._starts, t) - 1
        while 0 <= k < len(self.pieces) and self.pieces[k].vd <= 0 and side > 0:
            k += 1
        if not 0 <= k < len(self.pieces):
            return (0.0, 0.0, 0.0)
        p = self.pieces[k]
        if p.vd <= 0 or not p.move.moving or p.change is not None or not (p.v0 - 1e-9 <= t <= p.v0 + p.vd + 1e-9):
            return (0.0, 0.0, 0.0)
        return tuple(x / p.vd for x in p.move.velocity((t - p.v0) / p.vd))

    def speed_changes(self) -> list:
        """[(start, end)] seconds (sorted, joined) in which a move speeds up or slows down (task 0103)."""
        out = []
        for p in self.pieces:
            m = p.move
            if p.vd <= 0 or p.change is not None or not m.prof:
                continue
            ph = m.phase_times()
            if ph[0] > 1e-12:
                out.append((p.v0, p.v0 + ph[0] * p.vd))
            if ph[1] < 1 - 1e-12:
                out.append((p.v0 + ph[1] * p.vd, p.v0 + p.vd))
        return merge_spans(out)

    def samples(self, fps: float, tol: float = 0.002, per_frame: bool = True, turn_step: float = 0.0):
        """Times (s from the step's start) where the path needs a key so that straight keys between them
        follow it within ``tol`` mm: every move's start and end, and along arcs every frame plus as many
        points as the chord error needs; with acceleration (task 0103) also where a move stops speeding up and
        starts slowing down (keys that need Bezier handles from the speed between them). ``turn_step`` (degrees, task 0066): in a move that turns a rotary axis,
        a key at least every this many degrees (the tool following the turning part). Returns sorted
        [(t, (x, y, z))]."""
        out = []
        if self.start_point is None:
            return out
        out.append((0.0, self.start_point))
        for p in self.pieces:
            m = p.move
            if not m.moving:
                if p.change is not None and p.change.moves:      # the head goes to the changer and back
                    out += [(t, pt) for t, pt in p.change.knots()]
                if p.vd > 0:
                    out.append((p.v0 + p.vd, m.b))
                continue
            turning = turn_step > 0 and m.turn > TURN_EPS
            ph = m.phase_times() if p.vd > 0 else ()
            if ph and ph[0] < 1e-9 and ph[1] > 1 - 1e-9:
                ph = ()                                         # full speed all the way: the place goes with the time
            if (m.kind == "ARC" or turning or ph) and p.vd > 0:
                taus = set()                                    # shares of the move's time
                us = set()                                      # shares of its path
                if m.kind == "ARC":
                    r = max(m.r0, m.r1, 1e-6)
                    step = 2 * math.acos(max(-1.0, 1 - tol / r)) if tol < r else math.pi / 2
                    n = max(1, int(math.ceil(abs(m.sweep) / max(step, 1e-6))))
                    us |= {k / n for k in range(1, n)}
                if turning:
                    n = min(20000, max(1, int(math.ceil(m.turn / turn_step))))
                    us |= {k / n for k in range(1, n)}
                if ph:                                          # task 0103: where speeding up ends, slowing starts
                    taus |= set(ph)
                # a straight move needs keys only where its speed changes: the app gives them Bezier handles from
                # the speed, so the parabola between them is exact (blender/gcode.bake_step)
                if per_frame and (m.kind == "ARC" or turning):
                    f0 = math.floor(p.v0 * fps) + 1
                    f1 = math.ceil((p.v0 + p.vd) * fps)
                    taus |= {(f / fps - p.v0) / p.vd for f in range(f0, f1)}
                taus |= {m.tau_of(u) for u in us}
                for tau in sorted(x for x in taus if 0 < x < 1):
                    out.append((p.v0 + tau * p.vd, m.at(m.u_of(tau))))
            out.append((p.v0 + p.vd, m.b))
        # drop keys that land on the same moment (the later point wins: zero-length pieces)
        clean = []
        for t, pt in out:
            if clean and abs(clean[-1][0] - t) < 1e-9:
                clean[-1] = (t, pt)
            else:
                clean.append((t, pt))
        return clean

    def m_times(self) -> list:
        """[(video time, M number)] of the coolant / air codes in the program (task 0039). Codes before the
        first line shown come at 0, codes after the last line shown are left out."""
        prog = self.prog
        if not prog.m_events:
            return []
        index = {id(m): i for i, m in enumerate(prog.moves)}
        starts = [(index[id(p.move)], p.v0) for p in self.pieces if id(p.move) in index]
        lo = max(1, int(self.timing.line_from or 1))
        hi = int(self.timing.line_to) if self.timing.line_to and self.timing.line_to >= lo else 10 ** 12
        out = []
        import bisect
        keys = [k for k, _v in starts]
        for k, m, top in prog.m_events:
            if top > hi:
                continue
            if top < lo:
                out.append((0.0, m))
                continue
            j = bisect.bisect_left(keys, k)
            out.append((starts[j][1] if j < len(starts) else self.program_end, m))
        out.sort(key=lambda x: x[0])
        return out

    def air_spans(self, on_code: int = 7, off_code: int = 9, always: bool = False) -> list:
        """[(start, end)] video seconds while air blows: from the program's ``on_code`` to its ``off_code``
        (M9 also stops M7 / M8), and with ``always`` while the spindle turns. "Blow the part clean" is not in
        it (``clean_span``)."""
        spans = []
        on_at = None
        for t, m in self.m_times():
            if m == on_code and on_at is None:
                on_at = t
            elif on_at is not None and (m == off_code or (m == 9 and on_code in (7, 8))):
                spans.append((on_at, t))
                on_at = None
        if on_at is not None:
            spans.append((on_at, self.program_end))
        if always:
            keys = self.spindle_keys() + [(self.program_end, 0.0)]
            for (t0, rpm), (t1, _r) in zip(keys, keys[1:]):
                if abs(rpm) > 1e-9 and t1 > t0:
                    spans.append((t0, min(t1, self.program_end)))
        return merge_spans(spans)

    def spindle_keys(self):
        """[(t, rpm)] where the spindle's speed changes (signed rpm, + = clockwise)."""
        out = [(0.0, self.start_spindle)]
        for p in self.pieces:
            if p.move.spindle != out[-1][1]:
                out.append((p.v0, p.move.spindle))
        return out

    def path(self, tol: float = 0.01, max_step: float = 0.0, turn_step: float = 0.0):
        """Polylines of the path for drawing: [(rapid?, [(x, y, z, t)...])], consecutive feed moves joined.
        ``max_step``: split long straight moves so no piece takes longer than this (s), for the "already
        milled" colour; 0 = not split. ``turn_step``: split moves that turn a rotary axis every this many
        degrees (task 0066: drawn on the turning part they are curves); 0 = not split."""
        lines = []
        cur = None
        for p in self.pieces:
            m = p.move
            if not m.moving or m.cycle == CLEAN:
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
            if turn_step > 0 and m.turn > TURN_EPS:
                n = max(n, int(math.ceil(m.turn / turn_step)))
            n = min(n, 2000)
            for k in range(1, n + 1):
                u = k / n
                pt = m.at(u)
                cur[1].append((pt[0], pt[1], pt[2], p.v0 + m.tau_of(u) * p.vd))
        return lines
