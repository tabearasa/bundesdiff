"""Analyze one Bundesgesetzblatt publication into a synopsis (JSON-ready dicts)."""

from __future__ import annotations

import datetime as dt
import logging
import re

from . import sources
from .amendments import OPS, Amendment, analyze_article, split_document
from .diffing import diff_units, stats
from .engine import Snapshots, find_par, run
from .model import Node
from .pdftext import extract_lines

log = logging.getLogger(__name__)

MONTHS = {m: i for i, m in enumerate(
    ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
     "Dezember"], start=1)}


def parse_german_date(text: str) -> dt.date | None:
    m = re.search(r"(\d{1,2})\.\s*(\w+)\s+(\d{4})", text or "")
    if m and m.group(2) in MONTHS:
        return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    return None


def resolve_law(am: Amendment) -> sources.LawRef | None:
    """Find the current text of the amended law: NeuRIS first, then gesetze-im-internet.de."""
    if am.citation:
        for eli in am.citation.work_elis():
            ref = sources.neuris_by_eli(eli)
            if ref and (not am.law_name or sources.names_match(am.law_name, ref)):
                return ref
    if am.law_name:
        ref = sources.neuris_by_name(am.law_name)
        if ref:
            return ref
        slug = sources.gii_slug(am.law_name)
        if slug:
            return sources.gii_law(slug)
    return None


def default_state(ref: sources.LawRef, pub: sources.Publication, law_date: dt.date | None) -> str:
    """Whether the current text presumably already contains the publication's changes."""
    if ref.source == "gii":
        for seg in re.split(r"(?=Mittelbare Änderung|zuletzt geändert|Änderung durch)", ref.stand):
            if re.search(rf"\b{pub.year}\s+{'I' * int(pub.teil)}\s+Nr\.\s*{re.escape(pub.number)}\b", seg):
                return "pre" if "noch nicht" in seg else "post"
        m = re.search(r"zuletzt geändert durch .*? v\. (\d{1,2})\.(\d{1,2})\.(\d{4})", ref.stand)
        if m and law_date:
            last = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return "post" if last >= law_date else "pre"
        return "pre"
    return "post" if law_date and ref.version >= law_date.isoformat() else "pre"


def _snapshot_fetcher(ref: sources.LawRef, before: dt.date):
    """Earlier versions of a § – locally stored versions first, then the Internet Archive."""
    state: dict = {}

    def older_local():
        if "local" not in state:
            state["local"] = None
            for date, path in reversed(sources.stored_versions(ref)):
                if date < before.isoformat() and date != ref.version:
                    state["local"] = (sources.parse_stored(ref, path), date)
                    break
        return state["local"]

    def fetch(key: str):
        local = older_local()
        if local:
            hit = find_par(local[0], key)
            if hit:
                where = "NeuRIS" if ref.source == "neuris" else "gesetze-im-internet.de"
                return hit[0], f"lokal gespeicherte Fassung vom {_de(local[1])} ({where})"
        if "slug" not in state:
            try:
                state["slug"] = ref.gii_slug or sources.gii_slug(ref.name) or sources.gii_slug(ref.alternate_name)
            except Exception:  # noqa: BLE001 – TOC unavailable is not fatal
                log.exception("gii toc")
                state["slug"] = None
        if not state["slug"]:
            return None
        label = "§ " + key[1:] if key.startswith("§") else "Artikel " + key[3:]
        try:
            hit = sources.wayback_norm(state["slug"], label, before)
        except Exception:  # noqa: BLE001
            log.exception("wayback")
            return None
        if hit:
            return hit[0], f"Archivfassung von gesetze-im-internet.de vom {hit[1]} (Internet Archive)"
        return None

    return fetch


def _de(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def _instruction_json(res) -> dict:
    ins = res.instruction
    return {
        "marker": ins.marker,
        "raw": ins.raw,
        "op": ins.op,
        "opLabel": OPS.get(ins.op, ins.op),
        "location": ins.location,
        "status": res.status,
        "state": res.state,
        "message": res.message,
    }


def _par_title(node: Node | None, key: str) -> str:
    if node is None:
        return key.replace("§", "§ ")
    return " ".join(x for x in (node.label, node.heading) if x)


def analyze(teil: str, year: int, number: str) -> dict:
    pub = sources.find_publication(teil, year, number)
    pdf = sources.fetch_pdf(pub)
    doc = split_document(extract_lines(pdf))
    law_date = parse_german_date(doc.date)
    issued = parse_german_date(pub.date) if pub.date and not re.match(r"\d{4}-", pub.date) else None
    if pub.date and re.match(r"\d{4}-\d{2}-\d{2}", pub.date):
        issued = dt.date.fromisoformat(pub.date[:10])
    issued = issued or law_date or dt.date.today()

    articles = []
    for art in doc.articles:
        entry: dict = {"number": art.number, "heading": art.heading, "kind": "other", "text": art.text}
        am = analyze_article(art)
        if am is None:
            articles.append(entry)
            continue
        entry.update({"kind": "amendment", "lawName": am.law_name, "intro": am.intro})
        try:
            ref = resolve_law(am)
        except Exception as e:  # noqa: BLE001
            log.exception("resolve law")
            ref = None
            entry["error"] = f"Fehler bei der Suche des Gesetzes: {e}"
        if ref is None:
            entry.setdefault("error", f"„{am.law_name}“ wurde in der Rechtsinformationsplattform nicht gefunden.")
            entry["instructions"] = [
                {"marker": i.marker, "raw": i.raw, "op": i.op, "opLabel": OPS.get(i.op, i.op),
                 "location": i.location, "status": "unsupported", "state": None, "message": ""}
                for i in am.instructions]
            entry["pars"] = []
            articles.append(entry)
            continue
        law = sources.load_law(ref)
        # Wayback snapshots must predate the day the issue was published
        snaps = Snapshots(_snapshot_fetcher(ref, issued - dt.timedelta(days=1)))
        result = run(law, am.instructions, snaps, default_state(ref, pub, law_date))
        entry.update({
            "law": {"name": ref.name, "shortName": ref.alternate_name, "abbreviation": ref.abbreviation,
                    "source": ref.source, "version": ref.version, "url": ref.url},
            "instructions": [_instruction_json(r) for r in result.results],
            "pars": [],
        })
        for pd in result.pars:
            rows = diff_units(pd.before, pd.after)
            entry["pars"].append({
                "key": pd.key,
                "title": _par_title(pd.after or pd.before, pd.key),
                "state": pd.state,
                "source": pd.source_note,
                "rows": rows,
                "stats": stats(rows),
                "isNew": pd.before is None,
                "isRemoved": pd.after is None,
            })
        articles.append(entry)

    return {
        "publication": {
            "id": pub.id, "teil": pub.teil, "year": pub.year, "number": pub.number,
            "title": doc.title or pub.title, "date": doc.date, "issued": issued.isoformat(),
            "fundstelle": pub.fundstelle, "typ": pub.typ, "initiant": pub.initiant,
            "pdf": pub.pdf_url, "link": pub.link,
        },
        "preamble": doc.preamble,
        "articles": articles,
    }
