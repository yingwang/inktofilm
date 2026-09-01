"""Command-line interface."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

from vidspec import __version__
from vidspec.compare import ComparisonError, compare_report_files, output_paths, write_comparison
from vidspec.config import ConfigurationError, load_suite
from vidspec.engine import run_suite
from vidspec.media import MediaToolError, probe_video
from vidspec.models import STATUS_ORDER
from vidspec.produce import ProductionOrchestrator
from vidspec.production import (
    CodexProductionPlanner,
    CommandProductionPlanner,
    ProductionError,
    safe_id,
)
from vidspec.providers import (
    CodexCLIProvider,
    CommandVideoGenerator,
    FalFaceSwapper,
    FalImageGenerator,
    FalMiniMaxGenerator,
    ProviderError,
)
from vidspec.report import write_html, write_json
from vidspec.semantic import (
    CodexSemanticEvaluator,
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
    program = Path(sys.argv[0]).name.lower()
    if program not in {"inktofilm", "vidspec"}:
        program = "inktofilm"
    parser = argparse.ArgumentParser(prog=program, description=__doc__)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    commands = parser.add_subparsers(dest="command", required=True)

    default_suite = "vidspec.json" if program == "vidspec" else "inktofilm.json"
    init = commands.add_parser("init", help=f"write a starter {default_suite}")
    init.add_argument("path", nargs="?", default=default_suite)

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
    semantic.add_argument(
        "--semantic-codex",
        action="store_true",
        help="judge sampled frames with the locally authenticated Codex CLI",
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

    produce = commands.add_parser(
        "produce",
        help="turn a screenplay into a planned, generated, judged, and edited short film",
    )
    produce.add_argument("script", help="Markdown or text screenplay")
    produce.add_argument("--output", "-o", default="productions/latest")
    produce.add_argument(
        "--plan-only",
        action="store_true",
        help="create script.md, plan.json, and manifest.json without spending video credits",
    )
    produce.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="regenerate a shot after failed QA (default: 1)",
    )
    produce.add_argument(
        "--codex-model",
        help="optional model override for the authenticated Codex CLI",
    )
    produce.add_argument(
        "--codex-timeout",
        type=float,
        default=600.0,
        help="timeout in seconds for each Codex planning or judging request",
    )
    produce.add_argument(
        "--planner-command",
        help="BYOM planner command: read JSON from stdin and return a production plan",
    )
    produce.add_argument(
        "--judge-command",
        help="BYOM semantic judge command using InkToFilm's JSON evaluator protocol",
    )
    produce.add_argument(
        "--video-command",
        help="BYOM video command: read JSON from stdin and write the requested destination",
    )
    produce.add_argument(
        "--video-timeout",
        type=float,
        default=1800.0,
        help="timeout in seconds for each --video-command request",
    )
    produce.add_argument(
        "--video-model",
        default="minimax/h3-max/text-to-video",
        help="fal model endpoint (default: MiniMax H3 Max text-to-video)",
    )
    produce.add_argument(
        "--resolution",
        choices=("480P", "768P"),
        default="768P",
        help="native MiniMax generation resolution",
    )
    produce.add_argument(
        "--no-stills",
        action="store_true",
        help="skip still generation and shoot every shot from text alone",
    )
    produce.add_argument(
        "--image-model",
        default="fal-ai/nano-banana",
        help="fal model endpoint for stills generated from a prompt alone",
    )
    produce.add_argument(
        "--image-edit-model",
        default="fal-ai/nano-banana/edit",
        help="fal model endpoint for stills edited from reference stills",
    )
    produce.add_argument(
        "--face-swap-model",
        default="fal-ai/face-swap",
        help="fal model endpoint used by --face",
    )
    produce.add_argument(
        "--face",
        action="append",
        metavar="CHARACTER_ID=PATH",
        help=(
            "put a real photographed face on one character's close-up stills. "
            "The photo is uploaded to fal and never written into a model prompt. "
            "Repeat for more characters."
        ),
    )

    commands.add_parser("doctor", help="check local tools and default provider credentials")
    return parser


def _face_map(values: Optional[List[str]]) -> Dict[str, Path]:
    faces: Dict[str, Path] = {}
    for value in values or []:
        character_id, separator, raw_path = value.partition("=")
        if not separator or not character_id.strip() or not raw_path.strip():
            raise ProductionError(f"--face expects CHARACTER_ID=PATH, got '{value}'")
        path = Path(raw_path.strip()).expanduser().resolve()
        if not path.is_file():
            raise ProductionError(f"--face photo does not exist: {path}")
        faces[safe_id(character_id.strip())] = path
    return faces


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
        elif args.semantic_codex:
            semantic_evaluator = CodexSemanticEvaluator(
                CodexCLIProvider(timeout_seconds=args.semantic_timeout)
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

    if args.command == "doctor":
        checks = {
            "codex CLI": shutil.which("codex") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "ffprobe": shutil.which("ffprobe") is not None,
            "fal-client": importlib.util.find_spec("fal_client") is not None,
            "FAL_KEY": bool(os.environ.get("FAL_KEY")),
        }
        for name, ready in checks.items():
            print(f"{'ready' if ready else 'missing':7} {name}")
        return int(not all(checks.values()))

    if args.command == "produce":
        script_path = Path(args.script).resolve()
        script = script_path.read_text(encoding="utf-8")
        codex = CodexCLIProvider(
            model=args.codex_model,
            timeout_seconds=args.codex_timeout,
        )
        planner = (
            CommandProductionPlanner.from_string(
                args.planner_command,
                timeout_seconds=args.codex_timeout,
            )
            if args.planner_command
            else CodexProductionPlanner(codex)
        )
        faces = _face_map(args.face)
        generator = None
        evaluator = None
        image_generator = None
        face_swapper = None
        if not args.plan_only:
            generator = (
                CommandVideoGenerator.from_string(
                    args.video_command,
                    timeout_seconds=args.video_timeout,
                )
                if args.video_command
                else FalMiniMaxGenerator(
                    model=args.video_model,
                    resolution=args.resolution,
                )
            )
            evaluator = (
                CommandSemanticEvaluator.from_string(
                    args.judge_command,
                    timeout_seconds=args.codex_timeout,
                )
                if args.judge_command
                else CodexSemanticEvaluator(codex)
            )
            if not args.no_stills:
                image_generator = FalImageGenerator(
                    model=args.image_model,
                    edit_model=args.image_edit_model,
                )
                face_swapper = FalFaceSwapper(model=args.face_swap_model)
        if faces and args.no_stills:
            raise ProductionError("--face needs stills, so it cannot be used with --no-stills")
        result = ProductionOrchestrator(
            planner=planner,
            generator=generator,
            evaluator=evaluator,
            image_generator=image_generator,
            face_swapper=face_swapper,
            faces=faces,
        ).produce(
            script,
            Path(args.output),
            max_retries=args.max_retries,
            plan_only=args.plan_only,
        )
        print(f"{result.plan.title}: {'PLANNED' if args.plan_only else result.report.status.upper()}")
        print(f"Manifest: {result.manifest}")
        if result.final_video is not None:
            print(f"Film: {result.final_video}")
            print(f"Report: {result.output_dir / 'index.html'}")
        return 0 if result.report is None else int(result.report.status in {"fail", "error"})
    return 2


def main(argv: Optional[List[str]] = None) -> None:
    try:
        code = _run(_parser().parse_args(argv))
    except (
        ConfigurationError,
        ComparisonError,
        MediaToolError,
        ProductionError,
        ProviderError,
        SemanticEvaluationError,
        OSError,
        ValueError,
    ) as exc:
        program = Path(sys.argv[0]).name.lower()
        if program not in {"inktofilm", "vidspec"}:
            program = "inktofilm"
        print(f"{program}: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
