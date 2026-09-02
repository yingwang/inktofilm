# Production provider protocols

InkToFilm includes Codex CLI and Claude Code CLI planning and judging plus fal MiniMax H3 video
generation, and a Claude Code agent can also judge directly by supplying its own reviewed results.
Each role can instead be supplied as an explicit command. Commands are never loaded from a
screenplay or plan.

## Built-in judges

`--semantic-codex` on `run`, and the default judge in `produce`, sends the sampled frames to
`codex exec` with `--sandbox read-only` and a structured-output schema.

`--semantic-claude` on `run`, and `--judge-claude` on `produce`, does the same through `claude
--print --json-schema`. Claude Code has no flag for attaching an image, so the frames are named by
absolute path in the prompt and read with the Read tool, and their directories are opened with
`--add-dir`. The session runs `--restricted`, which removes the command-running tools and WebFetch,
confines the file tools to those directories, and ignores user, project, and local settings, so
nothing in the operator's own configuration can color a verdict. `--strict-mcp-config` keeps MCP
servers out of it, and `--allowedTools Read` leaves reading as the only capability. InkToFilm reads
the run's `structured_output`, falls back to parsing `result`, and treats a reported error or any
permission denial as a failed evaluation rather than a silent pass.

Both judges use the CLI's own authentication. InkToFilm never handles those credentials.

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

Two face-swap request shapes are supported. `fal-ai/face-swap` (the default) receives
`swap_image_url` and `base_image_url` and swaps one face. `easel-ai/advanced-face-swap` receives
`face_image_0`/`gender_0`, optionally `face_image_1`/`gender_1`, `target_image`, `workflow_type`
(`target_hair`, so the costume hairstyle stays), `upscale` and `detailer`; it is selected with
`--face-swap-model` and takes each face's gender from `--face-gender CHARACTER_ID=GENDER`
(`female`, `male`, or `non-binary`; an undeclared face is sent as `non-binary`). A shot whose
`face_reference` lists two characters needs the easel model, because a single-face model cannot be
told which person in the frame to replace.

Continuation frames (`continue_from_previous`) are cut locally with FFmpeg from the previous shot's
selected clip and are passed to the video model exactly as a still would be, through `image_url`.

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
