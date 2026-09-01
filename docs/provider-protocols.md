# Production provider protocols

InkToFilm includes Codex CLI planning and judging plus fal MiniMax H3 video generation. Each role can
instead be supplied as an explicit command. Commands are never loaded from a screenplay or plan.

## Planner command

`--planner-command` receives one JSON object on stdin:

```json
{
  "schema_version": "1.0",
  "task": "screenplay_to_short_film_plan",
  "script": "...",
  "output_schema": {"type": "object"}
}
```

It writes one production-plan JSON object to stdout. `output_schema` is the complete authoritative
schema; InkToFilm validates IDs, shot durations, aspect ratio, assertions, and duplicate shots again.

## Video command

`--video-command` receives one shot request on stdin:

```json
{
  "schema_version": "1.0",
  "prompt": "...",
  "duration_seconds": 5,
  "aspect_ratio": "16:9",
  "destination": "/absolute/path/to/shot.mp4"
}
```

The command should write a non-empty video at `destination`. Alternatively it may print
`{"video":"/absolute/path/to/result.mp4"}` and InkToFilm will copy that local file into the production
bundle. URLs are intentionally not accepted by this adapter; downloading and authentication remain
inside the user's provider wrapper.

## Judge command

`--judge-command` uses the same request and response contract as `inktofilm run --semantic-command`.
It receives the prompt, assertions, normalized video metadata, and absolute sampled-frame paths.
It returns one score, rationale, and cited frame list per assertion. The full schema and security
properties are described in [semantic evaluators](semantic-evaluators.md).

## Security boundary

- Commands come only from CLI arguments supplied by the operator.
- Screenplays, prompts, plans, and suites cannot execute commands.
- Credentials stay inside the selected provider process or environment.
- InkToFilm records provider provenance and local output paths, never credential values.
