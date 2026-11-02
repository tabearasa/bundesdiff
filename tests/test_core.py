"""Offline tests for instruction parsing, application and diffing."""

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
