# 006 Logo

Status: draft
Prefix: LOGO

## Problem

bundesdiff has no logo: the navbar shows a "§" in a circle next to the word "bundesdiff",
the browser tab a "§" on an oxblood square, and the README, GitHub page and shared links
nothing. A reader who sees the site in a tab, a bookmark or a link preview cannot recognise
it. The logo must fit the paper look: printed, typographic, no pictograms (A11Y-13).

## Requirements (proposal)

**LOGO-1** One logo as an SVG file in `bundesdiff/static/`, drawn in the colours of the page
(`currentColor` / the accent), used in the navbar, as the browser tab icon, as the icon when
saved to a phone's home screen, and at the top of the README.

**LOGO-2** The logo is readable and recognisable from 16 px (browser tab) to 512 px, in
light and dark mode, and centred in its frame (A11Y-12).

**LOGO-3** The navbar keeps NAV-3: below 960 px only the mark, with the full name for screen
readers ("bundesdiff – Startseite").

**LOGO-4** Link previews (when a link to bundesdiff is shared) show the logo and the line
"Was ändert sich im Gesetz?" (an Open-Graph image, a static PNG file).

## Accessibility

The logo image has a text alternative ("bundesdiff"); where it stands next to the word
"bundesdiff" it is decoration (`alt=""`). Contrast of the mark ≥ 3:1 against both paper
colours (WCAG 1.4.11).

## Out of scope

Colours, fonts and layout of the site.

## Decisions

Decided by Claude on the owner's behalf (owner, 2026-10-31: "decide by yourself"):

- The logo uses the oxblood accent of the site (`--accent`), so it changes with dark mode
  like the rest of the page; contrast ≥ 3:1 against both paper colours.
- An Open-Graph image (LOGO-4) is wanted: one static PNG, no external request.
- The mark follows the shape language of spec 007, so logo and controls speak the same
  visual language.

## Open questions

1. **The mark itself.** The first three candidates were rejected (owner, 2026-10-31). This
   is a matter of taste that cannot be decided from a description: the owner collects a few
   logos or marks they like (any field) in `design/references/`, Claude draws new
   candidates from them on a specimen sheet, the owner picks.
