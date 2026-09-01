#!/usr/bin/env python3
"""Assemble the Great Havoc demo with cinematic transitions and dialogue."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "great-havoc-in-heaven"
GENERATED = EXAMPLE / "generated"
OUTPUT = EXAMPLE / "great-havoc-in-heaven-trailer.mp4"

VIDEOS = (
    GENERATED / "shot-01-celestial-armada-768p.mp4",
    GENERATED / "shot-02-monkey-king-looks-up.mp4",
    GENERATED / "shot-03-breaks-formation-i2v.mp4",
    GENERATED / "shot-04-colossal-transformation.mp4",
    GENERATED / "shot-05-south-heavenly-gate-falls-final.mp4",
    GENERATED / "title-card.mp4",
)

DIALOGUE = (
    GENERATED / "dialogue-heavenly-decree.mp3",
    GENERATED / "dialogue-wukong-defiance.mp3",
    GENERATED / "dialogue-wukong-climax.mp3",
)

# Four 0.4-second overlaps make the five generated shots feel connected. The title card remains an
# intentional hard punctuation after the climax. Starts are the resulting positions in milliseconds.
SHOT_STARTS_MS = (0, 4784, 9568, 14352, 19136, 24136)
DIALOGUE_STARTS_MS = (1300, 6300, 16800)

# Loudness and echo treatment per spoken line, in the order of DIALOGUE.
DIALOGUE_TREATMENTS = (
    ("loudnorm=I=-19:TP=-3:LRA=6", "aecho=0.8:0.45:80|160:0.20|0.10"),
    ("loudnorm=I=-18:TP=-3:LRA=6", "aecho=0.8:0.55:48:0.12"),
    ("loudnorm=I=-18:TP=-3:LRA=7", "aecho=0.8:0.55:52:0.13"),
)

# A spoken line peaks far above this in its own window; ambience is mixed separately and
# never reaches the dialogue submix, so anything quieter means the line was lost.
DIALOGUE_FLOOR_DB = -40.0
DIALOGUE_WINDOW_SECONDS = 3.0


def input_args(paths: tuple[Path, ...]) -> list[str]:
    args: list[str] = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"missing input: {path.relative_to(ROOT)}")
        args.extend(("-i", str(path)))
    return args


def video_filters() -> list[str]:
    common = (
        "scale=1344:768:force_original_aspect_ratio=increase,"
        "crop=1344:768,fps=24,format=yuv420p,setsar=1,setpts=PTS-STARTPTS"
    )
    filters = [
        f"[{index}:v]trim=duration={5.184 if index < 4 else 5.0},{common}[v{index}]"
        for index in range(5)
    ]
    filters.append(
        f"[5:v]trim=duration=5,{common},tpad=stop_mode=clone:stop_duration=0.864[v5]"
    )
    filters.extend(
        (
            "[v0][v1]xfade=transition=fade:duration=0.4:offset=4.784[v01]",
            "[v01][v2]xfade=transition=fadefast:duration=0.4:offset=9.568[v012]",
            "[v012][v3]xfade=transition=fadewhite:duration=0.4:offset=14.352[v0123]",
            "[v0123][v4]xfade=transition=fadefast:duration=0.4:offset=19.136[vfilm]",
            "[vfilm][v5]concat=n=2:v=1:a=0,trim=duration=30,setpts=PTS-STARTPTS[vout]",
        )
    )
    return filters


def audio_filters() -> list[str]:
    durations = (5.184, 5.184, 5.184, 5.184, 5.0, 5.864)
    filters: list[str] = []
    for index, (duration, start_ms) in enumerate(zip(durations, SHOT_STARTS_MS)):
        fade_in = "" if index == 0 else "afade=t=in:st=0:d=0.4,"
        if index < 4:
            fade_out = f"afade=t=out:st={duration - 0.4:.3f}:d=0.4,"
        elif index == 4:
            # Let the impact decay into the title rather than crossfading the image.
            fade_out = "afade=t=out:st=4.55:d=0.45,"
        else:
            fade_out = ""
        pad = "apad=pad_dur=0.864," if index == 5 else ""
        filters.append(
            f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"atrim=duration={min(duration, 5.184):.3f},asetpts=PTS-STARTPTS,"
            f"{pad}{fade_in}{fade_out}volume=0.62,adelay={start_ms}|{start_ms}[a{index}]"
        )

    filters.extend(
        (
            # A restrained low resonance carries the final impact beneath the title card. It keeps
            # the ending spacious without leaving several seconds of accidental digital silence.
            "aevalsrc='0.075*sin(2*PI*52*t)*exp(-0.55*t)+"
            "0.025*sin(2*PI*104*t)*exp(-0.9*t)':s=48000:d=5.864,"
            "aformat=channel_layouts=stereo,adelay=24136|24136[title_tone]",
            "[a0][a1][a2][a3][a4][a5][title_tone]"
            "amix=inputs=7:duration=longest:normalize=0[base]",
        )
    )

    filters.extend(dialogue_filters(len(VIDEOS)))
    filters.append(
        "[base][dialogue]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
        "apad=whole_dur=30,loudnorm=I=-16:LRA=9:TP=-1.5,"
        "asetpts=PTS-STARTPTS,atrim=duration=30[aout]"
    )
    return filters


def dialogue_filters(first_input: int) -> list[str]:
    """Build the dialogue submix from three inputs starting at `first_input`.

    Dialogue intentionally straddles cuts. Its continuation across the visual boundary creates an
    audio bridge, so the scene change reads as one dramatic thought rather than a pasted clip.
    """
    filters = [
        f"[{first_input + index}:a]aresample=48000,aformat=channel_layouts=stereo,"
        f"{normalize},{echo},adelay={start_ms}|{start_ms}[d{index}]"
        for index, ((normalize, echo), start_ms) in enumerate(
            zip(DIALOGUE_TREATMENTS, DIALOGUE_STARTS_MS)
        )
    ]
    # adelay leaves the mixed stream with a non-zero start timestamp, and atrim measures its
    # window against those timestamps. Rebase to zero before trimming, or the trim discards
    # every spoken line and leaves only the silent lead-in.
    filters.append(
        "[d0][d1][d2]amix=inputs=3:duration=longest:normalize=0,"
        "apad=whole_dur=30,asetpts=PTS-STARTPTS,atrim=duration=30[dialogue]"
    )
    return filters


def max_volume_db(path: Path, start_seconds: float, duration_seconds: float) -> float:
    completed = subprocess.run(
        (
            "ffmpeg", "-hide_banner", "-nostats",
            "-ss", f"{start_seconds:.3f}", "-t", f"{duration_seconds:.3f}",
            "-i", str(path), "-af", "volumedetect", "-f", "null", "-",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    for line in completed.stderr.splitlines():
        if "max_volume:" in line:
            return float(line.split("max_volume:")[1].split("dB")[0])
    # volumedetect prints nothing when the requested window holds no samples at all, which
    # is what a track truncated ahead of the window looks like from here.
    return float("-inf")


def verify_dialogue_reaches_the_mix() -> None:
    """Confirm every spoken line is audible in the submix that feeds the final mix.

    A delayed submix carries non-zero timestamps, so a trim measured against them can drop
    every line and still hand back a track of the full length. The finished container looks
    correct in that case and only listening reveals the loss, so check the lines themselves.
    """
    submix = OUTPUT.with_name(f"{OUTPUT.stem}.dialogue-submix.wav")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y",
        *input_args(DIALOGUE),
        "-filter_complex", ";".join(dialogue_filters(0)),
        "-map", "[dialogue]", str(submix),
    ]
    subprocess.run(command, check=True)
    try:
        for line, start_ms in zip(DIALOGUE, DIALOGUE_STARTS_MS):
            peak = max_volume_db(submix, start_ms / 1000, DIALOGUE_WINDOW_SECONDS)
            if peak < DIALOGUE_FLOOR_DB:
                raise SystemExit(
                    f"dialogue line {line.name} is inaudible at {start_ms / 1000:.1f}s "
                    f"({peak:.1f} dB peak); the submix lost it before the final mix"
                )
    finally:
        submix.unlink(missing_ok=True)


def probe(path: Path) -> dict:
    completed = subprocess.run(
        (
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels,duration",
            "-of",
            "json",
            str(path),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def main() -> None:
    verify_dialogue_reaches_the_mix()

    all_inputs = VIDEOS + DIALOGUE
    temporary = OUTPUT.with_name(f"{OUTPUT.stem}.dialogue-cut.mp4")
    filters = ";".join(video_filters() + audio_filters())
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        *input_args(all_inputs),
        "-filter_complex_threads",
        "1",
        "-filter_complex",
        filters,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "16",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    subprocess.run(command, check=True)

    metadata = probe(temporary)
    duration = float(metadata["format"]["duration"])
    if abs(duration - 30.0) > 0.05:
        raise SystemExit(f"unexpected trailer duration: {duration:.3f}s")
    streams = metadata["streams"]
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise SystemExit("assembled trailer has no video stream")
    if audio_stream is None:
        raise SystemExit("assembled trailer has no audio stream")
    for label, stream in (("video", video_stream), ("audio", audio_stream)):
        stream_duration = float(stream.get("duration", 0))
        if abs(stream_duration - 30.0) > 0.05:
            raise SystemExit(
                f"assembled trailer {label} stream has unexpected duration: "
                f"{stream_duration:.3f}s"
            )

    os.replace(temporary, OUTPUT)
    print(f"assembled {OUTPUT.relative_to(ROOT)} ({duration:.3f}s)")


if __name__ == "__main__":
    main()
