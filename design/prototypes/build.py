"""Assembles the clickable mock-up: the phone timeline plus the real app (static, with the test
data of tests/frontend/fixtures), with the round buttons of phone-chrome.* laid over it.

    uv run python design/prototypes/build.py [OUT]            # default: design/prototypes/_build
    python3 -m http.server --bind <LAN-IP> 8766 -d design/prototypes/_build
    → http://<LAN-IP>:8766/phone-timeline.html

Mock-up only: not part of the website, not tested.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from bundesdiff.export import build_frontend

HERE = Path(__file__).parent
FIXTURES = HERE.parent.parent / "tests" / "frontend" / "fixtures" / "data"


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    site = out / "site"
    shutil.copytree(FIXTURES, site / "data")
    build_frontend(site)
    index = site / "index.html"
    html = index.read_text()
    html = html.replace('<link rel="stylesheet" href="static/style.css">',
                        '<link rel="stylesheet" href="static/style.css">\n  <link rel="stylesheet" href="../phone-chrome.css">')
    html = html.replace("</body>", '  <script src="../phone-chrome.js"></script>\n</body>')
    index.write_text(html)
    for name in ("phone-timeline.html", "phone-timeline-data.js", "phone-chrome.css", "phone-chrome.js"):
        shutil.copy(HERE / name, out / name)


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "_build")
