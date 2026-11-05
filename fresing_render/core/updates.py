"""Updates from GitHub, without Blender: versions, the update listing, the changelog, downloads.

How updates reach a PC (task 0020):
* GitHub publishes every new version on ``main`` as a release (``.github/workflows/tests.yml``,
  job "Publish the release"). Each release carries the installer zip, the extension zip,
  ``index.json`` (Blender's standard extension listing) and ``changelog.json`` (what changed in
  every version, from ``CHANGELOG.md``).
* ``https://github.com/<repo>/releases/latest/download/index.json`` always points at the newest
  release, so the app only needs that one address.
* The app reads it at start-up (``blender/updates.py``), downloads the extension zip when the
  user presses Update and checks it against the size and SHA-256 in ``index.json``; then
  ``update_helper.py`` installs it while Blender is closed and starts the app again.

Everything here is plain Python so it can be tested without Blender.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO = "smholte/CAD-render-animation"
DEFAULT_INDEX_URL = f"https://github.com/{REPO}/releases/latest/download/index.json"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
INDEX_NAME = "index.json"
CHANGELOG_NAME = "changelog.json"
PKG_ID = "fresing_render"
URL_ENV = "FRESING_UPDATE_URL"           # tests (and special cases): another update address
URL_FILE = "fresing_update.json"         # in Blender's config folder: {"url": ...} written by Install.bat -UpdateUrl
TIMEOUT = 20                             # seconds per network call
SELF_UPDATING_SINCE = "0.2.15"           # the first version with Update now (older ones need the installer once)


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^\s*v?(\d+(?:\.\d+)*)(?:[-+]?([0-9A-Za-z.\-]+))?\s*$")


def parse_version(text: str) -> tuple:
    """'0.2.14' -> ((0, 2, 14), 1, ''); a pre-release ('0.2.14-rc.1') sorts before its release.

    Unreadable text sorts below every real version."""
    m = _VERSION_RE.match(str(text or ""))
    if not m:
        return ((), 0, "")
    nums = tuple(int(p) for p in m.group(1).split("."))
    while len(nums) > 1 and nums[-1] == 0:           # 0.3 == 0.3.0
        nums = nums[:-1]
    pre = m.group(2) or ""
    return (nums, 0 if pre else 1, pre)


def is_newer(candidate: str, installed: str) -> bool:
    return parse_version(candidate) > parse_version(installed)


def _version_tuple3(text: str) -> tuple[int, int, int]:
    nums = list(parse_version(text)[0]) + [0, 0, 0]
    return tuple(nums[:3])


# ---------------------------------------------------------------------------
# the update listing (index.json)
# ---------------------------------------------------------------------------

PLATFORM_ENV = "FRESING_UPDATE_PLATFORM"   # tests: look for another kind of computer's package


def platform_tag() -> str:
    """Blender's name for this kind of computer, as in the manifest's ``platforms``."""
    if os.environ.get(PLATFORM_ENV):
        return os.environ[PLATFORM_ENV]
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    if sys.platform == "win32":
        return f"windows-{arch}"
    if sys.platform == "darwin":
        return f"macos-{arch}"
    return f"linux-{arch}"


def archive_url(index_url: str, url: str) -> str:
    """Where a package's zip is: relative names ('./x.zip') sit next to index.json (as Blender
    reads them); full addresses are kept."""
    if not url.startswith("./"):
        return url
    base = index_url
    if base.rstrip("/").endswith(INDEX_NAME):
        base = base.rstrip("/")[: -len(INDEX_NAME)]
    elif not base.endswith("/"):
        base += "/"
    return base + url[2:]


def sibling_url(index_url: str, name: str) -> str:
    """Another file next to index.json (changelog.json)."""
    return archive_url(index_url, "./" + name)


def pick_package(index: dict, *, pkg_id: str = PKG_ID, platform_name: str | None = None,
                 blender_version: tuple[int, int, int] | None = None) -> tuple[dict | None, dict | None]:
    """(newest package this PC can install, newest package of any kind).

    The second one differs when the newest version needs another Blender or another kind of
    computer: then it has to come with a new installer."""
    platform_name = platform_name or platform_tag()
    best = newest = None
    for item in (index or {}).get("data", []) or []:
        if not isinstance(item, dict) or item.get("id") != pkg_id or not item.get("version"):
            continue
        if newest is None or is_newer(item["version"], newest["version"]):
            newest = item
        plats = item.get("platforms") or []
        if plats and platform_name not in plats:
            continue
        if blender_version is not None:
            lo = item.get("blender_version_min")
            hi = item.get("blender_version_max")
            if lo and tuple(blender_version) < _version_tuple3(lo):
                continue
            if hi and tuple(blender_version) >= _version_tuple3(hi):
                continue
        if best is None or is_newer(item["version"], best["version"]):
            best = item
    return best, newest


def sha256_of(item: dict) -> str:
    """The SHA-256 written in index.json ('sha256:<hex>'), '' when there is none."""
    h = str(item.get("archive_hash") or "")
    return h.split(":", 1)[1].lower() if h.lower().startswith("sha256:") else ""


# ---------------------------------------------------------------------------
# the changelog
# ---------------------------------------------------------------------------

_HEAD_RE = re.compile(r"^##\s+(\d+(?:\.\d+)+\S*)\s*(.*)$")


def parse_changelog(md: str) -> list[dict]:
    """CHANGELOG.md -> [{"version", "date", "title", "text"}], newest first (as in the file).

    A version heading reads '## 0.2.13 – 5 Nov 2026 – rule sets …'; the 'Commit `…`.' line under it
    is left out (it is for developers)."""
    out: list[dict] = []
    cur = None
    for line in md.splitlines():
        m = _HEAD_RE.match(line)
        if m:
            parts = [p.strip() for p in re.split(r"\s+[–—-]\s+", m.group(2).strip(" –—-")) if p.strip()]
            cur = {"version": m.group(1), "date": parts[0] if parts else "",
                   "title": " – ".join(parts[1:]), "lines": []}
            out.append(cur)
            continue
        if line.startswith("## ") or line.startswith("# "):
            cur = None
            continue
        if cur is not None:
            if re.match(r"^Commits?\s+`", line.strip()):
                continue
            cur["lines"].append(line)
    for item in out:
        item["text"] = "\n".join(item.pop("lines")).strip("\n")
    return out


def changes_between(changelog: list[dict], installed: str, newest: str) -> list[dict]:
    """The versions after ``installed`` up to and including ``newest``, newest first."""
    return [c for c in changelog
            if is_newer(c.get("version", ""), installed) and not is_newer(c.get("version", ""), newest)]


def plain(text: str) -> str:
    """Markdown -> plain text for the app's labels: no **bold**, `code` or link syntax."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def whats_new_paragraphs(entries: list[dict]) -> list[tuple[str, list[str]]]:
    """[(heading, [paragraphs])] for the app: one heading per version, one paragraph per list item
    (its wrapped lines joined) and per block of text; section names stay short paragraphs of their own."""
    out = []
    for e in entries:
        head = f"{e.get('version', '')}" + (f" – {e['title']}" if e.get("title") else "")
        paras: list[str] = []
        kind = ""                                   # "item", "text" or "" (after a blank line)
        for raw in (e.get("text") or "").splitlines():
            line = raw.rstrip()
            if not line.strip():
                kind = ""
                continue
            if re.match(r"^\s*[-*]\s+", line):
                paras.append("• " + plain(re.sub(r"^\s*[-*]\s+", "", line)).strip())
                kind = "item"
            elif paras and kind and (raw.startswith((" ", "\t")) or kind == "text"):
                paras[-1] += " " + plain(line.strip())         # the paragraph or list item goes on
            else:
                paras.append(plain(line.strip()))
                kind = "text"
        out.append((head, paras))
    return out


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------

def user_agent(version: str) -> str:
    return f"FresingRender/{version} (update check)"


def _request(url: str, version: str):
    return urllib.request.Request(url, headers={"User-Agent": user_agent(version), "Accept": "*/*"})


def local_path(address: str, windows: bool | None = None) -> str:
    """The file behind an update address on a disk or network share, '' for a web address.

    Accepts plain paths (C:\\x\\index.json, \\\\SERVER\\share\\index.json, /srv/x/index.json) and file:
    addresses (file:///C:/x/index.json, file://SERVER/share/index.json, file:////SERVER/share/…), with
    %-escapes. urllib itself cannot open file://SERVER/… (it says "file not on local host")."""
    windows = sys.platform == "win32" if windows is None else windows
    if not address.lower().startswith("file:"):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]+://", address):
            return ""                                  # http(s) and the like
        return address                                 # a plain path
    parts = urllib.parse.urlsplit(address)
    host = parts.netloc if parts.netloc.lower() not in ("", "localhost") else ""
    path = urllib.parse.unquote(parts.path)
    if windows:
        if host:
            return "\\\\" + host + path.replace("/", "\\")
        path = path.replace("/", "\\")
        if re.match(r"^\\[a-zA-Z]:", path):          # \C:\x -> C:\x
            path = path[1:]
        elif path.startswith("\\\\"):                 # file:////SERVER/share (any number of slashes) -> \\SERVER\share
            path = "\\\\" + path.lstrip("\\")
        return path
    return ("//" + host + path) if host else path


class _LocalFile:
    """A file on disk with the little of urlopen's answer that is used here."""

    def __init__(self, path: str):
        self._fh = open(path, "rb")
        self.headers = {"Content-Length": str(os.path.getsize(path))}

    def read(self, n: int = -1) -> bytes:
        return self._fh.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._fh.close()


def _open(url: str, version: str, timeout: float):
    path = local_path(url)
    if path:
        try:
            return _LocalFile(path)
        except OSError as exc:
            raise urllib.error.URLError(exc) from exc
    return urllib.request.urlopen(_request(url, version), timeout=timeout)      # noqa: S310 - update address


def fetch_json(url: str, version: str = "", timeout: float = TIMEOUT) -> dict:
    with _open(url, version, timeout) as resp:
        data = resp.read(5_000_000)
    return json.loads(data.decode("utf-8-sig"))


def describe_error(exc: BaseException) -> str:
    """A network error in plain words."""
    import socket
    import urllib.error
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "no published version found at the update address (HTTP 404)"
        return f"the update server answered with an error (HTTP {exc.code})"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "no answer from the update server (time-out): check the internet connection"
        return f"could not reach the update server ({reason}): check the internet connection or firewall"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "no answer from the update server (time-out): check the internet connection"
    if isinstance(exc, ValueError):
        return "the update listing could not be read"
    return f"{type(exc).__name__}: {exc}"


class DownloadError(Exception):
    pass


def download(url: str, dest: str, *, size: int = 0, sha256: str = "", version: str = "",
             progress=None, should_stop=None, timeout: float = TIMEOUT) -> str:
    """Download ``url`` to ``dest`` (through ``dest + '.part'``), check size and SHA-256.

    ``progress(done_bytes, total_bytes)`` is called now and then; ``should_stop()`` returning True
    stops the download (DownloadError). Returns ``dest``."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    part = dest + ".part"
    digest = hashlib.sha256()
    done = 0
    try:
        with _open(url, version, timeout) as resp, open(part, "wb") as fh:
            total = size or int(resp.headers.get("Content-Length") or 0)
            while True:
                if should_stop and should_stop():
                    raise DownloadError("stopped")
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if size and done != size:
            raise DownloadError(f"the download is incomplete ({done} of {size} bytes)")
        if sha256 and digest.hexdigest().lower() != sha256.lower():
            raise DownloadError("the download is damaged (its checksum does not match)")
        os.replace(part, dest)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return dest


def check(index_url: str, installed: str, blender_version: tuple[int, int, int] | None = None,
          platform_name: str | None = None, timeout: float = TIMEOUT) -> dict:
    """Ask the update address whether there is a newer version.

    Returns a dict with ``state``:
      "available"        a newer version this PC can install: version, url, size, sha256, date, changes
      "needs_installer"  the newer version needs a new installer (another Blender): version
      "none"             nothing newer (``version`` = newest published)
      "error"            ``message`` says why in plain words
    """
    res = {"index_url": index_url, "installed": installed, "release_page": release_page("", index_url)}
    try:
        index = fetch_json(index_url, installed, timeout)
    except Exception as exc:  # noqa: BLE001 - any network or format problem is reported, never raised
        return dict(res, state="error", message=describe_error(exc))
    best, newest = pick_package(index, platform_name=platform_name, blender_version=blender_version)
    if newest is None:
        return dict(res, state="error", message="the update listing has no Fresing Render in it")
    if best is None or not is_newer(best["version"], installed):
        if is_newer(newest["version"], installed):
            return dict(res, state="needs_installer", version=newest["version"],
                        release_page=release_page(newest["version"], index_url))
        return dict(res, state="none", version=(best or newest)["version"])
    res.update(state="available", version=best["version"], url=archive_url(index_url, best.get("archive_url", "")),
               size=int(best.get("archive_size") or 0), sha256=sha256_of(best), changes=[], date="",
               release_page=release_page(best["version"], index_url))
    try:
        log = fetch_json(sibling_url(index_url, CHANGELOG_NAME), installed, timeout)
        entries = changes_between(log.get("versions", []), installed, best["version"])
        res["changes"] = entries
        res["date"] = next((e.get("date", "") for e in entries if e.get("version") == best["version"]), "")
    except Exception:  # noqa: BLE001 - "what's new" is a nice-to-have; the update works without it
        pass
    return res


# ---------------------------------------------------------------------------
# which address to use
# ---------------------------------------------------------------------------

def index_url_from(config_dir: str = "", env: dict | None = None) -> tuple[str, str]:
    """(update address, where it came from): the FRESING_UPDATE_URL environment variable, then
    ``<config>/fresing_update.json`` (Install.bat -UpdateUrl), then GitHub."""
    env = os.environ if env is None else env
    if env.get(URL_ENV):
        return env[URL_ENV].strip(), "environment variable " + URL_ENV
    if config_dir:
        path = os.path.join(config_dir, URL_FILE)
        try:
            with open(path, encoding="utf-8-sig") as fh:
                url = str(json.load(fh).get("url") or "").strip()
            if url:
                return url, path
        except (OSError, ValueError, AttributeError):
            pass
    return DEFAULT_INDEX_URL, "GitHub"


def release_page(version: str, index_url: str) -> str:
    """The release page of a version on GitHub; for another update address its folder."""
    if index_url == DEFAULT_INDEX_URL or "github.com/" + REPO.lower() in index_url.lower():
        return f"{RELEASES_PAGE}/tag/v{version}" if version else RELEASES_PAGE
    return sibling_url(index_url, "")


def file_url_to_path(url: str) -> str:
    """file:///C:/x/index.json -> C:\\x\\index.json (for messages)."""
    if not url.startswith("file:"):
        return url
    return urllib.request.url2pathname(urllib.parse.urlparse(url).path)
