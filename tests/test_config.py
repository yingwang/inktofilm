import json

import pytest

from vidspec.config import ConfigurationError, load_suite


def test_load_suite(tmp_path):
    path = tmp_path / "vidspec.json"
    path.write_text(
        json.dumps({"name": "demo", "cases": [{"id": "one", "video": "one.mp4"}]}),
        encoding="utf-8",
    )
    suite = load_suite(path)
    assert suite.name == "demo"
    assert suite.cases[0].case_id == "one"
    assert suite.base_dir == tmp_path


def test_duplicate_case_ids_are_rejected(tmp_path):
    path = tmp_path / "vidspec.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "same", "video": "one.mp4"},
                    {"id": "same", "video": "two.mp4"},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="Duplicate"):
        load_suite(path)


def test_semantic_assertions_are_validated(tmp_path):
    path = tmp_path / "vidspec.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "semantic",
                        "video": "clip.mp4",
                        "semantic": {
                            "sample_frames": 5,
                            "assertions": [
                                {
                                    "id": "subject",
                                    "description": "The subject remains visible",
                                    "min_score": 0.85,
                                }
                            ],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    suite = load_suite(path)
    semantic = suite.cases[0].semantic
    assert semantic is not None
    assert semantic.sample_frames == 5
    assert semantic.assertions[0].min_score == 0.85


def test_invalid_semantic_threshold_is_rejected(tmp_path):
    path = tmp_path / "vidspec.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "semantic",
                        "video": "clip.mp4",
                        "semantic": {
                            "assertions": [
                                {"id": "subject", "description": "visible", "min_score": 1.2}
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="min_score"):
        load_suite(path)
