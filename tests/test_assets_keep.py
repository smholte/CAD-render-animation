"""Task 0355: the plain rules of what a project keeps of the Fresing assets pack (``core/assets_keep.py``)."""

from fresing_render.core import assets_keep as K


BASE = {"id": "material:cast_iron", "pack": "fresing-assets-test", "version": "1.0.0", "contract": 1, "sha": "a" * 64}


def test_stamp_of_the_item_and_of_what_came_along():
    item = K.stamp(BASE, name="FRP cast_iron")
    assert item == {**BASE, "name": "FRP cast_iron"} and K.is_item(item)
    part = K.stamp(BASE, name="test.png", part="images", file="textures/2k/test.png", sha="b" * 64)
    assert part["part"] == "images" and part["sha"] == "b" * 64 and not K.is_item(part)
    assert K.read_stamp(item) == item and K.read_stamp(part) == part


def test_read_stamp_never_raises_and_takes_only_ours():
    import json
    for bad in (None, "", "{", "[]", 3, {"id": 5, "version": "1"}, {"id": "x"}, {"version": "1.0.0"}, b"\xff",
                {"id": "", "version": "1.0.0"}, {"id": "a:b", "version": 1}):
        assert K.read_stamp(bad) == {}
    assert K.read_stamp(json.dumps(BASE)) == BASE
    assert K.read_stamp({**BASE, "evil": "x", "contract": True}) == {k: v for k, v in BASE.items() if k != "contract"}

    class Group:                                      # Blender's group of ID properties
        def to_dict(self):
            return dict(BASE)
    assert K.read_stamp(Group()) == BASE


def test_share_key_pictures_by_bytes_others_by_name_and_version():
    a = K.stamp(BASE, name="x.png", part="images", file="textures/2k/x.png", sha="c" * 64)
    b = K.stamp({**BASE, "id": "environment:FACTORY", "version": "1.1.0"}, name="x.png", part="images",
                file="textures/2k/x.png", sha="c" * 64)
    assert K.share_key("images", a) == K.share_key("images", b)         # same bytes: one picture
    g1 = K.stamp(BASE, name="FRP cast_iron")
    g2 = K.stamp({**BASE, "id": "environment:FACTORY"}, name="FRP cast_iron", part="node_groups")
    g3 = K.stamp({**BASE, "version": "1.1.0"}, name="FRP cast_iron")
    assert K.share_key("node_groups", g1) == K.share_key("node_groups", g2)
    assert K.share_key("node_groups", g1) != K.share_key("node_groups", g3)


def test_versions_and_which_copy_answers():
    assert K.version_key("1.10.0") > K.version_key("1.9.2") and K.version_key("x") == ()
    st = [{"version": "1.0.0"}, {"version": "1.2.0"}, {"version": "1.1.0"}]
    assert K.best(st) == 1
    assert K.best(st, want="1.1.0") == 2
    assert K.best(st, want="9.9.9") == 1
    assert K.best([]) == -1


def test_sources():
    assert [K.source_of(v) for v in ("", "pack", "code", "PACK", None, "x")] == ["code", "pack", "code", "code",
                                                                                  "code", "code"]
    assert K.look_src() == "code" and K.look_src("1.2.0") == "pack:1.2.0"
    assert K.parse_look_src("pack:1.2.0") == ("pack", "1.2.0")
    for v in (None, "", "code", "pack", "pack:", "pack:x.y", 5):
        assert K.parse_look_src(v) == ("code", "")


def test_pictures_at_the_project_quality():
    files = {"textures/2k/a.png": 1, "textures/4k/a.png": 1, "textures/1k/a.png": 1, "hdri/h_2k.exr": 1,
             "hdri/h_4k.exr": 1, "textures/4k/only.png": 1}
    assert K.at_quality("textures/4k/a.png", files) == "textures/2k/a.png"
    assert K.at_quality("textures/1k/a.png", files) == "textures/2k/a.png"
    assert K.at_quality("textures/2k/a.png", files) == "textures/2k/a.png"
    assert K.at_quality("hdri/h_4k.exr", files) == "hdri/h_2k.exr"
    assert K.at_quality("textures/4k/only.png", files) == "textures/4k/only.png"     # no 2k sibling: as it is
    assert K.at_quality("textures/4k/a.png", files, "1k") == "textures/1k/a.png"
    assert K.at_quality("lights/PRODUCT.exr", files) == "lights/PRODUCT.exr"


def test_result():
    r = K.Result()
    assert r.ok
    r.failed.append(("material:x", "why"))
    assert not r.ok
