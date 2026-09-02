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
- Give every action a clock: "within the first half second", "at the midpoint", "in the final
  second". Untimed action either never arrives or is spent on a wind-up, and a shot with no timed
  beat comes back as a slow push-in on people holding a pose.
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
