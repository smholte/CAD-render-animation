"""tools/web_setup.sh (Claude Code on the web set-up, task 0031) must not drift from the versions the repository pins."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = (ROOT / "tools" / "web_setup.sh").read_text(encoding="utf-8")


def sh_var(name):
    return re.search(rf'^{name}="([^"]+)"', SH, re.M).group(1)


def test_blender_version_matches_installer():
    ps1 = (ROOT / "installer" / "Install-FresingRender.ps1").read_text(encoding="utf-8")
    assert sh_var("BLENDER_VERSION") == re.search(r'\$BlenderVersion\s*=\s*"([^"]+)"', ps1).group(1)


def test_wheel_versions_match_workflow_and_requirements():
    wf = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    req = (ROOT / "tools" / "requirements-dev.txt").read_text(encoding="utf-8")
    assert sh_var("OCP_VERSION") == re.search(r'OCP_VERSION: "([^"]+)"', wf).group(1)
    assert sh_var("MANIFOLD_VERSION") == re.search(r'MANIFOLD_VERSION: "([^"]+)"', wf).group(1)
    assert f"cadquery-ocp=={sh_var('OCP_VERSION')}" in req
    assert f"manifold3d=={sh_var('MANIFOLD_VERSION')}" in req


def test_script_uses_the_workflows_download_and_paths():
    assert "download.blender.org/release/Blender" in SH and "sha256sum -c" in SH
    assert 'VENV="$HOME/venv"' in SH and "linux-wheels" in SH
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "tools/web_setup.sh" in claude and "~/blender-5.2.3" in claude.replace(sh_var("BLENDER_VERSION"), "5.2.3")
