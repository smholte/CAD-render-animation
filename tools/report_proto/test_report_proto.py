"""Tests of the task-0288 prototype (study branch only):  ~/venv/bin/python -m pytest -q tools/report_proto

What they prove: the report and the weekly summary are built with the network blocked and the prototype imports no
network library; no made-up name, path or e-mail address of the samples survives; numbers come out in buckets; the
summary holds only the keys of its layout and stays small."""

from __future__ import annotations

import ast
import json
import os
import random
import socket
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report_proto as R  # noqa: E402

NETWORK = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "ssl", "asyncio", "xmlrpc", "webbrowser",
           "telnetlib", "poplib", "imaplib", "aiohttp", "httpx"}


def test_the_prototype_imports_no_network_library():
    tree = ast.parse(open(os.path.join(HERE, "report_proto.py"), encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    assert not names & NETWORK


@pytest.fixture
def no_network(monkeypatch):
    """Any attempt to open a connection or look up a host fails the test."""
    tried = []

    def refuse(*a, **k):
        tried.append(a)
        raise AssertionError("the network was used")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    yield tried
    assert not tried


def test_report_and_summary_are_built_with_the_network_blocked(no_network):
    out = R.build_samples()
    assert "Nothing has been sent" in out["report"]
    assert out["summary"]["schema"] == R.SCHEMA


def test_nothing_of_the_user_is_left():
    out = R.build_samples()
    texts = {"report": out["report"], "summary": json.dumps(out["summary"], ensure_ascii=False),
             "trace": out["trace_after"]}
    for name, text in texts.items():
        assert R.leaks(text, out["secrets"]) == [], name
        for word in ("jdevries", "WS-ENG-0412", "Acme", "FILESRV01", "pump_skid", "IMPELLER", "AppData", "my_helper"):
            assert word.lower() not in text.lower(), (name, word)


def test_the_samples_do_hold_what_must_be_taken_out():
    """The before texts really contain the names – else the test above would prove nothing."""
    out = R.build_samples()
    before = out["trace_before"] + out["pccheck_before"]
    assert R.leaks(before, out["secrets"])
    for word in ("jdevries", "WS-ENG-0412", "Klant Acme", "FILESRV01", "IMPELLER HOUSING 250-3"):
        assert word in before


def test_the_trace_keeps_what_helps():
    after = R.build_samples()["trace_after"]
    assert 'File "fresing_render/blender/joints.py", line 233, in create' in after
    assert "frame = _frame_from(members[0], axis)" in after            # the app's own source line
    assert 'File "<other file>", line 7, in fix' in after
    assert "print(" not in after                                        # a user's script: its line is dropped
    assert "'fr_rest_basis'" in after                                   # the app's own word stays
    assert after.splitlines()[-1].startswith("KeyError: '<text>'")


@pytest.mark.parametrize("seed", range(20))
def test_names_anywhere_in_a_trace_are_taken_out(seed):
    rnd = random.Random(seed)
    names = ["Kraan opbouw 7", "S. de Vries", "PROJECT-X42", "Bohrkopf links"]
    folder = rnd.choice([r"C:\Users\svries\Documents", r"D:\Klanten\Noord", r"\\nas01\cad", "/home/sv/work"])
    trace = "\n".join([
        "Traceback (most recent call last):",
        f'  File "{folder}\\{rnd.choice(names)}.py", line {rnd.randint(1, 999)}, in run',
        f"    do('{rnd.choice(names)}')",
        r'  File "C:\Program Files\FresingRender\portable\extensions\user_default\fresing_render\core\clash.py", '
        r'line 10, in check',
        "    raise RuntimeError(name)",
        f"RuntimeError: part '{rnd.choice(names)}' of {folder}\\{rnd.choice(names)}.step was not found"])
    after = R.strip_trace(trace, names)
    assert R.leaks(after, names) == [], after
    assert 'File "fresing_render/core/clash.py", line 10, in check' in after


def test_error_key_is_where_and_kind_only():
    key = R.error_key(R.samples()["trace"])
    assert key == {"where": "fresing_render/blender/joints.py:233 create", "type": "KeyError"}


@pytest.mark.parametrize("n, want", [(37, "under 100"), (100, "under 100"), (2310, "1,000–5,000"),
                                     (19999, "5,000–20,000"), (250000, "over 100,000"), ("x", "unknown")])
def test_part_buckets(n, want):
    assert R.bucket_parts(n) == want


@pytest.mark.parametrize("name, want", [
    ("GPU: NVIDIA GeForce RTX 3090", "NVIDIA RTX 30-series"), ("NVIDIA GeForce RTX 4070 Ti SUPER", "NVIDIA RTX 40-series"),
    ("NVIDIA GeForce GTX 1660", "NVIDIA GTX 16-series"), ("NVIDIA RTX A4000", "NVIDIA workstation"),
    ("AMD Radeon RX 7900 XTX", "AMD RX 7000-series"), ("Intel(R) Arc(TM) A770 Graphics", "Intel Arc A-series"),
    ("Intel(R) UHD Graphics 770", "Intel built-in"), ("none", "none"), ("", "none")])
def test_gpu_family(name, want):
    assert R.gpu_family(name) == want


@pytest.mark.parametrize("name, want", [
    ("AMD Ryzen 9 7950X 16-Core Processor", "AMD Ryzen 9"), ("AMD Ryzen Threadripper PRO 5965WX 24-Cores",
                                                            "AMD Threadripper"),
    ("12th Gen Intel(R) Core(TM) i7-12700K", "Intel Core i7"), ("Intel(R) Core(TM) Ultra 7 155H", "Intel Core Ultra 7"),
    ("Intel(R) Xeon(R) W-2245 CPU @ 3.90GHz", "Intel Xeon"), ("Some CPU", "other")])
def test_cpu_family(name, want):
    assert R.cpu_family(name) == want


def test_other_buckets():
    assert R.bucket_ram(63.7) == "64 GB" and R.bucket_ram(15.8) == "16 GB" and R.bucket_ram(300) == "over 256 GB"
    assert R.bucket_cores(24) == "17–32" and R.bucket_cores(4) == "1–4"
    assert R.two_digits(83.4) == 83 and R.two_digits(1234) == 1200 and R.two_digits(0.437) == 0.44
    assert R.windows_name("Windows 10 (10.0.26100)") == "Windows 11 24H2"
    assert R.windows_name("Windows 10 (10.0.19045)") == "Windows 10 22H2"


def test_week_counts_are_the_difference_and_survive_a_reset():
    now = {"functions": {"a.b": [12, 5], "c.d": [3, 5], "e.f": [2, 5]}}
    then = {"functions": {"a.b": [10, 4], "c.d": [3, 4], "e.f": [9, 4]}}       # e.f was reset in My usage
    assert R.week_counts(now, then) == {"a.b": 2, "e.f": 2}


SUMMARY_KEYS = {"schema", "asked", "id", "week", "app", "blender", "os", "cpu", "cores", "ram", "gpu", "sessions",
                "active_minutes", "functions", "speeds", "errors", "pccheck", "company_setup", "workspace"}


def test_the_summary_has_only_its_keys_and_stays_small():
    s = R.build_samples()["summary"]
    assert set(s) == SUMMARY_KEYS
    assert s["workspace"] == "own"                      # an own workspace's name is the user's: never sent
    assert set(s["active_minutes"]) <= set(R.U.STAGES)
    assert all(m % 15 == 0 for m in s["active_minutes"].values())
    assert R.summary_bytes(s) < 2048
    assert s["week"].count("-W") == 1 and ":" not in s["week"]           # a week, never a time of day
