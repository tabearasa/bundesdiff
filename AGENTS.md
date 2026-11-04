# bundesdiff – working rules

## Purpose: German law changes, accessible to everyone

bundesdiff exists so that anyone, not only lawyers, can see what a new law changes. Every
decision on this project is judged by one question: **can every reader, on every device, read
this without errors?** When a feature and accessibility conflict, accessibility wins; a
feature that cannot be made accessible is not shipped.

What that means in practice:

* **Every device.** Phones from 320 px wide up to large desktops, portrait and landscape,
  touch, mouse and keyboard. Chromium, Firefox and WebKit (Safari on iPhone/iPad).
* **Every reader.** WCAG 2.2 level AA as the minimum: contrast ≥ 4.5:1, everything usable
  by keyboard with visible focus, works with screen readers (real HTML elements first, ARIA
  only where HTML has nothing), works with text enlarged to 200 % and with wider letter and
  line spacing, no information by colour alone (old/new text is also marked by symbols and
  struck-through/underlined), respects `prefers-reduced-motion` and `prefers-color-scheme`.
* **Plain German.** The UI is written for readers without legal training: short sentences,
  everyday words, every legal term explained where it appears. Errors say what happened and
  what the reader can do.
* **Slow or old connections.** The static site has no build step, no framework and no
  external requests: no CDN fonts, no trackers, no cookies. Pages stay usable while data
  loads and say clearly when something could not be loaded.
* **Conservative paper look, laid out with care.** bundesdiff looks like a well-set printed
  page: serif type, paper colours, thin rules. Every button, badge and label is aligned
  exactly – text centred in its frame, items on a common baseline, equal spacing. No emoji or
  pictographic symbols (☾ ☀ ✕ ↗ …); controls are named with words, only typographic marks of
  printed text are used (§ – − + ± … ↑ ▾). Checked by `tests/frontend/centering.py` and
  `test_no_emoji_*` (A11Y-12, A11Y-13). Anything that looks slightly off in a screenshot is a
  bug, even if no check catches it – then add a check.
* **Correct before complete.** If a change cannot be computed reliably, show that it is
  uncertain or failed instead of showing a wrong text. Every page says that only the official
  Bundesgesetzblatt is binding.

## Spec first, then tests, then code

Every feature or change in behaviour starts as a spec in `specs/` (workflow and rules in
`specs/README.md`, template `specs/_template.md`):

1. Write or change the spec, `Status: draft`, with open questions listed – do not guess
   answers to them.
2. Stop and let the owner review it. Implement nothing from a draft.
3. When accepted: write the tests first, each marked `@pytest.mark.spec("ID")`, then the code.
4. Set `Status: done`; if the implementation deviated, update the spec in the same change.

`tests/test_specs.py` fails if a requirement of an accepted spec has no test.
`specs/000-accessibility.md` applies to every feature. Pure bug fixes that restore specified
behaviour need no new spec, but a test with the spec ID.

## Every frontend change comes with tests

When you add or change anything in `bundesdiff/static/` (HTML, CSS, JS):

1. Add or update a test in `tests/frontend/test_behaviour.py` that does what a reader would do
   with the feature (click, type, navigate) and checks what they should see.
2. A new kind of page or state (e.g. a new dialog, a new view mode): also add it to `PAGES` in
   `tests/frontend/conftest.py` or to `test_layout.py`, so it gets the layout and
   accessibility checks on every screen size, in light and dark mode.
3. Do not run the tests yourself. **The tests are always run by the `bug-hunter` agent**
   (`.claude/agents/bug-hunter.md`): launch it after every change, name the pages and
   features you changed. It runs everything in Chromium and Firefox, looks at the
   screenshots, tries to break the feature and reports bugs. It never edits tests or code.
4. Fix what it reports – in the code, not by weakening a check. If a check is truly wrong, fix
   the check in `tests/frontend/layout.js` / `centering.py` and say why. A finding that no
   spec covers gets a test first. Then launch it again, until it reports no failures and no
   findings. Only then is a change done.
5. WebKit (Safari) runs in CI, which tests all three engines; locally it only works on systems
   Playwright supports for WebKit (Ubuntu, macOS – not Debian 13).

The layout checks (`tests/frontend/layout.js`, plus `centering.py` for content off-centre in its frame) catch horizontal scrolling, text that does not
fit its box, overlapping or covered controls, click targets under 24 px, text under 12 px and words
split across lines without a hyphen. They run at 320 px (smallest phone), phone, phone landscape, tablet and desktop, at 200 % and
400 % browser zoom and with the wider WCAG text spacing. axe-core checks the WCAG 2.2 A/AA rules
(contrast, labels, ARIA, landmarks).

New fields in the analysis JSON: rebuild the test data with
`uv run python tests/frontend/make_fixtures.py` (see the list of fixtures in that file).

## Other

* Python tests for parsing and diffing: `tests/test_core.py`. A change to parsing or diffing
  needs a test with the real wording that triggered it.
* New dependencies for the frontend are not allowed; new Python dependencies only when the
  standard library cannot do it reasonably.

## Commands

```sh
uv sync
uv run bundesdiff serve [--port 8765]                            # live app
uv run bundesdiff export --site _site                            # static site, last 365 days
uv run bundesdiff prune --days 365 --archive archiv/old.tar.gz   # move older data into an archive
```

Tests (run only by the `bug-hunter` agent, see above):

```sh
uv run playwright install chromium firefox webkit
uv run pytest                                      # all tests, offline (about 45 s)
uv run pytest tests/frontend -k phone              # e.g. only the phone layouts
uv run pytest tests/frontend --browser firefox     # or webkit
```

## Test layout

* `tests/test_specs.py`: every requirement of an accepted spec has a test.
* `tests/test_core.py`: parsing of amendment instructions, applying and reversing them, diffing.
* `tests/frontend/`: the web app in a real browser (Playwright), with fixed test data from
  `tests/frontend/fixtures/` and a fixed clock. Every test also fails on JavaScript errors and
  failed requests.
  * `test_phone.py`: phone layout (round buttons, menu, timeline as a lens), blurred page
    behind windows, shapes of controls (specs 004, 005, 007).
  * `test_behaviour.py`: what readers do: search, filter, open a publication, switch views,
    fold, tabs, dialogs, light/dark, phone layout, keyboard, browser back, live API mode.
  * `test_layout.py`: every kind of page at every screen size, light and dark, 200 %/400 %
    zoom and wider text spacing, checked by `layout.js` and axe-core.
  * Screenshots of all combinations land in `test-results/screenshots/`; failing tests leave
    a screenshot and a Playwright trace in `test-results/failures/`.
* CI (`.github/workflows/tests.yml`) runs everything on every push in Chromium, Firefox and
  WebKit and uploads the screenshots as `frontend-screenshots-<browser>`.

## How the analysis works

1. **Publications**: RSS feed of Teil I (Teil II, international treaties, is deliberately left
   out). The PDF is fetched via its ELI URL.
2. **PDF → text** (`pdftext.py`, PyMuPDF): drops running headers, page numbers and footnotes
   (7 pt) and keeps each line's indentation.
3. **Instructions** (`amendments.py`): splits the issue into Artikel, finds the amended law
   (from the citation such as "BGBl. I S. 1870", or its name) and parses the numbered
   instruction list ("1.", "a)", "aa)", nested "wird wie folgt geändert:") into operations:
   word-level replacement/deletion/insertion; replacement/insertion/deletion/appending of
   Absätze, Nummern, Buchstaben and whole §§; sentence-level changes; new headings;
   renumbering.
4. **Current law text** (`sources.py`): NeuRIS (`testphase.rechtsinformationen.bund.de`,
   LegalDocML) when the law is there, otherwise gesetze-im-internet.de.
5. **Before or after?** (`engine.py`): the consolidated text is often updated within a day, so
   each § is checked for whether the change is already in it.
   * not yet → old = current text, new = instructions applied (**berechnet**)
   * already → new = current text, old = instructions reversed (**rückgerechnet**). Word-level
     changes reverse exactly; replaced or deleted wording comes from a stored earlier version
     or the Internet Archive's copy on gesetze-im-internet.de from before the publication date.
6. **Diff** (`diffing.py`): line by line per unit, then word by word within changed lines.

The background watcher of `serve` analyzes each new issue soon after it appears, so the
affected laws are stored *before* they are consolidated and later views use exact local old
versions instead of archive snapshots.

## Daily update workflow

`.github/workflows/update.yml` runs daily at 19:23 UTC (and manually via *Run workflow*):

1. Checks out the `data` branch (created on the first run) into `store/`.
2. `bundesdiff export`: analyzes up to 50 new publications from the last 365 days, newest
   first. For the first backfill (about 400 issues) run it by hand with `max_new` = 500.
   Failed analyses are retried after 24 hours.
3. `bundesdiff prune`: moves everything older than a year into
   `bundesdiff-archiv-YYYY-MM-DD.tar.gz`, attached to the monthly GitHub Release
   `archiv-YYYY-MM`. The newest version of each law stays, as it is still the "before" text.
4. Commits the updated `data` branch. Law versions are stored gzipped and only when changed.
5. Once a month the full history of `data` is saved as `historie-bis-YYYY-MM.bundle` in the
   monthly release, verified, and the branch is squashed to one commit and force-pushed.
   Restore with `git fetch historie-bis-2026-10.bundle data:data-alt`.
6. Uploads the static site as workflow artifact `site` (kept 7 days).

**GitHub Pages**: the site is published by the `deploy-pages` job of every update run, while
the repository variable `DEPLOY_PAGES` is `true` and *GitHub Actions* is the Pages source. It
deploys only when `tests.yml` passed for the commit. The site has no Impressum: the owner
judges it a private, non-commercial project (decision 2026-11-04). The frontend only reads
relative `data/…` files, so any static host works too.
