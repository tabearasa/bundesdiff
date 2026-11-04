"""Persistent data: analysis results and the law versions seen so far.

Kept separate from the HTTP cache so it can be committed (e.g. to a data
branch) and archived. Location: ``BUNDESDIFF_DATA`` (default: the cache dir).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import tarfile
from pathlib import Path

CACHE_DIR = Path(os.environ.get("BUNDESDIFF_CACHE", Path.home() / ".cache" / "bundesdiff"))
DATA_DIR = Path(os.environ.get("BUNDESDIFF_DATA", CACHE_DIR))

_VERSION_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.xml(?:\.gz)?$")


# --------------------------------------------------------------------------
# Analysis results


def result_path(pub_id: str) -> Path:
    return DATA_DIR / "results" / (pub_id.replace("/", "_") + ".json")


def load_result(pub_id: str) -> dict | None:
    path = result_path(pub_id)
    return json.loads(path.read_text()) if path.exists() else None


def save_result(pub_id: str, result: dict) -> None:
    path = result_path(pub_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


# --------------------------------------------------------------------------
# The list of publications, as last fetched from recht.bund.de (RES-2)


def listing_path(teil: str) -> Path:
    return DATA_DIR / f"publications-{teil}.json"


def save_listing(teil: str, publications: list, fetched: str) -> None:
    """``publications``: sources.Publication objects; ``fetched``: UTC, "YYYY-MM-DDTHH:MM"."""
    path = listing_path(teil)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [dataclasses.asdict(p) for p in publications]
    path.write_text(json.dumps({"fetched": fetched, "publications": rows}, ensure_ascii=False, indent=0))


def load_listing(teil: str):
    """(publications, fetched) of the last successful fetch, or None if there is none."""
    from .sources import Publication  # sources imports this module

    path = listing_path(teil)
    try:
        data = json.loads(path.read_text())
        pubs = [Publication(**row) for row in data["publications"]]
        fetched = data["fetched"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # a damaged file: better no list than a wrong one
    if not pubs or not _valid_time(fetched, "%Y-%m-%dT%H:%M"):
        return None
    for p in pubs:
        if not all(isinstance(getattr(p, f.name), str) for f in dataclasses.fields(p) if f.name != "year"):
            return None
        if (p.teil != teil or type(p.year) is not int or not re.fullmatch(r"[0-9a-z]+", p.number)
                or not _valid_time(p.date, "%Y-%m-%d")):
            return None
    return pubs, fetched


def _valid_time(text, form: str) -> bool:
    """``text`` has exactly the form (ASCII digits only) and names a real day and time."""
    if not isinstance(text, str) or not text.isascii():
        return False
    try:
        return dt.datetime.strptime(text, form).strftime(form) == text
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Law versions


def _content_hash(data: bytes) -> str:
    # gesetze-im-internet.de rebuilds every law daily; ignore the build stamps
    return hashlib.sha256(re.sub(rb'\sbuilddate="\d+"', b"", data)).hexdigest()


def law_versions(prefix: str) -> list[tuple[str, Path]]:
    """Stored versions of one law, oldest first: [(iso date, file)]."""
    out = []
    for p in (DATA_DIR / "laws").glob(prefix + "*"):
        m = _VERSION_RE.match(p.name[len(prefix):])
        if m:
            out.append((m.group(1), p))
    return sorted(out)


def read_law(path: Path) -> bytes:
    return gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()


def save_law_version(prefix: str, date: str, data: bytes) -> None:
    """Store a law text unless it is identical to the latest stored version."""
    versions = law_versions(prefix)
    if any(d == date for d, _ in versions):
        return
    if versions and _content_hash(read_law(versions[-1][1])) == _content_hash(data):
        return
    path = DATA_DIR / "laws" / f"{prefix}{date}.xml.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(data, mtime=0))


# --------------------------------------------------------------------------
# Retention


def prune(cutoff: dt.date, archive: Path) -> dict:
    """Move everything older than ``cutoff`` into the tar.gz ``archive``.

    * results of publications issued before the cutoff
    * law versions older than the cutoff – except the newest version of each
      law, which is still needed as the "before" text of future changes
    """
    old: list[Path] = []
    for path in (DATA_DIR / "results").glob("*.json"):
        try:
            issued = json.loads(path.read_text()).get("publication", {}).get("issued", "")
        except (json.JSONDecodeError, OSError):
            continue
        if issued and issued < cutoff.isoformat():
            old.append(path)
    by_law: dict[str, list[tuple[str, Path]]] = {}
    for path in (DATA_DIR / "laws").glob("*"):
        m = _VERSION_RE.search(path.name)
        if m:
            by_law.setdefault(path.name[: m.start()], []).append((m.group(1), path))
    for versions in by_law.values():
        versions.sort()
        old.extend(p for d, p in versions[:-1] if d < cutoff.isoformat())

    if old:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(old):
                tar.add(path, arcname=str(path.relative_to(DATA_DIR)))
        for path in old:
            path.unlink()
    return {"results": sum(p.parent.name == "results" for p in old),
            "laws": sum(p.parent.name == "laws" for p in old)}
