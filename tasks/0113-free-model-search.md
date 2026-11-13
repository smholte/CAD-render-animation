# 0113 – Study: free, detailed models for the site – a vessel, machines with moving parts, a truck

**Who:** worker (research) → owner picks · **Status:** open – can start · **Branch:** none (study; no code)
**Started by:** lead chat, 13 Nov 2026 (owner's request 13 Nov, 20:00)
**Model:** **Opus · effort Medium** · **Place:** a **new chat in the claude.ai project "STEP rendering App"** – not
Claude Code on the web: the licence of every model must be read on its own page, and web sessions cannot open most
pages (0083, 0104).
**Result:** project doc `claude/site-model-candidates.md` + a page (artifact) with the table for the owner to pick
from. The lead copies the owner's picks into TASKS.md.

## Goal

A list the owner can choose from: **free, detailed 3D models** to show on the landing page (gallery pictures, clips,
and maybe the "Turn it yourself" picker of 0111). Categories:

1. **Vessels** – offshore construction / cable-lay / supply vessel, tug, workboat, crane vessel, barge. Moving parts
   **not** needed.
2. **Machines with moving parts** – e.g. excavator, mobile / crawler / offshore crane, wheel loader, tractor with an
   implement, forklift, drilling rig, wind turbine (rotor, nacelle yaw), winch or A-frame, robot arm, conveyor.
3. **Trucks** – heavy truck, tipper (tipping bed), crane truck, trailer.

## Rules for a model to be on the list

- **Licence must allow** renders **and** a 3D web model of it on a public company website (Fresing): CC0, public
  domain, CC BY, CC BY-SA, CERN-OHL (P/W/S), MIT, Apache, GPL. **Excluded:** non-commercial (NC), no-derivatives (ND
  – a converted web model is a derivative), "editorial only", GrabCAD (its terms), supplier/catalogue sites whose terms
  forbid republishing (TraceParts, 3D ContentCentral, …) unless their terms say otherwise, and any model whose licence
  cannot be confirmed on its page. Write the exact credit line the licence asks for.
- **Format:** the app imports **STEP only**. List first: STEP, or CAD sources a session can convert to STEP (FreeCAD
  `.FCStd` incl. Assembly4 – `tools/fcstd_to_step.py`, `tools/a4_to_step.py` exist; Onshape/Fusion exports only if the
  licence covers the export). Mesh-only models (OBJ/FBX/glTF/STL/Blend) go in a **separate part of the list** marked
  "needs mesh import (not in the app yet)" – useful only if the owner wants that feature.
- **Detailed:** real proportions, separate bodies for the moving parts (one body per part), enough detail to look
  real in a close render; note part count and file size.
- Nothing of the owner's employer or its clients; no models from the owner's work.

## Where to look (at least)

GitHub / GitLab (open hardware), Printables, Thingiverse (licence per item), Wikimedia Commons, NASA 3D Resources,
Smithsonian 3D (CC0), Sketchfab (filter on CC licences; downloadable), Poly Haven, BlendSwap, Open Source Ecology,
FreeCAD library / forum, Onshape public documents (check what their terms let a non-Onshape site do), university or
research projects (e.g. open ship hull models, open wind turbines such as IEA reference turbines, if CAD exists).

## The list (per category, 3–6 candidates, best first)

| Column | What |
| --- | --- |
| Name, maker, link | the model's own page |
| Licence | as stated on the page (checked date), credit line |
| Format → work | STEP / FreeCAD → convert / mesh → needs mesh import |
| Parts, size | part count, MB |
| Moving parts | which ones are separate bodies (boom, stick, bucket, slewing, tipping bed, rotor…) |
| Looks | 1–5 by the pictures, one line why |
| Effort to use | low / medium / high, and what (colours, joints, cleaning) |
| Risks | licence doubts, scale, missing parts |

End with: your **top pick per category** and one line why, and anything the owner must decide (e.g. "mesh
import is needed for the best vessel"). Be honest when a category has nothing usable in STEP.

## Not in this task

Downloading models into the repository, building projects or rendering (a later task, after the owner picks).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Result** (link to the doc and page):

**Open points:**
