Viewer for the Web 3D model (task 0099)

model-viewer-umd.min.js  Google's <model-viewer> 4.4.0 (https://modelviewer.dev, npm @google/model-viewer),
                         the one-file build "dist/model-viewer-umd.min.js" unchanged. Licence: Apache-2.0
                         (LICENSE-model-viewer.txt). Inside it, with their licence notes kept:
                         three.js (MIT, Copyright 2010-2025 three.js authors) and lit (BSD-3-Clause, Google LLC).

Fresing Render puts this script into every viewer page it writes (5 Scene & Render > Web 3D model > Export),
and tools/build_site.py copies it to the landing page (vendor/). Nothing is loaded from the internet.
