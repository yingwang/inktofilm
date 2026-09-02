---
name: inktofilm
description: Turn a story idea, prompt, or screenplay into a finished AI short film by planning shots, generating video, checking story fidelity, selectively retrying failures, and editing the result. Use when the user asks to make an AI movie, trailer, short film, episode, or screenplay-to-video project. Do not use for analysis-only requests about an existing video.
---

# InkToFilm

Treat one natural-language prompt as a complete starting point. The user does not need to write code,
run commands, understand models, or prepare a screenplay.

## User experience

- Begin from the user's idea. When important creative direction is missing, make a strong default or
  offer one concise concept for approval; ask only questions that would materially change the film.
- Do the setup, planning, generation, evaluation, retries, and editing on the user's behalf. Do not
  surface internal commands, provider payloads, or implementation details unless the user asks.
- Default to a complete 30-second, 16:9 cinematic short or trailer when duration and format are
  unspecified. For a feature film or series, first create an approved short proof of concept, then
  continue in chapters or episodes with a shared character and world bible.

## Private setup and paid generation

Use an existing InkToFilm checkout when available. Otherwise prepare a project-local checkout from
https://github.com/yingwang/inktofilm and a project-local environment; do not modify unrelated system
configuration. Verify FFmpeg, FFprobe, and the fal client before production; `inktofilm doctor`
reports what is missing.

1. Look for `FAL_KEY` in the process environment, then in a project-local `.env`. The CLI reads only
   the environment, so load the file into the shell that runs it, for example with
   `set -a; . ./.env; set +a`, and never print the value.
2. If it is absent, ask the user once for their fal API key. When a signed-in browser is available,
   offer to create and copy an API-scoped key with explicit approval instead of making the user expose
   it in chat.
3. Never echo, log, summarize, place in a prompt, or commit the key. Store it only in an ignored local
   `.env` with mode `0600`, and verify Git ignores the file before any commit or push.
4. Read current provider pricing, estimate the number of generated seconds and retry allowance, state
   a hard spending cap, and obtain confirmation immediately before the first paid request. Stop before
   exceeding the approved cap. fal bills MiniMax H3 Max per generated second and nano-banana per
   still, so a five-shot 30-second film with stills and a few retries usually costs a few dollars;
   check the model pages for the current rates rather than assuming.

## Make the film

Do the creative and judging work with the agent that is running this skill, and use fal MiniMax H3
Max as the default video generator, while respecting any model the user explicitly chooses.

- In Claude Code, you are the planner and the judge. Write the screenplay, the plan, and the test
  suite yourself, and work through the stages below so that every image is looked at before a video
  credit is spent on it. To judge a shot, sample the same evenly spaced frames the evaluator uses
  with `inktofilm frames`, inspect them directly, write the reviewed per-case results JSON, and
  replay it with `inktofilm run suite.json --semantic-results`. Score only what is visible in the
  sampled frames, and record your own model name in the result provenance.
- In Codex, the CLI's built-in integration does the same work through the authenticated Codex CLI:
  `inktofilm run --semantic-codex` for judging, and the default planner and judge of
  `inktofilm produce`.
- When the user wants the run to finish unattended, hand judging to a CLI instead of doing it in the
  loop: `inktofilm run --semantic-claude`, or `inktofilm produce --judge-claude`, which needs nothing
  but Claude Code and a fal key. Prefer judging in the loop when you are already present, since it
  costs one model rather than two and you can notice what no assertion happened to ask about.
- Any other model can be wired in through the JSON stdin/stdout hooks: `--semantic-command`,
  `--planner-command`, `--judge-command`, and `--video-command`.
- Whichever judge runs, it only scores the assertions the plan wrote. Write assertions for the
  failures that actually recur, including invented on-screen text, letterboxing baked into a frame,
  a costume drifting toward the wrong culture, and an expression that contradicts the scene.

### The staged workflow

`inktofilm produce` is resumable: portraits, stills, and shot attempts that already exist in the
output directory are reused, so the same command can be run again after a review and only the
missing work is paid for.

1. Write `script.md` and `plan.json` yourself, then
   `inktofilm produce script.md --plan plan.json --stills-only -o <project>`. This renders one
   portrait per character and one still per shot and stops. Open every image. A portrait that is not
   the character, a still with the wrong framing, a face the wrong age, an extra person, or text on a
   prop is cheap to fix here and expensive to fix in a clip: delete the file, sharpen its prompt, and
   run the same command again.
2. Shoot with `--no-judge` when you will judge in the loop, or with `--judge-claude` when the run is
   unattended. `--no-judge` runs the media checks, selects the newest attempt of each shot, writes
   `suite.json` for the selected clips, and assembles a plain-cut `final.mp4`.
3. For each shot, `inktofilm frames shots/<shot>-attempt-1.mp4` samples the frames a judge would see.
   Look at them, write the reviewed results file, and replay it with
   `inktofilm run suite.json --semantic-results reviewed.json -o review`.
4. Regenerate only what failed: `--reshoot <shot_id>` gives that shot a fresh attempt, numbered after
   the ones on disk, and everything else is reused. Edit the prompt first when the failure was the
   prompt's fault. Judge the new take against the old one rather than assuming it is better; when
   the earlier take wins, `--select <shot_id>=<attempt>` makes it the shot's clip again, so the
   manifest, `suite.json`, and `final.mp4` all follow the reviewer's choice.
5. Assemble the final edit yourself with FFmpeg when the film needs more than a plain cut: overlaps,
   sound bridges, dialogue, and a locally typeset title card.

### Prompt rules

The full notes, with the failure each rule prevents, are in
[docs/field-notes.md](../../docs/field-notes.md); read them before writing any still or video
prompt, and the faces section before putting a photographed face into a film. The rules in
one breath:

- Write video prompts as a cinematographer: medium and physics first ("photorealistic
  live-action, not animation", lens, light, air, "physically believable cloth, hair and
  weight"), then blocking; name what must stay stable once, not five times.
- Give every action a clock ("within the first half second", "at the midpoint"); say
  "real-time speed" in the style and build tempo inside fight prompts; never put "slow
  motion" in `visual_style`. Check tempo with `inktofilm motion`.
- Text-to-video for wide, landscape, action and scale shots; image-to-video only where a
  face or exact composition must match a still, and front-load the action there.
- Describe a still as a photograph, list only the shot's characters, say "no text" on
  anything that could carry it, pin the weather and season, and end with "fills the entire
  frame edge to edge, no black bars, no letterbox".
- Quote spoken lines exactly, name the speaker, ask for natural lip movement and no
  subtitles, give dialogue a second more than its words need, and transcribe the native
  audio (whisper.cpp) rather than trusting the frames; a transcript of silence is not speech.
- A real face only where it is large in frame; ask for photos taken by someone else at a
  normal distance (a selfie distorts), describe glasses in the portrait prompt, describe a
  famous costume without its name, and reuse a character's supplied photographs in every
  later film.
- Assemble at CRF 16 or lower with `-preset slow`, keep the provider's frame size, pin
  `settb` around `concat` when mixing dissolves, and verify the mixed elements, not only
  the container.

- Expand a short idea into a screenplay, character and world bible, and a sequence of independently
  generatable shots. Preserve the user's named characters, dialogue, visual rules, and ending.
- Turn each shot into a self-contained prompt with continuity anchors and explicit observable
  requirements. Keep title cards and other exact text for local post-production.
- Settle the look as stills before spending video credits. Render one clean reference portrait per
  recurring character, edit every shot's opening still from those portraits, and generate the shot
  from its own still. Framing, costume, and light are cheap to correct in an image and expensive to
  correct in a clip, and a still that is reused as a neighbour's end frame makes a re-shoot local.
- Choose continuity method shot by shot. When action directly continues, hand the next shot's still
  to the generator as this shot's mandated last frame (`chain_to_next`), so the two clips meet on one
  image; or open the next shot on a frame cut from the previous take (`continue_from_previous`:
  `true` for 0.4 seconds before the end, a number for that many seconds before the end), which is
  what keeps two people, their costumes, the light and the place identical across a sequence that
  has no stills of its own. Use a clean character reference when only identity must persist, and
  keep text-to-video freedom for a new location, scale, time, or composition. A user who has seen
  a chained film will notice when the next one is "all separate pieces"; when they ask for the
  shots to connect, continue every shot inside a scene and cut only between scenes.
- A continued shot inherits the previous take's faces, so a photographed likeness has to be put on
  the handoff frame, not only on stills: list the characters in `face_reference` on the continued
  shot as well, and design the previous shot to end on a framing where those faces are large
  enough to swap (a tight two-shot, not the wide the fight was staged in). When two people share
  the frame, list them in `face_reference` in left-to-right order: the two-face model takes both in
  one request, and a single-face model is applied strip by strip so it cannot replace the wrong
  person. Stage two-shots with one person on each side of the frame for the same reason.
- `produce` writes the parsed plan back into the bundle as `plan.json`. Keep the plan you author
  outside the output directory, or diff the written copy after every run before editing it again:
  a field the writer serialises differently from the way the parser reads it changes the film
  silently on the next run, and the take that came out wrong is the only evidence.
- Generate the planned shots. For every shot, run media checks and evidence-backed semantic checks
  derived from the screenplay, including required characters, setting, action, camera intent, text,
  and visible defects.
- Retry only shots that fail meaningful story or quality requirements. Prefer a targeted rewrite or
  edit over regenerating clips that already pass. Never spend beyond the confirmed cap.
- Assemble the selected clips, dialogue or native audio, transitions, and local title cards into one
  playable film. Avoid presenting independent generations as hard-cut fragments: use motivated
  eyeline and action matches, restrained dissolves or light/occlusion transitions, and dialogue,
  ambience, or effects that cross the cut. Preserve intentional hard cuts when they provide dramatic
  punctuation. Normalize resolution, frame rate, codecs, audio format, and duration.
- Verify the finished container rather than assuming a successful encode is complete. Confirm the
  audio and video streams both span the intended duration, decode the full file, and scan the final
  mix for unintended long silence; distinguish deliberate quiet from a truncated audio stream.
- Verify the elements you mixed in, not only the container around them. A delayed submix that is
  then trimmed against its own timestamps can arrive at full length and completely silent, which
  every duration and stream check still passes. Confirm each spoken line is audible at the moment it
  belongs, and treat any element that survives only as a filename as missing from the film.

For the current H3 workflow, use InkToFilm's provider and production APIs rather than recreating fal
requests ad hoc. Keep generated prompts, reports, and media inside the user's chosen project. Treat
private screenplays and reference media as private unless the user explicitly authorizes publication:
a production directory inside the checkout is ignored by Git, and a private story must stay out of
commits, public example folders, and published reports.

## Deliver

Return the finished video first, followed by a visual contact sheet or poster and a brief plain-language
note covering duration, quality result, any honest limitation, and actual provider spend when known.
Do not make the user read a technical report to understand whether the film succeeded.
