"""The map read as a graph rather than a list.

A function map is only a spreadsheet until you follow the artifacts. Once
inputs and outputs are ids rather than prose, "where does this number come
from" stops being a question you ask a colleague and becomes a lookup, and
that is the single most useful thing the format buys.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import FunctionMap


@dataclass
class TraceNode:
    kind: str            # "artifact" or "function"
    id: str
    label: str
    detail: str = ""
    children: list = field(default_factory=list)
    repeated: bool = False   # already expanded higher up this branch
    truncated: bool = False  # the depth limit stopped the walk here


def producers(fmap: FunctionMap, artifact_id: str) -> list:
    return [fn for fn in fmap.functions if artifact_id in fn.outputs]


def consumers(fmap: FunctionMap, artifact_id: str) -> list:
    return [fn for fn in fmap.functions if artifact_id in fn.inputs]


def trace(
    fmap: FunctionMap, artifact_id: str, direction: str = "upstream", depth: int = 3
) -> TraceNode:
    """Walk from an artifact to the functions that produce or consume it.

    ``upstream`` answers "what has to happen before this exists". ``downstream``
    answers "what breaks if this stops arriving", which is the question people
    actually ask when a supplier changes a file format.
    """
    if direction not in ("upstream", "downstream"):
        raise ValueError("direction must be 'upstream' or 'downstream'")
    artifact = fmap.artifact(artifact_id)
    if artifact is None:
        raise KeyError(artifact_id)
    return _artifact_node(fmap, artifact_id, direction, depth, set())


def _artifact_node(
    fmap: FunctionMap, artifact_id: str, direction: str, depth: int, seen: set
) -> TraceNode:
    artifact = fmap.artifact(artifact_id)
    node = TraceNode("artifact", artifact_id, artifact.name, artifact.boundary)
    if artifact_id in seen:
        node.repeated = True
        return node
    if depth <= 0:
        node.truncated = True
        return node
    upstream = direction == "upstream"
    linked = producers(fmap, artifact_id) if upstream else consumers(fmap, artifact_id)
    for fn in sorted(linked, key=lambda f: f.id):
        node.children.append(
            _function_node(fmap, fn.id, direction, depth - 1, seen | {artifact_id})
        )
    return node


def _function_node(
    fmap: FunctionMap, function_id: str, direction: str, depth: int, seen: set
) -> TraceNode:
    fn = fmap.function(function_id)
    owner = fmap.actor(fn.owner).name if fn.owner and fmap.actor(fn.owner) else "no owner"
    node = TraceNode("function", fn.id, fn.name, owner)
    if function_id in seen:
        node.repeated = True
        return node
    if depth <= 0:
        node.truncated = True
        return node
    linked = fn.inputs if direction == "upstream" else fn.outputs
    for artifact_id in linked:
        node.children.append(
            _artifact_node(fmap, artifact_id, direction, depth - 1, seen | {function_id})
        )
    return node


def flatten(node: TraceNode) -> list:
    """Depth-first list of (indent, node), which is all the renderer needs."""
    out: list = []

    def walk(current: TraceNode, level: int) -> None:
        out.append((level, current))
        for child in current.children:
            walk(child, level + 1)

    walk(node, 0)
    return out


def dependency_edges(fmap: FunctionMap) -> dict:
    """function id -> ids of functions consuming anything it produces."""
    by_input: dict = {}
    for fn in fmap.functions:
        for artifact_id in fn.inputs:
            by_input.setdefault(artifact_id, []).append(fn.id)
    edges: dict = {fn.id: set() for fn in fmap.functions}
    for fn in fmap.functions:
        for artifact_id in fn.outputs:
            for consumer in by_input.get(artifact_id, []):
                if consumer != fn.id:
                    edges[fn.id].add(consumer)
    return {k: sorted(v) for k, v in edges.items()}


def strongly_connected(fmap: FunctionMap) -> list:
    """Groups of functions that can all reach each other. Tarjan, iterative.

    Recursion is avoided on purpose: the depth is the length of a dependency
    chain, and a map of a real company is written by people, not bounded by
    anyone's stack limit.
    """
    edges = dependency_edges(fmap)
    index: dict = {}
    low: dict = {}
    on_stack: set = set()
    stack: list = []
    groups: list = []
    counter = 0

    for start in sorted(edges):
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            node, child_i = work[-1]
            if child_i == 0:
                index[node] = low[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            children = edges.get(node, [])
            if child_i < len(children):
                work[-1] = (node, child_i + 1)
                nxt = children[child_i]
                if nxt not in index:
                    work.append((nxt, 0))
                elif nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                group = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    group.append(member)
                    if member == node:
                        break
                groups.append(sorted(group))
    return groups


def cycles(fmap: FunctionMap) -> list:
    """Loops in the function graph: one representative path per group.

    A loop is not automatically a defect. Plenty of real work goes round: a
    forecast feeds a plan, and last month's plan feeds the forecast. It is
    worth surfacing because a loop is where an unattended automation can run
    away, and because an accidental one usually means one artifact is quietly
    doing two jobs.

    Reported per strongly connected component rather than as every elementary
    cycle. Listing them all is exponential, and a reader who has been handed
    four hundred overlapping loops has been handed nothing.
    """
    edges = dependency_edges(fmap)
    loops: list = []
    for group in strongly_connected(fmap):
        members = set(group)
        if len(group) == 1:
            only = group[0]
            if only in edges.get(only, []):
                loops.append([only])
            continue
        loops.append(_shortest_loop(edges, members, group[0]))
    return sorted(loops, key=lambda loop: (len(loop), loop))


def _shortest_loop(edges: dict, members: set, start: str) -> list:
    """The shortest path from ``start`` back to itself, staying inside the group."""
    previous: dict = {}
    queue = [start]
    seen = {start}
    while queue:
        node = queue.pop(0)
        for nxt in edges.get(node, []):
            if nxt not in members:
                continue
            if nxt == start:
                path = [node]
                while path[-1] != start:
                    path.append(previous[path[-1]])
                return list(reversed(path))
            if nxt not in seen:
                seen.add(nxt)
                previous[nxt] = node
                queue.append(nxt)
    return sorted(members)
