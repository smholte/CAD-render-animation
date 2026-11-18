"""Task 0062: the Set-up window (ui_setup.py, ops_setup.py) – its steps, its step buttons, the kind switch.

Blender as a Python module has no window, so the window itself (the split, the copy, the tab) is checked in the real
app by ``tools/ui_test_setup.py``. Here: every step of both set-ups draws – on an empty scene and on its test model
(the gantry for the CNC mill, the linkage model for the mechanism) –, the buttons a step draws exist and take the
options they are given, a step that is done says so, the step is clamped, a change of kind starts at its first step,
and the window button says why it does nothing in a background run instead of failing.
"""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, gcode, joints, ops_setup, ui_setup  # noqa: E402

HERE = os.path.dirname(__file__)
GANTRY = os.path.join(HERE, "data", "test_gantry.step")
LINKAGE = os.path.join(HERE, "data", "test_linkage_a.step")
STOCK = "STOCK 300x200x30"
T1 = "TOOL T1 FLAT D6"


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    mine = []
    for cls in ops_setup.CLASSES + ui_setup.CLASSES:      # until fresing_render/__init__.py registers them itself
        try:
            bpy.utils.register_class(cls)
            mine.append(cls)
        except (RuntimeError, ValueError):
            pass
    yield
    for cls in reversed(mine):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    fresing_render.unregister()


def new_scene(tmp_path, model=""):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    if model:
        assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(*obs):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[-1] if obs else None


class Fake:
    """A layout that draws nothing: it writes down the texts and checks that what is drawn exists."""

    def __init__(self, seen=None):
        self.seen = seen if seen is not None else {"errors": [], "labels": [], "ops": [], "props": []}
        self.scale_y = 1
        self.alignment = "LEFT"
        self.active = True
        self.enabled = True
        self.alert = False

    def _child(self, *a, **k):
        return Fake(self.seen)

    row = column = box = split = grid_flow = _child

    def label(self, text="", **k):
        self.seen["labels"].append(text)

    def separator(self, *a, **k):
        pass

    def panel(self, idname, default_closed=False):
        return Fake(self.seen), Fake(self.seen)

    def prop(self, data, name, *a, **k):
        if data is None or name not in data.bl_rna.properties:
            self.seen["errors"].append(f"missing property {type(data).__name__}.{name}")
        self.seen["props"].append(name)

    def prop_search(self, data, name, search_data, search_prop, *a, **k):
        self.prop(data, name)
        if search_prop not in search_data.bl_rna.properties:
            self.seen["errors"].append(f"missing search list {search_prop}")

    def operator(self, idname, text="", **k):
        group, op = idname.split(".")
        errors = self.seen["errors"]
        given = {}
        self.seen["ops"].append((idname, text, given, dict(k)))
        try:
            rna = getattr(getattr(bpy.ops, group), op).get_rna_type()
        except Exception:
            errors.append(f"missing operator {idname}")
            return type("OpProps", (), {})()

        class OpProps:                       # setting an option the operator does not have is an error
            def __setattr__(self, name, value):
                if name not in rna.properties:
                    errors.append(f"operator {idname} has no option {name}")
                given[name] = value
        return OpProps()

    def operator_menu_enum(self, idname, prop, text="", **k):
        group, op = idname.split(".")
        try:
            rna = getattr(getattr(bpy.ops, group), op).get_rna_type()
            if prop not in rna.properties:
                self.seen["errors"].append(f"operator {idname} has no option {prop}")
        except Exception:
            self.seen["errors"].append(f"missing operator {idname}")
        self.seen["labels"].append(text)


def draw(context=None):
    """Draws the whole Set-up once; returns what was drawn."""
    fake = Fake()
    ui_setup.draw_setup(fake, context or bpy.context)
    assert not fake.seen["errors"], fake.seen["errors"]
    return fake.seen


def text_of(seen) -> str:
    return " ".join(seen["labels"])


def buttons(seen, idname):
    return [(text, given, kw) for name, text, given, kw in seen["ops"] if name == idname]


def draw_every_step(sc) -> dict:
    """Every step of every set-up, through the buttons; returns {(kind, step): what was drawn}."""
    out = {}
    for kind, (title, steps) in ui_setup.SETUPS.items():
        assert bpy.ops.fresing.setup_kind(kind=kind) == {"FINISHED"}
        for k, (name, _fn) in enumerate(steps):
            assert bpy.ops.fresing.setup_go(step=k) == {"FINISHED"}
            assert ui_setup.current(sc) == (kind, k, steps)
            seen = draw()
            assert title in seen["labels"], "the kind picker shows the set-up's title"
            assert f"Step {k + 1} of {len(steps)}: {name}" in seen["labels"]
            go = buttons(seen, "fresing.setup_go")
            numbers = [b for b in go if b[0].isdigit()]
            assert [b[0] for b in numbers] == [str(i + 1) for i in range(len(steps))]
            assert [b[1]["step"] for b in numbers] == list(range(len(steps)))
            assert [bool(b[2].get("depress")) for b in numbers] == [i == k for i in range(len(steps))]
            back = next(b for b in go if b[0] == "Back")
            assert back[1]["step"] == k - 1 and not back[2].get("depress"), "Back is grey"
            last = next(b for b in go if b[0] in ("Next", "Done"))
            assert last[2].get("depress"), "Next is the blue button"
            if k < len(steps) - 1:
                assert last[0] == "Next" and last[1]["step"] == k + 1
            else:
                assert last[0] == "Done" and last[1] == {"step": k, "done": True}
            out[(kind, k)] = seen
    return out


# ---------------------------------------------------------------------------------------------------------------

def test_the_table_of_set_ups():
    assert list(ui_setup.SETUPS) == ["CNC", "MECH"]
    kinds = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.properties["setup_kind"].enum_items
    assert [e.identifier for e in kinds] == list(ui_setup.SETUPS), "props.py and SETUPS list the same set-ups"
    for kind, (title, steps) in ui_setup.SETUPS.items():
        assert kinds[kind].name == title, "the same title in the project setting and in the window"
        assert len(ui_setup.CHECKS[kind]) == len(steps)
        assert all(callable(fn) and name for name, fn in steps)
    assert [n for n, _f in ui_setup.SETUPS["CNC"][1]] == ["Axes X, Y, Z", "Spindle", "Tool and workpiece",
                                                         "Work zero", "G-code program"]
    assert [n for n, _f in ui_setup.SETUPS["MECH"][1]] == ["Type", "Base", "Moving links", "Add it"]
    assert ui_setup.FRESING_PT_setup.bl_category == "Set-up" and ui_setup.FRESING_PT_setup.bl_label == "Set-up"
    assert ui_setup.CLASSES == (ui_setup.FRESING_PT_setup,)


def test_every_step_draws_on_an_empty_scene(tmp_path):
    sc = new_scene(tmp_path)
    drawn = draw_every_step(sc)
    assert len(drawn) == 9
    for (kind, k), seen in drawn.items():
        assert not ui_setup.is_done(bpy.context, kind, k), (kind, k)
    assert "not picked yet" in text_of(drawn[("CNC", 2)])
    assert buttons(drawn[("CNC", 4)], "fresing.block_add")[0][1] == {"kind": "GCODE"}
    # the panel itself: body, icon and state
    fake = type("P", (), {"layout": Fake()})()
    cls = ui_setup.FRESING_PT_setup
    cls.draw(fake, bpy.context)
    cls.draw_header(fake, bpy.context)
    cls.draw_header_preset(fake, bpy.context)
    assert not fake.layout.seen["errors"]
    assert "4 of 4" in fake.layout.seen["labels"]
    assert not cls.poll(bpy.context), "the tab shows only in a Set-up window"


def test_cnc_steps_on_the_gantry(tmp_path):
    sc = new_scene(tmp_path, GANTRY)
    drawn = draw_every_step(sc)
    assert "0 slide joints so far" in text_of(drawn[("CNC", 0)])
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    bpy.ops.fresing.setup_kind(kind="CNC")
    assert sc.fresing.setup_step == 0, "back from the mechanism: the first step"

    seen = draw()                                              # step 1: the axes
    assert "3 slide joints so far" in text_of(seen) and "X, Y and Z are picked" not in text_of(seen)
    assert buttons(seen, "fresing.cnc_find_axes")[0][0] == "Find the axes"
    assert not buttons(seen, "fresing.cnc_find_axes")[0][2].get("depress"), "only Next is blue"
    assert {"x_joint", "y_joint", "z_joint", "x_reverse"} <= set(seen["props"])
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    assert "X, Y and Z are picked" in text_of(draw())
    assert ui_setup.is_done(bpy.context, "CNC", 0) and not ui_setup.is_done(bpy.context, "CNC", 2)

    bpy.ops.fresing.setup_go(step=2)                           # step 3: tool and workpiece
    seen = draw()
    one = next(b for b in buttons(seen, "fresing.setup_go") if b[0] == "1")
    assert one[2].get("icon_value") or one[2].get("icon") == "CHECKMARK", "a done step's number carries the tick"
    assert "Nothing clicked yet" in text_of(seen) and "Tool: not picked yet" in text_of(seen)
    assert [b[0] for b in buttons(seen, "fresing.cnc_use_tool") + buttons(seen, "fresing.cnc_use_workpiece")] == \
        ["Use as tool", "Use as workpiece"]
    click(ob(sc, T1))
    assert f"Clicked: {T1}" in text_of(draw())
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    seen = draw()
    assert f"Tool: {T1}" in text_of(seen) and f"Workpiece: {STOCK}" in text_of(seen)
    assert ui_setup.is_done(bpy.context, "CNC", 2)

    bpy.ops.fresing.setup_go(step=3)                           # step 4: the work zero
    seen = draw()
    assert "zero_mode" in seen["props"] and "The machine is ready" in text_of(seen)
    assert not buttons(seen, "fresing.setup_in_view")
    gcode.settings(sc).zero_mode = "POINT"
    pick = buttons(draw(), "fresing.setup_in_view")
    assert pick and pick[0][1] == {"op": "fresing.cnc_zero_click"}, "the click picker runs in the main window"
    gcode.settings(sc).zero_mode = "TOP_CENTRE"

    bpy.ops.fresing.setup_go(step=4)                           # step 5: the program
    seen = draw()
    add = buttons(seen, "fresing.block_add")
    assert add and add[0][1] == {"kind": "GCODE"} and "gcode_file" not in seen["props"]
    assert bpy.ops.fresing.block_add(kind="GCODE") == {"FINISHED"}
    seen = draw()
    assert "gcode_file" in seen["props"] and not buttons(seen, "fresing.block_add")
    assert not ui_setup.is_done(bpy.context, "CNC", 4)
    program = tmp_path / "part.ngc"
    program.write_text("G21 G90\nG0 X0 Y0 Z5\nM30\n")
    ui_setup._gcode_step(sc).gcode_file = str(program)
    assert "The animation runs part.ngc" in text_of(draw())
    assert all(ui_setup.is_done(bpy.context, "CNC", k) for k in (0, 2, 3, 4))
    draw_every_step(sc)                                         # and every step again, on the finished machine


def test_mechanism_steps_on_the_linkage_model(tmp_path):
    sc = new_scene(tmp_path, LINKAGE)
    draw_every_step(sc)
    s = sc.fresing
    bpy.ops.fresing.setup_kind(kind="MECH")
    bpy.ops.fresing.setup_go(step=0)
    s.mech_kind = "FOURBAR"
    seen = draw()                                              # step 1: the type, with what it is in words
    assert "mech_kind" in seen["props"] and "coupler" in text_of(seen)

    bpy.ops.fresing.setup_go(step=1)                           # step 2: the base
    seen = draw()
    assert "the part the two arms turn on" in text_of(seen) and "No base picked" in text_of(seen)
    assert [b[0] for b in buttons(seen, "fresing.mechanism_pick_base")] == ["Use as base"]
    click(ob(sc, "FOURBAR.BASE.ASM"))
    assert bpy.ops.fresing.mechanism_pick_base() == {"FINISHED"}
    seen = draw()
    assert "Base: FOURBAR.BASE.ASM" in text_of(seen)
    assert buttons(seen, "fresing.mechanism_pick_base")[1][1] == {"clear": True}, "the X that forgets the base"

    bpy.ops.fresing.setup_go(step=2)                           # step 3: the links
    click()
    assert "Nothing selected yet" in text_of(draw())
    click(ob(sc, "FOURBAR.COUPLER.ASM"), ob(sc, "FOURBAR.ROCKER.ASM"), ob(sc, "FOURBAR.CRANK.ASM"))
    assert "3 subassemblies selected" in text_of(draw())

    bpy.ops.fresing.setup_go(step=3)                           # step 4: add it
    seen = draw()
    assert buttons(seen, "fresing.mechanism_add")[0][0] == "Add mechanism" and "Made:" not in text_of(seen)
    assert bpy.ops.fresing.mechanism_add() == {"FINISHED"}
    assert len(s.mechanisms) == 1
    assert f"Made: {s.mechanisms[0].name}" in text_of(draw())
    assert ui_setup.is_done(bpy.context, "MECH", 3)
    draw_every_step(sc)


def test_go_clamps_to_the_steps(tmp_path):
    sc = new_scene(tmp_path)
    s = sc.fresing
    bpy.ops.fresing.setup_kind(kind="CNC")
    for want, got in ((2, 2), (99, 4), (-7, 0), (4, 4), (5, 4)):
        assert bpy.ops.fresing.setup_go(step=want) == {"FINISHED"}
        assert s.setup_step == got and ui_setup.current(sc)[1] == got
    bpy.ops.fresing.setup_kind(kind="MECH")
    assert bpy.ops.fresing.setup_go(step=99) == {"FINISHED"} and s.setup_step == 3
    assert ops_setup.go(sc, 1) == 1 and ops_setup.go(sc, 50) == 3
    # the Done button stays on the last step and says what is still open
    assert bpy.ops.fresing.setup_go(step=3, done=True) == {"FINISHED"} and s.setup_step == 3
    # a step number left over from a longer set-up (a project written by hand) is shown clamped
    s.setup_step = 40
    assert ui_setup.current(sc)[1] == 3
    draw()


def test_a_change_of_kind_starts_at_the_first_step(tmp_path):
    sc = new_scene(tmp_path)
    s = sc.fresing
    assert (s.setup_kind, s.setup_step) == ("CNC", 0)
    bpy.ops.fresing.setup_go(step=3)
    assert bpy.ops.fresing.setup_kind(kind="MECH") == {"FINISHED"}
    assert (s.setup_kind, s.setup_step) == ("MECH", 0)
    bpy.ops.fresing.setup_go(step=2)
    assert bpy.ops.fresing.setup_kind(kind="MECH") == {"FINISHED"}
    assert (s.setup_kind, s.setup_step) == ("MECH", 2), "the same kind again keeps the step"
    # the window button with a kind: the same switch (the window itself does not open in a background run)
    assert bpy.ops.fresing.setup_window(kind="CNC") == {"CANCELLED"}
    assert (s.setup_kind, s.setup_step) == ("CNC", 0)
    bpy.ops.fresing.setup_go(step=4)
    assert bpy.ops.fresing.setup_window(kind="CNC") == {"CANCELLED"} and s.setup_step == 4
    assert bpy.ops.fresing.setup_window() == {"CANCELLED"} and (s.setup_kind, s.setup_step) == ("CNC", 4)
    # the setting changed directly (a script, a drop-down elsewhere): the window shows the first step all the same
    s.setup_kind = "MECH"
    assert ui_setup.current(sc)[:2] == ("MECH", 0)
    assert "Step 1 of 4: Type" in draw()["labels"]
    bpy.ops.fresing.setup_go(step=1)
    assert (s.setup_kind, s.setup_step) == ("MECH", 1) and ui_setup.current(sc)[1] == 1
    s.setup_kind = "CNC"
    assert ui_setup.current(sc)[:2] == ("CNC", 0)
    ops_setup.set_kind(sc, "CNC")
    assert (s.setup_kind, s.setup_step) == ("CNC", 0)


def test_the_window_button_in_a_background_run(tmp_path):
    sc = new_scene(tmp_path)
    assert bpy.app.background
    assert bpy.ops.fresing.setup_window() == {"CANCELLED"}, "a plain report, no window, no error"
    assert bpy.ops.fresing.setup_window("INVOKE_DEFAULT", kind="MECH") == {"CANCELLED"}
    assert sc.fresing.setup_kind == "MECH"
    with pytest.raises(RuntimeError, match="No set-up is called"):
        bpy.ops.fresing.setup_window(kind="LATHE")
    assert sc.fresing.setup_kind == "MECH"
    assert ops_setup.setup_windows() == [] and not ops_setup.is_setup_window(None)
    assert not bpy.ops.fresing.setup_close.poll()
    before = len(bpy.app.handlers.load_pre)
    ops_setup.restore_tabs()                                    # nothing to do, nothing left behind
    assert len(bpy.app.handlers.load_pre) == before and not ops_setup._STATE["busy"]
    # a button that picks in the 3D view: only the listed ones, and a plain message without a view
    with pytest.raises(RuntimeError, match="not a button that picks"):
        bpy.ops.fresing.setup_in_view(op="wm.quit_blender")
    assert bpy.ops.fresing.setup_in_view(op="fresing.cnc_zero_click") == {"CANCELLED"}


def test_tooltips():
    scene_ok = bpy.context.scene is not None
    assert scene_ok
    bpy.ops.fresing.setup_kind(kind="CNC")
    bpy.ops.fresing.setup_go(step=1)
    P = lambda **kw: type("Props", (), kw)()                    # noqa: E731
    cls = {c.bl_idname: c for c in ops_setup.CLASSES}
    texts = {
        "window": cls["fresing.setup_window"].description(bpy.context, P(kind="")),
        "window cnc": cls["fresing.setup_window"].description(bpy.context, P(kind="CNC")),
        "window mech": cls["fresing.setup_window"].description(bpy.context, P(kind="MECH")),
        "next": cls["fresing.setup_go"].description(bpy.context, P(step=2, done=False)),
        "back": cls["fresing.setup_go"].description(bpy.context, P(step=0, done=False)),
        "here": cls["fresing.setup_go"].description(bpy.context, P(step=1, done=False)),
        "jump": cls["fresing.setup_go"].description(bpy.context, P(step=4, done=False)),
        "done": cls["fresing.setup_go"].description(bpy.context, P(step=4, done=True)),
        "pick": cls["fresing.setup_in_view"].description(bpy.context, P(op="fresing.cnc_zero_click")),
        "kind": bpy.ops.fresing.setup_kind.get_rna_type().description,
        "close": bpy.ops.fresing.setup_close.get_rna_type().description,
    }
    for name, text in texts.items():
        assert len(text.split()) >= 8 and "\n" not in text and "  " not in text, (name, text)
    assert "Set up a CNC mill" in texts["window cnc"] and "Work zero" in texts["window cnc"]
    assert "Set up a mechanism" in texts["window mech"]
    assert texts["next"].startswith("Goes on to step 3 of 5: Tool and workpiece")
    assert texts["back"].startswith("Goes back to step 1 of 5: Axes X, Y, Z")
    assert texts["here"].startswith("This is step 2 of 5: Spindle")
    assert texts["jump"].startswith("Goes straight to step 5 of 5: G-code program")
    assert "main window" in texts["pick"] and "zero" in texts["pick"]
    for item in bpy.ops.fresing.setup_kind.get_rna_type().properties["kind"].enum_items:
        assert len(item.description.split()) >= 5, item.identifier
    for c in ops_setup.CLASSES:                                 # every option that can be set has its text
        for p in bpy.ops.fresing.__getattr__(c.bl_idname.split(".")[1]).get_rna_type().properties:
            if p.identifier != "rna_type":
                assert len(p.description.split()) >= 5, (c.bl_idname, p.identifier)


def test_the_green_tick_is_a_tick():
    px = ui_setup._tick_pixels(32)
    assert len(px) == 32 * 32 * 4
    alpha = px[3::4]
    assert 0.1 < sum(alpha) / len(alpha) < 0.35, "two strokes, not a blob"
    assert alpha[0] == 0.0 and alpha[-1] == 0.0 and max(alpha) == 1.0
    assert px[:3] == [0.0, 0.0, 0.0], "colour times alpha: nothing where the icon is see-through"
    k = alpha.index(1.0) * 4
    r, g, b = px[k:k + 3]
    assert g > 2 * r and g > 2 * b, "green"
    # drawing a done line never fails, with or without the icon
    fake = Fake()
    ui_setup.done_line(fake, bpy.context, "Tool and workpiece are picked " * 4)
    assert len(fake.seen["labels"]) >= 2
