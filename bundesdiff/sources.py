"""Remote data sources.

* recht.bund.de           – RSS feeds and PDFs of the Bundesgesetzblatt
* NeuRIS (rechtsinformationen.bund.de) – current consolidated law texts (LegalDocML)
* gesetze-im-internet.de   – table of contents (to find a law's page slug)
* Internet Archive         – earlier versions of single norms on gesetze-im-internet.de
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import lxml.html

from . import store
from .model import Node, comparable, label_kind, normalize, par_key, parse_label

RECHT_BUND = "https://www.recht.bund.de"
NEURIS = "https://testphase.rechtsinformationen.bund.de"
GII = "https://www.gesetze-im-internet.de"
USER_AGENT = "bundesdiff/0.1 (+https://github.com/; Synopse-Werkzeug)"

CACHE_DIR = store.CACHE_DIR

_client = httpx.Client(
    headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=httpx.Timeout(30, connect=10)
)


# --------------------------------------------------------------------------
# HTTP with a small disk cache


def fetch(url: str, *, max_age: float | None = None, params: dict | None = None) -> bytes:
    """GET ``url``; responses are cached on disk (``max_age`` seconds, None = forever)."""
    full = str(httpx.URL(url, params=params)) if params else url
    key = hashlib.sha256(full.encode()).hexdigest()
    path = CACHE_DIR / "http" / key[:2] / key
    if path.exists() and (max_age is None or time.time() - path.stat().st_mtime < max_age):
        return path.read_bytes()
    resp = _client.get(full)
    resp.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)
    return resp.content


def fetch_json(url: str, *, max_age: float | None = None, params: dict | None = None):
    return json.loads(fetch(url, max_age=max_age, params=params))


# --------------------------------------------------------------------------
# Bundesgesetzblatt (recht.bund.de)

# Only Teil I (federal laws and ordinances). Teil II – international treaties – is
# deliberately left out; its feed is rss_bgbl-2.xml should it ever be needed.
FEEDS = {
    "1": f"{RECHT_BUND}/rss/feeds/rss_bgbl-1.xml",
}
META_NS = "{http://recht.bund.de/rss/meta}"


@dataclass
class Publication:
    teil: str
    year: int
    number: str
    title: str
    date: str
    typ: str
    initiant: str
    fundstelle: str
    sachgebiet: str
    link: str

    @property
    def pdf_url(self) -> str:
        return f"{RECHT_BUND}/eli/bund/BGBl-{self.teil}/{self.year}/{self.number}/regelungstext.pdf?__blob=publicationFile"

    @property
    def id(self) -> str:
        return f"{self.teil}/{self.year}/{self.number}"


def list_publications(teil: str) -> list[Publication]:
    root = ET.fromstring(fetch(FEEDS[teil], max_age=15 * 60))
    pubs = []
    for item in root.iter("item"):
        def meta(name: str) -> str:
            return (item.findtext(META_NS + name) or "").strip()

        link = (item.findtext("link") or "").strip()
        m = re.search(r"/bgbl-(\d)/(\d{4})/([0-9a-z]+)", link, re.I)
        if not m:
            continue
        pubs.append(
            Publication(
                teil=m.group(1),
                year=int(m.group(2)),
                number=m.group(3),
                title=normalize(item.findtext("title") or ""),
                date=(item.findtext("pubDate") or "").strip(),
                typ=meta("typ"),
                initiant=meta("initiant"),
                fundstelle=meta("fundstelle"),
                sachgebiet=meta("sachgebiet"),
                link=link,
            )
        )
    return pubs


def find_publication(teil: str, year: int, number: str) -> Publication:
    for pub in list_publications(teil):
        if pub.year == year and pub.number == number:
            return pub
    # Older issues are not in the feed any more – we still know how to get the PDF.
    return Publication(teil, year, number, "", "", "", "", f"BGBl. {year} {'I' * int(teil)} Nr. {number}", "",
                       f"{RECHT_BUND}/eli/bund/bgbl-{teil}/{year}/{number}")


def fetch_pdf(pub: Publication) -> bytes:
    data = fetch(pub.pdf_url)
    if not data.startswith(b"%PDF"):
        raise LookupError(f"Keine PDF-Datei für {pub.fundstelle} gefunden")
    return data


# --------------------------------------------------------------------------
# Current consolidated texts: NeuRIS first, gesetze-im-internet.de as fallback


@dataclass
class LawRef:
    source: str  # "neuris" | "gii"
    name: str
    abbreviation: str
    key: str  # NeuRIS work ELI ("eli/bund/bgbl-1/2009/s1870") or GII slug ("tabstg_2009")
    version: str  # ISO date of the consolidated version
    xml_url: str
    alternate_name: str = ""
    stand: str = ""  # GII: "zuletzt geändert durch …" notes
    gii_slug: str | None = None

    @property
    def url(self) -> str:
        if self.source == "gii":
            return f"{GII}/{self.key}/"
        return self.xml_url.rsplit("/", 2)[0]

    @property
    def store_prefix(self) -> str:
        return (self.key if self.source == "neuris" else "gii_" + self.key).replace("/", "_") + "_"

    def names(self) -> list[str]:
        return [n for n in (self.name, self.alternate_name, self.abbreviation) if n]


def _law_ref(item: dict) -> LawRef | None:
    xml = next((e["contentUrl"] for e in item.get("encoding", []) if e["encodingFormat"] == "application/xml"), None)
    if not xml:
        return None
    m = re.search(r"/(\d{4}-\d{2}-\d{2})/\d+/deu$", item["legislationIdentifier"])
    return LawRef(
        source="neuris",
        name=item.get("name") or "",
        abbreviation=item.get("abbreviation") or "",
        key=item["exampleOfWork"]["legislationIdentifier"],
        version=m.group(1) if m else "",
        xml_url=NEURIS + xml,
        alternate_name=item.get("alternateName") or "",
    )


def names_match(wanted: str, ref: LawRef) -> bool:
    want = comparable(wanted)
    return any(comparable(n) == want or want in comparable(n) for n in ref.names())


def neuris_by_eli(work_eli: str) -> LawRef | None:
    data = fetch_json(f"{NEURIS}/v1/legislation", max_age=6 * 3600,
                      params={"eli": work_eli, "mostRelevantOn": dt.date.today().isoformat(), "size": 5})
    for m in data.get("member", []):
        ref = _law_ref(m["item"])
        if ref:
            return ref
    return None


def neuris_by_name(name: str) -> LawRef | None:
    data = fetch_json(f"{NEURIS}/v1/legislation", max_age=6 * 3600,
                      params={"searchTerm": name, "mostRelevantOn": dt.date.today().isoformat(), "size": 10})
    want = comparable(name)
    for m in data.get("member", []):
        ref = _law_ref(m["item"])
        if ref and any(comparable(n) == want for n in ref.names()):
            return ref
    return None


_ORDINALS = ["Erste", "Zweite", "Dritte", "Vierte", "Fünfte", "Sechste", "Siebte", "Achte", "Neunte", "Zehnte",
             "Elfte", "Zwölfte", "Dreizehnte", "Vierzehnte"]


def _gii_toc() -> list[tuple[str, str]]:
    root = ET.fromstring(fetch(f"{GII}/gii-toc.xml", max_age=7 * 86400))
    out = []
    for item in root.iter("item"):
        m = re.search(r"gesetze-im-internet\.de/([^/]+)/xml\.zip", item.findtext("link") or "")
        if m:
            out.append((normalize(item.findtext("title") or ""), m.group(1)))
    return out


def gii_slug(title: str) -> str | None:
    """Find a law's slug on gesetze-im-internet.de by its title."""
    title = normalize(title)
    toc = _gii_toc()
    sgb = re.match(r"^(\w+?)s? Buch(?:es)? Sozialgesetzbuch", title)
    if sgb and sgb.group(1) in _ORDINALS:
        n = _ORDINALS.index(sgb.group(1)) + 1
        return "sgb_9_2018" if n == 9 else f"sgb_{n}"
    want = comparable(title)
    for t, slug in toc:
        if comparable(t) == want:
            return slug
    for t, slug in toc:
        # "Sozialgesetzbuch … (Artikel 1 des Gesetzes v. …)", "Foo-Gesetz (FooG)"
        if comparable(t).startswith(want + "(") or comparable(t.split(" (")[0]) == want:
            return slug
    # Short titles ("Bundes-Immissionsschutzgesetz") are not in the TOC: try laws whose
    # abbreviation fits the name and verify against the law's own metadata.
    candidates = [(slug, abbr) for slug, abbr, _ in _gii_index() if _abbr_fits(abbr, title)]
    candidates.sort(key=lambda c: (-len(re.sub(r"[^A-Za-zÄÖÜäöüß]", "", c[1])), bool(re.search(r"\d", c[1]))))
    for slug, _ in candidates[:6]:
        try:
            meta = _gii_meta(slug)
        except (httpx.HTTPError, ET.ParseError, StopIteration, OSError):
            continue
        if any(comparable(v) == want for v in meta.values() if v):
            return slug
    return None


def _gii_index() -> list[tuple[str, str, str]]:
    """(slug, abbreviation, title) of all laws, from the alphabetical lists."""
    out = []
    for part in [*"ABCDEFGHIJKLMNOPQRSTUVWXYZ", *"123456789"]:
        try:
            html = fetch(f"{GII}/Teilliste_{part}.html", max_age=7 * 86400).decode("latin-1")
        except httpx.HTTPError:
            continue
        for m in re.finditer(r'href="\./([^/"]+)/index\.html"><abbr title="([^"]*)">\s*([^<]+?)\s*</abbr>', html):
            out.append((m.group(1), normalize(m.group(3)), normalize(m.group(2))))
    return out


def _abbr_fits(abbr: str, name: str) -> bool:
    """Could ``abbr`` (e.g. "BImSchG") abbreviate ``name`` ("Bundes-Immissionsschutzgesetz")?"""
    a = re.sub(r"[^a-zäöüß]", "", abbr.lower())
    n = re.sub(r"[^a-zäöüß]", "", name.lower())
    if not a or not n or a[0] != n[0]:
        return False
    endings = {"g": ("gesetz", "gesetzbuch"), "v": ("verordnung",), "o": ("ordnung",), "b": ("buch",)}
    if a[-1] in endings and not n.endswith(endings[a[-1]]):
        return False
    pos = 0
    for ch in a:
        pos = n.find(ch, pos)
        if pos < 0:
            return False
        pos += 1
    return True


def _gii_meta(slug: str) -> dict:
    root = ET.fromstring(_unzip_first_xml(fetch(f"{GII}/{slug}/xml.zip", max_age=12 * 3600)))
    meta = root.find("norm/metadaten")
    return {k: normalize(meta.findtext(k) or "") for k in ("kurzue", "langue", "jurabk", "amtabk")} \
        if meta is not None else {}


def gii_law(slug: str) -> LawRef:
    data = fetch(f"{GII}/{slug}/xml.zip", max_age=12 * 3600)
    xml = _unzip_first_xml(data)
    root = ET.fromstring(xml)
    build = (root.get("builddate") or "")[:8]
    first = root.find("norm/metadaten")
    name = normalize(first.findtext("kurzue") or first.findtext("langue") or "") if first is not None else ""
    abbr = (first.findtext("amtabk") or first.findtext("jurabk") or "") if first is not None else ""
    stand = " ".join(normalize(e.findtext("standkommentar") or "") for e in first.iter("standangabe")) \
        if first is not None else ""
    version = f"{build[:4]}-{build[4:6]}-{build[6:8]}" if len(build) == 8 else ""
    return LawRef("gii", name, abbr, slug, version, f"{GII}/{slug}/xml.zip", stand=stand, gii_slug=slug)


def _unzip_first_xml(data: bytes) -> bytes:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".xml"))
        return zf.read(name)


def load_law(ref: LawRef) -> Node:
    """Parse the law's current text and remember this version (see :mod:`store`)."""
    data = fetch(ref.xml_url, max_age=12 * 3600)
    if ref.source == "gii":
        data = _unzip_first_xml(data)
    store.save_law_version(ref.store_prefix, ref.version, data)
    return parse_legaldocml(data) if ref.source == "neuris" else parse_gii_xml(data)


def stored_versions(ref: LawRef) -> list[tuple[str, Path]]:
    """Locally stored versions of a law, oldest first: [(iso date, file)]."""
    return store.law_versions(ref.store_prefix)


def parse_stored(ref: LawRef, path: Path) -> Node:
    data = store.read_law(path)
    return parse_legaldocml(data) if ref.source == "neuris" else parse_gii_xml(data)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _inline_text(el: ET.Element) -> str:
    """Text of an inline container; sentence markers become sentence breaks."""
    out = [el.text or ""]
    for child in el:
        tag = _local(child.tag)
        if tag in ("blockList", "table", "list"):
            pass  # handled structurally by caller
        elif tag == "br":
            out.append(" ")
        elif tag in ("authorialNote", "noteRef"):
            pass
        else:
            out.append(_inline_text(child))
        out.append(child.tail or "")
    return "".join(out)


def _xml_parts(el: ET.Element, node: Node) -> None:
    for child in el:
        tag = _local(child.tag)
        if tag in ("num", "heading"):
            continue
        if tag == "p":
            text = normalize(_inline_text(child))
            if text:
                node.parts.append(text)
        elif tag in ("paragraph", "item", "point", "listItem"):
            num = child.find(f"./{{*}}num")
            label = normalize("".join(num.itertext())) if num is not None else ""
            kind = "abs" if tag == "paragraph" else "item"
            sub = Node(kind, label)
            lk = label_kind(label)
            if lk:
                sub.kind = lk[0]
            elif kind == "item":
                sub.kind = "nr"
            heading = child.find(f"./{{*}}heading")
            if heading is not None:
                sub.heading = normalize("".join(heading.itertext()))
            _xml_parts(child, sub)
            node.parts.append(sub)
        elif tag == "table":
            rows = []
            for tr in child.iter():
                if _local(tr.tag) == "tr":
                    rows.append(" | ".join(normalize("".join(td.itertext())) for td in tr if _local(td.tag) in ("td", "th")))
            node.parts.extend(r for r in rows if r)
        elif tag in ("content", "blockList", "intro", "wrapUp", "list", "blockContainer", "hcontainer",
                     "subparagraph", "wrap", "listIntroduction", "listWrapUp"):
            _xml_parts(child, node)
        else:
            text = normalize("".join(child.itertext()))
            if text:
                node.parts.append(text)


def parse_legaldocml(data: bytes) -> Node:
    root = ET.fromstring(data)
    law = Node("law")
    body = next((e for e in root.iter() if _local(e.tag) == "body"), None)
    if body is None:
        return law
    for art in body.iter():
        if _local(art.tag) != "article":
            continue
        num = art.find("./{*}num")
        heading = art.find("./{*}heading")
        node = Node(
            "par",
            normalize("".join(num.itertext())) if num is not None else "",
            normalize("".join(heading.itertext())) if heading is not None else "",
        )
        _xml_parts(art, node)
        law.parts.append(node)
    return law


# --------------------------------------------------------------------------
# gesetze-im-internet.de + Internet Archive (earlier versions of single norms)


_GII_INLINE_SKIP = {"FnR", "FnArea", "Footnotes", "fussnoten", "SUP"}


def parse_gii_xml(data: bytes) -> Node:
    """Parse a full law from gesetze-im-internet.de's XML (gii-norm.dtd)."""
    root = ET.fromstring(data)
    law = Node("law")
    for norm in root.iter("norm"):
        meta = norm.find("metadaten")
        enbez = normalize(meta.findtext("enbez") or "") if meta is not None else ""
        if not re.match(r"^(§|Art)", enbez):
            continue
        titel_el = meta.find("titel")
        titel = normalize("".join(titel_el.itertext())) if titel_el is not None else ""
        node = Node("par", enbez, titel)
        content = norm.find("textdaten/text/Content")
        if content is not None:
            _gii_xml_parts(content, node)
        law.parts.append(node)
    return law


def _gii_xml_parts(el: ET.Element, node: Node) -> None:
    state = {"new": True}

    def add(text: str) -> None:
        text = normalize(text)
        if not text:
            return
        if not state["new"] and node.parts and isinstance(node.parts[-1], str):
            node.parts[-1] = normalize(node.parts[-1] + " " + text)
        else:
            node.parts.append(text)
        state["new"] = False

    add(el.text or "")
    for child in el:
        tag = child.tag
        if tag == "P":
            first = normalize(child.text or "")
            parsed = parse_label(first) if first else None
            if parsed and parsed[0] == "abs" and node.kind == "par":
                sub = Node("abs", f"({parsed[1]})")
                child.text = parsed[2]
                _gii_xml_parts(child, sub)
                node.parts.append(sub)
            else:
                state["new"] = True
                _gii_xml_parts(child, node)
            state["new"] = True
        elif tag == "DL":
            label = ""
            for item in child:
                if item.tag == "DT":
                    label = normalize("".join(item.itertext()))
                elif item.tag == "DD":
                    lk = label_kind(label)
                    sub = Node(lk[0] if lk else "nr", label)
                    _gii_xml_parts(item, sub)
                    node.parts.append(sub)
            state["new"] = True
        elif tag in ("LA", "Content", "div", "table", "tgroup", "tbody", "row", "pre"):
            state["new"] = True
            _gii_xml_parts(child, node)
            state["new"] = True
        elif tag == "BR":
            add(" ")
        elif tag in _GII_INLINE_SKIP:
            pass
        else:
            add("".join(child.itertext()))
        add(child.tail or "")


def gii_norm_page(par_label: str) -> str | None:
    key = par_key(par_label)
    if key.startswith("§"):
        return f"__{key[1:]}.html"
    if key.startswith("art"):
        return f"art_{key[3:]}.html"
    return None


def wayback_norm(slug: str, par_label: str, before: dt.date) -> tuple[Node, str] | None:
    """The last archived version of a norm page before ``before``.

    Returns (unit tree, snapshot date) or None.
    """
    page = gii_norm_page(par_label)
    if not page:
        return None
    url = f"www.gesetze-im-internet.de/{slug}/{page}"
    try:
        rows = fetch_json(
            "https://web.archive.org/cdx/search/cdx",
            max_age=86400,
            params={"url": url, "output": "json", "to": before.strftime("%Y%m%d"),
                    "filter": "statuscode:200", "limit": "-1"},
        )
    except (httpx.HTTPError, json.JSONDecodeError):
        return None
    if len(rows) < 2:
        return None
    ts = rows[-1][1]
    try:
        html = fetch(f"https://web.archive.org/web/{ts}id_/https://{url}")
    except httpx.HTTPError:
        return None
    node = parse_gii_norm(html)
    if node is None:
        return None
    return node, f"{ts[6:8]}.{ts[4:6]}.{ts[0:4]}"


def parse_gii_norm(html: bytes) -> Node | None:
    doc = lxml.html.fromstring(html)
    enbez = doc.xpath("//span[@class='jnenbez']")
    if not enbez:
        return None
    title = doc.xpath("//span[@class='jnentitel']")
    node = Node("par", normalize(enbez[0].text_content()), normalize(title[0].text_content()) if title else "")
    content = doc.xpath("//div[@class='jnhtml']")
    if content:
        _gii_parts(content[0], node)
    return node


_BLOCK_TAGS = {"div", "p", "table", "tr"}


def _gii_parts(el, node: Node) -> None:
    """Walk mixed content of a gesetze-im-internet.de norm into ``node``."""
    state = {"new": True}

    def add(text: str) -> None:
        text = normalize(text)
        if not text:
            return
        if not state["new"] and node.parts and isinstance(node.parts[-1], str):
            node.parts[-1] = normalize(node.parts[-1] + " " + text)
        else:
            node.parts.append(text)
        state["new"] = False

    add(el.text or "")
    for child in el:
        tag = child.tag if isinstance(child.tag, str) else ""
        cls = child.get("class") or "" if tag else ""
        if tag == "dl":
            _gii_list(child, node)
            state["new"] = True
        elif tag == "div" and "jurAbsatz" in cls:
            first = normalize(child.text or "")
            parsed = parse_label(first) if first else None
            if parsed and parsed[0] == "abs" and node.kind == "par":
                sub = Node("abs", f"({parsed[1]})")
                child.text = parsed[2]
                _gii_parts(child, sub)
                node.parts.append(sub)
            else:
                state["new"] = True
                _gii_parts(child, node)
            state["new"] = True
        elif tag in _BLOCK_TAGS:
            state["new"] = True
            _gii_parts(child, node)
            state["new"] = True
        elif tag == "br":
            add(" ")
        elif tag:
            add(child.text_content())
        add(child.tail or "")


def _gii_list(dl, node: Node) -> None:
    label = ""
    for child in dl:
        if child.tag == "dt":
            label = normalize(child.text_content())
        elif child.tag == "dd":
            lk = label_kind(label)
            item = Node(lk[0] if lk else "nr", label)
            _gii_parts(child, item)
            node.parts.append(item)
