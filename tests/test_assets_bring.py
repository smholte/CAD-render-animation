"""Task 0355: bring, keep, ask and update Fresing assets pack items in a project (``blender/assets.py``).

Blender as a Python module with the app registered and 0354's made-up test pack (1.0.0 and 1.1.0, written at test
time). A "client" is the saved file opened alone in another folder by a plain Blender in a process of its own, with the
pack hidden: nothing may be missing (no library links, every picture packed) and a small Cycles picture must be the
same as with the pack (no pink, no black). Also a backup opened from ``Backups`` and the render queue's copy. Without
any pack every answer is the code look and nothing is written.
"""

from __future__ import annotations

import builtins
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import assets, backups, materials  # noqa: E402
from fresing_render.core import assets_keep as K  # noqa: E402
from fresing_render.core import assets_pack as ap  # noqa: E402
from fresing_render.core import backups as backups_core  # noqa: E402
from fresing_render.pccheck import assets_test_pack as tp  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OLD_PROJECT = os.path.join(ROOT, "tests", "data", "old_project_0_2_195.blend")
ALL_IDS = ("environment:FACTORY", "finish:knurl_diamond", "hdri:test_hall", "light:PRODUCT", "material:cast_iron",
           "material:paint_satin", "prop:PALLET")
ORANGE = (0.9, 0.55, 0.05, 1.0)


# ---------------------------------------------------------------------------
# set-up
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def packs(tmp_path_factory):
    base = tmp_path_factory.mktemp("packs")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = {}
    for v in tp.VERSIONS:
        out[v] = str(base / v / ap.FOLDER)
        tp.make(out[v], v)
    out["none"] = str(base / "none")                 # FRESING_ASSETS set to a folder without a pack
    os.makedirs(out["none"])
    return out


@pytest.fixture()
def env(monkeypatch, tmp_path):
    """use(<pack folder>) points the app at a pack and makes it read it again; backups go to tmp."""
    docs = tmp_path / "Documents"
    docs.mkdir()
    monkeypatch.setattr(backups, "documents", lambda: str(docs))
    monkeypatch.setattr(backups, "state_path", lambda: str(tmp_path / "config" / backups_core.STATE_FILE))
    monkeypatch.setitem(assets.SWITCH, "read", None)
    monkeypatch.setitem(assets.STATE, "notes", [])
    monkeypatch.setitem(assets.STATE, "log", [])

    def use(folder):
        monkeypatch.setenv(ap.ENV, folder)
        assets.forget()
        return assets.registry()
    yield use
    assets.forget()


def new_file():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assets.forget()


def _box(name, loc, mat):
    me = bpy.data.meshes.new(name)
    s = 0.25
    v = [(x * s, y * s, z * s) for x in (-1, 1) for y in (-1, 1) for z in (0, 2)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    bpy.context.scene.collection.objects.link(ob)
    return ob


def group_material(name, group, colour=ORANGE, wear=0.3):
    """Like the app's group material with a pack look (0360 builds the real one): the app's BSDF and output, the
    pack's node group as the look, the group's own colour on the group node, the app's own settings on the material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    node = nt.nodes.new("ShaderNodeGroup")
    node.node_tree = group
    node.name = "FR look"
    node.inputs["Colour"].default_value = colour
    for a, b in (("Colour", "Base Color"), ("Metallic", "Metallic"), ("Roughness", "Roughness"), ("Normal", "Normal")):
        nt.links.new(node.outputs[a], bsdf.inputs[b])
    mat["fr_wear"] = wear
    materials.set_look_src(mat, K.read_stamp(group.get(K.STAMP)).get("version", ""))
    return mat


def build_project(scene=None):
    """Every kind of the test pack brought through ``get`` and used, as the plug-in tasks will use them."""
    sc = scene or bpy.context.scene
    got = {aid: assets.get(sc, aid) for aid in ALL_IDS}
    assert all(a.source == "pack" for a in got.values()), {k: (a.source, assets.STATE["log"]) for k, a in got.items()}
    _box("part A", (-0.8, 0, 0), group_material("FR group A", got["material:paint_satin"].datablock))
    _box("part B", (0.0, 0, 0), group_material("FR group B", got["material:cast_iron"].datablock, (0.8, 0.8, 0.8, 1)))
    _box("part C", (0.8, 0, 0), group_material("FR group C", got["finish:knurl_diamond"].datablock, (0.7, 0.7, 0.7, 1)))
    world = bpy.data.worlds.new("FR World")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    mix = nt.nodes.new("ShaderNodeMixRGB")
    for i, aid in ((1, "light:PRODUCT"), (2, "hdri:test_hall")):
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = got[aid].datablock
        nt.links.new(tex.outputs["Color"], mix.inputs[i])
    nt.links.new(mix.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.6
    sc.world = world
    sc.collection.children.link(got["environment:FACTORY"].datablock)
    pallet = got["prop:PALLET"].datablock
    sc.collection.objects.link(pallet)
    pallet.location = (0, 1.2, 0)
    from mathutils import Vector
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.location = Vector((0.4, -3.2, 1.6))
    cam.rotation_euler = (Vector((0, 0.3, 0.25)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam
    return got


def stamped():
    """{(coll, name): stamp} of every stamped datablock of the open file."""
    out = {}
    for c in ("node_groups", "materials", "images", "objects", "meshes", "collections", "worlds"):
        for idb in getattr(bpy.data, c):
            st = assets.stamp_of(idb)
            if st:
                out[(c, idb.name)] = st
    return out


# ---------------------------------------------------------------------------
# the "client": a plain Blender in a process of its own, the pack hidden
# ---------------------------------------------------------------------------

CLIENT = textwrap.dedent(r'''
    import json, os, sys
    import bpy
    path, render = sys.argv[1], sys.argv[2] == "1"
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
    imgs = []
    for img in bpy.data.images:
        if img.source != "FILE":
            continue
        packed = img.packed_file is not None
        found = packed or os.path.exists(bpy.path.abspath(img.filepath))
        imgs.append({"name": img.name, "packed": packed, "found": found, "users": img.users,
                     "size": list(img.size) if packed else None})
    missing = sum(1 for c in ("materials", "node_groups", "worlds", "collections", "objects", "images")
                  for i in getattr(bpy.data, c) if getattr(i, "is_missing", False))
    out = {"libraries": [l.filepath for l in bpy.data.libraries], "images": imgs, "placeholders": missing,
           "linked": sum(1 for c in ("materials", "node_groups", "objects", "collections", "images")
                         for i in getattr(bpy.data, c) if i.library is not None),
           "node_groups": sorted(g.name for g in bpy.data.node_groups),
           "stamps": sum(1 for c in ("node_groups", "images", "objects", "collections", "materials", "meshes")
                         for i in getattr(bpy.data, c) if "fr_asset" in i)}
    mat = bpy.data.materials.get("FR group A")
    if mat is not None:
        n = mat.node_tree.nodes.get("FR look")
        out["colour"] = [round(v, 3) for v in n.inputs["Colour"].default_value]
        rough = [x for x in n.node_tree.nodes if x.bl_idname == "ShaderNodeValue"]
        out["values"] = sorted(round(x.outputs[0].default_value, 3) for x in rough)
    if render:
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        sc.cycles.device = "CPU"
        sc.cycles.samples = 4
        sc.cycles.use_denoising = False
        sc.cycles.seed = 1
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 96, 54, 100
        sc.render.filepath = os.path.join(os.path.dirname(path), "client.png")
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(sc.render.filepath)
        px = list(img.pixels)
        n = len(px) // 4
        out["magenta"] = sum(1 for i in range(n) if px[4*i] > 0.8 and px[4*i+1] < 0.15 and px[4*i+2] > 0.8) / n
        out["mean"] = [sum(px[c::4]) / n for c in range(3)]
    print("CLIENT" + json.dumps(out))
''')


def client(path, pack_folders=(), render=False, tmp=None):
    """Open ``path`` alone in a fresh folder in a plain Blender (no app, no FRESING_ASSETS), the packs hidden."""
    folder = os.path.join(tmp or os.path.dirname(path), f"client_{time.perf_counter_ns()}")
    os.makedirs(folder)
    alone = os.path.join(folder, "project.blend")
    shutil.copyfile(path, alone)
    hidden = []
    for p in pack_folders:
        if os.path.isdir(p):
            os.replace(p, p + " hidden")
            hidden.append(p)
    try:
        env = {k: v for k, v in os.environ.items() if k != ap.ENV}
        r = subprocess.run([sys.executable, "-c", CLIENT, alone, "1" if render else "0"], capture_output=True,
                           text=True, timeout=300, env=env, cwd=folder)
    finally:
        for p in hidden:
            os.replace(p + " hidden", p)
    line = next((x for x in r.stdout.splitlines() if x.startswith("CLIENT")), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    return json.loads(line[len("CLIENT"):])


def complete(info):
    assert info["libraries"] == [] and info["linked"] == 0 and info["placeholders"] == 0, info
    assert info["images"] and all(i["packed"] and i["found"] for i in info["images"]), info["images"]


def same_picture(a, b):
    assert a["magenta"] == 0 and b["magenta"] == 0, (a, b)
    assert sum(a["mean"]) > 0.15, a                                  # not black
    assert max(abs(x - y) for x, y in zip(a["mean"], b["mean"])) < 0.01, (a["mean"], b["mean"])


# ---------------------------------------------------------------------------
# the tests
# ---------------------------------------------------------------------------

def test_every_kind_brought_saved_and_complete_on_a_client(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    assert assets.source(bpy.context.scene) == "pack"
    got = build_project()
    st = stamped()
    for aid in ALL_IDS:
        own = assets.stamp_of(got[aid].datablock)
        assert own["id"] == aid and own["version"] == "1.0.0" and own["pack"] == tp.PACK_ID and K.is_item(own)
        assert own["sha"] == assets.registry().usable[aid].sha256
    assert all(s["version"] == "1.0.0" for s in st.values())
    # pictures at 2k, packed, the bytes of the pack's 2k files
    for img in bpy.data.images:
        if img.source == "FILE":
            s = assets.stamp_of(img)
            assert img.packed_file is not None and "/1k/" not in s["file"] and "_1k" not in s["file"], s
            assert s["sha"] == assets.registry().pack.files[s["file"]][1]
    path = str(tmp_path / "work" / "Crane é.blend")
    os.makedirs(os.path.dirname(path))
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc = bpy.context.scene
    assert (sc.fresing.assets_source, sc.fresing.assets_version) == ("pack", "1.0.0")
    with_pack = client(path, (), render=True, tmp=str(tmp_path))
    alone = client(path, [packs["1.0.0"], packs["1.1.0"]], render=True, tmp=str(tmp_path))
    complete(alone)
    same_picture(alone, with_pack)
    assert alone["colour"] == [round(v, 3) for v in ORANGE]
    assert alone["stamps"] == len(st)
    # a backup opened from Backups\ (0246's copy: relative_remap=False) and the render queue's copy (queue.py:378)
    b = backups.make(sc, force=True, note=False)
    assert b and os.path.basename(os.path.dirname(b)) == backups_core.FOLDER
    complete(client(b, [packs["1.0.0"]], tmp=str(tmp_path)))
    q = str(tmp_path / "queue" / "copy.blend")
    os.makedirs(os.path.dirname(q))
    bpy.ops.wm.save_as_mainfile(filepath=q, copy=True, compress=False, relative_remap=True)
    queue_copy = client(q, [packs["1.0.0"]], render=True, tmp=str(tmp_path))
    complete(queue_copy)
    same_picture(queue_copy, with_pack)


def test_one_copy_per_id_and_version_answered_from_memory(packs, env, monkeypatch):
    env(packs["1.0.0"])
    new_file()
    sc = bpy.context.scene
    first = {aid: assets.get(sc, aid).datablock for aid in ALL_IDS}
    counts = {c: len(getattr(bpy.data, c)) for c in ("node_groups", "images", "objects", "collections", "materials")}
    brings = assets.STATE["brings"]
    # from here on no disk: no file opened, no folder looked at, nothing appended or loaded
    touched = []

    def no(name):
        def f(*a, **k):
            touched.append((name, a[:1]))
            raise AssertionError(f"{name} called while answering from memory")
        return f
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda *a, **k: touched.append(("open", a[:1])) or real_open(*a, **k))
    for mod, name in ((os, "stat"), (os, "listdir"), (os, "scandir"), (os.path, "exists"), (os.path, "isfile"),
                      (os.path, "isdir"), (ap, "find"), (ap, "read")):
        monkeypatch.setattr(mod, name, no(name))
    t0 = time.perf_counter()
    for _ in range(200):
        for aid in ALL_IDS:
            a = assets.get(sc, aid)
            assert a.source == "project" and a.datablock == first[aid]
    per = (time.perf_counter() - t0) / (200 * len(ALL_IDS))
    monkeypatch.undo()
    assert touched == [], touched
    assert assets.STATE["brings"] == brings
    assert counts == {c: len(getattr(bpy.data, c)) for c in counts}
    assert per < 0.002, f"{per * 1000:.3f} ms per question"
    print(f"get from memory: {per * 1e6:.1f} us per question")
    # a second bring answers with the copy
    for aid in ALL_IDS:
        assert assets.bring(sc, aid) == first[aid]
    assert assets.STATE["brings"] == brings
    # bring=False (a draw) never makes anything
    new_file()
    assert assets.get(bpy.context.scene, "material:paint_satin", bring=False).source == "code"
    assert not stamped()


def _variant_pack(src: str, dst: str):
    """The test pack with an environment whose bench uses the cast iron look itself (its own copy of the node group
    and of the two pictures, as a pack .blend that stands alone has them)."""
    shutil.copytree(src, dst)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(os.path.join(dst, "materials", "cast_iron.blend")) as (_s, d):
        d.node_groups = ["FRP cast_iron"]
    with bpy.data.libraries.load(os.path.join(dst, "environments", "FACTORY.blend")) as (_s, d):
        d.collections = ["FRP FACTORY"]
    bench = bpy.data.materials["FRP FACTORY bench"]
    nt = bench.node_tree
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = bpy.data.node_groups["FRP cast_iron"]
    nt.links.new(g.outputs["Colour"], next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"])
    rel = "environments/FACTORY.blend"
    full = os.path.join(dst, *rel.split("/"))
    os.remove(full)
    bpy.data.libraries.write(full, {bpy.data.collections["FRP FACTORY"]}, path_remap="RELATIVE_ALL", compress=True)
    with open(os.path.join(dst, "pack.json"), encoding="utf-8") as f:
        data = json.load(f)
    data["files"][rel] = {"bytes": os.path.getsize(full), "sha256": tp.sha256(full)}
    data["version"] = "1.0.1"
    with open(os.path.join(dst, "pack.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    bpy.ops.wm.read_factory_settings(use_empty=True)


def test_shared_pictures_and_the_environments_own_copy_once(packs, env, tmp_path):
    variant = str(tmp_path / "v" / ap.FOLDER)
    _variant_pack(packs["1.0.0"], variant)
    for order in (("material:cast_iron", "environment:FACTORY"), ("environment:FACTORY", "material:cast_iron")):
        env(variant)
        new_file()
        sc = bpy.context.scene
        got = [assets.get(sc, aid) for aid in order]
        assert [g.source for g in got] == ["pack", "pack"], assets.STATE["log"]
        groups = [g for g in bpy.data.node_groups if assets.stamp_of(g)]
        assert [g.name for g in groups] == ["FRP cast_iron"], [g.name for g in bpy.data.node_groups]
        cast = assets.get(sc, "material:cast_iron").datablock
        assert K.is_item(assets.stamp_of(cast)) and cast == groups[0]
        bench = bpy.data.materials["FRP FACTORY bench"]
        assert any(getattr(n, "node_tree", None) == cast for n in bench.node_tree.nodes)
        names = sorted(i.name for i in bpy.data.images)
        assert len(names) == 3, names                   # cast iron's two pictures once + the concrete
        shas = [assets.stamp_of(i)["sha"] for i in bpy.data.images]
        assert len(set(shas)) == 3
        # the environment again: its copy
        assert assets.get(sc, "environment:FACTORY").datablock == got[order.index("environment:FACTORY")].datablock


def test_update_changes_the_changed_look_keeps_the_groups_own_settings_and_undoes(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    build_project()
    path = str(tmp_path / "p" / "project.blend")
    os.makedirs(os.path.dirname(path))
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc = bpy.context.scene
    reg = env(packs["1.1.0"])
    ch = assets.changes(sc, reg)
    assert sorted(c.id for c in ch) == ["material:cast_iron", "material:paint_satin"], ch
    assert all(c.what == "newer" and (c.old, c.new) == ("1.0.0", "1.1.0") for c in ch)
    colour_img = next(i for i in bpy.data.images if "colour_v1" in assets.stamp_of(i).get("file", "")
                      and "cast_iron" in i.name)
    pallet = bpy.data.objects["FRP PALLET"]
    bpy.ops.ed.undo_push(message="before")
    res = assets.apply(sc, reg, undo="Use the new Fresing looks")
    assert res.ok and len(res.done) == 2 and os.path.isfile(res.backup), res
    mat = bpy.data.materials["FR group A"]
    look = mat.node_tree.nodes["FR look"]
    st = assets.stamp_of(look.node_tree)
    assert st["version"] == "1.1.0" and look.node_tree.name == "FRP paint_satin"
    vals = sorted(round(n.outputs[0].default_value, 3) for n in look.node_tree.nodes if n.bl_idname == "ShaderNodeValue")
    assert 0.42 in vals and 0.36 not in vals
    assert tuple(round(v, 3) for v in look.inputs["Colour"].default_value) == ORANGE and mat["fr_wear"] == 0.3
    assert materials.look_src_of(mat) == "pack:1.1.0" and materials.look_src_matches(mat, "pack", "1.1.0")
    cast = bpy.data.materials["FR group B"].node_tree.nodes["FR look"].node_tree
    files = sorted(assets.stamp_of(n.image)["file"] for n in cast.nodes if n.bl_idname == "ShaderNodeTexImage")
    assert files == ["textures/2k/test_cast_iron_colour_v1.jpg", "textures/2k/test_cast_iron_rough_v2.png"]
    assert any(n.image == colour_img for n in cast.nodes if n.bl_idname == "ShaderNodeTexImage")   # not packed twice
    assert bpy.data.objects["FRP PALLET"] == pallet                                    # unchanged: kept, restamped
    assert {s["version"] for s in stamped().values() if s.get("part") != "images"} == {"1.1.0"}
    assert len([g for g in bpy.data.node_groups if assets.stamp_of(g)]) == 3           # the old copies are gone
    assert (sc.fresing.assets_source, sc.fresing.assets_version) == ("pack", "1.1.0")
    assert assets.changes(sc, reg) == []
    assert assets.apply(sc, reg).done == [] and not assets.apply(sc, reg).backup      # nothing more to do
    upd = str(tmp_path / "p" / "updated.blend")
    bpy.ops.wm.save_as_mainfile(filepath=upd, copy=True)
    info = client(upd, [packs["1.0.0"], packs["1.1.0"]], tmp=str(tmp_path))
    complete(info)
    assert 0.42 in info["values"] and info["colour"] == [round(v, 3) for v in ORANGE]
    # Ctrl+Z gives the old look back
    bpy.ops.ed.undo()
    look = bpy.data.materials["FR group A"].node_tree.nodes["FR look"]
    assert assets.stamp_of(look.node_tree)["version"] == "1.0.0"
    vals = sorted(round(n.outputs[0].default_value, 3) for n in look.node_tree.nodes if n.bl_idname == "ShaderNodeValue")
    assert 0.36 in vals and 0.42 not in vals
    assert bpy.context.scene.fresing.assets_version == "1.0.0"


def test_a_broken_pack_file_builds_nothing_half(packs, env, tmp_path):
    def counts():
        return {c: len(getattr(bpy.data, c)) for c in ("node_groups", "images", "objects", "meshes", "materials",
                                                        "collections", "libraries", "texts")}
    cases = {}
    # 1. a texture missing; 2. a .blend damaged; 3. a .blend that holds a script node (its sha listed as it is)
    for case in ("missing_picture", "damaged_blend", "script"):
        dst = str(tmp_path / case / ap.FOLDER)
        shutil.copytree(packs["1.0.0"], dst)
        if case == "missing_picture":
            os.remove(os.path.join(dst, "textures", "2k", "test_cast_iron_rough_v1.png"))
        elif case == "damaged_blend":
            with open(os.path.join(dst, "materials", "cast_iron.blend"), "r+b") as f:
                f.seek(200)
                f.write(b"\0" * 64)
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            full = os.path.join(dst, "materials", "cast_iron.blend")
            with bpy.data.libraries.load(full) as (_s, d):
                d.node_groups = ["FRP cast_iron"]
            ng = bpy.data.node_groups["FRP cast_iron"]
            sn = ng.nodes.new("ShaderNodeScript")
            sn.mode = "INTERNAL"
            sn.script = bpy.data.texts.new("evil.osl")
            os.remove(full)
            bpy.data.libraries.write(full, {ng}, path_remap="RELATIVE_ALL")
            with open(os.path.join(dst, "pack.json"), encoding="utf-8") as f:
                data = json.load(f)
            data["files"]["materials/cast_iron.blend"] = {"bytes": os.path.getsize(full), "sha256": tp.sha256(full)}
            with open(os.path.join(dst, "pack.json"), "w", encoding="utf-8") as f:
                json.dump(data, f)
        cases[case] = dst
    for case, dst in cases.items():
        env(dst)
        assets.STATE["notes"].clear()
        new_file()
        before = counts()
        a = assets.get(bpy.context.scene, "material:cast_iron")
        assert a.source == "code" and a.id == "material:cast_iron", case
        assert counts() == before, (case, before, counts())
        assert not stamped(), case
        assert assets.note() == assets.NOTE_BRING and assets.STATE["notes"] == [assets.NOTE_BRING], case
        assert assets.STATE["log"][-1][0] == "material:cast_iron"
        b = assets.get(bpy.context.scene, "material:paint_satin")                  # the rest of the pack still works
        assert b.source == "pack"
        assert assets.get(bpy.context.scene, "material:cast_iron").source == "code"
        assert len(assets.STATE["notes"]) == 1                                     # one note per session
    print({k: v for k, v in assets.STATE["log"]})


def test_the_projects_source(packs, env, tmp_path):
    # a new project: pack with a pack and the switch on; code with the switch off or without a pack
    env(packs["1.0.0"])
    new_file()
    sc = bpy.context.scene
    assert assets.source(sc) == "pack" and sc.fresing.assets_source == ""
    p = str(tmp_path / "new.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    assert (sc.fresing.assets_source, sc.fresing.assets_version) == ("pack", "1.0.0")
    assets.SWITCH["read"] = lambda: False
    new_file()
    assert assets.source(bpy.context.scene) == "code"
    assets.SWITCH["read"] = lambda: 1 / 0                         # a broken switch reader: on
    assert assets.use_pack()
    assets.SWITCH["read"] = None
    env(packs["none"])
    new_file()
    assert assets.source(bpy.context.scene) == "code"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "nopack.blend"))
    assert bpy.context.scene.fresing.assets_source == "code"
    # the saved pack project stays pack without the pack; a saved code project stays code with it
    bpy.ops.wm.open_mainfile(filepath=p)
    assert assets.source(bpy.context.scene) == "pack"
    env(packs["1.0.0"])
    bpy.ops.wm.open_mainfile(filepath=str(tmp_path / "nopack.blend"))
    assert assets.source(bpy.context.scene) == "code"
    assert assets.get(bpy.context.scene, "material:paint_satin").source == "code" and not stamped()


def test_an_opened_old_project_stays_code_with_a_pack_present(packs, env, tmp_path):
    env(packs["1.0.0"])
    work = str(tmp_path / "old.blend")
    shutil.copyfile(OLD_PROJECT, work)
    bpy.ops.wm.open_mainfile(filepath=work)
    sc = bpy.context.scene
    assert sc.fresing.assets_source == "" and assets.source(sc) == "code"
    brings = assets.STATE["brings"]
    for aid in ALL_IDS:
        assert assets.get(sc, aid).source == "code"
    assert assets.STATE["brings"] == brings and not stamped()
    assert assets.changes(sc) == []                       # no plug-in kinds yet: nothing a code project would swap
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=work)
    assert bpy.context.scene.fresing.assets_source == "" and assets.source(bpy.context.scene) == "code"


def test_without_any_pack_every_answer_is_code_and_nothing_is_written(packs, env):
    env(packs["none"])
    new_file()
    sc = bpy.context.scene
    reg = assets.registry()
    assert reg.pack is None
    before = {c: len(getattr(bpy.data, c)) for c in ("node_groups", "images", "objects", "materials", "libraries")}
    from fresing_render.core import assets_registry as areg
    for aid in sorted(areg.code_full_ids()):
        a = assets.get(sc, aid)
        assert a.source == "code" and a.id == aid, aid
    assert assets.get(sc, "hdri:test_hall").id == "" and assets.get(sc, "nonsense").source == "code"
    assert assets.get(sc, None).source == "code"
    assert before == {c: len(getattr(bpy.data, c)) for c in before} and not stamped()
    assert sc.fresing.assets_source == "" and assets.changes(sc) == []
    res = assets.apply(sc)
    assert res.note and not res.done and sc.fresing.assets_source == ""


def test_kinds_register_their_own_bring_and_update(packs, env):
    env(packs["1.0.0"])
    new_file()
    seen = []
    try:
        assets.register_kind("prop", name=lambda a, v: f"FR prop {a.code_id}",
                             after_bring=lambda idb, a: seen.append((idb.name, a.id)),
                             code_changes=lambda sc, reg: [K.Change("prop:PALLET", "prop", "code", "", reg.version)],
                             code_apply=lambda sc, reg: seen.append("applied") or ["prop:PALLET"])
        a = assets.get(bpy.context.scene, "prop:PALLET")
        assert a.datablock.name == "FR prop PALLET" and seen == [("FR prop PALLET", "prop:PALLET")]
        with pytest.raises(ValueError):
            assets.register_kind("nonsense")
        with pytest.raises(TypeError):
            assets.register_kind("prop", what=1)
        # a code project: the plug-in says what it would swap; apply makes it pack
        new_file()
        sc = bpy.context.scene
        sc.fresing.assets_source = "code"
        ch = assets.changes(sc)
        assert [c.what for c in ch] == ["code"]
        res = assets.apply(sc, backup=False)
        assert "applied" in seen and [c.id for c in res.done] == ["prop:PALLET"]
        assert (sc.fresing.assets_source, sc.fresing.assets_version) == ("pack", "1.0.0")
    finally:
        assets.unregister_kind("prop")
    assert "prop" not in assets.HOOKS


def test_apply_makes_a_backup_first_and_stops_without_one(packs, env, tmp_path, monkeypatch):
    env(packs["1.0.0"])
    new_file()
    build_project()
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "b.blend"))
    reg = env(packs["1.1.0"])
    monkeypatch.setattr(backups, "make", lambda *a, **k: "")
    backups._S["last_reason"] = "not enough free space"
    res = assets.apply(bpy.context.scene, reg)
    assert res.note == assets.NOTE_BACKUP.format(why="not enough free space") and not res.done
    assert bpy.context.scene.fresing.assets_version == "1.0.0"
    assert {s["version"] for s in stamped().values() if s.get("part") != "images"} == {"1.0.0"}


BACKGROUND = textwrap.dedent(r'''
    import json, os, sys
    sys.path.insert(0, sys.argv[1])
    import bpy, fresing_render
    fresing_render.register()
    from fresing_render.blender import assets
    bpy.ops.wm.read_factory_settings(use_empty=True)
    out = {}
    for aid in sys.argv[2].split(","):
        a = assets.get(bpy.context.scene, aid)
        out[aid] = {"source": a.source, "stamp": assets.stamp_of(a.datablock) if a.datablock else {}}
    out["source"] = assets.source(bpy.context.scene)
    print("BG" + json.dumps(out))
''')


def test_a_background_blender_finds_the_pack_by_its_variable_and_brings_the_same(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    here = {aid: assets.stamp_of(assets.get(bpy.context.scene, aid).datablock) for aid in ALL_IDS}
    e = dict(os.environ, **{ap.ENV: packs["1.0.0"]})
    r = subprocess.run([sys.executable, "-c", BACKGROUND, ROOT, ",".join(ALL_IDS)], capture_output=True, text=True,
                       timeout=300, env=e, cwd=str(tmp_path))
    line = next((x for x in r.stdout.splitlines() if x.startswith("BG")), None)
    assert line, r.stdout[-2000:] + r.stderr[-2000:]
    bg = json.loads(line[2:])
    assert bg["source"] == "pack"
    for aid in ALL_IDS:
        assert bg[aid]["source"] == "pack" and bg[aid]["stamp"] == here[aid], aid


def test_a_pack_project_on_a_pc_without_the_pack_keeps_its_copies(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    build_project()
    path = str(tmp_path / "pack_project.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    env(packs["none"])
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    for aid in ALL_IDS:
        a = assets.get(sc, aid)
        assert a.source == "project" and assets.stamp_of(a.datablock)["id"] == aid
    assert assets.get(sc, "material:steel_brushed").source == "code"      # a new group: the code look, no note
    assert assets.STATE["notes"] == []
    assert assets.changes(sc) == []


# ---------------------------------------------------------------------------
# the independent review's findings (each failed before its fix)
# ---------------------------------------------------------------------------

def _relist(dst, assets_rows=None):
    """pack.json again after files changed: every file's bytes + sha256, and the rows when given."""
    with open(os.path.join(dst, "pack.json"), encoding="utf-8") as f:
        data = json.load(f)
    data["files"] = {}
    for base, _d, names in os.walk(dst):
        for n in names:
            full = os.path.join(base, n)
            r = os.path.relpath(full, dst).replace(os.sep, "/")
            if r != "pack.json":
                data["files"][r] = {"bytes": os.path.getsize(full), "sha256": tp.sha256(full)}
    if assets_rows is not None:
        data["assets"] = assets_rows
    with open(os.path.join(dst, "pack.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return data


def _load(dst, rel, coll, name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    full = os.path.join(dst, *rel.split("/"))
    with bpy.data.libraries.load(full) as (_s, d):
        setattr(d, coll, [name])
    return full, getattr(bpy.data, coll)[name]


def _write(full, ids):
    os.remove(full)
    bpy.data.libraries.write(full, set(ids), path_remap="RELATIVE_ALL", fake_user=True)


def test_review_parts_of_two_files_with_the_same_name_stay_apart(packs, env, tmp_path):
    dst = str(tmp_path / "p" / ap.FOLDER)
    shutil.copytree(packs["1.0.0"], dst)
    full, ob = _load(dst, "props/PALLET.blend", "objects", "FRP PALLET")
    ob.data.name, ob.data.materials[0].name = "Box", "Wood"
    _write(full, [ob])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("Box")
    me.from_pydata([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new("Wood")
    mat.diffuse_color = (0.8, 0.1, 0.1, 1)
    me.materials.append(mat)
    bpy.data.libraries.write(os.path.join(dst, "props", "CONTAINER.blend"), {bpy.data.objects.new("FRP CONTAINER", me)},
                             path_remap="RELATIVE_ALL", fake_user=True)
    with open(os.path.join(dst, "pack.json"), encoding="utf-8") as f:
        rows = json.load(f)["assets"]
    row = dict(next(r for r in rows if r["id"] == "prop:PALLET"))
    row.update(id="prop:CONTAINER", file="props/CONTAINER.blend", datablock=["objects", "FRP CONTAINER"])
    _relist(dst, rows + [row])
    env(dst)
    new_file()
    sc = bpy.context.scene
    p, c = assets.get(sc, "prop:PALLET").datablock, assets.get(sc, "prop:CONTAINER").datablock
    assert len(p.data.vertices) > 8 and len(c.data.vertices) == 4 and p.data != c.data
    assert tuple(round(x, 2) for x in c.data.materials[0].diffuse_color) == (0.8, 0.1, 0.1, 1.0)


def test_review_a_prop_update_keeps_every_placed_copy_where_it_stands(packs, env, tmp_path):
    v11 = str(tmp_path / "p" / ap.FOLDER)
    shutil.copytree(packs["1.1.0"], v11)
    full, ob = _load(v11, "props/PALLET.blend", "objects", "FRP PALLET")
    ob.data.vertices[0].co.z = -0.01                                      # a changed look
    _write(full, [ob])
    with open(os.path.join(v11, "pack.json"), encoding="utf-8") as f:
        rows = json.load(f)["assets"]
    for r in rows:
        if r["id"] == "prop:PALLET":
            r["changed"] = "1.1.0"
    _relist(v11, rows)
    env(packs["1.0.0"])
    new_file()
    sc = bpy.context.scene
    p = assets.get(sc, "prop:PALLET").datablock
    sc.collection.objects.link(p)
    p.location = (3, 2, 0)
    dup = p.copy()
    sc.collection.objects.link(dup)
    dup.location = (-3, 0, 0)
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "props.blend"))
    res = assets.apply(sc, env(v11), backup=False)
    assert [c.id for c in res.done] == ["prop:PALLET"], res
    obs = sorted((o.name, tuple(round(v, 3) for v in o.location)) for o in bpy.data.objects)
    assert obs == [("FRP PALLET", (3.0, 2.0, 0.0)), ("FRP PALLET.001", (-3.0, 0.0, 0.0))], obs
    for o in bpy.data.objects:
        assert assets.stamp_of(o)["version"] == "1.1.0" and round(o.data.vertices[0].co.z, 3) == -0.01
    assert len(bpy.data.meshes) == 1


def test_review_a_shared_picture_keeps_each_colour_space(packs, env, tmp_path):
    dst = str(tmp_path / "p" / ap.FOLDER)
    shutil.copytree(packs["1.0.0"], dst)
    full, ng = _load(dst, "materials/paint_satin.blend", "node_groups", "FRP paint_satin")
    img = bpy.data.images.load(os.path.join(dst, "textures", "2k", "test_cast_iron_colour_v1.jpg"))
    img.colorspace_settings.name = "Non-Color"
    ng.nodes.new("ShaderNodeTexImage").image = img
    _write(full, [ng])
    _relist(dst)
    env(dst)
    new_file()
    sc = bpy.context.scene
    spaces = {}
    for aid in ("material:cast_iron", "material:paint_satin"):
        g = assets.get(sc, aid).datablock
        spaces[aid] = {n.image.colorspace_settings.name for n in g.nodes
                       if n.bl_idname == "ShaderNodeTexImage" and "colour_v1" in assets.stamp_of(n.image)["file"]}
    assert spaces == {"material:cast_iron": {"sRGB"}, "material:paint_satin": {"Non-Color"}}


def test_review_a_refused_item_is_not_tried_again_this_session(packs, env, tmp_path, monkeypatch):
    dst = str(tmp_path / "p" / ap.FOLDER)
    shutil.copytree(packs["1.0.0"], dst)
    os.remove(os.path.join(dst, "textures", "2k", "test_cast_iron_rough_v1.png"))
    env(dst)
    new_file()
    assert assets.get(bpy.context.scene, "material:cast_iron").source == "code"
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda *a, **k: opened.append(a[:1]) or real_open(*a, **k))
    for _ in range(20):
        assert assets.get(bpy.context.scene, "material:cast_iron").source == "code"
    monkeypatch.setattr(builtins, "open", real_open)
    assert len(assets.STATE["log"]) == 1 and opened == [], (assets.STATE["log"], opened)
    env(dst)                                         # the pack read again (an update put in place): tried again
    assets.get(bpy.context.scene, "material:cast_iron")
    assert len(assets.STATE["log"]) == 2


def test_review_a_scene_made_later_is_the_projects(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    assets.get(bpy.context.scene, "material:paint_satin")
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "s.blend"))
    later = bpy.data.scenes.new("House – later")
    assert later.fresing.assets_source == "" and assets.source(later) == "pack" and assets.version(later) == "1.0.0"
    assert assets.get(later, "material:cast_iron").source == "pack"
    bpy.ops.wm.save_mainfile()
    assert (later.fresing.assets_source, later.fresing.assets_version) == ("pack", "1.0.0")


def test_review_two_picture_items_with_the_same_bytes_are_two_items(packs, env, tmp_path):
    dst = str(tmp_path / "p" / ap.FOLDER)
    shutil.copytree(packs["1.0.0"], dst)
    shutil.copyfile(os.path.join(dst, "lights", "PRODUCT.exr"), os.path.join(dst, "hdri", "test_hall_2k.exr"))
    _relist(dst)
    env(dst)
    new_file()
    sc = bpy.context.scene
    light = assets.get(sc, "light:PRODUCT").datablock
    brings = assets.STATE["brings"]
    answers = [assets.get(sc, "hdri:test_hall") for _ in range(3)]
    assert [a.source for a in answers] == ["pack", "project", "project"] and assets.STATE["brings"] == brings + 1
    assert answers[0].datablock != light and assets.stamp_of(light)["id"] == "light:PRODUCT"


def test_review_forget_waits_for_the_start_up_read(packs, env, monkeypatch):
    monkeypatch.delenv(ap.ENV, raising=False)
    from fresing_render.core import assets_registry as areg
    slow_find = ap.find

    def slow(*a, **k):
        time.sleep(0.5)
        return slow_find(*a, **k)
    monkeypatch.setattr(ap, "find", slow)
    areg.forget()
    assets.warm()                                    # reads "no pack" slowly, as at a start
    monkeypatch.setenv(ap.ENV, packs["1.0.0"])
    assets.forget()
    assert assets.registry().version == "1.0.0"


def test_review_the_users_duplicate_is_not_the_pack_copy(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    sc = bpy.context.scene
    g = assets.get(sc, "material:paint_satin").datablock
    group_material("FR group A", g).use_fake_user = True
    dup = g.copy()
    dup.name = "AAA my own variant"
    group_material("FR mine", dup).use_fake_user = True
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "d.blend"))
    bpy.ops.wm.open_mainfile(filepath=str(tmp_path / "d.blend"))
    sc = bpy.context.scene
    assert assets.get(sc, "material:paint_satin").datablock.name == "FRP paint_satin"
    assets.apply(sc, env(packs["1.1.0"]), backup=False)
    mine = bpy.data.materials["FR mine"].node_tree.nodes["FR look"].node_tree
    assert mine.name == "AAA my own variant" and assets.stamp_of(mine) == {}
    assert assets.stamp_of(bpy.data.materials["FR group A"].node_tree.nodes["FR look"].node_tree)["version"] == "1.1.0"


def test_review_packed_pictures_refused_the_built_in_font_allowed(packs, env, tmp_path):
    dst = str(tmp_path / "a" / ap.FOLDER)
    shutil.copytree(packs["1.0.0"], dst)
    full, ng = _load(dst, "materials/paint_satin.blend", "node_groups", "FRP paint_satin")
    img = bpy.data.images.new("unlisted", 8, 8)
    img.pack()
    img.source = "FILE"
    ng.nodes.new("ShaderNodeTexImage").image = img
    _write(full, [ng])
    full, pal = _load(dst, "props/PALLET.blend", "objects", "FRP PALLET")
    cu = bpy.data.curves.new("label", "FONT")
    cu.body = "MAX 1000 kg"
    lab = bpy.data.objects.new("label", cu)
    pal["fr_label"] = lab
    _write(full, [pal])
    _relist(dst)
    env(dst)
    new_file()
    before = {c: len(getattr(bpy.data, c)) for c in ("node_groups", "images", "libraries")}
    assert assets.get(bpy.context.scene, "material:paint_satin").source == "code"
    assert assets.STATE["log"][-1][0] == "material:paint_satin"          # refused whole
    assert before == {c: len(getattr(bpy.data, c)) for c in before}
    assert assets.get(bpy.context.scene, "prop:PALLET").source == "pack"


def test_review_a_failed_update_keeps_the_version_and_says_so_once(packs, env, tmp_path):
    env(packs["1.0.0"])
    new_file()
    build_project()
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "h.blend"))
    v11 = str(tmp_path / "v" / ap.FOLDER)
    shutil.copytree(packs["1.1.0"], v11)
    os.remove(os.path.join(v11, "textures", "2k", "test_cast_iron_rough_v2.png"))
    sc = bpy.context.scene
    res = assets.apply(sc, env(v11), backup=False)
    assert [c.id for c in res.done] == ["material:paint_satin"] and [f[0] for f in res.failed] == ["material:cast_iron"]
    assert res.note == assets.NOTE_SOME.format(n="1 look") and assets.STATE["notes"] == []
    assert (sc.fresing.assets_source, sc.fresing.assets_version) == ("pack", "1.0.0")
    assert [c.id for c in assets.changes(sc)] == ["material:cast_iron"]
    assert assets.get(sc, "material:cast_iron").source == "project"
