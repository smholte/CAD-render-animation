"""Task 0139: mesh import fixes from bug hunt 0131 (rows 3, 4, 13, 15, 16b–e). Each test is the row's proof."""

import math
import os
import shutil
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
import make_test_mesh as maker  # noqa: E402
from fresing_render.blender import build, hover, joints, mesh_import  # noqa: E402
from fresing_render.importer import mesh_reader, runner  # noqa: E402

DATA = os.path.join(HERE, "data")
CRANE = os.path.join(DATA, "test_mesh_crane.glb")
OBJ_FILES = ("test_mesh_parts.obj", "test_mesh_parts.mtl", "test_mesh_tile.png")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(tmp_path, path, **kw):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_mesh(filepath=str(path), **kw) == {"FINISHED"}
    bpy.context.view_layer.update()
    return sc


def update(sc, path):
    t = os.path.getmtime(path) + 5
    os.utime(path, (t, t))
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_mesh(filepath=str(path), update_root=root.name) == {"FINISHED"}
    bpy.context.view_layer.update()


def parts(sc):
    return [o for o in sc.objects if o.get(build.PROP_KIND) == "part"]


def centre(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return sum(pts, Vector()) / 8


def part_at(sc, x, y):
    return min(parts(sc), key=lambda o: (centre(o).xy - Vector((x, y))).length)


# ---- row 3: names the reader made match by shape and place -----------------------------------------------------

def weldment(blocks=(-0.4, -0.15, 0.1), big_first=False) -> bytes:
    """One mesh of loose pieces (the reader names them "WELDMENT 1" … by size): plate, shaft, blocks."""
    g = maker.Gltf()
    grey = g.material("Machined", (0.6, 0.6, 0.62), metallic=1.0, rough=0.3)
    s = maker.Shape()
    pieces = []
    if big_first:
        big = maker.Shape()
        big.box((-0.6, 0.6, 0.0), (0.8, 1.2, 0.08))       # bigger than the plate: it becomes piece 1
        pieces.append(big)
    plate = maker.Shape()
    plate.box((-0.6, -0.4, 0.0), (0.6, 0.4, 0.05))
    pieces.append(plate)
    shaft = maker.Shape()
    shaft.cylinder(0.04, 0.05, 0.45, 16)
    pieces.append(shaft.moved(maker.move(0.3, 0.1, 0.0)))
    for x in blocks:
        b = maker.Shape()
        b.box((x, -0.3, 0.05), (x + 0.1, -0.2, 0.15))
        pieces.append(b)
    for piece in pieces:
        k = len(s.p)
        s.p += piece.p
        s.n += piece.n
        s.uv += piece.uv
        s.t += [(a + k, b + k, c + k) for a, b, c in piece.t]
    g.node("WELDMENT", g.mesh("Weldment", [(s, grey)], normals=False))
    return g.glb()


def _set_up_weldment(tmp_path):
    src = tmp_path / "weldment.glb"
    src.write_bytes(weldment())
    sc = fresh(tmp_path, src)
    assert all(o.get(build.PROP_MADE_NAME) for o in parts(sc))
    shaft, plate, block = part_at(sc, 0.3, 0.1), part_at(sc, 0.0, 0.0), part_at(sc, 0.15, -0.25)
    assert len(shaft.data.polygons) > 12 and len(plate.data.polygons) == 12
    block["fr_group_manual"] = "Block look"
    joints.create(sc, "ROTATE", [shaft], Vector((0.3, 0.1, 0.0)), Vector((0, 0, 1)), name="Shaft turn", base=plate)
    return sc, src


def test_a_removed_piece_keeps_the_work_on_the_other_pieces(tmp_path):
    sc, src = _set_up_weldment(tmp_path)
    src.write_bytes(weldment(blocks=(-0.15, 0.1)))            # the block at x -0.4 is gone: the numbers shift
    update(sc, src)
    s = sc.fresing
    assert len(s.report_missing) == 1 and len(s.report_new) == 0
    block = part_at(sc, 0.15, -0.25)
    assert block.get("fr_group_manual") == "Block look"
    assert sum(1 for o in parts(sc) if o.get("fr_group_manual")) == 1
    members = joints.members(joints.find(sc, "Shaft turn"))
    assert [centre(m).xy.to_tuple(2) for m in members] == [(0.3, 0.1)]


def test_a_piece_added_first_keeps_the_joint_on_the_shaft(tmp_path):
    sc, src = _set_up_weldment(tmp_path)
    src.write_bytes(weldment(big_first=True))
    update(sc, src)
    s = sc.fresing
    assert len(s.report_missing) == 0 and len(s.report_new) == 1
    assert not any("is now called" in n.text for n in s.report_notes)   # a new piece number is no rename
    members = joints.members(joints.find(sc, "Shaft turn"))
    assert len(members) == 1 and len(members[0].data.polygons) > 12
    assert centre(members[0]).xy.to_tuple(2) == (0.3, 0.1)
    assert part_at(sc, 0.15, -0.25).get("fr_group_manual") == "Block look"


def test_match_a_made_name_needs_the_same_place():
    from fresing_render.blender import reimport
    o = {"kind": "part", "key_a": None, "key_b": ("w", "w 2"), "leaf": "w 2", "pos": Vector((0, 0, 0)), "made": True}
    n = dict(o, pos=Vector((1, 0, 0)))
    assert reimport.match([o], [n]) == []
    assert len(reimport.match([dict(o, made=False)], [dict(n, made=False)])) == 1     # a file's own name: as before


# ---- row 4: a file material no part shows is kept at save --------------------------------------------------------

def test_a_file_material_no_part_shows_survives_save(tmp_path):
    sc = fresh(tmp_path, CRANE)
    boom = next(o for o in parts(sc) if o.get(build.PROP_NAME) == "BOOM")
    g = sc.fresing.groups[boom[build.PROP_GROUP]]
    g.material = "paint_gloss"
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    boom = next(o for o in parts(sc) if o.get(build.PROP_NAME) == "BOOM")
    assert mesh_import.file_material(boom) is not None
    sc.fresing.groups[boom[build.PROP_GROUP]].material = mesh_import.FROM_FILE
    assert boom.material_slots[0].material.name.startswith(mesh_import.MAT_PREFIX)


def test_an_update_lets_the_old_file_materials_go(tmp_path):
    src = tmp_path / "crane.glb"
    shutil.copy(CRANE, src)
    sc = fresh(tmp_path, src)
    count = sum(1 for m in bpy.data.materials if m.get("fr_file_material"))
    update(sc, src)
    update(sc, src)
    mats = [m for m in bpy.data.materials if m.get("fr_file_material")]
    assert len(mats) == count
    named = {me.get(mesh_import.PROP_FILE_MATERIAL) for me in bpy.data.meshes}
    assert {m.name for m in mats} <= named


# ---- row 13: the cache notices MTL / texture / .bin changes ------------------------------------------------------

def run_job(job, timeout=120):
    job.start()
    t0 = time.time()
    while not job.poll():
        time.sleep(0.05)
        assert time.time() - t0 < timeout
    return job


def test_a_changed_mtl_or_texture_reads_the_model_again(tmp_path):
    folder = tmp_path / "model"
    folder.mkdir()
    for name in OBJ_FILES:
        shutil.copy(os.path.join(DATA, name), folder / name)
    obj = str(folder / OBJ_FILES[0])
    job = run_job(runner.ImportJob(obj, "normal", str(tmp_path / "cache"), {"units": "mm", "up": "y", "split": "auto"}))
    assert job.error is None and runner.cache_is_valid(job.cache_dir)
    mtl = folder / OBJ_FILES[1]
    mtl.write_text(mtl.read_text().replace("Kd 0.05 0.2 0.6", "Kd 1 0 0"))
    assert not runner.cache_is_valid(job.cache_dir)
    again = run_job(runner.ImportJob(obj, "normal", str(tmp_path / "cache"),
                                     {"units": "mm", "up": "y", "split": "auto"}))
    assert again.error is None and runner.cache_is_valid(again.cache_dir)
    import json
    with open(os.path.join(again.cache_dir, "tree.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    blue = next(m for m in info["materials"] if m["name"] == "Blue")
    assert blue["color"][0] > 0.9 and blue["color"][2] < 0.01
    png = folder / OBJ_FILES[2]
    png.write_bytes(png.read_bytes() + b"\0")
    assert not runner.cache_is_valid(again.cache_dir)


def test_a_gltf_bin_file_is_a_side_file(tmp_path):
    g = maker.Gltf()
    box = maker.Shape()
    box.box((0, 0, 0), (1, 1, 1))
    g.node("BOX", g.mesh("Box", [(box, g.material("Grey", (0.5, 0.5, 0.5)))]))
    g.doc["buffers"][0]["byteLength"] = len(g.bin)
    g.doc["buffers"][0]["uri"] = "box data.bin"
    (tmp_path / "box data.bin").write_bytes(bytes(g.bin))
    import json
    (tmp_path / "box.gltf").write_text(json.dumps(g.doc))
    info = mesh_reader.read_mesh(str(tmp_path / "box.gltf"), str(tmp_path / "c"))
    assert [os.path.basename(r[0]) for r in info["side_files"]] == ["box data.bin"]
    assert not runner.side_files_changed(info)
    (tmp_path / "box data.bin").write_bytes(bytes(g.bin) + b"\0\0\0\0")
    assert runner.side_files_changed(info)


# ---- row 15: a big mesh model update is not quadratic ---------------------------------------------------------

def boxes(n: int, z: float = 0.0) -> bytes:
    g = maker.Gltf()
    grey = g.material("Grey", (0.5, 0.5, 0.5))
    root = g.node("BOXES")
    side = int(math.ceil(math.sqrt(n)))
    for k in range(n):
        b = maker.Shape()
        x, y = (k % side) * 0.2, (k // side) * 0.2
        b.box((x, y, z), (x + 0.1 + k * 1e-5, y + 0.1, z + 0.1))     # every box its own mesh (mesh files rarely share)
        g.node(f"Box {k}", g.mesh(f"Box {k}", [(b, grey)]), parent=root)
    return g.glb()


def test_update_of_1500_mesh_parts_is_quick(tmp_path):
    src = tmp_path / "boxes.glb"
    src.write_bytes(boxes(1500))
    t0 = time.time()
    sc = fresh(tmp_path, src)
    t_import = time.time() - t0
    t0 = time.time()
    update(sc, src)
    t_update = time.time() - t0
    print(f"1500 parts: import {t_import:.1f} s, update {t_update:.1f} s")
    assert sc.fresing.report_title.startswith("Model updated: 1,500 parts kept") or \
        sc.fresing.report_title.startswith("Model updated: 1500 parts kept")
    assert t_update < 2.0 * t_import + 2.0


# ---- row 16b: the radius of a part stretched along its axis -----------------------------------------------------

def test_a_rod_stretched_along_its_axis_shows_its_own_diameter(tmp_path):
    g = maker.Gltf()
    rod = maker.Shape()
    rod.cylinder(0.05, -0.1, 0.1, 32)
    rod = rod.moved(maker.rot_y(90))                          # its axis along its own X …
    g.node("ROD", g.mesh("Rod", [(rod, g.material("Steel", (0.6, 0.6, 0.6)))]),
           matrix=np.diag((3.0, 1.0, 1.0, 1.0)))              # … stretched along it: 0.6 m long, still Ø100
    src = tmp_path / "rod.glb"
    src.write_bytes(g.glb())
    sc = fresh(tmp_path, src)
    ob = parts(sc)[0]
    origin, direction = Vector((0.0, 0.0, 0.2)), Vector((0.0, 0.0, -1.0))
    hit_ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), origin, direction)
    assert hit_ob == ob and index >= 0
    _o, d, desc = joints.axis_from_hit(ob, index, loc, normal)
    assert abs(abs(d.x) - 1.0) < 1e-3
    assert desc == "round face Ø100.0 mm", desc


# ---- row 16c: the hover's cache is not keyed by the mesh's name ----------------------------------------------------

def test_hover_reads_a_new_mesh_with_an_old_name(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    hover.clear()

    def make(scale):
        me = bpy.data.meshes.new("Part")
        me.from_pydata([(0, 0, 0), (scale, 0, 0), (0, scale, 0)], [], [(0, 1, 2)])
        return me

    a = make(1.0)
    assert hover._mesh(a)[3][1][0] == pytest.approx(1.0)
    bpy.data.meshes.remove(a)
    b = make(0.001)
    assert b.name == "Part"
    assert hover._mesh(b)[3][1][0] == pytest.approx(0.001)
    assert hover.face_shape(b, 0)[0].max() == pytest.approx(0.001)


# ---- row 16d: OBJ / MTL written by older Windows programs (cp1252) -----------------------------------------------

def test_a_cp1252_obj_and_mtl_keep_their_names(tmp_path):
    (tmp_path / "plåt.mtl").write_bytes("newmtl Stål\nKd 1 1 1\nmap_Kd stål.png\n".encode("cp1252"))
    (tmp_path / "stål.png").write_bytes(maker.checker(8, 2))
    obj = ("mtllib plåt.mtl\no Plåt\nusemtl Stål\nv 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\n"
           "f 1/1 2/2 3/3\n")
    (tmp_path / "plåt.obj").write_bytes(obj.encode("cp1252"))
    info = mesh_reader.read_mesh(str(tmp_path / "plåt.obj"), str(tmp_path / "c"), units="m")
    assert [n["name"] for n in info["nodes"] if n["kind"] == "part"] == ["Plåt"]
    assert info["materials"][0]["name"] == "Stål" and info["materials"][0].get("base_texture")
    assert not any("missing" in n for n in info["notes"]), info["notes"]


# ---- row 16e: a glTF without "scene" ----------------------------------------------------------------------------

def test_a_gltf_without_a_default_scene_reads_the_first_scene_with_nodes(tmp_path):
    g = maker.Gltf()
    box = maker.Shape()
    box.box((0, 0, 0), (1, 1, 1))
    g.node("BOX", g.mesh("Box", [(box, g.material("Grey", (0.5, 0.5, 0.5)))]))
    g.doc["scenes"] = [{"nodes": []}, g.doc["scenes"][0]]
    del g.doc["scene"]
    (tmp_path / "two.glb").write_bytes(g.glb())
    info = mesh_reader.read_mesh(str(tmp_path / "two.glb"), str(tmp_path / "c"))
    assert [n["name"] for n in info["nodes"] if n["kind"] == "part"] == ["BOX"]


# ---- 0147 row 21b (task 0162): a file mostly UTF-8 with one cp1252 line ---------------------------------------------

def test_a_utf8_obj_with_one_cp1252_line_keeps_its_names(tmp_path):
    assert mesh_reader._decode("o Plåt\n".encode() + "# från\n".encode("cp1252") + "usemtl Stål".encode()) == \
        "o Plåt\n# från\nusemtl Stål"
    assert mesh_reader._decode("o Plåt".encode()[:-1] + b"") == "o Plå"     # (plain UTF-8 untouched)
    assert mesh_reader._decode("# a\no Pl".encode() + "å".encode()[:1], cut=True) == "# a\no Pl"   # a read cut in a letter
    obj = ("# Exported by Ritprogrammet för Windows\n".encode("cp1252")
           + "o Plåt\nv 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n".encode())
    (tmp_path / "mixed.obj").write_bytes(obj)
    info = mesh_reader.read_mesh(str(tmp_path / "mixed.obj"), str(tmp_path / "c"), units="m")
    assert [n["name"] for n in info["nodes"] if n["kind"] == "part"] == ["Plåt"]


# ---- 0147 row 3 (task 0162): unnamed groups ("Node k") all at the model's origin ---------------------------------------

def unnamed_groups(groups=("A", "B", "C")) -> bytes:
    """Unnamed group nodes at the origin (the reader names them "Node k"), each with two named boxes of its own."""
    g = maker.Gltf()
    grey = g.material("Grey", (0.5, 0.5, 0.5))
    x0 = {"A": -1.0, "B": 0.0, "C": 1.0}
    for name in groups:
        grp = g.node("")
        for k in (1, 2):
            s = maker.Shape()
            x = x0[name] + 0.3 * k
            s.box((x, 0.0, 0.0), (x + 0.2, 0.2 + 0.05 * k, 0.2))
            g.node(f"{name}{k}", g.mesh(f"{name}{k}", [(s, grey)]), parent=grp)
    return g.glb()


def test_unnamed_groups_keep_their_work_when_one_is_removed(tmp_path):
    from fresing_render.blender import logic, states
    src = tmp_path / "groups.glb"
    src.write_bytes(unnamed_groups())
    sc = fresh(tmp_path, src)

    def group_of(part_name):
        p = next(o for o in parts(sc) if o.get(build.PROP_NAME) == part_name)
        return build.logical_parent(p)

    b = group_of("B1")
    assert b.get(build.PROP_MADE_NAME) and b == group_of("B2")
    logic.set_hidden(b, True)
    a = sc.fresing.animations.add()
    step = a.blocks.add()
    step.kind, step.target_uid, step.target_name = "HIDE", b[build.PROP_UID], b[build.PROP_NAME]
    src.write_bytes(unnamed_groups(("B", "C")))              # A is gone: "Node 2" is now "Node 1"
    update(sc, src)
    b = group_of("B1")
    assert b == group_of("B2")
    tgt = states.by_uid(sc).get(step.target_uid)
    assert tgt == b, (tgt and tgt.get(build.PROP_NAME), b.get(build.PROP_NAME))
    assert logic.is_hidden(b) and not logic.is_hidden(group_of("C1"))
    src.write_bytes(unnamed_groups())                        # A back in front: the numbers shift the other way
    update(sc, src)
    b = group_of("B1")
    assert states.by_uid(sc).get(step.target_uid) == b == group_of("B2")
    assert logic.is_hidden(b) and not logic.is_hidden(group_of("A1")) and not logic.is_hidden(group_of("C1"))
