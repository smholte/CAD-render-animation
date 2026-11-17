# 0178 – "Fresing Render" in Task Manager (a branded copy of blender.exe)

**Who:** worker · **Status:** done (0.2.137) · **Branch:** `claude/eager-pasteur-w3w05t` (worktree `task/0177-exe-name`)
**Started by:** owner, directly in the 0169 session (17 Nov 2026) · **Model:** Opus · effort Medium (Windows-only code)
**Area:** new `fresing_render/winexe.py`; `fresing_render/appicon.py` (shortcut target), `blender/updates.py`
(restart), `update_helper.py` (names it waits for), `pccheck/ops.py` (console runs), `installer/*.ps1`,
`tools/ci_windows_install.ps1`, `tools/appicon_test.py`, tests, guide line, CHANGELOG.
**Number:** started as 0177; the lead gave 0177 to the render-kit window task at the same time, so this one is
0178. The code comments written before that say "task 0177" – the next change to those files corrects them.
**Lane:** Quality & delivery (`installer/`). **0171 (Windows job split) touches `tools/ci_windows_install.ps1` too: do
not run both at once.**

## Goal

Task Manager (and every other place Windows shows a program's name) says **Fresing Render**, not "Blender", while the
app runs – also for the render queue's background runs.

## Background (measured on Blender 5.2.3's own files, 17 Nov 2026)

- Task Manager shows a program's `FileDescription` from its version resource. `blender.exe` (113 MB) has one version
  resource (id 1, language 1033: FileDescription and ProductName "Blender", CompanyName "Blender Foundation", codepage
  0), two icon groups (`APPICON` and `1`, icons 1–8), a manifest (id 1) and an Authenticode signature (14,808 bytes at
  the end of the file).
- `blender.exe` is a **console** program (PE subsystem 3): started directly it opens a console window; Blender's own
  `blender-launcher.exe` (subsystem 2, GUI) exists to hide it. Every background run the app starts already writes to a
  log file with no window (`CREATE_NO_WINDOW`), except Help > Fresing Render PC check… (its own console window).

## Design

1. **The copy** `Fresing Render.exe` next to `blender.exe` (so Blender finds `blender.shared`, its DLLs, the `5.2`
   folder and `portable` exactly as before; the manifest stays): the bytes of `blender.exe` with
   - the signature taken off (the security directory entry zeroed and the certificate bytes cut from the end): a
     changed file with Blender's signature would be a *broken* signature; this way it is plainly unsigned;
   - the subsystem set to GUI (2): no console window (the entry point stays the C runtime's `main`, which works for
     both);
   - its version resource rebuilt with FileDescription / ProductName "Fresing Render" (CompanyName "Fresing", the
     rest – version numbers, GPL notice, original file name – kept, Comments say it is Blender 5.2.3);
   - both icon groups replaced by the Fresing Render icon (`brand/fresing-render.ico`).
   The byte work is plain Python (`winexe.py`, tested on Linux); the resources are written with Windows' own
   `BeginUpdateResource` / `UpdateResource` / `EndUpdateResource` (no tool downloaded). A stamp file
   (`fresing-render-exe.json`) holds the size and time of the `blender.exe` it was made from and the maker's version:
   a new Blender or a new maker makes it again.
2. **Started once before it is used:** `"Fresing Render.exe" --version` must answer "Blender 5.2…" within 60 s.
   Only then do shortcuts point at it. If anything fails (blocked, quarantined, no answer), the copy is deleted and
   everything stays on `blender-launcher.exe` / `blender.exe` (a line in the console / installer output).
3. **Smart App Control** (Windows 11) blocks unsigned programs when it is on, and may switch itself on from
   "evaluation": when its registry state (`HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy`,
   `VerifiedAndReputablePolicyState`) is 1 (on) or 2 (evaluation), no copy is made, and an existing one is taken out
   of use. SmartScreen only checks files that came from the internet (Mark of the Web): the copy is written locally and
   has none (checked in the test).
4. **Who starts it:** the app's shortcuts (Desktop, Start menu, pinned), the app's own restart after Update now, and –
   because they start `bpy.app.binary_path` – the render queue and the other background runs of a running app. The
   console runs (Self test, PC check shortcuts, Help > PC check…) keep `blender.exe` (`winexe.console_exe`).
5. **Made by:** Install.bat (after the extension is in), and for PCs that update with Update now the app at start (in
   the icon thread of 0169), before it refreshes the shortcuts. Install / Uninstall / the update helper treat a
   running `Fresing Render.exe` like `blender.exe`.

## Done when

- [ ] `winexe.py` with Linux tests (version resource rebuilt byte for byte from Blender's own, icon groups, signature
      and subsystem edits on a made-up PE)
- [ ] GitHub's Windows job: the installed copy's `FileDescription` is "Fresing Render", read from the **running
      process**; it starts without a console; Defender scans it clean; it has no Mark of the Web; shortcuts point at it
- [ ] An older install gets it from the app at start (tested on the Windows job)
- [ ] Independent review of the Windows code; version + CHANGELOG + guide line; merged; report with the owner's steps

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (the 0169 session), 17 Nov 2026. Released as **0.2.137**.

**What changed:** as in Design. Plus, from the independent review (a helper agent that did not write the code): five
places accepted only programs named "blender…" – the render queue, the queue's busy check, the project lock, the mesh
import's converter, the self-test – and now use `winexe.is_blender_program`; a **safe-start** shortcut on Blender's
launcher (Start menu, made by Install.bat and by the app when missing; never retargeted); a copy that vanished after
it was made and checked (an antivirus) is not made again for that Blender – the app stays on `blender.exe`; the swap
while the copy runs puts the old one back on failure; with no console (a windowed program) Python's output goes to
`Fresing Render console.log` next to the program.

**Tested and measured:** Linux: `tests/test_winexe.py` (20: Blender's own version resource rebuilt byte for byte, the
rebranded one, icon groups, signature/subsystem edits on made-up PE32/PE32+ files, stamp, safe start, restart, the
console log) + `test_appicon.py`, `test_updates*.py`, `test_pccheck.py`. Blender 5.2.3's real `blender.exe` (from
download.blender.org): console subsystem, signature 14,808 bytes at the very end, version resource id 1 / 1033, icon
groups `APPICON` and `1`. GitHub's Windows job (run 43992825471, full, green at the first try): Install.bat makes the
copy; the file's and the **running process's** FileDescription/Product are "Fresing Render"; it keeps running (not
blocked); **Defender's scan (MpCmdRun) finds nothing**; no Mark of the Web; GUI subsystem; no signature left; it
answers `--version` ("Blender 5.2.3 LTS"); the app shortcuts start it, the console ones stay on `blender.exe`, safe start
on the launcher; an older install (launcher shortcut, no copy) is fixed by the app's refresh; Smart App Control on
(simulated) takes the copy out and the shortcuts back to the launcher, off again brings it back; the restart after
Update now starts it. Runs: 1 full (green), 1 docs (renumbering), then reuse on `main`.

**Not proven here (only the owner's PC can):** Task Manager while the real app window runs; a later cloud/behaviour
verdict of Defender or another virus scanner; the NVIDIA driver profile (keyed by program name – `blender.exe`'s
profile no longer applies to `Fresing Render.exe`; probably no difference for CUDA/OptiX renders).

**Open points:** code comments say "task 0177" (renumbered, see the header). No PC-check line (the PC check runs
from `blender.exe`; a line would only read a file the Windows job already checks). Task Manager's name for the PC
check / self-test stays "Blender" (they need a console).
