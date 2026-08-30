"""The command line. Five commands, each of which also answers in JSON.

Exit codes are part of the interface:

    0   the command ran and found nothing wrong
    1   the map is invalid, or a check was asked to be strict and failed
    2   the command could not be run at all: no such file, no such artifact,
        a setting that is present and unusable
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from . import config, gaps, graph, report
from .automatability import assess, rank
from .loader import MapError, load

OK = 0
FOUND_PROBLEMS = 1
CANNOT_RUN = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="business-mapping",
        description="Read a function map: check it, rank what an agent could take, "
        "trace where an artifact comes from, and find the holes.",
    )
    parser.add_argument(
        "--map",
        dest="map_path",
        default=None,
        help="path to the map. Defaults to FUNCTION_MAP_PATH, then the bundled example",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="check the map against the schema")

    p_rank = sub.add_parser("rank", help="functions worth automating, most hours first")
    p_rank.add_argument("--pattern", default=None, help="show only one pattern")
    p_rank.add_argument(
        "--limit", type=int, default=None, help="rows to show; 0 for all. Defaults to RANK_LIMIT"
    )

    p_trace = sub.add_parser("trace", help="follow an artifact through the company")
    p_trace.add_argument("artifact", help="artifact id")
    p_trace.add_argument(
        "--downstream",
        action="store_true",
        help="follow what consumes it instead of what produces it",
    )
    p_trace.add_argument("--depth", type=int, default=3, help="how far to follow")

    p_gaps = sub.add_parser("gaps", help="unowned functions, orphaned artifacts, loops")
    p_gaps.add_argument("--strict", action="store_true", help="exit 1 if anything is found")

    sub.add_parser("report", help="the overview: where the hours are and what blocks them")
    return parser


def main(argv=None, stdout=None) -> int:
    out = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        path = args.map_path or config.map_path()
    except config.ConfigError as exc:
        print(exc, file=out)
        return CANNOT_RUN

    try:
        fmap = load(path)
    except MapError as exc:
        if args.command != "validate":
            print(report.render_errors(exc.path, exc.errors), file=out)
            return FOUND_PROBLEMS
        if args.json:
            print(
                json.dumps(
                    {
                        "path": str(exc.path),
                        "valid": False,
                        "errors": [dataclasses.asdict(e) for e in exc.errors],
                    },
                    indent=2,
                ),
                file=out,
            )
        else:
            print(report.render_errors(exc.path, exc.errors), file=out)
        return FOUND_PROBLEMS

    try:
        return _dispatch(args, fmap, out)
    except config.ConfigError as exc:
        print(exc, file=out)
        return CANNOT_RUN


def _dispatch(args, fmap, out) -> int:
    if args.command == "validate":
        if args.json:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "company": fmap.company,
                        "functions": len(fmap.functions),
                        "actors": len(fmap.actors),
                        "artifacts": len(fmap.artifacts),
                    },
                    indent=2,
                ),
                file=out,
            )
        else:
            print(report.render_validation_ok(fmap), file=out)
        return OK

    if args.command == "rank":
        limit = args.limit if args.limit is not None else config.rank_limit()
        if args.json:
            payload = [
                {"function": fn.id, "name": fn.name, "owner": fn.owner, "area": fn.area}
                | dataclasses.asdict(verdict)
                for fn, verdict in rank(fmap.functions, args.pattern)[: limit or None]
            ]
            print(json.dumps(payload, indent=2), file=out)
        else:
            print(report.render_rank(fmap, args.pattern, limit or None), file=out)
        return OK

    if args.command == "trace":
        direction = "downstream" if args.downstream else "upstream"
        if fmap.artifact(args.artifact) is None:
            print(f"no artifact with id '{args.artifact}'", file=out)
            return CANNOT_RUN
        if args.json:
            root = graph.trace(fmap, args.artifact, direction, args.depth)
            print(json.dumps(_node_json(root), indent=2), file=out)
        else:
            print(report.render_trace(fmap, args.artifact, direction, args.depth), file=out)
        return OK

    if args.command == "gaps":
        findings = gaps.find(fmap)
        if args.json:
            print(json.dumps([dataclasses.asdict(f) for f in findings], indent=2), file=out)
        else:
            print(report.render_gaps(findings), file=out)
        return FOUND_PROBLEMS if (findings and args.strict) else OK

    if args.command == "report":
        if args.json:
            payload = report.summarise(fmap)
            payload["gaps"] = [dataclasses.asdict(f) for f in gaps.find(fmap)]
            payload["functions_detail"] = [
                {"function": fn.id} | dataclasses.asdict(assess(fn)) for fn in fmap.functions
            ]
            print(json.dumps(payload, indent=2), file=out)
        else:
            print(report.render_report(fmap), file=out)
        return OK

    raise AssertionError(f"unhandled command {args.command!r}")


def _node_json(node) -> dict:
    return {
        "kind": node.kind,
        "id": node.id,
        "label": node.label,
        "detail": node.detail,
        "repeated": node.repeated,
        "truncated": node.truncated,
        "children": [_node_json(child) for child in node.children],
    }
