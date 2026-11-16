"""The logo as a watermark and the Fresing brand kit that ships with the app (task 0176)."""
import os

import numpy as np
import pytest

from fresing_render.core import brand
from fresing_render.core.brand import Finishing

LOGO = os.path.join(os.path.dirname(__file__), "..", "fresing_render", "brand", brand.SHIPPED_LOGO)
REVERSED = os.path.join(os.path.dirname(__file__), "..", "fresing_render", "brand", brand.SHIPPED_LOGO_REVERSED)


def test_logo_files_ship_sharp_enough_for_4k():
    for p in (LOGO, REVERSED):
        with open(p, "rb") as fh:
            head = fh.read(33)
        assert head[:8] == b"\x89PNG\r\n\x1a\n"
        assert int.from_bytes(head[16:20], "big") >= 2400
        assert head[25] == 6, "RGBA: the logo keeps its see-through background"


@pytest.mark.parametrize("place", ["CENTRE", "TL", "TR", "BL", "BR"])
@pytest.mark.parametrize("shape", [(1920, 1080), (1080, 1080), (1080, 1920)])
def test_logo_watermark_box_stays_inside_the_picture(place, shape):
    w, h = shape
    x, y, bw, bh = brand.wm_logo_box(place, w, h, 2400, 691, 0.4)
    assert x >= 0 and y >= 0 and x + bw <= w and y + bh <= h
    if place == "CENTRE":
        assert abs(x + bw / 2 - w / 2) <= 1 and abs(y + bh / 2 - h / 2) <= 1


def test_corner_logo_is_smaller_than_the_centre_one():
    c = brand.wm_logo_box("CENTRE", 1920, 1080, 2400, 691, 0.12)
    k = brand.wm_logo_box("BR", 1920, 1080, 2400, 691, 0.12)
    assert k[2] < c[2] / 2 and k[0] > 1920 / 2 and k[1] < 1080 / 2


def test_tint_keeps_the_shape_and_changes_the_colour():
    px = np.zeros((2, 2, 4), np.float32)
    px[..., 0], px[..., 3] = 0.8, [[1.0, 0.5], [0.0, 1.0]]
    assert np.array_equal(brand.tint_rgba(px, "COLOUR"), px)
    w, d = brand.tint_rgba(px, "WHITE"), brand.tint_rgba(px, "DARK")
    assert np.all(w[..., :3] == 1.0) and np.array_equal(w[..., 3], px[..., 3])
    assert np.allclose(d[0, 0, :3], np.array(brand.DARK_RGB) / 255.0) and np.array_equal(d[..., 3], px[..., 3])
    assert px[0, 0, 0] == pytest.approx(0.8), "the input is not changed"


def test_tiles_cover_the_turned_picture_and_png_round_trips(tmp_path):
    cw, ch = brand.tile_canvas_size(1920, 1080)
    assert cw >= (1920 ** 2 + 1080 ** 2) ** 0.5
    w, h, cell_w, cell_h = brand.tile_cell(1920, 2400, 691, 0.12)
    logo = np.full((h, w, 4), 200, np.uint8)
    t = brand.tile_pixels(logo, cell_w, cell_h, cw, ch)
    assert t.shape == (ch, cw, 4)
    covered = (t[..., 3] > 0)
    assert 0.1 < covered.mean() < 0.6
    for (a, b) in ((0, 0), (ch // 3, cw // 3), (ch - 1, cw - 1)):      # every part has logos within a cell or two
        block = covered[max(0, a - 2 * cell_h):a + 2 * cell_h, max(0, b - 2 * cell_w):b + 2 * cell_w]
        assert block.any()
    p = str(tmp_path / "t.png")
    brand.write_png(p, t[:50, :60])
    with open(p, "rb") as fh:
        head = fh.read(33)
    assert int.from_bytes(head[16:20], "big") == 60 and int.from_bytes(head[20:24], "big") == 50


def test_finishing_is_active_with_a_logo_watermark_only():
    assert not Finishing().active
    assert Finishing(wm_logo_file="x.png").active


def test_the_shipped_kit_is_always_listed_and_first(tmp_path):
    assert [k.name for k in brand.all_kits(str(tmp_path / "none"))] == [brand.SHIPPED_NAME]
    brand.save_kit(str(tmp_path), brand.BrandKit(name="Acme"))
    brand.save_kit(str(tmp_path), brand.BrandKit(name="fresing", contact="old"))     # same name: the shipped one wins
    names = [k.name for k in brand.all_kits(str(tmp_path))]
    assert names == [brand.SHIPPED_NAME, "Acme"]
    k = brand.shipped_kit()
    assert (k.color1, k.color2) == ("#1A2027", "#FFFFFF") and brand.is_shipped(" FRESING ")
    assert os.path.isfile(os.path.join(os.path.dirname(LOGO), k.logo))


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import video  # noqa: E402

W, H = 640, 360
GREY = 128


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _png(path, rgb, size=(W, H)):
    img = bpy.data.images.new("t", size[0], size[1], alpha=True)
    img.colorspace_settings.is_data = True
    px = np.empty((size[1], size[0], 4), np.float32)
    px[:, :, :3] = np.array(rgb, np.float32) / 255.0
    px[:, :, 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return str(path)


def _pixels(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.is_data = True
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return (px.reshape(h, w, 4)[::-1, :, :3] * 255.0).round()


def _still(tmp_path, name, **kw):
    path = _png(tmp_path / f"{name}.png", (GREY, GREY, GREY))
    base = dict(wm_logo_file=LOGO, watermark_size=0.12, watermark_opacity=1.0)
    base.update(kw)
    video.finish_picture(path, Finishing(**base), "PNG")
    return _pixels(path)


def test_centre_logo_lands_in_the_middle_only(tmp_path):
    px = _still(tmp_path, "c", wm_place="CENTRE")
    d = np.abs(px - GREY).max(axis=2)
    x, y, w, h = brand.wm_logo_box("CENTRE", W, H, 2400, 691, 0.12)
    assert d[H - (y + h):H - y, x:x + w].max() > 40
    assert d[:20, :].max() < 2 and d[:, :20].max() < 2 and d[-20:, :].max() < 2, "nothing near the edges"


def test_corner_logo_lands_in_its_corner(tmp_path):
    px = _still(tmp_path, "k", wm_place="BR")
    d = np.abs(px - GREY).max(axis=2)
    assert d[H // 2:, W // 2:].max() > 40
    assert d[:H // 2, :].max() < 2 and d[:, :W // 2].max() < 2


def test_tiled_logo_covers_the_picture(tmp_path):
    px = _still(tmp_path, "t", wm_place="TILED")
    d = np.abs(px - GREY).max(axis=2) > 20
    for ys in (slice(0, H // 2), slice(H // 2, H)):
        for xs in (slice(0, W // 2), slice(W // 2, W)):
            assert d[ys, xs].any(), "logos in every quarter"
    centre = _still(tmp_path, "t2", wm_place="CENTRE")
    assert d.mean() > (np.abs(centre - GREY).max(axis=2) > 20).mean() * 1.5


def test_colour_white_and_dark_differ(tmp_path):
    out = {t: _still(tmp_path, f"tint{t}", wm_place="CENTRE", wm_tint=t) for t in ("COLOUR", "WHITE", "DARK")}
    x, y, w, h = brand.wm_logo_box("CENTRE", W, H, 2400, 691, 0.12)
    sl = (slice(H - (y + h), H - y), slice(x, x + w))
    mx, mn = out["WHITE"][sl].max(), out["DARK"][sl].min()
    assert mx > 240 and mn < GREY - 60, "white letters lighter than the grey picture, dark ones darker"
    assert out["WHITE"][sl].min() >= GREY - 2 and out["DARK"][sl].max() <= GREY + 2, "one colour only"
    assert np.abs(out["COLOUR"] - out["WHITE"]).max() > 20 and np.abs(out["COLOUR"] - out["DARK"]).max() > 20


def test_see_through_makes_it_fainter(tmp_path):
    solid = _still(tmp_path, "s1", wm_tint="WHITE", watermark_opacity=1.0)
    faint = _still(tmp_path, "s2", wm_tint="WHITE", watermark_opacity=0.3)
    assert 3 < np.abs(faint - GREY).max() < np.abs(solid - GREY).max()


def test_logo_watermark_in_a_video_frame(tmp_path):
    folder = tmp_path / "fr"
    folder.mkdir()
    files = [_png(folder / f"frame_{i:04d}.png", (GREY, GREY, GREY)) for i in (1, 2)]
    enc = bpy.data.scenes.new("T enc")
    enc.render.resolution_x, enc.render.resolution_y, enc.render.resolution_percentage = W, H, 100
    enc.view_settings.view_transform = "Standard"
    video.build_sequence(enc, files, (W, H), 2, Finishing(wm_logo_file=LOGO, wm_tint="WHITE", watermark_opacity=1.0))
    enc.frame_start = enc.frame_end = 2
    im = enc.render.image_settings
    im.file_format, im.color_mode, im.color_depth = "PNG", "RGB", "8"
    enc.render.filepath = str(tmp_path / "v_")
    bpy.ops.render.render(animation=True, scene=enc.name)
    px = _pixels(tmp_path / "v_0002.png")
    assert np.abs(px - GREY).max() > 60
    bpy.data.scenes.remove(enc)


def test_settings_pick_the_logo_and_words_stay_words(tmp_path):
    sc = bpy.context.scene
    s = sc.fresing
    s.wm_on = True
    s.wm_kind = "FRESING_LOGO"
    s.wm_place, s.wm_tint = "TILED", "DARK"
    fin = video.finishing_for_still(sc, True)
    assert os.path.samefile(fin.wm_logo_file, LOGO) and fin.watermark == "" and (fin.wm_place, fin.wm_tint) == ("TILED", "DARK")
    s.wm_kind = "DRAFT"
    fin = video.finishing_for_still(sc, True)
    assert fin.watermark == "DRAFT" and fin.wm_logo_file == "", "an old project's DRAFT stays words"
    s.wm_kind = "KIT_LOGO"
    s.brand_logo = ""
    assert video.finishing_for_still(sc, True).wm_logo_file == "", "no kit logo: nothing, no crash"
    s.brand_logo = _png(tmp_path / "kit.png", (200, 30, 30), (80, 40))
    assert video.finishing_for_still(sc, True).wm_logo_file.endswith("kit.png")
    assert not video.finishing_for_still(sc, False).wm_logo_file, "off means off"
    assert s.bl_rna.properties["wm_kind"].default == "DRAFT" and not s.bl_rna.properties["wm_on"].default


def test_a_missing_logo_file_gives_no_watermark_instead_of_a_crash(tmp_path):
    px = _still(tmp_path, "m", wm_logo_file="")
    assert np.abs(px - GREY).max() < 1


def test_shipped_kit_loads_and_cannot_be_deleted_or_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv(video.ENV_FOLDER, str(tmp_path / "lib"))
    s = bpy.context.scene.fresing
    assert bpy.ops.fresing.brand_load(name="Fresing") == {"FINISHED"}
    assert s.brand_name == "Fresing" and os.path.samefile(s.brand_logo, REVERSED)
    assert brand.linear_to_hex(s.brand_color1) == "#1A2027"
    assert not bpy.ops.fresing.brand_delete.poll()
    with pytest.raises(RuntimeError, match="comes with the app"):
        bpy.ops.fresing.brand_save()
    s.brand_name = "Fresing copy"
    s.brand_contact = "mine"
    assert bpy.ops.fresing.brand_save() == {"FINISHED"}
    assert [k.name for k in brand.all_kits(str(tmp_path / "lib"))] == ["Fresing", "Fresing copy"]
    assert os.path.isfile(str(tmp_path / "lib" / "Fresing_copy_logo.png")) and s.brand_logo.startswith(str(tmp_path / "lib"))
