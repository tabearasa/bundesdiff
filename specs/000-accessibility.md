# 000 Accessibility baseline

Status: done
Prefix: A11Y

## Problem

bundesdiff is for the general public: people without legal training, on cheap phones and old
browsers, with poor eyesight, colour blindness, motor impairments, or using a screen reader.
If one of them cannot read a page, the project has failed for that person. These requirements
apply to every page and every future feature.

## Requirements

**A11Y-1** No page scrolls sideways, and no text spills out of or is cut off by its box, on
screens from 320 px wide (portrait and landscape) up to desktop, in light and dark mode.

**A11Y-2** At 200 % and 400 % browser zoom everything is still readable and usable without
scrolling sideways (WCAG 1.4.4, 1.4.10).

**A11Y-3** With wider letter, word and line spacing set by the reader, no text is cut off
(WCAG 1.4.12).

**A11Y-4** Controls do not overlap and are not covered by other elements; every click target
is at least 24 × 24 px (WCAG 2.5.8). Text is at least 12 px.

**A11Y-5** No word is split across lines without a hyphen.

**A11Y-6** No violations of the WCAG 2.2 A/AA rules checked by axe-core (contrast, names and
labels, ARIA, landmarks) on any page or dialog, in light and dark mode.

**A11Y-7** Removed and added text is marked by more than colour (struck through / underlined,
−/+ in the margin), and screen readers announce it ("gestrichen", "neu").

**A11Y-8** Everything works with the keyboard alone, with a visible focus marker.

**A11Y-9** With "reduce motion" turned on in the system, nothing animates or scrolls smoothly.

**A11Y-10** The colour theme follows the system setting until the reader picks one, and the
choice is remembered.

**A11Y-11** No page shows a JavaScript error or makes a request that fails.

**A11Y-12** Text and symbols inside a frame (a button, badge or logo with a border or a
background of its own) sit in the middle of the frame, left/right and top/bottom.

**A11Y-13** The pages use no emoji or pictographic symbols from fonts (☾, ☀, ✕, ↗ …): they
look different on every device and do not fit a printed page. Text uses letters, digits and
typographic marks of printed text (§, –, −, +, ±, …, ↑, ▾). Where a picture really helps (the
sun and moon of the light/dark switch), it is drawn as thin lines in the colours of the page.

## Accessibility

This spec is the accessibility section of every other spec.

## Out of scope

Support for browsers without JavaScript (the diff is computed in the browser from JSON).

## Open questions

None.
