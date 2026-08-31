import json
from datetime import datetime, timezone

from vidspec.compare import compare_report_files
from vidspec.models import CaseReport, Finding, Interval, RunReport, VideoProbe
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


def test_compare_detects_regression(tmp_path):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"cases": [{"id": "one", "status": "pass"}]}))
    candidate.write_text(json.dumps({"cases": [{"id": "one", "status": "fail"}]}))
    result = compare_report_files(baseline, candidate)
    assert result["regressions"] == 1
    assert result["changes"][0]["kind"] == "regression"

