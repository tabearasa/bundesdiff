"""Navigation bar, contents bar and about page – specs/001-navbar.md."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import VIEWPORTS

# the phone layout has no navbar, but round buttons (spec 004, PTL-1)
WITH_NAVBAR = [v for v in VIEWPORTS if v not in ("phone", "small")]
LOW_PHONE = {"width": 320, "height": 400}  # narrow but too low for the phone layout

TABAK = "#/1/2026/309"  # changes two laws
SMALL_ORDINANCE = "#/1/2026/306"  # changes one law
ANNOUNCEMENT = "#/1/2026/315"  # no comparison
ABOUT = "#/ueber"


def nav(page: Page):
    return page.get_by_role("navigation", name="Hauptnavigation")


def contents(page: Page):
    return page.get_by_role("navigation", name="Inhalt dieser Veröffentlichung")


def scroll_to(page: Page, selector: str) -> None:
    """Scroll the page (phones) or the text column (wide screens) so the element is at the top."""
    page.locator(selector).evaluate("e => e.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(150)  # the contents bar updates on the next animation frame


# ---------------------------------------------------------------- navbar

@pytest.mark.spec("NAV-1")
def test_navbar_entries_in_order(app):
    page = app()
    entries = nav(page).locator("a, button")
    expect(entries).to_have_text([re.compile(r"§\s*bundesdiff"), "Veröffentlichungen", "So funktioniert's",
                                  "Über bundesdiff", re.compile(r"Suchen"), ""], use_inner_text=True)
    expect(entries.last).to_have_role("switch")
    expect(nav(page).get_by_role("link", name="bundesdiff – Startseite")).to_have_attribute("href", "#/")


@pytest.mark.spec("NAV-1")
def test_navbar_help_opens_the_help(app):
    page = app(TABAK)
    nav(page).get_by_role("button", name="So funktioniert's").click()
    expect(page.locator("#dialog-title")).to_have_text("So funktioniert bundesdiff")


@pytest.mark.spec("NAV-2")
def test_current_page_is_marked(app):
    page = app()
    current = nav(page).locator("[aria-current=page]")
    expect(current).to_have_text("Veröffentlichungen", use_inner_text=True)
    assert "underline" in current.evaluate("e => getComputedStyle(e).textDecorationLine")
    nav(page).get_by_role("link", name="Über bundesdiff").click()
    expect(current).to_have_text("Über bundesdiff", use_inner_text=True)
    page.goto(page.url.split("#")[0] + TABAK)
    expect(page.locator(".pub-header h1")).to_be_visible()
    expect(current).to_have_count(0)


@pytest.mark.spec("NAV-3")
@pytest.mark.parametrize("viewport", [*WITH_NAVBAR, "low-phone"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_navbar_is_one_row(app, page, viewport, theme):
    page.set_viewport_size(LOW_PHONE if viewport == "low-phone" else VIEWPORTS[viewport])
    app(TABAK, theme=theme)
    tops = {round(b["y"]) for b in (e.bounding_box() for e in nav(page).locator("a, button").all())
            if b and b["width"]}
    assert max(tops) - min(tops) < 12, f"entries on several rows: {sorted(tops)}"


@pytest.mark.spec("NAV-3")
def test_navbar_fits_at_every_width(app, page):
    """Breakpoints between the test viewports: every width from 320 to 1300 px, in 10 px steps.

    Below 600 px the navbar is only shown on low screens (the phone layout has none, PTL-1).
    """
    app()
    for width in range(320, 1301, 10):  # up to where the search becomes a field (SRCH-1)
        page.set_viewport_size({"width": width, "height": 400 if width < 600 else 700})
        size = page.locator(".navbar").evaluate("n => [n.scrollWidth, n.clientWidth, n.offsetHeight]")
        assert size[0] <= size[1] + 1, f"{width}px: navbar content {size[0]}px wide, room for {size[1]}px"
        assert size[2] <= 56, f"{width}px: navbar {size[2]}px high"


@pytest.mark.spec("NAV-3")
def test_short_labels_on_phones_keep_full_names(app, page):
    page.set_viewport_size(LOW_PHONE)
    app()
    expect(nav(page).locator("a, button")).to_have_text(["§", "Liste", "Hilfe", "Über", "", ""], use_inner_text=True)
    expect(nav(page).get_by_role("button", name="Suchen")).to_be_visible()
    expect(nav(page).get_by_role("link", name="bundesdiff – Startseite")).to_be_visible()
    expect(nav(page).get_by_role("switch", name="Dunkle Ansicht")).to_be_visible()


@pytest.mark.spec("NAV-4")
@pytest.mark.parametrize("viewport", ["desktop", "phone-landscape"])
def test_navbar_stays_visible_while_scrolling(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(TABAK)
    bar = page.locator(".topbar")
    assert bar.bounding_box()["height"] <= 56, f"navbar is {bar.bounding_box()['height']}px high"
    scroll_to(page, "#art-1")
    expect(nav(page)).to_be_in_viewport()
    assert abs(bar.bounding_box()["y"]) <= 0.5, "navbar scrolled away"


@pytest.mark.spec("NAV-5")
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
def test_publications_entry_returns_to_the_last_read_entry(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app()
    page.locator(".tl-entry", has_text="Tabaksteuergesetzes").click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    expect(page.locator(".back-link")).to_have_count(0)
    # on phones the back arrow (PTL-11)
    nav(page).get_by_role("link", name=re.compile("Veröffentlichungen|Liste|Zurück zur Zeitleiste")).click()
    last = page.locator(".tl-entry.last-read")
    expect(last).to_contain_text("Tabaksteuergesetzes")
    expect(last).to_be_focused()
    expect(last).to_be_in_viewport()


@pytest.mark.spec("NAV-6")
def test_reading_settings_are_above_the_comparison(app):
    page = app()
    expect(page.get_by_role("button", name="Im Text markiert")).to_have_count(0)
    expect(page.locator("#only-changes")).to_have_count(0)
    page = app(TABAK)
    settings = page.locator(".reading-settings")
    expect(settings.get_by_role("button", name="Im Text markiert")).to_be_visible()
    expect(settings.get_by_label("Unverändertes ausblenden")).to_be_checked()
    expect(nav(page).get_by_role("button", name="Im Text markiert")).to_have_count(0)
    assert settings.bounding_box()["y"] < page.locator("table.diff").first.bounding_box()["y"]
    settings.get_by_label("Unverändertes ausblenden").uncheck()
    expect(page.locator("tr.fold")).to_have_count(0)
    page = app(ANNOUNCEMENT)
    expect(page.locator(".reading-settings")).to_have_count(0)


# ---------------------------------------------------------------- contents bar

@pytest.mark.spec("NAV-7")
def test_contents_bar_only_for_several_laws(app):
    page = app(SMALL_ORDINANCE)
    expect(contents(page)).to_have_count(0)
    page = app(TABAK)
    expect(contents(page)).to_be_visible()
    expect(contents(page).locator(".toc-current")).to_have_text("Artikel 1 · Tabaksteuergesetz (TabStG)")


@pytest.mark.spec("NAV-7", "NAV-A3")
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
def test_contents_list_jumps_to_a_law(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(TABAK)
    toggle = contents(page).get_by_role("button", name="Inhalt")
    toggle.click()
    entries = contents(page).get_by_role("link")
    expect(entries).to_have_count(2)
    expect(entries.nth(1)).to_contain_text("Tabaksteuerverordnung")
    expect(entries.nth(1)).to_contain_text(re.compile(r"\d+\s+Vorschrift"))
    entries.nth(1).click()
    expect(entries.first).to_be_hidden()  # list closed
    heading = page.locator("#art-1 h2")
    expect(heading).to_be_focused()
    expect(heading).to_be_in_viewport()
    bars = contents(page).bounding_box()
    assert heading.bounding_box()["y"] >= bars["y"] + bars["height"] - 1, "heading hidden behind the bars"


@pytest.mark.spec("NAV-8")
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
def test_contents_bar_follows_the_reader(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(TABAK)
    current = contents(page).locator(".toc-current")
    scroll_to(page, "#art-1")
    expect(current).to_contain_text("Tabaksteuerverordnung")
    navbar = page.locator(".topbar").bounding_box()  # none on phones: the bar is at the top (PTL-11)
    below = navbar["y"] + navbar["height"] if navbar else 0
    assert abs(contents(page).bounding_box()["y"] - below) <= 1, "contents bar is not right below the navbar"
    contents(page).get_by_role("button", name="Inhalt").click()
    expect(contents(page).locator("[aria-current=location]")).to_contain_text("Tabaksteuerverordnung")
    page.keyboard.press("Escape")
    scroll_to(page, "#art-0")
    expect(current).to_contain_text("Tabaksteuergesetz")


@pytest.mark.spec("NAV-9", "NAV-A3")
def test_each_law_ends_with_a_link_to_the_top(app):
    page = app(TABAK)
    links = page.get_by_role("link", name="Zum Anfang der Veröffentlichung")
    expect(links).to_have_count(2)
    links.last.click()
    title = page.locator(".pub-header h1")
    expect(title).to_be_in_viewport()
    expect(title).to_be_focused()


# ---------------------------------------------------------------- about page

@pytest.mark.spec("NAV-10")
def test_about_page_explains_purpose_sources_and_privacy(app):
    page = app(ABOUT)
    main = page.locator("#main")
    expect(main.locator("h1")).to_have_text("Über bundesdiff")
    for text in ("kein amtliches Angebot", "Bundesgesetzblatt", "§ 5 Urheberrechtsgesetz",
                 "recht.bund.de", "gesetze-im-internet.de", "Rechtsinformationsportal",
                 "keine Cookies"):
        expect(main).to_contain_text(text)


# ---------------------------------------------------------------- accessibility

@pytest.mark.spec("NAV-A1")
@pytest.mark.parametrize("route", ["", TABAK, ABOUT])
def test_skip_link_is_first_and_jumps_to_content(app, route):
    page = app(route)
    page.keyboard.press("Tab")
    skip = page.get_by_role("link", name="Zum Inhalt springen")
    expect(skip).to_be_focused()
    expect(skip).to_be_in_viewport()
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()
    assert page.url.endswith(route or "index.html"), "skip link must not change the page"


def test_skip_link_is_invisible_until_focused(app):
    page = app()
    expect(page.get_by_role("link", name="Zum Inhalt springen")).not_to_be_in_viewport()


@pytest.mark.spec("NAV-A2")
def test_landmarks_and_disclosure_state(app):
    page = app(TABAK)
    expect(nav(page)).to_have_count(1)
    toggle = contents(page).get_by_role("button", name="Inhalt")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    contents(page).get_by_role("link").first.focus()
    page.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_be_focused()


@pytest.mark.spec("NAV-A4")
def test_bars_are_not_sticky_on_very_low_screens(app, page):
    page.set_viewport_size({"width": 320, "height": 200})
    app(TABAK)
    scroll_to(page, "#art-1")
    expect(nav(page)).not_to_be_in_viewport()
    expect(contents(page)).not_to_be_in_viewport()


# ---------------------------------------------------------------- light/dark switch

def _box(locator) -> dict:
    return locator.evaluate("e => e.getBoundingClientRect().toJSON()")


@pytest.mark.spec("NAV-11")
@pytest.mark.parametrize("viewport", ["desktop", "small"])
def test_theme_switch_is_a_slider(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    page.emulate_media(reduced_motion="reduce")  # no sliding animation to wait for
    app(theme="light")
    if viewport == "small":  # on phones the switch is in the menu (PTL-6)
        nav(page).get_by_role("button", name="Menü").click()
        switch = page.get_by_role("dialog", name="Menü").get_by_role("switch", name="Dunkle Ansicht")
    else:
        switch = nav(page).get_by_role("switch", name="Dunkle Ansicht")
    expect(switch).to_have_attribute("aria-checked", "false")
    expect(switch).to_have_attribute("title", "Zur dunklen Ansicht wechseln")
    track, knob = _box(switch.locator(".track")), _box(switch.locator(".knob"))
    assert knob["left"] - track["left"] < track["right"] - knob["right"], "knob should be on the left"
    expect(switch.locator(".knob svg.sun")).to_be_visible()
    expect(switch.locator(".knob svg.moon")).to_be_hidden()

    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    expect(switch).to_have_attribute("title", "Zur hellen Ansicht wechseln")
    knob = _box(switch.locator(".knob"))
    assert knob["left"] - track["left"] > track["right"] - knob["right"], "knob should be on the right"
    expect(switch.locator(".knob svg.moon")).to_be_visible()
    expect(switch.locator(".knob svg.sun")).to_be_hidden()


@pytest.mark.spec("NAV-11")
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_switch_drawing_is_centred_and_in_page_colours(app, page, theme):
    app(theme=theme)
    switch = page.locator("#theme-toggle")
    track, knob = _box(switch.locator(".track")), _box(switch.locator(".knob"))
    icon = _box(switch.locator(".knob svg:visible"))
    # within a pixel: browsers snap the drawing to whole pixels
    assert abs((knob["top"] + knob["bottom"]) / 2 - (track["top"] + track["bottom"]) / 2) <= 1
    assert abs((icon["left"] + icon["right"]) / 2 - (knob["left"] + knob["right"]) / 2) <= 1
    assert abs((icon["top"] + icon["bottom"]) / 2 - (knob["top"] + knob["bottom"]) / 2) <= 1
    # drawn with the page's own colours, not a fixed colour of its own
    colours = page.evaluate("""() => {
        const s = getComputedStyle(document.documentElement), icon = document.querySelector('#theme-toggle[aria-checked=true] .moon, #theme-toggle[aria-checked=false] .sun');
        const probe = c => { const d = document.createElement('i'); d.style.color = c; document.body.append(d);
                             const v = getComputedStyle(d).color; d.remove(); return v; };
        return { stroke: getComputedStyle(icon).stroke,
                 page: ['--accent', '--ink', '--ink-soft', '--muted'].map(v => probe(s.getPropertyValue(v))) }; }""")
    assert colours["stroke"] in colours["page"]


@pytest.mark.spec("NAV-3")
@pytest.mark.parametrize("width", [320, 360, 400])
def test_navbar_entries_stay_apart_on_narrow_screens(app, page, width):
    """"Liste Hilfe Über" with 4 px between them read like one link: the free room is shared out."""
    page.set_viewport_size({"width": width, "height": 400})
    app()
    boxes = nav(page).locator("a, button").evaluate_all(
        "es => es.filter(e => e.offsetParent && !e.closest('.skip-link')).map(e => e.getBoundingClientRect()).map(r => [r.left, r.right])")
    gaps = [b[0] - a[1] for a, b in zip(boxes, boxes[1:])]
    assert min(gaps) >= 8, f"entries only {min(gaps):.1f}px apart: {gaps}"
    assert max(gaps) - min(gaps) <= 1, f"unequal gaps: {gaps}"
