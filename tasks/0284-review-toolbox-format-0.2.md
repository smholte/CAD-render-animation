# 0284 – Review (findings only): toolbox-format 0.2 against how Fresing Render uses it

**Who:** worker · **Status:** done (not a code task) · **Branch:** `task/0284-tbf-0.2-review`
**Started by:** lead, 23 Nov 2026 (ToolBox lead's request through the lead post, 21 Nov: format 0.2 ready for review;
round 3 – an empty `job.json` counts as "not there yet" – follows) · **Model:** Opus · effort Medium
**Area:** read only – `smholte/toolbox-format` branch `task/0011-format-0.2` (from commit `8cd350b`, and round 3 when
it is on the branch), its `CHANGELOG.md` section 0.2 "What changed for tool authors" (points 1–11); Fresing Render's
`core/toolbox.py`, `core/tbf/`, `blender/toolbox_inbox.py`, `ops_toolbox.py`, the installer / uninstaller. Writes only
this task file. No code change (the move to 0.2 is a later task after the tag).

## What to answer (in the report, each with the point / section it concerns)

1. **OK for 0.2, or findings** – what Fresing Render would have to change to move from v0.1.1, and anything in 0.2 that
   does not fit how it works.
2. **Point 10:** a native tool that may run as several copies does not delete `alive.json` when it closes (6.4), and a
   finished job's files may be removed at once without the checker complaining (P30). Can Fresing Render run as
   several copies (two windows of the app)? Who writes / deletes its `alive.json` today? How does it clean up a
   finished job? Does 0.2's rule fit, or what would break?
3. **Point 11 / `write_status()`:** where Fresing Render treats `false` as "the job has ended" today (from 0.2 it means
   "not written now").
4. **Round 3** (if pushed by the time you finish): an empty `job.json` from Chrome – does Fresing Render's receiver read
   it as "not there yet"? Anything else in round 3 that touches it.
5. The **Fresing Viewer**'s types for the next format version (from study 0269): which it needs built in (e.g. IGES,
   3MF, the baked 3D page) – one list.

The lead turns the report into the answer to the ToolBox lead. Keep it to what the ToolBox lead needs: one page.

## Report (23 Nov 2026)

Read: `toolbox-format` branch `task/0011-format-0.2` at `8cd350b` (FORMAT.md 2, 3.5, 5.1–5.2, 6.3, 6.4, 7.1–7.4; CHANGELOG
0.2 points 1–11, P1–P32, W3); Fresing Render `main` at 0.2.205: `core/toolbox.py`, `core/tbf/`, `blender/toolbox_inbox.py`,
`ops_toolbox.py`, the installer / uninstaller, `tests/test_toolbox*.py`, study 0269. **Round 3 is not on the branch yet**
(newest commit `8cd350b`, 23 Nov): answer 4 is about Fresing Render's code as it is. Nothing run, no code changed.

### 1. Verdict: OK for 0.2 – no rule that does not fit; one wish, one point to note

Fresing Render does **not** use the reference `tbf/folder.py`: it has its own inbox (`core/toolbox.py`, `Inbox`) and copies
only `tbf/names.py`, `tbf/detect.py`, `types.json`. So "copy the code" is not enough; the move to 0.2 (a later task)
changes this in `core/toolbox.py`:

| 0.2 point | What Fresing Render does today (v0.1.1) | Change for 0.2 |
| --- | --- | --- |
| 1, 3.5, 2 – version | `VERSION` from `names.py`; `ensure_folder` writes `toolbox-folder.json` only when missing | copy `names.py`/`detect.py`/`types.json`; **rewrite the folder mark when it has another version** (FORMAT 2) |
| 2, 3 – names (P3–P6) | job ids 22 chars, id `nl.fresing.render`; reply file = `safe_name(title)[:60] + ".hpbake"` ≤ 67 ASCII chars – fit. Duplicate names compared with `.lower()` (`take`, `send`) | use the new "same in capitals" + NFC of `names.py` in both places; `safe_name` should avoid device names (`COM0.hpbake` is refused by `send`, the result is then only kept locally – no crash) |
| 5, P1 – left-behind jobs | `_adopt()` once at start, and only when no other copy's `alive.json` is fresh; a `waiting` status is written again only when its text changes | take up only status > 5 min old, with `.taking-up`, at start **and once a minute**; **rewrite a held job's status every 2 min** (waiting too) |
| 6, P20 – short / missing file | `NotReady`: waits up to 60 s (`SHORT_WAIT`), then `bad-job` | `bad-job` at once |
| 6, P21 – cancelled before taken | claims `waiting`, then the next look ends it `cancelled` (same end state; a bad job with `cancel.json` ends `failed`) | step 2 first: `cancel.json` → `cancelled` |
| 7, P31 – user declines | "Not now" ends `cancelled` already | none |
| 8, 7.1 – never over a final status | `finish()` and `_flush()` (the retried writes) write without reading first | read `status.json` just before every write; skip when final |
| 7.1 – text one line | `one_line` joins whitespace; other control characters (e.g. U+0001) stay (escaped, the file stays JSON) | copy the reference's cleaner (control → space, broken → U+FFFD) |
| 11, W3 – refused write | a refused write (any state) is kept and tried at every look until it goes – no 2-s limit, never stops a job | fits; keep it |
| P23 – `failed` has a code | `finish()` adds `error` | none |
| P25 – cleaning up | 30-day rule by the **folder's mtime**; `_remove_tree` also removes a folder without files | by `job.json`'s `created` (else the newest file); leave a folder without files |
| P28 – `reply_to` | checked already | none |
| P30 – finished job without files | `finish()` deletes the job's files at once (keeps `job.json`, `status.json`, `cancel.json`) | fits – now no checker complaint |

**Wish (point 5, a fit question for the ToolBox lead):** with the 5-minute rule, a user who closes Fresing Render with a
house waiting and opens it again within 5 minutes does not see "Bake now" until the 5 minutes are over – today it shows at
once (`_adopt` when no other copy's `alive.json` is fresh). Acceptable, but the panel needs a line ("A house from House
Planner is waiting – it comes back here in N min"). If the ToolBox lead wants it simpler: allow a native tool to take up a
`waiting` job at once when the tool's own `alive.json` is older than 30 s (no copy watching).

**To note (6.4 / 7.1):** one bake step blocks Blender; a Cycles bake of a big atlas on the processor can block longer than
5 minutes. With two copies open, the other may then take the job up and end it `failed`; the first copy's `done` is then not
written (final stays). Rare (two copies + very long step), and correct by the format – the bake simply is lost.

### 2. Point 10 – several copies, `alive.json`, clean-up

- **Several copies: yes.** Every start from the shortcut is its own Blender process; nothing stops a second one. Each
  copy has its own `Inbox`; one job goes to one copy by the exclusive create of `status.json` (`claim`, tested in
  `test_two_copies_one_job`).
- **`alive.json` today:** every copy writes it every 10 s (`write_alive`, never the same bytes as already there); on
  closing (`atexit` → `toolbox_inbox.closing()`, and `use_folder()` when the folder changes) a copy deletes it **only when
  the file holds the bytes it wrote itself** (`remove_alive`). So one copy closing while another runs leaves the other's file
  (`test_alive_is_removed_only_by_the_copy_that_wrote_it`).
- **0.2's rule fits.** Change: stop calling `remove_alive` (two calls) and drop the tests that expect the delete. What
  changes for the user: House Planner says "Fresing Render is open" up to 30 s after it closed – harmless. Nothing else
  depends on the delete once the 5-minute take-up replaces today's `_others()` check (which used "alive.json gone = the
  other copies closed", `test_toolbox.py` line 324).
- **Clean-up of a finished job:** `finish()` deletes the job's files at once (not `job.json`, `status.json`,
  `cancel.json`; what Windows holds is tried at the next look); the folder goes a day after the final status's `updated`,
  any folder after 30 days (today by folder date – see P25). P30 fits exactly what it does.

### 3. Point 11 – `write_status()` false

**Nowhere.** Fresing Render's own `_write()` already means "not written now" with False (kept, written at the next look);
`progress()` returns False also for "too soon" (once a second) and "not held". The callers (`toolbox_inbox.py` lines 346,
386, 578; `begin()`) ignore the value; `_held()` only keeps the old text to try again. The light bake's
`progress(...) is False` → cancel (`lightbake.py` 346) is not wired to the Toolbox status. Nothing to change.

### 4. Round 3 – an empty `job.json`

Not pushed yet. Today Fresing Render already reads an empty `job.json` as "not there yet": `read_doc` raises `OSError`
for an empty file, `_new_jobs` skips it until the next look, no status is written (test
`test_an_empty_job_json_is_not_there_yet`). Same for an empty `status.json` (`_held`, `_adopt`, `clean` take it as not
readable now). It never refuses such a job; a `job.json` that stays empty for ever is removed by the 30-day rule. If round
3 adds anything else (e.g. a time after which an empty file is a fault), that needs a look when it is on the branch.

### 5. The Fresing Viewer's types for the next format version (study 0269)

Built-in types wanted (additions only):

1. **`iges`** – extensions `.igs`, `.iges`; by extension (no sure content rule).
2. **`3mf`** – `.3mf`, `zip_has` `3D/3dmodel.model`.
3. **`mp4`** – `.mp4`, `head_matches` `ftyp(isom|iso2|mp41|mp42|avc1)` at byte 4 (results of the turntable).
4. **Fresing Render's 3D page** – **new finding:** 0.2 forbids `head_matches` in own types (point 4), and the study planned
   to detect the page by a `<meta name="generator" content="Fresing Render 3D page">` in its head (an own type
   `nl.fresing.render.page`). That needs a pattern, so either a **built-in short type** (e.g. `frpage`: `.html`,
   `head_matches` on that meta line, `by_content`), or the page starts with a fixed marker `starts_with` can read (no
   spaces, ≤ 64 chars, e.g. a comment `<!--fresing-render-3d-page-->` before `<!DOCTYPE html>`). Preferred: the built-in
   type – a page cannot start with arbitrary bytes safely in every browser.

Already built in and used by the Viewer: `step`, `glb`, `gltf`, `stl`, `obj`, `png`, `jpeg`. Until the new ones come:
`ext:igs`, `ext:iges`, `ext:3mf`, `ext:mp4` work.

### Work and runs

One worker session, no subagents, no code; task-list-only pushes (no GitHub run starts for them).
