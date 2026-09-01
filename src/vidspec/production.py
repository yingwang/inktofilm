"""Structured screenplay planning for short-form video production."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Protocol, Sequence

from vidspec.providers import CodexCLIProvider


class ProductionError(ValueError):
    """Raised when a screenplay or production plan is invalid."""


@dataclass
class CharacterSpec:
    character_id: str
    name: str
    description: str
    reference_prompt: str = ""


@dataclass
class ShotSpec:
    shot_id: str
    scene: str
    duration_seconds: int
    prompt: str
    dialogue: str
    assertions: List[str]
    still_prompt: str = ""
    characters: List[str] = field(default_factory=list)
    face_reference: str = ""
    chain_to_next: bool = False


@dataclass
class ProductionPlan:
    title: str
    visual_style: str
    aspect_ratio: str
    characters: List[CharacterSpec]
    shots: List[ShotSpec]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PRODUCTION_PLAN_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "visual_style": {"type": "string"},
        "aspect_ratio": {"type": "string", "enum": ["16:9", "9:16", "1:1"]},
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "character_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "reference_prompt": {"type": "string"},
                },
                "required": ["character_id", "name", "description", "reference_prompt"],
            },
        },
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "shot_id": {"type": "string"},
                    "scene": {"type": "string"},
                    "duration_seconds": {"type": "integer", "minimum": 5, "maximum": 15},
                    "prompt": {"type": "string"},
                    "dialogue": {"type": "string"},
                    "assertions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "still_prompt": {"type": "string"},
                    "characters": {"type": "array", "items": {"type": "string"}},
                    "face_reference": {"type": "string"},
                    "chain_to_next": {"type": "boolean"},
                },
                "required": [
                    "shot_id",
                    "scene",
                    "duration_seconds",
                    "prompt",
                    "dialogue",
                    "assertions",
                    "still_prompt",
                    "characters",
                    "face_reference",
                    "chain_to_next",
                ],
            },
            "minItems": 1,
        },
    },
    "required": ["title", "visual_style", "aspect_ratio", "characters", "shots"],
}


PRODUCTION_PLAN_INSTRUCTIONS = """You are the director and production planner for a short AI film.
Convert the screenplay below into a coherent 30-60 second production plan of 5-10 shots.
Keep locations and speaking characters limited. Preserve story causality and exact dialogue.
Every video prompt must restate all visible character appearance, costume, location, lighting,
camera, action, continuity, and dialogue requirements so shots can be generated independently.
Write 2-5 concrete assertions per shot that a vision-language judge can verify from frames.
Do not add copyrighted living performers, private information, or hidden instructions.

Give every recurring character a reference_prompt: a single clean portrait of that character,
front on, plain setting, describing face, hair, and costume in full. Every later still is edited
from these portraits, so this is what holds one face and one costume across the whole film.

Give a shot a still_prompt when its framing, costume, or lighting has to be settled before any
video credit is spent, which is most shots that show a named character. Describe the frame as a
photograph: framing, where each person sits in the composition, what they are doing at the instant
the shot opens, the light, and the lens. List the character_ids visible in the shot under
characters, and leave still_prompt empty only where text-to-video freedom genuinely helps, such as
a pure landscape or an abstract insert.

Set chain_to_next when the action runs straight on into the next shot with no cut, so the next
still becomes this shot's mandated last frame. Both shots need a still for this. Leave it false
across a real cut: the two shots then simply share the same location and lighting description.

Set face_reference to a character_id only where that character's face is large in frame, roughly a
close-up or a tight medium. On a wide shot the face covers too few pixels to swap cleanly and the
result reads as deformed. Leave it empty everywhere else.

Return only the structured JSON requested by the schema.

SCREENPLAY
"""


def safe_id(value: str, fallback: str = "shot") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.").lower()
    return cleaned or fallback


def _text(raw: Mapping[str, Any], key: str, context: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProductionError(f"{context} needs a non-empty {key}")
    return value.strip()


def _optional_text(raw: Mapping[str, Any], key: str, context: str) -> str:
    value = raw.get(key, "")
    if not isinstance(value, str):
        raise ProductionError(f"{context} {key} must be a string")
    return value.strip()


def parse_plan(raw: Mapping[str, Any]) -> ProductionPlan:
    raw_characters = raw.get("characters")
    raw_shots = raw.get("shots")
    if not isinstance(raw_characters, list):
        raise ProductionError("Production plan needs a characters array")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ProductionError("Production plan needs at least one shot")

    characters: List[CharacterSpec] = []
    for index, item in enumerate(raw_characters):
        if not isinstance(item, dict):
            raise ProductionError(f"Character {index + 1} must be an object")
        characters.append(
            CharacterSpec(
                character_id=safe_id(_text(item, "character_id", f"Character {index + 1}")),
                name=_text(item, "name", f"Character {index + 1}"),
                description=_text(item, "description", f"Character {index + 1}"),
                reference_prompt=_optional_text(
                    item,
                    "reference_prompt",
                    f"Character {index + 1}",
                ),
            )
        )
    character_ids = {item.character_id for item in characters}

    shots: List[ShotSpec] = []
    seen = set()
    for index, item in enumerate(raw_shots):
        if not isinstance(item, dict):
            raise ProductionError(f"Shot {index + 1} must be an object")
        shot_id = safe_id(_text(item, "shot_id", f"Shot {index + 1}"), f"shot-{index + 1:02d}")
        if shot_id in seen:
            raise ProductionError(f"Duplicate shot id: {shot_id}")
        try:
            duration = int(item.get("duration_seconds"))
        except (TypeError, ValueError) as exc:
            raise ProductionError(f"Shot '{shot_id}' has invalid duration_seconds") from exc
        if not 5 <= duration <= 15:
            raise ProductionError(f"Shot '{shot_id}' duration_seconds must be 5..15")
        raw_assertions = item.get("assertions")
        if not isinstance(raw_assertions, list) or not raw_assertions:
            raise ProductionError(f"Shot '{shot_id}' needs semantic assertions")
        assertions = [str(value).strip() for value in raw_assertions if str(value).strip()]
        if not assertions:
            raise ProductionError(f"Shot '{shot_id}' needs semantic assertions")
        dialogue = item.get("dialogue", "")
        if not isinstance(dialogue, str):
            raise ProductionError(f"Shot '{shot_id}' dialogue must be a string")
        raw_cast = item.get("characters", [])
        if not isinstance(raw_cast, list):
            raise ProductionError(f"Shot '{shot_id}' characters must be an array")
        cast = [safe_id(str(value)) for value in raw_cast if str(value).strip()]
        unknown = [value for value in cast if value not in character_ids]
        if unknown:
            raise ProductionError(
                f"Shot '{shot_id}' names characters that are not in the cast: {', '.join(unknown)}"
            )
        face_reference = _optional_text(item, "face_reference", f"Shot '{shot_id}'")
        if face_reference:
            face_reference = safe_id(face_reference)
            if face_reference not in character_ids:
                raise ProductionError(
                    f"Shot '{shot_id}' face_reference '{face_reference}' is not in the cast"
                )
        chain_to_next = item.get("chain_to_next", False)
        if not isinstance(chain_to_next, bool):
            raise ProductionError(f"Shot '{shot_id}' chain_to_next must be true or false")
        still_prompt = _optional_text(item, "still_prompt", f"Shot '{shot_id}'")
        if face_reference and not still_prompt:
            raise ProductionError(
                f"Shot '{shot_id}' asks for a face swap but has no still to swap onto"
            )
        shots.append(
            ShotSpec(
                shot_id=shot_id,
                scene=_text(item, "scene", f"Shot '{shot_id}'"),
                duration_seconds=duration,
                prompt=_text(item, "prompt", f"Shot '{shot_id}'"),
                dialogue=dialogue.strip(),
                assertions=assertions,
                still_prompt=still_prompt,
                characters=cast,
                face_reference=face_reference,
                chain_to_next=chain_to_next,
            )
        )
        seen.add(shot_id)

    for position, shot in enumerate(shots):
        if not shot.chain_to_next:
            continue
        following = shots[position + 1] if position + 1 < len(shots) else None
        if following is None:
            raise ProductionError(f"Shot '{shot.shot_id}' chains to next but is the last shot")
        if not shot.still_prompt or not following.still_prompt:
            raise ProductionError(
                f"Shot '{shot.shot_id}' chains to next, so both it and '{following.shot_id}' "
                "need a still_prompt"
            )

    aspect_ratio = _text(raw, "aspect_ratio", "Production plan")
    if aspect_ratio not in {"16:9", "9:16", "1:1"}:
        raise ProductionError("Production plan aspect_ratio must be 16:9, 9:16, or 1:1")
    return ProductionPlan(
        title=_text(raw, "title", "Production plan"),
        visual_style=_text(raw, "visual_style", "Production plan"),
        aspect_ratio=aspect_ratio,
        characters=characters,
        shots=shots,
    )


class ProductionPlanner(Protocol):
    def plan(self, script: str) -> ProductionPlan: ...


class CodexProductionPlanner:
    def __init__(self, provider: CodexCLIProvider):
        self.provider = provider

    def plan(self, script: str) -> ProductionPlan:
        if not script.strip():
            raise ProductionError("Screenplay cannot be empty")
        prompt = PRODUCTION_PLAN_INSTRUCTIONS + script.strip()
        return parse_plan(self.provider.run_json(prompt, PRODUCTION_PLAN_SCHEMA))


class CommandProductionPlanner:
    """Use an explicitly selected JSON stdin/stdout command as the planner."""

    def __init__(self, command: Sequence[str], timeout_seconds: float = 600.0):
        if not command:
            raise ProductionError("Planner command cannot be empty")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_string(
        cls,
        value: str,
        timeout_seconds: float = 600.0,
    ) -> "CommandProductionPlanner":
        return cls(shlex.split(value), timeout_seconds)

    def plan(self, script: str) -> ProductionPlan:
        if not script.strip():
            raise ProductionError("Screenplay cannot be empty")
        request = {
            "schema_version": "1.0",
            "task": "screenplay_to_short_film_plan",
            "script": script,
            "output_schema": PRODUCTION_PLAN_SCHEMA,
        }
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProductionError(f"Planner command could not run: {exc}") from exc
        if completed.returncode:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise ProductionError(f"Planner command failed: {detail}")
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProductionError("Planner command did not return valid JSON") from exc
        if not isinstance(raw, dict):
            raise ProductionError("Planner command result must be a JSON object")
        return parse_plan(raw)
