"""Build a static version of the site (for GitHub Pages or any web server).

The analyses are precomputed and written as JSON files next to the frontend:

    site/index.html, site/static/…
    site/data/meta.json
    site/data/publications-1.json, publications-2.json
    site/data/<teil>/<year>/<number>.json
    site/data/entwuerfe.json                       bills (spec 016)
    site/data/entwurf/<wp>/<number>.json           one bill: the comparison
    site/data/entwurf/<wp>/<number>-info.json      its Vorblatt and Begründung
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import shutil
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from . import drafts, sources, store
from . import listing as list_entry
from .analysis import analyze, now_utc, reanalyze, retry_due

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"
LIST_WAITS = (60, 300, 900)  # seconds between the 4 tries to fetch the list (RES-1)
_sleep = time.sleep


def is_iso_date(text: str) -> bool:
    """YYYY-MM-DD in ASCII digits, and a day that exists."""
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text or ""):
        return False
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def update_results(pubs: list[sources.Publication], max_new: int, retry_hours: float,
                   now: dt.datetime | None = None) -> dict:
    """Analyze publications that have no (successful) result yet, newest first. Then analyse again
    the Artikel whose law could not be loaded (spec 017; RTY-7: new publications come first)."""
    now = now or now_utc()
    stats = {"analyzed": 0, "failed": 0, "pending": 0, "retried": 0}
    again: list[tuple[sources.Publication, dict]] = []
    for pub in pubs:
        result = store.load_result(pub.id)
        if result and not result.get("error"):
            if any(retry_due(a, now) for a in result.get("articles") or []):
                again.append((pub, result))
            continue
        if result and time.time() - result.get("failedAt", 0) < retry_hours * 3600:
            continue
        if stats["analyzed"] + stats["failed"] >= max_new:
            stats["pending"] += 1
            continue
        try:
            store.save_result(pub.id, analyze(pub.teil, pub.year, pub.number))
            stats["analyzed"] += 1
            log.info("analyzed %s", pub.fundstelle)
        except Exception as e:  # noqa: BLE001 – one broken issue must not stop the run
            log.exception("failed %s", pub.fundstelle)
            store.save_result(pub.id, {"error": str(e), "failedAt": time.time(),
                                       "publication": {"issued": pub.date}})
            stats["failed"] += 1
    for pub, result in again:
        if stats["analyzed"] + stats["failed"] + stats["retried"] >= max_new:
            stats["pending"] += 1
            continue
        try:
            store.save_result(pub.id, reanalyze(pub, result, now))
            stats["retried"] += 1
            log.info("analysed again %s", pub.fundstelle)
        except Exception:  # noqa: BLE001 – the stored result stays; the next run tries again
            log.exception("could not analyse %s again", pub.fundstelle)
    return stats


def fetch_listing(teil: str) -> list[sources.Publication]:
    """The list of publications from recht.bund.de, tried 4 times (RES-1).

    Raises sources.Unreachable when it cannot be fetched or read.
    """
    url = sources.FEEDS[teil]
    for wait in (*LIST_WAITS, None):
        try:
            pubs = sources.list_publications(teil)
        except (ET.ParseError, LookupError, ValueError) as e:  # an answer, but not a list: trying again will not help
            raise sources.Unreachable(url, f"Antwort nicht lesbar ({e})") from e
        except httpx.HTTPError as e:
            if wait is None or not sources.connection_problem(e):
                raise sources.Unreachable(url, sources.reason(e)) from e
            log.warning("list of publications: %s – next try in %d min", sources.reason(e), wait // 60)
            _sleep(wait)
            continue
        dated = [p for p in pubs if is_iso_date(p.date)]
        if len(dated) < len(pubs):
            log.warning("list of publications: %d without a date of the form YYYY-MM-DD left out",
                        len(pubs) - len(dated))
        if not dated:  # the real feed always lists hundreds: this is a maintenance page or similar
            raise sources.Unreachable(url, "Antwort enthält keine Veröffentlichungen")
        return dated
    raise AssertionError("unreachable")


def export(site: Path, days: int = 365, max_new: int = 50, retry_hours: float = 24) -> dict:
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    if site.exists():
        shutil.rmtree(site)
    (site / "data").mkdir(parents=True)

    totals: dict = {"analyzed": 0, "failed": 0, "pending": 0, "retried": 0}
    from_saved, list_fetched = False, ""
    for teil in sources.FEEDS:
        try:
            feed = fetch_listing(teil)
            fetched = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M")
            store.save_listing(teil, feed, fetched)
        except sources.Unreachable as e:
            saved = store.load_listing(teil)
            if saved is None:
                raise
            # RES-3: the site as after the last successful run, nothing new is analysed
            feed, fetched = saved
            from_saved = True
            log.error("%s – using the list saved at %s UTC", e, fetched)
        pubs = [p for p in feed if p.date >= cutoff]
        if not from_saved:
            budget = max_new - totals["analyzed"] - totals["failed"] - totals["retried"]
            for k, v in update_results(pubs, budget, retry_hours).items():
                totals[k] += v
        listing = []
        for p in pubs:
            result = store.load_result(p.id)
            if result is not None:
                _write_json(site / "data" / teil / str(p.year) / f"{p.number}.json", result)
            listing.append(list_entry.entry(p, result))
        _write_json(site / "data" / f"publications-{teil}.json", listing)
        list_fetched = min(list_fetched or fetched, fetched)

    try:
        # a few hand-listed bills: a failed analysis is tried again on every run
        draft_totals = export_drafts(site, retry_hours=0)
    except Exception:  # noqa: BLE001 – the bills must never stop the daily build of the publications
        log.exception("bills")
        draft_totals = {"analyzed": 0, "failed": 0, "error": True}
    _write_json(site / "data" / "meta.json", {"generated": dt.datetime.now(dt.UTC).isoformat(timespec="minutes"),
                                              "listFetched": list_fetched, "since": cutoff})
    build_frontend(site)
    return {**totals, "fromSavedList": from_saved, "listFetched": list_fetched, "drafts": draft_totals}


def export_drafts(site: Path, retry_hours: float = 24) -> dict:
    """The bills of ``entwuerfe.txt``: analysed once, then written from the store."""
    totals = drafts.update(retry_hours)
    for wp, number in drafts.listed():
        result = drafts.load(wp, number)
        if result is None:
            continue
        _write_json(site / "data" / "entwurf" / str(wp) / f"{number}.json", result)
        info = drafts.load(wp, number, "-info")
        if info is not None and not result.get("error"):
            _write_json(site / "data" / "entwurf" / str(wp) / f"{number}-info.json", info)
    _write_json(site / "data" / "entwuerfe.json", drafts.entries())
    return totals


def build_frontend(site: Path) -> None:
    """Copy the frontend into ``site`` and switch it to the precomputed data/ files."""
    shutil.copytree(STATIC, site / "static", dirs_exist_ok=True)
    index = (STATIC / "index.html").read_text()
    index = index.replace('<script src="static/app.js">',
                          '<script>window.BUNDESDIFF_STATIC = true;</script>\n  <script src="static/app.js">')
    (site / "index.html").write_text(index)
    (site / "static" / "index.html").unlink()
    (site / ".nojekyll").write_text("")
