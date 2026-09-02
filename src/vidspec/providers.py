"""External model providers used by the production workflow."""

from __future__ import annotations

import importlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence


class ProviderError(RuntimeError):
    """Raised when an external provider cannot complete a request."""


RunCommand = Callable[..., subprocess.CompletedProcess[str]]
Download = Callable[[str], bytes]


class CodexCLIProvider:
    """Use the locally authenticated Codex CLI as a structured-output model."""

    def __init__(
        self,
        model: Optional[str] = None,
        timeout_seconds: float = 600.0,
        runner: RunCommand = subprocess.run,
    ):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    @staticmethod
    def available() -> bool:
        return shutil.which("codex") is not None

    def run_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        images: Sequence[Path] = (),
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not self.available():
            raise ProviderError("Codex CLI is not installed or not available on PATH")
        base_dir = working_dir.resolve() if working_dir else None
        if base_dir is not None:
            base_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="vidspec-codex-", dir=base_dir) as temp_name:
            temp_dir = Path(temp_name)
            schema_path = temp_dir / "schema.json"
            output_path = temp_dir / "response.json"
            schema_path.write_text(
                json.dumps(schema, ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                "codex",
                "exec",
                "--ephemeral",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--ignore-user-config",
                "--ignore-rules",
            ]
            if self.model:
                command.extend(["--model", self.model])
            if images:
                command.append("--image")
                command.extend(str(path.resolve()) for path in images)
            command.extend(
                [
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "-",
                ]
            )
            try:
                completed = self.runner(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    cwd=str(base_dir) if base_dir else None,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProviderError(f"Codex CLI could not run: {exc}") from exc
            if completed.returncode:
                detail = completed.stderr.strip() or f"exit code {completed.returncode}"
                raise ProviderError(f"Codex CLI failed: {detail}")
            try:
                payload = output_path.read_text(encoding="utf-8")
            except OSError:
                payload = completed.stdout
            try:
                raw = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ProviderError("Codex CLI did not return valid JSON") from exc
            if not isinstance(raw, dict):
                raise ProviderError("Codex CLI result must be a JSON object")
            return raw


class ClaudeCodeProvider:
    """Use the locally authenticated Claude Code CLI as a structured-output model.

    The mirror of CodexCLIProvider. Claude Code has no flag for attaching images, so frames are
    named by absolute path in the prompt and read with the Read tool, which is why the directories
    holding them have to be opened with --add-dir.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        timeout_seconds: float = 600.0,
        runner: RunCommand = subprocess.run,
    ):
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    @staticmethod
    def available() -> bool:
        return shutil.which("claude") is not None

    def run_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        images: Sequence[Path] = (),
        working_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not self.available():
            raise ProviderError("Claude Code CLI is not installed or not available on PATH")
        resolved = [path.resolve() for path in images]
        directories = []
        for path in resolved:
            parent = str(path.parent)
            if parent not in directories:
                directories.append(parent)
        if resolved:
            listing = "\n".join(f"Frame {index}: {path}" for index, path in enumerate(resolved, 1))
            prompt = (
                f"{prompt}\n\nRead every one of these images before answering. "
                f"They are numbered in order.\n{listing}"
            )
        command = [
            "claude",
            "--print",
            # The judge reads frames and nothing else: no shell, no network, and no user,
            # project, or local settings that could color a verdict.
            "--restricted",
            "--strict-mcp-config",
            "--allowedTools",
            "Read",
            "--permission-mode",
            "dontAsk",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, ensure_ascii=False),
        ]
        for directory in directories:
            command.extend(["--add-dir", directory])
        if self.model:
            command.extend(["--model", self.model])
        base_dir = working_dir.resolve() if working_dir else None
        if base_dir is not None:
            base_dir.mkdir(parents=True, exist_ok=True)
        try:
            completed = self.runner(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=str(base_dir) if base_dir else None,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError(f"Claude Code CLI could not run: {exc}") from exc
        if completed.returncode:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise ProviderError(f"Claude Code CLI failed: {detail}")
        try:
            envelope = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError("Claude Code CLI did not return valid JSON") from exc
        if not isinstance(envelope, dict):
            raise ProviderError("Claude Code CLI result must be a JSON object")
        if envelope.get("is_error"):
            detail = envelope.get("result") or "the session reported an error"
            raise ProviderError(f"Claude Code CLI failed: {detail}")
        denials = envelope.get("permission_denials")
        if denials:
            raise ProviderError(
                f"Claude Code CLI could not read the evidence it was given: {denials}"
            )
        raw = envelope.get("structured_output")
        if raw is None:
            try:
                raw = json.loads(envelope.get("result", ""))
            except json.JSONDecodeError as exc:
                raise ProviderError("Claude Code CLI did not return structured output") from exc
        if not isinstance(raw, dict):
            raise ProviderError("Claude Code CLI structured output must be a JSON object")
        return raw


def _download(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            return response.read()
    except OSError as exc:
        raise ProviderError(f"Could not download generated video: {exc}") from exc


def _fal_client(client: Any) -> Any:
    if client is not None:
        return client
    try:
        return importlib.import_module("fal_client")
    except ImportError as exc:
        raise ProviderError(
            "fal-client is not installed; install InkToFilm with 'pip install inktofilm[fal]'"
        ) from exc


def _first_image_url(result: Any) -> str:
    """Read the image URL out of a fal result, which may hold one image or a list."""
    image = result.get("images") or result.get("image") if isinstance(result, dict) else None
    if isinstance(image, list):
        image = image[0] if image else None
    url = image.get("url") if isinstance(image, dict) else image
    if not isinstance(url, str) or not url:
        raise ProviderError("fal image result did not contain an image url")
    return url


def _write_image(url: str, destination: Path, downloader: Download) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(downloader(url))
    if not destination.is_file() or destination.stat().st_size == 0:
        raise ProviderError("fal returned an empty image")
    return destination


class FalImageGenerator:
    """Generate a composition-locked still through the user's fal account.

    A still fixes costume, framing, and lighting before any video credit is spent, and the
    same still can then condition the shot that follows it.
    """

    def __init__(
        self,
        model: str = "fal-ai/nano-banana",
        edit_model: str = "fal-ai/nano-banana/edit",
        client: Any = None,
        downloader: Download = _download,
    ):
        self.model = model
        self.edit_model = edit_model
        self._client = client
        self.downloader = downloader

    def generate(
        self,
        prompt: str,
        destination: Path,
        aspect_ratio: str = "16:9",
        references: Sequence[Path] = (),
    ) -> Path:
        """Render one still, editing from reference stills when any are supplied."""
        if not os.environ.get("FAL_KEY"):
            raise ProviderError("FAL_KEY is required for the fal image provider")
        for reference in references:
            if not reference.is_file():
                raise ProviderError(f"Reference still does not exist: {reference}")
        client = _fal_client(self._client)
        arguments: Dict[str, Any] = {
            "prompt": prompt,
            "num_images": 1,
            "aspect_ratio": aspect_ratio,
            # The file is saved as .jpg, so ask for JPEG rather than the model's PNG default.
            "output_format": "jpeg",
        }
        model = self.model
        if references:
            model = self.edit_model
            arguments["image_urls"] = [client.upload_file(item) for item in references]
        try:
            result = client.subscribe(model, arguments=arguments)
        except Exception as exc:
            raise ProviderError(f"fal still generation failed: {exc}") from exc
        return _write_image(_first_image_url(result), destination, self.downloader)


class FalFaceSwapper:
    """Put supplied faces onto a generated still through the user's fal account.

    Worth doing only where the face is large in frame. On a wide shot the face covers too few
    pixels for the swap to survive, and the attempt usually reads as a deformed face.

    Two model families are understood. `fal-ai/face-swap` takes one face and one base image.
    `easel-ai/advanced-face-swap` takes one or two faces, each with a declared gender, keeps the
    target's hair by default, and upscales; it is the one to use when two people share a frame,
    because a single-face model cannot be told which of them to replace.
    """

    GENDERS = ("female", "male", "non-binary")

    def __init__(
        self,
        model: str = "fal-ai/face-swap",
        client: Any = None,
        downloader: Download = _download,
        genders: Optional[Mapping[Path, str]] = None,
        default_gender: str = "non-binary",
        hair: str = "target_hair",
    ):
        self.model = model
        self._client = client
        self.downloader = downloader
        self.genders = {Path(key).resolve(): value for key, value in (genders or {}).items()}
        if default_gender not in self.GENDERS:
            raise ProviderError(f"Face gender must be one of {', '.join(self.GENDERS)}")
        self.default_gender = default_gender
        if hair not in ("target_hair", "user_hair"):
            raise ProviderError("Face swap hair mode must be target_hair or user_hair")
        self.hair = hair

    @property
    def is_easel(self) -> bool:
        return self.model.startswith("easel-ai/")

    def _gender(self, face_image: Path) -> str:
        return self.genders.get(face_image.resolve(), self.default_gender)

    def swap(self, face_image: Path, base_image: Path, destination: Path) -> Path:
        return self.swap_many([face_image], base_image, destination)

    def swap_many(
        self,
        face_images: Sequence[Path],
        base_image: Path,
        destination: Path,
    ) -> Path:
        if not os.environ.get("FAL_KEY"):
            raise ProviderError("FAL_KEY is required for the fal face-swap provider")
        faces = list(face_images)
        if not faces:
            raise ProviderError("A face swap needs at least one face image")
        for face_image in faces:
            if not face_image.is_file():
                raise ProviderError(f"Face image does not exist: {face_image}")
        if not base_image.is_file():
            raise ProviderError(f"Base still does not exist: {base_image}")
        if len(faces) > 1 and not self.is_easel:
            raise ProviderError(
                f"{self.model} swaps one face at a time; use easel-ai/advanced-face-swap for "
                "two faces in one frame"
            )
        if len(faces) > 2:
            raise ProviderError("At most two faces can be swapped onto one frame")
        client = _fal_client(self._client)
        arguments: Dict[str, Any]
        if self.is_easel:
            arguments = {
                "face_image_0": client.upload_file(faces[0]),
                "gender_0": self._gender(faces[0]),
                "target_image": client.upload_file(base_image),
                "workflow_type": self.hair,
                "upscale": True,
                "detailer": True,
            }
            if len(faces) == 2:
                arguments["face_image_1"] = client.upload_file(faces[1])
                arguments["gender_1"] = self._gender(faces[1])
        else:
            arguments = {
                "swap_image_url": client.upload_file(faces[0]),
                "base_image_url": client.upload_file(base_image),
            }
        try:
            result = client.subscribe(self.model, arguments=arguments)
        except Exception as exc:
            raise ProviderError(f"fal face swap failed: {exc}") from exc
        return _write_image(_first_image_url(result), destination, self.downloader)


class FalMiniMaxGenerator:
    """Generate a shot with MiniMax H3 through the user's fal account."""

    def __init__(
        self,
        model: str = "minimax/h3-max/text-to-video",
        image_model: str = "minimax/h3-max/image-to-video",
        resolution: str = "768P",
        client: Any = None,
        downloader: Download = _download,
    ):
        self.model = model
        self.image_model = image_model
        self.resolution = resolution
        self._client = client
        self.downloader = downloader

    def _load_client(self) -> Any:
        return _fal_client(self._client)

    def generate(
        self,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        destination: Path,
    ) -> Path:
        if not os.environ.get("FAL_KEY"):
            raise ProviderError("FAL_KEY is required for the fal MiniMax provider")
        client = self._load_client()
        arguments: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration_seconds,
            "resolution": self.resolution,
            "aspect_ratio": aspect_ratio,
            "prompt_expansion_mode": "balanced",
            "enable_safety_checker": True,
        }
        try:
            result = client.subscribe(self.model, arguments=arguments)
        except Exception as exc:
            raise ProviderError(f"fal MiniMax generation failed: {exc}") from exc
        video = result.get("video") if isinstance(result, dict) else None
        url = video.get("url") if isinstance(video, dict) else None
        if not isinstance(url, str) or not url:
            raise ProviderError("fal MiniMax result did not contain video.url")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.downloader(url))
        if not destination.is_file() or destination.stat().st_size == 0:
            raise ProviderError("fal MiniMax returned an empty video")
        return destination

    def generate_from_image(
        self,
        prompt: str,
        duration_seconds: int,
        start_image: Path,
        destination: Path,
        end_image: Optional[Path] = None,
    ) -> Path:
        """Generate a continuation using a still as the exact first-frame condition."""
        if not os.environ.get("FAL_KEY"):
            raise ProviderError("FAL_KEY is required for the fal MiniMax provider")
        if not start_image.is_file():
            raise ProviderError(f"Start image does not exist: {start_image}")
        if end_image is not None and not end_image.is_file():
            raise ProviderError(f"End image does not exist: {end_image}")

        client = self._load_client()
        arguments: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration_seconds,
            "resolution": self.resolution,
            "prompt_expansion_mode": "balanced",
            "enable_safety_checker": True,
            "image_url": client.upload_file(start_image),
        }
        if end_image is not None:
            arguments["end_image_url"] = client.upload_file(end_image)
        try:
            result = client.subscribe(self.image_model, arguments=arguments)
        except Exception as exc:
            raise ProviderError(f"fal MiniMax image generation failed: {exc}") from exc
        video = result.get("video") if isinstance(result, dict) else None
        url = video.get("url") if isinstance(video, dict) else None
        if not isinstance(url, str) or not url:
            raise ProviderError("fal MiniMax result did not contain video.url")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.downloader(url))
        if not destination.is_file() or destination.stat().st_size == 0:
            raise ProviderError("fal MiniMax returned an empty video")
        return destination


class CommandVideoGenerator:
    """Use an explicitly selected JSON stdin/stdout command as the video generator."""

    def __init__(self, command: Sequence[str], timeout_seconds: float = 1800.0):
        if not command:
            raise ProviderError("Video command cannot be empty")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_string(
        cls,
        value: str,
        timeout_seconds: float = 1800.0,
    ) -> "CommandVideoGenerator":
        return cls(shlex.split(value), timeout_seconds)

    def generate(
        self,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        destination: Path,
    ) -> Path:
        return self._run(
            {
                "prompt": prompt,
                "duration_seconds": duration_seconds,
                "aspect_ratio": aspect_ratio,
            },
            destination,
        )

    def generate_from_image(
        self,
        prompt: str,
        duration_seconds: int,
        start_image: Path,
        destination: Path,
        end_image: Optional[Path] = None,
    ) -> Path:
        if not start_image.is_file():
            raise ProviderError(f"Start image does not exist: {start_image}")
        if end_image is not None and not end_image.is_file():
            raise ProviderError(f"End image does not exist: {end_image}")
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "start_image": str(start_image.resolve()),
        }
        if end_image is not None:
            payload["end_image"] = str(end_image.resolve())
        return self._run(payload, destination)

    def _run(self, payload: Dict[str, Any], destination: Path) -> Path:
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = {
            "schema_version": "1.0",
            **payload,
            "destination": str(destination),
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
            raise ProviderError(f"Video command could not run: {exc}") from exc
        if completed.returncode:
            detail = completed.stderr.strip() or f"exit code {completed.returncode}"
            raise ProviderError(f"Video command failed: {detail}")
        if not destination.is_file():
            try:
                raw = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                raise ProviderError(
                    "Video command must write destination or return JSON containing video"
                ) from exc
            source_value = raw.get("video") if isinstance(raw, dict) else None
            source = Path(source_value).expanduser().resolve() if isinstance(source_value, str) else None
            if source is None or not source.is_file():
                raise ProviderError("Video command did not produce a readable video")
            shutil.copy2(source, destination)
        if destination.stat().st_size == 0:
            raise ProviderError("Video command produced an empty video")
        return destination
