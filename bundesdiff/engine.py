"""Apply amendment instructions to a law tree – forwards and backwards.

The consolidated text we can download (NeuRIS) may already contain the
changes of a publication ("post" state) or not yet ("pre" state). For each §
we decide which state the current text is in, by checking the instructions
against it, and then

* pre:  before = current, after = current + instructions applied
* post: after = current, before = current with instructions reversed

Reversing is exact for most text-level edits. Where the old wording is not
contained in the instruction (replaced units, deleted text), it is taken from
a snapshot of an earlier version (local cache or Internet Archive).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .amendments import Instruction, Step
from .model import Node, comparable, normalize, split_sentences

UNKNOWN = "⟪frühere Fassung nicht ermittelbar⟫"


class ApplyError(Exception):
    pass


SnapshotFn = Callable[[str], "tuple[Node, str] | None"]


def par_node_key(step_key: str) -> str:
    return step_key if step_key.startswith(("art", "§")) else "§" + step_key


# --------------------------------------------------------------------------
# Locating units


def find_par(law: Node, key: str) -> tuple[Node, int] | None:
    key = par_node_key(key)
    for i, p in enumerate(law.parts):
        if isinstance(p, Node) and p.kind == "par" and p.key == key:
            return p, i
    return None


def unit_steps(path: list[Step]) -> list[Step]:
    return [s for s in path if s.kind not in ("satz", "heading", "intro", "outro")]


def _transparent(node: Node) -> bool:
    return node.kind == "block" or (node.kind == "abs" and not node.label)


def _sentence_count(text: str, so_far: int) -> int:
    """Sentences that ``text`` adds to a unit which has ``so_far`` sentences already."""
    sentences = split_sentences(text)
    # text after a list that starts in lower case continues the sentence before the list
    return len(sentences) - (1 if sentences and sentences[0][:1].islower() and so_far else 0)


def _units_by_sentence(node: Node, kind: str) -> list[tuple[int, Node, int]]:
    """The sub-units of ``kind`` with the sentence that introduces them: (sentence, container, index).

    "Satz 3 Nummer 1" names the list that follows the third sentence of the unit – an Absatz can
    hold several lists, each with its own Nummer 1.
    """
    found: list[tuple[int, Node, int]] = []
    count = 0

    def walk(n: Node) -> None:
        nonlocal count
        for i, p in enumerate(n.parts):
            if isinstance(p, str):
                count += _sentence_count(p, count)
            elif p.kind == kind:
                found.append((count, n, i))
            elif _transparent(p):
                walk(p)

    walk(node)
    return found


def _in_sentence(node: Node, st: Step, satz: Step) -> list[tuple[Node, int]]:
    """(container, index) of the units ``st`` in the list introduced by sentence ``satz`` of ``node``."""
    units = _units_by_sentence(node, st.kind)
    wanted = [(n, c, i) for n, c, i in units if str(n) == satz.keys[0]]
    if not wanted:
        # the sentences were counted differently: only safe when the unit has a single list
        runs = {n for n, _, _ in units}
        if len(runs) != 1:
            return []
        wanted = units
    container = wanted[0][1]
    keys = _keys_for(st, container)
    return [(c, i) for _, c, i in wanted if c is container and c.parts[i].key in keys]


def resolve(law: Node, path: list[Step]) -> Node:
    steps = unit_steps(path)
    if not steps or steps[0].kind != "par":
        raise ApplyError("Fundstelle ohne Paragraph – nicht auswertbar")
    found = find_par(law, steps[0].keys[0])
    if not found:
        raise ApplyError(f"§ {steps[0].keys[0]} nicht gefunden")
    node = found[0]
    satz: Step | None = None
    for st in path[next(i for i, s in enumerate(path) if s is steps[0]) + 1:]:
        if st.kind == "satz":
            satz = st
            continue
        if st.kind in ("heading", "intro", "outro"):
            continue
        if satz is not None:
            hits = _in_sentence(node, st, satz)
            child = (hits[0][0].parts[hits[0][1]], 0) if hits else None
            satz = None
        else:
            child = node.find_child(st.kind, st.keys[0])
        if not child:
            raise ApplyError(f"{st.label()} nicht gefunden")
        node = child[0]
    return node


def _satz_before_last_unit(path: list[Step]) -> Step | None:
    """The "Satz 3" of "Satz 3 Nummer 1": a sentence step directly before the last unit step."""
    units = [i for i, s in enumerate(path) if s.kind not in ("satz", "heading", "intro", "outro")]
    if len(units) < 2:
        return None
    between = [s for s in path[units[-2] + 1: units[-1]] if s.kind == "satz"]
    return between[-1] if between else None


def select_units(law: Node, path: list[Step]) -> tuple[Node, list[int]]:
    """Container and indices of the units addressed by the last path step."""
    steps = unit_steps(path)
    last = steps[-1]
    if last.kind == "par":
        container = law
    else:
        parent = resolve(law, path[: next(i for i, s in enumerate(path) if s is last)])
        satz = _satz_before_last_unit(path)
        if satz is not None:
            # never fall back to the unit's other lists: their "Nummer 1" is a different one
            hits = _in_sentence(parent, last, satz)
            return (hits[0][0], [i for _, i in hits]) if hits else (parent.container_for(last.kind), [])
        container = parent.container_for(last.kind)
    idx = [i for i, p in enumerate(container.parts)
           if isinstance(p, Node) and p.kind == last.kind and p.key in _keys_for(last, container)]
    return container, idx


def _keys_for(step: Step, container: Node) -> set[str]:
    keys = {par_node_key(k) for k in step.keys} if step.kind == "par" else set(step.keys)
    if step.is_range and len(step.keys) == 2:
        order = [p.key for p in container.parts if isinstance(p, Node) and p.kind == step.kind]
        a, b = (par_node_key(k) if step.kind == "par" else k for k in step.keys)
        if a in order and b in order:
            keys = set(order[order.index(a): order.index(b) + 1])
    return keys


# --------------------------------------------------------------------------
# Text slots (positions of text inside a unit)


@dataclass
class Slot:
    node: Node
    idx: int | str  # index into node.parts, or "heading"
    start: int = 0
    end: int | None = None

    def get(self) -> str:
        return self.node.heading if self.idx == "heading" else self.node.parts[self.idx]

    def set(self, value: str) -> None:
        if self.idx == "heading":
            self.node.heading = value
        else:
            self.node.parts[self.idx] = value

    @property
    def stop(self) -> int:
        return len(self.get()) if self.end is None else self.end

    def region(self) -> str:
        return self.get()[self.start:self.stop]


def own_sentence_slots(node: Node) -> list[Slot]:
    """One slot per sentence of the unit's own text (not its sub-units)."""
    # a § without Absätze: its text lies in one unnumbered Absatz ("In § 6 Satz 2 …")
    while not node.texts() and len(node.children) == 1 and _transparent(node.children[0]):
        node = node.children[0]
    slots: list[Slot] = []
    for i, p in enumerate(node.parts):
        if not isinstance(p, str):
            continue
        pos = 0
        for k, sent in enumerate(split_sentences(p)):
            start = p.find(sent, pos)
            if start < 0:
                continue
            end = start + len(sent)
            pos = end
            continuation = k == 0 and sent[:1].islower() and slots
            if continuation:
                continue  # text after a list continues the sentence before it
            slots.append(Slot(node, i, start, end))
    return slots


def text_slots(node: Node, path: list[Step]) -> list[Slot]:
    if path and path[-1].kind == "heading":
        return [Slot(node, "heading")]
    part = next((s.kind for s in path if s.kind in ("intro", "outro")), None)
    if part:
        # own text before the first / after the last sub-unit
        first_child = next((i for i, p in enumerate(node.parts) if isinstance(p, Node)), len(node.parts))
        last_child = max((i for i, p in enumerate(node.parts) if isinstance(p, Node)), default=-1)
        idx = [i for i, p in enumerate(node.parts) if isinstance(p, str)
               and (i < first_child if part == "intro" else i > last_child)]
        return [Slot(node, i) for i in idx]
    satz = next((s for s in reversed(path) if s.kind == "satz"), None)
    if satz and any(s.kind not in ("satz", "heading", "intro", "outro")
                    for s in path[next(i for i, s in enumerate(path) if s is satz):]):
        satz = None  # "Satz 3 Nummer 1": the sentence chose the list (resolve), the text is the Nummer's
    if satz:
        slots = own_sentence_slots(node)
        out = []
        for k in satz.keys:
            if not k.isdigit() or int(k) > len(slots):
                raise ApplyError(f"Satz {k} nicht gefunden")
            out.append(slots[int(k) - 1])
        return out
    out = []

    def walk(n: Node):
        for i, p in enumerate(n.parts):
            if isinstance(p, str):
                out.append(Slot(n, i))
            else:
                walk(p)

    walk(node)
    return out


def _pattern(needle: str) -> re.Pattern:
    parts = []
    for ch in normalize(needle):
        if ch == " ":
            parts.append(r"\s*")
        elif ch in "„“”\"":
            parts.append("[„“”\"]")
        elif ch in "–-":
            parts.append("[–-]")
        else:
            parts.append(re.escape(ch))
    return re.compile("".join(parts))


def find_all(slots: list[Slot], needle: str) -> list[tuple[Slot, int, int]]:
    rx = _pattern(needle)
    hits = []
    for slot in slots:
        text = slot.get()
        for m in rx.finditer(text, slot.start, slot.stop):
            hits.append((slot, m.start(), m.end()))
    return hits


def splice(slot: Slot, start: int, end: int, new: str) -> None:
    text = slot.get()
    result = text[:start] + new + text[end:]
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\s+([,.;:)])", r"\1", result) if not new.strip() else result
    slot.set(result.strip())


def _join(a: str, b: str) -> str:
    if not a:
        return b
    if not b or b[0] in ",.;:)" or a.endswith(("(", " ")):
        return a + b
    return a + " " + b


# --------------------------------------------------------------------------
# Snapshots


@dataclass
class Snapshots:
    """Earlier versions of single §§, fetched lazily."""

    fetch: SnapshotFn
    cache: dict = field(default_factory=dict)
    used: dict = field(default_factory=dict)  # par key -> source description

    def par(self, key: str) -> Node | None:
        key = par_node_key(key)
        if key not in self.cache:
            self.cache[key] = self.fetch(key)
        hit = self.cache[key]
        if hit:
            self.used[key] = hit[1]
            return hit[0]
        return None

    def law_view(self, key: str) -> Node | None:
        """A pseudo law containing only the snapshot §, for path resolution."""
        node = self.par(key)
        return Node("law", parts=[node.clone()]) if node else None


def _unknown_like(kind: str, label: str) -> Node:
    return Node(kind, label, parts=[UNKNOWN])


# --------------------------------------------------------------------------
# Checks: is the current text before or after the instruction?


def check(law: Node, ins: Instruction) -> str | None:
    try:
        return _check(law, ins)
    except ApplyError:
        return None


def _check(law: Node, ins: Instruction) -> str | None:
    a = ins.args
    op = ins.op
    if op in ("replace_text", "delete_text", "insert_text", "append_text"):
        scope = resolve(law, ins.path)
        slots = text_slots(scope, ins.path)
        if op == "replace_text":
            old, new = a["old"], a["new"]
            if a.get("at_end"):
                tail = comparable(slots[-1].region())[-max(len(comparable(new)), 1):] if slots else ""
                return "post" if tail.endswith(comparable(new) or "\0") else "pre"
            n_old, n_new = len(find_all(slots, old)), len(find_all(slots, new))
            if comparable(old) in comparable(new):
                return "post" if n_new else ("pre" if n_old else None)
            if comparable(new) in comparable(old):
                return "pre" if n_old else ("post" if n_new else None)
            if n_old and not n_new:
                return "pre"
            if n_new and not n_old:
                return "post"
            return None
        if op == "delete_text":
            return "pre" if find_all(slots, a["old"]) else "post"
        if op == "insert_text":
            combo = _join(a["new"], a["anchor"]) if a.get("before") else _join(a["anchor"], a["new"])
            if find_all(slots, combo):
                return "post"
            return "pre" if find_all(slots, a["anchor"]) else None
        if op == "append_text":
            return "post" if comparable(scope.body_text()).endswith(comparable(a["new"])) else "pre"
    if op == "replace_units":
        new_nodes = _quote_nodes(ins)
        container, idx = _select_for_check(law, ins.path, new_nodes)
        if not idx:
            return None
        current = " ".join(container.parts[i].full_text() for i in idx)
        wanted = " ".join(n.full_text() for n in new_nodes)
        return "post" if comparable(current) == comparable(wanted) else "pre"
    if op in ("insert_units", "append_units"):
        new_nodes = _quote_nodes(ins)
        if not new_nodes:
            return None
        container = _container_for_new(law, ins, new_nodes[0].kind)
        if container is None:
            return None
        existing = {p.key: p for p in container.parts if isinstance(p, Node) and p.kind == new_nodes[0].kind}
        hit = existing.get(new_nodes[0].key)
        if hit is None:
            return "pre"
        same = comparable(hit.body_text()) == comparable(new_nodes[0].body_text())
        return "post" if same or not hit.is_repealed() else "pre"
    if op == "delete_units":
        try:
            container, idx = select_units(law, ins.path)
        except ApplyError:
            return "post"
        if not idx:
            return "post"
        return "post" if all(container.parts[i].is_repealed() for i in idx) else "pre"
    if op in ("replace_sentence", "insert_sentence", "append_sentence"):
        scope = resolve(law, ins.path)
        return "post" if find_all(text_slots(scope, []), a["new"]) else "pre"
    if op == "replace_heading":
        scope = resolve(law, ins.path)
        return "post" if comparable(scope.heading) == comparable(a["new"]) else "pre"
    if op == "renumber":
        container, idx = select_units(law, ins.path)
        last = unit_steps(ins.path)[-1]
        targets = {par_node_key(k) if last.kind == "par" else k for k in a["to"]}
        has_new = any(isinstance(p, Node) and p.kind == last.kind and p.key in targets for p in container.parts)
        if idx and not has_new:
            return "pre"
        if has_new and not idx:
            return "post"
        return None
    return None


def _quote_nodes(ins: Instruction) -> list[Node]:
    tree = ins.args["quote"].tree()
    nodes = [p for p in tree.parts if isinstance(p, Node)]
    if not nodes and tree.parts:
        # quoted unit without a label, e.g. the text of an unnumbered paragraph
        last = unit_steps(ins.path)[-1] if unit_steps(ins.path) else None
        kind = last.kind if last else "abs"
        nodes = [Node(kind, "", parts=list(tree.texts()))]
    return nodes


def _select_for_check(law: Node, path: list[Step], new_nodes: list[Node]) -> tuple[Node, list[int]]:
    """Units as addressed by the new keys (post state may have more units than the target)."""
    container, idx = select_units(law, path)
    new_keys = {n.key for n in new_nodes}
    extra = [i for i, p in enumerate(container.parts)
             if isinstance(p, Node) and p.key in new_keys and i not in idx and p.kind == new_nodes[0].kind]
    return container, sorted(set(idx) | set(extra))


def _container_for_new(law: Node, ins: Instruction, kind: str) -> Node | None:
    steps = unit_steps(ins.path)
    try:
        if kind == "par":
            return law
        if ins.op == "append_units":
            return resolve(law, steps).container_for(kind)
        return resolve(law, steps[:-1]).container_for(kind)
    except ApplyError:
        return None


# --------------------------------------------------------------------------
# Forward application


def forward(law: Node, ins: Instruction) -> None:
    a = ins.args
    op = ins.op
    if op in ("replace_text", "delete_text", "insert_text", "append_text"):
        scope = resolve(law, ins.path)
        slots = text_slots(scope, ins.path)
        if op == "append_text":
            target = slots[-1] if slots else None
            if not target:
                raise ApplyError("Kein Text zum Anfügen gefunden")
            target.set(_join(target.get(), a["new"]))
            return
        if op == "replace_text" and a.get("at_end"):
            slot = slots[-1]
            text = slot.get().rstrip()
            if not text.endswith(a["old"]):
                raise ApplyError(f"„{a['old']}“ am Ende nicht gefunden")
            new = a["new"]
            slot.set(text[: -len(a["old"])] + new if not new[:1].isalnum() else text[: -len(a["old"])] + " " + new)
            return
        needle = a["old"] if op != "insert_text" else a["anchor"]
        hits = find_all(slots, needle)
        if not hits:
            raise ApplyError(f"„{needle}“ nicht gefunden")
        if not a.get("all"):
            hits = hits[:1]
        for slot, s, e in reversed(hits):
            text = slot.get()
            if op == "replace_text":
                splice(slot, s, e, a["new"])
            elif op == "delete_text":
                splice(slot, s, e, "")
            elif a.get("before"):
                slot.set(text[:s] + _join(a["new"], text[s:]))
            else:
                slot.set(_join(text[:e], a["new"]) + text[e:])
        return

    if op == "replace_units":
        new_nodes = _quote_nodes(ins)
        container, idx = select_units(law, ins.path)
        if not idx:
            raise ApplyError(f"{ins.location} nicht gefunden")
        container.parts[idx[0]: idx[-1] + 1] = [n.clone() for n in new_nodes]
        return
    if op in ("insert_units", "append_units"):
        new_nodes = _quote_nodes(ins)
        if not new_nodes:
            raise ApplyError("Einzufügender Text nicht erkannt")
        kind = new_nodes[0].kind
        if op == "insert_units":
            container, idx = select_units(law, ins.path)
            if not idx:
                raise ApplyError(f"{ins.location} nicht gefunden")
            pos = idx[0] if a.get("before") else idx[-1] + 1
        else:
            container = _container_for_new(law, ins, kind)
            if container is None:
                raise ApplyError(f"{ins.location} nicht gefunden")
            same = [i for i, p in enumerate(container.parts) if isinstance(p, Node) and p.kind == kind]
            if a.get("prepend"):
                pos = same[0] if same else 0
            else:
                pos = same[-1] + 1 if same else len(container.parts)
        container.parts[pos:pos] = [n.clone() for n in new_nodes]
        return
    if op == "delete_units":
        container, idx = select_units(law, ins.path)
        if not idx:
            raise ApplyError(f"{ins.location} nicht gefunden")
        if a.get("repeal") and unit_steps(ins.path)[-1].kind in ("par", "abs"):
            for i in idx:
                container.parts[i].parts = ["(weggefallen)"]
                container.parts[i].heading = ""
        else:
            for i in reversed(idx):
                del container.parts[i]
        return
    if op in ("replace_sentence", "delete_sentence", "insert_sentence", "append_sentence"):
        scope = resolve(law, ins.path)
        slots = own_sentence_slots(scope)
        if op == "append_sentence":
            texts = [i for i, p in enumerate(scope.parts) if isinstance(p, str)]
            if not texts:
                scope.parts.append(a["new"])
            elif a.get("prepend"):
                scope.parts[texts[0]] = _join(a["new"], scope.parts[texts[0]])
            else:
                scope.parts[texts[-1]] = _join(scope.parts[texts[-1]], a["new"])
            return
        if op == "insert_sentence":
            k = int(a["after"])
            if k > len(slots):
                raise ApplyError(f"Satz {k} nicht gefunden")
            slot = slots[k - 1]
            text = slot.get()
            if a.get("before"):
                slot.set(_join(text[: slot.start] + a["new"], text[slot.start:]))
            else:
                slot.set(_join(text[: slot.stop], a["new"]) + text[slot.stop:])
            return
        targets = []
        for k in a["n"]:
            if not k.isdigit() or int(k) > len(slots):
                raise ApplyError(f"Satz {k} nicht gefunden")
            targets.append(slots[int(k) - 1])
        for j, slot in enumerate(reversed(targets)):
            first = j == len(targets) - 1
            replacement = a["new"] if (op == "replace_sentence" and first) else ""
            splice(slot, slot.start, slot.stop, replacement)
        return
    if op == "replace_heading":
        resolve(law, ins.path).heading = a["new"]
        return
    if op == "renumber":
        _renumber(law, ins.path, unit_steps(ins.path)[-1].keys, a["to"])
        return
    raise ApplyError("Änderungsbefehl nicht automatisch auswertbar")


def _renumber(law: Node, path: list[Step], src: list[str], dst: list[str]) -> None:
    last = unit_steps(path)[-1]
    container = law if last.kind == "par" else resolve(law, unit_steps(path)[:-1]).container_for(last.kind)
    nodes = {p.key: p for p in container.parts if isinstance(p, Node) and p.kind == last.kind}
    keyed = [par_node_key(k) if last.kind == "par" else k for k in src]
    if not all(k in nodes for k in keyed):
        raise ApplyError(f"{last.label()} nicht gefunden")
    for k, new_key in zip(keyed, dst):
        nodes[k].label = _display_label(last, new_key)


# --------------------------------------------------------------------------
# Reverse application


def reverse(law: Node, ins: Instruction, snaps: Snapshots) -> None:
    a = ins.args
    op = ins.op
    par_key = unit_steps(ins.path)[0].keys[0] if unit_steps(ins.path) else None

    def restore_scope(path: list[Step]) -> None:
        """Replace the unit at ``path`` with its version from the snapshot."""
        current = resolve(law, path)
        old_law = snaps.law_view(par_key) if par_key else None
        if old_law is None:
            raise ApplyError("Frühere Fassung nicht verfügbar")
        old = resolve(old_law, path)
        if unit_steps(path)[-1:] and unit_steps(path)[-1].kind == "par":
            current.heading, current.parts = old.heading, old.clone().parts
        else:
            current.parts = old.clone().parts
            current.heading = old.heading

    if op == "replace_text":
        scope = resolve(law, ins.path)
        slots = text_slots(scope, ins.path)
        if a.get("at_end"):
            slot = slots[-1]
            text = slot.get().rstrip()
            new = a["new"].strip()
            if not comparable(text).endswith(comparable(new)):
                raise ApplyError("Ersetzung am Ende nicht gefunden")
            slot.set(text[: len(text) - len(new)].rstrip() + a["old"])
            return
        hits = find_all(slots, a["new"])
        if not hits:
            raise ApplyError(f"„{a['new']}“ nicht gefunden")
        if not a.get("all"):
            hits = hits[:1]
        for slot, s, e in reversed(hits):
            splice(slot, s, e, a["old"])
        return
    if op == "insert_text":
        scope = resolve(law, ins.path)
        slots = text_slots(scope, ins.path)
        combo = _join(a["new"], a["anchor"]) if a.get("before") else _join(a["anchor"], a["new"])
        hits = find_all(slots, combo)
        if not hits:
            raise ApplyError(f"„{combo}“ nicht gefunden")
        if not a.get("all"):
            hits = hits[:1]
        for slot, s, e in reversed(hits):
            splice(slot, s, e, a["anchor"])
        return
    if op == "append_text":
        scope = resolve(law, ins.path)
        slot = text_slots(scope, ins.path)[-1]
        hits = find_all([slot], a["new"])
        if not hits:
            raise ApplyError(f"„{a['new']}“ nicht gefunden")
        _, s, e = hits[-1]
        splice(slot, s, e, "")
        return
    if op in ("delete_text", "replace_sentence", "delete_sentence", "replace_heading"):
        restore_scope(ins.path)
        return
    if op in ("insert_sentence", "append_sentence"):
        scope = resolve(law, ins.path)
        hits = find_all(text_slots(scope, []), a["new"])
        if not hits:
            raise ApplyError("Eingefügter Satz nicht gefunden")
        slot, s, e = hits[0]
        splice(slot, s, e, "")
        return
    if op == "renumber":
        last = unit_steps(ins.path)[-1]
        back = ins.path[:-1] + [Step(last.kind, list(a["to"]))]
        _renumber(law, back, a["to"], last.keys)
        return
    if op in ("insert_units", "append_units"):
        new_nodes = _quote_nodes(ins)
        kind = new_nodes[0].kind if new_nodes else None
        container = _container_for_new(law, ins, kind) if kind else None
        if container is None:
            raise ApplyError(f"{ins.location} nicht gefunden")
        keys = {n.key for n in new_nodes}
        before = len(container.parts)
        container.parts = [p for p in container.parts
                           if not (isinstance(p, Node) and p.kind == kind and p.key in keys)]
        if len(container.parts) == before:
            raise ApplyError("Eingefügte Einheit nicht gefunden")
        return
    if op in ("replace_units", "delete_units"):
        steps = unit_steps(ins.path)
        last = steps[-1]
        if op == "replace_units":
            new_nodes = _quote_nodes(ins)
            container, idx = _select_for_check(law, ins.path, new_nodes)
        else:
            try:
                container, idx = select_units(law, ins.path)
            except ApplyError:
                container, idx = None, []
            if container is None:
                container = law if last.kind == "par" else resolve(law, steps[:-1]).container_for(last.kind)
        # old units from the snapshot
        if last.kind == "par":
            old_units = [snaps.par(k) for k in last.keys]
            old_units = [u.clone() for u in old_units if u is not None]
        else:
            old_law = snaps.law_view(par_key)
            old_units = []
            if old_law is not None:
                try:
                    oc, oi = select_units(old_law, ins.path)
                    old_units = [oc.parts[i].clone() for i in oi]
                except ApplyError:
                    old_units = []
        if not old_units:
            old_units = [_unknown_like(last.kind, _display_label(last, k)) for k in last.keys]
        if idx:
            pos = idx[0]
            for i in reversed(idx):
                del container.parts[i]
        else:
            pos = _insert_position(container, last)
        container.parts[pos:pos] = old_units
        return
    raise ApplyError("Änderungsbefehl nicht automatisch auswertbar")


def _display_label(step: Step, key: str) -> str:
    return {"par": f"§ {key}", "abs": f"({key})", "nr": f"{key}.", "bst": f"{key})", "dbst": f"{key})",
            "tbst": f"{key})"}.get(step.kind, key)


def _sort_key(key: str) -> tuple:
    m = re.match(r"^\D*(\d+)([a-z]*)$", key)
    return (int(m.group(1)), m.group(2)) if m else (10**9, key)


def _insert_position(container: Node, step: Step) -> int:
    """Where a deleted unit used to be: after the last sibling with a smaller key."""
    target = _sort_key(par_node_key(step.keys[0]) if step.kind == "par" else step.keys[0])
    pos = 0
    for i, p in enumerate(container.parts):
        if isinstance(p, Node) and p.kind == step.kind and _sort_key(p.key) < target:
            pos = i + 1
    return pos


# --------------------------------------------------------------------------
# Whole amendment


@dataclass
class InstructionResult:
    instruction: Instruction
    state: str | None  # pre | post | None
    status: str  # applied | reversed | consolidated | failed | unsupported
    message: str = ""


@dataclass
class ParDiff:
    key: str
    before: Node | None
    after: Node | None
    state: str
    source_note: str = ""


@dataclass
class AmendmentResult:
    results: list[InstructionResult]
    pars: list[ParDiff]


def affected_pars(ins: Instruction) -> list[str]:
    steps = unit_steps(ins.path)
    if not steps or steps[0].kind != "par":
        return []
    keys = [par_node_key(k) for k in steps[0].keys] if len(steps) == 1 else [par_node_key(steps[0].keys[0])]
    if len(steps) == 1 and ins.op in ("insert_units", "append_units") and "quote" in ins.args:
        new = [n.key for n in _quote_nodes(ins) if n.kind == "par"]
        keys = new or keys
    return keys


def run(law: Node, instructions: list[Instruction], snaps: Snapshots, default_state: str,
        force_state: str | None = None) -> AmendmentResult:
    """``force_state="pre"``: the text is known not to contain the changes (a bill, spec 016 ENT-8)."""
    groups: dict[str, list[Instruction]] = {}
    results: dict[int, InstructionResult] = {}
    for ins in instructions:
        if ins.op == "unsupported" or any(s.kind in ("toc", "anlage") for s in ins.path):
            results[id(ins)] = InstructionResult(ins, None, "unsupported",
                                                 "Wird nicht automatisch ausgewertet (z. B. Inhaltsübersicht, "
                                                 "Anlagen oder unbekannte Formulierung).")
            continue
        pars = affected_pars(ins)
        if not pars:
            results[id(ins)] = InstructionResult(ins, None, "unsupported", "Fundstelle nicht erkannt.")
            continue
        groups.setdefault(pars[0], []).append(ins)

    before_law, after_law = law.clone(), law.clone()
    states: dict[str, str] = {}
    for key, group in groups.items():
        votes = [check(law, ins) for ins in group]
        pre, post = votes.count("pre"), votes.count("post")
        state = force_state or ("post" if post > pre else "pre" if pre > post else default_state)
        states[key] = state
        if state == "pre":
            for ins in group:
                try:
                    forward(after_law, ins)
                    results[id(ins)] = InstructionResult(ins, state, "applied")
                except ApplyError as e:
                    results[id(ins)] = InstructionResult(ins, state, "failed", str(e))
        else:
            for ins in reversed(group):
                try:
                    reverse(before_law, ins, snaps)
                    results[id(ins)] = InstructionResult(ins, state, "consolidated")
                except ApplyError as e:
                    results[id(ins)] = InstructionResult(ins, state, "failed", str(e))

    key_state: dict[str, str] = {}
    for key, group in groups.items():
        for ins in group:
            for k in affected_pars(ins):
                key_state.setdefault(k, states[key])

    pars: list[ParDiff] = []
    for key, state in key_state.items():
        b = find_par(before_law, key)
        a = find_par(after_law, key)
        pars.append(ParDiff(key, b[0] if b else None, a[0] if a else None, state, snaps.used.get(key, "")))
    return AmendmentResult([results[id(i)] for i in instructions], pars)
