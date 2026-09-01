#!/usr/bin/env python3
"""Generate the public Mandarin dialogue used by the Great Havoc demo."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.request import urlretrieve

import fal_client

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "examples" / "great-havoc-in-heaven" / "generated"
MODEL = "fal-ai/bytedance/seed-speech/tts/v2"

DIALOGUE = (
    {
        "filename": "dialogue-heavenly-decree.mp3",
        "text": "孙悟空。天命，不可违。",
        "voice": "felix_zh",
        "speed": 0.88,
        "pitch": -2,
        "instruction": (
            "A cold, ancient, commanding male voice from the heavens. "
            "Slow, restrained, solemn cinematic Mandarin with deliberate pauses."
        ),
    },
    {
        "filename": "dialogue-wukong-defiance.mp3",
        "text": "天命？也配压俺老孙。",
        "voice": "monkey_king_zh",
        "speed": 0.90,
        "pitch": -1,
        "instruction": (
            "Low, rough and defiant Monkey King. Controlled anger rather than shouting. "
            "Pause after the question, then deliver the final words with contempt."
        ),
    },
    {
        "filename": "dialogue-wukong-climax.mp3",
        "text": "这天若不容俺……那便，打碎了它！",
        "voice": "monkey_king_zh",
        "speed": 0.88,
        "pitch": -1,
        "instruction": (
            "Cinematic Monkey King in Mandarin. Begin low and controlled, pause in the middle, "
            "then rise into fierce resolve on the final phrase without becoming cartoonish."
        ),
    },
)


def load_local_key() -> None:
    """Load FAL_KEY from the ignored project .env without printing it."""
    if os.environ.get("FAL_KEY"):
        return
    env_file = ROOT / ".env"
    if not env_file.exists():
        raise SystemExit("FAL_KEY is not available in the environment or project .env")
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "FAL_KEY":
            os.environ["FAL_KEY"] = value.strip().strip("\"'")
            return
    raise SystemExit("FAL_KEY is missing from project .env")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="regenerate existing dialogue")
    args = parser.parse_args()

    load_local_key()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for line in DIALOGUE:
        output = OUTPUT_DIR / line["filename"]
        if output.exists() and not args.force:
            print(f"kept {output.relative_to(ROOT)}")
            continue

        result = fal_client.subscribe(
            MODEL,
            arguments={
                "text": line["text"],
                "voice": line["voice"],
                "output_format": "mp3",
                "sample_rate": 48000,
                "speed": line["speed"],
                "volume": 1.0,
                "pitch": line["pitch"],
                "language": "zh",
                "voice_instruction": line["instruction"],
            },
        )
        urlretrieve(result["audio"]["url"], output)
        print(f"generated {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
