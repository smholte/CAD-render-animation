"""Task 0356: ``tools/assets_check.py`` – the pack checks a worker runs before an upload and CI runs after it.

It passes on 0354's made-up test pack (made once here, in a process of its own) and fails, with the right line, on a
broken copy of it – one test per check. The plain checks run without Blender; the ``.blend`` checks and the small
renders run the checker's own Blender child (Blender as a Python module), on copies whose ``.blend`` files a second
child broke on purpose.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import zipfile

import pytest

pytest.importorskip("bpy")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import assets_check as ac  # noqa: E402
from fresing_render.core import assets_pack as ap  # noqa: E402

APP = "0.2.300"


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    """The test pack 1.0.0, made once (the folder holding pack.json)."""
    base = tmp_path_factory.mktemp("assets_check")
    root = base / "good" / "Fresing Assets"
    env = dict(os.environ)
    env.pop(ap.ENV, None)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_test_assets_pack.py"), str(root)],
                       capture_output=True, text=True, timeout=300, env=env)
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    return root


def copy(pack, tmp_path, name="copy"):
    dst = tmp_path / name / "Fresing Assets"
    shutil.copytree(pack, dst)
    return dst


def load(root):
    with open(root / "pack.json", encoding="utf-8") as f:
        return json.load(f)


def save(root, data):
    with open(root / "pack.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def rehash(root):
    """pack.json's 'files' written again from what is in the folder (a broken copy that is otherwise consistent)."""
    data = load(root)
    files = {}
    for base, _d, names in os.walk(root):
        for n in names:
            full = os.path.join(base, n)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel != "pack.json":
                with open(full, "rb") as f:
                    files[rel] = {"bytes": os.path.getsize(full), "sha256": hashlib.sha256(f.read()).hexdigest()}
    data["files"] = dict(sorted(files.items()))
    save(root, data)


def row(data, rid):
    return next(r for r in data["assets"] if r["id"] == rid)


def plain(root):
    return ac.check(str(root), APP, use_blender=False)


def has(rep, *words):
    """One problem line holds every word."""
    hit = [p for p in rep.problems if all(w in p for w in words)]
    assert hit, f"no problem with {words}: {rep.problems}"
    return hit[0]


def png(path, w, h):
    import zlib
    raw = b"".join(b"\0" + b"\x80" * (w * 3) for _ in range(h))
    chunk = lambda t, d: (len(d).to_bytes(4, "big") + t + d  # noqa: E731
                          + (zlib.crc32(t + d) & 0xFFFFFFFF).to_bytes(4, "big"))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", w.to_bytes(4, "big") + h.to_bytes(4, "big") + b"\x08\x02\0\0\0")
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


# ---------------------------------------------------------------------------------------------- the good pack

def test_the_test_pack_passes_every_check_with_its_renders(pack):
    rep = ac.check(str(pack), APP)
    assert rep.ok and rep.warnings == [], rep.lines()
    shown = " ".join(rep.info)
    for kind in ("material", "finish", "light", "hdri", "prop", "environment"):
        assert kind in shown, shown                   # a small render per item, every kind


def test_the_command_line_says_ok_and_exits_0(pack):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "assets_check.py"), str(pack), "--no-render",
                        "--app-version", APP], capture_output=True, text=True, timeout=300)
    assert p.returncode == 0 and "OK – every pack check passed" in p.stdout, p.stdout + p.stderr


def test_the_zip_of_the_test_pack_passes(pack, tmp_path):
    z = tmp_path / "FresingAssets-1.0.0.zip"
    shutil.make_archive(str(z)[:-4], "zip", pack.parent, ap.FOLDER)
    rep = ac.check(str(z), APP, use_blender=False)
    assert rep.ok, rep.lines()


def test_picture_size_reads_png_jpeg_and_exr_heads(pack):
    assert ac.picture_size(str(pack / "textures/2k/test_cast_iron_rough_v1.png")) == (2048, 2048)
    assert ac.picture_size(str(pack / "textures/1k/test_cast_iron_colour_v1.jpg")) == (1024, 1024)
    assert ac.picture_size(str(pack / "hdri/test_hall_1k.exr")) == (1024, 512)
    assert ac.picture_size(str(pack / "LICENSE-ASSETS.txt")) is None


# ---------------------------------------------------------------------------------------------- zip

def _zip(src_root, z, extra=None):
    with zipfile.ZipFile(z, "w") as zf:
        for base, _d, names in os.walk(src_root):
            for n in names:
                full = os.path.join(base, n)
                zf.write(full, ap.FOLDER + "/" + os.path.relpath(full, src_root).replace(os.sep, "/"))
        if extra:
            extra(zf)


def test_zip_with_the_wrong_name(pack, tmp_path):
    z = tmp_path / "pack.zip"
    _zip(pack, z)
    has(ac.check(str(z), APP, use_blender=False), "zip:", "is not FresingAssets-<version>.zip")


def test_zip_whose_name_and_pack_json_differ(pack, tmp_path):
    z = tmp_path / "FresingAssets-1.0.1.zip"
    _zip(pack, z)
    has(ac.check(str(z), APP, use_blender=False), "zip:", "version 1.0.1", "pack.json 1.0.0")


def test_zip_with_a_path_outside_the_top_folder(pack, tmp_path):
    z = tmp_path / "FresingAssets-1.0.0.zip"
    _zip(pack, z, lambda zf: zf.writestr("Fresing Assets/../evil.txt", "x"))
    has(ac.check(str(z), APP, use_blender=False), "zip:", "lies outside the top folder")


def test_zip_with_a_link(pack, tmp_path):
    z = tmp_path / "FresingAssets-1.0.0.zip"

    def link(zf):
        info = zipfile.ZipInfo("Fresing Assets/link.txt")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "/etc/passwd")
    _zip(pack, z, link)
    has(ac.check(str(z), APP, use_blender=False), "zip:", "is a link")


# ---------------------------------------------------------------------------------------------- pack.json

def test_damaged_pack_json(pack, tmp_path):
    root = copy(pack, tmp_path)
    (root / "pack.json").write_text("{not json", encoding="utf-8")
    has(plain(root), "pack.json:", "could not be read", "damaged")


def test_pack_json_for_a_newer_app(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    d["app_min"] = "9.0.0"
    save(root, d)
    has(plain(root), "pack.json:", "needs Fresing Render 9.0.0")


def test_a_row_the_app_leaves_out(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "material:paint_satin")["contract"] = 9
    save(root, d)
    has(plain(root), "material:paint_satin", "left out by the app", "contract 9")


# ---------------------------------------------------------------------------------------------- files

def test_a_file_with_another_content(pack, tmp_path):
    root = copy(pack, tmp_path)
    with open(root / "lights/PRODUCT.exr", "r+b") as f:
        f.seek(-10, 2)
        f.write(b"0123456789")
    has(plain(root), "files: lights/PRODUCT.exr", "sha256")


def test_a_listed_file_is_missing(pack, tmp_path):
    root = copy(pack, tmp_path)
    os.remove(root / "pictures/prop.PALLET.jpg")
    has(plain(root), "files: pictures/prop.PALLET.jpg is missing")


def test_a_file_pack_json_does_not_list(pack, tmp_path):
    root = copy(pack, tmp_path)
    (root / "textures/2k/stray.png").write_bytes(b"x")
    has(plain(root), "files: textures/2k/stray.png", "not in pack.json's 'files'")


def test_a_program_file_in_the_pack(pack, tmp_path):
    root = copy(pack, tmp_path)
    (root / "materials/helper.py").write_text("print('hi')\n")
    rehash(root)
    has(plain(root), "data only: materials/helper.py")


# ---------------------------------------------------------------------------------------------- licence

def test_no_licence_in_the_pack(pack, tmp_path):
    root = copy(pack, tmp_path)
    os.remove(root / "LICENSE-ASSETS.txt")
    d = load(root)
    d["licence"] = ""
    save(root, d)
    rehash(root)
    rep = plain(root)
    has(rep, "licence: LICENSE-ASSETS.txt is not in the pack")
    has(rep, "licence: pack.json names ''")


def test_an_empty_licence(pack, tmp_path):
    root = copy(pack, tmp_path)
    (root / "LICENSE-ASSETS.txt").write_text("")
    rehash(root)
    has(plain(root), "licence: LICENSE-ASSETS.txt is missing or empty")


# ---------------------------------------------------------------------------------------------- code twins

def test_an_id_with_no_code_twin(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "material:paint_satin")["id"] = "material:no_such_look"
    save(root, d)
    has(plain(root), "code twin: material:no_such_look")


def test_a_pack_only_photo_without_a_fallback(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "hdri:test_hall")["fallback"] = ""
    save(root, d)
    has(plain(root), "code twin: hdri:test_hall")


# ---------------------------------------------------------------------------------------------- pictures

def test_an_item_without_its_picker_picture(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "prop:PALLET")["picture"] = ""
    save(root, d)
    has(plain(root), "picture: prop:PALLET has no 256 px picker picture")


def test_a_picker_picture_of_the_wrong_size(pack, tmp_path):
    root = copy(pack, tmp_path)
    os.remove(root / "pictures/prop.PALLET.jpg")
    png(str(root / "pictures/prop.PALLET.png"), 128, 128)
    d = load(root)
    row(d, "prop:PALLET")["picture"] = "pictures/prop.PALLET.png"
    save(root, d)
    rehash(root)
    has(plain(root), "picture: pictures/prop.PALLET.png", "128 x 128 px, not 256 px")


def test_a_4k_picture_for_a_material(pack, tmp_path):
    root = copy(pack, tmp_path)
    png(str(root / "textures/4k/test_cast_iron_colour_v1.png"), 4096, 4096)
    d = load(root)
    row(d, "material:cast_iron")["textures"].append("textures/4k/test_cast_iron_colour_v1.png")
    save(root, d)
    rehash(root)
    has(plain(root), "picture size: textures/4k/test_cast_iron_colour_v1.png", "4k only for 360° photos")


def test_a_1k_picture_without_its_2k_variant(pack, tmp_path):
    root = copy(pack, tmp_path)
    png(str(root / "textures/1k/test_extra.png"), 1024, 1024)
    d = load(root)
    row(d, "material:cast_iron")["textures"].append("textures/1k/test_extra.png")
    save(root, d)
    rehash(root)
    has(plain(root), "picture size: textures/1k/test_extra.png", "no 2k variant")


def test_a_picture_larger_than_its_folder_says(pack, tmp_path):
    root = copy(pack, tmp_path)
    os.remove(root / "textures/1k/test_concrete_colour_v1.jpg")
    png(str(root / "textures/1k/test_concrete_colour_v1.jpg"), 2048, 2048)     # a PNG under a .jpg name is read too
    rehash(root)
    has(plain(root), "picture size: textures/1k/test_concrete_colour_v1.jpg", "more than its 1k")


def exr_head(path, w, h):
    """Only an OpenEXR head (magic, version, dataWindow): what the plain checks read."""
    import struct
    box = struct.pack("<iiii", 0, 0, w - 1, h - 1)
    data = b"\x76\x2f\x31\x01" + struct.pack("<I", 2) + b"dataWindow\0box2i\0" + struct.pack("<i", 16) + box + b"\0"
    with open(path, "wb") as f:
        f.write(data)


def test_a_360_photo_that_is_not_2_to_1(pack, tmp_path):
    root = copy(pack, tmp_path)
    exr_head(str(root / "hdri/test_hall_1k.exr"), 1024, 1024)
    rehash(root)
    has(plain(root), "picture size: hdri/test_hall_1k.exr", "not 2:1")


# ---------------------------------------------------------------------------------------------- sizes, cost

def test_a_set_above_its_budget(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    d["sets"]["test"]["budget_mb"] = 1
    save(root, d)
    has(plain(root), "size: Set 'test'", "above its budget of 1 MB")


def test_a_pack_above_300_mb_is_a_warning(pack, tmp_path, monkeypatch):
    monkeypatch.setattr(ap, "TOTAL_WARN_MB", 1)
    rep = plain(pack)
    assert rep.ok and any("above the planned 1 MB" in w for w in rep.warnings), rep.lines()


def test_a_look_without_its_render_time(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "material:cast_iron")["cost"] = 0
    save(root, d)
    has(plain(root), "render time: material:cast_iron says no 'cost'")


def test_a_look_slower_than_1_3_without_the_owners_ok(pack, tmp_path):
    root = copy(pack, tmp_path)
    d = load(root)
    row(d, "material:cast_iron")["cost"] = 1.6
    save(root, d)
    has(plain(root), "material:cast_iron", "left out by the app", "1.6 x", "without the owner's OK")
    row(d, "material:cast_iron")["approved_slower"] = "2026-12-01"
    save(root, d)
    assert plain(root).ok


# ---------------------------------------------------------------------------------------------- the pin

PIN = {"version": "1.0.0", "tag": "assets-1.0.0", "file": "FresingAssets-1.0.0.zip",
       "url": "https://github.com/smholte/CAD-render-animation/releases/download/assets-1.0.0/FresingAssets-1.0.0.zip",
       "sha256": "a" * 64, "bytes": 1234, "licence_id": "fresing-assets-1.0"}


def _pin(tmp_path, **change):
    p = tmp_path / "assets_pin.json"
    p.write_text(json.dumps({**PIN, **change}))
    return str(p)


def test_a_good_pin_prints_its_values(tmp_path, capsys):
    assert ac.main(["--pin", _pin(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert f"url={PIN['url']}" in out and "sha256=" + "a" * 64 in out and "version=1.0.0" in out


@pytest.mark.parametrize("change, words", [
    ({"tag": "v1.0.0"}, "tag"),
    ({"url": "https://example.com/FresingAssets-1.0.0.zip"}, "url"),
    ({"file": "fresing_render-1.0.0.zip"}, "file"),
    ({"sha256": "XYZ"}, "sha256"),
    ({"version": "1.0"}, "version"),
])
def test_a_wrong_pin(tmp_path, change, words):
    _p, problems = ac.read_pin(_pin(tmp_path, **change))
    assert any(p.startswith(f"pin: {words}") for p in problems), problems


# ---------------------------------------------------------------------------------------------- in Blender

BREAK = textwrap.dedent(r'''
    import os, shutil, sys
    import bpy
    good, base = sys.argv[1], sys.argv[2]

    def case(name, rel, edit):
        dst = os.path.join(base, name, "Fresing Assets")
        shutil.copytree(good, dst)
        path = os.path.join(dst, rel)
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
        edit(dst)
        bpy.ops.wm.save_as_mainfile(filepath=path)

    def group(name="FRP paint_satin"):
        return bpy.data.node_groups[name]

    def text(dst):
        bpy.data.texts.new("hello.py").write("print('hi')\n")
        bpy.data.texts["hello.py"].use_fake_user = True

    def py_driver(dst):
        nd = next(n for n in group().nodes if n.bl_idname == "ShaderNodeValue")
        fc = nd.outputs[0].driver_add("default_value")
        fc.driver.type = "SCRIPTED"
        fc.driver.expression = "__import__('os').getpid() * 0"

    def script_node(dst):
        group().nodes.new("ShaderNodeScript")

    def linked(dst):
        other = os.path.join(dst, "materials", "cast_iron.blend")
        with bpy.data.libraries.load(other, link=True, relative=True) as (src, to):
            to.node_groups = ["FRP cast_iron"]
        n = group().nodes.new("ShaderNodeGroup")
        n.node_tree = bpy.data.node_groups["FRP cast_iron"]

    def renamed(dst):
        group().name = "FRP paint_matte"

    def packed(dst):
        for img in bpy.data.images:
            img.pack()

    def no_roughness(dst):
        ng = group()
        ng.interface.remove(next(s for s in ng.interface.items_tree if s.name == "Roughness"
                                 and s.in_out == "OUTPUT"))

    def bsdf(dst):
        group().nodes.new("ShaderNodeBsdfDiffuse")

    def finish_blind(dst):
        for nd in group("FRP knurl_diamond").nodes:
            if nd.bl_idname == "ShaderNodeAttribute":
                nd.attribute_name = "something_else"

    def prop_no_lod(dst):
        me = bpy.data.objects["FRP PALLET"].data
        me.attributes.remove(me.attributes["fr_lod"])

    def prop_floating(dst):
        for v in bpy.data.objects["FRP PALLET"].data.vertices:
            v.co.z += 0.05

    def env_empty(dst):
        col = bpy.data.collections["FRP FACTORY"]
        for ob in list(col.objects):
            col.objects.unlink(ob)
            ob.use_fake_user = True

    def black(dst):
        ng = group()
        go = next(n for n in ng.nodes if n.bl_idname == "NodeGroupOutput")
        rgb = ng.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (0, 0, 0, 1)
        ng.links.new(rgb.outputs[0], go.inputs["Colour"])
        one = ng.nodes.new("ShaderNodeValue")
        one.outputs[0].default_value = 1.0
        ng.links.new(one.outputs[0], go.inputs["Metallic"])

    for name, rel, edit in (("text", "materials/paint_satin.blend", text),
                            ("py_driver", "materials/paint_satin.blend", py_driver),
                            ("script_node", "materials/paint_satin.blend", script_node),
                            ("linked", "materials/paint_satin.blend", linked),
                            ("renamed", "materials/paint_satin.blend", renamed),
                            ("packed", "materials/cast_iron.blend", packed),
                            ("no_roughness", "materials/paint_satin.blend", no_roughness),
                            ("bsdf", "materials/paint_satin.blend", bsdf),
                            ("finish_blind", "finishes/knurl_diamond.blend", finish_blind),
                            ("prop_no_lod", "props/PALLET.blend", prop_no_lod),
                            ("prop_floating", "props/PALLET.blend", prop_floating),
                            ("env_empty", "environments/FACTORY.blend", env_empty),
                            ("black", "materials/paint_satin.blend", black)):
        case(name, rel, edit)
    print("BROKEN-DONE")
''')


@pytest.fixture(scope="module")
def broken(pack, tmp_path_factory):
    """Copies of the test pack, each with one .blend broken on purpose (and pack.json's list made right again)."""
    base = tmp_path_factory.mktemp("assets_broken")
    script = base / "break.py"
    script.write_text(BREAK, encoding="utf-8")
    p = subprocess.run([sys.executable, str(script), str(pack), str(base)], capture_output=True, text=True,
                       timeout=600)
    assert p.returncode == 0 and "BROKEN-DONE" in p.stdout, p.stdout[-3000:] + p.stderr[-3000:]

    def get(name):
        root = base / name / "Fresing Assets"
        for junk in root.rglob("*.blend1"):
            junk.unlink()
        rehash(root)
        return root
    return get


def blend(root, render=False):
    return ac.check(str(root), APP, render=render)


def test_a_text_datablock(broken):
    has(blend(broken("text")), "data only: materials/paint_satin.blend holds a Text datablock")


def test_a_python_driver(broken):
    has(blend(broken("py_driver")), "data only: materials/paint_satin.blend has a Python driver")


def test_an_osl_script_node(broken):
    rep = blend(broken("script_node"))
    has(rep, "data only:", "OSL Script node in FRP paint_satin")
    has(rep, "contract: material:paint_satin", "ShaderNodeScript")


def test_a_link_to_another_file(broken):
    has(blend(broken("linked")), "data only: materials/paint_satin.blend links to another file")


def test_the_listed_datablock_is_missing(broken):
    has(blend(broken("renamed")), "blend: materials/paint_satin.blend holds no node group named 'FRP paint_satin'")


def test_a_packed_picture(broken):
    has(blend(broken("packed")), "pictures: materials/cast_iron.blend packs the picture")


def test_a_group_without_a_contract_socket(broken):
    has(blend(broken("no_roughness")), "contract: material:paint_satin", "lacks the socket(s) Roughness")


def test_a_bsdf_inside_a_group(broken):
    has(blend(broken("bsdf")), "contract: material:paint_satin", "ShaderNodeBsdfDiffuse node inside")


def test_a_finish_that_reads_no_face_data(broken):
    rep = blend(broken("finish_blind"))
    has(rep, "contract: finish:knurl_diamond", "reads none of its face data")
    has(rep, "contract: finish:knurl_diamond", "pixel angle")


def test_a_prop_without_its_levels(broken):
    has(blend(broken("prop_no_lod")), "contract: prop:PALLET", "fr_lod")


def test_a_prop_above_the_floor(broken):
    has(blend(broken("prop_floating")), "contract: prop:PALLET", "not on the floor")


def test_an_empty_environment(broken):
    has(blend(broken("env_empty")), "contract: environment:FACTORY", "holds no objects")


def test_a_missing_picture_renders_pink(pack, tmp_path):
    root = copy(pack, tmp_path)
    os.remove(root / "textures/2k/test_cast_iron_colour_v1.jpg")
    rep = ac.check(str(root), APP)
    has(rep, "render: material:cast_iron", "renders pink")
    has(rep, "append: material:cast_iron", "cannot be read after the append")


def test_a_black_look(broken):
    has(blend(broken("black"), render=True), "render: material:paint_satin", "renders black")


# ---------------------------------------------------------------------------------------------- a release (--fetch)

def _release(pack_zip, prerelease=True, licence=True, listing=None):
    data = open(pack_zip, "rb").read()
    files = {"FresingAssets-1.0.0.zip": data}
    if licence:
        files["LICENSE-ASSETS.txt"] = b"licence"
    if listing is not None:
        files["assets.json"] = json.dumps(listing).encode()
    rel = {"tag_name": "assets-1.0.0", "prerelease": prerelease,
           "assets": [{"name": n, "browser_download_url": f"https://dl/{n}"} for n in files]}

    def get(url, binary=False):
        if url.endswith("/releases/tags/assets-1.0.0"):
            return rel
        return files[url.rsplit("/", 1)[1]]
    return get, data


def test_fetch_takes_the_releases_zip_and_checks_its_listing(pack, tmp_path):
    z = tmp_path / "FresingAssets-1.0.0.zip"
    shutil.make_archive(str(z)[:-4], "zip", pack.parent, ap.FOLDER)
    data = z.read_bytes()
    listing = {"version": "1.0.0", "file": z.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    get, _ = _release(z, listing=listing)
    path, problems = ac.fetch("assets-1.0.0", str(tmp_path / "got"), get)
    assert problems == [] and open(path, "rb").read() == data
    assert ac.check(path, APP, use_blender=False).ok

    get, _ = _release(z, prerelease=False, licence=False, listing={**listing, "sha256": "0" * 64})
    _path, problems = ac.fetch("assets-1.0.0", str(tmp_path / "got2"), get)
    assert any("is not a pre-release" in p for p in problems)
    assert any("no LICENSE-ASSETS.txt" in p for p in problems)
    assert any("assets.json says sha256" in p for p in problems)
    assert ac.fetch("v0.2.270", str(tmp_path), get)[1][0].startswith("release: 'v0.2.270' is not a pack's tag")
