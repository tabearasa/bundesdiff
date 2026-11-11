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


def _old_source_texts(page) -> tuple[str, str]:
    """The par-note and the „Wie wurde … ermittelt?“ window of the first paragraph with a source."""
    note = page.locator(".par-note").filter(has_text="stammt aus").first
    note.locator("xpath=ancestor::section[1]").locator(".how").click()
    window = " ".join(page.locator("#dialog").inner_text().split())
    page.keyboard.press("Escape")
    return " ".join(note.inner_text().split()), window


@pytest.mark.parametrize("route, source, says", [
    ("#/1/2026/309", None,
     r"einer Kopie von gesetze-im-internet\.de, die das Internet Archive am \d{1,2}\. [A-Z][a-zä]+ \d{4} "
     r"gespeichert hat\."),
    ("#/1/2026/311", "lokal gespeicherte Fassung vom 01.02.2026 (gesetze-im-internet.de)",
     r"einer Fassung von gesetze-im-internet\.de, die bundesdiff am 1\. Februar 2026 gespeichert hat\."),
    ("#/1/2026/311", "lokal gespeicherte Fassung vom 01.02.2026 (NeuRIS)",
     r"einer Fassung vom Rechtsinformationsportal des Bundes, die bundesdiff am 1\. Februar 2026 "
     r"gespeichert hat\."),
    ("#/1/2026/311", "Rechtsdatenbank Beispiel (Stand 2025)",
     r"einer anderen Fassung \(Rechtsdatenbank Beispiel \(Stand 2025\)\)\."),
])
def test_old_text_says_in_plain_words_where_it_came_from(app, page, route, source, says):
    """Not „aus einer älteren, archivierten Fassung (Archivfassung … (Internet Archive))“ nor
    „aus einer lokal gespeicherte Fassung“: one plain phrase, the same in the note and the window."""
    if source:
        def with_source(r):
            data = r.fetch().json()
            for article in data["articles"]:
                for par in article.get("pars", []):
                    if par.get("source"):
                        par["source"] = source
            r.fulfill(json=data)
        page.route("**/data/1/2026/311.json", with_source)
    app(route)
    note, window = _old_source_texts(page)
    assert re.search(f"Der bisherige Text stammt aus {says}", note), note
    assert re.search(f"stammt der alte Wortlaut aus {says}", window), window
    assert "Fassung: " not in note + window
    if not source or source.startswith(("lokal", "Archiv")):  # a known source: no brackets left
        assert "))" not in note + window


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


# ---------------------------------------------------------------- old data (spec 014)

OLD_DATA_NOTICE = ("Die Liste der Veröffentlichungen ist vom 30. Oktober 2026. Neuere Veröffentlichungen "
                   "fehlen hier vielleicht noch, weil recht.bund.de zuletzt nicht erreichbar war. "
                   "Auf recht.bund.de finden Sie immer die amtlichen Texte.")


@pytest.mark.spec("RES-4")
def test_data_date_is_when_the_list_was_fetched(app):
    """meta.json: built 06:41, list fetched 06:23 UTC – the reader is told the time of the list,
    in German time (07:23 Uhr in winter)."""
    page = app()
    expect(page.locator("#data-date")).to_contain_text("Datenstand: 30.10.2026, 07:23 Uhr")


@pytest.mark.spec("RES-5")
def test_no_notice_while_the_list_is_fresh(app):
    page = app()
    expect(page.locator(".timeline")).to_be_visible()
    expect(page.locator(".old-data")).to_have_count(0)


@pytest.mark.spec("RES-5")
def test_notice_when_the_list_is_older_than_36_hours(app):
    page = app(PAGES["old-data"])
    notice = page.locator(".old-data")
    expect(notice).to_have_text(OLD_DATA_NOTICE)
    expect(notice.get_by_role("link", name="recht.bund.de")).to_have_attribute(
        "href", "https://www.recht.bund.de/")
    # above the timeline
    assert notice.bounding_box()["y"] < page.locator(".timeline").bounding_box()["y"]


@pytest.mark.spec("RES-5")
@pytest.mark.parametrize(("now", "shown"), [("2026-10-31T17:23:00Z", False),   # 35 hours later
                                             ("2026-10-31T19:23:00Z", True)])  # 37 hours later
def test_notice_appears_after_36_hours(page, base_url, problems, now, shown):
    page.clock.set_fixed_time(now)
    page.goto(base_url + "index.html")
    wait_rendered(page, "")
    expect(page.locator("#data-date")).to_contain_text("07:23 Uhr")  # meta.json has been read
    expect(page.locator(".old-data")).to_have_count(1 if shown else 0)
    assert not problems, "\n".join(problems)


@pytest.mark.spec("RES-5")
def test_notice_stays_when_filtering_and_switching_views(app):
    page = app(PAGES["old-data"])
    page.locator("#type-filter").select_option("Verordnung")
    expect(page.locator(".old-data")).to_have_count(1)
    page.get_by_role("button", name="Was ändert sich demnächst?").click()
    expect(page.locator(".old-data")).to_have_count(1)
    expect(page.locator(".old-data")).to_have_text(OLD_DATA_NOTICE)


@pytest.mark.spec("RES-5", "RES-4")
def test_notice_date_is_the_day_in_germany(app, page):
    """Fetched at 23:30 UTC on 29 October: in Germany that is already 30 October, 00:30 –
    the notice and the "Datenstand" line name the same day."""
    page.route("**/data/meta.json", lambda route: route.fulfill(json={
        "generated": "2026-10-29T23:41", "listFetched": "2026-10-29T23:30", "since": "2025-10-27"}))
    page = app(PAGES["old-data"])
    expect(page.locator(".old-data")).to_contain_text("ist vom 30. Oktober 2026.")
    expect(page.locator("#data-date")).to_contain_text("Datenstand: 30.10.2026, 00:30 Uhr")


@pytest.mark.spec("RES-4")
@pytest.mark.parametrize("damaged", ["kaputt", "2026-02-30T10:00", "2026-10-30T24:00", "2026-10-30T06:60",
                                     "2026-10-30T06:23+25:99"])
def test_an_unreadable_fetch_time_is_not_shown(app, page, damaged):
    """A damaged listFetched, also a day or hour that does not exist: the build time is used
    instead, never the broken or a shifted time."""
    page.route("**/data/meta.json", lambda route: route.fulfill(json={
        "generated": "2026-10-30T06:41", "listFetched": damaged, "since": "2025-10-27"}))
    page = app()
    expect(page.locator("#data-date")).to_contain_text("Datenstand: 30.10.2026, 07:41 Uhr")
    expect(page.locator("#data-date")).not_to_contain_text(damaged)


@pytest.mark.spec("RES-4")
@pytest.mark.parametrize("since", [None, "2025-13-45", "0000-00-00", "gestern"])
def test_a_missing_or_unreadable_start_date_is_left_out(app, page, since):
    meta = {"generated": "2026-10-30T06:41", "listFetched": "2026-10-30T06:23"}
    if since is not None:
        meta["since"] = since
    page.route("**/data/meta.json", lambda route: route.fulfill(json=meta))
    page = app()
    line = page.locator("#data-date")
    expect(line).to_have_text("Datenstand: 30.10.2026, 07:23\u00a0Uhr\u00a0· Aktualisierung einmal\u00a0täglich")


@pytest.mark.spec("RES-A1")
def test_notice_is_plain_text_with_a_border(app):
    page = app(PAGES["old-data"])
    notice = page.locator(".old-data")
    assert notice.evaluate("n => n.tagName") == "P"
    assert notice.get_attribute("role") is None and notice.get_attribute("aria-live") is None
    assert notice.evaluate("n => n.closest('[aria-live], [role=status], [role=alert]')") is None
    widths = notice.evaluate("n => { const s = getComputedStyle(n); return [s.borderTopWidth, "
                             "s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth] }")
    assert all(float(w.removesuffix("px")) >= 1 for w in widths), widths


SOURCE_CODE = "https://github.com/tabearasa/bundesdiff"


@pytest.mark.spec("SRC-1", "SRC-2", "SRC-3")
def test_about_page_links_to_the_source_code(app):
    page = app(PAGES["about"])
    section = page.locator("#main .about h2", has_text="Quelltext")
    expect(section).to_have_text("Quelltext")
    text = section.locator("xpath=following-sibling::p[1]")
    expect(text).to_have_text(
        "Der Quelltext von bundesdiff liegt öffentlich auf GitHub. Unter github.com/tabearasa/bundesdiff "
        "können Sie nachlesen, wie die Änderungen berechnet werden, und Fehler melden.")
    link = text.get_by_role("link", name="github.com/tabearasa/bundesdiff", exact=True)
    expect(link).to_have_attribute("href", SOURCE_CODE)
    expect(link).to_have_attribute("target", "_blank")
    expect(link).to_have_attribute("rel", "noopener")
    expect(link.locator(".domain")).to_have_text("github.com/tabearasa/bundesdiff")
    link.focus()
    expect(link).to_be_focused()


@pytest.mark.spec("SRC-1")
def test_source_code_link_is_only_on_the_about_page(app):
    for kind in ("start", "amendment"):
        page = app(PAGES[kind])
        expect(page.locator(f'a[href="{SOURCE_CODE}"]')).to_have_count(0)
    page.locator("#nav-help").click()  # the help dialog
    expect(page.locator("#dialog")).to_be_visible()
    expect(page.locator(f'a[href="{SOURCE_CODE}"]')).to_have_count(0)
    expect(page.get_by_text("GitHub")).to_have_count(0)


@pytest.mark.spec("SRC-4")
def test_about_page_loads_nothing_from_github(app, page):
    requested: list[str] = []
    page.on("request", lambda r: requested.append(r.url))
    app(PAGES["about"])
    page.wait_for_load_state("networkidle")
    assert not [u for u in requested if "github" in u], requested
    embedded = page.locator("#main :is(img, script, iframe, link, object, embed, video, audio)")
    expect(embedded).to_have_count(0)


# Every text on screen that names bundesdiff (or GitHub): may the browser hyphenate it?
_HYPHENATED_NAMES = """() => {
  const found = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    if (!/bundesdiff|GitHub/.test(n.textContent) || n.parentElement.closest('template, script, style')) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    if (!r.getClientRects().length) continue;  // not shown
    if (getComputedStyle(n.parentElement).hyphens === 'auto') found.push(n.textContent.trim().slice(0, 60));
  }
  return found;
}"""


@pytest.mark.spec("SRC-A2")
@pytest.mark.parametrize("kind", PAGES)
def test_the_name_bundesdiff_is_never_hyphenated(app, page, kind):
    page.set_viewport_size(VIEWPORTS["small"])
    app(PAGES[kind])
    found = page.evaluate(_HYPHENATED_NAMES)
    if kind == "start":  # the help window and its title
        page.locator("#fab-help, #nav-help").locator("visible=true").first.click()
        page.locator("#dialog[open]").wait_for()
        found += page.evaluate(_HYPHENATED_NAMES)
    assert not found, found


# For every link inside running text (an inline link in a paragraph or list item), with keyboard
# focus: the gap between its focus marker and each character beside it on the same line (px).
# Neighbours are all characters of the paragraph or list item outside the link, also those in
# other elements (e.g. „– 2 Vorschriften“ after a law in the contents list).
_MARKER_GAPS = """root => {
  const gaps = [];
  for (const a of root.querySelectorAll('p a, li a, dd a')) {
    if (getComputedStyle(a).display !== 'inline' || !a.getClientRects().length) continue;
    a.focus();
    const s = getComputedStyle(a);
    if (s.outlineStyle === 'none') { gaps.push([a.textContent, 'no marker', -1]); continue; }
    const grow = parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset);
    const boxes = [...a.getClientRects()];
    const block = a.parentElement.closest('p, li, dd');
    const walk = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    for (let node = walk.nextNode(); node; node = walk.nextNode()) {
      if (a.contains(node)) continue;
      const text = node.textContent;
      for (let i = 0; i < text.length; i++) {
        if (!text[i].trim()) continue;
        const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
        for (const c of r.getClientRects()) {
          const mid = (c.top + c.bottom) / 2;
          for (const b of boxes) {
            if (mid < b.top || mid > b.bottom) continue;  // another line
            const gap = c.left >= b.right ? c.left - (b.right + grow)
                      : c.right <= b.left ? (b.left - grow) - c.right : -1;
            gaps.push([a.textContent.trim(), text[i], gap]);
          }
        }
      }
    }
  }
  // ::before marks such as the „§“ before each law in the contents list
  for (const a of root.querySelectorAll('.glance-laws a')) {
    a.focus();
    const s = getComputedStyle(a), grow = parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset);
    const li = a.parentElement, first = a.getClientRects()[0];
    const before = getComputedStyle(li, '::before');
    if (before.content === 'none') continue;
    const probe = document.createElement('span');
    probe.textContent = '§ '; probe.style.font = before.font; probe.style.letterSpacing = before.letterSpacing;
    probe.style.position = 'absolute'; probe.style.visibility = 'hidden'; probe.style.whiteSpace = 'pre';
    document.body.append(probe);
    probe.textContent = '§';
    const signRight = li.getBoundingClientRect().left + probe.getBoundingClientRect().width;
    probe.remove();
    gaps.push([a.textContent.trim(), '§', (first.left - grow) - signRight]);
  }
  return gaps;
}"""


@pytest.mark.spec("SRC-A3")
@pytest.mark.parametrize("width", [320, 360, 390, 414, 600, 1440])
@pytest.mark.parametrize("kind", ["about", "amendment", "mixed-status", "old-data"])
def test_focus_marker_of_links_in_text_keeps_clear_of_the_words(app, page, kind, width, browser_name):
    page.set_viewport_size({"width": width, "height": 800})
    app(PAGES[kind])
    page.keyboard.press("Tab")  # the keyboard was used: focus() now shows the marker
    gaps = page.locator("body").evaluate(_MARKER_GAPS)
    assert gaps, "no link in running text found"
    # WebKit reports the boxes of single characters rounded (the space after a link starting
    # 0.66 px inside the link), so its gaps come out up to 0.16 px short although the page is the
    # same as in Chromium and Firefox. Half a pixel absorbs that rounding, not a real overlap.
    limit = 2 - (0.5 if browser_name == "webkit" else 0)
    tight = [g for g in gaps if g[2] < limit]
    assert not tight, tight
    if kind == "about":  # 1 px more room below and above: clear of the underline and of descenders
        link = page.get_by_role("link", name="github.com/tabearasa/bundesdiff", exact=True)
        link.focus()
        assert link.evaluate("a => parseFloat(getComputedStyle(a).paddingBottom)") >= 1


@pytest.mark.spec("SRC-A4")
@pytest.mark.parametrize("width", [320, 620, 1440])
def test_source_paragraph_is_set_ragged_right(app, page, width):
    page.set_viewport_size({"width": width, "height": 800})
    page = app(PAGES["about"])
    paragraph = page.locator("#main .about h2", has_text="Quelltext").locator("xpath=following-sibling::p[1]")
    assert paragraph.evaluate("p => getComputedStyle(p).textAlign") in ("left", "start")


def _law_not_loaded(article: dict, final: bool = False) -> None:
    """Spec 017: the Artikel as stored when the current text of its law could not be loaded."""
    article.update(error="Der aktuelle Text dieses Gesetzes konnte nicht geladen werden.", pars=[], lookupFailed={
        "first": "2026-11-10T19:35:00+00:00", "last": "2026-11-10T19:35:00+00:00", "tries": 1, "until": "2026-11-17",
        **({"final": True} if final else {})})
    for ins in article["instructions"]:
        ins.update(status="unsupported", state=None)


@pytest.mark.spec("RTY-4")
@pytest.mark.parametrize("final", [False, True])
def test_an_artikel_whose_law_did_not_load_says_what_happens_next(app, page, final):
    data = json.loads((FIXTURES / "data" / "1" / "2026" / "309.json").read_text())
    _law_not_loaded(data["articles"][1], final)
    page.route("**/data/1/2026/309.json", lambda route: route.fulfill(json=data))
    app(PAGES["amendment"])
    expect(page.locator("#art-1 .error")).to_have_text(
        "Der aktuelle Text dieses Gesetzes konnte nicht geladen werden. "
        "Die Änderungen stehen deshalb nur im Wortlaut der Veröffentlichung." if final else
        "Der aktuelle Text dieses Gesetzes konnte bei der Auswertung nicht geladen werden, weil die Quelle nicht "
        "antwortete. bundesdiff versucht es täglich erneut, bis zum 17.11.2026. "
        "Bis dahin stehen die Änderungen nur im Wortlaut der Veröffentlichung.")
    expect(page.locator("#art-0 .error")).to_have_count(0)
