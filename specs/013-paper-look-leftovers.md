# 013 Leftovers of a developer look; what the browser stores

Status: draft
Prefix: PAPER

## Problem

Some places still look like a developer tool, not like a printed page, and do not use plain
German. One text on "Über bundesdiff" is incomplete. (Found by the bug-hunter, 2026-11-01.)
- The buttons that unfold hidden text read "@@ 8 unveränderte Abschnitte – anzeigen @@": diff
  jargon that readers cannot understand.
- The small bar of five squares per section uses bright GitHub colours (`#3fb950`, `#e5534b`),
  the same in light and dark mode, unlike the paper colours everywhere else.
- On a Mac the search shortcut shows "⌘ K"; "⌘" is not among the marks of printed text allowed by
  A11Y-13.
- "Über bundesdiff" says only the theme and the display of changes are kept in the
  browser. It also keeps the last searches (`bundesdiff.recentSearches`, see spec 002).

## Requirements

**PAPER-1** The fold buttons read "8 unveränderte Abschnitte anzeigen" (singular: "1
unveränderten Abschnitt anzeigen"), with no "@@" and no other diff marks. The text is centred
in its row (A11Y-12).

**PAPER-2** The section bar uses the colour tokens of removed and added text (`--del-ink`,
`--ins-ink`, `--rule`) in both themes and reaches 3:1 contrast against the paper (WCAG 1.4.11).

**PAPER-3** The shortcut hint names the keys in words: "Strg K" on Windows/Linux, "Befehl K" on
Mac (`aria-keyshortcuts` stays as it is). `test_no_emoji_*` also checks the Mac variant.

**PAPER-4** "Über bundesdiff" lists everything the browser stores: "Ihre Einstellungen – helle
oder dunkle Ansicht, Darstellung der Änderungen – und Ihre letzten Suchen. Diese Angaben
bleiben auf Ihrem Gerät; die letzten Suchen können Sie in der Suche mit „Verlauf löschen“
entfernen." A test compares the text with the `localStorage` keys the app uses.

## Accessibility

PAPER-2 must not make the bar the only place where information is shown: it stays hidden from
screen readers with the counts said in words next to it, as today.

## Out of scope

Changing the shape of the fold rows (spec 007).

## Open questions

1. PAPER-1: keep a typographic mark to show "text left out", e.g. "…" before and after ("… 8
   unveränderte Abschnitte anzeigen …"), or words only?
2. PAPER-3: "Befehl K" or "Cmd K"? Apple's own German keyboards say "cmd"; "Befehlstaste" is
   the German name.
3. Should the section bar stay at all, given that the counts are already said in words?
