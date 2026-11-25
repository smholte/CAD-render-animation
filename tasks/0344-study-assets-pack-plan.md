# 0344 – Study (findings only): the Fresing assets pack – how every system uses it without breaking the app

**Who:** worker · **Status:** open – can start · **Branch:** `task/0344-study-assets-pack-plan` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 25 Nov 2026 20:4x (owner 20:34: "we must make a plan to how to do this and not break the app. what
additions is needed per system to not break it.") · **Model:** Opus · effort **Max** (owner: high standards – done
well, not fast)
**Area:** findings only. Reads the whole app, `installer/`, `tools/`, `.github/workflows/`, `docs/`, the briefs and
reports of 0228 (demo kits), 0272 (locations), 0273 (material picker), 0274 / 0318 / 0314 (finishes, looks), 0286
(asset libraries), 0340 (paint import), **0343** (report on branch `task/0343-study-paid-company-use`). A small proof
in **new files only** on the branch is allowed (e.g. `tools/assets_pack_proto/`); changes no existing file. Not a code
slot.

## Goal

A plan the owner and the lead can build from, task by task, so that **Fresing's own assets** (materials and node
groups, textures, HDRIs and 360° photos, environments, props, people, showcase and learning models, learning projects)
are **rebuilt as files Fresing owns** and used by every part of the app – **without breaking anything**: not the app
without a pack, not old projects, not the tests, not speed.

## Background – the owner's picks on 0343 (25 Nov 20:34)

1 **rebuild all** Fresing assets as new files Fresing owns, step by step · 2 **in the installer for everyone**, one
question at the first start (Private · Education · Non-profit · Company), a company sees the price and a Buy link once,
nothing locked · 3 one-time per user, updates of pack 1.x · 4 €129 / €59 freelancer (**prices may change; no selling
until the app is much further – the owner has high standards**) · 5 non-profits free for own unsold work · 6 Paddle ·
7 invoice + licence file, About "Licensed to …", **plus a nudge line** in About and the export window when the user
said "Company" and no licence file is found · 8 Benelux trademark before the first sale · 9 Blender support: later ·
10 e-mail, answer in 5 working days · 11 the plain licence draft · 12 **workers (AI) build the assets; the owner sets
the look, picks, adjusts and approves every set on pick pages and adds his own photos** – keep a short record per set of
his choices (ownership).

Ground rules from 0343 (check them, don't re-research): the code stays GPL-3.0-or-later; the pack is its own folder with
its own licence, never inside code files; **the app must run without the pack** (GPL condition and safety); no lock, no
online check (the app is fully offline); today's code looks are GPL for ever in 232 versions – they stay as the free
fallback.

**Changed while running (owner 25 Nov 21:35 – test minutes):** **no tests in the private repository** (the owner's
GitHub Free minutes are shared and limited; public repositories run tests for free). Only the **working files** stay
private (source `.blend` scenes, full-size textures, the owner's raw photos, sets not yet approved, the per-set records of
his choices) – that repository has **no CI**. The **finished pack** is public: a download attached to a GitHub release
(not Git LFS – LFS downloads, also by CI and forks, count against the owner's 10 GB a month), under the **Fresing Assets
Licence** with the licence file inside the pack. **All pack tests run in the public repository** – with and without
the pack – against that release download, cached between runs. Compare this with a private-CI plan in one short table
and recommend one.

## Questions to answer

1. **Pack format and place:** folder and zip layout, `pack.json` (id, version, the app versions it fits, asset list
   with stable ids, licence), where the installer puts it (beside the extension, not inside it), how the in-app update
   updates it apart from the app, how a company's approved-version folder and `.frsetup` (0272) carry it, uninstall,
   a broken or missing pack (the settings-file pattern of 0283: ignore, one line, never a crash). The public
   download of the finished pack as a release asset (size, how a pack version maps to a release, how the installer and
   CI fetch it); the working files stay private.
2. **One asset registry** every system asks ("material `steel.painted`", "HDRI `studio.soft`", "environment
   `quay.small`") → pack item if present, else the built-in code item with the same id; ids never change. Test in
   Blender 5.2.3: **append vs link** of pack materials / node groups / collections into a project – a saved project
   must open on a PC **without** the pack and be sendable to a client; what is stored to re-find the source (id + pack
   version) for "update looks"; file size and load time.
3. **Per system, the additions needed so it does not break** – for each: files, what changes, the fallback, the tests
   both ways, the lane, size, risk. At least: importer + paint rules (0340 / 0287), material library + picker (0273),
   finishes + adjust (0274 / 0314 / 0318), CAD colours / RAL, decals, light looks + world + weather + sea, surroundings
   + props + people, cables / hoses / chains looks, machining chips / coolant, demo kits + demo project, lifting crane
   classes, test tour + Learning hub + lessons (sets that need the pack vs not), material pictures, Web 3D export
   (baking pack textures; the page is the user's output), Fresing Viewer (MIT – exports only), PC check + Stress
   (lines with and without the pack; VRAM and render time with real textures), backups, Client view, workspaces,
   Settings ("Use Fresing assets" switch?), first-start set-up (the usage question), About + export window (licence
   lines, nudge), installer + update + uninstall, CI (all in the public repository: without the pack, with a tiny
   **test pack** made by a tool, and with the real pack from its release download, cached; **no private CI**), the
   user guide + function list.
4. **Old projects:** nothing changes in a project until the user chooses (like 0340); an "Use the new Fresing looks"
   action with before / after; models already imported keep their materials.
5. **Speed and size budget:** texture sizes per quality (Draft / Normal / Final), pack size in the installer, memory on
   the stress model (11,228 parts) and the demo; nothing slower than today without the user choosing it.
6. **Making the assets:** a pipeline per kind (node materials, textures – procedural and from the owner's photos, HDRIs
   from the Insta360, environments, models) built by workers in the private repository (no CI there); the **owner's pick page per
   set** with before / after pictures, his choices recorded (`OWNERSHIP.md` per set); quality bar = clearly better
   than today's code looks.
7. **Order of tasks** (lanes, sizes, model · effort, what waits for what) so the app is never broken in between: first
   the invisible parts (pack format, registry, fallback, test pack, CI both ways), then one asset set at a time, each
   with the owner's OK; licence texts, shop, first-start question and nudge **last, just before selling** (the owner
   decides when).

## Done when

- [ ] Report below answers 1–7 with file names and a task table (P-numbers; the lead turns them into tasks).
- [ ] The append / link proof was run in Blender 5.2.3 on the branch (say where it ran and what was measured).
- [ ] A pick page `tasks/0344_page/index.html` for the owner's choices (plain words, an explanation per choice, ★ first)
      with a diagram of the pack, the registry and the fallback.

## Not in this task

Building anything in the app; licence texts, shop, trademark; making real assets. Never the owner's STEP files or his
employer's name.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
