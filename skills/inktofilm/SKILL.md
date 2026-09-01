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

1. Look for `FAL_KEY` in the process environment, then in a project-local `.env`.
2. If it is absent, ask the user once for their fal API key. When a signed-in browser is available,
   offer to create and copy an API-scoped key with explicit approval instead of making the user expose
   it in chat.
3. Never echo, log, summarize, place in a prompt, or commit the key. Store it only in an ignored local
   `.env` with mode `0600`, and verify Git ignores the file before any commit or push.
4. Read current provider pricing, estimate the number of generated seconds and retry allowance, state
   a hard spending cap, and obtain confirmation immediately before the first paid request. Stop before
   exceeding the approved cap.

## Make the film

Do the creative and judging work with the agent that is running this skill, and use fal MiniMax H3
Max as the default video generator, while respecting any model the user explicitly chooses.

- In Claude Code, you are the planner and the judge. Write the screenplay, shot plan, and test suite
  yourself. To judge a shot, sample the same evenly spaced frames the evaluator uses, inspect them
  directly, write the reviewed per-case results JSON, and run the suite with `--semantic-results`.
  Score only what is visible in the sampled frames, and record your own model name in the result
  provenance.
- In Codex, the CLI's built-in integration does the same work through the authenticated Codex CLI:
  `inktofilm run --semantic-codex` for judging, and the default planner and judge of
  `inktofilm produce`.
- Any other model can be wired in through the JSON stdin/stdout hooks: `--semantic-command`,
  `--planner-command`, `--judge-command`, and `--video-command`.

- Expand a short idea into a screenplay, character and world bible, and a sequence of independently
  generatable shots. Preserve the user's named characters, dialogue, visual rules, and ending.
- Turn each shot into a self-contained prompt with continuity anchors and explicit observable
  requirements. Keep title cards and other exact text for local post-production.
- Choose continuity method shot by shot. When action directly continues, seed the next shot from a
  stable frame near the end of the previous clip rather than blindly using the literal final frame.
  Use a clean character reference when only identity must persist, and keep text-to-video freedom for
  a new location, scale, time, or composition. Do not chain every shot through its predecessor.
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

For the current H3 workflow, use InkToFilm's provider and production APIs rather than recreating fal
requests ad hoc. Keep generated prompts, reports, and media inside the user's chosen project. Treat
private screenplays and reference media as private unless the user explicitly authorizes publication.

## Deliver

Return the finished video first, followed by a visual contact sheet or poster and a brief plain-language
note covering duration, quality result, any honest limitation, and actual provider spend when known.
Do not make the user read a technical report to understand whether the film succeeded.
