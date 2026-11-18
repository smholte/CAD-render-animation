# 0219 – Web 3D page: measurement labels never overlap; measure to an edge

**Who:** worker · **Status:** waiting – after 0218 (same lane, same file `fr_tools.js`) · **Branch:**
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

- [ ] No two labels overlap in the owner's case and in tests with close points and several measurements
- [ ] Edge picks: straight and round edges hover and measure; tests in node for the edge maths and in pytest for the
      exported edge data (a block with a chamfer and a filleted hole, made by a test-model maker)
- [ ] File size before / after on the made demo's page and the test crane's page in the report
- [ ] Guide and README.txt; function entry `changed=`, tour stop / PC-check line as the precheck asks
- [ ] Report filled in

## Not in this task

Slice (0218); a page that opens on its own by a link, other file types, STEP in the browser (ToolBox plan, later).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
