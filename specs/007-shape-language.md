# 007 One shape language for all controls

Status: done
Prefix: SHAPE

## Problem

The controls of bundesdiff were designed one at a time and do not look like they belong
together. In the navbar the search button is a rectangle with slightly rounded corners, grey
frame and italic grey text; the light/dark switch next to it is a pill with a round knob and
an oxblood frame. The owner noticed this (2026-10-31): the page does not read as one
carefully set printed page. Spec 004 adds round buttons for phones, which makes a rule for
shapes necessary. The grey frames are also too faint to see for many readers (about 1.6:1
against the paper; WCAG 1.4.11 asks for 3:1).

## Requirements

**SHAPE-1** Every framed control – buttons with a frame, the search button, the reading
settings, the contents button, selection lists and input fields – is a rectangle with corners
of at most 3 px and a 1 px frame in the frame colour, which has a contrast of at least 3:1
against the paper, in both colour themes.

**SHAPE-2** The oxblood accent marks only a state: hover, keyboard focus, pressed, open or
current. A control at rest has no oxblood frame.

**SHAPE-3** The light/dark switch (NAV-11) is a rectangular track with 3 px corners and a
square knob (2 px corners) carrying the sun or moon. Behaviour, name and tooltip stay.

**SHAPE-4** Circles are used only for the logo mark, the round buttons of the phone layout
(PTL-5), the day marks on the time axis and the turning circle while a publication loads
(both decoration). Nothing is pill-shaped: the counters
on the tabs of a publication are rectangles with 3 px corners too.

**SHAPE-5** In the navbar the search button and the light/dark switch are equally high and
centred on the same line.

~~**SHAPE-6**~~ (dropped: the specimen page is a way of working, not a feature – see Decisions)

**SHAPE-7** Windows (search, help, menu, "Wie ermittelt?") are closed with an "x" drawn as
two thin lines in the page's colours (not the font character ✕, A11Y-13), without a frame,
at least 44 px to tap; screen readers hear "Schließen".

## Accessibility

The frames of SHAPE-1 reach 3:1 (WCAG 1.4.11); focus stays visible (2 px outline, A11Y-8).
The "x" of SHAPE-7 has the accessible name "Schließen".

## Out of scope

Colours of the text, fonts, the diff markings, the status badges (stamps in their own colour).

## Decisions

- Close buttons are a drawn "x" instead of the word "Schließen" (owner, 2026-10-31).
- The knob of the light/dark switch keeps its oxblood frame and drawing: it shows the state
  "hell/dunkel" itself, which SHAPE-2 allows (Claude, 2026-10-31, after the bug-hunter asked).
- Accepted with spec 004 after the mock-up (owner, 2026-10-31).

Decided by Claude on the owner's behalf (owner, 2026-10-31: "decide by yourself"):

- Rectangles, not pills: printed forms, tables and stamps are rectangular; the paper look
  of bundesdiff already uses 3 px corners for badges, the search button and the reading
  settings. Only the light/dark switch breaks the rule, so it is the one to change.
- Circles stay for the logo (a seal) and the floating thumb buttons from the owner's sketch –
  both stand apart from the text, so a different shape marks a different role.
- Visual changes to controls are judged side by side on a specimen sheet in both themes
  before they are accepted (the way of working agreed on 2026-10-31; not a requirement).
