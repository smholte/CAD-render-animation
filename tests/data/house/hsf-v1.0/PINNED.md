# house-scene-format, pinned at tag v1.0

Copied read-only from the public repository `smholte/house-scene-format`, **tag `v1.0`, commit
`52c0352d28c70ba4add21d8fbcfc362da698f397`** (13 Nov 2026), for task 0114: the checker (`check.py`, `hsf/`), the
schemas and the made-up samples. Never edit these files: a newer tag is a new task, which copies the new files and
this list again. `tests/test_house_pinned.py` checks every file against the SHA-256 below.

Run the checker: `~/venv/bin/python tests/data/house/hsf-v1.0/check.py <bake> --scene <hpscene>` (needs `jsonschema`,
`tools/requirements-dev.txt`).

## SHA-256

```
b80a0119dc8e5700c2d1e6fa9c4cec9238e89481bc014127641f30d7ed782d94  check.py
9b576eb7f7d9ae1d91c7932a43da01b2a6a764ef8e3a68d54a503673aa05712d  hsf/__init__.py
5afae9553ab12b0d4e8ae059a1dc66e1a7cfc0e2c496efe3c7d1c248cde02534  hsf/check.py
55eb9d2394084aa0d596ff0f0dbfd0db13b232f21864e1a01b3a48aedcc7d941  hsf/glb.py
dc4ae249bf582a14f31a28585ebbda8bd69e1b4724005133e09c08276c07d247  hsf/images.py
0da3061938ec580a2d0a53e49b4197c8a254729e30a55cc4d4a42a9d8c1654aa  hsf/package.py
f4a2289e7e0b218eb3fd349d36d0ff86e79b655ab8f8d070086786f82f98b926  hsf/sun.py
66d60dbcb7e0fbaa6dce0d02c062bd0f03fe5eeed81bbcf42950402d4642880e  hsf/surface.py
982a3cc9c66045e95b9e6c3d5bb52498b762da6b16ca8847a3ab941d60714f58  hsf/uv1.py
36d1828a0002d942dad90e4c81ecb6bd33e32dd3b0226234b0c8f81cc4a56a1c  samples/sample-house.hpbake
c5d34f407642c9d30f3be7efa35003f699e1d852610cddc592dfb05f462030e6  samples/sample-house.hpscene
3c0abf0db3da4a6d1a49cf7dd0f66c8bf67d0d773f5b5fda2d3af8b8a4f255ef  schemas/bake-1.schema.json
dd5fea4366dc34473b325299a74cbb2352032c5fa442daec26c4536d43fdb53a  schemas/scene-1.schema.json
393441fc3da962287dd6c296ab8798678fc910c6236b71b6baf073eaf09505c1  schemas/surface-1.schema.json
```
