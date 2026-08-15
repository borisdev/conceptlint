# Domain language

Three rules. No tool can check any of them — they happen in prose, before any file is written.

## 1. Before inventing a noun, look for one that exists

Reuse it. Refine it when it is close but too broad. Add a new word only when the distinction changes
behaviour, invariants, composition, serialisation or provenance.

**The trigger, which fires on its own:** when a conversation repeatedly needs *"by X here I mean…"*,
that is a missing type, not a wording problem.

Ask the repo rather than reconstructing it from memory:

```bash
conceptlint .          # duplicate, overloaded, drifting
```

## 2. Speak the same words in prose as in code

Do not drift between `run` / `execution` / `activity` / `job` / `task` / `step` / `workflow` /
`dataflow` unless they are genuinely interchangeable. If two words mean different things, that is a
missing type. If they mean the same thing, use the one the code uses.

⚠️ This is the rule most often broken, and the only one nothing can catch. It happens in a sentence,
not a file — a linter reads code and never hears you say the wrong word for a week.

## 3. Propose language changes; do not make them

When the vocabulary genuinely cannot express something, say so and let a human decide. Renaming a
type, or introducing a new word for an existing thing, is a proposal — not an implementation detail
to be reported afterwards.

A language that grows to make one task easier is a synonym list.
