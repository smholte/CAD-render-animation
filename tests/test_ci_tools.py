"""The helpers of the automatic tests on GitHub (tools/ci_*.py) and the self-test's skip switch."""

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ci_check_selftest  # noqa: E402
import ci_pytest_summary  # noqa: E402

HEAD = ("Fresing Render 0.2.8 self-test, 2026-11-04 22:00\n"
        "Blender 5.2.3 LTS, Python 3.13.9, Windows-11\n")
OK_LINES = "".join(f"[ OK ] Check number {i} ({i}.0 s): fine\n" for i in range(13))   # as many as a real report
GPU_SKIPS = ("[SKIP] Graphics card: skipped: no graphics card\n"
             "[SKIP] Render HD on graphics card: skipped: no graphics card\n")


def judge(text):
    return ci_check_selftest.judge(text)


def test_all_ok_with_the_graphics_card_skipped_passes():
    rows, problems = judge(HEAD + OK_LINES + GPU_SKIPS + "RESULT: ALL OK (2 skipped)\n")
    assert problems == []
    assert [r[0] for r in rows].count("skipped") == 2


def test_names_with_brackets_are_kept_whole():
    rows, _ = judge("[ OK ] STEP reader (OpenCascade) (0.6 s): OpenCascade loaded\n")
    assert rows[0][1] == "STEP reader (OpenCascade)"
    assert rows[0][2] == "0.6 s: OpenCascade loaded"


def test_a_failing_check_fails_and_is_named():
    text = HEAD + OK_LINES + GPU_SKIPS + "[FAIL] Render queue (second Blender in the background): FAILED: no output\n" \
        "Traceback (most recent call last):\n  ...\nRESULT: PROBLEMS FOUND (see above)\n"
    rows, problems = judge(text)
    assert len(problems) == 1 and problems[0].startswith("Render queue (second Blender in the background)")


def test_only_graphics_card_checks_may_be_skipped():
    _, problems = judge(HEAD + OK_LINES + GPU_SKIPS + "[SKIP] Video encoder (MP4): skipped: no graphics card\n"
                        "RESULT: ALL OK (1 skipped)\n")
    assert len(problems) == 1 and "only the graphics-card checks" in problems[0]
    _, problems = judge(HEAD + OK_LINES + "[ OK ] Render HD on graphics card (5.0 s): ok\n"
                        "[SKIP] Graphics card: driver too old\nRESULT: ALL OK\n")
    assert len(problems) == 1


def test_a_report_without_result_line_means_a_crash():
    _, problems = judge(HEAD + OK_LINES)
    assert any("no RESULT line" in p for p in problems)


def test_a_self_test_that_ran_almost_nothing_fails():
    _, problems = judge(HEAD + "[ OK ] STEP reader (OpenCascade) (0.6 s): ok\nRESULT: ALL OK\n")
    assert any("only 1 checks ran" in p for p in problems)


def test_missing_report_fails(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ci_check_selftest.main([str(tmp_path / "nothing.txt")]) == 1
    assert "FAILED" in summary.read_text(encoding="utf-8")


def test_report_file_verdict_and_job_summary(tmp_path, monkeypatch):
    report = tmp_path / "Fresing Render self-test.txt"
    report.write_text(HEAD + OK_LINES + GPU_SKIPS + "RESULT: ALL OK (2 skipped)\n", encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ci_check_selftest.main([str(report), "--title", "Windows self-test"]) == 0
    text = summary.read_text(encoding="utf-8")
    assert "Windows self-test: passed" in text and "| Graphics card | ⏭️ skipped |" in text


def test_pytest_summary_names_the_failing_test(tmp_path, monkeypatch, capsys):
    xml = tmp_path / "pytest.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" tests="3" '
        'failures="1" errors="0" skipped="1" time="12.5">'
        '<testcase classname="tests.test_core" name="test_good" time="0.1"/>'
        '<testcase classname="tests.test_core" name="test_bad" time="0.1">'
        '<failure message="assert 1 == 2">long traceback</failure></testcase>'
        '<testcase classname="tests.test_core" name="test_skip" time="0.0"><skipped/></testcase>'
        '</testsuite></testsuites>', encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ci_pytest_summary.main([str(xml)]) == 0          # pytest's own exit code decides failures
    text = summary.read_text(encoding="utf-8")
    assert "1 passed, 1 failed, 1 skipped, 3 in all" in text
    assert "tests.test_core::test_bad" in text and "assert 1 == 2" in text
    assert "::error title=Failing test tests.test_core::test_bad::" in capsys.readouterr().out
    # skipped tests (bpy/OCP not importing) must not look green
    assert ci_pytest_summary.main([str(xml), "--max-skipped", "1"]) == 0
    assert ci_pytest_summary.main([str(xml), "--max-skipped", "0"]) == 1
    assert "1 tests were skipped (at most 0 allowed)" in summary.read_text(encoding="utf-8")


@pytest.mark.parametrize("value, expected", [("1", True), ("", False), ("0", False), (None, False)])
def test_self_test_skips_graphics_card_only_when_asked(monkeypatch, value, expected):
    """On a user's PC (switch not set) a missing graphics card stays a problem in the report."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("fr_selftest_only", os.path.join(ROOT, "fresing_render", "selftest.py"))
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)          # module level has no Blender imports
    if value is None:
        monkeypatch.delenv(st.NO_GPU_ENV, raising=False)
    else:
        monkeypatch.setenv(st.NO_GPU_ENV, value)
    assert st._no_gpu_expected() is expected


def test_real_app_verdicts():
    import ci_real_app as R
    n = R.MIN_CHECKS["ui2"]                 # (raised whenever the test gets new checks)
    ok = "".join(f"[UITEST] PASS check {i}\n" for i in range(n)) + f"[UITEST] RESULT {n}/{n} passed\n"
    assert R.judge("ui2", 0, ok, 15)[0] is True
    # a failing check, a crash before RESULT, a timeout
    v, detail, fails = R.judge("ui2", 0, ok.replace(f"RESULT {n}/{n}", f"RESULT {n - 1}/{n}") +
                               "[UITEST] FAIL undo\n", 15)
    assert v is False and fails == ["[UITEST] FAIL undo"]
    assert "stopped half-way" in R.judge("ui2", 1, "[UITEST] PASS a\n", 15)[1]
    assert "did not finish" in R.judge("ui2", None, ok, 15)[1]
    # checks that silently disappear
    v, detail, _ = R.judge("ui2", 0, "[UITEST] RESULT 20/20 passed\n", 15)
    assert v is False and f"at least {n} checks" in detail
    assert R.judge("ui1", 0, "[UITEST] RESULT 18/18 passed\n", 15, quick=True)[0] is True
    # a Python error outside the steps (e.g. a panel that fails to draw) turns it red ...
    stray = ok + "Traceback (most recent call last):\n  File \"ui.py\", line 3, in draw\nAttributeError: 'NoneType'\n"
    v, detail, fails = R.judge("ui2", 0, stray, 15)
    assert v is False and "outside the test steps" in detail and "AttributeError" in fails[-1]
    # ... one inside a step is already a failed check and is not counted twice
    step_err = ok + "[UITEST] ERROR in s_looks Traceback (most recent call last):\nKeyError: 'x'\n"
    assert "outside" not in R.judge("ui2", 0, step_err, 15)[1]


def test_strict_mode_wants_the_app_start_for_real():
    text = (HEAD + OK_LINES + GPU_SKIPS +
            "[ OK ] App start (Desktop shortcut) (0.0 s): skipped (not started from Blender)\n"
            "RESULT: ALL OK (2 skipped because FRESING_SELFTEST_NO_GPU=1)\n")
    assert judge(text)[1] == []                                      # Linux bpy module: fine
    _, problems = ci_check_selftest.judge(text, strict=True)          # real Windows install: not fine
    assert len(problems) == 1 and problems[0].startswith("App start (Desktop shortcut)")


def test_a_lost_check_line_is_noticed():
    lines = OK_LINES.splitlines(keepends=True)
    n = len(lines) - 2 + 2                                         # two lines lost, two graphics-card skips
    _, problems = judge(HEAD + "".join(lines[:-2]) + GPU_SKIPS + "RESULT: ALL OK (2 skipped)\n")
    assert n < ci_check_selftest.MIN_CHECKS
    assert any(f"only {n} checks ran" in p for p in problems)
