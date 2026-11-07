# 0038 – Milling crash: store the bits' path safely

**Who:** worker · **Status:** open – can start · **Branch:** `task/0038-milling-memory-crash`
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

- [ ] One small helper stores an array in an ID property safely (`del` the key if it is there, then assign; a
      `.tolist()` or `array.array` is fine too if it is not slower for ~2,000 × 4 × 4 values – measure). All four
      stores in `machining.sample()` use it.
- [ ] The whole app is searched for other NumPy values assigned to ID properties (objects, scenes, property-group
      items, collections, materials, the runtime store); any found go through the same helper. The report lists
      what was searched and what was found.
- [ ] A **real-app test that crashes before the fix** and passes after: in a Blender subprocess, set up a small
      milling scene (reuse the existing milling test model), `sample()`, change the animation length so the sample
      count changes, `sample()` again, then do something allocation-heavy (a few Manifold cuts or a loop of large
      allocations). Before the fix the subprocess must die (check it locally on the old code and say so in the
      report – how many tries out of how many); after the fix it passes several times in a row. Plus a quick
      direct test of the helper (store 250 values, then 2,000, then 10, read back right).
- [ ] The queue path works: a queued job of a project with a stored path, after a Build that changed the count,
      renders a few frames and makes its MP4 without a crash (a small, low-resolution job is enough).
- [ ] A project saved with the old version (path stored as before) opens, is read again and cuts without a crash.
- [ ] `CLAUDE.md` section 8, two lines: (1) never assign a NumPy array of another length to an ID property in
      Blender 5.2.3 – use the helper; (2) in a background script nothing reads the milling path after Build
      (`mark_stale` only schedules in the UI) – call `machining.sample()` yourself (0037 problem 7).
- [ ] CHANGELOG entry in plain words for the owner ("fixed a crash when …"); no guide change (nothing visible).
      Version taken last (CLAUDE.md section 2).
- [ ] Tests on GitHub green; merged and released; `TASKS.md` updated; report below filled in.

## Not in this task

- The other six 0037 problems (bit detection of fluted end mills, two way covers per axis, Motor tick, second
  import re-lays the hall, "//" program path) – they stay listed in `TASKS.md` for the lead.
- Not re-reading the path in the queue when nothing changed – a possible later speed-up, not needed for safety.
- The sequencer's 4K frame cache while encoding (0037 addendum) – not now.
- Way covers (0035), PC check (0033): other tasks.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
