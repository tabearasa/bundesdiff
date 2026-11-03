# bundesdiff

[![Tests](https://github.com/tabearasa/bundesdiff/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/tabearasa/bundesdiff/actions/workflows/tests.yml)
[![License: MIT](.github/badges/license.svg)](LICENSE)

**Goal:** everyone, not only lawyers, can see what a new federal law changes.
A web app that shows what a Bundesgesetzblatt publication actually changes, as a side-by-side
diff (Synopse) of the old and new wording of every affected paragraph.

Verkündungen on [recht.bund.de](https://www.recht.bund.de) are published only as PDFs of
*Änderungsbefehle*, e.g. "§ 2 Absatz 1 wird durch den folgenden Absatz 1 ersetzt: „…“".
bundesdiff reads these instructions, applies them to the consolidated law text and renders
the result.

## Running it

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run bundesdiff serve               # live app, http://127.0.0.1:8000
uv run bundesdiff serve --port 8765

uv run bundesdiff export --site _site # static website with precomputed data (last 365 days)
python3 -m http.server -d _site 8080  # view it locally

uv run bundesdiff prune --days 365 --archive archiv/old.tar.gz  # move older data into an archive
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | listen address of `serve` |
| `BUNDESDIFF_CACHE` | `~/.cache/bundesdiff` | HTTP cache (disposable) |
| `BUNDESDIFF_DATA` | = cache dir | analysis results and stored law versions (worth keeping) |
| `BUNDESDIFF_WATCH_MINUTES` | `1440` | `serve` only: how often new issues are analyzed in the background (`0` disables) |

## Tests

```sh
uv run playwright install chromium   # once
uv run pytest                        # all tests, offline (about 45 s)
uv run pytest tests/frontend -k phone  # e.g. only the phone layouts
uv run playwright install firefox webkit
uv run pytest tests/frontend --browser firefox   # the same tests in Firefox (or webkit)
```

* `tests/test_specs.py`: every requirement of an accepted spec in `specs/` has a test
  (`@pytest.mark.spec("ID")`).
* `tests/test_core.py`: parsing of amendment instructions, applying and reversing them, diffing.
* `tests/frontend/`: the web app in a real browser (Playwright, Chromium), with fixed test data
  from `tests/frontend/fixtures/` and a fixed clock.
  * `test_phone.py`: the phone layout (round buttons, menu, the timeline as a lens), the blurred
    page behind windows and the shapes of controls (specs 004, 005, 007).
  * `test_behaviour.py`: what readers do: search, filter, open a publication, switch views,
    fold, tabs, dialogs, light/dark, phone layout, keyboard, browser back, live API mode.
  * `test_layout.py`: every kind of page on desktop, tablet, phone (portrait and landscape)
    and a 320 px phone, in light and dark mode, at 200 % and 400 % browser zoom and with wider
    text spacing, checked by `layout.js` (no horizontal scrolling, no cut-off or overflowing
    text, no overlapping or covered controls, click targets ≥ 24 px, text ≥ 12 px, no words torn
    apart without a hyphen) and by
    axe-core (all WCAG 2.2 A/AA rules: contrast, labels, ARIA, landmarks). Every test also fails on JavaScript errors and failed requests.
  * Screenshots of all combinations land in `test-results/screenshots/`. Failing tests leave
    a screenshot and a Playwright trace in `test-results/failures/`.
* GitHub Actions (`.github/workflows/tests.yml`) runs everything on every push in Chromium,
  Firefox and WebKit (Safari) and uploads the screenshots as `frontend-screenshots-<browser>`.

## Automatic updates with GitHub Actions

`.github/workflows/update.yml` runs once a day at 19:23 UTC (and manually via *Run workflow*):

1. Checks out the **`data` branch** (created on the first run) into `store/`.
2. `bundesdiff export`: analyzes up to 50 new publications from the **last 365 days**,
   newest first. The first backfill (about 400 issues of Teil I) would take about 8 days; start it
   once by hand with *Run workflow* and `max_new` = 500 instead. Failed
   analyses are retried after 24 hours.
3. `bundesdiff prune`: moves everything **older than one year** into a
   `bundesdiff-archiv-YYYY-MM-DD.tar.gz` file and deletes it from the `data` branch. This
   covers analysis results, and law versions except the newest version of each law, which
   is still needed as the "before" text. The file is attached to the monthly
   **GitHub Release** `archiv-YYYY-MM`.
4. Commits the updated `data` branch.
5. **Git history, once a month**: the complete history of `data` is saved as
   `historie-bis-YYYY-MM.bundle` in the monthly release and verified. The branch is then
   replaced by a single commit with the current state and force-pushed. The repository
   stays the size of the current year's data, and no history is lost. To restore it:
   ```sh
   git fetch historie-bis-2026-10.bundle data:data-alt   # old history as branch data-alt
   ```
6. Uploads the static website as the workflow artifact **`site`** (kept for 7 days).
   Download it, unzip, and run `python3 -m http.server -d site`.

Law versions are stored gzipped and only when their content changed, so even within a
month the branch grows slowly.

**GitHub Pages** is off. On the Free plan, Pages is not available for private repositories,
and on paid plans the site would be publicly reachable even when the repository is private.
To publish, set the repository variable `DEPLOY_PAGES=true` and select *GitHub Actions* as
the Pages source. The site is only published when the tests (`tests.yml`) passed for the
current commit. Before making it public, add an Impressum (operator's name and address) to the
about page (`tpl-about` in `bundesdiff/static/index.html`). The static frontend only reads relative `data/…` files, so any static web
host works too.

## How it works

1. **Publications**: from the RSS feed of Teil I (federal laws and ordinances; Teil II, international treaties, is deliberately left out). The PDF is fetched via its ELI URL.
2. **PDF → text** (`pdftext.py`, PyMuPDF): drops running headers, page numbers and footnotes
   (7 pt) and keeps each line's indentation.
3. **Instructions** (`amendments.py`): splits the issue into Artikel, finds the amended law
   (from the citation such as "BGBl. I S. 1870", or its name), and parses the numbered
   instruction list ("1.", "a)", "aa)", including nested "wird wie folgt geändert:"
   contexts) into operations:
   word-level replacement/deletion/insertion, replacement/insertion/deletion/appending of
   Absätze, Nummern, Buchstaben and whole §§, sentence-level changes, new headings and
   renumbering.
4. **Current law text** (`sources.py`): NeuRIS (`testphase.rechtsinformationen.bund.de`,
   LegalDocML) when the law is there. Otherwise gesetze-im-internet.de, which has every law.
5. **Before or after?** (`engine.py`): the consolidated text is often updated within a day.
   For each §, the instructions are checked against the current text to tell whether the
   change is already in it.
   * not yet in it → old = current text, new = text with instructions applied (**berechnet**)
   * already in it → new = current text, old = text with instructions reversed (**rückgerechnet**).
     Word-level changes reverse exactly. Wording that was replaced or deleted comes from an
     earlier version: one stored locally, or the Internet Archive's copy of the § on
     gesetze-im-internet.de from before the publication date.
6. **Diff** (`diffing.py`): line-by-line by unit, then word-level within changed lines.

The background watcher analyzes every new issue soon after it appears. That stores the
affected laws *before* they are consolidated, so later views use exact local old versions
rather than archive snapshots.

## Limitations

* Inhaltsübersichten, Anlagen, tables and decimal-numbered items ("Nummer 7.2.1") are listed
  but not applied.
* New standalone laws (Stammgesetze) and Bekanntmachungen are shown as plain text.
* When the old version comes from an Internet Archive snapshot, the snapshot can predate other
  amendments. The UI names the snapshot date in that case.
* NeuRIS is still in a test phase. Unusual wording can make an instruction fail; it is then
  marked **fehlgeschlagen**.
* Not legally binding. Only the official Bundesgesetzblatt is authoritative.

## Legal basis of the data use

* Laws, ordinances and official announcements are *amtliche Werke* and not protected by
  copyright (§ 5 UrhG).
* The Bundesgesetzblatt on recht.bund.de may be reused under § 2 Abs. 3 VkBkmG in
  conjunction with § 7 Datennutzungsgesetz.
* gesetze-im-internet.de offers its XML for automated processing and allows deep links.
* The NeuRIS API (test phase) explicitly allows building applications on it; its limit of
  600 requests per minute is far above what bundesdiff uses (all responses are cached).
* bundesdiff is not an official service and gives no individual legal advice. Every page says
  that only the official Bundesgesetzblatt is binding.

## Contributing and ideas

Ideas are welcome, also without code: see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The laws and the Bundesgesetzblatt themselves are official works and not
protected by copyright (§ 5 UrhG).
