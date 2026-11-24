"""Rust (task 0318): ONE rust look for the whole app – the group's **Rust** slider (``materials.build_nodes``), the
marine streaks and splash zone (``marine_looks``) and the welds (``weld_looks``) all take their rust colour from
``color`` here. Shader nodes only (no pictures, no scripts): Cycles and EEVEE, the render queue, scripts off.

Where a group rusts depends on what it is (``core.materials_lib.rust_kind``):

* **BARE** – bare carbon steel and cast iron: patches 10–40 mm that grow from the corners (ambient occlusion, shared
  with Wear's corner dirt), a thin brown haze over the rest (flash rust at a low value), flaking relief at a high one.
* **PAINTED** – painted steel: only where the paint is worn through (Wear's edges and scratches; a higher Rust also
  wears a little more paint), with short run-down streaks below on upright faces.
* **ZINC** / **PLATED** – galvanized, zinc-plated, chrome / nickel: red rust only where the coating is worn; zinc also
  gets dull white patches (white rust).
* "" – stainless steel, aluminium, brass, copper, plastics …: never red rust; the group shows why instead of a slider.

On the web 3D model's flat bake tiles the corners and edges are gone (``web3d._flatten_shape_nodes``): the patches of
bare steel still bake (their colour holds); the rust at worn edges and in corners needs the part's own shape."""

from __future__ import annotations

#: the rust colours, sRGB: dark pits, red-brown, brown, a little orange where it is loose
STOPS = ((0.0, (0.08, 0.04, 0.025)), (0.45, (0.24, 0.10, 0.04)), (0.75, (0.40, 0.17, 0.06)), (1.0, (0.55, 0.27, 0.10)))
#: the colour of rust as one number set (what a flat tile / the web model / a single streak colour uses), sRGB
MEAN = (0.36, 0.16, 0.06)
#: white rust on zinc, sRGB
WHITE = (0.72, 0.72, 0.69)
#: the material property that says how rusty a group is (the welds read it, task 0319)
PROP = "fr_rust"
#: the node that gives the rust mask of a group's look (tests and tools look it up)
NODE_MASK = "FR rust"


def _lin(c):
    from ..core import ral
    return (*(ral.srgb_to_linear(x) for x in c), 1.0)


def color(b, scale: float = 900.0, x: float = -1100.0, y: float = -1050.0):
    """Rust is not one orange: a colour ramp of a fine noise (``scale`` features per metre). Returns the colour
    socket."""
    n = b.noise(None, scale, 4.0, x=x - 300, y=y)
    r = b.node("ShaderNodeValToRGB", x, y)
    els = r.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = STOPS[0][0], _lin(STOPS[0][1])
    for pos, col in STOPS[1:]:
        e = els.new(pos)
        e.color = _lin(col)
    b.put(r.inputs["Fac"], n)
    return r.outputs["Color"]


def named(sock, name: str = NODE_MASK):
    sock.node.name = name
    sock.node.label = name
    return sock


def mask_value(patch: float, occluded: float, amount: float) -> float:
    """The bare-steel mask in plain Python (what the nodes do; tests): ``patch`` the patch noise 0 … 1, ``occluded``
    1 - AO (0 open, 1 deep in a corner), ``amount`` the slider."""
    lo = 0.70 - 0.35 * amount
    m = min(max((patch + 0.4 * occluded - lo) / 0.06, 0.0), 1.0)
    return min(1.0, m + (1.0 - m) * 0.25 * amount)
