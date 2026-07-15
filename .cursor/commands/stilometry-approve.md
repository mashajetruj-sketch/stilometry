# /stilometry-approve
Use when a human reviewer explicitly approves a validated draft or revised draft.
Do NOT use when approval is inferred from chat context or reviewer identity is absent.
Require an explicit reviewer and validated `status: draft` or `status: revised_draft`; create immutable approval event with timestamp and input hash. Chat context cannot approve.
CLI: `python stilometry.py approve runs/draft.json --reviewer NAME`.
