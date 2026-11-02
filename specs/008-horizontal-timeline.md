# 008 Horizontal time axis on wide screens

Status: dropped
Prefix: HTL

## Problem

On a desktop or a phone turned sideways the screen is wide and low, but the timeline of
spec 004 runs from top to bottom in a narrow column: most of the screen stays empty and only
two or three publications fit on it. The owner wants the time axis horizontal there
(2026-11-01): time runs from left to right, as on a printed time line.

## Layout on a wide screen

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ navbar                                                                       │
│        [Nach Veröffentlichung | Was ändert sich demnächst?]   Art [▾]        │
│ [‹ Ältere]             September 2026   Oktober 2026             [Neuere ›]  │
│  ┌───────────────────┐        ┌─────────────────────────┐                    │
│  │ VERORDNUNG  Nr.311│        │ VERORDNUNG       Nr. 313│  the card: full    │
│  │ Title …           │        │ Title …                 │  size, frame,      │
│  │ Ändert   …        │        │ Ändert      …           │  shadow            │
│  │ In Kraft …        │        │ Zuständig   …           │                    │
│  └─────────┬─────────┘        └────────────┬────────────┘                    │
│ ───────────●━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━●───────────────── the axis, in   │
│      Mi, 21. Okt.           │                              the middle        │
│               ┌─────────────┴─────────┐                                      │
│               │ VERORDNUNG    Nr. 312 │   entries alternate above and below  │
│               │ Title …               │                                      │
│               └───────────────────────┘                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

The clickable mock-up is `design/prototypes/wide-timeline.html` (built by `build.py` there).

## Requirements

**HTL-1** On screens at least 600 px wide and wider than they are high (desktops, phones and
tablets in landscape) the time axis of "Nach Veröffentlichung" runs horizontally across the
page. Narrower screens and screens in portrait – also tablets held upright – keep the
vertical axis of spec 004. The switch happens when the device is turned; the same
publication stays the card.

**HTL-2** On a desktop (from 650 px high) the axis runs through the middle of the strip and
the publications stand alternately above and below it, so neighbours may overlap sideways
and more of them fit on the screen. Each publication is a framed entry with a straight
vertical line that ends in a dot on the axis; all lines are equally long. Publications of one
day follow each other, a stroke on the axis joins their dots, and a gap separates the days.
The date stands beside the first dot of the day, on the side of the axis without its line;
on the first day of a month the month's name stands above the date. Lower screens (phones in
landscape) have one row of entries above the axis and the dates below it.

**HTL-8** On a desktop an entry shows more than in the vertical timeline: type and citation
("BGBl. 2026 I Nr. 314"), the whole title, and below a thin rule
"Ändert" (the names of the changed laws with their abbreviations, of more than four the first
three and "und 2 weitere"; or "kein bestehendes Gesetz" / "noch nicht ausgewertet"),
"In Kraft" ("ab 1. Januar 2027", "seit 22. Oktober 2026, Teile ab 1. August 2027"; only when
known), "Zuständig" (the ministry or office) and "Sachgebiete" (up to four, as PTL-2). The
title is the link; the whole entry can be clicked. Lower screens show the short entry of
PTL-2.

**HTL-3** The entry in the middle of the screen (horizontally) is the card, the others get
smaller towards the left and right edges, continuously while scrolling – as PTL-2 with
"left/right" for "top/bottom". Entries show the same lines as in PTL-2.

**HTL-4** The axis can be moved with the scroll bar, by swiping, with the touchpad's sideways
swipe, with the arrow keys and with the buttons "‹ Ältere" and "Neuere ›" (a button that
cannot move further is shown inactive). Over the axis the mouse wheel moves it: turning down
goes back in time (as down in the vertical list), up forward. At either end the wheel scrolls
the page as usual.

**HTL-5** Older publications are on the left, newer on the right. The page opens with the
newest publication as the card in the middle; to its right the axis is empty.

**HTL-6** The order switch, the filter, the two buttons and the row of months stand above the
axis and scroll away with the page. On low screens (phones in landscape) the strip of the
axis is then as high as the screen below the navbar. A month link moves the axis so that the
first publication of the month is the card. "Was ändert sich demnächst?" stays the list of TL-6.

**HTL-7** Entries with long titles are wider instead of higher (three widths, by the length of
the title); on a desktop an entry that is still higher than its half of the screen gets
wider, up to 640 px. On low screens the type is a little smaller (at least 13 px) and the
entries a little wider. Nothing is cut off: if an entry still does not fit, the page scrolls
down a little.

## Accessibility

**HTL-A1** For screen readers and the keyboard the timeline stays the ordered list of TL-3
(months, days, entries); `Tab` moves from entry to entry and the axis follows so that the
focused entry is fully visible and not under the navbar or the round buttons.

**HTL-A2** The scrolling strip is focusable and named ("Zeitleiste, nach links und rechts
verschiebbar") so keyboard users can move it with the arrow keys (WCAG 2.1.1). Horizontal
scrolling is limited to this strip; the page itself never scrolls sideways (WCAG 1.4.10).
At 320 px and at 400 % zoom the screen is narrower than 600 px, so the vertical axis is used.

**HTL-A3** With `prefers-reduced-motion` the axis jumps instead of gliding and no entry is
scaled (PTL-8).

**HTL-A4** At 200 % zoom and with wide text spacing the longest title still fits in its
entry without being cut off (PTL-2, HTL-7).

## Out of scope

"Was ändert sich demnächst?" (stays a list), the vertical timeline of phones in portrait
(spec 004), the history of a single law.

## Decisions

- Horizontal on desktops and phones in landscape (owner, 2026-11-01).
- Owner, 2026-11-01, following Claude's recommendations: mouse wheel moves the axis until its
  end, then the page; newest on the right, the page opens there; tablets held upright stay
  vertical; long titles get wider entries and the controls scroll away; a mock-up first.

Decided by Claude on the owner's behalf:

- Publications of one day stand side by side, not stacked: a phone in landscape has only
  about 340 px below the navbar, two stacked entries do not fit (2026-11-01, mock-up).
- The wheel turned down goes back in time: the page opens at the newest end, so with the
  usual direction (down = right) the first turn would do nothing visible (2026-11-01).
- "‹" and "›" are typographic quotation marks of printed text (A11Y-13), each with a word.

- First mock-up not accepted (owner, 2026-11-01): "On a desktop, the timeline can be in the
  middle and above and below there can be the publications. And they can be much bigger with
  more information." Now HTL-2 and HTL-8.
- Phones in landscape keep one row above the axis: about 340 px of height leave no room for
  two rows (Claude, 2026-11-01).
- The ministry is called "Zuständig", not "Initiant": the plain word (Claude, 2026-11-01).

## Dropped

The owner was not happy with the second mock-up either and dropped the idea (2026-11-01):
the timeline stays vertical on every screen (spec 004). The mock-up was removed; this spec is
kept so the idea and its reasons are not proposed again without new arguments.
