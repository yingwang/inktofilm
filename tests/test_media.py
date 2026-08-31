import json
import subprocess

from vidspec import media


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def test_probe_normalizes_ffprobe(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1280,
                "height": 720,
                "avg_frame_rate": "30000/1001",
                "duration": "5.5",
                "pix_fmt": "yuv420p",
                "nb_frames": "165",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "5.5"},
    }
    monkeypatch.setattr(media, "require_tool", lambda name: name)
    probe = media.probe_video(video, lambda *args, **kwargs: completed(json.dumps(payload)))
    assert probe.width == 1280
    assert round(probe.fps, 3) == 29.97
    assert probe.has_audio is True
    assert probe.frame_count == 165


def test_temporal_detector_parsing(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(media, "require_tool", lambda name: name)
    black_output = "[blackdetect] black_start:1.2 black_end:1.8 black_duration:0.6"
    black = media.detect_black_frames(
        video, runner=lambda *args, **kwargs: completed(stderr=black_output)
    )
    assert [(event.start_seconds, event.end_seconds) for event in black] == [(1.2, 1.8)]

    freeze_output = "freeze_start: 2.0\nfreeze_duration: 1.0\nfreeze_end: 3.0"
    frozen = media.detect_freezes(
        video, runner=lambda *args, **kwargs: completed(stderr=freeze_output)
    )
    assert [(event.start_seconds, event.end_seconds) for event in frozen] == [(2.0, 3.0)]

