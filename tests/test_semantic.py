import json
import subprocess

from vidspec.config import CaseSpec, SemanticAssertion, SemanticSpec
from vidspec.models import VideoProbe
from vidspec.semantic import CommandSemanticEvaluator, JsonSemanticEvaluator, SampledFrame


def test_json_semantic_evaluator_binds_frame_evidence(tmp_path, monkeypatch):
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps(
            {
                "cases": {
                    "clip": {
                        "evaluator": "test-vlm@1",
                        "assertions": [
                            {
                                "id": "subject",
                                "score": 0.9,
                                "summary": "Subject persists",
                                "rationale": "Visible in both views",
                                "evidence": [
                                    {"frame_index": 2, "description": "Subject in later view"}
                                ],
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    frame = tmp_path / "frame-02.jpg"
    frame.write_bytes(b"jpeg")
    monkeypatch.setattr(
        "vidspec.semantic.sample_frames",
        lambda *args, **kwargs: [
            SampledFrame(2, 3.0, frame, "assets/clip/frame-02.jpg")
        ],
    )
    spec = CaseSpec(
        "clip",
        "clip.mp4",
        semantic=SemanticSpec(
            assertions=[SemanticAssertion("subject", "The subject remains visible", 0.8)]
        ),
    )
    probe = VideoProbe("clip.mp4", 5.0, 1280, 720, 24.0, "h264")
    findings = JsonSemanticEvaluator(results).evaluate(
        spec, tmp_path / "clip.mp4", probe, tmp_path / "assets"
    )
    assert findings[0].status == "pass"
    assert findings[0].observed == {"score": 0.9}
    assert findings[0].evidence[0].timestamp_seconds == 3.0
    assert findings[0].evidence[0].image == "assets/clip/frame-02.jpg"
    assert findings[0].provenance["evaluator"] == "test-vlm@1"


def test_missing_semantic_assertion_becomes_error(tmp_path, monkeypatch):
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps({"cases": {"clip": {"evaluator": "test-vlm", "assertions": []}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("vidspec.semantic.sample_frames", lambda *args, **kwargs: [])
    spec = CaseSpec(
        "clip",
        "clip.mp4",
        semantic=SemanticSpec(assertions=[SemanticAssertion("missing", "Must be judged")]),
    )
    probe = VideoProbe("clip.mp4", 5.0, 1280, 720, 24.0, "h264")
    finding = JsonSemanticEvaluator(results).evaluate(
        spec, tmp_path / "clip.mp4", probe, tmp_path / "assets"
    )[0]
    assert finding.status == "error"
    assert "omitted" in finding.summary


def test_command_semantic_evaluator_uses_json_protocol(tmp_path, monkeypatch):
    frame = tmp_path / "frame-01.jpg"
    frame.write_bytes(b"jpeg")
    monkeypatch.setattr(
        "vidspec.semantic.sample_frames",
        lambda *args, **kwargs: [
            SampledFrame(1, 1.25, frame, "assets/clip/frame-01.jpg")
        ],
    )
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["request"] = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "evaluator": "command-vlm@2",
                    "provenance": {"model": "command-vlm"},
                    "assertions": [
                        {
                            "id": "subject",
                            "score": 0.75,
                            "summary": "Visible",
                            "rationale": "Seen in the sample",
                            "evidence": [{"frame_index": 1, "description": "Subject"}],
                        }
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr("vidspec.semantic.subprocess.run", fake_run)
    spec = CaseSpec(
        "clip",
        "clip.mp4",
        prompt="A visible subject",
        semantic=SemanticSpec(
            assertions=[SemanticAssertion("subject", "The subject is visible", 0.8, "warn")]
        ),
    )
    probe = VideoProbe("clip.mp4", 2.5, 640, 360, 24.0, "h264")
    finding = CommandSemanticEvaluator(["judge", "--json"]).evaluate(
        spec, tmp_path / "clip.mp4", probe, tmp_path / "assets"
    )[0]
    assert captured["command"] == ["judge", "--json"]
    assert captured["request"]["frames"][0]["timestamp_seconds"] == 1.25
    assert finding.status == "warn"
    assert finding.provenance["model"] == "command-vlm"
