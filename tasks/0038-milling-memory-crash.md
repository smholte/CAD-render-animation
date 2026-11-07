# 0038 – Milling crash: store the bits' path safely

**Who:** worker · **Status:** done (0.2.32) · **Branch:** `task/0038-milling-memory-crash`
**Started by:** lead chat, 7 Nov 2026 · **Area:** Machining lane – `fresing_render/blender/machining.py`
(storing the path), its tests; one line each in `CLAUDE.md` section 8 and `CHANGELOG.md`
**Model:** Opus · effort Medium (small fix, but a memory-safety bug in Blender that must be proven gone)

## Goal

Milling never crashes Blender again when the bits' path is read a second time – after a new Build, after a change
in the step's settings, or at the start of every queued job. The owner can render his mill project (task 0037) as a
queued 4K video and the MP4 gets made.

## Background

Found by task 0037 (report problem 1 and the addendum in `tasks/0037-owner-mill-gcode-demo.md`). Short version:

- Blender 5.2.3 corrupts its memory when an **array ID property** gets a **NumPy array of a different length** than
  it had: `scene["x"] = np.random.rand(250)`, then `scene["x"] = np.random.rand(2000)` → "free(): invalid size",
  "corrupted size vs. prev_size" or a segfault *a little later*, wherever the next big allocation happens (the
  Manifold boolean, the sequencer while encoding the MP4). Same length, a plain list (`.tolist()`), or `del` first
  are all fine.
- `machining.sample()` does exactly this at its end (`fresing_render/blender/machining.py`, about line 529–533):
  `item["fr_t"]`, `item["fr_o"]`, `item["fr_d"]` per bit and `s["fr_wp_m"]` for the workpiece.
- Every Build gives a slightly different number of samples (1,928 ↔ 1,930 on the 0037 project), and the path is
  read again after Build in the app **and** at the start of every queued job (`machining.prepare`, called from
  `blender/queue.py`). So a saved project with a stored path crashes at random: 4 of 4 cuts after a re-read in
  0037, and on the owner's PC a 2 h 16 min queued 4K video crashed after the last frame while making the MP4.
- Readers of these keys (`machining.py` ~line 573–576, `chips.py` ~line 201–203) wrap them in `np.array(...)`, so
  they work the same with a stored list.
- A grep by the lead found no other NumPy arrays stored in ID properties (`importer/step_reader.py:1029` and
  `core/machining.py:406` are plain dicts) – check it properly anyway, including `foreach_get` results and
  `rt[...]` / `runtime()` stores.

## Done when

- [x] One small helper stores an array in an ID property safely (`del` the key if it is there, then assign; a
      `.tolist()` or `array.array` is fine too if it is not slower for ~2,000 × 4 × 4 values – measure). All four
      stores in `machining.sample()` use it.
- [x] The whole app is searched for other NumPy values assigned to ID properties (objects, scenes, property-group
      items, collections, materials, the runtime store); any found go through the same helper. The report lists
      what was searched and what was found.
- [x] A **real-app test that crashes before the fix** and passes after: in a Blender subprocess, set up a small
      milling scene (reuse the existing milling test model), `sample()`, change the animation length so the sample
      count changes, `sample()` again, then do something allocation-heavy (a few Manifold cuts or a loop of large
      allocations). Before the fix the subprocess must die (check it locally on the old code and say so in the
      report – how many tries out of how many); after the fix it passes several times in a row. Plus a quick
      direct test of the helper (store 250 values, then 2,000, then 10, read back right).
- [x] The queue path works: a queued job of a project with a stored path, after a Build that changed the count,
      renders a few frames and makes its MP4 without a crash (a small, low-resolution job is enough).
- [x] A project saved with the old version (path stored as before) opens, is read again and cuts without a crash.
- [x] `CLAUDE.md` section 8, two lines: (1) never assign a NumPy array of another length to an ID property in
      Blender 5.2.3 – use the helper; (2) in a background script nothing reads the milling path after Build
      (`mark_stale` only schedules in the UI) – call `machining.sample()` yourself (0037 problem 7).
- [x] CHANGELOG entry in plain words for the owner ("fixed a crash when …"); no guide change (nothing visible).
      Version taken last (CLAUDE.md section 2).
- [x] Tests on GitHub green; merged and released; `TASKS.md` updated; report below filled in.

## Not in this task

- The other six 0037 problems (bit detection of fluted end mills, two way covers per axis, Motor tick, second
  import re-lays the hall, "//" program path) – they stay listed in `TASKS.md` for the lead.
- Not re-reading the path in the queue when nothing changed – a possible later speed-up, not needed for safety.
- The sequencer's 4K frame cache while encoding (0037 addendum) – not now.
- Way covers (0035), PC check (0033): other tasks.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 7 Nov 2026.

**What changed:**
- New `fresing_render/blender/idprops.py` with `store_array(owner, key, values)`: deletes the key if it is there,
  then assigns a flat float64 NumPy array. All four stores in `machining.sample()` (`fr_t`, `fr_o`, `fr_d`,
  `fr_wp_m`) use it. Readers unchanged (they already wrap in `np.array`).
- Timing (4-core session, bpy module, 2,000 × (1+3+3) + 32,000 values, 200 repeats): del + NumPy 0.016 ms,
  del + `.tolist()` 0.48 ms – kept NumPy.
- Search of the whole app (`fresing_render/`, all `.py`): every `x["…"] = …` and `x[VAR] = …` store, `foreach_get`
  results, `rt[...]`/`runtime()` stores. Found only the four in `machining.sample()`. Others checked and safe:
  `faces.py` (already `.tolist()`), `build.py` `fr_axes` (list), `surroundings.py` `fr_min/fr_max/fr_cut_c/fr_irr`
  (lists/tuples of floats), cylinders (scalars), `machining.runtime()` / `chips.runtime()` / `decals._ARRAYS`
  (plain Python dicts, not ID properties), `importer/step_reader.py:1012` (dict for an `.npz`), `pccheck/`.
  A test (`test_no_numpy_array_is_assigned_to_an_id_property_directly`) now refuses `["…"] = np.` in `blender/`.
- `CLAUDE.md`: section 8 two lines (NumPy arrays of another length; `sample()` yourself in background scripts),
  `idprops.py` in the layout. CHANGELOG 0.2.32.

**Tested and measured** (4-core Claude Code session, Blender 5.2.3 as a Python module; the real Blender
program could not be downloaded – download.blender.org is blocked here – so the real-app runs are GitHub's):
- Plain bug: 30 stores of random lengths into `scene["x"]` + allocations: 2 of 3 runs died
  ("free(): invalid size", "munmap_chunk(): invalid pointer").
- `tests/milling_crash_child.py` (test mill, sample, 5–6 re-reads with other animation lengths, cuts at ~12 frames
  each, big allocations): **old way (`--unsafe`) 5 of 5 died** (4 × segfault, 1 × "corrupted size vs. prev_size");
  new way 5 of 5 passed (sample counts 89, 111, 135, 114, 128, 47, 169).
- New `tests/test_idprops.py` (5 tests, 1 min 48 s): helper read-back (250 → 2,000 → 10 → 2,000 → 0 → 7), the
  child twice in a row, a project saved the old way (NumPy arrays stored) opened and re-read 4 times with cuts,
  and a queued draft MP4 job whose saved path was out of date (queue re-reads with another count). With the old
  `machining.py` the three crash tests failed 3 of 3 runs; the queue job ended "Renderer stopped unexpectedly"
  right after "reading the motion of the bits" – the owner's crash.
- `tests/test_machining.py` + `tests/test_chips.py`: 23 passed.
- GitHub runs: 1 (branch) + reuse on `main`.

**Open points / follow-up tasks:**
- Not re-reading the path in the queue when nothing changed (speed-up, not needed for safety) – as the brief says.
- The owner's mill project (0037): render the 4K queued video again with 0.2.32 to confirm on his PC.
