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
_PROGRESS_TIME_RE = re.compile(
    r"time=(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>[0-9.]+)"
)


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
    if pending is not None:
        progress = list(_PROGRESS_TIME_RE.finditer(output))
        if progress:
            last = progress[-1]
            end_seconds = (
                int(last.group("hours")) * 3600
                + int(last.group("minutes")) * 60
                + float(last.group("seconds"))
            )
            if end_seconds > pending:
                intervals.append(Interval(pending, end_seconds, "freeze"))
    return intervals


_MOTION_TIME_RE = re.compile(r"pts_time:(?P<time>[0-9.]+)")
_MOTION_VALUE_RE = re.compile(r"lavfi\.signalstats\.YAVG=(?P<value>[0-9.]+)")


def motion_energy(
    path: Path,
    bucket_seconds: float = 0.5,
    runner: Runner = subprocess.run,
) -> List[float]:
    """Mean frame-to-frame luminance change per time bucket, as a tempo curve.

    Each frame is differenced against the one before it and the average absolute change is
    read from `signalstats`; averaging those per bucket gives a curve a reviewer can read as
    rhythm without watching the clip: a fight with a real beat shows bursts and a lull, a
    floating one shows a flat line, and a shot that never moves shows values near zero.
    """
    if bucket_seconds <= 0:
        raise MediaToolError("bucket_seconds must be positive")
    ffmpeg = require_tool("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vf",
        "scale=320:-2,tblend=all_mode=difference,signalstats,"
        "metadata=print:key=lavfi.signalstats.YAVG:file=-",
        "-f",
        "null",
        "-",
    ]
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise MediaToolError(completed.stderr.strip() or "ffmpeg could not measure motion")
    sums: Dict[int, float] = {}
    counts: Dict[int, int] = {}
    current = 0.0
    for line in completed.stdout.splitlines():
        time_match = _MOTION_TIME_RE.search(line)
        if time_match:
            current = float(time_match.group("time"))
            continue
        value_match = _MOTION_VALUE_RE.search(line)
        if value_match:
            bucket = int(current / bucket_seconds)
            sums[bucket] = sums.get(bucket, 0.0) + float(value_match.group("value"))
            counts[bucket] = counts.get(bucket, 0) + 1
    if not sums:
        return []
    last = max(sums)
    return [round(sums.get(i, 0.0) / counts[i], 2) if counts.get(i) else 0.0 for i in range(last + 1)]


def extract_frame(
    path: Path,
    timestamp_seconds: float,
    destination: Path,
    runner: Runner = subprocess.run,
) -> Path:
    """Write the frame at `timestamp_seconds` as a full-resolution JPEG.

    Used to hand one shot's late frame to the next shot as its opening image, so the frame is
    kept at the clip's own size rather than the reduced size the judge samples at.
    """
    ffmpeg = require_tool("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(timestamp_seconds, 0.0):.6f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-y",
        str(destination),
    ]
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0 or not destination.is_file():
        raise MediaToolError(
            (completed.stderr or "").strip() or "ffmpeg did not write the requested frame"
        )
    return destination


def subprocess_runner(command: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess:
    """Public seam for integrations that need to wrap process execution."""
    return subprocess.run(command, **kwargs)  # type: ignore[arg-type]
