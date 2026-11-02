"""Line- and word-level diff between two versions of a unit."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from .model import Node, comparable, render_lines

_TOKEN = re.compile(r"\d+(?:[.,]\d+)*|\w+|[^\w\s]|\s+")


def word_diff(a: str, b: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Segments [{"t": "eq"|"del"|"ins", "s": text}] for the left side, the right side and an inline view."""
    ta, tb = _TOKEN.findall(a), _TOKEN.findall(b)
    sm = SequenceMatcher(None, ta, tb, autojunk=False)
    left: list[dict] = []
    right: list[dict] = []
    inline: list[dict] = []

    def push(side: list[dict], t: str, s: str) -> None:
        if not s:
            return
        if side and side[-1]["t"] == t:
            side[-1]["s"] += s
        else:
            side.append({"t": t, "s": s})

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            push(left, "eq", "".join(ta[i1:i2]))
            push(right, "eq", "".join(tb[j1:j2]))
            push(inline, "eq", "".join(ta[i1:i2]))
        else:
            push(left, "del", "".join(ta[i1:i2]))
            push(right, "ins", "".join(tb[j1:j2]))
            push(inline, "del", "".join(ta[i1:i2]))
            push(inline, "ins", "".join(tb[j1:j2]))
    return _absorb_spaces(left), _absorb_spaces(right), _absorb_spaces(inline)


def _absorb_spaces(segs: list[dict]) -> list[dict]:
    """Avoid highlighting that consists only of whitespace."""
    out: list[dict] = []
    for seg in segs:
        t = seg["t"] if seg["s"].strip() else "eq"
        if out and out[-1]["t"] == t:
            out[-1]["s"] += seg["s"]
        else:
            out.append({"t": t, "s": seg["s"]})
    return out


_LABEL = re.compile(r"^(?:\(\w{1,4}\)|\w{1,4}[.)])")


def _similarity(a: str, b: str) -> float:
    score = SequenceMatcher(None, a, b, autojunk=False).ratio()
    # lines with the same label ("b)", "(3)", "2.") are usually the same unit
    la, lb = _LABEL.match(a), _LABEL.match(b)
    if la and lb and la.group() == lb.group():
        score += 0.15
    return score


def diff_units(before: Node | None, after: Node | None) -> list[dict]:
    """Rows for a side-by-side view.

    Each row: {"op": "equal"|"change"|"delete"|"insert", "depth": int,
               "left": segments | None, "right": segments | None}
    """
    a_lines = render_lines(before) if before else []
    b_lines = render_lines(after) if after else []
    ka = [comparable(t) for _, t in a_lines]
    kb = [comparable(t) for _, t in b_lines]
    rows: list[dict] = []
    sm = SequenceMatcher(None, ka, kb, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for (d, t), (_, u) in zip(a_lines[i1:i2], b_lines[j1:j2]):
                rows.append({"op": "equal", "depth": d, "left": [{"t": "eq", "s": t}],
                             "right": [{"t": "eq", "s": u}], "inline": [{"t": "eq", "s": u}]})
            continue
        rows.extend(_pair_block(a_lines[i1:i2], b_lines[j1:j2]))
    return rows


def _pair_block(a: list[tuple[int, str]], b: list[tuple[int, str]]) -> list[dict]:
    """Align a replaced block line by line, pairing similar lines."""
    rows: list[dict] = []
    j = 0
    for i, (da, ta) in enumerate(a):
        # look ahead for the best partner on the right side
        best, best_score = None, 0.0
        for k in range(j, min(len(b), j + 4)):
            score = _similarity(comparable(ta), comparable(b[k][1]))
            if score > best_score:
                best, best_score = k, score
        if best is not None and best_score >= 0.45:
            for k in range(j, best):
                rows.append(_insert_row(b[k]))
            left, right, inline = word_diff(ta, b[best][1])
            rows.append({"op": "change", "depth": b[best][0], "left": left, "right": right, "inline": inline})
            j = best + 1
        else:
            seg = [{"t": "del", "s": ta}]
            rows.append({"op": "delete", "depth": da, "left": seg, "right": None, "inline": seg})
    for k in range(j, len(b)):
        rows.append(_insert_row(b[k]))
    return rows


def _insert_row(line: tuple[int, str]) -> dict:
    seg = [{"t": "ins", "s": line[1]}]
    return {"op": "insert", "depth": line[0], "left": None, "right": seg, "inline": seg}


def stats(rows: list[dict]) -> dict:
    return {
        "changed": sum(r["op"] == "change" for r in rows),
        "inserted": sum(r["op"] == "insert" for r in rows),
        "deleted": sum(r["op"] == "delete" for r in rows),
    }
