"""Gesetzentwürfe (spec 016): the list of bills and the page of one bill.

The fixture is Drucksache 21/6588, cut down to five Artikel (see make_fixtures.py).
"""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import FIXTURES, PAGES, THEMES, VIEWPORTS
from .test_behaviour import _law_not_loaded
from .test_layout import _shot, layout_issues, settle

BILLS = PAGES["bills"]
BILL = PAGES["bill"]
TITLE = "Entwurf eines Gesetzes zur Modernisierung des Städtebau- und Raumordnungsrechts"
PDF = "https://dserver.bundestag.de/btd/21/065/2106588.pdf"
LOW_PHONE = {"width": 320, "height": 400}  # narrow, but too low for the phone layout: the navbar is shown
LOW_WIDE = {"width": 600, "height": 400}  # as low, and wide enough for the short names of the pages


def nav(page: Page):
    return page.locator(".navbar")


def article(page: Page, heading):
    """The card of one Artikel, by its own heading (the §§ inside have headings too)."""
    return page.locator(".article").filter(has=page.locator("h2", has_text=heading))


def info(page: Page):
    return page.locator(".bill-info")


# ---------------------------------------------------------------- navigation and list

@pytest.mark.spec("ENT-1")
def test_navbar_leads_to_the_bills_and_marks_them(app):
    page = app()
    entry = nav(page).get_by_role("link", name="Gesetzentwürfe")
    expect(entry).not_to_have_attribute("aria-current", "page")
    entry.click()
    expect(page).to_have_url(re.compile(r"#/entwuerfe$"))
    expect(page.get_by_role("heading", level=1, name="Gesetzentwürfe")).to_be_visible()
    expect(nav(page).locator("[aria-current=page]")).to_have_text("Gesetzentwürfe", use_inner_text=True)
    page.get_by_role("link", name=re.compile("Modernisierung des Städtebau")).click()
    expect(page).to_have_url(re.compile(r"#/entwurf/21/6588$"))
    expect(page.locator(".pub-header h1")).to_have_text(TITLE)
    expect(nav(page).locator("[aria-current=page]")).to_have_text("Gesetzentwürfe", use_inner_text=True)
    # back to the publications: the entry is not marked any more
    nav(page).get_by_role("link", name="Veröffentlichungen").click()
    expect(nav(page).locator("[aria-current=page]")).to_have_text("Veröffentlichungen", use_inner_text=True)


@pytest.mark.spec("ENT-1", "ENT-A2")
def test_phone_menu_leads_to_the_bills(app, page):
    page.set_viewport_size(VIEWPORTS["phone"])
    app()
    page.get_by_role("button", name="Menü").click()
    page.locator("#menu").get_by_role("link", name="Gesetzentwürfe").click()
    expect(page.get_by_role("heading", level=1, name="Gesetzentwürfe")).to_be_visible()
    expect(page.locator("#menu")).to_be_hidden()
    page.get_by_role("button", name="Menü").click()
    expect(page.locator("#menu").get_by_role("link", name="Gesetzentwürfe")).to_have_attribute("aria-current", "page")


@pytest.mark.spec("ENT-2")
def test_list_names_number_date_author_and_laws(app):
    page = app(BILLS)
    entries = page.locator(".bill-list li")
    expect(entries).to_have_count(1)
    entry = entries.first
    expect(entry.get_by_role("link")).to_have_text(TITLE)
    expect(entry).to_contain_text("Drucksache 21/6588")
    expect(entry).to_contain_text("22.06.2026")
    expect(entry).to_contain_text("Gesetzentwurf der Bundesregierung")
    for law in ("Raumordnungsgesetz", "Verwaltungsgerichtsordnung", "Investitionsvorranggesetz"):
        expect(entry).to_contain_text(law)


@pytest.mark.spec("ENT-3")
def test_list_explains_what_a_bill_is(app):
    page = app(BILLS)
    expect(page.locator(".bills .lead")).to_have_text(
        "Ein Gesetzentwurf ist ein Vorschlag für ein neues Gesetz. Er gilt noch nicht. "
        "Der Bundestag kann ihn ändern oder ablehnen.")
    assert page.locator(".bills .lead").bounding_box()["y"] < page.locator(".bill-list").bounding_box()["y"]


@pytest.mark.spec("ENT-4")
def test_bills_are_not_among_the_publications(app):
    page = app()
    expect(page.locator(".tl-entry").first).to_be_visible()
    expect(page.locator(".tl-entry", has_text="Städtebau")).to_have_count(0)
    expect(page.locator("#main")).not_to_contain_text("Drucksache")
    page.get_by_role("button", name="Was ändert sich demnächst?").click()
    expect(page.locator(".timeline.upcoming")).to_be_visible()
    expect(page.locator("#main")).not_to_contain_text("Raumordnungsrechts")
    expect(page.locator("#main")).not_to_contain_text("Drucksache")


# ---------------------------------------------------------------- the page of a bill

@pytest.mark.spec("ENT-5", "ENT-A1")
def test_header_names_the_drucksache_and_says_entwurf(app):
    page = app(BILL)
    header = page.locator(".pub-header")
    expect(header.locator(".fundstelle")).to_have_text("Drucksache 21/6588")
    expect(header.get_by_role("heading", level=1)).to_have_text(TITLE)
    expect(header.locator(".date")).to_have_text(re.compile(r"Gesetzentwurf der Bundesregierung vom\s22\.06\.2026"))
    # ENT-A1: said in words, twice – not only by a colour
    expect(header.locator(".date")).to_contain_text("Entwurf")
    expect(header.locator(".draft-notice")).to_contain_text("Dies ist ein Entwurf.")


@pytest.mark.spec("ENT-6")
def test_notice_comes_before_any_comparison(app):
    page = app(BILL)
    notice = page.locator(".draft-notice")
    expect(notice).to_have_text(
        "Dies ist ein Entwurf. Er gilt nicht. Der Bundestag kann ihn noch ändern oder ablehnen. bundesdiff zeigt "
        "den Stand vom 22.06.2026 und verfolgt nicht, was danach mit dem Entwurf geschehen ist.",
        use_inner_text=True)
    below = notice.bounding_box()["y"] + notice.bounding_box()["height"]
    assert below <= page.locator(".pub-header .glance").bounding_box()["y"]
    assert below <= page.locator(".article").first.bounding_box()["y"]
    assert notice.bounding_box()["y"] >= page.locator(".pub-header h1").bounding_box()["y"]


@pytest.mark.spec("ENT-7")
def test_each_amended_law_is_compared_with_its_current_text(app, page):
    page.set_viewport_size(VIEWPORTS["desktop"])
    app(BILL)
    expect(page.locator(".article")).to_have_count(6)
    expect(page.locator(".glance-laws li")).to_have_count(5)
    for name in ("Raumordnungsgesetz", "Verwaltungsgerichtsordnung", "Investitionsvorranggesetz"):
        expect(article(page, re.compile(name)).locator("table.diff").first).to_be_attached()
    heads = article(page, re.compile("Verwaltungsgerichtsordnung")).locator("table.diff.split thead th")
    expect(heads).to_have_text(["Geltender Text", "Text nach dem Entwurf"])
    expect(page.locator("table.diff tr.change td.text.r ins").first).to_be_attached()
    # the words of a publication do not appear around the comparison (the law texts may contain them)
    expect(page.locator("#main")).not_to_contain_text("Vorher · bisheriger Text")
    for part in (".pub-header", ".tabs", ".to-start", ".article > header", ".reading-settings"):
        for found in page.locator(part).all():
            expect(found).not_to_contain_text("Gesetzblatt")
            expect(found).not_to_contain_text("Veröffentlichung")
            expect(found).not_to_contain_text("Vorher")


@pytest.mark.spec("ENT-8")
def test_nothing_is_shown_as_calculated_backwards(app):
    page = app(BILL)
    expect(page.locator(".badge.consolidated")).to_have_count(0)
    expect(page.locator(".badge", has_text="rekonstruiert")).to_have_count(0)
    expect(page.locator(".par-note")).to_have_count(0)  # no old text taken from an archive
    expect(page.locator(".pub-header")).not_to_contain_text("rekonstruiert")
    # the instruction that does not fit the law (a slip in the bill: "c)" instead of "cc)") keeps its wording
    rog = article(page, re.compile("Raumordnungsgesetz"))
    rog.get_by_role("tab", name=re.compile("Wortlaut im Entwurf")).click()
    slip = rog.locator(".instructions li", has_text="Satz 8 wird durch den folgenden Satz ersetzt")
    expect(slip).to_contain_text("Landesrecht zu weiteren Zugangsmöglichkeiten bleibt unberührt.")
    expect(slip.locator(".badge")).to_have_text("nicht anwendbar")
    # how a comparison was made: the current text is the "before" side
    rog.get_by_role("tab", name=re.compile("Geltend")).click()
    rog.get_by_role("button", name="Wie ermittelt?").first.click()
    expect(page.locator("#dialog-body")).to_contain_text("selbst berechnet")
    expect(page.locator("#dialog-body")).to_contain_text("Maßgeblich ist allein die Drucksache")
    expect(page.locator("#dialog-body")).not_to_contain_text("Gesetzblatt")


@pytest.mark.spec("ENT-9")
def test_each_law_names_the_version_compared_with(app):
    page = app(BILL)
    newer = "Das Gesetz wurde nach dem Entwurf noch geändert. Einzelne Änderungen passen deshalb vielleicht nicht mehr."
    rog = article(page, re.compile("Raumordnungsgesetz")).locator(".compared")
    expect(rog).to_contain_text(re.compile(r"Verglichen mit der Fassung vom\s22\.07\.2026\."))
    expect(rog).to_contain_text(newer)
    hoai = article(page, re.compile("Honorarordnung")).locator(".compared")
    expect(hoai).to_have_text(re.compile(r"^\s*Verglichen mit der Fassung vom\s28\.03\.2023\.\s*$"))


@pytest.mark.spec("ENT-10")
def test_page_says_how_much_is_shown(app):
    page = app(BILL)
    expect(page.locator(".pub-header .shown-count")).to_have_text(re.compile(
        r"41 von 47\sÄnderungen werden im Vergleich gezeigt\. "
        r"Die übrigen finden Sie bei jedem Gesetz unter „Wortlaut im Entwurf“\."))


@pytest.mark.spec("ENT-11")
def test_comparison_has_no_text_of_the_begruendung(app):
    page = app(BILL)
    # Vorblatt and Begründung are only in "Allgemeine Informationen" …
    expect(page.locator(".article .bill-info, .article [data-info], .article .info-body")).to_have_count(0)
    # … the comparison of a law holds its §§ and nothing else: a heading, the old and the new wording
    rog = article(page, "Raumordnungsgesetz")
    expect(rog.locator('[data-body="synopse"] > .par')).to_have_count(3)
    expect(rog.locator('[data-body="synopse"] > :not(.par)')).to_have_count(0)
    expect(rog.locator('[data-body="synopse"] > .par > :not(header, table.diff)')).to_have_count(0)
    # … and the wording tab the instructions: what each says, what it does, whether it could be applied
    rog.get_by_role("tab", name=re.compile("Wortlaut im Entwurf")).click()
    expect(rog.locator(".instructions > li")).to_have_count(41)
    expect(rog.locator(".instructions > li > div > :not(.raw, .where, .msg)")).to_have_count(0)
    # the reasons for an instruction ("Zu Nummer 1 …") appear above, once their part is opened
    part = info(page).locator("details").nth(2)
    part.locator("summary").click()
    expect(part.get_by_role("heading", name=re.compile(r"^Zu Nummer 1\b"))).to_be_visible()
    expect(page.locator(".article").get_by_role("heading", name=re.compile(r"^Zu Nummer"))).to_have_count(0)


@pytest.mark.spec("ENT-12")
def test_general_information_holds_vorblatt_and_begruendung(app):
    page = app(BILL)
    expect(info(page).get_by_role("heading", level=2)).to_have_text("Allgemeine Informationen")
    expect(info(page).locator(".info-note")).to_contain_text("Text der Bundesregierung, nicht von bundesdiff")
    parts = info(page).locator("details")
    expect(parts).to_have_count(7)
    expect(parts.locator("summary")).to_have_text([
        "Zusammenfassung des Entwurfs (Vorblatt)", "Begründung: Allgemeiner Teil",
        "Begründung zu Artikel 4 (Änderung des Raumordnungsgesetzes)",
        "Begründung zu Artikel 5 (Änderung der Verwaltungsgerichtsordnung)",
        "Begründung zu Artikel 6 (Änderung der Honorarordnung für Architekten und Ingenieure)",
        "Begründung zu Artikel 12 (Änderung des Investitionsvorranggesetzes)",
        "Begründung zu Artikel 13 (Inkrafttreten)"])
    for part in parts.all():  # closed at first
        expect(part).not_to_have_attribute("open", "")
    assert info(page).bounding_box()["y"] + info(page).bounding_box()["height"] \
        <= page.locator(".article").first.bounding_box()["y"]
    parts.nth(0).locator("summary").click()
    expect(parts.nth(0).get_by_role("heading", name="A. Problem und Ziel")).to_be_visible()
    expect(parts.nth(0)).to_contain_text("Das Baugesetzbuch (BauGB) formt die kommunale Planungshoheit aus.")
    expect(parts.nth(0).get_by_role("heading", name="B. Lösung; Nutzen")).to_be_visible()
    parts.nth(2).locator("summary").click()
    expect(parts.nth(2).get_by_role("heading", name=re.compile(r"^Zu Nummer 1\b"))).to_be_visible()
    # the other parts stay closed and empty
    expect(parts.nth(1).locator(".info-body")).to_be_hidden()


@pytest.mark.spec("ENT-12")
def test_general_information_says_when_it_cannot_be_loaded(page, base_url):
    """The comparison is there, the texts of Vorblatt and Begründung are not: the part says so."""
    page.clock.set_fixed_time("2026-10-30T10:00:00")
    page.route("**/data/entwurf/21/6588-info.json", lambda route: route.fulfill(status=404, body="not found"))
    page.goto(base_url + "index.html" + BILL)
    part = info(page).locator("details").first
    part.locator("summary").click()
    expect(part.locator(".info-body")).to_contain_text("Dieser Text konnte nicht geladen werden.")
    expect(part.locator(".info-body").get_by_role("link", name=re.compile("Drucksache beim Deutschen Bundestag"))
           ).to_have_attribute("href", PDF)


@pytest.mark.spec("ENT-13")
def test_inkrafttreten_is_shown_as_text_with_its_placeholders(app):
    page = app(BILL)
    last = page.locator(".article").last
    expect(last.locator("h2")).to_have_text("Inkrafttreten")
    expect(last.locator(".art-no")).to_have_text("Artikel 13")
    expect(last.locator(".plain")).to_be_hidden()
    last.locator("summary").click()
    expect(last.locator(".plain")).to_contain_text("am … [einsetzen: Datum des ersten Tages")
    expect(page.locator(".pub-header")).not_to_contain_text("Ab wann gilt das?")
    expect(page.locator(".pub-header .glance")).to_contain_text("Im Entwurf steht noch kein Datum")


@pytest.mark.spec("ENT-14")
def test_link_to_the_drucksache_and_what_counts(app):
    page = app(BILL)
    link = page.locator(".pub-header").get_by_role("link", name="Drucksache beim Deutschen Bundestag (PDF, externe Seite)")
    expect(link).to_have_attribute("href", PDF)
    expect(page.locator(".pub-header .binding")).to_have_text(
        "Maßgeblich ist allein die Drucksache des Deutschen Bundestages.")
    expect(page.locator(".pub-header")).not_to_contain_text("recht.bund.de")


@pytest.mark.spec("ENT-15")
@pytest.mark.parametrize("answer", [{"status": 404, "body": "not found"}, {"status": 200, "body": "{ broken"},
                                    {"status": 200, "json": {"error": "PDF nicht lesbar", "failedAt": 0}}])
def test_bill_that_cannot_be_loaded(page, base_url, answer):
    page.clock.set_fixed_time("2026-10-30T10:00:00")
    page.route("**/data/entwurf/21/6588.json", lambda route: route.fulfill(**answer))
    page.goto(base_url + "index.html" + BILL)
    box = page.locator("#main .error-box")
    expect(box).to_contain_text("Dieser Gesetzentwurf kann gerade nicht angezeigt werden.")
    expect(box).to_contain_text("Bitte versuchen Sie es später noch einmal.")
    expect(box.get_by_role("link", name="Drucksache beim Deutschen Bundestag (PDF, externe Seite)")
           ).to_have_attribute("href", PDF)
    expect(page.locator(".navbar [aria-current=page]")).to_have_text("Gesetzentwürfe", use_inner_text=True)


@pytest.mark.spec("ENT-15")
def test_list_of_bills_that_cannot_be_loaded(page, base_url):
    page.clock.set_fixed_time("2026-10-30T10:00:00")
    page.route("**/data/entwuerfe.json", lambda route: route.fulfill(status=404, body="not found"))
    page.goto(base_url + "index.html" + BILLS)
    expect(page.get_by_role("heading", level=1, name="Gesetzentwürfe")).to_be_visible()
    expect(page.locator("#main .error-box")).to_contain_text("Die Liste der Gesetzentwürfe konnte nicht geladen werden.")


@pytest.mark.spec("ENT-16")
def test_about_page_and_help_name_the_bundestag_as_a_source(app):
    page = app("#/ueber")
    sources = page.locator("#main .about h2", has_text="Woher kommen die Daten?").locator("xpath=following-sibling::ul[1]")
    entry = sources.locator("li", has_text="Gesetzentwürfen")
    expect(entry.get_by_role("link", name="Deutscher Bundestag")).to_have_attribute("href", "https://www.bundestag.de")
    page.locator(".navbar").get_by_role("button", name="So funktioniert's").click()
    expect(page.locator("#help-sources")).to_contain_text(
        "Gesetzentwürfe stammen vom Deutschen Bundestag (dserver.bundestag.de).")


@pytest.mark.spec("ENT-17")
def test_help_explains_the_terms_of_a_bill(app):
    page = app(BILL)
    page.locator(".navbar").get_by_role("button", name="So funktioniert's").click()
    terms = page.locator("#help-terms dt")
    for term in ("Gesetzentwurf", "Drucksache", "Vorblatt und Begründung"):
        expect(terms.filter(has_text=re.compile(f"^{term}$"))).to_have_count(1)
    expect(page.locator("#help-terms")).to_contain_text("Er gilt noch nicht")
    expect(page.locator("#help-terms")).to_contain_text("So heißen die Unterlagen des Bundestages")


@pytest.mark.spec("A11Y-8")
def test_reading_position_stays_when_a_setting_changes_with_parts_open(app, page):
    """With a long part of the information open above the reading settings, the control the reader
    used stays where it was on the screen, and the part stays open and filled."""
    page.set_viewport_size(VIEWPORTS["desktop"])
    app(BILL)
    part = info(page).locator("details").nth(0)
    part.locator("summary").click()
    part.locator(".info-body p").first.wait_for()
    button = page.get_by_role("button", name="Im Text markiert", exact=True)
    button.focus()
    top = button.evaluate("e => e.getBoundingClientRect().top")
    page.keyboard.press("Enter")
    expect(button).to_have_attribute("aria-pressed", "true")
    expect(button).to_be_focused()
    expect(part).to_have_attribute("open", "")
    expect(part.locator(".info-body p").first).to_be_visible()
    page.wait_for_timeout(300)  # anything that would still move the page has happened by now
    assert abs(button.evaluate("e => e.getBoundingClientRect().top") - top) <= 2, "the control moved"


@pytest.mark.spec("ENT-15")
def test_unknown_bill_address(page, base_url):
    """An address that is none of the bills shown (mistyped, or outdated): the page says so, does not
    ask the reader to try again later and does not link to a Drucksache that may not exist."""
    page.clock.set_fixed_time("2026-10-30T10:00:00")
    page.goto(base_url + "index.html#/entwurf/21/1")
    box = page.locator("#main .error-box")
    expect(box).to_contain_text("Diesen Gesetzentwurf zeigt bundesdiff nicht.")
    expect(box).not_to_contain_text("später")
    expect(box.get_by_role("link")).to_have_count(1)
    box.get_by_role("link", name="Zur Liste der Gesetzentwürfe").click()
    expect(page.locator(".bill-list li")).to_have_count(1)


@pytest.mark.spec("ENT-15")
def test_bill_and_list_cannot_be_loaded(page, base_url):
    """Nothing can be loaded at all: the reader is asked to try again and still gets the Drucksache."""
    page.clock.set_fixed_time("2026-10-30T10:00:00")
    page.route("**/data/entwurf/21/6588.json", lambda route: route.fulfill(status=404, body="not found"))
    page.route("**/data/entwuerfe.json", lambda route: route.fulfill(status=404, body="not found"))
    page.goto(base_url + "index.html" + BILL)
    box = page.locator("#main .error-box")
    expect(box).to_contain_text("Dieser Gesetzentwurf kann gerade nicht angezeigt werden.")
    expect(box.get_by_role("link", name="Drucksache beim Deutschen Bundestag (PDF, externe Seite)")
           ).to_have_attribute("href", PDF)


def test_reading_settings_work_on_a_bill(app, page):
    """The same settings as for publications; the reader stays on the bill."""
    page.set_viewport_size(VIEWPORTS["desktop"])
    app(BILL)
    page.get_by_role("button", name="Im Text markiert").click()
    expect(page.locator("table.diff.inline").first).to_be_attached()
    expect(page.locator("table.diff.split")).to_have_count(0)
    expect(page.locator(".pub-header .draft-notice")).to_be_visible()
    expect(info(page).locator("details")).to_have_count(7)
    page.get_by_role("button", name="Nebeneinander").click()
    expect(page.locator("table.diff.split").first).to_be_attached()


def test_links_to_the_top_and_contents_bar_speak_of_the_bill(app, page):
    page.set_viewport_size(VIEWPORTS["desktop"])
    app(BILL)
    expect(page.get_by_role("link", name="Zum Anfang des Entwurfs")).to_have_count(5)
    expect(page.get_by_role("navigation", name="Inhalt dieses Entwurfs")).to_be_visible()
    page.get_by_role("link", name="Zum Anfang des Entwurfs").last.click()
    expect(page.locator(".pub-header h1")).to_be_focused()


def test_browser_back_returns_from_bill_to_list(app):
    page = app(BILLS)
    page.get_by_role("link", name=re.compile("Modernisierung des Städtebau")).click()
    expect(page.locator(".pub-header h1")).to_be_visible()
    page.go_back()
    expect(page.locator(".bill-list")).to_be_visible()


# ---------------------------------------------------------------- accessibility

@pytest.mark.spec("ENT-A2")
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("viewport", ["desktop", "tablet", "phone-landscape", "low-phone"])
def test_navbar_with_four_entries_is_one_row(app, page, viewport, theme):
    page.set_viewport_size(LOW_PHONE if viewport == "low-phone" else VIEWPORTS[viewport])
    app(BILL, theme=theme)
    entries = nav(page).locator("a, button")
    tops = {round(b["y"]) for b in (e.bounding_box() for e in entries.all()) if b and b["width"]}
    assert max(tops) - min(tops) < 12, f"entries on several rows: {sorted(tops)}"
    size = nav(page).evaluate("n => [n.scrollWidth, n.clientWidth]")
    assert size[0] <= size[1] + 1, f"navbar content {size[0]}px wide, room for {size[1]}px"
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    if viewport == "low-phone":  # too narrow for the names of four pages: they are behind "Menü" (NAV-3)
        nav(page).get_by_role("button", name="Menü").click()
        entry = page.locator("#menu").get_by_role("link", name="Gesetzentwürfe")
    else:
        entry = nav(page).get_by_role("link", name="Gesetzentwürfe")
    expect(entry).to_be_visible()
    expect(entry).to_have_attribute("aria-current", "page")


@pytest.mark.spec("ENT-A2")
def test_short_label_keeps_the_full_name(app, page):
    page.set_viewport_size(LOW_WIDE)
    app(BILLS)
    entry = nav(page).get_by_role("link", name="Gesetzentwürfe")
    expect(entry).to_have_text("Entwürfe", use_inner_text=True)
    expect(entry).to_have_attribute("aria-current", "page")


@pytest.mark.spec("ENT-A3")
def test_parts_open_and_close_with_the_keyboard(app):
    page = app(BILL)
    part = info(page).locator("details").nth(1)
    summary = part.locator("summary")
    summary.focus()
    page.keyboard.press("Enter")
    expect(part).to_have_attribute("open", "")
    expect(part.get_by_role("heading", name=re.compile("Zielsetzung"))).to_be_visible()
    expect(summary).to_be_focused()
    assert part.evaluate("d => d.open") is True  # the state screen readers announce ("erweitert")
    page.keyboard.press("Space")
    expect(part).not_to_have_attribute("open", "")
    expect(summary).to_be_focused()
    assert part.evaluate("d => d.open") is False
    outline = summary.evaluate("e => getComputedStyle(e).outlineStyle")
    assert outline != "none", "the focused control shows no focus ring"


@pytest.mark.spec("A11Y-5")
@pytest.mark.parametrize("viewport", ["small", "phone", "desktop"])
@pytest.mark.parametrize("route", [BILL, "#/1/2026/309"])
def test_abbreviations_of_laws_are_not_hyphenated(app, page, route, viewport):
    """"Investitionsvorranggesetz (In-/VorG)" on a 320 px phone: an abbreviation torn by a hyphen
    reads like another word. It stays whole, in the list of laws and in the heading of each law."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app(route)
    torn = page.locator("#main").evaluate("""root => [...root.querySelectorAll('.glance-laws a, .article h2')]
      .flatMap((e) => {
        const text = e.textContent, m = /\\(([^()]+)\\)\\s*$/.exec(text);
        if (!m) return [];
        const abbr = e.querySelector('.abbr');
        if (!abbr) return [`${text}: abbreviation not marked`];
        const r = document.createRange();
        r.selectNodeContents(abbr);
        const lines = new Set([...r.getClientRects()].filter((b) => b.width > 0).map((b) => Math.round(b.top)));
        const style = getComputedStyle(abbr);
        return lines.size > 1 || (style.hyphens || style.webkitHyphens) === 'auto' ? [`${text}: torn`] : [];
      })""")
    assert not torn, torn
    assert page.locator(".glance-laws .abbr").count() >= 2  # the check looked at something


@pytest.mark.spec("ENT-A4", "A11Y-1", "A11Y-4", "A11Y-5")
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_layout_with_parts_of_the_information_open(app, page, viewport, theme):
    """PAGES has the list and the bill; this is the bill with a short and a long part open."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app(BILL, theme=theme)
    parts = info(page).locator("details")
    for i in (0, 2):
        parts.nth(i).locator("summary").click()
        parts.nth(i).locator(".info-body p").first.wait_for()
    settle(page)
    page.screenshot(path=_shot(page, f"bill-info-open-{viewport}-{theme}"), full_page=True)
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("ENT-A4")
def test_bill_pages_are_among_the_checked_pages():
    assert PAGES["bills"] == "#/entwuerfe" and PAGES["bill"] == "#/entwurf/21/6588"


@pytest.mark.spec("ENT-A4", "A11Y-1")
@pytest.mark.parametrize("viewport", ["desktop", "small"])
def test_layout_of_a_bill_with_everything_expanded(app, page, viewport):
    """Inline view, unchanged text shown, wording tabs and the Inkrafttreten open: the longest texts."""
    page.set_viewport_size(VIEWPORTS[viewport])
    app(BILL)
    page.get_by_role("button", name="Im Text markiert").click()
    page.locator("#only-changes").uncheck()
    for tab in page.locator(".tabs button:not(.active)").all():
        tab.click()
    page.locator(".article details.other summary").click()
    issues = layout_issues(page)
    assert not issues, "\n".join(issues)


@pytest.mark.spec("ENT-18")
def test_heading_of_a_new_teil_stands_above_its_first_par(app):
    page = app(BILL)
    title = page.get_by_role("heading", name="§ 135e Wiederherstellungssatzung")
    par = article(page, re.compile("Baugesetzbuch")).locator("section.par").filter(has=title)
    line = par.locator(".new-part")
    expect(line).to_have_text("Neu: Achter Teil – Besondere Regelungen für städtische Ökosystemgebiete im Sinne "
                              "des Artikels 8 der Verordnung (EU) 2024/1991")
    assert line.bounding_box()["y"] + line.bounding_box()["height"] <= title.bounding_box()["y"]
    expect(par.locator("table.diff")).not_to_contain_text("Achter Teil")
    expect(page.locator(".new-part")).to_have_count(1)  # only where the bill inserts a new part


@pytest.mark.spec("RTY-4")
def test_a_bill_whose_law_did_not_load_points_to_its_own_wording(app, page):
    data = json.loads((FIXTURES / "data" / "entwurf" / "21" / "6588.json").read_text())
    _law_not_loaded(next(a for a in data["articles"] if a["number"] == "12"))
    page.route("**/data/entwurf/21/6588.json", lambda route: route.fulfill(json=data))
    app(BILL)
    expect(article(page, re.compile("Investitionsvorrang")).locator(".error")).to_have_text(re.compile(
        r"bis zum\s17\.11\.2026\. Bis dahin stehen die Änderungen nur im Wortlaut des Entwurfs\.$"))
