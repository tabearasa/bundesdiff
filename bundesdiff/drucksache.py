"""Read a bill (Gesetzentwurf) from a Bundestag Drucksache PDF (spec 016).

A Drucksache with a bill has up to four parts:

* the Vorblatt ("A. Problem und Ziel", "B. Lösung" …),
* the bill itself – in the same form as a law in the Bundesgesetzblatt: its title, "Vom ...",
  Artikel with numbered instructions,
* the Begründung ("A. Allgemeiner Teil", "B. Besonderer Teil" with "Zu Artikel 1", "Zu Nummer 2" …),
* further Anlagen (Stellungnahmen), which are not read.

The bill starts at its title followed by "Vom ..." and ends at the bold heading "Begründung".
These two anchors hold whether or not the bill is printed as "Anlage 1" behind a letter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

from .model import join_lines, normalize
from .pdftext import Line

BODY_MIN_SIZE = 10.0  # body text is 10.5 pt; footnotes and tables are 9 pt and smaller
HEADING_MIN_SIZE = 10.9  # Artikel headings are 11 pt bold
HEADER_MAX_Y = 95  # running header: "Drucksache 21/6588", "– 7 –", "Deutscher Bundestag – 21. Wahlperiode"
PARAGRAPH_GAP = 15  # lines are 12 pt apart, paragraphs 18 pt
PDF_URL = "https://dserver.bundestag.de/btd/{wp}/{folder}/{wp}{number:05d}.pdf"

_VOM = re.compile(r"^Vom\s*(?:\.\s*\.\s*\.|…)")
_VORBLATT_HEADING = re.compile(r"^[A-H]\. \S")
_ZU = (("Zu Artikel", 2), ("Zu Nummer", 3), ("Zu Buchstabe", 4), ("Zu Doppelbuchstabe", 5),
       ("Zu Dreifachbuch", 6), ("Zu ", 4))


def pdf_url(wp: int, number: int) -> str:
    """21/6588 → …/btd/21/065/2106588.pdf"""
    return PDF_URL.format(wp=wp, number=number, folder=f"{number:05d}"[:3])


@dataclass
class Fragment:
    """One piece of text as the PDF places it."""
    y: float
    x: float
    text: str
    size: float
    bold: bool


@dataclass
class Row:
    """One printed line: the fragments on one baseline, left to right."""
    text: str
    x: float
    y: float
    page: int
    size: float
    bold: bool


@dataclass
class Section:
    heading: str
    level: int
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class Drucksache:
    wp: int
    number: int
    date: str  # ISO, "" if not found
    kind: str  # "Gesetzentwurf"
    author: str  # "der Bundesregierung"
    title: str
    vorblatt: list[Section]
    lines: list[Line]  # the bill, ready for amendments.split_document
    begruendung: list[Section]


def assemble(fragments: list[Fragment], page: int = 0) -> list[Row]:
    """Group the fragments of a page into printed lines.

    The opening quotation mark of new wording hangs to the left of the label and one point
    lower ("8." at y 306, „ at y 307). Read top to bottom this gives "8. „ in Gebieten …" and the
    label is taken for an instruction number. So fragments within 2 pt of a baseline form one
    line and are read left to right: "„8. in Gebieten …".
    """
    rows: list[list[Fragment]] = []
    for f in sorted(fragments, key=lambda f: (f.y, f.x)):
        if rows and abs(rows[-1][0].y - f.y) <= 2:
            rows[-1].append(f)
        else:
            rows.append([f])
    out = []
    for group in rows:
        group.sort(key=lambda f: f.x)
        text = ""
        for f in group:
            piece = f.text.strip()
            if not text or text.endswith("„"):
                text += piece
            else:
                text += " " + piece
        out.append(Row(text, group[0].x, group[0].y, page, max(f.size for f in group),
                       all(f.bold for f in group)))
    return out


def _page_rows(page, page_no: int, min_size: float) -> list[Row]:
    fragments = []
    for block in page.get_text("dict")["blocks"]:
        for ln in block.get("lines", []):
            spans = [s for s in ln["spans"] if s["text"].strip()]
            if not spans:
                continue
            size = max(s["size"] for s in spans)
            if size < min_size:
                continue
            fragments.append(Fragment(round(ln["bbox"][1]), ln["bbox"][0], "".join(s["text"] for s in ln["spans"]),
                                      size, all("Bold" in s["font"] for s in spans)))
    return assemble(fragments, page_no)


def read(pdf_bytes: bytes) -> Drucksache:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    if not len(doc):
        raise LookupError("Die Drucksache hat keine Seiten")
    first = _page_rows(doc[0], 0, 8.0)  # the date in the masthead is 8.5 pt
    head = _masthead(first)
    rows: list[Row] = [r for r in first if r.size >= BODY_MIN_SIZE]
    for no in range(1, len(doc)):
        rows.extend(r for r in _page_rows(doc[no], no, BODY_MIN_SIZE) if r.y >= HEADER_MAX_Y)

    start = _bill_start(rows)
    end = next((i for i in range(start, len(rows)) if rows[i].bold and rows[i].text == "Begründung"), len(rows))
    after = next((i for i in range(end, len(rows))
                  if rows[i].bold and re.fullmatch(r"Anlage \d+", rows[i].text) and rows[i].x > 300), len(rows))
    first_page = rows[start].page
    lines = [Line(r.text, r.x, r.page - first_page, 11.0 if r.bold and r.size >= HEADING_MIN_SIZE else 9.0, r.bold)
             for r in rows[start:end]]
    return Drucksache(
        wp=head["wp"], number=head["number"], date=head["date"], kind=head["kind"], author=head["author"],
        title=head["title"], vorblatt=_vorblatt(rows[:start]), lines=lines,
        begruendung=_sections(rows[end + 1: after], _begruendung_level))


def _masthead(rows: list[Row]) -> dict:
    """Number, date, kind, author and title from the first page."""
    head = {"wp": 0, "number": 0, "date": "", "kind": "", "author": "", "title": ""}
    author, title = [], []
    for r in rows:
        m = re.search(r"\bDrucksache (\d+)/(\d+)$", r.text)
        if m:
            head["wp"], head["number"] = int(m.group(1)), int(m.group(2))
        m = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})$", r.text)
        if m and not head["date"]:
            head["date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        if not r.bold or _VORBLATT_HEADING.match(r.text):
            if title:
                break
            continue
        if r.size > 15 and r.text.startswith("Gesetzentwurf"):
            head["kind"] = r.text
        elif head["kind"] and (title or r.text.startswith("Entwurf ")):
            title.append(r.text)
        elif head["kind"]:
            author.append(r.text)
    head["author"] = join_lines(author)
    head["title"] = join_lines(title)
    if not head["wp"] or head["kind"] != "Gesetzentwurf" or not head["title"]:
        raise LookupError("Die Drucksache ist kein Gesetzentwurf in der bekannten Form")
    return head


def _bill_start(rows: list[Row]) -> int:
    """Index of the first title line of the bill: the bold lines directly above "Vom ..."."""
    for i, r in enumerate(rows):
        if not _VOM.match(r.text) or r.bold:
            continue
        k = i
        while k > 0 and rows[k - 1].page == r.page and rows[k - 1].bold \
                and not re.fullmatch(r"Anlage \d+", rows[k - 1].text):
            k -= 1
        if k < i:
            return k
    raise LookupError("Der Gesetzestext wurde in der Drucksache nicht gefunden („Vom ...“ fehlt)")


def _paragraphs(rows: list[Row]) -> list[str]:
    """Join printed lines into paragraphs: a new one after a gap, never in the middle of a sentence."""
    out: list[list[str]] = []
    prev: Row | None = None
    for r in rows:
        same = prev is not None and (
            (r.page == prev.page and r.y - prev.y < PARAGRAPH_GAP)
            or (r.page != prev.page and not re.search(r"[.:;!?“]$", prev.text)))
        if same:
            out[-1].append(r.text)
        else:
            out.append([r.text])
        prev = r
    return [join_lines(p) for p in out]


def _sections(rows: list[Row], level_of) -> list[Section]:
    sections: list[Section] = []
    body: list[Row] = []

    def close() -> None:
        if body:
            if not sections:
                sections.append(Section("", 1))
            sections[-1].paragraphs.extend(_paragraphs(body))
            body.clear()

    i = 0
    while i < len(rows):
        r = rows[i]
        level = level_of(r) if r.bold else None
        if level is None:
            body.append(r)
            i += 1
            continue
        close()
        heading = [r.text]
        # a heading that runs over two lines
        while i + 1 < len(rows) and rows[i + 1].bold and rows[i + 1].page == r.page \
                and rows[i + 1].y - rows[i].y < PARAGRAPH_GAP and level_of(rows[i + 1]) in (None, 9):
            i += 1
            heading.append(rows[i].text)
        sections.append(Section(join_lines(heading), min(level, 6)))
        i += 1
    close()
    return sections


def _vorblatt(rows: list[Row]) -> list[Section]:
    """The sections "A. Problem und Ziel" … of the Vorblatt; a letter that follows is left out."""
    start = next((i for i, r in enumerate(rows) if r.bold and _VORBLATT_HEADING.match(r.text)), None)
    if start is None:
        return []
    end = next((i for i in range(start, len(rows)) if rows[i].size >= 13.5 and rows[i].page > 0), len(rows))
    return _sections(rows[start:end], lambda r: 1 if _VORBLATT_HEADING.match(r.text) else 9)


def _begruendung_level(r: Row) -> int | None:
    text = normalize(r.text)
    if re.match(r"^[AB]\. (Allgemeiner|Besonderer) Teil", text):
        return 1
    for prefix, level in _ZU:
        if text.startswith(prefix):
            return level
    if re.match(r"^[IVX]+\. \S", text):
        return 2
    if re.match(r"^\d+\. \S", text):
        return 3
    return 9  # any other bold line: a heading of the lowest rank
