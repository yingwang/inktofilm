# Production provider protocols

InkToFilm includes Codex CLI planning and judging plus fal MiniMax H3 video generation, and a Claude
Code agent plans and judges directly by supplying its own reviewed results. Each role can instead be
supplied as an explicit command. Commands are never loaded from a screenplay or plan.

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

When the shot has a still, the request carries that still instead of an aspect ratio, because the
still already fixes the frame:

```json
{
  "schema_version": "1.0",
  "prompt": "...",
  "duration_seconds": 5,
  "start_image": "/absolute/path/to/opening-frame.jpg",
  "end_image": "/absolute/path/to/closing-frame.jpg",
  "destination": "/absolute/path/to/shot.mp4"
}
```

`start_image` is the frame the shot opens on. `end_image` appears only where the plan chains this
shot into the next one, and is the frame the shot must land on, so the next clip begins on the image
this one ended with. A command that cannot condition on images should ignore both keys and generate
from `prompt` alone; InkToFilm only sends this shape to commands, and falls back to the plain request
for any generator without a `generate_from_image` method.

## Stills and faces

The default still provider is fal nano-banana, selected with `--image-model` and
`--image-edit-model`, and the default face-swap provider is fal, selected with `--face-swap-model`.
`--no-stills` skips both and shoots every shot from text alone.

`--face CHARACTER_ID=PATH` supplies a photographed face for one character. The file is uploaded to
the face-swap model and to nothing else. It is never written into a prompt, never sent to the
planner or the judge, and never copied into the production bundle, so a private photograph does not
travel with a shared film. InkToFilm rejects a `--face` naming a character the plan does not have.

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
