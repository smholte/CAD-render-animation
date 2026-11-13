// The three.js parts the Web 3D page with surroundings needs (task 0106), bundled by tools/build_web_viewer.py into
// fresing_render/web/three-viewer.min.js as one global, FRTHREE. Nothing else: the page's own code is
// fresing_render/web/fr_page.js (readable, inlined next to it).
export * from 'three';
export { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
export { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
export { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
export { Sky } from 'three/examples/jsm/objects/Sky.js';
export { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';
