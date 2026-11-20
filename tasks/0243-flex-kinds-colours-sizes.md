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

**Chat / date:** Claude Code on the web, 20 Nov 2026 (branch `claude/funny-clarke-fxi82c`; release 0.2.182)

**What changed:**
- New `core/flex_kinds.py`: 12 kinds (hose 4, cable 4, chain 4) with colours (library material + colour text) and
  size lists; `nearest_size`, `nearest_radius` (a drawn chain: never bigger than half its brackets' gap),
  `group_name` (one material group per kind and colour), `pattern_look`. New `blender/kinds.py`: the picks (kind ->
  colour kept if the new kind has it, else its first; nearest size; look; numbers written at once, worked out once),
  the shared look through manual material groups (as the cable looks do; back where it was with "NONE"), Custom when a
  number is typed. `props.py` (additive): `hose_kind`, `chain_kind`, `cable_kind` (fixed enum numbers, "NONE" = 0 =
  every older project), `kind_colour`/`colour`, `size_id`/`size` (dynamic drop-downs by get/set).
- Looks: `materials_lib` entries 57–61 (`hose_hydraulic`, `hose_braided`, `hose_sleeve`, `pu_tube_clear`,
  `wire_rope_galv`); `cable_looks.py` kinds HOSE (printed line), BRAID (over-one-under-one weave, bump), SLEEVE (spiral
  wrap, recessed black gap) + `hose_pattern` in plain Python; the hose tube gets `fr_cable` (flex tree VERSION 3, same
  shape). Plain colours use `plastic_matte` / `cable_black` / `galvanized`; the offshore cable keeps "Power cables" /
  "Served cables", the bright rope "Wire ropes" (old groups reused).
- `core/flex_chain.link_mesh`: OPEN (= the 0.2.180 link), CLOSED, HALF (lid on the outside of the bend), STEEL (plates
  + round tubes); `flex._made_link` remakes the link when the type changes. CAD-link chains: no type or size (a hint).
- UI: Kind/Type · Colour · Size + a line of what the size gives, in both panels; the pickers start drawn items as
  hydraulic hose / machine cable / open chain / wire rope of the nearest size; a drawn hose at its "as drawn" length
  gets the length for the new bend. **How it works** of Hoses and drag chains: step 4 now says Draw drag chain (by the
  brackets) or Add drag chain (CAD links); new step 5 for Kind · Colour · Size.
- Model update: `flex.after_model_update` puts the kinds' looks and pattern numbers on the new revision's part (found
  by the new test – it was lost before the fix).
- Tour set `flex_drawn` (changed 0.2.182): six drawn arches, one per hose-item kind, on the hoses model; the drawn
  chain closed; the drawn rope galvanised 16 mm. Stops `flex_kinds`, `chain_types`. PC-check line `motion.flex_kinds`
  (+ processor render). Functions `flex.kinds`, `flex.chain_types`, `paths.cable_kinds`. Guide: "Kind, colour and
  size", "Drag chain types", "Cable kinds"; pictures `view_flex_kinds.jpg`, `view_chain_types.jpg`, the panels
  `panel_4_flex*.png`, `panel_cables.png` again.

**Sizes and their sources** (checked 20 Nov through search results of the pages; the standards themselves are
paywalled and were not read; the web pages could not be opened from the session – only search snippets):
- Hydraulic + steel-braided: EN 853 2SN = SAE 100R2AT, DN 6/8/10/12/16/19/25/31/38/51, outer Ø 15.4 … 68.2 mm (middle
  of the data sheets' ranges), smallest bend 100/115/130/180/200/240/300/420/500/630 mm – makers' data sheets quoting
  the standard (hoseworld 144.pdf, hiparts "2 SN.pdf", tubes-international) and EN 853:2015's preview. Sources differ
  by ~1 mm on the outer Ø and on one bend (125 vs 130 mm at DN 10).
- Pneumatic PU: Ø 4/6/8/10/12/16, inner 2.5/4/5/6.5/8/11, bend 10/15/20/27/35 mm from SMC series TU (one maker's
  typical values, no standard found); 16 mm: inner and bend (56 mm) **invented**.
- Wire rope: 6 … 64 mm, the series makers list under EN 12385-4 (**the standard's table not seen**); smallest bend 10 d
  from sheave D ≥ 20 d (ISO 4308-1 / FEM 1.001 class M5, values via a crane maker's calculator).
- Invented: machine cable 6 … 28 mm (bend 7.5 d), power cable 10 … 60 (10 d), offshore 100 … 300 (20 d), sleeve
  16 … 63 (4 d), chains "Chain 10 x 15" … "Chain 60 x 150" (plastic) and 50 x 100 … 100 x 200 (steel).

**Tested and measured** (4-core web machine, test models only):
- `tests/test_flex_kinds.py` 18 tests: tables, sizes, nearest size, link types closed and where their lids are,
  patterns in Python; in Blender: hose kinds (Ø drawn to 0.1 mm, shared / separate materials, Custom, back to NONE),
  the 4 chain types on a drawn chain at 3 X positions (links one pitch apart to 1e-6 m, end on bracket, status OK),
  cable kinds (look, group, galvanised material, Custom), save + reopen, Build (no Python drivers), model update A -> B.
- `tests/test_cable_looks.py` 27 passed: the new kinds' render compared with the formula (print to 0.01; braid and
  wrap to 0.06 mean with correlation > 0.8 – the render's pixel filter at their many edges).
- **Old projects:** three projects saved by **0.2.175** (hoses, chains, cable) opened with 0.2.175 and with this code:
  60 shapes, materials and groups compared, **0 differences**; every item "As in the CAD file" / Custom.
- Tour set `flex_drawn` locally: builds in 4.4 s, all 6 stops' checks pass (kinds Ø to 0.000 mm; 4 chain types links
  to 0.0000 mm), clash check **0 rows**. PC check `motion.flex_kinds` OK in 4.3 s.
- Real app `ui_test_drawn.py` 25/25 (8 new: the picker's kind and size, Size / Kind / Colour as the drop-downs set
  them, a typed diameter -> Custom, undo x3).
- Renders (Cycles, processor, small): looked at the six kinds and the closed chain. EEVEE: no GL context here; the
  materials use only nodes both engines know (`test_cable_looks`).
- Flex tests 79 passed (`test_flex`, `test_flex_drawn`, `test_flex_drawn_independent`), panels, functions, places,
  guide, materials looks. Tooltip check: 884 ok, 0 missing.
- GitHub: see below.

**Open points / follow-up tasks:**
- Not tested separately: queue render and web export of the new looks (they go the same path as the cable looks);
  Client view: the Hoses and Cables panels are not in its workspace, so nothing there can be edited.
- No cable fill inside open / half-open chains (optional; left out).
- No ID band at a hydraulic hose's ends (optional; left out). The sleeve is drawn as a pattern on one tube (wrap + a
  recessed black gap), not a second tube.
- A CAD rope given the Wire rope kind takes the nearest standard Ø and may then warn "bends tighter than its MBR" on
  small sheaves (the test model's Ø360 sheaves allow up to 18 mm): true by the D/d rule, but new to such projects.
- A chain of real CAD links has no type or size (its links keep their shape).
- Subagents: one research agent looked up the standards (could not open pages, only search snippets – values above).
  No independent tester (Medium task, no Windows code).
