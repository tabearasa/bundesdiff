"""Bills (Gesetzentwürfe): what a bill would change in the laws as they stand (spec 016).

A bill is analysed like a publication of the Bundesgesetzblatt, with three differences:

* it is never in force, so the current law text is always the "before" side (ENT-8);
* it has no dates: no day of signing, no in-force date;
* it comes with a Vorblatt and a Begründung, kept apart from the comparison (ENT-11, ENT-12).

Which bills are shown is a hand-kept list, ``entwuerfe.txt``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from . import drucksache, listing, sources, store
from .amendments import split_document
from .analysis import article_entry
from .engine import Snapshots

log = logging.getLogger(__name__)
LIST_FILE = Path(__file__).parent / "entwuerfe.txt"


def listed() -> list[tuple[int, int]]:
    """The bills to show, as (Wahlperiode, number), in the order of the list."""
    out = []
    for line in LIST_FILE.read_text().splitlines():
        m = re.fullmatch(r"(\d{1,2})/(\d{1,5})", line.split("#")[0].strip())
        if m and (int(m.group(1)), int(m.group(2))) not in out:
            out.append((int(m.group(1)), int(m.group(2))))
    return out


def draft_id(wp: int, number: int) -> str:
    return f"{wp}/{number}"


def fetch_pdf(wp: int, number: int) -> bytes:
    data = sources.fetch(drucksache.pdf_url(wp, number))
    if not data.startswith(b"%PDF"):
        raise LookupError(f"Keine PDF-Datei für Drucksache {wp}/{number} gefunden")
    return data


def analyze(wp: int, number: int) -> tuple[dict, dict]:
    """(comparison, general information) of one bill, both JSON-ready."""
    ds = drucksache.read(fetch_pdf(wp, number))
    if (ds.wp, ds.number) != (wp, number):
        raise LookupError(f"Die Datei ist Drucksache {ds.wp}/{ds.number}, nicht {wp}/{number}")
    doc = split_document(ds.lines)
    articles = [article_entry(art, state_of=lambda ref: "pre", snapshots_of=lambda ref: Snapshots(lambda key: None),
                              force_state="pre")
                for art in doc.articles]
    instructions = [i for a in articles for i in a.get("instructions") or []]
    for a in articles:
        law = a.get("law")
        if law:  # ENT-9: the law may have changed after the bill was written
            law["newerThanDraft"] = bool(ds.date and str(law.get("version") or "")[:10] > ds.date)
    result = {
        "draft": {"id": draft_id(wp, number), "wp": wp, "number": number, "title": doc.title or ds.title,
                  "date": ds.date, "kind": ds.kind, "author": ds.author, "pdf": drucksache.pdf_url(wp, number)},
        "preamble": doc.preamble,
        "articles": articles,
        "counts": {"shown": sum(i["status"] == "applied" for i in instructions), "total": len(instructions)},
    }
    parts = info_parts(ds)
    # the comparison names the parts, so the page can list them without loading their text
    result["info"] = [{"id": p["id"], "title": p["title"]} for p in parts]
    return result, {"parts": parts}


def info_parts(ds: drucksache.Drucksache) -> list[dict]:
    """Vorblatt and Begründung in parts a reader opens one at a time (ENT-12).

    The Begründung is cut at "Zu Artikel 1", "Zu Artikel 2" …; what comes before is its general part.
    """
    parts: list[dict] = []

    def part(pid: str, title: str) -> dict:
        parts.append({"id": pid, "title": title, "sections": []})
        return parts[-1]

    if ds.vorblatt:
        part("vorblatt", "Zusammenfassung des Entwurfs (Vorblatt)")["sections"] = [_section(s) for s in ds.vorblatt]
    current = None
    for s in ds.begruendung:
        m = re.match(r"^Zu Artikel (\d+[a-z]*)\b", s.heading)
        if m and s.level <= 2:
            current = part(f"artikel-{m.group(1)}", "Begründung z" + s.heading[1:])
            if s.paragraphs:
                current["sections"].append(_section(drucksache.Section("", s.level, s.paragraphs)))
            continue
        if s.level == 1 and not s.paragraphs:
            if s.heading.startswith("A."):
                current = part("allgemein", "Begründung: Allgemeiner Teil")
            elif s.heading.startswith("B."):
                current = part("besonderer", "Begründung: Besonderer Teil")
            continue
        if current is None:
            current = part("allgemein", "Begründung: Allgemeiner Teil")
        current["sections"].append(_section(s))
    return [p for p in parts if p["sections"]]


def _section(s: drucksache.Section) -> dict:
    return {"heading": s.heading, "level": s.level, "paragraphs": s.paragraphs}


# --------------------------------------------------------------------------
# Stored results


def _path(wp: int, number: int, part: str = "") -> Path:
    return store.DATA_DIR / "drafts" / f"{wp}_{number}{part}.json"


def load(wp: int, number: int, part: str = "") -> dict | None:
    """The stored comparison (``part=""``) or general information (``part="-info"``)."""
    try:
        return json.loads(_path(wp, number, part).read_text())
    except (OSError, ValueError):
        return None


def _save(wp: int, number: int, part: str, data: dict) -> None:
    path = _path(wp, number, part)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def update(retry_hours: float = 24) -> dict:
    """Analyse every listed bill that has no (successful) result yet. A bill is analysed once."""
    stats = {"analyzed": 0, "failed": 0}
    for wp, number in listed():
        result = load(wp, number)
        if result and not result.get("error"):
            continue
        if result and time.time() - result.get("failedAt", 0) < retry_hours * 3600:
            continue
        try:
            result, info = analyze(wp, number)
            _save(wp, number, "-info", info)
            _save(wp, number, "", result)
            stats["analyzed"] += 1
            log.info("analyzed Drucksache %s/%s", wp, number)
        except Exception as e:  # noqa: BLE001 – one broken bill must not stop the run
            log.exception("failed Drucksache %s/%s", wp, number)
            _save(wp, number, "", {"error": str(e), "failedAt": time.time()})
            stats["failed"] += 1
    return stats


def get(wp: int, number: int) -> dict:
    """The comparison of a listed bill, analysed now if it is not stored (live server)."""
    if (wp, number) not in listed():
        raise LookupError(f"Drucksache {wp}/{number} gehört nicht zu den gezeigten Gesetzentwürfen")
    result = load(wp, number)
    if result is None or result.get("error"):
        result, info = analyze(wp, number)
        _save(wp, number, "-info", info)
        _save(wp, number, "", result)
    return result


def entries() -> list[dict]:
    """The list of bills (ENT-2): small, without the texts of the changes."""
    out = []
    for wp, number in listed():
        result = load(wp, number)
        ok = bool(result and not result.get("error"))
        item = {"id": draft_id(wp, number), "wp": wp, "number": number, "analyzed": ok,
                "failed": bool(result and result.get("error")), "pdf": drucksache.pdf_url(wp, number)}
        if ok:
            d = result["draft"]
            item.update({"title": d["title"], "date": d["date"], "kind": d["kind"], "author": d["author"],
                         "laws": listing.laws(result.get("articles") or [])})
        out.append(item)
    return out
