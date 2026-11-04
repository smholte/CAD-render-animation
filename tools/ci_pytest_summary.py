"""Turn pytest's JUnit XML into a short, readable verdict for the GitHub run page.

    python tools/ci_pytest_summary.py test-results/pytest.xml

Writes the totals and every failing test (with the first lines of its error) to the job summary
($GITHUB_STEP_SUMMARY) and as error annotations. Always exits 0: pytest's own exit code decides.
"""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET


def summarize(path: str) -> tuple[str, list[tuple[str, str]]]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed: list[tuple[str, str]] = []
    skipped = 0
    seconds = sum(float(s.get("time", 0)) for s in suites)
    for case in root.iter("testcase"):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        for tag in ("failure", "error"):
            el = case.find(tag)
            if el is not None:
                msg = (el.get("message") or el.text or "").strip().splitlines()
                failed.append((name, " ".join(msg[:3])[:300]))
                break
        if case.find("skipped") is not None:
            skipped += 1
    passed = total - len(failed) - skipped
    head = (f"### Test suite (pytest): {'passed' if not failed else 'FAILED'}\n\n"
            f"{passed} passed, {len(failed)} failed, {skipped} skipped, {total} in all, "
            f"{seconds / 60:.1f} min\n")
    if failed:
        head += "\n| Failing test | Error |\n| --- | --- |\n"
        head += "".join(f"| `{n}` | {m.replace('|', '/')} |\n" for n, m in failed)
    return head, failed


def main() -> int:
    path = sys.argv[1]
    if not os.path.isfile(path):
        text, failed = ("### Test suite (pytest): no results file - pytest did not start "
                        "(see the step log)\n"), []
    else:
        text, failed = summarize(path)
    print(text)
    for name, msg in failed:
        print(f"::error title=Failing test {name}::{msg}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
