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
    ClaudeCodeProvider,
    CodexCLIProvider,
    CommandVideoGenerator,
    FalFaceSwapper,
    FalImageGenerator,
    FalMiniMaxGenerator,
    ProviderError,
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


def _claude_envelope(**overrides):
    envelope = {"is_error": False, "permission_denials": [], "result": "{}"}
    envelope.update(overrides)
    return envelope


def test_claude_provider_reads_frames_in_a_restricted_session(tmp_path, monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(_claude_envelope(structured_output={"answer": "ok"})),
            stderr="",
        )

    monkeypatch.setattr(ClaudeCodeProvider, "available", staticmethod(lambda: True))
    frame = tmp_path / "frames" / "frame.jpg"
    frame.parent.mkdir()
    frame.write_bytes(b"jpeg")
    provider = ClaudeCodeProvider(model="test-model", runner=fake_run)
    result = provider.run_json(
        "judge this",
        {"type": "object"},
        images=[frame],
        working_dir=tmp_path,
    )
    command = captured["command"]
    assert result == {"answer": "ok"}
    # The judge gets a read-only session that ignores the user's own settings.
    assert "--restricted" in command
    assert "--strict-mcp-config" in command
    assert command[command.index("--allowedTools") + 1] == "Read"
    assert command[command.index("--output-format") + 1] == "json"
    assert json.loads(command[command.index("--json-schema") + 1]) == {"type": "object"}
    assert command[command.index("--model") + 1] == "test-model"
    # Claude Code has no image flag, so frames travel as paths plus an opened directory.
    assert command[command.index("--add-dir") + 1] == str(frame.parent.resolve())
    assert str(frame.resolve()) in captured["kwargs"]["input"]


def test_claude_provider_falls_back_to_the_result_text(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(_claude_envelope(result='{"answer": "parsed"}')),
            stderr="",
        )

    monkeypatch.setattr(ClaudeCodeProvider, "available", staticmethod(lambda: True))
    provider = ClaudeCodeProvider(runner=fake_run)
    assert provider.run_json("judge this", {"type": "object"}) == {"answer": "parsed"}


def test_claude_provider_reports_a_failed_or_blocked_session(monkeypatch):
    monkeypatch.setattr(ClaudeCodeProvider, "available", staticmethod(lambda: True))

    def failed(command, **kwargs):
        stdout = json.dumps(_claude_envelope(is_error=True, result="Not logged in"))
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(ProviderError, match="Not logged in"):
        ClaudeCodeProvider(runner=failed).run_json("judge this", {"type": "object"})

    def denied(command, **kwargs):
        stdout = json.dumps(_claude_envelope(permission_denials=[{"tool": "Read"}]))
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(ProviderError, match="could not read the evidence"):
        ClaudeCodeProvider(runner=denied).run_json("judge this", {"type": "object"})


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


def _staged_plan():
    return ProductionPlan(
        title="Lantern Test",
        visual_style="cinematic",
        aspect_ratio="16:9",
        characters=[
            CharacterSpec("traveler", "Traveler", "blue robe", "portrait of the traveler"),
            CharacterSpec("monk", "Monk", "grey robe", "portrait of the monk"),
        ],
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
            ),
            ShotSpec(
                "greeting",
                "temple gate",
                5,
                "The monk bows",
                "",
                ["The monk bows"],
                still_prompt="two-shot at the gate",
                characters=["traveler", "monk"],
            ),
        ],
    )


class _Images:
    def __init__(self):
        self.made = []

    def generate(self, prompt, destination, aspect_ratio="16:9", references=()):
        self.made.append(destination.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"still")
        return destination


class _Generator:
    def __init__(self):
        self.shot = []

    def generate(self, prompt, duration_seconds, aspect_ratio, destination):
        raise AssertionError("a shot with a still must be shot from that still")

    def generate_from_image(self, prompt, duration_seconds, start_image, destination, end_image=None):
        self.shot.append(destination.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination


class _Editor:
    def concat(self, clips, destination):
        destination.write_bytes(b"film:" + b",".join(clip.name.encode() for clip in clips))
        return destination


def test_orchestrator_takes_a_written_plan_and_stops_after_stills(tmp_path):
    images = _Images()
    generator = _Generator()
    result = ProductionOrchestrator(
        planner=None,
        generator=generator,
        evaluator=None,
        editor=_Editor(),
        image_generator=images,
    ).produce("script", tmp_path / "production", plan=_staged_plan(), stills_only=True)

    # Nothing was planned by a model and no video credit was spent.
    assert images.made == ["traveler.jpg", "monk.jpg", "arrival.jpg", "greeting.jpg"]
    assert generator.shot == []
    assert result.final_video is None and result.report is None
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["status"] == "stills"
    assert manifest["stills"] == {"arrival": "stills/arrival.jpg", "greeting": "stills/greeting.jpg"}
    assert json.loads((result.output_dir / "plan.json").read_text(encoding="utf-8"))["title"] == "Lantern Test"


def test_orchestrator_requires_a_planner_or_a_plan(tmp_path):
    with pytest.raises(ProductionError, match="planner or an existing plan"):
        ProductionOrchestrator(planner=None, generator=object(), evaluator=object()).produce(
            "script", tmp_path / "production"
        )


def test_orchestrator_reuses_reviewed_stills_and_attempts_and_reshoots_on_request(tmp_path, monkeypatch):
    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    output = tmp_path / "production"

    def run(images, generator, **kwargs):
        return ProductionOrchestrator(
            planner=None,
            generator=generator,
            evaluator=None,
            editor=_Editor(),
            image_generator=images,
        ).produce("script", output, plan=_staged_plan(), unjudged=True, max_retries=0, **kwargs)

    first_images, first_generator = _Images(), _Generator()
    first = run(first_images, first_generator)
    assert first_images.made == ["traveler.jpg", "monk.jpg", "arrival.jpg", "greeting.jpg"]
    assert first_generator.shot == ["arrival-attempt-1.mp4", "greeting-attempt-1.mp4"]

    # The reviewer rejects one still and deletes it; only that still is rendered again, and
    # no shot is regenerated because every attempt is already on disk.
    (output / "stills" / "greeting.jpg").unlink()
    second_images, second_generator = _Images(), _Generator()
    second = run(second_images, second_generator)
    assert second_images.made == ["greeting.jpg"]
    assert second_generator.shot == []
    manifest = json.loads(second.manifest.read_text(encoding="utf-8"))
    assert [shot["attempts"][0]["generated"] for shot in manifest["shots"]] == [False, False]

    # A reshoot gets the next attempt number and becomes the selected clip.
    third_generator = _Generator()
    third = run(_Images(), third_generator, reshoot=["greeting"])
    assert third_generator.shot == ["greeting-attempt-2.mp4"]
    manifest = json.loads(third.manifest.read_text(encoding="utf-8"))
    assert manifest["shots"][1]["selected_video"] == "shots/greeting-attempt-2.mp4"
    (attempt,) = manifest["shots"][1]["attempts"]
    assert attempt["attempt"] == 2 and attempt["generated"] is True
    assert attempt["video"] == "shots/greeting-attempt-2.mp4"
    assert manifest["judged"] is False
    assert third.final_video.read_bytes() == b"film:arrival-attempt-1.mp4,greeting-attempt-2.mp4"
    assert first.final_video == third.final_video

    with pytest.raises(ProductionError, match="finale"):
        run(_Images(), _Generator(), reshoot=["finale"])


def test_orchestrator_writes_a_replayable_suite_for_the_selected_clips(tmp_path, monkeypatch):
    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    result = ProductionOrchestrator(
        planner=None,
        generator=_Generator(),
        evaluator=None,
        editor=_Editor(),
        image_generator=_Images(),
    ).produce("script", tmp_path / "production", plan=_staged_plan(), unjudged=True)

    from vidspec.config import load_suite

    suite = load_suite(result.output_dir / "suite.json")
    assert [case.case_id for case in suite.cases] == ["arrival", "greeting"]
    assert suite.cases[0].video == "shots/arrival-attempt-1.mp4"
    assert suite.cases[1].semantic.assertions[0].description == "The monk bows"
    assert suite.cases[1].semantic.sample_frames == 6


def test_orchestrator_refuses_to_shoot_without_a_judge_unless_told_to(tmp_path):
    with pytest.raises(ProviderError, match="no-judge"):
        ProductionOrchestrator(planner=None, generator=object(), evaluator=None).produce(
            "script", tmp_path / "production", plan=_staged_plan()
        )


def test_generation_prompt_describes_only_the_cast_the_shot_lists():
    from vidspec.produce import _generation_prompt

    plan = _staged_plan()
    solo = _generation_prompt(plan, plan.shots[0])
    both = _generation_prompt(plan, plan.shots[1])
    assert "Traveler: blue robe" in solo and "Monk" not in solo
    assert "Traveler: blue robe" in both and "Monk: grey robe" in both


def test_orchestrator_uses_the_attempt_a_reviewer_selected(tmp_path, monkeypatch):
    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    output = tmp_path / "production"

    def run(generator, **kwargs):
        return ProductionOrchestrator(
            planner=None,
            generator=generator,
            evaluator=None,
            editor=_Editor(),
            image_generator=_Images(),
        ).produce("script", output, plan=_staged_plan(), unjudged=True, max_retries=0, **kwargs)

    run(_Generator())
    run(_Generator(), reshoot=["greeting"])
    # The reviewer prefers the first take after all: nothing is generated and take 1 is the clip.
    chooser = _Generator()
    result = run(chooser, select={"greeting": 1})
    assert chooser.shot == []
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["shots"][1]["selected_video"] == "shots/greeting-attempt-1.mp4"
    assert [a["attempt"] for a in manifest["shots"][1]["attempts"]] == [1]
    assert result.final_video.read_bytes() == b"film:arrival-attempt-1.mp4,greeting-attempt-1.mp4"

    with pytest.raises(ProductionError, match="does not exist"):
        run(_Generator(), select={"greeting": 9})
    with pytest.raises(ProductionError, match="both reshoot and select"):
        run(_Generator(), select={"greeting": 1}, reshoot=["greeting"])


def test_cli_selection_map_rejects_malformed_values():
    from vidspec.cli import _selection_map

    assert _selection_map(["Shot Two=2", "arrival=1"]) == {"shot-two": 2, "arrival": 1}
    for bad in ("arrival", "arrival=", "arrival=zero", "arrival=0"):
        with pytest.raises(ProductionError, match="SHOT_ID=ATTEMPT"):
            _selection_map([bad])


def test_unjudged_rerun_keeps_the_newest_take_from_an_earlier_reshoot(tmp_path, monkeypatch):
    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    output = tmp_path / "production"

    def run(**kwargs):
        return ProductionOrchestrator(
            planner=None,
            generator=_Generator(),
            evaluator=None,
            editor=_Editor(),
            image_generator=_Images(),
        ).produce("script", output, plan=_staged_plan(), unjudged=True, **kwargs)

    run()
    run(reshoot=["greeting"])
    # A plain re-run has no judge to prefer an older take, so the reshoot stands.
    result = run()
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["shots"][1]["selected_video"] == "shots/greeting-attempt-2.mp4"
    assert result.final_video.read_bytes() == b"film:arrival-attempt-1.mp4,greeting-attempt-2.mp4"


def test_parse_plan_reads_continuation_and_two_faces():
    raw = _raw_plan()
    raw["characters"].append(
        {"character_id": "guard", "name": "Guard", "description": "a guard in white"}
    )
    raw["shots"].append(
        {
            "shot_id": "banter",
            "scene": "temple gate at night",
            "duration_seconds": 6,
            "prompt": "They talk.",
            "dialogue": "",
            "assertions": ["Two people talk"],
            "continue_from_previous": True,
            "face_reference": ["traveler", "guard", "traveler"],
        }
    )
    raw["shots"].append(
        {
            "shot_id": "draw",
            "scene": "temple gate at night",
            "duration_seconds": 5,
            "prompt": "She draws.",
            "dialogue": "",
            "assertions": ["A blade is drawn"],
            "continue_from_previous": 2.5,
        }
    )
    plan = parse_plan(raw)
    assert plan.shots[0].continue_from_previous is None
    assert plan.shots[1].continue_from_previous == 0.4
    assert plan.shots[1].face_references == ["traveler", "guard"]
    assert plan.shots[1].face_reference == "traveler"
    assert plan.shots[2].continue_from_previous == 2.5
    assert plan.shots[2].face_references == []
    # A single string keeps working and is mirrored into the list.
    single = ShotSpec("s", "scene", 5, "p", "", ["a"], still_prompt="x", face_reference="traveler")
    assert single.face_references == ["traveler"]


def test_parse_plan_rejects_impossible_continuations():
    raw = _raw_plan()
    raw["shots"][0]["continue_from_previous"] = True
    with pytest.raises(ProductionError, match="first shot"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"].append(dict(raw["shots"][0], shot_id="second", continue_from_previous=True))
    raw["shots"][1]["still_prompt"] = "a still"
    with pytest.raises(ProductionError, match="cannot both continue"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"].append(dict(raw["shots"][0], shot_id="second", continue_from_previous=5))
    with pytest.raises(ProductionError, match="less than the previous"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"].append(dict(raw["shots"][0], shot_id="second", continue_from_previous="late"))
    with pytest.raises(ProductionError, match="true, false, or seconds"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"][0]["still_prompt"] = "a still"
    raw["shots"][0]["chain_to_next"] = True
    raw["shots"].append(dict(raw["shots"][0], shot_id="second", still_prompt="", chain_to_next=False))
    raw["shots"][1]["continue_from_previous"] = True
    with pytest.raises(ProductionError, match="use one or the other"):
        parse_plan(raw)

    raw = _raw_plan()
    raw["shots"][0]["face_reference"] = ["traveler", 3]
    with pytest.raises(ProductionError, match="string or a list"):
        parse_plan(raw)


def test_orchestrator_continues_from_the_previous_take_and_swaps_faces_on_the_frame(tmp_path, monkeypatch):
    plan = ProductionPlan(
        title="Rooftop",
        visual_style="cinematic",
        aspect_ratio="16:9",
        characters=[
            CharacterSpec("heroine", "Heroine", "crimson robe"),
            CharacterSpec("hero", "Hero", "white robe"),
        ],
        shots=[
            ShotSpec("ridge", "roof", 5, "She lands", "", ["She lands"], characters=["heroine"]),
            ShotSpec(
                "banter",
                "roof",
                6,
                "They talk",
                "",
                ["They talk"],
                characters=["heroine", "hero"],
                continue_from_previous=0.4,
                face_references=["heroine", "hero"],
            ),
            ShotSpec(
                "draw",
                "roof",
                5,
                "She draws",
                "",
                ["A blade"],
                characters=["heroine", "hero"],
                continue_from_previous=2.0,
            ),
        ],
    )
    grabbed, shoots, swaps = [], [], []

    def grabber(video, seconds_from_end, destination):
        grabbed.append((video.name, seconds_from_end, destination.name))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"frame")
        return destination

    class Swapper:
        @staticmethod
        def swap(face_image, base_image, destination):
            raise AssertionError("two faces must go through swap_many")

        @staticmethod
        def swap_many(face_images, base_image, destination):
            swaps.append(([face.name for face in face_images], base_image.name))
            destination.write_bytes(b"swapped")
            return destination

    class Generator:
        @staticmethod
        def generate(prompt, duration_seconds, aspect_ratio, destination):
            shoots.append((destination.name, None))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"video")
            return destination

        @staticmethod
        def generate_from_image(prompt, duration_seconds, start_image, destination, end_image=None):
            shoots.append((destination.name, start_image.name))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"video")
            return destination

    def fake_evaluate(spec, base_dir, **kwargs):
        return CaseReport(spec.case_id, spec.video, spec.prompt, None, [])

    monkeypatch.setattr("vidspec.produce.evaluate_case", fake_evaluate)
    her = tmp_path / "her.jpg"
    him = tmp_path / "him.jpg"
    her.write_bytes(b"her")
    him.write_bytes(b"him")
    output = tmp_path / "production"

    def run(**kwargs):
        return ProductionOrchestrator(
            planner=None,
            generator=Generator(),
            evaluator=None,
            editor=_Editor(),
            image_generator=_Images(),
            face_swapper=Swapper(),
            faces={"heroine": her, "hero": him},
            frame_grabber=grabber,
        ).produce("script", output, plan=plan, unjudged=True, max_retries=0, **kwargs)

    result = run()
    # The first shot is text-to-video; each later shot opens on a frame cut from the take before it,
    # named after that take, and both photographed faces land on the dialogue frame only.
    assert shoots == [
        ("ridge-attempt-1.mp4", None),
        ("banter-attempt-1.mp4", "banter-from-ridge-attempt-1-face.jpg"),
        ("draw-attempt-1.mp4", "draw-from-banter-attempt-1.jpg"),
    ]
    assert grabbed == [
        ("ridge-attempt-1.mp4", 0.4, "banter-from-ridge-attempt-1.jpg"),
        ("banter-attempt-1.mp4", 2.0, "draw-from-banter-attempt-1.jpg"),
    ]
    assert swaps == [(["her.jpg", "him.jpg"], "banter-from-ridge-attempt-1.jpg")]
    manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
    assert manifest["shots"][1]["continued_from"] == "shots/ridge-attempt-1.mp4"
    assert manifest["shots"][1]["still"] == "stills/banter-from-ridge-attempt-1-face.jpg"
    assert manifest["stills"]["draw"] == "stills/draw-from-banter-attempt-1.jpg"

    # Reshooting the middle shot grabs from the same first take, but the last shot then continues
    # from the new middle take, because its opening frame follows the selected clip.
    grabbed.clear()
    shoots.clear()
    swaps.clear()
    run(reshoot=["banter"])
    assert shoots == [("banter-attempt-2.mp4", "banter-from-ridge-attempt-1-face.jpg")]
    assert grabbed == [] and swaps == []
    grabbed.clear()
    shoots.clear()
    run(reshoot=["draw"])
    assert grabbed == [("banter-attempt-2.mp4", 2.0, "draw-from-banter-attempt-2.jpg")]
    assert shoots == [("draw-attempt-2.mp4", "draw-from-banter-attempt-2.jpg")]


def test_easel_face_swapper_sends_two_faces_with_their_genders(tmp_path, monkeypatch):
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
    her = tmp_path / "her.jpg"
    him = tmp_path / "him.jpg"
    base = tmp_path / "frame.jpg"
    for path in (her, him, base):
        path.write_bytes(b"x")
    swapper = FalFaceSwapper(
        model="easel-ai/advanced-face-swap",
        client=FakeClient(),
        downloader=lambda url: b"swapped-bytes",
        genders={her: "female", him: "male"},
    )
    swapper.swap_many([her, him], base, tmp_path / "out.jpg")
    arguments = captured["arguments"]
    assert captured["model"] == "easel-ai/advanced-face-swap"
    assert arguments["face_image_0"].endswith("her.jpg") and arguments["gender_0"] == "female"
    assert arguments["face_image_1"].endswith("him.jpg") and arguments["gender_1"] == "male"
    assert arguments["target_image"].endswith("frame.jpg")
    assert arguments["workflow_type"] == "target_hair"
    assert "private-test-key" not in json.dumps(arguments, default=str)

    # One face without a declared gender is sent as non-binary; three faces are refused.
    swapper.swap(base, her, tmp_path / "one.jpg")
    assert captured["arguments"]["gender_0"] == "non-binary"
    with pytest.raises(ProviderError, match="At most two"):
        swapper.swap_many([her, him, base], base, tmp_path / "three.jpg")


def test_single_face_model_swaps_two_faces_in_left_to_right_strips(tmp_path, monkeypatch):
    from pathlib import Path

    swapped = []
    commands = []

    class FakeClient:
        @staticmethod
        def upload_file(path):
            return f"https://example.test/{path.name}"

        @staticmethod
        def subscribe(model, arguments):
            swapped.append((arguments["swap_image_url"], arguments["base_image_url"]))
            return {"image": {"url": "https://example.test/swapped.jpg"}}

    def runner(command, **kwargs):
        commands.append(command)
        if command[0].endswith("ffprobe"):
            return subprocess.CompletedProcess(command, 0, '{"streams":[{"width":1344,"height":768}]}', "")
        output = Path(command[-1])
        output.write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setenv("FAL_KEY", "private-test-key")
    monkeypatch.setattr("vidspec.providers.shutil.which", lambda name: f"/usr/bin/{name}")
    her, him, base = tmp_path / "her.jpg", tmp_path / "him.jpg", tmp_path / "frame.jpg"
    for path in (her, him, base):
        path.write_bytes(b"x")
    out = tmp_path / "out.jpg"
    FalFaceSwapper(client=FakeClient(), downloader=lambda url: b"swapped", runner=runner).swap_many(
        [him, her], base, out
    )
    # The left strip gets the first face and the right strip the second, each swapped alone.
    assert swapped == [
        ("https://example.test/him.jpg", "https://example.test/out-strip0.jpg"),
        ("https://example.test/her.jpg", "https://example.test/out-strip1.jpg"),
    ]
    crops = [c[c.index("-vf") + 1] for c in commands if "-vf" in c]
    assert crops == ["crop=672:768:0:0", "crop=672:768:672:0"]
    composite = [c for c in commands if "-filter_complex" in c][0]
    assert composite[composite.index("-filter_complex") + 1] == (
        "[0:v][1:v]overlay=0:0[c0];[c0][2:v]overlay=672:0[c1]"
    )
    assert composite[-1] == str(out) and out.is_file()


def test_cli_gender_map_checks_names_and_values(tmp_path):
    from vidspec.cli import _gender_map

    her = tmp_path / "her.jpg"
    assert _gender_map(["heroine=Female"], {"heroine": her}) == {her: "female"}
    with pytest.raises(ProductionError, match="one of"):
        _gender_map(["heroine=woman"], {"heroine": her})
    with pytest.raises(ProductionError, match="has no --face"):
        _gender_map(["hero=male"], {"heroine": her})
    with pytest.raises(ProductionError, match="CHARACTER_ID=GENDER"):
        _gender_map(["heroine"], {"heroine": her})
