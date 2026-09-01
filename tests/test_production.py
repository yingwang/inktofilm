import json
import subprocess

import pytest

from vidspec.models import CaseReport, Finding
from vidspec.produce import ProductionOrchestrator
from vidspec.production import (
    CharacterSpec,
    CommandProductionPlanner,
    ProductionError,
    ProductionPlan,
    ShotSpec,
    parse_plan,
)
from vidspec.providers import (
    CodexCLIProvider,
    CommandVideoGenerator,
    FalFaceSwapper,
    FalImageGenerator,
    FalMiniMaxGenerator,
)


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


def test_parse_plan_defaults_to_no_stills_when_the_planner_omits_them():
    plan = parse_plan(_raw_plan())
    assert plan.characters[0].reference_prompt == ""
    assert plan.shots[0].still_prompt == ""
    assert plan.shots[0].characters == []
    assert plan.shots[0].face_reference == ""
    assert plan.shots[0].chain_to_next is False


def test_parse_plan_reads_stills_cast_and_chaining():
    raw = _raw_plan()
    raw["characters"][0]["reference_prompt"] = "portrait of the traveler"
    raw["shots"][0].update(
        {
            "still_prompt": "wide on the gate",
            "characters": ["Traveler"],
            "chain_to_next": True,
        }
    )
    raw["shots"].append(
        {
            "shot_id": "lantern-close",
            "scene": "temple gate at night",
            "duration_seconds": 5,
            "prompt": "The traveler looks up.",
            "dialogue": "",
            "assertions": ["The traveler's face fills the frame"],
            "still_prompt": "close on the traveler",
            "characters": ["traveler"],
            "face_reference": "traveler",
        }
    )
    plan = parse_plan(raw)
    assert plan.characters[0].reference_prompt == "portrait of the traveler"
    assert plan.shots[0].chain_to_next is True
    assert plan.shots[0].characters == ["traveler"]
    assert plan.shots[1].face_reference == "traveler"


def test_parse_plan_rejects_unusable_stills_and_chains():
    raw = _raw_plan()
    raw["shots"][0]["chain_to_next"] = True
    with pytest.raises(ProductionError, match="last shot"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"][0]["face_reference"] = "traveler"
    with pytest.raises(ProductionError, match="no still to swap onto"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"][0]["still_prompt"] = "close on a stranger"
    raw["shots"][0]["face_reference"] = "stranger"
    with pytest.raises(ProductionError, match="not in the cast"):
        parse_plan(raw)


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


def test_fal_generator_can_continue_from_a_stable_frame(tmp_path, monkeypatch):
    captured = {"uploads": []}

    class FakeClient:
        @staticmethod
        def upload_file(path):
            captured["uploads"].append(path)
            return "https://example.test/stable-frame.jpg"

        @staticmethod
        def subscribe(model, arguments):
            captured["model"] = model
            captured["arguments"] = arguments
            return {"video": {"url": "https://example.test/continuation.mp4"}}

    monkeypatch.setenv("FAL_KEY", "private-test-key")
    stable_frame = tmp_path / "stable-frame.jpg"
    stable_frame.write_bytes(b"jpeg")
    destination = tmp_path / "continuation.mp4"
    generator = FalMiniMaxGenerator(
        client=FakeClient(),
        downloader=lambda url: b"continued-video",
    )
    generator.generate_from_image("launch into battle", 5, stable_frame, destination)

    assert destination.read_bytes() == b"continued-video"
    assert captured["model"] == "minimax/h3-max/image-to-video"
    assert captured["uploads"] == [stable_frame]
    assert captured["arguments"]["image_url"].endswith("stable-frame.jpg")
    assert captured["arguments"]["duration"] == 5
    assert "private-test-key" not in json.dumps(captured, default=str)


def test_fal_image_generator_edits_from_references_only_when_given_them(tmp_path, monkeypatch):
    calls = []

    class FakeClient:
        @staticmethod
        def upload_file(path):
            return f"https://example.test/{path.name}"

        @staticmethod
        def subscribe(model, arguments):
            calls.append((model, arguments))
            return {"images": [{"url": "https://example.test/still.jpg"}]}

    monkeypatch.setenv("FAL_KEY", "private-test-key")
    generator = FalImageGenerator(client=FakeClient(), downloader=lambda url: b"still-bytes")

    portrait = tmp_path / "references" / "traveler.jpg"
    generator.generate("a portrait of the traveler", portrait, "1:1")
    assert portrait.read_bytes() == b"still-bytes"
    assert calls[0][0] == "fal-ai/nano-banana"
    assert "image_urls" not in calls[0][1]
    assert calls[0][1]["aspect_ratio"] == "1:1"

    still = tmp_path / "stills" / "arrival.jpg"
    generator.generate("wide on the gate", still, "16:9", [portrait])
    assert calls[1][0] == "fal-ai/nano-banana/edit"
    assert calls[1][1]["image_urls"] == ["https://example.test/traveler.jpg"]
    assert "private-test-key" not in json.dumps(calls, default=str)


def test_fal_face_swapper_sends_the_face_and_the_base_still(tmp_path, monkeypatch):
    captured = {}

    class FakeClient:
        @staticmethod
        def upload_file(path):
            return f"https://example.test/{path.name}"

        @staticmethod
        def subscribe(model, arguments):
            captured["model"] = model
            captured["arguments"] = arguments
            return {"image": {"url": "https://example.test/swapped.jpg"}}

    monkeypatch.setenv("FAL_KEY", "private-test-key")
    face = tmp_path / "face.jpg"
    face.write_bytes(b"photo")
    base = tmp_path / "still.jpg"
    base.write_bytes(b"still")
    destination = tmp_path / "swapped.jpg"

    FalFaceSwapper(client=FakeClient(), downloader=lambda url: b"swapped-bytes").swap(
        face,
        base,
        destination,
    )
    assert destination.read_bytes() == b"swapped-bytes"
    assert captured["model"] == "fal-ai/face-swap"
    assert captured["arguments"]["swap_image_url"].endswith("face.jpg")
    assert captured["arguments"]["base_image_url"].endswith("still.jpg")
    assert "private-test-key" not in json.dumps(captured, default=str)


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


def test_orchestrator_locks_stills_swaps_close_ups_and_chains_the_cut(tmp_path, monkeypatch):
    plan = ProductionPlan(
        title="Lantern Test",
        visual_style="cinematic",
        aspect_ratio="16:9",
        characters=[CharacterSpec("traveler", "Traveler", "blue robe", "portrait of the traveler")],
        shots=[
            ShotSpec(
                "arrival",
                "temple gate",
                5,
                "Traveler enters",
                "",
                ["Traveler is visible"],
                still_prompt="wide on the gate",
                characters=["traveler"],
                chain_to_next=True,
            ),
            ShotSpec(
                "close",
                "temple gate",
                5,
                "Traveler looks up",
                "",
                ["The traveler's face fills the frame"],
                still_prompt="close on the traveler",
                characters=["traveler"],
                face_reference="traveler",
            ),
        ],
    )

    class Planner:
        @staticmethod
        def plan(script):
            return plan

    stills_made = []
    swaps_made = []
    shoots = []

    class Images:
        @staticmethod
        def generate(prompt, destination, aspect_ratio="16:9", references=()):
            stills_made.append((prompt, aspect_ratio, [item.name for item in references]))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"still")
            return destination

    class Swapper:
        @staticmethod
        def swap(face_image, base_image, destination):
            swaps_made.append((face_image.name, base_image.name))
            destination.write_bytes(b"swapped")
            return destination

    class Generator:
        @staticmethod
        def generate(prompt, duration_seconds, aspect_ratio, destination):
            raise AssertionError("a shot with a still must be shot from that still")

        @staticmethod
        def generate_from_image(prompt, duration_seconds, start_image, destination, end_image=None):
            shoots.append((start_image.name, end_image.name if end_image else None))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"video")
            return destination

    class Editor:
        @staticmethod
        def concat(clips, destination):
            destination.write_bytes(b"film")
            return destination

    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    face = tmp_path / "her-photo.jpg"
    face.write_bytes(b"photo")
    result = ProductionOrchestrator(
        Planner(),
        generator=Generator(),
        evaluator=object(),
        editor=Editor(),
        image_generator=Images(),
        face_swapper=Swapper(),
        faces={"traveler": face},
    ).produce("A traveler reaches a temple.", tmp_path / "production", max_retries=0)

    # The portrait is rendered square and unconditioned, then each still edits from it.
    assert stills_made[0] == ("portrait of the traveler", "1:1", [])
    assert stills_made[1] == ("wide on the gate", "16:9", ["traveler-face.jpg"])
    # The photographed face lands on the portrait and on the close-up, never on the wide shot.
    assert swaps_made == [
        ("her-photo.jpg", "traveler.jpg"),
        ("her-photo.jpg", "close.jpg"),
    ]
    # The chained shot has to land on the next shot's still; the last shot has no end frame.
    assert shoots == [("arrival.jpg", "close-face.jpg"), ("close-face.jpg", None)]
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["stills"]["close"] == "stills/close-face.jpg"
    assert manifest["shots"][0]["chained_to_next"] is True


def test_orchestrator_rejects_a_face_for_a_character_the_plan_does_not_have(tmp_path):
    plan = ProductionPlan(
        title="Lantern Test",
        visual_style="cinematic",
        aspect_ratio="16:9",
        characters=[CharacterSpec("traveler", "Traveler", "blue robe")],
        shots=[ShotSpec("arrival", "temple gate", 5, "Traveler enters", "", ["Visible"])],
    )
    face = tmp_path / "photo.jpg"
    face.write_bytes(b"photo")
    orchestrator = ProductionOrchestrator(
        type("Planner", (), {"plan": staticmethod(lambda script: plan)})(),
        generator=object(),
        evaluator=object(),
        faces={"stranger": face},
    )
    with pytest.raises(ProductionError, match="stranger"):
        orchestrator.produce("A traveler reaches a temple.", tmp_path / "production")
