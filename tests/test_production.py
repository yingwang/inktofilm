import json
import subprocess

from vidspec.models import CaseReport, Finding
from vidspec.produce import ProductionOrchestrator
from vidspec.production import (
    CharacterSpec,
    CommandProductionPlanner,
    ProductionPlan,
    ShotSpec,
    parse_plan,
)
from vidspec.providers import CodexCLIProvider, CommandVideoGenerator, FalMiniMaxGenerator


def _raw_plan():
    return {
        "title": "Lantern Test",
        "visual_style": "cinematic moonlit period drama",
        "aspect_ratio": "16:9",
        "characters": [
            {
                "character_id": "traveler",
                "name": "Traveler",
                "description": "young traveler in a blue robe",
            }
        ],
        "shots": [
            {
                "shot_id": "lantern-arrival",
                "scene": "temple gate at night",
                "duration_seconds": 5,
                "prompt": "The traveler enters beneath a swaying lantern.",
                "dialogue": "Is anyone here?",
                "assertions": ["A blue-robed traveler enters", "A lantern sways overhead"],
            }
        ],
    }


def test_parse_plan_normalizes_ids():
    raw = _raw_plan()
    raw["shots"][0]["shot_id"] = "Lantern Arrival"
    plan = parse_plan(raw)
    assert plan.shots[0].shot_id == "lantern-arrival"
    assert plan.shots[0].duration_seconds == 5


def test_codex_provider_uses_ephemeral_read_only_structured_output(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        output = command[command.index("--output-last-message") + 1]
        with open(output, "w", encoding="utf-8") as handle:
            json.dump({"answer": "ok"}, handle)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(CodexCLIProvider, "available", staticmethod(lambda: True))
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")
    provider = CodexCLIProvider(model="test-model", runner=fake_run)
    result = provider.run_json(
        "judge this",
        {"type": "object"},
        images=[frame],
        working_dir=tmp_path,
    )
    command = captured["command"]
    assert result == {"answer": "ok"}
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--model") + 1] == "test-model"
    assert str(frame.resolve()) in command
    assert captured["kwargs"]["input"] == "judge this"


def test_fal_generator_uses_environment_key_without_persisting_it(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        @staticmethod
        def subscribe(model, arguments):
            captured["model"] = model
            captured["arguments"] = arguments
            return {"video": {"url": "https://example.test/video.mp4"}}

    monkeypatch.setenv("FAL_KEY", "private-test-key")
    destination = tmp_path / "shot.mp4"
    generator = FalMiniMaxGenerator(
        client=FakeClient(),
        downloader=lambda url: b"generated-video",
    )
    generator.generate("a visible traveler", 5, "16:9", destination)
    assert destination.read_bytes() == b"generated-video"
    assert captured["model"] == "minimax/h3-max/text-to-video"
    assert captured["arguments"]["duration"] == 5
    assert captured["arguments"]["prompt_expansion_mode"] == "balanced"
    assert "private-test-key" not in json.dumps(captured)


def test_command_planner_and_video_generator_use_explicit_json_protocol(tmp_path, monkeypatch):
    captured = {}

    def fake_plan_run(command, **kwargs):
        captured["plan_request"] = json.loads(kwargs["input"])
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(_raw_plan()), stderr="")

    monkeypatch.setattr("vidspec.production.subprocess.run", fake_plan_run)
    plan = CommandProductionPlanner.from_string("custom-llm --json").plan("A temple story")
    assert plan.title == "Lantern Test"
    assert captured["plan_request"]["task"] == "screenplay_to_short_film_plan"

    def fake_video_run(command, **kwargs):
        request = json.loads(kwargs["input"])
        captured["video_request"] = request
        with open(request["destination"], "wb") as handle:
            handle.write(b"custom-video")
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr("vidspec.providers.subprocess.run", fake_video_run)
    destination = tmp_path / "custom.mp4"
    CommandVideoGenerator.from_string("custom-video --json").generate(
        "a temple",
        5,
        "16:9",
        destination,
    )
    assert destination.read_bytes() == b"custom-video"
    assert captured["video_request"]["destination"] == str(destination.resolve())


def test_orchestrator_retries_failed_shot_and_writes_manifest(tmp_path, monkeypatch):
    plan = ProductionPlan(
        title="Lantern Test",
        visual_style="cinematic",
        aspect_ratio="16:9",
        characters=[CharacterSpec("traveler", "Traveler", "blue robe")],
        shots=[
            ShotSpec(
                "arrival",
                "temple gate",
                5,
                "Traveler enters",
                "",
                ["Traveler is visible"],
            )
        ],
    )

    class Planner:
        @staticmethod
        def plan(script):
            assert "temple" in script
            return plan

    prompts = []

    class Generator:
        @staticmethod
        def generate(prompt, duration_seconds, aspect_ratio, destination):
            prompts.append(prompt)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"video")
            return destination

    class Editor:
        @staticmethod
        def concat(clips, destination):
            assert len(clips) == 1
            destination.write_bytes(b"film")
            return destination

    statuses = iter(["fail", "pass"])

    def fake_evaluate(spec, base_dir, **kwargs):
        status = next(statuses)
        return CaseReport(
            spec.case_id,
            spec.video,
            spec.prompt,
            None,
            [Finding("semantic:visible-01", status, "Traveler missing" if status == "fail" else "Visible")],
        )

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    result = ProductionOrchestrator(
        Planner(),
        generator=Generator(),
        evaluator=object(),
        editor=Editor(),
    ).produce("A traveler reaches a temple.", tmp_path / "production", max_retries=1)
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert len(prompts) == 2
    assert "prior failures" in prompts[1]
    assert manifest["shots"][0]["attempts"][1]["status"] == "pass"
    assert result.final_video.read_bytes() == b"film"
    assert (result.output_dir / "plan.json").is_file()
    assert (result.output_dir / "index.html").is_file()
