#!/usr/bin/env python3
"""Render the Great Havoc title card locally with FFmpeg only.

The card is typeset rather than generated: exact glyphs, a real gold gradient across
the title, and a composition that carries the weight of the final impact. Keeping it
local means the trailer's only text is deterministic and reproducible.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "great-havoc-in-heaven" / "generated" / "title-card.mp4"

WIDTH, HEIGHT = 1344, 768
FPS = 24
DURATION = 5.0

SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"
SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"

TITLE = "西游 · 大闹天宫"
SUBTITLE = "不是成佛，是归来"
# Songti has no glyph for U+3007, so the release line spells the zero out.
RELEASE = "二零二六"

# The block sits above geometric center so the empty lower frame reads as deliberate
# space rather than a layout that drifted upward.
TITLE_TOP = 272
TITLE_SIZE = 96
RULE_Y = 404
RULE_WIDTH = 480
SUBTITLE_TOP = 438
SUBTITLE_SIZE = 34
RELEASE_TOP = 636
RELEASE_SIZE = 24


def escape(text: str) -> str:
    return text.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


# The screenplay asks for a gold staff streak to cross the frame before the title
# resolves, so the card plays in three beats instead of fading everything in at once.
STREAK_START = 0.30
STREAK_OPEN = 0.75
STREAK_HOLD = 0.95
STREAK_SETTLED = 1.50
TITLE_IN = 0.85
SUBTITLE_IN = 1.60
RELEASE_IN = 2.35


def streak_width_at(when: float) -> int:
    """Expand a gold line from nothing to the full frame, then settle it to the rule."""
    if when < STREAK_START:
        return 0
    if when < STREAK_OPEN:
        return round(WIDTH * (when - STREAK_START) / (STREAK_OPEN - STREAK_START))
    if when < STREAK_HOLD:
        return WIDTH
    if when < STREAK_SETTLED:
        travelled = (when - STREAK_HOLD) / (STREAK_SETTLED - STREAK_HOLD)
        return round(WIDTH - (WIDTH - RULE_WIDTH) * travelled)
    return RULE_WIDTH


def streak_boxes() -> str:
    """Draw the travelling streak as one constant-width box per frame.

    drawbox resolves its geometry expressions once, while the frame timestamp is still
    unknown, so an animated width silently collapses to the expression's final branch.
    Its enable condition is evaluated per frame, so the sweep is drawn as a short series
    of fixed-width boxes instead.
    """
    boxes = []
    frame = 0
    while True:
        when = STREAK_START + frame / FPS
        if when >= STREAK_SETTLED:
            break
        box_width = streak_width_at(when)
        if box_width > 0:
            boxes.append(
                f"drawbox=x={(WIDTH - box_width) // 2}:y={RULE_Y}:w={box_width}:h=2:"
                f"color=0xFFE9A8@0.92:t=fill:"
                f"enable='between(t,{when:.4f},{when + 1 / FPS:.4f})'"
            )
        frame += 1
    boxes.append(
        f"drawbox=x={(WIDTH - RULE_WIDTH) // 2}:y={RULE_Y}:w={RULE_WIDTH}:h=1:"
        f"color=0x9A7A34@0.9:t=fill:enable='gte(t,{STREAK_SETTLED})'"
    )
    return ",".join(boxes)


def fade_in(start: float, duration: float) -> str:
    return f"'if(lt(t,{start}),0,min(1,(t-{start})/{duration}))'"


def filtergraph() -> str:
    title_bottom = TITLE_TOP + TITLE_SIZE
    return ";".join(
        (
            # A soft radial lift keeps the black from reading as an empty encode. The
            # gradients source rotates by default, so both gradients pin speed=0.
            f"gradients=s={WIDTH}x{HEIGHT}:r={FPS}:d={DURATION}:type=radial:speed=0:"
            f"c0=0x191B24:c1=0x030305:x0={WIDTH // 2}:y0={TITLE_TOP + 60}[bg]",
            # The title is drawn once as a luma mask, then used as the alpha of a real
            # vertical gold gradient. A flat fill with a bevel shadow reads as a default
            # text effect; a gradient across the glyphs reads as a struck title.
            f"color=c=black:s={WIDTH}x{HEIGHT}:r={FPS}:d={DURATION},"
            f"drawtext=fontfile='{SERIF}':text='{escape(TITLE)}':fontcolor=white:"
            f"fontsize={TITLE_SIZE}:x=(w-text_w)/2:y={TITLE_TOP},format=gray[mask]",
            f"gradients=s={WIDTH}x{HEIGHT}:r={FPS}:d={DURATION}:speed=0:"
            f"c0=0xFFF4D2:c1=0xA8721C:x0={WIDTH // 2}:y0={TITLE_TOP + 8}:"
            f"x1={WIDTH // 2}:y1={title_bottom}[gold]",
            f"[gold][mask]alphamerge,fade=t=in:st={TITLE_IN}:d=0.75:alpha=1[goldtitle]",
            # The streak is brighter and thicker while it travels, then thins into the rule.
            f"[bg]{streak_boxes()}[streaked]",
            "[streaked][goldtitle]overlay=0:0[titled]",
            f"[titled]drawtext=fontfile='{SERIF}':text='{escape(SUBTITLE)}':"
            f"fontcolor=0xEBD9AC:fontsize={SUBTITLE_SIZE}:x=(w-text_w)/2:y={SUBTITLE_TOP}:"
            f"alpha={fade_in(SUBTITLE_IN, 0.65)}[subtitled]",
            f"[subtitled]drawtext=fontfile='{SERIF}':text='{escape(RELEASE)}':"
            f"fontcolor=0x7E6A3E:fontsize={RELEASE_SIZE}:x=(w-text_w)/2:y={RELEASE_TOP}:"
            f"alpha={fade_in(RELEASE_IN, 0.7)}[dated]",
            # Faint grain breaks up the banding rings a smooth radial ramp shows in 8-bit
            # and matches the texture of the generated footage it follows. The card holds
            # full brightness at the end so the assembled film's clone padding freezes on
            # the title rather than on a fade to black.
            "[dated]noise=alls=4:allf=t+u,format=yuv420p,setsar=1[vout]",
        )
    )


def render(destination: Path, preview_at: float | None) -> None:
    if preview_at is not None:
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-filter_complex", filtergraph(),
            "-map", "[vout]", "-ss", f"{preview_at}", "-frames:v", "1", "-q:v", "2",
            str(destination),
        ]
        subprocess.run(command, check=True)
        print(f"preview {destination}")
        return

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-t", f"{DURATION}",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex", filtergraph(),
        "-map", "[vout]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{DURATION}", "-movflags", "+faststart",
        str(destination),
    ]
    subprocess.run(command, check=True)
    print(f"rendered {destination.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", help="write a single JPEG frame instead of the card")
    parser.add_argument("--at", type=float, default=3.0, help="preview timestamp")
    args = parser.parse_args()

    if args.preview:
        render(Path(args.preview), args.at)
    else:
        render(OUTPUT, None)


if __name__ == "__main__":
    main()
