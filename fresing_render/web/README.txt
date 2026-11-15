Viewer for the Web 3D model (task 0099)

model-viewer-umd.min.js  Google's <model-viewer> 4.4.0 (https://modelviewer.dev, npm @google/model-viewer),
                         the one-file build "dist/model-viewer-umd.min.js" unchanged. Licence: Apache-2.0
                         (LICENSE-model-viewer.txt). Inside it, with their licence notes kept:
                         three.js (MIT, Copyright 2010-2025 three.js authors) and lit (BSD-3-Clause, Google LLC).

Since task 0134 the app's exports no longer use it (every page is the player below); tools/build_site.py still
copies it to the landing page (vendor/) for a bare .glb on "Turn it yourself". Nothing is loaded from the internet.

The web 3D page: the player (task 0106 with surroundings; task 0134: every page)

three-viewer.min.js      three.js r180 (https://threejs.org, npm three@0.180.0) with its add-ons OrbitControls,
                         GLTFLoader, Sky, HDRLoader and meshoptimizer's decoder, bundled into one file (global
                         FRTHREE) by tools/build_web_viewer.py with esbuild. Licence: MIT (LICENSE-three.txt);
                         meshoptimizer's decoder: MIT, Arseny Kapoulkine.
fr_math.js               our own: the sea's height and the vessel's motion (the app's formulas).
fr_page.js               our own: the page (sea, sky, clouds, haze, rain, spray, sun shadows, quality, Auto, drawing
                         only on a change, saved views, the "no graphics card" check).
fr_player.js             our own (task 0134): the controls – settings menu, playback, views, view tools, keys.

Fresing Render puts all four into every page it writes (5 Scene & Render > Web 3D model > Export). Nothing is
loaded from the internet.
