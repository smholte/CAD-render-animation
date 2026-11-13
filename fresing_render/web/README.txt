Viewer for the Web 3D model (task 0099)

model-viewer-umd.min.js  Google's <model-viewer> 4.4.0 (https://modelviewer.dev, npm @google/model-viewer),
                         the one-file build "dist/model-viewer-umd.min.js" unchanged. Licence: Apache-2.0
                         (LICENSE-model-viewer.txt). Inside it, with their licence notes kept:
                         three.js (MIT, Copyright 2010-2025 three.js authors) and lit (BSD-3-Clause, Google LLC).

Fresing Render puts this script into every viewer page it writes (5 Scene & Render > Web 3D model > Export),
and tools/build_site.py copies it to the landing page (vendor/). Nothing is loaded from the internet.

Web 3D page WITH surroundings (task 0106)

three-viewer.min.js      three.js r180 (https://threejs.org, npm three@0.180.0) with its add-ons OrbitControls,
                         GLTFLoader, Sky, HDRLoader and meshoptimizer's decoder, bundled into one file (global
                         FRTHREE) by tools/build_web_viewer.py with esbuild. Licence: MIT (LICENSE-three.txt);
                         meshoptimizer's decoder: MIT, Arseny Kapoulkine.
fr_math.js               our own: the sea's height and the vessel's motion (the app's formulas).
fr_page.js               our own: the page (sea, sky, clouds, haze, rain, spray, sun shadows, quality, Auto).

Fresing Render puts all three into the page when Surroundings on the page is "As in the project". Nothing is
loaded from the internet.
