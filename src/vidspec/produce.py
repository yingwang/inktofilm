"""End-to-end screenplay-to-short-film orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence

from vidspec.config import CaseSpec, SemanticAssertion, SemanticSpec
from vidspec.engine import evaluate_case
from vidspec.models import STATUS_ORDER, CaseReport, RunReport
from vidspec.production import ProductionError, ProductionPlan, ProductionPlanner, ShotSpec
from vidspec.providers import FalMiniMaxGenerator, ProviderError
from vidspec.report import write_html, write_json
from vidspec.semantic import SemanticEvaluator


class VideoGenerator(Protocol):
    def generate(
        self,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        destination: Path,
    ) -> Path: ...


class VideoEditor(Protocol):
    def concat(self, clips: Sequence[Path], destination: Path) -> Path: ...


@dataclass
class ProductionResult:
    plan: ProductionPlan
    output_dir: Path
    final_video: Optional[Path]
    report: Optional[RunReport]
    manifest: Path


class FFmpegEditor:
    """Normalize and concatenate generated shots into one portable MP4."""

    def __init__(self, runner: Any = subprocess.run):
        self.runner = runner

    def concat(self, clips: Sequence[Path], destination: Path) -> Path:
        if not clips:
            raise ProductionError("Cannot edit a film without generated shots")
        if shutil.which("ffmpeg") is None:
            raise ProductionError("ffmpeg is required to assemble the final film")
        destination.parent.mkdir(parents=True, exist_ok=True)
        root = destination.parent.resolve()
        lines = []
        for clip in clips:
            try:
                relative = clip.resolve().relative_to(root)
            except ValueError as exc:
                raise ProductionError("Generated shot is outside the production directory") from exc
            if "'" in str(relative) or "\n" in str(relative):
                raise ProductionError("Generated shot path contains unsupported characters")
            lines.append(f"file '{relative.as_posix()}'")
        concat_path = root / "concat.txt"
        concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_path.name,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-y",
            destination.name,
        ]
        try:
            completed = self.runner(command, capture_output=True, text=True, cwd=str(root))
        except OSError as exc:
            raise ProductionError(f"Could not run ffmpeg: {exc}") from exc
        if completed.returncode or not destination.is_file():
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise ProductionError(f"Could not assemble final film: {detail}")
        return destination


def _generation_prompt(plan: ProductionPlan, shot: ShotSpec, feedback: str = "") -> str:
    characters = "; ".join(
        f"{item.name}: {item.description}" for item in plan.characters
    ) or "No recurring named character"
    dialogue = f" Spoken dialogue, exact words: {shot.dialogue}" if shot.dialogue else ""
    correction = f" Correct these prior failures: {feedback}" if feedback else ""
    return (
        f"Create one continuous cinematic shot for a short film. Style: {plan.visual_style}. "
        f"Scene: {shot.scene}. Visible cast bible: {characters}. Shot direction: {shot.prompt}."
        f"{dialogue} Preserve identities, clothing, props, spatial continuity, natural anatomy, "
        f"coherent motion, and stable lighting. No subtitles, captions, logos, or watermarks."
        f"{correction}"
    )


def _case_spec(shot: ShotSpec, video: str, prompt: str) -> CaseSpec:
    assertions = [
        SemanticAssertion(
            assertion_id=f"visible-{index:02d}",
            description=description,
            min_score=0.72,
            severity="fail",
        )
        for index, description in enumerate(shot.assertions, start=1)
    ]
    return CaseSpec(
        case_id=shot.shot_id,
        video=video,
        prompt=prompt,
        expect={
            "duration_seconds": {
                "min": max(1.0, shot.duration_seconds - 2.0),
                "max": shot.duration_seconds + 3.0,
            },
            "resolution": {"min_width": 400, "min_height": 400},
            "fps": {"min": 20},
            "black_frames": {"max_total_ratio": 0.02},
            "freezes": {"max_total_ratio": 0.08},
        },
        semantic=SemanticSpec(assertions=assertions, sample_frames=6),
    )


def _feedback(report: CaseReport) -> str:
    failures = [
        f"{item.check}: {item.summary}"
        for item in report.findings
        if STATUS_ORDER[item.status] >= STATUS_ORDER["fail"]
    ]
    return "; ".join(failures[:6])


class ProductionOrchestrator:
    """Plan, generate, judge, retry, and edit a short film."""

    def __init__(
        self,
        planner: ProductionPlanner,
        generator: Optional[VideoGenerator] = None,
        evaluator: Optional[SemanticEvaluator] = None,
        editor: Optional[VideoEditor] = None,
    ):
        self.planner = planner
        self.generator = generator
        self.evaluator = evaluator
        self.editor = editor or FFmpegEditor()

    def produce(
        self,
        script: str,
        output_dir: Path,
        max_retries: int = 1,
        plan_only: bool = False,
    ) -> ProductionResult:
        if max_retries < 0 or max_retries > 5:
            raise ProductionError("max_retries must be between 0 and 5")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        plan = self.planner.plan(script)
        plan_path = output_dir / "plan.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        script_path = output_dir / "script.md"
        script_path.write_text(script.rstrip() + "\n", encoding="utf-8")
        manifest_path = output_dir / "manifest.json"
        manifest: Dict[str, Any] = {
            "schema_version": "1.0",
            "title": plan.title,
            "plan": plan_path.name,
            "script": script_path.name,
            "status": "planned" if plan_only else "running",
            "shots": [],
        }
        if plan_only:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return ProductionResult(plan, output_dir, None, None, manifest_path)
        if self.generator is None:
            raise ProviderError("A video generator is required unless --plan-only is used")
        if self.evaluator is None:
            raise ProviderError("A semantic evaluator is required unless --plan-only is used")

        cases: List[CaseReport] = []
        selected_clips: List[Path] = []
        for shot in plan.shots:
            attempts: List[Dict[str, Any]] = []
            feedback = ""
            selected_path: Optional[Path] = None
            selected_report: Optional[CaseReport] = None
            for attempt in range(1, max_retries + 2):
                prompt = _generation_prompt(plan, shot, feedback)
                clip_path = output_dir / "shots" / f"{shot.shot_id}-attempt-{attempt}.mp4"
                self.generator.generate(
                    prompt,
                    shot.duration_seconds,
                    plan.aspect_ratio,
                    clip_path,
                )
                relative = clip_path.relative_to(output_dir).as_posix()
                case = _case_spec(shot, relative, prompt)
                report = evaluate_case(
                    case,
                    output_dir,
                    semantic_evaluator=self.evaluator,
                    evidence_root=output_dir / "assets" / f"attempt-{attempt}",
                )
                attempts.append(
                    {
                        "attempt": attempt,
                        "video": relative,
                        "status": report.status,
                    }
                )
                selected_path = clip_path
                selected_report = report
                if STATUS_ORDER[report.status] < STATUS_ORDER["fail"]:
                    break
                feedback = _feedback(report)
            assert selected_path is not None and selected_report is not None
            selected_clips.append(selected_path)
            cases.append(selected_report)
            manifest["shots"].append(
                {
                    "id": shot.shot_id,
                    "selected_video": selected_path.relative_to(output_dir).as_posix(),
                    "status": selected_report.status,
                    "attempts": attempts,
                }
            )

        report = RunReport(
            suite_name=f"{plan.title} production",
            generated_at=datetime.now(timezone.utc).isoformat(),
            cases=cases,
        )
        write_json(report, output_dir / "report.json")
        write_html(report, output_dir / "index.html")
        final_video = self.editor.concat(selected_clips, output_dir / "final.mp4")
        manifest["status"] = report.status
        manifest["final_video"] = final_video.relative_to(output_dir).as_posix()
        manifest["report"] = "index.html"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return ProductionResult(plan, output_dir, final_video, report, manifest_path)


__all__ = [
    "FFmpegEditor",
    "FalMiniMaxGenerator",
    "ProductionOrchestrator",
    "ProductionResult",
]
