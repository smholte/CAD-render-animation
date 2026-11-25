"""Weld symbols and the weld list (task 0320), no Blender: what an ISO 2553 symbol of a weld says, and the rows of
the weld list and its CSV.

**ISO 2553, system A** (the one used in Europe): an arrow line from the seam to a *reference line*; a solid reference
line with a dashed line beside it. The symbol of a weld on the **arrow side** sits on the solid line's lower side, of
a weld on the **other side** above the dashed line; a weld on **both sides** (symmetric) has its symbol on both sides
of the solid line and no dashed line. Left of the symbol the size, right of it the length:

* fillet: ``a5 ◸ 300`` (a = the throat), the triangle with its upright leg on the left;
* butt: ``‖`` (square butt, plates up to 4 mm) or ``V`` (single-V, thicker): full penetration, no size; length after;
* intermittent: ``a5 ◸ 4 × 50 (100)`` = n pieces of l, a gap e between them (ISO's e is the *gap*, the app's pitch
  is from start to start: e = pitch − l);
* all round: a circle where the arrow line meets the reference line;
* ground flush: a bar over the symbol (``‾`` in the text form);
* the tail ``<`` carries the process number of ISO 4063 (MAG 135, MIG 131, TIG 141, stick 111).

The symbol describes a weld's **main seam** (its longest ticked one); "both sides" when a second ticked seam of the
same kind is as long (within 10 %) – a fin welded on both sides, a tube through a plate welded round on both faces,
a butt welded from both faces (a double-V). The weld list shows every seam's length summed.

Text form: ``lines(sym)`` gives the line above the reference line (other side) and the one below (arrow side); the
viewport draws them on a drawn reference line, a render puts them in a label box (the app's label style).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

FILLET = "◸"                 # arrow side: below the line (the right angle at the top left)
FILLET_OTHER = "◺"           # other side: on the line (the right angle at the bottom left)
SQUARE_BUTT = "‖"
V_BUTT = "V"
V_BUTT_OTHER = "Λ"           # (drawn hanging below: the V seen from the arrow side)
FLUSH = "‾"
ALL_ROUND = "○"
SQUARE_UP_TO_MM = 4.0        # butt welds of plates up to 4 mm: square butt (I); thicker: single-V
SAME_LENGTH = 0.10           # two seams within 10 % of each other's length: both sides

PROCESS_NUMBER = {"MAG": "135", "MIG": "131", "TIG": "141", "STICK": "111"}
PROCESS_WORD = {"MAG": "MAG", "MIG": "MIG", "TIG": "TIG", "STICK": "Stick"}
FINISH_WORD = {"AS_WELDED": "As welded", "PAINTED": "Painted", "GROUND": "Ground flush"}
METAL_WORD = {"STEEL": "Steel", "STAINLESS": "Stainless", "ALUMINIUM": "Aluminium"}


@dataclass
class Seam:
    """A ticked seam: its kind (FILLET / BUTT), length (m) and whether it goes all round."""
    kind: str
    length: float
    closed: bool = False


@dataclass
class Weld:
    """What the symbol and the list need of one weld (sizes in metres)."""
    number: int
    name: str = ""
    part_a: str = ""
    part_b: str = ""
    kind: str = "AUTO"              # AUTO (as found) / FILLET / BUTT
    size: float = 0.005             # fillet: the throat a
    thickness: float = 0.0          # the thinner plate (m; 0 = not known): square or V butt
    seams: list = field(default_factory=list)      # [Seam] – the ticked ones
    intermittent: bool = False
    piece: float = 0.05
    pitch: float = 0.15
    process: str = "MAG"
    finish: str = "AS_WELDED"
    metal: str = "STEEL"
    lost: bool = False


@dataclass
class Symbol:
    number: int
    kind: str                       # FILLET / BUTT
    glyph: str                      # the symbol on the arrow side
    glyph_other: str                # … and on the other side (both sides)
    size: str                       # "a5" / ""
    length: str                     # "300" / "4 × 50 (100)" / ""
    both_sides: bool
    all_round: bool
    flush: bool
    tail: str                       # "135"


def _mm(x: float) -> str:
    """A length in whole mm, or with one decimal below 20 mm ("a3.5", "a12.5"); halves round up. Not a number: "?"."""
    import math
    v = float(x) * 1000.0
    if not math.isfinite(v):
        return "?"
    whole = math.floor(v + 0.5)
    if abs(v - whole) < 0.05 or v >= 20.0:
        return str(int(whole))
    return f"{math.floor(v * 10.0 + 0.5) / 10.0:.1f}"


def seam_kind(weld: Weld, seam: Seam) -> str:
    return weld.kind if weld.kind in ("FILLET", "BUTT") else (seam.kind if seam.kind in ("FILLET", "BUTT") else "FILLET")


def main_seam(weld: Weld) -> Seam | None:
    return max(weld.seams, key=lambda s: s.length) if weld.seams else None


def both_sides(weld: Weld) -> bool:
    """A second ticked seam of the same kind as long as the main one (within 10 %): welded on both sides."""
    m = main_seam(weld)
    if m is None:
        return False
    k = seam_kind(weld, m)
    same = [s for s in weld.seams if seam_kind(weld, s) == k and s.closed == m.closed
            and abs(s.length - m.length) <= SAME_LENGTH * max(m.length, 1e-9)]
    return len(same) >= 2


def intermittent_text(length: float, piece: float, pitch: float, closed: bool) -> str:
    """'n × l (e)' of an intermittent seam of ``length`` (the pieces as the bead lays them: core.welds.pieces_of);
    '' when it comes out continuous."""
    if pitch < piece + 0.001 or length <= piece:
        return ""
    if closed:
        n = max(1, int(round(length / pitch)))
        p = length / n
        if p < piece + 0.001:
            return ""
    else:
        n = max(1, int((length - piece) // pitch) + 1)
        p = pitch
    if n == 1:
        return f"1 × {_mm(piece)}"                 # one piece: no gap to give
    return f"{n} × {_mm(piece)} ({_mm(p - piece)})"


def symbol(weld: Weld) -> Symbol | None:
    """The ISO 2553 symbol of a weld; None when it has no ticked seam (or is lost)."""
    m = main_seam(weld)
    if m is None or weld.lost:
        return None
    kind = seam_kind(weld, m)
    if kind == "FILLET":
        glyph, other, size = FILLET, FILLET_OTHER, f"a{_mm(weld.size)}"
    else:
        square = 0.0 < weld.thickness * 1000.0 <= SQUARE_UP_TO_MM
        glyph, other, size = (SQUARE_BUTT, SQUARE_BUTT, "") if square else (V_BUTT_OTHER, V_BUTT, "")
    length = ""
    if weld.intermittent:
        length = intermittent_text(m.length, weld.piece, weld.pitch, m.closed)
    if not length:
        length = _mm(m.length)
    return Symbol(number=weld.number, kind=kind, glyph=glyph, glyph_other=other, size=size, length=length,
                  both_sides=both_sides(weld), all_round=bool(m.closed), flush=weld.finish == "GROUND",
                  tail=PROCESS_NUMBER.get(weld.process, ""))


def side_text(sym: Symbol, other: bool = False) -> str:
    """'a5 ◸ 300' – one side's text (``other``: the glyph as drawn above the line)."""
    g = sym.glyph_other if other else sym.glyph
    if sym.flush:
        g = FLUSH + g
    return " ".join(x for x in (sym.size, g, sym.length) if x)


def lines(sym: Symbol) -> tuple[str, str]:
    """(above the reference line, below it): system A – arrow side below, both sides on both."""
    below = side_text(sym)
    return (side_text(sym, other=True) if sym.both_sides else "", below)


def label_text(sym: Symbol) -> str:
    """The symbol as a label's text (a render with 'Show in renders'): number, all round, the sides, the tail."""
    above, below = lines(sym)
    head = f"{sym.number}  " + (ALL_ROUND + " " if sym.all_round else "")
    tail = f"  < {sym.tail}" if sym.tail else ""
    if above:
        return f"{head}{above}\n{' ' * len(head)}{below}{tail}"
    return f"{head}{below}{tail}"


def one_line(sym: Symbol) -> str:
    """The symbol on one line (the weld list): 'a5 ◸ 300', both sides 'a5 ◺/◸ 300', all round '○ …', '< 135'."""
    g = (sym.glyph_other + "/" + sym.glyph) if sym.both_sides else sym.glyph
    if sym.flush:
        g = FLUSH + g
    body = " ".join(x for x in (sym.size, g, sym.length) if x)
    return ((ALL_ROUND + " ") if sym.all_round else "") + body + (f" < {sym.tail}" if sym.tail else "")


# ---------------------------------------------------------------------------
# the weld list
# ---------------------------------------------------------------------------

COLUMNS = ("No.", "Weld", "First part", "Second part", "Type", "Size", "Length (mm)", "Process", "Finish", "Metal",
           "Symbol")


def type_words(weld: Weld) -> str:
    sym = symbol(weld)
    if sym is None:
        return "lost" if weld.lost else "no seam ticked"
    if sym.kind == "FILLET":
        word = "Fillet, both sides" if sym.both_sides else "Fillet"
    elif sym.glyph == SQUARE_BUTT:
        word = "Square butt, both sides" if sym.both_sides else "Square butt"
    else:
        word = "Double-V butt" if sym.both_sides else "Single-V butt"
    if sym.all_round:
        word += ", all round"
    if weld.intermittent and "×" in sym.length:
        word += ", intermittent"
    return word


def row(weld: Weld) -> list[str]:
    """One row of the weld list (the columns of ``COLUMNS``)."""
    sym = symbol(weld)
    total = sum(s.length for s in weld.seams)
    size = sym.size if sym is not None else ""
    proc = PROCESS_WORD.get(weld.process, weld.process)
    if weld.process in PROCESS_NUMBER:
        proc += f" ({PROCESS_NUMBER[weld.process]})"
    return [str(weld.number), weld.name, weld.part_a, weld.part_b, type_words(weld), size or "–",
            f"{total * 1000:.0f}", proc, FINISH_WORD.get(weld.finish, weld.finish),
            METAL_WORD.get(weld.metal, weld.metal), one_line(sym) if sym is not None else ""]


def table(welds: list) -> list[list[str]]:
    return [list(COLUMNS)] + [row(w) for w in welds]


def _safe_cell(text: str) -> str:
    """A cell a spreadsheet would read as a formula (=, +, -, @ at its start) gets a ' in front: names come from STEP
    files."""
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def to_csv(welds: list) -> str:
    """The weld list as CSV text (comma-separated, a header row; UTF-8 with a byte-order mark when written, so Excel
    reads the symbols right)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for r in table(welds):
        w.writerow([_safe_cell(c) for c in r])
    return buf.getvalue()


def write_csv(path: str, welds: list) -> str:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(to_csv(welds))
    return path
