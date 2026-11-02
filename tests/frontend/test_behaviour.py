"""What a reader does in the app, and what they should see."""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import FIXTURES, PAGES, VIEWPORTS, wait_rendered

TABAK = "#/1/2026/309"  # two laws, old text reconstructed


# ---------------------------------------------------------------- publication

def test_open_publication_from_timeline(app):
    page = app()
    page.locator(".tl-entry", has_text="Tabaksteuergesetzes").click()
    expect(page).to_have_url(re.compile(TABAK + "$"))
    expect(page.locator(".pub-header h1")).to_have_text("Gesetz zur Änderung des Tabaksteuergesetzes")
    expect(page.locator(".glance-laws li")).to_have_count(2)
    expect(page.locator(".article")).to_have_count(2)
    expect(page.locator(".pub-header .summary")).to_contain_text("alter Text rekonstruiert")


def test_glance_links_jump_to_article(app):
    page = app(TABAK)
    page.locator(".glance-laws a").nth(1).click()
    expect(page.locator("#art-1")).to_be_in_viewport()


def test_split_and_inline_view_are_remembered(app):
    page = app(TABAK)
    expect(page.locator("table.diff.split").first).to_be_visible()
    page.get_by_role("button", name="Im Text markiert").click()
    expect(page.locator("table.diff.inline").first).to_be_visible()
    expect(page.locator("table.diff.split")).to_have_count(0)
    page.reload()
    wait_rendered(page, TABAK)
    expect(page.locator("table.diff.inline").first).to_be_visible()


def test_unchanged_sections_fold_and_unfold(app):
    page = app(TABAK)
    table = page.locator("table.diff").first
    folds = table.locator("tr.fold")
    expect(folds.first).to_be_visible()
    folds_before = folds.count()
    folds.first.locator("button").click()
    expect(folds).to_have_count(folds_before - 1)
    page.locator("#only-changes").uncheck()
    expect(page.locator("tr.fold")).to_have_count(0)


def test_diff_marks_deleted_and_inserted_words(app):
    page = app(TABAK)
    expect(page.locator("table.diff tr.change td.text.l del").first).to_be_visible()
    expect(page.locator("table.diff tr.change td.text.r ins").first).to_be_visible()


@pytest.mark.spec("A11Y-8")
def test_tabs_switch_by_click_and_arrow_keys(app):
    page = app(TABAK)
    article = page.locator("#art-0")
    wording = article.get_by_role("tab", name=re.compile("Wortlaut"))
    wording.click()
    expect(wording).to_have_attribute("aria-selected", "true")
    expect(article.locator('[data-body="befehle"]')).to_be_visible()
    expect(article.locator('[data-body="synopse"]')).to_be_hidden()
    page.keyboard.press("ArrowLeft")
    expect(article.get_by_role("tab", name=re.compile("Vorher"))).to_be_focused()
    expect(article.locator('[data-body="synopse"]')).to_be_visible()


def test_instruction_statuses_are_explained(app):
    page = app("#/1/2026/314")
    summary = page.locator(".pub-header .summary")
    for label in ("neuer Text berechnet", "nicht anwendbar", "nicht dargestellt"):
        expect(summary).to_contain_text(label)


def test_how_dialog_explains_a_paragraph(app):
    page = app(TABAK)
    page.locator(".how").first.click()
    dialog = page.locator("#dialog")
    expect(dialog).to_be_visible()
    expect(page.locator("#dialog-title")).to_have_text("Wie wurde § 2 ermittelt?")
    expect(dialog).to_contain_text("zurückgerechnet")
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()


def test_help_dialog_opens_and_closes(app):
    page = app()
    page.locator("#nav-help").click()
    expect(page.locator("#dialog-title")).to_have_text("So funktioniert bundesdiff")
    page.locator("#dialog-close").click()
    expect(page.locator("#dialog")).to_be_hidden()
    page.get_by_role("button", name=re.compile("So funktioniert's – und was die Fachbegriffe")).click()
    expect(page.locator("#dialog")).to_be_visible()
    page.mouse.click(5, 5)  # backdrop
    expect(page.locator("#dialog")).to_be_hidden()


def test_not_analyzed_and_failed_publications_explain_why(app):
    page = app("#/1/2026/322")
    # "not yet" is not "could not": the heading must not contradict the text
    expect(page.locator(".error-box strong")).to_have_text("Diese Veröffentlichung ist noch nicht ausgewertet.")
    expect(page.locator(".error-box")).not_to_contain_text("konnte nicht")
    page = app("#/1/2026/316")
    expect(page.locator(".error-box")).to_contain_text("Testfehler: PDF nicht lesbar")


def test_browser_back_and_logo_return_to_previous_pages(app):
    page = app("#/1/2026/315")
    page.get_by_role("link", name=re.compile("Ältere Veröffentlichung")).click()
    expect(page.locator(".pub-header h1")).to_contain_text("Preisangabenrechts")
    page.go_back()
    expect(page.locator(".pub-header h1")).to_contain_text("Hochseeschutzgesetzes")
    page.locator(".brand").click()
    expect(page.locator("#main h1")).to_have_text("Was ändert sich im Gesetz?")
    expect(page.locator(".timeline")).to_be_visible()


# ---------------------------------------------------------------- theme

def background(page: Page) -> str:
    return page.evaluate("getComputedStyle(document.body).backgroundColor")


@pytest.mark.spec("A11Y-10")
def test_theme_toggle_is_remembered(app):
    page = app()
    switch = page.get_by_role("switch", name="Dunkle Ansicht")
    expect(switch).to_have_attribute("aria-checked", "false")
    light = background(page)
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    assert background(page) != light
    page.reload()
    wait_rendered(page, "")
    expect(switch).to_have_attribute("aria-checked", "true")


@pytest.mark.spec("A11Y-10")
def test_theme_follows_the_system_setting(app, page):
    page.emulate_media(color_scheme="dark")
    app()
    expect(page.locator("#theme-toggle")).to_have_attribute("aria-checked", "true")


@pytest.mark.spec("A11Y-10")
def test_theme_switch_follows_a_change_of_the_system_setting(app, page):
    """The system turns dark while the page is open: the switches must say so, and the first
    click must turn the page light again – not leave switch and page disagreeing."""
    page.emulate_media(color_scheme="light")
    app()
    switch = page.locator("#theme-toggle")
    expect(switch).to_have_attribute("aria-checked", "false")
    light = background(page)
    page.emulate_media(color_scheme="dark")
    expect(switch).to_have_attribute("aria-checked", "true")
    for other in page.locator(".theme-switch").all():
        expect(other).to_have_attribute("aria-checked", "true")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "false")
    assert background(page) == light


# ---------------------------------------------------------------- keyboard

@pytest.mark.spec("A11Y-8")
def test_reading_settings_keep_the_keyboard_focus(app):
    """Changing how the comparison is shown draws the page anew; the reader must stay on the
    control they used, at the same place on the screen, and the next Tab goes on from there."""
    page = app(TABAK)
    toggle = page.locator("#only-changes")
    toggle.focus()
    top = toggle.evaluate("e => e.getBoundingClientRect().top")
    page.keyboard.press("Space")
    expect(toggle).not_to_be_checked()
    expect(toggle).to_be_focused()
    assert abs(toggle.evaluate("e => e.getBoundingClientRect().top") - top) <= 2
    for name in ("Im Text markiert", "Nebeneinander"):
        button = page.get_by_role("button", name=name, exact=True)
        button.focus()
        page.keyboard.press("Enter")
        expect(button).to_have_attribute("aria-pressed", "true")
        expect(button).to_be_focused()
    page.keyboard.press("Tab")  # the next control after "Nebeneinander", not the top of the page
    expect(page.get_by_role("button", name="Im Text markiert", exact=True)).to_be_focused()


@pytest.mark.spec("A11Y-8")
def test_reading_settings_keep_the_chosen_tab(app):
    page = app(TABAK)
    article = page.locator("#art-1")
    article.get_by_role("tab", name=re.compile("Wortlaut")).click()
    page.get_by_role("button", name="Im Text markiert", exact=True).click()
    expect(article.get_by_role("tab", name=re.compile("Wortlaut"))).to_have_attribute("aria-selected", "true")
    expect(article.locator('[data-body="befehle"]')).to_be_visible()
    expect(page.locator("#art-0").get_by_role("tab", name=re.compile("Vorher"))).to_have_attribute(
        "aria-selected", "true")


@pytest.mark.spec("A11Y-8")
def test_controls_show_keyboard_focus(app):
    page = app(TABAK)
    for selector in ("#search-open", "[data-view=inline]", "#theme-toggle", ".how", ".tabs button.active"):
        page.locator(selector).first.focus()
        page.keyboard.press("Shift")  # focus-visible needs keyboard modality
        style = page.locator(selector).first.evaluate(
            "e => { const s = getComputedStyle(e); return s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.boxShadow }")
        assert not style.startswith("none") or "rgb" in style, f"{selector} shows no focus: {style}"


# ---------------------------------------------------------------- live server mode

def test_live_api_mode(page, base_url, problems):
    """Without the static flag the frontend talks to the FastAPI backend."""
    data = FIXTURES / "data"
    calls: list[str] = []

    def api(route):
        url = route.request.url
        calls.append(url)
        if "/api/publications?" in url:
            body = (data / "publications-1.json").read_text()
        else:
            year, number = re.search(r"/api/publications/1/(\d+)/([^/?]+)", url).groups()
            body = (data / "1" / year / f"{number}.json").read_text()
        route.fulfill(status=200, content_type="application/json", body=body)

    page.route(re.compile(r".*/api/.*"), api)
    page.route(re.compile(r".*/index\.html$"), lambda r: r.fulfill(
        status=200, content_type="text/html",
        body=(FIXTURES.parents[2] / "bundesdiff" / "static" / "index.html").read_text()))
    page.goto(base_url + "index.html" + TABAK)
    wait_rendered(page, TABAK)
    expect(page.locator(".pub-header h1")).to_have_text("Gesetz zur Änderung des Tabaksteuergesetzes")
    expect(page.get_by_role("button", name="Neu auswerten")).to_be_visible()
    page.get_by_role("button", name="Neu auswerten").click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    assert any("refresh=true" in c for c in calls)
    assert json.loads((data / "meta.json").read_text())  # fixtures are intact
    assert not problems, "\n".join(problems)


def test_phone_stacks_old_above_new_text(app, page):
    """Side by side leaves two words per line on a phone: old and new text are stacked instead."""
    page.set_viewport_size(VIEWPORTS["phone"])
    app(TABAK)
    change = page.locator("table.diff.split tr.change").first
    old, new = change.locator("td.text.l"), change.locator("td.text.r")
    assert new.bounding_box()["y"] >= old.bounding_box()["y"] + old.bounding_box()["height"] - 1
    assert new.bounding_box()["width"] > 300
    expect(page.locator("table.diff.split tr.equal td.text.l").first).to_be_hidden()


# ---------------------------------------------------------------- accessibility

@pytest.mark.spec("A11Y-7")
def test_changed_words_are_marked_by_more_than_colour(app):
    """Colour-blind readers and black-and-white prints: struck through vs. underlined."""
    page = app(TABAK)
    deleted = page.locator("table.diff tr.change del").first
    inserted = page.locator("table.diff tr.change ins").first
    assert "line-through" in deleted.evaluate("e => getComputedStyle(e).textDecorationLine")
    assert "underline" in inserted.evaluate("e => getComputedStyle(e).textDecorationLine")


@pytest.mark.spec("A11Y-7")
def test_screen_readers_hear_which_words_changed(app):
    page = app(TABAK)
    before = "(e, p) => getComputedStyle(e, p).content"
    assert "gestrichen" in page.locator("tr.change del").first.evaluate(before, "::before")
    assert "neu" in page.locator("tr.change ins").first.evaluate(before, "::before")
    assert page.locator("tr.change del").first.evaluate(
        "e => getComputedStyle(e, '::before').position") == "absolute"  # invisible on screen


@pytest.mark.spec("A11Y-7")
def test_examples_of_the_marking_are_read_as_written(app):
    """"gestrichen"/"neu" belong to the comparison: in the intro and the legends the word itself
    says what the marking means, and the "§" ornament is not part of any name."""
    page = app()
    content = "(e, p) => getComputedStyle(e, p).content"
    for sample in page.locator("del.sample, ins.sample").all():
        assert sample.evaluate(content, "::before") == "none"
    expect(page.get_by_role("heading", name="Was ändert sich im Gesetz?", exact=True)).to_be_visible()
    page.locator(".welcome .linklike[data-help]").click()
    expect(page.locator("#dialog ins")).to_have_text("unterstrichen")
    expect(page.locator("#dialog")).not_to_contain_text("farbig")  # not by colour alone
    page.locator("#dialog-close").click()

    page = app(TABAK)
    expect(page.get_by_role("heading", name="Gesetz zur Änderung des Tabaksteuergesetzes", exact=True)).to_be_visible()
    # the "§" before each law is decoration: an empty alternative text after "/"
    ornament = page.locator(".glance-laws li").first.evaluate(content, "::before")
    assert "§" in ornament and re.search(r'/\s*""', ornament), ornament
    for sample in page.locator("del.sample, ins.sample").all():
        assert sample.evaluate(content, "::before") == "none"
    assert "gestrichen" in page.locator("tr.change del").first.evaluate(content, "::before")


@pytest.mark.spec("A11Y-7")
def test_changed_punctuation_is_named_for_screen_readers(app):
    """Screen readers skip a lone ":" – a change of only punctuation must say which mark it is."""
    page = app(TABAK)
    marks = page.locator("tr.change ins[data-say], tr.change del[data-say]")
    expect(marks.first).to_be_attached()
    for mark in marks.all():
        text = mark.evaluate("e => e.textContent")
        assert not re.search(r"\w", text), text
        # Firefox gives the parts of content as separate strings: " [neu: " "Doppelpunkt" "] "
        said = re.sub(r'"\s*"', "", mark.evaluate("e => getComputedStyle(e, '::before').content"))
        assert re.search(r"(gestrichen|neu): (Doppelpunkt|Komma|Punkt|Semikolon|\w+)", said), said
    words = page.locator("tr.change ins:not([data-say])").first
    assert "neu" in words.evaluate("e => getComputedStyle(e, '::before').content")


@pytest.mark.spec("A11Y-9")
def test_reduced_motion_jumps_instead_of_scrolling(app, page):
    page.emulate_media(reduced_motion="reduce")
    app(TABAK)
    page.locator(".glance-laws a").nth(1).click()
    expect(page.locator("#art-1")).to_be_in_viewport(timeout=300)  # no smooth scroll


@pytest.mark.spec("A11Y-5")
def test_counts_stay_on_one_line_with_their_noun(app, page):
    """"– 49 / Vorschriften" across two lines reads badly; number and noun belong together."""
    page.set_viewport_size(VIEWPORTS["small"])
    app("#/1/2026/314")
    counts = page.locator(".muted, .badge").filter(has_text=re.compile(r"\d\s+(Vorschrift|Änderung)"))
    assert counts.count()
    for text in counts.all_text_contents():
        assert not re.search(r"\d (Vorschrift|Änderung)", text), f"normal space in {text!r}"
    # nor the dash in front of it
    for count in page.locator(".count:visible").all():
        lines = count.evaluate("e => new Set([...e.getClientRects()].map(r => Math.round(r.top))).size")
        assert lines == 1, f"{count.inner_text()!r} spans {lines} lines"


@pytest.mark.spec("A11Y-5")
def test_dates_are_written_one_way_and_relative_days_stay_together(app, page):
    page.set_viewport_size(VIEWPORTS["small"])
    app(TABAK)
    expect(page.locator(".glance")).to_contain_text("beschlossen am 19. Oktober 2026, veröffentlicht am 20. Oktober 2026")
    app("#/?ansicht=demnaechst")
    rel = page.locator(".tl-rel", has_text="in 2 Tagen")
    expect(rel).to_have_count(1)
    assert rel.evaluate("e => new Set([...e.getClientRects()].map(r => Math.round(r.top))).size") == 1
    # copied text keeps the words apart: "… 2026 in 2 Tagen"
    assert rel.evaluate("e => e.parentElement.textContent").endswith("2026 in 2 Tagen")
    # and starts exactly below the date, not one space further right
    date = rel.locator("xpath=preceding-sibling::time")
    assert abs(rel.bounding_box()["x"] - date.bounding_box()["x"]) <= 0.5


@pytest.mark.spec("UPD-3")
def test_not_yet_analyzed_says_data_is_updated_daily(app):
    page = app(PAGES["not-analyzed"])
    expect(page.locator(".error-box")).to_contain_text("einmal täglich")
