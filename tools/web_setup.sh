#!/usr/bin/env bash
# Set-up of a Claude Code on the web session (task 0031, CLAUDE.md section 4).
# Idempotent: skips what is there. Run as the environment's "Setup script":
#     bash fresing-render-dir/tools/web_setup.sh        (see CLAUDE.md section 4)
# Parts: venv ~/venv (pinned packages), Blender into ~/blender-<ver>, xvfb + ImageMagick (apt),
# Linux wheels for the packaged test into ~/linux-wheels. One line per part with its time.
# Versions are read from the repository (tools/requirements-dev.txt, the workflow, the installer);
# tests/test_web_setup.py checks they still agree with the paths in here.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
T0=$(date +%s)
FAIL=0
BLENDER_VERSION="5.2.3"
OCP_VERSION="8.0.1.1.0"
MANIFOLD_VERSION="3.5.4"
VENV="$HOME/venv"
BLENDER_DIR="$HOME/blender-$BLENDER_VERSION"
WHEELS="$HOME/linux-wheels"

part() {  # part "name" command...
    local name="$1"; shift
    local t=$(date +%s)
    if "$@" >"/tmp/web_setup_${name// /_}.log" 2>&1; then
        echo "[ok]   $name ($(( $(date +%s) - t )) s)"
    else
        echo "[FAIL] $name ($(( $(date +%s) - t )) s) - see /tmp/web_setup_${name// /_}.log"; tail -5 "/tmp/web_setup_${name// /_}.log" | sed 's/^/         /'
        FAIL=1
    fi
}

do_venv() {
    if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" - "$REPO/tools/requirements-dev.txt" <<'PY'
import importlib.metadata as m, re, sys
for line in open(sys.argv[1]):
    line = line.split("#")[0].strip()
    if "==" in line:
        n, v = line.split("==")
        if m.version(n) != v: sys.exit(1)
PY
    then echo "already there"; return 0; fi
    PY=$(command -v python3.13 || command -v python3)
    [ -x "$VENV/bin/python" ] || "$PY" -m venv "$VENV" || return 1
    "$VENV/bin/pip" install -q -r "$REPO/tools/requirements-dev.txt"
}

do_blender() {
    local exe="$BLENDER_DIR/blender-$BLENDER_VERSION-linux-x64/blender"
    [ -x "$exe" ] && { echo "already there"; return 0; }
    local s="${BLENDER_VERSION%.*}" f="blender-$BLENDER_VERSION-linux-x64.tar.xz" tmp
    tmp=$(mktemp -d) || return 1
    ( cd "$tmp" &&
      curl -sSfL --retry 3 -o "$f" "https://download.blender.org/release/Blender$s/$f" &&
      curl -sSfL --retry 3 "https://download.blender.org/release/Blender$s/blender-$BLENDER_VERSION.sha256" | grep " $f\$" > blender.sha256 &&
      sha256sum -c blender.sha256 &&
      mkdir -p "$BLENDER_DIR" && tar -xJf "$f" -C "$BLENDER_DIR" ) || { rm -rf "$tmp"; return 1; }
    rm -rf "$tmp"
}

do_apt() {
    if command -v xvfb-run >/dev/null && command -v import >/dev/null && command -v convert >/dev/null; then
        echo "already there"; fi
    # libraries real Blender needs (same list as the workflow)
    local pk="xvfb xauth imagemagick libgl1 libglx-mesa0 libgl1-mesa-dri libegl1 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 libvulkan1"
    local missing=""
    for p in $pk; do dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"; done
    [ -z "$missing" ] && return 0
    ( apt-get update -q && apt-get install -y -q --no-install-recommends $missing )
}

do_wheels() {
    ls "$WHEELS"/cadquery_ocp_novtk-"$OCP_VERSION"*.whl "$WHEELS"/manifold3d-"$MANIFOLD_VERSION"*.whl >/dev/null 2>&1 && { echo "already there"; return 0; }
    "$VENV/bin/pip" download "cadquery-ocp-novtk==$OCP_VERSION" "cadquery-ocp-proxy==$OCP_VERSION" "manifold3d==$MANIFOLD_VERSION" \
        --no-deps --only-binary=:all: --platform manylinux_2_28_x86_64 --python-version 3.13 -d "$WHEELS"
}

part "system packages (apt)" do_apt
part "python venv" do_venv
part "Blender $BLENDER_VERSION" do_blender
[ -x "$VENV/bin/pip" ] && part "linux wheels" do_wheels
echo "Blender: $BLENDER_DIR/blender-$BLENDER_VERSION-linux-x64/blender   wheels: $WHEELS   python: $VENV/bin/python"
echo "ready in $(( $(date +%s) - T0 )) s$([ $FAIL = 1 ] && echo ' (with failures)')"
exit $FAIL
