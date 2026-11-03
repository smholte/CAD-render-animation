# Changelog

What changed in each version, in plain words. Newest first. "Commit" is the Git commit the
installer of that version was built from (tags cannot be pushed from the AI chats).

## 0.2.6 – 3 Nov 2026 – faster import, self-test checks the new features

Commit `b414a73`.

- The STEP reader takes each part's triangles from OpenCascade in one block instead of one
  point at a time. EGR line on the 2-core test machine: meshing 24.0 s → 17.7 s on one core,
  17.7 s → 14.8 s with 2 helpers; the result is identical to before, to the last bit.
- Self-test: new line "Animation time test (queue)" (the Time test button, run on your PC);
  the HD render line says whether noise removal ran on the graphics card.

## 0.2.5 – 3 Nov 2026 – side panel redesigned

Commit `e85321b`.

- Every section reads top to bottom: what you choose comes before its button.
- The main button of each section is big and blue: Import STEP, Render image,
  Render animation, Start queue.
- No cut-off labels at the normal side-panel width. Lists fit their items and show names;
  the details of the selected item are right under the list.
- Rarely used settings are folded away ("More", "Files & graphics card", joint "Set-up").
- Every panel header shows an icon and its state (model, parts, unsorted parts in red,
  joints, animation length, queue progress), also when the panel is closed.
- How-to steps where a section starts empty; "Selected: …" above Add joint.
- Renamed: "Open result" → "Open", "Back to CAD position" → "Everything back to CAD position",
  Clean-up "Remove for good" → "Remove selected".

## 0.2.4 – 3 Nov 2026 – faster animation renders

Commit `08a0f08`.

- Noise removal runs on the graphics card (Blender's default was the processor).
- Animation frames use lighter light-bounce settings: 44 % less render time per frame on
  the EGR line test, no visible difference.
- "Time test" renders two frames and shows how long the whole animation will take.
- "Show in folder" for queue results and for Render image.
- The queue log shows render and save time per frame.

## 0.2.3 – 3 Nov 2026 – import on all processor cores

Commit `72dce5e`.

- Big STEP files are meshed on all cores but one, at below-normal priority.
- A part that cannot be meshed is reported and skipped; the rest of the import goes on.
- Self-test line "Fast import (all cores)"; the import panel shows how many cores were used.

## 0.2.2 – 2 Nov 2026 – first working installer

Commit `0e21353`.

- Installer fixed: every earlier installer stopped with a PowerShell error before installing.
- Live preview and Render image no longer freeze the app.
- Big models: no false "moved" parts after an import, faster poses and animations.
- Queue keeps the PC awake; renders of unsaved projects go to Pictures\Fresing Render.

## 0.2.1 – 2 Nov 2026

- The Desktop shortcut opens the app with the Fresing panel (it was missing).
- Side panel opens on the Fresing tab; the view is framed on the model after import.

## 0.2.0 – 2 Nov 2026 – phase 2: motion

- Joints (rotate, slide, chains, limits; axis by clicking a hole or shaft), poses,
  exploded views, visibility sets, saved scenes.
- Animations from steps (joint moves, poses, camera moves, show/hide), Build & play.
- Render queue in a background Blender (images and MP4), keeps going when the app closes.
- Update to a new STEP revision keeps all work; "in use by" lock for shared projects.

## 0.1.0 – 2 Nov 2026 – phase 1: stills

- STEP import with assembly tree, names and CAD colours; fasteners recognised by name and
  sorted into material groups; RAL colours; paint schemes and templates.
- Backgrounds (colour, 360° photo, sky, transparent), studio light, floor, cameras, sizes
  from 16:9 to A3 at 300 dpi; GPU rendering; Windows installer; self-test.
