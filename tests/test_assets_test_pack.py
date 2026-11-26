"""Task 0354: the made-up test pack (``pccheck/assets_test_pack.py``) written by Blender, read by ``assets_pack``.

Blender as a Python module, in a process of its own: the maker writes versions 1.0.0 and 1.1.0, ``assets_pack``
reads both with no note, ``verify`` passes, every ``.blend`` opens and holds what pack.json lists – and nothing that
can run code (no Text datablocks, no drivers, no script nodes, no links to other files) –, the node groups keep the
contract of study 0344 2.3, and the caller's own file is left as it was.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

pytest.importorskip("bpy")

from fresing_render.core import assets_pack as ap  # noqa: E402
from fresing_render.core import assets_registry as reg  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

CHILD = textwrap.dedent(r'''
    import json, os, sys, time
    sys.path.insert(0, sys.argv[1])
    import bpy
    from fresing_render.pccheck import assets_test_pack as tp
    from fresing_render.core import assets_pack as ap
    out = {"made": {}, "blends": {}}
    def py(v):        # an ID property's value as plain Python, read now (the datablock goes at the next file)
        return v.to_list() if hasattr(v, "to_list") else v.to_dict() if hasattr(v, "to_dict") else v
    base = sys.argv[2]

    # the caller's own file: one of the maker's names is already taken, and nothing may be added or lost
    mine = bpy.data.node_groups.new("FRP paint_satin", "ShaderNodeTree")
    mine["mine"] = 1
    def counts():
        return {c: len(getattr(bpy.data, c)) for c in ("node_groups", "materials", "images", "objects", "meshes",
                                                        "collections", "scenes", "texts", "worlds")}
    before = counts()
    for v in tp.VERSIONS:
        out["made"][v] = tp.make(os.path.join(base, v, "Fresing Assets"), v)
    out["caller_kept"] = (counts() == before and bpy.data.node_groups["FRP paint_satin"].get("mine") == 1
                          and len(bpy.data.node_groups) == before["node_groups"])

    COLLS = ("node_groups", "materials", "images", "objects", "meshes", "collections", "scenes", "texts", "worlds",
             "actions", "libraries", "lights", "cameras")
    for v in tp.VERSIONS:
        root = os.path.join(base, v, "Fresing Assets")
        for dirpath, _d, names in os.walk(root):
            for n in names:
                if not n.endswith(".blend"):
                    continue
                path = os.path.join(dirpath, n)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                with bpy.data.libraries.load(path) as (src, _dst):
                    listed = {c: list(getattr(src, c)) for c in COLLS if hasattr(src, c)}
                bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
                info = {"listed": listed, "groups": {}, "drivers": 0, "libraries": len(bpy.data.libraries),
                        "texts": len(bpy.data.texts), "images": [], "objects": {}, "materials": {}}
                ids = [*bpy.data.node_groups, *bpy.data.materials, *bpy.data.objects, *bpy.data.meshes,
                       *bpy.data.collections, *bpy.data.images]
                for idb in ids:
                    ad = getattr(idb, "animation_data", None)
                    info["drivers"] += len(ad.drivers) if ad else 0
                    nt = getattr(idb, "node_tree", None)
                    ad = getattr(nt, "animation_data", None) if nt else None
                    info["drivers"] += len(ad.drivers) if ad else 0
                trees = [(g.name, g) for g in bpy.data.node_groups]
                trees += [(m.name, m.node_tree) for m in bpy.data.materials if m.node_tree]
                for name, nt in trees:
                    info["groups"][name] = {
                        "nodes": sorted({nd.bl_idname for nd in nt.nodes}),
                        "inputs": [s.name for s in nt.interface.items_tree if getattr(s, "in_out", "") == "INPUT"],
                        "outputs": [s.name for s in nt.interface.items_tree if getattr(s, "in_out", "") == "OUTPUT"],
                        "attributes": sorted((nd.attribute_type, nd.attribute_name) for nd in nt.nodes
                                             if nd.bl_idname == "ShaderNodeAttribute"),
                    }
                for m in bpy.data.materials:
                    info["materials"][m.name] = {k: py(m[k]) for k in m.keys() if k.startswith("fr_")}
                for img in bpy.data.images:
                    full = bpy.path.abspath(img.filepath, library=img.library) if not img.packed_file else ""
                    info["images"].append({"path": img.filepath, "packed": bool(img.packed_file),
                                           "full": os.path.normpath(os.path.join(os.path.dirname(path),
                                                                                img.filepath[2:]))
                                           if img.filepath.startswith("//") else img.filepath})
                for ob in bpy.data.objects:
                    d = {"type": ob.type, "props": {k: py(ob[k]) for k in ob.keys() if k.startswith("fr_")}}
                    if ob.type == "MESH":
                        me = ob.data
                        zs = [v.co.z for v in me.vertices]
                        d["min_z"], d["max_z"] = min(zs), max(zs)
                        a = me.attributes.get("fr_lod")
                        d["lod"] = sorted({x.value for x in a.data}) if a else []
                        d["lod_domain"] = a.domain if a else ""
                        d["materials"] = [m.name for m in me.materials if m]
                    info["objects"][ob.name] = d
                info["collections"] = {c.name: sorted(o.name for o in c.objects) for c in bpy.data.collections}
                out["blends"][f"{v}/{rel}"] = info
    print("CHILD-JSON " + json.dumps(out))
''')


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    base = tmp_path_factory.mktemp("assets_test_pack")
    script = base / "child.py"
    script.write_text(CHILD, encoding="utf-8")
    env = dict(os.environ)
    env.pop(ap.ENV, None)
    p = subprocess.run([sys.executable, str(script), ROOT, str(base)], capture_output=True, text=True,
                       timeout=600, env=env)
    line = next((x for x in p.stdout.splitlines() if x.startswith("CHILD-JSON ")), None)
    assert p.returncode == 0 and line, p.stdout[-3000:] + p.stderr[-3000:]
    return base, json.loads(line[len("CHILD-JSON "):])


def test_the_maker_is_quick_and_small(made):
    _base, out = made
    for v, got in out["made"].items():
        assert got["seconds"] < 30, got                        # brief: aim under 30 s
        assert got["bytes"] < 10e6 and got["files"] >= 20, got
        print(f"test pack {v}: {got['files']} files, {got['bytes'] / 1e6:.2f} MB, {got['seconds']} s")


def test_the_maker_leaves_the_callers_file_as_it_was(made):
    assert made[1]["caller_kept"]


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_assets_pack_reads_the_made_pack_with_no_notes(made, version):
    base, _ = made
    root = str(base / version / "Fresing Assets")
    f = ap.read(root, "0.2.300")
    assert f.state == "ok" and f.note == "" and f.pack.left_out == [], f.detail
    p = f.pack
    assert p.version == version and p.licence == "LICENSE-ASSETS.txt"
    assert "TEST PACK" in open(p.path(p.licence), encoding="utf-8").read()
    kinds = {a.kind for a in p.assets.values()}
    assert {"material", "finish", "light", "hdri", "prop", "environment"} <= kinds
    v = ap.verify(p)
    assert v.ok and v.problems == [] and v.files == sum(len(fs) for _d, _s, fs in os.walk(root)) - 1  # all but pack.json
    r = reg.Registry.build(f)
    assert r.refused == [] and r.problems() == [] and r.note == ""
    assert set(r.usable) == set(p.assets)
    assert r.resolve("material:paint_satin").source == "pack"
    assert r.resolve("hdri:test_hall", use_pack=False).id == "light:OVERCAST"
    for a in p.assets.values():
        assert a.picture and os.path.getsize(p.path(a.picture)) > 0
        for t in a.textures:
            assert p.path(t)
    # 1k and 2k pictures for draft and normal (owner's pick 2: projects carry 2k)
    assert any("/1k/" in t for t in p.assets["material:cast_iron"].textures)
    assert any("/2k/" in t for t in p.assets["material:cast_iron"].textures)


def test_every_blend_holds_what_pack_json_lists_and_nothing_that_runs_code(made):
    base, out = made
    seen = 0
    for version in ("1.0.0", "1.1.0"):
        root = str(base / version / "Fresing Assets")
        p = ap.read(root, "0.2.300").pack
        blends = {a.file: a for a in p.assets.values() if a.file.endswith(".blend")}
        assert len(blends) == 5
        for rel, a in blends.items():
            info = out["blends"][f"{version}/{rel}"]
            seen += 1
            coll, name = a.datablock
            assert name in info["listed"][coll], (rel, info["listed"])
            # data only (0344 1.5)
            assert info["listed"]["texts"] == [] and info["texts"] == 0, rel
            assert info["drivers"] == 0 and info["libraries"] == 0, rel
            for g in info["groups"].values():
                assert "ShaderNodeScript" not in g["nodes"], rel
            # every picture is a file of the pack, beside it, by a relative path
            for img in info["images"]:
                assert img["path"].startswith("//") and not img["packed"], (rel, img)
                assert os.path.isfile(img["full"]) and os.path.realpath(img["full"]).startswith(
                    os.path.realpath(root)), img
                assert os.path.relpath(img["full"], root).replace(os.sep, "/") in a.textures, (rel, img)
            if a.kind in ap.SOCKETS:
                g = info["groups"][name]
                spec = ap.SOCKETS[a.kind]
                assert set(spec["inputs"]) <= set(g["inputs"]), g
                assert set(spec["outputs"]) <= set(g["outputs"]) <= set(spec["outputs"]) | set(
                    spec["optional_outputs"]), g
                assert not any(n.startswith(ap.FORBIDDEN_NODES) for n in g["nodes"]), g["nodes"]
                assert "ShaderNodeTexCoord" in g["nodes"] or a.kind == "finish"
            if a.kind == "finish":
                attrs = info["groups"][name]["attributes"]
                assert ["GEOMETRY", "fr_fx_o"] in attrs and ["VIEW_LAYER", ap.PIXEL_ATTRIBUTE] in attrs
            if a.kind == "prop":
                ob = info["objects"][name]
                assert ob["lod"] == [1, 2] and ob["lod_domain"] == "FACE"
                assert abs(ob["min_z"]) < 1e-6 and ob["props"]["fr_size_m"] == [1.2, 0.8, 0.144]
            if a.kind == "environment":
                objs = info["collections"][name]
                assert len(objs) == 2
                floor = [m for m, props in info["materials"].items() if props.get("fr_env") == "floor"]
                assert floor == ["FRP FACTORY floor"]
    assert seen == 10


def test_version_1_1_changes_one_look_and_one_picture(made):
    base, _ = made
    old = ap.read(str(base / "1.0.0" / "Fresing Assets"), "0.2.300").pack
    new = ap.read(str(base / "1.1.0" / "Fresing Assets"), "0.2.300").pack
    assert set(old.assets) == set(new.assets)
    changed = {i for i in old.assets if old.assets[i].sha256 != new.assets[i].sha256}
    assert {"material:paint_satin", "material:cast_iron"} <= changed
    assert {i for i in new.assets if new.assets[i].changed == "1.1.0"} == {"material:paint_satin",
                                                                            "material:cast_iron"}
    # the changed picture has a new name: a file is never overwritten between versions
    assert set(new.files) - set(old.files) == {"textures/1k/test_cast_iron_rough_v2.png",
                                               "textures/2k/test_cast_iron_rough_v2.png"}
    same = set(old.files) & set(new.files)
    assert all(old.files[f] == new.files[f] for f in same if f.startswith("textures/"))


def test_the_maker_refuses_a_folder_with_other_files(tmp_path):
    from fresing_render.pccheck import assets_test_pack as tp
    (tmp_path / "mine.txt").write_text("keep me")
    with pytest.raises(ValueError, match="holds other files"):
        tp.make(str(tmp_path))
    assert (tmp_path / "mine.txt").read_text() == "keep me"
    with pytest.raises(ValueError, match="versions"):
        tp.make(str(tmp_path / "x"), "2.0.0")
