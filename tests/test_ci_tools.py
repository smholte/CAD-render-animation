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


def test_pytest_summary_does_not_count_skips_this_machine_cannot_help(tmp_path, monkeypatch):
    """Task 0108: EEVEE (no GL context) and the real-Blender test skip on GitHub's machines; two of them in one of
    the 8 groups turned it red. They no longer count against --max-skipped; any other skip still does."""
    xml = tmp_path / "pytest.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" tests="4" '
        'failures="0" errors="0" skipped="3" time="1.0">'
        '<testcase classname="tests.test_fade" name="test_eevee" time="0.1"><skipped type="pytest.skip" '
        'message="EEVEE cannot start here (no GL context)">x</skipped></testcase>'
        '<testcase classname="tests.test_section" name="test_eevee" time="0.1"><skipped type="pytest.skip" '
        'message="EEVEE cannot start here (no GL context)">x</skipped></testcase>'
        '<testcase classname="tests.test_spool_independent" name="test_real" time="0.0"><skipped '
        'type="pytest.skip" message="no real Blender here">x</skipped></testcase>'
        '<testcase classname="tests.test_core" name="test_good" time="0.1"/>'
        '</testsuite></testsuites>', encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert ci_pytest_summary.main([str(xml), "--max-skipped", "0"]) == 0
    assert "1 passed, 0 failed, 0 skipped (+ 3 that need a GL context or a real Blender), 4 in all" in \
        summary.read_text(encoding="utf-8")
    xml.write_text(xml.read_text(encoding="utf-8").replace(
        '<testcase classname="tests.test_core" name="test_good" time="0.1"/>',
        '<testcase classname="tests.test_core" name="test_good" time="0.1"><skipped type="pytest.skip" '
        'message="could not import \'bpy\'">x</skipped></testcase>'), encoding="utf-8")
    assert ci_pytest_summary.main([str(xml), "--max-skipped", "0"]) == 1


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
    q = R.MIN_CHECKS_QUICK["ui1"]
    assert R.judge("ui1", 0, f"[UITEST] RESULT {q}/{q} passed\n", 15, quick=True)[0] is True
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


# ---- task 0036: precheck, parallel groups, reuse of a green run --------------------------------------------

def _pre():
    import ci_precheck
    return ci_precheck


def _versions(v, *, on_main=False, main_v="0.2.28", base_v="0.2.28", released=("0.2.27", "0.2.28"),
              changelog=("0.2.29", "0.2.28")):
    return _pre().check_versions(v, v, list(changelog), on_main=on_main, main_v=main_v, base_v=base_v,
                                 released=set(released))


def test_precheck_versions():
    P = _pre()
    assert _versions("0.2.28")[0] == []                                   # not raised yet on the branch: fine
    assert _versions("0.2.29")[0] == []                                   # raised, newest, CHANGELOG heading
    problems, _ = _versions("0.2.29", main_v="0.2.29")                     # another task merged 0.2.29 first
    assert len(problems) == 1 and "someone took your version number" in problems[0] and "0.2.30" in problems[0]
    problems, _ = _versions("0.2.29", released=("0.2.29",), main_v="0.2.28")    # released, main not yet pulled
    assert "renumber to 0.2.30" in problems[0]
    problems, _ = _versions("0.2.30", changelog=("0.2.28",))
    assert "CHANGELOG.md has no heading for 0.2.30" in problems[0]
    problems, _ = P.check_versions("0.2.29", "0.2.28", ["0.2.29"], on_main=False, main_v="0.2.28",
                                   base_v="0.2.28", released=set())
    assert "version clash inside this commit" in problems[0]
    assert _versions("0.2.28", on_main=True)[0] == []                     # main, already released
    assert _versions("0.2.29", on_main=True)[0] == []
    assert "no heading" in _versions("0.2.30", on_main=True)[0][0]
    assert P.vtuple("0.2.10") > P.vtuple("0.2.9") and P.next_version("0.2.9") == "0.2.10"


def test_precheck_counts_groups_and_task_list_pass_on_this_repository():
    P = _pre()
    assert P.check_counts() == []
    assert P.check_groups() == []
    assert P.check_tasks(open(os.path.join(ROOT, "TASKS.md"), encoding="utf-8").read()) == []
    import ci_check_pccheck
    assert P.full_pccheck_lines(open(os.path.join(ROOT, "fresing_render", "pccheck", "checks.py"),
                                     encoding="utf-8").read()) <= ci_check_pccheck.MIN_LINES_FULL


def test_precheck_counts_full_lines_of_the_pc_check():
    src = ('Q, F, OWN = "quick", "full", "own"\n'
           '@line("a", "A", "0.1", (Q, F))\ndef a(ctx): pass\n'
           '@line("b", "B", "0.1")\ndef b(ctx): pass\n'
           '@line("c", "C", "0.1", modes=(F,))\ndef c(ctx): pass\n'
           '@line("d", "D", "0.1", (OWN,))\ndef d(ctx): pass\n'
           '@line("e", "E", "0.1", (Q,))\ndef e(ctx): pass\n')
    assert _pre().full_pccheck_lines(src) == 3


def test_precheck_finds_a_broken_task_table():
    P = _pre()
    good = "| # | Task | Who |\n| --- | --- | --- |\n| 0001 | a | lead |\n| 0002 | b | worker |\n"
    assert P.check_tasks(good) == []
    bad = good + "| 0003 | c | worker | extra |\n| 0001 | again | lead |\n"
    problems = P.check_tasks(bad)
    assert any("4 cells, the table has 3" in p for p in problems)
    assert any("task 0001 appears twice" in p for p in problems)


def test_precheck_real_app_group_rules(monkeypatch):
    import ci_real_app as R
    P = _pre()
    monkeypatch.setattr(R, "GROUPS", {"a": ["ui1", "ui2"], "b": ["ui2"]})
    problems = P.check_groups()
    assert any("'ui2' is in two groups" in p for p in problems)
    assert any("'pccheck' is in no group" in p for p in problems)


def test_pytest_groups_hold_every_file_once_and_are_balanced():
    import ci_groups
    files = [f"tests/test_{i}.py" for i in range(10)]
    secs = {"tests/test_0.py": 300, "tests/test_1.py": 200, "tests/test_2.py": 150}
    groups = ci_groups.pytest_groups(files, secs, n=4, selftest_secs=100)
    assert sorted(f for g in groups for f in g["files"]) == sorted(files)
    assert sum(g["selftest"] for g in groups) == 1
    assert max(g["secs"] for g in groups) <= 300 + 1e-9                    # the biggest file alone sets the pace
    assert groups == ci_groups.pytest_groups(list(reversed(files)), secs, n=4, selftest_secs=100)   # same split
    m = ci_groups.matrix_pytest() + ci_groups.matrix_demo()
    assert sorted(f for g in m for f in g["files"].split()) == ci_groups.test_files()


def test_demo_files_have_groups_of_their_own():
    """Task 0145: the files that open the made demo project run in the demo groups (after the one job that makes it),
    never in a plain group (which would have no made demo and make it again); demo groups have no packaged self-test."""
    import ci_groups
    demo = ci_groups.matrix_demo()
    files = [f for g in demo for f in g["files"].split()]
    assert "tests/test_demo_project.py" in files and "tests/test_demo_project_park.py" in files
    assert "tests/test_demo_vessel.py" not in files                        # the maker's own tests need no made demo
    assert all(g["name"].startswith("demo ") and not g["selftest"] for g in demo)
    plain = {f for g in ci_groups.matrix_pytest() for f in g["files"].split()}
    assert not plain & set(files)
    assert sum(g["selftest"] for g in ci_groups.matrix_pytest()) == 1


def test_docs_only_changes():
    P = _pre()
    diff_ver = ('diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -9 +9 @@\n-__version__ = "0.2.28"\n'
                '+__version__ = "0.2.29"\n')
    diff_code = diff_ver + '@@ -20 +20 @@\n-x = 1\n+x = 2\n'
    assert P.only_version_line(diff_ver) and not P.only_version_line(diff_code)
    docs = ["docs/USER-GUIDE.md", "CHANGELOG.md", "TASKS.md", "tasks/0036-ci-speed.md", "CLAUDE.md"]
    assert P.docs_only(docs, lambda f: "")
    assert P.docs_only(docs + [P.INIT, P.MANIFEST], lambda f: diff_ver)
    assert not P.docs_only(docs + [P.INIT], lambda f: diff_code)
    assert not P.docs_only(docs + ["fresing_render/blender/ui.py"], lambda f: "")
    assert not P.docs_only(docs + [".github/workflows/tests.yml"], lambda f: "")
    assert not P.docs_only([], lambda f: "")


def test_repository_basics_are_documents():
    """Task 0205: the licence, notices, security policy, contributing file and issue forms run as docs runs."""
    P = _pre()
    for f in ("LICENSE", "THIRD-PARTY-NOTICES.md", "SECURITY.md", "CONTRIBUTING.md", "docs/COMPANY-USE.md",
              ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/config.yml"):
        assert P.is_doc_path(f), f
    assert P.docs_only(["LICENSE", ".github/ISSUE_TEMPLATE/feature_request.yml", "SECURITY.md"], lambda f: "")
    # anything else under .github (the workflows) and code stay full runs
    assert not P.is_doc_path(".github/workflows/tests.yml")
    assert not P.is_doc_path(".github/CODEOWNERS")
    assert not P.docs_only(["LICENSE", ".github/workflows/tests.yml"], lambda f: "")
    assert not P.is_doc_path("fresing_render/LICENSE")


def _run(i, tree="t1", conclusion="success"):
    return {"id": i, "status": "completed", "conclusion": conclusion, "created_at": f"2026-11-06T1{i}:00:00Z",
            "head_branch": "task/x", "head_sha": f"sha{i}", "head_commit": {"tree_id": tree}}


def _job(name, conclusion="success"):
    return {"name": name, "conclusion": conclusion}


NEW_JOBS = [_job("Precheck (version, counts, groups; picks the mode)"), _job("Linux - test suite 1"),
            _job("Build the Windows installer zip"), _job("Windows - install + self-test"), _job("Tests - verdict")]
OLD_JOBS = [_job("Linux - test suite + packaged self-test"), _job("Linux - real app (simulated clicks)"),
            _job("Build the Windows installer zip"), _job("Windows - install + self-test")]


def test_a_run_is_proven_only_when_its_tests_are_green():
    P = _pre()
    assert P.run_is_proven(_run(1), NEW_JOBS)[0]
    assert P.run_is_proven(_run(1), OLD_JOBS)[0]                          # runs from before task 0036
    assert not P.run_is_proven(_run(1, conclusion="failure"), NEW_JOBS)[0]
    assert not P.run_is_proven(_run(1), NEW_JOBS[:-1] + [_job("Tests - verdict", "failure")])[0]
    assert not P.run_is_proven(_run(1), [j for j in OLD_JOBS if "real app" not in j["name"]])[0]
    assert not P.run_is_proven(_run(1), [j for j in NEW_JOBS if "Build" not in j["name"]])[0]


def test_reuse_finds_the_green_run_of_the_same_tree():
    P = _pre()
    arts = [{"name": n, "expired": False} for n in P.ARTIFACTS]
    runs = [_run(1, "t1"), _run(2, "t2"), _run(3, "t1")]

    def api(path, jobs=NEW_JOBS, arts=arts):
        if "/runs?" in path:
            return {"workflow_runs": runs}
        if path.endswith("jobs?per_page=100"):
            return {"jobs": jobs}
        return {"artifacts": arts}
    run, _ = P.find_proven_run("t1", "99", api)
    assert run["id"] == 3                                                  # the newest of the two with tree t1
    assert P.find_proven_run("t1", "3", api)[0]["id"] == 1                 # never its own run
    assert P.find_proven_run("t9", "99", api)[0] is None
    run, why = P.find_proven_run("t1", "99", lambda p: api(p, arts=arts[:1]))
    assert run is None and "installer files are gone" in why
    assert P.find_proven_run("t1", "99", lambda p: api(p, jobs=NEW_JOBS[:2]))[0] is None


def test_release_verifies_the_reused_run(monkeypatch):
    import release_tools
    run = _run(5, "tree5")

    def api(path):
        return {"jobs": NEW_JOBS} if path.endswith("jobs?per_page=100") else run
    assert release_tools.verify_run("5", "tree5", api)[0]
    ok, why = release_tools.verify_run("5", "other", api)
    assert not ok and "tree" in why


def test_pytest_summary_seconds_per_file(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text('<testsuites><testsuite tests="3" time="5">'
                   '<testcase classname="tests.test_a" name="x" time="1.5"/>'
                   '<testcase classname="tests.test_a.TestThing" name="y" time="2"/>'
                   '<testcase classname="tests.test_b" name="z" time="0.25"/></testsuite></testsuites>')
    assert ci_pytest_summary.file_seconds(str(xml)) == {"tests/test_a.py": 3.5, "tests/test_b.py": 0.2}


def test_ci_status_flags_a_slow_job():
    import ci_status
    rec = {"Linux - real app ui": 8.0}
    assert ci_status.slow_note("Linux - real app ui", 11.9, rec) == ""
    assert "SLOW: usually 8.0 min" in ci_status.slow_note("Linux - real app ui", 12.5, rec)
    assert ci_status.slow_note("Precheck", 0.9, {"Precheck": 0.3}) == ""            # under a minute: never
    assert ci_status.slow_note("new job", 30, rec) == ""                            # nothing recorded yet


def test_ci_status_merge_commit_is_never_a_task_list_only_commit():
    import ci_status
    only = [{"filename": "TASKS.md"}, {"filename": "tasks/0060-x.md"}]
    assert ci_status.commit_only_task_list({"parents": [{}], "files": only})
    # a merge commit: its diff against the first parent is only the task list, but GitHub ran the tests
    assert not ci_status.commit_only_task_list({"parents": [{}, {}], "files": only})
    assert not ci_status.commit_only_task_list({"parents": [{}], "files": only + [{"filename": "docs/a.md"}]})
    assert not ci_status.commit_only_task_list({"parents": [{}], "files": []})


def test_pc_check_lines_split_over_the_runners():
    """Task 0063: the two Linux halves of the PC check (Full) add up to every Full line; Windows runs a subset
    of them, and it keeps the lines that depend on Windows itself."""
    import ci_pccheck_lines as pl
    full = pl.full_ids()
    assert len(full) >= 46 and len(set(full)) == len(full)
    one, two = pl.ids_for("linux1"), pl.ids_for("linux2")
    assert set(one) | set(two) == set(full) and set(one) & set(two) == set(pl.LINUX2_NEEDS)
    win = pl.ids_for("windows")
    assert set(win) < set(full) and set(pl.WINDOWS_SKIPS) == set(full) - set(win)
    for keep in ("app.start", "import.crane", "render.cpu", "queue.frame_shown", "updates.check"):
        assert keep in win, keep
    assert pl.problems() == []
    assert pl.problems([i for i in full if i != "video.labels"]) != []          # a name that is no line any more is noticed


def test_ci_status_keeps_the_slowest_of_the_last_runs():
    import ci_status
    times = {"pytest_files": {"tests/test_a.py": 50.0}}
    ci_status.merge_file_times(times, {"tests/test_a.py": 20.0, "tests/test_b.py": 5.0})
    assert times["pytest_files"] == {"tests/test_a.py": 50.0, "tests/test_b.py": 5.0}
    for secs in (30.0, 25.0, 22.0):                      # the 50 s leaves the last three runs
        ci_status.merge_file_times(times, {"tests/test_a.py": secs})
    assert times["pytest_files"]["tests/test_a.py"] == 30.0
    assert times["pytest_history"]["tests/test_a.py"] == [30.0, 25.0, 22.0]


# ------------------------------------------------- task 0170: the mode of a task's last push (merge main + report)

class _Repo:
    """A small git repository in tmp_path; commits named by a label."""

    def __init__(self, path):
        import subprocess
        self.path, self.sha = str(path), {}
        self._sp = subprocess
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.commit("M0", {"fresing_render/__init__.py": '__version__ = "0.2.10"\nX = 1\n',
                           "fresing_render/blender_manifest.toml": 'version = "0.2.10"\n',
                           "fresing_render/a.py": "a = 1\n", "TASKS.md": "t0\n", "CHANGELOG.md": "c\n"})

    def git(self, *args):
        return self._sp.run(["git", "-C", self.path, *args], capture_output=True, text=True,
                            check=True).stdout.strip()

    def commit(self, label, files):
        for rel, text in files.items():
            full = os.path.join(self.path, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", label)
        self.sha[label] = self.git("rev-parse", "HEAD")
        return self.sha[label]

    def merge(self, label, other):
        self.git("merge", "-q", "--no-ff", "-m", label, other)
        self.sha[label] = self.git("rev-parse", "HEAD")
        return self.sha[label]


class _Runs:
    """Fake GitHub API: runs per commit. state: green | docs-green | reuse | red | cancelled | running-full |
    running-docs (turns docs-green after `turns` polls)."""

    def __init__(self, states, turns=99):
        self.states, self.turns, self.polls, self.ids = dict(states), turns, 0, {}

    def _run(self, sha, state):
        i = self.ids.setdefault(sha, 1000 + len(self.ids))
        if state == "running-docs" and self.polls >= self.turns:
            state = "docs-green"
        done = not state.startswith("running")
        concl = {"red": "failure", "cancelled": "cancelled"}.get(state, "success") if done else None
        return {"id": i, "status": "completed" if done else "in_progress", "conclusion": concl, "head_sha": sha,
                "created_at": "2026-11-16T10:00:00Z", "head_branch": "task/x", "head_commit": {"tree_id": "none"},
                "_state": state}

    def _jobs(self, state):
        pre = _job("Precheck (version, counts, groups; picks the mode)")
        if state in ("green", "red", "cancelled"):
            c = {"red": "failure", "cancelled": "cancelled"}.get(state, "success")
            return [pre, _job("Linux - test suite 1", c), _job("Build the Windows installer zip"),
                    _job("Tests - verdict", c)]
        if state == "docs-green":
            return [pre, _job("Linux - test suite 1", "skipped"), _job("Build the Windows installer zip"),
                    _job("Tests - verdict")]
        if state == "reuse":
            return [pre, _job("Linux - test suite 1", "skipped"), _job("Build the Windows installer zip", "skipped"),
                    _job("Tests - verdict")]
        if state == "running-docs":
            return [pre, _job("Linux - test suite 1", "skipped"), _job("Build the Windows installer zip", None),
                    _job("Tests - verdict", None)]
        return [pre, _job("Linux - test suite 1", None), _job("Build the Windows installer zip", None)]

    def __call__(self, path):
        import re
        if "status=success&per_page=100" in path:                     # reuse: no tree matches in these cases
            return {"workflow_runs": []}
        m = re.search(r"head_sha=([0-9a-f]+)", path)
        if m:
            sha = m.group(1)
            return {"workflow_runs": [self._run(sha, self.states[sha])] if sha in self.states else []}
        m = re.search(r"runs/(\d+)/jobs", path)
        if m:
            sha = {v: k for k, v in self.ids.items()}[int(m.group(1))]
            return {"jobs": self._jobs(self._run(sha, self.states[sha])["_state"])}
        raise AssertionError(path)

    def sleep(self, s):
        self.polls += 1


@pytest.fixture
def repo(tmp_path, monkeypatch):
    P = _pre()
    monkeypatch.setattr(P, "ROOT", str(tmp_path))
    return _Repo(tmp_path)


def _decide(repo, runs, sha, before, ref="refs/heads/main"):
    P = _pre()
    return P.decide("push", ref, repo.sha.get(sha, sha), repo.sha.get(before, before), "1", runs, sleep=runs.sleep)


def _task_branch(r):
    """main M0; the task's code B1 on its branch (ran green); main moves by the task list only (T1)."""
    r.git("checkout", "-q", "-b", "task")
    r.commit("B1", {"fresing_render/a.py": "a = 2\n", "CHANGELOG.md": "c\nnew\n"})
    r.git("checkout", "-q", "main")
    r.commit("T1", {"TASKS.md": "t1\n", "tasks/0099-x.md": "brief\n"})


def test_mode_merge_of_main_and_report_is_docs(repo):
    """Run 43894557321 / 43913541189: the green branch commit, then 'merge main' + report pushed to main."""
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.commit("R", {"tasks/0170-x.md": "report\n", "TASKS.md": "t2\n"})
    runs = _Runs({repo.sha["M0"]: "green", repo.sha["B1"]: "green"})
    mode, _, why = _decide(repo, runs, "R", "T1")
    assert mode == "docs" and repo.sha["B1"][:7] in why, why
    # the old rule walked main's first parents only: M0 (before the task's code) -> full
    assert "TASKS.md" in why


def test_mode_report_on_a_fast_forward_is_docs(repo):
    """The code merge was a fast-forward (its run on main a reuse run); the report comes on top of it."""
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "task")
    repo.commit("R", {"tasks/0170-x.md": "report\n"})
    # B2 ran full on the branch; on main the same commit got a reuse run (no build): the branch run proves it
    runs = _Runs({repo.sha["B2"]: "green"})
    assert _decide(repo, runs, "R", "B2")[0] == "docs"
    runs = _Runs({repo.sha["B2"]: "reuse"})                      # only a reuse run: not proven by itself
    assert _decide(repo, runs, "R", "B2")[0] == "full"


def test_mode_main_moved_by_the_task_list_only(repo):
    """Run 43899493566: main moved by TASKS.md pushes (no runs) between the green code and the report."""
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "task")
    repo.commit("T2", {"TASKS.md": "t3\n"})                     # the lead's push: no run
    repo.commit("T3", {"tasks/0100-y.md": "brief\n"})
    repo.commit("R", {"TASKS.md": "t4\n"})
    runs = _Runs({repo.sha["B2"]: "green"})
    mode, _, why = _decide(repo, runs, "R", "T3")
    assert mode == "docs" and repo.sha["B2"][:7] in why, why


def test_mode_a_merge_that_brings_other_code_is_full(repo):
    _task_branch(repo)
    repo.commit("M1", {"fresing_render/b.py": "b = 1\n"})        # another task's code on main, green there
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.commit("R", {"tasks/0170-x.md": "report\n"})
    runs = _Runs({repo.sha["M0"]: "green", repo.sha["B1"]: "green", repo.sha["M1"]: "green"})
    mode, _, why = _decide(repo, runs, "R", "M1")
    assert mode == "full" and "code changed" in why, why


@pytest.mark.parametrize("state", ["red", "cancelled", "running-full", "reuse"])
def test_mode_a_candidate_that_did_not_run_green_gives_full(repo, state):
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.commit("R", {"tasks/0170-x.md": "report\n"})
    runs = _Runs({repo.sha["M0"]: "green", repo.sha["B1"]: state})
    assert _decide(repo, runs, "R", "T1")[0] == "full"
    assert runs.polls == 0                                        # a full run still going is not waited for


def test_mode_waits_for_a_docs_run_still_going(repo):
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    repo.merge("B2", "main")
    repo.commit("R", {"tasks/0170-x.md": "report\n"})
    runs = _Runs({repo.sha["B2"]: "running-docs"}, turns=3)
    mode, _, why = _decide(repo, runs, "R", "T1")
    assert mode == "docs" and runs.polls == 3, (mode, why)
    runs = _Runs({repo.sha["B2"]: "running-docs"}, turns=999)    # never ends: bounded wait, then full
    mode, _, why = _decide(repo, runs, "R", "T1")
    assert mode == "full" and runs.polls == _pre().WAIT_LIMIT // _pre().WAIT_STEP and "stopped waiting" in why


def test_mode_version_line_only_is_docs_other_lines_full(repo):
    _task_branch(repo)
    repo.git("checkout", "-q", "task")
    base = repo.sha["B1"]
    repo.commit("V", {"fresing_render/__init__.py": '__version__ = "0.2.11"\nX = 1\n',
                      "fresing_render/blender_manifest.toml": 'version = "0.2.11"\n', "CHANGELOG.md": "c\n0.2.11\n"})
    runs = _Runs({base: "green"})
    assert _decide(repo, runs, "V", "B1", ref="refs/heads/task")[0] == "docs"
    repo.commit("W", {"fresing_render/__init__.py": '__version__ = "0.2.11"\nX = 2\n'})
    assert _decide(repo, runs, "W", "V", ref="refs/heads/task")[0] == "full"


# ------------------------------------------------- task 0171: Windows in two parts, lane runs while a task is built

def _groups():
    import ci_groups
    return ci_groups


def _plan_files(plan, key="pytest"):
    return {f for g in plan[key] for f in g["files"].split()}


def test_lane_plan_web3d_picks_the_web_tests_not_milling():
    G = _groups()
    plan = G.lane_plan(["fresing_render/blender/web3d.py"])
    assert not plan["full"], plan["why"]
    files = _plan_files(plan)
    assert "tests/test_web3d.py" in files and "tests/test_machining.py" not in files and "tests/test_air.py" not in files
    assert not plan["realapp"] and not plan["windows"] and not plan["build"]     # no milling, no installer
    assert len(plan["pytest"]) < G.PYTEST_GROUPS
    plan = G.lane_plan(["fresing_render/blender/ops_web3d.py"])                # ops_x: the tests of x too
    assert "tests/test_web3d.py" in _plan_files(plan)


def test_lane_plan_machining_picks_the_milling_real_app_group():
    plan = _groups().lane_plan(["fresing_render/blender/machining.py"])
    assert not plan["full"] and "tests/test_machining.py" in _plan_files(plan)
    assert [g["name"] for g in plan["realapp"]] == ["machines"]
    assert "tests/test_web3d.py" not in _plan_files(plan)


@pytest.mark.parametrize("path", ["fresing_render/blender/props.py", "fresing_render/blender/ui.py",
                                  "fresing_render/blender/tour.py", "fresing_render/pccheck/checks.py",
                                  "tools/ci_precheck.py", ".github/workflows/tests.yml", "installer/Install.bat",
                                  "tools/build_release.py", "fresing_render/importer/step_reader.py"])
def test_lane_plan_shared_files_give_full(path):
    plan = _groups().lane_plan(["fresing_render/blender/web3d.py", path])
    assert plan["full"] and path in plan["why"][0]


def test_lane_plan_a_file_no_test_names_gives_full():
    name = "zz" + "_never_named"                       # built here, or this file would name it
    plan = _groups().lane_plan([f"fresing_render/blender/{name}.py"])
    assert plan["full"] and "named by no test" in plan["why"][0]


def test_lane_plan_windows_code_builds_and_runs_part_a():
    G = _groups()
    plan = G.lane_plan(["fresing_render/core/updates.py"])
    assert not plan["full"] and plan["build"] and [p["part"] for p in plan["windows"]] == ["a"]
    assert [p["part"] for p in G.matrix_windows()] == ["a", "b"]
    plan = G.lane_plan(["fresing_render/selftest.py"])
    assert any(g["selftest"] for g in plan["pytest"])                          # the packaged self-test too


def test_lane_plan_documents_and_test_files():
    G = _groups()
    plan = G.lane_plan(["docs/USER-GUIDE.md", "TASKS.md", "tasks/0171-ci-shorter-runs.md"])
    assert not plan["full"] and "tests/test_user_guide.py" in _plan_files(plan)
    plan = G.lane_plan(["tests/test_web3d.py"])
    assert _plan_files(plan) == {"tests/test_web3d.py"}
    plan = G.lane_plan(["tests/test_demo_project_park.py"])                    # a demo file: in a demo group
    assert not plan["pytest"] and _plan_files(plan, "demo") == {"tests/test_demo_project_park.py"}
    assert G.lane_plan(["TASKS.md"])["full"]                                    # nothing to run: not a lane run


def test_lane_plan_every_group_is_valid():
    """The lane plan's real-app groups are GROUPS' own; its pytest groups hold each picked file once."""
    import ci_real_app
    G = _groups()
    plan = G.lane_plan(["fresing_render/core/clash.py"])
    for g in plan["realapp"]:
        assert ci_real_app.GROUPS[g["name"]] == g["tests"].split(",")
        assert not set(g["tests"].split(",")) & G.LANE_SKIP_REALAPP
    files = [f for k in ("pytest", "demo") for g in plan[k] for f in g["files"].split()]
    assert len(files) == len(set(files)) and set(files) <= set(G.test_files())
    assert all(g["minutes"] < 16 for g in plan["pytest"])


def test_a_lane_run_proves_nothing():
    P = _pre()
    lane = NEW_JOBS[:-1] + [_job("Tests - verdict (lane run - not a release check)")]
    ok, why = P.run_is_proven(_run(1), lane)
    assert not ok and "lane run" in why


def _lane_repo(r):
    """main M0 (+ a web3d module and its test); the task branch changes the module, version not raised."""
    r.commit("M1", {"fresing_render/web3d.py": "w = 1\n", "tests/test_web3d.py": "from fresing_render import web3d\n",
                    "tests/test_other.py": "x = 1\n"})
    r.git("checkout", "-q", "-b", "task")
    r.commit("L1", {"fresing_render/web3d.py": "w = 2\n"})


def test_mode_lane_while_the_version_is_not_raised(repo):
    _lane_repo(repo)
    runs = _Runs({repo.sha["M1"]: "green"})
    P = _pre()
    mode, _, why, plan = P.decide_plan("push", "refs/heads/task", repo.sha["L1"], repo.sha["M1"], "1", runs,
                                       sleep=runs.sleep, message="Work on web3d")
    assert mode == "lane" and "not raised" in why, why
    assert _plan_files(plan) == {"tests/test_web3d.py"} and not plan["windows"]


def test_mode_full_on_a_version_raise_full_run_word_main(repo):
    _lane_repo(repo)
    runs = _Runs({repo.sha["M1"]: "green"})
    P = _pre()

    def mode(sha, before, ref="refs/heads/task", message="x"):
        return P.decide_plan("push", ref, repo.sha[sha], repo.sha[before], "1", runs, sleep=runs.sleep,
                             message=message)

    assert mode("L1", "M1", message="Work [full run]")[0] == "full"
    assert mode("L1", "M1", message="Try [release rehearsal]")[0] == "full"
    repo.commit("V", {"fresing_render/__init__.py": '__version__ = "0.2.11"\nX = 1\n',
                      "fresing_render/blender_manifest.toml": 'version = "0.2.11"\n', "CHANGELOG.md": "c\n0.2.11\n"})
    m, _, why, _ = mode("V", "L1")
    assert m == "full" and "version raised" in why, why
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "task")
    assert mode("V", "M1", ref="refs/heads/main")[0] == "full"
    assert P.decide_plan("pull_request", "refs/pull/1/merge", repo.sha["L1"], "", "1", runs,
                         sleep=runs.sleep, message="x")[0] == "full"


def test_workflow_runs_windows_in_parts_and_judges_lane_runs():
    text = open(os.path.join(ROOT, ".github", "workflows", "tests.yml"), encoding="utf-8").read()
    assert "fromJSON(needs.precheck.outputs.windows)" in text and "-Part $env:PART" in text
    assert "lane run - not a release check" in text and "lane)  [ \"$PRE\" = \"success\" ] && lane_ok" in text
    ps = open(os.path.join(ROOT, "tools", "ci_windows_install.ps1"), encoding="utf-8-sig").read()
    assert '[ValidateSet("all", "a", "b")] [string]$Part = "all"' in ps
    for part in ("a", "b"):                                   # every verdict step of the job belongs to a part
        assert f"matrix.part.part == '{part}'" in text


def test_files_that_skip_on_github_never_share_a_pytest_group():
    """Task 0248: each group allows one skipped test; the files that skip one on GitHub by design go to different
    groups, however the times would pack them (here both would land in the lightest group)."""
    import ci_groups
    skippy = sorted(ci_groups.SKIPS_ON_GITHUB)
    files = [f"tests/test_big_{i}.py" for i in range(3)] + skippy
    secs = {f"tests/test_big_{i}.py": 600.0 for i in range(3)}
    secs.update({f: 1.0 for f in skippy})
    groups = ci_groups.pytest_groups(files, secs, n=4, selftest=False)
    owners = [g["name"] for f in skippy for g in groups if f in g["files"]]
    assert len(owners) == len(skippy) == len(set(owners))
    for g in ci_groups.matrix_pytest():                                     # and in the real split
        assert len(ci_groups.SKIPS_ON_GITHUB.intersection(g["files"])) <= 1, g["name"]

