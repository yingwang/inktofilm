"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from vidspec import __version__
from vidspec.compare import ComparisonError, compare_report_files, output_paths, write_comparison
from vidspec.config import ConfigurationError, load_suite
from vidspec.engine import run_suite
from vidspec.media import MediaToolError, probe_video
from vidspec.models import STATUS_ORDER
from vidspec.report import write_html, write_json
from vidspec.semantic import (
    CommandSemanticEvaluator,
    JsonSemanticEvaluator,
    SemanticEvaluationError,
)

_STARTER = {
    "name": "my-video-model",
    "cases": [
        {
            "id": "camera-orbit",
            "video": "videos/camera-orbit.mp4",
            "prompt": "A camera slowly orbits a red ceramic teapot on a wooden table.",
            "expect": {
                "duration_seconds": {"min": 4, "max": 8},
                "resolution": {"min_width": 720, "min_height": 480},
                "fps": {"min": 20},
                "black_frames": {"max_total_ratio": 0.01},
                "freezes": {"max_total_ratio": 0.05},
            },
        }
    ],
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vidspec", description=__doc__)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="write a starter vidspec.json")
    init.add_argument("path", nargs="?", default="vidspec.json")

    probe = commands.add_parser("probe", help="print normalized video metadata")
    probe.add_argument("video")

    run = commands.add_parser("run", help="run a JSON test suite")
    run.add_argument("suite")
    run.add_argument("--output", "-o", default="reports/latest")
    semantic = run.add_mutually_exclusive_group()
    semantic.add_argument(
        "--semantic-results",
        help="replay semantic evidence from a reviewed JSON result file",
    )
    semantic.add_argument(
        "--semantic-command",
        help="opt in to an evaluator command that reads a JSON request from stdin",
    )
    run.add_argument(
        "--semantic-timeout",
        type=float,
        default=180.0,
        help="timeout in seconds for --semantic-command (default: 180)",
    )
    run.add_argument(
        "--fail-on",
        choices=("never", "warn", "fail", "error"),
        default="fail",
        help="minimum run status that returns exit code 1",
    )

    compare = commands.add_parser("compare", help="compare two report.json files")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--output", "-o", default="reports/comparison")
    return parser


def _run(args: argparse.Namespace) -> int:
    if args.command == "init":
        path = Path(args.path)
        if path.exists():
            print(f"Refusing to overwrite {path}", file=sys.stderr)
            return 2
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_STARTER, indent=2) + "\n", encoding="utf-8")
        print(f"Created {path}")
        return 0

    if args.command == "probe":
        probe = probe_video(Path(args.video).resolve())
        print(json.dumps(probe.to_dict(), indent=2))
        return 0

    if args.command == "run":
        suite = load_suite(Path(args.suite))
        output = Path(args.output)
        semantic_evaluator = None
        if args.semantic_results:
            semantic_evaluator = JsonSemanticEvaluator(Path(args.semantic_results))
        elif args.semantic_command:
            semantic_evaluator = CommandSemanticEvaluator.from_string(
                args.semantic_command,
                timeout_seconds=args.semantic_timeout,
            )
        report = run_suite(
            suite,
            semantic_evaluator=semantic_evaluator,
            evidence_root=output / "assets",
        )
        write_json(report, output / "report.json")
        write_html(report, output / "index.html")
        print(f"{suite.name}: {report.status.upper()} ({len(report.cases)} cases)")
        print("Report: {0}".format((output / "index.html").resolve()))
        if args.fail_on == "never":
            return 0
        return int(STATUS_ORDER[report.status] >= STATUS_ORDER[args.fail_on])

    if args.command == "compare":
        result = compare_report_files(Path(args.baseline), Path(args.candidate))
        json_path, html_path = output_paths(Path(args.output))
        write_comparison(result, json_path, html_path)
        print("Regressions: {0}".format(result["regressions"]))
        print(f"Report: {html_path.resolve()}")
        return int(result["regressions"] > 0)
    return 2


def main(argv: Optional[List[str]] = None) -> None:
    try:
        code = _run(_parser().parse_args(argv))
    except (
        ConfigurationError,
        ComparisonError,
        MediaToolError,
        SemanticEvaluationError,
        OSError,
        ValueError,
    ) as exc:
        print(f"vidspec: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
