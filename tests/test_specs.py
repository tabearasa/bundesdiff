"""Specs and tests stay in step: every requirement of an accepted spec has a test.

See specs/README.md. Tests name the requirements they prove with @pytest.mark.spec("NAV-3").
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
REQUIREMENT = re.compile(r"^\*\*([A-Z0-9]+-A?\d+)\*\*", re.M)
DROPPED = re.compile(r"^~~\*\*([A-Z0-9]+-A?\d+)\*\*", re.M)
MARK = re.compile(r"""spec\(((?:\s*["'][A-Z0-9]+-A?\d+["']\s*,?)+)\)""")


def specs() -> dict[str, tuple[str, set[str]]]:
    """Spec file → (status, requirement IDs)."""
    found = {}
    for path in sorted((ROOT / "specs").glob("[0-9]*.md")):
        text = path.read_text()
        status = re.search(r"^Status: (\w+)", text, re.M)
        assert status, f"{path.name}: no 'Status:' line"
        found[path.name] = (status.group(1), set(REQUIREMENT.findall(text)) - set(DROPPED.findall(text)))
    return found


def marked_ids() -> set[str]:
    ids = set()
    for path in (ROOT / "tests").rglob("test_*.py"):
        if path.name == Path(__file__).name:  # its docstring shows an example mark
            continue
        for group in MARK.findall(path.read_text()):
            ids |= set(re.findall(r"[A-Z0-9]+-A?\d+", group))
    return ids


def test_specs_have_a_known_status():
    for name, (status, _) in specs().items():
        assert status in {"draft", "accepted", "done", "dropped"}, f"{name}: unknown status {status!r}"


def test_requirement_ids_are_unique():
    seen: dict[str, str] = {}
    for name, (_, ids) in specs().items():
        for i in ids:
            assert i not in seen, f"{i} is defined in {seen[i]} and {name}"
            seen[i] = name


def test_every_accepted_requirement_has_a_test():
    have = marked_ids()
    missing = sorted(i for status, ids in specs().values() if status not in {"draft", "dropped"} for i in ids - have)
    assert not missing, "requirements without a test (@pytest.mark.spec): " + ", ".join(missing)


def test_tests_refer_to_existing_requirements():
    defined = set().union(*(ids for _, ids in specs().values()))
    unknown = sorted(marked_ids() - defined)
    assert not unknown, "tests refer to requirements no spec defines: " + ", ".join(unknown)
