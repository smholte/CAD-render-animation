"""Weld symbols in the view and in renders, and the weld list (task 0320).

* **The switch** ``scene.fresing_welds.symbols`` (3 Looks > Welds, off by default, saved with the project): on, every
  shown weld gets an ISO 2553 symbol (system A) beside its main seam, drawn by a POST_PIXEL draw handler in every 3D
  view – fixed size on the screen, so it reads at any zoom, nothing in ``bpy.data``. The words come from
  ``core/weld_symbols.py``; the look is the app's label style (the brand kit's box colour, white lines and text).
* **Show in renders** (``symbols_render``, off by default): the same symbols go into rendered pictures and videos as
  labels (``callouts.draws_at`` asks ``label_todo``): a box with the symbol's text and a line to the seam.
* **The number** of a weld is its place in the list (1, 2 …): on the symbol and in the weld list.
* **The weld list** (``fresing.weld_list``, a function window) – one row per weld, and **Export CSV…**
  (``fresing.weld_list_csv``).
"""

from __future__ import annotations

import hashlib
import os

import bpy
from mathutils import Vector

from ..core import weld_symbols as core
from . import welds

_HANDLE = [None]
_THICK: dict = {}                    # weld key -> (seam_data hash, thinner plate in m)


def on(scene=None) -> bool:
    scene = scene or bpy.context.scene
    st = getattr(scene, "fresing_welds", None)
    return bool(st is not None and st.symbols and len(st.items))


def in_renders(scene=None) -> bool:
    scene = scene or bpy.context.scene
    st = getattr(scene, "fresing_welds", None)
    return bool(on(scene) and st.symbols_render)


# ---------------------------------------------------------------------------
# the data of a weld
# ---------------------------------------------------------------------------

def _thickness(item) -> float:
    """The thinner plate at the weld's seams (m; 0 when it cannot be read) – kept while its seams stay."""
    h = hashlib.md5(item.seam_data.encode()).hexdigest() if item.seam_data else ""
    hit = _THICK.get(item.key)
    if hit is not None and hit[0] == h:
        return hit[1]
    t = 0.0
    try:
        seams, sa, sb = welds.find(item)
        t = welds._thickness_mm(seams, sa, sb) / 1000.0
    except Exception:  # noqa: BLE001 - a symbol never breaks the view
        t = 0.0
    _THICK[item.key] = (h, t)
    return t


def data_of(item, number: int, thickness: bool = True) -> core.Weld:
    """What the symbol and the list need of one weld (``number``: its place in the list, from 1)."""
    seams = [core.Seam(kind=s.kind, length=float(s.length), closed=bool(s.closed)) for s in item.seams if s.enabled]
    if getattr(item, "from_cad", False) and item.cad_closed and len(seams) > 1:
        # task 0323: a CAD bead round a square post (seams round in a loop) is one weld all round
        seams = [core.Seam(kind=seams[0].kind, length=sum(x.length for x in seams), closed=True)]
    lost = bool(item.lost or item.part_a is None or item.part_b is None)
    metal, process = "STEEL", "MAG"
    if not lost:
        try:
            r = welds.resolved(item)
            metal, process = r["metal"], r["process"]
        except Exception:  # noqa: BLE001
            pass
    needs_t = thickness and not lost and any(core.seam_kind(core.Weld(0, kind=item.kind), s) == "BUTT" for s in seams)
    return core.Weld(number=number, name=item.name, part_a=welds.part_name(item.part_a),
                     part_b=welds.part_name(item.part_b), kind=item.kind, size=float(item.size),
                     thickness=_thickness(item) if needs_t else 0.0, seams=seams, intermittent=bool(item.intermittent),
                     piece=float(item.length), pitch=float(item.pitch), process=process, finish=item.finish,
                     metal=metal, lost=lost,
                     square=bool(getattr(item, "from_cad", False) and item.cad_kind == "BUTT" and item.cad_gap > 0))


def all_data(scene) -> list:
    return [data_of(it, i + 1) for i, it in enumerate(welds.items(scene))]


def symbol_of(item, number: int) -> core.Symbol | None:
    return core.symbol(data_of(item, number))


def anchor_world(item) -> Vector | None:
    """Where the arrow points: the middle of the weld's longest ticked seam, in the world."""
    on_ = [s for s in item.seams if s.enabled]
    if not on_ or item.part_a is None:
        return None
    m = max(on_, key=lambda s: s.length)
    return item.part_a.matrix_world @ Vector(m.mid)


def shown(item) -> bool:
    """A weld whose symbol is drawn: not lost or hidden, both parts shown in the view."""
    if item.lost or item.hidden or item.part_a is None or item.part_b is None:
        return False
    try:
        return item.part_a.visible_get() and item.part_b.visible_get()
    except RuntimeError:
        return False


def shown_in_render(item) -> bool:
    if item.lost or item.hidden or item.part_a is None or item.part_b is None:
        return False
    from . import callouts
    return not (callouts.is_hidden(item.part_a) or callouts.is_hidden(item.part_b))


# ---------------------------------------------------------------------------
# renders: the symbols as labels (callouts.draws_at)
# ---------------------------------------------------------------------------

def label_todo(scene, size, mat) -> list:
    """[(text, anchor pixel, alpha)] of the weld symbols in a picture of ``size`` seen through ``mat`` (camera), when
    the symbols are on and 'Show in renders' is ticked."""
    if not in_renders(scene):
        return []
    from . import callouts
    out = []
    for i, it in enumerate(welds.items(scene)):
        if not shown_in_render(it):
            continue
        sym = symbol_of(it, i + 1)
        p = anchor_world(it)
        if sym is None or p is None:
            continue
        px, front = callouts.project(mat, size, [tuple(p)])
        if not front[0]:
            continue
        a = (float(px[0, 0]), float(px[0, 1]))
        if not (0 <= a[0] <= size[0] and 0 <= a[1] <= size[1]):
            continue
        out.append((core.label_text(sym), a, 1.0))
    return out


# ---------------------------------------------------------------------------
# the view: one symbol per weld, drawn on the screen
# ---------------------------------------------------------------------------

def layout(sym: core.Symbol, ax: float, ay: float, scale: float, text_w) -> dict:
    """Where everything of one symbol goes on the screen (pixels): the arrow from the seam to the knee, the reference
    line, the dashed line (one side only), the texts, the all-round circle, the tail and the number. ``text_w(t)``
    measures a text in pixels. Plain numbers – tested without a screen."""
    above, below = core.lines(sym)
    pad = 6 * scale
    knee = (ax + 34 * scale, ay + 44 * scale)
    w = max(text_w(above) if above else 0.0, text_w(below)) + 2 * pad
    tail_w = (text_w(sym.tail) + 14 * scale) if sym.tail else 0.0
    num = str(sym.number)
    num_w = text_w(num) + 2 * pad
    x0, y0 = knee
    x1 = x0 + w
    out = {"arrow": (ax, ay, x0, y0), "ref": (x0, y0, x1, y0), "dashed": None, "circle": None,
           "above": (above, x0 + pad, y0 + 5 * scale) if above else None,
           "below": (below, x0 + pad, y0 - 5 * scale), "tail": None,
           "number": (num, x1 + tail_w + pad, y0)}
    if not sym.both_sides:
        out["dashed"] = (x0, y0 + 5 * scale, x1, y0 + 5 * scale)
    if sym.all_round:
        out["circle"] = (x0, y0, 5 * scale)
    if sym.tail:
        out["tail"] = (sym.tail, x1, y0, 9 * scale)
    out["box"] = (x0 - 3 * scale, y0 - 24 * scale, x1 + tail_w + num_w + 2 * pad, y0 + (24 if above else 12) * scale)
    return out


def _colours(scene):
    """The brand kit's card colour (labels' box) and white, as screen values."""
    from ..core import brand
    try:
        c1 = tuple(scene.fresing.brand_color1)
    except Exception:  # noqa: BLE001
        c1 = brand.hex_to_rgb(brand.DEFAULT_COLOR_1)
    return (c1[0], c1[1], c1[2], 0.88), (1.0, 1.0, 1.0, 1.0)


DRAWN = [0]                          # symbols drawn by the last draw (tests)
LAST_ERROR = [""]                    # the last draw's error, if any (a symbol never breaks the view)


def _draw():
    DRAWN[0] = 0
    try:
        _draw_all()
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR[0] = f"{type(exc).__name__}: {exc}"
        print("Fresing Render: weld symbols:", LAST_ERROR[0])


def _draw_all():
    context = bpy.context
    scene = context.scene
    if scene is None or not on(scene):
        return
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return
    import blf
    import gpu
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from gpu_extras.batch import batch_for_shader
    scale = context.preferences.system.ui_scale
    fid = 0
    px = int(round(12 * scale))
    blf.size(fid, px)

    def tw(t):
        return blf.dimensions(fid, t)[0] if t else 0.0
    box_col, ink = _colours(scene)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(max(1.0, 1.5 * scale))
    try:
        for i, it in enumerate(welds.items(scene)):
            if not shown(it):
                continue
            sym = symbol_of(it, i + 1)
            p = anchor_world(it)
            if sym is None or p is None:
                continue
            a = location_3d_to_region_2d(region, rv3d, p)
            if a is None:
                continue
            L = layout(sym, a.x, a.y, scale, tw)
            bx0, by0, bx1, by1 = L["box"]
            shader.uniform_float("color", box_col)
            batch_for_shader(shader, "TRIS", {"pos": [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]},
                             indices=[(0, 1, 2), (0, 2, 3)]).draw(shader)
            lines = [L["arrow"][:2], L["arrow"][2:], L["ref"][:2], L["ref"][2:]]
            ax, ay, kx, ky = L["arrow"]                         # the arrow head at the seam
            d = Vector((kx - ax, ky - ay))
            if d.length > 1e-6:
                d.normalize()
                n = Vector((-d.y, d.x))
                h = 8 * scale
                tip = Vector((ax, ay))
                for side in (1, -1):
                    lines += [tuple(tip), tuple(tip + d * h + n * side * h * 0.4)]
            if L["dashed"] is not None:
                x0, y, x1, _ = L["dashed"]
                step = 7 * scale
                x = x0
                while x < x1:
                    lines += [(x, y), (min(x + step * 0.55, x1), y)]
                    x += step
            if L["tail"] is not None:
                _t, tx, ty, tl = L["tail"]
                lines += [(tx, ty), (tx + tl * 0.8, ty + tl * 0.6), (tx, ty), (tx + tl * 0.8, ty - tl * 0.6)]
            if L["circle"] is not None:
                cx, cy, r = L["circle"]
                import math
                pts = [(cx + r * math.cos(k * math.pi / 8), cy + r * math.sin(k * math.pi / 8)) for k in range(17)]
                for k in range(16):
                    lines += [pts[k], pts[k + 1]]
            shader.uniform_float("color", ink)
            batch_for_shader(shader, "LINES", {"pos": lines}).draw(shader)
            blf.color(fid, *ink)
            if L["above"] is not None:
                t, x, y = L["above"]
                blf.position(fid, x, y, 0)
                blf.draw(fid, t)
            t, x, y = L["below"]
            blf.position(fid, x, y - px, 0)
            blf.draw(fid, t)
            if L["tail"] is not None:
                t, tx, ty, tl = L["tail"]
                blf.position(fid, tx + tl * 0.9, ty - px * 0.4, 0)
                blf.draw(fid, t)
            t, x, y = L["number"]
            blf.position(fid, x, y - px * 0.4, 0)
            blf.draw(fid, t)
            DRAWN[0] += 1
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")


def redraw() -> None:
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:  # noqa: BLE001
        pass


def register():
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_PIXEL")


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], "WINDOW")
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    _THICK.clear()


# ---------------------------------------------------------------------------
# the weld list
# ---------------------------------------------------------------------------

def default_csv_path(scene) -> str:
    from . import render
    try:
        folder = render.default_output_dir(scene)
    except Exception:  # noqa: BLE001
        folder = bpy.app.tempdir or "."
    stem = bpy.path.display_name_from_filepath(bpy.data.filepath) if bpy.data.filepath else "project"
    return os.path.join(folder, f"{stem} – weld list.csv")


def export_csv(scene, path: str) -> str:
    if not path.lower().endswith(".csv"):
        path += ".csv"
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    return core.write_csv(path, all_data(scene))
