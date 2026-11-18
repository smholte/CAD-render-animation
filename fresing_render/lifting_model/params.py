"""The numbers of a crane made in the app (task 0204, "Make a crane…") – plain Python, no OpenCascade, no Blender.

Each kind (mobile telescopic AT, crawler CC, knuckle-boom KB) has the numbers a user may change, each a ``Field`` with
its label, unit, fold, limits and how it is shown (mm shown as m where natural). A crane's numbers are a plain dict
``values`` in the dataclass's own units (``classes.Mobile`` / ``Crawler`` / ``Knuckle``: mm, t, degrees); the dialog
shows them in ``Field.unit`` (``to_ui`` / ``from_ui``, rounded so the class's own numbers come back exactly).

- ``of_class(name)``: the numbers of a built-in class (the dialog's **Start from**);
- ``validate(kind, values)``: every rule that fails, as ``Problem(rule, text)`` in plain words – ranges, the rules
  between the numbers (sections fit inside each other, spreads full > middle > narrow, counterweight steps rising,
  tracks long enough for the upper's tail …), then the maker's own geometry (axles, cylinders, sections that keep
  enough of themselves in the one below) and at least one stable chart;
- ``to_class(kind, values, name)``: the dataclass the makers take (``classes.layout``, ``charts.charts_of``,
  ``mobile/crawler/knuckle.build``, ``equipment.data``);
- ``suggest_masses(kind, values, start)``: the masses (and hook block) from the start class's own rule, scaled by the
  sizes that changed – the class's own numbers give the class's own masses;
- ``random_values(kind, rng, start)``: a valid random set near a class (the tests make ≥ 20 per kind).
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from . import classes as C

KINDS = ("AT", "CC", "KB")
KIND_LABELS = {"AT": "Mobile telescopic crane", "CC": "Crawler crane", "KB": "Knuckle-boom crane"}
FOLDS = {
    "AT": ("Crane", "Boom", "Carrier", "Outriggers", "Counterweight", "Hoist & hook", "Masses"),
    "CC": ("Crane", "Boom", "Tracks", "Counterweight", "Hoist & hook", "Masses"),
    "KB": ("Crane", "Boom", "Truck", "Stabilisers", "Hoist & hook", "Masses"),
}
MASS_KEYS = {
    "AT": ("mass_carrier", "mass_upper", "mass_boom", "hook_mass"),
    "CC": ("mass_lower", "mass_upper", "mass_boom", "mass_jib", "hook_mass"),
    "KB": ("mass_truck", "mass_column", "mass_main", "mass_outer", "hook_mass"),
}


@dataclass(frozen=True)
class Field:
    key: str            # the key in ``values``
    label: str
    unit: str           # as shown: "m", "mm", "t", "deg", "m/s", "t·m", "" (a count)
    fold: str
    lo: float           # limits in the shown unit
    hi: float
    scale: float = 1.0  # stored = shown x scale (m shown, mm stored: 1000)
    digits: int = 1     # stored value rounded to this many decimals (float32 of the UI must give the class back)
    integer: bool = False
    is_list: bool = False   # a list of numbers (m), typed as "24, 30, 36"
    tip: str = ""

    def to_ui(self, v):
        if self.is_list:
            return ", ".join(f"{x / self.scale:g}" for x in v)
        return int(v) if self.integer else v / self.scale

    def from_ui(self, v):
        if self.is_list:
            return parse_list(v, self.scale, self.digits)
        if self.integer:
            return int(round(float(v)))
        return round(float(v) * self.scale, self.digits)

    def shown(self, v) -> str:
        if self.is_list:
            return self.to_ui(v) + (f" {self.unit}" if self.unit else "")
        x = self.to_ui(v)
        return f"{x:g}" + (f" {self.unit}" if self.unit else "")


def parse_list(text, scale: float = 1.0, digits: int = 3) -> tuple:
    """'24, 30, 36' (also ';' or spaces; a decimal comma only with ';') -> (24.0, 30.0, 36.0) x scale. ValueError
    naming the piece that is not a number."""
    if isinstance(text, (tuple, list)):
        return tuple(round(float(x) * scale, digits) for x in text)
    s = str(text).strip()
    if not s:
        return ()
    if ";" in s:
        pieces = [p.strip().replace(",", ".") for p in s.split(";")]
    else:
        pieces = [p for p in s.replace(",", " ").split()]
    out = []
    for p in pieces:
        if not p:
            continue
        try:
            x = float(p)
        except ValueError:
            raise ValueError(f"'{p}' is not a number") from None
        if not math.isfinite(x):
            raise ValueError(f"'{p}' is not a number")
        out.append(round(x * scale, digits))
    return tuple(out)


def _F(key, label, unit, fold, lo, hi, **kw):
    if unit == "m" and "scale" not in kw and not kw.get("is_list"):
        kw["scale"] = 1000.0
    return Field(key, label, unit, fold, float(lo), float(hi), **kw)


AT_FIELDS = (
    _F("rated", "Rated capacity", "t", "Crane", 10, 1200, tip="The class number: t at the shortest radius"),
    _F("wind_max", "Chart wind speed", "m/s", "Crane", 5, 20, tip="The charts' wind (3 s gust at the boom head)"),
    _F("sections", "Boom sections", "", "Boom", 2, 9, integer=True, tip="Base section included"),
    _F("L0", "Boom retracted", "m", "Boom", 6, 30, tip="Luff pin to head sheave, every section in"),
    _F("Lmax", "Boom fully out", "m", "Boom", 12, 120, tip="Luff pin to head sheave, every section out"),
    _F("boom_w", "Base section width", "m", "Boom", 0.3, 2.5),
    _F("boom_h", "Base section height", "m", "Boom", 0.4, 3.0),
    _F("wall", "Section wall", "mm", "Boom", 5, 40),
    _F("gap", "Gap between sections", "mm", "Boom", 10, 80),
    _F("luff_max", "Steepest boom angle", "deg", "Boom", 60, 85),
    _F("axles", "Axles", "", "Carrier", 2, 10, integer=True),
    _F("wheel_r", "Wheel radius", "mm", "Carrier", 450, 900),
    _F("width", "Carrier width", "m", "Carrier", 2.3, 3.5),
    _F("spread_full", "Spread full", "m", "Outriggers", 3, 14, tip="Pad centre to pad centre, across"),
    _F("spread_middle", "Spread middle", "m", "Outriggers", 2.6, 14),
    _F("spread_narrow", "Spread narrow", "m", "Outriggers", 2.4, 14),
    _F("span_x", "Front to rear pads", "m", "Outriggers", 3, 14),
    _F("cw_1", "Counterweight step 1", "t", "Counterweight", 0, 300, digits=3),
    _F("cw_2", "Counterweight step 2", "t", "Counterweight", 0, 300, digits=3),
    _F("cw_3", "Counterweight step 3", "t", "Counterweight", 0, 300, digits=3, tip="The model carries the largest"),
    _F("cw_x", "Counterweight behind the slew axis", "m", "Counterweight", 1.5, 9),
    _F("hook_falls", "Falls of rope", "", "Hoist & hook", 2, 32, integer=True, tip="An even number"),
    _F("line_pull", "Line pull per fall", "t", "Hoist & hook", 1, 30, digits=3),
    _F("block_h", "Hook block height", "m", "Hoist & hook", 0.4, 4),
    _F("hook_mass", "Hook block mass", "t", "Masses", 0.05, 20, digits=3),
    _F("mass_carrier", "Carrier (with outriggers)", "t", "Masses", 5, 200, digits=3),
    _F("mass_upper", "Superstructure", "t", "Masses", 1, 120, digits=3, tip="Without counterweight and boom"),
    _F("mass_boom", "Boom", "t", "Masses", 0.5, 120, digits=3, tip="Every section and the head"),
)

CC_FIELDS = (
    _F("rated", "Rated capacity", "t", "Crane", 20, 3000),
    _F("wind_max", "Chart wind speed", "m/s", "Crane", 5, 20),
    _F("boom_cad", "Model's boom", "m", "Boom", 12, 200, tip="The boom drawn in the model: one of the chart lengths"),
    _F("boom_lengths", "Chart boom lengths", "m", "Boom", 6, 250, is_list=True, scale=1.0, digits=3,
       tip="Rising, e.g. 18, 24, 30"),
    _F("boom_w", "Lattice section", "m", "Boom", 0.8, 6),
    _F("luff_cad", "Boom angle in the model", "deg", "Boom", 20, 85),
    _F("luff_min", "Flattest boom angle", "deg", "Boom", 0, 80),
    _F("luff_max", "Steepest boom angle", "deg", "Boom", 30, 88),
    _F("jib_cad", "Model's luffing jib (0 = none)", "m", "Boom", 0, 120),
    _F("jib_lengths", "Chart jib lengths", "m", "Boom", 6, 150, is_list=True, scale=1.0, digits=3),
    _F("jib_angle", "Jib against the boom in the model", "deg", "Boom", -50, 0),
    _F("pitch", "Track link pitch", "mm", "Tracks", 120, 600),
    _F("teeth", "Sprocket teeth", "", "Tracks", 8, 24, integer=True, tip="An even number"),
    _F("run_links", "Links on the ground", "", "Tracks", 12, 80, integer=True),
    _F("shoe_w", "Track shoe width", "m", "Tracks", 0.4, 3),
    _F("gauge", "Track gauge", "m", "Tracks", 2, 16, tip="Track centre to track centre"),
    _F("cw_1", "Counterweight step 1", "t", "Counterweight", 0, 1500, digits=3),
    _F("cw_2", "Counterweight step 2", "t", "Counterweight", 0, 1500, digits=3, tip="The model carries the largest"),
    _F("cw_x", "Counterweight behind the slew axis", "m", "Counterweight", 2, 16),
    _F("hook_falls", "Falls of rope", "", "Hoist & hook", 2, 48, integer=True, tip="An even number"),
    _F("line_pull", "Line pull per fall", "t", "Hoist & hook", 1, 50, digits=3),
    _F("block_h", "Hook block height", "m", "Hoist & hook", 0.6, 6),
    _F("hook_mass", "Hook block mass", "t", "Masses", 0.1, 60, digits=3),
    _F("mass_lower", "Carbody and tracks", "t", "Masses", 5, 1500, digits=3),
    _F("mass_upper", "Upper works", "t", "Masses", 5, 1000, digits=3, tip="Without counterweight"),
    _F("mass_boom", "Model's boom", "t", "Masses", 1, 600, digits=3),
    _F("mass_jib", "Model's jib", "t", "Masses", 0, 300, digits=3),
)

KB_FIELDS = (
    _F("moment", "Lifting moment", "t·m", "Crane", 5, 400, tip="The class number"),
    _F("max_cap", "Capacity at the shortest outreach", "t", "Crane", 0.5, 150, digits=3),
    _F("wind_max", "Chart wind speed", "m/s", "Crane", 5, 20),
    _F("main_len", "Main boom", "m", "Boom", 1.5, 12, tip="Column pin to knuckle pin"),
    _F("outer_len", "Outer boom", "m", "Boom", 1.5, 10, tip="Knuckle pin to tip, extensions in"),
    _F("extensions", "Extensions", "", "Boom", 1, 9, integer=True),
    _F("ext_stroke", "Stroke per extension", "m", "Boom", 0.4, 6),
    _F("boom_w", "Boom width", "m", "Boom", 0.15, 1.2),
    _F("boom_h", "Boom height", "m", "Boom", 0.2, 1.5),
    _F("main_cad", "Main boom angle in the model", "deg", "Boom", -10, 80),
    _F("main_min", "Main boom lowest", "deg", "Boom", -30, 30),
    _F("main_max", "Main boom highest", "deg", "Boom", 30, 85),
    _F("knuckle_cad", "Knuckle in the model", "deg", "Boom", -150, 0, tip="0 = in line, negative = folded down"),
    _F("knuckle_min", "Knuckle most folded", "deg", "Boom", -160, -20),
    _F("knuckle_max", "Knuckle most open", "deg", "Boom", -20, 30),
    _F("axles", "Axles", "", "Truck", 2, 4, integer=True),
    _F("wheel_r", "Wheel radius", "mm", "Truck", 400, 700),
    _F("width", "Truck width", "m", "Truck", 2.2, 2.6),
    _F("spread_full", "Spread full", "m", "Stabilisers", 2.5, 14, tip="Pad centre to pad centre, across"),
    _F("spread_narrow", "Spread narrow", "m", "Stabilisers", 2.2, 14),
    _F("line_pull", "Winch line pull", "t", "Hoist & hook", 0.2, 20, digits=3),
    _F("block_h", "Hook block height", "m", "Hoist & hook", 0.2, 2),
    _F("hook_mass", "Hook block mass", "t", "Masses", 0.01, 2, digits=3),
    _F("mass_truck", "Truck (with stabilisers)", "t", "Masses", 3, 60, digits=3),
    _F("mass_column", "Column and base", "t", "Masses", 0.2, 20, digits=3),
    _F("mass_main", "Main boom", "t", "Masses", 0.2, 20, digits=3),
    _F("mass_outer", "Outer boom and extensions", "t", "Masses", 0.2, 30, digits=3),
)

FIELDS = {"AT": AT_FIELDS, "CC": CC_FIELDS, "KB": KB_FIELDS}


def field(kind: str, key: str) -> Field:
    return next(f for f in FIELDS[kind] if f.key == key)


def fields_in(kind: str, fold: str) -> list:
    return [f for f in FIELDS[kind] if f.fold == fold]


# ---------------------------------------------------------------------------------------------------------------------
# class <-> values

def of_class(name_or_cls) -> dict:
    """The numbers of a class as ``values`` (the dataclass's units)."""
    c = C.CLASSES[name_or_cls] if isinstance(name_or_cls, str) else name_or_cls
    d = {f.name: getattr(c, f.name) for f in dataclasses.fields(c)}
    v = {}
    for f in FIELDS[c.kind]:
        if f.key in d:
            v[f.key] = d[f.key]
    if c.kind == "AT":
        v["spread_full"], v["spread_middle"], v["spread_narrow"] = c.spread
        v["cw_1"], v["cw_2"], v["cw_3"] = c.counterweights
    elif c.kind == "CC":
        v["cw_1"], v["cw_2"] = c.counterweights
        v["boom_lengths"] = tuple(float(x) for x in c.boom_lengths)
        v["jib_lengths"] = tuple(float(x) for x in c.jib_lengths)
    else:
        v["spread_full"], v["spread_narrow"] = c.spread
        v["main_min"], v["main_max"] = c.main_range
        v["knuckle_min"], v["knuckle_max"] = c.knuckle_range
    for f in FIELDS[c.kind]:
        if f.integer:
            v[f.key] = int(v[f.key])
        elif f.is_list:
            v[f.key] = tuple(float(x) for x in v[f.key])
        else:
            v[f.key] = float(v[f.key])
    return v


def to_class(kind: str, values: dict, name: str = "Crane"):
    """The dataclass the makers take. No checks: call ``validate`` first."""
    v = dict(values)
    if kind == "AT":
        keys = {f.name for f in dataclasses.fields(C.Mobile)}
        args = {k: v[k] for k in keys if k in v}
        args.update(spread=(v["spread_full"], v["spread_middle"], v["spread_narrow"]),
                    counterweights=(v["cw_1"], v["cw_2"], v["cw_3"]))
        args.pop("name", None)
        args.pop("kind", None)
        return C.Mobile(name=name, **args)
    if kind == "CC":
        keys = {f.name for f in dataclasses.fields(C.Crawler)}
        args = {k: v[k] for k in keys if k in v}
        jib = v.get("jib_cad", 0.0) > 0
        args.update(counterweights=(v["cw_1"], v["cw_2"]),
                    boom_lengths=tuple(_num(x) for x in v["boom_lengths"]),
                    jib_lengths=tuple(_num(x) for x in v["jib_lengths"]) if jib else (),
                    jib_boom=_num(v["boom_cad"] / 1000.0) if jib else 0.0,
                    jib_cad=v["jib_cad"] if jib else 0.0,
                    mass_jib=v["mass_jib"] if jib else 0.0)
        args.pop("name", None)
        args.pop("kind", None)
        return C.Crawler(name=name, **args)
    keys = {f.name for f in dataclasses.fields(C.Knuckle)}
    args = {k: v[k] for k in keys if k in v}
    args.update(spread=(v["spread_full"], v["spread_narrow"]), main_range=(v["main_min"], v["main_max"]),
                knuckle_range=(v["knuckle_min"], v["knuckle_max"]))
    args.pop("name", None)
    args.pop("kind", None)
    return C.Knuckle(name=name, **args)


def _num(x):
    """24.0 -> 24 (the classes write whole chart lengths as int: the chart names and hashes stay the same)."""
    x = float(x)
    return int(x) if x == int(x) else x


def class_of_data(data: dict):
    """The dataclass of an equipment file: a made crane's own numbers (``made_from``, task 0204), else its built-in
    class; None for any other item (an own STEP crane)."""
    mf = data.get("made_from") if isinstance(data, dict) else None
    if isinstance(mf, dict) and mf.get("kind") in FIELDS and isinstance(mf.get("values"), dict):
        v = {k: (tuple(x) if isinstance(x, list) else x) for k, x in mf["values"].items()}
        if not validate(mf["kind"], v, charts=False):
            return to_class(mf["kind"], v, str(data.get("name", "Crane")))
        return None
    cls = data.get("class") if isinstance(data, dict) else None
    return C.CLASSES.get(cls) if isinstance(cls, str) else None


def class_word(kind: str, values: dict) -> str:
    """The size-class word of a made crane: 'AT-120', 'CC-450', 'KB-35'."""
    num = values["moment"] if kind == "KB" else values["rated"]
    return f"{kind}-{num:g}"


def nearest_class(kind: str, values: dict) -> str:
    key = "moment" if kind == "KB" else "rated"
    names = C.names(kind)
    return min(names, key=lambda n: abs(math.log(max(1e-6, getattr(C.CLASSES[n], key)) / max(1e-6, values[key]))))


# ---------------------------------------------------------------------------------------------------------------------
# rules

@dataclass(frozen=True)
class Problem:
    rule: str          # 'range:L0', 'boom_lengths', 'sections_nest' … (tests name the rule)
    text: str          # plain words


def _m(mm: float) -> str:
    return f"{mm / 1000.0:.2f} m"


def _ranges(kind: str, values: dict, out: list) -> bool:
    ok = True
    for f in FIELDS[kind]:
        if values.get(f.key) is None:
            out.append(Problem(f"missing:{f.key}", f"{f.label}: missing."))
            ok = False
            continue
        v = values[f.key]
        if f.is_list:
            try:
                xs = parse_list(v, 1.0, f.digits) if isinstance(v, str) else tuple(float(x) for x in v)
            except (TypeError, ValueError) as exc:
                out.append(Problem(f"range:{f.key}", f"{f.label}: {exc}."))
                ok = False
                continue
            bad = [x for x in xs if not (f.lo <= x / f.scale <= f.hi)]
            if bad:
                out.append(Problem(f"range:{f.key}", f"{f.label}: {bad[0]:g} {f.unit} is outside {f.lo:g} … "
                                                     f"{f.hi:g} {f.unit}."))
                ok = False
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            out.append(Problem(f"range:{f.key}", f"{f.label}: not a number."))
            ok = False
            continue
        if not math.isfinite(x):
            out.append(Problem(f"range:{f.key}", f"{f.label}: not a number."))
            ok = False
            continue
        if f.integer and x != int(x):
            out.append(Problem(f"range:{f.key}", f"{f.label}: a whole number, please."))
            ok = False
        shown = x / f.scale
        if not (f.lo - 1e-9 <= shown <= f.hi + 1e-9):
            out.append(Problem(f"range:{f.key}", f"{f.label}: {shown:g} {f.unit} is outside {f.lo:g} … {f.hi:g} "
                                                 f"{f.unit}.".replace("  ", " ")))
            ok = False
    return ok


def _rising(xs, strict=True) -> bool:
    return all((b > a) if strict else (b >= a) for a, b in zip(xs, xs[1:]))


def _rules_at(v: dict, out: list) -> None:
    if not v["L0"] < v["Lmax"]:
        out.append(Problem("boom_lengths", f"The boom fully out ({_m(v['Lmax'])}) must be longer than retracted "
                                           f"({_m(v['L0'])})."))
    n = v["sections"]
    shrink = 2 * (n - 1) * (v["wall"] + v["gap"])
    tip_w, tip_h = v["boom_w"] - shrink, v["boom_h"] - shrink
    if min(tip_w, tip_h) < max(150.0, 0.3 * min(v["boom_w"], v["boom_h"])):
        out.append(Problem("sections_nest", f"{n} sections do not fit inside each other: the tip section would be "
                                            f"{max(0.0, tip_w):.0f} x {max(0.0, tip_h):.0f} mm. Fewer sections, thinner "
                                            "walls or a bigger base section."))
    if v["boom_w"] > v["width"] - 300.0:
        out.append(Problem("boom_fits", f"The boom ({_m(v['boom_w'])} wide) does not fit on the carrier "
                                        f"({_m(v['width'])} wide): at most the width less 0.3 m."))
    if not v["spread_full"] > v["spread_middle"] > v["spread_narrow"]:
        out.append(Problem("spreads", "Outrigger spreads: full must be wider than middle, middle wider than narrow."))
    if v["spread_narrow"] <= v["width"]:
        out.append(Problem("spreads_out", f"The narrow spread ({_m(v['spread_narrow'])}) must be wider than the "
                                          f"carrier ({_m(v['width'])})."))
    if not _rising((v["cw_1"], v["cw_2"], v["cw_3"])):
        out.append(Problem("counterweights", "Counterweight steps must rise: step 1 < step 2 < step 3."))
    if v["hook_falls"] % 2:
        out.append(Problem("falls", f"Falls of rope: an even number (the hook block has falls / 2 sheaves), not "
                                    f"{v['hook_falls']}."))


def _rules_cc(v: dict, out: list) -> None:
    bl = tuple(float(x) for x in v["boom_lengths"])
    if len(bl) < 1:
        out.append(Problem("boom_list", "Chart boom lengths: at least one."))
    elif not _rising(bl):
        out.append(Problem("boom_list", "Chart boom lengths must rise from the shortest to the longest."))
    if bl and not any(abs(x * 1000.0 - v["boom_cad"]) < 1.0 for x in bl):
        out.append(Problem("model_boom", f"The model's boom ({_m(v['boom_cad'])}) must be one of the chart boom "
                                         "lengths."))
    if not v["luff_min"] < v["luff_cad"] < v["luff_max"]:
        out.append(Problem("luff_order", "Boom angles: flattest < angle in the model < steepest."))
    jl = tuple(float(x) for x in v["jib_lengths"])
    if v["jib_cad"] > 0:
        if v["jib_cad"] < 6000.0:
            out.append(Problem("jib", "A luffing jib is at least 6 m long (or 0 for none)."))
        if not jl:
            out.append(Problem("jib", "With a luffing jib, give its chart lengths."))
        elif not _rising(jl):
            out.append(Problem("jib", "Chart jib lengths must rise from the shortest to the longest."))
        elif not any(abs(x * 1000.0 - v["jib_cad"]) < 1.0 for x in jl):
            out.append(Problem("jib", f"The model's jib ({_m(v['jib_cad'])}) must be one of the chart jib lengths."))
        if v["mass_jib"] <= 0:
            out.append(Problem("jib", "With a luffing jib, give its mass."))
        if v["jib_cad"] > 0.8 * v["boom_cad"]:
            out.append(Problem("jib", "The jib can be at most 0.8 x the model's boom."))
    if v["teeth"] % 2:
        out.append(Problem("teeth", f"Sprocket teeth: an even number, not {v['teeth']}."))
    contact = v["run_links"] * v["pitch"]
    if contact < 1.1 * v["cw_x"]:
        out.append(Problem("tracks_tail", f"The tracks are too short for the upper's tail: {_m(contact)} on the "
                                          f"ground, at least 1.1 x the counterweight distance ({_m(1.1 * v['cw_x'])})."))
    if v["gauge"] < 2.0 * v["shoe_w"]:
        out.append(Problem("gauge", f"Track gauge ({_m(v['gauge'])}) must be at least twice the shoe width "
                                    f"({_m(v['shoe_w'])}): the tracks would overlap."))
    if not _rising((v["cw_1"], v["cw_2"])):
        out.append(Problem("counterweights", "Counterweight steps must rise: step 1 < step 2."))
    if v["hook_falls"] % 2:
        out.append(Problem("falls", f"Falls of rope: an even number, not {v['hook_falls']}."))


def _rules_kb(v: dict, out: list) -> None:
    if not v["main_min"] < v["main_cad"] < v["main_max"]:
        out.append(Problem("main_order", "Main boom angles: lowest < angle in the model < highest."))
    if not v["knuckle_min"] < v["knuckle_cad"] < v["knuckle_max"]:
        out.append(Problem("knuckle_order", "Knuckle angles: most folded < angle in the model < most open."))
    if v["ext_stroke"] > 0.7 * v["outer_len"]:
        out.append(Problem("ext_stroke", f"The stroke per extension ({_m(v['ext_stroke'])}) is at most 0.7 x the outer "
                                         f"boom ({_m(0.7 * v['outer_len'])}): each extension keeps itself in the one "
                                         "below."))
    w, h = v["boom_w"], v["boom_h"]
    wall, ewall, egap = 0.05 * w, max(6.0, 0.025 * w), 10.0
    for k in range(1, v["extensions"] + 1):
        d = 2 * (wall if k == 1 else ewall) + 2 * egap
        w, h = w - d, h - d
    if min(w, h) < max(60.0, 0.25 * min(v["boom_w"], v["boom_h"])):
        out.append(Problem("ext_nest", f"{v['extensions']} extensions do not fit inside the outer boom: the last would "
                                       f"be {max(0.0, w):.0f} x {max(0.0, h):.0f} mm. Fewer extensions or a bigger "
                                       "boom."))
    rs = 0.30 * (v["boom_h"] - 2 * (v["extensions"] + 1) * 22.0)       # the tip sheave (classes.knuckle_layout)
    if rs < 45.0:
        out.append(Problem("tip_sheave", f"The boom ({v['boom_h']:.0f} mm high) is too low for a tip sheave with "
                                         f"{v['extensions']} extensions: a higher boom or fewer extensions."))
    if v["boom_w"] > v["width"] - 600.0:
        out.append(Problem("boom_fits", f"The boom ({_m(v['boom_w'])} wide) does not fit on the truck "
                                        f"({_m(v['width'])} wide)."))
    if not v["spread_full"] > v["spread_narrow"]:
        out.append(Problem("spreads", "Stabiliser spreads: full must be wider than narrow."))
    if v["spread_narrow"] <= v["width"]:
        out.append(Problem("spreads_out", f"The narrow spread ({_m(v['spread_narrow'])}) must be wider than the "
                                          f"truck ({_m(v['width'])})."))
    if v["max_cap"] > v["moment"] / 2.0:
        out.append(Problem("max_cap", f"Capacity at the shortest outreach ({v['max_cap']:g} t) is at most the lifting "
                                      f"moment / 2 m ({v['moment'] / 2.0:g} t)."))


_GEOMETRY = (
    ("keeps only", "sections_overlap", "The telescopic sections are too short for their stroke: each must keep 15 % of "
                                       "itself in the one below. A shorter boom fully out or more sections."),
    ("outrigger stroke", "spreads_out", "The full spread is too narrow for the outrigger beams to move out."),
    ("too close to the outrigger", "axles_fit", "The axles do not fit between the outrigger boxes: fewer axles, "
                                                "smaller wheels or the pads further apart (front to rear)."),
    ("overlap", "axles_fit", "The axles do not fit on the carrier: fewer axles or smaller wheels."),
    ("no cylinder fits", "cylinder_fit", "No luffing cylinder fits for this boom angle range: a smaller range or "
                                         "other boom sizes."),
)


def _geometry(kind: str, c, out: list):
    """The makers' own layout: their ValueErrors in plain words. Returns the layout or None."""
    try:
        L = C.layout(c)
    except ValueError as exc:
        msg = str(exc)
        for key, rule, text in _GEOMETRY:
            if key in msg:
                if kind == "KB" and rule == "cylinder_fit":
                    text = ("No boom cylinder fits for these boom angle ranges: smaller ranges or other boom "
                            "lengths.")
                if kind == "CC" and rule == "cylinder_fit":
                    text = ("The boom (or jib) pendants cannot reach over this angle range: a smaller range or another "
                            "boom.")
                out.append(Problem(rule, f"{text} ({msg})"))
                return None
        out.append(Problem("geometry", f"The crane cannot be laid out: {msg}"))
        return None
    if kind == "AT":
        p = L.pts
        if p["front"] - p["rear"] < 2300.0 + 2000.0:
            out.append(Problem("carrier_length", "The carrier is too short for its cab and deck: a longer boom "
                                                 "retracted or the counterweight further back."))
            return None
    return L


def validate(kind: str, values: dict, charts: bool = True) -> list:
    """Every rule the numbers break, in plain words ([] = they fit). ``charts``: also the SAMPLE chart rule (at least
    one stable configuration)."""
    out: list = []
    if kind not in FIELDS:
        return [Problem("kind", f"Unknown kind '{kind}'.")]
    v = dict(values)
    if not _ranges(kind, v, out):
        return out
    for f in FIELDS[kind]:
        if f.is_list and isinstance(v[f.key], str):
            v[f.key] = parse_list(v[f.key], 1.0, f.digits)
    {"AT": _rules_at, "CC": _rules_cc, "KB": _rules_kb}[kind](v, out)
    if out:
        return out
    c = to_class(kind, v)
    L = _geometry(kind, c, out)
    if L is None or out or not charts:
        return out
    from . import charts as K
    try:
        got = K.charts_of(c)
    except (ValueError, ZeroDivisionError, ArithmeticError) as exc:
        out.append(Problem("charts", f"No SAMPLE chart can be worked out: {exc}"))
        return out
    if not got:
        out.append(Problem("stable", "No configuration stays stable: more counterweight, wider outriggers or a "
                                     "lighter / shorter boom."))
    return out


def fits_text(problems: list) -> str:
    return "Fits." if not problems else problems[0].text


# ---------------------------------------------------------------------------------------------------------------------
# derived numbers

def _ratio(a: float, b: float) -> float:
    return a / b if b else 1.0


def suggest_masses(kind: str, values: dict, start: str) -> dict:
    """The masses from the start class's rule, scaled by what changed (sizes, lengths, axles). The class's own numbers
    give the class's own masses."""
    s = of_class(start)
    v = values
    out = {}
    if kind == "AT":
        out["mass_boom"] = s["mass_boom"] * _ratio(v["Lmax"] * (v["boom_w"] + v["boom_h"]) * v["wall"],
                                                   s["Lmax"] * (s["boom_w"] + s["boom_h"]) * s["wall"])
        out["mass_carrier"] = s["mass_carrier"] * _ratio(v["axles"] * v["width"] * v["spread_full"],
                                                         s["axles"] * s["width"] * s["spread_full"]) ** 0.7
        out["mass_upper"] = s["mass_upper"] * _ratio(v["rated"], s["rated"]) ** 0.6
        out["hook_mass"] = s["hook_mass"] * _ratio(v["hook_falls"] * v["line_pull"], s["hook_falls"] * s["line_pull"])
    elif kind == "CC":
        out["mass_boom"] = s["mass_boom"] * _ratio(v["boom_cad"] * v["boom_w"], s["boom_cad"] * s["boom_w"])
        if v["jib_cad"] > 0:
            ref_j, ref_w = (s["jib_cad"], s["boom_w"]) if s["jib_cad"] > 0 else (s["boom_cad"], s["boom_w"] * 1.8)
            ref_m = s["mass_jib"] if s["jib_cad"] > 0 else s["mass_boom"]
            out["mass_jib"] = ref_m * _ratio(v["jib_cad"] * v["boom_w"], ref_j * ref_w)
        else:
            out["mass_jib"] = 0.0
        out["mass_lower"] = s["mass_lower"] * _ratio(v["gauge"] * v["run_links"] * v["pitch"] * v["shoe_w"],
                                                     s["gauge"] * s["run_links"] * s["pitch"] * s["shoe_w"]) ** 0.6
        out["mass_upper"] = s["mass_upper"] * _ratio(v["rated"], s["rated"]) ** 0.6
        out["hook_mass"] = s["hook_mass"] * _ratio(v["hook_falls"] * v["line_pull"], s["hook_falls"] * s["line_pull"])
    else:
        out["mass_main"] = s["mass_main"] * _ratio(v["main_len"] * v["boom_w"] * v["boom_h"],
                                                   s["main_len"] * s["boom_w"] * s["boom_h"])
        out["mass_outer"] = s["mass_outer"] * _ratio((v["outer_len"] + v["extensions"] * v["ext_stroke"]) * v["boom_w"]
                                                     * v["boom_h"], (s["outer_len"] + s["extensions"] * s["ext_stroke"])
                                                     * s["boom_w"] * s["boom_h"])
        out["mass_column"] = s["mass_column"] * _ratio(v["moment"], s["moment"]) ** 0.8
        out["mass_truck"] = s["mass_truck"] * _ratio(v["axles"] * v["spread_full"], s["axles"] * s["spread_full"]) ** 0.7
        out["hook_mass"] = s["hook_mass"] * _ratio(v["max_cap"], s["max_cap"]) ** 0.5
    return {k: round(x, 3) for k, x in out.items()}


# ---------------------------------------------------------------------------------------------------------------------
# random valid sets (tests)

def random_values(kind: str, rng, start: str | None = None, spread: float = 0.25, tries: int = 400) -> dict:
    """A valid set near a class: each number scaled by up to ±``spread``, counts moved by one or two, lists kept in
    shape; masses from ``suggest_masses``. ``rng``: a ``random.Random``. RuntimeError when nothing valid was found."""
    names = C.names(kind)
    for _ in range(tries):
        st = start or rng.choice(names)
        base = of_class(st)
        v = dict(base)
        for f in FIELDS[kind]:
            if f.key in MASS_KEYS[kind]:
                continue
            x = base[f.key]
            if f.integer:
                step = 2 if f.key in ("hook_falls", "teeth") else 1
                v[f.key] = int(min(f.hi, max(f.lo, x + step * rng.choice((-1, 0, 0, 1)))))
            elif f.is_list:
                continue
            elif f.key.startswith("cw_") and x == 0:
                continue
            else:
                y = x * (1.0 + rng.uniform(-spread, spread))
                if f.key in ("luff_max", "luff_cad", "luff_min", "main_cad", "main_min", "main_max", "knuckle_cad",
                             "knuckle_min", "knuckle_max", "jib_angle"):
                    y = x + rng.uniform(-4.0, 4.0)
                v[f.key] = round(min(f.hi * f.scale, max(f.lo * f.scale, y)), f.digits)
        if kind == "CC":
            k = v["boom_cad"] / 1000.0
            step = rng.choice((6.0, 6.0, 12.0))
            lo = max(6.0, k - step * rng.randint(1, 4))
            bl = []
            x = lo
            while x <= k + step * rng.randint(1, 4) + 1e-9:
                bl.append(round(x, 3))
                x += step
            if round(k, 3) not in bl:
                bl.append(round(k, 3))
            v["boom_lengths"] = tuple(sorted(set(bl)))
            if base["jib_cad"] > 0 and rng.random() < 0.7:
                j = round(v["jib_cad"] / 1000.0, 3)
                v["jib_cad"] = j * 1000.0
                v["jib_lengths"] = tuple(sorted({round(j - 12, 3), j, round(j + 12, 3)}))
            elif rng.random() < 0.3 and base["jib_cad"] == 0:
                j = round(0.5 * v["boom_cad"] / 1000.0)
                v["jib_cad"] = j * 1000.0
                v["jib_lengths"] = (float(j - 6), float(j), float(j + 6))
                v["mass_jib"] = 1.0
            elif base["jib_cad"] > 0:
                v["jib_cad"], v["jib_lengths"], v["mass_jib"] = 0.0, (), 0.0
        v.update(suggest_masses(kind, v, st))
        if kind == "CC" and v["jib_cad"] == 0:
            v["mass_jib"] = 0.0
        for k in ("cw_1", "cw_2", "cw_3"):
            if k in v:
                v[k] = round(v[k], 1)
        if not validate(kind, v):
            return v
    raise RuntimeError(f"no valid {kind} set found in {tries} tries")
