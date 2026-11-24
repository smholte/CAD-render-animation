"""Lead motions on the web 3D page (task 0310), no Blender: the numbers of the clips and of the page's mixing.

A lead motion (task 0309, ``core/lead_motions.py``) moves joints; the page gets **one glTF clip per joint** the lead
motions use – the parts' places while that joint alone goes from the lowest to the highest value any lead motion gives
it (clip time 0 … 1 s = ``(value − lo) / (hi − lo)``) – and the lead motions' **rows** (joint, values, windows, easing)
as plain data. The page works out each joint's value from the sliders exactly as the app does (``joint_values``, the
same formulas as ``core/lead_motions.values``; a joint in two lead motions takes the value of the one moved last –
0309's rule) and puts the joints' clips together as moves of the world: a joint's move of a part is
``D = M(v) · M0⁻¹`` (M0 = the part's place in the file, the export's pose), the part's place ``D_last · … · D_first · M0``
– exact for joints that ride on joints (a trolley on a boom) when the carrier's move comes last. Which joint carries
which is measured at export (``outer``, both joints set at once in Blender) and handed to the page as one ``apply``
number per joint (``apply_order``).

``mixed`` is the page's sum in plain Python (fr_page.js ``leadPose`` does the same): the tests compare both with Blender.
Why one clip per joint and not per lead motion: two lead motions that share a joint (the crane's "Boom up and out" and
"Boom up") cannot be put together from their own clips – the trolley's place mixes both joints – but from the joints'
clips they can, exactly as in the app; and a joint used by several lead motions is in the file once.
"""

from __future__ import annotations

import numpy as np

from . import lead_motions as lm_core

STEPS = 100                    # joint values read per clip (the keys are thinned afterwards)


def joint_ranges(lms) -> dict:
    """{joint: (lo, hi)}: the lowest and highest value any lead motion gives each joint (rad / m)."""
    out: dict = {}
    for lm in lms:
        for r in lm_core._rows(lm):
            lo, hi = sorted((float(r.v0), float(r.v1)))
            if r.joint in out:
                lo, hi = min(lo, out[r.joint][0]), max(hi, out[r.joint][1])
            out[r.joint] = (lo, hi)
    return out


def values(lo: float, hi: float, steps: int = STEPS) -> np.ndarray:
    """The joint values read for a clip: ``steps`` even steps from lo to hi."""
    if hi - lo < 1e-12:
        return np.array([lo, lo])
    return np.linspace(lo, hi, max(2, int(steps)) + 1)


def clip_time(v, lo: float, hi: float):
    """The clip's time (0 … 1) of a joint value."""
    if hi - lo < 1e-12:
        return np.zeros_like(np.asarray(v, np.float64))
    return np.clip((np.asarray(v, np.float64) - lo) / (hi - lo), 0.0, 1.0)


def far_index(mats: np.ndarray, rest: np.ndarray) -> int:
    """The read value where the parts are furthest from the export's pose (``mats`` (V, N, 4, 4), ``rest``
    (N, 4, 4)): the moment used to measure which of two joints is the carrier."""
    d = np.abs(np.asarray(mats, np.float64) - np.asarray(rest, np.float64)[None]).reshape(len(mats), -1).max(axis=1)
    return int(np.argmax(d)) if len(d) else 0


def delta(m: np.ndarray, m0: np.ndarray) -> np.ndarray:
    """The move of the world that takes a part from ``m0`` to ``m`` (4 x 4, or stacks of them)."""
    return np.asarray(m, np.float64) @ np.linalg.inv(np.asarray(m0, np.float64))


def outer(m0: np.ndarray, ma: np.ndarray, mb: np.ndarray, both: np.ndarray, reach: np.ndarray | None = None) -> int:
    """Which of two joints carries the other on the parts both move: ``m0`` (N, 4, 4) their places in the file, ``ma``
    / ``mb`` with only A / only B moved, ``both`` with both moved (Blender). +1: A is the carrier (applied last),
    -1: B, 0: either order gives the same places. ``reach``: each part's size (m), so a turn counts at its far end."""
    da, db = delta(ma, m0), delta(mb, m0)
    m0 = np.asarray(m0, np.float64)
    both = np.asarray(both, np.float64)
    w = np.ones(len(m0)) if reach is None else np.maximum(np.asarray(reach, np.float64), 1e-3)

    def err(m):
        e_t = np.linalg.norm(m[:, :3, 3] - both[:, :3, 3], axis=1)
        e_r = np.abs(m[:, :3, :3] - both[:, :3, :3]).max(axis=(1, 2)) * w
        return float(np.maximum(e_t, e_r).max(initial=0.0))

    ea, eb = err(da @ db @ m0), err(db @ da @ m0)
    if abs(ea - eb) <= 1e-6 + 1e-4 * min(ea, eb):
        return 0
    return 1 if ea < eb else -1


def apply_order(n: int, carriers: dict, sizes=None) -> list:
    """One ``apply`` number per joint (0 = applied first): ``carriers`` {(i, j): +1 if i carries j, -1 if j carries i};
    a carrier comes after what rides on it. Without a rule (or in a loop of rules) the one moving fewer parts
    (``sizes``) comes first."""
    sizes = list(sizes) if sizes is not None else [0] * n
    after = {i: set() for i in range(n)}              # i must come after these
    for (i, j), s in carriers.items():
        if s > 0:
            after[i].add(j)
        elif s < 0:
            after[j].add(i)
    order: list = []
    left = set(range(n))
    while left:
        ready = [i for i in left if not (after[i] & left)] or list(left)
        i = min(ready, key=lambda k: (sizes[k], k))
        order.append(i)
        left.discard(i)
    out = [0] * n
    for k, i in enumerate(order):
        out[i] = k
    return out


def joint_values(motions: list, positions: list, used: list) -> dict:
    """{joint id: value} the sliders give (fr_page.js ``jointValues``): ``motions`` = the page's lead motions
    (``rows`` with ``j`` = joint id), ``positions`` their sliders (%), ``used[k]`` when lead motion k was last moved (0:
    never; higher = later). A joint in several of them takes the value of the one moved last; a joint no moved slider
    names is not set (it stays as in the file)."""
    out: dict = {}
    for k in sorted((k for k in range(len(motions)) if used[k]), key=lambda k: used[k]):
        rows = [lm_core.Row(r["j"], r["v0"], r["v1"], r["start"], r["end"], r["easing"]) for r in motions[k]["rows"]]
        out.update(lm_core.values(rows, positions[k]))
    return out


def mixed(rest: np.ndarray, places: dict, apply: dict) -> np.ndarray:
    """The parts' places the page shows (fr_page.js ``leadPose``): ``rest`` (N, 4, 4) their places in the file;
    ``places`` {joint id: (N, 4, 4) the places its clip gives at the joint's value, NaN where the clip does not move a
    part}; ``apply`` {joint id: its order}."""
    rest = np.asarray(rest, np.float64)
    out = rest.copy()
    inv = np.linalg.inv(rest)
    for j in sorted(places, key=lambda j: apply[j]):
        c = np.asarray(places[j], np.float64)
        on = ~np.isnan(c[:, 0, 0])
        if on.any():
            out[on] = c[on] @ inv[on] @ out[on]
    return out


def motion_entry(lm, joint_ids: dict, at, ends) -> dict:
    """A lead motion in the page's settings (``ST.lead.motions``): name, description, seconds, its rows with joint ids,
    the slider position of the export's pose (``at``, None when none fits) and the slider's two end labels."""
    return {"name": lm.name, "about": getattr(lm, "description", "") or "", "seconds": round(float(lm.seconds), 3),
            "rows": [{"j": int(joint_ids[r.joint]), "v0": float(r.v0), "v1": float(r.v1), "start": float(r.start),
                      "end": float(r.end), "easing": r.easing if r.easing in lm_core.EASINGS else "SMOOTH"}
                     for r in lm_core._rows(lm) if r.joint in joint_ids],
            "at": None if at is None else round(float(at), 3), "ends": [str(e) for e in ends]}


def joint_entry(clip: int, lo: float, hi: float, apply: int, kind: str, parts: int) -> dict:
    """A joint in the page's settings (``ST.lead.joints``): its clip, value range, order and kind."""
    return {"clip": int(clip), "lo": float(lo), "hi": float(hi), "apply": int(apply), "kind": str(kind),
            "parts": int(parts)}


# ---------------------------------------------------------------------------
# reading a file back as the page plays it (tests, the PC check)
# ---------------------------------------------------------------------------

def _trs(t, q, s) -> np.ndarray:
    from . import web3d_keys
    m = np.eye(4)
    m[:3, :3] = web3d_keys.rot_matrix(np.asarray(q, np.float64)[None])[0] * np.asarray(s, np.float64)[None, :]
    m[:3, 3] = t
    return m


def file_places(doc: dict, node_ids: list) -> np.ndarray:
    """The places of these nodes as the file holds them (their parent's coordinates), (N, 4, 4)."""
    out = []
    for n in node_ids:
        nd = doc["nodes"][n]
        if "matrix" in nd:
            out.append(np.array(nd["matrix"], np.float64).reshape(4, 4).T)
        else:
            out.append(_trs(nd.get("translation", [0, 0, 0]), nd.get("rotation", [0, 0, 0, 1]),
                            nd.get("scale", [1, 1, 1])))
    return np.array(out)


def clip_places(doc: dict, binary: bytes, clip: int, node_ids: list, t: float) -> np.ndarray:
    """The places a clip gives these nodes at its time ``t`` as three.js plays it, NaN where it does not move one."""
    from . import web3d, web3d_keys
    anim = doc["animations"][clip]
    got: dict = {}
    for c in anim["channels"]:
        smp = anim["samplers"][c["sampler"]]
        kt = web3d.accessor_array(doc, binary, smp["input"])[:, 0].astype(np.float64)
        kv = web3d.accessor_array(doc, binary, smp["output"]).astype(np.float64)
        got.setdefault(c["target"]["node"], {})[c["target"]["path"]] = web3d_keys.played(kt, kv, [t],
                                                                                          c["target"]["path"])[0]
    out = np.full((len(node_ids), 4, 4), np.nan)
    for k, n in enumerate(node_ids):
        if n in got:
            nd = doc["nodes"][n]
            out[k] = _trs(got[n].get("translation", nd.get("translation", [0, 0, 0])),
                          got[n].get("rotation", nd.get("rotation", [0, 0, 0, 1])), nd.get("scale", [1, 1, 1]))
    return out


def page_places(doc: dict, binary: bytes, block: dict, node_ids: list, moves: list) -> np.ndarray:
    """What the page shows these nodes after the slider moves ``moves`` = [(lead motion index, %), …] in that order
    (``block`` = the page's ``ST.lead``)."""
    motions = block["motions"]
    pos, used = [0.0] * len(motions), [0] * len(motions)
    for n, (k, p) in enumerate(moves):
        pos[k], used[k] = float(p), n + 1
    vals = joint_values(motions, pos, used)
    js = block["joints"]
    places = {j: clip_places(doc, binary, js[j]["clip"], node_ids, float(clip_time(v, js[j]["lo"], js[j]["hi"])))
              for j, v in vals.items()}
    return mixed(file_places(doc, node_ids), places, {j: js[j]["apply"] for j in vals})
