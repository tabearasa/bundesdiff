"""Structural model of legal text: a tree of units (§, Absatz, Nummer, …).

Each unit holds an ordered list of ``parts`` — plain text strings and child
units — so that text before a list ("Die Steuer beträgt:"), the list items
and text after the list ("beziehen. Verweist …") keep their order.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Text normalization


def normalize(text: str) -> str:
    text = text.replace("­", "").replace(" ", " ").replace(" ", " ")
    text = text.replace(" ", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def comparable(text: str) -> str:
    """Normalization used for equality checks (ignores spacing and quote style)."""
    text = normalize(text)
    text = re.sub(r"[„“”\"']", '"', text)
    text = text.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", text)


def join_lines(lines: list[str]) -> str:
    """Join wrapped PDF lines, undoing hyphenation."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif out.endswith("­"):
            out = out[:-1] + ln
        elif out.endswith("-") and not out.endswith(" -") and ln[:1].isupper():
            # "Bundes-" + "Immissionsschutzgesetz" -> compound word with hyphen
            out = out + ln
        else:
            out = out + " " + ln
    return normalize(out)


# --------------------------------------------------------------------------
# Unit labels

LEVELS = {"law": 0, "par": 1, "abs": 2, "nr": 3, "bst": 4, "dbst": 5, "tbst": 6}

# Parts of a law above the § ("Gliederungseinheiten" in the Handbuch der Rechtsförmlichkeit). Older
# laws such as the Baugesetzbuch count them in words ("Achter Teil"), newer ones in numbers ("Teil 8").
STRUCTURE_UNITS = r"(?:Buch|Teil|Kapitel|Unterkapitel|Abschnitt|Unterabschnitt|Titel|Untertitel)"
ORDINAL = (r"(?:Erst|Zweit|Dritt|Viert|Fünft|Sechst|Siebent|Siebt|Acht|Neunt|Zehnt|Elft|Zwölft|"
           r"(?:Drei|Vier|Fünf|Sech|Sieb|Acht|Neun)zehnt|"
           r"(?:(?:Ein|Zwei|Drei|Vier|Fünf|Sechs|Sieben|Acht|Neun)und(?:zwanzig|dreißig|vierzig|fünfzig)|"
           r"Zwanzig|Dreißig|Vierzig|Fünfzig)st)(?:er|es|en|e)")
_STRUCTURE_LINE = re.compile(rf"^(?:{ORDINAL}\s+{STRUCTURE_UNITS}|{STRUCTURE_UNITS}\s+(?:\d+[a-z]*|[IVXLC]+))$")
_PAR_LINE = re.compile(r"^(§\s*\d+[a-z]*|Artikel\s+\d+[a-z]*)$")

LABEL_RES = [
    ("abs", re.compile(r"^\((\d+[a-z]*)\)")),
    ("nr", re.compile(r"^(\d+[a-z]*)\.(?=\s|$)")),
    ("tbst", re.compile(r"^([a-z])\1\1\)(?=\s|$)")),
    ("dbst", re.compile(r"^([a-z])\1\)(?=\s|$)")),
    ("bst", re.compile(r"^([a-z])\)(?=\s|$)")),
]


def parse_label(text: str) -> tuple[str, str, str] | None:
    """Recognize a unit label at the start of ``text``.

    Returns (kind, key, rest) – e.g. "(3a) Foo" -> ("abs", "3a", "Foo").
    """
    for kind, rx in LABEL_RES:
        m = rx.match(text)
        if m:
            key = m.group(0).strip("().") if kind in ("tbst", "dbst") else m.group(1)
            return kind, key.rstrip(")"), text[m.end():].strip()
    return None


def label_kind(label: str) -> tuple[str, str] | None:
    parsed = parse_label(label.strip())
    return (parsed[0], parsed[1]) if parsed else None


def par_key(label: str) -> str:
    """'§ 38' -> '§38', 'Artikel 3a' / 'Art 3a' -> 'art3a'."""
    label = normalize(label)
    m = re.match(r"^§\s*(\d+[a-z]*)", label)
    if m:
        return "§" + m.group(1)
    m = re.match(r"^Art(?:ikel|\.)?\s*(\d+[a-z]*)", label)
    if m:
        return "art" + m.group(1)
    m = re.match(r"^Anlage\s*(\d*[a-z]*)", label)
    if m:
        return "anlage" + m.group(1)
    return label.lower().replace(" ", "")


# --------------------------------------------------------------------------
# Tree


@dataclass
class Node:
    kind: str  # law | par | abs | nr | bst | dbst | tbst | block
    label: str = ""
    heading: str = ""
    parts: list = field(default_factory=list)  # str | Node
    # a new §: headings of the new parts of the law that begin with it, outer first (spec 016 ENT-18)
    part_headings: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        if self.kind == "par":
            return par_key(self.label)
        parsed = label_kind(self.label)
        return parsed[1] if parsed else ""

    @property
    def children(self) -> list[Node]:
        return [p for p in self.parts if isinstance(p, Node)]

    def texts(self) -> list[str]:
        return [p for p in self.parts if isinstance(p, str)]

    def clone(self) -> Node:
        return copy.deepcopy(self)

    def full_text(self) -> str:
        bits = [self.label, self.heading]
        for p in self.parts:
            bits.append(p if isinstance(p, str) else p.full_text())
        return normalize(" ".join(b for b in bits if b))

    def body_text(self) -> str:
        """Text without own label/heading (used to compare replaced units)."""
        bits = []
        for p in self.parts:
            bits.append(p if isinstance(p, str) else p.full_text())
        return normalize(" ".join(bits))

    def find_child(self, kind: str, key: str) -> tuple[Node, int] | None:
        """Find a direct (or transparently nested) child unit by kind and key."""
        for i, p in enumerate(self.parts):
            if not isinstance(p, Node):
                continue
            if p.kind == kind and p.key == key:
                return p, i
            if p.kind == "block" or (p.kind == "abs" and not p.label):
                found = p.find_child(kind, key)
                if found:
                    return found
        return None

    def container_for(self, kind: str) -> Node:
        """The node whose parts hold children of ``kind`` (looks through unlabeled wrappers)."""
        if any(isinstance(p, Node) and p.kind == kind for p in self.parts):
            return self
        for p in self.parts:
            if isinstance(p, Node) and (p.kind == "block" or (p.kind == "abs" and not p.label)):
                inner = p.container_for(kind)
                if inner is not p or any(isinstance(c, Node) and c.kind == kind for c in p.parts):
                    return inner
        return self

    def is_repealed(self) -> bool:
        body = self.body_text().strip("() .")
        return body in ("", "weggefallen", "aufgehoben")


def render_lines(node: Node, depth: int = 0) -> list[tuple[int, str]]:
    """Flatten a unit into indented display lines."""
    out: list[tuple[int, str]] = []
    if node.kind == "par":
        head = normalize(f"{node.label} {node.heading}")
        if head:
            out.append((depth, head))
        child_depth = depth
    elif node.kind == "law":
        child_depth = depth
    else:
        child_depth = depth + (1 if node.kind != "block" else 0)
    pending_label = node.label if node.kind not in ("par", "law", "block") else ""
    if node.kind not in ("par", "law", "block") and node.heading:
        out.append((depth, normalize(f"{pending_label} {node.heading}")))
        pending_label = ""
    for p in node.parts:
        if isinstance(p, str):
            text = normalize(f"{pending_label} {p}") if pending_label else normalize(p)
            pending_label = ""
            if text:
                out.append((depth, text))
        else:
            if pending_label:
                out.append((depth, pending_label))
                pending_label = ""
            out.extend(render_lines(p, child_depth))
    if pending_label:
        out.append((depth, pending_label))
    return out


# --------------------------------------------------------------------------
# Sentences

_ABBREV = set(
    "Nr Abs Art S Bd Buchst bzw ca d ggf gem i Kap lit o u usw v vgl z zB Ziff BGBl ABl Anl "
    "Bek Dr Prof Rn Rdnr St Str Tz Abschn Unterabs Var Alt Hs Halbs Ges Verf".split()
)
_SENT_END = re.compile(r"[.?!](?=\s+[„\"(]?[A-ZÄÖÜ§])")
# "… nach Satz 1. Bei …", "… Absatz 3 Satz 4. Sie …", "… die Sätze 1 und 2. Danach …": the number
# belongs to a reference, so the full stop ends the sentence (unlike "am 1. Januar", "die 32. Verordnung")
_REFERENCE_NUMBER = re.compile(
    r"(?:Satz|Satzes|Sätzen?|Absatz|Absatzes|Absätzen?|Nummern?|Artikels?|Halbsatz|§§?)\s+"
    r"(?:\d+[a-z]*\s*(?:,|und|bis|oder)\s*)*$")
_AFTER_ORDINAL = re.compile(r"\s+(?:Halbsatz|Halbsatzes|Alternative|Variante|Teilsatz|Spiegelstrich)\b")


def split_sentences(text: str) -> list[str]:
    """Heuristic split into sentences ("Sätze") as counted in German law."""
    text = normalize(text)
    if not text:
        return []
    out, start = [], 0
    for m in _SENT_END.finditer(text):
        word = re.search(r"(\S+)$", text[start:m.start()])
        prev = word.group(1) if word else ""
        if prev in _ABBREV or re.fullmatch(r"[a-z]", prev):
            continue  # "Nr. 5", "z. B."
        if prev.isdigit() and not (_REFERENCE_NUMBER.search(text[start:m.start() - len(prev)])
                                   and not _AFTER_ORDINAL.match(text, m.end())):
            continue  # "1. Januar", "32. Verordnung", "Satz 1 1. Halbsatz"
        out.append(text[start:m.end()].strip())
        start = m.end()
    rest = text[start:].strip()
    if rest:
        out.append(rest)
    return out


# --------------------------------------------------------------------------
# Building trees from PDF lines (quoted replacement text)


_MONTHS = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
           "November", "Dezember")


def _can_start_unit(prev: str, line: str, kind: str) -> bool:
    """Is a label at the start of ``line`` a real unit label (not a wrapped "31. Dezember")?"""
    if kind == "nr" and re.match(r"^\d+\.\s+(" + "|".join(_MONTHS) + r")\b", line):
        return False
    if parse_label(line)[1] in ("1", "a", "aa", "aaa"):
        return True  # a list starts – it may follow any word ("…, wenn")
    prev = prev.strip()
    if not prev or parse_label(prev) and not parse_label(prev)[2]:
        return True  # first line, or previous line is a bare label
    if re.match(r"^§\s*\d+[a-z]*$", prev):
        return True
    return bool(re.search(r"([:;,.]|\bund|\boder|\bsowie|\bbis)$", prev)) or prev.endswith("“")


def tree_from_lines(lines: list[tuple[float, str]], root_kind: str = "block") -> Node:
    """Build a unit tree from quoted text lines given as (x, text).

    List items are recognized by their label; continuation lines are
    attached to the open item when they are indented beyond the item label,
    otherwise to the enclosing unit (text after a list).
    """
    root = Node(root_kind)
    # stack entries: (node, label_x, pending_lines)
    stack: list[list] = [[root, -1.0, []]]

    def flush(entry):
        if entry[2]:
            entry[0].parts.append(join_lines(entry[2]))
            entry[2] = []

    def flush_all():
        for e in stack:
            flush(e)

    part_headings: list[str] = []  # "Achter Teil – …" waiting for the § that begins the part

    i = 0
    while i < len(lines):
        x, text = lines[i]
        text = text.strip()
        i += 1
        if not text:
            continue
        if _STRUCTURE_LINE.match(text):
            # the heading of a new part of the law: its title lines, then a § or a part inside it
            j = i
            while j < len(lines) and j - i < 4:
                nxt = lines[j][1].strip()
                if _PAR_LINE.match(nxt) or _STRUCTURE_LINE.match(nxt) or parse_label(nxt):
                    break
                j += 1
            nxt = lines[j][1].strip() if j < len(lines) else ""
            if _PAR_LINE.match(nxt) or _STRUCTURE_LINE.match(nxt):
                flush_all()
                del stack[1:]
                title = join_lines([t for _, t in lines[i:j]])
                part_headings.append(f"{normalize(text)} – {normalize(title)}" if title else normalize(text))
                i = j
                continue
        par = _PAR_LINE.match(text)
        if par:
            flush_all()
            del stack[1:]
            heading = ""
            if i < len(lines) and not parse_label(lines[i][1].strip()):
                heading = lines[i][1].strip()
                i += 1
            node = Node("par", normalize(par.group(1)), normalize(heading))
            node.part_headings, part_headings = part_headings, []
            root.parts.append(node)
            stack.append([node, x, []])
            continue
        parsed = parse_label(text)
        if parsed and not _can_start_unit(lines[i - 2][1] if i >= 2 else "", text, parsed[0]):
            parsed = None
        if parsed:
            kind, key, rest = parsed
            flush_all()
            # close units at same or deeper level
            while len(stack) > 1 and LEVELS.get(stack[-1][0].kind, 9) >= LEVELS[kind]:
                stack.pop()
            label = text[: len(text) - len(rest)].strip() if rest else text
            node = Node(kind, label)
            stack[-1][0].parts.append(node)
            stack.append([node, x, [rest] if rest else []])
            continue
        # continuation or text after a list
        while len(stack) > 1 and stack[-1][0].kind in ("nr", "bst", "dbst", "tbst") and x <= stack[-1][1] + 3:
            flush(stack[-1])
            stack.pop()
        stack[-1][2].append(text)
    flush_all()
    return root
