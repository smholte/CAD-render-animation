# 0219 – Web 3D page: measurement labels never overlap; measure to an edge

**Who:** worker · **Status:** running · **Branch:**
`task/0219-web3d-measure-edges`
**Started by:** lead, 18 Nov 2026 (owner's list of 18 Nov 22:21, through the ToolBox lead's lead-post message
`1118-toolbox-to-fresing-render-viewer-and-slice.md`) · **Model:** Opus · effort Medium
**Area:** Web 3D lane – `fresing_render/web/fr_tools.js`, `fr_measure.js`, `core/web3d_faces.py` (+ where the export
writes `extras.fr_faces` in `blender/web3d.py`, additively), `tests/test_web_tools.py`, `tests/test_web3d*.py` of the
face data, the guide's web-page chapter.

## Goal

Measuring on the web 3D page – which the owner finds good, "better than I remembered" – gets its two missing pieces:
every label can be read, and he can measure to an **edge**.

## What to do

1. **Labels apart.** Owner's screenshot (18 Nov): a measurement with its X / Y / Z parts – "X −27.8 mm" lay over "Y
   4.07 mm", and the distance "160.0 mm" half under "Z −157.5 mm". Labels must move apart or stack (in screen space,
   every frame the view moves) so each one can be read, also when the points lie close together on the screen and
   with several measurements on the page. A short leader line from a moved label to its line. Test the placement in
   node (`fr_measure.js` or a small new pure function) with labels that start on top of each other.
2. **Measure to an edge.** Today a pick is a point, a flat face, a round face or an axis (`fr_measure.js` header). Add
   **edge** picks: a straight edge (a corner of two faces: a line) and a round edge (where a rounding meets a flat face
   or a hole's rim: a circle with centre, axis, radius). The hover shows the edge before the click. Distances: point /
   face / axis / edge to edge as the existing modes do (edge to parallel edge, edge to plane, circle centre to axis …);
   say in the report which pairs give what.
3. **Where the edges come from:** the CAD face of every triangle is known at export (`fr_face_starts`, `fr_faces`).
   Work out the edges where two CAD faces meet (a line or a circle fitted to the shared mesh edges, with a tolerance
   from the facet size), store them compactly in the file's face data, and keep files small (say the size change on
   the made demo's page and the test crane's). No change to the STEP importer or its cache unless that proves
   necessary – then bump `CACHE_VERSION` and say why.

## Done when

- [x] No two labels overlap in the owner's case and in tests with close points and several measurements
- [x] Edge picks: straight and round edges hover and measure; tests in node for the edge maths and in pytest for the
      exported edge data (a block with a chamfer and a filleted hole, made by a test-model maker)
- [x] File size before / after on the made demo's page and the test crane's page in the report
- [x] Guide and README.txt; function entry `changed=`, tour stop / PC-check line as the precheck asks
- [x] Report filled in

## Not in this task

Slice (0218); a page that opens on its own by a link, other file types, STEP in the browser (ToolBox plan, later).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 20 Nov 2026 · version 0.2.174

**What changed:**
- **Edges in the file** (`core/web3d_faces.py` `edges`, `fit_edge`, `pack_edges`, `unpack_edges`, `read_edges`): mesh
  edges on the border of two CAD faces (points welded; the importer meshes each face with its own points) are chained
  per pair of faces and fitted with a line or a circle (tolerance 0.005 mm + 1/500 of the mean segment + 32-bit
  rounding: the mesh's nodes lie ON the CAD edge). Splines / ellipses are left out. Stored as a third accessor per mesh
  in `extras.fr_faces.meshes` (records: kind, face row a, row b + 6 numbers for a line / 9 for an arc: centre, start,
  axis × angle), only where one side has a face row. Old pages and readers ignore it. No importer / cache change.
- **Page** (`fr_measure.js`, `fr_tools.js`): picks `line` and `circle`; hover snaps to the hovered face's edge within
  9 px (18 px on touch) and draws it as a 3.5 px SVG line (orange hover, blue picked). Pairs: line–line parallel =
  "Edge to edge", skew = shortest + angle; line–flat = "Face to edge" (along) or meeting angle; line–round/axis =
  "Edge to centre"; point–line; circle = from its centre: to a circle (+ "Across the axes … · along …" when parallel),
  to an axis / edge (square), to a flat face (square), to a point. One line = its length, one circle = Ø + arc angle.
- **Labels apart** (`FRMeasure.layout`, `leader`): every frame the labels are measured and placed in priority order
  (the distance first, then X / Y / Z), each moved up/down/aside in small steps until it covers no label and no
  clicked dot; a moved label gets a short leader line.
- Guide (Web 3D chapter), `web/README.txt`, tooltip of "Faces for measuring", function `web.tools` changed=0.2.174,
  tour stop `web3d` (text + check reads the edges; set crane changed=0.2.174), PC-check line `web3d.export` (the
  page's self-test counts edges and checks the layout).

**Tested and measured** (4-core web machine):
- `tests/test_web3d_edges.py` (5, new): the block of `tools/make_test_edges.py` (chamfer 5 × 5, hole Ø20 with an R3
  rounding) meshed by the importer's mesher at fine and coarse facets – all 15 straight edges and the 3 circles
  (Ø20 at z 0, Ø20 at z 27, Ø26 at z 30) exact; pack → glb → read back; the fit on its own (quarter arc's angle and
  direction, ellipse and zig-zag left out).
- `tests/test_web_tools.py` (+3): edge maths in node (moved / scaled / mirrored part, every pair), the layout (the
  owner's case, six labels on one spot, 40 random clusters of 2–8 labels with dots: no overlap), and in Chromium:
  hover lights the edge, edge length, edge to edge 200 mm, the shaft's rim Ø40, rim to rim, labels with X / Y / Z
  apart. Self-test counts 16 edges. `tests/test_web3d_faces_blender.py`: the crane's file has > 200 lines, > 30
  circles, rims Ø13 and Ø40.
- **File sizes** (draft import, texture 256): test crane `.glb` 160,088 → 190,272 bytes (+19 %, 766 edges), its
  page 1,482,519 → 1,492,835 (+0.7 %); demo vessel (`demo_cable_lay.step`) `.glb` 4,419,996 → 5,083,924 (+15 %,
  16,784 edges), its page 4,073,911 → 4,558,271 (+11.9 %). Export time unchanged (7.3 s vs 7.2 s). Variable-length
  records saved ~20 % against fixed 12-number rows. The Blender test's limit for faces+edges went from 20 % to 40 %
  of the small-picture draft `.glb`.
- No independent reviewer/tester subagent (no Windows code; usage rule).

**Open points / follow-up tasks:**
- Edges between two faces without a face row (both free-form) are left out: the page finds edges from the hovered
  face's row.
- Snap only in Faces mode; Points mode measures plain points.
- Only one measurement at a time on the page; the layout is written for any number of labels (tested with 8).
