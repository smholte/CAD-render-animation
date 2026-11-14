"""Task 0117: the mesh reader (glTF / GLB, OBJ, FBX through Blender) writes the STEP reader's cache. No Blender here,
except the FBX test, which uses this Python's bpy module as the converter."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_mesh as maker  # noqa: E402
from fresing_render.importer import mesh_reader, runner, step_reader  # noqa: E402

DATA = os.path.join(HERE, "data")
CRANE = os.path.join(DATA, "test_mesh_crane.glb")
CRANE_B = os.path.join(DATA, "test_mesh_crane_b.glb")
SINGLE = os.path.join(DATA, "test_mesh_single.glb")
OBJ = os.path.join(DATA, "test_mesh_parts.obj")


def read(path, tmp_path, name="c", **kw):
    out = str(tmp_path / name)
    info = mesh_reader.read_mesh(path, out, **kw)
    return info, np.load(os.path.join(out, "meshes.npz")), out


def node(info, name):
    hits = [n for n in info["nodes"] if n["name"] == name]
    assert hits, name
    return hits[0]


def world(info, k):
    m = np.eye(4)
    while k >= 0:
        n = info["nodes"][k]
        m = (np.array(n["matrix"]) if n["matrix"] else np.eye(4)) @ m
        k = n["parent"]
    return m


# ---- the test models ---------------------------------------------------------

def test_the_test_models_are_made_by_the_maker(tmp_path):
    maker.main([str(tmp_path)])
    for name in maker.files():
        with open(tmp_path / name, "rb") as a, open(os.path.join(DATA, name), "rb") as b:
            assert a.read() == b.read(), f"run python tools/make_test_mesh.py ({name})"
    for name in maker.SHIPPED:
        with open(os.path.join(ROOT, "fresing_render", "data", name), "rb") as a, \
                open(os.path.join(DATA, name), "rb") as b:
            assert a.read() == b.read(), f"copy tests/data/{name} to fresing_render/data/"


# ---- glTF ----------------------------------------------------------------------

def test_gltf_tree_names_instancing_colours_and_the_cache(tmp_path):
    info, arr, out = read(CRANE, tmp_path)
    assert info["version"] == step_reader.CACHE_VERSION and info["units"] == "m" and info["source_kind"] == "mesh"
    names = [n["name"] for n in info["nodes"]]
    assert names[0] == "MESH CRANE" and info["nodes"][0]["kind"] == "assembly"
    for name in ("BASE", "SLEWING RING", "BOOM", "BOOM PIN", "WHEEL FL", "WHEEL RR"):
        assert node(info, name)["kind"] == "part", name
    assert node(info, "TURRET")["kind"] == "assembly"
    # the cab is one mesh of two primitives (materials): an assembly with a part per material
    cab = node(info, "CAB")
    kids = [n for n in info["nodes"] if n["parent"] == info["nodes"].index(cab)]
    assert cab["kind"] == "assembly" and sorted(k["name"] for k in kids) == ["Glass", "Yellow paint"]
    # four wheels, one mesh (instancing)
    wheels = [n for n in info["nodes"] if n["name"].startswith("WHEEL")]
    assert len(wheels) == 4 and len({w["mesh"] for w in wheels}) == 1
    assert info["stats"]["unique_parts"] == 7 and info["stats"]["placed_parts"] == 10
    # uids as the STEP reader makes them
    assert node(info, "BOOM")["uid"] == "MESH CRANE#1/TURRET#1/BOOM#1"
    # colours: baseColorFactor (linear) -> sRGB, material name for the rules
    boom = node(info, "BOOM")
    assert boom["material"] == "Yellow paint"
    assert np.allclose(boom["color"], [mesh_reader._srgb(c) for c in (0.85, 0.55, 0.02)], atol=1e-4)
    for n in info["nodes"]:
        if n["kind"] == "part":
            mid = n["mesh"]
            p, t = arr[f"p{mid}"], arr[f"t{mid}"]
            assert p.dtype == np.float32 and t.dtype == np.int32 and t.max() < len(p)
            assert np.allclose(np.linalg.norm(arr[f"n{mid}"], axis=1), 1.0, atol=1e-3)
            f = arr[f"f{mid}"]
            assert f[0] == 0 and f[-1] == len(t) and (np.diff(f) > 0).all()


def test_gltf_y_up_comes_in_z_up_in_metres(tmp_path):
    info, arr, _ = read(CRANE, tmp_path)
    ring = node(info, "SLEWING RING")
    p = arr[f"p{ring['mesh']}"]
    w = world(info, info["nodes"].index(ring))
    pw = p @ w[:3, :3].T + w[:3, 3]
    assert np.allclose(pw.min(axis=0), [-0.8, -0.8, 0.40], atol=1e-3)     # the app's coordinates: Z up
    assert np.allclose(pw.max(axis=0), [0.8, 0.8, 0.55], atol=1e-3)
    # a wheel: placed at its node, turned so its axis lies along Y; RL/RR mirrored by a negative scale
    for name, (x, y, z, side) in maker.WHEELS.items():
        k = info["nodes"].index(node(info, name))
        m = world(info, k)
        assert np.allclose(m[:3, 3], (x, y, z), atol=1e-6)
        assert np.sign(np.linalg.det(m[:3, :3])) == side
        assert abs(abs((m[:3, :3] @ [0, 0, 1])[1]) - 1.0) < 1e-6           # the wheel's own Z along the app's Y


def test_gltf_material_texture_uvs_and_credit(tmp_path):
    info, arr, out = read(CRANE, tmp_path)
    mats = {m["name"]: m for m in info["materials"]}
    steel = mats["Base steel"]
    assert steel["base_texture"].startswith("textures/") and os.path.isfile(os.path.join(out, steel["base_texture"]))
    with open(os.path.join(out, steel["base_texture"]), "rb") as fh:
        assert fh.read(8) == b"\x89PNG\r\n\x1a\n"
    assert mats["Glass"]["alpha"] == pytest.approx(0.4)
    base = node(info, "BASE")
    meta = info["meshes"][base["mesh"]]
    assert info["materials"][meta["file_material"]]["name"] == "Base steel"
    uv = arr[f"u{base['mesh']}"]
    assert uv.shape == (len(arr[f"p{base['mesh']}"]), 2) and uv.min() >= -1e-6 and uv.max() <= 2.0 + 1e-6
    assert "Mesh crane (test model)" in info["credit"] and "Fresing test models" in info["credit"]
    assert "CC BY 4.0" in info["credit"] and "\n" not in info["credit"]


def test_a_licence_file_next_to_the_model_is_the_credit(tmp_path):
    folder = tmp_path / "dl"
    folder.mkdir()
    shutil.copy(SINGLE, folder / "scene.glb")
    (folder / "license.txt").write_text(
        "Model Information:\n* title:\tWorking boat\n* source:\thttps://example.org/boat\n\n"
        "Model License:\n* license type:\tCC-BY-4.0\n* requirements:\tAuthor must be credited.\n\n"
        "This work is based on \"Working boat\" by Someone (https://example.org/someone) licensed under CC-BY-4.0\n",
        encoding="utf-8")
    info, _, _ = read(str(folder / "scene.glb"), tmp_path)
    assert "licensed under CC-BY-4.0" in info["credit"] and "Working boat" in info["credit"]
    assert "Author must be credited" in info["credit_text"] and len(info["credit_text"]) <= mesh_reader.CREDIT_MAX


def test_one_mesh_is_split_by_loose_parts(tmp_path):
    info, arr, _ = read(SINGLE, tmp_path)
    assert info["options"]["split"] is True                                   # Auto: 1 mesh in the file
    parts = [n for n in info["nodes"] if n["kind"] == "part"]
    assert len(parts) == 5 and {n["name"] for n in parts} == {f"WELDMENT {k}" for k in range(1, 6)}
    assert parts[0]["name"] == "WELDMENT 1"
    sizes = [np.ptp(arr[f"p{n['mesh']}"], axis=0).prod() for n in parts]
    assert sizes[0] == max(sizes)                                               # the plate first (biggest)
    info, _, _ = read(SINGLE, tmp_path, "off", split="off")
    assert sum(1 for n in info["nodes"] if n["kind"] == "part") == 1


def test_no_normals_gives_flat_normals(tmp_path):
    info, arr, _ = read(SINGLE, tmp_path, split="off")
    mid = next(n["mesh"] for n in info["nodes"] if n["kind"] == "part")
    p, t, n = arr[f"p{mid}"], arr[f"t{mid}"], arr[f"n{mid}"]
    fn = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True)
    for k in range(3):
        assert np.allclose(n[t[:, k]], fn, atol=1e-4)


def test_split_meshes_with_many_pieces_keep_the_small_ones_together(tmp_path, monkeypatch):
    monkeypatch.setattr(mesh_reader, "MAX_PIECES", 3)
    info, _, _ = read(SINGLE, tmp_path)
    parts = [n["name"] for n in info["nodes"] if n["kind"] == "part"]
    assert parts == ["WELDMENT 1", "WELDMENT 2", "WELDMENT small pieces"]
    assert any("small pieces" in note for note in info["notes"])


# ---- OBJ -------------------------------------------------------------------------

def test_obj_objects_materials_ngons_units_guess(tmp_path):
    info, arr, out = read(OBJ, tmp_path)
    assert info["options"]["units"] == "mm" and any("units guessed: mm" in n for n in info["notes"])
    assert {n["name"] for n in info["nodes"] if n["parent"] < 0} == {"Frame", "Cover", "Pipe"}
    frame = node(info, "Frame")
    p = arr[f"p{frame['mesh']}"]
    assert np.allclose(np.ptp(p, axis=0), [1.2, 0.2, 0.4], atol=1e-4)           # mm -> m, Y up -> Z up
    assert frame["material"] == "Steel"
    assert np.allclose(frame["color"], [mesh_reader._srgb(c) for c in (0.55, 0.56, 0.58)], atol=1e-4)
    cover = node(info, "Cover")
    kids = {n["name"]: n for n in info["nodes"] if n["parent"] == info["nodes"].index(cover)}
    assert set(kids) == {"Blue", "Tile"}
    assert len(arr[f"t{kids['Blue']['mesh']}"]) == 4                         # a hexagon: 4 triangles
    tile = info["materials"][info["meshes"][kids["Tile"]["mesh"]]["file_material"]]
    assert tile["base_texture"].endswith(".png") and os.path.isfile(os.path.join(out, tile["base_texture"]))
    assert f"u{kids['Tile']['mesh']}" in arr
    info, arr, _ = read(OBJ, tmp_path, "m", units="m")
    assert info["options"]["units"] == "m" and not any("guessed" in n for n in info["notes"])
    assert np.ptp(arr[f"p{node(info, 'Frame')['mesh']}"], axis=0).max() == pytest.approx(1200.0, rel=1e-5)
    info, arr, _ = read(OBJ, tmp_path, "z", up="z")
    assert np.allclose(np.ptp(arr[f"p{node(info, 'Frame')['mesh']}"], axis=0), [1.2, 0.4, 0.2], atol=1e-4)


def test_obj_with_a_missing_mtl_and_texture_still_reads(tmp_path):
    shutil.copy(OBJ, tmp_path / "a.obj")
    info, _, _ = read(str(tmp_path / "a.obj"), tmp_path, "x")
    assert any("test_mesh_parts.mtl" in n and "missing" in n for n in info["notes"])
    assert sum(1 for n in info["nodes"] if n["kind"] == "part") == 4


# ---- errors ----------------------------------------------------------------------

@pytest.mark.parametrize("data, words", [
    (b"", "not a glTF"), (b"glTF\x01\x00\x00\x00", "cut off"),
    (b'{"asset": {"version": "1.0"}}', "only glTF 2.0"),
    (b'{"asset": {"version": "2.0"}, "extensionsRequired": ["KHR_magic"]}', "KHR_magic"),
    (b'{"asset": {"version": "2.0"}}', "no faces"),
])
def test_broken_gltf_says_why(tmp_path, data, words):
    p = tmp_path / "x.gltf"
    p.write_bytes(data)
    with pytest.raises(mesh_reader.MeshError) as e:
        mesh_reader.read_mesh(str(p), str(tmp_path / "o"))
    assert words in str(e.value)


def test_the_reader_program_reports_errors_as_a_line(tmp_path):
    p = tmp_path / "x.glb"
    p.write_bytes(b"nonsense")
    out = subprocess.run([sys.executable, os.path.join(ROOT, "fresing_render", "importer", "mesh_reader.py"),
                          str(p), str(tmp_path / "o")], capture_output=True, text=True, timeout=60)
    assert out.returncode == 1
    last = json.loads(out.stdout.strip().splitlines()[-1])
    assert last["stage"] == "error" and "glTF" in last["msg"]


# ---- the job runner ------------------------------------------------------------------

def run_job(job, timeout=120):
    job.start()
    t0 = time.time()
    while not job.poll():
        time.sleep(0.05)
        assert time.time() - t0 < timeout
    return job


def test_runner_picks_the_mesh_reader_and_keeps_options_in_the_cache_key(tmp_path):
    a = runner.ImportJob(CRANE, "normal", str(tmp_path))
    assert a.mesh and a.quality == "mesh" and a.command()[1] == runner.MESH_READER
    assert run_job(a).error is None and runner.cache_is_valid(a.cache_dir)
    b = runner.ImportJob(OBJ, "normal", str(tmp_path), {"units": "mm"})
    c = runner.ImportJob(OBJ, "normal", str(tmp_path), {"units": "m"})
    assert b.cache_dir != c.cache_dir
    # STEP keys are what they were (stored imports stay valid)
    step = os.path.join(DATA, "test_machine.step")
    assert runner.ImportJob(step, "draft", str(tmp_path)).cache_dir == runner.cache_dir_for(step, "draft", str(tmp_path))


def test_two_imports_of_the_same_new_file_at_once(tmp_path):
    """Bug hunt 0118 row 14: two imports started together each write their own folder; both end with a valid
    cache, and the one that comes second uses the first one's."""
    src = tmp_path / "same.glb"
    shutil.copy(CRANE, src)
    root = str(tmp_path / "cache")
    jobs = [runner.ImportJob(str(src), "normal", root) for _ in range(2)]
    assert jobs[0].tmp_dir != jobs[1].tmp_dir and jobs[0].cache_dir == jobs[1].cache_dir
    for j in jobs:
        j.start()
    t0 = time.time()
    while not all(j.poll() for j in jobs):
        time.sleep(0.05)
        assert time.time() - t0 < 120
    for j in jobs:
        assert j.error is None and runner.cache_is_valid(j.cache_dir)
        assert not os.path.exists(j.tmp_dir)
    assert os.listdir(root) == [os.path.basename(jobs[0].cache_dir)]


def test_two_step_imports_at_once(tmp_path):
    pytest.importorskip("OCP")
    src = tmp_path / "m.step"
    shutil.copy(os.path.join(DATA, "test_machine.step"), src)
    root = str(tmp_path / "cache")
    jobs = [runner.ImportJob(str(src), "draft", root) for _ in range(2)]
    errors = []

    def go(j):
        try:
            run_job(j)
        except AssertionError as exc:
            errors.append(exc)
    threads = [threading.Thread(target=go, args=(j,)) for j in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and all(j.error is None and runner.cache_is_valid(j.cache_dir) for j in jobs)
    assert os.listdir(root) == [os.path.basename(jobs[0].cache_dir)]


def test_stale_half_written_folders_are_cleared(tmp_path):
    root = str(tmp_path / "cache")
    job = runner.ImportJob(CRANE, "normal", root)
    os.makedirs(job.cache_dir + ".partial")                       # the name before 0117
    old = job.cache_dir + ".partial-99999-1"
    os.makedirs(old)
    young = job.cache_dir + ".partial-99998-1"
    os.makedirs(young)
    t = time.time() - runner.STALE_PARTIAL_S - 10
    os.utime(old, (t, t))
    run_job(job)
    left = sorted(os.listdir(root))
    assert left == sorted([os.path.basename(job.cache_dir), os.path.basename(young)])


# ---- FBX (Blender's own importer; this Python's bpy module stands in for Blender) ----------

def test_fbx_through_blender(tmp_path):
    pytest.importorskip("bpy")
    fbx = tmp_path / "crane.fbx"
    script = (
        "import bpy, sys\n"
        "bpy.ops.wm.read_factory_settings(use_empty=True)\n"
        f"bpy.ops.import_scene.gltf(filepath={CRANE!r})\n"
        f"bpy.ops.export_scene.fbx(filepath={str(fbx)!r}, path_mode='COPY', embed_textures=True)\n")
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, timeout=300)
    info, arr, out = read(str(fbx), tmp_path, converter=sys.executable)
    assert info["options"]["format"] == "fbx" and any("FBX" in n for n in info["notes"])
    names = {n["name"] for n in info["nodes"]}
    assert {"BASE", "SLEWING RING", "BOOM", "WHEEL FL"} <= names
    ring = node(info, "SLEWING RING")
    w = world(info, info["nodes"].index(ring))
    p = arr[f"p{ring['mesh']}"] @ w[:3, :3].T + w[:3, 3]
    assert np.allclose(p.min(axis=0), [-0.8, -0.8, 0.40], atol=2e-3)         # metres, Z up after the round trip
    assert np.allclose(p.max(axis=0), [0.8, 0.8, 0.55], atol=2e-3)
    assert not os.path.exists(os.path.join(out, "converted.glb"))


def test_fbx_without_a_converter_says_so(tmp_path):
    p = tmp_path / "x.fbx"
    p.write_bytes(b"Kaydara FBX Binary  \x00")
    with pytest.raises(mesh_reader.MeshError) as e:
        mesh_reader.read_mesh(str(p), str(tmp_path / "o"))
    assert "Blender" in str(e.value)
