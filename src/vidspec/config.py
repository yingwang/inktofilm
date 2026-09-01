"""Configuration loading and validation for VidSpec JSON suites."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigurationError(ValueError):
    pass


@dataclass
class SemanticAssertion:
    assertion_id: str
    description: str
    min_score: float = 0.7
    severity: str = "fail"


@dataclass
class SemanticSpec:
    assertions: List[SemanticAssertion]
    sample_frames: int = 6


@dataclass
class CaseSpec:
    case_id: str
    video: str
    prompt: str = ""
    expect: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    semantic: Optional[SemanticSpec] = None


@dataclass
class SuiteSpec:
    name: str
    cases: List[CaseSpec]
    base_dir: Path


def load_suite(path: Path) -> SuiteSpec:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Could not read suite JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("Suite root must be a JSON object")
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ConfigurationError("Suite must contain a non-empty 'cases' array")

    parsed: List[CaseSpec] = []
    seen = set()
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            raise ConfigurationError(f"Case {index + 1} must be an object")
        case_id = item.get("id")
        video = item.get("video")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ConfigurationError(f"Case {index + 1} needs a non-empty string id")
        if case_id in seen:
            raise ConfigurationError(f"Duplicate case id: {case_id}")
        if not isinstance(video, str) or not video.strip():
            raise ConfigurationError(f"Case '{case_id}' needs a video path")
        expect = item.get("expect", {})
        metrics = item.get("metrics", {})
        if not isinstance(expect, dict) or not isinstance(metrics, dict):
            raise ConfigurationError(f"Case '{case_id}' expect and metrics must be objects")
        semantic = _parse_semantic(item.get("semantic"), case_id)
        seen.add(case_id)
        parsed.append(
            CaseSpec(
                case_id=case_id,
                video=video,
                prompt=str(item.get("prompt", "")),
                expect=expect,
                metrics=metrics,
                semantic=semantic,
            )
        )

    return SuiteSpec(
        name=str(raw.get("name", path.stem)),
        cases=parsed,
        base_dir=path.resolve().parent,
    )


def _parse_semantic(raw: Any, case_id: str) -> Optional[SemanticSpec]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Case '{case_id}' semantic must be an object")
    assertions = raw.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise ConfigurationError(f"Case '{case_id}' semantic needs a non-empty assertions array")

    sample_frames = raw.get("sample_frames", 6)
    if not isinstance(sample_frames, int) or not 1 <= sample_frames <= 24:
        raise ConfigurationError(f"Case '{case_id}' sample_frames must be between 1 and 24")

    parsed: List[SemanticAssertion] = []
    seen = set()
    for index, item in enumerate(assertions):
        if not isinstance(item, dict):
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion {index + 1} must be an object"
            )
        assertion_id = item.get("id")
        description = item.get("description")
        if not isinstance(assertion_id, str) or not assertion_id.strip():
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion {index + 1} needs a non-empty id"
            )
        if assertion_id in seen:
            raise ConfigurationError(
                f"Case '{case_id}' has duplicate semantic assertion id: {assertion_id}"
            )
        if not isinstance(description, str) or not description.strip():
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion '{assertion_id}' needs a description"
            )
        try:
            min_score = float(item.get("min_score", 0.7))
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion '{assertion_id}' has invalid min_score"
            ) from exc
        if not 0.0 <= min_score <= 1.0:
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion '{assertion_id}' min_score must be 0..1"
            )
        severity = item.get("severity", "fail")
        if severity not in {"warn", "fail"}:
            raise ConfigurationError(
                f"Case '{case_id}' semantic assertion '{assertion_id}' severity must be warn or fail"
            )
        parsed.append(
            SemanticAssertion(
                assertion_id=assertion_id,
                description=description,
                min_score=min_score,
                severity=severity,
            )
        )
        seen.add(assertion_id)
    return SemanticSpec(assertions=parsed, sample_frames=sample_frames)
