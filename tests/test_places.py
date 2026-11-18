"""core/places.py is the one table of where each side-panel panel sits (task 0062): it must match the panels."""

import pytest

from fresing_render.core import places


def test_where_names_the_whole_way():
    assert places.where("FRESING_PT_labels") == "6 Animation > Labels"
    assert places.where("labels") == "6 Animation > Labels"
    assert places.where("cnc_tools") == "4 Motion > CNC machine > Tools"
    assert places.where("scene") == "5 Scene & Render"
    assert places.where("cables", "Into the sea") == "4 Motion > Cables and paths > Into the sea"
    with pytest.raises(KeyError):
        places.where("no_such_panel")


def test_sections_and_numbers():
    assert list(places.SECTIONS.values())[0] == "1 Import" and len(places.SECTIONS) == 8
    assert places.number_of("FRESING_PT_cnc_tools") == 4
    assert places.number_of("FRESING_PT_brand") == 6            # 0062 moved the video finishing group to 6
    assert places.number_of("FRESING_PT_workspace") == 0
    assert places.section_of("FRESING_PT_milling_chips") == "FRESING_PT_motion"
    assert places.children("FRESING_PT_cnc") == ["FRESING_PT_cnc_rotary", "FRESING_PT_cnc_tools",
                                                 "FRESING_PT_cnc_changes", "FRESING_PT_cnc_coolant"]


def test_scene_and_render_is_in_work_order():
    kids = places.children("FRESING_PT_scene")
    order = [kids.index("FRESING_PT_" + n) for n in ("weather", "props", "camera", "shots", "output", "turntable",
                                                      "web3d")]
    assert order == sorted(order)                               # surroundings, camera, saved scenes, outputs
    video = places.children("FRESING_PT_animation")
    for name in ("finishing", "cards", "music", "brand", "labels", "watermark"):
        assert "FRESING_PT_" + name in video


def test_table_matches_the_registered_panels():
    bpy = pytest.importorskip("bpy")
    import fresing_render
    classes = [c for c in fresing_render._all_classes() if isinstance(c, type) and issubclass(c, bpy.types.Panel)
               and getattr(c, "bl_category", "") == "Fresing" and getattr(c, "bl_region_type", "") == "UI"]
    names = {c.__name__ for c in classes}
    for c in classes:
        name, parent = c.__name__, getattr(c, "bl_parent_id", "")
        label = " ".join(c.bl_label.split())
        if name in places.SECTIONS:
            assert not parent and places.SECTIONS[name] == label, name
        elif name in places.PLACES:
            assert places.PLACES[name] == (parent, label), (name, places.PLACES[name], parent, label)
        else:
            assert not parent and name in places.OTHER, f"{name} is not in core/places.py"
    missing = (set(places.SECTIONS) | set(places.PLACES)) - names
    assert not missing, f"core/places.py names panels that do not exist: {sorted(missing)}"
    # sub-panels are registered in the table's order (a sub-panel shows in registration order)
    order = [c.__name__ for c in classes]
    for parent in list(places.SECTIONS) + list(places.PLACES):
        kids = places.children(parent)
        at = [order.index(k) for k in kids]
        assert at == sorted(at), parent
        assert all(order.index(parent) < i for i in at), parent
