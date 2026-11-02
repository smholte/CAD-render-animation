"""RAL Classic colour table.

Screen (sRGB) values are approximations of the physical RAL colours; they are
the commonly published values (Wikipedia "List of RAL colours"). For exact
colour matching, compare against a physical RAL fan deck.
"""

from __future__ import annotations

import re

# (code, English name, sRGB hex)
RAL_CLASSIC: tuple[tuple[str, str, str], ...] = (
    ("1000", "Green beige", "#CDBA88"),
    ("1001", "Beige", "#D0B084"),
    ("1002", "Sand yellow", "#D2AA6D"),
    ("1003", "Signal yellow", "#F9A800"),
    ("1004", "Golden yellow", "#E49E00"),
    ("1005", "Honey yellow", "#CB8E00"),
    ("1006", "Maize yellow", "#E29000"),
    ("1007", "Daffodil yellow", "#E88C00"),
    ("1011", "Brown beige", "#AF804F"),
    ("1012", "Lemon yellow", "#DDAF27"),
    ("1013", "Oyster white", "#E3D9C6"),
    ("1014", "Ivory", "#DDC49A"),
    ("1015", "Light ivory", "#E6D2B5"),
    ("1016", "Sulfur yellow", "#F1DD38"),
    ("1017", "Saffron yellow", "#F6A950"),
    ("1018", "Zinc yellow", "#FACA30"),
    ("1019", "Grey beige", "#A48F7A"),
    ("1020", "Olive yellow", "#A08F65"),
    ("1021", "Colza yellow", "#F6B600"),
    ("1023", "Traffic yellow", "#F7B500"),
    ("1024", "Ochre yellow", "#BA8F4C"),
    ("1026", "Luminous yellow", "#FFFF00"),
    ("1027", "Curry", "#A77F0E"),
    ("1028", "Melon yellow", "#FF9B00"),
    ("1032", "Broom yellow", "#E2A300"),
    ("1033", "Dahlia yellow", "#F99A1C"),
    ("1034", "Pastel yellow", "#EB9C52"),
    ("1035", "Pearl beige", "#908370"),
    ("1036", "Pearl gold", "#80643F"),
    ("1037", "Sun yellow", "#F09200"),
    ("2000", "Yellow orange", "#DD7907"),
    ("2001", "Red orange", "#BE4E20"),
    ("2002", "Vermilion", "#C63927"),
    ("2003", "Pastel orange", "#FA842B"),
    ("2004", "Pure orange", "#E75B12"),
    ("2005", "Luminous orange", "#FF2300"),
    ("2007", "Luminous bright orange", "#FFA421"),
    ("2008", "Bright red orange", "#F3752C"),
    ("2009", "Traffic orange", "#E15501"),
    ("2010", "Signal orange", "#D4652F"),
    ("2011", "Deep orange", "#EC7C25"),
    ("2012", "Salmon orange", "#DB6A50"),
    ("2013", "Pearl orange", "#954527"),
    ("2017", "RAL orange", "#FA4402"),
    ("3000", "Flame red", "#AB2524"),
    ("3001", "Signal red", "#A02128"),
    ("3002", "Carmine red", "#A1232B"),
    ("3003", "Ruby red", "#8D1D2C"),
    ("3004", "Purple red", "#701F29"),
    ("3005", "Wine red", "#5E2028"),
    ("3007", "Black red", "#402225"),
    ("3009", "Oxide red", "#703731"),
    ("3011", "Brown red", "#7E292C"),
    ("3012", "Beige red", "#CB8D73"),
    ("3013", "Tomato red", "#9C322E"),
    ("3014", "Antique pink", "#D47479"),
    ("3015", "Light pink", "#E1A6AD"),
    ("3016", "Coral red", "#AC4034"),
    ("3017", "Rose", "#D3545F"),
    ("3018", "Strawberry red", "#D14152"),
    ("3020", "Traffic red", "#C1121C"),
    ("3022", "Salmon pink", "#D56D56"),
    ("3024", "Luminous red", "#F70000"),
    ("3026", "Luminous bright red", "#FF0000"),
    ("3027", "Raspberry red", "#B42041"),
    ("3028", "Pure red", "#E72512"),
    ("3031", "Orient red", "#AC323B"),
    ("3032", "Pearl ruby red", "#711521"),
    ("3033", "Pearl pink", "#B24C43"),
    ("4001", "Red lilac", "#8A5A83"),
    ("4002", "Red violet", "#933D50"),
    ("4003", "Heather violet", "#D15B8F"),
    ("4004", "Claret violet", "#691639"),
    ("4005", "Blue lilac", "#83639D"),
    ("4006", "Traffic purple", "#992572"),
    ("4007", "Purple violet", "#4A203B"),
    ("4008", "Signal violet", "#904684"),
    ("4009", "Pastel violet", "#A38995"),
    ("4010", "Telemagenta", "#C63678"),
    ("4011", "Pearl violet", "#8773A1"),
    ("4012", "Pearl blackberry", "#6B6880"),
    ("5000", "Violet blue", "#384C70"),
    ("5001", "Green blue", "#1F4764"),
    ("5002", "Ultramarine blue", "#2B2C7C"),
    ("5003", "Sapphire blue", "#2A3756"),
    ("5004", "Black blue", "#1D1F2A"),
    ("5005", "Signal blue", "#154889"),
    ("5007", "Brilliant blue", "#41678D"),
    ("5008", "Grey blue", "#313C48"),
    ("5009", "Azure blue", "#2E5978"),
    ("5010", "Gentian blue", "#13447C"),
    ("5011", "Steel blue", "#232C3F"),
    ("5012", "Light blue", "#3481B8"),
    ("5013", "Cobalt blue", "#232D53"),
    ("5014", "Pigeon blue", "#6C7C98"),
    ("5015", "Sky blue", "#2874B2"),
    ("5017", "Traffic blue", "#0E518D"),
    ("5018", "Turquoise blue", "#21888F"),
    ("5019", "Capri blue", "#1A5784"),
    ("5020", "Ocean blue", "#0B4151"),
    ("5021", "Water blue", "#07737A"),
    ("5022", "Night blue", "#2F2A5A"),
    ("5023", "Distant blue", "#4D668E"),
    ("5024", "Pastel blue", "#6A93B0"),
    ("5025", "Pearl Gentian blue", "#296478"),
    ("5026", "Pearl night blue", "#102C54"),
    ("6000", "Patina green", "#327662"),
    ("6001", "Emerald green", "#28713E"),
    ("6002", "Leaf green", "#276235"),
    ("6003", "Olive green", "#4B573E"),
    ("6004", "Blue green", "#0E4243"),
    ("6005", "Moss green", "#0F4336"),
    ("6006", "Grey olive", "#40433B"),
    ("6007", "Bottle green", "#283424"),
    ("6008", "Brown green", "#35382E"),
    ("6009", "Fir green", "#26392F"),
    ("6010", "Grass green", "#3E753B"),
    ("6011", "Reseda green", "#68825B"),
    ("6012", "Black green", "#31403D"),
    ("6013", "Reed green", "#797C5A"),
    ("6014", "Yellow olive", "#444337"),
    ("6015", "Black olive", "#3D403A"),
    ("6016", "Turquoise green", "#026A52"),
    ("6017", "May green", "#468641"),
    ("6018", "Yellow green", "#48A43F"),
    ("6019", "Pastel green", "#B7D9B1"),
    ("6020", "Chrome green", "#354733"),
    ("6021", "Pale green", "#86A47C"),
    ("6022", "Olive drab", "#3E3C32"),
    ("6024", "Traffic green", "#008754"),
    ("6025", "Fern green", "#53753C"),
    ("6026", "Opal green", "#005D52"),
    ("6027", "Light green", "#81C0BB"),
    ("6028", "Pine green", "#2D5546"),
    ("6029", "Mint green", "#007243"),
    ("6032", "Signal green", "#0F8558"),
    ("6033", "Mint turquoise", "#478A84"),
    ("6034", "Pastel turquoise", "#7FB0B2"),
    ("6035", "Pearl green", "#1B542C"),
    ("6036", "Pearl opal green", "#005D4C"),
    ("6037", "Pure green", "#25E712"),
    ("6038", "Luminous green", "#00F700"),
    ("7000", "Squirrel grey", "#7E8B92"),
    ("7001", "Silver grey", "#8F999F"),
    ("7002", "Olive grey", "#817F68"),
    ("7003", "Moss grey", "#7A7B6D"),
    ("7004", "Signal grey", "#9EA0A1"),
    ("7005", "Mouse grey", "#6B716F"),
    ("7006", "Beige grey", "#756F61"),
    ("7008", "Khaki grey", "#746643"),
    ("7009", "Green grey", "#5B6259"),
    ("7010", "Tarpaulin grey", "#575D57"),
    ("7011", "Iron grey", "#555D61"),
    ("7012", "Basalt grey", "#596163"),
    ("7013", "Brown grey", "#555548"),
    ("7015", "Slate grey", "#51565C"),
    ("7016", "Anthracite grey", "#373F43"),
    ("7021", "Black grey", "#2E3234"),
    ("7022", "Umbra grey", "#4B4D46"),
    ("7023", "Concrete grey", "#818479"),
    ("7024", "Graphite grey", "#474A50"),
    ("7026", "Granite grey", "#374447"),
    ("7030", "Stone grey", "#939388"),
    ("7031", "Blue grey", "#5D6970"),
    ("7032", "Pebble grey", "#B9B9A8"),
    ("7033", "Cement grey", "#818979"),
    ("7034", "Yellow grey", "#939176"),
    ("7035", "Light grey", "#CBD0CC"),
    ("7036", "Platinum grey", "#9A9697"),
    ("7037", "Dusty grey", "#7C7F7E"),
    ("7038", "Agate grey", "#B4B8B0"),
    ("7039", "Quartz grey", "#6B695F"),
    ("7040", "Window grey", "#9DA3A6"),
    ("7042", "Traffic grey A", "#8F9695"),
    ("7043", "Traffic grey B", "#4E5451"),
    ("7044", "Silk grey", "#BDBDB2"),
    ("7045", "Telegrey 1", "#91969A"),
    ("7046", "Telegrey 2", "#82898E"),
    ("7047", "Telegrey 4", "#CFD0CF"),
    ("7048", "Pearl mouse grey", "#888175"),
    ("8000", "Green brown", "#887142"),
    ("8001", "Ochre brown", "#9C6B30"),
    ("8002", "Signal brown", "#7B5141"),
    ("8003", "Clay brown", "#80542F"),
    ("8004", "Copper brown", "#8F4E35"),
    ("8007", "Fawn brown", "#6F4A2F"),
    ("8008", "Olive brown", "#6F4F28"),
    ("8011", "Nut brown", "#5A3A29"),
    ("8012", "Red brown", "#673831"),
    ("8014", "Sepia brown", "#49392D"),
    ("8015", "Chestnut brown", "#633A34"),
    ("8016", "Mahogany brown", "#4C2F26"),
    ("8017", "Chocolate brown", "#44322D"),
    ("8019", "Grey brown", "#3F3A3A"),
    ("8022", "Black brown", "#211F20"),
    ("8023", "Orange brown", "#A65E2F"),
    ("8024", "Beige brown", "#79553C"),
    ("8025", "Pale brown", "#755C49"),
    ("8028", "Terra brown", "#4E3B2B"),
    ("8029", "Pearl copper", "#773C27"),
    ("9001", "Cream", "#EFEBDC"),
    ("9002", "Grey white", "#DDDED4"),
    ("9003", "Signal white", "#F4F8F4"),
    ("9004", "Signal black", "#2E3032"),
    ("9005", "Jet black", "#0A0A0D"),
    ("9006", "White aluminium", "#A5A8A6"),
    ("9007", "Grey aluminium", "#8F8F8C"),
    ("9010", "Pure white", "#F7F9EF"),
    ("9011", "Graphite black", "#1C1C1C"),
    ("9012", "Clean room white", "#FFFDE6"),
    ("9016", "Traffic white", "#F7FBF5"),
    ("9017", "Traffic black", "#2A2D2F"),
    ("9018", "Papyrus white", "#CFD3CD"),
    ("9022", "Pearl light grey", "#858583"),
    ("9023", "Pearl dark grey", "#7E8182"),
)

_BY_CODE = {code: (name, hexv) for code, name, hexv in RAL_CLASSIC}


def hex_to_rgb(hexv: str) -> tuple[float, float, float]:
    """'#RRGGBB' -> sRGB floats 0..1."""
    h = hexv.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Not a hex colour: {hexv!r}")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb) -> str:
    r, g, b = (max(0, min(255, round(float(c) * 255))) for c in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def normalise_code(text: str) -> str | None:
    """'RAL 5010', 'ral5010', '5010' -> '5010' (None if not a known RAL code)."""
    m = re.search(r"(\d{4})", text or "")
    if not m:
        return None
    code = m.group(1)
    return code if code in _BY_CODE else None


def lookup(text: str):
    """Return (code, name, hex) for a RAL reference, or None."""
    code = normalise_code(text)
    if code is None:
        return None
    name, hexv = _BY_CODE[code]
    return code, name, hexv


def parse_colour(text: str) -> tuple[str, tuple[float, float, float]] | None:
    """Accept 'RAL 1003', '#F9A800' or 'F9A800'. Returns (label, sRGB)."""
    t = (text or "").strip()
    if not t:
        return None
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", t):
        hexv = "#" + t.lstrip("#").upper()
        return hexv, hex_to_rgb(hexv)
    found = lookup(t)
    if found:
        code, name, hexv = found
        return f"RAL {code} {name}", hex_to_rgb(hexv)
    return None


def nearest(rgb) -> tuple[str, str, str]:
    """Nearest RAL colour to an sRGB triple (simple RGB distance)."""
    best = None
    for code, name, hexv in RAL_CLASSIC:
        r2 = hex_to_rgb(hexv)
        d = sum((a - b) ** 2 for a, b in zip(rgb, r2))
        if best is None or d < best[0]:
            best = (d, code, name, hexv)
    return best[1], best[2], best[3]
