# Writing the script

The film is decided in the script, before a still is rendered or a second of video is paid for.
Two scripts for the same one-minute comedy, a day apart, made the point. The first kept one man
alone with his television through three identical rounds; it measured his kitchen to the
centimetre and timed his thumb to the tenth of a second, and the film it produced was judged slow,
thin and "one man sitting in front of a television". The rewrite kept the measuring and the timing
and changed what was scheduled: it put the world outside the kitchen on screen, cut every one to
three seconds on an action, planned the sound as beats with one music bed, and gated the money
behind a likeness test. The user called that film obviously better, faster, fuller of detail, with
music on the beat, and asked for its method to be learned. This page is that method. Read it
before writing `script.md`, and write the script in the user's language.

## The shape of the document

1. **The engine, in one sentence.** What the film is about as a mechanism, not a synopsis:
   "the whole world is already celebrating, and the one person in the kitchen is the only one who
   does not know yet." Every later choice is checked against this line. Follow it with the hard
   numbers: target length, aspect ratio, resolution, "real-time speed throughout".
2. **The structure at a glance.** A table with one row per shot: id, length, camera position, and
   the one thing that is on screen or on the television. A reader should see the rhythm here
   before reading a word of prose, including the alternation that makes the film breathe (three
   rounds of "look at the television, then back to his face"; a beat every one to three seconds
   with the longer holds reserved for a full spoken line or a reaction).
3. **The world, measured.** Character and set in physical units, not adjectives. The costume down
   to "stone-grey unprinted long-sleeve shirt, left cuff folded once"; the posture ("right hip
   against the counter, weight on the right; two fingers through the mug handle, thumb on top of
   it; on the remote only the thumb moves"); the room in square metres and the objects on the
   counter one by one, including what is in the sink from last night; the television's size, age,
   bezel width and the scuff on its corner; the distance from him to it; the window's width and
   what is outside it; the season and the light in kelvin, with why ("6500K window light, white
   balance 5600K, so the walls go cool while the skin keeps its blood"); no ceiling lights; the
   room tone (refrigerator compressor, dripper, tyres on a wet road); how far the steam rises
   before it disperses. "Not a staged mess, not a hotel-empty counter." Say where text is not
   allowed (no calendars, no book spines, no labels), because the model will otherwise invent it.
4. **How it will be shot.** Which shots are image-to-video and which text-to-video, and the
   continuity rule in one line ("every room shot starts from the previous shot's last clean frame,
   before any compositing; a composited frame never goes back into the generator"). The locked
   framings with percentages ("his head and shoulder in the left fifteen percent, the television at
   seventy percent of frame width, all four corners visible, perspective within ten degrees"). What
   the generator must leave blank for post ("the screen is an even pale glow; every channel, logo,
   caption and photograph is composited later"). Where the face must be large ("A1 and A7 carry the
   likeness: face at least forty percent of frame height"). Whose faces are fictional.
5. **The shots, one by one.** Each shot gets a title that names its beat ("Coffee still dripping",
   "Two countries, one story", "The first time he does not believe it"), a paragraph of prose
   written physically, as if describing footage that already exists, and then a technical line:
   lens, camera height, aperture, focus behaviour, and a timeline to the tenth of a second
   ("0.0-0.5 already pouring the last stream; 1.1 water stops; 1.5 kettle lands on the cork mat;
   1.6-2.2 dripper moved onto the towel; 2.2-2.7 left hand lifts the mug, right hand takes the
   remote; 2.7-7.0 camera travels round his right side to the rear shoulder; 7.2 thumb presses
   power; 7.35 cool light reaches his fingers; 7.6 framing locks; hold to 8.0"). The timeline is
   what the prompt is later built from, so it must be complete: a second with nothing written in it
   is a second the model fills with a slow push-in and a blink.
6. **The sound plan.** Which noises are the edit's beats (grinder switch, remote click, mug on wood,
   the crowd's cheer, the phone's vibration). Whether there is music, and if so: one continuous
   original instrumental bed made once, tightening as the film goes, ducked under every spoken
   line, and pulled out hard at the turn; every generated shot carries native sound only, never its
   own music, so that clips do not fight at the cuts. Write the music to the film's clock: name
   the second of the climax in the script, and the bed's loudest bar has to land on that second,
   not somewhere near it. A generated bed does not know where your climax is, so measure it
   (`inktofilm music-peak bed.mp3 --climax 47.0` prints where its loudest half second falls and
   the offset that puts it on the cut) and slide or trim the bed, or nudge the cut by a few frames,
   until the two coincide; then the drop or the hard stop that follows is the reveal, and the
   viewer feels the film hit rather than drift. Which lines are in which language and the rule
   that each is transcribed and checked. What the final mix is checked for: a line cut off, a
   line buried, a silent tail, an audio stream shorter than the picture, and a music peak that
   arrives before or after the picture's.
7. **Acceptance gates and the budget.** What must be looked at and approved before the next stage
   spends money: the character still, then a five-second motion test, then the batch. What counts
   as failure at each gate ("a still that is not him, a test in which nothing happens in the first
   second, a crowd that is a wall of clones"). The approved cap, what has been reserved against it,
   and the rule that a request id is saved before a result is trusted and a failed request is
   never resubmitted blindly. Put these in the script or in an `ACCEPTANCE.md` beside it, and
   never let the assembly step decide them.

## Where scale and pace come from

- Scale is a set of places, not a longer list of anchors. A campaign headquarters seen from inside
  with foreground, middle ground and background all moving; a square outside a stone civic
  building with flags at different heights and a news van behind; a reporter in front of a crowd
  with a camera crew crossing the foreground; a corridor of press flashes. Write each as its own
  layered shot with its own action at its own second, and cut between them under one sentence of
  broadcast audio.
- Pace is beats, not speed. One to three seconds per visual beat, cut on an action (the click, the
  mug set down, the head turn), a spoken line allowed to run across two or three pictures. Never
  speed up a clip to fake tempo, never rely on rapid unmotivated cuts or a loud track to disguise a
  scene in which nothing happens.
- Comedy of contrast is staged in the body. The world in uproar; in the kitchen a mug rises two
  centimetres and stops. Write the small movement to the centimetre and forbid the large one
  ("no head shake, no smile, no widened eyes, mouth stays closed").
- The reveal is written as a sound event. The crowd peaks, the music stops, the room tone is all
  that is left, and the phone vibrates against the counter half a second later, the liquid in the
  mug trembling. Then the picture cuts.

## From script to prompt

- Every prompt of a film opens with the same verbatim sentence ("Photorealistic live-action,
  real-time speed, natural motion blur, physically grounded human movement, 16:9, 768P.") so the
  clips share a look. Then lens, height, aperture, focus behaviour; light with its kelvin; the
  air and the physics (steam, cloth creasing with breath, hair moving only with the head).
- A continued shot says "Match the input frame exactly:" followed by the list of what must not
  drift (identity, wardrobe, body position, mug grip and liquid level, remote angle, room
  geometry, exposure, camera). Then the framing percentages again. Then the timeline, verbatim
  from the script, with what does not move stated as an action ("from 5.0 to 10.0 nothing moves
  but breathing; the mug stays where it is and he does not turn").
- End every prompt with the audio list and the negatives, in that order: native sounds it may
  produce, "no intelligible speech, no music", then "no text anywhere in frame, no captions, no
  subtitles, no logos" and what the screen must be instead.
- A crowd prompt names the layers (nearby moving people, a dense middle ground, architecture and
  the van behind), gives two or three timed events (a photographer raising a camera, two friends
  embracing, the crew crossing at the midpoint, a wide glimpse at the end), and forbids the stock
  failures by name: no slow motion, no clone faces, no confetti wall, no giant American-style
  rally, no recognisable public figure, no readable signs.
