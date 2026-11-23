"""Writes tasks/0288_page/index.html from page_template.html, with the prototype's output put in:

    ~/venv/bin/python tools/report_proto/make_page.py
"""

from __future__ import annotations

import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report_proto as R  # noqa: E402

OUT = os.path.join(R.ROOT, "tasks", "0288_page", "index.html")


def main() -> None:
    out = R.build_samples()
    summary = json.dumps(out["summary"], indent=1, ensure_ascii=False)
    fill = {
        "REPORT": html.escape(out["report"]),
        "REPORT_LEAKS": html.escape(", ".join(R.leaks(out["report"], out["secrets"])) or "none"),
        "TRACE_BEFORE": html.escape(out["trace_before"].rstrip()),
        "TRACE_AFTER": html.escape(out["trace_after"].rstrip()),
        "PCCHECK_BEFORE": html.escape(out["pccheck_before"].rstrip()),
        "SUMMARY": html.escape(summary),
        "SUMMARY_BYTES": f"{R.summary_bytes(out['summary']):,}",
        "SECRETS": html.escape(", ".join(out["secrets"])),
    }
    with open(os.path.join(HERE, "page_template.html"), encoding="utf-8") as fh:
        page = fh.read()
    for k, v in fill.items():
        page = page.replace("{{" + k + "}}", v)
    assert "{{" not in page, page[page.index("{{"):page.index("{{") + 40]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("wrote", OUT, len(page), "bytes")


if __name__ == "__main__":
    main()
