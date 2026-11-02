# 011 The page of a publication that is not analysed yet

Status: draft
Prefix: NAP

## Problem

Opening a publication that is in the list but not yet analysed (`#/1/2026/322`) shows only an
error box and the pager. There is no heading, no title, and the date is missing. The reader
cannot tell which publication this is. The box says "Den amtlichen Text finden Sie schon jetzt
auf recht.bund.de", but there is no link to it. (Found by the bug-hunter, 2026-11-01.)

## Requirements

**NAP-1** The page has the same header as an analysed publication, built from the list entry:
the citation ("BGBl. 2026 I Nr. 322"), the title as `h1`, the kind ("Gesetz", "Verordnung" …)
and the date.

**NAP-2** Below the header, a notice (not styled as an error) says: "Diese Veröffentlichung ist noch nicht
ausgewertet. Die Daten werden einmal täglich am Abend aktualisiert – bitte morgen noch einmal
vorbeischauen." (UPD-3 stays satisfied.)

**NAP-3** A link "Amtlicher Text im Bundesgesetzblatt" leads to the publication on
recht.bund.de and opens in the same tab. The link text says that it leaves bundesdiff: "(externe
Seite)".

**NAP-4** The same header and link appear for a publication whose analysis failed (ERR-2,
last case).

**NAP-5** The pager (TL-2) stays below.

## Accessibility

The page gets the layout and axe checks (add the state to `PAGES`); the focus goes to the
heading per PAGE-3.

## Out of scope

Analysing a publication on demand from the static site.

## Open questions

1. Is the URL on recht.bund.de for a publication known from the list data, or must
   `listing.entry` add it (a new field → rebuild the fixtures)?
2. Should "noch nicht ausgewertet" be marked on the page with a badge in the same style as
   the status badges, or as plain text only?
