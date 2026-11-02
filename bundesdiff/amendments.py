"""Parse amending acts ("Mantelgesetze"/"Änderungsverordnungen") into instructions.

German amending acts follow a fairly rigid drafting language
(Handbuch der Rechtsförmlichkeit), e.g.

    1. § 2 Absatz 1 wird durch den folgenden Absatz 1 ersetzt: „(1) …“
    2. § 38 wird wie folgt geändert:
       a) Nach Absatz 3 wird der folgende Absatz 3a eingefügt: „(3a) …“
       b) In Absatz 4 wird die Angabe „3“ durch die Angabe „3 und 3a“ ersetzt.

This module turns such text into a list of :class:`Instruction` objects with a
resolved location (path of units) and an operation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import Node, join_lines, normalize, tree_from_lines
from .pdftext import Line

# --------------------------------------------------------------------------
# Document structure


@dataclass
class Article:
    number: str  # "1" or "" for acts without articles
    heading: str
    lines: list[Line]

    @property
    def text(self) -> str:
        return join_lines([ln.text for ln in self.lines])


@dataclass
class Document:
    title: str
    date: str  # "Vom 19. Oktober 2026"
    preamble: str
    articles: list[Article]


def split_document(lines: list[Line]) -> Document:
    title_lines, date, preamble_lines = [], "", []
    articles: list[Article] = []
    i = 0
    # Title: bold lines at the very top of page 1
    while i < len(lines) and lines[i].page == 0 and lines[i].bold and not lines[i].text.startswith("Vom "):
        title_lines.append(lines[i].text)
        i += 1
    if i < len(lines) and lines[i].text.startswith("Vom "):
        date = lines[i].text
        i += 1
    current: Article | None = None
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^Artikel (\d+[a-z]*)$", ln.text.strip())
        if m and ln.is_heading:
            heading = []
            i += 1
            while i < len(lines) and lines[i].is_heading:
                heading.append(lines[i].text)
                i += 1
            current = Article(m.group(1), normalize(" ".join(heading)).rstrip("*").strip(), [])
            articles.append(current)
            continue
        if current is None:
            preamble_lines.append(ln)
        else:
            current.lines.append(ln)
        i += 1
    if not articles:
        # Acts without articles (typical for single-purpose amending ordinances):
        # the body starts after the enacting formula ("… verordnet …:").
        body_start = 0
        for k, ln in enumerate(preamble_lines):
            if ln.text.rstrip().endswith(":") and not re.search(r"geändert:$", ln.text):
                body_start = k + 1
                break
        articles = [Article("", "", preamble_lines[body_start:])]
        preamble_lines = preamble_lines[:body_start]
    return Document(
        title=normalize(" ".join(title_lines)),
        date=date,
        preamble=join_lines([ln.text for ln in preamble_lines]),
        articles=articles,
    )


# --------------------------------------------------------------------------
# Quotes

OPEN_Q, CLOSE_Q = "„", "“"


@dataclass
class Quote:
    text: str
    lines: list[tuple[float, str]]

    def tree(self) -> Node:
        return tree_from_lines(self.lines)


def extract_quotes(lines: list[tuple[float, str]]) -> tuple[str, list[Quote]]:
    """Replace top-level „…“ quotes by placeholders ⟦0⟧, ⟦1⟧ …"""
    sentence_lines: list[str] = []
    quotes: list[Quote] = []
    depth = 0
    cur_sentence = ""
    q_lines: list[tuple[float, str]] = []
    q_buf = ""
    for x, text in lines:
        q_line_start = True
        for ch in text:
            if ch == OPEN_Q:
                if depth == 0:
                    q_lines, q_buf = [], ""
                    q_x = x
                    depth = 1
                    q_line_start = False
                    continue
                depth += 1
            elif ch == CLOSE_Q and depth > 0:
                depth -= 1
                if depth == 0:
                    if q_buf:
                        q_lines.append((q_x, q_buf))
                    quotes.append(Quote(join_lines([t for _, t in q_lines]), q_lines))
                    cur_sentence += f" ⟦{len(quotes) - 1}⟧ "
                    continue
            if depth > 0:
                if q_line_start:
                    q_x = x
                    q_line_start = False
                q_buf += ch
            else:
                cur_sentence += ch
        if depth > 0:
            q_lines.append((q_x, q_buf))
            q_buf = ""
        else:
            sentence_lines.append(cur_sentence)
            cur_sentence = ""
    if cur_sentence:
        sentence_lines.append(cur_sentence)
    if depth > 0 and (q_lines or q_buf):  # unbalanced quotes
        quotes.append(Quote(join_lines([t for _, t in q_lines] + [q_buf]), q_lines))
    return join_lines(sentence_lines), quotes


# --------------------------------------------------------------------------
# Locations

KIND_WORDS = {
    "§": "par", "§§": "par", "Artikel": "par", "Absatz": "abs", "Absätze": "abs", "Absätzen": "abs",
    "Satz": "satz", "Sätze": "satz", "Sätzen": "satz", "Nummer": "nr", "Nummern": "nr",
    "Buchstabe": "bst", "Buchstaben": "bst", "Doppelbuchstabe": "dbst", "Doppelbuchstaben": "dbst",
    "Dreifachbuchstabe": "tbst", "Dreifachbuchstaben": "tbst", "Anlage": "anlage", "Anhang": "anlage",
}
UNIT_LEVEL = {"par": 1, "anlage": 1, "toc": 1, "abs": 2, "nr": 3, "bst": 4, "dbst": 5, "tbst": 6, "satz": 7,
              "heading": 7, "intro": 8, "outro": 8}
KEY = r"\d+[a-z]*|[a-z]{1,3}"
_LOC_TOKEN = re.compile(
    r"(§§|§|Artikel|Absätzen|Absätze|Absatz|Sätzen|Sätze|Satz|Nummern|Nummer|Doppelbuchstaben|Doppelbuchstabe|"
    r"Dreifachbuchstaben|Dreifachbuchstabe|Buchstaben|Buchstabe|Anlage|Anhang)\s+"
    rf"((?:{KEY})(?:\s*(?:,|und|bis|sowie)\s*(?:{KEY})(?![\w]))*)"
)


@dataclass
class Step:
    kind: str
    keys: list[str]
    is_range: bool = False

    def label(self) -> str:
        names = {"par": "§", "abs": "Absatz", "nr": "Nummer", "bst": "Buchstabe", "dbst": "Doppelbuchstabe",
                 "tbst": "Dreifachbuchstabe", "satz": "Satz", "anlage": "Anlage", "heading": "Überschrift",
                 "toc": "Inhaltsübersicht", "intro": "(Text vor der Aufzählung)", "outro": "(Text nach der Aufzählung)"}
        if self.kind in ("heading", "toc", "intro", "outro"):
            return names[self.kind]
        joiner = " bis " if self.is_range else " und "
        keys = joiner.join(self.keys)
        if self.kind == "par":
            return ("§ " if len(self.keys) == 1 else "§§ ") + keys if not self.keys[0].startswith("art") else (
                "Artikel " + joiner.join(k[3:] for k in self.keys))
        return f"{names[self.kind]} {keys}"


def _expand_keys(spec: str) -> tuple[list[str], bool]:
    spec = normalize(spec)
    if " bis " in spec:
        a, b = [s.strip() for s in spec.split(" bis ", 1)]
        if a.isdigit() and b.isdigit():
            return [str(n) for n in range(int(a), int(b) + 1)], False
        return [a, b], True
    return [k for k in re.split(r"\s*(?:,|und|sowie)\s*", spec) if k], False


def parse_location(text: str) -> list[Step]:
    """'§ 4 Absatz 1 Satz 2' -> [Step(par,[4]), Step(abs,[1]), Step(satz,[2])]"""
    steps: list[Step] = []
    if re.search(r"\bInhaltsübersicht\b", text):
        steps.append(Step("toc", []))
    for m in _LOC_TOKEN.finditer(text):
        kind = KIND_WORDS[m.group(1)]
        keys, is_range = _expand_keys(m.group(2))
        if kind == "par" and m.group(1) == "Artikel":
            keys = ["art" + k for k in keys]
        steps.append(Step(kind, keys, is_range))
    if re.search(r"\bÜberschrift\b", text):
        steps.append(Step("heading", []))
    return steps


def combine(context: list[Step], loc: list[Step]) -> list[Step]:
    if not loc:
        return list(context)
    if any(s.kind in ("toc", "anlage") for s in context):
        return list(context) + loc  # positions inside a table of contents / annex
    first = UNIT_LEVEL.get(loc[0].kind, 9)
    base = [s for s in context if UNIT_LEVEL.get(s.kind, 0) < first]
    return base + loc


def format_path(path: list[Step]) -> str:
    return " ".join(s.label() for s in path)


# --------------------------------------------------------------------------
# Instructions


@dataclass
class Instruction:
    raw: str  # instruction sentence as printed (quotes included)
    marker: str  # "2. b) aa)"
    path: list[Step]  # resolved location
    op: str  # see OPS below
    args: dict = field(default_factory=dict)
    note: str = ""

    @property
    def location(self) -> str:
        return format_path(self.path)

    @property
    def par(self) -> str | None:
        """Key of the § / Artikel this instruction belongs to (for grouping)."""
        for s in self.path:
            if s.kind == "par":
                return s.keys[0]
        return None


OPS = {
    "replace_text": "Ersetzung",
    "delete_text": "Streichung",
    "insert_text": "Einfügung",
    "append_text": "Anfügung",
    "replace_units": "Neufassung",
    "insert_units": "Einfügung",
    "append_units": "Anfügung",
    "delete_units": "Streichung",
    "replace_sentence": "Satz ersetzt",
    "insert_sentence": "Satz eingefügt",
    "append_sentence": "Satz angefügt",
    "delete_sentence": "Satz gestrichen",
    "replace_heading": "Überschrift ersetzt",
    "renumber": "Umnummerierung",
    "unsupported": "nicht automatisch auswertbar",
}

_MARKER = re.compile(r"^((?:\d+[a-z]?\.)|(?:[a-z]{1,3}\)))\s+")
_PUNCT = {"Punkt": ".", "Komma": ",", "Semikolon": ";", "Doppelpunkt": ":"}
_NOUN = (r"(?:Absatz|Absätze|Satz|Sätze|Nummer|Nummern|Buchstabe|Buchstaben|Doppelbuchstabe|Doppelbuchstaben|"
         r"Dreifachbuchstabe|Dreifachbuchstaben|§|§§|Artikel|Überschrift|Angabe|Angaben|Teil|Abschnitt|"
         r"Unterabschnitt|Kapitel|Zeile|Zeilen|Spalte|Anlage|Anhang|Tabelle|Fußnote|Eintrag|Einträge)")


def marker_level(marker: str) -> int:
    if marker.endswith("."):
        return 1
    letters = marker.rstrip(")")
    return 1 + len(letters)


def _quote_count(text: str) -> int:
    return len(re.findall(r"⟦\d+⟧", text))


def _unit_kind_of_noun(noun: str) -> str:
    noun = noun.strip()
    for word, kind in KIND_WORDS.items():
        if noun.startswith(word):
            return kind
    if noun.startswith("Überschrift"):
        return "heading"
    return "other"


TEXT_OPS = ("replace_text", "delete_text", "insert_text", "append_text")
_MULTI_LOC = re.compile(r"\s*(?:,|\bund\b|\bsowie\b)\s+(?=(?:in\s+)?(?:§|Artikel|Absatz|Satz|Nummer|Buchstabe)\s)")


def parse_sentence(sentence: str, quotes: list[Quote], context: list[Step]) -> list[tuple[str, list[Step], dict]]:
    """Classify one instruction sentence into (op, path, args) – one per addressed location."""
    op, path, args = _parse_sentence(sentence, quotes, context)
    if op not in TEXT_OPS:
        return [(op, path, args)]
    # "In § 23 Absatz 1 Satz 1 und § 25 Absatz 1a wird jeweils …"
    m = re.match(r"^In (?:der |dem |den )?(.+?),? (?:wird|werden) ", normalize(sentence))
    paths = [path]
    if m and _MULTI_LOC.search(m.group(1)):
        paths = []
        for piece in _MULTI_LOC.split(m.group(1)):
            piece = re.sub(r"^in\s+", "", piece)
            sub = combine(context, parse_location(piece))
            if sub:
                paths.append(sub + [st for st in path if st.kind in ("heading", "intro", "outro")])
        paths = paths or [path]
    # "In den Absätzen 1 und 2 wird jeweils …" -> one instruction per unit
    out = []
    for p in paths:
        expanded = [[]]
        for st in p:
            keys = st.keys if (len(st.keys) > 1 and not st.is_range and st.kind != "satz") else [None]
            expanded = [e + [Step(st.kind, [k]) if k else st] for e in expanded for k in keys]
        out.extend((op, e, args) for e in expanded)
    return out


def _parse_sentence(sentence: str, quotes: list[Quote], context: list[Step]) -> tuple[str, list[Step], dict]:
    s = normalize(sentence).rstrip(".").strip()
    # "… ersetzt: ⟦0⟧" – the quoted block follows a colon
    block = re.match(r"^(.*?):\s*(?:⟦\d+⟧[\s.,;]*)+$", s)
    if block:
        s = block.group(1)
    s = s.rstrip(".:").strip()
    q = [qq.text for qq in quotes]

    def loc_of(text: str) -> list[Step]:
        return combine(context, parse_location(text))

    # --- text-level changes: "In <loc> wird die Angabe „x“ durch die Angabe „y“ ersetzt"
    m = re.match(r"^In (?:der |dem |den )?(.+?),? (?:wird|werden) (.*)$", s)
    scope_text, rest = (m.group(1), m.group(2)) if m else ("", s)
    if not m:
        m2 = re.match(r"^(.*?)\s*(?:Die|Das|Der|Den) (?:Angabe|Angaben|Wort|Wörter|Zeichen|Punkt|Komma|Semikolon)\b", s)
        if m2 and m2.group(1):
            scope_text = m2.group(1)
    part_step = None
    ma = re.search(r"(?:\bin )?(?:der )?Angabe (vor|nach) (?:der |dem )?(?:Nummer|Buchstabe|Doppelbuchstabe)\s+\S+",
                   scope_text)
    if ma:
        # text before ("Angabe vor Nummer 1") or after a list belongs to the enclosing unit
        part_step = Step("intro" if ma.group(1) == "vor" else "outro", [])
        scope_text = (scope_text[: ma.start()] + scope_text[ma.end():]).strip(" ,")
    scope = loc_of(scope_text) if scope_text else list(context)
    if scope_text and "Überschrift" in scope_text and not any(st.kind == "heading" for st in scope):
        scope.append(Step("heading", []))
    if part_step:
        scope.append(part_step)

    jeweils = bool(re.search(r"\bjeweils\b", rest))
    n = _quote_count(rest)

    # "In Absatz 1 werden die Sätze 5 bis 8 gestrichen."
    if m and n == 0:
        md = re.match(rf"^(?:der|die|das) ({_NOUN}.*?) (gestrichen|aufgehoben)$", rest)
        if md:
            s = f"{scope_text} {md.group(1)} wird {md.group(2)}"

    # Renumbering: "Der bisherige Absatz 4 wird zu Absatz 5", "Die Absätze 9 bis 11 werden zu den Absätzen 7 bis 9"
    mr = re.match(rf"^(?:Der|Die|Das) (?:bisherigen? )?(.*?) (?:wird|werden) (?:zu|die|der) (?:den |dem |der )?({_NOUN}.*)$", s)
    if mr and n == 0:
        src, dst = loc_of(mr.group(1)), parse_location(mr.group(2))
        if src and dst and src[-1].kind == dst[-1].kind and src[-1].kind not in ("satz", "heading", "toc"):
            dst_keys = dst[-1].keys
            if src[-1].is_range or dst[-1].is_range or len(src[-1].keys) != len(dst_keys):
                return "unsupported", src, {}
            return "renumber", src, {"to": dst_keys}

    if re.search(r"\bersetzt$", rest) and n == 2 and not re.search(r"durch (?:den|die|das) folgenden?\b", rest):
        a, b = [int(x) for x in re.findall(r"⟦(\d+)⟧", rest)]
        return "replace_text", scope, {"old": q[a], "new": q[b], "all": jeweils}
    if re.search(r"\bersetzt$", rest) and n <= 1 and re.search(r"\b(Punkt|Komma|Semikolon|Doppelpunkt) am Ende\b", rest):
        old = _PUNCT[re.search(r"\b(Punkt|Komma|Semikolon|Doppelpunkt) am Ende", rest).group(1)]
        repl = rest.split(" durch ", 1)[1] if " durch " in rest else ""
        new = ""
        for tok in re.finditer(r"⟦(\d+)⟧|\b(Punkt|Komma|Semikolon|Doppelpunkt)\b", repl):
            new += (" " + q[int(tok.group(1))]) if tok.group(1) else _PUNCT[tok.group(2)]
        return "replace_text", scope, {"old": old, "new": new.lstrip() if new.startswith(" ") and not new.strip()[0].isalnum() else new, "at_end": True}
    if re.search(r"\b(gestrichen|aufgehoben)$", rest) and n == 1:
        return "delete_text", scope, {"old": q[int(re.search(r"⟦(\d+)⟧", rest).group(1))], "all": jeweils}
    mi = re.search(r"\b(nach|vor) (?:der|dem|den) [^⟦]*⟦(\d+)⟧.*?⟦(\d+)⟧.*eingefügt$", rest)
    if mi:
        return "insert_text", scope, {"anchor": q[int(mi.group(2))], "new": q[int(mi.group(3))],
                                       "before": mi.group(1) == "vor", "all": jeweils}
    if re.search(r"\bangefügt$", rest) and n == 1 and re.search(r"\b(Angabe|Wort|Wörter|Zeichen)\b", rest):
        return "append_text", scope, {"new": q[0]}

    # --- unit level changes
    m = re.match(rf"^(.*?) (?:wird|werden) durch (?:den|die|das|einen|eine) (?:folgenden?|neuen?) ({_NOUN}.*?) ersetzt$", s)
    if not m:
        m = re.match(r"^(.*?) (?:wird|werden) wie folgt gefasst$", s)
    if m and quotes:
        target = loc_of(m.group(1))
        if not target:
            return "unsupported", scope, {}
        last = target[-1]
        if last.kind == "satz":
            return "replace_sentence", target[:-1], {"n": last.keys, "new": q[-1]}
        if last.kind == "heading":
            return "replace_heading", target[:-1], {"new": q[-1]}
        if last.kind in ("toc", "anlage"):
            return "unsupported", target, {}
        return "replace_units", target, {"quote": quotes[-1]}

    m = re.match(rf"^(Nach|Vor) (.*?) (?:wird|werden) (?:der|die|das) (?:folgenden?|neuen?) ({_NOUN}.*?) eingefügt$", s)
    if m and quotes:
        anchor = loc_of(m.group(2))
        if not anchor:
            return "unsupported", scope, {}
        last = anchor[-1]
        if last.kind == "satz":
            return "insert_sentence", anchor[:-1], {"after": last.keys[-1], "new": q[-1],
                                                     "before": m.group(1) == "Vor"}
        if last.kind in ("toc", "anlage", "heading"):
            return "unsupported", anchor, {}
        return "insert_units", anchor, {"quote": quotes[-1], "before": m.group(1) == "Vor"}

    m = re.match(rf"^(?:(?:Dem|Der|Den) (.*?) (?:wird|werden) (?:der|die|das)? ?(?:folgenden?|neuen?) ({_NOUN}.*?)|"
                 rf"(?:Folgender|Folgende|Folgendes|Die folgenden?|Der folgende|Das folgende) ({_NOUN}.*?) (?:wird|werden)) "
                 rf"(angefügt|vorangestellt)$", s)
    if m and quotes:
        container = loc_of(m.group(1)) if m.group(1) else list(context)
        noun = m.group(2) or m.group(3)
        kind = _unit_kind_of_noun(noun)
        prepend = m.group(4) == "vorangestellt"
        if kind == "satz":
            return "append_sentence", container, {"new": q[-1], "prepend": prepend}
        if kind in ("abs", "nr", "bst", "dbst", "tbst", "par"):
            return "append_units", container, {"quote": quotes[-1], "kind": kind, "prepend": prepend}
        return "unsupported", container, {}

    m = re.match(r"^(.*?) (?:wird|werden) (gestrichen|aufgehoben)$", s)
    if m and n == 0:
        target = loc_of(m.group(1))
        if not target:
            return "unsupported", scope, {}
        last = target[-1]
        if last.kind == "satz":
            return "delete_sentence", target[:-1], {"n": last.keys}
        if last.kind in ("toc", "anlage", "heading"):
            return "unsupported", target, {}
        return "delete_units", target, {"repeal": m.group(2) == "aufgehoben"}

    return "unsupported", scope, {}


@dataclass
class Item:
    marker: str
    level: int
    lines: list[tuple[float, str]]


def split_items(lines: list[tuple[float, str]]) -> list[Item]:
    """Split instruction text into numbered items ("1.", "a)", "aa)", …).

    Markers are only recognized outside of quoted text.
    """
    items: list[Item] = []
    depth = 0
    for x, text in lines:
        stripped = text.strip()
        m = _MARKER.match(stripped) if depth == 0 else None
        if m:
            items.append(Item(m.group(1), marker_level(m.group(1)), [(x, stripped[m.end():])]))
        elif items:
            items[-1].lines.append((x, stripped))
        else:
            items.append(Item("", 0, [(x, stripped)]))
        depth += text.count(OPEN_Q) - text.count(CLOSE_Q)
        depth = max(depth, 0)
    return items


def _fix_letter_levels(items: list[Item]) -> None:
    """'aa)' could be a Doppelbuchstabe level or a plain letter; resolve by context."""
    prev_level = 0
    for it in items:
        if it.marker and not it.marker.endswith(".") and it.level > prev_level + 1:
            # e.g. "b)" directly after "1." is level 2 — fine; but a single letter
            # "aa)"-style marker cannot skip levels.
            it.level = prev_level + 1
        prev_level = it.level


def parse_instructions(lines: list[tuple[float, str]], base: list[Step] | None = None) -> list[Instruction]:
    items = split_items(lines)
    _fix_letter_levels(items)
    out: list[Instruction] = []
    ctx_stack: list[tuple[int, list[Step]]] = [(-1, list(base or []))]
    markers: list[tuple[int, str]] = []
    for it in items:
        while len(ctx_stack) > 1 and ctx_stack[-1][0] >= it.level:
            ctx_stack.pop()
        while markers and markers[-1][0] >= it.level:
            markers.pop()
        if it.marker:
            markers.append((it.level, it.marker))
        context = ctx_stack[-1][1]
        sentence, quotes = extract_quotes(it.lines)
        raw = join_lines([t for _, t in it.lines])
        marker = " ".join(mk for _, mk in markers)
        sentence = sentence.strip()
        # "Absatz 8 wird zu Absatz 6 und Satz 2 wird gestrichen" / "… und wie folgt geändert:"
        mr = _COMPOUND_RENUMBER.match(sentence)
        if mr and "⟦" not in mr.group(1) + mr.group(2):
            src, dst = combine(context, parse_location(mr.group(1))), parse_location(mr.group(2))
            if src and dst and src[-1].kind == dst[-1].kind and len(src[-1].keys) == len(dst[-1].keys):
                out.append(Instruction(raw=raw, marker=marker, path=src, op="renumber", args={"to": dst[-1].keys}))
                context = src[:-1] + [Step(src[-1].kind, dst[-1].keys)]
                sentence = mr.group(3).strip()
                sentence = sentence[:1].upper() + sentence[1:]
                if re.match(r"^Wie folgt geändert", sentence):
                    ctx_stack.append((it.level, context))
                    continue
        if re.search(r"wie folgt geändert:?$", sentence):
            loc_text = re.sub(r"\s*(?:wird|werden) wie folgt geändert:?$", "", sentence)
            ctx_stack.append((it.level, combine(context, parse_location(loc_text))))
            continue
        if not sentence and not quotes:
            continue
        for op, path, args in parse_sentence(sentence, quotes, context):
            out.append(Instruction(raw=raw, marker=marker, path=path, op=op, args=args))
    return out


_COMPOUND_RENUMBER = re.compile(
    r"^(?:(?:Der|Die|Das) )?(?:bisherigen? )?((?:§|Absatz|Absätze|Nummer|Nummern|Buchstabe|Buchstaben|"
    r"Doppelbuchstabe)\s.*?) (?:wird|werden) zu (?:den |dem |der )?((?:§|Absatz|Absätzen|Nummer|Nummern|Buchstabe|"
    r"Buchstaben|Doppelbuchstabe|Doppelbuchstaben)\s[^⟦]*?) und (.+)$"
)


# --------------------------------------------------------------------------
# Articles that amend a law


@dataclass
class Citation:
    year: int | None
    teil: str
    pages: list[str]
    number: str | None

    def work_elis(self) -> list[str]:
        if not self.year:
            return []
        if self.number:
            return [f"eli/bund/bgbl-{self.teil}/{self.year}/{self.number}"]
        return [f"eli/bund/bgbl-{self.teil}/{self.year}/s{p}" for p in self.pages]


@dataclass
class Amendment:
    article: Article
    law_name: str
    citation: Citation | None
    intro: str
    instructions: list[Instruction]


_CIT = re.compile(r"BGBl\.\s*(?:(\d{4})\s+)?(I{1,3})\s+(?:S\.\s*(\d+(?:\s*,\s*\d+)*)|Nr\.\s*(\d+[a-z]?))")
_DATE_YEAR = re.compile(r"vom \d{1,2}\. \w+ (\d{4})")


def parse_citation(text: str) -> Citation | None:
    m = _CIT.search(text)
    if not m:
        return None
    year = int(m.group(1)) if m.group(1) else None
    if year is None:
        dates = _DATE_YEAR.findall(text[: m.start()])
        year = int(dates[-1]) if dates else None
    teil = str(len(m.group(2)))
    pages = [p.strip() for p in (m.group(3) or "").split(",") if p.strip()]
    # The page of the act itself is usually the last one ("S. 3262, 3263")
    pages = list(reversed(pages))
    return Citation(year, teil, pages, m.group(4))


_INTRO_NAME = re.compile(
    r"^(?:Das|Die|Der)\s+(.+?)\s+(?:vom\s+\d|in der Fassung|in der im Bundesgesetzblatt|\(BGBl)"
)
_INLINE_NAME = re.compile(
    r"\b(?:des|der|dem)\s+((?:[A-ZÄÖÜ][\w\-]*(?:gesetz|gesetzes|verordnung|ordnung|ordnungs|vertrag|vertrags|"
    r"abkommens|abkommen|satzung)\w*)|(?:[A-ZÄÖÜ][^,()]*?))\s+(?:vom\s+\d|in der Fassung)"
)


def _nominative(name: str) -> str:
    name = normalize(name)
    for suffix_from, suffix_to in (("gesetzes", "gesetz"), ("buches", "buch"), ("abkommens", "abkommen"),
                                   ("vertrages", "vertrag"), ("vertrags", "vertrag")):
        if name.endswith(suffix_from):
            return name[: -len(suffix_from)] + suffix_to
    return name


def analyze_article(article: Article) -> Amendment | None:
    """Return an Amendment if the article amends an existing law."""
    lines = [(ln.x, ln.text) for ln in article.lines]
    full = join_lines([t for _, t in lines])
    if not re.search(r"(wird|werden) wie folgt geändert|geändert worden ist, (wird|werden)|"
                     r"\b(ersetzt|eingefügt|gestrichen|aufgehoben|angefügt)\b", full):
        return None
    if article.heading and not re.match(r"^(Änderung|Weitere Änderung|Folgeänderung)", article.heading) \
            and not re.search(r"wie folgt geändert", full):
        return None

    # Intro sentence: everything up to "… wird wie folgt geändert:"
    intro_end = None
    acc = []
    depth = 0
    for k, (x, text) in enumerate(lines):
        acc.append(text)
        depth += text.count(OPEN_Q) - text.count(CLOSE_Q)
        if depth == 0 and re.search(r"(?:wird|werden) wie folgt geändert:\s*$", join_lines(acc)):
            intro_end = k + 1
            break
    if intro_end is not None:
        intro = join_lines(acc)
        rest = lines[intro_end:]
        m = _INTRO_NAME.match(intro)
        name = m.group(1) if m else ""
        if not name and article.heading:
            name = re.sub(r"^(Weitere |Folge)?Änderung (des|der|zur)\s+", "", article.heading)
        citation = parse_citation(intro)
        instructions = parse_instructions(rest)
        return Amendment(article, _nominative(name), citation, intro, instructions)

    # Single-sentence amendment: "In § 3 der Foo-Verordnung vom … (BGBl. …), die … geändert
    # worden ist, wird die Angabe „x“ durch die Angabe „y“ ersetzt."
    sentence, _ = extract_quotes(lines)
    m = _INLINE_NAME.search(sentence)
    name = _nominative(m.group(1)) if m else re.sub(r"^(Weitere |Folge)?Änderung (des|der|zur)\s+", "",
                                                    article.heading)
    citation = parse_citation(full)
    # Drop "des Foo-Gesetzes vom … (BGBl. …), das … geändert worden ist," from the sentence
    cut = re.search(r"\s(?:des|der|dem)\s+[^⟦]*?\((?:BGBl|Bundesgesetzblatt)[^⟦]*?\)(?:,\s*(?:das|die|der)\s[^⟦]*?"
                    r"(?:geändert worden ist|bereinigten Fassung)\s*,)?\s*(?=(?:wird|werden)\s)", sentence)
    if cut:
        sentence = sentence[: cut.start()] + " " + sentence[cut.end():]
    _, quotes = extract_quotes(lines)
    raw = join_lines([t for _, t in lines])
    instructions = [Instruction(raw=raw, marker="", path=path, op=op, args=args)
                    for op, path, args in parse_sentence(sentence, quotes, [])]
    return Amendment(article, name, citation, full, instructions)
