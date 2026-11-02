# 002 Search and timeline instead of the sidebar

Status: done
Prefix: SRCH, TL

## Problem

The sidebar is a long list in a narrow column. It takes a third of the screen while reading, it
is hidden on phones while reading, and the only way to find something is to scroll or type into
a filter that matches titles. But readers come with a question ("Was ändert sich bei der
Rente?", "Was ist mit dem Designgesetz?"), not with the title of a Bundesgesetzblatt issue.
Two separate needs are mixed in one list:

1. **Finding** a law change by topic, law name or abbreviation → a search.
2. **Following** what happened recently, in order → a timeline.

The sidebar goes away. Search lives in the navbar on every page (like the documentation sites
built with Zensical/Material for MkDocs: a field with "Strg K" that opens a search window). The
timeline becomes the start page. A publication is read full width, like a page in a book.

## Brainstorm (not requirements – the owner picks, see open questions)

**Search window**
- In the navbar a field-like button "Suchen … Strg K" (on phones a drawn magnifying glass).
  Click, `Strg K`/`⌘ K` or `/` opens a search window over the page; `Esc` closes it.
- Results appear while typing, best first, grouped: *Gesetze* (changed laws, e.g.
  "Designgesetz (DesignG) – geändert durch 3 Veröffentlichungen"), *Veröffentlichungen*,
  *Themen* (Sachgebiete like "Rentenversicherung").
- The matching words are highlighted (underlined + bold, not colour alone).
- Arrow keys move through the results, `Enter` opens; the window remembers the last searches.
- Forgiving: "ae" finds "ä", upper/lower case ignored, part of a word is enough ("steuer" finds
  "Einkommensteuergesetz"), abbreviations ("EStG", "SGB VI"), citation ("BGBl. 2026 I Nr. 322").
- Everyday words: a small hand-made list maps words readers use to legal terms ("Rente" →
  Sozialgesetzbuch VI, "Miete" → BGB Mietrecht, "Bürgergeld" → SGB II).
- Possible later: search the changed wording itself (full text), loaded only when asked for.

**Timeline (start page)**
- One column in the middle, like the table of contents of a yearbook: a thin vertical rule,
  months as chapter headings, days as marks on the rule, the date in the margin.
- Each entry: type in small caps (Gesetz / Verordnung …), title, topics, and what it changes
  ("ändert 5 Gesetze", "tritt am 1. Januar 2027 in Kraft").
- Above it: filters as quiet text toggles (Art, Thema) and a strip of
  months to jump to.
- Variant: a second view **"Was ändert sich demnächst?"** – ordered by the date a change takes
  effect instead of the publication date. Very useful for the public, but the in-force date must
  be read reliably from the text ("Correct before complete"), so maybe a later spec.

**Reading a publication**
- Full width, centred like a book page; the contents bar stays.
- At the end: "← Ältere Veröffentlichung" / "Neuere Veröffentlichung →" so one can read on
  through the timeline without going back.

## Requirements

### Layout

**TL-1** There is no sidebar any more. Every page has the full width below the navbar; a
publication is set as one centred page, like a book page.

**TL-2** At the end of a publication there are two links, "← Ältere Veröffentlichung" and
"Neuere Veröffentlichung →" (only those that exist), to read on through the timeline.

### Search

**SRCH-1** The navbar has a search button on every page (on phones a round button at the
bottom, PTL-5). From 1100 px it looks like a field:
a drawn magnifying glass, "Suchen …" and the hint "Strg K" (on a Mac "⌘ K"); below 1100 px only
the magnifying glass (narrower, the field would push the navbar out of the screen). Screen
readers hear "Suchen".

**SRCH-2** Click/tap, `Strg K` / `⌘ K` and `/` open the search window; `/` only when the reader
is not typing in another field. `Esc` or "Schließen" (the drawn x, SHAPE-7) closes it and returns the focus to the button
that opened it.

**SRCH-3** The search looks through: titles, topics (Sachgebiete), type, ministry, the citation
("BGBl. 2026 I Nr. 322", also "2026 I 322") and the names and abbreviations of every law a
publication changes ("Designgesetz", "DesignG"). Not the changed wording itself.

**SRCH-4** Results appear while typing (from the first letter), at most 50 ms after the last key
on a mid-range phone, best matches first, grouped under "Gesetze" (a changed law, with the
publications that change it, newest first) and "Veröffentlichungen".

**SRCH-5** Forgiving matching: upper/lower case ignored; "ae/oe/ue/ss" find "ä/ö/ü/ß" and the
other way round; part of a word is enough ("steuer" finds "Einkommensteuergesetz"); several words
must all match, in any order.

**SRCH-6** The matching letters are highlighted in bold and underlined (not by colour alone).

**SRCH-7** Arrow keys move through the results, `Enter` opens the selected one, the selection is
always scrolled into view. Without a query the window shows the last five searches (stored only
in this browser) and can clear them ("Verlauf löschen").

**SRCH-8** No result: "Nichts gefunden für „…“." with a hint what to try (shorter word, law
abbreviation, topic).

**SRCH-9** The search index is part of the static data, loads with the list and is at most
300 KB (compressed) for a year of publications; the search works offline once the page is loaded.

### Timeline

**TL-3** The start page is the timeline: one column in the middle with a thin vertical rule;
months are headings ("Oktober 2026"), each day a mark on the rule with the date beside it, newest
first. Each entry shows the type in small caps, the title, the topics, and "ändert 5 Gesetze" /
"ändert kein Gesetz". *(Amended by spec 004, PTL-2/PTL-3: each entry is framed, on its own line to the rule,
up to four topics, of more the first three and how many more; the entry in the middle of the screen is the card.)*

**TL-4** Above the timeline: the filter "Art" (Gesetz, Verordnung, Sonstiges) and a row of the
months to jump to. The filter is kept in the address, so a filtered view can be shared; a type
in other letters ("gesetz") is the same type, an unknown one is ignored. Choosing a type keeps
the focus on the list and screen readers hear how many publications are shown ("16
Veröffentlichungen der Art „Gesetz“"; in "Was ändert sich demnächst?" how many coming dates it lists under "Demnächst", "2 kommende
Termine für Veröffentlichungen der Art „Verordnung“", or "Keine kommenden Termine …");
"Was ändert sich demnächst?" names the chosen type when it
has nothing to show.
*(Amended 2026-11-01: the checkbox "nur Gesetzesänderungen" was removed – readers could not tell
it from "Art", and every entry already says "ändert 2 Gesetze" or "ändert kein Gesetz". Old links
with `nur=aenderungen` show the whole timeline.)*

**TL-5** A switch above the timeline chooses the order: "Nach Veröffentlichung" (default) or
"Was ändert sich demnächst?".

**TL-6** "Was ändert sich demnächst?" lists, from today forward, the dates on which changes take
effect, each with the publications and articles that take effect then ("tritt in Kraft:
Artikel 1 – Designgesetz"). Past dates of the last 30 days follow under "Kürzlich in Kraft
getreten" ("Kürzlich in Kraft oder außer Kraft getreten" when something expired), in the past
tense ("ist in Kraft getreten: …", "ist außer Kraft getreten: …"). Without future dates the list
says "Es sind keine kommenden Termine bekannt, an denen etwas in Kraft oder außer Kraft tritt."
(with a chosen type: "Für Veröffentlichungen der Art „Sonstiges“ sind keine kommenden Termine
bekannt, …"). *(Amended 2026-11-01:
the view calls its dates "Termine" throughout; "Kürzlich geändert" and "Änderungen" did not fit
entries that say "ist in Kraft getreten".)*

**TL-7** The in-force dates are read from the in-force article (Inkrafttreten) of each
publication: fixed dates ("am 9. Dezember 2027"), "am Tag nach der Verkündung" (= publication
date + 1 day), "am ersten Tag des … folgenden Kalendermonats", and per-article exceptions ("Artikel 5
tritt mit Wirkung vom 27. September 2026 in Kraft"). A date that cannot be read with certainty is
not guessed: the entry appears under "Datum nicht sicher erkannt" with the original sentence.
The same goes for *what* takes effect: when it cannot be read with certainty, the entry names
nothing and says "Was in Kraft oder außer Kraft tritt, steht im Wortlaut".
Every date can show the sentence it was read from ("Wortlaut", folded).

**TL-8** Every page of this view says that the dates are read automatically and only the
Bundesgesetzblatt is binding.

## Accessibility

- The search window is a real modal dialog: focus moves into the field when it opens, stays in
  the dialog, and returns to the search button when it closes.
- The results are announced ("12 Treffer") via a live region; the field is a combobox with
  `aria-activedescendant` for the arrow keys, so screen readers follow the selection.
- `Strg K` is shown as a hint only; everything also works by click/touch. `/` does not fire while
  typing in another field.
- Phones: the search window fills the screen, results are large touch targets.
- The timeline is an ordered list with headings per month, so screen readers can jump by
  heading; the vertical rule and day marks are decoration (hidden from screen readers).
- Same baseline as every page: 320 px, 200/400 % zoom, text spacing, light/dark, no emoji, the
  magnifying glass drawn as thin lines like the sun/moon.

## Out of scope

Server-side search, any external search service, tracking of what people search for.

## Decisions

- Search covers titles, topics, ministry, citation and changed law names, not the full wording
  (owner, 2026-10-30).
- The start page is the timeline (owner, 2026-10-30).
- "Was ändert sich demnächst?" is part of this spec (owner, 2026-10-30).
- Everyday words ("Rente" → SGB VI) come in a later spec (owner, 2026-10-30).
- The in-force dates are read in Python when the data is built and stored in the data files
  (owner, 2026-10-30).
- The navbar entry keeps its name "Veröffentlichungen" and leads to the timeline (owner, 2026-10-30).

## Open questions

None.
