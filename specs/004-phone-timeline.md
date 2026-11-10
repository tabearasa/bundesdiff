# 004 Timeline with a lens; on phones round buttons instead of the navbar

Status: done
Prefix: PTL

## Problem

On a phone the timeline (TL-3) is one very long column of small, equal entries: a year of
publications is many screens long, nothing stands out, and the reader loses the sense of
*when* things happened. The navbar also takes room at the top of every screen, while the
thumb is at the bottom. The owner sketched a different design for phones (2026-10-31): the
publication in the middle of the screen is shown large, the ones above and below get smaller
towards the edges, and the controls are round buttons at the bottom.

## Layout on a phone

```
┌──────────────────────────────┐
│          BUNDESDIFF          │  no navbar: a quiet masthead that scrolls away
│  Was ändert sich im Gesetz?  │
│ │                            │
│ │   ┌──────┐                 │  entries near the edge: smaller
│ ●───┤      │                 │
│ │   └──────┘                 │
│ ○ Dienstag, 20. Oktober      │  a day: its mark on the axis, the date beside it
│ │   ┌──────────────────────┐ │
│ │   │ GESETZ               │ │  the entry in the middle of the
│ ●───┤ Gesetz zur Änderung  │ │  screen: enlarged into a card
│ │   │ des Tabaksteuer…     │ │
│ │   │ ändert 2 Gesetze     │ │
│ │   └──────────────────────┘ │
│ │   ┌──────────────────────┐ │  same day: underneath, its own line to the axis
│ ●───┤ second publication   │ │
│ │   └──────────────────────┘ │
│  (=)              (?)  (⌕)   │  round buttons: menu │ help, search
└──────────────────────────────┘
```

On a publication the bar is `(←) (=) … (?) (⌕)`: back to the timeline, menu, help, search.

The clickable mock-up of this design is in `design/prototypes/` (see `build.py` there).

## Requirements

**PTL-1** The round buttons (PTL-5 … PTL-7, PTL-10, PTL-11) replace the navbar on screens
narrower than 600 px and at least 480 px high (CSS pixels, so browser zoom counts). Wider or
lower screens – tablets, phones in landscape, desktops at 400 % zoom – keep the navbar. The
timeline with the lens (PTL-2, PTL-3) is the same on every screen; on wide screens the date
stays in the margin left of the axis.

**PTL-2** In the order "Nach Veröffentlichung" every publication is a framed entry with the
same lines: type in small caps, "ändert 2 Gesetze", the whole title and up to four
topics; of more the first three and "9 weitere Sachgebiete". Nothing is cut off with "…". The entry in the middle of the screen is the card: drawn at full
size, with a stronger frame, a shadow and its line to the axis in the accent colour. The
further another entry is from the middle, the smaller it is drawn, down to 88 % of its size.
Both follow the scrolling continuously: while the reader scrolls, entries grow as they near
the middle and the card changes as soon as another entry crosses it – nothing waits for the
scrolling to stop. Entries never change their height, so the page never jumps, and it never
moves by itself. Only after an action of the reader does the card glide into the middle: an
entry reached with the keyboard (PTL-A1), coming back from a publication (PTL-11), turning
the phone. When the page opens, the newest publication is the card; after turning the phone
the same entry is the card again.

**PTL-3** Every publication has its own straight horizontal line that ends on the time axis,
at every size of the entry. Several publications of the same day are set underneath each
other below the day's mark, each with its own line to the axis.

**PTL-4** Every entry – small or enlarged – is one link: tapping it opens the publication
directly. There is no separate button to open it.

**PTL-5** Round buttons stay at the bottom of the screen, within reach of the thumb: on the
left the menu (two drawn lines), on the right help ("?") and search (the magnifying glass of
SRCH-1). Each is a circle of at least 48 px with a thin frame, its lines drawn in the page's
colours, without a visible word; screen readers hear "Menü", "So funktioniert's" and
"Suchen". There is no navbar.

**PTL-6** The menu button opens a small window above it with the logo (link to the start
page), "Veröffentlichungen", "Gesetzentwürfe" (spec 016), "Über bundesdiff" and the light/dark switch (NAV-11). The
current page is marked as in NAV-2. `Esc`, the close button (SHAPE-7) or a tap outside close
it. The same menu is opened by "Menü" in a navbar too narrow for the names of the pages
(NAV-3); it then opens at the top of the screen.

**PTL-7** The help button opens the help ("So funktioniert bundesdiff"), the search button
the search window (SRCH-2).

**PTL-8** With `prefers-reduced-motion` nothing moves: all entries have their normal size,
the card is not animated, the page jumps instead of gliding, and windows appear without
animation.

**PTL-9** The order switch (TL-5) and the filters (TL-4) are above the timeline as on larger
screens. "Was ändert sich demnächst?" is shown as the list of TL-6, without the lens.

**PTL-10** The start page begins with a quiet masthead: the name "bundesdiff" in small caps
above the title "Was ändert sich im Gesetz?". It scrolls away with the page.

**PTL-11** On a publication and on the about page the round buttons stay, with one more on
the far left: an arrow (drawn lines; screen readers hear "Zurück zur Zeitleiste"). It leads
to the timeline as the reader left it – with the chosen "Art" and view (TL-4, TL-5) – where the
publication the reader came from is the card in the middle and has the keyboard focus (as NAV-5). The contents bar of a publication (NAV-7) is at the very
top of the screen.

## Accessibility

**PTL-A1** The round buttons never hide anything for good: the end of every page can be
scrolled above them (also with `Ende`/`End`), nothing is under them before the reader scrolls
except the timeline and the text, which move on, and whatever gets the keyboard focus is
scrolled clear of them.

**PTL-A2** The menu is a modal dialog: focus moves into it when it opens and returns to the
menu button when it closes. Help and search return the focus to the round button that
opened them.

**PTL-A3** The lens is visual only: for screen readers and the keyboard the timeline stays
the ordered list of TL-3 with month and day headings; every entry is a complete link with
text of at least 12 px at every size.

## Out of scope

The navbar of tablets and desktops (stays as in NAV). The history of a single law (idea list
in `CONTRIBUTING.md`).

## Decisions

- Left round button is the menu; the round buttons replace the navbar on phones (owner, 2026-10-31).
- Scrolling is vertical, newest at the top (owner, 2026-10-31).
- Several publications on one day are set underneath each other, each with a line to the axis (owner, 2026-10-31).
- Tapping a publication opens it directly, no "Änderungen ansehen" (owner, 2026-10-31).
- Every entry's line ends on the time axis, never in between (owner, 2026-10-31).
- On a publication too: no navbar, the round buttons stay at the bottom, plus a back arrow
  on the left (owner, 2026-10-31).
- The menu button has two lines and no word (owner, 2026-10-31).
- Menu, search and help blur the page behind them (owner, 2026-10-31, spec 005).
- Accepted after the mock-up (owner, 2026-10-31).
- The card appeared only after scrolling stopped, which felt slow ("you need to wait and then
  the article in the centre pops up"). Now it grows while scrolling; for that every entry shows
  the same lines, so nothing changes its height. The citation is no
  longer in the timeline, it is in the header of the publication (owner, 2026-11-01).
- Desktops and tablets get the same timeline with the lens; the navbar stays there
  (owner, 2026-11-01).
- The back arrow returns to the filtered timeline, not the whole one (owner, 2026-11-01).
- When a publication appears twice in "Was ändert sich demnächst?", the back arrow focuses its
  first entry, not necessarily the one that was tapped (owner, 2026-11-01).

Decided by Claude on the owner's behalf (owner, 2026-10-31: "decide by yourself"):

- The time axis runs vertically near the left edge (like TL-3); alternating left/right was
  not chosen: at 320 px each half would be too narrow for a German title.
- Phone layout below 600 px wide and from 480 px high. The first draft said 560 px; an
  iPhone SE shows only about 550 px in Safari, so 480 px.
- "Was ändert sich demnächst?" keeps its list: its entries carry the in-force sentence and
  its source, which do not fit a lens.
- No gliding above the timeline, at the end of the page or while a filter has the focus: the
  bug-hunter found that it skipped the filters and pushed the focused control off the screen
  (2026-10-31).
- Titles are shown whole and topics as "the first three · 9 weitere Sachgebiete", not cut off after a few
  lines with "…": with German hyphenation a line often ended in "Straßenver-…", and without it
  long words were torn apart (Claude, 2026-11-01, after the bug-hunter found it).
- The lens also works on low screens (phones in landscape, 400 % zoom): it only scales
  entries, which costs no room (Claude, 2026-11-01).
- The page does not glide by itself when the reader stops scrolling (the mock-up snapped the
  card into the middle like a picker). In five bug-hunter runs every form of that snapping
  fought some readers: slow wheel steps, arrow keys and Page Down stalled, two entries took
  turns, the card came to rest off screen (Claude, 2026-10-31).
- Entries shrink to 88 %, not less, and do not fade: fading would lower the contrast of
  their text below 4.5:1.

## Open questions

None.
