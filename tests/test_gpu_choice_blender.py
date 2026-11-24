"""Task 0296: always the graphics card – Cycles' devices picked by render.setup_gpu (a made-up Cycles), the Settings
line, the self-test / PC check line, the Windows preference with a made-up registry, Update now's helper."""

import os
import sys

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import gpu_choice as core  # noqa: E402
from fresing_render.core.gpu_choice import Adapter  # noqa: E402


class _Dev:
    def __init__(self, type_, name, id_):
        self.type, self.name, self.id, self.use = type_, name, id_, True


class FakeCycles:
    """Cycles' add-on preferences on the tester's PC: an AMD card and the Ryzen's built-in Radeon, both HIP."""

    def __init__(self, devices):
        self._all = devices
        self._type = "NONE"
        self.devices = []

    @property
    def compute_device_type(self):
        return self._type

    @compute_device_type.setter
    def compute_device_type(self, value):
        if value not in ("NONE",) + tuple({d.type for d in self._all if d.type != "CPU"}) + ("OPTIX", "CUDA"):
            raise TypeError(value)
        self._type = value

    def refresh_devices(self):
        self.devices = [d for d in self._all if d.type in (self._type, "CPU")]


TESTER = [_Dev("HIP", "AMD Radeon RX 6700 XT", "HIP_AMD Radeon RX 6700 XT_0000:03:00"),
          _Dev("HIP", "AMD Radeon(TM) Graphics (Display)", "HIP_AMD Radeon(TM) Graphics_0000:0e:00"),
          _Dev("CPU", "AMD Ryzen 7 7700X", "CPU")]


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def render(tmp_path, monkeypatch):
    from fresing_render.blender import gpu_choice, render
    monkeypatch.setattr(gpu_choice, "state_path", lambda: str(tmp_path / core.FILE_NAME))
    render._SEEN.clear()
    render.LAST["plan"] = None
    yield render
    render._SEEN.clear()
    render.LAST["plan"] = None


def test_the_tester_pc_renders_on_the_card_only(render):
    prefs = FakeCycles(TESTER)
    info = render.setup_gpu(prefs=prefs)
    assert info.startswith("GPU (HIP): AMD Radeon RX 6700 XT")
    assert "built-in AMD Radeon Graphics left out" in info
    assert prefs.compute_device_type == "HIP"
    use = {d.name: d.use for d in prefs.devices}
    assert use == {"AMD Radeon RX 6700 XT": True, "AMD Radeon(TM) Graphics (Display)": False, "AMD Ryzen 7 7700X": False}


def test_the_device_picked_in_settings(render):
    from fresing_render.blender import gpu_choice
    st = core.fresh()
    st["render_device"] = TESTER[1].id
    core.save(gpu_choice.state_path(), st)
    prefs = FakeCycles(TESTER)
    assert render.setup_gpu(prefs=prefs).startswith("GPU (HIP): AMD Radeon Graphics")
    assert [d.use for d in prefs.devices] == [False, True, False]
    st["render_device"] = core.CPU
    core.save(gpu_choice.state_path(), st)
    assert render.setup_gpu(prefs=FakeCycles(TESTER)) == "CPU"


def test_no_gpu_at_all(render):
    prefs = FakeCycles([_Dev("CPU", "Some CPU", "CPU")])
    assert render.setup_gpu(prefs=prefs) == "CPU"
    assert prefs.compute_device_type == "NONE"


def test_the_settings_line_draws_without_reading_devices(render):
    from fresing_render.blender import gpu_choice, ui_settings
    gpu_choice.draw_settings(ui_settings._Any())                    # devices not read yet: "Look for devices"
    assert render.known_devices() is None
    render.setup_gpu(prefs=FakeCycles(TESTER))
    s = gpu_choice.summary()
    assert s["known"] and s["renders"].startswith("GPU (HIP): AMD Radeon RX 6700 XT") and s["choice"].startswith("Automatic")
    gpu_choice.draw_settings(ui_settings._Any())
    assert "general" in ui_settings.draw_all(bpy.context)


def _window(monkeypatch, gpu_choice, state):
    st = core.fresh()
    st["window"] = state
    core.save(gpu_choice.state_path(), st)


def test_the_check_line(render, monkeypatch):
    from fresing_render.blender import gpu_choice
    monkeypatch.setattr(render, "setup_gpu", lambda *a, **k: render.LAST.update(plan=core.render_plan(
        core.devices_from([(d.type, d.name, d.id) for d in TESTER]))) or render.LAST["plan"].text())
    # the tester's PC as the app's last start saw it: built-in graphics drew the window
    w = core.window_state("AMD Radeon(TM) Graphics", [Adapter("AMD Radeon(TM) Graphics", 0x1002, 1, 512),
                                                      Adapter("AMD Radeon RX 6700 XT", 0x1002, 2, 12272)])
    _window(monkeypatch, gpu_choice, dict(w, when="2026-11-23 20:00"))
    status, text = gpu_choice.check()
    assert status == "problem" and "Use the graphics card" in text and "AMD Radeon RX 6700 XT" in text
    _window(monkeypatch, gpu_choice, dict(core.window_state("AMD Radeon RX 6700 XT"), when="x"))
    status, text = gpu_choice.check()
    assert status == "ok" and "draws: AMD Radeon RX 6700 XT (graphics card" in text and "renders: GPU (HIP)" in text


def test_the_check_line_without_a_gpu_is_skipped_on_a_test_server(render, monkeypatch):
    from fresing_render.blender import gpu_choice
    monkeypatch.setattr(render, "setup_gpu", lambda *a, **k: render.LAST.update(plan=core.Plan()) or "CPU")
    _window(monkeypatch, gpu_choice, core.window_state("Microsoft Basic Render Driver"))
    assert gpu_choice.check(no_gpu_expected=True)[0] == "skip"
    status, text = gpu_choice.check(no_gpu_expected=False)
    assert status == "ok" and "no graphics card" in text


def test_nothing_pops_up_in_the_background_or_the_tests():
    from fresing_render.blender import gpu_choice
    assert gpu_choice.suppressed()
    assert hasattr(bpy.ops.fresing, "gpu_notice") and hasattr(bpy.ops.fresing, "gpu_render_device")


class Reg:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def read(self, exe):
        return self.values.get(exe)

    def write(self, exe, text):
        self.values[exe] = text


def test_the_windows_preference_with_a_made_up_registry():
    from fresing_render import wingpu
    reg = Reg({"C:/b/blender.exe": "GpuPreference=1;", "C:/b/x.exe": "SwapEffectUpgradeEnable=1;"})
    assert wingpu.ensure(["C:/b/blender.exe", "C:/b/x.exe", "C:/b/new.exe"], reg) == ["C:/b/x.exe", "C:/b/new.exe"]
    assert reg.values["C:/b/blender.exe"] == "GpuPreference=1;"                   # the user's own choice kept
    assert reg.values["C:/b/x.exe"] == "SwapEffectUpgradeEnable=1;GpuPreference=2;"
    assert wingpu.force(["C:/b/blender.exe", "C:/b/new.exe"], reg) == ["C:/b/blender.exe"]
    assert reg.values["C:/b/blender.exe"] == "GpuPreference=2;"
    assert wingpu.adapters() == [] if sys.platform != "win32" else True


def test_update_now_sets_the_preference(tmp_path):
    from fresing_render import update_helper as h
    bdir = tmp_path / "blender-5.2.3-windows-x64"
    bdir.mkdir()
    for n in ("blender.exe", "Fresing Render.exe"):
        (bdir / n).write_bytes(b"")
    reg = Reg({str(bdir / "Fresing Render.exe"): "GpuPreference=1;"})
    plan = {"blender": str(bdir / "Fresing Render.exe")}
    assert h.set_gpu_preference(plan, read=reg.read, write=reg.write) == ""       # not an Install.bat folder
    (tmp_path / "installed.txt").write_text("Fresing Render")
    note = h.set_gpu_preference(plan, read=reg.read, write=reg.write)
    assert note == "graphics preference High performance: blender.exe"
    assert reg.values[str(bdir / "blender.exe")] == "GpuPreference=2;"
    assert reg.values[str(bdir / "Fresing Render.exe")] == "GpuPreference=1;"
    for text in (None, "", "GpuPreference=0;", "SwapEffectUpgradeEnable=1;", "GpuPreference=1;", "GpuPreference=2;"):
        assert h.gpu_preference_text(text) == core.auto_preference(text)       # the helper's copy of the rule


def test_the_installer_and_uninstaller_handle_the_preference():
    root = os.path.join(os.path.dirname(__file__), "..")
    inst = open(os.path.join(root, "installer", "Install-FresingRender.ps1"), encoding="ascii").read()
    unin = open(os.path.join(root, "installer", "Uninstall-FresingRender.ps1"), encoding="ascii").read()
    assert core.PREF_KEY.replace("\\\\", "\\") in inst and "GpuPreference=2;" in inst
    assert core.PREF_KEY in unin and "DeleteValue" in unin


def test_the_start_sets_each_program_once_then_keeps_the_users_choice(render, monkeypatch, tmp_path):
    """Independent review: "Let Windows decide" (0) chosen by the user after the app set High performance is kept."""
    from fresing_render import wingpu
    from fresing_render.blender import gpu_choice
    exes = [str(tmp_path / "blender.exe"), str(tmp_path / "Fresing Render.exe")]
    reg = Reg()
    monkeypatch.setattr(wingpu, "Registry", lambda: reg)
    monkeypatch.setattr(wingpu, "adapters", lambda fresh=False: [])
    monkeypatch.setattr(gpu_choice, "installed", lambda: True)
    monkeypatch.setattr(gpu_choice, "programs", lambda: exes)
    monkeypatch.setattr(sys, "platform", "win32")
    gpu_choice._RUN.update(done=False, shown=False, pending=False)
    gpu_choice.at_start()
    assert reg.values == {e: "GpuPreference=2;" for e in exes}
    assert gpu_choice.load()["auto_done"] == exes
    reg.values[exes[0]] = "GpuPreference=0;"                 # the user: Let Windows decide
    gpu_choice.at_start()
    assert reg.values[exes[0]] == "GpuPreference=0;"
