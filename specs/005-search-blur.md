# 005 Windows over the page: the page behind is blurred

Status: done
Prefix: SBL

## Problem

When the search window (SRCH-2) or the help ("So funktioniert's") is open, the page behind
it is only darkened. Its text stays sharp and competes with the window, especially on
tablets and desktops, where the window does not fill the screen. The owner wants the
background blurred (2026-10-31), so the eye goes to the window alone.

## Requirements

**SBL-1** While the search window, the help window or the menu (PTL-6) is open, the page
behind it (navbar included) is blurred by 4 px – still recognisable as a page, but its text
can no longer be read – and slightly darkened, in light and dark mode. Closing
the window removes the blur at once.

**SBL-2** Browsers that cannot blur (no `backdrop-filter`) show the darkened background as
today, never a fully transparent one; the window stays readable.

**SBL-3** With `prefers-reduced-motion` the blur appears without a fade; otherwise it fades
in within 150 ms.

## Accessibility

The blur is decoration: the contrast of everything inside the window stays ≥ 4.5:1
regardless of the background. Nothing changes for screen readers or keyboard users.

## Decisions

- Search, help and menu all blur the page behind them (owner, 2026-10-31).
- Accepted with spec 004 after the mock-up (owner, 2026-10-31).
- Light blur of 4 px: the reader still sees that the page is there and nothing was lost,
  but nothing competes with the window (Claude on the owner's behalf, 2026-10-31).

## Open questions

None – waiting for the owner to accept.
