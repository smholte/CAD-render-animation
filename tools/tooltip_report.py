"""Tooltip check: every button and setting in the Fresing side panel, with the tooltip it shows.

    ~/venv/bin/python tools/tooltip_report.py                 # summary + list of missing / weak tooltips
    ~/venv/bin/python tools/tooltip_report.py --all           # every button and setting, also the good ones
    ~/venv/bin/python tools/tooltip_report.py --markdown out.md --all
    ~/venv/bin/python tools/tooltip_report.py --strict        # exit code 1 when a tooltip is missing

How it works: the panels' source (fresing_render/blender/ui*.py) is read to find what is drawn
(buttons, settings, the small buttons beside lists) and in which panel; then the extension is
registered in Blender (as a Python module) and asked for the text that Blender shows when the
mouse rests on each one: an operator's docstring or description(), a property's description,
and for choices shown as a row of buttons each choice's description.

Verdicts (a heuristic that finds the clear cases; a person still reads the "ok" ones):
    missing  hovering shows only the name, no explanation
    weak     the text repeats the label, or is too short to say what happens and how to use it
    ok       says what it does (and, in most cases, how to use it or what happens next)

The style guide for good tooltips is at the top of docs/USER-GUIDE.md.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass, field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

UI_FILES = ["fresing_render/blender/ui.py", "fresing_render/blender/ui_motion.py",
            "fresing_render/blender/ui_machining.py", "fresing_render/blender/ui_decals.py",
            "fresing_render/blender/ui_gcode.py", "fresing_render/blender/ui_section.py",
            "fresing_render/blender/updates.py"]
UNTITLED = {"FRESING_PT_update": "Update notice"}      # panels whose header is drawn by draw_header
# drawing functions called from a panel in another file: {file: {function: panel}}
OTHER_FILE_HELPERS = {"fresing_render/blender/ui_gcode.py": {"draw_step": "6 Animation"}}

# Which lane owns which panel (TASKS.md): the report is a to-do list per lane.
LANE_OF_PANEL = {
    "1 Import": "Looks lane", "2 Structure": "Looks lane", "Clean-up": "Looks lane",
    "Visibility sets": "Looks lane", "3 Looks": "Looks lane", "Find & sort parts": "Looks lane",
    "Sorting rules": "Looks lane", "Paint schemes & templates": "Looks lane", "Paint faces": "Looks lane",
    "4 Motion": "Motion lane", "Poses & exploded views": "Motion lane", "6 Animation": "Motion lane",
    "7 Render queue": "Motion lane", "Saved scenes": "Motion lane",
    "5 Scene & Render": "Scene & Render lane", "Image size & render": "Scene & Render lane",
    "Props for scale": "Scene & Render lane",
    "Update notice": "Quality lane",
    "Milling": "Machining lane", "Chips": "Machining lane", "Make a toolpath": "Machining lane", "CNC machine": "Motion lane",
    "Logos & stickers": "Looks lane", "Cutaway": "Cutaway lane",
}

# Owners of drawn properties, by the expression in the panel code.
OWNER_TYPES = {
    "s": "FRSceneSettings", "g": "FRMaterialGroup", "r": "FRRule", "j": "FRJoint", "b": "FRAnimBlock",
    "a": "FRAnimation", "shot": "FRShot", "scene.camera.data": "Camera", "scene.camera.data.dof": "CameraDOFSettings",
    "m": "FRMilling", "bit": "FRMillBit",                     # 4 Motion > Milling (ui_machining.py)
    "tp": "FRToolpath",                                       # 4 Motion > Milling > Make a toolpath
    "d": "FRDecalSettings", "it": "FRDecal",                  # 3 Looks > Logos & stickers (ui_decals.py)
    "cyl": "FRCylinder",                                      # 4 Motion > Cylinders
    "mech": "FRMechanism",                                    # 4 Motion > Mechanisms
    "cnc": "FRCnc", "tl": "FRCncTool",                        # 4 Motion > CNC machine (ui_gcode.py)
    "cut": "FRCut",                                           # 3 Looks > Cutaway (ui_section.py)
}
# list rows: the type of `item` in each UIList
ITEM_TYPES = {
    "FRESING_UL_groups": "FRMaterialGroup", "FRESING_UL_rules": "FRRule", "FRESING_UL_schemes": "FRScheme",
    "FRESING_UL_visibility": "FRVisSet", "FRESING_UL_found": "FRFoundPart", "FRESING_UL_joints": "FRJoint",
    "FRESING_UL_poses": "FRPose", "FRESING_UL_shots": "FRShot", "FRESING_UL_anims": "FRAnimation",
    "FRESING_UL_blocks": "FRAnimBlock", "FRESING_UL_queue": "FRQueueJob", "FRESING_UL_tree": "FRTreeItem",
    "FRESING_UL_mill_bits": "FRMillBit", "FRESING_UL_cylinders": "FRCylinder",
    "FRESING_UL_mechanisms": "FRMechanism", "FRESING_UL_cnc_tools": "FRCncTool",
    "FRESING_UL_cnc_pockets": "FRCncPocket", "FRESING_UL_cuts": "FRCut",
}


@dataclass
class Item:
    panel: str
    kind: str                  # "button" | "setting" | "choice" (one button of a row of choices)
    label: str                 # what the user sees on it
    ident: str                 # fresing.import_step / FRSceneSettings.import_quality
    line: str                  # file:line
    tooltip: str = ""
    verdict: str = ""
    why: str = ""
    props: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. what the panels draw (source)
# ---------------------------------------------------------------------------


def _text(node) -> str | None:
    """The label as the user sees it; f-strings get … where a value goes."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            out.append(v.value if isinstance(v, ast.Constant) else "…")
        return "".join(out)
    if isinstance(node, ast.IfExp):
        a, b = _text(node.body), _text(node.orelse)
        return f"{a} / {b}" if a is not None and b is not None else (a or b)
    return "…"


def _kw(call: ast.Call, name: str):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def _value(node):
    """A button's option as set in the panel code; '…' when it is computed (a name, an index)."""
    return node.value if isinstance(node, ast.Constant) else "…"


class _Scan(ast.NodeVisitor):
    def __init__(self, fname: str, panels: dict, helpers: dict):
        self.fname = fname
        self.panels = panels              # class name -> panel title
        self.helpers = helpers            # helper function name -> panel title
        self.items: list[Item] = []
        self.panel = ""
        self.cls = ""

    # where are we
    def visit_ClassDef(self, node):
        self.cls = node.name
        self.panel = self.panels.get(node.name, "")
        self.generic_visit(node)
        self.cls, self.panel = "", ""

    def visit_FunctionDef(self, node):
        if not self.cls:
            self.panel = self.helpers.get(node.name, "")
        if self.panel or self.cls.startswith("FRESING_UL_"):
            self._block(node.body)
        if not self.cls:
            self.panel = ""

    # statements in order, so `op = row.operator(...)` and the `op.kind = ...` lines after it stay together
    def _block(self, body):
        last_op = None
        for st in body:
            for call, target in self._calls_in(st):
                it = self._item(call, st)
                if it is None:
                    continue
                self.items.append(it)
                if it.kind == "button" and target is not None:
                    last_op = (target, it)
            # op.kind = "X" / op.mode, op.kind = "NEW", "ROTATE" / row.operator(...).name = n
            if isinstance(st, ast.Assign):
                self._props_from_assign(st, last_op)
            for child in ast.iter_child_nodes(st):
                if isinstance(child, list):
                    continue
            for fld in ("body", "orelse", "finalbody"):
                sub = getattr(st, fld, None)
                if isinstance(sub, list) and sub and not isinstance(st, ast.FunctionDef):
                    self._block(sub)
            if isinstance(st, ast.FunctionDef):      # nested def (e.g. what() in a panel)
                pass

    def _calls_in(self, st):
        """Drawing calls directly in this statement (not in nested blocks); with the name they are assigned to."""
        if isinstance(st, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            exprs = [getattr(st, "test", None), getattr(st, "iter", None)]
            exprs += [w.context_expr for w in getattr(st, "items", [])]
            nodes = [e for e in exprs if e is not None]
        else:
            nodes = [st]
        found = []
        for n in nodes:
            target = None
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                target = st.targets[0].id
            for sub in ast.walk(n):
                if isinstance(sub, ast.Call):
                    found.append((sub, target if sub is getattr(st, "value", None) else None))
        return found

    def _props_from_assign(self, st, last_op):
        # chained: row.operator(...).name = x
        for t in st.targets:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Call):
                it = next((i for i in reversed(self.items) if i.line.endswith(f":{t.value.lineno}")), None)
                if it is not None:
                    it.props[t.attr] = _value(st.value)
        if last_op is None:
            return
        name, it = last_op
        t = st.targets[0]
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == name:
            it.props[t.attr] = _value(st.value)
        elif isinstance(t, ast.Tuple) and isinstance(st.value, ast.Tuple):
            for tt, vv in zip(t.elts, st.value.elts):
                if isinstance(tt, ast.Attribute) and isinstance(tt.value, ast.Name) and tt.value.id == name:
                    it.props[tt.attr] = _value(vv)

    def _item(self, call: ast.Call, st) -> Item | None:
        f = call.func
        name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        line = f"{os.path.basename(self.fname)}:{call.lineno}"
        panel = self.panel or (f"list {self.cls}" if self.cls.startswith("FRESING_UL_") else "")
        if not panel:
            return None
        a = call.args
        if name == "operator" and a and _const(a[0]):
            label = _text(_kw(call, "text"))
            icon = _const(_kw(call, "icon")) or ""
            return Item(panel, "button", label if label else f"[icon {icon}]" if label == "" else "(label from operator)",
                        a[0].value, line)
        if name == "operator_menu_enum" and a and _const(a[0]):
            label = _text(_kw(call, "text")) or ""
            icon = _const(_kw(call, "icon")) or ""
            return Item(panel, "button", label or f"[icon {icon}]", a[0].value, line,
                        props={"__menu__": _const(a[1]) if len(a) > 1 else None})
        if name == "primary" and len(a) >= 4:
            return Item(panel, "button", _text(a[2]) or "", _const(a[1]) or "?", line)
        if name == "use_button" and len(a) >= 2:
            return Item(panel, "button", "Use", _const(a[1]) or "?", line)
        if name in ("prop", "prop_search") and len(a) >= 2:
            owner = ast.unparse(a[0])
            pname = _const(a[1])
            if pname is None:
                pname = ast.unparse(a[1])
            label = _text(_kw(call, "text"))
            it = Item(panel, "setting", label if label is not None else "(label from setting)",
                      f"{owner}.{pname}", line)
            it.props["__owner__"] = owner
            it.props["__prop__"] = pname
            it.props["__expand__"] = bool(_const(_kw(call, "expand")))
            return it
        return None


def scan_ui() -> list[Item]:
    items = []
    for rel in UI_FILES:
        path = os.path.join(ROOT, rel)
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        panels, helpers = {}, {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for st in node.body:
                    if (isinstance(st, ast.Assign) and isinstance(st.targets[0], ast.Name)
                            and st.targets[0].id == "bl_label"):
                        panels[node.name] = (re.sub(r"\s+", " ", st.value.value).strip()
                                             or UNTITLED.get(node.name, node.name))
        # helper functions drawn from a panel (e.g. _draw_joints from 4 Motion)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in panels:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                        helpers.setdefault(sub.func.id, panels[node.name])
        helpers.update(OTHER_FILE_HELPERS.get(rel, {}))
        # ... and the helpers those call (e.g. _draw_coupling from _draw_joints), to any depth
        funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        todo = [n for n in helpers if n in funcs]
        while todo:
            name = todo.pop()
            for sub in ast.walk(funcs[name]):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in funcs
                        and sub.func.id not in helpers):
                    helpers[sub.func.id] = helpers[name]
                    todo.append(sub.func.id)
        sc = _Scan(rel, panels, helpers)
        sc.visit(tree)
        items += sc.items
    # list rows: name them after the list
    return items


# ---------------------------------------------------------------------------
# 2. the tooltip texts (registered extension)
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


# Texts Blender shows when the code gives none (meant for programmers, not for users).
BLENDER_DEFAULTS = {
    "(undocumented operator)": "Blender's 'undocumented operator'",
    "Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed":
        "Blender's default text for a name field (meant for programmers)",
}


def judge(label: str, name: str, text: str) -> tuple[str, str]:
    t = (text or "").strip()
    if not t:
        return "missing", "no tooltip"
    if t in BLENDER_DEFAULTS:
        return "missing", BLENDER_DEFAULTS[t]
    words = len(re.findall(r"[A-Za-z0-9]+", t))
    if _norm(t) in (_norm(label), _norm(name)) or _norm(t).startswith(_norm(label) + " ") and words <= 4:
        return "weak", "repeats the label"
    if words < 5:
        return "weak", f"only {words} words"
    return "ok", ""


_STRUCTS: dict = {}


def _walk_structs(rna) -> None:
    """All property groups reachable from scene.fresing (registered PropertyGroups are not in bpy.types)."""
    if rna is None or rna.identifier in _STRUCTS:
        return
    _STRUCTS[rna.identifier] = rna
    for p in rna.properties:
        if p.type in ("POINTER", "COLLECTION") and p.fixed_type is not None and p.fixed_type.identifier.startswith("FR"):
            _walk_structs(p.fixed_type)


def _struct(name: str):
    import bpy
    if name in _STRUCTS:
        return _STRUCTS[name]
    t = getattr(bpy.types, name, None)
    return t.bl_rna if t is not None else None


def fill_tooltips(items: list[Item]) -> None:
    import bpy
    import addon_utils
    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    _STRUCTS.clear()            # the types of an earlier registration are gone (a second check in one run)
    try:
        _walk_structs(bpy.types.Scene.bl_rna.properties["fresing"].fixed_type)
        _walk_structs(bpy.types.Scene.bl_rna.properties["fresing_decal"].fixed_type)    # decals (task 0024)
        _walk_structs(bpy.types.Mesh.bl_rna.properties["fresing_decals"].fixed_type)
        prop_types = dict(_STRUCTS)
        for it in items:
            if it.kind == "button":
                _fill_button(it)
            else:
                _fill_setting(it, prop_types)
    finally:
        fresing_render.unregister()


def _fill_button(it: Item) -> None:
    import bpy
    mod, _, op = it.ident.partition(".")
    cls = getattr(bpy.types, f"{mod.upper()}_OT_{op}", None)
    if cls is None:
        it.verdict, it.why = "missing", "operator not found"
        return
    rna = getattr(getattr(bpy.ops, mod), op).get_rna_type()     # the operator type (name, description)
    text = rna.description or ""
    vals = {k: v for k, v in it.props.items() if not k.startswith("__")}
    if hasattr(cls, "description") and callable(getattr(cls, "description", None)):
        class _P:          # stands in for the button's properties
            def __getattr__(self, k):
                if k in vals:
                    return vals[k]
                p = rna.properties.get(k)
                return getattr(p, "default", None) if p is not None else None
        try:
            text = cls.description(bpy.context, _P()) or text
        except Exception as exc:  # report it rather than stop the whole check
            text = text or f"(description() failed: {exc})"
    menu = it.props.get("__menu__")
    if menu:
        it.why = f"menu of '{menu}'"
    it.tooltip = text.strip()
    label = it.label if not it.label.startswith("[icon") else ""
    v, why = judge(label, rna.name, it.tooltip)
    if v == "ok" and it.label.startswith("[icon") and len(re.findall(r"\w+", it.tooltip)) < 7:
        v, why = "weak", "icon-only button: the tooltip is all there is"
    it.verdict, it.why = v, "; ".join(x for x in (it.why, why) if x)
    if vals:
        it.ident += " (" + ", ".join(f"{k}={v}" for k, v in vals.items()) + ")"


def _fill_setting(it: Item, prop_types: dict) -> None:
    owner, pname = it.props["__owner__"], it.props["__prop__"]
    if pname.startswith("[") or pname.startswith("f'") or pname.startswith('f"'):
        # a joint's value slider: a custom property with its own description (joints.apply_limits;
        # the text depends on the joint: rotate, slide, motor or following another joint)
        it.ident = f"{owner}[joint value]"
        it.tooltip = "Angle of the joint, in degrees (0 = CAD position). Drag it, or type a number"
        it.verdict, it.why = judge(it.label, "value", it.tooltip)
        return
    tname = OWNER_TYPES.get(owner)
    if owner == "item":
        tname = ITEM_TYPES.get(it.panel.replace("list ", ""), None)
        if tname is None and it.panel == "Logos & stickers":
            tname = "FRDecal"
    rna = _struct(tname) if tname else None
    if rna is None or pname not in rna.properties:
        hits = [n for n, r in prop_types.items() if pname in r.properties]
        if len(hits) == 1:
            tname, rna = hits[0], prop_types[hits[0]]
    if rna is None or pname not in rna.properties:
        it.verdict, it.why = "missing", f"could not find {owner}.{pname}"
        return
    # a property group that defines its own `name` has two: Blender's and its own; the UI shows its own
    p = [q for q in rna.properties if q.identifier == pname][-1]
    it.ident = f"{tname}.{pname}"
    it.tooltip = (p.description or "").strip()
    label = it.label if it.label not in ("", "(label from setting)") else p.name
    if it.label == "":
        label = ""                         # a field with no label (e.g. the search box)
    v, why = judge(label, p.name, it.tooltip)
    if v == "ok" and it.label == "" and len(re.findall(r"\w+", it.tooltip)) < 7:
        v, why = "weak", "field without a label: the tooltip is all there is"
    it.verdict, it.why = v, why
    if p.type == "ENUM" and it.props.get("__expand__"):
        it.kind = "setting (row of choices)"
        weak = []
        for e in p.enum_items:
            if not e.description.strip() or _norm(e.description) == _norm(e.name):
                weak.append(e.name)
        if weak:
            it.why = "; ".join(x for x in (it.why, "choices without explanation: " + ", ".join(weak)) if x)
            if it.verdict == "ok":
                it.verdict = "weak"


# ---------------------------------------------------------------------------
# 3. report
# ---------------------------------------------------------------------------


def _md(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def report(items: list[Item], show_all: bool) -> str:
    out = []
    order = ["missing", "weak", "ok"]
    n = {v: sum(1 for i in items if i.verdict == v) for v in order}
    out.append(f"Buttons and settings found: {len(items)} · missing {n['missing']} · weak {n['weak']} · "
               f"ok {n['ok']}")
    panels = []
    for it in items:
        if it.panel not in panels:
            panels.append(it.panel)
    for panel in panels:
        rows = [i for i in items if i.panel == panel and (show_all or i.verdict != "ok")]
        if not rows:
            continue
        lane = LANE_OF_PANEL.get(panel, "")
        out.append("")
        out.append(f"### {panel}" + (f" ({lane})" if lane else ""))
        out.append("")
        out.append("| Verdict | On screen | Tooltip now | Why | Code |")
        out.append("| --- | --- | --- | --- | --- |")
        for i in sorted(rows, key=lambda i: order.index(i.verdict)):
            out.append(f"| {i.verdict} | {_md(i.label)} | {_md(i.tooltip) or '–'} | {_md(i.why)} | "
                       f"`{_md(i.ident)}` {i.line} |")
    return "\n".join(out) + "\n"


def collect() -> list[Item]:
    items = scan_ui()
    fill_tooltips(items)
    # list rows: show them under the panel that holds the list
    holder = {"FRESING_UL_tree": "2 Structure", "FRESING_UL_visibility": "Visibility sets",
              "FRESING_UL_groups": "3 Looks", "FRESING_UL_rules": "Sorting rules",
              "FRESING_UL_schemes": "Paint schemes & templates", "FRESING_UL_found": "Find & sort parts",
              "FRESING_UL_joints": "4 Motion", "FRESING_UL_poses": "Poses & exploded views",
              "FRESING_UL_shots": "Saved scenes", "FRESING_UL_anims": "6 Animation",
              "FRESING_UL_blocks": "6 Animation", "FRESING_UL_queue": "7 Render queue",
              "FRESING_UL_mill_bits": "Milling", "FRESING_UL_cylinders": "Cylinders",
              "FRESING_UL_mechanisms": "Mechanisms", "FRESING_UL_cnc_tools": "CNC machine",
              "FRESING_UL_cnc_pockets": "Tool changes"}
    for it in items:
        if it.panel.startswith("list "):
            cls = it.panel[5:]
            it.panel = holder.get(cls, it.panel)
            it.label = f"{it.label} (in each list row)"
    same_text_on_different_buttons(items)
    return items


def same_text_on_different_buttons(items: list[Item]) -> None:
    """One tooltip on buttons that do different things (Add / Remove / Select, Stop / Stop now) cannot tell
    the user which is which: the operator needs a description() per variant."""
    by_text: dict[tuple, list[Item]] = {}
    for it in items:
        if it.kind == "button" and it.tooltip and it.verdict == "ok":
            op = it.ident.split(" ")[0]
            by_text.setdefault((op, it.tooltip), []).append(it)
    for (_op, _t), group in by_text.items():
        variants = {i.ident for i in group}
        labels = {i.label for i in group}
        if len(variants) > 1 and len(labels) > 1:
            for it in group:
                others = sorted(lab for lab in labels if lab != it.label)
                it.verdict = "weak"
                it.why = "; ".join(x for x in (it.why, "same text as " + ", ".join(others)) if x)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="also list the tooltips that look fine")
    ap.add_argument("--markdown", help="write the report to this Markdown file")
    ap.add_argument("--strict", action="store_true", help="exit code 1 when any tooltip is missing")
    args = ap.parse_args(argv)
    items = collect()
    text = report(items, args.all)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(text)
        print(text.splitlines()[0])
        print("written to", args.markdown)
    else:
        print(text)
    return 1 if args.strict and any(i.verdict == "missing" for i in items) else 0


if __name__ == "__main__":
    sys.exit(main())
