"""Extract body text lines (with indentation) from Bundesgesetzblatt PDFs."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

BODY_MIN_SIZE = 8.5  # footnotes are set in 7pt, body text in 9pt
HEADER_MAX_Y = 60  # running header ("Bundesgesetzblatt Jahrgang …", "Seite x von y")
FOOTER_RE = re.compile(r"^Herausgeber: Bundesministerium der Justiz")


@dataclass
class Line:
    text: str
    x: float
    page: int
    size: float
    bold: bool

    @property
    def is_heading(self) -> bool:
        return self.size >= 10.5


def extract_lines(pdf_bytes: bytes) -> list[Line]:
    """Return the body lines of the document in reading order.

    Running headers, page numbers and footnotes are dropped. Fragments on
    the same baseline (e.g. a list label and its text) are merged into one
    line whose ``x`` is the position of the first fragment.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    lines: list[Line] = []
    for page_no, page in enumerate(doc):
        raw: list[tuple[float, float, str, float, bool]] = []
        for block in page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [s for s in ln["spans"] if s["text"].strip()]
                if not spans:
                    continue
                size = max(s["size"] for s in spans)
                bold = all("Bold" in s["font"] for s in spans)
                text = "".join(s["text"] for s in ln["spans"])
                x0, y0 = ln["bbox"][0], ln["bbox"][1]
                if y0 < HEADER_MAX_Y or size < BODY_MIN_SIZE:
                    continue
                if FOOTER_RE.match(text.strip()):
                    continue
                raw.append((round(y0, 0), x0, text, size, bold))
        raw.sort(key=lambda r: (r[0], r[1]))
        prev_y = None
        for y, x, text, size, bold in raw:
            prev = lines[-1] if lines else None
            if prev_y is not None and abs(prev_y - y) <= 2:
                sep = "" if prev.text.endswith(" ") else " "
                prev.text = (prev.text + sep + text).rstrip()
                continue
            lines.append(Line(text.rstrip(), x, page_no, size, bold))
            prev_y = y
    return _drop_cover(lines)


def _drop_cover(lines: list[Line]) -> list[Line]:
    """Remove the masthead of the first page (title, issue number, date)."""
    out = []
    for ln in lines:
        if ln.page == 0 and ln.size > 13:
            continue
        if ln.page == 0 and re.match(r"^(Ausgegeben zu Bonn am|Nr\. \d)", ln.text):
            continue
        out.append(ln)
    return out
