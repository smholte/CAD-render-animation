"""Task 0336 (0328 rows 14, 15, 31): the Web 3D model panel (5 Scene & Render > Web 3D model, and Make > 3D page).

Row 14: after Export the result lay below the Make window's edge – Open page and Show in folder now sit on Export's
own row (greyed until there is a page). Row 15: "Include animation" was greyed with no reason – before a Build the
panel says so and offers Build & play. Row 31: every camera became a page view (the Turntable camera too) – a tick per
camera, the app's own cameras off by default.
"""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import cameras, ui_web3d, web3d  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MILL = os.path.join(ROOT, "tests", "data", "test_mill.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    return bpy.context.scene


class Rec:
    """A layout that writes down every item: (kind, what, text, enabled, the id of the row it sits in)."""
    _n = [0]

    def __init__(self, items, enabled=True, rid=0):
        self.items, self._enabled, self.rid = items, enabled, rid
        self.enabled = True
        self.scale_y = self.scale_x = 1
        self.alignment = "LEFT"
        self.active = True
        self.alert = False
        self.use_property_split = self.use_property_decorate = False

    def _on(self):
        return self._enabled and self.enabled

    def _child(self, *a, **k):
        Rec._n[0] += 1
        return Rec(self.items, self._on(), Rec._n[0])

    row = column = box = split = grid_flow = _child

    def panel(self, idname, default_closed=False):
        head = self._child()
        self.items.append(("fold", idname, "", True, self.rid))
        return head, self._child()

    def separator(self, *a, **k):
        pass

    def operator_menu_enum(self, idname, prop, *a, **k):
        return self.operator(idname, **k)

    def menu(self, *a, **k):
        pass

    def popover(self, *a, **k):
        pass

    def label(self, *a, **k):
        self.items.append(("label", "", k.get("text", ""), self._on(), self.rid))

    def prop(self, data, name, *a, **k):
        assert name in data.bl_rna.properties, name
        self.items.append(("prop", name, k.get("text", ""), self._on(), self.rid))

    def operator(self, idname, *a, **k):
        self.items.append(("op", idname, k.get("text", ""), self._on(), self.rid))
        mod, op = idname.split(".")
        rna = getattr(getattr(bpy.ops, mod), op).get_rna_type()

        class Props:
            def __setattr__(self, name, value):
                assert name in rna.properties, (idname, name)
                object.__setattr__(self, name, value)
        return Props()


def draw(context=None):
    items = []
    ui_web3d.FRESING_PT_web3d.draw(type("P", (), {"layout": Rec(items)})(), context or bpy.context)
    return items


def ops(items, idname):
    return [x for x in items if x[0] == "op" and x[1] == idname]


def test_open_page_sits_on_the_export_row(tmp_path):
    """Row 14: Open page and Show in folder are on Export's row – greyed before an export, live after it."""
    sc = fresh()
    items = draw()
    (export,) = ops(items, "fresing.web3d_export")
    (page,) = ops(items, "fresing.open_file")
    (folder,) = ops(items, "fresing.show_in_folder")
    k = items.index(export)
    assert items[k + 1:k + 3] == [page, folder]                 # drawn right after Export, on its row
    assert not page[3] and not folder[3] and export[3]
    glb, html = tmp_path / "m.glb", tmp_path / "m.html"
    glb.write_bytes(b"x")
    html.write_text("x")
    w = web3d.settings(sc)
    w.last_path, w.last_html, w.last_text, w.last_size = str(glb), str(html), "12 parts, 1.0 MB", 1000
    items = draw()
    (export,) = ops(items, "fresing.web3d_export")
    (page,) = ops(items, "fresing.open_file")
    (folder,) = ops(items, "fresing.show_in_folder")
    assert page[3] and folder[3] and page[2] == "Open page"
    # nothing between Export and Open page: they are drawn one after the other
    k = items.index(export)
    assert items[k + 1:k + 3] == [page, folder]
    assert any(x[0] == "label" and x[2] == "m.glb" for x in items[k:])


def test_include_animation_says_why_and_offers_build():
    """Row 15: before a Build the tick is replaced by its label and a Build & play button; after it, the tick."""
    sc = fresh()
    items = draw()
    assert not [x for x in items if x[0] == "prop" and x[1] == "animation"]
    (build,) = ops(items, "fresing.anim_build")
    assert build[2] == "Build & play first"
    k = items.index(build)
    assert items[k - 1][0] == "label" and items[k - 1][2] == "Include animation"
    from fresing_render.blender import turntable
    turntable.make(sc)
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    items = draw()
    assert [x for x in items if x[0] == "prop" and x[1] == "animation" and x[3]]
    assert not ops(items, "fresing.anim_build")


def test_app_cameras_are_off_by_default_and_ticks_choose_the_views(tmp_path):
    """Row 31: the user's cameras go on the page, the app's (turntable, Animation camera) start unticked; a tick per
    camera (fresing.web3d_view, with undo) chooses; All / None; the export follows the ticks."""
    from fresing_render.blender import turntable
    from fresing_render.core import web3d_env as env
    sc = fresh()
    hero = cameras.add_camera(sc, "LOW", lens=50.0, name="Hero shot")
    turntable.make(sc)
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    bpy.context.view_layer.update()
    every = web3d.all_cameras(sc)
    app = [ob for ob in every if web3d.app_camera(ob)]
    assert app and any(ob.get("fr_turntable") for ob in app)
    names = web3d.view_names(sc)
    assert "Hero shot" in names and not set(names) & {ob.name for ob in app}
    assert set(names) == {ob.name for ob in every if not web3d.app_camera(ob)}
    # the fold: header "N of M", a tick row per camera
    items = draw()
    assert ("fold", "fr_web3d_views") in [x[:2] for x in items]
    assert any(x[0] == "label" and x[2] == f"{len(names)} of {len(every)}" for x in items)
    ticks = [x for x in ops(items, "fresing.web3d_view") if x[2] not in ("All", "None")]
    assert len(ticks) == len(every) and all(x[3] for x in ticks)
    # untick the hero, tick the turntable camera
    tt = next(ob for ob in app if ob.get("fr_turntable"))
    assert bpy.ops.fresing.web3d_view(name="Hero shot") == {"FINISHED"}
    assert bpy.ops.fresing.web3d_view(name=tt.name) == {"FINISHED"}
    assert not web3d.on_page(hero) and web3d.on_page(tt)
    names = web3d.view_names(sc)
    assert "Hero shot" not in names and tt.name in names
    out = web3d.export(sc, str(tmp_path / "ticked.glb"), size=512)
    st = env.page_settings(open(out["html"], encoding="utf-8").read())
    assert [v["name"] for v in st["views"]] == names and out["views"] == len(names)
    assert bpy.ops.fresing.web3d_view(every=True, on=False) == {"FINISHED"}
    assert web3d.view_names(sc) == [] and web3d.views(sc) == []
    assert bpy.ops.fresing.web3d_view(every=True, on=True) == {"FINISHED"}
    assert len(web3d.view_names(sc)) == len(every)
    assert bpy.ops.fresing.web3d_view(name="No such camera") == {"CANCELLED"}
