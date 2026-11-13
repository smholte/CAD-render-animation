"""The landing page's moving models (task 0112): sources -> STEP with the moving bodies as sub-assemblies + a joint
sheet the render kit's project maker reads (``site/render_kit/projects.py``). No Blender here; OpenCascade (OCP).

    thor.py   the Thor arm from AngelLM/Thor's FreeCAD Assembly4 files: 6 joints read from the files' coordinate
              systems, the motor pinions and the wrist's bevel gears coupled by their tooth counts, the gripper
    ceb.py    the CEB brick press from goscommons/CEB-Press: its two hydraulic cylinders split into barrel and rod
    a4.py     reading Assembly4 files; stepout.py writing the STEP; fetch.py cloning the sources (pinned commits)
"""
