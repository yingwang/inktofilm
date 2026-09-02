"""End-to-end screenplay-to-short-film orchestration."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Sequence

from vidspec.config import CaseSpec, SemanticAssertion, SemanticSpec
from vidspec.engine import evaluate_case
from vidspec.media import MediaToolError, extract_frame, probe_video
from vidspec.models import STATUS_ORDER, CaseReport, RunReport
from vidspec.production import ProductionError, ProductionPlan, ProductionPlanner, ShotSpec
from vidspec.providers import (
    FalFaceSwapper,
    FalImageGenerator,
    FalMiniMaxGenerator,
    ProviderError,
)
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


class ImageGenerator(Protocol):
    def generate(
        self,
        prompt: str,
        destination: Path,
        aspect_ratio: str = ...,
        references: Sequence[Path] = ...,
    ) -> Path: ...


class FaceSwapper(Protocol):
    def swap(self, face_image: Path, base_image: Path, destination: Path) -> Path: ...


# (video, seconds before its end, destination) -> the written frame
FrameGrabber = Callable[[Path, float, Path], Path]


def grab_frame_before_end(video: Path, seconds_from_end: float, destination: Path) -> Path:
    """Write the frame `seconds_from_end` before the clip ends, at the clip's own size.

    The literal last frame of a generated clip is often mid-blur or already fading, so callers
    ask for a frame a fraction of a second earlier; the offset is clamped inside the clip.
    """
    try:
        probe = probe_video(video)
        fps = probe.fps if probe.fps > 0 else 24.0
        latest = max(probe.duration_seconds - 1.0 / fps, 0.0)
        timestamp = min(max(probe.duration_seconds - seconds_from_end, 0.0), latest)
        return extract_frame(video, timestamp, destination)
    except MediaToolError as exc:
        raise ProductionError(f"Could not take a frame from {video.name}: {exc}") from exc


class VideoEditor(Protocol):
    def concat(self, clips: Sequence[Path], destination: Path) -> Path: ...


@dataclass
class ProductionResult:
    plan: ProductionPlan
    output_dir: Path
    final_video: Optional[Path]
    report: Optional[RunReport]
    manifest: Path
    stills: Dict[str, Path] = field(default_factory=dict)


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
    # Only the characters the shot lists go into its prompt. Describing the whole cast on a
    # single-character shot invites the model to seat the others in the background.
    cast = [
        item for item in plan.characters if not shot.characters or item.character_id in shot.characters
    ]
    characters = "; ".join(
        f"{item.name}: {item.description}" for item in cast
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


def _suite_case(case: CaseSpec) -> Dict[str, Any]:
    """Serialize a case the way `inktofilm run` reads it, so verdicts can be replayed on it."""
    semantic = case.semantic
    assert semantic is not None
    return {
        "id": case.case_id,
        "video": case.video,
        "prompt": case.prompt,
        "expect": case.expect,
        "semantic": {
            "sample_frames": semantic.sample_frames,
            "assertions": [
                {
                    "id": item.assertion_id,
                    "description": item.description,
                    "min_score": item.min_score,
                    "severity": item.severity,
                }
                for item in semantic.assertions
            ],
        },
    }


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
        planner: Optional[ProductionPlanner],
        generator: Optional[VideoGenerator] = None,
        evaluator: Optional[SemanticEvaluator] = None,
        editor: Optional[VideoEditor] = None,
        image_generator: Optional[ImageGenerator] = None,
        face_swapper: Optional[FaceSwapper] = None,
        faces: Optional[Mapping[str, Path]] = None,
        frame_grabber: Optional[FrameGrabber] = None,
    ):
        self.planner = planner
        self.generator = generator
        self.evaluator = evaluator
        self.editor = editor or FFmpegEditor()
        self.image_generator = image_generator
        self.face_swapper = face_swapper
        self.faces = dict(faces or {})
        self.frame_grabber = frame_grabber or grab_frame_before_end

    def _swap_faces(self, shot: ShotSpec, base: Path) -> Path:
        """Put every supplied face the shot asks for onto `base`, reusing a swap already on disk."""
        faces = [self.faces[name] for name in shot.face_references if name in self.faces]
        if not faces or self.face_swapper is None:
            return base
        swapped = base.with_name(f"{base.stem}-face{base.suffix}")
        if swapped.is_file():
            return swapped
        if len(faces) == 1:
            self.face_swapper.swap(faces[0], base, swapped)
        elif hasattr(self.face_swapper, "swap_many"):
            self.face_swapper.swap_many(faces, base, swapped)
        else:
            # A single-face model cannot be told which person to replace, so swapping twice is
            # the only option left; the second pass may land on the wrong face.
            current = base
            for index, face in enumerate(faces):
                step = swapped if index == len(faces) - 1 else base.with_name(
                    f"{base.stem}-face{index}{base.suffix}"
                )
                self.face_swapper.swap(face, current, step)
                current = step
        return swapped

    def _continuation_still(self, shot: ShotSpec, previous_clip: Path, output_dir: Path) -> Path:
        """Take this shot's opening frame from the previous shot's selected clip.

        The frame is named after the clip it came from, so choosing a different take of the
        previous shot produces a new frame instead of silently reusing a stale one, and the
        shot's photographed faces go onto the frame before any video credit is spent on it.
        """
        assert shot.continue_from_previous is not None
        frame = output_dir / "stills" / f"{shot.shot_id}-from-{previous_clip.stem}.jpg"
        if not frame.is_file():
            self.frame_grabber(previous_clip, shot.continue_from_previous, frame)
        return self._swap_faces(shot, frame)

    def _reference_stills(self, plan: ProductionPlan, output_dir: Path) -> Dict[str, Path]:
        """Render one clean portrait per character, so every later still edits from one face.

        A portrait that already exists on disk is kept, so a reviewer can delete the ones that
        failed and re-run without paying for the ones that passed.
        """
        if self.image_generator is None:
            return {}
        references: Dict[str, Path] = {}
        for character in plan.characters:
            if not character.reference_prompt:
                continue
            portrait = output_dir / "references" / f"{character.character_id}.jpg"
            if not portrait.is_file():
                self.image_generator.generate(character.reference_prompt, portrait, "1:1")
            face = self.faces.get(character.character_id)
            if face is not None and self.face_swapper is not None:
                swapped = portrait.with_name(f"{character.character_id}-face.jpg")
                if not swapped.is_file():
                    self.face_swapper.swap(face, portrait, swapped)
                portrait = swapped
            references[character.character_id] = portrait
        return references

    def _shot_stills(
        self,
        plan: ProductionPlan,
        output_dir: Path,
        references: Mapping[str, Path],
    ) -> Dict[str, Path]:
        """Lock each shot's opening frame before spending a video credit on it.

        Like portraits, a still that already exists is kept rather than regenerated.
        """
        if self.image_generator is None:
            return {}
        stills: Dict[str, Path] = {}
        for shot in plan.shots:
            if not shot.still_prompt:
                continue
            sources = [references[name] for name in shot.characters if name in references]
            still = output_dir / "stills" / f"{shot.shot_id}.jpg"
            if not still.is_file():
                self.image_generator.generate(
                    shot.still_prompt,
                    still,
                    plan.aspect_ratio,
                    sources,
                )
            stills[shot.shot_id] = self._swap_faces(shot, still)
        return stills

    @staticmethod
    def _existing_attempts(output_dir: Path, shot_id: str) -> int:
        """Count the attempts already on disk for a shot, so a re-run can continue from them."""
        count = 0
        while (output_dir / "shots" / f"{shot_id}-attempt-{count + 1}.mp4").is_file():
            count += 1
        return count

    def _shoot(
        self,
        plan: ProductionPlan,
        position: int,
        prompt: str,
        destination: Path,
        stills: Mapping[str, Path],
    ) -> Path:
        """Shoot from the shot's still when there is one, and land on the next still when chained."""
        shot = plan.shots[position]
        start = stills.get(shot.shot_id)
        if start is None or not hasattr(self.generator, "generate_from_image"):
            return self.generator.generate(
                prompt,
                shot.duration_seconds,
                plan.aspect_ratio,
                destination,
            )
        end: Optional[Path] = None
        if shot.chain_to_next and position + 1 < len(plan.shots):
            end = stills.get(plan.shots[position + 1].shot_id)
        return self.generator.generate_from_image(
            prompt,
            shot.duration_seconds,
            start,
            destination,
            end_image=end,
        )

    def produce(
        self,
        script: str,
        output_dir: Path,
        max_retries: int = 1,
        plan_only: bool = False,
        plan: Optional[ProductionPlan] = None,
        stills_only: bool = False,
        reshoot: Sequence[str] = (),
        unjudged: bool = False,
        select: Optional[Mapping[str, int]] = None,
    ) -> ProductionResult:
        """Run the production, or one stage of it, inside `output_dir`.

        The bundle is resumable. Portraits, stills, and shot attempts already on disk are
        reused, so the same command can be run again after a reviewer has deleted a bad still
        or edited a prompt, and only the missing work is paid for. `plan` skips the planner
        entirely, which is how an agent that wrote the plan itself hands it over. `stills_only`
        stops once every portrait and still exists, before any video credit is spent. `reshoot`
        names shots that must get a fresh attempt even though one exists. `unjudged` allows a
        run without a semantic evaluator: media checks still run, the newest attempt of each shot
        is selected, and judging is left to whoever reviews the sampled frames afterwards. `select`
        maps a shot id to the attempt number a reviewer has chosen; that attempt is evaluated and
        used as the shot's clip, and nothing is generated for it.
        """
        if max_retries < 0 or max_retries > 5:
            raise ProductionError("max_retries must be between 0 and 5")
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if plan is None:
            if self.planner is None:
                raise ProductionError("A planner or an existing plan is required")
            plan = self.planner.plan(script)
        select = dict(select or {})
        shot_ids = {shot.shot_id for shot in plan.shots}
        unknown_shots = sorted((set(reshoot) | set(select)) - shot_ids)
        if unknown_shots:
            raise ProductionError(
                f"No shot in this plan is named {', '.join(unknown_shots)}"
            )
        both = sorted(set(reshoot) & set(select))
        if both:
            raise ProductionError(
                f"Cannot both reshoot and select an attempt for {', '.join(both)}"
            )
        for shot_id, attempt in select.items():
            chosen = output_dir / "shots" / f"{shot_id}-attempt-{attempt}.mp4"
            if not chosen.is_file():
                raise ProductionError(f"Selected attempt does not exist: {chosen.name}")
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

        def write_manifest() -> None:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        if plan_only:
            write_manifest()
            return ProductionResult(plan, output_dir, None, None, manifest_path)
        unknown_faces = sorted(
            set(self.faces) - {character.character_id for character in plan.characters}
        )
        if unknown_faces:
            raise ProductionError(
                f"No character in this plan is named {', '.join(unknown_faces)}"
            )
        if stills_only:
            if self.image_generator is None:
                raise ProviderError("Stills need an image generator; --no-stills makes none")
        else:
            if self.generator is None:
                raise ProviderError("A video generator is required unless --plan-only is used")
            if self.evaluator is None and not unjudged:
                raise ProviderError(
                    "A semantic evaluator is required unless --plan-only, --stills-only, "
                    "or --no-judge is used"
                )

        references = self._reference_stills(plan, output_dir)
        stills = self._shot_stills(plan, output_dir, references)
        if references:
            manifest["references"] = {
                name: path.relative_to(output_dir).as_posix()
                for name, path in references.items()
            }
        if stills:
            manifest["stills"] = {
                name: path.relative_to(output_dir).as_posix() for name, path in stills.items()
            }
        if stills_only:
            manifest["status"] = "stills"
            write_manifest()
            return ProductionResult(plan, output_dir, None, None, manifest_path, stills)

        cases: List[CaseReport] = []
        selected_clips: List[Path] = []
        suite_cases: List[Dict[str, Any]] = []
        for position, shot in enumerate(plan.shots):
            attempts: List[Dict[str, Any]] = []
            feedback = ""
            selected_path: Optional[Path] = None
            selected_report: Optional[CaseReport] = None
            selected_case: Optional[CaseSpec] = None
            # A reshoot continues numbering after the attempts on disk, so nothing is lost and
            # the fresh take is the one the loop evaluates. A selected attempt is the only one
            # considered. With a judge, existing attempts are evaluated in order and only a
            # missing attempt is generated. Without one there is nothing to rank them by, so the
            # newest take stands: a reshoot from an earlier run must not be undone by a re-run.
            existing = self._existing_attempts(output_dir, shot.shot_id)
            if shot.shot_id in select:
                candidates: Sequence[int] = (select[shot.shot_id],)
            elif shot.shot_id in reshoot:
                candidates = range(existing + 1, existing + max_retries + 2)
            elif self.evaluator is None:
                candidates = (max(existing, 1),)
            else:
                candidates = range(1, max_retries + 2)
            if shot.continue_from_previous is not None and any(
                not (output_dir / "shots" / f"{shot.shot_id}-attempt-{n}.mp4").is_file()
                for n in candidates
            ):
                # Only a shot about to be generated needs its opening frame, so a selected or
                # already finished take costs no frame grab and no face swap.
                stills[shot.shot_id] = self._continuation_still(
                    shot, selected_clips[-1], output_dir
                )
            for attempt in candidates:
                prompt = _generation_prompt(plan, shot, feedback)
                clip_path = output_dir / "shots" / f"{shot.shot_id}-attempt-{attempt}.mp4"
                generated = not clip_path.is_file()
                if generated:
                    self._shoot(plan, position, prompt, clip_path, stills)
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
                        "generated": generated,
                    }
                )
                selected_path = clip_path
                selected_report = report
                selected_case = case
                if STATUS_ORDER[report.status] < STATUS_ORDER["fail"]:
                    break
                feedback = _feedback(report)
            assert selected_path is not None and selected_report is not None
            assert selected_case is not None
            selected_clips.append(selected_path)
            cases.append(selected_report)
            suite_cases.append(_suite_case(selected_case))
            entry: Dict[str, Any] = {
                "id": shot.shot_id,
                "selected_video": selected_path.relative_to(output_dir).as_posix(),
                "status": selected_report.status,
                "attempts": attempts,
            }
            still = stills.get(shot.shot_id)
            if still is not None:
                entry["still"] = still.relative_to(output_dir).as_posix()
                entry["chained_to_next"] = shot.chain_to_next
            if shot.continue_from_previous is not None:
                entry["continued_from"] = selected_clips[-2].relative_to(output_dir).as_posix()
                entry["continue_from_previous"] = shot.continue_from_previous
            manifest["shots"].append(entry)

        report = RunReport(
            suite_name=f"{plan.title} production",
            generated_at=datetime.now(timezone.utc).isoformat(),
            cases=cases,
        )
        if stills:
            manifest["stills"] = {
                name: path.relative_to(output_dir).as_posix() for name, path in stills.items()
            }
        write_json(report, output_dir / "report.json")
        write_html(report, output_dir / "index.html")
        # The suite of selected clips lets a reviewer replay their own verdicts later with
        # `inktofilm run suite.json --semantic-results reviewed.json`.
        suite_path = output_dir / "suite.json"
        suite_path.write_text(
            json.dumps(
                {"name": f"{plan.title} production", "cases": suite_cases},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        final_video = self.editor.concat(selected_clips, output_dir / "final.mp4")
        manifest["status"] = report.status
        manifest["judged"] = self.evaluator is not None
        manifest["final_video"] = final_video.relative_to(output_dir).as_posix()
        manifest["report"] = "index.html"
        manifest["suite"] = suite_path.name
        write_manifest()
        return ProductionResult(plan, output_dir, final_video, report, manifest_path, stills)


__all__ = [
    "FFmpegEditor",
    "FalFaceSwapper",
    "FalImageGenerator",
    "FalMiniMaxGenerator",
    "ProductionOrchestrator",
    "ProductionResult",
]
