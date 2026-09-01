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
    GENERATED / "shot-03-breaks-formation.mp4",
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

    # Dialogue intentionally straddles cuts. Its continuation across the visual boundary creates an
    # audio bridge, so the scene change reads as one dramatic thought rather than a pasted clip.
    filters.extend(
        (
            "[6:a]aresample=48000,aformat=channel_layouts=stereo,"
            "loudnorm=I=-19:TP=-3:LRA=6,aecho=0.8:0.45:80|160:0.20|0.10,"
            f"adelay={DIALOGUE_STARTS_MS[0]}|{DIALOGUE_STARTS_MS[0]}[d0]",
            "[7:a]aresample=48000,aformat=channel_layouts=stereo,"
            "loudnorm=I=-18:TP=-3:LRA=6,aecho=0.8:0.55:48:0.12,"
            f"adelay={DIALOGUE_STARTS_MS[1]}|{DIALOGUE_STARTS_MS[1]}[d1]",
            "[8:a]aresample=48000,aformat=channel_layouts=stereo,"
            "loudnorm=I=-18:TP=-3:LRA=7,aecho=0.8:0.55:52:0.13,"
            f"adelay={DIALOGUE_STARTS_MS[2]}|{DIALOGUE_STARTS_MS[2]}[d2]",
            "[d0][d1][d2]amix=inputs=3:duration=longest:normalize=0,"
            "apad=whole_dur=30,atrim=duration=30,asetpts=PTS-STARTPTS[dialogue]",
            "[base][dialogue]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
            "apad=whole_dur=30,loudnorm=I=-16:LRA=9:TP=-1.5,atrim=duration=30,"
            "asetpts=PTS-STARTPTS[aout]",
        )
    )
    return filters


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
