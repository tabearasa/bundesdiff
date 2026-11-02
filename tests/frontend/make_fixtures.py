"""Rebuild the frontend test data from real analyses.

    uv run python tests/frontend/make_fixtures.py

Needs the analyses below in the data store (run `bundesdiff serve` and open them once).
The output is committed, so the frontend tests run offline and always see the same data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from bundesdiff import listing as list_entry
from bundesdiff import sources, store

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
    write(OUT / "meta.json", {"generated": "2026-10-27T06:23", "since": "2025-10-27"})
    print(f"{len(listing)} publications, {len(ANALYZED)} analyses → {OUT}")


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
