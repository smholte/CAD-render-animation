# 0147 – Bug hunt round 5: everything merged 15–16 Nov (findings only)

**Who:** worker · **Status:** running (findings only: no app code, starts no test run) · **Branch:**
`task/0147-bug-hunt-5` (report only)
**Started by:** lead chat, 16 Nov 2026 – 11 releases in one night, most of them merged unattended · **Model:** Opus ·
effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** reading and running everything; **no edits** except this file (and `tasks/img/0147_*`).

## Goal

Find what broke or is still wrong in the work merged since 0.2.104, before the owner relies on it – as bug hunts 0045,
0068, 0118 and 0131 did (same report format: one row per finding with place, proof, effect for the owner, suggested
fix, size).

## Scope (the reports in `tasks/` say what each changed)

0.2.105 0128 turbine extras + ATC web model · 0.2.106 0136 export crash fix + waterline · 0.2.107/108 0126 CPS run from
the rack, 0140 sequence fixes · 0.2.109 0130 House format 1.0.1 · 0.2.110 0137 cable data kept, sea re-bake, old
projects · 0.2.111 0139 mesh import fixes · 0.2.112 0134 web player · 0.2.113 0138 Build at any frame · 0144 render
kit start window (kit only).

Look especially for: work lost on save / reopen / model update / undo; old projects (made with 0.2.95–0.2.104)
opening and building the same; the fixes of 0136–0140 really holding (repeat each 0131 row's proof); two tasks merged
the same night touching neighbouring code (0137 + 0138 in paths/paths_sea, 0126 + 0137 + 0138 in the demo, 0134 +
0136 in web3d); the web player on a phone-sized window and with a software renderer (headless Chrome); the kit
window's PowerShell/Windows parts read carefully (no Windows here: say what you could not run).

## Done when

- [ ] Report with rows sorted by harm (crash / lost work / wrong result / slow / cosmetic), each with a proof script
      or steps; a short "In short (for the owner)".
- [ ] Pushed to `main` touching only `tasks/` (no run); then check that main really contains your commit.

## Not in this task

Fixing (the lead turns rows into tasks); 0142 and 0145 (running).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
