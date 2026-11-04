# Tooltips still to do

Snapshot of `tools/tooltip_report.py` on `main` at `e8365b8` (task 0021, 4 Nov 2026): 203 buttons and settings in the side panel, **83 without a tooltip**, **31 weak**, 89 fine.

Each lane does its own panels (TASKS.md) and writes the tooltips by the style guide at the top of
`docs/USER-GUIDE.md`. The suggestions below follow it and were checked against the code; use them,
or better ones. Where the same operator sits on several buttons, give it a
`description(cls, context, properties)` classmethod with one text per button.

See the live state (also after your changes) with
`~/venv/bin/python tools/tooltip_report.py` (`--all` lists the good ones too). Tick off a row by
deleting it when your change is merged; the file goes when it is empty.

Not in the list: the choices inside drop-down lists (each item's own description) – most already
have one; check yours when you touch a setting.

## Looks lane (35)

### 1 Import

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Detail | – | no tooltip | How finely round faces are turned into triangles. Normal suits most renders; Fine for close-ups (slower import, more memory); Draft for a quick look | `FRSceneSettings.import_quality` ui.py:161 |
| Up axis | – | no tooltip | Which way is up in the STEP file. Z up for most files; Y up when the model comes in lying on its back | `FRSceneSettings.import_up_axis` ui.py:162 |
| Import STEP… | Import a STEP assembly (runs in the background, the app stays responsive) | same text as Update to new revision… – needs a description() per button | Reads a STEP assembly with its tree, names and colours, in the background: the app stays usable. You can also drag a .step file onto the view | `fresing.import_step` ui.py:163 |
| Update to new revision… | Import a STEP assembly (runs in the background, the app stays responsive) | same text as Import STEP… – needs a description() per button | Loads a newer STEP file of this model and keeps your work: materials, hidden parts, joints, poses, scenes. A report lists new and missing parts | `fresing.import_step (update_root=…)` ui.py:179 |
| icon X | Close the model update report | icon-only button: the tooltip is all there is | Closes this update report. The model does not change | `fresing.report_clear` ui.py:185 |

### 2 Structure

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (row of choices) | – | no tooltip | What a click in the view selects: the whole subassembly of the part you click, or only that part | `FRSceneSettings.pick_mode` ui.py:288 |
| icon DISCLOSURE_TRI_DOWN | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_RIGHT] – needs a description() per button | Opens every subassembly in the tree | `fresing.tree_open_all (open=True)` ui.py:292 |
| icon DISCLOSURE_TRI_RIGHT | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_DOWN] – needs a description() per button | Closes every subassembly in the tree; only the top level stays | `fresing.tree_open_all (open=False)` ui.py:293 |
| icon FILE_REFRESH | Rebuild the subassembly list | only 4 words | Reads the model tree again (after parts were added, removed or renamed). Open and closed subassemblies stay as they are | `fresing.tree_refresh` ui.py:294 |

### Clean-up

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Max size (mm) | Size in mm | only 3 words | Parts whose largest side is shorter than this (in mm) are picked by Select the small parts | `FRSceneSettings.small_part_mm` ui.py:338 |

### Visibility sets

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the visibility set. Double-click to rename | `FRVisSet.name` ui.py:349 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected visibility set. Which parts are hidden now does not change | `fresing.vis_remove` ui.py:370 |

### 3 Looks

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the material group. Double-click to rename; the sorting rules keep sending parts to it | `FRMaterialGroup.name` ui.py:388 |
| Show only the unsorted parts | Show only these parts (Show all brings everything back) | same text as Show only these – needs a description() per button | Shows only the parts no rule could sort (Unsorted), so you see what still needs a group. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=)` ui.py:437 |
| icon ADD | Add a new material group | icon-only button: the tooltip is all there is | Adds a new, empty material group; you type its name. Fill it with Put selected in or Find & sort parts | `fresing.group_add` ui.py:444 |
| Material | – | no tooltip | The material of every part in this group. Paints and plastics also take a Colour below. Ready-made material… sets both at once | `FRMaterialGroup.material` ui.py:453 |
| Show only these | Show only these parts (Show all brings everything back) | same text as Show only the unsorted parts – needs a description() per button | Shows only the parts of this group and hides the rest. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=…)` ui.py:460 |

### Sorting rules

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Switches this rule on or off. A rule that is off is skipped when parts are sorted | `FRRule.enabled` ui.py:397 |
| icon ADD | Add a sorting rule (checked from top to bottom; the first match wins) | same text as From active part – needs a description() per button | Adds a rule at the top of the list (so it wins), for the selected group. Set what it looks for below, then Sort parts into groups | `fresing.rule_add` ui.py:564 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected rule. Sort parts into groups then sorts the parts again without it | `fresing.rule_remove` ui.py:565 |
| icon TRIA_UP | (undocumented operator) | Blender's 'undocumented operator' | Moves the selected rule up: rules higher in the list are checked first | `fresing.rule_move (direction=UP)` ui.py:567 |
| icon TRIA_DOWN | (undocumented operator) | Blender's 'undocumented operator' | Moves the selected rule down: rules lower in the list are checked later | `fresing.rule_move (direction=DOWN)` ui.py:568 |
| (field without label) | – | no tooltip | What the rule looks at: the part name, its assembly path, CAD colour, finish, part type, CAD material and more | `FRRule.field` ui.py:574 |
| (field without label) | – | no tooltip | How the value is compared: contains, is, starts with, ends with, matches a pattern (* = any text) | `FRRule.op` ui.py:575 |
| (field without label) | – | no tooltip | The text to look for, for example RVS or 40x40. Capitals do not matter | `FRRule.value` ui.py:577 |
| Note | – | no tooltip | Your own note about this rule; not used for sorting | `FRRule.note` ui.py:580 |
| From active part | Add a sorting rule (checked from top to bottom; the first match wins) | same text as [icon ADD] – needs a description() per button | Adds a rule 'Part name contains <the clicked part's name>' for the selected group, at the top of the list. Edit it below | `fresing.rule_add (from_selection=True)` ui.py:582 |

### Paint schemes & templates

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the paint scheme. Double-click to rename | `FRScheme.name` ui.py:407 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected paint scheme. The colours on the model do not change | `fresing.scheme_remove` ui.py:603 |

### Find & sort parts

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Tick the part names to put in a group or to select | `FRFoundPart.use` ui.py:488 |
| Only inside … | – | no tooltip | Searches only inside the subassembly selected in 2 Structure | `FRSceneSettings.find_in_selected` ui.py:521 |
| Only inside a subassembly (pick it in 2) | – | no tooltip | Searches only inside the subassembly selected in 2 Structure | `FRSceneSettings.find_in_selected` ui.py:525 |
| icon CHECKBOX_HLT | Tick or untick every part name found | same text as [icon CHECKBOX_DEHLT] – needs a description() per button | Ticks every part name found | `fresing.find_tick (tick=True)` ui.py:537 |
| icon CHECKBOX_DEHLT | Tick or untick every part name found | same text as [icon CHECKBOX_HLT] – needs a description() per button | Unticks every part name found | `fresing.find_tick (tick=False)` ui.py:538 |
| Select the ticked parts in the view | Select the ticked parts in the view | repeats the label | Selects the ticked parts in the view, so you can see where they are (or hide them in 2 Structure) | `fresing.find_select` ui.py:539 |

## Scene & Render lane (25)

### 5 Scene & Render

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Background | – | no tooltip | What is behind the model: a solid colour, a 360° photo (that also lights it), sky with sun, or nothing (transparent PNG) | `FRSceneSettings.background` ui.py:637 |
| Colour | – | no tooltip | The background colour. Click to pick one | `FRSceneSettings.background_color` ui.py:639 |
| Photo | – | no tooltip | The 360° photo (.hdr or .exr) around the model; it also gives the light. The icon next to it picks one from the shared library | `FRSceneSettings.hdri_path` ui.py:642 |
| Light | – | no tooltip | Where the light comes from when the background is a colour or transparent: soft studio lamps, a 360° photo, or sky with sun | `FRSceneSettings.lighting` ui.py:645 |
| Light photo | – | no tooltip | The 360° photo (.hdr or .exr) that lights the model; it is not seen in the picture | `FRSceneSettings.light_hdri_path` ui.py:648 |
| Strength | – | no tooltip | How bright the light is: 1 is normal, 2 twice as bright | `FRSceneSettings.light_strength` ui.py:652 |
| Sun height | – | no tooltip | How high the sun stands, in degrees above the horizon. A low sun gives long shadows | `FRSceneSettings.sun_elevation` ui.py:654 |
| Exposure | – | no tooltip | Makes the whole picture lighter (+) or darker (−), like a camera. 0 is normal; +1 is twice as light | `FRSceneSettings.exposure` ui.py:655 |
| Floor | – | no tooltip | What the model stands on: nothing, an invisible floor that only shows shadows, or a visible floor | `FRSceneSettings.floor` ui.py:657 |
| Own colour | – | no tooltip | Gives the visible floor its own colour instead of the background colour | `FRSceneSettings.floor_use_own_color` ui.py:659 |
| Floor colour | – | no tooltip | The colour of the visible floor. Click to pick one | `FRSceneSettings.floor_color` ui.py:661 |
| Gap | – | no tooltip | Moves the floor this far below the lowest part of the model (0 = touching) | `FRSceneSettings.floor_offset` ui.py:663 |
| icon X | (undocumented operator) | Blender's 'undocumented operator' | Deletes this camera from the project. Add camera makes a new one | `fresing.camera_remove (name=…)` ui.py:676 |

### Image size & render

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Format | – | no tooltip | The shape of the picture: screen formats (16:9, 4:3, square…) or print formats (A4, A3…) at their real size | `FRSceneSettings.out_format` ui.py:710 |
| Size | – | no tooltip | How many pixels: HD (1920 × 1080) for screens and slides, 4K for big screens or cropping, Preview for quick checks | `FRSceneSettings.out_resolution` ui.py:713 |
| Orientation | – | no tooltip | Landscape or portrait. Default uses the format's usual way | `FRSceneSettings.out_orientation` ui.py:714 |
| Resolution | – | no tooltip | Print resolution: 300 dpi for print shops, 150 dpi for office printers and smaller files | `FRSceneSettings.out_dpi` ui.py:716 |
| Orientation | – | no tooltip | Landscape or portrait. Default uses the format's usual way | `FRSceneSettings.out_orientation` ui.py:717 |
| Bleed (mm) | – | no tooltip | Extra picture around the page for the print shop to cut off (usually 3 mm) | `FRSceneSettings.out_bleed_mm` ui.py:720 |
| Width | – | no tooltip | Width of the picture in pixels (Custom size) | `FRSceneSettings.out_custom_w` ui.py:722 |
| Height | – | no tooltip | Height of the picture in pixels (Custom size) | `FRSceneSettings.out_custom_h` ui.py:723 |
| Quality | – | no tooltip | How clean the picture is: Draft (quick check, half size), Preview, Final (clean) or Best (very clean, slow). Cleaner takes longer | `FRSceneSettings.quality` ui.py:726 |
| Open | Open this render | repeats the label | Opens the rendered picture in your picture viewer | `fresing.open_file (path=…)` ui.py:738 |
| File | – | no tooltip | PNG: sharp, can be transparent. JPEG: much smaller files, no transparency | `FRSceneSettings.out_file_type` ui.py:744 |
| Graphics card | – | no tooltip | Renders on the graphics card when the PC has a suitable one. Off: renders on the processor | `FRSceneSettings.use_gpu` ui.py:746 |

## Motion lane (54)

### 4 Motion

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the joint, used in animation steps. Double-click to rename | `FRJoint.name` ui_motion.py:23 |
| Add rotate joint | Click a hole, shaft or face on the model to set the joint axis | same text as Add slide joint, [icon EYEDROPPER] – needs a description() per button | Adds a joint that turns the selected subassembly. Then click its pivot on the model: a hole or shaft, or a flat face. Esc cancels | `fresing.joint_pick_axis (mode=NEW, kind=ROTATE)` ui_motion.py:73 |
| Add slide joint | Click a hole, shaft or face on the model to set the joint axis | same text as Add rotate joint, [icon EYEDROPPER] – needs a description() per button | Adds a joint that slides the selected subassembly. Then click a hole, shaft or flat face that points the way it slides. Esc cancels | `fresing.joint_pick_axis (mode=NEW, kind=SLIDE)` ui_motion.py:75 |
| Show joint arrows in the view | – | no tooltip | Shows or hides the joints' arrows in the view. They never show in renders | `FRSceneSettings.show_joints` ui_motion.py:92 |
| (field without label) | – | no tooltip | Lowest angle this joint can turn to, in degrees (CAD position = 0°) | `FRJoint.rot_min` ui_motion.py:115 |
| (field without label) | – | no tooltip | Highest angle this joint can turn to, in degrees (CAD position = 0°) | `FRJoint.rot_max` ui_motion.py:116 |
| (field without label) | – | no tooltip | Shortest position this joint can slide to, in mm (CAD position = 0) | `FRJoint.slide_min` ui_motion.py:118 |
| (field without label) | – | no tooltip | Furthest position this joint can slide to, in mm (CAD position = 0) | `FRJoint.slide_max` ui_motion.py:119 |
| Add | Add the selected subassemblies to the joint, or take them out | same text as Remove, Select – needs a description() per button | Adds the selected parts or subassemblies to what this joint moves | `fresing.joint_members (action=ADD)` ui_motion.py:127 |
| Remove | Add the selected subassemblies to the joint, or take them out | same text as Add, Select – needs a description() per button | Takes the selected parts or subassemblies out of what this joint moves | `fresing.joint_members (action=REMOVE)` ui_motion.py:128 |
| Select | Add the selected subassemblies to the joint, or take them out | same text as Add, Remove – needs a description() per button | Selects everything this joint moves, so you can see it in the view | `fresing.joint_members (action=SELECT)` ui_motion.py:129 |
| icon EYEDROPPER | Click a hole, shaft or face on the model to set the joint axis | same text as Add rotate joint, Add slide joint – needs a description() per button | Gives this joint a new axis: click a hole or shaft (axis through its centre) or a flat face (axis at right angles to it) | `fresing.joint_pick_axis (mode=EDIT)` ui_motion.py:133 |

### Poses & exploded views

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the pose, used in saved scenes and animations. Double-click to rename | `FRPose.name` ui_motion.py:150 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected pose. The model does not move | `fresing.pose_remove` ui_motion.py:169 |
| Pieces | – | no tooltip | What moves apart: the subassemblies directly inside the selected one, or every single part | `FRSceneSettings.explode_level` ui_motion.py:180 |
| Direction | – | no tooltip | Which way the pieces move: outwards from the centre, along X, along Y, or up and down | `FRSceneSettings.explode_direction` ui_motion.py:181 |

### Saved scenes

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the scene, used in the queue and as an animation's start. Double-click to rename | `FRShot.name` ui_motion.py:197 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected saved scene. The model and the cameras do not change | `fresing.shot_remove` ui_motion.py:226 |
| Camera | – | no tooltip | The camera this scene renders from | `FRShot.camera` ui_motion.py:236 |
| Queue this | Add a render to the queue | same text as All scenes, Current view, Queue all, Render animation, Time test (2 frames) – needs a description() per button | Adds a picture of the selected scene to 7 Render queue. Start queue there renders it in the background | `fresing.queue_add (kind=SHOT)` ui_motion.py:242 |
| Queue all | Add a render to the queue | same text as All scenes, Current view, Queue this, Render animation, Time test (2 frames) – needs a description() per button | Adds a picture of every saved scene to 7 Render queue. Start queue there renders them in the background | `fresing.queue_add (kind=ALL_SHOTS)` ui_motion.py:244 |

### 6 Animation

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
|  (in each list row) | – | no tooltip | Name of the animation, shown in the queue. Double-click to rename | `FRAnimation.name` ui_motion.py:259 |
|  (in each list row) | – | no tooltip | Switches this step on or off. A step that is off is left out of Build & play and the video | `FRAnimBlock.enabled` ui_motion.py:268 |
| icon ADD | New animation | repeats the label | Adds a new, empty animation. Then add its steps below | `fresing.anim_add` ui_motion.py:308 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected animation and its steps. Joints, poses and scenes stay | `fresing.anim_remove` ui_motion.py:309 |
| Frame rate | – | no tooltip | Pictures per second: 25 is usual in Europe, 30 in the US. 50 or 60 moves more smoothly but has twice as many frames to render | `FRAnimation.fps` ui_motion.py:315 |
| Hold at end (s) | – | no tooltip | How many seconds the last picture stays at the end of the video | `FRAnimation.tail` ui_motion.py:316 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected step from this animation | `fresing.block_remove` ui_motion.py:325 |
| icon TRIA_UP | (undocumented operator) | Blender's 'undocumented operator' | Moves the selected step up the list. When it plays is set by its Start time | `fresing.block_move (direction=UP)` ui_motion.py:327 |
| icon TRIA_DOWN | (undocumented operator) | Blender's 'undocumented operator' | Moves the selected step down the list. When it plays is set by its Start time | `fresing.block_move (direction=DOWN)` ui_motion.py:328 |
| Joint | – | no tooltip | The joint this step moves (made in 4 Motion) | `FRAnimBlock.joint` ui_motion.py:337 |
| From | – | no tooltip | The angle the joint starts at, in degrees (0 = CAD position) | `FRAnimBlock.from_angle` ui_motion.py:343 |
| To | – | no tooltip | The angle the joint moves to, in degrees (0 = CAD position) | `FRAnimBlock.to_angle` ui_motion.py:346 |
| From | – | no tooltip | The position the joint starts at, in mm (0 = CAD position) | `FRAnimBlock.from_dist` ui_motion.py:349 |
| To | – | no tooltip | The position the joint moves to, in mm (0 = CAD position) | `FRAnimBlock.to_dist` ui_motion.py:352 |
| Pose | – | no tooltip | The saved pose everything moves to (made in 4 Motion) | `FRAnimBlock.pose` ui_motion.py:358 |
| (row of choices) | – | no tooltip | Cut to: switch to a camera at once. Move to: fly smoothly to a camera. Orbit: turn around the model | `FRAnimBlock.camera_mode` ui_motion.py:360 |
| Turn | – | no tooltip | How far the camera turns around the model, in degrees (360 = once round) | `FRAnimBlock.orbit_angle` ui_motion.py:363 |
| To camera | – | no tooltip | The camera to cut or fly to (cameras are made in 5 Scene & Render) | `FRAnimBlock.camera` ui_motion.py:365 |
| Start (s) | – | no tooltip | When this step starts, in seconds from the beginning of the video | `FRAnimBlock.start` ui_motion.py:371 |
| Duration (s) | – | no tooltip | How long this step takes, in seconds | `FRAnimBlock.duration` ui_motion.py:373 |
| Motion | – | no tooltip | How the motion starts and stops: Smooth (slow start and stop), constant speed, slow start or slow stop | `FRAnimBlock.easing` ui_motion.py:374 |
| Size | – | no tooltip | Size of the video in pixels: HD for screens and presentations, Small for quick checks, 4K for big screens | `FRAnimation.out_resolution` ui_motion.py:391 |
| Shape | – | no tooltip | Shape of the video: 16:9 for screens, 1:1 for posts, 9:16 upright for phones | `FRAnimation.out_format` ui_motion.py:392 |
| File | – | no tooltip | MP4: a video file (the single frames are kept too). PNG frames only: numbered pictures, transparency kept | `FRAnimation.video` ui_motion.py:393 |
| Quality | – | no tooltip | Fast preview (EEVEE) checks the motion in minutes. Draft to Best: real light, cleaner but slower. Try Time test first | `FRAnimation.quality` ui_motion.py:394 |
| Time test (2 frames) | Add a render to the queue | same text as All scenes, Current view, Queue all, Queue this, Render animation – needs a description() per button | Renders 2 frames of this animation in the queue, then shows how long the whole video will take with these settings | `fresing.queue_add (kind=TEST, name=…, start=True)` ui_motion.py:405 |
| Render animation | Add a render to the queue | same text as All scenes, Current view, Queue all, Queue this, Time test (2 frames) – needs a description() per button | Renders this animation in the background and starts the queue (7 Render queue). Keep working, or close the app: it keeps going | `fresing.queue_add (kind=ANIMATION, name=…, start=True)` ui_motion.py:407 |

### 7 Render queue

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Current view | Add a render to the queue | same text as All scenes, Queue all, Queue this, Render animation, Time test (2 frames) – needs a description() per button | Adds a picture of the model as it is now, from the active camera, to the queue | `fresing.queue_add (kind=STILL)` ui_motion.py:471 |
| All scenes | Add a render to the queue | same text as Current view, Queue all, Queue this, Render animation, Time test (2 frames) – needs a description() per button | Adds a picture of every saved scene to 7 Render queue. Start queue there renders them in the background | `fresing.queue_add (kind=ALL_SHOTS)` ui_motion.py:473 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Takes the selected job out of the queue. Files it already rendered stay | `fresing.queue_remove` ui_motion.py:479 |
| icon BRUSH_DATA | (undocumented operator) | Blender's 'undocumented operator' | Takes all finished jobs out of the list. Their files stay | `fresing.queue_remove (finished=True)` ui_motion.py:480 |
| Stop after this frame | Stop after the current frame or image (start again later to continue an animation) | same text as Stop now – needs a description() per button | Stops when the current frame or picture is done. Start queue continues an animation where it stopped | `fresing.queue_stop` ui_motion.py:498 |
| Stop now | Stop after the current frame or image (start again later to continue an animation) | same text as Stop after this frame – needs a description() per button | Stops the render at once; the frame being rendered is lost. Start queue continues an animation where it stopped | `fresing.queue_stop (now=True)` ui_motion.py:501 |
