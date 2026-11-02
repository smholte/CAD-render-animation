# Update channel

Blender has a built-in update system for extensions. A "repository" is just a folder
with an `index.json` listing and the extension zips. `tools/build_release.py` creates it
in `dist/update-repo/`.

## Publishing a new version

1. Raise the version in `fresing_render/__init__.py` **and** `fresing_render/blender_manifest.toml`.
2. Run the tests: `python -m pytest tests/`.
3. `python tools/build_release.py`
4. Copy the contents of `dist/update-repo/` to the update location (keep older zips there
   if you like; `index.json` lists what is present).
5. On the PCs: Blender shows "update available" in the status bar (it checks on start-up);
   Edit > Preferences > Get Extensions > Update. One click.

## Where to host it

Fresing PCs and other sites are on different networks, so the repository should be
reachable over the internet, but private.

| Option | Private how | Notes |
| --- | --- | --- |
| Small web host / cloud bucket behind a token check | Access token (Blender sends it as an `Authorization` header) | Best fit; needs a tiny server-side check |
| Static host on an unguessable URL | Secret URL | Simplest; anyone with the link can download |
| Windows network share (`file://SERVER/share/index.json`) | Network permissions | Works only inside one company network |

The installer accepts the URL and token:

```
Install.bat -UpdateUrl https://<host>/fresing-render/index.json -AccessToken <token>
```

## Blender version changes

The extension is pinned to Blender 5.2 (`blender_version_min = 5.2.0`,
`blender_version_max = 5.3.0`). When moving to the next LTS:

1. Change `$BlenderVersion`, `$BlenderSeries` and `$BlenderSha256` in
   `installer/Install-FresingRender.ps1` (checksum from download.blender.org/release/BlenderX.Y/).
2. Update the version range and the OpenCascade wheel (Python version of the new Blender)
   in the manifest and `tools/build_release.py`.
3. Run the tests against the new `bpy` version, build, and roll out the new installer to
   all PCs at the same time (files saved in a newer Blender may not open in an older one).
