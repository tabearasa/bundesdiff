"""Spec 014: when recht.bund.de cannot be reached."""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

import httpx
import pytest

from bundesdiff import cli, export, sources, store

ROOT = Path(__file__).parents[1]
FEED_URL = sources.FEEDS["1"]

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:meta="http://recht.bund.de/rss/meta"><channel>
<item><title>Gesetz zur Änderung des Tabaksteuergesetzes</title>
  <link>https://www.recht.bund.de/eli/bund/bgbl-1/2026/309</link>
  <pubDate>{today}</pubDate><meta:typ>Gesetz</meta:typ><meta:initiant>Bundestag</meta:initiant>
  <meta:fundstelle>BGBl. 2026 I Nr. 309 vom 28.10.2026</meta:fundstelle>
  <meta:sachgebiet>Steuerrecht</meta:sachgebiet></item>
<item><title>Verordnung über etwas Neues</title>
  <link>https://www.recht.bund.de/eli/bund/bgbl-1/2026/310</link>
  <pubDate>{today}</pubDate><meta:typ>Verordnung</meta:typ><meta:initiant>BMF</meta:initiant>
  <meta:fundstelle>BGBl. 2026 I Nr. 310 vom 29.10.2026</meta:fundstelle>
  <meta:sachgebiet></meta:sachgebiet></item>
</channel></rss>"""


class FakeClient:
    """Stands in for the HTTP client: answers from a list of results, one per request."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.urls: list[str] = []

    def get(self, url):
        self.urls.append(url)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        status, body = answer
        return httpx.Response(status, content=body, request=httpx.Request("GET", url))


def timeout() -> httpx.ConnectTimeout:
    return httpx.ConnectTimeout("_ssl.c:1067: The handshake operation timed out")


@pytest.fixture
def waits(monkeypatch, tmp_path):
    """No real waiting, an empty cache and data store; returns the waits of both kinds."""
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path / "data")
    quick: list[float] = []
    long: list[float] = []
    monkeypatch.setattr(sources, "_sleep", quick.append)
    monkeypatch.setattr(export, "_sleep", long.append)
    monkeypatch.setattr(export, "analyze", lambda teil, year, number: _result(teil, year, number))
    return {"quick": quick, "long": long, "site": tmp_path / "site"}


def _result(teil, year, number):
    return {"publication": {"id": f"{teil}/{year}/{number}", "issued": "2026-10-28"}, "articles": []}


def feed() -> bytes:
    """Like the real feed: ELI links, the date as YYYY-MM-DD."""
    return FEED.format(today=dt.date.today().isoformat()).encode()


def use(monkeypatch, *answers) -> FakeClient:
    """Answers the next requests; empties the HTTP cache, as on a fresh GitHub runner."""
    shutil.rmtree(sources.CACHE_DIR, ignore_errors=True)
    client = FakeClient(answers)
    monkeypatch.setattr(sources, "_client", client)
    return client


# ---------------------------------------------------------------- RES-8: single requests


@pytest.mark.spec("RES-8")
def test_a_request_that_times_out_is_tried_again(monkeypatch, waits):
    client = use(monkeypatch, timeout(), timeout(), (200, b"ok"))
    assert sources.fetch("https://www.gesetze-im-internet.de/x.html") == b"ok"
    assert len(client.urls) == 3
    assert waits["quick"] == [2, 10]


@pytest.mark.spec("RES-8")
@pytest.mark.parametrize("status", [500, 502, 503, 429])
def test_a_server_error_is_tried_again(monkeypatch, waits, status):
    client = use(monkeypatch, (status, b""), (200, b"ok"))
    assert sources.fetch("https://testphase.rechtsinformationen.bund.de/v1/x") == b"ok"
    assert len(client.urls) == 2


@pytest.mark.spec("RES-8")
def test_a_request_gives_up_after_three_tries(monkeypatch, waits):
    client = use(monkeypatch, timeout())
    with pytest.raises(httpx.ConnectTimeout):
        sources.fetch("https://web.archive.org/web/2026/x")
    assert len(client.urls) == 3
    assert waits["quick"] == [2, 10]


@pytest.mark.spec("RES-8")
def test_a_missing_page_is_not_tried_again(monkeypatch, waits):
    """404 is an answer, not a connection problem: the Internet Archive often has no copy."""
    client = use(monkeypatch, (404, b""))
    with pytest.raises(httpx.HTTPStatusError):
        sources.fetch("https://web.archive.org/web/2026/x")
    assert len(client.urls) == 1
    assert waits["quick"] == []


# ---------------------------------------------------------------- RES-1: the list


@pytest.mark.spec("RES-1")
def test_the_list_is_tried_four_times_with_long_waits(monkeypatch, waits):
    client = use(monkeypatch, timeout())
    with pytest.raises(sources.Unreachable):
        export.fetch_listing("1")
    assert waits["long"] == [60, 300, 900]
    assert len(client.urls) == 4 * 3  # each try is a request with its own quick retries
    assert set(client.urls) == {FEED_URL}


@pytest.mark.spec("RES-1")
def test_the_list_is_fetched_when_a_later_try_works(monkeypatch, waits):
    use(monkeypatch, timeout(), timeout(), timeout(), (200, feed()))
    pubs = export.fetch_listing("1")
    assert [p.id for p in pubs] == ["1/2026/309", "1/2026/310"]
    assert waits["long"] == [60]


@pytest.mark.spec("RES-1")
def test_a_broken_list_is_not_tried_again(monkeypatch, waits):
    use(monkeypatch, (200, b"<rss><channel><item>"))
    with pytest.raises(sources.Unreachable):
        export.fetch_listing("1")
    assert waits["long"] == []


@pytest.mark.spec("RES-1")
@pytest.mark.parametrize("body", [
    b"<rss><channel></channel></rss>",
    b"<html><body><p>Wartungsarbeiten</p></body></html>",
    b'<?xml version="1.0" encoding="foo"?><rss/>',  # an encoding Python does not know
    FEED.replace("{today}", "").encode(),  # items, but no dates
    FEED.replace("{today}", "Wed, 04 Nov 2026 10:00:00 +0100").encode(),  # dates in another form
    FEED.replace("{today}", "2026-02-31").encode(),  # a day that does not exist
    FEED.replace("{today}", "\uff12\uff10\uff12\uff16-10-30").encode(),  # full-width digits
])
def test_a_list_without_publications_counts_as_unreadable(monkeypatch, waits, body):
    """The real feed always lists hundreds of publications; an empty one is a maintenance page."""
    use(monkeypatch, (200, body))
    with pytest.raises(sources.Unreachable):
        export.fetch_listing("1")
    assert waits["long"] == []


# ---------------------------------------------------------------- RES-2 to RES-4: export


@pytest.mark.spec("RES-2")
def test_a_fetched_list_is_saved_in_the_data_store(monkeypatch, waits, tmp_path):
    use(monkeypatch, (200, feed()))
    export.export(tmp_path / "site")
    saved = store.load_listing("1")
    assert saved is not None
    pubs, fetched = saved
    assert [p.id for p in pubs] == ["1/2026/309", "1/2026/310"]
    assert pubs[0].title == "Gesetz zur Änderung des Tabaksteuergesetzes"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", fetched)
    assert (tmp_path / "data" / "publications-1.json").exists()


@pytest.mark.spec("RES-3")
def test_without_recht_bund_de_the_site_is_built_from_the_saved_list(monkeypatch, waits, tmp_path):
    use(monkeypatch, (200, feed()))
    export.export(tmp_path / "before", max_new=1)  # 309 analysed, 310 not yet
    listing = (tmp_path / "before" / "data" / "publications-1.json").read_text()

    use(monkeypatch, timeout())
    monkeypatch.setattr(export, "analyze", lambda *a: pytest.fail("nothing is analysed"))
    totals = export.export(tmp_path / "after", max_new=50)

    site = tmp_path / "after"
    assert (site / "data" / "publications-1.json").read_text() == listing
    assert (site / "data" / "1" / "2026" / "309.json").exists()
    assert (site / "index.html").exists()
    assert totals["fromSavedList"] is True
    assert totals["analyzed"] == 0


@pytest.mark.spec("RES-3")
def test_an_empty_answer_does_not_replace_the_saved_list(monkeypatch, waits, tmp_path):
    use(monkeypatch, (200, feed()))
    export.export(tmp_path / "before")
    use(monkeypatch, (200, b"<rss><channel></channel></rss>"))
    totals = export.export(tmp_path / "after")
    assert totals["fromSavedList"] is True
    assert [p.id for p in store.load_listing("1")[0]] == ["1/2026/309", "1/2026/310"]
    assert len(json.loads((tmp_path / "after" / "data" / "publications-1.json").read_text())) == 2


@pytest.mark.spec("RES-3")
@pytest.mark.parametrize("damage", ["not json", "no publications", "date null", "title null",
                                    "fetched empty", "fetched in words", "fetched impossible",
                                    "date impossible", "year not a number", "number a path",
                                    "other teil"])
def test_a_damaged_saved_list_counts_as_missing(monkeypatch, waits, damage):
    use(monkeypatch, (200, feed()))
    export.export(waits["site"])
    path = store.listing_path("1")
    data = json.loads(path.read_text())
    row = data["publications"][0]
    changes = {
        "no publications": lambda: data.update(publications=[]),
        "date null": lambda: row.update(date=None),
        "title null": lambda: row.update(title=None),
        "fetched empty": lambda: data.update(fetched=""),
        "fetched in words": lambda: data.update(fetched="gestern"),
        "fetched impossible": lambda: data.update(fetched="2026-99-99T99:99"),
        "date impossible": lambda: row.update(date="2026-02-31"),
        "year not a number": lambda: row.update(year=True),
        "number a path": lambda: row.update(number="../../x"),
        "other teil": lambda: row.update(teil="2"),
    }
    if damage == "not json":
        path.write_text("not json")
    else:
        changes[damage]()
        path.write_text(json.dumps(data))
    assert store.load_listing("1") is None


@pytest.mark.spec("RES-4")
def test_meta_says_when_the_list_was_fetched(monkeypatch, waits, tmp_path):
    use(monkeypatch, (200, feed()))
    export.export(tmp_path / "before")
    fetched = json.loads((tmp_path / "before" / "data" / "meta.json").read_text())["listFetched"]
    assert fetched == store.load_listing("1")[1]

    use(monkeypatch, timeout())
    export.export(tmp_path / "after")
    meta = json.loads((tmp_path / "after" / "data" / "meta.json").read_text())
    assert meta["listFetched"] == fetched  # the time of the saved list, not of this run


# ---------------------------------------------------------------- RES-6, RES-7


@pytest.mark.spec("RES-6")
def test_without_a_saved_list_the_run_stops_with_one_line(monkeypatch, waits, tmp_path, capsys):
    use(monkeypatch, timeout())
    monkeypatch.setattr(sys, "argv", ["bundesdiff", "export", "--site", str(tmp_path / "site")])
    with pytest.raises(SystemExit) as stop:
        cli.main()
    assert stop.value.code == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    last = err.strip().splitlines()[-1]
    assert FEED_URL in last
    assert "nicht erreichbar" in last
    assert "keine lesbare gespeicherte Liste" in last  # also right when the saved file is damaged


@pytest.mark.spec("RES-7")
def test_the_run_reports_that_it_used_the_saved_list(monkeypatch, waits, tmp_path, capsys):
    use(monkeypatch, (200, feed()))
    export.export(tmp_path / "before")
    use(monkeypatch, timeout())
    monkeypatch.setattr(sys, "argv", ["bundesdiff", "export", "--site", str(tmp_path / "site")])
    cli.main()
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["fromSavedList"] is True
    assert out["listFetched"] == store.load_listing("1")[1]


@pytest.mark.spec("RES-7")
def test_the_workflow_fails_only_after_publishing_from_the_saved_list():
    workflow = (ROOT / ".github" / "workflows" / "update.yml").read_text()
    jobs = workflow[workflow.index("\njobs:"):]
    # the export result goes into the step summary and into an output of the update job
    assert "GITHUB_STEP_SUMMARY" in workflow
    assert "recht.bund.de konnte nicht erreicht werden" in workflow
    assert re.search(r"outputs:\s*\n\s*from_saved_list: \$\{\{ steps\.export\.outputs\.from_saved_list \}\}", jobs)
    # a last job fails the run, after the data commit (update) and the deploy
    last = jobs[jobs.index("\n  source-unreachable:"):]
    assert re.search(r"needs: \[update, deploy-pages\]", last)
    assert "always()" in last and "needs.update.outputs.from_saved_list == 'true'" in last
    assert "exit 1" in last


def test_the_workflow_installs_no_test_tools():
    """Fixed alongside spec 014: `uv run` would install ruff and Playwright again."""
    workflow = (ROOT / ".github" / "workflows" / "update.yml").read_text()
    runs = re.findall(r"uv run(?! --no-dev)", workflow)
    assert not runs
