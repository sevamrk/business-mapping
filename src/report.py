"""Rendering. Everything here takes a map and returns text or plain data.

Both shapes exist for the same reason the project exists: a person reads the
table, and a program reads ``--json``. A map is meant to be something an agent
can act on, so every command answers in both.
"""

from __future__ import annotations

from . import config, gaps, graph, vocab
from .automatability import assess, rank
from .model import FunctionMap


def table(headers, rows, aligns=None) -> str:
    """A plain text table. No dependency earns its place for this."""
    rows = [[str(cell) for cell in row] for row in rows]
    headers = [str(h) for h in headers]
    aligns = aligns or ["<"] * len(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = "  ".join(f"{h:<{widths[i]}}" for i, h in enumerate(headers)).rstrip()
    rule = "  ".join("-" * w for w in widths)
    out = [line, rule]
    for row in rows:
        out.append(
            "  ".join(f"{cell:{aligns[i]}{widths[i]}}" for i, cell in enumerate(row)).rstrip()
        )
    return "\n".join(out)


# --- validate ---------------------------------------------------------------

def render_validation_ok(fmap: FunctionMap) -> str:
    return (
        f"{fmap.company}: {len(fmap.functions)} functions, {len(fmap.actors)} actors, "
        f"{len(fmap.artifacts)} artifacts, {len(fmap.areas)} areas. No problems."
    )


def render_errors(path, errors) -> str:
    head = f"{path}: {len(errors)} problem(s)"
    body = table(
        ["where", "code", "problem"],
        [[e.path, e.code, e.message] for e in errors],
    )
    return f"{head}\n\n{body}"


# --- rank -------------------------------------------------------------------

def render_rank(fmap: FunctionMap, pattern=None, limit=None) -> str:
    pairs = rank(fmap.functions, pattern)
    shown = pairs[:limit] if limit else pairs
    rows = []
    for fn, verdict in shown:
        owner = fmap.actor(fn.owner).name if fn.owner and fmap.actor(fn.owner) else "-"
        rows.append(
            [
                fn.id,
                fn.name,
                owner,
                f"{verdict.hours_per_year:,.0f}",
                f"{verdict.readiness:.2f}",
                verdict.risk_band,
                verdict.pattern,
                f"{verdict.recoverable_hours:,.0f}",
            ]
        )
    head = ["id", "function", "owner", "hrs/yr", "ready", "risk", "pattern", "recover"]
    aligns = ["<", "<", "<", ">", ">", "<", "<", ">"]
    out = table(head, rows, aligns)
    if limit and len(pairs) > limit:
        out += f"\n\n{len(pairs) - limit} more; raise RANK_LIMIT or pass --limit 0"
    return out


# --- trace ------------------------------------------------------------------

def render_trace(fmap: FunctionMap, artifact_id: str, direction: str, depth: int) -> str:
    root = graph.trace(fmap, artifact_id, direction, depth)
    verb = "is produced by" if direction == "upstream" else "is used by"
    arrow = "<-" if direction == "upstream" else "->"
    lines = [f"{root.label} ({root.id}) {verb}:"]
    for level, node in graph.flatten(root):
        if level == 0:
            continue
        indent = "  " * level
        if node.kind == "function":
            body = f"fn {node.label}  [{node.detail}]"
        else:
            body = f"{arrow} {node.label}"
        if node.repeated:
            body += "   (already shown above)"
        elif node.truncated:
            body += "   (goes further, raise --depth)"
        elif node.kind == "artifact" and not node.children:
            body += f"   ({node.detail}, nothing further)"
        lines.append(indent + body)
    if len(lines) == 1:
        boundary = fmap.artifact(artifact_id).boundary
        lines.append(f"  nothing. It is declared {boundary}.")
    return "\n".join(lines)


# --- gaps -------------------------------------------------------------------

def render_gaps(findings) -> str:
    if not findings:
        return "No gaps found."
    rows = [[f.severity, f.code, f.subject, f.message] for f in findings]
    counts: dict = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    summary = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts)
    listing = table(["severity", "code", "subject", "detail"], rows)
    return f"{listing}\n\n{len(findings)} findings: {summary}"


# --- report -----------------------------------------------------------------

def summarise(fmap: FunctionMap) -> dict:
    """The numbers behind the overview, so the text and the JSON cannot disagree."""
    by_pattern: dict = {
        p: {"functions": 0, "hours": 0.0, "recoverable": 0.0} for p in vocab.PATTERNS
    }
    by_area: dict = {}
    total_hours = 0.0
    total_recoverable = 0.0
    automated_hours = 0.0

    for fn in fmap.functions:
        verdict = assess(fn)
        bucket = by_pattern[verdict.pattern]
        bucket["functions"] += 1
        bucket["hours"] += verdict.hours_per_year
        bucket["recoverable"] += verdict.recoverable_hours
        area = by_area.setdefault(
            fn.area, {"functions": 0, "hours": 0.0, "recoverable": 0.0, "unowned": 0}
        )
        area["functions"] += 1
        area["hours"] += verdict.hours_per_year
        area["recoverable"] += verdict.recoverable_hours
        if fn.owner is None:
            area["unowned"] += 1
        total_hours += verdict.hours_per_year
        total_recoverable += verdict.recoverable_hours
        automated_hours += verdict.hours_per_year * vocab.CURRENT_STATES[fn.current_state]

    fte = config.hours_per_fte_year()
    return {
        "company": fmap.company,
        "functions": len(fmap.functions),
        "actors": len(fmap.actors),
        "artifacts": len(fmap.artifacts),
        "areas": len(fmap.areas),
        "hours_per_year": round(total_hours, 1),
        "hours_already_automated": round(automated_hours, 1),
        "recoverable_hours": round(total_recoverable, 1),
        "recoverable_fte": round(total_recoverable / fte, 2),
        "hours_per_fte_year": fte,
        "by_pattern": {k: _round(v) for k, v in by_pattern.items()},
        "by_area": {k: _round(v) for k, v in by_area.items()},
    }


def _round(bucket: dict) -> dict:
    return {k: (round(v, 1) if isinstance(v, float) else v) for k, v in bucket.items()}


def render_report(fmap: FunctionMap) -> str:
    data = summarise(fmap)
    findings = gaps.find(fmap)

    lines = [
        f"{data['company']}",
        f"{data['functions']} functions, {data['actors']} actors, "
        f"{data['artifacts']} artifacts, {data['areas']} areas",
        f"{data['hours_per_year']:,.0f} hours a year of mapped work, of which "
        f"{data['hours_already_automated']:,.0f} already runs without a person",
        "",
        "What could be handed over",
    ]
    rows = []
    for pattern in vocab.PATTERNS:
        bucket = data["by_pattern"][pattern]
        if not bucket["functions"]:
            continue
        rows.append(
            [
                pattern,
                bucket["functions"],
                f"{bucket['hours']:,.0f}",
                f"{bucket['recoverable']:,.0f}",
            ]
        )
    lines.append(
        table(["pattern", "functions", "hrs/yr", "recoverable"], rows, ["<", ">", ">", ">"])
    )
    lines += [
        "",
        f"{data['recoverable_hours']:,.0f} recoverable hours a year, about "
        f"{data['recoverable_fte']:.1f} full-time people at "
        f"{data['hours_per_fte_year']:,.0f} hours each.",
        "That figure is readiness-weighted, and it is only as good as the volumes in the map.",
        "",
        "By area",
    ]
    area_rows = [
        [
            area,
            bucket["functions"],
            f"{bucket['hours']:,.0f}",
            f"{bucket['recoverable']:,.0f}",
            bucket["unowned"] or "",
        ]
        for area, bucket in sorted(
            data["by_area"].items(), key=lambda kv: -kv[1]["recoverable"]
        )
    ]
    lines.append(
        table(
            ["area", "functions", "hrs/yr", "recoverable", "unowned"],
            area_rows,
            ["<", ">", ">", ">", ">"],
        )
    )

    counts: dict = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    if findings:
        summary = ", ".join(f"{counts[s]} {s}" for s in ("high", "medium", "low") if s in counts)
        lines += [
            "",
            f"{len(findings)} gaps in the map itself: {summary}. Run `gaps` for the list.",
        ]
    else:
        lines += ["", "No gaps in the map itself."]
    return "\n".join(lines)
