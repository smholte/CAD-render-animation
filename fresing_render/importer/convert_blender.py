"""Convert an FBX (or a compressed glTF) to a plain GLB with Blender's own importer and exporter (task 0117).

Run by ``mesh_reader.convert_with_blender`` in a background Blender:

    blender -b --factory-startup --python convert_blender.py -- model.fbx out.glb
    python convert_blender.py model.fbx out.glb        (a Python with the bpy module: the tests)

Prints ``FRCONVERT <what it does>`` lines for the progress and ``FRERROR <why>`` when it fails. The GLB is written
in metres, Y up, without compression, with names, materials, textures and UVs; no animations, cameras or lights.
"""

import os
import sys


def _args() -> list:
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def convert(src: str, dst: str) -> None:
    import bpy
    # an empty scene without read_factory_settings: resetting the set-up makes Blender sync the extensions' wheels
    # (``mesh_reader`` also gives this Blender a settings folder of its own)
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            coll.remove(block)
    ext = os.path.splitext(src)[1].lower()
    print("FRCONVERT Reading the file with Blender", flush=True)
    if ext == ".fbx":
        res = bpy.ops.import_scene.fbx(filepath=src, use_anim=False, use_image_search=True)
    elif ext in (".glb", ".gltf"):
        res = bpy.ops.import_scene.gltf(filepath=src)
    else:
        raise RuntimeError(f"cannot convert {ext} files")
    if "FINISHED" not in res:
        raise RuntimeError("Blender's importer did not finish")
    for ob in list(bpy.data.objects):            # only shapes: cameras, lights and bones' empties stay behind
        if ob.type in ("CAMERA", "LIGHT", "SPEAKER", "LIGHT_PROBE"):
            bpy.data.objects.remove(ob)
    print("FRCONVERT Writing it for the app", flush=True)
    kw = dict(filepath=dst, export_format="GLB", export_yup=True, export_apply=False, export_texcoords=True,
              export_normals=True, export_materials="EXPORT", export_extras=False, export_cameras=False,
              export_lights=False, export_animations=False, use_selection=False)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kw = {k: v for k, v in kw.items() if k in props}           # exporter options differ between versions
    if "export_draco_mesh_compression_enable" in props:
        kw["export_draco_mesh_compression_enable"] = False
    res = bpy.ops.export_scene.gltf(**kw)
    if "FINISHED" not in res or not os.path.isfile(dst):
        raise RuntimeError("Blender's glTF exporter did not finish")


def main() -> int:
    args = _args()
    if len(args) != 2:
        print("FRERROR usage: convert_blender.py <in> <out.glb>", flush=True)
        return 2
    try:
        convert(args[0], args[1])
    except Exception as exc:
        print(f"FRERROR {exc.__class__.__name__}: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)          # a background Blender keeps running after a script's sys.exit: end it here
