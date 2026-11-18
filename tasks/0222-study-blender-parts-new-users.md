# 0222 – Study (findings only): which parts of Blender's own interface a Fresing Render user does not need

**Who:** worker · **Status:** open – can start (study, no code – no lane) · **Branch:** `task/0222-study-blender-parts`
**Started by:** lead, 19 Nov 2026 (owner, 00:05: "I want the app as simple as possible, with the needed functions,
and my guess is that most users are not familiar with Blender … but the option to open it easily will be good")
· **Model:** Opus · effort Medium
**Area:** this file only (+ pictures under `tasks/img/0222/`, made from the invented demo / test models only)

## Goal

A list the owner can pick from in a few minutes: every part of Blender's own interface that a user of Fresing Render
still sees, and for each whether the app needs it, and what to do – **keep**, **hide** (with an easy way back, as
0221 does for the Outliner / Properties column), **replace** by a Fresing button, or **leave for now**. The owner's aim:
as simple as possible with the needed functions, for users who do not know Blender; Blender's tools stay reachable for
those who do.

## What to look at (0.2.168 + 0221's plan; the window as a new user meets it)

- The **splash**: Blender's "New File" list (General, 2D Animation, Sculpting, Storyboarding, VFX, More…), Recover
  Last Session, What's New (Blender's), Donate to Blender – next to the Fresing welcome.
- The **top bar**: File, Edit, Render, Window, Help – which items the app uses, which are Blender-only (e.g. Render >
  Render Image vs the app's Render queue, Edit > Preferences), Blender's workspace tabs if any show.
- The **3D view header**: Object Mode menu, View / Select / Add / Object menus, transform orientation, pivot, snapping,
  proportional editing, the overlay / gizmo / X-ray / shading buttons, Options.
- The **side panel's** Blender tabs (Tool, View, Animation) next to Fresing; the navigation gizmo.
- The **timeline** and the **status bar**; right-click menus in the 3D view; keys a new user hits by accident (Tab,
  G / R / S, X / Delete, Ctrl+Space…) – which the Client view already swallows (`lock.py`) and whether some should
  be off in Full access too.
- What the existing **workspaces** (0062) and the **Client view** already hide, so the study does not repeat them.

## For each row

What it is · what the app needs it for (with the function / guide anchor if any) · proposal (keep / hide with a way
back / replace / later) · how the way back would work · rough size (S / M / L) and risk (Blender updates, add-ons,
old projects, Windows) · one picture where it helps. Group the rows into 2–4 packages the lead can brief as tasks, in
the order that gives the owner the biggest "simpler" step first.

## Done when

- [ ] The table above for every part listed, plus anything else found
- [ ] 2–4 packages with model · effort and lane for each
- [ ] Questions for the owner at the end (short, one line each)
- [ ] No code changed; report merged to `main` (no release)

## Not in this task

Building anything. The Outliner / Properties column (0221). The Fresing tab's own panels (0062, 0200).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Packages proposed:**

**Questions for the owner:**
