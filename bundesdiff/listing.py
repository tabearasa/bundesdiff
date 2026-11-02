"""One entry of the publication list – also the search index and the data of the timeline (spec 002).

Kept small (no texts of the changes): the whole list of a year must stay well below 300 KB
compressed (SRCH-9), because it is loaded on every page.
"""

from __future__ import annotations

import re

from . import inforce, sources

_IN_FORCE = re.compile(r"inkrafttreten|außerkrafttreten|geltungsdauer", re.I)


def entry(p: sources.Publication, result: dict | None) -> dict:
    ok = bool(result and not result.get("error"))
    item = {
        "id": p.id, "teil": p.teil, "year": p.year, "number": p.number, "title": p.title,
        "date": p.date, "typ": p.typ, "initiant": p.initiant, "fundstelle": p.fundstelle,
        "sachgebiet": p.sachgebiet, "analyzed": ok, "failed": bool(result and result.get("error")),
    }
    if ok:
        articles = result.get("articles") or []
        item["laws"] = laws(articles)
        item["inForce"] = [
            e for a in articles if a.get("kind") != "amendment" and _IN_FORCE.search(a.get("heading") or "")
            for e in in_force(a.get("text") or "", p.date)]
    return item


def in_force(text: str, date: str) -> list[dict]:
    """The in-force entries of one article; a text the reader trips over never stops the list.

    One unexpected wording must not break the daily build or the list for every reader: the whole
    article is then one entry without a date ("Datum nicht sicher erkannt", TL-7).
    """
    try:
        return inforce.parse(text, date)
    except Exception:  # noqa: BLE001 – any failure means: not read with certainty
        sentence = " ".join(text.split())
        return [{"date": None, "retroactive": False, "kind": "in", "whole": False, "rest": False,
                 "subject": None, "articles": [], "sentence": sentence}]


def laws(articles: list[dict]) -> list[dict]:
    """The laws a publication changes: everyday name, abbreviation, official name, article number."""
    found: dict[str, dict] = {}
    for a in articles:
        if a.get("kind") != "amendment":
            continue
        law = a.get("law") or {}
        name = law.get("shortName") or law.get("name") or a.get("lawName") or ""
        if not name:
            continue
        known = found.setdefault(name, {"name": name, "abbr": law.get("abbreviation") or "",
                                        "full": law.get("name") if law.get("name") != name else "",
                                        "articles": []})
        known["articles"].append(a.get("number"))
    return list(found.values())
