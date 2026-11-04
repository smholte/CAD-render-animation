"""Rule sets in a project (3 Looks): which one the project uses, its copy, switching and saving.

The project keeps
* ``scene.fresing.rule_set``: the name of the rule set it uses;
* ``scene.fresing.rule_set_data``: that rule set as it was last loaded or saved (JSON) – the
  project's own copy, so the project opens without the library;
* the working state in the usual places: rules (``s.rules``), group renames (``s.group_aliases``)
  and the looks of the groups (``s.groups``).

"Changed" = the working state differs from the saved copy (``current`` vs ``saved``). The look
of a group belongs to the rule set when the rules fill it (``group.by_rules``); a group that only
holds parts put in by hand belongs to the project.

Files: ``<shared library>/Rule sets/*.json``; without a shared library a folder on this PC
(Documents\\Fresing Render\\Rule sets).
"""

from __future__ import annotations

import os
import sys
import time

import bpy

from ..core import rule_sets as RS
from ..core import rules as R
from . import build, logic

ENV_FOLDER = "FRESING_RULE_SETS_DIR"         # tests: use this folder instead of the library
SCAN_SECONDS = 15.0                          # a network folder is read at most this often while drawing

# ---------------------------------------------------------------------------
# where the files are
# ---------------------------------------------------------------------------


def documents_dir() -> str:
    """The user's Documents folder (on Windows asked from the system: OneDrive may have moved it)."""
    if sys.platform == "win32":
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]

            u = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")      # FOLDERID_Documents
            guid = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            path = ctypes.c_wchar_p()
            shell32 = ctypes.WinDLL("shell32")
            shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
                                                     ctypes.POINTER(ctypes.c_wchar_p)]
            shell32.SHGetKnownFolderPath.restype = ctypes.c_long
            if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path)) == 0 and path.value:
                result = path.value
                ctypes.windll.ole32.CoTaskMemFree(path)
                if os.path.isdir(result):
                    return result
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def folder() -> tuple[str, bool, str]:
    """(folder, shared, problem): the "Rule sets" folder, whether it is in the shared library, and
    why it cannot be used right now ('' = fine)."""
    override = os.environ.get(ENV_FOLDER)
    if override:
        return override, True, ""
    from . import prefs
    p = prefs.get()
    lib = bpy.path.abspath(p.library_path) if p is not None and p.library_path else ""
    if lib:
        path = os.path.join(lib, RS.FOLDER)
        if not os.path.isdir(lib):
            return path, True, f"The shared library cannot be reached ({lib})"
        return path, True, ""
    return os.path.join(documents_dir(), "Fresing Render", RS.FOLDER), False, ""


_SCAN: dict = {"key": None, "time": 0.0, "found": {}}


def library(force: bool = False) -> dict[str, tuple[str, RS.RuleSet]]:
    """{name: (file, rule set)} in the rule-set folder (read again at most every few seconds)."""
    path, _shared, problem = folder()
    if problem:
        return {}
    now = time.monotonic()
    if force or _SCAN["key"] != path or now - _SCAN["time"] > SCAN_SECONDS:
        _SCAN.update(key=path, time=now, found=RS.scan(path))
    return _SCAN["found"]


def forget_scan() -> None:
    _SCAN["key"] = None


def find(name: str) -> RS.RuleSet | None:
    """A fresh copy of a rule set by name: the built-in Standard or one from the library."""
    if name == RS.STANDARD:
        return RS.standard()
    hit = library().get(name)
    return hit[1].copy() if hit else None


def default_name() -> str:
    """The rule set new projects start with (add-on preferences)."""
    from . import prefs
    p = prefs.get()
    return (getattr(p, "default_rule_set", "") or RS.STANDARD) if p is not None else RS.STANDARD


# ---------------------------------------------------------------------------
# the project's copy
# ---------------------------------------------------------------------------

_PARSED: dict[str, RS.RuleSet] = {}


def saved(s) -> RS.RuleSet | None:
    """The project's rule set as it was last loaded or saved (None for a project before 0.2.10)."""
    text = s.rule_set_data
    if not text:
        return None
    rs = _PARSED.get(text)
    if rs is None:
        try:
            rs = RS.RuleSet.from_json(text)
        except (ValueError, TypeError):
            rs = RS.RuleSet(s.rule_set or RS.FROM_PROJECT)
        if len(_PARSED) > 8:
            _PARSED.clear()
        _PARSED[text] = rs
    return rs


def saved_looks(s) -> dict[str, tuple[str, str]]:
    rs = saved(s)
    return rs.looks if rs is not None else {}


def set_saved(s, rs: RS.RuleSet) -> None:
    s.rule_set = rs.name
    s.rule_set_data = rs.to_json()


def current(s) -> RS.RuleSet:
    """The project's rule set as it is now: its rules, its group renames and the looks of the
    groups the rules fill (on top of the looks of the saved copy)."""
    base = saved(s)
    looks = dict(base.looks) if base is not None else {}
    for g in s.groups:
        if g.by_rules:
            looks[g.name] = (g.material, g.color)
    return RS.RuleSet(name=s.rule_set or RS.FROM_PROJECT, rules=logic.rules_from_scene(s), looks=looks,
                      renames={a.source: a.target for a in s.group_aliases if a.source != a.target},
                      note=base.note if base is not None else "")


def differences(s) -> dict:
    base = saved(s)
    if base is None:
        return {"rules": 0, "looks": 0, "renames": 0}
    return RS.differences(base, current(s))


def is_changed(s) -> bool:
    return any(differences(s).values())


def kind(s) -> str:
    """'builtin' (Standard), 'library' (a file in the rule-set folder) or 'project' (only here)."""
    if s.rule_set == RS.STANDARD:
        return "builtin"
    return "library" if s.rule_set in library() else "project"


def library_differs(s) -> bool:
    """The library holds another version of this project's rule set than the one it was loaded from
    (a colleague saved changes)."""
    if kind(s) != "library":
        return False
    base = saved(s)
    hit = library().get(s.rule_set)
    return base is not None and hit is not None and not hit[1].same_content(base)


# ---------------------------------------------------------------------------
# choosing the rule set
# ---------------------------------------------------------------------------


def load_into(scene, rs: RS.RuleSet) -> None:
    """Make ``rs`` the project's rule set (rules, group renames, saved copy) without sorting."""
    s = scene.fresing
    logic.load_rules_into_scene(s, rs.rules)
    s.group_aliases.clear()
    for src, dst in rs.renames.items():
        if src and dst and src != dst:
            a = s.group_aliases.add()
            a.source, a.target = src, dst
    set_saved(s, rs)


_NOTICE = {"text": ""}


def take_notice() -> str:
    """A message for the user from the last ``ensure`` (shown after an import), once."""
    text, _NOTICE["text"] = _NOTICE["text"], ""
    return text


def ensure(scene) -> None:
    """Every project uses a rule set. A new project gets the default one (preferences; Standard if
    it is not in the library); a project made before rule sets keeps its rules, as a rule set of
    its own ("From this project", or "Standard" when they are the untouched defaults)."""
    s = scene.fresing
    if s.rule_set:
        return
    if len(s.rules) == 0:
        name = default_name()
        rs = find(name)
        if rs is None:
            rs = RS.standard()
            _NOTICE["text"] = s.last_message = f"Rule set '{name}' is not in the library: this project uses Standard"
        load_into(scene, rs)
        return
    adopt(scene)


def adopt(scene, name: str | None = None) -> RS.RuleSet:
    """Turn the project's own rules into its rule set, without changing how anything is sorted.
    ``name``: the name to give it (default "From this project"); the untouched defaults are Standard."""
    s = scene.fresing
    s.rule_set = ""
    logic.ensure_default_rules(s)               # untouched rules of before 0.2.8 -> the new defaults
    rules = logic.rules_from_scene(s)
    renames = {a.source: a.target for a in s.group_aliases if a.source != a.target}
    by_rules = logic.sort_plan(scene, rules, renames)["by_rules"]
    looks = {}
    for g in s.groups:
        if g.by_rules != (g.name in by_rules):
            g.by_rules = g.name in by_rules
        if g.by_rules:
            looks[g.name] = (g.material, g.color)
    rs = RS.RuleSet(name or RS.FROM_PROJECT, rules, looks, renames)
    if rs.same_content(RS.standard()):
        rs = RS.standard()
    set_saved(s, rs)
    return rs


def on_load(scene) -> bool:
    """A project opened: one made before rule sets gets its rule set. True if its rules were the
    untouched defaults of before 0.2.8 and became the new defaults."""
    s = scene.fresing
    if s.rule_set:
        return False
    upgraded = logic.ensure_default_rules(s)
    adopt(scene)
    return upgraded


def _target_look(g, rs: RS.RuleSet, by_rules: bool):
    """The look group ``g`` gets from rule set ``rs`` (None: it keeps its own)."""
    if g.name in rs.looks:
        return rs.looks[g.name]
    if by_rules:
        return R.default_material_for_group(g.name)
    return None                                 # only parts put in by hand: the project's own group


def preview(scene, rs: RS.RuleSet) -> dict:
    """What switching to ``rs`` would change, without changing anything."""
    s = scene.fresing
    plan = logic.sort_plan(scene, rs.rules, {k: v for k, v in rs.renames.items() if k != v})
    parts = plan["parts"]
    moved = sum(1 for ob, g in zip(parts, plan["groups"]) if ob.get(build.PROP_GROUP) != g)
    by_hand = sum(1 for ob in parts if ob.get("fr_group_manual"))
    after = set(plan["per_group"]) | set(plan["per_face_group"])
    now = {g.name for g in s.groups}
    looks = 0
    for g in s.groups:
        if g.name in after:
            target = _target_look(g, rs, g.name in plan["by_rules"])
            if target is not None and RS.look_key(*target) != RS.look_key(g.material, g.color):
                looks += 1
    faces_moved = 0
    from . import faces
    for ob in parts:
        new = plan["face_groups"].get(ob.name)
        if new:
            old = faces.groups_on(ob)
            faces_moved += sum(1 for k, g in enumerate(new) if k >= len(old) or old[k] != g)
    return {"name": rs.name, "parts": len(parts), "moved": moved, "by_hand": by_hand,
            "added": sorted(after - now, key=str.casefold), "gone": sorted(now - after, key=str.casefold),
            "looks": looks, "faces_moved": faces_moved, "unsorted": plan["unmatched"],
            "unsorted_now": s.unmatched}


def describe_preview(p: dict) -> list[str]:
    """Lines for the confirm dialog: '312 parts change group', '4 new groups'..."""
    lines = []
    n = p["moved"]
    lines.append(f"{n} of {p['parts']} parts change group" if n else "No part changes group")
    if p["faces_moved"]:
        lines.append(f"{p['faces_moved']} painted face sets change group")
    if p["added"]:
        k = len(p["added"])
        lines.append(f"{k} new group{'s' if k != 1 else ''}: " + ", ".join(p["added"][:4])
                     + (" …" if k > 4 else ""))
    if p["gone"]:
        k = len(p["gone"])
        lines.append(f"{k} group{'s go' if k != 1 else ' goes'} away (no parts left): " + ", ".join(p["gone"][:4])
                     + (" …" if k > 4 else ""))
    if p["looks"]:
        lines.append(f"{p['looks']} group{'s get' if p['looks'] != 1 else ' gets'} another material or colour")
    if p["by_hand"]:
        lines.append(f"{p['by_hand']} parts you put in a group by hand stay there")
    lines.append(f"Unsorted: {p['unsorted_now']} now, {p['unsorted']} after")
    return lines


def switch(scene, rs: RS.RuleSet) -> dict:
    """Use rule set ``rs`` from now on: its rules, renames and group looks. Parts put in a group by
    hand stay there (and so do their groups); groups left without parts go away."""
    s = scene.fresing
    load_into(scene, rs)
    logic.apply_rules(scene)
    for g in s.groups:
        target = _target_look(g, rs, g.by_rules)
        if target is not None and RS.look_key(*target) != RS.look_key(g.material, g.color):
            mat, color = target
            if g.material != mat:
                g.material = mat
            if g.color != color:
                g.color = color
    active = s.groups[s.groups_index].name if 0 <= s.groups_index < len(s.groups) else ""
    for i in reversed(range(len(s.groups))):
        g = s.groups[i]
        if g.count == 0 and g.faces == 0:
            s.groups.remove(i)
    names = [g.name for g in s.groups]
    s.groups_index = names.index(active) if active in names else 0
    logic.refresh_group_materials(scene)
    return {"groups": len(s.groups), "unsorted": s.unmatched}


# ---------------------------------------------------------------------------
# saving to the library
# ---------------------------------------------------------------------------


def _writable_folder() -> str:
    path, _shared, problem = folder()
    if problem:
        raise OSError(problem)
    return path


def save_to_library(scene) -> str:
    """Save the project's rule set as it is now into its library file (not Standard)."""
    s = scene.fresing
    if s.rule_set == RS.STANDARD:
        raise ValueError("Standard is built in and cannot be changed: save it as a new rule set")
    rs = current(s)
    path = RS.save_in(_writable_folder(), rs)
    forget_scan()
    set_saved(s, rs)
    return path


def save_as(scene, name: str, note: str = "") -> str:
    """Save the project's rule set as it is now under a new name; the project uses it from now on."""
    s = scene.fresing
    name = RS.clean_name(name)
    problem = RS.name_problem(name, list(library(force=True)))
    if problem:
        raise ValueError(problem)
    rs = current(s)
    old = rs.name
    rs.name = name
    rs.note = note or (f"Based on '{old}'" if old else "")
    path = RS.save_in(_writable_folder(), rs)
    forget_scan()
    set_saved(s, rs)
    return path


def new_empty(name: str) -> RS.RuleSet:
    """Save an empty rule set (only "Unsorted") in the library and return it (not used yet)."""
    name = RS.clean_name(name)
    problem = RS.name_problem(name, list(library(force=True)))
    if problem:
        raise ValueError(problem)
    rs = RS.empty(name)
    rs.note = "Started empty"
    RS.save_in(_writable_folder(), rs)
    forget_scan()
    return rs


def rename(scene, old: str, new: str) -> str:
    """Rename a rule set in the library; this project follows if it uses it. Other projects keep
    their own copy under the old name."""
    s = scene.fresing
    new = RS.clean_name(new)
    if old == RS.STANDARD:
        raise ValueError("Standard is built in and cannot be renamed")
    if old in library(force=True):
        RS.rename_in(_writable_folder(), old, new)
        forget_scan()
    elif old != s.rule_set:
        raise FileNotFoundError(f"'{old}' is not in the library")
    else:
        problem = RS.name_problem(new, list(library()))
        if problem:
            raise ValueError(problem)
    if s.rule_set == old:
        base = (saved(s) or current(s)).copy(new)
        set_saved(s, base)
    return new


def delete(name: str) -> None:
    """Delete a rule set file from the library. Projects that use it keep their own copy."""
    RS.delete_in(_writable_folder(), name)
    forget_scan()
