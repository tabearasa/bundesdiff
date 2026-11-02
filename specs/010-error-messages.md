# 010 Error messages in plain German

Status: draft
Prefix: ERR

## Problem

When something cannot be loaded, the error box shows the browser's own technical English text:
"Failed to fetch" (Chromium), "NetworkError when attempting to fetch resource." (Firefox),
"Internal Server Error". Readers without a technical background cannot tell what happened or
what to do. Other cases give the wrong message:
- When the list could not be loaded, search still answers "Nichts gefunden für „Steuer“. Versuchen
  Sie ein kürzeres Wort …", as if the list had been searched.
- A publication that does not exist (`#/1/2026/9999`) is reported as "konnte nicht ausgewertet
  werden".

CLAUDE.md asks that errors "say what happened and what the reader can do". (Found by the
bug-hunter, 2026-11-01.)

## Requirements

**ERR-1** No error message shows text from the browser or the server (exception messages, HTTP
status texts, English words). The technical detail goes to the browser console only.

**ERR-2** Each kind of failure has its own message, written as one sentence on what happened and one
sentence on what the reader can do:
- no connection / request failed: "bundesdiff konnte keine Verbindung herstellen." –
  "Prüfen Sie Ihre Internetverbindung und laden Sie die Seite neu."
- server error (HTTP 5xx) or unreadable data: "Die Daten konnten gerade nicht geladen werden."
  – "Bitte versuchen Sie es in ein paar Minuten noch einmal."
- publication not in the list (HTTP 404 and not in the list): "Diese Veröffentlichung gibt es
  in bundesdiff nicht." – "Vielleicht ist die Nummer falsch. Zur Übersicht: [Alle
  Veröffentlichungen]."
- in the list but not analysed yet: as today (UPD-3), see spec 011.
- analysis failed (stored error): "bundesdiff konnte diese Veröffentlichung nicht auswerten." –
  link to the official text.

**ERR-3** Where a retry makes sense (ERR-2, first two cases), the box has a button "Noch einmal
versuchen" that loads again without reloading the page.

**ERR-4** While the list of publications is missing, search does not claim "Nichts gefunden": it says
"Die Suche ist gerade nicht möglich, weil die Liste der Veröffentlichungen nicht geladen werden
konnte." and offers the same retry.

**ERR-5** Every error box is announced to screen readers (`role="alert"` for a failure after an
action of the reader, otherwise part of the page heading per spec 009) and the browser tab
says what happened (PAGE-1).

## Accessibility

Error boxes are not shown by colour alone: they start with a bold sentence and have a frame. The
retry button meets the 24 px target size and keeps focus after a failed retry.

## Out of scope

Offline caching (service worker).

## Open questions

1. Are the texts in ERR-2 right? They are suggestions to be reworded by the owner.
2. ERR-3: also retry automatically (e.g. once after 10 s), or only on request?
3. Should a 404 for a number newer than the newest known publication say "noch nicht
   erschienen oder noch nicht in bundesdiff" instead of "gibt es nicht"?
