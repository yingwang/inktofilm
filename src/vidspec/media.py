"""FFprobe and FFmpeg adapters with deliberately small, stable parsing surfaces."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Callable, Dict, List, Optional

from vidspec.models import Interval, VideoProbe


class MediaToolError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess]


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise MediaToolError(
            f"{name} was not found. Install FFmpeg and ensure {name} is on PATH."
        )
    return executable


def _ratio(value: str) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        if float(denominator) == 0:
            return 0.0
        return float(numerator) / float(denominator)
    return float(value)


def probe_video(path: Path, runner: Runner = subprocess.run) -> VideoProbe:
    ffprobe = require_tool("ffprobe")
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr.strip() or "ffprobe could not read the video")
    try:
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
    except (json.JSONDecodeError, StopIteration, TypeError) as exc:
        raise MediaToolError("ffprobe returned no readable video stream") from exc

    format_info: Dict[str, str] = payload.get("format", {})
    duration = float(video.get("duration") or format_info.get("duration") or 0)
    frame_count = video.get("nb_frames")
    return VideoProbe(
        path=str(path),
        duration_seconds=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        fps=_ratio(str(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0")),
        codec=str(video.get("codec_name") or "unknown"),
        pixel_format=str(video.get("pix_fmt") or ""),
        frame_count=int(frame_count) if frame_count and str(frame_count).isdigit() else None,
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
        size_bytes=int(path.stat().st_size),
    )


_BLACK_RE = re.compile(
    r"black_start:(?P<start>[0-9.]+)\s+black_end:(?P<end>[0-9.]+)"
)
_FREEZE_START_RE = re.compile(r"freeze_start:\s*(?P<value>[0-9.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:\s*(?P<value>[0-9.]+)")


def _run_filter(path: Path, video_filter: str, runner: Runner) -> str:
    ffmpeg = require_tool("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vf",
        video_filter,
        "-an",
        "-f",
        "null",
        "-",
    ]
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 255):
        raise MediaToolError(completed.stderr.strip() or "ffmpeg analysis failed")
    return completed.stderr


def detect_black_frames(
    path: Path,
    minimum_duration: float = 0.10,
    pixel_threshold: float = 0.10,
    runner: Runner = subprocess.run,
) -> List[Interval]:
    output = _run_filter(
        path,
        f"blackdetect=d={minimum_duration}:pix_th={pixel_threshold}",
        runner,
    )
    return [
        Interval(float(match.group("start")), float(match.group("end")), "black")
        for match in _BLACK_RE.finditer(output)
    ]


def detect_freezes(
    path: Path,
    minimum_duration: float = 0.50,
    noise_db: float = -50.0,
    runner: Runner = subprocess.run,
) -> List[Interval]:
    output = _run_filter(
        path,
        f"freezedetect=n={noise_db}dB:d={minimum_duration}",
        runner,
    )
    intervals: List[Interval] = []
    pending: Optional[float] = None
    for line in output.splitlines():
        start = _FREEZE_START_RE.search(line)
        if start:
            pending = float(start.group("value"))
        end = _FREEZE_END_RE.search(line)
        if end and pending is not None:
            intervals.append(Interval(pending, float(end.group("value")), "freeze"))
            pending = None
    return intervals


def subprocess_runner(command: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess:
    """Public seam for integrations that need to wrap process execution."""
    return subprocess.run(command, **kwargs)  # type: ignore[arg-type]

