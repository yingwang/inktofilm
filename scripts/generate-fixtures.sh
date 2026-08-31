#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="$root_dir/examples/generated"
mkdir -p "$output_dir"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=1280x720:rate=24:duration=4" \
  -c:v libx264 -pix_fmt yuv420p \
  "$output_dir/good.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=640x360:rate=24:duration=1.5" \
  -f lavfi -i "color=c=black:size=640x360:rate=24:duration=1" \
  -f lavfi -i "color=c=blue:size=640x360:rate=24:duration=1.5" \
  -filter_complex "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]" \
  -map "[v]" -c:v libx264 -pix_fmt yuv420p \
  "$output_dir/bad.mp4"

echo "Generated real media fixtures in $output_dir"

