# 0189 – Fix: web 3D export of the demo too slow + small page faults (bug hunt 6, rows 9, 6, 12, 13, 17)

**Who:** worker · **Status:** running · **Branch:** `task/0189-web3d-follow-ups`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Opus · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Web 3D lane (`blender/web3d.py`, `core/web3d.py`, `ui_web3d.py`, the page's `fr_*.js`, their tests)

## Goal

Exporting the demo as a web page takes minutes again (not ~36 min), the panel's time estimate is honest, and the page
has no floating sea cable or covered buttons.

## Background

- **Row 9 (main):** the demo's export takes 2,174 s instead of 96 s – 264 parts get their own marine bake (~7 s each),
  mostly wind-park parts baked again per turbine (CLAMP J-TUBE ×36, TP SLEEVE ×9 …); the panel says "about 34 s".
  Suggested: copies with the same mesh, looks and world height / turn share one bake; the estimate counts the per-part
  bakes (or warns above N parts). 0175 (0.2.143) changed the file sizes since – measure again on main first.
- **Row 6:** vessel motion off (at export, or the visitor's switch) → the laid sea cable dips 0.78 m into the seabed or
  floats 0.85 m above it.
- **Row 12:** phone sideways: the part tools' panel covers the saved-views row (`placePanel` only ≤ 600 px; `layoutCheck`
  leaves out `#fr-tpanel`).
- **Row 13:** an animated page shows a label's live fields at the exported frame ("Lay speed 0.0 m/min").
- **Row 17:** one draw of the Web 3D panel costs ~45–60 ms on the small demo (estimates walk every part).

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [ ] Row 9: the small demo's static export at least 5× faster than the row's 2,174 s on the same machine (say the
      load), same look where copies share a bake (compare pictures); the estimate within ~2× of the measured time.
- [ ] Rows 6, 12, 13, 17 each fixed with a test (row 12 in the phone-size layout check).
- [ ] The site's models still build (`build_site.py --web-model` keeps the IEA entries in media.json – 0179's note).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Spool solids after a scripted export (row 11 is in 0187); the Flex lane's files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
