# 003 Data updated once a day

Status: done
Prefix: UPD

## Problem

The Bundesgesetzblatt appears on working days, usually a few issues a day. Checking every hour
costs GitHub Actions minutes and load on recht.bund.de for little gain: readers need the changes
of the day, not of the hour.

## Requirements

**UPD-1** The GitHub workflow looks for new publications once a day, in the evening
(19:23 UTC = 20:23/21:23 German time, after the day's issues are out), and can still be started
by hand ("Run workflow").

**UPD-2** The local server (`bundesdiff serve`) also checks once a day by default
(`BUNDESDIFF_WATCH_MINUTES=1440`).

**UPD-3** Where the site tells readers when data is updated, it says "einmal täglich".

## Accessibility

Only text; the baseline in `000-accessibility.md` applies.

## Out of scope

Push notifications for new issues.

## Decisions

- Once a day instead of every hour (owner, 2026-10-30).

## Open questions

None.
