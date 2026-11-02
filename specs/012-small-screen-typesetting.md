# 012 Typesetting on small phones: line breaks and title size

Status: draft
Prefix: TYPE

## Problem

On a 320 px phone the text of the law breaks between a day number and its month: "vom 1." ends one line and "Januar"
starts the next. The bug-hunter counted 47 such breaks on `#/1/2026/309`. It also breaks between "§"
and its number. A printed page would never do that. The page title stays 38 px wide-screen size: "Gesetz zur Änderung des
Preisangabenrechts …" (`#/1/2026/314`) takes more than a full screen and ends five lines in a
row in a hyphen. (Found by the bug-hunter, 2026-11-01.)

## Requirements

**TYPE-1** In every text bundesdiff shows (law text, instructions, titles, timeline), these
never stand at the end of a line without what follows them:
- a day number and its month ("1. Januar", "31. Dezember 2030");
- "§", "§§", "Art.", "Artikel", "Absatz", "Abs.", "Nr.", "Satz" and the number after it;
- a number and its unit or noun ("5 Wochen", "300 KB").
- a dash that adds to what stands before it never opens a line: "Tabaksteuergesetz (TabStG)
  – 2 Vorschriften" breaks before the law's name, not before "–" (seen on `#/1/2026/309` at 320 px).

Done by joining them with a no-break space when the text is rendered, never by changing the stored text.

**TYPE-2** On screens up to 599 px wide the `h1` of a publication and of the start page is at most
28 px. It becomes larger with the width up to the present 38 px (desktop is unchanged).

**TYPE-3** No more than two consecutive lines of a heading end in a hyphen.

**TYPE-4** A layout check finds a line that ends in one of the TYPE-1 words or in a day
number ("1.") directly before a month on the next line. It runs at all screen sizes in
`layout.js`, like the check for words split without a hyphen.

## Accessibility

Bigger text at 200 %/400 % zoom must still reflow: no-break spaces join two to four words at
most, so no group can be wider than 320 px at 400 % zoom. Screen readers read a no-break space as a normal space.

## Out of scope

Justified text; hyphenation dictionaries beyond the browser's own `hyphens: auto`.

## Open questions

1. Is the list in TYPE-1 complete? Proposed additions: "Buchstabe", "Doppelbuchstabe", "Anlage".
2. TYPE-2: 28 px at 320 px – or keep the size and shorten nothing, only allow fewer hyphens?
3. TYPE-3 can only be fully met by `text-wrap: balance`/`pretty` or `hyphenate-limit-lines`;
   Firefox does not support the latter. Accept "best effort" in Firefox?
