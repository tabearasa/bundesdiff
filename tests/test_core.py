"""Offline tests for instruction parsing, application and diffing."""

import pytest

from bundesdiff.amendments import parse_citation, parse_instructions, parse_location
from bundesdiff.diffing import diff_units, word_diff
from bundesdiff.engine import Snapshots, check, find_par, forward, reverse, run
from bundesdiff.model import Node, render_lines, split_sentences, tree_from_lines


def law() -> Node:
    return Node("law", parts=[
        Node("par", "§ 38", "Übergangsvorschriften", parts=[
            Node("abs", "(3)", parts=["Steuerzeichen können zwei Monate vor Inkrafttreten bezogen werden."]),
            Node("abs", "(4)", parts=["Die Steuer, die durch Steuerzeichen nach Absatz 3 entrichtet wird, entsteht. "
                                      "Satz 1 gilt entsprechend."]),
            Node("abs", "(5)", parts=["(weggefallen)"]),
        ]),
    ])


def lines(text: str) -> list[tuple[float, str]]:
    return [(64.0, ln) for ln in text.strip().splitlines()]


def test_parse_location():
    steps = parse_location("§ 4 Absatz 1 Satz 2 Nummer 3")
    assert [(s.kind, s.keys) for s in steps] == [("par", ["4"]), ("abs", ["1"]), ("satz", ["2"]), ("nr", ["3"])]
    assert parse_location("Absätze 4 bis 6")[0].keys == ["4", "5", "6"]


def test_parse_citation():
    assert parse_citation("vom 15. Juli 2009 (BGBl. I S. 1870)").work_elis() == ["eli/bund/bgbl-1/2009/s1870"]
    assert parse_citation("(BGBl. 2024 I Nr. 204)").work_elis() == ["eli/bund/bgbl-1/2024/204"]


def test_parse_nested_instructions():
    ins = parse_instructions(lines("""
1. § 38 wird wie folgt geändert:
a) Nach Absatz 3 wird der folgende Absatz 3a eingefügt:
„(3a) Neue Regel für „Tabak“.“
b) In Absatz 4 Satz 1 wird die Angabe „Absatz 3“ durch die Angabe „den Absätzen 3 und 3a“ ersetzt.
2. In § 1 und § 2 wird jeweils die Angabe „x“ gestrichen.
3. Der bisherige Absatz 4 wird zu Absatz 5.
"""))
    assert [(i.op, i.location) for i in ins] == [
        ("insert_units", "§ 38 Absatz 3"),
        ("replace_text", "§ 38 Absatz 4 Satz 1"),
        ("delete_text", "§ 1"),
        ("delete_text", "§ 2"),
        ("renumber", "Absatz 4"),
    ]
    assert ins[0].args["quote"].text == "(3a) Neue Regel für „Tabak“."
    assert ins[1].args == {"old": "Absatz 3", "new": "den Absätzen 3 und 3a", "all": False}


def test_forward_and_reverse_roundtrip():
    ins = parse_instructions(lines("""
1. § 38 wird wie folgt geändert:
a) Nach Absatz 3 wird der folgende Absatz 3a eingefügt:
„(3a) Neue Regel.“
b) In Absatz 4 Satz 1 wird die Angabe „Absatz 3“ durch die Angabe „den Absätzen 3 und 3a“ ersetzt.
"""))
    before = law()
    after = before.clone()
    for i in ins:
        assert check(after, i) == "pre"
        forward(after, i)
    par = find_par(after, "38")[0]
    assert [c.label for c in par.children] == ["(3)", "(3a)", "(4)", "(5)"]
    assert "nach den Absätzen 3 und 3a entrichtet" in par.full_text()
    for i in ins:
        assert check(after, i) == "post"
    restored = after.clone()
    for i in reversed(ins):
        reverse(restored, i, Snapshots(lambda key: None))
    assert render_lines(find_par(restored, "38")[0]) == render_lines(find_par(before, "38")[0])


def test_run_reconstructs_replaced_unit_from_snapshot():
    ins = parse_instructions(lines("""
§ 38 Absatz 3 wird durch den folgenden Absatz 3 ersetzt:
„(3) Steuerzeichen können fünf Wochen vor Inkrafttreten bezogen werden.“
"""))
    old = law()
    current = old.clone()
    forward(current, ins[0])
    snaps = Snapshots(lambda key: (find_par(old, key)[0], "Test") if key == "§38" else None)
    result = run(current, ins, snaps, default_state="pre")
    assert result.results[0].status == "consolidated"
    pd = result.pars[0]
    assert "zwei Monate" in pd.before.full_text() and "fünf Wochen" in pd.after.full_text()


def test_tree_from_lines_lists_and_dates():
    tree = tree_from_lines([
        (98, "(1) Die Steuer beträgt:"),
        (88, "1. für Zigaretten bis zum"),
        (100, "31. Dezember 2026 und"),
        (88, "2. für Zigarren,"),
        (88, "jeweils je Stück."),
    ])
    abs1 = tree.children[0]
    assert [c.label for c in abs1.children] == ["1.", "2."]
    assert abs1.children[0].parts == ["für Zigaretten bis zum 31. Dezember 2026 und"]
    assert abs1.parts[-1] == "jeweils je Stück."


def test_sentences():
    assert split_sentences("Nach § 5 Abs. 1 Nr. 2 gilt das. Am 1. Januar 2027 endet es.") == [
        "Nach § 5 Abs. 1 Nr. 2 gilt das.", "Am 1. Januar 2027 endet es."]


def test_word_diff_and_rows():
    left, right, inline = word_diff("12,28 Cent je Stück", "18,57 Cent je Stück")
    assert left[0] == {"t": "del", "s": "12,28"} and right[0] == {"t": "ins", "s": "18,57"}
    assert [s["t"] for s in inline] == ["del", "ins", "eq"]
    rows = diff_units(Node("abs", "(1)", parts=["a"]), Node("abs", "(1)", parts=["a", Node("nr", "1.", parts=["b"])]))
    assert [r["op"] for r in rows] == ["equal", "insert"]


def test_rows_pair_units_with_the_same_label():
    old = Node("nr", "2.", parts=[
        Node("bst", "a)", parts=["vorbehaltlich Buchstabe b 1,4 Cent"]),
        Node("bst", "b)", parts=["vom 1. Januar 2022 bis zum 31. Dezember 2022 1,4 Cent"]),
    ])
    new = Node("nr", "2.", parts=[
        Node("bst", "a)", parts=["vorbehaltlich der Buchstaben b bis d 2,85 Cent"]),
        Node("bst", "b)", parts=["vom 1. Januar 2027 bis zum 28. Februar 2027 1,4 Cent"]),
        Node("bst", "c)", parts=["vom 1. März 2027 bis zum 31. Dezember 2027 2,14 Cent"]),
        Node("bst", "d)", parts=["vom 1. Januar 2028 bis zum 31. Dezember 2028 2,35 Cent"]),
    ])
    rows = diff_units(old, new)
    pairs = [(r["left"][0]["s"][:2], r["right"][0]["s"][:2]) for r in rows if r["op"] == "change"]
    assert ("b)", "b)") in pairs


def test_footnote_marks_are_not_part_of_article_headings():
    """BGBl. 2026 I Nr. 322: the footnote "5" is set as a superscript right after the heading and
    ended up in the law's name ("Gesetzes gegen den unlauteren Wettbewerb5"), so the law was not found."""
    from bundesdiff.amendments import split_document
    from bundesdiff.pdftext import Line

    def ln(text, size=9.0):
        return Line(text, 50, 1, size, False)

    doc = split_document([ln("Artikel 1", 11), ln("Änderung des Designgesetzes1", 11), ln("Das Designgesetz …"),
                          ln("Artikel 6", 11), ln("Weitere Änderung des Gesetzes", 11),
                          ln("gegen den unlauteren Wettbewerb5", 11), ln("Das Gesetz …"),
                          ln("Artikel 7", 11), ln("Änderung der Verordnung (EU) 2018/1240", 11), ln("…")])
    assert [a.heading for a in doc.articles] == [
        "Änderung des Designgesetzes", "Weitere Änderung des Gesetzes gegen den unlauteren Wettbewerb",
        "Änderung der Verordnung (EU) 2018/1240"]


# --------------------------------------------------------------------------
# Found with the bill Drucksache 21/6588 (spec 016); each also affects publications.


def test_sentences_end_after_a_reference_number():
    """§ 15 Absatz 2 ROG: "… nach Satz 1. Bei raumbedeutsamen …" was one sentence, so the
    "Satz 6" of Artikel 4 Nummer 12 a) did not exist. § 4c BauGB: "… Absatz 3 Satz 4. Sie nutzen …"."""
    rog = ("Fordert die Raumordnungsbehörde den Vorhabenträger nicht innerhalb der Frist nach Satz 3 zur "
           "Vervollständigung der Verfahrensunterlagen auf, beginnt die Frist des Absatzes 1 Satz 3 am Tag des "
           "Eingangs der Verfahrensunterlagen nach Satz 1. Bei raumbedeutsamen Planungen und Maßnahmen der "
           "Verteidigung entscheidet das Bundesministerium der Verteidigung.")
    assert [s[:6] for s in split_sentences(rog)] == ["Forder", "Bei ra"]
    baugb = ("Gegenstand der Überwachung ist auch die Durchführung von Maßnahmen nach § 1a Absatz 3 Satz 4. "
             "Sie nutzen dabei die im Umweltbericht nach Nummer 3 Buchstabe b der Anlage 1 angegebenen "
             "Überwachungsmaßnahmen und die Informationen der Behörden nach § 4 Absatz 3.")
    assert len(split_sentences(baugb)) == 2
    assert len(split_sentences("Die Sätze 1 und 2. Danach gilt Absatz 3.")) == 2
    # dates and ordinals still do not end a sentence
    assert len(split_sentences("Dieses Gesetz tritt am 1. Januar 2027 in Kraft.")) == 1
    assert len(split_sentences("Es gilt die 32. Verordnung zur Durchführung des Gesetzes.")) == 1
    assert len(split_sentences("Es gilt Satz 1 1. Halbsatz entsprechend.")) == 1


def test_sentence_of_a_paragraph_without_absatz():
    """Artikel 12 (InVorG): "In § 6 Satz 2 …" failed with "Satz 2 nicht gefunden", because NeuRIS
    wraps the text of a § without Absätze in an unnumbered Absatz."""
    law = Node("law", parts=[Node("par", "§ 6", "Unterrichtung der Gemeinde", parts=[Node("abs", "", parts=[
        "Soweit ein Grundstück nach diesem Gesetz veräußert wird, besteht kein Vorkaufsrecht der Gemeinde nach "
        "den Vorschriften des Bauplanungsrechts. Die Mitteilungspflicht nach § 28 des Baugesetzbuchs entfällt."])])])
    ins = parse_instructions(lines(
        "In § 6 Satz 2 wird die Angabe „§ 28“ durch die Angabe „den §§ 28 und 28b“ ersetzt."))
    forward(law, ins[0])
    assert find_par(law, "§6")[0].full_text().endswith(
        "Die Mitteilungspflicht nach den §§ 28 und 28b des Baugesetzbuchs entfällt.")


def windbg() -> Node:
    """§ 6 Absatz 1 WindBG, shortened: two lists in one Absatz, after Satz 3 and after Satz 8."""
    return Node("law", parts=[Node("par", "§ 6", "Genehmigungserleichterung in Windenergiegebieten", parts=[
        Node("abs", "(1)", parts=[
            "Wird die Errichtung einer Windenergieanlage beantragt, ist keine Prüfung durchzuführen. Abweichend von "
            "Satz 1 ist eine Umweltverträglichkeitsprüfung durchzuführen. Satz 1 ist nur anzuwenden,",
            Node("nr", "1.", parts=["wenn bei Ausweisung des Windenergiegebietes eine Umweltprüfung nach § 8 des "
                                    "Raumordnungsgesetzes oder § 2 Absatz 4 des Baugesetzbuchs durchgeführt wurde und"]),
            Node("nr", "2.", parts=["soweit das Windenergiegebiet nicht in einem Nationalpark liegt."]),
            "Die zuständige Behörde hat Minderungsmaßnahmen anzuordnen. Geeignete Minderungsmaßnahmen sind "
            "anzuordnen. Soweit Maßnahmen nicht verfügbar sind, hat der Betreiber eine Zahlung zu leisten. Die "
            "Zahlung ist festzusetzen. Die Höhe der Zahlung beträgt:",
            Node("nr", "1.", parts=["450 Euro je Megawatt nach § 2 Absatz 4 der Verordnung,"]),
            Node("nr", "2.", parts=["ansonsten 3 000 Euro je Megawatt installierter Leistung."]),
            "Sie ist von dem Betreiber zu leisten.",
        ])])])


def test_number_of_the_list_that_a_sentence_introduces():
    """Artikel 8 Nummer 2 (WindBG): "In § 6 Absatz 1 Satz 3 Nummer 1 …" failed with "Satz 3 nicht
    gefunden": the sentence was looked for inside Nummer 1 instead of choosing the list by it."""
    law = windbg()
    ins = parse_instructions(lines(
        "In § 6 Absatz 1 Satz 3 Nummer 1 wird die Angabe „§ 2 Absatz 4“ durch die Angabe „§ 2a Absatz 2 und 3“ "
        "ersetzt."))
    assert check(law, ins[0]) == "pre"
    forward(law, ins[0])
    first, second = [p for p in find_par(law, "§6")[0].children[0].children if p.label == "1."]
    assert "§ 2a Absatz 2 und 3 des Baugesetzbuchs" in first.full_text()
    assert "§ 2 Absatz 4 der Verordnung" in second.full_text()  # the list of Satz 8 is untouched

    law = windbg()
    ins = parse_instructions(lines(
        "In § 6 Absatz 1 Satz 8 Nummer 1 wird die Angabe „§ 2 Absatz 4“ durch die Angabe „§ 3“ ersetzt."))
    forward(law, ins[0])
    first, second = [p for p in find_par(law, "§6")[0].children[0].children if p.label == "1."]
    assert "§ 2 Absatz 4 des Baugesetzbuchs" in first.full_text()
    assert "§ 3 der Verordnung" in second.full_text()


def test_units_of_the_list_that_a_sentence_introduces():
    """With two lists in one Absatz, "Satz 8 Nummer 2 wird … ersetzt" must not touch the first list."""
    law = windbg()
    ins = parse_instructions(lines("""
§ 6 Absatz 1 Satz 8 Nummer 2 wird durch die folgende Nummer 2 ersetzt:
„2. ansonsten 4 000 Euro je Megawatt installierter Leistung.“
"""))
    forward(law, ins[0])
    texts = [p.full_text() for p in find_par(law, "§6")[0].children[0].children]
    assert texts[1] == "2. soweit das Windenergiegebiet nicht in einem Nationalpark liegt."
    assert texts[3] == "2. ansonsten 4 000 Euro je Megawatt installierter Leistung."
    assert len(texts) == 4


def test_table_rows_with_numbers_are_a_list():
    """Artikel 2 Nummer 2 a) (§ 1 Absatz 2 BauNVO): NeuRIS delivers the list of Baugebiete as a table
    ("1. | Kleinsiedlungsgebiete | (WS)"), so "Nummer 1 wird gestrichen" found no Nummer 1."""
    import xml.etree.ElementTree as ET

    from bundesdiff.sources import _xml_parts

    rows = [("1.", "Kleinsiedlungsgebiete", "(WS)"), ("2.", "reine Wohngebiete", "(WR)"),
            ("3.", "allgemeine Wohngebiete", "(WA).")]
    xml = "<content><p>Die Flächen können dargestellt werden als</p><table>" + "".join(
        "<tr>" + "".join(f"<td><p>{c}</p></td>" for c in r) + "</tr>" for r in rows) + "</table></content>"
    absatz = Node("abs", "(2)")
    _xml_parts(ET.fromstring(xml), absatz)
    assert [(c.kind, c.label, c.parts) for c in absatz.children] == [
        ("nr", "1.", ["Kleinsiedlungsgebiete | (WS)"]), ("nr", "2.", ["reine Wohngebiete | (WR)"]),
        ("nr", "3.", ["allgemeine Wohngebiete | (WA)."])]

    law = Node("law", parts=[Node("par", "§ 1", "Allgemeine Vorschriften", parts=[absatz])])
    ins = parse_instructions(lines("""
2. § 1 wird wie folgt geändert:
a) Absatz 2 wird wie folgt geändert:
aa) Nummer 1 wird gestrichen.
bb) Die Nummern 2 bis 3 werden zu den Nummern 1 bis 2.
"""))
    for i in ins:
        forward(law, i)
    assert [c.full_text() for c in absatz.children] == ["1. reine Wohngebiete | (WR)",
                                                        "2. allgemeine Wohngebiete | (WA)."]

    # a table whose first column is not a numbering stays a table
    other = Node("abs", "(1)")
    _xml_parts(ET.fromstring("<content><table><tr><td>Zone</td><td>Wert</td></tr>"
                             "<tr><td>I</td><td>10</td></tr></table></content>"), other)
    assert other.parts == ["Zone | Wert", "I | 10"]


@pytest.mark.spec("ENT-8")
def test_a_bill_is_never_taken_as_already_in_the_law():
    """Artikel 2 Nummer 9 (§ 6a Absatz 2 BauNVO): "Nach Nummer 3 wird die folgende Nummer 4 eingefügt"
    was judged as already done, because a Nummer 4 exists; the renumbering after it then failed."""
    law = Node("law", parts=[Node("par", "§ 6a", "Urbane Gebiete", parts=[Node("abs", "(2)", parts=[
        "Zulässig sind",
        Node("nr", "1.", parts=["Wohngebäude,"]),
        Node("nr", "2.", parts=["Geschäfts- und Bürogebäude,"]),
        Node("nr", "3.", parts=["Einzelhandelsbetriebe, Schank- und Speisewirtschaften sowie Betriebe des "
                                "Beherbergungsgewerbes,"]),
        Node("nr", "4.", parts=["sonstige Gewerbebetriebe,"]),
        Node("nr", "5.", parts=["Anlagen für Verwaltungen sowie für kirchliche, kulturelle, soziale, "
                                "gesundheitliche und sportliche Zwecke."]),
    ])])])
    ins = parse_instructions(lines("""
9. § 6a Absatz 2 wird wie folgt geändert:
a) Nach Nummer 3 wird die folgende Nummer 4 eingefügt:
„4. Musikclubs,“.
b) Die bisherigen Nummern 4 und 5 werden zu den Nummern 5 und 6.
"""))
    result = run(law, ins, Snapshots(lambda key: None), "pre", force_state="pre")
    assert [(r.status, r.state) for r in result.results] == [("applied", "pre"), ("applied", "pre")]
    after = [c.full_text() for c in result.pars[0].after.children[0].children]
    assert after[2:5] == ["3. Einzelhandelsbetriebe, Schank- und Speisewirtschaften sowie Betriebe des "
                          "Beherbergungsgewerbes,", "4. Musikclubs,", "5. sonstige Gewerbebetriebe,"]
    assert after[5].startswith("6. Anlagen für Verwaltungen")
    assert [c.label for c in result.pars[0].before.children[0].children] == ["1.", "2.", "3.", "4.", "5."]
    # without the bill's fixed direction the engine still guesses, as for publications
    guessed = run(law, ins, Snapshots(lambda key: None), "pre")
    assert guessed.results[0].state == "post"


# Drucksache 21/6588, Artikel 1 Nummer 49 – real lines, Absatz 1 shortened after its first sentence part
BAUGB_NEW_TEIL = """
49. Nach § 135d wird der folgende Achte Teil eingefügt:
„Achter Teil
Besondere Regelungen für städtische Ökosystemgebiete im Sinne des Artikels 8 der
Verordnung (EU) 2024/1991
§ 135e
Wiederherstellungssatzung
(1) Die Gemeinde kann für städtische Ökosystemgebiete im Sinne des Artikels 8 der Verordnung (EU)
2024/1991 oder für Teile davon in einer Satzung ergänzende Vorgaben für die bauliche und sonstige Nutzung
der Grundstücke treffen.“
"""


@pytest.mark.spec("ENT-18")
def test_a_new_teil_counted_in_words_is_inserted_with_its_heading():
    """"der folgende Achte Teil" was not understood: the parser wanted the word for the unit right
    after "der folgende", so § 135e was missing from the Baugesetzbuch."""
    law = Node("law", parts=[Node("par", "§ 135c", "Satzungen", parts=["Die Gemeinde kann durch Satzung regeln."]),
                             Node("par", "§ 135d", "Ersatzgeld", parts=["Das Ersatzgeld wird erhoben."])])
    ins = parse_instructions(lines(BAUGB_NEW_TEIL))
    assert [(i.op, [(s.kind, s.keys) for s in i.path]) for i in ins] == [("insert_units", [("par", ["135d"])])]
    result = run(law, ins, Snapshots(lambda key: None), "pre", force_state="pre")
    assert [r.status for r in result.results] == ["applied"]
    (new,) = result.pars
    assert (new.key, new.before, new.after.heading) == ("§135e", None, "Wiederherstellungssatzung")
    assert new.new_parts == ["Achter Teil – Besondere Regelungen für städtische Ökosystemgebiete im Sinne des "
                             "Artikels 8 der Verordnung (EU) 2024/1991"]
    assert "Achter Teil" not in new.after.full_text()
    forward(law, ins[0])
    assert [p.key for p in law.children] == ["§135c", "§135d", "§135e"]


@pytest.mark.spec("ENT-18")
def test_a_new_unterabschnitt_counted_in_words_before_a_par():
    """BGBl. 2026 I Nr. 326, Artikel 1 Nummer 10 (Approbationsordnung für Ärzte), Absatz 1 shortened:
    the same wording with "Vor" and the form "Erste"."""
    ins = parse_instructions(lines("""
10. Vor § 34 wird der folgende Erste Unterabschnitt eingefügt:
„Erster Unterabschnitt
Allgemeine Vorgaben für die einzureichenden Unterlagen
§ 33a
Allgemeine Vorgaben für die einzureichenden Unterlagen
(1) Die nach diesem Abschnitt einzureichenden Unterlagen sind der zuständigen Behörde in Form von
Abschriften vorzulegen oder elektronisch zu übermitteln.“
"""))
    assert [(i.op, [(s.kind, s.keys) for s in i.path], i.args.get("before")) for i in ins] == [
        ("insert_units", [("par", ["34"])], True)]
    (par,) = ins[0].args["quote"].tree().children
    assert (par.key, par.heading) == ("§33a", "Allgemeine Vorgaben für die einzureichenden Unterlagen")
    assert par.part_headings == ["Erster Unterabschnitt – Allgemeine Vorgaben für die einzureichenden Unterlagen"]


@pytest.mark.spec("ENT-18")
def test_headings_between_new_pars_go_with_the_par_after_them():
    """BGBl. 2026 I Nr. 320, Artikel 5 Nummer 2 (Gesetz über die internationale Rechtshilfe in
    Strafsachen), real lines, Absätze shortened: "Unterabschnitt 2 Ausgehende Ersuchen" was shown
    at the end of § 91r instead of above § 91s."""
    tree = tree_from_lines(lines("""
Abschnitt 3
Zusammenarbeit nach Maßgabe der Richtlinie (EU) 2024/1260
Unterabschnitt 1
Eingehende Ersuchen
§ 91k
Übermittlung von Informationen auf Ersuchen
(1) Auf Ersuchen einer Vermögensabschöpfungsstelle eines Mitgliedstaates werden Informationen übermittelt.
§ 91r
Vorübergehende Sicherstellung von Vermögenswerten
(4) Bei Gefahr im Verzug sind die gemäß Absatz 2 zuständigen staatsanwaltlichen Vermögensabschöpfungs­
stellen befugt, die Sicherstellungsmaßnahmen nach Absatz 1 anzuordnen. § 111j Absatz 2 Satz 1 der Straf­
prozessordnung findet keine Anwendung.
Unterabschnitt 2
Ausgehende Ersuchen
§ 91s
Ausgehende Ersuchen um Übermittlung von Informationen an Vermögensabschöpfungsstellen
(1) Die deutschen Vermögensabschöpfungsstellen können ersuchen.
"""))
    k, r, s = tree.children
    assert [p.key for p in tree.children] == ["§91k", "§91r", "§91s"]
    assert tree.texts() == []
    assert k.part_headings == ["Abschnitt 3 – Zusammenarbeit nach Maßgabe der Richtlinie (EU) 2024/1260",
                               "Unterabschnitt 1 – Eingehende Ersuchen"]
    assert r.part_headings == []
    assert r.full_text().endswith("Strafprozessordnung findet keine Anwendung.")
    assert s.part_headings == ["Unterabschnitt 2 – Ausgehende Ersuchen"]


@pytest.mark.spec("ENT-18")
def test_a_new_part_without_a_par_of_its_own_is_not_evaluated():
    """Constructed: a quote with only the heading of a part has nothing to compare – it must not
    turn into a § without a number."""
    ins = parse_instructions(lines("""
49. Nach § 135d wird der folgende Achte Teil eingefügt:
„Achter Teil
Besondere Regelungen für städtische Ökosystemgebiete“.
"""))
    assert [i.op for i in ins] == ["unsupported"]
