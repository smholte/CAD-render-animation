"""CAD material and appearance names from STEP files (task 0008)."""

import json
import os
import time

import pytest

from fresing_render.core import ral
from fresing_render.core import rules as R
from fresing_render.importer import step_meta

HERE = os.path.dirname(__file__)
MATERIALS_STEP = os.path.join(HERE, "data", "test_materials.step")

# The structure Fusion 360 / Inventor (Autodesk Translation Framework) write, with made-up
# names: material as a 'material property', appearance as the style name of the body, and the
# body reached from the product through SHAPE_REPRESENTATION -> SHAPE_REPRESENTATION_RELATIONSHIP.
AUTODESK_STYLE = r"""ISO-10303-21;
HEADER;
FILE_SCHEMA (('AUTOMOTIVE_DESIGN { 1 0 10303 214 3 1 1 }'));
ENDSEC;
DATA;
#10=MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',(#31,#32),#227);
#13=(
REPRESENTATION_RELATIONSHIP($,$,#241,#240)
REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#11)
SHAPE_REPRESENTATION_RELATIONSHIP()
);
#15=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#13,#238);
#27=SHAPE_REPRESENTATION_RELATIONSHIP('SRR','None',#241,#29);
#28=SHAPE_REPRESENTATION_RELATIONSHIP('SRR','None',#242,#30);
#29=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#33),#225);
#30=ADVANCED_BREP_SHAPE_REPRESENTATION('',(#34,#35),#226);
#31=STYLED_ITEM('',(#260),#33);
#32=STYLED_ITEM('',(#261),#34);
#36=STYLED_ITEM('',(#261),#35);
#37=OVER_RIDING_STYLED_ITEM('',(#260),#99,#32);
#33=MANIFOLD_SOLID_BREP('Body1',#104);
#34=MANIFOLD_SOLID_BREP('Body1',#105);
#35=MANIFOLD_SOLID_BREP('Body2',#106);
#119=REPRESENTATION('material name',(#123),#225);
#120=REPRESENTATION('density',(#113),#225);
#121=REPRESENTATION('material name',(#124),#226);
#113=MEASURE_REPRESENTATION_ITEM('density measure',
POSITIVE_RATIO_MEASURE(930.),#111);
#123=DESCRIPTIVE_REPRESENTATION_ITEM('Rubber','Rubber');
#124=DESCRIPTIVE_REPRESENTATION_ITEM('Alumin\X2\00EF\X0\um','Aluminum');
#115=PROPERTY_DEFINITION_REPRESENTATION(#125,#119);
#116=PROPERTY_DEFINITION_REPRESENTATION(#126,#120);
#117=PROPERTY_DEFINITION_REPRESENTATION(#127,#121);
#125=PROPERTY_DEFINITION('material property','material name',#245);
#126=PROPERTY_DEFINITION('material property','density of part',#245);
#127=PROPERTY_DEFINITION('material property','material name',#246);
#233=SHAPE_DEFINITION_REPRESENTATION(#236,#241);
#234=SHAPE_DEFINITION_REPRESENTATION(#237,#242);
#235=SHAPE_DEFINITION_REPRESENTATION(#239,#240);
#236=PRODUCT_DEFINITION_SHAPE('',$,#245);
#237=PRODUCT_DEFINITION_SHAPE('',$,#246);
#239=PRODUCT_DEFINITION_SHAPE('',$,#244);
#240=SHAPE_REPRESENTATION('',(#129,#147),#224);
#241=SHAPE_REPRESENTATION('',(#130),#225);
#242=SHAPE_REPRESENTATION('',(#134),#226);
#244=PRODUCT_DEFINITION('(Unsaved)','(Unsaved)',#247,#243);
#245=PRODUCT_DEFINITION('Seal ring','Seal ring',#248,#243);
#246=PRODUCT_DEFINITION('Bracket','Bracket',#249,#243);
#247=PRODUCT_DEFINITION_FORMATION('',$,#256);
#248=PRODUCT_DEFINITION_FORMATION('',$,#257);
#249=PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('',$,#258,.NOT_KNOWN.);
#256=PRODUCT('(Unsaved)','(Unsaved)',$,(#255));
#257=PRODUCT('P-0001','Seal ring',$,(#255));
#258=PRODUCT('P-0002','',$,(#255));
#260=PRESENTATION_STYLE_ASSIGNMENT((#263));
#261=PRESENTATION_STYLE_ASSIGNMENT((#264));
#263=SURFACE_STYLE_USAGE(.BOTH.,#266);
#264=SURFACE_STYLE_USAGE(.BOTH.,#267);
#266=SURFACE_SIDE_STYLE('',(#269));
#267=SURFACE_SIDE_STYLE('',(#270));
#269=SURFACE_STYLE_FILL_AREA(#272);
#270=SURFACE_STYLE_FILL_AREA(#273);
#272=FILL_AREA_STYLE('Rubber - Soft',(#275));
#273=FILL_AREA_STYLE('',(#276));
#275=FILL_AREA_STYLE_COLOUR('Rubber - Soft',#278);
#276=FILL_AREA_STYLE_COLOUR('',#279);
#278=COLOUR_RGB('Rubber - Soft',0.15,0.15,0.15);
#279=COLOUR_RGB('Paint - Enamel Glossy (Red)',0.75,0.,0.);
ENDSEC;
END-ISO-10303-21;
"""


def test_autodesk_structure():
    meta = step_meta.read_text(AUTODESK_STYLE)
    assert meta == {
        "Seal ring": {"material": "Rubber", "appearance": "Rubber - Soft"},
        # product without a name: OpenCascade names the part after its id; unicode escape decoded;
        # the appearance comes from the colour name when the fill style has none
        "P-0002": {"material": "Aluminïum", "appearance": "Paint - Enamel Glossy (Red)"},
    }


def test_step_strings():
    assert step_meta.decode("It''s") == "It's"
    assert step_meta.decode(r"Geh\X2\00E4\X0\use") == "Gehäuse"
    assert step_meta.decode(r"\X\E4") == "ä"
    assert step_meta.decode(r"\S\d") == "ä"
    assert step_meta.decode("Gehäuse".encode("utf-8").decode("latin-1")) == "Gehäuse"   # raw UTF-8 bytes
    args, end = step_meta.parse_args("('a',#12,(#1,#2),.T.,$,*,3.5E-2,POSITIVE_RATIO_MEASURE(930.));", 0)
    assert args == ["a", 12, [1, 2], "T", None, None, 0.035, 930.0] and isinstance(args[1], step_meta.Ref)


def test_file_without_names_is_skipped_quickly(tmp_path):
    p = tmp_path / "ap203.step"
    body = "".join(f"#{i}=CARTESIAN_POINT('',({i}.,0.,0.));\n" for i in range(1, 200000))
    p.write_text("ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));\nENDSEC;\nDATA;\n" + body
                 + "#200000=PRODUCT('PLATE','PLATE','',(#1));\nENDSEC;\nEND-ISO-10303-21;\n")
    t = time.perf_counter()
    assert step_meta.read(str(p)) == {}
    assert time.perf_counter() - t < 1.0


def test_names_from_an_opencascade_file():
    meta = step_meta.read(MATERIALS_STEP)
    assert meta["PLATE"] == {"material": "Aluminium 6082", "appearance": "Aluminum - Satin"}
    assert meta["SEAL RING"] == {"material": "EPDM", "appearance": "Rubber - Soft"}
    assert meta["BODY1"] == {"material": "Steel", "appearance": "Paint - Enamel Glossy (Red)"}
    assert meta["BODY2"] == {"material": "Generic", "appearance": ""}
    assert "BODY3" not in meta
    assert "TWIN" not in meta, "two parts with one name and different materials: no guessing"


# ---- the reader and the sorting rules --------------------------------------------------------

def _read(tmp_path):
    pytest.importorskip("OCP")
    from fresing_render.importer import step_reader
    return step_reader.read_step(MATERIALS_STEP, str(tmp_path), "draft")


def test_reader_stores_material_names(tmp_path):
    from fresing_render.importer import step_reader
    info = _read(tmp_path)
    assert info["version"] == step_reader.CACHE_VERSION == 4
    parts = {n["name"]: n for n in info["nodes"] if n["kind"] == "part"}
    assert parts["PLATE"]["material"] == "Aluminum - Satin"             # the appearance decides the look
    assert parts["PLATE"]["material_name"] == "Aluminium 6082"
    assert parts["SEAL RING"]["material"] == "Rubber - Soft"
    assert parts["BODY1"]["material"] == "Paint - Enamel Glossy (Red)"
    assert "material" not in parts["BODY2"] and parts["BODY2"]["material_name"] == "Generic"
    assert "material" not in parts["BODY3"]
    assert info["stats"]["parts_with_material"] == 3
    with open(tmp_path / "tree.json", encoding="utf-8") as fh:
        saved = {n["name"]: n.get("material") for n in json.load(fh)["nodes"]}
    assert saved["SEAL RING"] == "Rubber - Soft"


def test_material_names_sort_the_parts(tmp_path):
    info = _read(tmp_path)
    rules = R.default_rules()
    out = {}
    for n in info["nodes"]:
        if n["kind"] == "part":
            color = ral.rgb_to_hex(n["color"]) if n.get("color") else ""
            f = R.facts_for(n["name"], color=color, cad_material=n.get("material", ""))
            out.setdefault(n["name"], set()).add(R.classify_one(f, rules)[0])
    assert out["PLATE"] == {"Aluminum - Satin"}                       # CAD appearance beats "plate"
    assert out["SEAL RING"] == {"Seals & O-rings"}                    # part type first
    (body1,) = out["BODY1"]
    assert body1.startswith("Paint - Enamel Glossy (Red) #")
    assert R.default_material_for_group(body1)[0] == "paint_gloss"
    (body2,) = out["BODY2"]
    assert body2.startswith("Colour #")                                 # "Generic": the colour decides
    assert out["BODY3"] == {R.FALLBACK_GROUP} and out["TWIN"] == {R.FALLBACK_GROUP}
    assert R.default_material_for_group("Aluminum - Satin") == ("aluminium_machined", "")


def test_import_job_reads_names(tmp_path):
    """The import job runs the reader as a separate script: its imports must work there too."""
    pytest.importorskip("OCP")
    from fresing_render.importer import runner
    job = runner.ImportJob(MATERIALS_STEP, "draft", str(tmp_path))
    job.start()
    deadline = time.time() + 120
    while not job.poll() and time.time() < deadline:
        time.sleep(0.1)
    assert job.error is None, job.error
    with open(os.path.join(job.cache_dir, "tree.json"), encoding="utf-8") as fh:
        nodes = json.load(fh)["nodes"]
    assert any(n.get("material") == "Rubber - Soft" for n in nodes)


def test_old_caches_are_read_again(tmp_path):
    from fresing_render.importer import runner
    d = tmp_path / "cache"
    d.mkdir()
    (d / "tree.json").write_text(json.dumps({"version": 3, "nodes": []}))
    assert not runner.cache_is_valid(str(d))
