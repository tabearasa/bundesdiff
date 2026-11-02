"""Spec 002: the timeline as start page, "Was ändert sich demnächst?", reading without a sidebar."""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import FIXTURES, VIEWPORTS

TABAK = "#/1/2026/309"
UPCOMING = "#/?ansicht=demnaechst"


def entry(page: Page, pub_id: str):
    return page.locator(f'.tl-entry[data-id="{pub_id}"]')


# ---------------------------------------------------------------- layout

@pytest.mark.spec("TL-1")
@pytest.mark.parametrize("viewport", ["desktop", "phone"])
def test_no_sidebar_and_the_text_is_one_centred_page(app, page, viewport):
    page.set_viewport_size(VIEWPORTS[viewport])
    app(TABAK)
    expect(page.locator(".sidebar, #pub-list")).to_have_count(0)
    header = page.locator(".pub-header").bounding_box()
    width = page.evaluate("document.documentElement.clientWidth")  # without the scrollbar
    assert abs(header["x"] + header["width"] / 2 - width / 2) <= 2, "the page is not centred"


@pytest.mark.spec("TL-2")
def test_read_on_to_older_and_newer_publications(app):
    page = app(TABAK)
    pager = page.get_by_role("navigation", name="Weiterlesen")
    older = pager.get_by_role("link", name=re.compile("Ältere Veröffentlichung"))
    newer = pager.get_by_role("link", name=re.compile("Neuere Veröffentlichung"))
    expect(older).to_have_attribute("href", "#/1/2026/308")
    expect(newer).to_have_attribute("href", "#/1/2026/310")
    expect(older).to_contain_text("Spitzensports")  # the title, so the reader knows where it leads
    newer.click()
    expect(page).to_have_url(re.compile("#/1/2026/310$"))
    # the newest publication has nothing newer
    page = app("#/1/2026/326")
    expect(page.get_by_role("navigation", name="Weiterlesen").get_by_role("link")).to_have_count(1)


# ---------------------------------------------------------------- timeline

@pytest.mark.spec("TL-3")
def test_start_page_is_a_timeline_by_month_and_day(app):
    page = app()
    expect(page.locator("h1")).to_have_text("Was ändert sich im Gesetz?")
    expect(page.locator(".timeline h2")).to_have_text(["Oktober 2026", "September 2026"])
    first_day = page.locator(".timeline h3").first
    expect(first_day).to_contain_text("30. Oktober")
    expect(first_day).to_contain_text("heute")
    expect(page.locator(".tl-entry")).to_have_count(60)
    tabak = entry(page, "1/2026/309")
    expect(tabak.locator(".typ")).to_have_text("Gesetz")
    expect(tabak).to_contain_text("Gesetz zur Änderung des Tabaksteuergesetzes")
    expect(tabak).to_contain_text("Verbrauchsteuern und Monopole")
    expect(tabak.locator(".tl-changes")).to_have_text("ändert 2 Gesetze")
    expect(entry(page, "1/2026/306").locator(".tl-changes")).to_have_text("ändert 1 Gesetz")
    expect(entry(page, "1/2026/315").locator(".tl-changes")).to_have_text("ändert kein Gesetz")
    expect(entry(page, "1/2026/322").locator(".tl-changes")).to_have_text("noch nicht ausgewertet")
    # the rule and the day marks are decoration
    assert page.locator(".timeline").evaluate(
        "e => [...e.querySelectorAll('.tl-mark')].every(m => m.getAttribute('aria-hidden') === 'true')")


@pytest.mark.spec("TL-4")
def test_filters_are_kept_in_the_address(app, page):
    app()
    page.get_by_label("Art", exact=True).select_option("Verordnung")
    expect(page).to_have_url(re.compile(r"art=Verordnung"))
    types = page.locator(".tl-entry .typ").all_inner_texts()
    assert types and {t.lower() for t in types} == {"verordnung"}
    page.reload()
    expect(page.get_by_label("Art", exact=True)).to_have_value("Verordnung")
    expect(page.locator(".tl-entry .typ").first).to_have_text(re.compile("verordnung", re.I))

    page.get_by_label("Art", exact=True).select_option("")
    expect(page).not_to_have_url(re.compile(r"art="))
    expect(page.locator(".tl-entry")).to_have_count(60)


@pytest.mark.spec("TL-4")
def test_there_is_only_one_filter_and_old_links_show_everything(app, page):
    """The checkbox "nur Gesetzesänderungen" was removed: readers could not tell it from "Art"."""
    app("#/?nur=aenderungen")
    expect(page.locator(".tl-filters select")).to_have_count(1)
    expect(page.locator(".tl-filters input")).to_have_count(0)
    expect(page.get_by_text("Gesetzesänderungen")).to_have_count(0)
    expect(page.locator(".tl-entry")).to_have_count(60)
    expect(entry(page, "1/2026/315")).to_have_count(1)  # changes nothing, still shown
    expect(entry(page, "1/2026/315")).to_contain_text("ändert kein Gesetz")
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    expect(page).to_have_url(re.compile(r"art=Gesetz"))
    expect(page).not_to_have_url(re.compile(r"nur="))


@pytest.mark.spec("TL-4")
def test_choosing_a_filter_keeps_the_same_controls(app, page):
    """Safari on the iPhone opened the list of "Art" a second time: the change rebuilt the
    page and put the focus on a new list, while the first one was still open."""
    app()
    page.evaluate("window.oldSelect = document.querySelector('#type-filter')")
    page.get_by_label("Art", exact=True).focus()  # select_option alone does not focus the list
    page.get_by_label("Art", exact=True).select_option("Verordnung")
    expect(page).to_have_url(re.compile(r"art=Verordnung"))
    assert page.evaluate("document.querySelector('#type-filter') === window.oldSelect")
    assert page.evaluate("document.activeElement === window.oldSelect")
    types = page.locator(".tl-entry .typ").all_inner_texts()
    assert types and {t.lower() for t in types} == {"verordnung"}
    expect(page.locator(".list-count")).to_have_text(re.compile(r"^\d+\u00a0Veröffentlichungen"))
    expect(page.locator(".tl-focus")).to_have_count(1)


@pytest.mark.spec("TL-4", "A11Y-6")
def test_screen_readers_hear_how_many_publications_the_filter_shows(app, page):
    """The focus stays on the list of "Art": without a status message nothing says the timeline changed."""
    app()
    status = page.locator(".tl-filters [role=status]")
    expect(status).to_have_count(1)
    page.get_by_label("Art", exact=True).focus()
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    expect(status).to_have_text("16 Veröffentlichungen der Art „Gesetz“")
    assert status.evaluate("e => e.getBoundingClientRect().width") <= 1  # heard, not seen
    page.get_by_label("Art", exact=True).select_option("")
    expect(status).to_have_text("60 Veröffentlichungen aller Arten")


@pytest.mark.spec("TL-4", "TL-6", "A11Y-6")
def test_in_the_upcoming_view_the_status_counts_what_is_shown(app, page):
    app("#/?ansicht=demnaechst")
    status = page.locator(".tl-filters [role=status]")
    page.get_by_label("Art", exact=True).focus()
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    coming = page.locator(".timeline.upcoming > .tl-month").first.locator(".tl-day:not(.tl-undated)")
    expect(status).not_to_have_text("")
    n = coming.count()  # the dates under "Demnächst", not the entries of "Kürzlich …"
    assert n >= 1
    expect(status).to_have_text(f"{n}\u00a0{'kommender Termin' if n == 1 else 'kommende Termine'} für Veröffentlichungen der Art „Gesetz“")
    page.get_by_label("Art", exact=True).select_option("Sonstiges")
    expect(page.locator(".timeline.upcoming .tl-entry")).to_have_count(0)
    expect(status).to_have_text("Keine kommenden Termine für Veröffentlichungen der Art „Sonstiges“")


@pytest.mark.spec("NAV-1")
def test_veroeffentlichungen_with_ctrl_still_opens_a_new_tab(app, page):
    app("#/?art=Verordnung")
    with page.context.expect_page() as new_tab:
        page.locator(".navbar").get_by_role("link", name="Veröffentlichungen").click(modifiers=["ControlOrMeta"])
    expect(new_tab.value).to_have_url(re.compile(r"#/\?art=Verordnung$"))


@pytest.mark.spec("TL-6")
def test_the_type_name_in_the_empty_text_is_not_hyphenated(app, page):
    page.set_viewport_size({"width": 320, "height": 568})
    app("#/?art=Sonstiges&ansicht=demnaechst")
    name = page.locator(".tl-empty .keep").first
    expect(name).to_have_text("„Sonstiges“")
    assert len({round(r["top"]) for r in name.evaluate("e => [...e.getClientRects()].map(r => r.toJSON())")}) == 1


@pytest.mark.spec("TL-4")
@pytest.mark.parametrize("art", ["Unbekannt", "gesetz"])
def test_a_link_with_an_unknown_type_does_not_show_an_empty_list(app, page, art):
    app(f"#/?art={art}")
    if art == "gesetz":  # the type in other letters: the same type
        expect(page.get_by_label("Art", exact=True)).to_have_value("Gesetz")
        expect(page.locator(".tl-entry")).to_have_count(16)
    else:  # unknown: the whole timeline, and the list says so
        expect(page.get_by_label("Art", exact=True)).to_have_value("")
        expect(page.locator(".tl-entry")).to_have_count(60)
    expect(page.locator(".tl-empty")).to_have_count(0)


@pytest.mark.spec("TL-4")
def test_the_removed_filter_leaves_the_address_on_every_change(app, page):
    app("#/?nur=aenderungen")
    page.get_by_role("button", name="Was ändert sich demnächst?").click()
    expect(page).to_have_url(re.compile(r"ansicht=demnaechst"))
    expect(page).not_to_have_url(re.compile(r"nur="))


@pytest.mark.spec("TL-6", "TL-4")
def test_filtered_upcoming_view_says_it_shows_one_type(app, page):
    app("#/?art=Sonstiges&ansicht=demnaechst")
    expect(page.locator(".timeline.upcoming .tl-empty").first).to_have_text(
        "Für Veröffentlichungen der Art „Sonstiges“ sind keine kommenden Termine bekannt, "
        "an denen etwas in Kraft oder außer Kraft tritt.")


@pytest.mark.spec("TL-4")
def test_month_row_jumps_to_the_month(app):
    page = app()
    page.get_by_role("navigation", name="Monate").get_by_role("link", name="September 2026").click()
    expect(page.get_by_role("heading", name="September 2026")).to_be_in_viewport()
    expect(page).not_to_have_url(re.compile("#/1/"))  # still the timeline


@pytest.mark.spec("TL-5")
def test_order_switch(app):
    page = app()
    by_date = page.get_by_role("button", name="Nach Veröffentlichung")
    upcoming = page.get_by_role("button", name="Was ändert sich demnächst?")
    expect(by_date).to_have_attribute("aria-pressed", "true")
    upcoming.click()
    expect(upcoming).to_have_attribute("aria-pressed", "true")
    expect(page).to_have_url(re.compile("ansicht=demnaechst"))
    expect(page.locator(".timeline h2").first).to_have_text("Demnächst")
    by_date.click()
    expect(page.locator(".timeline h2").first).to_have_text("Oktober 2026")


@pytest.mark.spec("TL-6")
def test_upcoming_changes_by_date(app):
    page = app(UPCOMING)
    expect(page.locator(".timeline h2")).to_have_text(["Demnächst", "Kürzlich in Kraft getreten"])
    soon = page.locator(".tl-month").nth(0)
    expect(soon.locator("h3")).to_have_text([
        re.compile("1. November 2026"), re.compile("1. Januar 2027"), re.compile("1. August 2027")])
    expect(soon.locator(".tl-entry").first).to_contain_text("Integrationskurstestverordnung")
    expect(soon.locator(".tl-what").first).to_have_text("tritt in Kraft: die ganze Verordnung")
    rest = soon.locator(".tl-day").nth(2)
    expect(rest.locator(".tl-what")).to_have_text("tritt in Kraft: die übrigen Teile der Verordnung")
    recent = page.locator(".tl-month").nth(1)
    expect(recent.locator("h3")).to_have_text([re.compile("22. Oktober 2026"), re.compile("21. Oktober 2026")])
    expect(recent.locator(".tl-what").first).to_have_text(
        "ist in Kraft getreten: Artikel 2 – Verordnung über die Berufsausbildung zum Landwirt/zur Landwirtin")
    expect(recent.locator(".tl-entry").nth(1)).to_contain_text("Tabaksteuergesetzes")


@pytest.mark.spec("TL-7")
def test_each_date_shows_its_sentence_and_unclear_dates_are_not_guessed(app, page):
    listing = json.loads((FIXTURES / "data" / "publications-1.json").read_text())
    for p in listing:
        if p["id"] == "1/2026/309":
            p["inForce"].append({"date": None, "retroactive": False, "kind": "in", "whole": False, "rest": False,
                                 "subject": "Artikel 2", "articles": ["2"],
                                 "sentence": "Artikel 2 tritt an dem Tag in Kraft, an dem die Kommission zustimmt."})
    page.route("**/data/publications-1.json", lambda route: route.fulfill(json=listing))
    app(UPCOMING)
    wording = page.locator(".tl-day").first.locator("details.tl-source")
    expect(wording.locator("summary")).to_have_text("Wortlaut")
    wording.locator("summary").click()
    expect(wording).to_contain_text("Diese Verordnung tritt am 1. November 2026 in Kraft.")
    unclear = page.locator(".tl-month").filter(has=page.get_by_role("heading", name="Datum nicht sicher erkannt"))
    expect(unclear).to_contain_text("Tabaksteuergesetzes")
    expect(unclear).to_contain_text("an dem die Kommission zustimmt")  # the sentence is shown right away


@pytest.mark.spec("TL-7")
def test_a_sentence_that_was_not_understood_names_nothing(app, page):
    """Nothing is presented as taking effect when the subject could not be read – not even
    "ein Teil der Veröffentlichung": the reader is pointed to the wording below."""
    listing = json.loads((FIXTURES / "data" / "publications-1.json").read_text())
    for p in listing:
        if p["id"] == "1/2026/309":
            p["inForce"].append({"date": None, "retroactive": False, "kind": "unclear", "whole": False, "rest": False,
                                 "subject": None, "articles": [],
                                 "sentence": "Sie tritt am 31. Dezember 2031 außer Kraft."})
    page.route("**/data/publications-1.json", lambda route: route.fulfill(json=listing))
    app(UPCOMING)
    unclear = page.locator(".tl-month").filter(has=page.get_by_role("heading", name="Datum nicht sicher erkannt"))
    entry = unclear.locator(".tl-entries > li", has_text="Sie tritt am 31. Dezember 2031")
    expect(entry.locator(".tl-what")).to_have_text("Was in Kraft oder außer Kraft tritt, steht im Wortlaut")
    expect(entry).to_contain_text("Tabaksteuergesetzes")


@pytest.mark.spec("TL-6")
def test_recent_heading_names_rules_that_expired(app, page):
    listing = json.loads((FIXTURES / "data" / "publications-1.json").read_text())
    for p in listing:
        if p["id"] == "1/2026/309":
            p["inForce"].append({"date": "2026-10-20", "retroactive": False, "kind": "out", "whole": False, "rest": False,
                                 "subject": "Artikel 3", "articles": ["3"],
                                 "sentence": "Artikel 3 tritt am 20. Oktober 2026 außer Kraft."})
    page.route("**/data/publications-1.json", lambda route: route.fulfill(json=listing))
    app(UPCOMING)
    recent = page.locator(".tl-month").filter(
        has=page.get_by_role("heading", name="Kürzlich in Kraft oder außer Kraft getreten"))
    expect(recent).to_contain_text("ist außer Kraft getreten")
    # the same day split in two or "Termine" counting entries of "Kürzlich …": neither
    page.get_by_label("Art", exact=True).focus()
    page.get_by_label("Art", exact=True).select_option("Gesetz")
    n = page.locator(".timeline.upcoming > .tl-month").first.locator(".tl-day:not(.tl-undated)").count()
    expect(page.locator(".tl-filters [role=status]")).to_contain_text(f"{n}\u00a0kommende")


@pytest.mark.spec("TL-8")
def test_upcoming_view_says_dates_are_read_automatically(app):
    page = app(UPCOMING)
    note = page.locator(".tl-note")
    expect(note).to_contain_text("automatisch")
    expect(note).to_contain_text("verbindlich ist allein das Bundesgesetzblatt")
