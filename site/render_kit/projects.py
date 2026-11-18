"""Fresing Render – the moving models of the web page as app projects (task 0112).

A *sheet* (``projects/<model>.json``, written by ``tools/make_site_projects.py`` from the model's own source files)
says which sub-assemblies turn or slide about which axis, which joints follow others and by how much, where the
cylinders' pins are, the named poses and the animation. ``make(pkg, scene, sheet)`` does on an imported model what a
user does with the buttons, through the app's own functions: joints (4 Motion > Joints, ``joints.create`` in one
batch), couplings (``joints.set_follows``), cylinders (``cylinders.create``), poses (``states.save_pose``), the
animation of "Go to pose" steps (6 Animation), Build (``animation.bake``) and the clash check (``clash.check``).

Sheet coordinates are the STEP file's, in mm; the model root's matrix takes them into the scene (the importer's up
axis and units). Parts are found by their CAD name (sub-assembly names in the sheet are unique in the model).

Task 0116 (the wind turbine) adds to a sheet: ``scene`` (the sea's water level, the floor), ``decals`` (texts and
signs on parts, 3 Looks > Decals), ``cameras`` (named cameras: a saved scene each, models.ini ``views`` may name them),
an animation ``camera``, JOINT steps that run side by side (constant speed: easing LINEAR), ``periods`` (a joint
whose value may differ by whole periods between the loop's ends: the rotor of a three-bladed turbine, 120°) and a
``check_animation`` that only the clash check of ``tools/make_site_projects.py --project`` builds.

Since task 0201 the reader itself is part of the app (``fresing_render/blender/sheet.py``: the Lifting plan rigs
its cranes with it); this file keeps the kit's names and hands every call on to the installed app's copy.

Used by the render kit (``make_site_pictures.py``, models.ini ``project = <model>``) on the owner's PC, by
``tools/make_site_projects.py`` and by the tests (Blender as a Python module).
"""

from __future__ import annotations

import importlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(HERE, "projects")


def sheet_path(model: str) -> str:
    return os.path.join(SHEETS, f"{model}.json")


def load(model_or_path: str) -> dict:
    path = model_or_path if model_or_path.endswith(".json") else sheet_path(model_or_path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _sheet(pkg):
    """The app's sheet reader (0.2.156 and newer)."""
    try:
        return importlib.import_module(f"{pkg.__name__}.blender.sheet")
    except ImportError as exc:
        raise RuntimeError("This render kit needs Fresing Render 0.2.156 or newer: update the app "
                           "(Help > Check for updates)") from exc


def Model(pkg, scene, sheet: dict, root=None, prefix: str = ""):  # noqa: N802 - the kit's old class name
    return _sheet(pkg).Model(scene, sheet, root=root, prefix=prefix)


def animation_item(scene, sheet: dict):
    a = sheet.get("animation") or {}
    return scene.fresing.animations.get(a.get("name", "")) if a else None


def _hand_on(name):
    def call(pkg, scene, *args, **kw):
        return getattr(_sheet(pkg), name)(scene, *args, **kw)
    call.__name__ = name
    call.__doc__ = f"``fresing_render.blender.sheet.{name}`` of the installed app."
    return call


for _name in ("hide_parts", "make_joints", "make_cylinders", "set_values", "make_poses",
              "make_animation", "frame_all_poses", "build_animation", "axis_errors", "loop_gap", "clash_rows",
              "apply_scene", "sheet_camera", "make_cameras", "make_decals", "check_extra", "make"):
    globals()[_name] = _hand_on(_name)
