# 014 When recht.bund.de cannot be reached

Status: done
Prefix: RES

Extends [003 Data updated once a day](003-daily-updates.md).

## Problem

The daily run first asks recht.bund.de which publications exist (the RSS feed of Teil I). If
that one request fails, the whole run stops: nothing is analysed, nothing is saved and the
website is not built or published. On 4 November 2026 this happened twice in a row
(`httpx.ConnectTimeout: The handshake operation timed out`), while recht.bund.de answered
normally from a computer in Germany. A reader then sees an old site, or – right after Pages
was switched on – no site at all, although the `data` branch holds a year of analyses.

At the same time the site must not pretend to be newer than it is: today the line
"Datenstand: …" shows when the site was *built*, not when the list of publications was last
fetched.

## Requirements

**RES-1** If fetching the list of publications fails because of a connection problem (no
connection, timeout, HTTP status 5xx or 429), the run tries again before it gives up: 4 tries
in all, waiting 1, 5 and 15 minutes in between. An answer
that arrives but cannot be read (e.g. broken XML) or lists no publication with a date of
the form YYYY-MM-DD (e.g. a maintenance page) is not retried; it counts as unreachable at once, so it never replaces the
saved list.

**RES-2** Every successful fetch saves the list of publications in the data store (`data`
branch), next to the analyses.

**RES-3** If the list still cannot be fetched after the last try, the run uses the list saved
by the last successful fetch, analyses nothing new, builds the website from it and from the
stored analyses, commits the data and publishes the site. The site then shows the same
publications, with the same texts, as after the last successful run.

**RES-4** `data/meta.json` records when the list of publications was last fetched
successfully. The line "Datenstand: …" on the start page shows that time in German time
("Datenstand: 30.10.2026, 07:23 Uhr"), not the time the site was built. A time that cannot be
read is never shown: then the build time is used, or "Datenstand unbekannt".

**RES-5** If that time is more than 36 hours old, the start page shows above the timeline:
„Die Liste der Veröffentlichungen ist vom 4. November 2026. Neuere Veröffentlichungen fehlen
hier vielleicht noch, weil recht.bund.de zuletzt nicht erreichbar war. Die amtlichen Texte
finden Sie immer auf recht.bund.de.“ (the date of the fetch in German time, „recht.bund.de“ as a link). The date is
compared with the reader's clock, so the notice also appears when the daily runs stop
altogether.

**RES-6** If there is no usable saved list either (first run, or the saved list is missing or
damaged), the run
stops with an error message that says in one line which address could not be reached, without
a Python traceback.

**RES-7** A run that published the site from the saved list ends as *failed* on GitHub (so the
owner gets an e-mail), but only after the data was committed and the site was published. Its
summary page says in one sentence that recht.bund.de could not be reached and the site shows
the saved list from <date>.

**RES-8** Every single request to a source (recht.bund.de, NeuRIS, gesetze-im-internet.de, the
Internet Archive) that fails with a connection problem as in RES-1 is tried 3 times in all,
waiting 2 and 10 seconds in between, before it counts as failed.

## Accessibility

**RES-A1** The notice of RES-5 is ordinary text in a box with a visible border, not shown by
colour alone; it is a paragraph a screen reader reads in page order (no live region – it is
there when the page loads). It fits at 320 px and 400 % zoom without horizontal scrolling and
passes the layout and axe checks in light and dark mode.

## Out of scope

* Notifying readers by other channels (e-mail, RSS of bundesdiff).
* The local server `bundesdiff serve`: it is a development tool; spec 014 covers only the daily
  GitHub run, which feeds the public site.
* Fixed alongside, without a requirement: the workflow step runs `uv run` without `--no-dev`
  and so downloads ruff and Playwright (about 60 MB) on every daily run.

## Decisions

* 4 tries for the list, waiting 1, 5 and 15 minutes (owner, 2026-11-04).
* A run published from the saved list counts as failed, after publishing (owner, 2026-11-04).
* Notice after 36 hours, text as in RES-5 (owner, 2026-11-04).
* Single requests to every source are retried quickly: RES-8 (owner, 2026-11-04).
* `bundesdiff serve` stays as it is (owner, 2026-11-04).

## Open questions

None.
