"""tools/ci_toolbox_w2w3.py (task 0245) – the Windows checks W2 (junctions) and W3 (status.json replaced while read)
– runs here for a few seconds with symbolic links in place of junctions (Linux never refuses a replace). GitHub's
Windows job runs it for 40 s with the installed Blender's own Python (tools/ci_windows_install.ps1, part A)."""

import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "tools" / "ci_toolbox_w2w3.py"


def test_w2_w3_pass_and_report_their_numbers(tmp_path):
    r = subprocess.run([sys.executable, str(TOOL), str(tmp_path / "w é"), "--seconds", "3", "--label", "test"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    last = [ln for ln in r.stdout.splitlines() if ln.startswith("W2W3 ")][-1]
    info = json.loads(last[5:])
    assert info["failed"] == [] and info["label"] == "test"
    assert info["w3"]["reader"]["reads"] > 0 and info["w3"]["reader"]["not_whole"] == 0
    assert "W2 a junction in place of a job's file: bad-job" in r.stdout
