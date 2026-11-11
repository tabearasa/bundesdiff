"""Spec 017: an Artikel whose law could not be loaded because a source did not answer is analysed
again by the following daily runs, for 7 days. No network: the sources are replaced."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import httpx
import pytest

from bundesdiff import analysis, drafts, export, sources, store
from bundesdiff.amendments import Article
from bundesdiff.engine import Snapshots
from bundesdiff.model import Node
from bundesdiff.pdftext import Line

T0 = dt.datetime(2026, 11, 10, 19, 35, tzinfo=dt.UTC)  # the nightly run in which the source did not answer
HOUR, DAY, MINUTE = dt.timedelta(hours=1), dt.timedelta(days=1), dt.timedelta(minutes=1)
LAW = "Musterverordnung"  # made up: these tests are about retrying, not about the wording
REF = sources.LawRef("neuris", LAW, "MusterV", "eli/bund/bgbl-1/2020/s1", "2026-10-01",
                     "https://example.invalid/musterv.xml")
PUB = sources.Publication("1", 2026, "326", "Verordnung zur Änderung der Musterverordnung", "2026-10-30",
                          "Verordnung", "Bundesregierung", "BGBl. 2026 I Nr. 326", "", "")
NEW = sources.Publication("1", 2026, "330", "Gesetz zur Änderung des Mustergesetzes", "2026-11-10",
                          "Gesetz", "Bundestag", "BGBl. 2026 I Nr. 330", "", "")


def article(number: str) -> Article:
    text = [f"Die {LAW} vom 1. Januar 2020 (BGBl. I S. 1), die zuletzt durch Artikel 1 der Verordnung",
            "vom 1. Juli 2025 (BGBl. 2025 I Nr. 1) geändert worden ist, wird wie folgt geändert:",
            "1. In § 1 wird die Angabe „alt“ durch die Angabe „neu“ ersetzt."]
    return Article(number, f"Änderung der {LAW}", [Line(t, 64.0, 1, 10.0, False) for t in text])


def sources_answer(monkeypatch) -> None:
    monkeypatch.setattr(analysis, "resolve_law", lambda am: REF)
    monkeypatch.setattr(sources, "load_law", lambda ref: Node("law", parts=[
        Node("par", "§ 1", "Zweck", parts=["Der Wert ist alt."])]))


def sources_silent(monkeypatch) -> None:
    def timeout(am):
        raise httpx.ConnectTimeout("timed out")
    monkeypatch.setattr(analysis, "resolve_law", timeout)


def entry(number: str, now: dt.datetime) -> dict:
    return analysis.article_entry(article(number), state_of=lambda ref: "pre",
                                  snapshots_of=lambda ref: Snapshots(lambda key: None), now=now)


def issue_read_again(monkeypatch) -> None:
    """The PDF of the issue is read again for a retry: it has the Artikel 1 and 2."""
    doc = SimpleNamespace(articles=[article("1"), article("2")])
    monkeypatch.setattr(analysis, "_prepare", lambda pub: (
        doc, dt.date(2026, 10, 30), lambda ref: "pre", lambda ref: Snapshots(lambda key: None)))


@pytest.fixture
def stored(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    issue_read_again(monkeypatch)


def run(now: dt.datetime, pubs=(PUB,), max_new: int = 50) -> dict:
    return export.update_results(list(pubs), max_new, 24, now=now)


@pytest.mark.spec("RTY-1")
def test_an_artikel_whose_law_did_not_load_is_marked_for_another_try(monkeypatch):
    sources_silent(monkeypatch)
    e = entry("2", T0)
    assert e["lookupFailed"] == {"first": "2026-11-10T19:35:00+00:00", "last": "2026-11-10T19:35:00+00:00",
                                 "tries": 1, "until": "2026-11-17"}
    assert e["error"] == "Der aktuelle Text dieses Gesetzes konnte nicht geladen werden."
    assert [i["status"] for i in e["instructions"]] == ["unsupported"] and e["pars"] == []
    assert not analysis.retry_due(e, T0 + 19 * HOUR)
    assert analysis.retry_due(e, T0 + 20 * HOUR)  # the next daily run may start a little earlier


@pytest.mark.spec("RTY-1")
def test_the_next_daily_run_analyses_only_that_artikel_again(monkeypatch, stored):
    sources_answer(monkeypatch)
    good = entry("1", T0)
    sources_silent(monkeypatch)
    store.save_result(PUB.id, {"publication": {"id": PUB.id}, "articles": [good, entry("2", T0)]})
    sources_answer(monkeypatch)
    assert run(T0 + 10 * HOUR)["retried"] == 0  # the same night: not yet
    assert run(T0 + DAY - 5 * MINUTE)["retried"] == 1
    first, second = store.load_result(PUB.id)["articles"]
    assert first == good  # what was already shown stays as it is
    assert "lookupFailed" not in second and "error" not in second
    assert [p["key"] for p in second["pars"]] == ["§1"]


@pytest.mark.spec("RTY-2")
def test_a_law_the_sources_do_not_have_is_not_tried_again(monkeypatch):
    monkeypatch.setattr(analysis, "resolve_law", lambda am: None)
    e = entry("2", T0)
    assert e["error"] == f"„{LAW}“ wurde in der Rechtsinformationsplattform nicht gefunden."
    assert "lookupFailed" not in e
    assert not analysis.retry_due(e, T0 + 3 * DAY)


@pytest.mark.spec("RTY-2", "RTY-1")
def test_a_page_of_laws_that_did_not_load_is_not_taken_as_not_found(monkeypatch):
    """The search for short titles on gesetze-im-internet.de skipped pages that did not load, so a
    timeout there looked like "nicht gefunden" and would never have been tried again."""
    monkeypatch.setattr(sources, "_gii_toc", lambda: [])

    def silent(url, **kw):
        raise httpx.ConnectTimeout("timed out")
    monkeypatch.setattr(sources, "fetch", silent)
    with pytest.raises(httpx.ConnectTimeout):
        sources.gii_slug(LAW)

    def missing(url, **kw):
        raise httpx.HTTPStatusError("404", request=httpx.Request("GET", url), response=httpx.Response(404))
    monkeypatch.setattr(sources, "fetch", missing)
    assert sources.gii_slug(LAW) is None  # a page that does not exist is still skipped


@pytest.mark.spec("RTY-3")
def test_after_seven_days_the_failure_is_final(monkeypatch, stored):
    sources_silent(monkeypatch)
    store.save_result(PUB.id, {"publication": {"id": PUB.id}, "articles": [entry("1", T0), entry("2", T0)]})
    for n in range(1, 8):  # the daily runs, each a few minutes earlier than the night before
        assert run(T0 + n * DAY - n * MINUTE)["retried"] == 1
    failed = store.load_result(PUB.id)["articles"][1]["lookupFailed"]
    assert failed == {"first": "2026-11-10T19:35:00+00:00", "last": "2026-11-17T19:28:00+00:00", "tries": 8,
                      "until": "2026-11-17", "final": True}
    assert run(T0 + 9 * DAY)["retried"] == 0


@pytest.mark.spec("RTY-5")
def test_failures_stored_before_this_rule_are_tried_again(monkeypatch, stored):
    sources_silent(monkeypatch)
    old = entry("2", T0)
    del old["lookupFailed"]
    old["error"] = "Fehler bei der Suche des Gesetzes: timed out"  # as stored until 2026-11-10
    store.save_result(PUB.id, {"publication": {"id": PUB.id}, "articles": [old]})
    later = T0 + 2 * HOUR
    assert run(later)["retried"] == 1
    (again,) = store.load_result(PUB.id)["articles"]
    assert again["lookupFailed"] == {"first": "2026-11-10T21:35:00+00:00", "last": "2026-11-10T21:35:00+00:00",
                                     "tries": 1, "until": "2026-11-17"}  # the 7 days start now


@pytest.mark.spec("RTY-5")
def test_a_lookup_that_broke_for_another_reason_is_not_taken_for_an_old_failure(monkeypatch):
    def broken(am):
        raise ValueError("unexpected answer")
    monkeypatch.setattr(analysis, "resolve_law", broken)
    e = entry("2", T0)
    assert "lookupFailed" not in e and not analysis.retry_due(e, T0 + 3 * DAY)


@pytest.mark.spec("RTY-6")
def test_bills_follow_the_same_rule(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(drafts, "listed", lambda: [(21, 6588)])
    monkeypatch.setattr(drafts, "_read", lambda wp, number: (
        SimpleNamespace(date="2026-06-22"), SimpleNamespace(articles=[article("1"), article("2")])))
    sources_answer(monkeypatch)
    good = entry("1", T0)
    sources_silent(monkeypatch)
    drafts._save(21, 6588, "", {"draft": {"id": "21-6588"}, "articles": [good, entry("2", T0)],
                                "counts": {"shown": 1, "total": 2}})
    sources_answer(monkeypatch)
    assert drafts.update(now=T0 + DAY - 5 * MINUTE)["retried"] == 1
    bill = drafts.load(21, 6588)
    assert bill["articles"][0] == good and "lookupFailed" not in bill["articles"][1]
    assert bill["counts"] == {"shown": 2, "total": 2}
    assert bill["articles"][1]["law"]["newerThanDraft"] is True  # ENT-9 as in a first analysis


@pytest.mark.spec("RTY-7")
def test_new_publications_come_before_retries(monkeypatch, stored):
    sources_silent(monkeypatch)
    store.save_result(PUB.id, {"publication": {"id": PUB.id}, "articles": [entry("2", T0)]})
    sources_answer(monkeypatch)
    monkeypatch.setattr(export, "analyze", lambda teil, year, number: {
        "publication": {"id": f"{teil}/{year}/{number}"}, "articles": []})
    stats = run(T0 + DAY, pubs=(NEW, PUB), max_new=1)
    assert (stats["analyzed"], stats["retried"], stats["pending"]) == (1, 0, 1)
    assert "lookupFailed" in store.load_result(PUB.id)["articles"][0]
    stats = run(T0 + DAY, pubs=(NEW, PUB), max_new=1)
    assert (stats["analyzed"], stats["retried"], stats["pending"]) == (0, 1, 0)
