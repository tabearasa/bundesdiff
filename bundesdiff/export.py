"""Build a static version of the site (for GitHub Pages or any web server).

The analyses are precomputed and written as JSON files next to the frontend:

    site/index.html, site/static/…
    site/data/meta.json
    site/data/publications-1.json, publications-2.json
    site/data/<teil>/<year>/<number>.json
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import time
from pathlib import Path

from . import sources, store
from .analysis import analyze

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def update_results(pubs: list[sources.Publication], max_new: int, retry_hours: float) -> dict:
    """Analyze publications that have no (successful) result yet, newest first."""
    stats = {"analyzed": 0, "failed": 0, "pending": 0}
    for pub in pubs:
        result = store.load_result(pub.id)
        if result and not result.get("error"):
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
    return stats


def export(site: Path, days: int = 365, max_new: int = 50, retry_hours: float = 24) -> dict:
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    if site.exists():
        shutil.rmtree(site)
    (site / "data").mkdir(parents=True)

    totals: dict = {}
    for teil in sources.FEEDS:
        pubs = [p for p in sources.list_publications(teil) if p.date >= cutoff]
        for k, v in update_results(pubs, max_new - totals.get("analyzed", 0) - totals.get("failed", 0),
                                   retry_hours).items():
            totals[k] = totals.get(k, 0) + v
        listing = []
        for p in pubs:
            result = store.load_result(p.id)
            if result is not None:
                _write_json(site / "data" / teil / str(p.year) / f"{p.number}.json", result)
            listing.append({
                "id": p.id, "teil": p.teil, "year": p.year, "number": p.number, "title": p.title,
                "date": p.date, "typ": p.typ, "initiant": p.initiant, "fundstelle": p.fundstelle,
                "sachgebiet": p.sachgebiet, "analyzed": bool(result and not result.get("error")),
            })
        _write_json(site / "data" / f"publications-{teil}.json", listing)

    _write_json(site / "data" / "meta.json", {"generated": dt.datetime.now(dt.UTC).isoformat(timespec="minutes"),
                                              "since": cutoff})
    shutil.copytree(STATIC, site / "static")
    index = (STATIC / "index.html").read_text()
    index = index.replace('<script src="static/app.js">',
                          '<script>window.BUNDESDIFF_STATIC = true;</script>\n  <script src="static/app.js">')
    (site / "index.html").write_text(index)
    (site / "static" / "index.html").unlink()
    (site / ".nojekyll").write_text("")
    return totals
