"""Build fresing_render/web/three-viewer.min.js: the three.js parts of the Web 3D page with surroundings (task 0106).

    python3 tools/build_web_viewer.py            # needs node + npm (package registry); writes the bundle

The page itself (fresing_render/web/fr_page.js) is our own readable code and is not built. This bundle is only
three.js (MIT) and four of its add-ons (orbit controls, glTF loader, meshopt decoder, sky, HDR loader), pinned to the
versions below, as one global ``FRTHREE`` that works from an inline <script> (no modules, no internet). It is committed:
the app and the tests never run npm. Run this only to change the three.js version (then update THREE_VERSION in
fresing_render/core/web3d_env.py and fresing_render/web/README.txt).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

THREE = "0.180.0"            # three.js r180 (3 Sep 2025)
ESBUILD = "0.25.10"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "fresing_render", "web", "three-viewer.min.js")
LICENCE = os.path.join(ROOT, "fresing_render", "web", "LICENSE-three.txt")


def main() -> int:
    work = tempfile.mkdtemp(prefix="fr_three_")
    try:
        npm = shutil.which("npm")
        if not npm:
            print("npm is not installed")
            return 1
        subprocess.run([npm, "init", "-y"], cwd=work, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([npm, "install", "--no-audit", "--no-fund", f"three@{THREE}", f"esbuild@{ESBUILD}"],
                       cwd=work, check=True)
        shutil.copy2(os.path.join(HERE, "web_viewer", "entry.js"), os.path.join(work, "entry.js"))
        banner = (f"/* three.js r{THREE.split('.')[1]} (MIT, Copyright 2010-2025 three.js authors) with OrbitControls, "
                  "GLTFLoader, Sky, HDRLoader and meshoptimizer's decoder (MIT, Arseny Kapoulkine); bundled for "
                  "Fresing Render by tools/build_web_viewer.py */")
        subprocess.run([os.path.join(work, "node_modules", ".bin", "esbuild"), "entry.js", "--bundle", "--minify",
                        "--format=iife", "--global-name=FRTHREE", "--target=es2019", "--legal-comments=none",
                        f"--banner:js={banner}", f"--outfile={OUT}"], cwd=work, check=True)
        shutil.copy2(os.path.join(work, "node_modules", "three", "LICENSE"), LICENCE)
        print(f"wrote {OUT} ({os.path.getsize(OUT) / 1e6:.2f} MB)")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
