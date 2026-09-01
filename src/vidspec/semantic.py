"""Opt-in, provider-neutral semantic evaluation with frame evidence."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Protocol, Sequence

from vidspec.config import CaseSpec
from vidspec.models import Evidence, Finding, VideoProbe
from vidspec.providers import CodexCLIProvider, ProviderError


class SemanticEvaluationError(RuntimeError):
    pass


class SemanticEvaluator(Protocol):
    def evaluate(
        self,
        spec: CaseSpec,
        video_path: Path,
        probe: VideoProbe,
        evidence_root: Path,
    ) -> List[Finding]: ...


SEMANTIC_RESULT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "evaluator": {"type": "string"},
        "provenance": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "model": {"type": "string"},
                "revision": {"type": "string"},
                "judge_prompt_hash": {"type": "string"},
                "sampling_policy": {"type": "string"},
            },
            "required": ["model", "revision", "judge_prompt_hash", "sampling_policy"],
        },
        "assertions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                    "summary": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "frame_index": {"type": "integer", "minimum": 1},
                                "description": {"type": "string"},
                            },
                            "required": ["frame_index", "description"],
                        },
                    },
                },
                "required": ["id", "score", "summary", "rationale", "evidence"],
            },
        },
    },
    "required": ["evaluator", "provenance", "assertions"],
}


@dataclass
class SampledFrame:
    index: int
    timestamp_seconds: float
    path: Path
    report_path: str


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return cleaned or "case"


def sample_frames(
    video_path: Path,
    duration_seconds: float,
    count: int,
    evidence_root: Path,
    case_id: str,
) -> List[SampledFrame]:
    case_dir = evidence_root / _safe_id(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    frames: List[SampledFrame] = []
    for offset in range(count):
        timestamp = duration_seconds * (offset + 0.5) / count
        name = f"frame-{offset + 1:02d}.jpg"
        path = case_dir / name
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale='min(768,iw)':-2",
            "-q:v",
            "2",
            "-y",
            str(path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SemanticEvaluationError(f"Could not sample semantic evidence: {exc}") from exc
        if completed.returncode or not path.is_file():
            message = completed.stderr.strip() or "FFmpeg did not produce a frame"
            raise SemanticEvaluationError(f"Could not sample semantic evidence: {message}")
        frames.append(
            SampledFrame(
                index=offset + 1,
                timestamp_seconds=timestamp,
                path=path,
                report_path=f"assets/{_safe_id(case_id)}/{name}",
            )
        )
    return frames


def _request(spec: CaseSpec, probe: VideoProbe, frames: Sequence[SampledFrame]) -> Dict[str, Any]:
    assert spec.semantic is not None
    return {
        "schema_version": "1.0",
        "case": {
            "id": spec.case_id,
            "prompt": spec.prompt,
            "video": {
                "duration_seconds": probe.duration_seconds,
                "width": probe.width,
                "height": probe.height,
                "fps": probe.fps,
            },
        },
        "instructions": (
            "Judge only visible evidence. Return one result per assertion. Scores are 0..1. "
            "Cite frame_index values from the supplied samples and disclose uncertainty."
        ),
        "assertions": [
            {
                "id": item.assertion_id,
                "description": item.description,
                "min_score": item.min_score,
            }
            for item in spec.semantic.assertions
        ],
        "frames": [
            {
                "frame_index": frame.index,
                "timestamp_seconds": round(frame.timestamp_seconds, 4),
                "path": str(frame.path.resolve()),
            }
            for frame in frames
        ],
        "response_schema": {
            "evaluator": "model or reviewer name and revision",
            "provenance": {
                "model": "provider model id",
                "revision": "immutable model or evaluator revision",
                "judge_prompt_hash": "stable hash when a learned judge is used",
                "sampling_policy": "optional evaluator-side sampling details",
            },
            "assertions": [
                {
                    "id": "assertion id",
                    "score": "number from 0 to 1",
                    "summary": "short verdict",
                    "rationale": "visible evidence and uncertainty",
                    "evidence": [
                        {"frame_index": "1-based sampled frame index", "description": "what it shows"}
                    ],
                }
            ],
        },
    }


def _parse_result(
    spec: CaseSpec,
    raw: Mapping[str, Any],
    frames: Sequence[SampledFrame],
) -> List[Finding]:
    assert spec.semantic is not None
    evaluator = str(raw.get("evaluator", "unspecified evaluator"))
    raw_provenance = raw.get("provenance", {})
    provenance = dict(raw_provenance) if isinstance(raw_provenance, dict) else {}
    provenance["evaluator"] = evaluator
    provenance["vidspec_sampling"] = f"{spec.semantic.sample_frames} evenly spaced center frames"
    raw_assertions = raw.get("assertions")
    if not isinstance(raw_assertions, list):
        raise SemanticEvaluationError("Semantic result needs an assertions array")
    by_id: Dict[str, Mapping[str, Any]] = {}
    for item in raw_assertions:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise SemanticEvaluationError("Every semantic result needs a string id")
        if item["id"] in by_id:
            raise SemanticEvaluationError(f"Duplicate semantic result id: {item['id']}")
        by_id[item["id"]] = item

    frame_by_index = {frame.index: frame for frame in frames}
    findings: List[Finding] = []
    for assertion in spec.semantic.assertions:
        result = by_id.get(assertion.assertion_id)
        if result is None:
            findings.append(
                Finding(
                    check=f"semantic:{assertion.assertion_id}",
                    status="error",
                    summary="Evaluator omitted this semantic assertion",
                    expected={"min_score": assertion.min_score},
                    details=evaluator,
                )
            )
            continue
        try:
            score = float(result.get("score"))
        except (TypeError, ValueError) as exc:
            raise SemanticEvaluationError(
                f"Semantic result '{assertion.assertion_id}' has an invalid score"
            ) from exc
        if not 0.0 <= score <= 1.0:
            raise SemanticEvaluationError(
                f"Semantic result '{assertion.assertion_id}' score must be 0..1"
            )
        passed = score >= assertion.min_score
        evidence: List[Evidence] = []
        raw_evidence = result.get("evidence", [])
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                if not isinstance(item, dict):
                    continue
                try:
                    frame_index = int(item.get("frame_index"))
                except (TypeError, ValueError):
                    continue
                frame = frame_by_index.get(frame_index)
                if frame is None:
                    continue
                evidence.append(
                    Evidence(
                        timestamp_seconds=frame.timestamp_seconds,
                        description=str(item.get("description", "")),
                        frame_index=frame.index,
                        image=frame.report_path,
                    )
                )
        summary = str(result.get("summary", "Semantic assertion evaluated"))
        rationale = str(result.get("rationale", ""))
        findings.append(
            Finding(
                check=f"semantic:{assertion.assertion_id}",
                status="pass" if passed else assertion.severity,
                summary=summary,
                observed={"score": round(score, 4)},
                expected={"min_score": assertion.min_score},
                evidence=evidence,
                details=f"{evaluator} · {rationale}".strip(" ·"),
                provenance=provenance,
            )
        )
    return findings


class JsonSemanticEvaluator:
    """Replay auditable semantic results produced by a model or human reviewer."""

    def __init__(self, path: Path):
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SemanticEvaluationError(f"Could not read semantic results: {exc}") from exc
        if not isinstance(self.data, dict) or not isinstance(self.data.get("cases"), dict):
            raise SemanticEvaluationError("Semantic results need a cases object")

    def evaluate(
        self,
        spec: CaseSpec,
        video_path: Path,
        probe: VideoProbe,
        evidence_root: Path,
    ) -> List[Finding]:
        assert spec.semantic is not None
        frames = sample_frames(
            video_path,
            probe.duration_seconds,
            spec.semantic.sample_frames,
            evidence_root,
            spec.case_id,
        )
        raw = self.data["cases"].get(spec.case_id)
        if not isinstance(raw, dict):
            raise SemanticEvaluationError(f"No semantic result for case '{spec.case_id}'")
        return _parse_result(spec, raw, frames)


class CodexSemanticEvaluator:
    """Judge sampled frames with an authenticated Codex CLI session."""

    def __init__(self, provider: CodexCLIProvider):
        self.provider = provider

    def evaluate(
        self,
        spec: CaseSpec,
        video_path: Path,
        probe: VideoProbe,
        evidence_root: Path,
    ) -> List[Finding]:
        assert spec.semantic is not None
        frames = sample_frames(
            video_path,
            probe.duration_seconds,
            spec.semantic.sample_frames,
            evidence_root,
            spec.case_id,
        )
        request = _request(spec, probe, frames)
        prompt = """Act as a strict, evidence-bound video QA judge.
Inspect every attached frame and evaluate every requested assertion exactly once.
Use only visible evidence, cite the supplied 1-based frame indexes, and lower the score when
the evidence is ambiguous or temporal behavior cannot be established from sampled frames.
Never infer identity, dialogue accuracy, or off-screen events without visible support.
Return only the JSON object required by the output schema.

INKTOFILM REQUEST
""" + json.dumps(request, ensure_ascii=False, indent=2)
        try:
            raw = self.provider.run_json(
                prompt,
                SEMANTIC_RESULT_SCHEMA,
                images=[frame.path for frame in frames],
                working_dir=evidence_root,
            )
        except ProviderError as exc:
            raise SemanticEvaluationError(str(exc)) from exc
        return _parse_result(spec, raw, frames)


class CommandSemanticEvaluator:
    """Run an explicitly selected evaluator command using JSON over stdin/stdout."""

    def __init__(self, command: Sequence[str], timeout_seconds: float = 180.0):
        if not command:
            raise SemanticEvaluationError("Semantic command cannot be empty")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_string(cls, value: str, timeout_seconds: float = 180.0) -> "CommandSemanticEvaluator":
        return cls(shlex.split(value), timeout_seconds=timeout_seconds)

    def evaluate(
        self,
        spec: CaseSpec,
        video_path: Path,
        probe: VideoProbe,
        evidence_root: Path,
    ) -> List[Finding]:
        assert spec.semantic is not None
        frames = sample_frames(
            video_path,
            probe.duration_seconds,
            spec.semantic.sample_frames,
            evidence_root,
            spec.case_id,
        )
        request = _request(spec, probe, frames)
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SemanticEvaluationError(f"Semantic evaluator could not run: {exc}") from exc
        if completed.returncode:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise SemanticEvaluationError(f"Semantic evaluator failed: {detail}")
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise SemanticEvaluationError("Semantic evaluator did not return valid JSON") from exc
        if not isinstance(raw, dict):
            raise SemanticEvaluationError("Semantic evaluator result must be a JSON object")
        return _parse_result(spec, raw, frames)
