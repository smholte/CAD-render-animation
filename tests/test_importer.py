"""The STEP reader and the background job runner, without Blender."""

import json
import os
import time

import numpy as np
import pytest

pytest.importorskip("OCP")

from fresing_render.importer import runner, step_reader  # noqa: E402

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")


def test_reader_output(tmp_path):
    info = step_reader.read_step(STEP, str(tmp_path), "draft")
    nodes = info["nodes"]
    assert info["stats"]["unique_parts"] == 6
    assert info["stats"]["placed_parts"] == 11
    names = [n["name"] for n in nodes]
    assert names[0] == "TEST.MACHINE"
    frame = next(n for n in nodes if n["name"] == "FRAME")
    assert frame["color"] == [0.976, 0.659, 0.0] or tuple(frame["color"]) == (0.976, 0.659, 0.0)
    arrays = np.load(tmp_path / "meshes.npz")
    p = arrays[f"p{frame['mesh']}"]
    assert np.allclose(p.max(axis=0) - p.min(axis=0), [1.0, 0.6, 0.05], atol=1e-4)
    n = arrays[f"n{frame['mesh']}"]
    assert np.allclose(np.linalg.norm(n, axis=1), 1.0, atol=1e-3)
    t = arrays[f"t{frame['mesh']}"]
    assert t.max() < len(p)
    # placement of a component is a translation in metres
    bolts = [n for n in nodes if n["name"].startswith("ISO 4017")]
    assert len(bolts) == 4 and len({b["mesh"] for b in bolts}) == 1
    xs = sorted(round(b["matrix"][0][3], 3) for b in bolts)
    assert xs == [0.05, 0.05, 0.95, 0.95]


def test_quality_changes_detail(tmp_path):
    draft = step_reader.read_step(STEP, str(tmp_path / "d"), "draft")["stats"]["triangles_unique"]
    fine = step_reader.read_step(STEP, str(tmp_path / "f"), "fine")["stats"]["triangles_unique"]
    assert fine > draft


def test_job_runs_in_background_and_caches(tmp_path):
    job = runner.ImportJob(STEP, "draft", str(tmp_path))
    assert not job.cached
    job.start()
    t0 = time.time()
    while not job.poll():
        assert time.time() - t0 < 120
        time.sleep(0.1)
    assert job.error is None, job.error
    assert job.cached
    with open(os.path.join(job.cache_dir, "tree.json")) as fh:
        assert json.load(fh)["stats"]["placed_parts"] == 11
    # same file + quality -> same cache; other quality -> other cache
    assert runner.ImportJob(STEP, "draft", str(tmp_path)).cache_dir == job.cache_dir
    assert runner.ImportJob(STEP, "fine", str(tmp_path)).cache_dir != job.cache_dir


def test_job_reports_bad_file(tmp_path):
    bad = tmp_path / "broken.step"
    bad.write_text("this is not a STEP file")
    job = runner.ImportJob(str(bad), "draft", str(tmp_path / "cache"))
    job.start()
    t0 = time.time()
    while not job.poll():
        assert time.time() - t0 < 60
        time.sleep(0.1)
    assert job.error
    assert not job.cached


# ---- meshing on all cores (helper processes) -------------------------------------------

CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")


def _write_face_colour_step(path):
    """A grey plate with one red face, and a part made of two bodies."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_sRGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_StepModelType
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool
    from OCP.gp import gp_Pnt, gp_Trsf, gp_Vec
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
    app.InitDocument(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ct = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())

    def rgb(r, g, b):
        return Quantity_Color(r, g, b, Quantity_TOC_sRGB)

    plate = BRepPrimAPI_MakeBox(gp_Pnt(0, 0, 0), 400.0, 300.0, 20.0).Shape()
    lab = st.AddShape(plate, False)
    TDataStd_Name.Set_s(lab, TCollection_ExtendedString("PLATE"))
    ct.SetColor(lab, rgb(0.5, 0.5, 0.5), XCAFDoc_ColorType.XCAFDoc_ColorSurf)
    exp = TopExp_Explorer(plate, TopAbs_FACE)
    exp.Next()                                   # the second face gets its own colour
    sub = st.AddSubShape(lab, exp.Current())
    ct.SetColor(sub, rgb(0.8, 0.1, 0.1), XCAFDoc_ColorType.XCAFDoc_ColorSurf)

    comp = TopoDS_Compound()
    bld = BRep_Builder()
    bld.MakeCompound(comp)
    bld.Add(comp, BRepPrimAPI_MakeCylinder(30.0, 100.0).Shape())
    bld.Add(comp, BRepPrimAPI_MakeBox(gp_Pnt(100, 0, 0), 50.0, 50.0, 50.0).Shape())
    two = st.AddShape(comp, False)
    TDataStd_Name.Set_s(two, TCollection_ExtendedString("TWO.BODIES"))

    root = st.NewShape()
    TDataStd_Name.Set_s(root, TCollection_ExtendedString("FACE.COLOURS"))
    st.AddComponent(root, lab, TopLoc_Location())
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(0, 0, 200))
    st.AddComponent(root, two, TopLoc_Location(t))
    st.UpdateAssemblies()
    w = STEPCAFControl_Writer()
    w.SetColorMode(True)
    w.SetNameMode(True)
    w.Transfer(doc, STEPControl_StepModelType.STEPControl_AsIs)
    assert w.Write(str(path)) == IFSelect_RetDone


def _same_cache(a, b):
    with open(os.path.join(a, "tree.json")) as fh:
        ta = json.load(fh)
    with open(os.path.join(b, "tree.json")) as fh:
        tb = json.load(fh)
    assert ta["nodes"] == tb["nodes"]
    assert ta["meshes"] == tb["meshes"]
    za, zb = np.load(os.path.join(a, "meshes.npz")), np.load(os.path.join(b, "meshes.npz"))
    assert sorted(za.files) == sorted(zb.files)
    # Meshing in another process may order the triangles of a face differently (OpenCascade
    # walks some maps in memory-address order): same counts, same places, same colours.
    for k in za.files:
        x, y = za[k], zb[k]
        assert x.shape == y.shape and x.dtype == y.dtype, k
        if k[0] == "p":
            assert np.allclose(np.sort(x, axis=0), np.sort(y, axis=0), atol=1e-5), k
        elif k[0] == "c":
            assert np.array_equal(np.bincount(x + 1), np.bincount(y + 1)), k
    return ta


@pytest.mark.parametrize("which", ["crane", "face_colours"])
def test_helpers_give_the_same_cache(tmp_path, which, capsys):
    step = CRANE_B
    if which == "face_colours":
        step = str(tmp_path / "fc.step")
        _write_face_colour_step(step)
    one = step_reader.read_step(step, str(tmp_path / "one"), "normal", workers=0)
    two = step_reader.read_step(step, str(tmp_path / "two"), "normal", workers=2)
    assert one["stats"]["mesh_helpers"] == 0 and two["stats"]["mesh_helpers"] == 2
    info = _same_cache(str(tmp_path / "one"), str(tmp_path / "two"))
    if which == "face_colours":
        plate = next(m for m in info["meshes"] if m["name"] == "PLATE")
        assert [0.8, 0.1, 0.1] in plate["palette"]
        mid = info["meshes"].index(plate)
        cols = np.load(str(tmp_path / "two" / "meshes.npz"))[f"c{mid}"]
        red = plate["palette"].index([0.8, 0.1, 0.1])
        assert (cols == red).sum() == 2                   # one box face = two triangles
        node = next(n for n in info["nodes"] if n["name"] == "PLATE")
        assert node["color"] == [0.5, 0.5, 0.5]           # the part keeps its own colour
        assert "Could not mesh" not in capsys.readouterr().out


def test_located_faces_are_transformed_like_opencascade():
    """Faces of a moved (and of a mirrored) shape: numpy transform == OpenCascade's own per-node transform."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.TopLoc import TopLoc_Location
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    occ = step_reader._occ()
    lin, ang = step_reader.QUALITY["normal"]
    rot = gp_Trsf()
    rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 1, 0)), 0.7)
    rot.SetTranslationPart(gp_Vec(120.0, -40.0, 15.0))
    mirror = gp_Trsf()
    mirror.SetMirror(gp_Ax2(gp_Pnt(10, 0, 0), gp_Dir(1, 0, 0)))
    for trsf in (rot, mirror):
        shape = BRepPrimAPI_MakeCylinder(25.0, 80.0).Shape().Moved(TopLoc_Location(trsf))
        pos, nrm, tri, _tc, _pal = step_reader._mesh_shape(occ, shape, lin, ang)
        exp_p, exp_n = [], []
        for face in step_reader._faces(occ, shape):
            loc = occ["TopLoc_Location"]()
            t = occ["BRep_Tool"].Triangulation_s(face, loc)
            tr = loc.Transformation()
            flip = -1.0 if face.Orientation() == occ["TopAbs_REVERSED"] else 1.0
            for i in range(1, t.NbNodes() + 1):
                exp_p.append(t.Node(i).Transformed(tr).Coord())
                exp_n.append(tuple(flip * c for c in t.Normal(i).Transformed(tr).Coord()))
        assert np.allclose(pos, np.array(exp_p) * step_reader.MM_TO_M, atol=1e-7)
        assert np.allclose(nrm, np.array(exp_n), atol=1e-5)


def test_helper_that_dies_skips_only_that_part(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FRESING_TEST_CRASH_PART", "0")
    info = step_reader.read_step(CRANE_B, str(tmp_path), "normal", workers=2)
    out = capsys.readouterr().out
    assert f"Could not mesh {info['meshes'][0]['name']}" in out
    assert info["meshes"][0]["tris"] == 0
    assert all(m["tris"] > 0 for m in info["meshes"][1:])
    assert info["stats"]["mesh_helpers"] == 2


def test_part_that_fails_in_a_helper_is_meshed_again_here(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FRESING_TEST_FAIL_PART", "1")
    info = step_reader.read_step(CRANE_B, str(tmp_path / "x"), "normal", workers=2)
    assert "Could not mesh" not in capsys.readouterr().out
    assert all(m["tris"] > 0 for m in info["meshes"])
    monkeypatch.delenv("FRESING_TEST_FAIL_PART")
    step_reader.read_step(CRANE_B, str(tmp_path / "y"), "normal", workers=0)
    _same_cache(str(tmp_path / "x"), str(tmp_path / "y"))


def test_helpers_that_do_not_start_fall_back_to_one_core(tmp_path, monkeypatch):
    false = "/bin/false" if os.path.exists("/bin/false") else None
    if false is None:
        pytest.skip("no /bin/false")
    monkeypatch.setattr(step_reader.sys, "executable", false)
    info = step_reader.read_step(CRANE_B, str(tmp_path / "x"), "normal", workers=2)
    monkeypatch.undo()
    assert info["stats"]["mesh_helpers"] == 0
    step_reader.read_step(CRANE_B, str(tmp_path / "y"), "normal", workers=0)
    _same_cache(str(tmp_path / "x"), str(tmp_path / "y"))


def test_helpers_stop_when_the_reader_is_killed():
    import signal
    import subprocess
    import sys
    code = ("import sys, time; sys.path.insert(0, %r)\n"
            "from fresing_render.importer import step_reader as R\n"
            "h = R._Helpers(2)\n"
            "print(' '.join(str(p.pid) for p in h.procs), flush=True)\n"
            "time.sleep(120)\n") % os.path.dirname(HERE)
    parent = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    pids = [int(x) for x in parent.stdout.readline().split()]
    assert len(pids) == 2
    time.sleep(1.0)
    parent.send_signal(signal.SIGKILL)
    parent.wait()

    def alive(pid):
        try:
            with open(f"/proc/{pid}/status") as fh:
                return "\nState:\tZ" not in fh.read()
        except FileNotFoundError:
            return False
    t0 = time.time()
    while any(alive(p) for p in pids) and time.time() - t0 < 10:
        time.sleep(0.1)
    assert not any(alive(p) for p in pids)


def test_worker_count_setting(monkeypatch):
    monkeypatch.setenv("FRESING_IMPORT_WORKERS", "6")
    assert step_reader.worker_count() == 6
    monkeypatch.setenv("FRESING_IMPORT_WORKERS", "1")
    assert step_reader.worker_count() == 0              # one helper is slower than none
    monkeypatch.setenv("FRESING_IMPORT_WORKERS", "99")
    assert step_reader.worker_count() == step_reader.MAX_WORKERS
