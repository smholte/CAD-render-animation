import pytest

from fresing_render.core import fasteners as F


@pytest.mark.parametrize("name, kind, size, length, pclass, finish", [
    ("ISO 4017 M12 x 40 - 8.8 HDG", "hex_bolt", "M12", 40.0, "8.8", "galvanized"),
    ("DIN 912 M10x30 - 12.9", "socket_cap", "M10", 30.0, "12.9", "black"),
    ("ISO 4032 M12 A4", "hex_nut", "M12", None, None, "stainless"),
    ("DIN 125-A 13", "washer", None, None, None, None),
    ("ISO 4762 M8 x 25", "socket_cap", "M8", 25.0, None, "black"),
    ("DIN 933 M16x50 8.8 tZn", "hex_bolt", "M16", 50.0, "8.8", "galvanized"),
    ("DIN 934 M20 verzinkt", "hex_nut", "M20", None, None, "zinc"),
    ("DIN EN ISO 4762 - M6 x 16 - A2-70", "socket_cap", "M6", 16.0, None, "stainless"),
    ("ISO 7380 M5x10", "button_socket", "M5", 10.0, None, "black"),
    ("ISO 7089 - 12 - 200 HV", "washer", None, None, None, None),
    ("DIN 985 M8", "lock_nut", "M8", None, None, None),
    ("BOLT.M4.8L", "bolt", "M4", 8.0, None, None),
    ("Inbusbout M8x20 RVS", "socket_cap", "M8", 20.0, None, "stainless"),
    ("Zeskantmoer M10 thermisch verzinkt", "hex_nut", "M10", None, None, "galvanized"),
    ("Sechskantschraube M12x60 feuerverzinkt", "hex_bolt", "M12", 60.0, None, "galvanized"),
    ("Black-Oxide Alloy Steel Socket Head Screw M3 x 0.5 mm Thread, 10 mm Long", "socket_cap", "M3", None, None, "black"),
    ("18-8 Stainless Steel Washer for M6", "washer", "M6", None, None, "stainless"),
    ("CB6-20", "socket_cap", "M6", 20.0, None, "black"),
    ("SCB8-30", "socket_cap", "M8", 30.0, None, "stainless"),
    ("ISO 4014 M24x120-10.9 Geomet", "hex_bolt", "M24", 120.0, "10.9", "zinc_flake"),
    ("DIN 7991 M8x25", "countersunk_socket", "M8", 25.0, None, "black"),
    ("DIN 471 - 30x1.5", "circlip", None, None, None, None),
    ("DIN 6885 A 8x7x40", "key", None, None, None, None),
    ("ISO 8752 - 6x30 - St", "spring_pin", None, None, None, None),
    ("M2.5x8 ISO 4762", "socket_cap", "M2.5", 8.0, None, "black"),
])
def test_parse(name, kind, size, length, pclass, finish):
    info = F.parse(name)
    assert info is not None, name
    assert info.kind == kind
    assert info.size == size
    assert info.length == length
    assert info.property_class == pclass
    assert info.finish == finish


@pytest.mark.parametrize("name", [
    "SIDE.FRAME.1", "BEARING.HOUSING1", "COMPRESSION.SPRING.WL16-25", "BALL SCREW SFU1605",
    "NUT HOUSING", "RAIL.MOUNT11", "GUIDE.BLOCK", "LINE3.TEST.CELL.WORK", "", "O-RING 20x2",
    "DOOR.HINGE", "Frame weldment", "CABLEVEYOR.BRACKET1",
])
def test_not_fastener(name):
    assert F.parse(name) is None


def test_families():
    assert F.parse("DIN 934 M12").family == "nut"
    assert F.parse("DIN 125 A 13").family == "washer"
    assert F.parse("ISO 4017 M12x40").family == "screw"
    assert F.parse("ISO 2338 6m6x20").family == "pin"


def test_describe():
    text = F.describe(F.parse("ISO 4017 M12 x 40 - 8.8 HDG"))
    assert "Hex bolt M12x40" in text and "8.8" in text and "galvanized" in text.lower()
    assert F.describe(None) == "Not a standard part"
