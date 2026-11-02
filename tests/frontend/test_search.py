"""Spec 002: the search window (Strg K)."""

from __future__ import annotations

import gzip
import json
import re

import pytest
from playwright.sync_api import Page, expect

from .conftest import FIXTURES, VIEWPORTS

TABAK = "#/1/2026/309"


def open_search(page: Page):
    page.get_by_role("button", name="Suchen").click()
    return page.locator("#search-dialog").get_by_role("combobox")


def results(page: Page):
    return page.locator("#search-results [role=option]")


@pytest.mark.spec("SRCH-1")
def test_search_button_in_the_navbar(app, page):
    app()
    button = page.get_by_role("navigation", name="Hauptnavigation").get_by_role("button", name="Suchen")
    expect(button).to_contain_text("Suchen")
    expect(button.locator("kbd")).to_have_text("Strg K")
    expect(button.locator("svg")).to_be_visible()
    page.set_viewport_size(VIEWPORTS["small"])
    expect(button).to_be_visible()
    expect(button.locator("svg")).to_be_visible()
    expect(button.locator(".long").first).to_be_hidden()


@pytest.mark.spec("SRCH-2")
def test_open_and_close_the_search_window(app):
    page = app(TABAK)
    field = open_search(page)
    expect(field).to_be_focused()
    page.keyboard.press("Escape")
    expect(page.locator("#search-dialog")).not_to_have_attribute("open", "")
    expect(page.get_by_role("button", name="Suchen")).to_be_focused()
    page.keyboard.press("Control+k")
    expect(field).to_be_focused()
    page.get_by_role("button", name="Schließen").last.click()
    expect(field).to_be_hidden()
    expect(page.locator(".pub-header h1")).to_have_text("Gesetz zur Änderung des Tabaksteuergesetzes")
    page.keyboard.press("Meta+k")
    expect(field).to_be_focused()
    page.keyboard.press("Escape")
    page.keyboard.press("/")
    expect(field).to_be_focused()
    page.keyboard.type("/")  # inside the field "/" is just a character
    expect(field).to_have_value("/")


@pytest.mark.spec("SRCH-2")
def test_escape_closes_even_with_text_in_the_field(app):
    page = app()
    field = open_search(page)
    field.fill("steuer")
    page.keyboard.press("Escape")
    expect(field).to_be_hidden()
    expect(page.get_by_role("button", name="Suchen")).to_be_focused()


@pytest.mark.spec("SRCH-2")
def test_slash_does_not_open_while_typing_elsewhere(app):
    page = app()
    page.get_by_label("Art", exact=True).focus()
    page.keyboard.press("/")
    expect(page.locator("#search-dialog").get_by_role("combobox")).to_be_hidden()


@pytest.mark.spec("SRCH-3", "SRCH-4")
@pytest.mark.parametrize("query", ["Tabaksteuer", "TabStG", "Verbrauchsteuern", "BGBl. 2026 I Nr. 309",
                                   "2026 I 309", "Bundesministerium der Finanzen"])
def test_finds_by_title_law_topic_citation_and_ministry(app, query):
    page = app()
    open_search(page).fill(query)
    expect(results(page).filter(has_text="Tabaksteuer").first).to_be_visible()


@pytest.mark.spec("SRCH-4")
def test_results_are_grouped_and_appear_from_the_first_letter(app):
    page = app()
    field = open_search(page)
    field.press_sequentially("t")
    expect(results(page).first).to_be_visible()
    field.fill("tabaksteuer")
    expect(page.locator("#search-results .search-group-title")).to_have_text(["Gesetze", "Veröffentlichungen"])
    law = page.locator("#search-results [role=group]").first.locator("[role=option]").first
    expect(law).to_contain_text("Tabaksteuergesetz (TabStG)")
    expect(law).to_contain_text("geändert durch")
    expect(page.locator("#search-status")).to_have_text(re.compile(r"\d+ Treffer"))


@pytest.mark.spec("SRCH-4")
def test_results_within_50_ms_on_a_year_of_data(app, page):
    listing = json.loads((FIXTURES / "data" / "publications-1.json").read_text())
    year = [dict(p, id=f"{p['id']}-{i}") for i in range(8) for p in listing]  # ~ a year: 480 entries
    page.route("**/data/publications-1.json", lambda route: route.fulfill(json=year))
    app()
    open_search(page)
    ms = page.evaluate("""() => {
        const field = document.querySelector('#search-input'); let worst = 0;
        for (const q of ['s', 'st', 'steuer', 'verordnung änderung', 'bgbl 2026 i 30']) {
            const t = performance.now(); field.value = q; field.dispatchEvent(new Event('input'));
            worst = Math.max(worst, performance.now() - t); }
        return worst; }""")
    assert ms < 50, f"search took {ms:.0f} ms"


@pytest.mark.spec("SRCH-5")
@pytest.mark.parametrize("query, finds", [
    ("TABAK", "Tabaksteuergesetzes"),
    ("steuer tabak", "Tabaksteuergesetzes"),  # any order
    ("aenderung tabak", "Tabaksteuergesetzes"),  # ae = ä
    ("strasse", "Straßenverkehr"),  # ss = ß
    ("integrationskurstest", "Integrationskurstestverordnung"),  # part of a word
])
def test_forgiving_matching(app, query, finds):
    page = app()
    open_search(page).fill(query)
    expect(page.locator("#search-results")).to_contain_text(finds)


@pytest.mark.spec("SRCH-6")
def test_matches_are_highlighted_by_more_than_colour(app):
    page = app()
    open_search(page).fill("tabak")
    mark = page.locator("#search-results mark").first
    expect(mark).to_have_text(re.compile("^tabak$", re.I))
    style = mark.evaluate("e => { const s = getComputedStyle(e); return [s.fontWeight, s.textDecorationLine]; }")
    assert int(style[0]) >= 600 and "underline" in style[1]


@pytest.mark.spec("SRCH-7")
def test_keyboard_selection_and_recent_searches(app):
    page = app()
    field = open_search(page)
    field.fill("tabaksteuer")
    field.press("ArrowDown")
    first = results(page).first
    expect(first).to_have_attribute("aria-selected", "true")
    expect(field).to_have_attribute("aria-activedescendant", first.get_attribute("id"))
    field.press("ArrowDown")
    expect(results(page).nth(1)).to_have_attribute("aria-selected", "true")
    field.press("ArrowUp")
    field.press("Enter")
    expect(page).to_have_url(re.compile("#/1/2026/309$"))
    expect(page.locator(".pub-header h1")).to_have_text("Gesetz zur Änderung des Tabaksteuergesetzes")

    field = open_search(page)
    expect(field).to_have_value("")
    recent = page.locator("#search-results [role=group]", has_text="Zuletzt gesucht")
    expect(recent.locator("[role=option]")).to_have_text(["tabaksteuer"])
    recent.locator("[role=option]").first.click()
    expect(field).to_have_value("tabaksteuer")
    field.fill("")
    page.get_by_role("button", name="Verlauf löschen").click()
    expect(page.locator("#search-results")).not_to_contain_text("tabaksteuer")


@pytest.mark.spec("SRCH-8")
def test_nothing_found_says_what_to_try(app):
    page = app()
    open_search(page).fill("gibtesnicht")
    status = page.locator("#search-status")
    expect(status).to_contain_text("Nichts gefunden für „gibtesnicht“.")
    expect(status).to_contain_text("Abkürzung")
    expect(results(page)).to_have_count(0)


@pytest.mark.spec("SRCH-9")
def test_index_is_small_enough_for_a_year():
    raw = (FIXTURES / "data" / "publications-1.json").read_bytes()
    listing = json.loads(raw)
    compact = json.dumps(listing, ensure_ascii=False, separators=(",", ":")).encode()  # as exported
    per_entry = len(gzip.compress(compact)) / len(listing)
    assert per_entry * 450 < 300_000, f"{per_entry * 450 / 1000:.0f} KB for a year"


@pytest.mark.spec("SRCH-9")
def test_search_works_offline_once_loaded(app, page):
    app()
    page.context.set_offline(True)
    open_search(page).fill("tabak")
    expect(results(page).first).to_be_visible()
    page.context.set_offline(False)


@pytest.mark.spec("SRCH-4")
def test_end_of_the_result_list_is_visible_above_the_window_edge(app, page):
    """The rule under the list must not merge with the window's edge, or a cut result looks broken."""
    app()
    open_search(page).fill("steuer")
    gap = page.evaluate("""() => document.querySelector('#search-dialog').getBoundingClientRect().bottom
                                 - document.querySelector('#search-results').getBoundingClientRect().bottom""")
    assert gap >= 8, f"only {gap:.0f}px between the list and the window edge"
