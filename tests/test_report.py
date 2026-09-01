import json
from datetime import datetime, timezone

from vidspec.compare import compare_report_files
from vidspec.models import CaseReport, Evidence, Finding, Interval, RunReport, VideoProbe
from vidspec.report import render_html


def test_html_contains_visual_timeline_and_escaped_prompt():
    probe = VideoProbe("clip.mp4", 10.0, 1280, 720, 24.0, "h264")
    case = CaseReport(
        "case-one",
        "clip.mp4",
        "a <red> cube",
        probe,
        [
            Finding(
                "black frames",
                "fail",
                "Black segment",
                intervals=[Interval(2.0, 3.0, "black")],
            )
        ],
    )
    report = RunReport("demo", datetime.now(timezone.utc).isoformat(), [case])
    page = render_html(report)
    assert "left:20.000%" in page
    assert "width:10.000%" in page
    assert "a &lt;red&gt; cube" in page


def test_html_renders_semantic_evidence_thumbnail():
    probe = VideoProbe("clip.mp4", 5.0, 832, 480, 24.0, "h264")
    case = CaseReport(
        "semantic-case",
        "clip.mp4",
        "a monkey hero",
        probe,
        [
            Finding(
                "semantic:hero",
                "pass",
                "Hero is visible",
                evidence=[
                    Evidence(
                        2.5,
                        "Hero raises the staff",
                        frame_index=3,
                        image="assets/semantic-case/frame-03.jpg",
                    )
                ],
            )
        ],
    )
    page = render_html(RunReport("semantic", "2026-09-01T00:00:00Z", [case]))
    assert 'src="assets/semantic-case/frame-03.jpg"' in page
    assert "2.50s · Hero raises the staff" in page


def test_compare_detects_regression(tmp_path):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"cases": [{"id": "one", "status": "pass"}]}))
    candidate.write_text(json.dumps({"cases": [{"id": "one", "status": "fail"}]}))
    result = compare_report_files(baseline, candidate)
    assert result["regressions"] == 1
    assert result["changes"][0]["kind"] == "regression"
