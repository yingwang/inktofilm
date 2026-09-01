#!/usr/bin/env python3
"""Regenerate the Great Havoc charge as a continuation of the prior shot."""

from __future__ import annotations

import argparse
from pathlib import Path

from generate_great_havoc_dialogue import load_local_key

from vidspec.providers import FalMiniMaxGenerator

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "examples" / "great-havoc-in-heaven" / "generated"
SOURCE_VIDEO = GENERATED / "shot-02-monkey-king-looks-up.mp4"
STABLE_FRAME = GENERATED / "shot-02-stable-frame.jpg"
OUTPUT = GENERATED / "shot-03-breaks-formation-i2v.mp4"

PROMPT = """
Begin exactly from the supplied frame without changing the Monkey King's face, fur, crown, dark-gold
armor, crimson cape, black-and-gold staff, body proportions, lighting, heavenly soldiers, jade
terrace, or camera axis. This is the next continuous shot, not a new scene. Within the very first
half second Sun Wukong has already stamped down, shattered the white-jade terrace, and launched
forward and upward into the heavenly formation; do not linger on the opening pose. The camera
accelerates alongside him in the same screen direction while flying spears, banners and bronze
chariots rush past with clear parallax. At the midpoint of the shot he swings the staff through one
wide, clearly readable arc that releases a bright golden shockwave: the expanding golden wave
visibly blasts the nearest ranks of armored soldiers, spears and banners outward and tears a clear
open path through the army, without any blood. In the final second he keeps flying forward through
the opened gap as golden light, debris and torn banners scatter around him. One continuous
five-second photorealistic live-action Chinese mythological action shot, physically coherent motion,
stable anatomy and weapon, 35mm anamorphic IMAX scale. No cut, no transformation, no duplicate
limbs, no second staff, no text, no subtitles, no logo, no watermark. No spoken dialogue; cinematic
battle ambience and impact sounds only.
""".strip()


def extract_frame() -> None:
    """Choose a stable frame 0.43 seconds before the generated clip ends."""
    import subprocess

    subprocess.run(
        (
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "4.75",
            "-i",
            str(SOURCE_VIDEO),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(STABLE_FRAME),
        ),
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="regenerate an existing continuation")
    args = parser.parse_args()

    if OUTPUT.exists() and not args.force:
        print(f"kept {OUTPUT.relative_to(ROOT)}")
        return
    if not SOURCE_VIDEO.is_file():
        raise SystemExit(f"missing source video: {SOURCE_VIDEO.relative_to(ROOT)}")

    load_local_key()
    extract_frame()
    FalMiniMaxGenerator().generate_from_image(PROMPT, 5, STABLE_FRAME, OUTPUT)
    print(f"generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
