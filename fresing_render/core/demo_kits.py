"""Demo kits (task 0228): a demo project that comes from a zip the user adds, not from the app.

Help > Make demo project… lists the app's own demo (while it has one) and every kit added with **Add a demo kit…**.
A kit is Python code that runs in the app: add only kits you made yourself (``docs/COMPANY-USE.md``). No Blender here.

THE ZIP – every file under ONE top folder (any name)::

    <top>/kit.json
    <top>/<package>/...            the kit's Python package (its stage module, its model maker)

``kit.json``::

    {"id": "my-demo",              a slug: a-z first, then a-z 0-9 - (at most 40)
     "title": "My demo",           the list's name and the project file's name ("My demo 0.2.180.blend")
     "kit_version": "3",           the kit's own version, shown in the list
     "app_min": "0.2.176",         the app versions it was made for ("app_max" "" = no upper end)
     "app_max": "0.2.199",
     "stage_module": "my_kit.stages",   imported in the build: its @stage functions make the project
     "maker": "my_kit.make",       optional: run first as its own program (writes the model files), see below
     "stages": ["box", "camera"],  the stage ids the stage module must register (checked)
     "uses": ["blender.demo.stage", "demo_model.geom"]}   app names it imports, relative to the app (checked)

HOW A KIT IS BUILT (``blender/demo.py`` ``build_project(kit=…)``): the app's own stages are set aside; the build runs
the kit's maker (stage ``kit_model``), then the stages the kit's stage module registers with the app's ``@stage`` –
nothing else. Inside the kit the app is importable as ``fresing_app`` whatever Blender named the installed package
(``from fresing_app.blender.demo import Demo, stage``; ``fresing_app.demo_model.geom``) – in the build and in the maker.
A stage module may define ``Demo``, a subclass of the app's ``Demo``: the build then hands that to the stages.

THE MAKER runs with Blender's Python (no bpy), started by ``demo_kit_run.py``::

    python -m <maker> <model folder> [--small] [--progress <file.json>]

It writes its files into ``<model folder>`` and may write {"text": "...", "done": i, "total": n} to the progress file.

WHERE: ``<Blender's config folder>/fresing_demo_kits/<id>/`` (kit.json + the package; ``FRESING_DEMO_KITS`` moves it
for tests). Add again = replace. The kit's demo project goes to ``<demo folder>/Kits/<id>/<version>/``, next to the
app's own demo (``<demo folder>/<version>/``).
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.abc
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field

KIT_JSON = "kit.json"
FOLDER = "fresing_demo_kits"          # in Blender's config folder
ENV = "FRESING_DEMO_KITS"             # tests, the PC check: another folder
ALIAS = "fresing_app"                 # the name the app goes by inside a kit
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
MAX_FILES = 20000
MAX_BYTES = 2_000_000_000             # unpacked
ZIP_DATE = (2026, 1, 1, 0, 0, 0)      # ``pack`` writes every file with this date: the same folder gives the same zip


class KitError(Exception):
    """A kit that cannot be used; the message says why in plain words."""


@dataclass
class KitInfo:
    id: str
    title: str
    kit_version: str
    app_min: str
    app_max: str
    stage_module: str
    maker: str = ""
    stages: list = field(default_factory=list)
    uses: list = field(default_factory=list)
    folder: str = ""                  # where it is unpacked (empty while only checked)

    @property
    def label(self) -> str:
        return f"{self.title} (kit {self.kit_version})"

    def made_for(self) -> str:
        return f"{self.app_min}–{self.app_max}" if self.app_max else f"{self.app_min} and newer"


def _text(data: dict, key: str, need: bool = True, limit: int = 120) -> str:
    v = data.get(key, "")
    if not isinstance(v, str):
        raise KitError(f"kit.json: '{key}' must be text")
    v = v.strip()
    if need and not v:
        raise KitError(f"kit.json has no '{key}'")
    if len(v) > limit or any(ord(c) < 32 for c in v):
        raise KitError(f"kit.json: '{key}' is too long or holds control characters")
    return v


def _names(data: dict, key: str, pattern=None) -> list:
    v = data.get(key, [])
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
        raise KitError(f"kit.json: '{key}' must be a list of names")
    out = [x.strip() for x in v]
    if pattern is not None:
        bad = [x for x in out if not pattern.match(x)]
        if bad:
            raise KitError(f"kit.json: '{key}' has a name that is not a module path: {bad[0]}")
    return out


def _version(text: str, key: str) -> str:
    from .updates import parse_version
    if not parse_version(text)[0]:
        raise KitError(f"kit.json: '{key}' is not a version number: {text!r}")
    return text


def info_from(data, folder: str = "") -> KitInfo:
    """``kit.json`` read and checked (raises KitError)."""
    if not isinstance(data, dict):
        raise KitError("kit.json is not a JSON object")
    kid = _text(data, "id", limit=40)
    if not ID_RE.match(kid):
        raise KitError(f"kit.json: the id {kid!r} must be lower-case letters, digits and '-', starting with a letter")
    info = KitInfo(id=kid, title=_text(data, "title"), kit_version=_text(data, "kit_version", limit=40),
                   app_min=_version(_text(data, "app_min", limit=40), "app_min"),
                   app_max=_text(data, "app_max", need=False, limit=40),
                   stage_module=_text(data, "stage_module"), maker=_text(data, "maker", need=False),
                   stages=_names(data, "stages"), uses=_names(data, "uses", MODULE_RE), folder=folder)
    if info.app_max:
        _version(info.app_max, "app_max")
    for key in ("stage_module", "maker"):
        v = getattr(info, key)
        if v and not MODULE_RE.match(v):
            raise KitError(f"kit.json: '{key}' is not a module path: {v!r}")
    if any(c in info.title for c in '<>:"/\\|?*'):
        raise KitError("kit.json: the title may not hold any of < > : \" / \\ | ? * (it names a file)")
    return info


def version_message(info: KitInfo, app_version: str) -> str:
    """'' when the kit was made for this app version, else what to do, in plain words."""
    from .updates import parse_version
    v = parse_version(app_version)
    if v < parse_version(info.app_min) or (info.app_max and v > parse_version(info.app_max)):
        if v < parse_version(info.app_min):
            return (f"This kit was made for {info.made_for()}. Update Fresing Render (Help > Check for updates), "
                    f"then add the kit again.")
        return f"This kit was made for {info.made_for()}. Download the kit's newer version."
    return ""


# ---------------------------------------------------------------------------
# the zip
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> bool:
    if not name or name.startswith(("/", "\\")) or "\\" in name or ":" in name:
        return False
    return all(p not in ("..", "") for p in name.rstrip("/").split("/"))


def check_zip(path: str) -> tuple[KitInfo, str]:
    """(kit.json, the top folder's name) of a kit zip, checked (raises KitError)."""
    if not os.path.isfile(path):
        raise KitError(f"There is no file {path}")
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise KitError(f"{os.path.basename(path)} is not a zip file ({exc})") from exc
    with zf:
        infos = zf.infolist()
        if not infos:
            raise KitError("The zip is empty")
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise KitError("The zip is too big for a demo kit")
        tops = set()
        for i in infos:
            if not _safe_name(i.filename):
                raise KitError(f"The zip holds a file outside its folder: {i.filename!r}")
            if (i.external_attr >> 16) & 0o170000 == 0o120000:
                raise KitError(f"The zip holds a link: {i.filename!r}")
            tops.add(i.filename.split("/", 1)[0])
            if "/" not in i.filename.rstrip("/") and not i.is_dir():
                raise KitError(f"Every file of a kit lies in one folder: {i.filename!r} does not")
        if len(tops) != 1:
            raise KitError("Every file of a kit lies in ONE folder; this zip has " + ", ".join(sorted(tops)[:4]))
        top = tops.pop()
        try:
            raw = zf.read(f"{top}/{KIT_JSON}")
        except KeyError as exc:
            raise KitError(f"The zip has no {top}/{KIT_JSON}: is it a demo kit?") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise KitError(f"kit.json cannot be read: {exc}") from exc
    return info_from(data), top


def pack(folder: str, zip_path: str, top: str = "") -> str:
    """Zip a kit folder (kit.json at its top) the same way every time; ``top`` = the folder name in the zip."""
    top = top or os.path.basename(os.path.normpath(folder))
    files = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in sorted(names):
            if n.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(root, n)
            files.append((full, top + "/" + os.path.relpath(full, folder).replace(os.sep, "/")))
    os.makedirs(os.path.dirname(os.path.abspath(zip_path)), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, arc in sorted(files, key=lambda x: x[1]):
            zi = zipfile.ZipInfo(arc, ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(full, "rb") as fh:
                zf.writestr(zi, fh.read())
    return zip_path


# ---------------------------------------------------------------------------
# the kits folder
# ---------------------------------------------------------------------------

def add(zip_path: str, kits_dir: str, app_version: str) -> KitInfo:
    """Check a kit zip and unpack it into ``<kits_dir>/<id>/`` (an older copy of that id is replaced)."""
    info, top = check_zip(zip_path)
    msg = version_message(info, app_version)
    if msg:
        raise KitError(msg)
    os.makedirs(kits_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".adding-", dir=kits_dir)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for i in zf.infolist():
                if i.is_dir():
                    continue
                rel = i.filename.split("/", 1)[1]
                dest = os.path.join(tmp, *rel.split("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(i) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
        final = os.path.join(kits_dir, info.id)
        if os.path.exists(final):
            old = final + ".old"
            shutil.rmtree(old, ignore_errors=True)
            os.replace(final, old)
            shutil.rmtree(old, ignore_errors=True)
        os.replace(tmp, final)
    except OSError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        raise KitError(f"The kit could not be unpacked into {kits_dir}: {exc}") from exc
    info.folder = os.path.join(kits_dir, info.id)
    return info


def get(kits_dir: str, kit_id: str) -> KitInfo | None:
    """An added kit, or None (not there or its kit.json broken)."""
    if not ID_RE.match(kit_id or ""):
        return None
    folder = os.path.join(kits_dir, kit_id)
    try:
        with open(os.path.join(folder, KIT_JSON), encoding="utf-8") as fh:
            info = info_from(json.load(fh), folder)
    except (OSError, ValueError, KitError):
        return None
    return info if info.id == kit_id else None


def list_kits(kits_dir: str) -> list[KitInfo]:
    """Every added kit, by title."""
    try:
        names = sorted(os.listdir(kits_dir))
    except OSError:
        return []
    found = [get(kits_dir, n) for n in names if ID_RE.match(n)]
    return sorted((k for k in found if k is not None), key=lambda k: (k.title.lower(), k.id))


def remove(kits_dir: str, kit_id: str) -> bool:
    """Delete an added kit (its made demo projects stay). False when it was not there."""
    if not ID_RE.match(kit_id or ""):
        return False
    folder = os.path.join(kits_dir, kit_id)
    if not os.path.isdir(folder):
        return False
    shutil.rmtree(folder, ignore_errors=True)
    if os.path.exists(folder):
        raise KitError(f"The kit could not be removed: a file in {folder} is open")
    return True


# ---------------------------------------------------------------------------
# loading a kit's code
# ---------------------------------------------------------------------------

class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """``fresing_app[.x.y]`` = the app's own modules (the same objects, not copies)."""

    def __init__(self, alias: str, real: str):
        self.alias, self.real = alias, real
        self._specs: dict = {}

    def find_spec(self, name, path=None, target=None):
        if name != self.alias and not name.startswith(self.alias + "."):
            return None
        real = self.real + name[len(self.alias):]
        try:
            importlib.import_module(real)
        except ImportError:
            return None
        return importlib.util.spec_from_loader(name, self, is_package=hasattr(sys.modules[real], "__path__"))

    def create_module(self, spec):
        module = sys.modules[self.real + spec.name[len(self.alias):]]
        self._specs[spec.name] = module.__spec__      # importlib puts the alias's spec on it: put the real one back
        return module

    def exec_module(self, module):
        real = self._specs.pop(module.__spec__.name, None)
        if real is not None:
            module.__spec__ = real


def _kit_modules(folder: str) -> list[str]:
    """Top-level module and package names a kit folder brings."""
    out = []
    try:
        for n in os.listdir(folder):
            p = os.path.join(folder, n)
            if os.path.isdir(p) and os.path.isfile(os.path.join(p, "__init__.py")):
                out.append(n)
            elif n.endswith(".py"):
                out.append(n[:-3])
    except OSError:
        pass
    return out


@contextlib.contextmanager
def loaded(folder: str, app_package: str, alias: str = ALIAS):
    """While inside: the kit's folder on ``sys.path`` and the app importable as ``fresing_app``. On the way out the
    kit's modules and the alias are forgotten again (a second build imports the kit afresh)."""
    tops = _kit_modules(folder)
    clash = [t for t in tops if t in sys.modules and not _inside(sys.modules[t], folder)]
    if clash:
        raise KitError(f"The kit's module {clash[0]!r} has the name of a module the app already uses: rename it")
    finder = _Alias(alias, app_package)
    sys.path.insert(0, folder)
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        try:
            sys.meta_path.remove(finder)
        except ValueError:
            pass
        try:
            sys.path.remove(folder)
        except ValueError:
            pass
        for name in list(sys.modules):
            top = name.split(".", 1)[0]
            if top == alias or top in tops:
                del sys.modules[name]
        importlib.invalidate_caches()


def _inside(module, folder: str) -> bool:
    f = getattr(module, "__file__", None) or ""
    return bool(f) and os.path.normcase(os.path.abspath(f)).startswith(os.path.normcase(os.path.abspath(folder)))


def missing_uses(info: KitInfo, app_package: str) -> list[str]:
    """The names in ``uses`` this app does not have (``blender.demo.stage``: module ``blender.demo``, name ``stage``)."""
    gone = []
    for name in info.uses:
        parts = name.split(".")
        ok = False
        for cut in range(len(parts), -1, -1):
            mod_name = ".".join([app_package] + parts[:cut])
            try:
                obj = importlib.import_module(mod_name)
            except ImportError:
                continue
            try:
                for attr in parts[cut:]:
                    obj = getattr(obj, attr)
                ok = True
            except AttributeError:
                pass
            break
        if not ok:
            gone.append(name)
    return gone
