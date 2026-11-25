"""The app's keys in one list (task 0295) – no Blender.

Settings > Keys shows every key and mouse action of the app in five groups (``GROUPS``): moving the view, selecting,
Fresing's own keys, Blender's keys that still work outside Full access and Blender's keys that do nothing there. The
rows of the last three groups are made from the live key lists of ``blender/lock.py`` (``APP_KEYS``,
``BLENDER_KEYS``) by ``blender/keys.py``: a key added there shows here by itself. This module holds what needs no
Blender:

* ``Row`` – one line of the list; ``label`` writes a key for people ("Ctrl+F12", "Delete", "Numpad 1").
* **Changing a key** – Fresing's own keys named in ``OWN`` can be given another key. The changes are a small dict
  ``{own id: {"key": "K", "ctrl": true, ...}}``, kept as JSON text in the settings file (task 0283: Blender forgets an
  extension's preferences over a restart); ``read_changes`` / ``write_changes`` never fail on a bad text.
* ``check_new`` – may this key be used? Refused: keys the app needs as they are (Esc, Return, the left and middle
  mouse, the wheel, a modifier alone) and a key another of Fresing's own keys has; a warning (taken anyway): a key
  Blender uses in the 3D view.
* ``sheet_html`` – the printable key sheet, one A4 page in the Fresing look.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field

GROUPS = (
    ("view", "Move the view"),
    ("select", "Select"),
    ("own", "Fresing's own keys"),
    ("kept", "Blender keys that still work"),
    ("off", "Blender keys that do nothing outside Full access"),
)
GROUP_KEYS = tuple(g[0] for g in GROUPS)

MODS = ("ctrl", "shift", "alt")

# Fresing's own keys that can be changed: id -> (operator, default key, default modifiers, what it does). Each
# matches one entry of ``lock.APP_KEYS``; the others there (right-click menu, G / R / S) stay as they are.
OWN = {
    "render_image": ("fresing.key_render", "F12", {}, "Render the picture (as Render image)"),
    "render_animation": ("fresing.key_render", "F12", {"ctrl": True},
                         "Render the animation (in the background)"),
    "remove_x": ("fresing.remove_key", "X", {"any": True}, "Remove what is selected (asks first)"),
    "remove_delete": ("fresing.remove_key", "DEL", {"any": True},
                      "Remove what is selected (asks first)"),
    "copy": ("fresing.copy_key", "C", {"ctrl": True}, "Copy what is selected, with its joints"),
    "paste": ("fresing.paste_key", "V", {"ctrl": True}, "Paste the copy, with its joints"),
    "measure": ("fresing.measure_key", "M", {}, "Measure"),
    "measure_all": ("fresing.measure", "M", {"alt": True}, "Measure (also in Full access)"),
}

# keys a user cannot give to a function: the app and Blender need them as they are
RESERVED = {"ESC": "Esc cancels", "RET": "Return confirms", "NUMPAD_ENTER": "Enter confirms",
            "LEFTMOUSE": "the left mouse button selects", "MIDDLEMOUSE": "the middle mouse button turns the view",
            "WHEELUPMOUSE": "the mouse wheel zooms", "WHEELDOWNMOUSE": "the mouse wheel zooms",
            "WHEELINMOUSE": "the mouse wheel zooms", "WHEELOUTMOUSE": "the mouse wheel zooms",
            "MOUSEMOVE": "", "INBETWEEN_MOUSEMOVE": "", "TRACKPADPAN": "", "TRACKPADZOOM": "", "MOUSEROTATE": "",
            "MOUSESMARTZOOM": "", "TIMER": "", "TIMER0": "", "TIMER1": "", "TIMER2": "", "TIMER_JOBS": "",
            "TIMER_AUTOSAVE": "", "TIMER_REPORT": "", "TIMERREGION": "", "WINDOW_DEACTIVATE": "", "NONE": "",
            "TEXTINPUT": ""}
MODIFIER_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY", "HYPER",
                 "APP"}

NAMES = {"DEL": "Delete", "TAB": "Tab", "PAGE_UP": "Page Up", "PAGE_DOWN": "Page Down", "HOME": "Home", "END": "End",
         "INSERT": "Insert", "SPACE": "Space", "BACK_SPACE": "Backspace", "RET": "Return", "ESC": "Esc",
         "ZERO": "0", "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5", "SIX": "6", "SEVEN": "7",
         "EIGHT": "8", "NINE": "9", "ACCENT_GRAVE": "`", "MINUS": "-", "EQUAL": "=", "COMMA": ",", "PERIOD": ".",
         "SLASH": "/", "BACK_SLASH": "\\", "SEMI_COLON": ";", "QUOTE": "'", "LEFT_BRACKET": "[",
         "RIGHT_BRACKET": "]", "UP_ARROW": "Up", "DOWN_ARROW": "Down", "LEFT_ARROW": "Left", "RIGHT_ARROW": "Right",
         "RIGHTMOUSE": "Right mouse", "LEFTMOUSE": "Left mouse", "MIDDLEMOUSE": "Middle mouse", "APP": "Menu key",
         "NUMPAD_PERIOD": "Numpad .", "NUMPAD_ENTER": "Numpad Enter", "NUMPAD_PLUS": "Numpad +",
         "NUMPAD_MINUS": "Numpad -", "NUMPAD_ASTERIX": "Numpad *", "NUMPAD_SLASH": "Numpad /",
         "BUTTON4MOUSE": "Mouse button 4", "BUTTON5MOUSE": "Mouse button 5"}


@dataclass(frozen=True)
class Row:
    """One line of the key list."""
    group: str                 # a key of GROUPS
    what: str                  # what it does, in plain words
    key: str                   # the key as people write it ("Ctrl+F12")
    where: str = "3D view"     # where it works
    id: str = ""               # Fresing's own changeable key: its id in OWN
    default: str = ""          # a changed key: the key it had
    note: str = ""             # e.g. "works in Full access"

    @property
    def changed(self) -> bool:
        return bool(self.default) and self.default != self.key


@dataclass
class Check:
    """The answer of ``check_new``: ok (it may be used), a refusal or warnings in plain words."""
    ok: bool
    refusal: str = ""
    warnings: list = field(default_factory=list)


def key_name(key: str) -> str:
    if key in NAMES:
        return NAMES[key]
    if key.startswith("NUMPAD_") and key[7:].isdigit():
        return "Numpad " + key[7:]
    if key.startswith("NDOF_"):
        return "3D mouse " + key[5:].replace("_", " ").lower()
    if len(key) <= 3 and key[:1] == "F" and key[1:].isdigit():
        return key
    return key.replace("_", " ").title() if len(key) > 1 else key


def label(key: str, mods: dict | None = None) -> str:
    """"Shift+D", "Ctrl+F12", "Numpad 1": how a key is written for people. ``any`` modifiers are not written."""
    mods = mods or {}
    out = [m.capitalize() for m in MODS if mods.get(m)]
    return "+".join(out + [key_name(key)])


def norm(mods: dict | None) -> dict:
    """Only the modifiers that matter (ctrl / shift / alt / any), each True."""
    return {m: True for m in (*MODS, "any") if (mods or {}).get(m)}


def same(a: tuple, b: tuple) -> bool:
    """Do two keys (type, modifiers) answer the same press? A key with ``any`` answers every modifier."""
    (ka, ma), (kb, mb) = a, b
    if ka != kb:
        return False
    ma, mb = norm(ma), norm(mb)
    if ma.get("any") or mb.get("any"):
        return True
    return all(bool(ma.get(m)) == bool(mb.get(m)) for m in MODS)


# ---------------------------------------------------------------------------
# the stored changes
# ---------------------------------------------------------------------------

def read_changes(text: str) -> dict:
    """{own id: (key, modifiers)} from the stored JSON text; anything odd is left out (never raises)."""
    try:
        data = json.loads(text or "{}")
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for kid, v in data.items():
        if kid not in OWN or not isinstance(v, dict):
            continue
        key = v.get("key")
        if not isinstance(key, str) or not key or key in RESERVED or key in MODIFIER_KEYS:
            continue
        out[kid] = (key, {m: True for m in MODS if v.get(m) is True})
    return out


def write_changes(changes: dict) -> str:
    """The JSON text kept in the settings file; a change back to the default key is left out."""
    data = {}
    for kid, (key, mods) in sorted(changes.items()):
        if kid not in OWN:
            continue
        _op, dkey, dmods, _what = OWN[kid]
        if key == dkey and norm(mods) == norm({m: v for m, v in dmods.items() if m != "any"}):
            continue
        data[kid] = {"key": key, **{m: True for m in MODS if mods.get(m)}}
    return json.dumps(data, sort_keys=True) if data else ""


def own_key(kid: str, changes: dict) -> tuple:
    """(key, modifiers) of one of Fresing's own keys now: the user's change, else the default."""
    if kid in changes:
        return changes[kid]
    _op, key, mods, _what = OWN[kid]
    return key, dict(mods)


def own_id(op: str, key: str, mods: dict) -> str:
    """The id in OWN of an ``APP_KEYS`` entry, or ""."""
    for kid, (o, k, m, _what) in OWN.items():
        if o == op and k == key and norm(m) == norm(mods):
            return kid
    return ""


# ---------------------------------------------------------------------------
# may a key be used?
# ---------------------------------------------------------------------------

def check_new(kid: str, key: str, mods: dict, own_now: dict, blender_taken: list) -> Check:
    """May Fresing's own key ``kid`` get ``key`` + ``mods``? ``own_now`` = {id: (key, mods)} of all own keys as they
    are now; ``blender_taken`` = [(key, mods, what)] of Blender's keys that work in the 3D view."""
    mods = {m: True for m in MODS if (mods or {}).get(m)}
    if kid not in OWN:
        return Check(False, f"'{kid}' is not one of Fresing's own keys")
    if key in MODIFIER_KEYS:
        return Check(False, "Press a key together with Ctrl, Shift or Alt – not Ctrl, Shift or Alt alone")
    if key in RESERVED:
        why = RESERVED[key]
        return Check(False, f"{key_name(key)} cannot be used: {why}" if why else "That cannot be used as a key")
    new = (key, mods)
    for other, (k, m) in own_now.items():
        if other != kid and same(new, (k, m)):
            return Check(False, f"{label(key, mods)} is already Fresing's key for: {OWN[other][3]}")
    warnings = []
    seen = set()
    for k, m, what in blender_taken:
        if same(new, (k, m)) and what not in seen:
            seen.add(what)
            warnings.append(f"{label(key, mods)} is also Blender's key for {what}: outside Full access the Fresing "
                            "key wins")
    return Check(True, "", warnings)


def search(rows: list, text: str) -> list:
    """The rows whose words, key or place hold every word of ``text`` (any case)."""
    words = (text or "").lower().split()
    if not words:
        return list(rows)
    out = []
    for r in rows:
        hay = f"{r.what} {r.key} {r.where} {r.note} {dict(GROUPS).get(r.group, '')}".lower()
        if all(w in hay for w in words):
            out.append(r)
    return out


# ---------------------------------------------------------------------------
# the printable key sheet
# ---------------------------------------------------------------------------

SHEET_CSS = """
@page { size: A4; margin: 12mm; }
* { box-sizing: border-box; }
body { margin: 0; font: 9.5pt/1.35 "IBM Plex Sans", "Segoe UI", system-ui, Arial, sans-serif; color: #252E36;
       background: #FFFFFF; }
.page { max-width: 186mm; margin: 0 auto; padding: 6mm 0; }
header { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 2px solid #479B29;
         padding-bottom: 2mm; margin-bottom: 3mm; }
h1 { font-size: 16pt; margin: 0; color: #252E36; }
h1 span { color: #479B29; }
.meta { color: #5B6670; font-size: 8.5pt; }
.cols { column-count: 2; column-gap: 7mm; }
section { break-inside: avoid; margin-bottom: 3mm; }
h2 { font-size: 10.5pt; margin: 0 0 1mm; color: #2F6A1B; }
table { width: 100%; border-collapse: collapse; }
td { padding: 0.6mm 1mm; border-bottom: 1px solid #D3D9DE; vertical-align: top; }
td.k { width: 34%; font-family: "IBM Plex Mono", Consolas, monospace; font-size: 8.5pt; white-space: nowrap; }
tr.off td { color: #8A949C; }
.changed { color: #479B29; font-weight: 600; }
footer { margin-top: 3mm; color: #5B6670; font-size: 8pt; border-top: 1px solid #D3D9DE; padding-top: 1.5mm; }
.print { float: right; }
@media print { .print { display: none; } .page { padding: 0; } }
"""


def sheet_html(rows: list, version: str = "", date: str = "") -> str:
    """One A4 page: every group with its keys, in the Fresing look. A changed key is marked."""
    e = html.escape
    parts = []
    for gkey, gtitle in GROUPS:
        mine = [r for r in rows if r.group == gkey]
        if not mine:
            continue
        lines = []
        for r in mine:
            what = e(r.what) + (f' <span class="changed">(yours; was {e(r.default)})</span>' if r.changed else "")
            lines.append(f'<tr class="{"off" if gkey == "off" else ""}"><td class="k">{e(r.key)}</td>'
                         f"<td>{what}</td></tr>")
        parts.append(f"<section><h2>{e(gtitle)}</h2><table>{''.join(lines)}</table></section>")
    meta = " · ".join(x for x in (f"Fresing Render {e(version)}" if version else "", e(date)) if x)
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>Fresing Render keys</title><style>{SHEET_CSS}</style></head><body><div class=\"page\">"
            "<button class=\"print\" onclick=\"window.print()\">Print / save as PDF</button>"
            f"<header><h1><span>Fresing</span> Render – keys</h1><div class=\"meta\">{meta}</div></header>"
            f"<div class=\"cols\">{''.join(parts)}</div>"
            "<footer>Outside Full access (every workspace but Full access). In Full access every key is Blender's own: "
            "Fresing &gt; Show all of Blender. Change Fresing's own keys in Fresing &gt; Settings… &gt; Keys.</footer>"
            "</div></body></html>")
