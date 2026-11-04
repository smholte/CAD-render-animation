# Tooltips still to do

Snapshot of `tools/tooltip_report.py` on `main` at `5936ed9` (after 0.2.9, task 0010; 5 Nov 2026): 209 buttons and settings in the side panel, **65 without a tooltip**, **28 weak**, 116 fine.

Each lane does its own panels (TASKS.md) and writes the tooltips by the style guide at the top of
`docs/USER-GUIDE.md`. The suggestions below follow it and were checked against the code; use them,
or better ones. Where the same operator sits on several buttons, give it a
`description(cls, context, properties)` classmethod with one text per button.

See the live state (also after your changes) with
`~/venv/bin/python tools/tooltip_report.py` (`--all` lists the good ones too). Tick off a row by
deleting it when your change is merged; the file goes when it is empty.

Not in the list: the choices inside drop-down lists (each item's own description) – most already
have one; check yours when you touch a setting.

## Looks lane (14)

### 1 Import

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon X | Close the model update report | icon-only button: the tooltip is all there is | Closes this update report. The model does not change | `fresing.report_clear` ui.py:185 |

### 2 Structure

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon DISCLOSURE_TRI_DOWN | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_RIGHT] | Opens every subassembly in the tree | `fresing.tree_open_all (open=True)` ui.py:292 |
| icon DISCLOSURE_TRI_RIGHT | Open or close every assembly in the list | same text as [icon DISCLOSURE_TRI_DOWN] | Closes every subassembly in the tree; only the top level stays | `fresing.tree_open_all (open=False)` ui.py:293 |

### Visibility sets

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the visibility set. Double-click to rename | `FRVisSet.name` ui.py:349 |

### 3 Looks

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Show only the unsorted parts | Show only these parts (Show all brings everything back) | same text as Show only these | Shows only the parts no rule could sort (Unsorted), so you see what still needs a group. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=)` ui.py:440 |
| Show only these | Show only these parts (Show all brings everything back) | same text as Show only the unsorted parts | Shows only the parts of this group and hides the rest. Show all (2 Structure) brings everything back | `fresing.show_only_group (group=…)` ui.py:465 |

### Sorting rules

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon ADD | Add a sorting rule (checked from top to bottom; the first match wins) | same text as From active part | Adds a rule at the top of the list (so it wins), for the selected group. Set what it looks for below, then Sort parts into groups | `fresing.rule_add` ui.py:639 |
| icon TRIA_UP | Move the selected rule up or down. Rules are checked from the top: the first rule that fits a part decides its group | same text as [icon TRIA_DOWN] | Moves the selected rule up: rules higher in the list are checked first | `fresing.rule_move (direction=UP)` ui.py:642 |
| icon TRIA_DOWN | Move the selected rule up or down. Rules are checked from the top: the first rule that fits a part decides its group | same text as [icon TRIA_UP] | Moves the selected rule down: rules lower in the list are checked later | `fresing.rule_move (direction=DOWN)` ui.py:643 |
| From active part | Add a sorting rule (checked from top to bottom; the first match wins) | same text as [icon ADD] | Adds a rule 'Part name contains <the clicked part's name>' for the selected group, at the top of the list. Edit it below | `fresing.rule_add (from_selection=True)` ui.py:657 |

### Paint schemes & templates

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the paint scheme. Double-click to rename | `FRScheme.name` ui.py:410 |

### Find & sort parts

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| icon CHECKBOX_HLT | Tick or untick every part name found | same text as [icon CHECKBOX_DEHLT] | Ticks every part name found | `fresing.find_tick (tick=True)` ui.py:612 |
| icon CHECKBOX_DEHLT | Tick or untick every part name found | same text as [icon CHECKBOX_HLT] | Unticks every part name found | `fresing.find_tick (tick=False)` ui.py:613 |
| Select the ticked parts in the view | Select the ticked parts in the view | repeats the label | Selects the ticked parts in the view, so you can see where they are (or hide them in 2 Structure) | `fresing.find_select` ui.py:614 |

## Scene & Render lane (25)

### 5 Scene & Render

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Background | – | no tooltip | What is behind the model: a solid colour, a 360° photo (that also lights it), sky with sun, or nothing (transparent PNG) | `FRSceneSettings.background` ui.py:712 |
| Colour | – | no tooltip | The background colour. Click to pick one | `FRSceneSettings.background_color` ui.py:714 |
| Photo | – | no tooltip | The 360° photo (.hdr or .exr) around the model; it also gives the light. The icon next to it picks one from the shared library | `FRSceneSettings.hdri_path` ui.py:717 |
| Light | – | no tooltip | Where the light comes from when the background is a colour or transparent: soft studio lamps, a 360° photo, or sky with sun | `FRSceneSettings.lighting` ui.py:720 |
| Light photo | – | no tooltip | The 360° photo (.hdr or .exr) that lights the model; it is not seen in the picture | `FRSceneSettings.light_hdri_path` ui.py:723 |
| Strength | – | no tooltip | How bright the light is: 1 is normal, 2 twice as bright | `FRSceneSettings.light_strength` ui.py:727 |
| Sun height | – | no tooltip | How high the sun stands, in degrees above the horizon. A low sun gives long shadows | `FRSceneSettings.sun_elevation` ui.py:729 |
| Exposure | – | no tooltip | Makes the whole picture lighter (+) or darker (−), like a camera. 0 is normal; +1 is twice as light | `FRSceneSettings.exposure` ui.py:730 |
| Floor | – | no tooltip | What the model stands on: nothing, an invisible floor that only shows shadows, or a visible floor | `FRSceneSettings.floor` ui.py:732 |
| Own colour | – | no tooltip | Gives the visible floor its own colour instead of the background colour | `FRSceneSettings.floor_use_own_color` ui.py:734 |
| Floor colour | – | no tooltip | The colour of the visible floor. Click to pick one | `FRSceneSettings.floor_color` ui.py:736 |
| Gap | – | no tooltip | Moves the floor this far below the lowest part of the model (0 = touching) | `FRSceneSettings.floor_offset` ui.py:738 |
| icon X | (undocumented operator) | Blender's 'undocumented operator' | Deletes this camera from the project. Add camera makes a new one | `fresing.camera_remove (name=…)` ui.py:751 |

### Image size & render

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Format | – | no tooltip | The shape of the picture: screen formats (16:9, 4:3, square…) or print formats (A4, A3…) at their real size | `FRSceneSettings.out_format` ui.py:785 |
| Size | – | no tooltip | How many pixels: HD (1920 × 1080) for screens and slides, 4K for big screens or cropping, Preview for quick checks | `FRSceneSettings.out_resolution` ui.py:788 |
| Orientation | – | no tooltip | Landscape or portrait. Default uses the format's usual way | `FRSceneSettings.out_orientation` ui.py:789 |
| Resolution | – | no tooltip | Print resolution: 300 dpi for print shops, 150 dpi for office printers and smaller files | `FRSceneSettings.out_dpi` ui.py:791 |
| Orientation | – | no tooltip | Landscape or portrait. Default uses the format's usual way | `FRSceneSettings.out_orientation` ui.py:792 |
| Bleed (mm) | – | no tooltip | Extra picture around the page for the print shop to cut off (usually 3 mm) | `FRSceneSettings.out_bleed_mm` ui.py:795 |
| Width | – | no tooltip | Width of the picture in pixels (Custom size) | `FRSceneSettings.out_custom_w` ui.py:797 |
| Height | – | no tooltip | Height of the picture in pixels (Custom size) | `FRSceneSettings.out_custom_h` ui.py:798 |
| Quality | – | no tooltip | How clean the picture is: Draft (quick check, half size), Preview, Final (clean) or Best (very clean, slow). Cleaner takes longer | `FRSceneSettings.quality` ui.py:801 |
| Open | Open this render | repeats the label | Opens the rendered picture in your picture viewer | `fresing.open_file (path=…)` ui.py:813 |
| File | – | no tooltip | PNG: sharp, can be transparent. JPEG: much smaller files, no transparency | `FRSceneSettings.out_file_type` ui.py:819 |
| Graphics card | – | no tooltip | Renders on the graphics card when the PC has a suitable one. Off: renders on the processor | `FRSceneSettings.use_gpu` ui.py:821 |

## Motion lane (54)

### 4 Motion

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the joint, used in animation steps. Double-click to rename | `FRJoint.name` ui_motion.py:23 |
| Add rotate joint | Click a hole, shaft or face on the model to set the joint axis | same text as Add slide joint, [icon EYEDROPPER] | Adds a joint that turns the selected subassembly. Then click its pivot on the model: a hole or shaft, or a flat face. Esc cancels | `fresing.joint_pick_axis (mode=NEW, kind=ROTATE)` ui_motion.py:73 |
| Add slide joint | Click a hole, shaft or face on the model to set the joint axis | same text as Add rotate joint, [icon EYEDROPPER] | Adds a joint that slides the selected subassembly. Then click a hole, shaft or flat face that points the way it slides. Esc cancels | `fresing.joint_pick_axis (mode=NEW, kind=SLIDE)` ui_motion.py:75 |
| Show joint arrows in the view | – | no tooltip | Shows or hides the joints' arrows in the view. They never show in renders | `FRSceneSettings.show_joints` ui_motion.py:92 |
| (field without label) | – | no tooltip | Lowest angle this joint can turn to, in degrees (CAD position = 0°) | `FRJoint.rot_min` ui_motion.py:115 |
| (field without label) | – | no tooltip | Highest angle this joint can turn to, in degrees (CAD position = 0°) | `FRJoint.rot_max` ui_motion.py:116 |
| (field without label) | – | no tooltip | Shortest position this joint can slide to, in mm (CAD position = 0) | `FRJoint.slide_min` ui_motion.py:118 |
| (field without label) | – | no tooltip | Furthest position this joint can slide to, in mm (CAD position = 0) | `FRJoint.slide_max` ui_motion.py:119 |
| Add | Add the selected subassemblies to the joint, or take them out | same text as Remove, Select | Adds the selected parts or subassemblies to what this joint moves | `fresing.joint_members (action=ADD)` ui_motion.py:127 |
| Remove | Add the selected subassemblies to the joint, or take them out | same text as Add, Select | Takes the selected parts or subassemblies out of what this joint moves | `fresing.joint_members (action=REMOVE)` ui_motion.py:128 |
| Select | Add the selected subassemblies to the joint, or take them out | same text as Add, Remove | Selects everything this joint moves, so you can see it in the view | `fresing.joint_members (action=SELECT)` ui_motion.py:129 |
| icon EYEDROPPER | Click a hole, shaft or face on the model to set the joint axis | same text as Add rotate joint, Add slide joint | Gives this joint a new axis: click a hole or shaft (axis through its centre) or a flat face (axis at right angles to it) | `fresing.joint_pick_axis (mode=EDIT)` ui_motion.py:133 |

### Poses & exploded views

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the pose, used in saved scenes and animations. Double-click to rename | `FRPose.name` ui_motion.py:150 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected pose. The model does not move | `fresing.pose_remove` ui_motion.py:169 |
| Pieces | – | no tooltip | What moves apart: the subassemblies directly inside the selected one, or every single part | `FRSceneSettings.explode_level` ui_motion.py:180 |
| Direction | – | no tooltip | Which way the pieces move: outwards from the centre, along X, along Y, or up and down | `FRSceneSettings.explode_direction` ui_motion.py:181 |

### Saved scenes

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the scene, used in the queue and as an animation's start. Double-click to rename | `FRShot.name` ui_motion.py:197 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Deletes the selected saved scene. The model and the cameras do not change | `fresing.shot_remove` ui_motion.py:226 |
| Camera | – | no tooltip | The camera this scene renders from | `FRShot.camera` ui_motion.py:236 |
| Queue this | Add a render to the queue | same text as All scenes, Current view, Queue all, Render animation, Time test (2 frames) | Adds a picture of the selected scene to 7 Render queue. Start queue there renders it in the background | `fresing.queue_add (kind=SHOT)` ui_motion.py:242 |
| Queue all | Add a render to the queue | same text as All scenes, Current view, Queue this, Render animation, Time test (2 frames) | Adds a picture of every saved scene to 7 Render queue. Start queue there renders them in the background | `fresing.queue_add (kind=ALL_SHOTS)` ui_motion.py:244 |

### 6 Animation

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| (in each list row) | – | no tooltip | Name of the animation, shown in the queue. Double-click to rename | `FRAnimation.name` ui_motion.py:259 |
| (in each list row) | – | no tooltip | Switches this step on or off. A step that is off is left out of Build & play and the video | `FRAnimBlock.enabled` ui_motion.py:268 |
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
| Time test (2 frames) | Add a render to the queue | same text as All scenes, Current view, Queue all, Queue this, Render animation | Renders 2 frames of this animation in the queue, then shows how long the whole video will take with these settings | `fresing.queue_add (kind=TEST, name=…, start=True)` ui_motion.py:405 |
| Render animation | Add a render to the queue | same text as All scenes, Current view, Queue all, Queue this, Time test (2 frames) | Renders this animation in the background and starts the queue (7 Render queue). Keep working, or close the app: it keeps going | `fresing.queue_add (kind=ANIMATION, name=…, start=True)` ui_motion.py:407 |

### 7 Render queue

| On screen | Now | Problem | Suggested tooltip | Code |
| --- | --- | --- | --- | --- |
| Current view | Add a render to the queue | same text as All scenes, Queue all, Queue this, Render animation, Time test (2 frames) | Adds a picture of the model as it is now, from the active camera, to the queue | `fresing.queue_add (kind=STILL)` ui_motion.py:471 |
| All scenes | Add a render to the queue | same text as Current view, Queue all, Queue this, Render animation, Time test (2 frames) | Adds a picture of every saved scene to 7 Render queue. Start queue there renders them in the background | `fresing.queue_add (kind=ALL_SHOTS)` ui_motion.py:473 |
| icon REMOVE | (undocumented operator) | Blender's 'undocumented operator' | Takes the selected job out of the queue. Files it already rendered stay | `fresing.queue_remove` ui_motion.py:479 |
| icon BRUSH_DATA | (undocumented operator) | Blender's 'undocumented operator' | Takes all finished jobs out of the list. Their files stay | `fresing.queue_remove (finished=True)` ui_motion.py:480 |
| Stop after this frame | Stop after the current frame or image (start again later to continue an animation) | same text as Stop now | Stops when the current frame or picture is done. Start queue continues an animation where it stopped | `fresing.queue_stop` ui_motion.py:498 |
| Stop now | Stop after the current frame or image (start again later to continue an animation) | same text as Stop after this frame | Stops the render at once; the frame being rendered is lost. Start queue continues an animation where it stopped | `fresing.queue_stop (now=True)` ui_motion.py:501 |
