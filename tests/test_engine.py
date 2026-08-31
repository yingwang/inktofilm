from datetime import datetime, timezone

from vidspec.config import CaseSpec, SuiteSpec
from vidspec.engine import evaluate_case, run_suite
from vidspec.models import Interval, VideoProbe


def fake_probe(path):
    return VideoProbe(str(path), 5.0, 1280, 720, 24.0, "h264", size_bytes=123)


def test_rule_engine_finds_temporal_failure(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    spec = CaseSpec(
        "clip",
        "clip.mp4",
        "A stable red cube",
        expect={
            "duration_seconds": {"min": 4, "max": 6},
            "resolution": {"min_width": 720, "min_height": 480},
            "black_frames": {"max_total_ratio": 0.01},
            "freezes": {"max_total_ratio": 0.2},
        },
        metrics={"prompt_alignment": {"value": 0.88, "min": 0.8, "source": "demo-vlm"}},
    )
    report = evaluate_case(
        spec,
        tmp_path,
        probe_fn=fake_probe,
        black_fn=lambda path: [Interval(1.0, 1.5, "black")],
        freeze_fn=lambda path: [],
    )
    assert report.status == "fail"
    assert next(item for item in report.findings if item.check == "prompt_alignment").status == "pass"
    black = next(item for item in report.findings if item.check == "black frames")
    assert black.observed["ratio"] == 0.1


def test_suite_is_deterministic_given_clock_and_adapters(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    suite = SuiteSpec("demo", [CaseSpec("clip", "clip.mp4")], tmp_path)
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    report = run_suite(
        suite,
        probe_fn=fake_probe,
        black_fn=lambda path: [],
        freeze_fn=lambda path: [],
        now=now,
    )
    assert report.generated_at == "2026-09-01T00:00:00+00:00"
    assert report.status == "pass"


def test_path_escape_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside.mp4"
    outside.write_bytes(b"video")
    report = evaluate_case(CaseSpec("escape", "../outside.mp4"), tmp_path, probe_fn=fake_probe)
    assert report.status == "error"
    assert "escapes" in report.findings[0].summary

