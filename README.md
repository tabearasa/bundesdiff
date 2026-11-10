# bundesdiff

[![Tests](https://github.com/tabearasa/bundesdiff/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/tabearasa/bundesdiff/actions/workflows/tests.yml)
[![License: MIT](.github/badges/license.svg)](LICENSE)

> [!NOTE]
> This is a vibe-coded experiment mainly created from my phone through
> a remote controlled agent session and inspired by the LdN podcast
> episode [#499](https://talk.lagedernation.org/t/ldn-499-tabaksteuer-gesetzgebungsfehler/34944).

**See what a new federal law changes – old and new wording side by side.**

New laws in the Bundesgesetzblatt are published only as lists of instructions, e.g.
"§ 2 Absatz 1 wird durch den folgenden Absatz 1 ersetzt: „…“". To see what actually
changed, you have to apply them to the law yourself. bundesdiff does that for you and shows
every affected paragraph as a side-by-side comparison (Synopse), so that anyone, not only
lawyers, can follow it.

## Running it

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run bundesdiff serve                # live app at http://127.0.0.1:8000
uv run bundesdiff export --site _site  # static website with the last 365 days
python3 -m http.server -d _site 8080   # view the static website
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | where `serve` listens |
| `BUNDESDIFF_CACHE` | `~/.cache/bundesdiff` | downloads (safe to delete) |
| `BUNDESDIFF_DATA` | = cache dir | analyses and stored law versions (worth keeping) |
| `BUNDESDIFF_WATCH_MINUTES` | `1440` | how often `serve` checks for new issues (`0` = never) |

## Tests

```sh
uv run playwright install chromium   # once
uv run pytest                        # everything, offline, about 45 s
```

The frontend tests open every page in a real browser on phone, tablet and desktop sizes,
in light and dark mode and zoomed in, and check layout and accessibility (WCAG 2.2 AA).
GitHub Actions runs them in Chromium, Firefox and WebKit on every push.

## How it works

1. Fetch the new issues of Bundesgesetzblatt Teil I from [recht.bund.de](https://www.recht.bund.de).
2. Read the PDF and turn the amendment instructions into operations.
3. Load the current text of the amended law from NeuRIS or gesetze-im-internet.de.
4. Apply the instructions – or, if the law text already contains the change, reverse them
   to get the old wording.
5. Show old and new wording side by side, with the changed words marked.

## Gesetzentwürfe (prototype)

Besides published laws, bundesdiff shows one bill that is still before the Bundestag:
[Drucksache 21/6588](https://dserver.bundestag.de/btd/21/065/2106588.pdf), the bill to modernise
planning law (Baugesetzbuch and eleven other laws). A bill has the same form as a law, so the
same steps apply – with one difference: a bill is never in force, so the law as it stands is
always the "before" side and the bill's wording the "after" side. The page says clearly that it
is a draft, names the law version it was compared with, and keeps the bill's own summary and
reasoning (Vorblatt, Begründung) apart from the comparison.

Which bills are shown is a hand-kept list, `bundesdiff/entwuerfe.txt`. bundesdiff does not
follow what happens to a bill after its date. Details: [specs/016-gesetzentwuerfe.md](specs/016-gesetzentwuerfe.md).

## Limitations

* Tables of contents, annexes, tables and items like "Nummer 7.2.1" are listed but not applied.
* Completely new laws and announcements are shown as plain text.
* Unusual wording can make an instruction fail; it is then marked **fehlgeschlagen**.
* When the old wording comes from an Internet Archive snapshot, the page says from which day.
* **Not legally binding.** Only the official Bundesgesetzblatt is authoritative; for a bill,
  only the Drucksache of the Bundestag.

## Legal basis of the data use

* Laws and official announcements are not protected by copyright (§ 5 UrhG).
* The Bundesgesetzblatt may be reused under § 2 Abs. 3 VkBkmG with § 7 Datennutzungsgesetz.
* gesetze-im-internet.de offers its XML for automated use; the NeuRIS API (test phase)
  explicitly allows building applications on it. All responses are cached.
* bundesdiff is not an official service and gives no legal advice.

## Contributing

Ideas are welcome, also without code: see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The laws themselves are official works and not protected by copyright.
