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


def _download(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            return response.read()
    except OSError as exc:
        raise ProviderError(f"Could not download generated video: {exc}") from exc


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
        if self._client is not None:
            return self._client
        try:
            return importlib.import_module("fal_client")
        except ImportError as exc:
            raise ProviderError(
                "fal-client is not installed; install InkToFilm with 'pip install inktofilm[fal]'"
            ) from exc

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
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = {
            "schema_version": "1.0",
            "prompt": prompt,
            "duration_seconds": duration_seconds,
            "aspect_ratio": aspect_ratio,
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
