# 017 Analyse again when a law could not be loaded

Status: done
Prefix: RTY

## Problem

A reader opens BGBl. 2026 I Nr. 326 (Approbationsordnungen) and finds no comparison at all: each
of its five Artikel says "Fehler bei der Suche des Gesetzes: timed out Die Änderungen werden
deshalb nur im Wortlaut angezeigt." The message is technical, partly English, and it stays
forever. The cause was brief: during the nightly run on 2026-10-30, gesetze-im-internet.de did
not answer, so the current text of these laws could not be loaded. A publication is analysed only
once. Only an analysis that failed as a whole is retried after 24 hours; Artikel whose law could
not be loaded are never tried again.

On 2026-11-10 this affects 43 of the 450 publications on the site, with 1,145 instructions that
are shown only in their wording. The bill of spec 016 had the same problem in CI (Baugesetzbuch,
PlanZV, VwGO) and was analysed by hand.

## Requirements

**RTY-1** If the current text of a law could not be loaded because a source did not answer in
time, answered with a server error, or could not be reached, that Artikel is analysed again by
the next daily run – at the earliest 20 hours after the last try, because the daily run does not
start at the same minute every day. The rest of the publication stays as it is (decision 1).

**RTY-2** A law that the sources answered for but do not contain ("„…“ wurde in der
Rechtsinformationsplattform nicht gefunden.") is not retried: trying again would give the same
answer (decision 3).

**RTY-3** bundesdiff keeps trying for 7 days (decision 2): the last try is the daily run on the
seventh day after the first failure, the date that RTY-4 names. If it fails too, the failure is
final and the Artikel says so.

**RTY-4** While bundesdiff is still trying, the Artikel says in plain German what happened and
what comes next, without technical terms: "Der aktuelle Text dieses Gesetzes konnte bei der
Auswertung nicht geladen werden, weil die Quelle nicht antwortete. bundesdiff versucht es täglich
erneut, bis zum 17.11.2026. Bis dahin stehen die Änderungen nur im Wortlaut der Veröffentlichung."
(The date is that of the last try.) After the last try: "Der aktuelle Text dieses Gesetzes konnte nicht geladen werden. Die Änderungen
stehen deshalb nur im Wortlaut der Veröffentlichung." For a bill the last sentence of each
message says "im Wortlaut des Entwurfs".

**RTY-5** The 43 publications already stored with such failures are found by their stored
message ("Fehler bei der Suche des Gesetzes: …") and are retried by the same rule, without a
manual step. Their 7 days start with the first retry.

**RTY-6** Bills (spec 016) follow the same rule.

**RTY-7** Retries count towards the limit of analyses per run (50); new publications come first
(decision 4).

## Accessibility

The message uses the existing error box of an Artikel: text, not colour alone, read by screen
readers in its place before the comparison. Nothing else changes for readers.

## Out of scope

* Laws that are not found although they exist, because their name is written differently (e.g.
  "Strafprozessordnung" in the instruction, "Strafprozeßordnung" in the sources). That is a
  question of matching names, not of retrying – a spec of its own.
* Retries within one run: every request is already tried 3 times (RES-8).

## Notes for the implementation

The analysis records per Artikel that the lookup failed for a network reason, when it was tried
and how often. `bundesdiff export` (and `drafts.update`) re-run only those Artikel and merge them
into the stored result. Stored results without these fields are recognised by their message
(RTY-5). A re-analysed Artikel may come out "rückgerechnet" if the law has been updated in the
meantime; that is the normal behaviour for any late analysis. A lookup that breaks for another reason (an
error in bundesdiff) is not retried; its message now begins "Bei der Suche des Gesetzes trat ein
Fehler auf:", so it is not taken for an old failure. The search for short titles on
gesetze-im-internet.de no longer skips pages that did not load, which made a timeout look like
"nicht gefunden".

## Decisions

Owner, 2026-11-10, all as proposed:

1. Only the failed Artikel are analysed again; comparisons already shown stay as they are.
2. bundesdiff keeps trying for 7 days.
3. "nicht gefunden" is not tried again.
4. Retries count towards the 50 analyses per run, new publications first.
5. The list of publications does not mark an issue that is still being completed; only the
   Artikel says it.

## Open questions

None.
