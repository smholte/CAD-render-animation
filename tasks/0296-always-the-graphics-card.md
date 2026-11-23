# 0296 – Always the graphics card: NVIDIA, AMD or Intel Arc before built-in graphics; a calm notice with a guide when not

**Who:** worker · **Status:** open – can start · **Branch:** `task/0296-always-the-graphics-card`
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

## Done when

- [ ] Pure-Python tests of the rules with made-up adapter lists: Intel built-in + NVIDIA, AMD built-in + AMD card, Intel
      built-in + Intel Arc, AMD APU only, a laptop with Optimus, no GPU at all, a GPU change between starts
- [ ] The Windows code reviewed by an independent helper that did not write it (CLAUDE.md 6); installer files plain
      ASCII; GitHub's Windows install green (no GPU there: the notice never shows, the lines say "skipped")
- [ ] Guide section "Graphics card", function entry, PC check line `pc.gpu`, self-test line; report; merged, version,
      release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC (and the tester's):**
