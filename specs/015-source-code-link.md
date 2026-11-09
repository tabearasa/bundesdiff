# 015 Link to the source code

Status: done
Prefix: SRC

## Problem

bundesdiff is computed automatically and can contain errors. A reader who wants to know how a
diff was made, check the method or report a wrong text has no way today to find out where the
project lives. The source code is public on GitHub, but the site never says so.

## Requirements

**SRC-1** The page „Über bundesdiff“ has a section „Quelltext“ with the text:
„Der Quelltext von bundesdiff liegt öffentlich auf GitHub. Unter
github.com/tabearasa/bundesdiff können Sie nachlesen, wie die Änderungen berechnet werden,
und Fehler melden.“ (The address stands inside the sentence, not before a full stop, so the
focus marker of the link never covers a punctuation mark, SRC-A3.) – the address is a link to
`https://github.com/tabearasa/bundesdiff`.

**SRC-2** The link text is the address itself (marked as a domain like the other addresses, so
it never breaks inside a word, A11Y-13), not „hier“.

**SRC-3** The link opens in a new tab like the other external links on that page
(`target="_blank" rel="noopener"`).

**SRC-4** The site still loads nothing from GitHub: no logo, no badge, no star counter – only
the plain text link.

## Accessibility

**SRC-A1** The new section passes the layout and axe checks of the about page at every screen
size, light and dark, 200 %/400 % zoom and wider text spacing; the address fits at 320 px
without horizontal scrolling.

**SRC-A2** The names „bundesdiff“ and „GitHub“ in the section are never hyphenated, at any
width, zoom or text spacing. „bundesdiff“ is not hyphenated anywhere else on the site either
(owner's decision 2026-11-07: it was split as „bundes-diff“ in headings and text on phones).

**SRC-A3** When a link inside running text has keyboard focus, its focus marker keeps at least
2 px clear of the characters beside it on the same line (owner's decision 2026-11-07: for
every such link on the site; the marker of these links hugs the link instead of standing 2 px
off).

**SRC-A4** The paragraph of the section is set ragged-right at every width, so the address,
which can only break after a slash, never stretches the line before it to wide word gaps.

## Out of scope

* A GitHub logo or icon (no pictographic symbols, no external requests).
* A form for reporting errors on the site itself.
* A link in the footer of every page or in the help (owner's decision 2026-11-07: only on
  „Über bundesdiff“).
* The licence (owner's decision 2026-11-07: too technical for readers).
* Telling screen readers that external links open a new tab: none of the site's external links
  does this yet; that belongs in a site-wide change, not in this spec.

## Open questions
