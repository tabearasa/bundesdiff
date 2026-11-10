# 016 Gesetzentwürfe: what a bill would change (prototype with one bill)

Status: done
Prefix: ENT

## Problem

bundesdiff shows what a law changed once it is published in the Bundesgesetzblatt. By then
nothing can be influenced any more. The public debate happens earlier, while the bill
(Gesetzentwurf) is in the Bundestag – and a bill is even harder to read than the final law: this
one is a 170-page PDF in which 62 pages are instructions such as "In § 4c Satz 2 wird die Angabe
… ersetzt". A reader without legal training cannot see what the bill would do to the law they
know.

This spec is a prototype: one bill, shown in the same before/after view as a publication, in its
own category. It also records how the approach generalises to every bill.

## Analysis of the prototype bill

Drucksache 21/6588, "Entwurf eines Gesetzes zur Modernisierung des Städtebau- und
Raumordnungsrechts", Gesetzentwurf der Bundesregierung, 22.06.2026, 170 pages
(<https://dserver.bundestag.de/btd/21/065/2106588.pdf>).

### Structure

| Pages | Part | Use for bundesdiff |
| --- | --- | --- |
| 1–4 | Vorblatt: A. Problem und Ziel, B. Lösung; Nutzen, C. Alternativen, D. Haushaltsausgaben, E. Erfüllungsaufwand, F. Weitere Kosten | A and B are a summary in fairly plain words |
| 5 | Letter of the Bundeskanzler to the Bundestag president | names the ministry in charge and the date sent to the Bundesrat |
| 7–62 | Anlage 1: the bill itself. Title, "Vom ...", Inhaltsübersicht, Artikel 1–13 | **same form as a law in the Bundesgesetzblatt** |
| 63–74 | Begründung, A. Allgemeiner Teil | background |
| 74–164 | Begründung, B. Besonderer Teil: "Zu Artikel 1", "Zu Nummer 2 (§ 1)", "Zu Buchstabe a", "Zu Doppelbuchstabe aa" … | **one explanation per instruction**, addressed by the same markers as the instructions |
| 165–170 | Anlage 2: Stellungnahme des Nationalen Normenkontrollrates | not needed |

Artikel 1–12 each amend one existing law or ordinance (Baugesetzbuch, Baunutzungsverordnung,
Planzeichenverordnung, Raumordnungsgesetz, Verwaltungsgerichtsordnung, HOAI,
Wasserhaushaltsgesetz, Windenergieflächenbedarfsgesetz, Bundesnaturschutzgesetz,
Umwelt-Rechtsbehelfsgesetz, 32. BImSchV, Investitionsvorranggesetz). Artikel 13 is the
Inkrafttreten, with placeholders instead of dates ("am … [einsetzen: Datum des ersten Tages
…]").

The Begründung has 129 "Zu Nummer", 126 "Zu Buchstabe", 45 "Zu Doppelbuchstabe" and 9 "Zu
Dreifachbuchstabe" headings (one of them misspelt "Dreifachbuchtsabe" in the original).

### What the existing analysis already does with it

Measured with a throwaway script that feeds pages 7–62 into the unchanged `amendments.py` and
`engine.py` (nothing in the repository was changed):

* All 13 Artikel are split correctly; all 12 amended laws are found (8 in NeuRIS, 4 on
  gesetze-im-internet.de).
* 335 instructions are recognised. **265 (79 %) are applied** to the current law text and
  give a before/after comparison of 136 §§.
* 60 are not evaluated, for reasons that already exist for publications: 30 concern the
  Inhaltsübersicht, 12 concern Anlagen, 8 concern headings of Teile/Abschnitte or insert a whole
  new Teil, 10 use wordings the parser does not know (mostly two replacements in one sentence:
  "wird die Angabe … durch … und die Angabe … durch … ersetzt").
* 10 fail and 1 is applied in the wrong direction. Looked at one by one (owner's decision,
  see below), none is caused by the bill or by a law that changed after it. All are weaknesses
  of the engine that affect publications in the same way:

  | Cause | Instructions | Example |
  | --- | --- | --- |
  | A sentence addressed together with a number of its list ("Satz 4 Nummer 3"): the sentence that introduces a list is not found | 3 | Art. 1 Nr. 35 e) aa) (§ 35 Absatz 6 BauGB), Art. 6 Nr. 1 (§ 19 HOAI), Art. 8 Nr. 2 (§ 6 WindBG) |
  | A sentence addressed in a § that has no Absätze ("In § 6 Satz 2") | 2 | Art. 12 (§ 6 InVorG), Art. 1 Nr. 8 (§ 4c BauGB) |
  | Sentences are not split after a number: "… nach Satz 1. Bei raumbedeutsamen …" counts as one sentence, so "Satz 6" does not exist | 1, probably 2 | Art. 4 Nr. 12 a) and c) (§ 15 ROG) |
  | The numbers of a list are stored as rows of a table in NeuRIS ("1. \| Kleinsiedlungsgebiete \| (WS)") and are not found as Nummern | 2 | Art. 2 Nr. 2 a) aa) and bb) (§ 1 Absatz 2 BauNVO) |
  | Wrong direction: "Nach Nummer 3 wird die folgende Nummer 4 eingefügt" is taken as already done because a Nummer 4 exists; the renumbering after it then fails | 1 wrong, 1 failed | Art. 2 Nr. 9 a) and b) (§ 6a BauNVO) |

  The causes of the first three rows are read from the instruction and the law text side by
  side; they are not yet confirmed by a fix. For Art. 4 Nr. 12 c) the cause is not pinned down.

### What differs from a Bundesgesetzblatt PDF

1. **Layout.** Body text is 10.5 pt (BGBl. 9 pt), headings 11 pt bold, the running header is
   lower on the page. `pdftext.py` needs its own profile for Drucksachen.
2. **Hanging quotation marks.** The opening „ of new wording is a separate text fragment to the
   left of the label, one point lower ("8." above, „ below). Read top to bottom this gives
   `8. „ in Gebieten …` instead of `„8. in Gebieten …`; the label is then mistaken for an
   instruction number. Assembling each line left to right raised the result from 220 to 265
   applied instructions – the largest single effect.
3. **A bill is never in force.** The engine guesses per § whether a change is already in the
   law text ("rückgerechnet"). For one instruction of this bill it guessed "already contained".
   For a bill that is always wrong: the direction must be fixed to "berechnet".
4. **The law moves on while the bill waits.** The bill was written against the law as it stood
   in June 2026. Our Baugesetzbuch text is the version of 30.09.2026. If a law changed in
   between, instructions may no longer fit, or fit a different text.
5. **No dates.** "Vom ..." and the placeholders in the Inkrafttreten: there is no in-force date
   to compute, so a bill has no place on the timeline of in-force dates.
6. **More to show.** A Begründung per instruction and the Vorblatt do not exist for
   publications.

### How it generalises to every bill

* **The instruction language is the same** for bills and for laws (both follow the Handbuch der
  Rechtsförmlichkeit). Parser and engine are shared; every improvement made for bills also
  improves publications, and the reverse.
* **Three kinds of bills, one core.** Bills of the Bundesregierung have the form above (later
  printings add the Stellungnahme of the Bundesrat and the reply as further Anlagen). Bills of
  the Bundesrat also come with a letter and Anlagen. Bills of Fraktionen have no letter and no
  Anlage: the bill text follows the Vorblatt directly. In all three the bill text starts at its
  title followed by "Vom ..." and ends at the bold heading "Begründung". These two anchors are
  the general rule; "Anlage 1" is not. *Checked only on this one document – the other two kinds
  are from knowledge of the format and need one real example each as a test.*
* **Bills that create a new law** (Stammgesetz) have §§ instead of instructions. There is
  nothing to compare; the whole text is new. Mixed bills (Mantelgesetze) have both.
* **Addresses are predictable.** `dserver.bundestag.de/btd/<WP>/<first three digits of the
  five-digit number>/<WP><five-digit number>.pdf` – 21/6588 gives `btd/21/065/2106588.pdf`.
* **Finding all bills** needs a list like the RSS feed of the Bundesgesetzblatt. The
  Bundestag's documentation system DIP has a public interface with the kind of document, the
  date, the author and the further course of each bill. It needs an access key. *Not verified
  for this spec.*
* **Later versions of the same bill.** Committees change bills (Beschlussempfehlung, printed as
  a two-column comparison of bill and committee version). The published law may therefore
  differ from the bill. Linking bill → committee version → Bundesgesetzblatt is the natural
  next step and would let readers see what Parliament changed.

## Requirements

**ENT-1** The navigation has an entry "Gesetzentwürfe" (short form on narrow screens:
"Entwürfe") that leads to the list of bills, `#/entwuerfe`. It is marked as active there and on
every page of a bill.

**ENT-2** The list of bills shows for each bill: its title, "Drucksache 21/6588", the date,
who introduced it ("Gesetzentwurf der Bundesregierung") and the laws it would change. In the
prototype the list has one entry.

**ENT-3** Above the list a short text explains the category: "Ein Gesetzentwurf ist ein
Vorschlag für ein neues Gesetz. Er gilt noch nicht. Der Bundestag kann ihn ändern oder
ablehnen."

**ENT-4** Bills never appear in the list of Veröffentlichungen or on its timeline.

**ENT-5** The page of a bill (`#/entwurf/21/6588`) has a header with "Drucksache 21/6588", the
title as `h1`, "Gesetzentwurf der Bundesregierung" and the date.

**ENT-6** Directly below the header, before any comparison, a notice says: "Dies ist ein
Entwurf. Er gilt nicht. Der Bundestag kann ihn noch ändern oder ablehnen. bundesdiff zeigt den
Stand vom 22.06.2026 und verfolgt nicht, was danach mit dem Entwurf geschehen ist."

**ENT-7** Each Artikel that amends a law is shown in the same comparison as a publication. The
two sides are named "Geltender Text" and "Text nach dem Entwurf".

**ENT-8** No § of a bill is ever shown as "rückgerechnet" ("alter Text rekonstruiert"). An
instruction that does not fit the current law text is shown as "nicht anwendbar" with its
original wording, under "Wortlaut im Entwurf".

**ENT-9** Each amended law names the version it was compared with: "Verglichen mit der Fassung
vom 30.09.2026." If that version is newer than the bill, it adds: "Das Gesetz wurde nach dem
Entwurf noch geändert. Einzelne Änderungen passen deshalb vielleicht nicht mehr."

**ENT-10** The page says how much could be shown, with the real numbers of the bill, for
example: "274 von 335 Änderungen werden im Vergleich gezeigt. Die übrigen finden Sie bei jedem
Gesetz unter „Wortlaut im Entwurf“."

**ENT-11** The comparison contains no text of the Begründung or of the Vorblatt: between
the old and the new wording only the instruction itself appears, as for publications.

**ENT-12** The page of a bill has a section "Allgemeine Informationen", above the comparison
and separate from it. It holds the Vorblatt ("Zusammenfassung des Entwurfs (Vorblatt)") and
the Begründung of the bill in parts – its general part and one part per Artikel –, each closed
at first and marked as the words of the author: "Text der Bundesregierung, nicht von
bundesdiff". A note says that tables and footnotes are missing and stand in the Drucksache.
The text of a part is loaded when the reader opens it; if that fails, the part says "Dieser
Text konnte nicht geladen werden." and links to the Drucksache.

**ENT-13** Articles that amend nothing (here: Inkrafttreten) are shown as text, with the
placeholders unchanged. No in-force date is shown; where the bill has placeholders, the header
says: "Im Entwurf steht noch kein Datum. Es wird erst eingesetzt, wenn das Gesetz beschlossen
und verkündet ist."

**ENT-14** A link "Drucksache beim Deutschen Bundestag (PDF, externe Seite)" leads to the
original. The note about the binding text reads, on pages of bills: "Maßgeblich ist allein die
Drucksache des Deutschen Bundestages."

**ENT-15** If the data of a bill cannot be loaded, the page says: "Dieser Gesetzentwurf kann
gerade nicht angezeigt werden. Bitte versuchen Sie es später noch einmal." and still shows the
link of ENT-14. If the list cannot be loaded: "Die Liste der Gesetzentwürfe konnte nicht
geladen werden." An address that is none of the bills shown (mistyped or outdated) gets:
"Diesen Gesetzentwurf zeigt bundesdiff nicht. Bisher sind hier nur einzelne Gesetzentwürfe zu
sehen." with a link "Zur Liste der Gesetzentwürfe" – no request to try again, no link to a
Drucksache that may not exist.

**ENT-16** The about page names the Deutscher Bundestag as the source of the bills, next to
the other sources (NAV-10). The help does the same under "Quellen und Grenzen".

**ENT-17** The help explains the new terms in its "Kleines Wörterbuch": "Gesetzentwurf",
"Drucksache", "Vorblatt und Begründung".

**ENT-18** When an instruction inserts a new part of the law above the § – a Buch, Teil,
Kapitel, Abschnitt, Unterabschnitt, Titel or Untertitel – together with its §§, the heading of
that part stands as one line above the first of these §§, for example above "§ 135e
Wiederherstellungssatzung" (Artikel 1 Nummer 49): "Neu: Achter Teil – Besondere Regelungen für
städtische Ökosystemgebiete im Sinne des Artikels 8 der Verordnung (EU) 2024/1991". Nested
parts get one line each, the outer one first. The heading is never dropped and never becomes
part of the text of a § (owner, 2026-11-10). Publications use the same parser, so this holds
for them too.

## Accessibility

**ENT-A1** That a page is a bill is not shown by colour alone: the word "Entwurf" stands in
the header and in the notice of ENT-6.

**ENT-A2** With the fourth entry the navigation still fits on one row at 320 px (NAV-3); on
phones the entry is in the menu. Four names do not fit beside the logo, the help, the search
and the switch below 480 px, so there the navbar shows "Menü" instead of the pages (NAV-3
changed).

**ENT-A3** The parts of "Allgemeine Informationen" open and close with Enter and Space, announce
their state (open/closed) to screen readers and keep the focus on the control.

**ENT-A4** The list of bills and the page of a bill are added to `PAGES`; the page with parts
of "Allgemeine Informationen" open has its own test. So all three get the layout and axe checks
on every screen size, light and dark.

## Out of scope

* Finding and analysing all bills automatically; daily updates of bills.
* The further course of a bill (readings, committee version, Bundesrat, publication) and the
  link from a bill to the later publication in the Bundesgesetzblatt.
* Bills of Fraktionen and of the Bundesrat, bills that create a new law, Referentenentwürfe of
  ministries, Änderungsanträge.
* Changes to the Inhaltsübersicht, to Anlagen and to headings of Teile and Abschnitte – as for
  publications.
* The Begründung next to each instruction in the comparison (decision 3).
* The Stellungnahme of the Normenkontrollrat.

## Engine fixes before the prototype

Decision 2: the failures are fixed first. They are fixes of `engine.py` and `model.py`, not
part of the reader-facing requirements. Each gets a test in `tests/test_core.py` with the real
wording from the table above:

1. "Satz N Nummer M": find the sentence that introduces a list and then the number in it.
2. Sentences of a § without Absätze.
3. Split sentences after "Satz 1.", "Absatz 3." and similar when a new sentence follows.
4. Lists that NeuRIS delivers as table rows are read as Nummern.
5. For bills the direction is always "berechnet" (ENT-8).
6. Added 2026-11-10: "Nach § 135d wird der folgende Achte Teil eingefügt" (Artikel 1 Nummer 49,
   likewise Nummer 65 with § 191a) was not understood, so § 135e and § 191a were missing. The
   parser expected the word for the unit right after "der folgende". Older laws such as the
   Baugesetzbuch count their parts with words ("Achter Teil"), newer ones with numbers
   ("Teil 8", Handbuch der Rechtsförmlichkeit); both are read now. The headings in the quoted
   text go with the § after them (ENT-18). Before, a heading between two new §§ ended up in the
   text of the first one (BGBl. 2026 I Nr. 320, Artikel 5: "Unterabschnitt 2 Ausgehende
   Ersuchen" at the end of § 91r). A new part without a § of its own is not evaluated.

The line assembly for Drucksachen (finding 2) is part of the new PDF profile and is tested with
the real lines of Art. 1 Nr. 27 a) aa).

## Decisions

Owner, 2026-11-09:

1. Compare with the current law text and warn when it is newer than the bill (ENT-9).
2. Look into the 10 failures before the prototype (table above, section "Engine fixes").
3. Begründung and Vorblatt are not part of the comparison; they are kept under "Allgemeine
   Informationen" (ENT-11, ENT-12).
4. The category is called "Gesetzentwürfe", as the Bundestag writes it.

Owner, 2026-11-10:

5. The heading of a new part of the law is shown above its first § (ENT-18).

## Open questions

None. The owner accepted the spec on 2026-11-09 as written; the five questions that were still
listed are closed with what the requirements and proposals said:

1. *How much of the Begründung?* All of it, as ENT-12 says – but in parts that are loaded only
   when opened, so the page stays small on slow connections.
2. *Is this bill still open?* Not tracked; ENT-6 says so.
3. *Search.* Unchanged: it finds publications only.
4. *Data.* `bundesdiff/entwuerfe.txt` lists the Drucksachen; `bundesdiff export` analyses each
   once, keeps the result in the store under `drafts/` and writes `data/entwuerfe.json`,
   `data/entwurf/<wp>/<number>.json` and `…-info.json`.
5. *Navigation.* A fourth entry after "Veröffentlichungen" (NAV-1, PTL-6 changed); the start
   page stays the list of Veröffentlichungen.

## Result on the real bill

With the engine fixes, 276 of the 335 instructions of Drucksache 21/6588 are shown in the
comparison (before: 220 with the unchanged code, 265 with the line assembly alone, 274 until
the new Achter and Zehnter Teil of the Baugesetzbuch were read, fix 6). 58 are not evaluated
(Inhaltsübersicht, Anlagen, changed headings of Teile, unknown wordings). One does not
fit: Artikel 4 Nummer 12 "c) Satz 8 wird … ersetzt" – a slip in the bill itself, which should
read "cc)" under Absatz 3. bundesdiff shows it as "nicht anwendbar" instead of guessing.
