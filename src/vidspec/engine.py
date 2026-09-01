"""Rule engine for repeatable video checks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from vidspec.config import CaseSpec, SuiteSpec
from vidspec.media import MediaToolError, detect_black_frames, detect_freezes, probe_video
from vidspec.models import CaseReport, Finding, Interval, RunReport, VideoProbe
from vidspec.semantic import SemanticEvaluationError, SemanticEvaluator

ProbeFn = Callable[[Path], VideoProbe]
IntervalFn = Callable[..., List[Interval]]


def _range_check(name: str, value: float, rule: Dict[str, Any], unit: str = "") -> Finding:
    minimum = rule.get("min")
    maximum = rule.get("max")
    passed = (minimum is None or value >= float(minimum)) and (
        maximum is None or value <= float(maximum)
    )
    expected = {key: rule[key] for key in ("min", "max") if key in rule}
    label = f"{value:g}{unit}"
    return Finding(
        check=name,
        status="pass" if passed else "fail",
        summary=f"{name} is within range" if passed else f"{name} is outside range",
        observed=label,
        expected=expected,
    )


def _interval_check(
    name: str,
    intervals: List[Interval],
    duration: float,
    rule: Dict[str, Any],
) -> Finding:
    total = sum(interval.duration_seconds for interval in intervals)
    ratio = total / duration if duration > 0 else 0.0
    max_ratio = float(rule.get("max_total_ratio", 0.0))
    passed = ratio <= max_ratio
    return Finding(
        check=name,
        status="pass" if passed else "fail",
        summary=(
            f"No excessive {name} detected"
            if passed
            else f"{name.capitalize()} occupies {ratio:.1%} of the video"
        ),
        observed={"seconds": round(total, 4), "ratio": round(ratio, 6), "events": len(intervals)},
        expected={"max_total_ratio": max_ratio},
        intervals=intervals,
    )


def _metric_findings(metrics: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for name, rule in sorted(metrics.items()):
        if not isinstance(rule, dict) or "value" not in rule:
            findings.append(
                Finding(name, "error", "Metric needs an object containing 'value'", observed=rule)
            )
            continue
        value = float(rule["value"])
        finding = _range_check(name, value, rule)
        finding.details = str(rule.get("source", "external metric"))
        findings.append(finding)
    return findings


def evaluate_case(
    spec: CaseSpec,
    base_dir: Path,
    probe_fn: ProbeFn = probe_video,
    black_fn: IntervalFn = detect_black_frames,
    freeze_fn: IntervalFn = detect_freezes,
    semantic_evaluator: Optional[SemanticEvaluator] = None,
    evidence_root: Optional[Path] = None,
) -> CaseReport:
    path = (base_dir / spec.video).resolve()
    try:
        path.relative_to(base_dir.resolve())
    except ValueError:
        return CaseReport(
            spec.case_id,
            spec.video,
            spec.prompt,
            None,
            [Finding("path", "error", "Video path escapes the suite directory")],
        )
    if not path.is_file():
        return CaseReport(
            spec.case_id,
            spec.video,
            spec.prompt,
            None,
            [Finding("file", "error", "Video file does not exist", observed=str(path))],
        )

    try:
        probe = probe_fn(path)
    except (MediaToolError, OSError, ValueError) as exc:
        return CaseReport(
            spec.case_id,
            spec.video,
            spec.prompt,
            None,
            [Finding("probe", "error", "Could not inspect video", details=str(exc))],
        )

    findings: List[Finding] = [Finding("decode", "pass", "Video stream is readable")]
    duration_rule = spec.expect.get("duration_seconds")
    if isinstance(duration_rule, dict):
        findings.append(_range_check("duration", probe.duration_seconds, duration_rule, "s"))

    resolution_rule = spec.expect.get("resolution")
    if isinstance(resolution_rule, dict):
        width_ok = probe.width >= int(resolution_rule.get("min_width", 0))
        height_ok = probe.height >= int(resolution_rule.get("min_height", 0))
        findings.append(
            Finding(
                "resolution",
                "pass" if width_ok and height_ok else "fail",
                "Resolution meets minimum" if width_ok and height_ok else "Resolution is too small",
                observed=f"{probe.width}x{probe.height}",
                expected=resolution_rule,
            )
        )

    fps_rule = spec.expect.get("fps")
    if isinstance(fps_rule, dict):
        findings.append(_range_check("fps", probe.fps, fps_rule))

    codecs = spec.expect.get("codecs")
    if isinstance(codecs, list) and codecs:
        passed = probe.codec in codecs
        findings.append(
            Finding(
                "codec",
                "pass" if passed else "fail",
                "Codec is allowed" if passed else "Codec is not allowed",
                observed=probe.codec,
                expected=codecs,
            )
        )

    for key, label, detector in (
        ("black_frames", "black frames", black_fn),
        ("freezes", "freezes", freeze_fn),
    ):
        rule = spec.expect.get(key)
        if isinstance(rule, dict):
            try:
                intervals = detector(path)
                findings.append(_interval_check(label, intervals, probe.duration_seconds, rule))
            except (MediaToolError, OSError, ValueError) as exc:
                findings.append(Finding(label, "error", "Could not run temporal check", details=str(exc)))

    findings.extend(_metric_findings(spec.metrics))
    if spec.semantic is not None:
        if semantic_evaluator is None:
            findings.append(
                Finding(
                    "semantics",
                    "skipped",
                    "Semantic assertions declared but no evaluator was selected",
                    expected={"assertions": len(spec.semantic.assertions)},
                    details="Use --semantic-results or --semantic-command to opt in.",
                )
            )
        elif evidence_root is None:
            findings.append(
                Finding("semantics", "error", "Semantic evidence output directory is unavailable")
            )
        else:
            try:
                findings.extend(
                    semantic_evaluator.evaluate(spec, path, probe, evidence_root)
                )
            except SemanticEvaluationError as exc:
                findings.append(
                    Finding("semantics", "error", "Semantic evaluation failed", details=str(exc))
                )
    return CaseReport(spec.case_id, spec.video, spec.prompt, probe, findings)


def run_suite(
    suite: SuiteSpec,
    probe_fn: ProbeFn = probe_video,
    black_fn: IntervalFn = detect_black_frames,
    freeze_fn: IntervalFn = detect_freezes,
    now: Optional[datetime] = None,
    semantic_evaluator: Optional[SemanticEvaluator] = None,
    evidence_root: Optional[Path] = None,
) -> RunReport:
    timestamp = now or datetime.now(timezone.utc)
    cases = [
        evaluate_case(
            case,
            suite.base_dir,
            probe_fn,
            black_fn,
            freeze_fn,
            semantic_evaluator,
            evidence_root,
        )
        for case in suite.cases
    ]
    return RunReport(suite.name, timestamp.isoformat(), cases)
