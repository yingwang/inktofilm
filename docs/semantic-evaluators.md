# Semantic evaluators

InkToFilm keeps semantic expectations in the suite and evaluator choice on the command line. This
separation is intentional: opening an untrusted test suite must never execute a command or upload a
video.

## Declare assertions

```json
{
  "semantic": {
    "sample_frames": 6,
    "assertions": [
      {
        "id": "red-teapot",
        "description": "One red ceramic teapot remains visible and unchanged.",
        "min_score": 0.8,
        "severity": "fail"
      }
    ]
  }
}
```

`sample_frames` accepts 1–24 frames. `min_score` is 0–1 and `severity` is either `warn` or `fail`.

## Replay a reviewed result

Use this for checked-in public fixtures, human calibration, or a result produced by an evaluator in
another environment:

```bash
inktofilm run suite.json \
  --semantic-results semantic-results.json \
  --output reports/semantic
```

InkToFilm resamples the video, binds the cited frame indexes to their timestamps, and writes the
evidence thumbnails beside the HTML report.

## Run any VLM or research evaluator

Choose an executable explicitly:

```bash
inktofilm run suite.json \
  --semantic-command "my-video-judge --model research-v3" \
  --semantic-timeout 300 \
  --output reports/semantic
```

The command receives one JSON object on stdin and must return one JSON object on stdout. The request
contains the prompt, assertions, normalized video metadata, and absolute paths to sampled JPEG
frames. It also contains a `response_schema` example. A response has this shape:

```json
{
  "evaluator": "research-v3@a1b2c3",
  "provenance": {
    "model": "research-v3",
    "revision": "a1b2c3",
    "judge_prompt_hash": "sha256:…",
    "sampling_policy": "six InkToFilm frames"
  },
  "assertions": [
    {
      "id": "red-teapot",
      "score": 0.91,
      "summary": "The requested object persists",
      "rationale": "Color and shape remain stable under the orbit.",
      "evidence": [
        {"frame_index": 1, "description": "Red teapot in the opening view"},
        {"frame_index": 6, "description": "Same teapot after the orbit"}
      ]
    }
  ]
}
```

InkToFilm owns thresholding, missing-assertion errors, evidence paths, report rendering, and regression
status. The evaluator owns perception and must disclose its name and revision.

## Privacy and trust boundary

- No semantic provider runs by default.
- A suite cannot choose or execute an evaluator.
- `--semantic-command` is an explicit trust decision: the command can read the sampled frames and
  prompt, and a remote-backed command may upload them.
- Keep tokens in the evaluator process environment. Never place API keys, cookies, account names,
  or private URLs in a suite, result file, report, or repository.
- Review public fixtures before committing them. InkToFilm records evaluator provenance but cannot
  prove that a third-party result is truthful.
