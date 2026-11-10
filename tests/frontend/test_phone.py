"""Phones: timeline with a lens and round buttons instead of the navbar (specs/004), the blurred
page behind windows (specs/005) and one shape language for all controls (specs/007)."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import PAGES, VIEWPORTS
from .test_layout import TEXT_SPACING, _assert_accessible, _shot, layout_issues

TABAK = "#/1/2026/309"
NEWEST = "1/2026/326"
UPCOMING = "#/?ansicht=demnaechst"


def on_phone(app, page: Page, route: str = "", viewport: str = "phone", **kwargs) -> Page:
    page.set_viewport_size(VIEWPORTS[viewport])
    return app(route, **kwargs)


def bar(page: Page):
    """The round buttons: on phones they are the main navigation."""
    return page.get_by_role("navigation", name="Hauptnavigation")


def card(page: Page):
    return page.locator(".tl-entry.tl-focus")


def menu(page: Page):
    return page.get_by_role("dialog", name="Menü")


def settled(page: Page, scrolled: bool = True) -> None:
    """Waits until the reader's scrolling and the lens's own glide have stopped and the card has grown."""
    if scrolled:  # the wheel scroll has really started (else "at the top" would count as settled)
        page.wait_for_function("scrollY > 100")
    page.wait_for_function("""() => {
        const at = scrollY;
        return new Promise(ok => setTimeout(() => ok(scrollY === at
            && document.querySelector('.tl-entry.tl-focus') !== null), 450));
    }""", timeout=8000)
    animations_done(page)


def scroll_down(page: Page, pixels: int) -> None:
    """Turns the mouse wheel in steps: one long turn scrolls only about a screen in Firefox."""
    page.mouse.move(200, 300)
    for _ in range(pixels // 400):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(40)


def middle_of(page: Page, locator) -> float:
    box = locator.bounding_box()
    return box["y"] + box["height"] / 2 - page.viewport_size["height"] / 2


def card_index(page: Page) -> int:
    return page.evaluate("[...document.querySelectorAll('.tl-entry')].findIndex(e => e.classList.contains('tl-focus'))")


def card_crosses_middle(page: Page) -> bool:
    """The card is the entry across the middle of the screen – or, where the middle falls on a
    date or between two entries, the entry nearest to it."""
    return page.evaluate("""() => {
        const mid = innerHeight / 2;
        const gap = e => { const r = e.getBoundingClientRect();
            return r.top <= mid && r.bottom >= mid ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid)); };
        const entries = [...document.querySelectorAll('.tl-entry')];
        const card = entries.find(e => e.classList.contains('tl-focus'));
        return gap(card) <= Math.min(...entries.map(gap)) + 1;
    }""")


def animations_done(page: Page) -> None:
    page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")


def scale(locator) -> float:
    return locator.evaluate("e => new DOMMatrix(getComputedStyle(e).transform).a")


# ---------------------------------------------------------------- layout

@pytest.mark.spec("PTL-1", "PTL-5")
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_phones_have_round_buttons_instead_of_the_navbar(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    expect(page.locator(".topbar")).to_be_hidden()
    buttons = bar(page).get_by_role("button")
    expect(buttons).to_have_count(3)
    for name in ("Menü", "So funktioniert's", "Suchen"):
        button = bar(page).get_by_role("button", name=name, exact=True)
        expect(button).to_be_visible()
        expect(button).to_have_text("")  # lines only, no visible word
        box = button.bounding_box()
        assert box["width"] >= 48 and box["height"] >= 48, f"{name}: {box['width']}×{box['height']}px"
        radius = button.evaluate("e => parseFloat(getComputedStyle(e).borderTopLeftRadius)")
        assert radius >= box["width"] / 2 - 0.5, f"{name} is not round"
        assert box["y"] + box["height"] <= page.viewport_size["height"] and \
            box["y"] > page.viewport_size["height"] - 110, f"{name} is not at the bottom"
    # menu on the left, help and search on the right
    xs = [bar(page).get_by_role("button", name=n, exact=True).bounding_box()["x"] for n in ("Menü", "So funktioniert's", "Suchen")]
    assert xs[0] < page.viewport_size["width"] / 2 < xs[1] < xs[2]


@pytest.mark.spec("PTL-1")
@pytest.mark.parametrize("size", [VIEWPORTS["phone-landscape"], VIEWPORTS["tablet"], {"width": 320, "height": 400}])
def test_wider_or_lower_screens_keep_the_navbar(app, page, size):
    page.set_viewport_size(size)
    app()
    expect(page.locator(".topbar")).to_be_visible()
    expect(page.locator(".fab-bar")).to_be_hidden()
    expect(card(page)).to_have_count(1)  # the timeline with the lens is on every screen


@pytest.mark.spec("PTL-10")
def test_start_page_has_a_masthead_with_the_name(app, page):
    on_phone(app, page)
    name = page.locator(".masthead-name")
    expect(name).to_have_text("bundesdiff")
    assert name.bounding_box()["y"] < page.locator("h1").bounding_box()["y"]
    assert name.evaluate("e => getComputedStyle(e).fontVariantCaps") in ("small-caps", "all-small-caps")
    scroll_down(page, 1200)
    expect(name).not_to_be_in_viewport()  # scrolls away
    # with the navbar the logo already names the site
    page.set_viewport_size(VIEWPORTS["desktop"])
    expect(name).to_be_hidden()


# ---------------------------------------------------------------- the lens

@pytest.mark.spec("PTL-2")
@pytest.mark.parametrize("viewport", ["phone", "desktop"])
def test_newest_publication_is_the_card_when_the_page_opens(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    expect(card(page)).to_have_count(1)
    expect(card(page)).to_have_attribute("data-id", NEWEST)
    # card and small entries show the same lines
    for entry in (card(page), page.locator(".tl-entry:not(.tl-focus):has(.tl-topics)").nth(3)):
        expect(entry.locator(".typ")).to_be_visible()
        expect(entry.locator(".tl-changes")).to_be_visible()
        expect(entry.locator(".tl-title")).to_be_visible()
        expect(entry.locator(".tl-topics")).to_be_visible()
    # the card stands out: a stronger frame, a shadow, its line to the axis in the accent colour
    look = "e => [getComputedStyle(e).borderTopColor, getComputedStyle(e).boxShadow, getComputedStyle(e.parentElement, '::before').backgroundColor]"
    big, small = card(page).evaluate(look), page.locator(".tl-entry:not(.tl-focus)").nth(3).evaluate(look)
    assert big[0] != small[0] and big[1] != "none" and big[2] != small[2], (big, small)


@pytest.mark.spec("PTL-2", "PTL-1")
@pytest.mark.parametrize("viewport", ["phone", "small", "desktop", "phone-landscape"])
def test_scrolling_makes_the_entry_in_the_middle_the_card(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    scroll_down(page, 1600)
    settled(page)
    expect(card(page)).to_have_count(1)
    assert card(page).get_attribute("data-id") != NEWEST
    assert abs(scale(card(page)) - 1) < 0.001
    assert card_crosses_middle(page), "the card is not the entry in the middle"
    # the further from the middle, the smaller; never below 88 %
    sizes = page.evaluate("""() => [...document.querySelectorAll('.tl-entry:not(.tl-focus)')]
        .map(e => [e.getBoundingClientRect(), new DOMMatrix(getComputedStyle(e).transform).a])
        .filter(([r]) => r.bottom > 0 && r.top < innerHeight)
        .map(([r, s]) => [Math.abs(r.top + r.height / 2 - innerHeight / 2), s])""")
    assert sizes, "no other entries on screen"
    assert all(0.88 - 1e-3 <= s <= 1 for _, s in sizes), sizes
    nearest, farthest = min(sizes), max(sizes)
    assert farthest[1] <= nearest[1], f"the far entry is larger: {sizes}"
    if viewport in ("phone", "desktop"):
        assert farthest[1] < nearest[1], f"the far entry is not smaller: {sizes}"


@pytest.mark.spec("PTL-2")
@pytest.mark.parametrize("viewport", ["phone", "desktop"])
def test_card_follows_while_scrolling_and_nothing_jumps(app, page, viewport):
    """The owner (2026-11-01): the card must not wait until the scrolling stops."""
    on_phone(app, page, viewport=viewport)
    page.evaluate("window.scrollTo(0, 3000)")
    page.wait_for_timeout(300)
    heights = page.locator(".tl-entry").evaluate_all("es => es.map(e => e.offsetHeight)")
    page.mouse.move(300, 300)
    seen, wrong = [], []
    for _ in range(12):  # small wheel steps, without a pause in which the scrolling could stop
        page.mouse.wheel(0, 90)
        page.wait_for_timeout(50)
        page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        seen.append(card_index(page))
        if not card_crosses_middle(page):
            wrong.append(page.evaluate("scrollY"))
    assert not wrong, f"while scrolling the card was not the entry in the middle at {wrong}"
    assert seen[-1] - seen[0] >= 2, f"the card did not move on while scrolling: {seen}"
    assert page.locator(".tl-entry").evaluate_all("es => es.map(e => e.offsetHeight)") == heights, \
        "an entry changed its height: the page jumps"


FRAMES_JS = """ms => new Promise(done => { const seen = [], end = performance.now() + ms;
    const step = () => {
        const es = [...document.querySelectorAll('.tl-entry')];
        seen.push({ card: es.findIndex(e => e.classList.contains('tl-focus')),
                    scales: es.map(e => new DOMMatrix(getComputedStyle(e).transform).a) });
        performance.now() < end ? requestAnimationFrame(step) : done(seen); };
    requestAnimationFrame(step); })"""


@pytest.mark.spec("PTL-2")
@pytest.mark.parametrize("viewport", ["phone", "small", "desktop"])
def test_no_entry_jumps_in_size_when_the_card_changes(app, page, viewport):
    """Where two entries meet in the middle, both are at full size: the card changes without a pop."""
    on_phone(app, page, viewport=viewport)
    # Start shortly before the middle of the screen reaches a large gap (between two dates): there a
    # lens that ignored the gaps would show the pop; across the small gaps of one day it hardly could.
    start = page.evaluate("""() => {
        const boxes = [...document.querySelectorAll('.timeline:not(.upcoming) .tl-entry')].map(e => {
            const r = e.getBoundingClientRect(), mid = r.top + r.height / 2 + scrollY;
            return { top: mid - e.offsetHeight / 2, bottom: mid + e.offsetHeight / 2 }; });
        for (let i = 1; i < boxes.length; i++) {
            const gap = boxes[i].top - boxes[i - 1].bottom, at = (boxes[i].top + boxes[i - 1].bottom) / 2;
            if (gap >= 40 && at - innerHeight / 2 > 1500) return Math.round(at - innerHeight / 2 - 300);
        }
        return null; }""")
    assert start is not None, "no gap of 40 px or more between two entries in the test data"
    page.evaluate(f"window.scrollTo(0, {start})")
    page.wait_for_timeout(300)
    worst, changes = 0, 0
    for _ in range(100):  # 6 px a frame: a slow, steady scroll
        before = page.evaluate(FRAMES_JS, 0)[0]
        # until the page has handled the scroll: WebKit sends the event of a script scroll some frames
        # later, and a fixed wait would count several steps as one
        # (a scroll that does not move the page sends no event: then fail instead of waiting forever)
        handled = page.evaluate("""new Promise(r => { addEventListener('scroll', () => requestAnimationFrame(
            () => requestAnimationFrame(() => r(true))), { once: true }); setTimeout(() => r(false), 2000);
            scrollBy(0, 6); })""")
        assert handled, "no scroll event within 2 s at scrollY {} (the page ends at {})".format(
            *page.evaluate("[scrollY, document.documentElement.scrollHeight - innerHeight]"))
        after = page.evaluate(FRAMES_JS, 0)[0]
        if before["card"] != after["card"]:  # where the two cells meet, both entries are at full size
            changes += 1
            pair = [x["scales"][i] for x in (before, after) for i in (before["card"], after["card"])]
            assert min(pair) >= 0.998, f"where the card changes an entry is not at full size: {pair}"
        worst = max(worst, *(abs(a - b) for a, b in zip(before["scales"], after["scales"])))
    assert changes >= 1, "the card never changed"
    assert worst <= 0.012, f"an entry changed its size by {worst:.3f} in one step of 6 px"


@pytest.mark.spec("PTL-2", "PTL-A1")
@pytest.mark.parametrize("viewport", ["phone", "desktop"])
@pytest.mark.parametrize("key", ["Tab", "Shift+Tab"])
def test_the_card_stays_on_the_entry_reached_with_the_keyboard(app, page, viewport, key):
    """While the page glides to it, the entries it passes do not light up on the way."""
    on_phone(app, page, viewport=viewport)
    entries = page.locator(".tl-entry")
    entries.nth(6).focus()
    page.keyboard.press(key)  # back and forth once: a glide in both directions
    page.wait_for_timeout(1200)
    page.keyboard.press(key)
    target = page.evaluate("[...document.querySelectorAll('.tl-entry')].indexOf(document.activeElement)")
    seen = [f["card"] for f in page.evaluate(FRAMES_JS, 1200)]
    assert set(seen) == {target}, f"the card went {seen}, the focus is on {target}"


@pytest.mark.spec("PTL-2", "PTL-1")
def test_resizing_the_window_keeps_the_lens_right(app, page):
    on_phone(app, page, viewport="desktop")
    page.evaluate("window.scrollTo(0, 3000)")
    page.wait_for_timeout(300)
    page.set_viewport_size({"width": 1440, "height": 500})  # only lower: the entry now in the middle
    page.wait_for_timeout(400)
    assert card_crosses_middle(page), "after a lower window the card is not the entry in the middle"
    before = card(page).get_attribute("data-id")
    page.set_viewport_size({"width": 800, "height": 700})  # narrower: the text flows anew
    page.wait_for_timeout(400)
    expect(card(page)).to_have_attribute("data-id", before)
    assert abs(middle_of(page, card(page))) <= 40, "the card did not come back to the middle"


@pytest.mark.spec("TL-4", "A11Y-8")
@pytest.mark.parametrize("viewport", ["desktop", "phone-landscape"])
def test_month_link_shows_the_month_below_the_navbar(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    page.get_by_role("navigation", name="Monate").get_by_role("link").nth(1).click()
    page.wait_for_timeout(900)
    heading = page.locator(".tl-month > h2:focus")
    expect(heading).to_have_count(1)
    bottom = page.locator(".topbar").bounding_box()
    assert heading.bounding_box()["y"] >= bottom["y"] + bottom["height"] - 0.5, "the month is under the navbar"


@pytest.mark.spec("PTL-2")
@pytest.mark.parametrize("viewport", ["small", "desktop"])
def test_nothing_in_an_entry_is_cut_off_with_an_ellipsis(app, page, viewport):
    """A clamp with "…" left a torn word before it ("Straßenver-…")."""
    on_phone(app, page, viewport=viewport)
    clamped = page.locator(".tl-entry *").evaluate_all("""es => es.filter(e => {
        const s = getComputedStyle(e);
        return (s.webkitLineClamp && s.webkitLineClamp !== 'none') || s.textOverflow === 'ellipsis'; }).length""")
    assert clamped == 0
    topics = page.locator(".timeline:not(.upcoming) .tl-topics").evaluate_all("es => es.map(e => e.textContent)")
    assert all(t.count("·") <= 3 for t in topics), [t for t in topics if t.count("·") > 3]
    many = [t for t in topics if "weitere" in t]
    assert many, "no entry with more than four topics in the test data"
    # "· 9 weitere Sachgebiete": never "1 weitere", the count stays with its word
    assert all(re.search(r"\u00a0· ([2-9]|\d\d+)\u00a0weitere Sachgebiete$", t) for t in many), many
    # a line never starts with the separator
    assert all(" · " not in t for t in topics), [t for t in topics if " · " in t]
    # "und -" / "zwangsverfahren", "Deutsche Telekom" / "AG": never split there
    assert any("\u00a0-\u2060zwangsverfahren" in t for t in topics), "no example in the test data"
    assert not [t for t in topics if re.search(r" (-\w|AG\b)", t)]


@pytest.mark.spec("PTL-2", "A11Y-3")
@pytest.mark.parametrize("spacing", [False, True])
@pytest.mark.parametrize("where", ["timeline", "search"])
def test_a_leading_hyphen_stays_with_its_word(app, page, spacing, where):
    """"Verwaltungsverfahren und -" / "zwangsverfahren": the line must not break after the hyphen."""
    on_phone(app, page, viewport="small")
    if spacing:
        page.add_style_tag(content=TEXT_SPACING)
    if where == "search":
        bar(page).get_by_role("button", name="Suchen").click()
        page.keyboard.type("zwangsverfahren")
        topics = page.locator(".so-detail", has_text="Verwaltungsverfahren").first
    else:
        topics = page.locator('.tl-entry[data-id="1/2026/305"] .tl-topics')
    # from the hyphen to the end of the word, across the <mark> of the search
    lines = topics.evaluate("""e => { const r = document.createRange(), text = e.textContent, i = text.indexOf(' -') + 1;
        const at = n => { const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let k = n;
            for (let t = w.nextNode(); t; t = w.nextNode()) { if (k <= t.length) return [t, k]; k -= t.length; } };
        r.setStart(...at(i)); r.setEnd(...at(text.indexOf('verfahren', i) + 9));
        return new Set([...r.getClientRects()].filter(q => q.width > 0).map(q => Math.round(q.top))).size; }""")
    assert lines == 1, "„-zwangsverfahren“ is split across lines"


@pytest.mark.spec("PTL-3", "PTL-1")
@pytest.mark.parametrize("viewport", ["phone", "small", "tablet", "desktop"])
def test_every_entry_has_its_own_line_to_the_time_axis(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    scroll_down(page, 2400)
    settled(page)
    lines = page.evaluate("""() => {
        const axis = [...document.querySelectorAll('.tl-mark')].map(m => {
            const r = m.getBoundingClientRect(); return r.left + r.width / 2; });
        return { axis, lines: [...document.querySelectorAll('.tl-entries > li')].map(li => {
            const s = getComputedStyle(li, '::before'), r = li.getBoundingClientRect();
            const a = li.querySelector('.tl-entry').getBoundingClientRect();
            const left = r.left + parseFloat(s.left), y = r.top + parseFloat(s.top);
            return { start: left, end: left + parseFloat(s.width), y, entryLeft: a.left, top: a.top, bottom: a.bottom,
                     shown: s.content !== 'none' && parseFloat(s.height) >= 1 };
        }).filter(l => l.bottom > 0 && l.top < innerHeight) };
    }""")
    axis = lines["axis"]
    assert max(axis) - min(axis) < 1, "the day marks are not on one axis"
    assert lines["lines"]
    for line in lines["lines"]:
        assert line["shown"], "an entry without its line"
        assert abs(line["start"] - axis[0]) <= 1, f"line starts at {line['start']}, the axis is at {axis[0]}"
        assert abs(line["end"] - line["entryLeft"]) <= 1.5, f"line ends at {line['end']}, the entry at {line['entryLeft']}"
        assert line["top"] - 1 <= line["y"] <= line["bottom"] + 1, "the line does not meet its entry"


@pytest.mark.spec("PTL-4")
@pytest.mark.parametrize("which", ["card", "small"])
def test_tapping_an_entry_opens_the_publication(app, page, which):
    on_phone(app, page)
    expect(page.get_by_text("Änderungen ansehen")).to_have_count(0)
    entry = card(page) if which == "card" else page.locator(".tl-entry:not(.tl-focus)").nth(1)
    target = entry.get_attribute("href")
    entry.click()
    expect(page).to_have_url(re.compile(re.escape(target) + "$"))
    expect(page.locator(".pub-header h1, .error-box").first).to_be_visible()


@pytest.mark.spec("PTL-4", "PTL-8")
@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_a_held_press_on_a_small_entry_opens_it(app, page, motion):
    """A real finger or mouse stays down for a moment: the entry must not slide away meanwhile."""
    page.emulate_media(reduced_motion=motion)
    on_phone(app, page)
    scroll_down(page, 2500)
    settled(page)
    target = page.evaluate("""() => { const mid = innerHeight / 2;
        const e = [...document.querySelectorAll('.tl-entry:not(.tl-focus)')].find(e => {
            const r = e.getBoundingClientRect(); return r.top > 40 && r.bottom < innerHeight - 120; });
        const r = e.getBoundingClientRect(); return { href: e.getAttribute('href'), x: r.left + 30, y: r.top + 20 }; }""")
    page.mouse.move(target["x"], target["y"])
    page.mouse.down()
    page.wait_for_timeout(150)
    page.mouse.up()
    expect(page).to_have_url(re.compile(re.escape(target["href"]) + "$"))


@pytest.mark.spec("PTL-2")
def test_turning_the_phone_keeps_the_card_on_screen(app, page):
    on_phone(app, page)
    scroll_down(page, 2500)
    settled(page)
    before = card(page).get_attribute("data-id")
    page.set_viewport_size(VIEWPORTS["phone-landscape"])
    page.wait_for_timeout(600)
    expect(page.locator(f'.tl-entry[data-id="{before}"]')).to_be_in_viewport()  # the place is kept
    page.set_viewport_size(VIEWPORTS["phone"])
    page.wait_for_timeout(400)
    expect(card(page)).to_have_count(1)
    expect(card(page)).to_have_attribute("data-id", before)
    expect(card(page)).to_be_in_viewport()
    assert abs(middle_of(page, card(page))) <= 40, "the card is not in the middle again"


@pytest.mark.spec("PTL-2", "A11Y-8")
@pytest.mark.parametrize("direction", [1, -1])
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_slow_wheel_steps_get_on(app, page, viewport, direction):
    """A slow turn of the wheel, a notch at a time: the glide must not pull the page back."""
    on_phone(app, page, viewport=viewport)
    page.evaluate("window.scrollTo(0, 4000)")
    page.wait_for_timeout(800)
    start = card_index(page)
    page.mouse.move(200, 300)
    for _ in range(10):
        page.mouse.wheel(0, 100 * direction)
        page.wait_for_timeout(300)
    page.wait_for_timeout(300)
    passed = (card_index(page) - start) * direction
    assert passed >= 3, f"ten notches of 100 px passed only {passed} entries"
    assert card_crosses_middle(page)


@pytest.mark.spec("PTL-2", "A11Y-8")
@pytest.mark.parametrize("focused", [False, True])
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_arrow_keys_get_on_and_the_card_never_goes_back(app, page, viewport, focused):
    on_phone(app, page, viewport=viewport)
    if focused:
        page.locator(".tl-months a").last.focus()
        for _ in range(3):
            page.keyboard.press("Tab")
    else:
        page.evaluate("window.scrollTo(0, 1500)")
    page.wait_for_timeout(900)
    seen = [card_index(page)]
    for _ in range(30):
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(300)
        seen.append(card_index(page))
    page.wait_for_timeout(400)
    seen.append(card_index(page))
    assert seen[-1] - seen[0] >= 2, f"30 arrow presses passed only {seen[-1] - seen[0]} entries: {seen}"
    assert all(b >= a for a, b in zip(seen, seen[1:])), f"the card went back and forth: {seen}"
    assert card_crosses_middle(page)


@pytest.mark.spec("PTL-2")
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_card_is_in_the_middle_after_page_down(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    page.evaluate("window.scrollTo(0, 1500)")
    page.wait_for_timeout(600)
    for _ in range(6):
        page.keyboard.press("PageDown")
        page.wait_for_timeout(700)
    page.wait_for_timeout(400)
    assert card_crosses_middle(page), "the card is not on screen"


@pytest.mark.spec("PTL-2", "A11Y-8")
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_page_down_gets_on_from_a_focused_entry(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    page.locator(".tl-months a").last.focus()
    for _ in range(4):
        page.keyboard.press("Tab")
    page.wait_for_timeout(900)
    start = page.evaluate("scrollY")
    for _ in range(5):
        page.keyboard.press("PageDown")
        page.wait_for_timeout(700)
    moved = page.evaluate("scrollY") - start
    height = page.viewport_size["height"]
    assert moved >= 2.5 * height, f"five times Page Down moved the page only {moved:.0f}px"


@pytest.mark.spec("PTL-2", "PTL-9")
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_nothing_glides_above_the_timeline(app, page, viewport):
    """The intro, the order switch and the filters are read where the reader stops."""
    on_phone(app, page, viewport=viewport)
    select = page.get_by_label("Art", exact=True)
    stop = select.evaluate("e => e.getBoundingClientRect().top + scrollY - innerHeight / 2")
    page.evaluate(f"window.scrollTo(0, {stop})")
    page.wait_for_timeout(700)
    assert abs(page.evaluate("scrollY") - stop) <= 2, "the page moved on by itself"
    expect(select).to_be_in_viewport()


@pytest.mark.spec("PTL-8", "A11Y-9")
def test_reduced_motion_keeps_every_entry_at_its_size(app, page):
    page.emulate_media(reduced_motion="reduce")
    on_phone(app, page)
    scroll_down(page, 1600)
    page.wait_for_timeout(600)
    sizes = page.evaluate("[...document.querySelectorAll('.tl-entry')].map(e => new DOMMatrix(getComputedStyle(e).transform).a)")
    assert all(abs(s - 1) < 1e-3 for s in sizes)
    expect(card(page)).to_have_count(1)
    bar(page).get_by_role("button", name="Menü").click()
    expect(menu(page)).to_be_visible()
    assert page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length") == 0


@pytest.mark.spec("PTL-9")
def test_order_and_filters_work_on_phones(app, page):
    on_phone(app, page)
    expect(page.get_by_role("button", name="Nach Veröffentlichung")).to_be_visible()
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    expect(page.locator(".tl-entry")).not_to_have_count(60)
    expect(card(page)).to_have_count(1)
    page.get_by_role("button", name="Was ändert sich demnächst?").click()
    expect(page.locator(".timeline.upcoming")).to_be_visible()
    expect(card(page)).to_have_count(0)  # the list of TL-6, no lens


# ---------------------------------------------------------------- the round buttons

@pytest.mark.spec("PTL-6", "PTL-A2", "NAV-2")
def test_menu_opens_above_its_button_and_leads_everywhere(app, page):
    on_phone(app, page, theme="light")
    button = bar(page).get_by_role("button", name="Menü")
    expect(button).to_have_attribute("aria-expanded", "false")
    button.click()
    expect(menu(page)).to_be_visible()
    expect(button).to_have_attribute("aria-expanded", "true")
    # its final place; while it opens: test_menu_never_covers_its_button_while_it_opens
    page.wait_for_function("document.getElementById('menu').getAnimations().every(a => a.playState !== 'running')")
    assert menu(page).bounding_box()["y"] + menu(page).bounding_box()["height"] <= button.bounding_box()["y"] + 1
    expect(menu(page).get_by_role("link", name="bundesdiff – Startseite")).to_be_visible()
    current = menu(page).get_by_role("link", name="Veröffentlichungen")
    expect(current).to_have_attribute("aria-current", "page")
    # focus is in the menu, Esc closes and returns it to the button
    assert page.evaluate("document.getElementById('menu').contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(menu(page)).to_be_hidden()
    expect(button).to_be_focused()
    expect(button).to_have_attribute("aria-expanded", "false")
    # the light/dark switch is in the menu
    button.click()
    switch = menu(page).get_by_role("switch", name="Dunkle Ansicht")
    expect(switch).to_have_attribute("aria-checked", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    # the close button, then a tap outside
    menu(page).get_by_role("button", name="Schließen").click()
    expect(menu(page)).to_be_hidden()
    button.click()
    page.mouse.click(page.viewport_size["width"] - 10, 10)
    expect(menu(page)).to_be_hidden()
    # "Über bundesdiff"
    button.click()
    menu(page).get_by_role("link", name="Über bundesdiff").click()
    expect(page.locator("#main h1")).to_have_text("Über bundesdiff")
    expect(menu(page)).to_be_hidden()
    button.click()
    expect(menu(page).get_by_role("link", name="Über bundesdiff")).to_have_attribute("aria-current", "page")


@pytest.mark.spec("PTL-6")
def test_menu_never_covers_its_button_while_it_opens(app, page):
    """The menu grows out of its button: in no frame of the opening does it reach over it."""
    on_phone(app, page, theme="light")
    button = bar(page).get_by_role("button", name="Menü")
    top = button.bounding_box()["y"]
    frames = page.evaluate("""() => new Promise(done => {
        const menu = document.getElementById('menu'), seen = [], end = performance.now() + 500;
        const step = () => { if (menu.open) seen.push(menu.getBoundingClientRect().bottom);
                             performance.now() < end ? requestAnimationFrame(step) : done(seen); };
        document.getElementById('fab-menu').click();
        step(); })""")
    assert frames, "the menu did not open"
    assert max(frames) <= top + 1, f"the menu reaches {max(frames) - top:.1f} px over its button: {frames}"


@pytest.mark.spec("PTL-7", "PTL-A2")
def test_help_and_search_buttons_open_their_windows(app, page):
    on_phone(app, page, TABAK)
    help_ = bar(page).get_by_role("button", name="So funktioniert's")
    help_.click()
    expect(page.locator("#dialog-title")).to_have_text("So funktioniert bundesdiff")
    page.keyboard.press("Escape")
    expect(help_).to_be_focused()
    search = bar(page).get_by_role("button", name="Suchen")
    search.click()
    expect(page.locator("#search-input")).to_be_focused()
    page.keyboard.press("Escape")
    expect(search).to_be_focused()


@pytest.mark.spec("PTL-11", "NAV-5")
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_back_arrow_returns_to_the_publication_on_the_timeline(app, page, viewport):
    on_phone(app, page, viewport=viewport)
    page.locator('.tl-entry[data-id="1/2026/309"]').click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    links = bar(page).locator("a, button")
    back = bar(page).get_by_role("link", name="Zurück zur Zeitleiste")
    expect(back).to_be_visible()
    assert links.first.get_attribute("aria-label") == "Zurück zur Zeitleiste", "the arrow is not on the far left"
    expect(back).to_have_text("")
    back.click()
    expect(card(page)).to_have_attribute("data-id", "1/2026/309")
    expect(card(page)).to_be_focused()
    settled(page)
    box = card(page).bounding_box()
    assert abs(box["y"] + box["height"] / 2 - page.viewport_size["height"] / 2) <= 40, "the card is not in the middle"
    # on the timeline itself there is nothing to go back to
    expect(back).to_be_hidden()


@pytest.mark.spec("PTL-11", "TL-4")
@pytest.mark.parametrize("view", ["", "&ansicht=demnaechst"])
def test_back_arrow_returns_to_the_filtered_timeline(app, page, view):
    on_phone(app, page, f"#/?art=Gesetz{view}")
    page.get_by_label("Art", exact=True).select_option("Verordnung")  # changed on the page: kept too
    page.locator('.tl-entry[data-id="1/2026/311"]').first.click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    bar(page).get_by_role("link", name="Zurück zur Zeitleiste").click()
    expect(page).to_have_url(re.compile(rf"#/\?art=Verordnung{re.escape(view)}$"))
    expect(page.get_by_label("Art", exact=True)).to_have_value("Verordnung")
    types = page.locator(".tl-entry .typ").all_inner_texts()
    assert types and {t.lower() for t in types} == {"verordnung"}
    if not view:
        expect(card(page)).to_have_attribute("data-id", "1/2026/311")


@pytest.mark.spec("NAV-1", "TL-4")
@pytest.mark.parametrize("viewport", ["phone", "desktop"])
def test_veroeffentlichungen_returns_to_the_filtered_timeline_and_the_logo_to_all(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app()
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    page.locator('.tl-entry[data-id="1/2026/309"]').click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    if viewport == "phone":
        bar(page).get_by_role("button", name="Menü").click()
        menu(page).get_by_role("link", name="Veröffentlichungen").click()
    else:
        page.locator(".navbar").get_by_role("link", name="Veröffentlichungen").click()
    expect(page).to_have_url(re.compile(r"#/\?art=Gesetz$"))
    expect(page.get_by_label("Art", exact=True)).to_have_value("Gesetz")
    expect(page.locator(".tl-entry")).to_have_count(16)
    # the logo: the start page with everything
    if viewport == "phone":
        bar(page).get_by_role("button", name="Menü").click()
        menu(page).get_by_role("link", name="bundesdiff – Startseite").click()
    else:
        page.locator(".navbar").get_by_role("link", name="bundesdiff – Startseite").click()
    expect(page.get_by_label("Art", exact=True)).to_have_value("")
    expect(page.locator(".tl-entry")).to_have_count(60)


@pytest.mark.spec("NAV-1")
def test_veroeffentlichungen_on_the_same_timeline_goes_to_its_top(app, page):
    page.set_viewport_size(VIEWPORTS["desktop"])
    app("#/?art=Verordnung")
    page.mouse.wheel(0, 1500)
    page.wait_for_function("scrollY > 500")
    page.locator(".navbar").get_by_role("link", name="Veröffentlichungen").click()
    page.wait_for_function("scrollY === 0")
    expect(page).to_have_url(re.compile(r"#/\?art=Verordnung$"))


@pytest.mark.spec("PTL-11")
def test_about_page_has_the_back_arrow_too(app, page):
    on_phone(app, page, PAGES["about"])
    expect(bar(page).get_by_role("link", name="Zurück zur Zeitleiste")).to_be_visible()


@pytest.mark.spec("PTL-11", "NAV-7")
def test_contents_bar_is_at_the_top_on_phones(app, page):
    on_phone(app, page, TABAK)
    page.locator("#art-1").evaluate("e => e.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(150)
    contents = page.get_by_role("navigation", name="Inhalt dieser Veröffentlichung")
    expect(contents).to_be_in_viewport()
    assert abs(contents.bounding_box()["y"]) <= 0.5


@pytest.mark.spec("PTL-A1")
@pytest.mark.parametrize("viewport", ["phone", "small"])
@pytest.mark.parametrize("kind", PAGES)
def test_end_of_every_page_can_be_scrolled_above_the_round_buttons(app, page, kind, viewport):
    on_phone(app, page, PAGES[kind], viewport=viewport)
    at_end = "scrollY + innerHeight >= document.documentElement.scrollHeight - 2"
    page.keyboard.press("End")
    # WebKit scrolls to the end smoothly: on a long page (a bill) and a slow CI runner that took
    # longer than a fixed wait. So wait for the end first, then check that the lens does not pull
    # the page back up.
    page.wait_for_function(at_end, timeout=5000)
    page.wait_for_timeout(900)
    assert page.evaluate(at_end), "the page was pulled back up from its end"
    top = page.evaluate("Math.min(...[...document.querySelectorAll('.fab-bar .fab')].filter(b => b.offsetParent).map(b => b.getBoundingClientRect().top))")
    end = page.evaluate("""() => {
        const all = [...document.querySelectorAll('#main *')].filter(e => {
            const r = e.getBoundingClientRect();
            return r.height > 0 && getComputedStyle(e).visibility !== 'hidden'
                && !e.closest('details:not([open]) > :not(summary)'); });
        return Math.max(...all.map(e => e.getBoundingClientRect().bottom)); }""")
    assert end <= top + 0.5, f"the end of the page ({end:.0f}px) stays under the round buttons ({top:.0f}px)"


@pytest.mark.spec("PTL-A1", "A11Y-8")
@pytest.mark.parametrize("viewport", ["phone", "small"])
@pytest.mark.parametrize("route", ["", TABAK])
def test_keyboard_focus_is_never_under_the_round_buttons(app, page, route, viewport):
    on_phone(app, page, route, viewport=viewport)
    top = page.evaluate("Math.min(...[...document.querySelectorAll('.fab-bar .fab')].filter(b => b.offsetParent).map(b => b.getBoundingClientRect().top))")
    hidden = []
    for _ in range(25):
        page.keyboard.press("Tab")
        page.wait_for_timeout(120 if route else 450)  # the lens may glide the card into the middle
        box = page.evaluate("""() => { const e = document.activeElement;
            if (!e || e === document.body || e.closest('.fab-bar')) return null;
            const r = e.getBoundingClientRect(); return { name: (e.innerText || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 40), top: r.top, h: r.height }; }""")
        if box and box["h"] and box["top"] + min(box["h"], 24) > top:
            hidden.append(f"{box['name']!r} at {box['top']:.0f}px, the buttons start at {top:.0f}px")
        elif box and box["h"] and box["top"] < -1:
            hidden.append(f"{box['name']!r} is cut off at the top ({box['top']:.0f}px)")
    assert not hidden, "\n".join(hidden)


@pytest.mark.spec("PTL-A1", "A11Y-8")
@pytest.mark.parametrize("viewport", ["phone", "small"])
@pytest.mark.parametrize("pub_id, key", [
    ("1/2026/326", "Tab"),         # the newest: the first entry reached from the filters
    ("1/2026/275", "Tab"),         # long titles: the card is nearly as high as a small phone
    ("1/2026/270", "Shift+Tab"),
])
def test_a_card_reached_with_the_keyboard_is_on_screen(app, page, viewport, pub_id, key):
    on_phone(app, page, viewport=viewport)
    entries = page.locator(".tl-entry")
    ids = entries.evaluate_all("es => es.map(e => e.dataset.id)")
    i = ids.index(pub_id)
    if i == 0:
        start = page.locator(".tl-months a").last
    else:
        start = entries.nth(i - 1 if key == "Tab" else i + 1)
    start.focus()
    page.keyboard.press(key)
    target = page.locator(f'.tl-entry[data-id="{pub_id}"]')
    expect(target).to_be_focused()
    page.wait_for_timeout(900)
    animations_done(page)
    box = target.bounding_box()
    top = page.evaluate("Math.min(...[...document.querySelectorAll('.fab-bar .fab')].filter(b => b.offsetParent).map(b => b.getBoundingClientRect().top))")
    assert box["y"] >= -1, f"the card starts above the screen ({box['y']:.0f}px)"
    shown = min(box["height"], top - 12)
    assert box["y"] + shown <= top + 1, \
        f"the card ({box['y']:.0f}–{box['y'] + box['height']:.0f}px) runs under the buttons ({top:.0f}px) although it would fit"


@pytest.mark.spec("A11Y-5")
def test_citation_keeps_vom_with_its_date(app, page):
    """"… Nr. 309 vom / 20.10.2026" reads badly: "vom" stays with the date."""
    on_phone(app, page, TABAK, viewport="small")
    cite = page.locator(".pub-header .fundstelle")
    lines = cite.evaluate("""e => { const t = e.firstChild, i = t.textContent.indexOf('vom');
        const r = document.createRange(); r.setStart(t, i); r.setEnd(t, t.textContent.length);
        return new Set([...r.getClientRects()].filter(q => q.width > 0).map(q => Math.round(q.top))).size; }""")
    assert lines == 1, "„vom“ and the date are split across lines"


@pytest.mark.spec("PTL-A3", "A11Y-6")
@pytest.mark.parametrize("route", ["", TABAK])
def test_phone_layout_is_accessible(app, page, route):
    on_phone(app, page, route)
    if not route:
        expect(page.locator("ol.timeline")).to_have_count(1)
        expect(page.locator(".timeline h2").first).to_have_text("Oktober 2026")
        expect(page.locator(".timeline h3").first).to_contain_text("30. Oktober")
    _assert_accessible(page)
    bar(page).get_by_role("button", name="Menü").click()
    animations_done(page)
    _assert_accessible(page)


@pytest.mark.spec("PTL-6", "A11Y-1", "A11Y-4")
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("viewport", ["phone", "small"])
def test_layout_of_the_menu(app, page, viewport, theme):
    on_phone(app, page, TABAK, viewport=viewport, theme=theme)
    bar(page).get_by_role("button", name="Menü").click()
    page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
    page.screenshot(path=_shot(page, f"menu-{viewport}-{theme}"))
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


# ---------------------------------------------------------------- spec 005: blurred background

BACKDROP = "e => { const s = getComputedStyle(e, '::backdrop'); return [s.backdropFilter, s.backgroundColor, s.animationName, s.animationDuration]; }"


def _open(page: Page, which: str) -> str:
    if which == "menu":
        bar(page).get_by_role("button", name="Menü").click()
        selector = "#menu"
    elif which == "help":
        page.get_by_role("button", name="So funktioniert's", exact=True).first.click()
        selector = "#dialog"
    else:
        page.get_by_role("button", name="Suchen").click()
        selector = "#search-dialog"
    page.locator(f"{selector}[open]").wait_for()
    animations_done(page)
    return selector


@pytest.mark.spec("SBL-1", "SBL-2")
@pytest.mark.parametrize("which", ["search", "help", "menu"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_page_behind_a_window_is_blurred_and_darkened(app, page, which, theme):
    if which == "menu":
        on_phone(app, page, theme=theme)
    else:
        app(TABAK, theme=theme)
    dialog = page.locator(_open(page, which))
    expect(dialog).to_be_visible()
    blur, colour, *_ = dialog.evaluate(BACKDROP)
    assert "blur(4px)" in blur, blur
    alpha = re.match(r"rgba?\((?:[\d.]+,\s*){3}([\d.]+)\)", colour)
    assert alpha and 0 < float(alpha.group(1)) < 1, f"backdrop {colour} is not a darkening veil"
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()


@pytest.mark.spec("SBL-3", "A11Y-9")
@pytest.mark.parametrize("motion", ["no-preference", "reduce"])
def test_blur_fades_in_quickly_or_not_at_all(app, page, motion):
    page.emulate_media(reduced_motion=motion)
    app(TABAK)
    dialog = page.locator(_open(page, "search"))
    _, _, name, duration = dialog.evaluate(BACKDROP)
    seconds = float(duration.rstrip("ms")) / (1000 if duration.endswith("ms") else 1)
    if motion == "reduce":
        assert name == "none" or seconds == 0
    else:
        assert name != "none" and 0 < seconds <= 0.15, (name, duration)


# ---------------------------------------------------------------- spec 007: shapes

FRAMED_JS = """() => {
  const px = v => parseFloat(v) || 0;
  const seen = c => c && c !== 'transparent' && !/rgba\\(.*,\\s*0\\)$/.test(c);
  const out = [];
  for (const e of document.querySelectorAll('button, a, select, input, summary, .segmented, .track')) {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    if (!r.width || !r.height || s.visibility === 'hidden' || e.closest('dialog:not([open]), [hidden]')) continue;
    if (e.matches('.fab, .badge, .skip-link, .brand, .tl-entry')) continue;
    const framed = ['Top', 'Right', 'Bottom', 'Left'].every(d => px(s[`border${d}Width`]) >= 1 && seen(s[`border${d}Color`]));
    if (!framed) continue;
    const bg = (() => { for (let a = e.parentElement; a; a = a.parentElement) {
        const c = getComputedStyle(a).backgroundColor; if (seen(c)) return c; } return 'rgb(255, 255, 255)'; })();
    out.push({ name: (e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + [...e.classList].join('.')) + ` "${(e.innerText || '').trim().slice(0, 20)}"`,
               radius: Math.max(...['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].map(c => px(s[`border${c}Radius`]))),
               border: s.borderTopColor, bg,
               state: e.matches('[aria-expanded=true], [aria-pressed=true], [aria-current], .active, :focus, :hover') });
  }
  return out;
}"""


def _rgb(colour: str) -> tuple[float, float, float]:
    r, g, b = (float(v) for v in re.findall(r"[\d.]+", colour)[:3])
    return r, g, b


def _contrast(a: str, b: str) -> float:
    def lum(c):
        ch = [v / 255 for v in _rgb(c)]
        ch = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _accent(page: Page) -> str:
    return page.evaluate("""() => { const d = document.createElement('i'); d.style.color = 'var(--accent)';
        document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; }""")


@pytest.mark.spec("SHAPE-1", "SHAPE-2")
@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
@pytest.mark.parametrize("route", ["", TABAK])
def test_framed_controls_are_rectangles_with_a_visible_frame(app, page, route, viewport, theme):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(route, theme=theme)
    page.mouse.move(0, 0)
    page.evaluate("document.activeElement && document.activeElement.blur()")
    accent = _accent(page)
    controls = page.evaluate(FRAMED_JS)
    assert controls, "no framed controls found"
    problems = []
    for c in controls:
        if c["radius"] > 3:
            problems.append(f"{c['name']}: corners of {c['radius']}px")
        if not c["state"] and _rgb(c["border"]) == _rgb(accent):
            problems.append(f"{c['name']}: oxblood frame at rest")
        elif _contrast(c["border"], c["bg"]) < 3:
            problems.append(f"{c['name']}: frame {c['border']} on {c['bg']} is {_contrast(c['border'], c['bg']):.2f}:1")
    assert not problems, "\n".join(problems)


@pytest.mark.spec("SHAPE-3", "NAV-11")
def test_theme_switch_is_rectangular(app, page):
    app()
    switch = page.locator("#theme-toggle")
    radius = "e => parseFloat(getComputedStyle(e).borderTopLeftRadius)"
    assert switch.locator(".track").evaluate(radius) <= 3
    assert switch.locator(".knob").evaluate(radius) <= 2


@pytest.mark.spec("SHAPE-4")
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
@pytest.mark.parametrize("route", ["", TABAK, "#/1/2026/314"])
def test_only_logo_round_buttons_and_day_marks_are_round(app, page, route, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(route)
    for tab in page.locator(".tabs button:not(.active)").all():
        tab.click()
    round_ = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => {
        const s = getComputedStyle(e), r = e.getBoundingClientRect();
        if (!r.width || !r.height || s.display === 'none' || e.closest('dialog:not([open])')) return false;
        const radius = Math.max(...['TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'].map(c => parseFloat(s[`border${c}Radius`]) || 0));
        return radius > 3;
    }).filter(e => !e.matches('.brand-mark, .fab, .tl-mark, .spinner'))
      .map(e => e.tagName.toLowerCase() + '.' + [...e.classList].join('.'))""")
    assert not round_, f"round or pill-shaped: {sorted(set(round_))}"


@pytest.mark.spec("SHAPE-5")
@pytest.mark.parametrize("width", [1440, 1000])
def test_search_button_and_switch_are_equally_high_on_one_line(app, page, width):
    page.set_viewport_size({"width": width, "height": 800})
    app()
    search = page.locator("#search-open").bounding_box()
    track = page.locator("#theme-toggle .track").bounding_box()
    assert abs(search["height"] - track["height"]) <= 0.5, f"search {search['height']}px, switch {track['height']}px"
    assert abs((search["y"] + search["height"] / 2) - (track["y"] + track["height"] / 2)) <= 0.5


@pytest.mark.spec("SHAPE-7", "A11Y-13")
@pytest.mark.parametrize("which", ["search", "help", "how", "menu"])
def test_windows_close_with_a_drawn_x(app, page, which):
    if which == "menu":
        on_phone(app, page)
        selector = _open(page, "menu")
    elif which == "how":
        app(TABAK)
        page.locator(".how").first.click()
        selector = "#dialog"
        page.locator("#dialog[open]").wait_for()
        animations_done(page)
    else:
        app(TABAK)
        selector = _open(page, which)
    close = page.locator(selector).get_by_role("button", name="Schließen")
    expect(close).to_be_visible()
    expect(close).to_have_text("")
    assert close.locator("svg path, svg line").count() >= 1
    shape = close.evaluate("""e => { const s = getComputedStyle(e), r = e.getBoundingClientRect();
        return { w: r.width, h: r.height, border: parseFloat(s.borderTopWidth) || 0 }; }""")
    assert shape["w"] >= 44 and shape["h"] >= 44, shape
    assert shape["border"] == 0, "the x has no frame"
    close.click()
    expect(page.locator(selector)).to_be_hidden()
