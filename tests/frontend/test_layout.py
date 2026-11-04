"""Layout and accessibility on every kind of page, screen size and colour theme.

Each combination also saves a screenshot to test-results/screenshots/ to look through
after a change (in CI: the "frontend-screenshots" artifact).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe

from .centering import off_centre
from .conftest import PAGES, THEMES, VIEWPORTS

LAYOUT_JS = (Path(__file__).parent / "layout.js").read_text()
SCREENSHOTS = Path(__file__).parents[2] / "test-results" / "screenshots"


def _shot(page, name: str) -> Path:
    """Screenshot path; other browsers than Chromium get their name appended."""
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    browser = page.context.browser.browser_type.name
    return SCREENSHOTS / (f"{name}.png" if browser == "chromium" else f"{name}-{browser}.png")


def layout_issues(page) -> list[str]:
    return [f"[{i['check']}] {i['element']}: {i['detail']}" for i in page.evaluate(LAYOUT_JS)]


def open_help(page) -> None:
    """The help: in the navbar, on phones the round "?" button (PTL-7); waits until it has opened."""
    page.get_by_role("button", name="So funktioniert's", exact=True).first.click()
    page.locator("#dialog[open]").wait_for()
    settle(page)


def settle(page) -> None:
    """Waits until opening animations are over, so what is measured is what stays."""
    page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")


@pytest.mark.spec("A11Y-1", "A11Y-4", "A11Y-5", "A11Y-11", "RES-A1")
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("kind", PAGES)
def test_layout(app, page, kind, viewport, theme):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(PAGES[kind], theme=theme)
    page.screenshot(path=_shot(page, f"{kind}-{viewport}-{theme}"), full_page=True)
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("A11Y-1", "A11Y-4", "A11Y-5")
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_layout_with_everything_expanded(app, page, viewport):
    """Inline view, all unchanged sections shown, instruction tab open: the longest texts."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app("#/1/2026/314")
    page.get_by_role("button", name="Im Text markiert").click()
    page.locator("#only-changes").uncheck()
    for tab in page.locator(".tabs button:not(.active)").all():
        tab.click()
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("RES-A1", "A11Y-12")
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_old_data_notice_text_lines_up_with_intro_and_timeline(app, page, viewport):
    """Intro, notice and timeline card: one text edge on the left and right, like one column of print."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app(PAGES["old-data"])
    edges = page.evaluate("""() => [".welcome", ".old-data", ".timeline-page"].map((sel) => {
      const n = document.querySelector(sel), r = n.getBoundingClientRect(), s = getComputedStyle(n);
      return [r.left + parseFloat(s.borderLeftWidth) + parseFloat(s.paddingLeft),
              r.right - parseFloat(s.borderRightWidth) - parseFloat(s.paddingRight)];
    })""")
    lefts, rights = {round(left) for left, _ in edges}, {round(right) for _, right in edges}
    assert len(lefts) == 1 and len(rights) == 1, edges


@pytest.mark.spec("RES-5", "A11Y-5")
@pytest.mark.parametrize("spacing", [False, True])
def test_old_data_notice_keeps_the_date_and_short_words_whole(app, page, spacing):
    """„30. Oktober 2026“ is never torn apart (not after „30.“, not „Ok-tober“), and no word
    of five letters or less is hyphenated („im-mer“)."""
    app(PAGES["old-data"])
    if spacing:
        page.add_style_tag(content=TEXT_SPACING)
    torn = []
    for width in range(320, 1001, 4):
        page.set_viewport_size({"width": width, "height": 800})
        torn += [f"{word} at {width} px" for word in page.locator(".old-data").evaluate("""n => {
          const lines = (range) => new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size;
          const date = document.createRange();
          date.selectNodeContents(n.querySelector(".keep"));
          const out = lines(date) > 1 ? [date.toString()] : [];
          const walker = document.createTreeWalker(n, NodeFilter.SHOW_TEXT);
          for (let t; (t = walker.nextNode());) {
            for (const m of t.data.matchAll(/(?<!\\p{L})\\p{L}{2,5}(?!\\p{L})/gu)) {
              const r = document.createRange();
              r.setStart(t, m.index); r.setEnd(t, m.index + m[0].length);
              if (lines(r) > 1) out.push(m[0]);
            }
          }
          return out;
        }""")]
    assert not torn, torn


@pytest.mark.spec("RES-4", "A11Y-5")
@pytest.mark.parametrize("spacing", [False, True])
def test_data_date_line_keeps_its_parts_together(app, page, spacing):
    """„07:23 Uhr“ and „seit 27.10.2025“ stay together, no line starts with the separator „·“,
    and the last line is never a single word or syllable („täg-/lich“)."""
    app()
    if spacing:
        page.add_style_tag(content=TEXT_SPACING)
    page.locator("#data-date").filter(has_text="Uhr").wait_for()
    torn = []
    for width in range(320, 1001, 2):
        page.set_viewport_size({"width": width, "height": 800})
        torn += [f"{part} at {width} px" for part in page.locator("#data-date").evaluate("""n => {
          const text = n.firstChild, out = [];
          const tops = (from, to) => {
            const r = document.createRange();
            r.setStart(text, from); r.setEnd(text, to);
            return new Set([...r.getClientRects()].filter((b) => b.width > 0).map((b) => Math.round(b.top))).size;
          };
          for (const m of text.data.matchAll(/\\d\\d:\\d\\d\\s+Uhr|seit\\s+\\S+/gu)) {
            if (tops(m.index, m.index + m[0].length) > 1) out.push(m[0]);
          }
          for (const m of text.data.matchAll(/\\S\\s+·/gu)) {  // the word before „·“ and „·“ on one line
            if (tops(m.index, m.index + m[0].length) > 1) out.push(m[0]);
          }
          // the last line holds at least the last two words: the piece after the last ordinary
          // space has two words and stays on one line
          const tail = text.data.slice(text.data.lastIndexOf(" ") + 1);
          if (!/\\S\\s\\S/u.test(tail) || tops(text.data.length - tail.length, text.data.length) > 1) {
            out.push("last line: " + tail);
          }
          return out;
        }""")]
    assert not torn, torn


# WCAG 1.4.12: readers may widen spacing with their own style sheet; nothing may get cut off
TEXT_SPACING = """* { line-height: 1.5 !important; letter-spacing: .12em !important;
                     word-spacing: .16em !important; }
                 p { margin-bottom: 2em !important; }"""


@pytest.mark.spec("A11Y-2", "RES-A1")
@pytest.mark.parametrize("zoom", [200, 400])
@pytest.mark.parametrize("kind", ["start", "amendment", "old-data"])
def test_layout_when_zoomed(app, page, kind, zoom):
    """Browser zoom on a 1280 × 800 desktop: 200 % (WCAG 1.4.4) and 400 % (WCAG 1.4.10).

    Zooming makes the CSS viewport smaller by the same factor, which is what is tested here.
    """
    page.set_viewport_size({"width": 1280 * 100 // zoom, "height": 800 * 100 // zoom})
    app(PAGES[kind])
    page.screenshot(path=_shot(page, f"{kind}-zoom{zoom}"), full_page=True)
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


ZOOM_400 = {"width": 320, "height": 200}  # 1280×800 at 400 %: the navbar instead of the round buttons


@pytest.mark.spec("A11Y-3", "A11Y-2", "RES-A1")
@pytest.mark.parametrize("viewport", ["desktop", "small", "zoom-400"])
@pytest.mark.parametrize("kind", ["start", "amendment", "old-data"])
def test_layout_with_wide_text_spacing(app, page, kind, viewport):
    page.set_viewport_size(ZOOM_400 if viewport == "zoom-400" else VIEWPORTS[viewport])
    app(PAGES[kind])
    page.add_style_tag(content=TEXT_SPACING)
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("A11Y-1", "A11Y-4")
@pytest.mark.parametrize("viewport", ["desktop", "phone", "small"])
def test_layout_of_dialogs(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app("#/1/2026/309")
    open_help(page)
    page.screenshot(path=_shot(page, f"help-{viewport}"))
    assert not layout_issues(page), "\n".join(layout_issues(page))
    page.keyboard.press("Escape")
    page.locator(".how").first.click()
    settle(page)
    assert not layout_issues(page), "\n".join(layout_issues(page))
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Suchen").click()
    settle(page)
    page.screenshot(path=_shot(page, f"search-empty-{viewport}"))
    page.locator("#search-dialog").get_by_role("combobox").fill("steuer")
    page.screenshot(path=_shot(page, f"search-{viewport}"))
    assert not layout_issues(page), "\n".join(layout_issues(page))
    assert not off_centre(page), "\n".join(off_centre(page))


@pytest.mark.spec("A11Y-12")
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("viewport", ["desktop", "small"])
@pytest.mark.parametrize("kind", PAGES)
def test_framed_content_is_centred(app, page, kind, viewport, theme):
    """Buttons, badges, the logo: text or symbol in the middle of the frame (checked on pixels)."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app(PAGES[kind], theme=theme)
    issues = off_centre(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("A11Y-12")
@pytest.mark.parametrize("viewport", ["desktop", "small"])
def test_framed_content_in_dialogs_and_menus_is_centred(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app("#/1/2026/314")
    page.locator(".toc-toggle").click()
    assert not off_centre(page), "\n".join(off_centre(page))
    page.keyboard.press("Escape")
    open_help(page)
    assert not off_centre(page), "\n".join(off_centre(page))


# emoji and pictographic blocks: arrows that have an emoji form, misc. technical, geometric
# shapes with an emoji form, misc. symbols, dingbats, supplemental symbols, emoji planes
PICTOGRAPHS = re.compile(
    "[\u00a9\u00ae\u203c\u2049\u2122\u2139\u2194-\u2199\u21a9\u21aa\u231a\u231b\u2328\u23cf"
    "\u23e9-\u23fa\u24c2\u25aa\u25ab\u25b6\u25c0\u25fb-\u25fe\u2600-\u27bf\u2934\u2935"
    "\u2b05-\u2b55\u3030\u303d\u3297\u3299\ufe0f\U0001f000-\U0001faff]")


@pytest.mark.spec("A11Y-13")
def test_no_emoji_or_pictographs():
    static = Path(__file__).parents[2] / "bundesdiff" / "static"
    found = [f"{f.name}:{n}: {m.group()!r} in {line.strip()[:60]}"
             for f in sorted(static.iterdir()) if f.suffix in (".html", ".js", ".css")
             for n, line in enumerate(f.read_text().splitlines(), 1)
             for m in PICTOGRAPHS.finditer(line)]
    assert not found, "\n".join(found)


@pytest.mark.spec("A11Y-13")
@pytest.mark.parametrize("kind", PAGES)
def test_no_emoji_on_screen(app, page, kind):
    """Also nothing that comes in with the data or is generated."""
    app(PAGES[kind])
    text = page.locator("body").inner_text()
    assert not PICTOGRAPHS.findall(text)


@pytest.mark.spec("A11Y-6", "RES-A1")
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("kind", PAGES)
def test_accessibility(app, page, kind, theme):
    """axe-core: contrast, labels, landmarks, ARIA … – no serious or critical violations."""
    app(PAGES[kind], theme=theme)
    _assert_accessible(page)


@pytest.mark.spec("A11Y-6")
@pytest.mark.parametrize("theme", THEMES)
def test_accessibility_of_search_window(app, page, theme):
    app(theme=theme)
    page.get_by_role("button", name="Suchen").click()
    settle(page)  # axe measures colours: not while the window fades in
    _assert_accessible(page)
    page.locator("#search-dialog").get_by_role("combobox").fill("steuer")
    page.locator("#search-dialog").get_by_role("combobox").press("ArrowDown")
    _assert_accessible(page)


@pytest.mark.spec("A11Y-6")
def test_accessibility_of_help_dialog(app, page):
    app()
    open_help(page)
    _assert_accessible(page)


# every WCAG 2.2 rule up to level AA, plus axe's best practices
AXE_OPTIONS = {"runOnly": {"type": "tag", "values": [
    "wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]}}


def _assert_accessible(page) -> None:
    result = Axe().run(page, options=AXE_OPTIONS)
    # WCAG rules fail at any impact, best practices only when serious
    serious = [v for v in result.response["violations"]
               if v["impact"] in ("serious", "critical") or "best-practice" not in v["tags"]]
    report = "\n".join(
        f"[{v['impact']}] {v['id']}: {v['help']} – " + "; ".join(n["target"][0] for n in v["nodes"][:5])
        for v in serious)
    assert not serious, report
