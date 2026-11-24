"""Task 0296: always the graphics card – the rules of core/gpu_choice.py with made-up adapter lists (no Blender)."""
from __future__ import annotations

import json

import pytest

from fresing_render.core import gpu_choice as g
from fresing_render.core.gpu_choice import Adapter, Device

# made-up PCs (names as Windows' adapter list, Cycles and the OpenGL renderer give them)
INTEL_UHD = Adapter("Intel(R) UHD Graphics 770", 0x8086, 0x4680, 128, 16000, outputs=0, high_performance=1)
RTX_3090 = Adapter("NVIDIA GeForce RTX 3090", 0x10DE, 0x2204, 24268, 16000, outputs=1, high_performance=0)
RTX_A2000 = Adapter("NVIDIA RTX A2000", 0x10DE, 0x2531, 6000, 16000, outputs=1, high_performance=0)
AMD_IGPU = Adapter("AMD Radeon(TM) Graphics", 0x1002, 0x164E, 512, 16000, outputs=0, high_performance=1)
RX_6700 = Adapter("AMD Radeon RX 6700 XT", 0x1002, 0x73DF, 12272, 16000, outputs=1, high_performance=0)
ARC_IGPU = Adapter("Intel(R) Arc(TM) Graphics", 0x8086, 0x7D55, 128, 16000, outputs=1)
ARC_A770 = Adapter("Intel(R) Arc(TM) A770 Graphics", 0x8086, 0x56A0, 16000, 16000, outputs=1)
APU_780M = Adapter("AMD Radeon 780M Graphics", 0x1002, 0x15BF, 2048, 16000, outputs=1)
BASIC = Adapter("Microsoft Basic Render Driver", 0x1414, 0x8C, 0, 16000, software=True)


@pytest.mark.parametrize("name, want", [
    ("NVIDIA GeForce RTX 3090", g.CARD), ("NVIDIA GeForce RTX 3090/PCIe/SSE2", g.CARD), ("NVIDIA RTX A2000", g.CARD),
    ("Quadro P1000", g.CARD), ("AMD Radeon RX 6700 XT", g.CARD), ("Radeon RX 7900 XTX", g.CARD),
    ("AMD Radeon PRO W7600", g.CARD), ("AMD Radeon RX 6800M", g.CARD), ("Radeon VII", g.CARD),
    ("Intel(R) Arc(TM) A770 Graphics", g.CARD), ("Intel(R) Arc(TM) B580 Graphics", g.CARD),
    ("Intel(R) Arc(TM) A370M Graphics", g.CARD), ("Intel(R) Arc(TM) Pro A40 Graphics", g.CARD),
    ("AMD Radeon(TM) Graphics", g.BUILT_IN), ("AMD Radeon 780M Graphics", g.BUILT_IN),
    ("AMD Radeon(TM) 890M", g.BUILT_IN), ("AMD Radeon(TM) Vega 8 Graphics", g.BUILT_IN),
    ("AMD Radeon(TM) RX Vega 11 Graphics", g.BUILT_IN), ("AMD Radeon 8060S Graphics", g.BUILT_IN),
    ("Intel(R) UHD Graphics 770", g.BUILT_IN), ("Intel(R) Iris(R) Xe Graphics", g.BUILT_IN),
    ("Intel(R) Arc(TM) Graphics", g.BUILT_IN), ("Intel(R) Arc(TM) 140V GPU (16GB)", g.BUILT_IN),
    ("Apple M2", g.BUILT_IN),
    ("Microsoft Basic Render Driver", g.SOFTWARE), ("llvmpipe (LLVM 17.0.6, 256 bits)", g.SOFTWARE),
    ("Mystery GPU 9000", g.UNKNOWN),
])
def test_names_tell_a_card_from_built_in_graphics(name, want):
    assert g.kind(name) == want


def test_unknown_names_fall_back_to_the_adapters_own_memory():
    assert g.kind("Mystery GPU 9000", dedicated_mb=8192) == g.CARD
    assert g.kind("Mystery GPU 9000", dedicated_mb=256) == g.BUILT_IN
    assert g.kind("Some Adapter", 0x1414, 0, software=True) == g.SOFTWARE


def test_the_same_gpu_under_its_different_names():
    assert g.same_gpu("AMD Radeon RX 6700 XT", "AMD Radeon(TM) RX 6700 XT")
    assert g.same_gpu("NVIDIA GeForce RTX 3090/PCIe/SSE2", "NVIDIA GeForce RTX 3090")
    assert not g.same_gpu("AMD Radeon(TM) Graphics", "AMD Radeon RX 6700 XT")
    assert not g.same_gpu("", "AMD Radeon RX 6700 XT")


# --- the window -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("pc, renderer, state, card", [
    ([INTEL_UHD, RTX_3090], "NVIDIA GeForce RTX 3090/PCIe/SSE2", "card", "NVIDIA GeForce RTX 3090"),
    ([INTEL_UHD, RTX_3090], "Intel(R) UHD Graphics 770", "built_in_with_card", "NVIDIA GeForce RTX 3090"),
    ([AMD_IGPU, RX_6700], "AMD Radeon(TM) Graphics", "built_in_with_card", "AMD Radeon RX 6700 XT"),   # the tester's
    ([AMD_IGPU, RX_6700], "AMD Radeon RX 6700 XT", "card", "AMD Radeon RX 6700 XT"),
    ([INTEL_UHD, ARC_A770], "Intel(R) UHD Graphics 770", "built_in_with_card", "Intel Arc A770 Graphics"),
    ([ARC_IGPU], "Intel(R) Arc(TM) Graphics", "built_in", ""),
    ([APU_780M], "AMD Radeon 780M Graphics", "built_in", ""),                                         # APU only
    ([INTEL_UHD, RTX_A2000], "Intel(R) UHD Graphics 770", "built_in_with_card", "NVIDIA RTX A2000"),   # Optimus
    ([BASIC], "Microsoft Basic Render Driver", "software", ""),                                       # no GPU at all
    ([], "llvmpipe (LLVM 17.0.6, 256 bits)", "software", ""),
    ([], "Mystery GPU 9000", "unknown", ""),
])
def test_what_draws_the_window(pc, renderer, state, card):
    w = g.window_state(renderer, pc)
    assert w["state"] == state
    assert w["card"] == card


def test_the_cards_come_in_windows_high_performance_order():
    a = Adapter("AMD Radeon RX 6400", 0x1002, 1, 4096, high_performance=1)
    b = Adapter("NVIDIA GeForce RTX 4060", 0x10DE, 2, 8192, high_performance=0)
    assert [c.name for c in g.cards([a, b, INTEL_UHD])] == [b.name, a.name]


def test_software_adapters_and_doubles_are_not_gpus():
    twice = Adapter(RX_6700.name, RX_6700.vendor_id, RX_6700.device_id, RX_6700.dedicated_mb)
    assert [a.name for a in g.hardware([BASIC, RX_6700, twice])] == [RX_6700.name]


def test_a_monitor_on_the_motherboard_is_found():
    on_board = Adapter(AMD_IGPU.name, AMD_IGPU.vendor_id, AMD_IGPU.device_id, 512, outputs=1)
    card_free = Adapter(RX_6700.name, RX_6700.vendor_id, RX_6700.device_id, 12272, outputs=0)
    assert g.cable_in_motherboard([on_board, card_free])
    assert not g.cable_in_motherboard([AMD_IGPU, RX_6700])
    assert not g.cable_in_motherboard([Adapter(AMD_IGPU.name, 0x1002, 1, 512), Adapter(RX_6700.name, 0x1002, 2, 12272)])
    assert "monitor cable" in g.guide_steps("AMD Radeon RX 6700 XT", cable=True)[0]


# --- the Windows preference -----------------------------------------------------------------------------------

def test_the_preference_is_written_only_where_the_user_has_not_chosen():
    assert g.auto_preference(None) == "GpuPreference=2;"
    assert g.auto_preference("") == "GpuPreference=2;"
    assert g.auto_preference("GpuPreference=0;") == "GpuPreference=2;"
    assert g.auto_preference("SwapEffectUpgradeEnable=1;") == "SwapEffectUpgradeEnable=1;GpuPreference=2;"
    assert g.auto_preference("GpuPreference=2;") is None
    assert g.auto_preference("GpuPreference=1;") is None              # the user's own Power saving stays


def test_use_the_graphics_card_overrides_power_saving_and_keeps_other_settings():
    assert g.forced_preference("SwapEffectUpgradeEnable=1;GpuPreference=1;") == \
        "SwapEffectUpgradeEnable=1;GpuPreference=2;"
    assert g.forced_preference("GpuPreference=2;") is None
    assert g.preference_name("GpuPreference=2;") == "High performance"
    assert g.preference_name(None).startswith("not set")


# --- Cycles -----------------------------------------------------------------------------------------------------

def _dev(*rows):
    return g.devices_from(rows)


def test_intel_built_in_and_nvidia_renders_on_the_nvidia_card():
    devs = _dev(("OPTIX", "NVIDIA GeForce RTX 3090", "OPTIX_0"), ("CUDA", "NVIDIA GeForce RTX 3090", "CUDA_0"),
                ("ONEAPI", "Intel(R) UHD Graphics 770", "ONEAPI_0"), ("CPU", "AMD Ryzen 9 9900X", "CPU"))
    p = g.render_plan(devs)
    assert (p.backend, p.ids) == ("OPTIX", ["OPTIX_0"])
    assert p.text() == "GPU (OPTIX): NVIDIA GeForce RTX 3090"


def test_amd_built_in_and_amd_card_render_on_the_card_only():
    devs = _dev(("HIP", "AMD Radeon RX 6700 XT", "HIP_0"), ("HIP", "AMD Radeon(TM) Graphics", "HIP_1"),
                ("CPU", "AMD Ryzen 7 7700X", "CPU"))
    p = g.render_plan(devs)
    assert (p.backend, p.ids, p.left_out) == ("HIP", ["HIP_0"], ["AMD Radeon(TM) Graphics"])
    assert p.text().startswith("GPU (HIP): AMD Radeon RX 6700 XT")
    assert "built-in AMD Radeon Graphics left out" in p.text()


def test_a_card_on_no_backend_and_an_intel_built_in_one_on_oneapi():
    p = g.render_plan(_dev(("ONEAPI", "Intel(R) UHD Graphics 770", "ONEAPI_0")))
    assert p.backend == "ONEAPI" and "built-in graphics only" in p.note       # as before 0296: better than nothing


def test_intel_built_in_and_intel_arc():
    devs = _dev(("ONEAPI", "Intel(R) UHD Graphics 770", "ONEAPI_1"), ("ONEAPI", "Intel(R) Arc(TM) A770 Graphics", "ONEAPI_0"))
    p = g.render_plan(devs)
    assert (p.backend, p.ids) == ("ONEAPI", ["ONEAPI_0"])


def test_amd_apu_only_keeps_its_built_in_graphics():
    p = g.render_plan(_dev(("HIP", "AMD Radeon 780M Graphics", "HIP_0"), ("CPU", "AMD Ryzen 7 8700G", "CPU")))
    assert (p.backend, p.ids) == ("HIP", ["HIP_0"]) and "built-in graphics only" in p.note


def test_no_gpu_at_all_renders_on_the_processor():
    p = g.render_plan(_dev(("CPU", "Intel Xeon", "CPU")))
    assert not p.gpu and p.text() == "CPU" and p.backend == "NONE"


def test_a_chosen_device_and_a_chosen_device_that_is_gone():
    devs = _dev(("OPTIX", "NVIDIA GeForce RTX 3090", "OPTIX_0"), ("CUDA", "NVIDIA GeForce RTX 3090", "CUDA_0"))
    assert g.render_plan(devs, "CUDA_0").backend == "CUDA"
    assert not g.render_plan(devs, g.CPU).gpu
    p = g.render_plan(devs, "HIP_7")
    assert p.backend == "OPTIX" and "not there" in p.note


def test_the_settings_list():
    devs = _dev(("HIP", "AMD Radeon RX 6700 XT", "HIP_0"), ("HIP", "AMD Radeon(TM) Graphics", "HIP_1"),
                ("CPU", "AMD Ryzen 7 7700X", "CPU"))
    items = g.choices(devs)
    assert [i[0] for i in items] == [g.AUTO, "HIP_0", "HIP_1", g.CPU]
    assert "built-in graphics" in items[2][2] and "graphics card" in items[1][2]


# --- the notice -------------------------------------------------------------------------------------------------

def test_the_notice_shows_on_built_in_graphics_with_a_card():
    w = g.window_state("AMD Radeon(TM) Graphics", [AMD_IGPU, RX_6700])
    sig = g.signature([AMD_IGPU, RX_6700])
    st = g.fresh()
    assert g.decide_notice(st, sig, w) == "built_in"
    assert g.decide_notice(st, sig, w, shown=True) == ""                    # at most once per start
    assert g.decide_notice(st, sig, w, pending=True) == ""                  # the preference waits for the next start
    st["never_for"] = sig
    assert g.decide_notice(st, sig, w) == ""                                # Don't ask again


def test_dont_ask_again_holds_until_the_gpus_change():
    old = g.signature([AMD_IGPU, RX_6700])
    new = g.signature([AMD_IGPU, Adapter("AMD Radeon RX 7800 XT", 0x1002, 0x747E, 16000)])
    assert old != new and old == g.signature([RX_6700, AMD_IGPU, BASIC])     # order and software do not count
    st = dict(g.fresh(), never_for=old)
    w = g.window_state("AMD Radeon(TM) Graphics", [AMD_IGPU, RX_6700])
    assert g.decide_notice(st, new, w) == "built_in"


def test_no_notice_on_a_card_or_without_one_unless_slow():
    st = g.fresh()
    on_card = g.window_state("NVIDIA GeForce RTX 3090", [INTEL_UHD, RTX_3090])
    apu = g.window_state("AMD Radeon 780M Graphics", [APU_780M])
    assert g.decide_notice(st, "x", on_card) == ""
    assert g.decide_notice(st, "x", apu) == ""
    assert g.decide_notice(st, "x", apu, slow=True) == "slow"
    assert g.decide_notice(st, "x", g.window_state("Microsoft Basic Render Driver", [BASIC])) == ""


def test_slow_needs_several_slow_frames_in_a_row():
    t = g.DrawTimes()
    assert not t.add(3.0) and not t.add(3.0)
    assert not t.add(0.1)                       # one quick frame starts the count again
    assert not t.add(2.5) and not t.add(2.5)
    assert t.add(2.5) and t.worst == 3.0


def test_the_texts_name_the_gpus():
    w = g.window_state("AMD Radeon(TM) Graphics", [AMD_IGPU, RX_6700])
    text = " ".join(g.notice_text("built_in", w))
    assert "AMD Radeon Graphics" in text and "AMD Radeon RX 6700 XT" in text and "(TM)" not in text
    assert "6.0 s" in " ".join(g.notice_text("slow", g.window_state("AMD Radeon 780M Graphics", [APU_780M]), 6.0))
    steps = g.guide_steps("AMD Radeon RX 6700 XT", exes=[r"C:\x\Fresing Render.exe"])
    assert any("Fresing Render.exe" in s for s in steps) and any("High performance" in s for s in steps)


def test_the_state_file(tmp_path):
    p = tmp_path / "cfg" / g.FILE_NAME
    assert g.load(str(p)) == g.fresh()
    st = dict(g.fresh(), never_for="abc", render_device="HIP_0", window={"state": "card", "drawn": "X"},
              auto_done=[r"C:\x\blender.exe"])
    g.save(str(p), st)
    assert g.load(str(p)) == st
    p.write_text("{broken")
    assert g.load(str(p)) == g.fresh()
    p.write_text(json.dumps({"never_for": 3, "render_device": "", "window": {"a": [1]}}))
    assert g.load(str(p)) == g.fresh()
