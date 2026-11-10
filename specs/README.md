# Specs

Every feature of bundesdiff starts as a spec in this folder. Code follows the spec, tests prove
the spec, and the spec stays as the documentation of why the feature looks the way it does.

## Workflow

1. **Draft.** Copy `_template.md` to `NNN-short-name.md` (next free number) and set
   `Status: draft`. Describe the reader's problem first, then the requirements. Anything
   undecided goes under *Open questions*, not into the requirements.
2. **Review.** The owner reads the spec and answers the open questions. Only then:
   `Status: accepted`. Nothing is implemented from a draft.
3. **Tests first.** Each requirement gets at least one test, marked with its ID:
   ```python
   @pytest.mark.spec("NAV-3")
   def test_navbar_stays_on_one_row_on_phones(app, page): ...
   ```
   The tests fail at this point – that is expected.
4. **Implement** until the `bug-hunter` agent reports that these and all other tests pass in
   Chromium and Firefox and finds nothing in the screenshots (see `AGENTS.md`). The tests are
   always run by that agent, never by the one writing the code.
5. **Done.** `Status: done`. If the implementation had to deviate, the spec is changed in the
   same change set, never left outdated.

A spec the owner decides against gets `Status: dropped` and a short "Dropped" section with the
reason; it is kept so the idea is not proposed again without new arguments.

Changing a feature later means changing its spec first (new or edited requirements), then the
tests, then the code.

## Rules for requirements

* One line per requirement, starting with its ID in bold: `**NAV-3** The navbar …`.
  IDs are never reused or renumbered; a dropped requirement is struck through (`~~NAV-3~~`).
* Write what the reader sees or can do, not how it is built: "On a 320 px phone the navbar
  fits on one row", not "use flexbox".
* Every requirement must be checkable by a test. "Looks nice" is not a requirement;
  "the active page is marked by more than colour" is.
* Every spec has an *Accessibility* section. The baseline in `000-accessibility.md` always
  applies; the section names what is specific to the feature (keyboard, screen reader
  announcements, small screens, zoom).
* UI text is quoted in German, exactly as it will appear.

## Enforced by tests

`tests/test_specs.py` fails when a requirement of an `accepted` or `done` spec has no test
marked with its ID, or a test refers to an ID that no spec defines.

## Index

| Spec | Status |
| --- | --- |
| [000 Accessibility baseline](000-accessibility.md) | done |
| [001 Navigation bar](001-navbar.md) | done |
| [002 Search and timeline instead of the sidebar](002-search-and-timeline.md) | done |
| [003 Data updated once a day](003-daily-updates.md) | done |
| [004 Timeline with a lens; on phones round buttons instead of the navbar](004-phone-timeline.md) | done |
| [005 Windows over the page: the page behind is blurred](005-search-blur.md) | done |
| [006 Logo](006-logo.md) | draft |
| [007 One shape language for all controls](007-shape-language.md) | done |
| [008 Horizontal time axis on wide screens](008-horizontal-timeline.md) | dropped |
| [009 Moving between pages: title, focus and announcement](009-page-changes.md) | draft |
| [010 Error messages in plain German](010-error-messages.md) | draft |
| [011 The page of a publication that is not analysed yet](011-not-analyzed-page.md) | draft |
| [012 Typesetting on small phones: line breaks and title size](012-small-screen-typesetting.md) | draft |
| [013 Leftovers of a developer look; what the browser stores](013-paper-look-leftovers.md) | draft |
| [014 When recht.bund.de cannot be reached](014-source-unreachable.md) | done |
| [015 Link to the source code](015-source-code-link.md) | done |
| [016 Gesetzentwürfe: what a bill would change (prototype with one bill)](016-gesetzentwuerfe.md) | done |
