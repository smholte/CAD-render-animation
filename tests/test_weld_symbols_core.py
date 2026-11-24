"""Task 0320: the ISO 2553 text of a weld and the weld list (core/weld_symbols.py, no Blender)."""

import csv
import io

from fresing_render.core import weld_symbols as W


def weld(*seams, **kw):
    kw.setdefault("number", 1)
    return W.Weld(seams=[W.Seam(*s) for s in seams], **kw)


def test_fillet_one_side():
    s = W.symbol(weld(("FILLET", 0.2), size=0.005))
    assert W.lines(s) == ("", "a5 ◸ 200")
    assert not s.both_sides and not s.all_round
    assert W.one_line(s) == "a5 ◸ 200 < 135"


def test_fillet_both_sides_and_small_sizes():
    s = W.symbol(weld(("FILLET", 0.2), ("FILLET", 0.195), ("FILLET", 0.01), size=0.0035, process="TIG"))
    assert s.both_sides
    assert W.lines(s) == ("a3.5 ◺ 200", "a3.5 ◸ 200")
    assert W.one_line(s) == "a3.5 ◺/◸ 200 < 141"


def test_all_round():
    s = W.symbol(weld(("FILLET", 0.1894, True), size=0.003, process="MIG"))
    assert s.all_round and W.one_line(s) == "○ a3 ◸ 189 < 131"
    assert W.label_text(s).startswith("1  ○ a3 ◸ 189")


def test_intermittent_gap_is_iso_e():
    # 400 mm, pieces of 50 every 150 (start to start): 3 pieces, 100 mm between them
    s = W.symbol(weld(("FILLET", 0.4), intermittent=True, piece=0.05, pitch=0.15))
    assert s.length == "3 × 50 (100)"
    # pitch not longer than the piece: continuous
    s = W.symbol(weld(("FILLET", 0.4), intermittent=True, piece=0.05, pitch=0.05))
    assert s.length == "400"


def test_intermittent_count_matches_the_bead():
    from fresing_render.core import welds as core
    for total in (0.12, 0.2, 0.33, 0.5, 1.0):
        for closed in (False, True):
            look = core.Look(intermittent=True, length=0.04, pitch=0.11)
            n = len(core.pieces_of(total, look, closed))
            text = W.intermittent_text(total, 0.04, 0.11, closed)
            assert (text.split(" × ")[0] if text else "1") == str(n), (total, closed, text)


def test_butt_square_or_v_by_thickness():
    thin = W.symbol(weld(("BUTT", 0.3), thickness=0.003))
    assert thin.glyph == "‖" and W.lines(thin)[1] == "‖ 300"
    thick = W.symbol(weld(("BUTT", 0.3), thickness=0.012))
    assert thick.glyph == "Λ" and thick.glyph_other == "V" and W.type_words(weld(("BUTT", 0.3), thickness=0.012)) == \
        "Single-V butt"
    both = weld(("BUTT", 0.3), ("BUTT", 0.3), thickness=0.012, finish="GROUND")
    assert W.type_words(both) == "Double-V butt" and W.one_line(W.symbol(both)) == "‾V/Λ 300 < 135"


def test_kind_overrides_what_was_found():
    s = W.symbol(weld(("BUTT", 0.1), kind="FILLET", size=0.004))
    assert s.kind == "FILLET" and s.size == "a4"


def test_no_symbol_without_seams_or_lost():
    assert W.symbol(weld()) is None
    assert W.symbol(weld(("FILLET", 0.1), lost=True)) is None
    assert W.row(weld(lost=True))[4] == "lost"


def test_list_and_csv():
    ws = [weld(("FILLET", 0.2), ("FILLET", 0.2), number=1, name='Plate, "A" – Fin', part_a="Plate", part_b="Fin"),
          weld(("BUTT", 0.3), number=2, name="Butt", thickness=0.003, process="STICK", finish="PAINTED")]
    rows = list(csv.reader(io.StringIO(W.to_csv(ws))))
    assert rows[0] == list(W.COLUMNS) and len(rows) == 3
    assert rows[1][1] == 'Plate, "A" – Fin' and rows[1][6] == "400" and rows[1][7] == "MAG (135)"
    assert rows[2][4] == "Square butt" and rows[2][7] == "Stick (111)" and rows[2][8] == "Painted"


def test_csv_file_has_a_bom_for_excel(tmp_path):
    p = W.write_csv(str(tmp_path / "list.csv"), [weld(("FILLET", 0.1))])
    raw = open(p, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf") and "◸".encode() in raw
