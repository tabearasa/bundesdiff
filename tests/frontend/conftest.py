"""Browser tests for the frontend (Playwright + Chromium).

The tests run against the static build with the committed data in fixtures/, served
from a local HTTP server: no network access, no backend, the same data every time.
The clock is fixed, so relative dates ("gestern") do not change from day to day.

Every test fails if the page logs a JavaScript error or a request fails.
"""

from __future__ import annotations

import functools
import http.server
import shutil
import threading
from pathlib import Path

import pytest
from playwright.sync_api import Page

from bundesdiff.export import build_frontend

FIXTURES = Path(__file__).parent / "fixtures"
NOW = "2026-10-30T10:00:00"  # the newest fixture publication is from this day
# two days later: the list of publications (fetched 2026-10-30 06:23 UTC = 07:23 German time) is then more than
# 36 hours old and the start page says so (RES-5)
LATER = "2026-11-01T10:00:00"

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 834, "height": 1112},
    "phone": {"width": 390, "height": 844},
    "phone-landscape": {"width": 844, "height": 390},
    "small": {"width": 320, "height": 568},  # smallest phones; also 1280 px at 400 % zoom (WCAG 1.4.10)
}
THEMES = ["light", "dark"]
# one example of each kind of page
PAGES = {
    "start": "",
    "upcoming": "#/?ansicht=demnaechst",
    "filtered": "#/?art=Verordnung",
    "amendment": "#/1/2026/309",
    "mixed-status": "#/1/2026/314",
    "announcement": "#/1/2026/315",
    "not-analyzed": "#/1/2026/322",
    "gii-source": "#/1/2026/311",  # a law from gesetze-im-internet.de (source badge)
    "about": "#/ueber",
    "old-data": "#/",  # the start page, opened at LATER (see NOW_FOR_ROUTE)
}
# routes opened at another time than NOW; "#/" is reserved for "old-data" – other tests open
# the start page as "" (PAGES["start"])
NOW_FOR_ROUTE = {PAGES["old-data"]: LATER}


@pytest.fixture(scope="session")
def site(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("site")
    shutil.copytree(FIXTURES / "data", root / "data")
    build_frontend(root)
    return root


@pytest.fixture(scope="session")
def base_url(site: Path) -> str:
    """Overrides pytest-playwright's base_url: a local server for the static build."""
    handler = functools.partial(_QuietHandler, directory=str(site))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass


@pytest.fixture
def problems(page: Page) -> list[str]:
    """JavaScript errors, console errors and failed requests of the current test."""
    found: list[str] = []
    page.on("pageerror", lambda e: found.append(f"JavaScript error: {e}"))
    page.on("console", lambda m: found.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("requestfailed", lambda r: found.append(f"request failed: {r.url} ({r.failure})"))
    page.on("response", lambda r: found.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
    return found


@pytest.fixture
def app(page: Page, base_url: str, problems: list[str]):
    """Opens the app (a hash route like "#/1/2026/309") and waits until it has rendered."""
    page.clock.set_fixed_time(NOW)
    page.set_default_timeout(10_000)

    def open_(route: str = "", theme: str | None = None) -> Page:
        page.clock.set_fixed_time(NOW_FOR_ROUTE.get(route, NOW))
        if theme:
            page.add_init_script(f"localStorage.setItem('bundesdiff.theme', '{theme}')")
        page.goto(base_url + "index.html" + route)
        wait_rendered(page, route)
        if route == PAGES["old-data"]:  # the notice comes with meta.json, after the timeline
            page.locator(".old-data").wait_for()
        return page

    yield open_
    assert not problems, "\n".join(problems)


def wait_rendered(page: Page, route: str) -> None:
    page.locator("#main .timeline, #main .pub-header, #main .error-box, #main .about").first.wait_for()
    page.evaluate("document.fonts.ready")
