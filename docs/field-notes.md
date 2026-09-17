# InkToFilm field notes

What generation actually does with a prompt, collected from productions. The
[skill](../skills/inktofilm/SKILL.md) tells an agent to read this file before writing any
still or video prompt and before putting a real face into a film; the rules below are the
reason each of its short rules exists.

## Writing prompts that survive generation

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
- Untimed action either never arrives or is spent on a wind-up, and a shot with no beat at all
  comes back as a slow push-in on people holding a pose. The fix is a chain of forceful verbs, not
  a stopwatch: "a boot lashes out and kicks the pendant skidding away out of frame; a hand shoves
  her shoulder hard, the blow turns her, her feet scuff for purchase, her sleeve and hem whip with
  it, and she comes back square exactly where she stood". Naming the clock ("0.6 s", "three or four
  centimetres") does raise the measured energy, but it also spends the model's attention on hitting
  marks, and what comes back is stiffer and less natural. Reserve explicit timings for a fight,
  where the rhythm is the point; everywhere else let the verbs carry it. Measured on the same shot,
  verb chains with no numbers moved the frame-to-frame energy from a peak of 2.4 to peaks of 9 and
  10, which is the whole usable range.
- Never write "slow motion" or "elegant, unhurried" into `visual_style` for a film with a fight in
  it: the style is restated on every shot, so every exchange arrives floating and the fight has no
  rhythm. Say "real-time speed" in the style, and build tempo inside the fight prompts: count the
  exchanges ("three cuts and three parries in the first two seconds"), name the stop ("blades lock,
  one held beat"), then the release ("she breaks the lock and the next flurry is faster"), and let a
  speed ramp exist only at one impact. Contrast is what reads as rhythm; uniform grace reads as slow.
  Check the result without watching it: `inktofilm motion take.mp4` prints the mean frame-to-frame
  change per half second. A fight with a beat shows two bursts around a lull (values near 10 falling
  to 2 and rising again); a floating one is a flat line, and a talking head sits near 1.
- When a shot continues from a dialogue take, the handoff frame is cut 0.4 s before the end, and a
  line that is still being spoken there loses its last syllable at the join. Read the word
  timestamps before choosing the offset: either give the dialogue shot a second more than its lines
  need so the last word ends before the handoff, or set `continue_from_previous` to a smaller
  number, or, in the edit, let the outgoing picture run a few frames past the handoff (four repeated
  frames are invisible; a clipped word is not). An audio-only L-cut is the other repair, and only
  works when the incoming take does not start speaking at once.
- A downward exit reads as a fall. A figure who "steps off the eave and drops into the mist" is
  seen by a viewer as someone jumping off a building, however light the prompt makes it. End a
  rooftop scene on the roof (a toast, a sheathed sword, a look), or take the descent in a shot of
  its own with a visible landing that carries weight.
- Dialogue that survives a viewer is drama dialogue, not aphorism. Two symmetrical epigrams
  ("the frost is cold, the wine is not") sound written; a plain exchange with a turn in it sounds
  spoken. When the user names a scene they love, borrow that scene's logic of exchange (a rule
  stated, a loophole claimed, a curt order, a cheeky refusal) and put it in your own characters'
  mouths in their own register, then keep each line short enough to be said in the seconds you gave
  it.
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

## The script is the edit

- Two scripts for the same film, a day apart, and the user could say which was "obviously
  better", faster, fuller of detail, with the sound doing work. The video model was the same. The
  first script was meticulous and slow: one man, one television, three identical rounds, every
  thumb press timed. The second kept the measuring and decided different things before anything
  was generated: what the world outside is doing in every second, what sound crosses each cut,
  where the beats fall, which gate the money waits behind. Write that document first;
  [docs/script-writing.md](script-writing.md) is its shape. Precision is necessary and not
  sufficient; what is scheduled matters more than how finely.
- Measure the world instead of describing it. "A lived-in kitchen" gets a showroom; "a mug, a
  dripper, a wet brown filter, a gooseneck kettle, a tea towel folded twice, a cork mat, last
  night's saucer and teaspoon in the sink, an eight-year-old fifty-five-inch television with a
  two-centimetre bezel and a scuff on the lower right" gets a kitchen someone lives in. The same
  goes for light (kelvin and white balance, and why), posture (which fingers hold the handle),
  and air (how far the steam rises).
- Fill every tenth of a second. The timeline in the script is what the prompt is built from, and a
  stretch with nothing written is where the model puts a slow push-in and a blink. "From 5.0 to
  10.0 nothing moves but breathing" is an instruction; silence in the timeline is not.
- The music has to hit the picture's peak, and the user hears whether it does. The film she
  preferred had, in her words, music "on the beat: the loudest moment and the climax matched", and
  she asked for that to be kept. Measured, its 40-second bed (prompted to "build to a massive
  climax at the very end") peaked at 32 s and decayed from 33 s; started at the first channel
  change and cut at the mute, the loudest bar sat 2.9 s before the cut to silence, close enough
  to land as a hit. Make it exact rather than lucky next time: name the climax second in the
  script, measure the bed (`inktofilm music-peak bed.mp3 --climax 49.6` would have said "start
  the bed at 17.6 s"), and slide or trim it before ducking and loudness; when the two are a few
  frames apart, move the cut, not the music.
- Keep the gates out of the assembly. Which still, which five-second test and which batch must be
  approved, and what fails each, belong in the script or an `ACCEPTANCE.md` next to it, with the
  budget and the rule that a request id is saved before a result is trusted. When those decisions
  are made in the cutting room they are made too late and under pressure to ship.

## Faces and likenesses

- A hosted face-swap model can sit in its queue for ten minutes and more while every other model
  answers in seconds. Probe it with a submit-and-poll before a production run, keep the basic
  single-face model as the fallback, and never let a swap that has not returned block the shots
  that do not need it.
- A likeness has two routes and they differ by face. Editing the costume portrait directly from the
  photographs (nano-banana/edit with the photos as references) keeps a soft, fine-featured face
  well and can beat a swap for it; a swap is what restores a face the edit has idealised away.
  Look at both before choosing, per character, and keep the rejected one in `rejected/`.
- Put a user's own photographed face into a film only where it can survive. Swap it on close and
  tight-medium shots, and leave wide shots to the generated face: below roughly a tight medium the
  face covers too few pixels, and the attempt reads as deformed rather than as a likeness. Ask for
  the photo once, pass it by path, and never place it or its description into a model prompt. If a
  swapped face looks uncanny rather than merely wrong, suspect the proportions of the base face
  rather than the swap: a base face narrower than the supplied one stretches the features to fill it.
  Fix it by constraining the base still's face shape and feature spacing, then swap again.
- For a costume that belongs to a famous character, describe the look ("a fitted red-and-blue
  spider-themed superhero suit with a black web pattern and a small spider emblem") and never the
  name: the image and video models then render it without balking, and the film stays a private
  homage. A mask hides the face the user asked for, so plan the close shots mask-off.
- A selfie is a distorted reference. A phone held below the chin at arm's length widens the face,
  flattens the hair and enlarges the glasses, and every portrait, still and swap built on it will be
  "not quite him" to anyone who knows him. Before building a likeness, ask for one or two photos
  taken by someone else at a normal distance; when the user says the face is not right, ask for
  those photos first and rewrite the character bible (face shape, hair, glasses) from them before
  touching the pipeline. Editing the costume portrait directly from two good photos, then swapping
  the same face onto it, gave the likeness the user accepted.
- Glasses survive a face swap when the generated portrait already wears them: describe them in
  the character bible and the portrait prompt, and the swap keeps the frames over the new face.
- A face written from a description is nobody's face. When the user has supplied photographs for a
  character in an earlier film, "her face" means those photographs, in every later film with that
  character, and a portrait generated from words alone will be recognised at once as not hers. Keep
  the photographs where the next production can find them and reuse them without being asked.

## Identity stills: one image model with the photographs as references

Two attempts at the same character on the same day, and the difference was the whole
verdict. The first built the opening still with nano-banana from two photographs and then
swapped the real face onto it with `fal-ai/face-swap`; the second gave all three photographs to
a GPT image model (`fal-ai/gpt-image-1.5/edit`, `input_fidelity` high, `quality` high,
`1536x1024`) and asked for one film still. The swap route produced a face that reads as pasted:
the skin tone stops at the jaw, the head sits a little wrong on the neck, and the kitchen behind
it is a bare showroom because nano-banana draws what the prompt names and nothing more. The
GPT route produced a face the user's friend would be recognised by, on a body that belongs to
it, in a kitchen with a fruit bowl, photographs on the fridge and a window onto a real street,
and it took one call of about a minute. The user, shown both films, asked for the second method
to be learned. So:

- Build a photographed character's still with a reference-taking image model and every good
  photograph at once, and only then think about a swap. Say in the prompt that all attached
  photographs are identity references of the SAME person and not edit targets; list the features
  that must survive (face length and jaw, nose, eyes, the glasses, the hair as it actually grows,
  "closely cut sides, irregular upstanding top", not "spiky"); forbid the model's reflexes by name
  (no beautification, slimming, widening, age change, airbrushed skin, no straight fringe). A swap
  stays the repair for a face the edit idealised away, not the first move.
- Do not overstate a feature. "Full cheeks" written once made the generated face rounder and
  shorter than the man's, and the user's first comment was that the face should be longer. Describe
  proportions from the photographs, or say nothing and let the references carry them.
- Put the still in mid-action and looking off frame ("setting the mug down with one hand, head
  already turned toward a television outside the frame, a brief incredulous half smile") rather
  than posing for the camera. A still that already contains the first beat gives image-to-video
  somewhere to go in the first half second, and the eye-line is cut-ready.
- Ask for a lived-in background in words ("slightly messy lived-in kitchen") and pin the lens
  (50mm), the light (soft overcast morning) and the wardrobe; the GPT model fills the world when
  told the world is there, and a bare set is what you get when you forget.
- Then shoot a five-second motion test from that still before any batch: put a real action in the
  first half second, a turn of the eyes at a stated time, a brief half smile, the remote picked up
  and pressed at stated seconds, and write "no long pauses, no slow push-in, no mug remaining in
  hand after being set down". Judge the test on a frame sheet and show it to the user; expressions
  come out a size too large by default, so the next prompt asks for restraint ("eyes move first,
  hold half a beat, then the remote; face stays quiet").
- The image model's endpoint takes `image_size` in pixels (`1536x1024`, `1024x1536`,
  `1024x1024`) rather than an aspect ratio, and accepts `jpeg` output; `FalImageGenerator` maps the
  ratio when the model name contains `gpt-image`, so `--image-edit-model fal-ai/gpt-image-1.5/edit`
  is the only switch. The balance endpoint lagged the charge, so count the call at roughly a fifth
  of a dollar until the ledger catches up.

## Screens, broadcasts and readable text

- A television inside the shot is best built as a still first. `nano-banana/edit` with the room
  frame as the first reference and a photograph as the second, and a prompt that begins "keep this
  photograph exactly as it is, change only what is on the television screen", returns the same
  room with a new broadcast on the set: studio, presenter, logo, lower third, and the supplied
  photograph inset. The video model then keeps that picture steady and lip-syncs the presenter to
  the quoted line. Spelling on the graphics fails about half the time ("SMEDEN", "BRSAKING", a
  channel number off by two), so request two takes, crop the screen region and enlarge it before
  choosing, and re-run rather than accept a misspelt strap.
- One video shot can carry two channel changes. Give the start frame with channel A on the set and
  the end frame with channel B, quote both presenters' lines with their own clocks, and put the
  press of the remote at the switch; the model flips the picture on the press and keeps both
  broadcasts stable. Cutting to a face between such shots is what lets the next shot start on a
  different channel without a visible switch.
- The still editor rarely moves the camera when told to keep everything else. "Rebuild from a new
  camera position" with a long "keep the same" clause came back at the same angle; the same
  request that rebuilt the whole composition (a low view from a counter with new foreground props)
  succeeded. For a second, tighter setup on an existing frame, crop the frame (about 75 percent)
  and upscale it with lanczos instead: the start and end frames stay identical in every detail and
  the shot reads as a new lens.
- A single-change edit fixes prop continuity cheaply: "remove the mug from his left hand, his hand
  hangs empty, everything else identical" returns the same frame without the mug, and the video
  shot from it inherits the fix. Check continuity across the whole cut before shooting, not after:
  a prop set down in one shot must be gone from every later start frame.
- A phone whose notifications must be read on screen belongs in a close-up of its own. Asked for
  "dozens of notifications, one card legible" in a wide shot, the video model twice rendered the
  cards as panels floating in the air above the handset, and a prompt forbidding it did not help.
  In the wide shot describe only the glass lighting up and a list too small to read; give the
  legible card to a macro insert built from a still (the still editor writes the sentence correctly
  at that size) and generate the insert with `end_image_url` alone, so the clip animates a dark
  screen into that exact final frame.
- A dense shot is not a blurred shot. Five to ten seconds carry a full arc (a stare, a laugh, a
  glance down, a press, a change of light) when each beat has its own clock; the same shot written
  with one gesture returns as a slow push-in and reads as slow motion to the viewer. Write the
  beats, and let a shot be cut only when it ends on the image the next shot starts from.
- Whisper transcribes a muffled off-screen television as fluent sentences in whatever language you
  ask for. Treat a transcript of "no intelligible words" audio as noise, and judge a presenter's
  line only from the shot where the set is on screen.

## Product films: real screens, generated world

- A screen recording from the Android emulator (`adb shell screenrecord`) only emits a frame when
  the screen changes, so its timeline has gaps; seek into it with `-ss` and the cut opens on black
  until the next change. Convert every recording to constant frame rate first
  (`ffmpeg -vf fps=30 -fps_mode cfr`), then cut. On a watch emulator the swipe-to-dismiss from the
  list screen also leaves the app, so start every recorded beat from a known screen and count the
  dismissals back.
- The same recorder gives a one-frame file for a screen that never changes, and the constant-rate
  conversion of that is empty. A static beat (a library list, a settings page) is a screenshot
  turned into a clip with `ffmpeg -loop 1 -framerate 30 -t 2.5 -i shot.png`, with the tap ripple
  drawn on top as usual.
- Join segments with the `concat` filter in one encode, not the concat demuxer with `-c copy`. The
  copied segments kept their own timestamps; the container reported the full length, and yet a
  frame sampler and a player both saw only the last few seconds. `setpts=N/30/TB` on the demuxer
  output was worse, it folded 27 seconds into 10. `[0:v][1:v]...concat=n=N:v=1:a=0,fps=30` gives
  clean timestamps every time.

## Broadcast look: render graphics locally, let the model shoot only the picture

- Ask the video model for a clean anchor or field reporter with the person on the LEFT third, the bottom fifth of the frame empty, and "no on-screen text, no lower third, no logo". It obeys almost every time, and the generated speech in Swedish, English, Russian, Japanese and Arabic came out correct on the first take when the line was given verbatim in quotes.
- Bugs, lower thirds, tickers, clocks and a framed file-photo box are drawn with PIL at the final resolution and overlaid with ffmpeg. Spelling is then guaranteed, every language works (Arabic via arabic-reshaper + python-bidi, Japanese via Hiragino), and the ticker scrolls with an overlay x expression across a whole block so it stays continuous through cuts.
- A studio shot with an empty panel and a static camera takes a pasted graphic directly (gradient background, portrait, caption). No tracking needed.
- Four elements are enough to read as a real channel: bug top-left, lower third, ticker for the 24-hour channels, and a full-screen file-photo slate with a slow zoom. Cutting to the slate mid-sentence while the anchor audio continues is exactly what real news does and hides the seam.
- Identity of a real person: generate the scene still with the reference photos, then face-swap the real face onto the still before image-to-video. The prompt alone kept giving a rounder, shorter face; the swap locks the true proportions and the motion model carries them.
- Phone screens: generate the phone dark, then composite the UI locally with a perspective warp into the screen quad, keep a little of the original glass reflection, light the screen up over a few frames, jitter the frame during vibration and push in slowly. Legible and no floating cards.
- Music under a montage: sidechain-compress the music with the dialogue track as key, then two-pass loudnorm. Add faint pink-noise room tone so quiet kitchen beats are not digital silence.

## Running a whole film unattended

- A film is a queue, not a conversation. Write every shot's prompt first, then hand the entire list
  to one runner and let it work through them: start frame, motion, log the failure and go on to the
  next. Stopping after six shots to show progress and waiting to be told to continue wastes hours
  and makes the person watch the machine. Generation is cheap enough to run the whole film in one
  pass and review the result.
- The runner reads three small files per shot: the still prompt, the motion prompt, and a `who`
  file naming which identity references to attach and how many seconds to generate. A shot that
  needs no face skips the reference model entirely and goes to text-to-image.
- A slot longer than one generation is two segments, and the second one opens on the last clean
  frame of the first (`ffmpeg -ss <duration - 0.12>`), so the look does not change across the join.
  The same trick chains a sustained moment across several cuts: the final three shots of a film
  that ends on one long look were generated as one continuous take in three pieces, each starting
  where the last ended, with the world dimming and the light arriving over the run.
- Skip any shot whose output already exists. Reruns then cost nothing, and a failed shot can be
  retried by deleting one file rather than regenerating the batch.
- Keep the assembly in a second script that reads the slot lengths from the shot table and cuts
  each clip to its slot. Re-encode the cuts rather than copying: copied streams keep their own
  timestamps and the concatenated file plays wrong even when the container reports the right length.

## What a film actually costs

- Price the two steps separately before planning a film, because they are charged on different
  axes and the cheaper-looking one is usually the larger bill. Video is charged per second of
  output: a six-second clip at 768P is a quarter of the price of the same clip at 1080P, and the
  rate can be sitting under a temporary promotion that will end. Images are charged per image and
  per quality tier, and the top tier is roughly four times the middle one at the same size.
- A three-minute film is not one bill, it is about eighty: thirty-four shots, a tail segment for
  every shot longer than one generation, a start frame for each, plus the casting rounds and the
  shots that get redone. Count the generations before starting, not after.
- Ask for the expensive image tier only where a face carries the shot. A wide, a back, an empty
  room, a sky and a crowd look the same at the middle tier, and on a thirty-four shot film two
  thirds of the frames are in that group.
- Reference photographs are charged as input on every still that carries them. Three photographs
  place a face as well as five; the extra two are paid for on every shot they are attached to.
- Uploading references to the provider's own storage adds a dependency that fails on its own
  schedule: when the account was locked the storage endpoint began answering 403 while the models
  still ran, so the queue died on an error that named the wrong cause. Send references inline as
  data URIs and the step has one fewer way to break.
- A queue that hits an exhausted balance keeps going and logs one failure per remaining shot, so
  the first failure is the only one worth reading. Check the earliest error in the log, not the
  last.

