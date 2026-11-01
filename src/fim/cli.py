"""Command-line interface for the file integrity monitor."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from fim.core import SUPPORTED_ALGOS, Baseline, compare


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fim",
        description="Baseline a directory tree and detect later changes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--algo", choices=SUPPORTED_ALGOS, default="sha256", help="hash algorithm")
    common.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip paths matching this glob (repeatable), e.g. '*.log'",
    )

    p_base = sub.add_parser("baseline", parents=[common], help="record a baseline")
    p_base.add_argument("path", help="directory to snapshot")
    p_base.add_argument("-o", "--output", required=True, help="baseline file to write")

    p_verify = sub.add_parser("verify", parents=[common], help="check a tree against a baseline")
    p_verify.add_argument("path", help="directory to check")
    p_verify.add_argument("-b", "--baseline", required=True, help="baseline file to read")

    return parser


def _run_baseline(args: argparse.Namespace, out) -> int:
    baseline = Baseline.create(args.path, algo=args.algo, excludes=args.exclude)
    baseline.save(args.output)
    print(f"Wrote baseline of {len(baseline.files)} file(s) to {args.output}", file=out)
    return 0


def _run_verify(args: argparse.Namespace, out) -> int:
    baseline = Baseline.load(args.baseline)
    current = Baseline.create(args.path, algo=baseline.algo, excludes=args.exclude).files
    report = compare(baseline.files, current)

    if report.clean:
        print(f"OK: {len(current)} file(s) match the baseline.", file=out)
        return 0

    for path in report.added:
        print(f"  + added     {path}", file=out)
    for path in report.removed:
        print(f"  - removed   {path}", file=out)
    for path in report.modified:
        print(f"  ~ modified  {path}", file=out)
    print(
        f"CHANGED: {report.total_changes} change(s) "
        f"({len(report.added)} added, {len(report.removed)} removed, "
        f"{len(report.modified)} modified).",
        file=out,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "baseline":
            return _run_baseline(args, sys.stdout)
        if args.command == "verify":
            return _run_verify(args, sys.stdout)
    except (OSError, ValueError) as exc:
        print(f"fim: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")  # pragma: no cover
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
