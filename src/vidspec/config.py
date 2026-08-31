"""Configuration loading and validation for VidSpec JSON suites."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


class ConfigurationError(ValueError):
    pass


@dataclass
class CaseSpec:
    case_id: str
    video: str
    prompt: str = ""
    expect: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


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
        seen.add(case_id)
        parsed.append(
            CaseSpec(
                case_id=case_id,
                video=video,
                prompt=str(item.get("prompt", "")),
                expect=expect,
                metrics=metrics,
            )
        )

    return SuiteSpec(
        name=str(raw.get("name", path.stem)),
        cases=parsed,
        base_dir=path.resolve().parent,
    )

