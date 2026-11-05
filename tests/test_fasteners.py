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
    # supplier-notation lookalikes that are not fasteners
    "MSSF", "WRENCH", "WRENCH HOLDER", "BOLT HOLE 5-20", "NUT HOUSING 5", "WASHER PLATE 6",
    "NUTRUNNER5", "SSD5-5", "MSSF55", "SCREW CONVEYOR 5-20", "BALL SCREW5-20", "TORQUE WRENCH 5-20",
])
def test_not_fastener(name):
    assert F.parse(name) is None


@pytest.mark.parametrize("name, kind, size, length, pclass, finish", [
    # supplier notation (invented example names)
    ("MSSF5-5", "set_screw", "M5", 5.0, None, "black"),
    ("MSS4-6", "set_screw", "M4", 6.0, None, "black"),
    ("SSS6-10", "set_screw", "M6", 10.0, None, "black"),
    ("SSCP5-8", "set_screw", "M5", 8.0, None, "black"),
    ("SSEB4-12", "set_screw", "M4", 12.0, None, "black"),
    ("WRENCHBOLT M8x20", "socket_cap", "M8", 20.0, None, "black"),
    ("WRENCHBOLT6-15", "socket_cap", "M6", 15.0, None, "black"),
    ("WRENCH BOLT 8-25", "socket_cap", "M8", 25.0, None, "black"),
    ("BOLT5-20", "bolt", "M5", 20.0, None, None),
    ("BOLT 6-12", "bolt", "M6", 12.0, None, None),
    ("SCREW4-10", "bolt", "M4", 10.0, None, None),
    ("BOLT8", "bolt", "M8", None, None, None),
    ("NUT5", "nut", "M5", None, None, None),
    ("WASHER6", "washer", "M6", None, None, None),
    ("CBM6-20", "socket_cap", "M6", 20.0, None, "black"),
    # the owner's own bolts, nuts and washers: normal metric, many lengths and coatings
    ("DIN 933 M16x50 8.8 HDG", "hex_bolt", "M16", 50.0, "8.8", "galvanized"),
    ("DIN 931 M20x120 10.9 tZn", "hex_bolt", "M20", 120.0, "10.9", "galvanized"),
    ("ISO 4014 M24x150 8.8 thermisch verzinkt", "hex_bolt", "M24", 150.0, "8.8", "galvanized"),
    ("DIN 912 M10x30 12.9", "socket_cap", "M10", 30.0, "12.9", "black"),
    ("ISO 4762 M8x25 - 12.9 zwart", "socket_cap", "M8", 25.0, "12.9", "black"),
    ("ISO 4762 M6x20 A2-70", "socket_cap", "M6", 20.0, None, "stainless"),
    ("DIN 7991 M8x20 10.9 gvz", "countersunk_socket", "M8", 20.0, "10.9", "zinc"),
    ("ISO 10642 M6x16 A4", "countersunk_socket", "M6", 16.0, None, "stainless"),
    ("ISO 7380 M6x12 RVS", "button_socket", "M6", 12.0, None, "stainless"),
    ("DIN 934 M16 8 HDG", "hex_nut", "M16", None, None, "galvanized"),
    ("ISO 4032 M12 - 8 tZn", "hex_nut", "M12", None, None, "galvanized"),
    ("DIN 985 M10 A2", "lock_nut", "M10", None, None, "stainless"),
    ("ISO 7040 M8 Zn", "lock_nut", "M8", None, None, "zinc"),
    ("DIN 125 A17 HDG", "washer", None, None, None, "galvanized"),
    ("ISO 7089 M12 - 200HV HDG", "washer", "M12", None, None, "galvanized"),
    ("DIN 9021 M8 A4", "washer", "M8", None, None, "stainless"),
    ("DIN 127 B10 Zn", "spring_washer", None, None, None, "zinc"),
    ("DIN 975 M12x1000 8.8 HDG", "threaded_rod", "M12", 1000.0, "8.8", "galvanized"),
    ("DIN 913 M6x10 45H", "set_screw", "M6", 10.0, None, "black"),
    ("ISO 4026 M8x12 A2", "set_screw", "M8", 12.0, None, "stainless"),
    # coating words
    ("DIN 933 M10x40 8.8 galvanisch verzinkt", "hex_bolt", "M10", 40.0, "8.8", "zinc"),
    ("DIN 933 M10x40 8.8 elektrolytisch verzinkt", "hex_bolt", "M10", 40.0, "8.8", "zinc"),
    ("DIN 933 M10x40 8.8 Delta Tone", "hex_bolt", "M10", 40.0, "8.8", "zinc_flake"),
    ("DIN 933 M10x40 8.8 blank", "hex_bolt", "M10", 40.0, "8.8", "plain"),
    ("DIN 933 M10x40 stainless", "hex_bolt", "M10", 40.0, None, "stainless"),
])
def test_parse_supplier_and_owner_names(name, kind, size, length, pclass, finish):
    info = F.parse(name)
    assert info is not None, name
    assert (info.kind, info.size, info.length, info.property_class, info.finish) == \
        (kind, size, length, pclass, finish), name


def test_supplier_notation_is_vendor_match():
    assert F.parse("MSSF5-5").matched_by == "vendor"
    assert F.parse("BOLT5-20").family == "screw"
    assert F.parse("NUT5").family == "nut"
    assert F.parse("WASHER6").family == "washer"


def test_families():
    assert F.parse("DIN 934 M12").family == "nut"
    assert F.parse("DIN 125 A 13").family == "washer"
    assert F.parse("ISO 4017 M12x40").family == "screw"
    assert F.parse("ISO 2338 6m6x20").family == "pin"


def test_describe():
    text = F.describe(F.parse("ISO 4017 M12 x 40 - 8.8 HDG"))
    assert "Hex bolt M12x40" in text and "8.8" in text and "galvanized" in text.lower()
    assert F.describe(None) == "Not a standard part"
