"""Reading in-force dates (spec 002, TL-7) – every case with real wording from the Bundesgesetzblatt."""

from __future__ import annotations

import pytest

from bundesdiff.inforce import parse

SIGNATURE = (" Die verfassungsmäßigen Rechte des Bundesrates sind gewahrt. Das vorstehende Gesetz wird "
             "hiermit ausgefertigt. Es ist im Bundesgesetzblatt zu verkünden. Berlin, den 19. Oktober 2026")


def dates(entries):
    return [(e["date"], e["subject"], e["whole"], e["rest"]) for e in entries]


@pytest.mark.spec("TL-7")
def test_fixed_date():  # BGBl. 2026 I Nr. 314
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft." + SIGNATURE, "2026-10-27")
    assert dates(entries) == [("2027-01-01", None, True, False)]
    assert entries[0]["sentence"] == "Dieses Gesetz tritt am 1. Januar 2027 in Kraft."
    assert entries[0]["kind"] == "in" and not entries[0]["retroactive"]


@pytest.mark.spec("TL-7")
def test_day_after_promulgation_and_signature_of_an_ordinance():  # BGBl. 2026 I Nr. 298
    text = ("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Langen, den 13. Oktober 2026 "
            "D e r D i r e k t o r d e s B u n d e s a u f s i c h t s a m t e s")
    assert dates(parse(text, "2026-10-14")) == [("2026-10-15", None, True, False)]


@pytest.mark.spec("TL-7")
def test_second_day_after_promulgation():  # BGBl. 2026 I Nr. 304
    text = ("(1) Dieses Gesetz tritt vorbehaltlich der Absätze 2 bis 6 am zweiten Tag nach der Verkündung "
            "in Kraft. (2) Artikel 1 Nummer 10 Buchstabe b und Nummer 13 Buchstabe a sowie Artikel 7 Nummer "
            "1 bis 3 treten am 1. Januar 2028 in Kraft.")
    entries = parse(text, "2026-10-20")
    assert dates(entries) == [
        ("2026-10-22", None, True, True),
        ("2028-01-01", "Artikel 1 Nummer 10 Buchstabe b und Nummer 13 Buchstabe a sowie Artikel 7 Nummer 1 bis 3",
         False, False)]
    assert entries[1]["articles"] == []  # only parts of articles


@pytest.mark.spec("TL-7")
def test_exceptions_retroactive_and_article_lists():  # BGBl. 2026 I Nr. 322 and 2025 I Nr. 353
    entries = parse("(1) Dieses Gesetz tritt vorbehaltlich der Absätze 2 und 3 am 9. Dezember 2027 in Kraft. "
                    "(2) Artikel 5 tritt mit Wirkung vom 27. September 2026 in Kraft. "
                    "(3) Artikel 6 tritt am 27. September 2028 in Kraft." + SIGNATURE, "2026-10-27")
    assert dates(entries) == [("2027-12-09", None, True, True), ("2026-09-27", "Artikel 5", False, False),
                              ("2028-09-27", "Artikel 6", False, False)]
    assert entries[1]["retroactive"] and entries[1]["articles"] == ["5"]

    entries = parse("(1) Die Artikel 1 bis 4, 6, 7 und 9 dieses Gesetzes treten am Tag nach der Verkündung in "
                    "Kraft. (2) Artikel 5 tritt mit Wirkung vom 1. Juli 2021 in Kraft.", "2025-12-23")
    assert entries[0]["subject"] == "Artikel 1 bis 4, 6, 7 und 9"
    assert entries[0]["articles"] == ["1", "2", "3", "4", "6", "7", "9"]
    assert entries[0]["date"] == "2025-12-24"


@pytest.mark.spec("TL-7")
def test_inverted_sentence_with_numbered_list():  # BGBl. 2026 I Nr. 191
    entries = parse("(1) Dieses Gesetz tritt vorbehaltlich der Absätze 2 bis 4 am 1. November 2026 in Kraft. "
                    "(2) Am Tag nach der Verkündung treten in Kraft: 1. Artikel 1 § 3, 2. Artikel 7 und "
                    "3. Artikel 8.", "2026-06-25")
    assert dates(entries) == [("2026-11-01", None, True, True),
                              ("2026-06-26", "Artikel 1 § 3, Artikel 7, Artikel 8", False, False)]


@pytest.mark.spec("TL-7")
def test_repeal():  # BGBl. 2026 I Nr. 318
    entries = parse("Das Bundespolizeigesetz vom 19. Oktober 1994 (BGBl. I S. 2978, 2979), das zuletzt durch "
                    "Artikel 8 des Gesetzes vom 10. Februar 2026 (BGBl. 2026 I Nr. 39) geändert worden ist, tritt "
                    "am 28. Oktober 2026 außer Kraft.", "2026-10-27")
    assert dates(entries) == [("2026-10-28", "Bundespolizeigesetz", False, False)]
    assert entries[0]["kind"] == "out"


@pytest.mark.spec("TL-7")
def test_first_day_of_following_month_and_quarter():
    assert parse("Diese Verordnung tritt am ersten Tag des auf die Verkündung folgenden Kalendermonats in Kraft.",
                 "2026-11-30")[0]["date"] == "2026-12-01"
    assert parse("Diese Verordnung tritt am ersten Tag des dritten auf die Verkündung folgenden Kalendermonats "
                 "in Kraft.", "2026-11-30")[0]["date"] == "2027-02-01"
    assert parse("Dieses Gesetz tritt am ersten Tag des auf die Verkündung folgenden Kalendervierteljahres in "
                 "Kraft.", "2026-11-30")[0]["date"] == "2027-01-01"


@pytest.mark.spec("TL-7")
def test_what_is_not_understood_is_not_guessed():
    entries = parse("Dieses Gesetz tritt an dem Tag in Kraft, an dem das Abkommen nach seinem Artikel 30 "
                    "für die Bundesrepublik Deutschland in Kraft tritt.", "2026-10-27")
    assert [e["date"] for e in entries] == [None]
    # two dates in one sentence: unclear which applies to what
    entries = parse("Artikel 2 tritt am 1. Januar 2027 und Artikel 3 am 1. Juli 2027 in Kraft.", "2026-10-27")
    assert [e["date"] for e in entries] == [None]
    assert entries[0]["sentence"].startswith("Artikel 2 tritt")


@pytest.mark.spec("TL-7")
def test_event_with_latest_date_is_not_a_date():  # BGBl. 2026 I Nr. 304 and 2025 I Nr. 369
    entries = parse("(3) Artikel 1 Nummer 43 Buchstabe f tritt an dem Tag in Kraft, an dem der Durchführungsbeschluss "
                    "der Kommission über BVT-Schlussfolgerungen im Amtsblatt der Europäischen Union veröffentlicht "
                    "wird, spätestens jedoch am 1. September 2034. Das Bundesministerium für Umwelt, Klimaschutz, "
                    "Naturschutz und nukleare Sicherheit gibt den Tag des Inkrafttretens im Bundesgesetzblatt "
                    "bekannt.", "2026-10-19")
    assert [e["date"] for e in entries] == [None]
    assert entries[0]["subject"] == "Artikel 1 Nummer 43 Buchstabe f"
    entries = parse("(4) Artikel 1 Nummer 17 Buchstabe b Doppelbuchstabe bb tritt zum Datum der Inbetriebnahme des "
                    "Europäischen Reiseinformations- und -genehmigungssystems, das durch Beschluss der Kommission "
                    "gemäß Artikel 88 Absatz 1 der Verordnung (EU) 2018/1240 festgelegt wird, in Kraft.", "2025-12-29")
    assert [e["date"] for e in entries] == [None]


@pytest.mark.spec("TL-7")
def test_in_force_and_out_of_force_in_one_sentence():  # usual wording of temporary ordinances
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft und mit Ablauf des "
                    "31. Dezember 2030 außer Kraft.", "2026-10-30")
    assert [(e["kind"], e["date"], e["whole"]) for e in entries] == [("in", "2026-10-31", True),
                                                                     ("out", None, True)]
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft; gleichzeitig tritt die Musterverordnung "
                    "vom 3. März 2001 (BGBl. I S. 1) außer Kraft.", "2026-10-30")
    assert [(e["kind"], e["date"], e["whole"], e["subject"]) for e in entries] == [
        ("in", "2027-01-01", True, None), ("out", "2027-01-01", False, "Musterverordnung")]


@pytest.mark.spec("TL-7")
def test_pronoun_refers_to_the_act_before():
    entries = parse("Diese Verordnung tritt am 1. Januar 2027 in Kraft. Sie tritt am 31. Dezember 2031 "
                    "außer Kraft.", "2026-10-30")
    assert [(e["kind"], e["date"], e["whole"], e["subject"]) for e in entries] == [
        ("in", "2027-01-01", True, None), ("out", "2031-12-31", True, None)]
    entries = parse("(1) Artikel 2 tritt am 1. Januar 2027 in Kraft. (2) Er tritt am 31. Dezember 2030 außer "
                    "Kraft.", "2026-10-30")
    assert [(e["kind"], e["date"], e["articles"]) for e in entries] == [("in", "2027-01-01", ["2"]),
                                                                       ("out", "2030-12-31", ["2"])]
    # without anything before it the pronoun names nothing: unclear, never "a part of the publication"
    entries = parse("Sie tritt am 31. Dezember 2031 außer Kraft.", "2026-10-30")
    assert [(e["kind"], e["date"], e["subject"], e["whole"]) for e in entries] == [("unclear", None, None, False)]


@pytest.mark.spec("TL-7")
def test_lettered_article_ranges_and_impossible_dates_do_not_crash():
    entries = parse("Artikel 2a bis 4 treten am 1. Juli 2027 in Kraft.", "2026-10-30")
    assert entries[0]["subject"] == "Artikel 2a bis 4" and entries[0]["articles"] == []
    assert parse("Artikel 2 bis 4a treten am 1. Juli 2027 in Kraft.", "2026-10-30")[0]["articles"] == []
    assert parse("Dieses Gesetz tritt am 30. Februar 2027 in Kraft.", "2026-10-30")[0]["date"] is None


@pytest.mark.spec("TL-7")
def test_a_failing_in_force_text_does_not_stop_the_list(monkeypatch):
    from bundesdiff import inforce, listing

    def broken(text, date):
        raise ValueError("unexpected wording")

    monkeypatch.setattr(inforce, "parse", broken)
    entries = listing.in_force("Dieses Gesetz tritt  am 1. Januar 2027 in Kraft.", "2026-10-30")
    assert entries == [{"date": None, "retroactive": False, "kind": "in", "whole": False, "rest": False,
                        "subject": None, "articles": [], "sentence": "Dieses Gesetz tritt am 1. Januar 2027 in Kraft."}]


def kinds(entries):
    return [(e["kind"], e["date"], e["whole"], e["subject"]) for e in entries]


@pytest.mark.spec("TL-7")
def test_list_after_in_kraft_is_not_cut_by_a_later_clause():
    entries = parse("Am Tag nach der Verkündung treten in Kraft: 1. Artikel 1 § 3, 2. Artikel 7 und 3. Artikel 8; "
                    "Artikel 9 tritt außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", False, "Artikel 1 § 3, Artikel 7, Artikel 8"),
                              ("out", None, False, "Artikel 9")]
    entries = parse("Am Tag nach der Verkündung treten außer Kraft: 1. die Altverordnung, 2. das Altgesetz. "
                    "Im Übrigen tritt dieses Gesetz am 1. Januar 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("out", "2026-06-11", False, "Altverordnung, Altgesetz"),
                              ("in", "2027-01-01", True, None)]
    assert entries[1]["rest"]  # "Im Übrigen": the rest of the act


@pytest.mark.spec("TL-7")
def test_und_with_a_new_subject_gets_its_own_entry():
    entries = parse("Artikel 4 und 5 treten am Tag nach der Verkündung außer Kraft und Artikel 6 am 1. Januar 2027 "
                    "in Kraft.", "2026-06-10")
    assert [(e["kind"], e["date"], e["articles"]) for e in entries] == [("out", "2026-06-11", ["4", "5"]),
                                                                       ("in", "2027-01-01", ["6"])]
    entries = parse("Das Mustergesetz vom 1. Januar 2000 (BGBl. I S. 1) tritt am Tag nach der Verkündung außer Kraft "
                    "und Artikel 3 tritt am 1. Juli 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("out", "2026-06-11", False, "Mustergesetz"), ("in", "2027-07-01", False, "Artikel 3")]


@pytest.mark.spec("TL-7")
def test_gleichzeitig_as_its_own_sentence_and_with_several_laws():
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Gleichzeitig tritt das Altgesetz außer Kraft.",
                    "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("out", "2027-01-01", False, "Altgesetz")]
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Gleichzeitig treten außer Kraft: 1. die "
                    "Altverordnung vom 3. März 2001 (BGBl. I S. 5), 2. das Altgesetz vom 4. April 2002 (BGBl. I S. 6).",
                    "2026-06-10")
    assert kinds(entries)[1] == ("out", "2027-01-01", False, "Altverordnung, Altgesetz")
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft; gleichzeitig treten das Mustergesetz vom "
                    "1. Januar 2000 (BGBl. I S. 1) und die Musterverordnung vom 2. Februar 2001 (BGBl. I S. 2) "
                    "außer Kraft.", "2026-06-10")
    assert kinds(entries)[1] == ("out", "2027-01-01", False, "Mustergesetz, Musterverordnung")
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft; gleichzeitig tritt die Musterverordnung am "
                    "1. Januar 2027 außer Kraft.", "2026-06-10")
    assert kinds(entries)[1] == ("out", "2027-01-01", False, "Musterverordnung")
    # the subject after the verb, the date not known: still named, never "a part of the publication"
    entries = parse("Mit dem Inkrafttreten dieses Gesetzes tritt das Altgesetz außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("out", None, False, "Altgesetz")]


@pytest.mark.spec("TL-7")
def test_every_clause_of_a_sentence_is_kept():
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft und am 31. Dezember 2030 außer Kraft; "
                    "gleichzeitig tritt das Altgesetz außer Kraft.", "2026-06-10")
    # "gleichzeitig" after two dates: which one is meant is not certain
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("out", "2030-12-31", True, None),
                              ("out", None, False, "Altgesetz")]
    entries = parse("Artikel 1 tritt am 1. Januar 2027 in Kraft; Artikel 2 tritt am 1. Juli 2027 in Kraft.",
                    "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", False, "Artikel 1"), ("in", "2027-07-01", False, "Artikel 2")]


@pytest.mark.spec("TL-7")
def test_abbreviations_do_not_end_a_sentence():
    entries = parse("Die Musterverordnung vom 1. Januar 2000 (BGBl. I S. 1), die zuletzt durch Art. 2 Abs. 3 z. B. "
                    "geändert worden ist, tritt am 1. Juli 2027 außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("out", "2027-07-01", False, "Musterverordnung")]
    # a full stop inside a citation does not end the sentence either
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Gleichzeitig tritt die Polizeiverordnung vom "
                    "1. Mai 1938 (RGBl. I S. 3) außer Kraft.", "2026-06-10")
    assert kinds(entries)[1] == ("out", "2027-01-01", False, "Polizeiverordnung")
    assert entries[1]["sentence"].endswith("(RGBl. I S. 3) außer Kraft.")


@pytest.mark.spec("TL-7")
def test_sentence_ends_after_a_number_and_before_a_paragraph_sign():
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft, mit Ausnahme von Artikel 1 Nummer 3. "
                    "Artikel 1 Nummer 3 tritt am 1. Juli 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("in", "2027-07-01", False, "Artikel 1 Nummer 3")]
    assert entries[0]["rest"]  # "mit Ausnahme": not the whole act
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Es gilt für Veranlagungszeiträume ab 2027. "
                    "Gleichzeitig tritt das Altgesetz außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("unclear", None, False, None),
                              ("out", "2027-01-01", False, "Altgesetz")]
    assert entries[1]["sentence"] == "Es gilt für Veranlagungszeiträume ab 2027."
    entries = parse("§ 1 tritt am 1. Januar 2027 in Kraft. § 2 tritt am 1. Juli 2027 in Kraft.", "2026-06-10")
    assert [e["sentence"] for e in entries] == ["§ 1 tritt am 1. Januar 2027 in Kraft.",
                                                "§ 2 tritt am 1. Juli 2027 in Kraft."]


@pytest.mark.spec("TL-7")
def test_in_kraft_of_a_clause_inside_the_sentence_is_not_an_entry():
    entries = parse("Das Altgesetz tritt außer Kraft, sobald Artikel 4 in Kraft tritt.", "2026-06-10")
    assert kinds(entries) == [("out", None, False, "Altgesetz")]
    entries = parse("Artikel 2 tritt an dem Tag in Kraft, an dem Artikel 1 in Kraft tritt.", "2026-06-10")
    assert kinds(entries) == [("in", None, False, "Artikel 2")]


@pytest.mark.spec("TL-7")
def test_opening_phrases_are_not_the_subject():
    for opening in ("Abweichend von Absatz 1", "Abweichend hiervon", "Hiervon abweichend", "Mit Wirkung vom"):
        text = (f"{opening} tritt Artikel 3 am 1. Juli 2027 in Kraft." if opening != "Mit Wirkung vom"
                else "Mit Wirkung vom 1. Juli 2027 tritt Artikel 3 in Kraft.")
        assert kinds(parse(text, "2026-06-10")) == [("in", "2027-07-01", False, "Artikel 3")], text
    for opening in ("Vorbehaltlich des Absatzes 2", "Soweit nichts anderes bestimmt ist,"):
        entries = parse(f"{opening} tritt dieses Gesetz am 1. Januar 2027 in Kraft.", "2026-06-10")
        assert kinds(entries) == [("in", "2027-01-01", True, None)] and entries[0]["rest"], opening
    entries = parse("Abweichend von Absatz 1 treten am Tag nach der Verkündung in Kraft: 1. Artikel 1 Nummer 3, "
                    "2. Artikel 2.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", False, "Artikel 1 Nummer 3, Artikel 2")]


@pytest.mark.spec("TL-7")
def test_only_a_recognised_subject_is_named():
    """A part of the act or the name of a law – anything else names nothing ("unclear")."""
    for text in ("In Artikel 1 tritt § 3 am 1. Januar 2027 in Kraft.",
                 "Artikel 3 hingegen tritt am 1. Januar 2027 in Kraft.",
                 "Die Verordnung tritt am 1. Januar 2027 in Kraft.",  # which one?
                 "Das Gesetz vom 1. Januar 2000 (BGBl. I S. 1) tritt am 1. Januar 2027 außer Kraft.",
                 "Die Erste und die Zweite Musterverordnung treten am 1. Januar 2027 außer Kraft.",
                 # two dates without a verb between them: which date is whose?
                 "Artikel 1 tritt am 1. Januar 2027, Artikel 2 am 1. Juli 2027 in Kraft.",
                 "Artikel 3 tritt am 1. Juli 2027 in Kraft, Artikel 4 am 1. Juli 2028."):
        assert kinds(parse(text, "2026-06-10")) == [("unclear", None, False, None)], text
    for text, subject in (("Artikel 3 Nr. 2 Buchst. a tritt am 1. Januar 2027 in Kraft.", "Artikel 3 Nr. 2 Buchst. a"),
                          ("§ 5 Abs. 2 S. 1 tritt am 1. Januar 2027 in Kraft.", "§ 5 Abs. 2 S. 1"),
                          ("Das Gesetz zur Regelung der Bundesbank i. d. F. der Bekanntmachung vom 1. Mai 2000 tritt "
                           "am 1. Januar 2027 außer Kraft.", "Gesetz zur Regelung der Bundesbank")):
        assert kinds(parse(text, "2026-06-10"))[0][3] == subject, text


@pytest.mark.spec("TL-7")
def test_more_ways_to_say_the_day():
    assert parse("Diese Verordnung tritt am Tag nach ihrer Verkündung in Kraft.", "2026-06-10")[0]["date"] == "2026-06-11"
    assert parse("Diese Verordnung tritt am Tage nach der Verkündung in Kraft.", "2026-06-10")[0]["date"] == "2026-06-11"
    assert parse("Artikel 2 tritt zum 1. Januar 2027 in Kraft.", "2026-06-10")[0]["date"] == "2027-01-01"
    entries = parse("Mit Wirkung vom 1. Januar 2026 tritt Artikel 3 in Kraft.", "2026-06-10")
    assert entries[0]["date"] == "2026-01-01" and entries[0]["retroactive"]


@pytest.mark.spec("TL-7")
def test_a_following_exception_means_not_the_whole_act():
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Satz 1 gilt nicht für Artikel 3.", "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("unclear", None, False, None)]
    assert entries[0]["rest"] and entries[1]["sentence"] == "Satz 1 gilt nicht für Artikel 3."


@pytest.mark.spec("TL-7")
def test_an_ordinal_inside_a_sentence_does_not_end_it():
    entries = parse("Die 2. Mustergesetz-Durchführungsverordnung tritt am 1. Januar 2027 außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("out", "2027-01-01", False, "2. Mustergesetz-Durchführungsverordnung")]
    assert entries[0]["sentence"].startswith("Die 2. Mustergesetz")
    entries = parse("Artikel 3 tritt am ersten Tag des 2. Monats nach der Verkündung in Kraft.", "2026-06-10")
    assert entries[0]["sentence"].startswith("Artikel 3 tritt") and entries[0]["date"] is None
    # but "Artikel 2 und 3." is the end of a sentence
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Satz 1 gilt nicht für Artikel 2 und 3. "
                    "Artikel 4 tritt am 1. Januar 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("unclear", None, False, None),
                              ("in", "2027-01-01", False, "Artikel 4")]
    assert entries[0]["rest"]


@pytest.mark.spec("TL-7")
def test_a_pronoun_refers_by_its_gender():
    entries = parse("Diese Verordnung tritt am 1. Januar 2027 in Kraft. Artikel 2 tritt am 1. Januar 2028 in Kraft. "
                    "Sie tritt am 31. Dezember 2030 außer Kraft.", "2026-06-10")
    assert kinds(entries)[2] == ("out", "2030-12-31", True, None)  # the Verordnung, not Artikel 2
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Artikel 2 tritt am 1. Januar 2028 in Kraft. "
                    "Es tritt am 31. Dezember 2030 außer Kraft.", "2026-06-10")
    assert kinds(entries)[2] == ("out", "2030-12-31", True, None)
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft; sie tritt am 31. Dezember 2030 "
                    "außer Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("out", "2030-12-31", True, None)]
    # two feminine names before it: which one?
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Gleichzeitig tritt die "
                    "Polizeiverordnung vom 1. Mai 1938 außer Kraft. Sie tritt am 31. Dezember 2030 außer Kraft.",
                    "2026-06-10")
    assert kinds(entries)[2] == ("unclear", None, False, None)


@pytest.mark.spec("TL-7")
def test_bare_or_cut_law_names_and_trailing_words_name_nothing():
    for text in ("Das Abkommen vom 3. März 2000 tritt am 1. Januar 2027 außer Kraft.",
                 "Der Vertrag vom 3. März 2000 tritt am 1. Januar 2027 außer Kraft.",
                 "Das Gesetz zu dem Abkommen vom 3. März 2000 zwischen der Bundesrepublik Deutschland und der "
                 "Französischen Republik tritt am 1. Januar 2027 außer Kraft.",
                 "Das Mustergesetz hingegen tritt am 1. Januar 2027 außer Kraft.",
                 "Die Gesetzesänderungen in Artikel 1 treten am 1. Januar 2027 in Kraft."):
        assert kinds(parse(text, "2026-06-10")) == [("unclear", None, False, None)], text


@pytest.mark.spec("TL-7")
def test_an_exception_in_the_next_paragraph_means_not_the_whole_act():
    entries = parse("(1) Dieses Gesetz tritt am 1. Januar 2027 in Kraft. (2) Abweichend von Absatz 1 tritt Artikel 3 "
                    "am Tag nach der Verkündung in Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("in", "2026-06-11", False, "Artikel 3")]
    assert entries[0]["rest"]
    entries = parse("Abweichend von § 1 tritt Artikel 2 am 1. Juli 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2027-07-01", False, "Artikel 2")]


@pytest.mark.spec("TL-7")
def test_gilt_sentences_change_only_what_they_say():
    # an exception that could be about the coming into force or the expiry: neither date is certain,
    # and the exception itself is shown
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft und am 31. Dezember 2030 außer Kraft. "
                    "Satz 1 gilt nicht für § 3.", "2026-06-10")
    assert kinds(entries) == [("in", None, True, None), ("out", None, True, None), ("unclear", None, False, None)]
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Gleichzeitig tritt das Mustergesetz "
                    "außer Kraft. Satz 2 gilt nicht für § 4 des Mustergesetzes.", "2026-06-10")
    # it names the Mustergesetz: only that repeal is uncertain, the act's own date stays
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("out", None, False, "Mustergesetz"),
                              ("unclear", None, False, None)]
    # a part that applies from another day, said without "in Kraft": shown, not dropped
    for text in ("Artikel 3 gilt ab dem 1. Januar 2027.", "Artikel 3 gilt bis zum 31. Dezember 2030."):
        entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. " + text, "2026-06-10")
        assert kinds(entries) == [("in", "2026-06-11", True, None), ("unclear", None, False, None)], text
        assert entries[0]["rest"] and entries[1]["sentence"] == text
    # about the whole act: shown, but the act is not "the rest"
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Es gilt erst ab dem 1. Juli 2027.",
                    "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", True, None), ("unclear", None, False, None)]
    assert not entries[0]["rest"]
    # a limit of scope is not an exception for a part
    entries = parse("Diese Verordnung tritt am 1. Januar 2027 in Kraft. Sie gilt nur für Anträge, die nach diesem Tag "
                    "gestellt werden.", "2026-06-10")
    assert [e["rest"] for e in entries] == [False]
    # a later date for a part that is not said with "in Kraft": shown as not understood, never dropped
    entries = parse("Diese Verordnung tritt am 1. Januar 2027 in Kraft. § 3 gilt erst ab dem 1. Januar 2028.",
                    "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("unclear", None, False, None)]
    assert entries[0]["rest"] and entries[1]["sentence"] == "§ 3 gilt erst ab dem 1. Januar 2028."


@pytest.mark.spec("TL-7")
def test_more_wordings_of_lists_and_days():
    entries = parse("Es treten am Tag nach der Verkündung in Kraft: 1. Artikel 2, 2. Artikel 3.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", False, "Artikel 2, Artikel 3")]
    assert parse("Dieses Gesetz tritt am Tag nach der Verkündung dieses Gesetzes in Kraft.",
                 "2026-06-10")[0]["date"] == "2026-06-11"
    # the issue date as older stored results give it
    assert parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft.",
                 "Vom 10. Juni 2026")[0]["date"] == "2026-06-11"


@pytest.mark.spec("TL-7")
def test_a_plural_pronoun_never_means_the_whole_act():
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Die §§ 3 und 4 treten am 1. Januar "
                    "2027 in Kraft. Sie treten am 31. Dezember 2030 außer Kraft.", "2026-06-10")
    assert kinds(entries)[2] == ("out", "2030-12-31", False, "§§ 3 und 4")
    # "Er" is one: not "Artikel 2 und 3"
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Die Artikel 2 und 3 treten am "
                    "1. Januar 2027 in Kraft. Er tritt am 31. Dezember 2030 außer Kraft.", "2026-06-10")
    assert kinds(entries)[2] == ("unclear", None, False, None)


@pytest.mark.spec("TL-7")
def test_es_before_the_verb_can_be_a_placeholder():
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Es treten am 1. Januar 2027 außer Kraft "
                    "das Altgesetz und die Altverordnung.", "2026-06-10")
    assert kinds(entries)[1] == ("out", "2027-01-01", False, "Altgesetz, Altverordnung")
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Es tritt außer Kraft das Altgesetz vom "
                    "1. Januar 2000 (BGBl. I S. 1).", "2026-06-10")
    assert kinds(entries)[1] == ("out", None, False, "Altgesetz")
    # "es" after ";" with nothing after "Kraft": the act itself
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft; es tritt am 31. Dezember 2030 außer Kraft.",
                    "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("out", "2030-12-31", True, None)]


@pytest.mark.spec("TL-7")
def test_a_list_ends_where_a_sentence_with_its_own_verb_follows():
    entries = parse("Am Tag nach der Verkündung treten in Kraft: 1. Artikel 1, 2. Artikel 2. Artikel 3 tritt am "
                    "1. Januar 2027 in Kraft.", "2026-06-10")
    assert kinds(entries) == [("in", "2026-06-11", False, "Artikel 1, Artikel 2"),
                              ("in", "2027-01-01", False, "Artikel 3")]


@pytest.mark.spec("TL-7")
def test_the_number_of_a_pronoun_comes_from_its_own_verb():
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Die Artikel 2 und 3 treten am 1. Januar "
                    "2027 in Kraft. Sie tritt am 31. Dezember 2030 außer Kraft, sofern nicht vorher andere Regelungen "
                    "in Kraft treten.", "2026-06-10")
    assert kinds(entries)[2] == ("out", "2030-12-31", True, None)
    # the head of "Artikel 2 Nummer 3" is "Nummer": "sie", not "er"
    entries = parse("Artikel 2 Nummer 3 tritt am 1. Januar 2027 in Kraft. Er tritt am 31. Dezember 2030 außer Kraft.",
                    "2026-06-10")
    assert kinds(entries)[1] == ("unclear", None, False, None)


@pytest.mark.spec("TL-7")
def test_titles_after_the_verb_are_not_cut_at_zum_or_am():  # the closing sentence of training regulations
    entries = parse("Diese Verordnung tritt am 1. August 2026 in Kraft. Gleichzeitig tritt die Verordnung über die "
                    "Berufsausbildung zum Koch/zur Köchin vom 13. Februar 1998 (BGBl. I S. 364) außer Kraft.",
                    "2026-06-10")
    assert kinds(entries)[1] == ("out", "2026-08-01", False, "Verordnung über die Berufsausbildung zum Koch/zur Köchin")
    entries = parse("Diese Verordnung tritt am 1. August 2026 in Kraft. Gleichzeitig tritt die Verordnung über die "
                    "Gebühren am Bundesgerichtshof außer Kraft.", "2026-06-10")
    assert kinds(entries)[1][3] == "Verordnung über die Gebühren am Bundesgerichtshof"
    entries = parse("Diese Verordnung tritt am 1. August 2026 in Kraft und die Verordnung über die Berufsausbildung "
                    "zum Koch am 31. Juli 2026 außer Kraft.", "2026-06-10")
    assert kinds(entries)[1] == ("out", "2026-07-31", False, "Verordnung über die Berufsausbildung zum Koch")


@pytest.mark.spec("TL-7")
def test_sentences_that_change_no_time_change_nothing():
    for text in ("Die auf Grund des § 122 der Handwerksordnung weiter anzuwendenden Vorschriften sind, soweit sie "
                 "Gegenstände dieser Verordnung regeln, nicht mehr anzuwenden.",  # BGBl. 1984 I S. 1148
                 "§ 3 gilt nur für Anträge nach § 2.", "Artikel 2 gilt entsprechend.", "§ 7 bleibt unberührt."):
        entries = parse("Diese Verordnung tritt am 1. August 2026 in Kraft. " + text, "2026-06-10")
        assert kinds(entries) == [("in", "2026-08-01", True, None)] and not entries[0]["rest"], text
    # an exception about the repealed law leaves the act's own date alone
    entries = parse("Dieses Gesetz tritt am 1. Januar 2027 in Kraft. Gleichzeitig tritt das Altgesetz außer Kraft. "
                    "§ 4 des Altgesetzes ist bis zum 31. Dezember 2027 weiter anzuwenden.", "2026-06-10")
    assert kinds(entries) == [("in", "2027-01-01", True, None), ("out", None, False, "Altgesetz"),
                              ("unclear", None, False, None)]


@pytest.mark.spec("TL-7")
def test_a_pronoun_does_not_skip_what_was_not_understood():
    for middle in ("Tabelle 2 tritt am 1. Januar 2027 in Kraft.",
                   "Die Übergangsvorschrift in § 9 tritt am 1. Januar 2027 in Kraft."):
        entries = parse(f"Diese Verordnung tritt am Tag nach der Verkündung in Kraft. {middle} "
                        "Sie tritt am 31. Dezember 2030 außer Kraft.", "2026-06-10")
        assert kinds(entries)[-1] == ("unclear", None, False, None), middle
    entries = parse("Kapitel 3 tritt am 1. Januar 2027 in Kraft und es tritt am 31. Dezember 2030 außer Kraft.",
                    "2026-06-10")
    assert all(e["kind"] == "unclear" for e in entries)


@pytest.mark.spec("TL-7")
def test_a_date_in_a_title_is_not_the_date_of_the_repeal():
    entries = parse("Diese Verordnung tritt am Tag nach der Verkündung in Kraft. Gleichzeitig tritt die Verordnung "
                    "zur Bestimmung des Rentenwerts zum 1. Juli 2024 außer Kraft.", "2026-06-10")
    assert kinds(entries)[1] == ("unclear", None, False, None)
    # a date before the publication without "mit Wirkung vom" is never taken as certain
    assert parse("Artikel 2 tritt am 1. Januar 2020 in Kraft.", "2026-06-10")[0]["date"] is None


@pytest.mark.spec("TL-7")
def test_a_later_exception_for_a_repealed_law_makes_its_repeal_uncertain():
    entries = parse("(1) Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. (2) Gleichzeitig tritt das Altgesetz "
                    "außer Kraft. (3) Abweichend von Absatz 2 tritt § 4 des Altgesetzes am 1. Januar 2027 außer Kraft.",
                    "2026-06-10")
    assert kinds(entries)[:2] == [("in", "2026-06-11", True, None), ("out", None, False, "Altgesetz")]
    entries = parse("Dieses Gesetz tritt am Tag nach der Verkündung in Kraft. Gleichzeitig tritt das Altgesetz außer "
                    "Kraft. Es ist bis zum 31. Dezember 2027 weiter anzuwenden.", "2026-06-10")
    assert kinds(entries)[:2] == [("in", "2026-06-11", True, None), ("out", None, False, "Altgesetz")]
