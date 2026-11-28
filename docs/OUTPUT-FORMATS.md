# Format numbers on what the app writes (task 0353)

For the Fresing Viewer (task V1) and anyone else who reads these files. The rules live in
`fresing_render/core/outputs.py` (Python) and `fresing_render/web/fr_page.js` (the page); a test compares the words.

## The rule (same for every output)

- A format number is a **whole number of 1 or more**. **No number = format 1** (everything written before 0.2.274).
  Anything else (text, 0, a fraction, true) is "not a number": say so, never guess.
- A reader says what **it reads** (`reads`). A number **below** it: read as it is. **Equal**: read. **Above**: read
  what can be read, show what you can, and say **once**, plainly: *"Made by a newer Fresing Render – update to open
  it fully."* (the maker's name in the words: "House Planner" for a house scene).
- The number goes **up** only when a reader of the old number would show something **wrong**. A new optional field a
  reader may ignore does not raise it.

## The outputs

| Output | Where the number is | Now | Reader |
| --- | --- | --- | --- |
| **3D page** (one HTML file) | the settings block `<script type="application/json" id="fr-env">`: `"v"` (there since the first page) | 1 | `fr_page.js` (`READS`), `outputs.page_state()` |
| **Its data file** (the glTF model inside the page, also a `.glb` next to a site page) | `asset.extras.fresing_format` | 1 | the page takes the higher of the two numbers; `outputs.page_format()` |
| **House scene** `.hpscene` (from House Planner) | `scene.json` `"version"` = the House format's own `"M.n"` (github.com/smholte/house-scene-format `FORMAT.md` section 2; pinned tag in `tests/data/house/`) | 1.0 | `core/house_scene.check_version`: another major version refused, a newer minor read with a note |
| **House bake** `.hpbake` (our answer) | `bake.json` `"version"` = the same format's number, plus `"generator": {"app", "version"}` = the app that made it | 1.0 | House Planner's reader; our own `structure_problems` |
| **Toolbox inbox** | not a file of ours: a refusal of a house is handed on in the job's `status.json` text exactly as the reader words it | – | `blender/toolbox_inbox.py` |

The House format's version **is** the number there (agreed with the House format; this app adds no field to it).
When the Fresing Viewer reads a page it should treat `"v"` and `fresing_format` as above: older / same = open,
newer = open and show the line.

## Raising a number

Raise `PAGE_FORMAT` (and `PAGE_READS` together with the page code that reads it) in `core/outputs.py`, in the same
commit change `fr_page.js` (`READS`), this file and `CHANGELOG.md`, and add a sample page of the new number to the
tests. Never lower a number.
