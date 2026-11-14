"""Opening and writing the two packages (.hpscene, .hpbake) – zip files, read safely (FORMAT.md section 2)."""
from __future__ import annotations

import io
import json
import zipfile

MAX_ENTRY = 512 * 1024 * 1024      # one file in a package: 512 MB
MAX_TOTAL = 2 * 1024 * 1024 * 1024  # all files unpacked: 2 GB
MAX_FILES = 10000
FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # every file's date in packages the sample script writes (same bytes every run)

KINDS = {"scene.json": ("house-scene", ".hpscene"), "bake.json": ("house-bake", ".hpbake")}


class PackageError(ValueError):
    pass


def _no_constant(name):
    raise ValueError(f"{name} is not allowed (JSON has no NaN or Infinity)")


def control_text(obj, at="") -> str | None:
    """Where a text (or a key) holds a control character such as a line break – not allowed anywhere in the
    format's JSON (JavaScript and Python would read patterns differently)."""
    if isinstance(obj, str):
        return f"text at {at or '(top)'} holds a control character" if any(ord(c) < 32 or ord(c) == 127
                                                                             for c in obj) else None
    if isinstance(obj, dict):
        for k, v in obj.items():
            r = control_text(k, at + "/" + str(k)[:20]) or control_text(v, at + "/" + str(k)[:20])
            if r:
                return r
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            r = control_text(v, f"{at}/{i}")
            if r:
                return r
    return None


def safe_name(name: str) -> str | None:
    """Why a path inside a package is not allowed, or None when it is fine."""
    if not name or name.startswith("/") or "\\" in name or ":" in name.split("/")[0]:
        return "must be a relative path with forward slashes"
    if any(part in ("", ".", "..") for part in name.rstrip("/").split("/")):
        return "must not contain empty parts, '.' or '..'"
    return None


class Package:
    """The files of a package in memory: ``.files`` {path: bytes}, ``.kind`` "house-scene" | "house-bake",
    ``.doc`` the parsed scene.json / bake.json."""

    def __init__(self, files: dict[str, bytes], name: str = ""):
        self.files = files
        self.name = name
        main = [k for k in KINDS if k in files]
        if len(main) != 1:
            raise PackageError("a package holds exactly one of scene.json or bake.json at its top level")
        self.main = main[0]
        self.kind = KINDS[self.main][0]
        try:
            self.doc = json.loads(files[self.main].decode("utf-8"), parse_constant=_no_constant)
        except (UnicodeDecodeError, ValueError) as e:
            raise PackageError(f"{self.main} is not valid JSON (UTF-8): {e}") from None
        if not isinstance(self.doc, dict):
            raise PackageError(f"{self.main} must hold a JSON object")
        bad = control_text(self.doc)
        if bad:
            raise PackageError(f"{self.main}: {bad}")

    @classmethod
    def open(cls, path_or_bytes) -> "Package":
        data = path_or_bytes
        name = ""
        if not isinstance(path_or_bytes, (bytes, bytearray)):
            name = str(path_or_bytes)
            with open(path_or_bytes, "rb") as f:
                data = f.read()
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise PackageError("not a zip file") from None
        infos = zf.infolist()
        if len(infos) > MAX_FILES:
            raise PackageError(f"more than {MAX_FILES} files")
        total, files = 0, {}
        for info in infos:
            if info.is_dir():
                continue
            why = safe_name(info.filename)
            if why:
                raise PackageError(f"'{info.filename}': {why}")
            if info.filename in files:
                raise PackageError(f"'{info.filename}' is in the zip twice")
            if info.flag_bits & 0x1:
                raise PackageError(f"'{info.filename}' is encrypted")
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise PackageError(f"'{info.filename}': only stored or deflated files are allowed")
            if info.file_size > MAX_ENTRY:
                raise PackageError(f"'{info.filename}' is larger than {MAX_ENTRY // 2**20} MB")
            total += info.file_size
            if total > MAX_TOTAL:
                raise PackageError(f"the files add up to more than {MAX_TOTAL // 2**30} GB")
            with zf.open(info) as f:
                body = f.read(MAX_ENTRY + 1)
            if len(body) != info.file_size:
                raise PackageError(f"'{info.filename}' is not the size the zip says")
            files[info.filename] = body
        return cls(files, name)


def write(path, files: dict[str, bytes]) -> None:
    """Write a package: the main JSON first, every file with the same date, pictures and models stored (they are
    compressed already), JSON deflated. The same files give the same bytes."""
    main = [k for k in files if k in KINDS]
    order = main + sorted(k for k in files if k not in KINDS)
    with zipfile.ZipFile(path, "w") as zf:
        for name in order:
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.external_attr = 0o644 << 16
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED if name.endswith((".json", ".bin")) else zipfile.ZIP_STORED
            zf.writestr(info, files[name], compresslevel=9 if info.compress_type == zipfile.ZIP_DEFLATED else None)
