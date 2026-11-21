# Third-party notices

Fresing Render itself is free software under **GPL-3.0-or-later** (`LICENSE`), © 2026 Fresing. It uses and ships parts
that others made, under their own licences. This file lists them: what, which version, where it is, which licence,
where it comes from, and the credit line it asks for. Written 18 Nov 2026 (task 0205) for version 0.2.158; every
licence was looked at at its source (the project's own licence file or the package's own metadata) unless a line says
"not checked".

Short: **the app's own code is GPL-3.0-or-later; every library below is under a licence that allows this use.** The
licence texts – Fresing Render's own and those of the libraries inside the OpenCascade package – ship with every install
since 0.2.162 (task 0206): `licenses\` in the install folder and inside the extension.

## The Fresing name and logo (owner to check – a lawyer may word it)

The GPL covers the **software**. The **Fresing name, the Fresing and Fresing Render logos and icons**
(`fresing_render/brand/`, `site/brand/`, `app_template/fresing_render/splash.png`) are Fresing's brand, **not** licensed
for other products. A fork or a changed copy that you give to others must use its own name and its own logo.
Fresing's own pictures, videos and 3D pages on the landing page (`site/media/`, other than the credited third-party
models below) are Fresing's too: all rights reserved unless the owner says otherwise.

## 1. Downloaded by the installer (not in our zip)

| What | Version | Where | Licence | Source | Credit |
| --- | --- | --- | --- | --- | --- |
| **Blender** (the program the app runs in; Cycles, Python, its own libraries) | 5.2.3 LTS, Windows x64 portable | `%LOCALAPPDATA%\FresingRender\blender-5.2.3-windows-x64\` – downloaded by `Install.bat` from `download.blender.org`, SHA-256 checked | **GPL-3.0-or-later** (© Blender Foundation); its own third-party list: `license\license.md` and `copyright.txt` in its folder | https://www.blender.org – https://download.blender.org/release/Blender5.2/ | "Blender" is a trademark of the Blender Foundation; Fresing Render is not made or endorsed by it |

Blender's `license\` folder (the GPL text, `license.md`, `licenses.json`, the licence texts of its libraries) and
`copyright.txt` come with the Blender zip that the installer unpacks as it is (checked on the Linux build of the same
version; the Windows zip has the same layout – checked on Windows by the Windows install test since task 0206, and
linked from the app: Fresing > About Fresing Render).

## 2. Inside the extension zip (`fresing_render-<version>.zip`, and so inside the installer zip)

### 2.1 Python packages (wheels, `tools/build_release.py`)

| What | Version | Licence | Source | Where on the PC |
| --- | --- | --- | --- | --- |
| **cadquery-ocp-novtk** ("OCP": Python bindings of OpenCascade, with OpenCascade's own libraries `TK*.dll` inside) | 8.0.1.1.0 (OCCT 8.0.1, no VTK) | bindings: **Apache-2.0** (package metadata; CadQuery/OCP `LICENSE`); the OpenCascade libraries: **LGPL-2.1 with the "Open CASCADE exception 1.0"** (OCCT's `LICENSE_LGPL_21.txt`, `OCCT_LGPL_EXCEPTION.txt`) | https://pypi.org/project/cadquery-ocp-novtk/ – https://github.com/CadQuery/OCP – https://github.com/Open-Cascade-SAS/OCCT | the extension's `wheels/` folder in the zip; unpacked into Blender's extension site-packages (`cadquery_ocp_novtk.libs\` next to `OCP\`) |
| **cadquery-ocp-proxy** | 8.0.1.1.0 | Apache-2.0 (package metadata) | https://pypi.org/project/cadquery-ocp-proxy/ | as above |
| **manifold3d** (mesh booleans for milling) | 3.5.4 | **Apache-2.0** (`LICENSE` and `AUTHORS` inside the wheel's `dist-info`); © 2022–2026 the Manifold authors, Google LLC | https://github.com/elalish/manifold | as above; its `LICENSE` stays inside the installed package |
| the Microsoft Visual C++ runtime libraries (`msvcp140*.dll`, `vcomp140*.dll`) inside the two wheels above | – | Microsoft's redistribution terms for the Visual C++ runtime | https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files | inside the wheels (put there by their makers) |

LGPL notes for OpenCascade: the libraries are separate `.dll` files next to the bindings, not linked into a program of
ours, so a user can replace them; the source is at the OCCT address above, version tag matching 8.0.1.

**Libraries that the OpenCascade wheel brings along** (the wheel's maker bundles them; the wheel itself carries **no
licence texts** for them – listed from its file names; their licences are those of their own projects and are not
checked file by file here): Imath and OpenEXR / OpenEXRCore (BSD-3-Clause), FreeType (FreeType Licence or GPL-2.0),
libpng (libpng-2.0), libjpeg (IJG / BSD-style), libtiff (libtiff), libwebp / libsharpyuv (BSD-3-Clause), Lerc
(Apache-2.0), OpenJPEG `openjp2` (BSD-2-Clause), OpenJPH (BSD-2-Clause), Little CMS `lcms2` (MIT), xz `liblzma`
(0BSD / public domain), libdeflate (MIT), zlib (Zlib), zstd (BSD-3-Clause or GPL-2.0, our choice: BSD), **FreeImage**
(FreeImage Public License or GPL-2.0 / GPL-3.0 – used under the GPL-3.0 option, compatible with this app), **LibRaw**
(LGPL-2.1 or CDDL-1.0). The Linux build of the same wheel (used only in the tests) lists the same family
(`auditwheel` SBOM inside it). Their licence texts ship since 0.2.162 (task 0206): `licenses/third-party/` inside the
extension and the install folder (`SOURCES.txt` there says where each came from).

### 2.2 The web viewer (`fresing_render/web/`, written into every Web 3D page the app makes)

| What | Version | Licence | Source | Where |
| --- | --- | --- | --- | --- |
| **three.js** with OrbitControls, GLTFLoader, Sky, HDRLoader (bundled as `three-viewer.min.js`) | r180 (npm three 0.180.0) | MIT, © 2010-2025 three.js authors | https://threejs.org – https://github.com/mrdoob/three.js | `fresing_render/web/three-viewer.min.js`; licence text `web/LICENSE-three.txt` |
| **meshoptimizer** decoder (inside `three-viewer.min.js`) | as in three.js r180 | MIT, © 2016-2026 Arseny Kapoulkine | https://github.com/zeux/meshoptimizer | inside the bundle; its licence text ships as `licenses/third-party/meshoptimizer-MIT.txt` (since 0.2.162, task 0206) |
| **model-viewer** (`model-viewer-umd.min.js`, used by the landing page's bare `.glb` view; not by the app's exports since task 0134) | 4.4.0 | Apache-2.0, © Google LLC; inside it **three.js** (MIT, © 2010-2026 three.js authors) and **lit** (BSD-3-Clause, © Google LLC), with their `@license` notes kept in the file | https://modelviewer.dev – https://github.com/google/model-viewer | `fresing_render/web/model-viewer-umd.min.js`; licence text `web/LICENSE-model-viewer.txt` |

`fresing_render/web/fr_*.js` are Fresing's own. Nothing is loaded from the internet by these pages.

### 2.3 Fresing's own, inside the zip

All other code, the test models in `fresing_render/data/` (made by the makers in `tools/`: invented machines, written by
Fresing Render's own test-model makers; the glTF and OBJ test files say "Fresing test models (invented), CC BY 4.0"),
the built-in crane classes (`data/lifting/`, invented classes), `data/sample-house.hpscene` (a made-up house from
`smholte/house-scene-format`), the user guide (built from `docs/USER-GUIDE.md` with the Python package `markdown`,
BSD-3-Clause – only its output is shipped) and the brand files (see the brand note above).

**The Toolbox format's reference code** (task 0217, tag `v0.1.1` since task 0245): `fresing_render/core/tbf/` holds `names.py`, `detect.py` and
`types.json` of https://github.com/smholte/toolbox-format, tag `v0.1.1` (MIT, © 2026 Fresing – checked in that
repository's `LICENSE` at the tag), byte for byte but one marked line; the MIT notice is in `core/tbf/__init__.py`.
A copy of the whole tag (text, schemas, checker, made-up samples) is in `tests/data/toolbox/tbf-v0.1.1/` (repository only).

No pictures, HDRIs, sounds or music of others ship with the app. (360° photos and music are the user's own, chosen in
the app; `docs/SURROUNDINGS.md` only links to where free ones can be found.)

## 3. In the repository only (not in a release zip)

| What | Licence | Source | Notes |
| --- | --- | --- | --- |
| **IBM Plex Sans**, **IBM Plex Mono** (`site/fonts/`; Mono: Medium, Latin-1 subset from `@ibm/plex-mono` 2.5.0) | SIL Open Font License 1.1 (`site/fonts/OFL-IBM-Plex.txt`), © 2017 IBM Corp. | https://github.com/IBM/plex | landing page |
| Pictures, videos and 3D pages of **third-party models** on the landing page (`site/media/`): Thor robot arm (Ángel L. M.), CEB press (Open Source Ecology), IEA 15 MW reference turbine (IEA Wind TCP Task 37) | **CC BY-SA 4.0** (Thor, CEB press – these pictures and 3D pages stay CC BY-SA 4.0, not GPL); **Apache-2.0** (IEA 15 MW; modified, changes listed in `site/CREDITS.md`) | https://github.com/AngelLM/Thor – https://github.com/goscommons/CEB-Press – https://github.com/IEAWindSystems/IEA-15-240-RWT | credit lines, licences and changes: `site/CREDITS.md` and `site/media/media.json`; licences checked at their repositories on 18 Nov 2026 |
| Models that the landing page's render kit can use (`site/render_kit/models.ini`): Mekanika EVO, OpenArm, FarmBot Genesis | CERN-OHL-S-2.0 (EVO's `cad/*.step`, OpenArm); CC0 1.0 claimed (FarmBot) | https://github.com/mekanika-dev/evo – https://github.com/enactic/openarm_hardware – https://genesis.farm.bot/ | **the models themselves are not in the repository**; EVO and OpenArm re-checked 18 Nov 2026; FarmBot **not** confirmed (see "Needs the owner") |
| Sheets that describe how those models move (`site/render_kit/projects/*.json`, from `tools/site_projects/`) | follow the model they describe | as above | made by Fresing from the models' own files, cloned at pinned commits when the kit is built |
| `tests/data/house/hsf-v1.0.1/` – a pinned copy of the house scene format's checker, schemas and made-up samples | the owner's own repository `smholte/house-scene-format` (**has no licence file yet** – see below) | https://github.com/smholte/house-scene-format | invented samples only |
| Development and test tools, **not shipped and not copied**: `bpy` 5.2.3 (GPL-3.0), `numpy` 2.5.4 (BSD-3-Clause and others), `pillow` 13.0.0 (MIT-CMU), `pytest` 9.2.0 (MIT), `markdown` 3.11.2 (BSD-3-Clause), `jsonschema` 4.26.0 (MIT); `esbuild` and `three` through npm, only to rebuild `three-viewer.min.js` (`tools/build_web_viewer.py`) | as stated (metadata of the installed packages) | PyPI / npm | `tools/requirements-dev.txt` |
| The documentation pictures (`docs/img/`, `tasks/*/img/`) show Blender's own interface and Fresing's invented test models | Fresing's own; the Blender interface in them is the program's | – | – |

## 4. Needs the owner (nothing was deleted or moved because of these)

| # | What | Why it matters | What to do |
| --- | --- | --- | --- |
| 1 | Brand note (above) | wording of "name and logo not licensed" – a lawyer may word it | owner to check |
| 2 | **Pictures, videos and 3D pages in `site/media/`** that are Fresing's own (milling video, test-mill pages) and the **logos** | they sit in a GPL-3.0 repository, but the GPL is meant for the software | decide: "all rights reserved" (what the brand note now says) or a licence such as CC BY 4.0 |
| 3 | `smholte/house-scene-format` has **no licence file**, and a copy of its checker is in `tests/data/house/` | the code has no stated licence (all rights reserved by default) | give that repository a licence (for example MIT or GPL-3.0-or-later) in its own task |
| 4 | **FarmBot Genesis**: `site/CREDITS.md` says "CC0 1.0 (to be confirmed on genesis.farm.bot)" – the site was not reachable from the build machine, and the licence was **not confirmed** here | a model used for pictures without a confirmed licence | confirm on genesis.farm.bot, or do not use it for the page (nothing of it is in the repository) |
| 5 | Licence texts on the PC: Fresing Render's own GPL, the OpenCascade package's bundled libraries, meshoptimizer | MIT/LGPL/BSD ask that the notice goes with the copies | **Done in 0206:** the licence files are in both release zips and every install (`licenses\`); nothing |
| 6 | The installer **switches Blender's online access on** (`Install-FresingRender.ps1`, the `set_prefs.py` block) for the app's own update check. Blender's own extension repository `extensions.blender.org` is set to sync at start-up by default in Blender 5.2.3 | **Done in 0206:** the installer sets `use_sync_on_startup = False` on every remote repository, and an older install gets the same once at its first start after the update (`blender/ext_sync.py`); the Windows test checks it | nothing |
| 7 | CC BY-SA 4.0 pictures of Thor and the CEB press sit in a GPL repository | CC BY-SA 4.0 stays on them; fine as long as the credit lines stay (they are on the page and in `site/CREDITS.md`) | nothing now; keep the credits when the page changes |
| 8 | No contact address in `SECURITY.md` and `CONTRIBUTING.md` | none was given in the start line, so GitHub's private report form is the only private route | give an address if you want one |
