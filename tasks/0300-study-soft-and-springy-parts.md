# 0300 – Study + prototype (findings only): soft and springy parts – rubber that squeezes, springs that compress – set up in a few clicks

**Who:** worker · **Status:** done 23 Nov (findings on the branch, not merged) · **Branch:** `task/0300-study-soft-parts` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Simulated materials like rubber getting squished, spring
and such. And again, a way to add it with a few clicks or possibly a popup window with a few steps.") · **Model:** Opus ·
effort High
**Area:** findings only; prototype code in new files on the branch (e.g. `tools/soft_proto/`); reads `cylinders.py`,
`joints.py`, `flex.py`, `core/part_types_data.py` ("Springs", "Gas springs & shock absorbers"), 0282's `form_window.py`.
Clips and the page in `tasks/0300_page/`. Not a code slot.

## What to find out

A. **Kinds and how each moves:** coil springs (compression, extension, torsion – pitch changes, wire Ø and coil count
   kept; ground or closed ends), read from the CAD spring (outer Ø, wire Ø, turns, free length from its mesh) or typed;
   gas springs / dampers (two rigid parts like a cylinder?); rubber – bushings, buffers / bump stops, seals, mounts,
   bellows / gaiters (folding), tyres on the ground – squeezed with the volume kept (bulging) when two parts come closer.
B. **How in Blender** and the cost per frame on the 4-core machine, scripts off (CLAUDE.md 8: simple-expression
   drivers): a Geometry Nodes helix driven by the distance between the two seats, shape keys made at set-up, a GN
   squash with bulge, lattice / Simple Deform; what the clash check, the web 3D export, a model update and the render
   queue do with each.
C. **Set-up in a few clicks:** a function window with steps (0282) – pick the spring / rubber part → the two parts it
   sits between → Check → Done; found by itself from the part kind or name where possible.
D. **Prototype** on a small invented test model: a spring between two plates moved by a slide joint, a rubber buffer
   hit by a stop, a bellows on a cylinder rod – clips.
E. **Page:** a clip per kind, the cost, the set-up flow as a mock-up, ranked build tasks; pick ticks + Copy line.

## Done when

- [x] Report + page on the branch; the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus · High), 23 Nov 2026.

**What changed:** nothing in the app. On the branch only:
- `tools/soft_proto/` – the prototype: `shapes.py` (invented CAD-like meshes: a compression spring with closed end turns, a
  rubber buffer, a bellows, a tyre – round sides one strip high, as an import gives them), `read.py` (a spring read from its
  mesh alone), `nodes.py` (three Geometry Nodes deformers: **FR soft axial** – springs with the wire kept round, bellows with
  folds that close; **FR soft squeeze** – rubber with the volume kept by a bulge; **FR soft ground** – a tyre's flat and
  bulging walls), `scene.py` (the four-station test scene), `measure.py` (→ `tasks/0300_page/numbers.json`), `render.py`
  (the clips).
- `tasks/0300_page/` – the page for the owner's picks: four clips today | soft, the wire picture, the tables, the Set-up
  window mock-up, 8 build tasks with ticks + Copy line (`0300 pick: …`).

**Findings** (details and numbers on the page):
1. **How:** a Geometry Nodes modifier on the part's own object, reading the two parts it sits between with Object Info – no
   driver and no Python at play or render time. Real Blender 5.2.3 with `--disable-autoexec`, frame 40: spring 50.0 mm,
   buffer 16.5 mm, bellows 80.0 mm (as in the module) – works with scripts off and in the render queue.
2. **Springs:** "following the wire" (each point moves with the wire's centre line; the closed end turns stay) keeps the wire
   round – 0.044 mm max off a 2 mm radius at 80 → 50 mm; a plain stretch along the axis is 0.92 mm off (a flat ribbon). One
   guess of the turn a point is on put the top of the last closed turn on the first free turn (1.9 mm off): the nodes now
   take the nearest of three turns.
3. **Spring reader** (mesh only, 4 invented springs turned 40° and moved): outer Ø, wire Ø, free length exact; turns
   10.00 / 6.99 / 6.50 / 12.25 (made 10 / 7 / 6.5 / 12.25); end turns within 0.1; 0.7–1.1 s each (NumPy, one core).
   Not tried: ground ends, conical springs, rectangular wire, a spring drawn squeezed in the CAD, the owner's own models.
4. **Cost** (4-core web machine, 100 copies sharing one mesh, 48 frames; range of two runs): spring 0.22–0.26 ms per part
   per frame (15,392 triangles), bellows 0.13–0.17, tyre 0.15–0.20; rubber refined in the nodes 0.49–0.53 (level 2) /
   1.28–1.38 (level 3), rubber meshed finer at import 0.05–0.08. 200 soft parts of all kinds: 90–102 ms a frame (0.2–0.3
   without). Shape key + driver: 0.02–0.03 ms but a shape key
   is on the shared mesh (all copies would squeeze together) – not chosen.
5. **Rubber:** volume kept 100.0–100.4 % up to 50 % squeeze (Ø30 → Ø48 at 50 %); the import's mesh has no points half-way up
   a round side, so the importer should mesh rubber / bellows kinds finer (the bulge otherwise becomes a cone).
6. **Linear:** springs and bellows move every point linearly with the seats → one glTF morph target is exact (7e-6 mm);
   rubber needs 2–3 (one: 2.2 mm off, two: 0.6 mm). Today `web3d.py` exports part places only.
7. **Clash check** reads the CAD mesh and rigid places (`clash.objects`, `ob.data`): a soft part must be left out
   (`clash.HOOKS`, as hoses) and get its own "squeezed solid" row. **Model update** keeps the modifier; the numbers read must
   be read again (as `flex.after_model_update`).
8. **Gas springs / dampers** need no deformer: the app's cylinder in Follow mode (`cylinders.py`) is exactly two rigid
   parts between two eyes – the build task only has to find and set it up.
9. **Set-up:** a new kind in the Set-up window (`ui_setup.SETUPS`, task 0062): part (found by kind: Springs, Rubber parts,
   Gas springs & shock absorbers) → the two parts (found by touching) → Check (the numbers read, the length range in the
   animation, a squeeze test) → Done (other copies too). Plus "Find springs and rubber" for a whole machine.

**Ranked build tasks** (page section 6): **A ★** springs and bellows (Opus · High, M–L) → **B ★** rubber that squeezes
(Opus · Medium) · **C ★** gas springs / dampers as cylinders (Sonnet · Medium, S) · **F ★** soft parts in the web 3D model
(Opus · Medium) · D right-click "Make it springy…" · E tyres on the ground (Vehicles lane, with 0306) · G torsion springs,
bending gaiters, twisting bushes (a blend deformer, not prototyped) · H springs that push back (a spring rate + solver).

**Tested and measured:** all on the web machine (4 cores, no graphics card), Blender 5.2.3 as a Python module, the invented
test model of `tools/soft_proto/`; the scripts-off check in the real Blender 5.2.3 (background). Clips: Cycles on the
processor. No GitHub run (branch only, `[skip ci]`). Subagents: none (one prototype, one owner of every file).

**Open points / follow-up tasks:**
- Before A: try the reader on 2–3 of the owner's own springs (ground ends, catalogue springs from Misumi / Lee Spring, a
  spring drawn squeezed in the CAD) – attached in a chat, never committed.
- Cost on the owner's 24-core PC is an expectation (parts are worked out side by side), not measured.
- Soft body / cloth not tried (they need a bake after every change; a machine's spring needs its two ends, not physics).
- The lead publishes `tasks/0300_page/` for the owner's picks.
