# 001 Navigation bar

Status: done
Prefix: NAV

## Problem

The bar at the top today mixes two things: where you are on the site (the logo) and settings
for reading a diff ("Nebeneinander / Im Text markiert", "Unverändertes ausblenden"), which
only matter while a publication is open. On a phone it wraps to four rows and takes up half
the first screen, and it scrolls away, so a reader deep inside a long publication has no way
to get back to the list, to the help or to another changed law except scrolling all the way
up. There is no clear sign of where you are, no page that says who is behind bundesdiff and
where the data comes from, and no "skip to content" link for keyboard and screen-reader users.

## Requirements

Navbar on every page:

**NAV-1** Every page has one navigation bar at the top (on phones the round buttons of
spec 004 replace it, PTL-1/PTL-5) with, in this order: the logo
"bundesdiff" (link to the start page), "Veröffentlichungen" (the timeline, spec 002, as the
reader left it: with the chosen "Art" and view – owner, 2026-11-01; on that timeline already,
it goes to its top), "Gesetzentwürfe" (the list of bills, spec 016 – added 2026-11-09), "So
funktioniert's" (opens the help), "Über bundesdiff" (the about page, NAV-10), the search
(SRCH-1) and the light/dark switch. Where the names of the pages do not fit (NAV-3), an
entry "Menü" stands in their place.

**NAV-2** On the start page "Veröffentlichungen" and on the about page "Über bundesdiff" is
marked as the current page, by more than colour (underline), and announced as current to
screen readers (`aria-current="page"`). On a publication no entry is marked.

**NAV-3** The navbar is one row high on every screen it is shown on (all but the phone
layout of PTL-1, so down to 320 px wide on low screens and at 400 % zoom), in portrait and
landscape, and in both colour themes. Below 1230 px the logo shows only "§"; below 940 px the
entries show short labels (both moved up on 2026-11-10 for the fourth page, spec 016) – "Liste", "Entwürfe", "Hilfe", "Über". Below 480 px – and wherever
the entries still do not fit, for example with wider text spacing – the three pages
("Veröffentlichungen", "Gesetzentwürfe", "Über bundesdiff") are in the menu of PTL-6, opened by
an entry "Menü" in their place; it opens at the top of the screen and scrolls where the screen
is lower than the menu. (Added 2026-11-10 with spec 016: with a fourth page the entries need
368 px in Firefox, a 320 px screen has room for 304 px.) The light/dark switch (NAV-11) has
the same size everywhere. Screen
readers always hear a full name ("bundesdiff – Startseite", "Hell / Dunkel umschalten").

**NAV-4** The navbar stays visible at the top while scrolling, on every screen it is shown
on. It is
at most 56 px high.

**NAV-5** "Veröffentlichungen" shows the timeline (spec 002). Coming from a publication, the
timeline is scrolled to that publication's entry, which is marked and has the keyboard focus,
so the reader continues where they left off. It replaces the "← Alle Veröffentlichungen" link.
On phones the back arrow and "Veröffentlichungen" in the menu do the same (PTL-11, PTL-6).
(Changed by spec 002: before, it moved the focus into the sidebar list.)

**NAV-6** The reading settings ("Nebeneinander / Im Text markiert", "Unverändertes
ausblenden") are no longer in the navbar but above the text of a publication that has a
before/after comparison, together with the colour legend. They are not shown on the start
page, the about page or publications without a comparison, where they have no effect.

Navigation inside a publication:

**NAV-7** A publication that changes more than one law has a contents bar right below the
navbar. It names the law being read ("Artikel 1 · Tabaksteuergesetz (TabStG)") and has a
button "Inhalt", which opens a list with one entry per changed law and its number of changed
provisions. Choosing an entry jumps to that law and closes the list.

**NAV-8** While scrolling, the contents bar always names the law currently on screen, and the
list marks it as current.

**NAV-9** At the end of every law there is a link "Zum Anfang der Veröffentlichung", which
goes back to the title of the publication.

About page:

**NAV-10** The about page (`#/ueber`) explains in plain German: what bundesdiff is for, that
it is not an official service and only the Bundesgesetzblatt is binding, where the data comes
from and why it may be used (amtliche Werke, § 5 UrhG; terms of recht.bund.de, NeuRIS and
gesetze-im-internet.de), and that nothing about the reader is stored or sent elsewhere (no
cookies, no tracking; only the colour theme and view are remembered in the browser).

**NAV-11** The light/dark switch is a small slider, like a switch on a device: a track with
a knob (both rectangular, SHAPE-3) that sits on the left in the light theme and on the right in the dark
theme. The knob shows a sun (light) or a moon (dark), drawn as thin lines in the colours of the
page – no emoji, no symbol from a font. The sun and moon are centred in the knob, the knob is
centred in the track's height. Screen readers hear a switch named "Dunkle Ansicht", on or off;
the tooltip says what a click does ("Zur dunklen Ansicht wechseln"). On phones it is in the
menu (PTL-6).

## Accessibility

**NAV-A1** The first element that receives keyboard focus on every page is a link
"Zum Inhalt springen", invisible until focused, which moves the focus to the main content.

**NAV-A2** The navbar is a `<nav>` landmark named "Hauptnavigation"; the contents bar is a
`<nav>` named "Inhalt dieser Veröffentlichung". The "Inhalt" button says whether the list is
open (`aria-expanded`), and Escape closes the list and returns focus to the button.

**NAV-A3** Jumping to a law (NAV-7) or back to the top (NAV-9) moves the keyboard focus
there, and the target heading is not hidden behind the sticky bars.

**NAV-A4** On very low screens (at most 300 px high, e.g. 400 % zoom) the bars are not
sticky, so they never cover more than a third of the screen.

## Out of scope

* A menu button ("hamburger") that hides entries: the navbar has few enough entries to show
  them all, and hidden menus are harder to find for many readers.
* Search in the navbar (stays above the list).
* Impressum: the site is a private, non-commercial project and has none (owner, 2026-11-04).

## Decisions

* Navbar entries: core four plus "Über bundesdiff" (owner, 2026-10-30).
* The contents bar is part of this spec (owner, 2026-10-30).
* The navbar is sticky on phones too (owner, 2026-10-30).
* Implementation: the full labels need about 840 px in Firefox (wider fonts than Chromium), so
  the logo text goes below 960 px and the short labels below 820 px, not below 600 px as first
  drafted. `test_navbar_fits_at_every_width` checks every width from 320 to 1000 px.
