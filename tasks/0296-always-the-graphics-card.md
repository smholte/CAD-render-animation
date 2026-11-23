# 0296 – Always the graphics card: NVIDIA, AMD or Intel Arc before built-in graphics; a calm notice with a guide when not

**Who:** worker · **Status:** done (0.2.217) · **Branch:** `task/0296-always-the-graphics-card`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: someone tested the app on a Windows 11 PC with an AMD
graphics card and the app used the processor's built-in graphics; on a second PC of the owner's (Intel Core i7-12700,
NVIDIA RTX A2000) and on his own (Ryzen 9 9900X, RTX 3090) it chose the card. "Fresing Render should rather always
choose the GPU, if NVIDIA, AMD or Intel GPU, instead of integrated graphics. And if the app recognizes low performance
or that the app is on integrated graphics, ask the user to check and give a guide on how (this should not be spam).")
· **Model:** Opus · effort High
**Area:** `blender/render.py` (`setup_gpu`), a new `core/gpu_choice.py` (the rules, no Blender – tested with made-up
adapter lists) + `blender/gpu_choice.py` (the notice, the Settings line), a Windows-only reader of the graphics adapters
(DXGI through ctypes, new file), the installer / Update now / the app's start (the per-user GPU preference, like 0265's
Installed apps entry), `selftest.py` and the PC check (one line each), the guide, `docs/COMPANY-USE.md` only if
something changes there (it should not: nothing goes on the network).
**Not:** render quality settings, the PC check's other lines.

## Background – two separate choices

1. **Which GPU draws the app's window** (viewport, EEVEE, Live preview): Windows decides per program (Settings > System
   > Display > Graphics). On a PC with built-in graphics plus a card, an unknown program may get "power saving" =
   built-in. A program can ask for the fast GPU with the exports `NvOptimusEnablement` / `AmdPowerXpressRequest
   HighPerformance` in **its own exe** (check whether Blender 5.2.3's exe has them, and which exe really starts the
   app – `winexe.py` / `appicon.py`: "Fresing Render.exe"), or the user / installer can set the per-user value under
   `HKCU\Software\Microsoft\DirectX\UserGpuPreferences` (name = the full exe path, data `GpuPreference=2;`) – **check
   both against Microsoft's and the vendors' own documentation**, not from memory.
2. **Which device Cycles renders on:** `setup_gpu` takes the first backend of OPTIX, CUDA, HIP, ONEAPI, METAL that has a
   device and then uses **every** device of it – an AMD processor's built-in Radeon and an AMD card are both HIP (the
   built-in one slows the card down); a card HIP does not support (old driver) leaves ONEAPI = an Intel built-in GPU.

**The tester's PC** (owner 23 Nov 20:12): AMD Ryzen 7 7700X (it has small built-in Radeon graphics) + Gigabyte Radeon
RX 6700 XT EAGLE, Windows 11. Both are AMD, so both can show up as HIP devices for Cycles, and Windows may draw the
window on the built-in one. Also check (and put in the guide): **a monitor cable plugged into the motherboard's video
port** makes Windows draw everything on the built-in graphics – the cable belongs in the graphics card.

## What to do

1. **Prefer a dedicated GPU, always** – NVIDIA, AMD or Intel Arc over built-in graphics – for both choices: Cycles uses
   only dedicated devices when one exists (tell them apart by the adapter list: dedicated video memory, names); the
   window: the per-user preference for the app's exe written by the installer, Update now and the app's start (removed
   by the uninstaller), and checked at start: `gpu.platform.renderer_get()` / `vendor_get()` against the adapter list.
2. **A calm notice** when the window is drawn by built-in graphics while a dedicated card exists, or when the PC is
   clearly slow (the Quick PC check's result, or a measured view frame time over a few seconds): one small window –
   "Fresing Render is running on your processor's built-in graphics. Your PC has a faster graphics card: <name>."
   **Use the graphics card** (writes the preference, asks to restart) · **Show me how** (steps for Windows' Graphics
   settings, NVIDIA Control Panel, AMD Software) · **Not now** · **Don't ask again**. At most once per start, never
   again after "Don't ask again" unless the set of GPUs changes; never in background runs, tests or the PC check.
3. **Settings > General**: a "Graphics" line – which GPU draws, which renders; a list to pick the render device.
4. **Self-test and PC check:** a line "graphics card used" (skipped without a card – `FRESING_SELFTEST_NO_GPU`); the PC
   check report names the GPU that draws and the one that renders.
5. **Owner's test steps** in the report, for the tester's PC: install / Update now, start, see no notice (or press Use
   the graphics card), Help > PC check (Quick), read the graphics line.

6. **Live preview black after sleep** (owner 23 Nov 20:32, lead's reading – not proven): on his RTX 3090 PC the app
   stayed open overnight while Windows slept (`Win32 Error# (0)` in the console at that time); next evening Live
   preview showed only black with "Rendering Done", while Solid view and **Render image** were fine. Changing the
   Light look, Background or sea detail and switching Live preview off and on did not help; restarting the app did.
   Most likely the driver's link between Cycles' viewport and the window was lost on resume. Find out (Blender's
   own bug reports, a test on Windows if the session has one – otherwise reason and say so) whether the app can
   give Live preview a fresh start after a resume without a restart; if yes, do it where it is small and safe, if
   not, say so in the report. The guide line under Troubleshooting > Render problems is already on `main` (lead).

## Done when

- [x] Pure-Python tests of the rules with made-up adapter lists: Intel built-in + NVIDIA, AMD built-in + AMD card, Intel
      built-in + Intel Arc, AMD APU only, a laptop with Optimus, no GPU at all, a GPU change between starts
- [x] The Windows code reviewed by an independent helper that did not write it (CLAUDE.md 6); installer files plain
      ASCII; GitHub's Windows install green (no GPU there: the notice never shows, the lines say "skipped")
- [x] Guide section "Graphics card", function entry, PC check line `pc.gpu`, self-test line; report; merged, version,
      release

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 23 Nov 2026. Released as 0.2.217.

**What changed:**
- **Measured first:** Blender 5.2.3's `blender.exe` (Windows zip, read on Linux with `pefile`) exports
  `NvOptimusEnablement = 1` (GHOST, since 2013) but **no** `AmdPowerXpressRequestHighPerformance` – the AMD driver is
  never asked for the card, which fits the tester's AMD PC (NVIDIA PCs chose the card). `Fresing Render.exe` is a
  byte copy, so it has the same export. Blender 5.2 draws with OpenGL by default (Vulkan only from 5.3, from source).
- **Cycles (`render.setup_gpu`)** now reads every backend's devices once per start and follows
  `core/gpu_choice.render_plan`: only graphics cards when there is one (HIP lists a Ryzen's built-in Radeon next to
  the card and Cycles ticks both – checked in Cycles' source), else what there is (as before). The text says what was
  left out: "GPU (HIP): AMD Radeon RX 6700 XT (built-in AMD Radeon Graphics left out)".
- **The window:** `HKCU\Software\Microsoft\DirectX\UserGpuPreferences`, value = the program's full path,
  `GpuPreference=2;` for `blender.exe` and `Fresing Render.exe` – written by the installer (step 4b), Update now
  (`update_helper.set_gpu_preference`, only an Install.bat folder) and the app's start (`wingpu.ensure`, once per
  program); removed by the uninstaller (values under the install folder). Only where the user has not chosen; other
  keys in the value (`SwapEffectUpgradeEnable=1;`) kept. **Not documented by Microsoft**: the format is from
  Microsoft's own tools on GitHub (HOBL, Accera) and 3D Slicer's installer (OpenGL, tested there on an NVIDIA laptop).
  No primary source says AMD's OpenGL driver on a desktop with Ryzen iGPU + Radeon honours it – hence the notice and
  the guide's monitor-cable step.
- `wingpu.py` (new): DXGI adapters through ctypes (name, vendor, own memory, software flag, monitors plugged in,
  Windows' high-performance order). `core/gpu_choice.py` (new, no Blender): card / built-in / software from the names
  (Intel Arc A/B vs. Core Ultra's "Arc Graphics", Radeon RX/Pro vs. "Radeon(TM) Graphics", 780M, Vega 11 …), memory as
  fallback; the window state; the preference text; the notice's rules; the steps of Show me how.
- `blender/gpu_choice.py` (new): the start check (timer, persistent), the record in `<config>/fresing_gpu.json` (the
  background self-test / PC check read what the last start saw), the notice (Use the graphics card · Show me how ·
  Cancel = not now · Don't ask again; once per start; never with the welcome / What's new, in the background, tests
  or the PC check; asks again when the set of GPUs changes), a slow-view sampler (3 frames in a row over 2 s),
  Settings > General > **Graphics** (draws / renders / Windows' preference / **Render on** list / Look for devices).
- Self-test line "Graphics card used", PC check line `pc.gpu` (Quick + Full), the report's header names "renders on"
  and "window drawn by". Guide section "Graphics card" (Troubleshooting), function `settings.graphics`.
- **Item 6, Live preview black after sleep:** not fixed in code. Blender's tracker has only near cases (T65207, #58774:
  "only a restart helps", left as driver issues); in 5.2's Cycles source the viewport session is made new only when
  the view leaves Rendered shading – which the owner already tried without help. No safe restart-free fix found; the
  guide's line under Render problems (restart) stays. No Windows machine with a GPU here to try more.

**Tested and measured** (4-core web machine, no GPU): `tests/test_gpu_choice.py` (59: the seven PCs of the brief –
Intel + NVIDIA, AMD + AMD card, Intel + Arc, AMD APU only, Optimus laptop, no GPU, a GPU change –, names, the
preference text, the state file), `tests/test_gpu_choice_blender.py` (12: a made-up Cycles on the tester's PC – only
the card ticked –, the device picked in Settings, the Settings line, the check line, a made-up registry, Update now,
once-per-program). Real app `settings` 52/52 (the start check ran: "drawn by llvmpipe (software)"). PC check lines
`app.start` + `pc.gpu` in bpy: skipped "no graphics card" as expected. GitHub: Windows install checks the values after
Install.bat and that Uninstall removes them (`Check-GpuPref`).
- **Subagents:** a research agent (sources for the registry value, the exports, Blender's backend and Cycles' HIP /
  oneAPI device lists, sleep bug reports – only GitHub was reachable, vendor pages from search snippets); an
  **independent reviewer** of the Windows code (no crash path found; four behaviour points fixed: a later "Let Windows
  decide" now kept, Update now only for the app's own install, one bad adapter no longer empties the list, the start
  check survives an early project load). Not fixed (Windows never writes such text): PowerShell and Python differ on
  malformed values (duplicate keys, lower case).
- GitHub runs: see below.

**Open points / follow-up tasks:**
- Whether Windows' preference moves an **OpenGL** window on an AMD desktop (iGPU + card) is not proven anywhere – only
  the tester's PC can say. If it does not: the monitor cable, or switching off the iGPU in the BIOS, or adding the AMD
  export to `Fresing Render.exe` (a PE export-table edit in `winexe.py`; AMD documents it for switchable laptops only).
- A re-install (Install.bat) sets High performance again even if the user chose "Let Windows decide" afterwards.
- No tour stop (the notice is suppressed in tests; Settings' stop shows the page).

**Owner's check on your PC (and the tester's):**
1. Update now (or Install.bat) to 0.2.217, start Fresing Render.
2. Tester's PC (Ryzen 7700X + RX 6700 XT): close and start the app **once more** (Windows' setting counts from the
   next start). Expected: no notice. If the notice "running on your processor's built-in graphics" shows: press
   **Use the graphics card**, start again; still there: **Show me how** – first check the monitor cable is in the
   graphics card (the lower ports on the back), not the motherboard.
3. **Fresing > Settings > General > Graphics:** "Draws the window: AMD Radeon RX 6700 XT (graphics card)". Press
   **Look for devices**: "Renders (Cycles): graphics card (HIP): AMD Radeon RX 6700 XT (built-in … left out)".
4. Help > PC check (Quick): the line "Graphics card used" is OK; the report's top says "renders on …" and "window
   drawn by …". Send the text block.
5. Your RTX 3090 PC: the same lines should name the RTX 3090 (OptiX); no notice.
