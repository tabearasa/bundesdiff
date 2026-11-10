"""Web application: publication list, synopsis API and static frontend."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import drafts, listing, sources, store
from .analysis import analyze

log = logging.getLogger("bundesdiff")
STATIC = Path(__file__).parent / "static"
RESULT_TTL = 6 * 3600  # analyses are recomputed after this many seconds
WATCH_MINUTES = float(os.environ.get("BUNDESDIFF_WATCH_MINUTES", "1440"))  # once a day (UPD-2)

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def get_analysis(teil: str, year: int, number: str, refresh: bool = False) -> dict:
    pub_id = f"{teil}/{year}/{number}"
    path = store.result_path(pub_id)
    with _locks_guard:
        lock = _locks.setdefault(pub_id, threading.Lock())
    with lock:  # concurrent requests for the same issue wait for one analysis
        if not refresh and path.exists() and time.time() - path.stat().st_mtime < RESULT_TTL:
            return json.loads(path.read_text())
        result = analyze(teil, year, number)
        store.save_result(pub_id, result)
        return result


def _watch() -> None:
    """Analyze new issues soon after publication.

    This stores the amended laws' texts while they are still unconsolidated,
    so later the "before" version is available locally instead of having to be
    reconstructed or taken from the Internet Archive.
    """
    seen: set[str] = set()
    while True:
        for teil in sources.FEEDS:
            try:
                pubs = sources.list_publications(teil)[:20]
            except Exception:  # noqa: BLE001
                log.exception("watch: feed")
                continue
            for pub in pubs:
                if pub.id in seen:
                    continue
                seen.add(pub.id)
                if store.result_path(pub.id).exists():
                    continue
                try:
                    get_analysis(pub.teil, pub.year, pub.number)
                    log.info("watch: analyzed %s", pub.fundstelle)
                except Exception:  # noqa: BLE001
                    log.exception("watch: %s", pub.id)
        time.sleep(WATCH_MINUTES * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if WATCH_MINUTES > 0:
        threading.Thread(target=_watch, daemon=True, name="watcher").start()
    yield


app = FastAPI(title="bundesdiff", lifespan=lifespan)


@app.get("/api/publications")
def publications(teil: str = "1") -> list[dict]:
    if teil not in sources.FEEDS:
        raise HTTPException(400, "nur Teil I wird unterstützt")
    try:
        pubs = sources.list_publications(teil)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"RSS-Feed nicht erreichbar: {e}") from e
    return [listing.entry(p, store.load_result(p.id)) for p in pubs]


@app.get("/api/publications/{teil}/{year}/{number}")
def publication(teil: str, year: int, number: str, refresh: bool = False) -> dict:
    if teil not in sources.FEEDS:
        raise HTTPException(400, "nur Teil I wird unterstützt")
    try:
        return get_analysis(teil, year, number, refresh=refresh)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("analysis %s/%s/%s", teil, year, number)
        raise HTTPException(500, f"Auswertung fehlgeschlagen: {e}") from e


@app.get("/api/entwuerfe")
def bills() -> list[dict]:
    return drafts.entries()


@app.get("/api/entwuerfe/{wp}/{number}")
def bill(wp: int, number: int) -> dict:
    with _locks_guard:
        lock = _locks.setdefault(f"entwurf/{wp}/{number}", threading.Lock())
    try:
        with lock:
            return drafts.get(wp, number)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("bill %s/%s", wp, number)
        raise HTTPException(500, f"Auswertung fehlgeschlagen: {e}") from e


@app.get("/api/entwuerfe/{wp}/{number}/info")
def bill_info(wp: int, number: int) -> dict:
    info = drafts.load(wp, number, "-info") if (wp, number) in drafts.listed() else None
    if info is None:
        raise HTTPException(404, f"Zu Drucksache {wp}/{number} sind keine allgemeinen Informationen gespeichert")
    return info


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def serve(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
