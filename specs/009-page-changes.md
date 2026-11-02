# 009 Moving between pages: title, focus and announcement

Status: draft
Prefix: PAGE

## Problem

bundesdiff is one HTML page; a "page" is a hash route (`#/`, `#/1/2026/309`, `#/ueber`). When the
reader opens a publication, nothing tells them a new page has loaded. The browser tab always says
"bundesdiff – Was ändert sich im Gesetz?", so tabs, bookmarks and the history list cannot be told
apart. After Enter on a timeline entry the keyboard focus is left on `<body>`, so a screen reader
says nothing and the next Tab starts at the top of the page. A reader with a screen reader
cannot tell whether the click worked or the page is still loading. (Found by the bug-hunter,
2026-11-01; WCAG 2.4.2 *Page titled*, 2.4.3 *Focus order*, 4.1.3 *Status messages*.)

## Requirements

**PAGE-1** The browser tab names the page in front, the name first:
- timeline: "Was ändert sich im Gesetz? – bundesdiff"
- "Was ändert sich demnächst?": "Was ändert sich demnächst? – bundesdiff"
- a publication: its title, e.g. "Gesetz zur Änderung des Tabaksteuergesetzes – bundesdiff"
- "Über bundesdiff": "Über bundesdiff – bundesdiff"
- a publication that could not be shown: "Nicht gefunden – bundesdiff" or
  "Fehler – bundesdiff" (see spec 010).

**PAGE-2** While a publication loads, the tab says "Wird geladen … – bundesdiff". The loading
message on the page is a status message (`role="status"`), so screen readers read it out
without the focus moving.

**PAGE-3** When a new page has rendered after the reader chose it (a link, an entry, the
pager, the back button of the phone layout), the keyboard focus is on its main heading (`h1`,
`tabindex="-1"`, no visible focus ring for a mouse click). The next Tab goes to the first control
after the heading.

**PAGE-4** Coming back to the timeline keeps NAV-5 / PTL-11: the focus goes to the entry the
reader came from, not to the heading.

**PAGE-5** Browser back/forward and opening a link in a new tab follow PAGE-1 and PAGE-3 in the same way.

## Accessibility

Screen readers announce the heading when it gets the focus; nothing extra is announced on top
of that, so nothing is read out twice. At 400 % zoom the page scrolls so that the
heading is at the top, below the sticky navbar.

## Out of scope

Server-side titles for links shared in messengers (there is no server-side rendering).

## Open questions

1. Is the order of PAGE-1, "name – bundesdiff", right, or should it be "bundesdiff – name"?
   The name first is usual practice and easier to read in narrow tabs.
2. Long titles ("Gesetz zur Änderung des Preisangabenrechts und …"): use the full title, or
   the everyday name of the changed law where there is one ("Preisangabenverordnung")?
3. PAGE-3 on the timeline itself (e.g. after "Was ändert sich demnächst?" is chosen): focus the
   heading, or leave the focus on the switch that was pressed (TL filters do the latter today)?
