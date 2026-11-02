"""Draws a small README badge as SVG, without any external service.

    python .github/scripts/badge.py coverage coverage.json > coverage.svg   # from pytest-cov's JSON report
    python .github/scripts/badge.py ruff 0 > ruff.svg                        # number of ruff findings
    python .github/scripts/badge.py license MIT > .github/badges/license.svg # fixed, kept in the repo
"""

from __future__ import annotations

import json
import sys
from html import escape

GREEN, YELLOW, RED = "#2e7d32", "#9a6700", "#b3261e"  # all ≥ 4.5:1 against white text


def _width(text: str) -> int:
    # Verdana 11 px is up to 7.5 px per character; generous, so the text never touches the edge
    return round(7.5 * len(text)) + 14


def svg(label: str, value: str, colour: str) -> str:
    lw, vw = _width(label), _width(value)
    w = lw + vw
    label, value = escape(label), escape(value)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">
<title>{label}: {value}</title>
<clipPath id="r"><rect width="{w}" height="20" rx="3"/></clipPath>
<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{vw}" height="20" fill="{colour}"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
<text x="{lw / 2}" y="14">{label}</text><text x="{lw + vw / 2}" y="14">{value}</text></g>
</svg>
"""


def coverage(report: str) -> str:
    pct = json.load(open(report))["totals"]["percent_covered"]
    colour = GREEN if pct >= 80 else YELLOW if pct >= 60 else RED
    return svg("coverage", f"{pct:.0f} %", colour)


def ruff(findings: str) -> str:
    n = int(findings)
    return svg("ruff", "no findings" if n == 0 else f"{n} findings", GREEN if n == 0 else RED)


def license(name: str) -> str:
    return svg("license", name, GREEN)


if __name__ == "__main__":
    kind, arg = sys.argv[1], sys.argv[2]
    sys.stdout.write({"coverage": coverage, "ruff": ruff, "license": license}[kind](arg))
