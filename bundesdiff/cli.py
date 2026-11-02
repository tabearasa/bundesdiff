"""Command line: ``bundesdiff [serve|export|prune]``."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="bundesdiff", description="Synopse zum Bundesgesetzblatt")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("serve", help="Web-App mit Live-Auswertung starten (Standard)")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))

    p = sub.add_parser("export", help="Statische Website mit vorberechneten Auswertungen erzeugen")
    p.add_argument("--site", type=Path, default=Path("_site"), help="Zielverzeichnis")
    p.add_argument("--days", type=int, default=365, help="nur Veröffentlichungen der letzten N Tage")
    p.add_argument("--max-new", type=int, default=50, help="höchstens so viele neue Auswertungen pro Lauf")
    p.add_argument("--retry-hours", type=float, default=24, help="fehlgeschlagene Auswertungen erst nach N Stunden wiederholen")

    p = sub.add_parser("prune", help="Daten älter als N Tage in ein Archiv (tar.gz) verschieben")
    p.add_argument("--days", type=int, default=365)
    p.add_argument("--archive", type=Path, required=True, help="Pfad der Archivdatei (.tar.gz)")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "export":
        from .export import export

        print(json.dumps(export(args.site, args.days, args.max_new, args.retry_hours)))
    elif args.cmd == "prune":
        from .store import prune

        print(json.dumps(prune(dt.date.today() - dt.timedelta(days=args.days), args.archive)))
    else:
        from .app import serve

        serve(getattr(args, "host", os.environ.get("HOST", "127.0.0.1")),
              getattr(args, "port", int(os.environ.get("PORT", "8000"))))
