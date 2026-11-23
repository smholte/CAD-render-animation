# 0294 – Workspaces round 2: Essentials as the start, task workspaces (Sales, Quick render, Animator, Reviewer), favourites on top

**Who:** worker · **Status:** open – can start after 0282 is merged (0276 follows this) · **Branch:**
`task/0294-workspaces-round-2`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "More Workspaces for the functions. And some very
specified simple workspaces, where a user has to only do very specific task, like a sales person." – "Favorite
workspace on top of the list when you click on the drop down menu to select your workspace." – "On startup if a user
hasn't set their own chosen workspace, there should be one essentials workspace where users first come in to."; owner's
click box 23 Nov: all four task workspaces – Sales, Quick render, Animator, Reviewer) · **Model:** Opus · effort Medium
**Area:** Start & learn lane – `core/workspaces.py` (`BUILTIN`), `blender/workspaces.py`, `blender/ops_workspace.py`, the
Workspace part of the left panel (`ui_left.py`), `core/functions.py` (`workspaces=`, `FAMILY_WORKSPACES`), the settings
file (0283) + Settings > General (`ui_settings.py`), guide, tour stop, PC check, CHANGELOG.
**Not:** `welcome.py` and the first-start set-up (0276 comes after this and uses it), `lock.py`'s Client view rules.

## Background

0062 made the built-in list (All functions, CNC & machining, Offshore & cable laying, Product design & R&D, Client
view, Education & training, Lifting plans, Full access) and own workspaces as files. 0062's lead decision "default
workspace All functions" is changed by the owner: new users start in **Essentials**.

## What to do

1. **Essentials** (new built-in, first in the list): only what a new user needs for a first good picture and a simple
   motion – import, sort into groups + materials, surroundings + light look, camera views, a joint + a pose, Build &
   play, render image / turntable, save. Propose the exact function list in the report (from `functions.py`) and build
   it. It is the workspace of anyone who **has not chosen one** (state how "not chosen" is known – a user who already
   works in another workspace keeps it), and the default for new projects until the user picks another (Settings >
   General: "Workspace for new projects").
2. **Task workspaces** (owner's picks): **Sales** – take a finished project and make outputs: saved scenes, looks /
   paint schemes, surroundings, render picture, turntable, product video, 3D page; the model's structure and motion
   locked (say how it differs from the Client view); **Quick render** – import a STEP, sort + looks, surroundings,
   light, one picture / turntable; **Animator** – joints, cylinders, mechanisms, poses, animation steps, cameras and
   camera paths, labels, render queue, video; **Reviewer** – look at a finished model: saved scenes, slice / cutaway,
   exploded views, labels / notes, measuring (if the app has no measuring in the 3D view, say so as an open point).
   Each with a tooltip saying what it is for.
3. **More workspaces for the functions:** propose 2–3 more from the function families in the report (do not build
   them) – the owner decides.
4. **Favourites on top:** a star on each workspace in the drop-down; starred ones (and the user's "for new projects"
   choice) at the top above a line; kept per user in the settings file.
5. Note for 0276 (first-start set-up, next in the lane): its "Your work" step maps ticks to these; no tick → Essentials
   – write that line into `tasks/0276-first-start-setup.md` under step 2.

## Done when

- [ ] Tests: Essentials / the four task workspaces show exactly their functions; a new user lands in Essentials, an
      existing user keeps his; star order kept over a restart; own workspaces still load
- [ ] Real-app test of the drop-down with a star; guide (Workspaces) + pictures; tour stop `changed=`; PC check line
      `workspace.essentials`; function entries; full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**

**Owner's check on your PC:**
