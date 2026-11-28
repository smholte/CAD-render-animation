"""The Fresing assets pack in a project: bring, keep, ask and update (task 0355, study 0344 2.2–2.5). No UI.

The engine every later assets task uses (0357 Settings > Assets, 0359 "Use the new Fresing looks", the plug-in tasks
0360–0363). Plain rules in ``core/assets_keep.py``; the pack and its registry in ``core/assets_pack.py`` /
``core/assets_registry.py`` (0354).

**Ask in one place** – ``get(scene, full_id)`` answers in 2.2's order and never raises:

1. the project's own copy (a datablock whose ``fr_asset`` id is ``full_id``) → ``Answer("project", id, datablock)``.
   Answered from memory (an index per datablock collection, checked by its length and first / last datablock), so
   ``world.apply``, the colour / wear sliders and a picker's draw never touch the disk (``bring=False`` in a draw);
2. the project's source is ``pack`` (``source``), the switch is on (``use_pack``), the pack has the id with a fitting
   contract → **bring** it → ``Answer("pack", id, datablock)``;
3. otherwise ``Answer("code", code_id)``: the caller builds today's code look (a pack-only id: its fallback's id;
   ``""`` when nobody knows the id – the caller's default).

**Bring** (``bring``): append the item's datablock from the pack's ``.blend`` (never a link) or load its picture file
(light, HDRI, decal), check what came in (no Text, no linked data, no script node, no Python driver, no picture outside
the pack's own list, every file's sha256 as pack.json says), **pack every picture into the project** at the project
quality (``normal`` = 2k: a 4k file is swapped for its 2k sibling; the bytes packed are the bytes checked), stamp
``fr_asset`` on every datablock that came in. **One per id + version**: a second bring answers with the copy; a picture
file is one image datablock (by its sha256 – also across items and versions), and a datablock another item already
brought (an environment's own copy of a material's node group) is that one. **All or nothing:** anything wrong → what
was appended is removed, the code look answers, and ONE note per session (``note()``; the details go to the console).

**The project's source** (2.5, picks 5 and 7) – ``scene.fresing.assets_source``: ``""`` (made before the pack) counts
as ``code``. A project made in this version gets its source when it is made: until its first save ``source`` answers
``new_source()`` (``pack`` with a pack and the switch on, else ``code``) and the first save writes it (``save_pre``;
also the first bring writes it). A project opened from a file without the field stays ``code`` – installing, updating
or removing the pack never changes it; only ``apply`` (0359's button) does. No load handler, no ``LOOK_VERSION`` /
``MAT_VERSION`` / ``fr_prop_ver`` stamp is used for any of it.

**Update** (``changes`` / ``apply``, no UI): copies of an older pack version are brought again in the new version and
every user is pointed at the new copy (``ID.user_remap`` – a group material's own colour, wear, rust, Adjust and finish
settings live on the app's material and the group node's inputs, so they stay), the old copies go, the scenes get
``pack`` and the pack's version. A backup first (0246's ``backups.make``), one undo step (``undo=`` the step's name, or
the caller's operator with ``UNDO``). A ``code`` project: the kinds a plug-in registered (``register_kind``) say what
they would swap – none yet.

**Kinds** (``register_kind``): a plug-in task says what "bring" and "update" mean for its kind without editing this
file: ``name`` (the app's name for the brought datablock), ``after_bring``, ``swap`` (point users of an old copy at the
new one; default ``user_remap``), ``code_changes`` / ``code_apply`` (a code project's looks of that kind).
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass

import bpy
from bpy.app.handlers import persistent

from ..core import assets_keep as K
from ..core import assets_pack as ap
from ..core import assets_registry as areg

STAMP = K.STAMP

# What may come in with a pack item (anything else – a Text, a scene, a screen … – refuses the item).
ALLOWED = frozenset(("node_groups", "materials", "images", "objects", "meshes", "collections", "worlds", "lights",
                     "cameras", "curves", "armatures", "shape_keys", "actions", "lattices", "pointclouds", "volumes",
                     "hair_curves", "textures", "libraries"))
# Where an item's own copy can be (looked up by ``get``): the kinds' datablock collections + pictures.
ITEM_COLLS = {kind: tuple(colls) for kind, colls in ap.BLEND_KINDS.items()}
ITEM_COLLS.update({kind: ("images",) for kind in ap.PICTURE_KINDS})
TREE_OWNERS = ("materials", "worlds", "lights")      # their node_tree is looked into too

NOTE_BRING = ("A look of the Fresing assets pack could not be brought into the project – the app uses its built-in "
              "look instead.")
NOTE_NO_PACK = "No Fresing assets pack was found on this PC – nothing was changed."
NOTE_BACKUP = "No backup of the project could be saved ({why}) – nothing was changed."
NOTE_BLOCKED = "{why} – nothing was changed."
NOTE_SOME = "{n} could not be brought from the Fresing assets pack – they keep their look."

STATE: dict = {
    "notes": [],            # the one note of this session (a list so tests can read it)
    "log": [],              # (id, why) of every refused bring, for the console / the PC check
    "brings": 0,            # appends + picture loads done (tests: "no disk work twice")
    "index_scans": 0,       # collection scans (tests: hot paths answer from the index)
}
SWITCH: dict = {"read": None}     # 0357: Settings > Assets' switch "Use the Fresing assets pack for new projects"
FOLDER: dict = {"read": None}     # 0358: the company's shared pack folder (the .frsetup's "assets" key)
HOOKS: dict = {}                  # kind -> KindHooks (``register_kind``)


# ---------------------------------------------------------------------------
# the registry, the switch, the notes
# ---------------------------------------------------------------------------

def _version() -> str:
    from .. import __version__
    return __version__


def _call(slot: dict, default):
    f = slot.get("read")
    if f is None:
        return default
    try:
        return f()
    except Exception:  # noqa: BLE001 - a broken reader never stops the app
        return default


def registry() -> areg.Registry:
    """The app's registry: the pack looked for and read ONCE (0354's ``current``; a background Blender finds it by
    ``FRESING_ASSETS`` or the install folder, never by settings); later calls answer from memory."""
    return areg.current(_version(), folder=str(_call(FOLDER, "") or ""),
                        binary_path=getattr(bpy.app, "binary_path", "") or "")


def forget() -> None:
    """Read the pack again at the next question (a pack update put in place; tests)."""
    areg.forget()
    _INDEX.clear()


def warm() -> None:
    """Read the pack in a helper thread now, so the first question in a hot path answers from memory."""
    threading.Thread(target=lambda: _quiet(registry), name="fresing-assets", daemon=True).start()


def _quiet(f):
    try:
        return f()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render (assets):", exc)
        return None


def use_pack() -> bool:
    """The user's switch (0357 puts it in Settings > Assets and sets ``SWITCH["read"]``); on until then."""
    return bool(_call(SWITCH, True))


def note() -> str:
    """ONE plain line for the user, or "": this session's bring problem, else what the registry says (a damaged pack,
    rows left out)."""
    if STATE["notes"]:
        return STATE["notes"][0]
    try:
        return registry().note
    except Exception:  # noqa: BLE001
        return ""


def _refused(aid: str, why: str) -> None:
    STATE["log"].append((aid, why))
    print(f"Fresing Render (assets): {aid} not brought – {why}")
    if not STATE["notes"]:
        STATE["notes"].append(NOTE_BRING)


# ---------------------------------------------------------------------------
# kinds
# ---------------------------------------------------------------------------

@dataclass
class KindHooks:
    name: object = None          # (asset, version) -> the app's name for the brought datablock
    after_bring: object = None   # (datablock, asset) -> None, after it is stamped
    swap: object = None          # (old, new) -> None: every user of the old copy uses the new one (default user_remap)
    code_changes: object = None  # (scene, registry) -> [assets_keep.Change]: a code project's looks of this kind
    code_apply: object = None    # (scene, registry) -> [ids done]: swap them for pack items (inside ``apply``)


def register_kind(kind: str, **hooks) -> KindHooks:
    """A plug-in task (0360–0363) says what bring and update mean for its kind. Unknown hook names raise."""
    if kind not in ap.CONTRACTS:
        raise ValueError(f"unknown kind {kind!r}")
    h = KindHooks(**hooks)
    HOOKS[kind] = h
    return h


def unregister_kind(kind: str) -> None:
    HOOKS.pop(kind, None)


def _hook(kind: str, name: str):
    h = HOOKS.get(kind)
    return getattr(h, name, None) if h else None


# ---------------------------------------------------------------------------
# the project's source
# ---------------------------------------------------------------------------

def _settings(scene):
    return getattr(scene, "fresing", None) if scene is not None else None


def is_new_project() -> bool:
    """A project made in this session and not saved yet (an opened file has a path)."""
    return not bpy.data.filepath


def new_source(reg: areg.Registry | None = None) -> str:
    """The source a project made now gets: ``pack`` when a pack is found and the switch is on, else ``code``."""
    try:
        reg = reg or registry()
        return K.PACK if reg.pack is not None and use_pack() else K.CODE
    except Exception:  # noqa: BLE001
        return K.CODE


def source(scene) -> str:
    """``pack`` or ``code`` for this scene's project. Stored ``assets_source`` first; an unsaved new project:
    ``new_source()``; anything else (opened from a file without the field) = ``code``."""
    s = _settings(scene)
    stored = getattr(s, "assets_source", "") if s is not None else ""
    if stored:
        return K.source_of(stored)
    if getattr(scene, "library", None) is None and is_new_project():
        return new_source()
    return K.CODE


def version(scene) -> str:
    """The pack version the project's copies come from ("" for a code project or before the first bring)."""
    s = _settings(scene)
    return str(getattr(s, "assets_version", "") or "") if s is not None else ""


def _local_scenes():
    return [sc for sc in bpy.data.scenes if getattr(sc, "library", None) is None]


def _set_source(src: str, ver: str = "", scenes=None, only_empty: bool = False) -> None:
    for sc in scenes if scenes is not None else _local_scenes():
        s = _settings(sc)
        if s is None or (only_empty and getattr(s, "assets_source", "")):
            continue
        try:
            s.assets_source = src
            s.assets_version = ver if src == K.PACK else ""
        except Exception:  # noqa: BLE001 - e.g. a draw context: written at the next chance
            pass


def stamp_new_project(reg: areg.Registry | None = None) -> None:
    """A new project's scenes get their source now (its first save, its first bring). An opened one never does."""
    if not is_new_project():
        return
    src = new_source(reg)
    ver = ""
    if src == K.PACK:
        try:
            ver = (reg or registry()).version
        except Exception:  # noqa: BLE001
            ver = ""
    _set_source(src, ver, only_empty=True)


@persistent
def _before_save(_filepath=None, *_args):
    try:
        stamp_new_project()
    except Exception as exc:  # noqa: BLE001 - a save must never fail on this
        print("Fresing Render (assets):", exc)


# ---------------------------------------------------------------------------
# the project's copies, from memory
# ---------------------------------------------------------------------------

_INDEX: dict = {}      # coll -> (signature, {id: [names of item copies]}, {share key: name})


def stamp_of(idb) -> dict:
    try:
        return K.read_stamp(idb.get(STAMP))
    except Exception:  # noqa: BLE001
        return {}


def _signature(coll):
    """Cheap and O(1) (Blender keeps these lists linked: the last item would cost a walk over 11,000 parts): the
    length and the first datablock – another file or an undo gives another one. Names found are checked again."""
    n = len(coll)
    return (n, coll[0].as_pointer() if n else 0)


def _scan(name: str):
    coll = getattr(bpy.data, name)
    STATE["index_scans"] += 1
    items, shared = {}, {}
    for idb in coll:
        if getattr(idb, "library", None) is not None:
            continue
        st = stamp_of(idb)
        if not st:
            continue
        shared.setdefault(K.share_key(name, st), idb.name)
        if K.is_item(st):
            items.setdefault(st["id"], []).append(idb.name)
    entry = (_signature(coll), items, shared)
    _INDEX[name] = entry
    return entry


def _index(name: str):
    coll = getattr(bpy.data, name)
    entry = _INDEX.get(name)
    if entry is None or entry[0] != _signature(coll):
        entry = _scan(name)
    return entry


def copies(full_id: str, colls=None) -> list:
    """The project's own copies of ``full_id`` (local datablocks whose ``fr_asset`` is the item itself), any version."""
    kind = full_id.split(":", 1)[0] if isinstance(full_id, str) else ""
    out = []
    for name in colls or ITEM_COLLS.get(kind, ()):
        for attempt in (0, 1):
            _sig, items, _shared = _index(name)
            coll = getattr(bpy.data, name)
            found, stale = [], False
            for n in items.get(full_id, ()):
                idb = coll.get(n)
                st = stamp_of(idb) if idb is not None and getattr(idb, "library", None) is None else {}
                if st.get("id") == full_id and K.is_item(st):
                    found.append(idb)
                else:
                    stale = True
            if stale and attempt == 0:          # renamed, undone …: look again once
                _scan(name)
                continue
            out += found
            break
    return out


def _shared(coll_name: str, key: tuple):
    _sig, _items, shared = _index(coll_name)
    n = shared.get(key)
    idb = getattr(bpy.data, coll_name).get(n) if n else None
    if idb is not None and K.share_key(coll_name, stamp_of(idb)) == key:
        return idb
    _sig, _items, shared = _scan(coll_name)
    n = shared.get(key)
    return getattr(bpy.data, coll_name).get(n) if n else None


def own_copy(scene, full_id: str):
    """The copy that answers for ``full_id`` (the project's ``assets_version`` when several are there, else the
    newest), or None. From memory."""
    have = copies(full_id)
    if not have:
        return None
    i = K.best([stamp_of(x) for x in have], version(scene))
    return have[i]


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Answer:
    source: str              # "project" (its own copy), "pack" (just brought) or "code"
    id: str                  # the id that answers (a code look may be a pack-only id's fallback; "" = nobody knows it)
    datablock: object = None

    @property
    def code_id(self) -> str:
        return self.id.split(":", 1)[1] if self.id else ""


def get(scene, full_id: str, bring: bool = True) -> Answer:
    """Pack item or code look for ``full_id`` (2.2's order, module docstring). ``bring=False`` in a draw or anywhere
    a datablock must not be made: then only the project's own copy or the code look answers. Never raises."""
    try:
        have = own_copy(scene, full_id)
        if have is not None:
            return Answer("project", full_id, have)
        reg = registry()
        src = source(scene)
        choice = reg.resolve(full_id, src, use_pack())
        if choice.source == "pack":
            if bring:
                idb = bring_choice(scene, choice, reg)
                if idb is not None:
                    return Answer("pack", full_id, idb)
            code = reg.resolve(full_id, K.CODE, False)
            return Answer("code", code.id)
        return Answer("code", choice.id)
    except Exception as exc:  # noqa: BLE001 - the code look always answers
        print("Fresing Render (assets): asking for", full_id, "–", exc)
        return Answer("code", full_id if isinstance(full_id, str) and ":" in full_id else "")


def bring(scene, full_id: str):
    """Bring ``full_id`` from the pack into the project (or answer with its copy of the pack's version). The
    project's source and the switch are NOT asked – ``get`` asks them; this is for ``apply`` and tests."""
    reg = registry()
    choice = reg.resolve(full_id, K.PACK, True)
    if choice.source != "pack":
        return None
    return bring_choice(scene, choice, reg)


# ---------------------------------------------------------------------------
# bring: append / load, check, pack the pictures, stamp
# ---------------------------------------------------------------------------

class _Refuse(Exception):
    pass


def _id_colls() -> tuple:
    names = _ID_COLLS.get("names")
    if names is None:
        names = tuple(p.identifier for p in bpy.data.bl_rna.properties
                      if p.type == "COLLECTION" and isinstance(getattr(bpy.data, p.identifier, None),
                                                                 bpy.types.bpy_prop_collection)
                      and p.identifier not in ("window_managers", "screens", "workspaces", "all_ids"))
        _ID_COLLS["names"] = names
    return names


_ID_COLLS: dict = {}


def _snapshot() -> dict:
    return {c: {i.as_pointer() for i in getattr(bpy.data, c)} for c in _id_colls()}


def _new_since(before: dict) -> list:
    """(coll, datablock) of every datablock made since ``before``."""
    out = []
    for c in _id_colls():
        old = before.get(c, set())
        out += [(c, i) for i in getattr(bpy.data, c) if i.as_pointer() not in old]
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_checked(pack: ap.Pack, rel: str) -> bytes:
    """The bytes of a pack file, refused unless pack.json lists it with these very bytes (a pack changed or removed
    under a running app answers with the code look, never a half-right copy)."""
    entry = pack.files.get(rel)
    full = pack.path(rel)
    if entry is None or not full:
        raise _Refuse(f"{rel} is not a file of the pack")
    try:
        with open(full, "rb") as f:
            data = f.read()
    except OSError as exc:
        raise _Refuse(f"{rel} could not be read ({exc.strerror or exc})") from None
    size, sha = entry
    if len(data) != size or _sha(data) != sha:
        raise _Refuse(f"{rel} is not the file pack.json lists (changed or damaged)")
    return data


def _pack_rel(pack: ap.Pack, path: str) -> str:
    """The pack path of a file a brought datablock points at ('' when it lies outside the pack)."""
    try:
        full = os.path.realpath(bpy.path.abspath(path))
        root = os.path.realpath(pack.root)
    except Exception:  # noqa: BLE001
        return ""
    if os.path.normcase(os.path.commonpath([full, root])) != os.path.normcase(root):
        return ""
    return os.path.relpath(full, root).replace(os.sep, "/")


def _trees(coll: str, idb):
    if coll == "node_groups":
        yield idb
    elif coll in TREE_OWNERS and getattr(idb, "node_tree", None) is not None:
        yield idb.node_tree


def _check(coll: str, idb) -> None:
    """Refuse what could run code or reach outside the project."""
    if coll not in ALLOWED:
        raise _Refuse(f"it holds {coll} ({idb.name})")
    if getattr(idb, "library", None) is not None:
        raise _Refuse(f"it links to another file ({idb.name})")
    for owner in (idb, *(_trees(coll, idb))):
        ad = getattr(owner, "animation_data", None)
        for d in (ad.drivers if ad else ()):
            drv = d.driver
            if drv.type == "SCRIPTED" and not drv.is_simple_expression:
                raise _Refuse(f"{idb.name} has a Python driver")
    for nt in _trees(coll, idb):
        for nd in nt.nodes:
            if nd.bl_idname == "ShaderNodeScript":
                raise _Refuse(f"{idb.name} has a script node")


def _remove(items) -> None:
    live = []
    for _c, i in items:
        try:
            i.name                              # noqa: B018 - still there?
            live.append(i)
        except ReferenceError:
            pass
    if not live:
        return
    try:
        bpy.data.batch_remove(live)
    except Exception:  # noqa: BLE001
        for i in live:
            for c in _id_colls():
                coll = getattr(bpy.data, c)
                try:
                    if i in coll.values():
                        coll.remove(i)
                        break
                except (ReferenceError, RuntimeError, TypeError):
                    break


def _pack_name(idb, path: str) -> str:
    """The datablock's name inside the pack file (Blender's weak reference to where it was appended from)."""
    wr = getattr(idb, "library_weak_reference", None)
    try:
        if wr is not None and os.path.normcase(os.path.realpath(wr.filepath)) == os.path.normcase(
                os.path.realpath(path)) and len(wr.id_name) > 2:
            return wr.id_name[2:]
    except Exception:  # noqa: BLE001
        pass
    name = idb.name
    head, dot, tail = name.rpartition(".")
    return head if dot and tail.isdigit() and len(tail) == 3 else name


def bring_choice(scene, choice, reg: areg.Registry | None = None):
    """Bring the item ``choice`` (``Registry.resolve`` gave it, source "pack") into the project, or answer with its
    copy of the pack's version. None (and one note) when it cannot be brought whole."""
    reg = reg or registry()
    a, pack = choice.asset, reg.pack
    if a is None or pack is None:
        return None
    for idb in copies(a.id):
        if stamp_of(idb).get("version") == reg.version:
            return idb
    before = _snapshot()
    t0 = time.perf_counter()
    try:
        main = _bring(a, pack, reg, before)
    except Exception as exc:  # noqa: BLE001 - never a half-built item
        _remove(_new_since(before))
        _INDEX.clear()
        _refused(a.id, str(exc) if isinstance(exc, _Refuse) else f"{type(exc).__name__}: {exc}")
        return None
    _INDEX.clear()
    STATE["brings"] += 1
    STATE.setdefault("times", []).append((a.id, round(time.perf_counter() - t0, 4)))
    after = _hook(a.kind, "after_bring")
    if after is not None:
        _quiet(lambda: after(main, a))
    stamp_new_project(reg)
    if scene is not None and source(scene) == K.PACK and not version(scene):
        _set_source(K.PACK, reg.version, only_empty=False, scenes=[scene])
    return main


def _bring(a: ap.Asset, pack: ap.Pack, reg: areg.Registry, before: dict):
    base = reg.stamp(areg.Choice("pack", a.id, a, reg.version))
    quality = str((pack.qualities or {}).get("normal") or ap.DEFAULT_QUALITIES["normal"])
    if a.datablock:
        coll_name, db_name = a.datablock
        path = pack.path(a.file)
        _read_checked(pack, a.file)                     # the .blend is the one pack.json lists
        with bpy.data.libraries.load(path, link=False, relative=False) as (src, dst):
            if db_name not in getattr(src, coll_name):
                raise _Refuse(f"{a.file} holds no {coll_name} {db_name!r}")
            setattr(dst, coll_name, [db_name])
        main = getattr(dst, coll_name)[0]
        if main is None:
            raise _Refuse(f"{db_name} could not be appended")
    else:                                               # a picture file: light, 360° photo, decal
        coll_name, path = "images", pack.path(K.at_quality(a.file, pack.files, quality))
        if not path:
            raise _Refuse(f"{a.file} is not a file of the pack")
        main = bpy.data.images.load(path, check_existing=False)
    new = _new_since(before)
    # 1. check everything that came in, before anything is kept
    for coll, idb in new:
        if coll != "libraries":
            _check(coll, idb)
    # 2. every picture: in the pack's list, at the project quality, its bytes checked (read once per file)
    pictures = []
    for coll, img in new:
        if coll != "images" or img.source == "GENERATED":
            continue
        if img.source != "FILE":
            raise _Refuse(f"picture {img.name} is a {img.source.lower()}, not one picture file")
        if img.packed_file is not None:                 # packed inside the checked .blend already
            data = bytes(img.packed_file.data)
            rel, sha = "", _sha(data)
        else:
            rel = _pack_rel(pack, img.filepath)
            if not rel:
                raise _Refuse(f"picture {img.name} lies outside the pack")
            rel = K.at_quality(rel, pack.files, quality)
            if rel not in pack.files:
                raise _Refuse(f"picture {rel} is not a file of the pack")
            sha, data = pack.files[rel][1], None
        have = _shared("images", ("images", sha))
        if have is None and data is None:
            data = _read_checked(pack, rel)
        pictures.append((img, rel, sha, data, have))
    # 3. keep: pack the pictures, share what the project has, stamp, drop leftovers
    drop = []
    for img, rel, sha, data, have in pictures:
        is_main = img == main
        st = K.stamp(base, name=os.path.basename(rel) if not a.datablock else _pack_name(img, path),
                     part="" if is_main else "images", file=rel, sha=sha)
        if have is not None:                            # the project holds these bytes already: one picture
            img.user_remap(have)
            drop.append(("images", img))
            if is_main:
                if not K.is_item(stamp_of(have)):
                    have[STAMP] = st
                main = have
            continue
        if rel:
            full = pack.path(rel)
            if os.path.normcase(os.path.realpath(bpy.path.abspath(img.filepath))) != os.path.normcase(
                    os.path.realpath(full)):
                img.filepath = full
            img.pack(data=data, data_len=len(data))
        img[STAMP] = st
    pic_set = {p[0].as_pointer() for p in pictures}
    for coll, idb in new:
        if coll == "libraries":                         # an append leaves its library behind, holding nothing
            drop.append((coll, idb))
            continue
        if idb.as_pointer() in pic_set:
            continue
        is_main = idb == main
        st = K.stamp(base, name=_pack_name(idb, path), part="" if is_main else coll)
        have = _shared(coll, K.share_key(coll, st))
        if have is not None and have != idb:
            have_st = stamp_of(have)
            if not (is_main and K.is_item(have_st)):    # another item brought this one already: one copy
                idb.user_remap(have)
                drop.append((coll, idb))
                if is_main:                             # ... and it is this item itself
                    have[STAMP] = st
                    main = have
                continue
        idb[STAMP] = st
    _remove(drop)
    namer = _hook(a.kind, "name")
    if namer is not None:
        want = namer(a, reg.version)
        if want:
            main.name = want
    elif not a.datablock:
        main.name = f"FRP {a.kind} {a.code_id}"
    return main


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def _items() -> dict:
    """{id: [copies]} of every item copy in the project."""
    out: dict = {}
    for kind, colls in ITEM_COLLS.items():
        for name in colls:
            _sig, items, _shared_ = _index(name)
            for aid in items:
                if aid.split(":", 1)[0] == kind:
                    out.setdefault(aid, [])
    for aid in out:
        out[aid] = copies(aid)
    return out


def _unchanged(reg: areg.Registry, aid: str, copy) -> bool:
    """The pack's item is the copy's: the same file bytes, or the pack row says it last changed in the copy's version
    or before (``changed``, else ``since``) – then the copy only takes the new version's stamp."""
    a = reg.usable.get(aid)
    st = stamp_of(copy)
    if a is None or not st:
        return False
    if a.sha256 and st.get("sha") == a.sha256:
        return True
    last = K.version_key(a.changed or a.since)
    return bool(last) and last <= K.version_key(st.get("version", ""))


def _older(reg: areg.Registry, aid: str, have: list) -> list:
    """The copies of ``aid`` older than the pack's version (sorted oldest first); [] when the pack lacks the id."""
    if not reg.has(aid):
        return []
    newv = K.version_key(reg.version)
    olds = [x for x in have if K.version_key(stamp_of(x).get("version", "")) < newv]
    return sorted(olds, key=lambda x: K.version_key(stamp_of(x).get("version", "")))


def _restamp(reg: areg.Registry) -> list:
    """Items whose file is byte for byte the pack's (only the version moved on): their copies and what came along
    with them take the new version – nothing is appended again. Returns the ids."""
    done = []
    for aid, have in _items().items():
        olds = _older(reg, aid, have)
        if not olds or not all(_unchanged(reg, aid, x) for x in olds):
            continue
        vers = {stamp_of(x).get("version") for x in olds}
        for c in _id_colls():
            for idb in getattr(bpy.data, c):
                st = stamp_of(idb)
                if st.get("id") == aid and st.get("version") in vers and getattr(idb, "library", None) is None:
                    idb[STAMP] = {**st, "version": reg.version}
        done.append(aid)
    _INDEX.clear()
    return done


def changes(scene=None, reg: areg.Registry | None = None) -> list:
    """What ``apply`` would change: copies of an older pack version (the pack has a newer one), and for a ``code``
    project what the registered kinds would swap (none until 0360–0363). Answers from memory."""
    scene = scene if scene is not None else bpy.context.scene
    reg = reg or registry()
    out = []
    if reg.pack is None:
        return out
    for aid, have in sorted(_items().items()):
        olds = _older(reg, aid, have)
        if olds and not all(_unchanged(reg, aid, x) for x in olds):
            old = stamp_of(olds[-1]).get("version", "")
            out.append(K.Change(aid, aid.split(":", 1)[0], "newer", old, reg.version,
                                K.newer_text(aid, old, reg.version)))
    if source(scene) == K.CODE:
        for kind, h in sorted(HOOKS.items()):
            if h.code_changes is not None:
                out += list(_quiet(lambda h=h: h.code_changes(scene, reg)) or ())
    return out


def _swap(kind: str, old, new) -> None:
    f = _hook(kind, "swap")
    if f is not None:
        f(old, new)
        return
    old.user_remap(new)
    from . import materials
    if isinstance(new, bpy.types.ShaderNodeTree):
        ver = stamp_of(new).get("version", "")
        for mat in bpy.data.materials:
            nt = mat.node_tree
            if nt is None or materials.look_src_of(mat) == K.CODE:
                continue
            if any(getattr(nd, "node_tree", None) == new for nd in nt.nodes):
                materials.set_look_src(mat, ver)


def _drop_old(pack_id: str, keep_version: str, keep_ids: set) -> int:
    """Remove copies of other versions nobody uses any more (pictures: any stamped picture nobody uses)."""
    gone = []
    for c in ("node_groups", "materials", "objects", "meshes", "collections", "worlds", "lights", "curves",
              "armatures", "actions", "images"):
        for idb in getattr(bpy.data, c):
            st = stamp_of(idb)
            if not st or st.get("pack") != pack_id or getattr(idb, "library", None) is not None:
                continue
            if c == "images":
                if idb.users == 0:
                    gone.append((c, idb))
                continue
            if st.get("version") != keep_version and st.get("id") not in keep_ids and idb.users == 0:
                gone.append((c, idb))
    _remove(gone)
    return len(gone)


def _drop_unused_parts(pack_id: str, keep_version: str, keep_ids: set) -> None:
    """Drop the old version's leftovers in rounds (a collection holds objects, an object its mesh …)."""
    for _round in range(6):
        if not _drop_old(pack_id, keep_version, keep_ids):
            break


def apply(scene=None, reg: areg.Registry | None = None, *, backup: bool = True, undo: str = "") -> K.Result:
    """Make ``changes``: bring the newer versions, point every user at them, drop the old copies, give the project
    the source ``pack`` and the pack's version. A backup first (``backup``; when none can be saved nothing changes).
    ``undo`` = the name of the one undo step it pushes when done (empty: the caller's operator makes the step)."""
    scene = scene if scene is not None else bpy.context.scene
    reg = reg or registry()
    res = K.Result()
    from . import compat
    why = compat.blocked(scene)
    if why:
        res.note = NOTE_BLOCKED.format(why=why.rstrip("."))
        return res
    if reg.pack is None:
        res.note = reg.note or NOTE_NO_PACK
        return res
    todo = changes(scene, reg)
    already = all(source(sc) == K.PACK and version(sc) == reg.version for sc in _local_scenes())
    if not todo and already:
        return res
    if backup:
        from . import backups
        res.backup = backups.make(scene, force=True, note=False)
        if not res.backup:
            res.note = NOTE_BACKUP.format(why=backups._S.get("last_reason", "") or "unknown")
            return res
    failed_ids = set()
    for ch in todo:
        if ch.what != "newer":
            continue
        olds = [x for x in copies(ch.id) if stamp_of(x).get("version") != reg.version]
        new = bring(scene, ch.id)
        if new is None:
            failed_ids.add(ch.id)
            res.failed.append((ch.id, STATE["log"][-1][1] if STATE["log"] else "not brought"))
            continue
        for old in olds:
            name = old.name
            _swap(ch.kind, old, new)
            if old.users == 0:
                _remove([("", old)])
                try:
                    new.name = name                     # the copy keeps the name the project knew
                except Exception:  # noqa: BLE001
                    pass
        res.done.append(ch)
    if source(scene) == K.CODE:
        for kind, h in sorted(HOOKS.items()):
            if h.code_apply is not None:
                done = _quiet(lambda h=h: h.code_apply(scene, reg)) or ()
                res.done += [c for c in todo if c.what == "code" and c.id in set(done)]
    _restamp(reg)
    _drop_unused_parts(reg.pack.id, reg.version, failed_ids)
    _set_source(K.PACK, reg.version)
    _INDEX.clear()
    if res.failed:
        res.note = NOTE_SOME.format(n=_plural(len(res.failed)))
    if undo:
        try:
            bpy.ops.ed.undo_push(message=undo)
        except Exception as exc:  # noqa: BLE001 - Blender as a module has no undo
            print("Fresing Render (assets): no undo step –", exc)
    return res


def _plural(n: int) -> str:
    from ..core import words
    return words.plural(n, "look")


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

def register() -> None:
    if _before_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_before_save)
    warm()


def unregister() -> None:
    if _before_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_before_save)
    _INDEX.clear()
