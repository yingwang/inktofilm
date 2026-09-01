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

### Writing prompts that survive generation

- The cast bible in each video prompt covers only the characters the shot lists, so list them. A
  single-character shot that describes the whole cast tends to seat the others in the background.
- Reference portraits are handed to the still editor in the order of the shot's `characters`. Refer
  to them by that order in the still prompt, for example "the woman from the first reference image",
  and restate her hair, skin, and costume anyway; the reference fixes identity, the words fix the
  frame.
- Describe a still as a photograph: framing, where each person is, what they are doing at the instant
  the shot opens, the light, the lens. Say "no text" on anything that could carry it, such as a
  paddle, a sign, or a screen, and end every still prompt with "fills the entire frame edge to edge,
  no black bars, no letterbox": wide establishing frames otherwise come back with cinema bars baked
  into the image, which the video then inherits.
- Portraits drift older and tidier than written. Give an age twice ("25, reads as twenty-five and not
  older"), describe the hair by length and behaviour ("five centimetres on top, swept to one side,
  not slicked back, not a buzz cut"), and name the light and palette the rest of the film uses, or a
  lone shot comes back in a different colour temperature from its neighbours.
- When a still is rejected, move it into a `rejected/` folder beside the others instead of deleting
  it. The re-run only renders what is missing, and the earlier take stays available if the new one
  loses a composition that was right.
- Open a video prompt with "Begin exactly on the supplied frame" when the shot has a still, and say
  who keeps the same face, hair, and clothing. Name the number of props that must not multiply.
- MiniMax H3 Max generates native sound and lip-synced speech. For a spoken line, quote the exact
  words in the prompt, name the speaker, and ask for natural lip movement and no subtitles; put the
  same words in the plan's `dialogue` field so the judge can check them. Accepted durations are 5 to
  15 seconds per shot at 480P or 768P; two lines of dialogue need six seconds rather than five.
  Frames cannot confirm what was said, so transcribe the native audio (a local whisper.cpp is
  enough) and compare it with the script; the model also improvises murmured lines in crowd
  scenes, so read the whole transcript, not only the lines you wrote.
- Light "catching" or "reflected in" a character's eyes is rendered literally as glowing irises.
  Say the eyes stay their natural colour and forbid coloured light in them.
- Two hand-held props tend to merge into one hand within a few frames, whatever the still shows.
  When a prop matters, give it a place that is not a hand (mouth, pocket, table) or plan for it to
  be optional, and judge the take on staging rather than on which hand holds what.
- End a shot with an eyeline toward the next shot's subject (a glance toward the front row before
  the cut to her turning) so the join reads as cause and effect rather than as two generations.
- In the FFmpeg assembly, `concat` emits a microsecond timebase that a following `xfade` rejects;
  pin every video chain to `settb=1/<fps>` before and after concat when mixing dissolves and hard
  cuts. Trim each clip to its planned length so the title card keeps its full run, and read the
  clip durations from the files rather than assuming them.
- Write the video prompt as a cinematographer, not as a stage manager. Open with the medium and the
  physics before any blocking: "photorealistic live-action <genre> film, not animation, not a game
  cutscene", the lens, where the light comes from, what the air is doing (mist, frost dust, rain),
  and "physically believable cloth, hair and weight". A prompt that is mostly blocking and
  prohibitions ("stays seated", "nobody moves from their place", "same face as the first frame")
  returns a photograph that twitches: the model animates what it is told to animate and freezes the
  rest, and the stillness reads as fake. Name what must stay stable in one clause (one sword, both
  faces), not in five.
- Give every action a clock: "within the first half second", "at the midpoint", "in the final
  second". Untimed action either never arrives or is spent on a wind-up, and a shot with no timed
  beat comes back as a slow push-in on people holding a pose.
- Choose text-to-video for wide, landscape, action and scale shots. The model owns the motion and the
  clip reads as filmed. Reserve image-to-video for shots whose face or exact composition must match a
  still, and front-load the action there too. A polished still is a liability for motion: the tidier
  the photograph, the more the clip looks like a photograph waking up. When the user prefers
  convincing motion over an identical face, say so in the plan: leave `still_prompt` and
  `reference_prompt` empty and carry identity in each character's `description`, which the production
  prompt restates verbatim on every shot that lists the character.
- Judge the encode by the source, not by the file size. Compare a raw provider clip's bitrate with the
  assembled film's: a much lower final number under the same encoder settings means the clips were
  static, not that the encode was lossy. Assemble at CRF 16 or lower with `-preset slow`, keep the
  provider's frame size (no rescale of a 768P clip in either direction), and say so in the delivery
  note when the user asks whether quality was lost in post.
- Before trimming a dialogue shot to its planned length, read the word timestamps from the transcript
  (`whisper-cli -ml 1`) and keep the clip long enough that the last word ends before the outgoing
  audio fade begins; a line that survives the clip can still lose its final syllable to a dissolve.
  Re-transcribe the dialogue window of the assembled film, not only the raw clip.
- A transcript of a clip with no speech is not proof of speech. whisper invents short lines and
  subtitle credits over steady ambience; before reshooting for an "improvised" line, confirm it with
  timestamps and a loudness envelope (speech shows as peaks over the ambience floor).
- A still edited from a reference portrait inherits the portrait's face but invents the weather. Pin
  the sky, precipitation and season in every still prompt ("clear night, frost on the tiles, no snow")
  or a single face-matched close-up arrives in a snowfall the rest of the film does not have.

- Expand a short idea into a screenplay, character and world bible, and a sequence of independently
  generatable shots. Preserve the user's named characters, dialogue, visual rules, and ending.
- Turn each shot into a self-contained prompt with continuity anchors and explicit observable
  requirements. Keep title cards and other exact text for local post-production.
- Settle the look as stills before spending video credits. Render one clean reference portrait per
  recurring character, edit every shot's opening still from those portraits, and generate the shot
  from its own still. Framing, costume, and light are cheap to correct in an image and expensive to
  correct in a clip, and a still that is reused as a neighbour's end frame makes a re-shoot local.
- Choose continuity method shot by shot. When action directly continues, hand the next shot's still
  to the generator as this shot's mandated last frame, so the two clips meet on one image; failing
  that, seed the next shot from a stable frame near the end of the previous clip rather than blindly
  using the literal final frame. Use a clean character reference when only identity must persist, and
  keep text-to-video freedom for a new location, scale, time, or composition. Do not chain every shot
  through its predecessor.
- Put a user's own photographed face into a film only where it can survive. Swap it on close and
  tight-medium shots, and leave wide shots to the generated face: below roughly a tight medium the
  face covers too few pixels, and the attempt reads as deformed rather than as a likeness. Ask for
  the photo once, pass it by path, and never place it or its description into a model prompt. If a
  swapped face looks uncanny rather than merely wrong, suspect the proportions of the base face
  rather than the swap: a base face narrower than the supplied one stretches the features to fill it.
  Fix it by constraining the base still's face shape and feature spacing, then swap again.
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
