# From aggregate scores to evidence-producing video tests

InkToFilm is built around a simple distinction: a benchmark ranks models, while a test tells a model
developer what broke.

## The unit of evaluation

An InkToFilm case binds four things:

1. an input prompt or conditioning artifact;
2. a generated video;
3. explicit expectations and thresholds;
4. findings tied to inspectable evidence.

A finding should ideally locate its evidence in time and, where appropriate, space. “Identity score
0.61” is less actionable than “the tracked subject changes appearance between 4.2 and 5.8 seconds.”

## Evidence schema

Version 0.1 supports temporal intervals. Later schema revisions can add normalized regions, frame
references, comparison pairs, evaluator configuration, uncertainty, and human calibration data while
retaining backward-compatible JSON reports.

Every learned evaluator should report:

- model and revision;
- complete judge prompt or stable prompt hash;
- input sampling policy;
- scalar value and decision threshold;
- supporting frame or interval evidence;
- calibration set and agreement, when available.

## Proposed semantic probe families

### Entity persistence

Detect and track prompt-mentioned entities. Compare embeddings and structured attributes across
unoccluded track segments. Treat legitimate viewpoint and lighting changes separately from identity
drift.

### Event execution

Translate the prompt into ordered observable events, then test whether each event occurred and
whether their order was preserved. Report missing, duplicated, and reversed events rather than only
prompt alignment.

### Camera and scene grammar

Estimate global motion, cuts, and focal changes. Test explicit camera instructions and distinguish a
camera move from independent foreground motion.

### Physical and causal consistency

Track object permanence, contact, support, collision, and state change. Prefer controlled prompt
pairs that differ in one causal factor, making regressions easier to attribute.

### Long-horizon memory

Measure whether entities, environment state, and consequences survive beyond the model's easiest
short window. Tests should disclose the horizon at which the first contradiction appears.

## Human calibration

Automated judges must periodically be checked against blinded pairwise human decisions. InkToFilm
should preserve both judgments, disagreements, and confidence rather than overwriting one with the
other. The goal is a diagnostic instrument, not a cosmetically precise score.
