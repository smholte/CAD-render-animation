# 0121 – Bug-hunt fixes C: hoses with vessel motion, the Assembly sequence preview, old vessel-motion rigs

**Who:** worker · **Status:** open – can start · **Branch:** `task/0121-fixes-motion-hoses-sequence` (or the web session's)
**Started by:** lead chat, 14 Nov 2026, from bug hunt 0118 (`tasks/0118-bug-hunt-3.md`)
**Area:** Flex + Motion: `blender/flex.py` (`_moved`, `_live`, `_follow`), `blender/vessel_motion.py` (`changed`, `_sync`) + `core/vessel_motion.py` (rig key version), `blender/sequence.py` + `core/sequence.py` (preview, `_in_way`, `_across`, measuring at rest), `props.py` (`_seq_preview_changed`, additive), `reimport.py` (`_carry_over`: end the preview), `animation.py` **only** the one call in `clear_keys` (0120 edits it too: merge carefully); their tests. **Do not edit:** files of 0119, 0120, 0117 named in their briefs.
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Fix rows **4, 5, 8, 9, 10, 12** of the bug hunt (a sequence preview left above 0 % becomes permanent moves at a model update; hoses left behind when a vessel-motion setting changes after Build; the preview slider re-plans the whole step at every move – 2.8–5.1 s for 260 parts, aim well under 0.2 s and measure it; old 0.2.65–0.2.87 rigs never rebuilt; every hose solved from scratch every frame with vessel motion on and no Build – aim: no solve when the pair moved rigidly; sequence keys depending on the frame Build was pressed at).

## How

- The rows' text in `tasks/0118-bug-hunt-3.md` (Findings) gives where, what happens, the proof and a suggested fix.
  Read each row, repeat its proof first (it must fail), then fix. **Every fix gets a test that failed before**
  (CLAUDE.md section 6). The suggested fix is a suggestion: a better one is fine, say why in the report.
- A row that turns out not to be real (cannot be shown on today's `main`): say so in the report, no change.
- No new features, no UI redesign. A visible change (a new warning, a note) gets its tooltip/guide line; no new tour
  stop or PC-check line is needed for a fix unless the row asks for one.
- One version at the end (take the number last, CLAUDE.md section 2).

## Done when

- [ ] Each row: fixed with a test that failed before, or shown not real (with how)
- [ ] Full run green on GitHub; CHANGELOG in plain words (what the owner would have noticed); version taken last
- [ ] Report filled in; TASKS.md row → done

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed (per row):**

**Tested:**

**Open points:**
