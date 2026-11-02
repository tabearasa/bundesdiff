"""When does a publication take effect? Read the dates from its in-force article (spec 002, TL-7).

The article "Inkrafttreten" is short and formulaic:

    (1) Dieses Gesetz tritt vorbehaltlich der Absätze 2 und 3 am 9. Dezember 2027 in Kraft.
    (2) Artikel 5 tritt mit Wirkung vom 27. September 2026 in Kraft.
    (3) Am Tag nach der Verkündung treten in Kraft: 1. Artikel 1 § 3, 2. Artikel 7 und 3. Artikel 8.

Each clause that says "in Kraft" or "außer Kraft" becomes one entry: what takes effect, when, and
the sentence itself. A date is only given when the clause contains exactly one date expression this
module understands – anything else is returned with ``date: None`` and shown as "not recognised with
certainty", never guessed. A clause whose subject cannot be read gets ``kind: "unclear"``.
"""

from __future__ import annotations

import datetime as dt
import re

MONTHS = {m: i for i, m in enumerate(["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
                                      "September", "Oktober", "November", "Dezember"], 1)}
ORDINALS = {"": 1, "ersten": 1, "zweiten": 2, "dritten": 3, "vierten": 4, "fünften": 5, "sechsten": 6,
            "siebten": 7, "achten": 8, "neunten": 9, "zehnten": 10}

_DATE = r"(\d{1,2})\.\s*(" + "|".join(MONTHS) + r")\s+(\d{4})"
_ORD = "|".join(o for o in ORDINALS if o)
# the signature block that follows the last sentence
_END = re.compile(r"Die verfassungsmäßigen Rechte|Das vorstehende Gesetz|Der Bundesrat hat zugestimmt"
                  r"|[A-ZÄÖÜ][\wäöüß-]+, den \d")
_WHOLE = re.compile(r"^(?:Dieses|Diese|Dieser)\s+(?:Gesetz|Verordnung|Bekanntmachung|Anordnung|Satzung)\b")
_KRAFT = re.compile(r"\b(?:in|außer) Kraft\b")
# "in Kraft" of the sentence itself – not of a clause inside it: "…, an dem das Abkommen in Kraft tritt"
_MAIN_KRAFT = re.compile(r"\b(?:in|außer) Kraft\b(?!\s+(?:tritt|treten|getreten|gesetzt)\b)")
_ARTICLES = re.compile(r"^Artikel\s+\d+[a-z]?(?:(?:\s*,\s*|\s+und\s+|\s+bis\s+)\d+[a-z]?)*$")


def parse(text: str, promulgated: str) -> list[dict]:
    """Entries of an in-force article; ``promulgated`` is the issue date (ISO), the "Verkündung"."""
    text = re.sub(r"\s+", " ", text or "").strip()
    end = _END.search(text)
    if end:
        text = text[:end.start()].strip()
    day = _promulgation_day(promulgated)
    entries: list[dict] = []
    before: list[dict] = []  # the entries of the sentence before: what "Sie" and "Gleichzeitig" refer to
    for sentence in _sentences(text):
        if not _KRAFT.search(sentence):
            if _exception(sentence):
                # "Satz 1 gilt nicht für § 3.", "Artikel 3 gilt ab dem 1. Januar 2027.": some part takes
                # effect otherwise – which, and when, is not read: the sentence is shown as it stands
                if not re.match(r"(?:Es|Sie|Er)\b", sentence):  # "Es gilt …" is about the whole act, not a part
                    _qualify(entries, sentence)
                elif entries and entries[-1]["kind"] == "out" and not entries[-1]["whole"]:
                    # "Gleichzeitig tritt das Altgesetz außer Kraft. Es ist bis … weiter anzuwenden."
                    entries[-1]["date"], entries[-1]["retroactive"] = None, False
                entries.append(_unclear(sentence))
            continue
        current: list[dict] = []
        for clause in _clauses(sentence):
            entry = _entry(clause, sentence, day, current or before, entries + current)
            if re.match(r"abweichend|hiervon abweichend", clause, re.I):
                # "Abweichend von Absatz 2 tritt § 4 des Altgesetzes … außer Kraft": that repeal is not whole
                _undate_named(entries + current, sentence)
            if entry.pop("_deviates", False):  # "Abweichend von Absatz 1 tritt Artikel 3 …"
                _not_whole(entries + current)
            current.append(entry)
        entries += current
        before = current
    for e in entries:
        e.pop("_gender", None)
    return entries


def _promulgation_day(promulgated: str) -> dt.date:
    """ "2026-10-27", also "Vom 27. Oktober 2026" as in older stored results."""
    m = re.fullmatch(r"(?:[Vv]om\s+)?" + _DATE, promulgated.strip())
    if m:
        return dt.date(int(m[3]), MONTHS[m[2]], int(m[1]))
    return dt.date.fromisoformat(promulgated[:10])


_PART_START = r"(?:Artikel|Art\.|§§?|Nummer|Nr\.|Absatz|Abs\.|Satz|Anlage|Buchstabe|Teil)"


def _exception(sentence: str) -> bool:
    """A sentence without "in Kraft" that changes when something applies: "Satz 1 gilt nicht für
    § 3", "Artikel 3 gilt ab dem 1. Januar 2027", "Es gilt erst ab …", "… bleibt bis … anwendbar".
    Not a limit of scope without a part or a date: "Sie gilt nur für Anträge, die …"."""
    if not re.search(r"\b(?:gilt|gelten|anzuwenden|anwendbar|bleibt|bleiben)\b", sentence):
        return False
    if re.search(r"\bnicht mehr anzuwenden\b|\bentsprechend\b|\bunberührt\b", sentence):
        return False  # old rules no longer applied, "gilt entsprechend": no other time for a part
    timing = re.search(r"\b(?:ab|bis|erst|erstmals|weiter|nicht für|mit Wirkung vom)\b", sentence)
    return bool(timing and (re.search(_PART_START + r"\s+\d", sentence) or re.search(_DATE, sentence)
                            or re.match(r"(?:Es|Sie|Er)\b", sentence)))


def _qualify(entries: list[dict], sentence: str) -> None:
    """An exception follows. If it names a repealed law ("§ 4 des Altgesetzes ist … weiter
    anzuwenden"), only that repeal is uncertain. If it can only be about the coming into force of
    the act, that is "the rest of the act"; if it could also be about an expiry, none is certain."""
    if _undate_named(entries, sentence):
        return
    whole_in = [e for e in entries if e["whole"] and e["kind"] == "in"]
    others = [e for e in entries if e["kind"] == "out"]
    if not others:
        for e in whole_in:
            e["rest"] = True
        return
    for e in whole_in + others:
        e["date"], e["retroactive"] = None, False


def _undate_named(entries: list[dict], sentence: str) -> bool:
    """A repealed law named again in an exception: when it goes is no longer certain."""
    named = [e for e in entries if e["kind"] == "out" and e["subject"]
             and any(n and n in sentence for n in e["subject"].split(", "))]
    for e in named:
        e["date"], e["retroactive"] = None, False
    return bool(named)


def _not_whole(entries: list[dict]) -> None:
    """The act takes effect "in the rest" only: some part takes effect at another time."""
    for e in entries:
        if e["whole"] and e["kind"] == "in":
            e["rest"] = True


def _entry(clause: str, sentence: str, day: dt.date, context: list[dict], earlier: list[dict]) -> dict:
    """One entry for a clause. ``context``: the entries of the clauses before it in the sentence,
    else those of the sentence before – what a clause without its own subject or date refers to.

    Understood, besides "X tritt am … in Kraft":
    - "… in Kraft und mit Ablauf des … außer Kraft": the second clause has the same subject;
    - "…; Artikel 2 tritt am … in Kraft", "… und Artikel 6 am … in Kraft": a subject of its own;
    - "Am …/Gleichzeitig/Im Übrigen tritt X … in Kraft": the subject follows the verb; "Gleichzeitig"
      takes the date of the clause before, if there is exactly one;
    - "Sie/Es/Er tritt …": the one entry before (``earlier``) whose subject has that gender –
      "Sie" a Verordnung, "Es" a Gesetz, "Er" an Artikel; none or several: unclear.
    Anything else is "unclear": shown with its wording, nothing named, no date.
    """
    kinds = {m[0].split()[0] for m in _MAIN_KRAFT.finditer(clause)}
    if len(kinds) != 1:
        return _unclear(sentence)
    out = kinds == {"außer"}
    shares = re.match(r"(?:und|sowie)\s+(?:am|mit|zum|an)\b", clause)
    body = re.sub(r"^(?:und|sowie)\s+", "", clause)
    dates = _dates(body, day)
    if len(dates) > 1:  # "Artikel 1 tritt am …, Artikel 2 am … in Kraft": which date is whose?
        return _unclear(sentence)
    certain = len(dates) == 1 and dates[0][0] is not None
    date, retroactive = (dates[0][0].isoformat(), dates[0][1]) if certain else (None, False)
    if certain and dates[0][0] < day and not retroactive:
        return _unclear(sentence)  # before the publication, without "mit Wirkung vom": misread or a title
    only = context[0] if len(context) == 1 and context[0]["kind"] != "unclear" else None
    rest, adverb = False, ""
    if shares:
        if not context or context[-1]["kind"] == "unclear":
            return _unclear(sentence)
        ref = context[-1]
        whole, subject, articles = ref["whole"], ref["subject"], ref["articles"]
    else:
        found = _subject(body, elliptic=bool(context) and clause != body)
        if found is None:
            return _unclear(sentence)
        subject, adverb = found
        if subject.lower() in _PRONOUNS:  # refers to what was named before, by its gender and number
            plural = bool(re.match(r"\S+\s+treten\b", body))  # the verb of the pronoun, not of a clause after it
            gender = "p" if plural else _PRONOUNS[subject.lower()]
            if plural and subject.lower() != "sie":
                return _unclear(sentence)
            referents = {(e["whole"], e["subject"]): e for e in earlier
                         if e["kind"] != "unclear" and e.get("_gender") == gender}
            if len(referents) != 1:
                return _unclear(sentence)
            last = max(i for i, e in enumerate(earlier) if (e["whole"], e["subject"]) in referents)
            if any(e["kind"] == "unclear" for e in earlier[last + 1:]):
                return _unclear(sentence)  # something not understood was named after it: it may be meant
            ref = next(iter(referents.values()))
            whole, subject, articles = ref["whole"], ref["subject"], ref["articles"]
        else:
            whole = bool(_WHOLE.match(subject))
            rest = whole and bool(re.search(r"vorbehaltlich|soweit|mit Ausnahme|im übrigen|abweichend", clause, re.I))
            subject = None if whole else subject
            articles = _article_numbers(subject) if subject else []
        if adverb in ("gleichzeitig", "zugleich") and re.search(r"\bzum\s+\d", body):
            return _unclear(sentence)  # "… zur Bestimmung des Rentenwerts zum 1. Juli 2024": title or time?
        if adverb in ("gleichzeitig", "zugleich") and not dates:
            if only is None or only["date"] is None:
                date = None
            else:
                date, retroactive = only["date"], only["retroactive"]
    return {"date": date, "retroactive": retroactive, "kind": "out" if out else "in", "whole": whole,
            "rest": rest, "subject": subject, "articles": articles, "sentence": sentence,
            "_gender": _gender(clause if whole else subject or ""),
            "_deviates": not shares and adverb == "abweichend"}


_PRONOUNS = {"sie": "f", "es": "n", "er": "m"}


def _gender(subject: str) -> str:
    """Grammatical gender of what an entry names – what "Sie", "Es" or "Er" can refer to."""
    whole = re.search(r"\b(?:Dieses|Diese|Dieser|dieses|diese|dieser)\s+(Gesetz|Verordnung|Bekanntmachung|Anordnung|Satzung)\b",
                      subject)
    word = whole[1] if whole else (subject.split() or [""])[0]
    if not whole and (re.search(r",\s|\s(?:und|sowie|bis)\s", subject) or word in ("§§", "Anlagen")):
        return "p"  # several: "Sie treten …"
    if not whole and _is_part(subject):  # "Artikel 2 Nummer 3": "Nummer" is the head – "sie"
        word = [t for t in subject.split() if t in _PART_WORDS and t not in ("und", "bis", "sowie")][-1]
    if word in ("Kapitel",):
        return "n"
    if word in ("Artikel", "Art.", "§", "Absatz", "Abs.", "Teil", "Abschnitt", "Satz", "S.", "Buchstabe",
                "Buchst.", "Doppelbuchstabe", "Doppelbuchst."):
        return "m"
    if word in ("Anlage", "Nummer", "Nr.") or re.search(r"(?:verordnung|ordnung|bekanntmachung|satzung|richtlinie)$", word, re.I):
        return "f"
    if re.search(r"(?:gesetz|abkommen|übereinkommen|statut)$", word, re.I):
        return "n"
    if re.search(r"(?:vertrag|erlass)$", word, re.I):
        return "m"
    return ""


def _unclear(sentence: str) -> dict:
    """Something takes effect, but what and when could not be read with certainty (TL-7)."""
    return {"date": None, "retroactive": False, "kind": "unclear", "whole": False, "rest": False,
            "subject": None, "articles": [], "sentence": sentence}


def _clauses(sentence: str) -> list[str]:
    """The parts of a sentence that each say "in Kraft" or "außer Kraft" once.

    Split at ";" – unless a part would then say neither – and after every "in Kraft"/"außer Kraft"
    that another one follows, but never before the list after "treten in Kraft:".
    """
    pieces = _outside_parentheses_split(sentence, ";")
    if any(not _MAIN_KRAFT.search(p) for p in pieces):
        pieces = [sentence]
    clauses = []
    for piece in pieces:
        ends = [m.end() for m in _MAIN_KRAFT.finditer(piece) if not piece[m.end():].lstrip().startswith(":")]
        start = 0
        for end in ends[:-1]:
            clauses.append(piece[start:end])
            start = end
        clauses.append(piece[start:])
    return [c.strip(" ,.;") for c in clauses if c.strip(" ,.;")]


def _outside_parentheses_split(text: str, sep: str) -> list[str]:
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")")
        if ch == sep and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


# words before a full stop that do not end a sentence: "BGBl. I S. 1", "Abs. 2", "z. B."
_ABBREVIATIONS = {"BGBl", "Abs", "Nr", "Art", "Buchst", "Doppelbuchst", "Anl", "Bek", "Ziff", "vgl", "bzw",
                  "ggf", "geänd", "zul", "usw", "Gesetzbl", "Verordnungsbl", "ABl"}


def _sentences(text: str) -> list[str]:
    """Paragraphs "(1) …" and the sentences in them.

    A sentence ends at a full stop followed by a capital or "§" – not inside parentheses
    ("(RGBl. I S. 3)"), not after an abbreviation or a single letter ("z. B.", "S. 1"), not after the
    day of a date ("1. Januar") or the number of a list ("…, 2. das Altgesetz").
    """
    parts = [p.strip() for p in re.split(r"\(\d+[a-z]?\)\s*", text) if p.strip()]
    sentences = []
    for part in parts:
        start = 0
        for m in re.finditer(r"(?<=[\wäöüß)])\.\s+(?=[A-ZÄÖÜ§])", part):
            head = part[start:m.start()]
            if head.count("(") > head.count(")"):
                continue
            word = re.search(r"([\wäöüß]+)\)?$", head)
            if not word or word[1] in _ABBREVIATIONS or (len(word[1]) == 1 and not word[1].isdigit()):
                continue
            # after a number only when it is a year or the number of a part ("… Artikel 2 und 3.") –
            # not the day of a date, not "die 2. Durchführungsverordnung", not a list "…: 1. Artikel 7"
            in_list = re.search(r"(?:in|außer) Kraft\s*:", head)
            if word[1].isdigit() and in_list and re.match(r"[^.,;:]*?\b(?:tritt|treten)\b", part[m.end():]):
                pass  # the list ends, a sentence with a verb of its own follows: "… 2. Artikel 2. Artikel 3 tritt …"
            elif word[1].isdigit() and not (
                    (len(word[1]) == 4 and not re.search(r"(?:in|außer) Kraft\s*:", head))
                    or (re.search(_PART_START + r"\s+\d+[a-z]?(?:\s*(?:,|und|bis|sowie)\s*\d+[a-z]?)*$", head)
                        and not re.search(r"(?:in|außer) Kraft\s*:", head))):
                continue
            sentences.append(part[start:m.start() + 1].strip())
            start = m.end()
        sentences.append(part[start:].strip())
    return [s for s in sentences if s]



def _dates(sentence: str, promulgated: dt.date) -> list[tuple[dt.date | None, bool]]:
    """Every date expression in the sentence, with True if it is retroactive ("mit Wirkung vom").

    A date that does not stand right before "in Kraft" (or open the sentence, "Am Tag nach der
    Verkündung treten in Kraft: …") belongs to something else – "spätestens jedoch am 1. September
    2034" after an event – and makes the sentence unclear: it is returned as ``None``.
    """
    found: list[tuple[dt.date | None, bool]] = []

    def add(m: re.Match, day: dt.date, retroactive: bool = False) -> None:
        governs = m.start() == 0 or re.match(r"\s+(?:in|außer) Kraft\b", sentence[m.end():])
        found.append((day if governs else None, retroactive))

    for m in re.finditer(r"([Mm]it Wirkung vom|[Aa]m|[Zz]um)\s+" + _DATE, sentence):
        try:
            day = dt.date(int(m[4]), MONTHS[m[3]], int(m[2]))
        except ValueError:  # "30. Februar": a misprint – not a date to rely on
            found.append((None, False))
            continue
        add(m, day, m[1].lower().startswith("mit"))
    for m in re.finditer(rf"[Aa]m\s+(?:({_ORD})\s+)?Tage? nach (?:der|ihrer|seiner) Verkündung"
                         r"(?:\s+(?:dieses Gesetzes|dieser Verordnung))?", sentence):
        add(m, promulgated + dt.timedelta(days=ORDINALS[m[1] or ""]))
    for m in re.finditer(rf"[Aa]m ersten Tage? des (?:({_ORD}) )?auf (?:die|ihre|seine) Verkündung folgenden "
                         r"(Kalendermonats|Monats|Kalendervierteljahres|Quartals)", sentence):
        months = 1 if "monats" in m[2].lower() else 3
        add(m, _first_of_following(promulgated, ORDINALS[m[1] or ""], months))
    return found


def _first_of_following(day: dt.date, n: int, months: int) -> dt.date:
    """First day of the n-th following month (months=1) or quarter (months=3)."""
    index = day.year * 12 + day.month - 1
    if months == 3:
        index -= index % 3
    index += n * months
    return dt.date(index // 12, index % 12 + 1, 1)


# where the name ends and the time begins – "zum Koch", "am Bundesgerichtshof" belong to a title
_TIME = (r"\s+(?:am\s+(?:\d|Tage?\b|ersten\b|zweiten\b|dritten\b)|mit Wirkung\b|mit Ablauf\b"
         r"|mit dem (?:Tag|Inkrafttreten|Zeitpunkt)\b|zum\s+(?:\d|Zeitpunkt\b|Datum\b)|zu dem (?:Tag|Zeitpunkt)\b"
         r"|an dem Tag\b|in Kraft\b|außer Kraft\b)")
# what may stand before "tritt" when the subject follows the verb – the whole of it, nothing else
_ADVERB = re.compile(r"(im übrigen|gleichzeitig|zugleich|ferner|außerdem|ebenso)"
                     r"|(darüber hinaus)"
                     r"|(abweichend) von (?:den |dem )?(?:absatz|absätzen|satz|sätzen|artikel|§§?)\s*[\w ,]+"
                     r"|(abweichend) hiervon|hiervon (abweichend)|(vorbehaltlich)\s+[^,]+|(soweit)\s+[^,]+,"
                     r"|(am|mit|zum)\s+.+", re.I)


def _subject(clause: str, elliptic: bool = False) -> tuple[str, str] | None:
    """What takes effect, and the adverb the clause opens with ("" if none); None if unclear.

    "Am Tag nach der Verkündung treten in Kraft: 1. Artikel 1 § 3, 2. Artikel 7" names a list;
    "Gleichzeitig tritt das Altgesetz außer Kraft" names it after the verb; "und Artikel 6 am …
    in Kraft" (``elliptic``, after another clause) names it without a verb.
    """
    m = re.match(r"(.*?)\s*\b(?:tritt|treten)\b\s*(.*)$", clause)
    if not m:
        if not elliptic:
            return None
        e = re.match(r"(.+?)" + _TIME, clause)
        name = _names(e[1]) if e and not _ADVERB.fullmatch(e[1]) else None
        return (name, "") if name else None
    before, after = m[1], m[2]
    # "treten in Kraft: 1. …", also "treten am Tag nach der Verkündung in Kraft: 1. …"
    listed = re.match(r"(?:(?:am|mit|zum)\b[^:]*?\s)?(?:in|außer) Kraft\s*:\s*(.*)$", after)
    adverb = _ADVERB.fullmatch(before)
    if listed:
        if before and not adverb and before not in ("Es", "Folgende Vorschriften"):
            return None
        items = re.sub(r"(?:^|,|\bund|\bsowie)\s*\d+\.\s+", "\x00", listed[1]).split("\x00")
        names = [_names(i.strip(" ,.")) for i in items if i.strip(" ,.")]
        if not names or None in names:
            return None
        return ", ".join(names), _adverb_word(adverb)
    if adverb:
        a = re.match(r"(.+?)" + _TIME, " " + after)
        name = _names(a[1]) if a else None
        return (name, _adverb_word(adverb)) if name else None
    if not before:
        return None
    if before.lower() == "es":  # "Es tritt außer Kraft das Altgesetz …": a placeholder, the name follows
        named = re.search(r"\b(?:in|außer) Kraft\s+(.+)$", after)
        if named:
            name = _names(named[1])
            return (name, "") if name else None
        if re.match(r"treten\b", clause[len(before):].strip()):
            return None
    if before.lower() in _PRONOUNS:  # resolved by the caller from what was named before
        return before, ""
    name = _names(before)
    return (name, "") if name else None


def _adverb_word(adverb: re.Match | None) -> str:
    """ "gleichzeitig", "im übrigen", "abweichend" … – the key word of the opening phrase."""
    if not adverb:
        return ""
    return next(g for g in adverb.groups() if g).lower()


# a part of the act: "Artikel 1 Nummer 10 Buchstabe b und Nummer 13", "§ 5 Abs. 2 S. 1", "Anlage 1 Teil A"
_PART_WORDS = {"Artikel", "Art.", "§", "§§", "Anlage", "Anlagen", "Nummer", "Nummern", "Nr.", "Buchstabe",
               "Buchstaben", "Buchst.", "Doppelbuchstabe", "Doppelbuchst.", "Absatz", "Absätze", "Abs.", "Satz",
               "Sätze", "S.", "Teil", "Abschnitt", "und", "bis", "sowie"}
_LAW_NOUN = r"(?:gesetz|verordnung|ordnung|abkommen|übereinkommen|bekanntmachung|satzung|vertrag|richtlinie|erlass|statut)"
# the first word ends in the law noun ("Bundespolizeigesetz", "Verordnung"); more words only as
# the rest of a title ("Verordnung über die Berufsausbildung …"), not "Mustergesetz hingegen"
_LAW = re.compile(r"(?:(?:Erste|Zweite|Dritte|Vierte|Fünfte|Sechste|Siebte|Achte|Neunte|Zehnte|\d+\.)\s+)?"
                  rf"(?:[A-ZÄÖÜ][\wäöüß-]*{_LAW_NOUN}|{_LAW_NOUN.title()})"
                  r"(?:\s+(?:zur|zum|zu|über|für|gegen|des|der|betreffend)\s+[\wäöüßÄÖÜ/-]+(?:\s+[\wäöüßÄÖÜ/-]+)*)?")


def _is_part(item: str) -> bool:
    tokens = item.replace(",", " , ").split()
    return bool(tokens) and tokens[0] in {"Artikel", "Art.", "§", "§§", "Anlage", "Anlagen"} and all(
        t in _PART_WORDS or t == "," or re.fullmatch(r"\d+[a-z]?|[a-z]{1,2}|[A-Z]|[IVX]+", t) for t in tokens)


def _names(subject: str) -> str | None:
    """Only the names: "Mustergesetz, Musterverordnung" for "das Mustergesetz vom 1. Januar 2000
    (BGBl. I S. 1) und die Musterverordnung vom …"; "Diese Verordnung" stays as it is."""
    subject = subject.strip(" ,.")
    if not subject:
        return None
    subject = subject[0].upper() + subject[1:]
    if _WHOLE.match(subject):
        return subject if re.fullmatch(_WHOLE.pattern + r"(?:\s+vorbehaltlich\b.*)?", subject) else None
    subject = re.sub(r"\s*\([^()]*\)", "", subject)  # citations: "(BGBl. I S. 2978, 2979)"
    # "…, das zuletzt durch Artikel 8 des Gesetzes vom … geändert worden ist,"
    subject = re.sub(r",\s+(?:das|die|der)\s+[^,]*?\bworden ist\b,?", "", subject)
    names = []
    for item in re.split(r"\s*,\s*(?=(?:das|die|der)\s)|\s+(?:und|sowie)\s+(?=(?:das|die|der)\s)", subject):
        item = re.sub(r"\s+(?:dieses Gesetzes|dieser Verordnung)$", "", item.strip())
        item = re.split(r"\s+(?:vom|in der Fassung|i\.\s*d\.\s*F\.)(?:\s+|$)", item)[0]
        item = re.sub(r"^(?:[Dd]as|[Dd]ie|[Dd]er)\s+", "", item).strip(" ,.")
        # only what is recognised for certain: a part of the act or the name of a law – not a bare
        # "Gesetz" (which one?), not "Abweichend von Absatz 1" or "Artikel 3 hingegen"
        bare = re.fullmatch(r"(?:\d+\.\s+)?" + _LAW_NOUN.title(), item)  # "Gesetz", "Abkommen": which one?
        cut = re.search(r"\b(?:zu dem|zum|über das|über den|über die)\s+\S*(?:Abkommen|Vertrag|Übereinkommen|Protokoll)$",
                        item)  # "Gesetz zu dem Abkommen" – the rest of the title was cut at "vom"
        if not (_is_part(item) or (_LAW.fullmatch(item) and not bare and not cut)):
            return None
        names.append(item)
    return ", ".join(names)



def _article_numbers(subject: str) -> list[str]:
    """["1", "2", "3", "6"] for "Artikel 1 bis 3 und 6"; [] if only parts of articles are named.

    A range with a lettered article ("Artikel 2a bis 4") cannot be counted out – which of 3, 3a,
    3b … exist is not known here – so it gives [] as well and the subject is shown as written.
    """
    if not _ARTICLES.match(subject):
        return []
    numbers: list[str] = []
    for m in re.finditer(r"(\d+[a-z]?)(?:\s+bis\s+(\d+[a-z]?))?", subject[len("Artikel"):]):
        if m[2] and not (m[1].isdigit() and m[2].isdigit()):
            return []
        if m[2]:
            numbers += [str(n) for n in range(int(m[1]), int(m[2]) + 1)]
        else:
            numbers.append(m[1])
    return numbers
