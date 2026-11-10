"""Rebuild the frontend test data from real analyses.

    uv run python tests/frontend/make_fixtures.py

Needs the analyses below in the data store (run `bundesdiff serve` and open them once).
The output is committed, so the frontend tests run offline and always see the same data.

Only the bill (spec 016), without touching the publications:

    uv run python tests/frontend/make_fixtures.py entwuerfe
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from bundesdiff import drafts, sources, store
from bundesdiff import listing as list_entry

OUT = Path(__file__).parent / "fixtures" / "data"

# Chosen to cover every way a publication can look:
ANALYZED = {
    "1/2026/309": "two laws, old text reconstructed, archive note",
    "1/2026/314": "new text calculated, failed and unsupported instructions",
    "1/2026/306": "small ordinance with one change",
    "1/2026/315": "announcement without any amendment",
    "1/2026/311": "two in-force dates: the rest of the act later, Artikel 2 the day after promulgation",
}
FAILED = "1/2026/316"  # stored with an error instead of a result
LIST_LENGTH = 60  # spans more than one month

# The bill Drucksache 21/6588, cut down so the tests stay fast (the full one changes 136 §§) and the
# page stays below 32767 px even at 320 px width – Firefox cannot take a screenshot of a taller page:
DRAFT = (21, 6588)
DRAFT_ARTICLES = {
    "1": "Baugesetzbuch: only Nummer 49, the new Achter Teil with § 135e – its heading stands above the § (ENT-18)",
    "4": "Raumordnungsgesetz: many instructions, some not shown, one that does not fit (a slip in the bill), "
         "law changed after the bill; of its 14 §§ only those of DRAFT_PARS are kept",
    "5": "Verwaltungsgerichtsordnung: one change, law from gesetze-im-internet.de, changed after the bill",
    "6": "HOAI: one change shown, two only in the wording; law older than the bill",
    "12": "Investitionsvorranggesetz: an Artikel with a single instruction",
    "13": "Inkrafttreten: text with placeholders instead of dates",
}
DRAFT_PARS = {"1": ["§135e"], "4": ["§3", "§6", "§27"]}
DRAFT_INSTRUCTIONS = {"1": ["49."]}  # Artikel → the instructions kept (others: all)
# part → number of sections kept (None: all); of each section the first DRAFT_PARAGRAPHS paragraphs
DRAFT_INFO = {"vorblatt": 2, "allgemein": 2, "artikel-4": 5, "artikel-5": None, "artikel-6": None,
              "artikel-12": None, "artikel-13": None}
DRAFT_PARAGRAPHS = 2


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    pubs = sources.list_publications("1")[:LIST_LENGTH]
    listing = []
    for p in pubs:
        result = None
        if p.id in ANALYZED:
            result = store.load_result(p.id)
            if not result or result.get("error"):
                raise SystemExit(f"{p.id}: no stored analysis – open it once in `bundesdiff serve`")
            write(OUT / p.teil / str(p.year) / f"{p.number}.json", result)
        elif p.id == FAILED:
            result = {"error": "Testfehler: PDF nicht lesbar", "failedAt": 0, "publication": {"issued": p.date}}
            write(OUT / p.teil / str(p.year) / f"{p.number}.json", result)
        listing.append(list_entry.entry(p, result))
    missing = set(ANALYZED) - {p["id"] for p in listing}
    if missing:
        raise SystemExit(f"not among the newest {LIST_LENGTH} publications: {sorted(missing)}")
    write(OUT / "publications-1.json", listing)
    write(OUT / "meta.json", {"generated": "2026-10-30T06:41", "listFetched": "2026-10-30T06:23",
                                 "since": "2025-10-27"})
    print(f"{len(listing)} publications, {len(ANALYZED)} analyses → {OUT}")
    draft()


def draft() -> None:
    """The bill, reduced to the Artikel of DRAFT_ARTICLES and the parts of DRAFT_INFO."""
    wp, number = DRAFT
    result, info = drafts.load(wp, number), drafts.load(wp, number, "-info")
    if not result or result.get("error") or not info:
        raise SystemExit(f"Drucksache {wp}/{number}: no stored analysis – run "
                         "`uv run python -c 'from bundesdiff import drafts; print(drafts.update())'`")
    result["articles"] = [a for a in result["articles"] if a["number"] in DRAFT_ARTICLES]
    for a in result["articles"]:
        if a["number"] in DRAFT_PARS:
            a["pars"] = [p for p in a["pars"] if p["key"] in DRAFT_PARS[a["number"]]]
            assert len(a["pars"]) == len(DRAFT_PARS[a["number"]]), f"Artikel {a['number']}: a § of DRAFT_PARS is missing"
        if a["number"] in DRAFT_INSTRUCTIONS:
            a["instructions"] = [i for i in a["instructions"] if i["marker"] in DRAFT_INSTRUCTIONS[a["number"]]]
            assert len(a["instructions"]) == len(DRAFT_INSTRUCTIONS[a["number"]]), f"Artikel {a['number']}: an instruction is missing"
    instructions = [i for a in result["articles"] for i in a.get("instructions") or []]
    result["counts"] = {"shown": sum(i["status"] == "applied" for i in instructions), "total": len(instructions)}
    parts = []
    for part in info["parts"]:
        if part["id"] in DRAFT_INFO:
            sections = [{**s, "paragraphs": s["paragraphs"][:DRAFT_PARAGRAPHS]}
                        for s in part["sections"][:DRAFT_INFO[part["id"]]]]
            parts.append({**part, "sections": sections})
    result["info"] = [{"id": p["id"], "title": p["title"]} for p in parts]
    if OUT.joinpath("entwurf").exists():
        shutil.rmtree(OUT / "entwurf")
    write(OUT / "entwurf" / str(wp) / f"{number}.json", result)
    write(OUT / "entwurf" / str(wp) / f"{number}-info.json", {"parts": parts})
    entry = next(e for e in drafts.entries() if e["id"] == drafts.draft_id(wp, number))
    entry["laws"] = list_entry.laws(result["articles"])
    write(OUT / "entwuerfe.json", [entry])
    print(f"Drucksache {wp}/{number}: {len(result['articles'])} Artikel, {len(parts)} parts of information → {OUT}")


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    draft() if sys.argv[1:] == ["entwuerfe"] else main()
