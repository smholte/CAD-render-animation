# Security policy

## Which version is supported

The **newest release** (https://github.com/smholte/CAD-render-animation/releases/latest). Older versions get no
separate fixes: update with **Update now** in the app (or run the newest installer).

## How to report a security problem

**Never in a public issue, a public comment or a pull request** – everything in this repository is public.

1. Open the Security tab of this repository: https://github.com/smholte/CAD-render-animation/security/advisories/new
   ("Report a vulnerability"). Only the owner and you can see what you write there.
2. Say what you found, which version (Help menu in the app), what you did and what happened. A small test file that
   shows the problem helps – **made up, never a confidential model**.

If "Report a vulnerability" is not shown to you, tell the owner by the contact he gave you, or open a public issue that
says only "I have a security report, please open a private channel" – without any detail.

Answers are best effort: there is no fixed time, and no reward programme.

## What counts

- the **installer** and the **updater** (`Install.bat`, the in-app **Update now**, the checks of the downloaded file)
- the **file readers**: STEP, mesh files (glTF / OBJ), G-code, house packages, project and library files (`.json`)
- the **web pages the app writes** (Web 3D model) and the landing page
- anything that makes the app run code from a file it only had to read, or reach the network without being asked

Not in this repository's scope: problems in Blender itself (report them to the Blender project), in OpenCascade or in
the other libraries listed in `THIRD-PARTY-NOTICES.md` (report them to their projects), and a PC that is already
controlled by someone else.

A company that wants to know what the app does on the network: `docs/COMPANY-USE.md`.
