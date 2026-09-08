"""Command line interface for the mission advisor.

    advise    review a catalog against a product brief
    catalog   print the rendered catalog (what the model actually sees)

Exit codes: 0 ok, 1 blocker-severity considerations present, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .advisor import MODEL, RefusalError, advise, build_mission_prompt, read_mission
from .catalog import load_catalog, render_catalog
from .report import render

EXIT_OK = 0
EXIT_BLOCKERS = 1
EXIT_BAD_INPUT = 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cmd_advise(args: argparse.Namespace) -> int:
    records = load_catalog(args.catalog)
    mission = read_mission(args.mission)
    bom = read_mission(args.bom) if args.bom else None
    findings = read_mission(args.engine_findings) if args.engine_findings else None

    if args.dry_run:
        print(render_catalog(records))
        print(build_mission_prompt(mission, bom, findings))
        return EXIT_OK

    print(f"Reviewing {len(records)} parts against the brief "
          f"({MODEL}, effort={args.effort})...", file=sys.stderr)
    try:
        out, usage = advise(
            mission=mission,
            records=records,
            current_bom=bom,
            engine_findings=findings,
            effort=args.effort,
        )
    except RefusalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    outdir = Path(args.out)
    _write(outdir / "considerations.json",
           json.dumps(out.model_dump(), indent=2) + "\n")
    _write(outdir / "considerations.md",
           render(out, mission_label=str(args.mission)[:80], usage=usage))

    blockers = [c for c in out.considerations if c.severity == "blocker"]
    by_action: dict[str, int] = {}
    for c in out.considerations:
        by_action[c.action] = by_action.get(c.action, 0) + 1

    print(f"\n{len(out.considerations)} considerations "
          f"({len(blockers)} blocker):")
    for action, n in sorted(by_action.items()):
        print(f"    {n:2d}  {action}")
    for c in blockers:
        print(f"\n  [BLOCKER] {c.title}")
        print(f"            {c.what_changes}")
    print(f"\n  -> {outdir}/considerations.md")
    print(f"  -> {outdir}/considerations.json")
    print(f"  tokens: {usage['input_tokens']} in / {usage['output_tokens']} out"
          f" / {usage['cache_read_input_tokens']} cached")

    return EXIT_BLOCKERS if blockers else EXIT_OK


def cmd_catalog(args: argparse.Namespace) -> int:
    print(render_catalog(load_catalog(args.catalog)))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mission_advisor",
        description="Review a part catalog against a product brief and produce "
                    "design considerations.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("advise", help="review the catalog against a brief")
    a.add_argument("--catalog", default="parts/catalog",
                   help="directory of part records")
    a.add_argument("--mission", required=True,
                   help="the product brief: inline text, or a path to a file")
    a.add_argument("--bom", default=None,
                   help="parts currently selected: inline text or a path")
    a.add_argument("--engine-findings", default=None,
                   help="measured results from the constraint engine: text or path")
    a.add_argument("--out", default="out/advisor", help="output directory")
    a.add_argument("--effort", default="high",
                   choices=["low", "medium", "high", "xhigh", "max"])
    a.add_argument("--dry-run", action="store_true",
                   help="print the assembled prompt without calling the model")
    a.set_defaults(func=cmd_advise)

    c = sub.add_parser("catalog", help="print the rendered catalog")
    c.add_argument("--catalog", default="parts/catalog")
    c.set_defaults(func=cmd_catalog)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
