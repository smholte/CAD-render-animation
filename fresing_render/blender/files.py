"""Open a render, or show it in its folder (File Explorer with the file selected)."""

from __future__ import annotations

import os
import subprocess
import sys


def open_path(path: str) -> None:
    """Open a file with its program, or a folder in the file manager."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opening a file or folder for the user
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def explorer_select_command(path: str) -> str:
    """Windows command line that opens File Explorer with ``path`` selected.

    Explorer reads its own command line: the path goes in quotes right after "/select,"."""
    return f'explorer /select,"{os.path.normpath(path)}"'


def show_in_folder(path: str) -> None:
    """File manager at the file's folder, the file selected where the system supports it."""
    path = os.path.abspath(path)
    if sys.platform == "win32":
        subprocess.Popen(explorer_select_command(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])
