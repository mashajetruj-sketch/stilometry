---
name: style-prompt-compiler
description: Compile approved evidence into abstract style constraints.
---
Require immutable approval and evidence references. Emit `must`, `must_not`, and `tests`; preserve uncertainty and negative constraints. Strip raw quotes and PII. Reject persona, diagnosis, attribution, generic AI filler and invented evidence.
Use when compiling an approved evidence-bound style prompt.
Do NOT use when approval is absent, evidence is invalid, or the goal is person imitation or attribution.
## Do NOT apply
Do NOT apply before immutable human approval, to raw corpus, for author attribution, personality diagnosis, or when network/privacy gates fail.
## Write boundary
Write only approved prompt artifacts under `stilometry-memory/runs/`; network is denied by default.
