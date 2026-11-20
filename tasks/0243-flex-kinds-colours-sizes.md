# 0243 – Hoses, cables and drag chains: standard kinds, colours and sizes to pick from; open / closed / half-open / steel chains

**Who:** worker · **Status:** running · **Branch:** `claude/funny-clarke-fxi82c`
**Started by:** lead, 20 Nov 2026 (owner 17:36: "for hoses and cables i want to have standard colours and materials to
choose from, and different sizes. also for drag chain different types, open closed. also different sizes"; his picks
17:40 in the answer box below) · **Model:** Opus · effort Medium
**Area:** Flex parts lane – a **new** `core/flex_kinds.py` (the kinds, colours and size lists – no Blender, tested);
`core/flex_chain.py` (link shapes per chain type only); `blender/flex.py`, `ops_flex.py`, `ui_flex.py`; `blender/paths.py`,
`ui_paths.py` (the cable's kind and size only); `blender/cable_looks.py` and the hose / cable materials (new looks);
`props.py` (additive); `core/functions.py`, the PC-check lines, the guide chapters "Hoses and drag chains" + "Cables and
paths" (+ pictures, test models only), the tour set `flex_drawn` (0240's), tests. **Not** the tour sets `hoses`,
`chains`, `cables` (0233's), not `reimport.py`, not `spool.py` / `tracks.py`.

## Goal

Every hose, cable and drag chain – read from a CAD part or drawn by clicking (0240) – gets a **Kind** and a **Size** to
pick from a list. The kind brings the right look and its standard colours; the size brings the outer diameter (or the
chain's width, height, link pitch) and the smallest bend radius in one click. **Custom** unlocks the numbers as today.

## Owner's picks (20 Nov 17:40)

- **Hoses:** hydraulic rubber hose · steel-braided hose · pneumatic tube · protective sleeve (over a hose).
- **Cables and ropes:** drag-chain / machine cable · power cable · offshore power cable (today's "Power cables" look) ·
  wire rope.
- **Drag chains:** open (frame stays) · closed (tube with lids) · half-open (lids on one side) · steel heavy-duty.
- **Sizes:** a standard list per kind, everything follows from the pick, plus **Custom** for free numbers.

## What to do

1. **`core/flex_kinds.py`** – one table per family (hose, cable, chain): each kind with its colours (names + RGB), its
   look id and its size list. Sizes from **public standards where one exists – checked at the source, not from memory**,
   and named in a comment: hydraulic hose DN with outer Ø and smallest bend radius (EN 853 / EN 857 / SAE J517 two-wire
   classes), pneumatic tube outer Ø 4 / 6 / 8 / 10 / 12 / 16 mm (metric OD series) with bend radius, wire rope Ø (EN
   12385-4 series) with D/d for sheaves, steel-braided like hydraulic. Where no standard exists (machine and power cables,
   drag-chain sizes) a sensible **invented** series of outer Ø (cables) and inner height × inner width × pitch × bend
   radii (chains) – generic names ("Chain 25 × 50"), **no maker's names, part numbers or catalogue copies**.
2. **Looks** (shader nodes, as `cable_looks.py`; scripts off; Cycles + EEVEE): hydraulic rubber (black, slight
   texture, a printed text line along it in a generic text, optional coloured ID band at the ends), steel braid (woven
   look by normal + colour, no extra geometry), pneumatic tube (matte coloured PU: blue, black, clear, red, yellow,
   green, silver; clear = see-through), protective sleeve (spiral wrap over the hose: one more tube a little larger
   with a spiral cut-out pattern, black / orange / yellow), drag-chain cable (PUR grey / orange / black / green), power
   cable (black / grey), offshore power cable (today's look, kept exactly), wire rope (today's look + galvanised /
   bright). The colour is a pick per item; each item's look stays one material per kind-and-colour (shared, not one per
   item).
3. **Drag-chain types** in `core/flex_chain.py`'s link maker: **open** (two side links + crossbars every link or every
   second link), **closed** (side links + lids top and bottom – a closed tube), **half-open** (lid on the outside of the
   bend only), **steel** (steel side plates, round crossbar tubes, steel look). Each a low-poly link as today; the
   cables inside show through open / half-open (a fill of drawn cables when the chain has none: optional, say in the
   report if left out). Chain colour: black / grey / orange for plastic, steel for steel.
4. **UI** (4 Motion > Hoses and drag chains, 4 Motion > Cables and paths, 0240's Draw pickers too): on the item, **Kind**
   (drop-down), **Colour** (swatches of that kind), **Size** (drop-down, "Custom" last). A kind / size pick sets Ø, bend
   radius, chain width / height / pitch / bend radius at once; changing a number by hand sets Size to Custom. The hover
   picker's default size is the nearest standard size to the fitting's bore / the CAD part's Ø. Tooltips; the panel
   rules of CLAUDE.md section 6.
5. **Old projects** open unchanged: every existing item reads as its present look with Size = Custom (a test with a
   project of 0.2.175 or older). Model update, save / reopen, undo, Build, queue render, web export (the looks bake),
   scripts off, Client view (shows, never edits).
6. Tour: stops in **0240's set `flex_drawn`** only (one hose of each kind side by side, a chain of each type, the cable
   kinds) with number checks (Ø of each size within 0.1 mm, links one pitch apart, 0 clashes); `changed=` + record.
   Guide sections with a picture of the kinds, function-list entries (`since=`), PC-check line ("each hose / cable kind
   and chain type builds and renders; size picks set the numbers"), `THIRD-PARTY-NOTICES.md` only if anything from
   outside is used.

## Done when

- [ ] Every kind, colour and size of the owner's picks can be chosen on drawn and CAD-read items; Custom works
- [ ] Standard sizes match their named standard (source named in the code; the report lists them)
- [ ] The four chain types build, roll with the axis and give 0 clashes on the test chain model
- [ ] Renders (small, test models only) of every kind look right in Cycles; EEVEE where a GL context exists
- [ ] Old projects unchanged; model update, undo, save, Build, queue, web export, scripts off checked
- [ ] Tests for `core/flex_kinds.py` and the link shapes; real-app test of the drop-downs; guide, function list,
      PC-check line, tour stops; precheck green
- [ ] Report filled in, merged, released

## Not in this task

Three-end hoses, bundles, hoses pushing on parts; cable fills of drag chains beyond an optional simple one; the
offshore cable's sizes changing the private demo kit (the kit keeps its own); makers' catalogues; the `hoses`, `chains`,
`cables` tour sets (0233).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
