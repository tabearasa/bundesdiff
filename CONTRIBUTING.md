# Contributing to bundesdiff

Thank you for helping. bundesdiff exists so that anyone, not only lawyers, can see what a new
law changes.

## Ideas welcome

You do not need to write code to help. The easiest contribution is an idea or 
domain knowledge: something you missed while reading a law change, something that
confused you, something that would help people you know.

**How to add an idea:** add a line to the list below (a pull request that changes only this
file is fine) or open an issue. Describe the reader's problem first, the solution second:

> *Reader's problem:* I want to know how § 622 BGB looked in 2019.
> *Idea:* a history of every version of a law.

Ideas are not promises. When the owner picks one up, it becomes a spec in [`specs/`](specs/)
and is moved from this list into the table under "Picked up".

### Idea list

| Idea | Reader's problem | Added by |
| --- | --- | --- |
| **History of a law** – every version of one law as a list of changes, like the history of a file in Git: which publication changed which paragraph when, with the diff of each step, and the text as it was on any chosen day. | "How did this law look before?" / "Who changed § 5 when?" Today bundesdiff shows one publication at a time, never the life of one law. | owner |
| **Everyday words in the search** – "Rente" finds Sozialgesetzbuch VI, "Miete" finds the tenancy rules of the BGB. | Readers search with their own words, not the names of laws. | owner |
| **Search the changed wording** – full-text search, loaded only when asked for. | "Where does the word *Wärmepumpe* appear in this year's changes?" | owner |

### Picked up

| Idea | Spec |
| --- | --- |
| "Was ändert sich demnächst?" – changes ordered by the day they take effect | [002](specs/002-search-and-timeline.md) |

## Contributing code

1. **Spec first.** Every feature or change in behaviour starts as a spec in `specs/`
   (`Status: draft`, open questions listed). Nothing is implemented from a draft; the owner
   reviews it first. See [`specs/README.md`](specs/README.md).
2. **Tests, then code.** Each requirement gets a test marked `@pytest.mark.spec("ID")`.
   `tests/test_specs.py` fails if an accepted requirement has no test.
3. **Accessibility is not optional.** WCAG 2.2 AA, 320 px phones, 200 %/400 % zoom, keyboard
   only, screen readers, light and dark – see [`specs/000-accessibility.md`](specs/000-accessibility.md).
4. **Paper look.** Serif type, paper colours, thin rules, every control exactly centred, no
   emoji. Words instead of icons.
5. **No new frontend dependencies**, no build step, no external requests from the site.
   New Python dependencies only when the standard library cannot do it reasonably.
6. **Plain German** in the interface: short sentences, everyday words, legal terms explained.

Run the tests as described in the [README](README.md#tests). A frontend change is done when
all tests pass in Chromium and Firefox (CI also runs WebKit) and the screenshots in
`test-results/` look right on every screen size.

## License

By contributing you agree that your contribution is published under the
[MIT License](LICENSE).
