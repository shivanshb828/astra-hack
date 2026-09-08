"""Command line interface.

    validate   check one layout, write results JSON + Markdown report
    solve      search for a corrected layout, write it, then validate it
    compare    validate several layouts side by side
    explain    emit the LLM hand-off brief for a layout's failures

Exit codes: 0 all checks passed, 1 failures present, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brief import build_brief, render_brief_text
from .engine import ENGINE_VERSION, validate
from .loader import LoadError, layout_to_dict, load_layout, load_parts
from .report import render_report
from .solver import DEFAULT_SEEDS, solve

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_BAD_INPUT = 2


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load(parts_path: str, layout_path: str):
    parts, parts_warnings = load_parts(parts_path)
    layout, layout_warnings = load_layout(layout_path)
    return parts, layout, parts_warnings + layout_warnings


def _emit(results, outdir: Path, parts_path: str, layout_path: str,
          stem: str = "validation") -> None:
    _write(
        outdir / f"{stem}_results.json",
        json.dumps(results.to_dict(), indent=2) + "\n",
    )
    _write(
        outdir / f"{stem}_report.md",
        render_report(results, parts_source=parts_path, layout_source=layout_path),
    )


def _summarize(results, label: str) -> None:
    counts = results.summary()
    verdict = "PASS" if results.passed else "FAIL"
    print(
        f"{label}: {verdict} - {counts['PASS']} passed, {counts['FAIL']} failed, "
        f"{counts['WARN']} warnings, {counts['SKIP']} skipped"
    )
    for c in sorted(results.failures, key=lambda x: (x.severity, x.id)):
        print(f"    [{c.severity}] {c.title}")
        print(f"        {c.message}")


def cmd_validate(args: argparse.Namespace) -> int:
    parts, layout, warnings = _load(args.parts, args.layout)
    results = validate(layout, parts, warnings, generated_at=args.now)
    _emit(results, Path(args.out), args.parts, args.layout)
    for w in warnings:
        print(f"  warning: {w}", file=sys.stderr)
    _summarize(results, layout.name)
    print(f"  -> {args.out}/validation_results.json")
    print(f"  -> {args.out}/validation_report.md")
    return EXIT_OK if results.passed else EXIT_FAILURES


def cmd_solve(args: argparse.Namespace) -> int:
    parts, layout, warnings = _load(args.parts, args.layout)

    before = validate(layout, parts, warnings, generated_at=args.now)
    _summarize(before, f"{layout.name} (input)")

    seeds = tuple(args.seeds) if args.seeds else DEFAULT_SEEDS
    solved, cost = solve(layout, parts, seeds=seeds, name=args.name)

    out_path = Path(args.out)
    _write(out_path, json.dumps(layout_to_dict(solved), indent=2) + "\n")

    # Re-validate through the ordinary path. If the solver's internal cost and
    # the real rule set ever disagree, this is where it surfaces.
    after = validate(solved, parts, warnings, generated_at=args.now)
    print()
    _summarize(after, f"{solved.name} (solved)")
    print(f"  residual solver cost: {cost:.4f}")
    print(f"  -> {out_path}")

    if args.report_dir:
        _emit(after, Path(args.report_dir), args.parts, str(out_path))
        print(f"  -> {args.report_dir}/validation_report.md")

    fixed = len(before.failures) - len(after.failures)
    if after.passed:
        print(f"\n  resolved all {len(before.failures)} failures.")
    else:
        print(
            f"\n  resolved {fixed} of {len(before.failures)} failures; "
            f"{len(after.failures)} remain and are reported above."
        )
    return EXIT_OK if after.passed else EXIT_FAILURES


def cmd_compare(args: argparse.Namespace) -> int:
    parts, parts_warnings = load_parts(args.parts)

    rows = []
    all_passed = True
    for layout_path in args.layouts:
        layout, layout_warnings = load_layout(layout_path)
        results = validate(
            layout, parts, parts_warnings + layout_warnings, generated_at=args.now
        )
        rows.append((layout.name, layout_path, results))
        all_passed = all_passed and results.passed
        if args.out:
            stem = Path(layout_path).stem
            _emit(results, Path(args.out), args.parts, layout_path, stem=stem)

    width = max(len(name) for name, _, _ in rows)
    print(f"{'Layout'.ljust(width)}  {'Verdict':>7}  {'Pass':>5}  {'Fail':>5}")
    print(f"{'-' * width}  {'-' * 7}  {'-' * 5}  {'-' * 5}")
    for name, _, results in rows:
        counts = results.summary()
        verdict = "PASS" if results.passed else "FAIL"
        print(
            f"{name.ljust(width)}  {verdict:>7}  "
            f"{counts['PASS']:>5}  {counts['FAIL']:>5}"
        )

    # Which checks changed verdict between the first and last layout.
    if len(rows) >= 2:
        first, last = rows[0][2], rows[-1][2]
        first_fails = {c.id for c in first.failures}
        last_fails = {c.id for c in last.failures}
        resolved = sorted(first_fails - last_fails)
        introduced = sorted(last_fails - first_fails)
        if resolved:
            print(f"\nResolved going from '{rows[0][0]}' to '{rows[-1][0]}':")
            for cid in resolved:
                print(f"  + {cid}")
        if introduced:
            print(f"\nIntroduced going from '{rows[0][0]}' to '{rows[-1][0]}':")
            for cid in introduced:
                print(f"  - {cid}")

    if args.out:
        print(f"\n  -> {args.out}/")
    return EXIT_OK if all_passed else EXIT_FAILURES


def cmd_explain(args: argparse.Namespace) -> int:
    parts, layout, warnings = _load(args.parts, args.layout)
    results = validate(layout, parts, warnings, generated_at=args.now)
    brief = build_brief(results, layout, parts, include_passes=args.include_passes)

    outdir = Path(args.out)
    _write(outdir / "explain_brief.json", json.dumps(brief, indent=2) + "\n")
    text = render_brief_text(brief)
    _write(outdir / "explain_brief.txt", text)

    if args.stdout:
        print(text)
    else:
        print(
            f"{layout.name}: {len(brief['findings'])} findings prepared for "
            f"explanation."
        )
        print(f"  -> {outdir}/explain_brief.json")
        print(f"  -> {outdir}/explain_brief.txt")
    return EXIT_OK if results.passed else EXIT_FAILURES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="constraint_engine",
        description="MissionPCB constraint engine: validate a layout against "
                    "mission constraints, or search for one that passes.",
    )
    parser.add_argument("--version", action="version", version=ENGINE_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--parts", required=True, help="parts library JSON")
        p.add_argument(
            "--now",
            default=None,
            help="timestamp to stamp on outputs; omit for reproducible files",
        )

    p_validate = sub.add_parser("validate", help="check one layout")
    common(p_validate)
    p_validate.add_argument("--layout", required=True)
    p_validate.add_argument("--out", default="out", help="output directory")
    p_validate.set_defaults(func=cmd_validate)

    p_solve = sub.add_parser("solve", help="search for a corrected layout")
    common(p_solve)
    p_solve.add_argument("--layout", required=True, help="starting layout")
    p_solve.add_argument("--out", required=True, help="path for the solved layout JSON")
    p_solve.add_argument("--name", default=None, help="name for the solved layout")
    p_solve.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help=f"restart seeds (default {list(DEFAULT_SEEDS)}); fixed for reproducibility",
    )
    p_solve.add_argument(
        "--report-dir", default=None, help="also write a report for the solved layout"
    )
    p_solve.set_defaults(func=cmd_solve)

    p_compare = sub.add_parser("compare", help="validate several layouts side by side")
    common(p_compare)
    p_compare.add_argument("--layouts", required=True, nargs="+")
    p_compare.add_argument("--out", default=None, help="optional output directory")
    p_compare.set_defaults(func=cmd_compare)

    p_explain = sub.add_parser(
        "explain", help="emit the LLM hand-off brief for a layout's failures"
    )
    common(p_explain)
    p_explain.add_argument("--layout", required=True)
    p_explain.add_argument("--out", default="out", help="output directory")
    p_explain.add_argument(
        "--include-passes",
        action="store_true",
        help="include passing checks, not just failures",
    )
    p_explain.add_argument(
        "--stdout", action="store_true", help="print the brief instead of a summary"
    )
    p_explain.set_defaults(func=cmd_explain)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
