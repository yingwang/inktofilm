"""Small serializable domain models used by the runner and reporters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

STATUS_ORDER = {"pass": 0, "skipped": 1, "warn": 2, "fail": 3, "error": 4}


def worst_status(statuses: List[str]) -> str:
    if not statuses:
        return "skipped"
    return max(statuses, key=lambda value: STATUS_ORDER[value])


@dataclass
class VideoProbe:
    path: str
    duration_seconds: float
    width: int
    height: int
    fps: float
    codec: str
    pixel_format: str = ""
    frame_count: Optional[int] = None
    has_audio: bool = False
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Interval:
    start_seconds: float
    end_seconds: float
    kind: str

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["duration_seconds"] = round(self.duration_seconds, 4)
        return value


@dataclass
class Evidence:
    timestamp_seconds: float
    description: str = ""
    frame_index: Optional[int] = None
    image: str = ""

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["timestamp_seconds"] = round(self.timestamp_seconds, 4)
        return value


@dataclass
class Finding:
    check: str
    status: str
    summary: str
    observed: Any = None
    expected: Any = None
    intervals: List[Interval] = field(default_factory=list)
    details: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "summary": self.summary,
            "observed": self.observed,
            "expected": self.expected,
            "intervals": [interval.to_dict() for interval in self.intervals],
            "details": self.details,
            "evidence": [item.to_dict() for item in self.evidence],
            "provenance": self.provenance,
        }


@dataclass
class CaseReport:
    case_id: str
    video: str
    prompt: str
    probe: Optional[VideoProbe]
    findings: List[Finding]

    @property
    def status(self) -> str:
        return worst_status([finding.status for finding in self.findings])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.case_id,
            "video": self.video,
            "prompt": self.prompt,
            "status": self.status,
            "probe": self.probe.to_dict() if self.probe else None,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass
class RunReport:
    suite_name: str
    generated_at: str
    cases: List[CaseReport]
    schema_version: str = "1.0"

    @property
    def status(self) -> str:
        return worst_status([case.status for case in self.cases])

    @property
    def summary(self) -> Dict[str, int]:
        counts = {status: 0 for status in STATUS_ORDER}
        for case in self.cases:
            counts[case.status] += 1
        counts["total"] = len(self.cases)
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite": self.suite_name,
            "generated_at": self.generated_at,
            "status": self.status,
            "summary": self.summary,
            "cases": [case.to_dict() for case in self.cases],
        }
